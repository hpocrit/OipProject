import os
import re
import logging
from bs4 import BeautifulSoup
import pymorphy3

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

# --- пути: страницы из task1, результаты рядом с этим скриптом ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
HTML_DIR = os.path.join(ROOT_DIR, "task1", "pages")
WORDS_FILE = os.path.join(SCRIPT_DIR, "tokens.txt")
FORMS_FILE = os.path.join(SCRIPT_DIR, "lemmas_tokens.txt")

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
    """
    Снимает разметку с HTML и отдаёт чистый текст.

    Перед извлечением удаляет блоки, которые не содержат
    читаемого контента: скрипты, стили, навигацию, шапку и подвал.
    """
    doc = BeautifulSoup(markup, "html.parser")

    for el in doc(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
        el.decompose()

    return doc.get_text(separator=" ")


def split_words(plain: str) -> list[str]:
    """
    Режет строку на слова по любому небуквенному символу.

    Результат приводится к нижнему регистру; пустые фрагменты отбрасываются.
    """
    return [w for w in re.split(r"[^а-яёa-z]+", plain.lower()) if w]


def filter_words(words: list[str]) -> list[str]:
    """
    Оставляет только осмысленные кириллические слова.

    Отсеивает служебные слова, латиницу, числа и любые слова короче двух букв.
    Возвращает отсортированный список уникальных токенов.
    """
    result = set()
    for word in words:
        if word in FUNCTION_WORDS:
            continue
        if VALID_WORD.match(word):
            result.add(word)
    return sorted(result)


def group_by_lemma(words: list[str], analyzer: pymorphy3.MorphAnalyzer) -> dict[str, set[str]]:
    """
    Сводит токены к начальным формам и группирует по лемме.

    Для каждого слова берётся первый (наиболее вероятный) разбор.
    Если нормальная форма попадает в служебные слова, токен пропускается.
    Возвращает словарь {лемма: множество словоформ}.
    """
    groups: dict[str, set[str]] = {}

    for word in words:
        analysis = analyzer.parse(word)[0]
        base = analysis.normal_form

        if base in FUNCTION_WORDS:
            continue

        if base not in groups:
            groups[base] = set()
        groups[base].add(word)

    return groups


def dump_tokens(word_list: list[str], filename: str = WORDS_FILE) -> None:
    """Записывает токены в файл — по одному на строку."""
    with open(filename, "w", encoding="utf-8") as f:
        for word in word_list:
            f.write(word + "\n")

    logger.info("Токены записаны в %s — %d шт.", filename, len(word_list))


def dump_lemmas(groups: dict[str, set[str]], filename: str = FORMS_FILE) -> None:
    """
    Сохраняет леммы в файл.

    Каждая строка: лемма, затем через пробел все её словоформы.
    Строки отсортированы по лемме.
    """
    with open(filename, "w", encoding="utf-8") as f:
        for base in sorted(groups.keys()):
            forms = " ".join(sorted(groups[base]))
            f.write(f"{base} {forms}\n")

    logger.info("Леммы записаны в %s — %d шт.", filename, len(groups))


def run_pipeline(src_dir: str = HTML_DIR) -> tuple[list[str], dict[str, set[str]]]:
    """
    Читает все HTML-файлы из папки и строит общий словарь токенов и лемм.

    Проходит по файлам последовательно: извлекает текст, токенизирует,
    фильтрует, накапливает уникальные токены. После обхода всех файлов
    запускает лемматизацию накопленного словаря.
    """
    if not os.path.isdir(src_dir):
        logger.error("Папка со страницами не найдена: %s", src_dir)
        return [], {}

    files = sorted(f for f in os.listdir(src_dir) if f.endswith(".html"))
    logger.info("В папке %s найдено %d HTML-файлов", src_dir, len(files))

    vocab: set[str] = set()
    processed = 0

    for fname in files:
        path = os.path.join(src_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                markup = f.read()
        except (UnicodeDecodeError, OSError) as e:
            logger.warning("Пропущен файл %s: %s", path, e)
            continue

        plain = strip_markup(markup)
        words = split_words(plain)
        filtered = filter_words(words)
        vocab.update(filtered)
        processed += 1

        if processed % 20 == 0:
            logger.info("Обработано %d из %d файлов...", processed, len(files))

    logger.info("Файлов обработано: %d", processed)
    logger.info("Уникальных токенов собрано: %d", len(vocab))

    logger.info("Лемматизация...")
    analyzer = pymorphy3.MorphAnalyzer()
    word_list = sorted(vocab)
    groups = group_by_lemma(word_list, analyzer)
    logger.info("Уникальных лемм получено: %d", len(groups))

    return word_list, groups


def main() -> None:
    """Точка входа — обрабатывает страницы из task1 и сохраняет результаты."""
    logger.info("=" * 60)
    logger.info("Токенизация и лемматизация запущены")
    logger.info("Источник: %s", HTML_DIR)
    logger.info("=" * 60)

    word_list, groups = run_pipeline()

    if not word_list:
        logger.error("Токены не получены — проверьте содержимое папки %s", HTML_DIR)
        return

    dump_tokens(word_list)
    dump_lemmas(groups)

    logger.info("=" * 60)
    logger.info("Готово")
    logger.info("  Токенов:   %d  →  %s", len(word_list), WORDS_FILE)
    logger.info("  Лемм:      %d  →  %s", len(groups), FORMS_FILE)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()