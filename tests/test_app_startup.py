import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class AppStartupTests(unittest.TestCase):
    def test_app_import_does_not_contact_pinecone(self):
        project_root = Path(__file__).resolve().parents[1]
        server_dir = project_root / "server"
        original_cwd = Path.cwd()
        original_path = list(sys.path)
        env_values = {
            "GOOGLE_API_KEY": "test-google-key",
            "PINECONE_API_KEY": "test-pinecone-key",
            "PINECONE_ENVIRONMENT": "us-east1",
            "PINECONE_INDEX_NAME": "test-index",
        }

        modules_to_clear = [
            "logger",
            "main",
            "modules.vector_store",
            "routes.upload_pdf",
            "routes.queries",
        ]
        for module_name in modules_to_clear:
            sys.modules.pop(module_name, None)

        try:
            os.chdir(server_dir)
            sys.path.insert(0, str(server_dir))

            with patch.dict(os.environ, env_values), patch("pinecone.Pinecone") as pinecone_cls:
                module = importlib.import_module("main")

                self.assertEqual(type(module.app).__name__, "FastAPI")
                pinecone_cls.assert_not_called()
        finally:
            for module_name in modules_to_clear:
                module = sys.modules.pop(module_name, None)
                if module_name == "logger" and module is not None:
                    for handler in list(module.logger.handlers):
                        handler.close()
                        module.logger.removeHandler(handler)
            sys.path[:] = original_path
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
