import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class QueryRouteTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.server_dir = self.project_root / "server"
        self.original_cwd = Path.cwd()
        self.original_path = list(sys.path)
        os.chdir(self.server_dir)
        sys.path.insert(0, str(self.server_dir))
        for module_name in ["main", "routes.queries"]:
            sys.modules.pop(module_name, None)

    def tearDown(self):
        for module_name in ["main", "routes.queries"]:
            sys.modules.pop(module_name, None)
        sys.path[:] = self.original_path
        os.chdir(self.original_cwd)

    def test_queries_accepts_only_user_query_form_field(self):
        main = importlib.import_module("main")
        queries_module = importlib.import_module("routes.queries")
        client = TestClient(main.app)

        index = MagicMock()
        index.query.return_value = SimpleNamespace(
            matches=[
                {
                    "metadata": {
                        "text": "Diabetes is a chronic condition.",
                        "source": "DIABETES.pdf",
                    }
                }
            ]
        )
        embeddings = MagicMock()
        embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch.object(
            queries_module, "get_pinecone_index", return_value=(index, "auth-index")
        ), patch.object(
            queries_module, "get_embeddings", return_value=embeddings
        ), patch.object(
            queries_module, "get_llm", return_value=object()
        ), patch.object(
            queries_module,
            "handle_query_chain",
            return_value={"answer": "Diabetes is a chronic condition."},
        ):
            response = client.post(
                "/api/queries/",
                data={"user_query": "what is diabetes?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"answer": "Diabetes is a chronic condition."},
        )

    def test_queries_returns_500_when_chain_processing_fails(self):
        main = importlib.import_module("main")
        queries_module = importlib.import_module("routes.queries")
        client = TestClient(main.app)

        index = MagicMock()
        index.query.return_value = SimpleNamespace(matches=[])
        embeddings = MagicMock()
        embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        with patch.object(
            queries_module, "get_pinecone_index", return_value=(index, "auth-index")
        ), patch.object(
            queries_module, "get_embeddings", return_value=embeddings
        ), patch.object(
            queries_module, "get_llm", return_value=object()
        ), patch.object(
            queries_module,
            "handle_query_chain",
            side_effect=ValueError("Missing some input keys: {'query'}"),
        ):
            response = client.post(
                "/api/queries/",
                data={"user_query": "what is diabetes?"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"error": "Missing some input keys: {'query'}"},
        )
