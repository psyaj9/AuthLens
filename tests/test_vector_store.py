import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.server_dir = self.project_root / "server"
        self.original_path = list(sys.path)
        sys.path.insert(0, str(self.server_dir))
        sys.modules.pop("modules.vector_store", None)
        self.vector_store = importlib.import_module("modules.vector_store")

    def tearDown(self):
        sys.modules.pop("modules.vector_store", None)
        sys.path[:] = self.original_path

    def test_get_pinecone_index_creates_serverless_vector_index_with_current_sdk(self):
        env_values = {
            "GOOGLE_API_KEY": "test-google-key",
            "PINECONE_API_KEY": "test-pinecone-key",
            "PINECONE_ENVIRONMENT": "us-east-1",
            "PINECONE_INDEX_NAME": "authlens-test",
        }
        pc = MagicMock()
        pc.list_indexes.return_value = []
        pc.indexes.describe.return_value = SimpleNamespace(
            status=SimpleNamespace(ready=True)
        )
        index = object()
        pc.index.return_value = index

        with patch.dict(os.environ, env_values), patch.object(
            self.vector_store, "Pinecone", return_value=pc
        ):
            actual_index, index_name = self.vector_store.get_pinecone_index()

        self.assertIs(actual_index, index)
        self.assertEqual(index_name, "authlens-test")
        pc.indexes.create.assert_called_once()
        create_kwargs = pc.indexes.create.call_args.kwargs
        self.assertEqual(create_kwargs["name"], "authlens-test")
        self.assertEqual(create_kwargs["dimension"], 768)
        self.assertEqual(create_kwargs["metric"], "cosine")
        pc.index.assert_called_once_with("authlens-test")
        pc.create_index.assert_not_called()
        pc.Index.assert_not_called()

    def test_load_vector_store_includes_chunk_text_in_pinecone_metadata(self):
        document = SimpleNamespace(page_content="First chunk", metadata={"source": "doc.pdf"})
        upload = SimpleNamespace(
            filename="doc.pdf",
            file=SimpleNamespace(read=lambda: b"%PDF-test"),
        )
        index = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            self.vector_store, "UPLOAD_DIR", Path(tmpdir)
        ), patch.object(
            self.vector_store, "get_pinecone_index", return_value=(index, "authlens-test")
        ), patch.object(
            self.vector_store, "PyPDFLoader"
        ) as loader_cls, patch.object(
            self.vector_store, "RecursiveCharacterTextSplitter"
        ) as splitter_cls, patch.object(
            self.vector_store, "GoogleGenerativeAIEmbeddings"
        ) as embeddings_cls, patch.object(
            self.vector_store, "tqdm"
        ) as tqdm_cls:
            loader_cls.return_value.load.return_value = [document]
            splitter_cls.return_value.split_documents.return_value = [document]
            embeddings_cls.return_value.embed_documents.return_value = [[0.1, 0.2, 0.3]]
            tqdm_cls.return_value.__enter__.return_value = MagicMock()

            self.vector_store.load_vector_store([upload])

        embeddings_cls.assert_called_once_with(
            model="gemini-embedding-2-preview",
            output_dimensionality=768,
        )
        vectors = index.upsert.call_args.kwargs["vectors"]
        self.assertEqual(vectors[0][2]["text"], "First chunk")
        self.assertEqual(vectors[0][2]["source"], "doc.pdf")

    def test_load_vector_store_removes_saved_upload_after_indexing(self):
        document = SimpleNamespace(page_content="First chunk", metadata={"source": "doc.pdf"})
        upload = SimpleNamespace(
            filename="doc.pdf",
            file=SimpleNamespace(read=lambda: b"%PDF-test"),
        )
        index = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            self.vector_store, "UPLOAD_DIR", Path(tmpdir)
        ), patch.object(
            self.vector_store, "get_pinecone_index", return_value=(index, "authlens-test")
        ), patch.object(
            self.vector_store, "PyPDFLoader"
        ) as loader_cls, patch.object(
            self.vector_store, "RecursiveCharacterTextSplitter"
        ) as splitter_cls, patch.object(
            self.vector_store, "GoogleGenerativeAIEmbeddings"
        ) as embeddings_cls, patch.object(
            self.vector_store, "tqdm"
        ) as tqdm_cls:
            loader_cls.return_value.load.return_value = [document]
            splitter_cls.return_value.split_documents.return_value = [document]
            embeddings_cls.return_value.embed_documents.return_value = [[0.1, 0.2, 0.3]]
            tqdm_cls.return_value.__enter__.return_value = MagicMock()

            self.vector_store.load_vector_store([upload])

            self.assertFalse((Path(tmpdir) / "doc.pdf").exists())

    def test_load_vector_store_does_not_log_filename_in_production(self):
        document = SimpleNamespace(
            page_content="First chunk",
            metadata={"source": "sensitive-name.pdf"},
        )
        upload = SimpleNamespace(
            filename="sensitive-name.pdf",
            file=SimpleNamespace(read=lambda: b"%PDF-test"),
        )
        index = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"ENVIRONMENT": "production"},
            clear=False,
        ), patch.object(
            self.vector_store, "UPLOAD_DIR", Path(tmpdir)
        ), patch.object(
            self.vector_store, "get_pinecone_index", return_value=(index, "authlens-test")
        ), patch.object(
            self.vector_store, "PyPDFLoader"
        ) as loader_cls, patch.object(
            self.vector_store, "RecursiveCharacterTextSplitter"
        ) as splitter_cls, patch.object(
            self.vector_store, "GoogleGenerativeAIEmbeddings"
        ) as embeddings_cls, patch.object(
            self.vector_store, "tqdm"
        ) as tqdm_cls, self.assertLogs(
            self.vector_store.logger,
            level="INFO",
        ) as logs:
            loader_cls.return_value.load.return_value = [document]
            splitter_cls.return_value.split_documents.return_value = [document]
            embeddings_cls.return_value.embed_documents.return_value = [[0.1, 0.2, 0.3]]
            tqdm_cls.return_value.__enter__.return_value = MagicMock()

            self.vector_store.load_vector_store([upload])

        self.assertNotIn("sensitive-name.pdf", "\n".join(logs.output))
        self.assertEqual(
            tqdm_cls.call_args.kwargs["desc"],
            "Uploading document to Pinecone",
        )

    def test_load_vector_store_enforces_chunk_limit_before_upsert(self):
        first = SimpleNamespace(page_content="First chunk", metadata={"source": "doc.pdf"})
        second = SimpleNamespace(page_content="Second chunk", metadata={"source": "doc.pdf"})
        upload = SimpleNamespace(
            filename="doc.pdf",
            file=SimpleNamespace(read=lambda: b"%PDF-test"),
        )
        index = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"MAX_DOCUMENT_CHUNKS": "1"},
            clear=False,
        ), patch.object(
            self.vector_store, "UPLOAD_DIR", Path(tmpdir)
        ), patch.object(
            self.vector_store, "get_pinecone_index", return_value=(index, "authlens-test")
        ), patch.object(
            self.vector_store, "PyPDFLoader"
        ) as loader_cls, patch.object(
            self.vector_store, "RecursiveCharacterTextSplitter"
        ) as splitter_cls, patch.object(
            self.vector_store, "GoogleGenerativeAIEmbeddings"
        ) as embeddings_cls, patch.object(
            self.vector_store, "tqdm"
        ):
            loader_cls.return_value.load.return_value = [first, second]
            splitter_cls.return_value.split_documents.return_value = [first, second]

            with self.assertRaisesRegex(ValueError, "Document chunk limit exceeded"):
                self.vector_store.load_vector_store([upload])

        embeddings_cls.return_value.embed_documents.assert_not_called()
        index.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
