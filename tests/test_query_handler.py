import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class QueryHandlerTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.server_dir = self.project_root / "server"
        self.original_path = list(sys.path)
        sys.path.insert(0, str(self.server_dir))
        sys.modules.pop("modules.query_handler", None)
        self.query_handler = importlib.import_module("modules.query_handler")

    def tearDown(self):
        sys.modules.pop("modules.query_handler", None)
        sys.path[:] = self.original_path

    def test_handle_query_chain_invokes_chain_and_logs_query_and_response(self):
        class Chain:
            def __init__(self):
                self.input_payload = None

            def __call__(self, payload):
                raise AssertionError("deprecated __call__ should not be used")

            def invoke(self, payload):
                self.input_payload = payload
                return {
                    "result": "Diabetes is a chronic condition.",
                    "source_documents": [
                        SimpleNamespace(metadata={"source": "DIABETES.pdf"})
                    ],
                }

        chain = Chain()

        with self.assertLogs(self.query_handler.logger, level="INFO") as logs:
            response = self.query_handler.handle_query_chain(
                chain,
                "what is diabetes?",
            )

        self.assertEqual(chain.input_payload, {"query": "what is diabetes?"})
        self.assertEqual(
            response,
            {
                "response": "Diabetes is a chronic condition.",
                "source_documents": ["DIABETES.pdf"],
            },
        )
        self.assertIn("User query: what is diabetes?", logs.output[0])
        self.assertIn(
            "LLM response: Diabetes is a chronic condition.",
            logs.output[1],
        )

    def test_handle_query_chain_raises_chain_errors_after_logging(self):
        class Chain:
            def invoke(self, payload):
                raise ValueError("Missing some input keys: {'query'}")

        with self.assertLogs(self.query_handler.logger, level="ERROR") as logs:
            with self.assertRaisesRegex(ValueError, "Missing some input keys"):
                self.query_handler.handle_query_chain(
                    Chain(),
                    "what is diabetes?",
                )

        self.assertIn("Error handling query: Missing some input keys", logs.output[0])

    def test_handle_query_chain_suppresses_query_and_response_text_in_production(self):
        class Chain:
            def invoke(self, payload):
                return {
                    "result": "Diabetes is a chronic condition.",
                    "source_documents": [
                        SimpleNamespace(metadata={"source": "DIABETES.pdf"})
                    ],
                }

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            with self.assertLogs(self.query_handler.logger, level="INFO") as logs:
                response = self.query_handler.handle_query_chain(
                    Chain(),
                    "what is diabetes?",
                )

        self.assertEqual(
            response,
            {
                "response": "Diabetes is a chronic condition.",
                "source_documents": ["DIABETES.pdf"],
            },
        )
        log_text = "\n".join(logs.output)
        self.assertNotIn("what is diabetes?", log_text)
        self.assertNotIn("Diabetes is a chronic condition.", log_text)


if __name__ == "__main__":
    unittest.main()
