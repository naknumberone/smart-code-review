"""Построение графа вызовов."""

import os
import logging
from typing import Any

from .models import ParsedFile
from .config import ImpactConfig

logger = logging.getLogger(__name__)


class CallGraph:
    """Граф вызовов функций."""

    def __init__(self, repo_path: str, config: ImpactConfig):
        self.repo_path = repo_path
        self.config = config
        self._graph: dict[str, dict[str, Any]] = {}

    def build(self, file_analysis: dict[str, ParsedFile]) -> None:
        """
        Построить граф вызовов из распарсенных файлов.

        Args:
            file_analysis: словарь {file_path: ParsedFile}
        """
        logger.info("[Graph] Building call graph...")

        self._create_nodes(file_analysis)
        self._create_edges(file_analysis)

        logger.info(f"[Graph] Built with {len(self._graph)} nodes")

    def _create_nodes(self, file_analysis: dict[str, ParsedFile]) -> None:
        """Создать узлы графа из функций."""
        for file_path, parsed in file_analysis.items():
            for func in parsed.functions:
                key = f"{file_path}:{func.name}"
                self._graph[key] = {
                    "name": func.name,
                    "file": file_path,
                    "line": func.line,
                    "end_line": func.end_line,
                    "code": func.code,
                    "callers": [],
                    "callees": [],
                }

    def _create_edges(self, file_analysis: dict[str, ParsedFile]) -> None:
        """Создать рёбра графа из вызовов функций."""
        for file_path, parsed in file_analysis.items():
            for func in parsed.functions:
                caller_key = f"{file_path}:{func.name}"

                for call_name in func.calls:
                    callee_key = self._resolve_callee(
                        call_name, file_path, parsed.dependencies
                    )

                    if callee_key and callee_key in self._graph:
                        self._graph[caller_key]["callees"].append(callee_key)
                        self._graph[callee_key]["callers"].append(caller_key)

    def _resolve_callee(
        self, call_name: str, current_file: str, dependencies: list
    ) -> str | None:
        """
        Резолвить вызов в ключ графа.

        Сначала ищем в том же файле, потом в импортах.
        """
        # Пробуем в том же файле
        callee_key = f"{current_file}:{call_name}"
        if callee_key in self._graph:
            return callee_key

        # Ищем в импортах
        for dep in dependencies:
            if not dep.is_external:
                dep_file = self._resolve_import_path(dep.source, current_file)
                callee_key = f"{dep_file}:{call_name}"

                if callee_key in self._graph:
                    return callee_key

        return None

    def _resolve_import_path(self, import_path: str, current_file: str) -> str:
        """Резолвить путь импорта в путь к файлу."""
        # Обработка алиасов
        for alias, real_path in self.config.path_aliases.items():
            if import_path.startswith(alias):
                resolved = import_path.replace(alias, real_path, 1)
                return self._try_extensions(resolved)

        # Обработка относительных путей
        if import_path.startswith("."):
            current_dir = os.path.dirname(current_file)
            resolved = os.path.normpath(os.path.join(current_dir, import_path))
            return self._try_extensions(resolved)

        # Внешний пакет или неизвестный путь
        return import_path

    def _try_extensions(self, base_path: str) -> str:
        """Попробовать разные расширения для пути."""
        for suffix in self.config.import_resolution_suffixes:
            full_path = os.path.join(self.repo_path, base_path + suffix)
            if os.path.exists(full_path):
                return base_path + suffix
        return base_path

    def get_node(self, key: str) -> dict[str, Any] | None:
        """Получить узел графа по ключу."""
        return self._graph.get(key)

    def has_node(self, key: str) -> bool:
        """Проверить наличие узла в графе."""
        return key in self._graph
