"""Создаёт тестовый архив test_data/сдача.zip, чтобы проверить программу."""
import io
import os
import zipfile


def make_docx(text: str) -> bytes:
    """Минимальный DOCX без сторонних библиотек: архив с word/document.xml."""
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def make_student_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def build() -> bytes:
    original = "def summa(a, b):\n    return a + b\n\nprint(summa(2, 3))\n"
    renamed = "def add(x, y):\n    return x + y\n\nprint(add(2, 3))\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # Вариант 1: папка на студента
        z.writestr("Иванов_НС/lab1.py", original)
        z.writestr("Иванов_НС/отчёт.docx", make_docx("Отчёт Иванова по лабораторной работе"))
        z.writestr("Каныгин_КК/lab1.py", renamed)
        z.writestr("Каныгин_КК/Main.java", "public class Main { public static void main(String[] a) {} }")
        z.writestr("Каныгин_КК/отчёт.pdf", b"%PDF-1.4\n%%EOF")
        # Вариант 2: вложенный архив студента
        z.writestr("Мельниченко_ВС.zip", make_student_zip({
            "lab1.cpp": "#include <iostream>\nint main() { return 0; }\n",
            "report.docx": make_docx("Отчёт Мельниченко"),
        }))
        # Вариант 3: файл в корне архива
        z.writestr("Миронов_lab1.py", original)
        # Плохие файлы — должны попасть в список ошибок
        z.writestr("Миронов_отчёт.pdf", "это не pdf")
        z.writestr("Савельев_ЯВ/notes.txt", "текстовый файл")
        z.writestr("Савельев_ЯВ/lab1.py", "")
        z.writestr("Савельев_ЯВ/отчёт.docx", "битый docx")
        z.writestr("Савельев_ЯВ/Solution.java", "class Solution {}")
        z.writestr("../evil.py", "print('взлом')")
    return buf.getvalue()


if __name__ == "__main__":
    os.makedirs("test_data", exist_ok=True)
    with open("test_data/сдача.zip", "wb") as f:
        f.write(build())
    print("Создан test_data/сдача.zip")
