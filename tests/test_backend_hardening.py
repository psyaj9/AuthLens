import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class BackendHardeningTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.server_dir = self.project_root / "server"
        self.original_cwd = Path.cwd()
        self.original_path = list(sys.path)
        os.chdir(self.server_dir)
        sys.path.insert(0, str(self.server_dir))
        self._clear_server_modules()

    def tearDown(self):
        self._clear_server_modules()
        sys.path[:] = self.original_path
        os.chdir(self.original_cwd)

    def _clear_server_modules(self):
        for module_name in [
            "main",
            "modules.config",
            "modules.security",
            "routes.health",
            "routes.queries",
            "routes.upload_pdf",
        ]:
            sys.modules.pop(module_name, None)

    def _client(self):
        main = importlib.import_module("main")
        return TestClient(main.app)

    def _query_dependencies(self):
        queries_module = importlib.import_module("routes.queries")
        index = MagicMock()
        index.query.return_value = SimpleNamespace(
            matches=[
                {
                    "metadata": {
                        "text": "Sensitive document chunk",
                        "source": "DIABETES.pdf",
                    }
                }
            ]
        )
        embeddings = MagicMock()
        embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        return queries_module, index, embeddings

    def test_health_is_public_and_does_not_check_external_services(self):
        with patch.dict(os.environ, {"INTERNAL_API_TOKEN": "secret"}, clear=False):
            client = self._client()

            with patch("pinecone.Pinecone") as pinecone_cls:
                response = client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "authlens-api",
                "environment": "development",
                "dependencies": {
                    "pinecone": "not_checked",
                    "groq": "not_checked",
                    "google": "not_checked",
                },
            },
        )
        pinecone_cls.assert_not_called()

    def test_cors_uses_default_localhost_origins_without_wildcard_credentials(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            client = self._client()

            allowed = client.options(
                "/api/health/",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
            disallowed = client.options(
                "/api/health/",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertEqual(allowed.headers["access-control-allow-credentials"], "true")
        self.assertNotEqual(disallowed.headers.get("access-control-allow-origin"), "*")
        self.assertNotEqual(
            disallowed.headers.get("access-control-allow-origin"),
            "https://evil.example",
        )

    def test_cors_uses_allowed_origins_from_environment(self):
        with patch.dict(
            os.environ,
            {"ALLOWED_ORIGINS": "https://app.example.com, http://localhost:3000"},
            clear=False,
        ):
            client = self._client()
            response = client.options(
                "/api/health/",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.headers["access-control-allow-origin"], "https://app.example.com")

    def test_cors_rejects_wildcard_origins_with_credentials(self):
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "*"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "ALLOWED_ORIGINS cannot include wildcard"):
                self._client()

    def test_unhandled_errors_use_error_response_shape(self):
        main = importlib.import_module("main")

        @main.app.get("/boom")
        async def boom():
            raise RuntimeError("Sensitive failure")

        client = TestClient(main.app)
        response = client.get("/boom")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Internal Server Error"})

    def test_internal_token_protects_upload_and_query_but_not_health(self):
        with patch.dict(os.environ, {"INTERNAL_API_TOKEN": "secret"}, clear=False):
            client = self._client()

            upload_response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("doc.pdf", b"%PDF-1.4", "application/pdf"))],
            )
            query_response = client.post(
                "/api/queries/",
                data={"user_query": "what is diabetes?"},
            )
            health_response = client.get("/api/health/")

        self.assertEqual(upload_response.status_code, 401)
        self.assertEqual(upload_response.json(), {"error": "Unauthorized"})
        self.assertEqual(query_response.status_code, 401)
        self.assertEqual(query_response.json(), {"error": "Unauthorized"})
        self.assertEqual(health_response.status_code, 200)

    def test_internal_token_allows_authorized_query_with_existing_wire_shape(self):
        with patch.dict(os.environ, {"INTERNAL_API_TOKEN": "secret"}, clear=False):
            client = self._client()
            queries_module, index, embeddings = self._query_dependencies()

            with patch.object(
                queries_module, "get_pinecone_index", return_value=(index, "auth-index")
            ), patch.object(
                queries_module, "get_embeddings", return_value=embeddings
            ), patch.object(
                queries_module, "get_llm", return_value=object()
            ), patch.object(
                queries_module,
                "handle_query_chain",
                return_value={
                    "response": "Diabetes is a chronic condition.",
                    "source_documents": ["DIABETES.pdf"],
                },
            ):
                response = client.post(
                    "/api/queries/",
                    data={"user_query": "what is diabetes?"},
                    headers={"Authorization": "Bearer secret"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "response": "Diabetes is a chronic condition.",
                "source_documents": ["DIABETES.pdf"],
            },
        )

    def test_upload_rejects_non_pdf_files_before_indexing(self):
        client = self._client()
        upload_module = importlib.import_module("routes.upload_pdf")

        with patch.object(upload_module, "load_vector_store") as load_vector_store:
            response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("notes.txt", b"hello", "text/plain"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Only PDF uploads are allowed."})
        load_vector_store.assert_not_called()

    def test_upload_rejects_pdf_extension_with_non_pdf_bytes_before_indexing(self):
        client = self._client()
        upload_module = importlib.import_module("routes.upload_pdf")

        with patch.object(upload_module, "load_vector_store") as load_vector_store:
            response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("notes.pdf", b"not a pdf", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Only valid PDF uploads are allowed."})
        load_vector_store.assert_not_called()

    def test_upload_rejects_path_like_filenames_before_indexing(self):
        client = self._client()
        upload_module = importlib.import_module("routes.upload_pdf")

        with patch.object(upload_module, "load_vector_store") as load_vector_store:
            response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("../patient.pdf", b"%PDF-1.4", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Uploaded filename is not allowed."})
        load_vector_store.assert_not_called()

    def test_upload_rejects_empty_filenames_before_indexing(self):
        client = self._client()
        upload_module = importlib.import_module("routes.upload_pdf")

        with patch.object(upload_module, "load_vector_store") as load_vector_store:
            response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("   ", b"%PDF-1.4", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Uploaded file must have a filename."})
        load_vector_store.assert_not_called()

    def test_upload_rejects_file_count_over_environment_limit(self):
        with patch.dict(os.environ, {"MAX_UPLOAD_FILES": "1"}, clear=False):
            client = self._client()
            upload_module = importlib.import_module("routes.upload_pdf")

            with patch.object(upload_module, "load_vector_store") as load_vector_store:
                response = client.post(
                    "/api/upload_pdf/",
                    files=[
                        ("uploaded_files", ("one.pdf", b"%PDF-1.4", "application/pdf")),
                        ("uploaded_files", ("two.pdf", b"%PDF-1.4", "application/pdf")),
                    ],
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Upload limit exceeded. Maximum files allowed: 1."})
        load_vector_store.assert_not_called()

    def test_upload_rejects_file_size_over_environment_limit(self):
        with patch.dict(os.environ, {"MAX_UPLOAD_MB": "1"}, clear=False):
            client = self._client()
            upload_module = importlib.import_module("routes.upload_pdf")

            with patch.object(upload_module, "load_vector_store") as load_vector_store:
                response = client.post(
                    "/api/upload_pdf/",
                    files=[
                        (
                            "uploaded_files",
                            (
                                "large.pdf",
                                b"%PDF-" + (b"x" * (1024 * 1024 + 1)),
                                "application/pdf",
                            ),
                        )
                    ],
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "File large.pdf exceeds 1 MB upload limit."})
        load_vector_store.assert_not_called()

    def test_upload_accepts_pdf_filename_without_consuming_stream(self):
        client = self._client()
        upload_module = importlib.import_module("routes.upload_pdf")
        observed_payloads = []

        def load_and_read(uploaded_files):
            observed_payloads.append(uploaded_files[0].file.read())

        with patch.object(upload_module, "load_vector_store", side_effect=load_and_read):
            response = client.post(
                "/api/upload_pdf/",
                files=[("uploaded_files", ("doc.pdf", b"%PDF-stream", "application/octet-stream"))],
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Files uploaded and processed successfully."})
        self.assertEqual(observed_payloads, [b"%PDF-stream"])

    def test_upload_rejection_logs_do_not_include_filename_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "MAX_UPLOAD_MB": "1"}, clear=False):
            client = self._client()
            upload_module = importlib.import_module("routes.upload_pdf")

            with patch.object(upload_module, "load_vector_store") as load_vector_store:
                with self.assertLogs(upload_module.logger, level="WARNING") as logs:
                    response = client.post(
                        "/api/upload_pdf/",
                        files=[
                            (
                                "uploaded_files",
                                (
                                    "uploaded-sensitive-name.pdf",
                                    b"x" * (1024 * 1024 + 1),
                                    "application/pdf",
                                ),
                            )
                        ],
                    )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Upload rejected."})
        self.assertEqual(load_vector_store.call_count, 0)
        self.assertNotIn("uploaded-sensitive-name.pdf", "\n".join(logs.output))

    def test_queries_suppresses_sensitive_content_logs_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            client = self._client()
            queries_module, index, embeddings = self._query_dependencies()

            with patch.object(
                queries_module, "get_pinecone_index", return_value=(index, "auth-index")
            ), patch.object(
                queries_module, "get_embeddings", return_value=embeddings
            ), patch.object(
                queries_module, "get_llm", return_value=object()
            ), patch.object(
                queries_module,
                "handle_query_chain",
                return_value={
                    "response": "Diabetes is a chronic condition.",
                    "source_documents": ["DIABETES.pdf"],
                },
            ), self.assertLogs(queries_module.logger, level="INFO") as logs:
                response = client.post(
                    "/api/queries/",
                    data={"user_query": "what is diabetes?"},
                )

        self.assertEqual(response.status_code, 200)
        log_text = "\n".join(logs.output)
        self.assertNotIn("what is diabetes?", log_text)
        self.assertNotIn("Diabetes is a chronic condition.", log_text)
        self.assertNotIn("Sensitive document chunk", log_text)

    def test_query_errors_do_not_leak_exception_details_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            client = self._client()
            queries_module, index, embeddings = self._query_dependencies()

            with patch.object(
                queries_module, "get_pinecone_index", return_value=(index, "auth-index")
            ), patch.object(
                queries_module, "get_embeddings", return_value=embeddings
            ), patch.object(
                queries_module, "get_llm", return_value=object()
            ), patch.object(
                queries_module,
                "handle_query_chain",
                side_effect=RuntimeError("vendor timeout with sensitive context"),
            ):
                response = client.post(
                    "/api/queries/",
                    data={"user_query": "what is diabetes?"},
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Unable to process query."})

    def test_upload_errors_do_not_leak_exception_details_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            client = self._client()
            upload_module = importlib.import_module("routes.upload_pdf")

            with patch.object(
                upload_module,
                "load_vector_store",
                side_effect=RuntimeError("filesystem path with sensitive context"),
            ):
                response = client.post(
                    "/api/upload_pdf/",
                    files=[("uploaded_files", ("doc.pdf", b"%PDF-1.4", "application/pdf"))],
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Unable to process upload."})


if __name__ == "__main__":
    unittest.main()
