# Smart Code Review

Умный ревьюер кода на базе LLM с анализом влияния изменений.

## Возможности

- Автоматическое извлечение измененных функций и классов из diff
- Анализ влияния изменений на остальной код через граф вызовов
- Контекстный review с учетом того, где используется измененный код
- Структурированный вывод в JSON формате

**Документация:**

- [Как работает извлечение сущностей](__docs__/ENTITY_SERVICE.md)
- [Как работает анализ влияния](__docs__/IMPACT_SERVICE.md)
- [Как работает батчинг и бюджетирование](__docs__/REVIEW_BATCHING.md)

## Установка

### Требования

- Python 3.10+
- Git репозиторий для анализа

### Быстрый старт

```bash
# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac или venv\Scripts\activate для Windows

# Установить зависимости
pip install -r requirements.txt

# Создать и настроить .env
cp .env.example .env
# Отредактировать .env - указать пути, ветки и API ключ

# Переключиться на целевую ветку в анализируемом репозитории
# Запустить ревью
python -m app.main
```

## Конфигурация

Основные параметры в `.env`:

```bash
# Обязательные
REPO_PATH=/path/to/your/repo              # Путь к git-репозиторию
BASE_BRANCH=main                          # Базовая ветка (с чем сравниваем)
TARGET_BRANCH=feature-branch              # Целевая ветка (что анализируем)
LLM_API_URL=https://api.openai.com/v1    # API endpoint (можно использовать совместимые)
LLM_MODEL=gpt-4                           # Модель (gpt-4o-mini и тп)
LLM_API_KEY=sk-...                        # API ключ

# Опциональные
PROMPT_BUDGET_CHARS=50000                        # Бюджет символов на промпт
FINALIZE_BATCH_SIZE=4                            # Размер батча для финализации
MAX_STAGES=0                                     # Максимум stages (0 = без лимита)
LLM_PRICE_PER_MILLION_INPUT_TOKENS=0.150        # Цена за 1M input токенов
LLM_PRICE_PER_MILLION_OUTPUT_TOKENS=0.600       # Цена за 1M output токенов
```

Для локальных или прокси LLM измените `LLM_API_URL`.

## Результаты

После завершения в папке `__artifacts__/YYYY-MM-DD_HH-MM-SS.branch-name/` создаются:

- `*.prompt.md` - промпты для LLM
- `*.review.md` - ответы от LLM
- `*.finalized.json` - финализированные ревью
- `review.final.json` - итоговый файл с комментариями (file, line, severity, message, suggestion)

## Пример запуска

```bash
# .env
REPO_PATH=/Users/me/my-project
BASE_BRANCH=main
TARGET_BRANCH=feature/new-auth
LLM_API_KEY=sk-xxx

# Запуск
python -m app.main
```

## Ограничения

- Поддерживаются только TypeScript/JavaScript файлы (`.ts`, `.tsx`, `.js`, `.jsx`)
- Impact-анализ не работает для динамических импортов
- Большие репозитории могут требовать много времени на первый запуск
