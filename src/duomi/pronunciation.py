import json
from pathlib import Path


DICTIONARY_FILE = Path(__file__).with_name(
    "pronunciation.json"
)


def load_pronunciation_dict():
    if not DICTIONARY_FILE.exists():
        return []

    try:
        with open(
            DICTIONARY_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        entries = data.get("entries", [])

        if not isinstance(entries, list):
            return []

        return entries

    except (OSError, json.JSONDecodeError) as e:
        print(f"发音词典加载失败：{e}")
        return []


def apply_pronunciation(text):
    if not text:
        return text

    result = text
    entries = load_pronunciation_dict()

    # 长词优先，避免短词提前匹配
    entries = sorted(
        entries,
        key=lambda item: len(
            str(item.get("text", ""))
        ),
        reverse=True
    )

    for entry in entries:
        word = str(entry.get("text", ""))
        pronunciation = str(
            entry.get("pronunciation", "")
        )

        if not word or not pronunciation:
            continue

        result = result.replace(
            word,
            pronunciation
        )

    return result
