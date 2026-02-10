"""Модели данных для импакт-анализа."""

from dataclasses import dataclass


@dataclass
class FunctionInfo:
    """Информация о функции."""

    name: str
    line: int
    end_line: int
    code: str
    calls: list[str]


@dataclass
class DependencyInfo:
    """Информация о зависимости."""

    source: str
    is_external: bool


@dataclass
class CallerInfo:
    """Информация о вызывающей функции."""

    file: str
    line: int
    end_line: int
    name: str
    code: str


@dataclass
class EntityImpact:
    """Результат анализа импакта для одной сущности."""

    entity_name: str
    file: str
    direct_callers: list[CallerInfo]
    all_callers: list[CallerInfo]
    affected_files: list[str]


@dataclass
class ParsedFile:
    """Результат парсинга файла."""

    functions: list[FunctionInfo]
    dependencies: list[DependencyInfo]
