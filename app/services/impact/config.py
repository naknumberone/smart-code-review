"""Конфигурация для импакт-анализа."""

from dataclasses import dataclass, field

from app.constants import LANGUAGE_MAP


@dataclass
class ImpactConfig:
    """Конфигурация анализа импакта."""

    # Расширения файлов для анализа
    file_extensions: tuple[str, ...] = tuple(f".{ext}" for ext in LANGUAGE_MAP.keys())

    # Максимальная глубина поиска вызывающих
    max_depth: int = 5

    # Алиасы путей (для резолва импортов)
    path_aliases: dict[str, str] = field(
        default_factory=lambda: {"app/": "allure-gateway-service/src/main/javascript/"}
    )

    # Суффиксы для резолва импортов в Node.js/JS экосистеме (пробуем по порядку)
    import_resolution_suffixes: tuple[str, ...] = (
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        "/index.ts",
        "/index.tsx",
        "/index.js",
        "/index.jsx",
    )
