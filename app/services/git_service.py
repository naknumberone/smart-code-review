"""Git-сервис для операций с диффом веток."""

import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from git import Repo

logger = logging.getLogger(__name__)


@dataclass
class FileDiff:
    """Представляет файл с его diff."""

    path: str
    diff: str
    status: str  # A, M, D, R


@dataclass
class BranchDiffResult:
    """Результат сравнения ветки с main."""

    branch_name: str
    base_commit: str  # первый коммит перед ответвлением (merge-base)
    head_commit: str  # последний коммит в ветке
    files: list[FileDiff]

    def to_dict(self) -> dict:
        """Преобразовать в словарь для JSON сериализации."""
        return asdict(self)


class GitService:
    """Сервис для получения диффов между веткой и main."""

    def __init__(self, repo_path: str):
        """
        Инициализация сервиса.

        Args:
            repo_path: путь к репозиторию
        """
        self.repo_path = Path(repo_path)
        self.repo = Repo(self.repo_path)

    def get_current_branch(self) -> str:
        """
        Получить название текущей ветки.

        Returns:
            Название текущей ветки
        """
        return self.repo.active_branch.name

    def get_branch_diff(self, branch: str, base_branch: str) -> BranchDiffResult:
        """
        Получить diff ветки относительно base_branch.

        Args:
            branch: ветка для анализа
            base_branch: базовая ветка

        Returns:
            BranchDiffResult с информацией о изменениях
        """

        logger.info(f"Getting diff for branch '{branch}' from '{base_branch}'")

        # Получаем коммиты
        merge_base_commit = self.repo.merge_base(base_branch, branch)[0]
        head_commit = self.repo.commit(branch)

        logger.info(f"Merge base: {merge_base_commit.hexsha}")
        logger.info(f"Head commit: {head_commit.hexsha}")

        # Получаем список измененных файлов и их диффы через git напрямую
        diff_output = self.repo.git.diff(
            f"{merge_base_commit.hexsha}..{head_commit.hexsha}", "--name-status"
        )

        files = []
        for line in diff_output.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0][0]  # A, M, D, R, etc
            file_path = parts[-1]  # последний элемент - всегда путь файла

            # Получаем diff для файла
            file_diff = self.repo.git.diff(
                f"{merge_base_commit.hexsha}..{head_commit.hexsha}", "--", file_path
            )

            files.append(FileDiff(path=file_path, diff=file_diff, status=status))

        return BranchDiffResult(
            branch_name=branch,
            base_commit=merge_base_commit.hexsha,
            head_commit=head_commit.hexsha,
            files=files,
        )
