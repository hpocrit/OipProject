"""
search.py
---------
Задание 5: векторный поиск по TF-IDF индексу.

Принцип работы
--------------
1. Загружаются TF-IDF векторы документов из task4/lemmas/<doc>_lemmas_tf_idf.txt.
2. Запрос лемматизируется (pymorphy3), строится вектор запроса:
       query_tfidf(t) = tf(t, query) * idf(t, коллекция)
   где IDF берётся из task4/lemmas_idf.txt.
3. Для каждого документа вычисляется косинусное сходство с вектором запроса.
4. Возвращаются top-N документов с URL (task1/index.txt) и оценкой сходства.

Использование:
    python task5/search.py                          # интерактивный режим
    python task5/search.py "рецепт авокадо"         # запрос из аргумента
    python task5/search.py -n 5 "рецепт авокадо"   # вернуть 5 результатов
"""

import math
import os
import re
import sys
from collections import defaultdict

import pymorphy3

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(SCRIPT_DIR)
LEMMAS_DIR   = os.path.join(ROOT_DIR, "task4", "lemmas")
IDF_FILE     = os.path.join(ROOT_DIR, "task4", "lemmas_idf.txt")
INDEX_FILE   = os.path.join(ROOT_DIR, "task1", "index.txt")

DEFAULT_TOP_N = 10

# ---------------------------------------------------------------------------
# Загрузка данных
# ---------------------------------------------------------------------------

def load_index(path: str) -> "dict[int, str]":
    """Загружает task1/index.txt → {doc_id: url}."""
    mapping: dict[int, str] = {}
    if not os.path.exists(path):
        return mapping
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                mapping[int(parts[0])] = parts[1]
    return mapping


def load_idf(path: str) -> "dict[str, float]":
    """Загружает task4/lemmas_idf.txt → {лемма: idf}."""
    idf: dict[str, float] = {}
    with open(path, encoding="utf-8") as f:
        next(f)  # пропускаем заголовок
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                idf[parts[0]] = float(parts[1])
    return idf


def load_doc_vectors(lemmas_dir: str) -> "dict[int, dict[str, float]]":
    """
    Загружает TF-IDF векторы всех документов.
    Возвращает {doc_id: {лемма: tf_idf}}.
    """
    vectors: dict[int, dict[str, float]] = {}
    for fname in sorted(os.listdir(lemmas_dir)):
        if not fname.endswith("_lemmas_tf_idf.txt"):
            continue
        doc_id = int(fname.split("_")[0])
        vec: dict[str, float] = {}
        with open(os.path.join(lemmas_dir, fname), encoding="utf-8") as f:
            next(f)  # заголовок
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 4:
                    lemma, _tf, _idf, tfidf = parts
                    val = float(tfidf)
                    if val > 0:
                        vec[lemma] = val
        vectors[doc_id] = vec
    return vectors

# ---------------------------------------------------------------------------
# Векторные операции
# ---------------------------------------------------------------------------

def cosine_similarity(v1: "dict[str, float]", v2: "dict[str, float]") -> float:
    """Косинусное сходство двух разреженных векторов."""
    dot = sum(v1.get(k, 0.0) * v for k, v in v2.items())
    norm1 = math.sqrt(sum(x * x for x in v1.values()))
    norm2 = math.sqrt(sum(x * x for x in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

# ---------------------------------------------------------------------------
# Обработка запроса
# ---------------------------------------------------------------------------

VALID_WORD = re.compile(r"^[а-яёА-ЯЁ]{2,}$")

def build_query_vector(
    query: str,
    analyzer: pymorphy3.MorphAnalyzer,
    idf_map: "dict[str, float]",
) -> "dict[str, float]":
    """
    Лемматизирует запрос, вычисляет TF·IDF вектор.
    TF считается как частота в самом запросе.
    """
    words = re.split(r"[^а-яёА-ЯЁ]+", query.lower())
    lemmas: list[str] = []
    for word in words:
        if not word or not VALID_WORD.match(word):
            continue
        lemma = analyzer.parse(word)[0].normal_form
        if lemma in idf_map:
            lemmas.append(lemma)

    if not lemmas:
        return {}

    counts: dict[str, int] = defaultdict(int)
    for lemma in lemmas:
        counts[lemma] += 1

    total = len(lemmas)
    vector: dict[str, float] = {}
    for lemma, cnt in counts.items():
        tf = cnt / total
        vector[lemma] = tf * idf_map[lemma]

    return vector

# ---------------------------------------------------------------------------
# Поисковый движок
# ---------------------------------------------------------------------------

class VectorSearchEngine:
    def __init__(self) -> None:
        print("Загрузка IDF...")
        self.idf_map = load_idf(IDF_FILE)

        print("Загрузка TF-IDF векторов документов...")
        self.doc_vectors = load_doc_vectors(LEMMAS_DIR)

        print("Загрузка URL-индекса...")
        self.url_map = load_index(INDEX_FILE)

        self.analyzer = pymorphy3.MorphAnalyzer()
        print(
            f"Готово. Лемм: {len(self.idf_map)}, "
            f"документов: {len(self.doc_vectors)}\n"
        )

    def search(self, query: str, top_n: int = DEFAULT_TOP_N) -> "list[tuple[int, float, str]]":
        """
        Возвращает список (doc_id, similarity, url), отсортированный по убыванию сходства.
        """
        query_vec = build_query_vector(query, self.analyzer, self.idf_map)
        if not query_vec:
            return []

        scores: list[tuple[float, int]] = []
        for doc_id, doc_vec in self.doc_vectors.items():
            sim = cosine_similarity(doc_vec, query_vec)
            if sim > 0:
                scores.append((sim, doc_id))

        scores.sort(reverse=True)
        results = []
        for sim, doc_id in scores[:top_n]:
            url = self.url_map.get(doc_id, f"doc#{doc_id}")
            results.append((doc_id, sim, url))
        return results


def format_results(results: "list[tuple[int, float, str]]") -> str:
    if not results:
        return "Ничего не найдено."
    lines = [f"Найдено: {len(results)} документов\n"]
    for rank, (doc_id, sim, url) in enumerate(results, 1):
        lines.append(f"  {rank:2d}. [doc {doc_id:03d}] score={sim:.4f}  {url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    top_n = DEFAULT_TOP_N

    # Разбираем флаг -n
    if len(args) >= 2 and args[0] == "-n":
        try:
            top_n = int(args[1])
            args = args[2:]
        except ValueError:
            pass

    engine = VectorSearchEngine()

    # Одиночный запрос из аргумента
    if args:
        query = " ".join(args)
        print(f"Запрос: {query}")
        results = engine.search(query, top_n)
        print(format_results(results))
        return

    # Интерактивный режим
    print("Векторный поиск (TF-IDF + косинусное сходство)")
    print(f"Показывает топ-{top_n} документов. Для смены: -n <число> в начале запроса.")
    print("Для выхода введите 'exit' или нажмите Ctrl+C.\n")

    while True:
        try:
            raw = input("Запрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "выход"):
            print("Завершение работы.")
            break

        # Поддержка -n прямо в интерактивном запросе
        parts = raw.split()
        n = top_n
        if len(parts) >= 3 and parts[0] == "-n":
            try:
                n = int(parts[1])
                raw = " ".join(parts[2:])
            except ValueError:
                pass

        results = engine.search(raw, n)
        print(format_results(results))
        print()


if __name__ == "__main__":
    main()