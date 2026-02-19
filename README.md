## Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone https://git.kpfu.ru/hpocrit/OipProject.git
cd OipProject
```

### 2. Создать виртуальное окружение 

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

---

## Задание 1 — Веб-краулер

Обходит сайт **povarenok.ru** (тематика: еда и рецепты) методом BFS,
автоматически находит ссылки через BeautifulSoup и сохраняет 100+ страниц в папку `task1/pages/`.

### Запуск

```bash
cd task1
python crawler.py
```

### Структура файлов после запуска

```
task1/
├── crawler.py
├── crawler.log       # лог выполнения
├── index.txt         # индекс: номер → URL
└── pages/
    ├── 001.html
    ├── 002.html
    └── ...
```

### Формат index.txt

```
1 https://www.povarenok.ru/recipes/
2 https://www.povarenok.ru/recipes/show/12345/
3 https://www.povarenok.ru/recipes/category/salads/
...
```
---
## Задание 2 — Токенизация и лемматизация

### Описание

Модуль извлекает текст из скачанных HTML-страниц, разбивает на слова (токены),
очищает от мусора и группирует по леммам (базовым формам слов).

### Зависимости

- `beautifulsoup4` — извлечение текста из HTML
- `pymorphy3` — лемматизация русского языка

Все зависимости указаны в `requirements.txt`.

### Установка

```bash
pip install -r requirements.txt
```

### Запуск

```bash
python task2/tokenizer.py
```
### Выходные файлы

**tokens.txt** — один токен на строку, без дубликатов:
```
алгоритм
программирование
компьютер
```

**lemmas_tokens.txt** — лемма и все её словоформы через пробел:
```
алгоритм алгоритм алгоритма алгоритмов алгоритму
программирование программирование программирования
```

### Примеры использования

```bash
# Запуск обработки (HTML-файлы берутся из ./pages/)
python task2/tokenizer.py

# Проверить количество токенов
wc -l task2/tokens.txt

# Проверить формат лемм
head task2/lemmas_tokens.txt
```