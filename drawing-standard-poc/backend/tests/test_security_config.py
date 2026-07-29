import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend.app.core.paths import resolve_child_path
from backend.config.setting import DEFAULTS, get_env


class SecurityConfigTests(unittest.TestCase):
    def test_default_database_password_is_not_committed(self):
        self.assertEqual(DEFAULTS["MYSQL_PASSWORD"], "")

    def test_environment_overrides_database_config(self):
        with patch.dict(os.environ, {"MYSQL_HOST": "db.internal"}):
            self.assertEqual(get_env("MYSQL_HOST"), "db.internal")

    def test_file_path_must_remain_under_configured_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(resolve_child_path(root, "task/image.png"), root / "task" / "image.png")
            with self.assertRaisesRegex(ValueError, "非法文件路径"):
                resolve_child_path(root, "../outside.txt")


if __name__ == "__main__":
    unittest.main()
