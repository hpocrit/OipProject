"""
search.py
---------
Булев поиск по инвертированному индексу.

Поддерживаемые операторы:
    AND  — пересечение
    OR   — объединение
    NOT  — дополнение (ко всем документам в индексе)
    ( )  — группировка

Пример запроса:
    (Клеопатра AND Цезарь) OR (Антоний AND Цицерон) OR Помпей

Запрос читается из командной строки или вводится в интерактивном режиме.
Каждый термин нормализуется к лемме с помощью pymorphy2 перед поиском.

Использование:
    python search.py                          # интерактивный режим
    python search.py "Клеопатра AND Цезарь"  # запрос из аргумента
"""

import json
import os
import re
import sys
from typing import Optional

import pymorphy2

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_JSON = os.path.join(SCRIPT_DIR, "inverted_index.json")

# ---------------------------------------------------------------------------
# Загрузка индекса
# ---------------------------------------------------------------------------

def load_index(path: str) -> "dict[str, set[int]]":
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Файл индекса не найден: {path}\n"
            "Сначала запустите build_index.py"
        )
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {lemma: set(ids) for lemma, ids in raw.items()}


# ---------------------------------------------------------------------------
# Токенизатор запроса
# ---------------------------------------------------------------------------

# Распознаём: AND, OR, NOT (без учёта регистра), скобки, слова
_TOKEN_RE = re.compile(
    r"\bAND\b"               # оператор AND
    r"|\bOR\b"               # оператор OR
    r"|\bNOT\b"              # оператор NOT
    r"|\("                   # открывающая скобка
    r"|\)"                   # закрывающая скобка
    r"|[а-яёА-ЯЁa-zA-Z\-]+" # слово (кириллическое или латинское)
    ,
    re.IGNORECASE,
)

def tokenize_query(query: str) -> "list[str]":
    tokens = [m.group() for m in _TOKEN_RE.finditer(query)]
    # нормализуем операторы к верхнему регистру
    return [t.upper() if t.upper() in ("AND", "OR", "NOT") else t for t in tokens]


# ---------------------------------------------------------------------------
# Рекурсивный парсер / вычислитель булева выражения
# ---------------------------------------------------------------------------
# Грамматика:
#   expr   ::= term  (OR term)*
#   term   ::= factor (AND factor)*
#   factor ::= NOT factor | '(' expr ')' | WORD

class BooleanSearchEngine:
    def __init__(self, index: "dict[str, set[int]]", analyzer: pymorphy2.MorphAnalyzer):
        self.index = index
        self.analyzer = analyzer
        self.all_docs: set[int] = set().union(*index.values()) if index else set()

        # состояние парсера
        self._tokens: list[str] = []
        self._pos: int = 0

    # ------------------------------------------------------------------
    # Поиск термина в индексе (с лемматизацией)
    # ------------------------------------------------------------------

    def _lookup(self, word: str) -> set[int]:
        lemma = self.analyzer.parse(word.lower())[0].normal_form
        result = self.index.get(lemma, set())
        if not result:
            # пробуем исходное слово (вдруг уже лемма)
            result = self.index.get(word.lower(), set())
        return set(result)

    # ------------------------------------------------------------------
    # Парсер
    # ------------------------------------------------------------------

    def _peek(self) -> Optional[str]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> str:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _parse_expr(self) -> set[int]:
        """expr ::= term (OR term)*"""
        result = self._parse_term()
        while self._peek() == "OR":
            self._consume()
            result = result | self._parse_term()
        return result

    def _parse_term(self) -> set[int]:
        """term ::= factor (AND factor)*"""
        result = self._parse_factor()
        while self._peek() == "AND":
            self._consume()
            result = result & self._parse_factor()
        return result

    def _parse_factor(self) -> set[int]:
        """factor ::= NOT factor | '(' expr ')' | WORD"""
        tok = self._peek()
        if tok is None:
            raise SyntaxError("Неожиданный конец запроса")

        if tok == "NOT":
            self._consume()
            operand = self._parse_factor()
            return self.all_docs - operand

        if tok == "(":
            self._consume()
            result = self._parse_expr()
            if self._peek() != ")":
                raise SyntaxError("Ожидалась закрывающая скобка ')'")
            self._consume()
            return result

        # слово
        self._consume()
        return self._lookup(tok)

    # ------------------------------------------------------------------
    # Публичный метод
    # ------------------------------------------------------------------

    def search(self, query: str) -> set[int]:
        self._tokens = tokenize_query(query)
        self._pos = 0
        if not self._tokens:
            raise ValueError("Пустой запрос")
        result = self._parse_expr()
        if self._pos != len(self._tokens):
            raise SyntaxError(
                f"Непредвиденный токен: '{self._tokens[self._pos]}'"
            )
        return result


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def format_results(doc_ids: set[int]) -> str:
    if not doc_ids:
        return "Ничего не найдено."
    ids_sorted = sorted(doc_ids)
    return (
        f"Найдено документов: {len(ids_sorted)}\n"
        f"ID документов: {', '.join(str(i) for i in ids_sorted)}"
    )


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    print("Загрузка индекса...")
    index = load_index(INDEX_JSON)
    analyzer = pymorphy2.MorphAnalyzer()
    engine = BooleanSearchEngine(index, analyzer)
    print(f"Индекс загружен. Лемм: {len(index)}, документов: {len(engine.all_docs)}\n")

    # --- режим одного запроса (аргумент командной строки) ---
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Запрос: {query}")
        try:
            result = engine.search(query)
            print(format_results(result))
        except (SyntaxError, ValueError) as e:
            print(f"Ошибка разбора запроса: {e}")
        return

    # --- интерактивный режим ---
    print("Булев поиск. Операторы: AND, OR, NOT, скобки ( )")
    print("Пример: (Клеопатра AND Цезарь) OR Помпей")
    print("Для выхода введите 'exit' или нажмите Ctrl+C.\n")

    while True:
        try:
            query = input("Запрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "выход"):
            print("Завершение работы.")
            break

        try:
            result = engine.search(query)
            print(format_results(result))
        except (SyntaxError, ValueError) as e:
            print(f"Ошибка разбора запроса: {e}")
        print()


if __name__ == "__main__":
    main()