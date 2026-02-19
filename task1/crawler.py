import os
import time
import random
import logging
import urllib.parse
from collections import deque

import requests
from bs4 import BeautifulSoup

# --- логирование: вывод в консоль и в файл одновременно ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "crawler.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

# --- точка входа в обход и ограничение по домену ---
SEED_URL = "https://www.povarenok.ru/recipes/"
TARGET_DOMAIN = "www.povarenok.ru"

# --- папка для html-файлов и индексный файл рядом со скриптом ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(_BASE_DIR, "pages")
MAP_FILE = os.path.join(_BASE_DIR, "index.txt")

PAGE_LIMIT = 100            # целевое количество сохранённых страниц
HTTP_TIMEOUT = 15           # сколько секунд ждать ответа от сервера
PAUSE_MIN = 1.0             # нижняя граница паузы между запросами
PAUSE_MAX = 2.0             # верхняя граница паузы между запросами
CYRILLIC_THRESHOLD = 300    # порог кириллицы для признания страницы текстовой

AGENT_STRING = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# --- форматы, которые не являются HTML-документами ---
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".rar", ".gz", ".tar",
    ".mp3", ".mp4", ".avi", ".mov",
    ".js", ".css", ".xml", ".json", ".rss", ".atom",
    ".woff", ".woff2", ".ttf", ".eot",
}


def host_of(url: str) -> str:
    """Возвращает хост из переданного адреса."""
    return urllib.parse.urlparse(url).netloc


def resolve(url: str, base_url: str) -> str | None:
    """
    Строит абсолютный URL и удаляет якорную часть.

    Относительные пути разрешаются относительно base_url.
    Если схема не http/https — возвращает None.
    """
    try:
        full = urllib.parse.urljoin(base_url, url)
    except ValueError:
        return None

    parts = urllib.parse.urlparse(full)
    result = parts._replace(fragment="").geturl()  # убираем #anchor

    if parts.scheme not in ("http", "https"):
        return None

    return result


def likely_html(url: str) -> bool:
    """
    Проверяет URL по расширению пути — без обращения к серверу.

    Возвращает False, если путь заканчивается на нетекстовое расширение.
    """
    p = urllib.parse.urlparse(url).path.lower()
    _, suffix = os.path.splitext(p)
    return suffix not in SKIP_EXTENSIONS


def is_russian(html: str) -> bool:
    """
    Оценивает, достаточно ли на странице кириллического текста.

    Перед подсчётом удаляет блоки script, style и noscript,
    чтобы не считать символы внутри кода или стилей.
    """
    doc = BeautifulSoup(html, "html.parser")
    for el in doc(["script", "style", "noscript"]):
        el.decompose()

    plain = doc.get_text()
    count = sum(
        1 for c in plain
        if "\u0400" <= c <= "\u04ff"  # весь кириллический блок Unicode
    )
    return count >= CYRILLIC_THRESHOLD


def gather_links(html: str, base_url: str) -> list[str]:
    """
    Собирает со страницы все ссылки, ведущие внутрь того же сайта.

    Пропускает внешние домены и адреса с нетекстовыми расширениями.
    Дубликаты не фильтрует — это делает множество seen в main().
    """
    doc = BeautifulSoup(html, "html.parser")
    result = []

    for el in doc.find_all("a", href=True):
        href = el["href"].strip()
        if not href:
            continue

        link = resolve(href, base_url)
        if link is None:
            continue

        if host_of(link) != TARGET_DOMAIN:
            continue

        if not likely_html(link):
            continue

        result.append(link)

    return result


def fetch(url: str, session: requests.Session) -> str | None:
    """
    Выполняет GET-запрос и возвращает текст страницы.

    Если сервер отдал не HTML или запрос завершился ошибкой,
    возвращает None и пишет запись в лог.
    """
    hdrs = {"User-Agent": AGENT_STRING}

    try:
        resp = session.get(url, headers=hdrs, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()

        ctype = resp.headers.get("Content-Type", "")
        if "text/html" not in ctype:
            logger.debug("Не HTML (Content-Type: %s): %s", ctype, url)
            return None

        return resp.text

    except requests.exceptions.Timeout:
        logger.error("Превышено время ожидания: %s", url)
    except requests.exceptions.ConnectionError:
        logger.error("Не удалось установить соединение: %s", url)
    except requests.exceptions.HTTPError as e:
        logger.error("Сервер вернул ошибку %s: %s", e.response.status_code, url)
    except requests.exceptions.RequestException as e:
        logger.error("Ошибка при загрузке страницы %s — %s", url, e)

    return None


def write_html(content: str, page_number: int) -> str:
    """
    Записывает HTML в файл NNN.html внутри SAVE_DIR.

    Нумерация с ведущими нулями до трёх цифр (001, 002, ...).
    Возвращает полный путь к созданному файлу.
    """
    name = f"{page_number:03d}.html"
    path = os.path.join(SAVE_DIR, name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def register(page_number: int, url: str) -> None:
    """Дописывает в конец index.txt строку вида: <номер> <url>."""
    with open(MAP_FILE, "a", encoding="utf-8") as f:
        f.write(f"{page_number} {url}\n")


def load_progress() -> tuple[set[str], int]:
    """
    Восстанавливает состояние из предыдущего запуска.

    Читает index.txt и возвращает множество уже посещённых URL
    и номер последней сохранённой страницы.
    """
    seen: set[str] = set()
    last = 0

    if not os.path.exists(MAP_FILE):
        return seen, last

    with open(MAP_FILE, "r", encoding="utf-8") as f:
        for row in f:
            row = row.strip()
            if not row:
                continue
            chunks = row.split(maxsplit=1)
            if len(chunks) == 2:
                try:
                    n = int(chunks[0])
                    seen.add(chunks[1])
                    last = max(last, n)
                except ValueError:
                    continue

    logger.info("Найдено %d ранее скачанных страниц, продолжаем с места остановки", len(seen))
    return seen, last


def main() -> None:
    """
    Точка входа — запускает BFS-обход сайта.

    Последовательность действий:
    1. Создать папку pages/, если её нет.
    2. Прочитать index.txt, чтобы не скачивать то, что уже есть.
    3. Обходить очередь URL: скачать страницу, проверить текст,
       сохранить файл, добавить найденные ссылки в очередь.
    4. Выдерживать случайную паузу после каждого запроса.
    5. Остановиться, когда набрано PAGE_LIMIT страниц.
    """
    logger.info("=" * 60)
    logger.info("Веб-краулер запущен")
    logger.info("Сайт:          %s", TARGET_DOMAIN)
    logger.info("Цель:          %d страниц", PAGE_LIMIT)
    logger.info("Директория:    %s", SAVE_DIR)
    logger.info("=" * 60)

    os.makedirs(SAVE_DIR, exist_ok=True)

    seen, saved = load_progress()

    frontier: deque[str] = deque()
    if SEED_URL not in seen:
        frontier.append(SEED_URL)

    skipped = 0
    failed = 0

    with requests.Session() as session:
        while frontier and saved < PAGE_LIMIT:
            url = frontier.popleft()

            if url in seen:
                continue
            seen.add(url)

            logger.info(
                "[%d/%d] %s",
                saved + 1, PAGE_LIMIT, url,
            )

            raw = fetch(url, session)
            if raw is None:
                failed += 1
                continue

            if not is_russian(raw):
                logger.debug("Пропущено — недостаточно русского текста: %s", url)
                skipped += 1
                continue

            saved += 1
            path = write_html(raw, saved)
            register(saved, url)
            logger.info("  Сохранено: %s (%d байт)", path, len(raw.encode()))

            found = gather_links(raw, url)
            enqueued = 0
            for candidate in found:
                if candidate not in seen:
                    frontier.append(candidate)
                    enqueued += 1
            if enqueued:
                logger.debug("  В очередь добавлено %d новых ссылок", enqueued)

            if saved < PAGE_LIMIT:
                pause = random.uniform(PAUSE_MIN, PAUSE_MAX)
                time.sleep(pause)

    logger.info("=" * 60)
    logger.info("Работа завершена")
    logger.info("  Скачано страниц:        %d", saved)
    logger.info("  Пропущено (мало текста):%d", skipped)
    logger.info("  Ошибок при загрузке:    %d", failed)
    logger.info("  Осталось в очереди:     %d", len(frontier))
    logger.info("  Страницы сохранены в:   %s/", SAVE_DIR)
    logger.info("  Индексный файл:         %s", MAP_FILE)
    logger.info("=" * 60)

    if saved < PAGE_LIMIT:
        logger.warning(
            "Скачано только %d из %d страниц — попробуйте изменить SEED_URL.",
            saved, PAGE_LIMIT,
        )


if __name__ == "__main__":
    main()