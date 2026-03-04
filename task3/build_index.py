"""
build_index.py
--------------
Строит инвертированный индекс из лемм (task2/lemmas/).

Формат файла лемм (task2):
    лемма форма1 форма2 ...

Выходные файлы (task3/):
    inverted_index.json  — машиночитаемый (лемма → [id, id, ...])
    inverted_index.txt   — человекочитаемый
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEMMAS_DIR = os.path.join(SCRIPT_DIR, "..", "task2", "lemmas")
INDEX_JSON = os.path.join(SCRIPT_DIR, "inverted_index.json")
INDEX_TXT  = os.path.join(SCRIPT_DIR, "inverted_index.txt")


def build_inverted_index(lemmas_dir: str) -> "dict[str, list[int]]":
    """
    Читает все *_lemmas.txt из lemmas_dir.
    Возвращает словарь {лемма: sorted_list_of_doc_ids}.
    """
    index = {}  # type: dict[str, set[int]]

    files = sorted(f for f in os.listdir(lemmas_dir) if f.endswith("_lemmas.txt"))
    if not files:
        raise FileNotFoundError(f"Не найдено файлов лемм в {lemmas_dir}")

    for fname in files:
        # doc_id — числовая часть имени файла: 001_lemmas.txt → 1
        doc_id = int(fname.split("_")[0])
        path = os.path.join(lemmas_dir, fname)

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                lemma = parts[0]          # первое слово — нормальная форма
                if lemma not in index:
                    index[lemma] = set()
                index[lemma].add(doc_id)

    # преобразуем множества в отсортированные списки
    return {lemma: sorted(ids) for lemma, ids in sorted(index.items())}


def save_index(index: "dict[str, list[int]]") -> None:
    # JSON
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"JSON-индекс сохранён: {INDEX_JSON}")

    # TXT — удобно для проверки
    with open(INDEX_TXT, "w", encoding="utf-8") as f:
        for lemma, ids in index.items():
            f.write(f"{lemma}: {', '.join(str(i) for i in ids)}\n")
    print(f"TXT-индекс сохранён:  {INDEX_TXT}")


def main() -> None:
    print("Построение инвертированного индекса...")
    index = build_inverted_index(LEMMAS_DIR)
    save_index(index)
    print(f"Готово. Уникальных лемм: {len(index)}")


if __name__ == "__main__":
    main()