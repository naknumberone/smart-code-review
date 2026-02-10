"""Анализ импакта для сущностей."""

import logging
from collections import deque

from .models import EntityImpact, CallerInfo
from .call_graph import CallGraph
from .config import ImpactConfig

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """Анализ импакта для сущностей через граф вызовов."""

    def __init__(self, call_graph: CallGraph, config: ImpactConfig):
        self.call_graph = call_graph
        self.config = config

    def analyze(self, entity_name: str, file_path: str) -> EntityImpact | None:
        """
        Анализ импакта для сущности.

        Args:
            entity_name: имя функции/компонента
            file_path: путь к файлу

        Returns:
            EntityImpact с прямыми и транзитивными вызывающими
        """
        key = f"{file_path}:{entity_name}"

        if not self.call_graph.has_node(key):
            return None

        # BFS для поиска всех вызывающих
        direct_keys, all_keys, affected_files = self._find_callers(key)

        return EntityImpact(
            entity_name=entity_name,
            file=file_path,
            direct_callers=self._keys_to_caller_infos(direct_keys),
            all_callers=self._keys_to_caller_infos(all_keys),
            affected_files=list(affected_files),
        )

    def _find_callers(self, start_key: str) -> tuple[list[str], set[str], set[str]]:
        """
        Найти всех вызывающих через BFS.

        Returns:
            (direct_callers, all_callers, affected_files)
        """
        visited = set()
        queue = deque([(start_key, 0)])
        direct = []
        all_callers = set()
        files = set()

        while queue:
            key, depth = queue.popleft()

            if key in visited or depth > self.config.max_depth:
                continue

            visited.add(key)
            node = self.call_graph.get_node(key)

            if not node:
                continue

            for caller_key in node["callers"]:
                if depth == 0:
                    direct.append(caller_key)

                all_callers.add(caller_key)
                files.add(caller_key.split(":")[0])
                queue.append((caller_key, depth + 1))

        return direct, all_callers, files

    def _keys_to_caller_infos(self, keys: list[str] | set[str]) -> list[CallerInfo]:
        """Преобразовать ключи графа в CallerInfo объекты."""
        caller_infos = []

        for key in keys:
            node = self.call_graph.get_node(key)
            if node:
                caller_infos.append(
                    CallerInfo(
                        file=node["file"],
                        line=node["line"],
                        end_line=node["end_line"],
                        name=node["name"],
                        code=node["code"],
                    )
                )

        return caller_infos
