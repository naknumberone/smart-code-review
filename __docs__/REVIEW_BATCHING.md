# Батчирование и бюджетирование в Review Pipeline

## Общая идея

Пайплайн обрабатывает код-ревью в два этапа батчирования:

1. **Review Batches** — делим файлы на порции и отправляем на ревью
2. **Finalize Batches** — объединяем результаты ревью в финальный отчёт

Это нужно, потому что:

- LLM имеет лимит размера промпта
- Параллельная обработка ускоряет процесс
- Удобно контролировать расходы токенов

---

## 1. Review Batches — ревью кода

### Что это?

После анализа изменений (diff, entities, impact), каждый изменённый файл превращается в **stage** — структуру данных с:

- diff файла
- локальным кодом изменённых функций
- информацией о том, где используются экспорты

### Как работает бюджет?

**`prompt_budget_chars: int = 50000`** (по умолчанию)

Это лимит символов для одного промпта. Система:

1. Превращает каждый stage в текст (markdown с кодом, диффами, usage)
2. Упаковывает stages в **паки** до тех пор, пока их суммарный размер не превысит `prompt_budget_chars`
3. К каждому паку добавляет системный промпт (инструкции для LLM)

```python
# app/services/review_service.py, строка 119-141
def _pack_prompts(self, stage_prompts: list[str], budget_chars: int):
    packs = []
    current_pack = ""
    system_size = len(SYSTEM_PROMPT) + SYSTEM_PROMPT_OVERHEAD

    for prompt in stage_prompts:
        # Если добавление этого stage превысит лимит — начинаем новый пак
        if len(current_pack) + len(prompt) + system_size > budget_chars:
            if current_pack:
                packs.append(current_pack)
            current_pack = prompt
        else:
            # Иначе добавляем в текущий пак
            if current_pack:
                current_pack += STAGE_SEPARATOR
            current_pack += prompt

    # Последний пак
    if current_pack:
        packs.append(current_pack)

    return packs
```

### Результат

Получаем список промптов (паков), каждый ≤ `prompt_budget_chars` символов.

**Пример:**

- 10 файлов изменено
- Каждый stage ~8000 символов
- Бюджет 50000
- Результат: 2 пака (по 5 файлов в каждом)

### Отправка на ревью

```python
# app/main.py, строка 205-232
async def review_prompts(self, prompts: list[str]):
    # Все промпты отправляются параллельно через asyncio.gather
    tasks = [process_prompt(i, prompt) for i, prompt in enumerate(prompts, 1)]
    results = await asyncio.gather(*tasks)
    return [review for _, review in sorted(results)]
```

**Все паки обрабатываются параллельно** — это быстро!

Сохраняются как:

- `1.prompt.md` — что отправили
- `1.review.md` — что получили

---

## 2. Finalize Batches — сборка финального отчёта

### Проблема

После review_prompts у нас есть N ответов от LLM (markdown с комментариями). Нужно:

- Превратить их в единый JSON
- Объединить все комментарии

Если отправить все N ответов в один промпт — получится слишком длинный запрос.

### Решение

**`finalize_batch_size: int = 4`** (по умолчанию)

Делим ревью на батчи по 4 штуки и обрабатываем параллельно.

```python
# app/main.py, строка 234-288
async def generate_final_summary(self, reviews: list[str]):
    batch_size = self.config.finalize_batch_size  # 4

    # Разбиваем на батчи
    batches = [
        reviews[i : i + batch_size]
        for i in range(0, len(reviews), batch_size)
    ]

    # Каждый батч обрабатывается параллельно
    tasks = []
    for batch_num, batch in enumerate(batches, 1):
        tasks.append(finalize_batch(batch_num, batch))

    results = await asyncio.gather(*tasks)
    finalized_reviews = [summary for _, summary in sorted(results)]

    # Объединяем JSON из всех батчей
    all_comments = []
    for summary in finalized_reviews:
        data = self._parse_json_response(summary)
        all_comments.extend(data.get("comments", []))

    return {"summary": "Final review", "comments": all_comments}
```

### Как работает?

1. **Разбивка**: 10 ревью → 3 батча (4+4+2)
2. **Параллельная финализация**: каждый батч → JSON с комментариями
3. **Объединение**: собираем все комментарии в один массив

**Пример:**

```
Ревью: [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10]
         ↓
Батчи: [[r1,r2,r3,r4], [r5,r6,r7,r8], [r9,r10]]
         ↓ (параллельно)
JSON:  [{comments: [...]}, {comments: [...]}, {comments: [...]}]
         ↓
Итог:  {comments: [...все вместе...]}
```

Сохраняются как:

- `1.finalized.json` — результат первого батча
- `2.finalized.json` — результат второго батча
- `review.final.json` — финальный объединённый результат

---

## Настройка параметров

### В `.env` файле:

```bash
# Лимит stages
MAX_STAGES=0               # Максимум stages для обработки (0 = без лимита)

# Ревью батчи
PROMPT_BUDGET_CHARS=50000  # Максимум символов в одном промпте

# Финализация батчи
FINALIZE_BATCH_SIZE=4      # Сколько ревью финализировать за раз
```

### Как выбрать значения?

**`max_stages`:**

- 0 → без лимита, обрабатываются все файлы
- Положительное значение → обрабатываются только первые N stages (файлов)
- Полезно для отладки или ограничения расходов на больших ветках

**`prompt_budget_chars`:**

- Слишком мало (20000) → много паков → долго
- Слишком много (200000) → может превысить лимит модели
- Оптимально: 30000-80000 (зависит от модели)

**`finalize_batch_size`:**

- Слишком мало (1-2) → недогружаем параллельность
- Слишком много (10+) → один батч может быть слишком большим
- Оптимально: 3-6

---

## Статистика и мониторинг

### Budget Tracker

Отслеживает использование токенов:

```python
# app/main.py, строка 143-153
def _log_budget_summary(self):
    summary = self.budget_tracker.get_summary()
    logger.info(f"Budget: {summary['total_tokens']:,} tokens | ${summary['estimated_cost_usd']:.4f} USD")
    logger.info(f"  ↳ Input: {summary['input_tokens']:,} | Output: {summary['output_tokens']:,}")
```

### Логи процесса

```
[5/7] Prompts created: 3 packs, 120,450 chars total
[6/7] Pack 1/3: ✓ 15,234 tokens
[6/7] Pack 2/3: ✓ 14,892 tokens
[6/7] Pack 3/3: ✓ 12,456 tokens
[7/7] Finalize batch 1/1: ✓ 8,123 tokens
───────────────────────────────────────────────────────────
Budget: 50,705 tokens | $0.0345 USD
  ↳ Input: 42,582 | Output: 8,123
───────────────────────────────────────────────────────────
```

---

## Схема работы

```
Изменённые файлы (N шт)
         ↓
   Stages (N шт)
         ↓
max_stages (обрезка, если задан)
         ↓
format_prompts(budget=50k)
         ↓
   Промпты-паки (M шт, M <= N)
         ↓
review_prompts() — параллельно
         ↓
   Ревью (M шт markdown)
         ↓
generate_final_summary(batch_size=4)
         ↓
   Финализация (K батчей, K = ceil(M/4)) — параллельно
         ↓
   Финальный JSON с комментариями
```

**Ключевые моменты:**

- **Лимит stages**: `max_stages` ограничивает число файлов до упаковки в промпты
- **Две стадии батчирования**: review → finalize
- **Два параллельных процесса**: `asyncio.gather` для скорости
- **Три бюджетных параметра**: лимит stages, символы для промптов, размер батча для финализации
