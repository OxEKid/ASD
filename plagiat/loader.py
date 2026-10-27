"""Загрузка сдачи: распаковка ZIP и раскладка файлов по студентам и типам.

Поддерживаемые варианты архива:
  сдача.zip/Иванов_ИИ/lab.py          — папка на каждого студента
  сдача.zip/Иванов_ИИ.zip             — вложенный архив на каждого студента
  сдача.zip/Иванов_ИИ_lab.py          — файл в корне, студент = начало имени до «_»
"""
import io
import os
import zipfile
from dataclasses import dataclass, field, asdict

# Какой язык у какого расширения (нужно частям 2 и 3)
LANGUAGES = {".py": "python", ".cpp": "cpp", ".h": "cpp", ".hpp": "cpp", ".java": "java"}

# Служебные файлы, которые молча пропускаем
JUNK = ("__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini")


@dataclass
class SubmissionFile:
    student: str        # имя студента (папка или начало имени файла)
    path: str           # путь внутри архива
    kind: str           # "code" или "report"
    language: str       # python / cpp / java для кода, docx / pdf для отчёта
    size: int           # размер в байтах
    content: bytes = field(repr=False)  # само содержимое файла


@dataclass
class LoadResult:
    files: list = field(default_factory=list)    # список SubmissionFile
    errors: list = field(default_factory=list)   # сообщения о пропущенных файлах

    def students(self) -> list:
        """Отсортированный список студентов без повторов."""
        return sorted({f.student for f in self.files})

    def files_of(self, student: str, kind: str = None) -> list:
        """Файлы одного студента, можно отфильтровать по типу."""
        return [f for f in self.files
                if f.student == student and (kind is None or f.kind == kind)]


def fix_name(info: zipfile.ZipInfo) -> str:
    """Исправляет русские имена файлов из архивов, созданных в Windows.

    Если в архиве не стоит флаг UTF-8 (бит 0x800), Python читает имя
    в кодировке cp437, а Windows записала его в cp866. Перекодируем.
    """
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp866")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def is_safe_path(name: str) -> bool:
    """Защита от путей вида ../../file и /etc/file внутри архива."""
    parts = name.replace("\\", "/").split("/")
    return not name.startswith("/") and ".." not in parts


def check_content(ext: str, data: bytes) -> str:
    """Проверяет, что файл не повреждён. Возвращает текст ошибки или ''."""
    if len(data) == 0:
        return "пустой файл"
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        return "повреждённый PDF (нет заголовка %PDF)"
    if ext == ".docx":
        # DOCX — это тоже ZIP-архив, внутри обязан быть word/document.xml
        if not zipfile.is_zipfile(io.BytesIO(data)):
            return "повреждённый DOCX (не открывается как архив)"
        with zipfile.ZipFile(io.BytesIO(data)) as docx:
            if "word/document.xml" not in docx.namelist():
                return "повреждённый DOCX (нет word/document.xml)"
    if ext in LANGUAGES:
        for encoding in ("utf-8", "cp1251"):
            try:
                data.decode(encoding)
                return ""
            except UnicodeDecodeError:
                pass
        return "исходный код не читается ни в UTF-8, ни в CP1251"
    return ""


def student_and_inner_path(name: str):
    """Из пути в архиве получает (студент, путь внутри работы студента)."""
    parts = [p for p in name.replace("\\", "/").split("/") if p]
    if len(parts) >= 2:
        return parts[0], "/".join(parts[1:])
    # Файл лежит в корне: студент — часть имени до первого «_»
    stem = os.path.splitext(parts[0])[0]
    return stem.split("_")[0], parts[0]


def load_zip(source, config: dict) -> LoadResult:
    """Главная функция части 1: принимает путь к ZIP (или байты) и раскладывает файлы."""
    result = LoadResult()

    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    if not zipfile.is_zipfile(source):
        result.errors.append("Архив сдачи повреждён или это не ZIP")
        return result

    with zipfile.ZipFile(source) as archive:
        _read_archive(archive, config, result, student=None)

    result.files.sort(key=lambda f: (f.student, f.path))
    return result


def _read_archive(archive, config, result, student):
    """Обходит все файлы архива. student != None, если это вложенный архив студента."""
    code_ext = config["code_extensions"]
    report_ext = config["report_extensions"]
    max_size = config["max_file_size_mb"] * 1024 * 1024

    for info in archive.infolist():
        if info.is_dir():
            continue
        name = fix_name(info)
        if any(j in name for j in JUNK):
            continue
        if not is_safe_path(name):
            result.errors.append(f"{name}: опасный путь в архиве, пропущен")
            continue
        if info.file_size > max_size:
            result.errors.append(f"{name}: больше {config['max_file_size_mb']} МБ, пропущен")
            continue

        if student is None:
            owner, inner = student_and_inner_path(name)
        else:
            owner, inner = student, name
        ext = os.path.splitext(name)[1].lower()

        try:
            data = archive.read(info)
        except (zipfile.BadZipFile, OSError, RuntimeError) as e:
            result.errors.append(f"{name}: не удалось распаковать ({e})")
            continue

        # Вложенный архив студента: Иванов_ИИ.zip в корне сдачи
        if ext == ".zip":
            if student is not None:
                result.errors.append(f"{name}: архив внутри архива студента, пропущен")
                continue
            if not zipfile.is_zipfile(io.BytesIO(data)):
                result.errors.append(f"{name}: повреждённый архив студента")
                continue
            owner = os.path.splitext(os.path.basename(name))[0]
            with zipfile.ZipFile(io.BytesIO(data)) as inner_zip:
                _read_archive(inner_zip, config, result, student=owner)
            continue

        if ext in code_ext:
            kind, language = "code", LANGUAGES.get(ext, ext[1:])
        elif ext in report_ext:
            kind, language = "report", ext[1:]
        else:
            result.errors.append(f"{name}: неподдерживаемый формат {ext or '(без расширения)'}")
            continue

        error = check_content(ext, data)
        if error:
            result.errors.append(f"{name}: {error}")
            continue

        result.files.append(SubmissionFile(owner, inner, kind, language, len(data), data))


def make_pairs(students: list) -> list:
    """Все пары «кто с кем» без повторов: для n студентов их n*(n-1)/2."""
    pairs = []
    for i in range(len(students)):
        for j in range(i + 1, len(students)):
            pairs.append((students[i], students[j]))
    return pairs


def to_manifest(result: LoadResult) -> dict:
    """Описание сдачи для остальных частей проекта (без содержимого файлов)."""
    students = result.students()
    files = []
    for f in result.files:
        item = asdict(f)
        del item["content"]
        files.append(item)
    return {
        "students": students,
        "files": files,
        "pairs": make_pairs(students),
        "errors": result.errors,
    }
