import io
import json
import os
import tempfile
import unittest
import zipfile

from make_test_archive import build, make_docx
from plagiat.config import DEFAULTS, load_config
from plagiat.loader import fix_name, load_zip, make_pairs, to_manifest


def zip_of(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class TestLoader(unittest.TestCase):
    def setUp(self):
        self.config = dict(DEFAULTS)
        self.result = load_zip(build(), self.config)

    def test_students(self):
        self.assertEqual(self.result.students(),
                         ["Иванов_НС", "Каныгин_КК", "Мельниченко_ВС", "Миронов", "Савельев_ЯВ"])

    def test_kinds_and_languages(self):
        kanygin = self.result.files_of("Каныгин_КК")
        self.assertEqual({(f.kind, f.language) for f in kanygin},
                         {("code", "python"), ("code", "java"), ("report", "pdf")})

    def test_nested_zip(self):
        names = [f.path for f in self.result.files_of("Мельниченко_ВС")]
        self.assertEqual(sorted(names), ["lab1.cpp", "report.docx"])

    def test_bad_files_go_to_errors(self):
        errors = " ".join(self.result.errors)
        self.assertIn("неподдерживаемый формат .txt", errors)
        self.assertIn("пустой файл", errors)
        self.assertIn("повреждённый DOCX", errors)
        self.assertIn("повреждённый PDF", errors)
        self.assertIn("опасный путь", errors)
        self.assertEqual(len(self.result.errors), 5)

    def test_good_file_of_student_with_errors_kept(self):
        files = self.result.files_of("Савельев_ЯВ")
        self.assertEqual([f.path for f in files], ["Solution.java"])

    def test_not_zip(self):
        result = load_zip(b"not a zip", self.config)
        self.assertEqual(result.files, [])
        self.assertEqual(len(result.errors), 1)

    def test_windows_russian_names(self):
        # Архив из Windows: имя записано в cp866, флага UTF-8 нет,
        # поэтому Python прочитал его как cp437 и получилась «каша»
        info = zipfile.ZipInfo("Петров".encode("cp866").decode("cp437") + "/lab.py")
        info.flag_bits = 0
        self.assertEqual(fix_name(info), "Петров/lab.py")

    def test_utf8_names_not_changed(self):
        info = zipfile.ZipInfo("Петров/lab.py")
        info.flag_bits = 0x800
        self.assertEqual(fix_name(info), "Петров/lab.py")

    def test_cp1251_source_accepted(self):
        result = load_zip(zip_of({"А/a.py": "# комментарий".encode("cp1251")}), self.config)
        self.assertEqual(len(result.files), 1)

    def test_too_big_file(self):
        self.config["max_file_size_mb"] = 0.0001  # около 100 байт
        result = load_zip(zip_of({"А/a.py": "x = 1\n" * 100}), self.config)
        self.assertEqual(result.files, [])
        self.assertIn("больше", result.errors[0])

    def test_batch_over_100_files(self):
        files = {}
        for s in range(30):
            for k in range(4):
                files[f"student{s}/lab{k}.py"] = f"print({s}, {k})\n"
        result = load_zip(zip_of(files), self.config)
        self.assertEqual(len(result.files), 120)
        self.assertEqual(len(result.students()), 30)


class TestPairs(unittest.TestCase):
    def test_pairs_count(self):
        self.assertEqual(len(make_pairs(["a", "b", "c", "d", "e"])), 10)

    def test_no_self_and_no_repeats(self):
        pairs = make_pairs(["a", "b", "c"])
        self.assertEqual(pairs, [("a", "b"), ("a", "c"), ("b", "c")])

    def test_manifest_has_no_content(self):
        manifest = to_manifest(load_zip(build(), dict(DEFAULTS)))
        self.assertNotIn("content", manifest["files"][0])
        json.dumps(manifest, ensure_ascii=False)  # должно сериализоваться


class TestConfig(unittest.TestCase):
    def write(self, data):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(data, f)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_missing_file_gives_defaults(self):
        self.assertEqual(load_config("нет_такого.json"), DEFAULTS)

    def test_override(self):
        config = load_config(self.write({"threshold_code": 50}))
        self.assertEqual(config["threshold_code"], 50)
        self.assertEqual(config["threshold_text"], DEFAULTS["threshold_text"])

    def test_bad_threshold(self):
        with self.assertRaises(ValueError):
            load_config(self.write({"threshold_text": 150}))

    def test_unknown_key(self):
        with self.assertRaises(ValueError):
            load_config(self.write({"porog": 10}))


if __name__ == "__main__":
    unittest.main()
