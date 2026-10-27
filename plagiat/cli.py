"""Интерфейс командной строки (CLI) детектора заимствований."""
import argparse
import json
import os
import sys
import time

from plagiat.config import load_config
from plagiat.loader import load_zip, make_pairs, to_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="antiplagiat",
        description="Детектор заимствований в коде и отчётах студентов",
    )
    parser.add_argument("archive", help="ZIP-архив со сдачей группы")
    parser.add_argument("-c", "--config", default="config.json",
                        help="файл настроек (по умолчанию config.json)")
    parser.add_argument("-o", "--out", help="папка для результатов (иначе из config.json)")
    parser.add_argument("--threshold-code", type=int, help="порог сходства кода, %%")
    parser.add_argument("--threshold-text", type=int, help="порог сходства текста, %%")
    parser.add_argument("--extract", action="store_true",
                        help="разложить файлы по папкам студент/code и студент/report")
    return parser


def save_files(result, out_dir: str) -> None:
    """Сохраняет файлы на диск: out/files/<студент>/<code|report>/<путь>."""
    for f in result.files:
        path = os.path.join(out_dir, "files", f.student, f.kind, f.path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as out:
            out.write(f.content)


def print_summary(result) -> None:
    """Печатает таблицу: студент, сколько файлов кода и отчётов."""
    print(f"\n{'Студент':<25}{'Код':>6}{'Отчёты':>8}")
    print("-" * 39)
    for student in result.students():
        code = len(result.files_of(student, "code"))
        reports = len(result.files_of(student, "report"))
        print(f"{student:<25}{code:>6}{reports:>8}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if not os.path.exists(args.archive):
        print(f"Ошибка: файл {args.archive} не найден")
        return 1

    try:
        config = load_config(args.config)
        # Параметры из командной строки важнее config.json
        if args.threshold_code is not None:
            config["threshold_code"] = args.threshold_code
        if args.threshold_text is not None:
            config["threshold_text"] = args.threshold_text
        if args.out:
            config["output_dir"] = args.out
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Ошибка в настройках: {e}")
        return 1

    start = time.time()
    result = load_zip(args.archive, config)
    elapsed = time.time() - start

    print(f"Архив: {args.archive}")
    print(f"Файлов принято: {len(result.files)}, студентов: {len(result.students())}, "
          f"время: {elapsed:.2f} с")
    print_summary(result)

    if result.errors:
        print(f"\nПропущено файлов: {len(result.errors)}")
        for error in result.errors:
            print("  -", error)

    pairs = make_pairs(result.students())
    print(f"\nПар для сравнения «кто с кем»: {len(pairs)}")
    print(f"Пороги: код {config['threshold_code']} %, текст {config['threshold_text']} %")

    out_dir = config["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(to_manifest(result), f, ensure_ascii=False, indent=2)
    print(f"Описание сдачи сохранено: {manifest_path}")

    if args.extract:
        save_files(result, out_dir)
        print(f"Файлы разложены по папкам: {os.path.join(out_dir, 'files')}")

    # Здесь подключаются части 2–4 (сравнение) и 5 (итоговая таблица и веб)
    print("\nСравнение кода (части 2, 3) и текстов (часть 4) пока не подключено.")
    return 0 if result.files else 2


if __name__ == "__main__":
    sys.exit(main())
