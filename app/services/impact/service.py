"""Главный сервис импакт-анализа (фасад)."""

import os
import logging

from .models import EntityImpact, ParsedFile
from .config import ImpactConfig
from .file_scanner import FileScanner
from .ast_parser import ASTParser
from .call_graph import CallGraph
from .impact_analyzer import ImpactAnalyzer

logger = logging.getLogger(__name__)


class ImpactService:
    """Сервис для анализа импакта изменённых сущностей."""

    def __init__(self, repo_path: str, config: ImpactConfig | None = None):
        self.repo_path = repo_path
        self.config = config if config is not None else ImpactConfig()

        self.scanner = FileScanner(repo_path, self.config)
        self.parser = ASTParser(self.config)
        self.call_graph = CallGraph(repo_path, self.config)
        self.analyzer = ImpactAnalyzer(self.call_graph, self.config)

        # Кэш распарсенных файлов
        self._file_analysis: dict[str, ParsedFile] = {}

    def analyze_impact(self, entities_result: list) -> dict[str, list[EntityImpact]]:
        """
        Анализировать импакт для сущностей из entities_result.

        Args:
            entities_result: список FileEntities с полями path и top_level

        Returns:
            словарь где ключ - путь к файлу, значение - список EntityImpact
        """
        logger.info("[Impact] Starting impact analysis...")

        self._scan_and_parse()
        self.call_graph.build(self._file_analysis)

        # Анализируем импакт для каждой сущности
        result = {}

        for entities in entities_result:
            file_path = entities.path
            top_level_entities = entities.top_level

            if not top_level_entities:
                continue

            entity_impacts = []

            for entity_name in top_level_entities:
                impact = self.analyzer.analyze(entity_name, file_path)
                if impact:
                    entity_impacts.append(impact)

            if entity_impacts:
                result[file_path] = entity_impacts
                self._log_impacts(entity_impacts, file_path)

        logger.info(f"[Impact] Complete. Analyzed {len(result)} files")
        return result

    def _scan_and_parse(self) -> None:
        """Сканировать и парсить все файлы проекта."""
        files = self.scanner.scan()

        for file_path in files:
            full_path = os.path.join(self.repo_path, file_path)

            try:
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()

                filename = os.path.basename(file_path)
                parsed = self.parser.parse_file(content, filename)
                self._file_analysis[file_path] = parsed

            except Exception as e:
                logger.debug(f"Failed to parse {file_path}: {e}")

        logger.info(f"[Impact] Parsed {len(self._file_analysis)} files")

    def _log_impacts(self, impacts: list[EntityImpact], file_path: str) -> None:
        """Логировать информацию об импактах."""
        for impact in impacts:
            logger.info(
                f"[Impact] {impact.entity_name} in {file_path}: "
                f"Direct: {len(impact.direct_callers)}, Total: {len(impact.all_callers)}"
            )
