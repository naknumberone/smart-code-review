# Smart Code Review

Умный ревьюер кода на базе LLM с анализом влияния изменений.

## Что делает проект

Сервис анализирует изменения в git-ветке и генерирует детальный code review с использованием LLM.

**Основные возможности:**

- Автоматическое извлечение измененных функций и классов из diff
- Анализ влияния изменений на остальной код через граф вызовов
- Контекстный review с учетом того, где используется измененный код
- Структурированный вывод в JSON формате

**Как это работает:**

Проект использует `git merge-base` для нахождения точки ответвления, затем сравнивает изменения от этой точки до последнего коммита в анализируемой ветке. Находит измененные функции, строит граф вызовов по всему проекту, определяет где эти функции используются, и формирует контекстные промпты для LLM с полной информацией об изменениях и их влиянии.

**Подробнее:**

- [Как работает извлечение сущностей](__docs__/ENTITY_SERVICE.md)
- [Как работает анализ влияния](__docs__/IMPACT_SERVICE.md)
- [Как работает батчинг и бюджетирование](__docs__/REVIEW_BATCHING.md)

## Установка

### Требования

- Python 3.10+
- Git репозиторий для анализа

### Быстрый старт

```bash
# 1. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Создать .env файл
cp .env.example .env

# 4. Заполнить обязательные параметры в .env
# LLM_API_KEY=your-openai-key
# REPO_PATH=/path/to/your/repo
# BASE_BRANCH=main
# TARGET_BRANCH=feature-branch

# 5. Перейти в локальном репозитории в ветку TARGET_BRANCH самостоятельно

# 6. Запустить анализ
python -m app.main
```

## Конфигурация (.env)

### Обязательные параметры

```bash
# Путь к git-репозиторию
REPO_PATH=/path/to/your/repo

# Базовая ветка (с чем сравниваем)
BASE_BRANCH=main

# Целевая ветка (что анализируем)
TARGET_BRANCH=feature-branch

# LLM конфигурация
LLM_API_URL=https://api.openai.com/v1  # можно использовать совместимые API
LLM_MODEL=gpt-4                        # или gpt-3.5-turbo, claude-3, etc
LLM_API_KEY=sk-...                     # API ключ
```

### Опциональные параметры

```bash
# Бюджет символов для одного промпта (влияет на разбиение на паки)
PROMPT_BUDGET_CHARS=50000

# Размер батча для финализации ревью (сколько ревью обрабатывать за раз)
FINALIZE_BATCH_SIZE=4

# Цены за токены (используется для подсчета стоимости)
# По умолчанию используется pricing OpenAI для gpt-4o-mini
LLM_PRICE_PER_MILLION_INPUT_TOKENS=0.150   # $0.15 за 1M input токенов
LLM_PRICE_PER_MILLION_OUTPUT_TOKENS=0.600  # $0.60 за 1M output токенов
```

### Результаты

После завершения будут созданы файлы в папке `__artifacts__/YYYY-MM-DD_HH-MM-SS.branch-name/`:

- `1.prompt.md`, `2.prompt.md`, ... - промпты отправленные в LLM
- `1.review.md`, `2.review.md`, ... - ответы от LLM по каждому паку
- `1.finalized.json`, `2.finalized.json`, ... - финализированные ревью по батчам
- `review.final.json` - финальный структурированный review со всеми комментариями

```json
{
  "summary": "Краткое резюме изменений",
  "comments": [
    {
      "file": "path/to/file.ts",
      "line": 42,
      "severity": "high",
      "message": "Описание проблемы",
      "suggestion": "Предложение по исправлению"
    }
  ]
}
```

## Зависимости

- **gitpython** - работа с git репозиториями
- **openai** - клиент для LLM API
- **tree-sitter** - парсинг кода (AST)
- **pydantic** - валидация конфигурации

## Примеры использования

### Пример 1: Анализ feature ветки

```bash
# .env
REPO_PATH=/Users/me/my-project
BASE_BRANCH=main
TARGET_BRANCH=feature/new-auth
LLM_API_KEY=sk-xxx

# Запуск
python -m app.main
```

### Пример 2: Использование с локальной LLM (через Ollama)

```bash
# .env
LLM_API_URL=http://localhost:11434/v1  # Ollama совместим с OpenAI API
LLM_MODEL=llama2
LLM_API_KEY=dummy  # не используется для локальной LLM
```

## Ограничения

- Поддерживаются только TypeScript/JavaScript файлы (`.ts`, `.tsx`, `.js`, `.jsx`)
- Impact-анализ не работает для динамических импортов
- Большие репозитории могут требовать много времени на первый запуск
