import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from make_test_archive import build
from plagiat.cli import main


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.archive = os.path.join(self.tmp, "сдача.zip")
        with open(self.archive, "wb") as f:
            f.write(build())

    def run_cli(self, *args):
        out = StringIO()
        with redirect_stdout(out):
            code = main(list(args))
        return code, out.getvalue()

    def test_full_run(self):
        out_dir = os.path.join(self.tmp, "res")
        code, text = self.run_cli(self.archive, "-o", out_dir, "--extract", "-c", "нет.json")
        self.assertEqual(code, 0)
        self.assertIn("студентов: 5", text)
        self.assertIn("Пар для сравнения «кто с кем»: 10", text)
        with open(os.path.join(out_dir, "manifest.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["pairs"]), 10)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "files", "Иванов_НС", "code", "lab1.py")))

    def test_threshold_from_command_line(self):
        out_dir = os.path.join(self.tmp, "res")
        _, text = self.run_cli(self.archive, "-o", out_dir, "--threshold-code", "40", "-c", "нет.json")
        self.assertIn("код 40 %", text)

    def test_missing_archive(self):
        code, text = self.run_cli("нет_архива.zip")
        self.assertEqual(code, 1)
        self.assertIn("не найден", text)


if __name__ == "__main__":
    unittest.main()
