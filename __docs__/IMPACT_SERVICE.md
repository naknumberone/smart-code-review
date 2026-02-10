# Impact Service - Анализ влияния изменений

## Цель

Найти все места в коде, где используются измененные функции или классы. Понять масштаб влияния изменений.

## Зачем это нужно

Когда вы меняете функцию, важно знать:

- Где она вызывается?
- Сколько мест затронуто?
- Какие другие функции зависят от нее?

Это помогает LLM дать более качественный review, учитывая контекст использования.

## Как это работает

### Общая схема

```
1. Сканируем весь проект → находим все файлы
2. Парсим каждый файл → извлекаем функции и их вызовы
3. Строим граф вызовов → кто кого вызывает
4. Ищем в графе → кто вызывает измененную функцию
```

### Шаг 1: Сканирование проекта (FileScanner)

Обходим все папки проекта и собираем TypeScript/JavaScript файлы.

**Что фильтруем:**

- Исключаем `.git` (служебная папка)
- Учитываем `.gitignore` (через него исключаются `node_modules`, `dist`, `build` и т.д.)
- Берем только `.ts`, `.tsx`, `.js`, `.jsx`

### Шаг 2: Парсинг файлов (ASTParser)

Для каждого файла извлекаем:

**Функции:**

```typescript
function getData() {
  // ← нашли функцию
  fetchApi(); // ← нашли вызов
  processData(); // ← нашли вызов
}
```

Сохраняем:

- Имя функции: `getData`
- Что она вызывает: `[fetchApi, processData]`
- Код функции, номера строк

**Импорты:**

```typescript
import { fetchApi } from "./api"; // ← внутренний импорт (относительный путь)
import { Button } from "app/components"; // ← внутренний импорт (алиас app/)
import { useState } from "react"; // ← внешний импорт
```

Различаем внутренние и внешние импорты. Импорты с алиасом `app/` также считаются внутренними.

### Шаг 3: Построение графа (CallGraph)

Граф - это структура данных, где каждая функция - это узел, а вызов - это ребро.

**Пример:**

```
File: api.ts
  function fetchApi() { ... }

File: service.ts
  import { fetchApi } from './api'
  function getData() {
    fetchApi()  // ← вызов
  }

Граф:
  api.ts:fetchApi ← service.ts:getData
```

**Ключ узла:** `file_path:function_name`

**Данные узла:**

```python
{
  'name': 'getData',
  'file': 'service.ts',
  'line': 5,
  'end_line': 10,
  'code': 'function getData() { ... }',
  'callers': ['другие функции, которые вызывают getData'],
  'callees': ['функции, которые getData вызывает']
}
```

**Резолв импортов:**

Когда видим вызов `fetchApi()` в `service.ts`, нужно понять - это какая функция?

1. Ищем в том же файле
2. Смотрим импорты: `import { fetchApi } from './api'`
3. Резолвим путь: `./api` + расширения → `api.ts`
4. Находим узел: `api.ts:fetchApi`

Поддержка алиасов:

```typescript
import { Button } from "app/components/Button";
// 'app/' → 'src/main/javascript/' (настраивается)
```

### Шаг 4: Анализ влияния (ImpactAnalyzer)

Для измененной функции ищем всех вызывающих через **BFS** (поиск в ширину).

**Пример:**

Изменили функцию `fetchApi`:

```
fetchApi       ← прямые вызывающие:
  ↑              - getData
  getData        - loadUser
  ↑
  render       ← транзитивные вызывающие:
                 - render (вызывает getData, который вызывает fetchApi)
```

**Алгоритм BFS:**

```python
from collections import deque

visited = set()
queue = deque([(fetchApi, 0)])  # (key, depth)
direct = []
all_callers = set()
files = set()

while queue:
    key, depth = queue.popleft()

    if key in visited or depth > max_depth:
        continue

    visited.add(key)
    node = graph.get_node(key)

    for caller_key in node['callers']:
        if depth == 0:
            direct.append(caller_key)

        all_callers.add(caller_key)
        files.add(caller_key.split(':')[0])
        queue.append((caller_key, depth + 1))
```

Собираем:

- **direct_callers** - функции, которые напрямую вызывают измененную (depth=0)
- **all_callers** - все вызывающие включая транзитивные (до глубины max_depth=5)
- **affected_files** - список файлов, которые затронуты

### Результат

Для каждой измененной функции получаем `EntityImpact`:

```python
EntityImpact(
    entity_name="fetchApi",
    file="api.ts",
    direct_callers=[
        CallerInfo(
            file="service.ts",
            line=15,
            end_line=20,
            name="getData",
            code="function getData() {\n  return fetchApi()\n}"
        )
    ],
    all_callers=[...],  # включая транзитивные
    affected_files=["service.ts", "components/User.tsx"]
)
```

## Для чего используется результат

LLM видит не только изменение в `fetchApi`, но и:

- Эта функция вызывается в 5 местах
- Код вызывающих функций (контекст использования)
- Какие файлы затронуты

Это помогает дать более качественный review:

- "Вы поменяли сигнатуру функции, но не обновили вызов в service.ts:15"
- "Это критичное изменение - функция используется в 10 местах"

## Конфигурация

**Глубина поиска (max_depth):**

```python
max_depth = 5  # искать транзитивные вызовы до 5 уровней
```

**Алиасы путей (path_aliases):**

```python
path_aliases = {
    'app/': 'src/main/javascript/'
}
```

**Расширения для резолва:**

```python
import_extensions = (
    '.ts', '.tsx', '.js', '.jsx',
    '/index.ts', '/index.tsx'
)
```

## Производительность

**Кэширование:**
Сейчас граф строится каждый раз заново. Для больших проектов это может быть медленно.
