"""Сканирование файлов с поддержкой gitignore."""

import os
import logging
from pathlib import Path
import pathspec

from .config import ImpactConfig

logger = logging.getLogger(__name__)


class FileScanner:
    """Сканирование файлов проекта с учётом .gitignore."""

    def __init__(self, repo_path: str, config: ImpactConfig):
        self.repo_path = repo_path
        self.config = config
        self._gitignore_spec = self._load_gitignore()

    def _load_gitignore(self) -> pathspec.PathSpec | None:
        """Загрузить .gitignore."""
        gitignore_path = Path(self.repo_path) / ".gitignore"
        if not gitignore_path.exists():
            return None

        with open(gitignore_path) as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)

    def scan(self) -> list[str]:
        """
        Сканировать проект и вернуть список файлов для анализа.

        Returns:
            Список относительных путей к файлам
        """
        logger.info("[Scanner] Scanning files...")
        files = []

        for root, dirs, filenames in os.walk(self.repo_path):
            rel_root = os.path.relpath(root, self.repo_path)

            # Фильтруем директории
            dirs[:] = self._filter_directories(dirs, rel_root)

            # Собираем подходящие файлы
            for filename in filenames:
                if self._should_include_file(filename, rel_root):
                    rel_path = os.path.relpath(
                        os.path.join(root, filename), self.repo_path
                    )
                    files.append(rel_path)

        logger.info(f"[Scanner] Found {len(files)} files")
        return files

    def _filter_directories(self, dirs: list[str], rel_root: str) -> list[str]:
        """Фильтровать директории по .gitignore."""
        # Всегда исключаем .git (служебная папка)
        filtered = [d for d in dirs if d != ".git"]

        # Остальное фильтруем по .gitignore
        if self._gitignore_spec:
            filtered = [
                d
                for d in filtered
                if not self._gitignore_spec.match_file(f"{rel_root}/{d}/")
            ]

        return filtered

    def _should_include_file(self, filename: str, rel_root: str) -> bool:
        """Проверить, нужно ли включать файл в анализ."""
        # Проверка расширения
        if not filename.endswith(self.config.file_extensions):
            return False

        # Проверка .gitignore
        if self._gitignore_spec:
            rel_path = os.path.join(rel_root, filename)
            if self._gitignore_spec.match_file(rel_path):
                return False

        return True
