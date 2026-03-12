"""
tf_idf.py
---------
Задание 4: подсчёт TF и IDF для токенов и лемм.

Словарь терминов  берётся из task2/tokens/  (*_tokens.txt).
Словарь лемм      берётся из task2/lemmas/  (*_lemmas.txt).
Исходные тексты   — HTML-файлы из task1/pages/.

Формулы
-------
TF(t, d)     = count(t, d) / total_tokens(d)
               для лемм: сумма вхождений всех форм / total_tokens(d)
IDF(t)       = log( N / df(t) )
               N   — число документов в коллекции
               df  — число документов, содержащих термин

Выходные файлы
--------------
task4/tokens/<doc>_tokens_tf_idf.txt  — TF·IDF по токенам для каждого документа
task4/lemmas/<doc>_lemmas_tf_idf.txt  — TF·IDF по леммам для каждого документа
task4/tokens_idf.txt                  — глобальный IDF для всех токенов
task4/lemmas_idf.txt                  — глобальный IDF для всех лемм
"""

import logging
import math
import os
import re
from collections import defaultdict

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR      = os.path.dirname(SCRIPT_DIR)
HTML_DIR      = os.path.join(ROOT_DIR, "task1", "pages")
TOKENS_SRC    = os.path.join(ROOT_DIR, "task2", "tokens")
LEMMAS_SRC    = os.path.join(ROOT_DIR, "task2", "lemmas")
OUT_TOKENS    = os.path.join(SCRIPT_DIR, "tokens")
OUT_LEMMAS    = os.path.join(SCRIPT_DIR, "lemmas")
OUT_TOKEN_IDF = os.path.join(SCRIPT_DIR, "tokens_idf.txt")
OUT_LEMMA_IDF = os.path.join(SCRIPT_DIR, "lemmas_idf.txt")

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(SCRIPT_DIR, "tf_idf.log"), encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Служебные слова и паттерн (те же, что в task2)
# ---------------------------------------------------------------------------
FUNCTION_WORDS = {
    "я", "ты", "он", "она", "оно", "мы", "вы", "они",
    "мне", "мной", "тебе", "тебя", "его", "её", "ее", "их",
    "нас", "нам", "вас", "вам", "им", "ему", "ей",
    "себя", "себе", "собой", "свой", "своя", "своё", "свои",
    "сам", "сама", "само", "сами",
    "этот", "эта", "это", "эти", "тот", "та", "те", "то",
    "весь", "вся", "все", "всё", "всех", "всем",
    "такой", "такая", "такое", "такие",
    "каждый", "каждая", "каждое",
    "один", "одна", "одно", "одни",
    "кто", "что", "какой", "какая", "какое", "какие",
    "который", "которая", "которое", "которые",
    "в", "на", "с", "со", "к", "по", "из", "у", "о", "об", "от", "до",
    "за", "для", "при", "без", "над", "под", "про", "через",
    "перед", "после", "около", "вокруг", "среди", "ради", "вдоль", "между",
    "и", "а", "но", "или", "да", "ни", "не", "же", "бы",
    "как", "что", "если", "чтобы", "хотя", "либо", "также",
    "тоже", "однако", "зато", "причём", "притом",
    "когда", "пока", "пусть", "будто", "словно", "точно",
    "ли", "ведь", "вот", "вон", "даже", "лишь", "только",
    "уже", "ещё", "еще", "именно", "разве", "неужели",
    "быть", "был", "была", "было", "были", "есть",
    "будет", "будут", "будем", "стал", "стала",
    "является", "являются",
    "так", "там", "тут", "здесь", "где", "куда", "откуда",
    "тогда", "потом", "затем", "поэтому", "потому",
    "очень", "более", "менее", "надо", "нужно", "можно",
    "то", "ну", "нет", "при", "же",
    "может", "могут",
    "другой", "другая", "другое", "другие",
}

VALID_WORD = re.compile(r"^[а-яёА-ЯЁ]{2,}$")

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def strip_markup(markup: str) -> str:
    doc = BeautifulSoup(markup, "html.parser")
    for el in doc(["script", "style", "noscript", "meta", "link",
                   "header", "footer", "nav"]):
        el.decompose()
    return doc.get_text(separator=" ")


def count_tokens(text: str) -> "dict[str, int]":
    """Возвращает {токен: кол-во_вхождений} для всех валидных токенов."""
    counts: "dict[str, int]" = defaultdict(int)
    for word in re.split(r"[^а-яёa-z]+", text.lower()):
        if word and word not in FUNCTION_WORDS and VALID_WORD.match(word):
            counts[word] += 1
    return dict(counts)


def load_token_vocab() -> "set[str]":
    """Объединяет токены из всех файлов task2/tokens/."""
    vocab: "set[str]" = set()
    for fname in os.listdir(TOKENS_SRC):
        if not fname.endswith("_tokens.txt"):
            continue
        with open(os.path.join(TOKENS_SRC, fname), encoding="utf-8") as f:
            for line in f:
                token = line.strip()
                if token:
                    vocab.add(token)
    return vocab


def load_lemma_vocab() -> "dict[str, set[str]]":
    """
    Читает все файлы task2/lemmas/ и строит словарь {лемма: множество_форм}.
    Каждая строка файла: «лемма форма1 форма2 ...»
    """
    lemma_vocab: "dict[str, set[str]]" = {}
    for fname in os.listdir(LEMMAS_SRC):
        if not fname.endswith("_lemmas.txt"):
            continue
        with open(os.path.join(LEMMAS_SRC, fname), encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                lemma = parts[0]
                forms = set(parts)      # включаем саму лемму
                if lemma not in lemma_vocab:
                    lemma_vocab[lemma] = set()
                lemma_vocab[lemma].update(forms)
    return lemma_vocab


def idf(df: int, N: int) -> float:
    """IDF(t) = log(N / df(t)).  Если df=0 — возвращает 0."""
    if df == 0:
        return 0.0
    return math.log(N / df)


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------

def main() -> None:
    os.makedirs(OUT_TOKENS, exist_ok=True)
    os.makedirs(OUT_LEMMAS, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Загрузка словарей из task2 ...")
    token_vocab = load_token_vocab()          # множество токенов
    lemma_vocab = load_lemma_vocab()          # {лемма: {формы}}
    logger.info("Токенов в словаре: %d", len(token_vocab))
    logger.info("Лемм в словаре:    %d", len(lemma_vocab))

    # Список HTML-файлов
    html_files = sorted(f for f in os.listdir(HTML_DIR) if f.endswith(".html"))
    N = len(html_files)
    logger.info("Документов:        %d", N)
    logger.info("=" * 60)

    # --- Шаг 1: подсчёт вхождений токенов в каждом документе ---
    # doc_counts[doc_id] = {token: count}
    doc_counts: "dict[int, dict[str, int]]" = {}
    doc_totals: "dict[int, int]" = {}       # суммарное кол-во токенов в документе

    for fname in html_files:
        doc_id = int(os.path.splitext(fname)[0])
        try:
            with open(os.path.join(HTML_DIR, fname), encoding="utf-8") as f:
                markup = f.read()
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Пропущен %s: %s", fname, e)
            continue

        text = strip_markup(markup)
        counts = count_tokens(text)
        doc_counts[doc_id] = counts
        doc_totals[doc_id] = sum(counts.values())
        logger.info("Прочитан %s: %d уникальных токенов, %d всего",
                    fname, len(counts), doc_totals[doc_id])

    # --- Шаг 2: document frequency (df) для токенов ---
    token_df: "dict[str, int]" = defaultdict(int)
    for token in token_vocab:
        for counts in doc_counts.values():
            if counts.get(token, 0) > 0:
                token_df[token] += 1

    # --- Шаг 3: document frequency (df) для лемм ---
    lemma_df: "dict[str, int]" = defaultdict(int)
    for lemma, forms in lemma_vocab.items():
        for counts in doc_counts.values():
            if any(counts.get(f, 0) > 0 for f in forms):
                lemma_df[lemma] += 1

    # --- Шаг 4: глобальные IDF ---
    token_idf_map = {t: idf(token_df[t], N) for t in token_vocab}
    lemma_idf_map = {l: idf(lemma_df[l], N) for l in lemma_vocab}

    # Сохраняем глобальные IDF-файлы
    with open(OUT_TOKEN_IDF, "w", encoding="utf-8") as f:
        f.write("токен\tIDF\n")
        for token in sorted(token_idf_map):
            f.write(f"{token}\t{token_idf_map[token]:.6f}\n")
    logger.info("Глобальный IDF токенов → %s", OUT_TOKEN_IDF)

    with open(OUT_LEMMA_IDF, "w", encoding="utf-8") as f:
        f.write("лемма\tIDF\n")
        for lemma in sorted(lemma_idf_map):
            f.write(f"{lemma}\t{lemma_idf_map[lemma]:.6f}\n")
    logger.info("Глобальный IDF лемм   → %s", OUT_LEMMA_IDF)

    # --- Шаг 5: per-document TF / TF-IDF ---
    for fname in html_files:
        doc_id = int(os.path.splitext(fname)[0])
        if doc_id not in doc_counts:
            continue

        counts = doc_counts[doc_id]
        total  = doc_totals[doc_id]
        name   = f"{doc_id:03d}"

        # --- токены ---
        token_path = os.path.join(OUT_TOKENS, f"{name}_tokens_tf_idf.txt")
        with open(token_path, "w", encoding="utf-8") as f:
            f.write("токен\tTF\tIDF\tTF-IDF\n")
            for token in sorted(token_vocab):
                cnt = counts.get(token, 0)
                if cnt == 0:
                    continue
                tf     = cnt / total if total else 0.0
                i      = token_idf_map[token]
                f.write(f"{token}\t{tf:.6f}\t{i:.6f}\t{tf * i:.6f}\n")

        # --- леммы ---
        lemma_path = os.path.join(OUT_LEMMAS, f"{name}_lemmas_tf_idf.txt")
        with open(lemma_path, "w", encoding="utf-8") as f:
            f.write("лемма\tTF\tIDF\tTF-IDF\n")
            for lemma in sorted(lemma_vocab):
                forms     = lemma_vocab[lemma]
                form_cnt  = sum(counts.get(form, 0) for form in forms)
                if form_cnt == 0:
                    continue
                tf = form_cnt / total if total else 0.0
                i  = lemma_idf_map[lemma]
                f.write(f"{lemma}\t{tf:.6f}\t{i:.6f}\t{tf * i:.6f}\n")

        logger.info("Документ %s обработан", name)

    logger.info("=" * 60)
    logger.info("Готово. Обработано %d документов.", len(doc_counts))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
