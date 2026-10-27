"""Чтение настроек из config.json."""
import json
import os

# Значения по умолчанию: если в config.json чего-то нет, берём отсюда
DEFAULTS = {
    "code_extensions": [".py", ".cpp", ".h", ".hpp", ".java"],
    "report_extensions": [".docx", ".pdf"],
    "max_file_size_mb": 20,
    "threshold_code": 70,
    "threshold_text": 60,
    "shingle_size": 5,
    "templates_dir": "templates",
    "output_dir": "result",
}


def load_config(path: str) -> dict:
    """Читает config.json и дополняет его значениями по умолчанию."""
    config = dict(DEFAULTS)
    if path is None or not os.path.exists(path):
        return config

    with open(path, encoding="utf-8") as f:
        user_config = json.load(f)

    for key, value in user_config.items():
        if key not in DEFAULTS:
            raise ValueError(f"Неизвестный параметр в config.json: {key}")
        config[key] = value

    check_config(config)
    return config


def check_config(config: dict) -> None:
    """Проверяет, что пороги в диапазоне 0–100 и числа положительные."""
    for key in ("threshold_code", "threshold_text"):
        if not 0 <= config[key] <= 100:
            raise ValueError(f"{key} должен быть от 0 до 100")
    if config["shingle_size"] < 1:
        raise ValueError("shingle_size должен быть больше 0")
    if config["max_file_size_mb"] <= 0:
        raise ValueError("max_file_size_mb должен быть больше 0")
