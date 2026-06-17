import importlib
import os
import sys
import unittest
from pathlib import Path


class LoggerImportTests(unittest.TestCase):
    def test_logger_imports_when_process_starts_inside_server_directory(self):
        project_root = Path(__file__).resolve().parents[1]
        server_dir = project_root / "server"
        original_cwd = Path.cwd()
        original_path = list(sys.path)

        sys.modules.pop("logger", None)

        try:
            os.chdir(server_dir)
            sys.path.insert(0, str(server_dir))

            module = importlib.import_module("logger")
            file_handlers = [
                handler
                for handler in module.logger.handlers
                if hasattr(handler, "baseFilename")
            ]

            self.assertTrue(file_handlers)
            self.assertEqual(
                Path(file_handlers[0].baseFilename),
                server_dir / "app.log",
            )
        finally:
            module = sys.modules.pop("logger", None)
            if module is not None:
                for handler in list(module.logger.handlers):
                    handler.close()
                    module.logger.removeHandler(handler)
            sys.path[:] = original_path
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
