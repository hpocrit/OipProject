import os
import re
import logging
from bs4 import BeautifulSoup
import pymorphy2

# --- логирование: консоль + файл рядом со скриптом ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokenizer.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

# --- пути ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
HTML_DIR = os.path.join(ROOT_DIR, "task1", "pages")
TOKENS_DIR = os.path.join(SCRIPT_DIR, "tokens")
LEMMAS_DIR = os.path.join(SCRIPT_DIR, "lemmas")

# --- служебные слова, которые не несут смысловой нагрузки ---
FUNCTION_WORDS = {
    # Местоимения личные
    "я", "ты", "он", "она", "оно", "мы", "вы", "они",
    "мне", "мной", "тебе", "тебя", "его", "её", "ее", "их",
    "нас", "нам", "вас", "вам", "им", "ему", "ей",
    # Местоимения возвратные и притяжательные
    "себя", "себе", "собой", "свой", "своя", "своё", "свои",
    "сам", "сама", "само", "сами",
    # Указательные и определительные местоимения
    "этот", "эта", "это", "эти", "тот", "та", "те", "то",
    "весь", "вся", "все", "всё", "всех", "всем",
    "такой", "такая", "такое", "такие",
    "каждый", "каждая", "каждое",
    "один", "одна", "одно", "одни",
    # Вопросительные и относительные местоимения
    "кто", "что", "какой", "какая", "какое", "какие",
    "который", "которая", "которое", "которые",
    # Предлоги
    "в", "на", "с", "со", "к", "по", "из", "у", "о", "об", "от", "до",
    "за", "для", "при", "без", "над", "под", "про", "через",
    "перед", "после", "около", "вокруг", "среди", "ради", "вдоль", "между",
    # Союзы
    "и", "а", "но", "или", "да", "ни", "не", "же", "бы",
    "как", "что", "если", "чтобы", "хотя", "либо", "также",
    "тоже", "однако", "зато", "причём", "притом",
    "когда", "пока", "пусть", "будто", "словно", "точно",
    # Частицы
    "ли", "ведь", "вот", "вон", "даже", "лишь", "только",
    "уже", "ещё", "еще", "именно", "разве", "неужели",
    # Глаголы-связки
    "быть", "был", "была", "было", "были", "есть",
    "будет", "будут", "будем", "стал", "стала",
    "является", "являются",
    # Наречия и слова-связки
    "так", "там", "тут", "здесь", "где", "куда", "откуда",
    "тогда", "потом", "затем", "поэтому", "потому",
    "очень", "более", "менее", "надо", "нужно", "можно",
    # Прочее
    "то", "ну", "нет", "при", "же",
    "может", "могут",
    "другой", "другая", "другое", "другие",
}

# --- только кириллица, не короче двух символов ---
VALID_WORD = re.compile(r"^[а-яёА-ЯЁ]{2,}$")


def strip_markup(markup: str) -> str:
    """Снимает HTML-разметку и возвращает чистый текст."""
    doc = BeautifulSoup(markup, "html.parser")
    for el in doc(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
        el.decompose()
    return doc.get_text(separator=" ")


def split_words(plain: str) -> list[str]:
    """Режет строку на слова по любому небуквенному символу."""
    return [w for w in re.split(r"[^а-яёa-z]+", plain.lower()) if w]


def filter_words(words: list[str]) -> list[str]:
    """
    Оставляет только осмысленные кириллические слова.
    Возвращает отсортированный список уникальных токенов.
    """
    result = set()
    for word in words:
        if word in FUNCTION_WORDS:
            continue
        if VALID_WORD.match(word):
            result.add(word)
    return sorted(result)


def group_by_lemma(words: list[str], analyzer: pymorphy2.MorphAnalyzer) -> dict[str, set[str]]:
    """
    Сводит токены к леммам (начальным формам) с помощью pymorphy2.

    pymorphy2 возвращает настоящую лемму (словарную форму), а не срезает окончание.
    Для каждого слова берётся первый (наиболее вероятный) разбор.
    """
    groups: dict[str, set[str]] = {}

    for word in words:
        analysis = analyzer.parse(word)[0]
        lemma = analysis.normal_form

        if lemma in FUNCTION_WORDS:
            continue

        if lemma not in groups:
            groups[lemma] = set()
        groups[lemma].add(word)

    return groups


def process_file(
    html_path: str,
    analyzer: pymorphy2.MorphAnalyzer,
    tokens_dir: str,
    lemmas_dir: str,
) -> None:
    """
    Обрабатывает один HTML-файл:
    - извлекает токены → tokens_dir/<name>_tokens.txt
    - лемматизирует    → lemmas_dir/<name>_lemmas.txt
    """
    name = os.path.splitext(os.path.basename(html_path))[0]

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            markup = f.read()
    except (UnicodeDecodeError, OSError) as e:
        logger.warning("Пропущен файл %s: %s", html_path, e)
        return

    plain = strip_markup(markup)
    words = split_words(plain)
    tokens = filter_words(words)
    groups = group_by_lemma(tokens, analyzer)

    # --- токены ---
    tokens_path = os.path.join(tokens_dir, f"{name}_tokens.txt")
    with open(tokens_path, "w", encoding="utf-8") as f:
        for token in tokens:
            f.write(token + "\n")

    # --- леммы ---
    lemmas_path = os.path.join(lemmas_dir, f"{name}_lemmas.txt")
    with open(lemmas_path, "w", encoding="utf-8") as f:
        for lemma in sorted(groups.keys()):
            forms = " ".join(sorted(groups[lemma]))
            f.write(f"{lemma} {forms}\n")

    logger.info(
        "%s → %d токенов, %d лемм",
        name,
        len(tokens),
        len(groups),
    )


def main() -> None:
    """Точка входа — обрабатывает страницы из task1, сохраняет пофайловые результаты."""
    os.makedirs(TOKENS_DIR, exist_ok=True)
    os.makedirs(LEMMAS_DIR, exist_ok=True)

    if not os.path.isdir(HTML_DIR):
        logger.error("Папка со страницами не найдена: %s", HTML_DIR)
        return

    files = sorted(f for f in os.listdir(HTML_DIR) if f.endswith(".html"))
    logger.info("=" * 60)
    logger.info("Источник: %s  (%d файлов)", HTML_DIR, len(files))
    logger.info("Токены → %s", TOKENS_DIR)
    logger.info("Леммы  → %s", LEMMAS_DIR)
    logger.info("=" * 60)

    analyzer = pymorphy2.MorphAnalyzer()

    for fname in files:
        process_file(
            os.path.join(HTML_DIR, fname),
            analyzer,
            TOKENS_DIR,
            LEMMAS_DIR,
        )

    logger.info("=" * 60)
    logger.info("Готово. Обработано %d файлов.", len(files))
    logger.info("=" * 60)


if __name__ == "__main__":
    main()