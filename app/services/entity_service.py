"""Сервис извлечения сущностей из диффов."""

import logging
from dataclasses import dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

from app.constants import LANGUAGE_MAP
from app.services.git_service import FileDiff

logger = logging.getLogger(__name__)


@dataclass
class LocalCodeBlock:
    """Блок локального кода с номерами строк."""

    code: str
    start_line: int
    end_line: int


@dataclass
class FileEntities:
    """Сущности найденные в файле."""

    path: str
    top_level: list[str]  # экспортированные имена
    local_code: list[LocalCodeBlock]  # код затронутых функций/классов с номерами строк


class EntityService:
    """Сервис для поиска затронутых сущностей в коде."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.parsers = {}

    def _get_parser(self, file_path: str):
        """Получить parser для файла по расширению."""
        ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        lang = LANGUAGE_MAP.get(ext)

        if not lang:
            return None

        if lang not in self.parsers:
            self.parsers[lang] = get_parser(lang)  # type: ignore

        return self.parsers[lang]

    def extract_entities(self, files: list[FileDiff]) -> list[FileEntities]:
        """
        Извлечь сущности из списка файлов.

        Args:
            files: список файлов с диффами

        Returns:
            список FileEntities для каждого обработанного файла
        """
        results = []

        for file in files:
            try:
                entities = self._extract_from_file(file)
                if entities:
                    results.append(entities)
            except Exception as e:
                logger.warning(f"Failed to extract entities from {file.path}: {e}")

        return results

    def _extract_from_file(self, file: FileDiff) -> FileEntities | None:
        """Извлечь сущности из одного файла."""
        parser = self._get_parser(file.path)
        if not parser:
            return None

        # Читаем файл
        code = self._read_file(file.path)
        if code is None:
            return None

        # Парсим diff для получения изменённых строк
        changed_lines = self._parse_changed_lines(file.diff)
        if not changed_lines:
            return None

        # Парсим код
        root = parser.parse(code).root_node

        # Ищем затронутые сущности
        top_level = []
        local_code = []

        for child in root.children:
            if child.type == "export_statement":
                self._check_and_add_node(
                    child, code, changed_lines, top_level, local_code, is_exported=True
                )
            elif child.type in (
                "function_declaration",
                "class_declaration",
                "lexical_declaration",
                "variable_declaration",
            ):
                self._check_and_add_node(
                    child, code, changed_lines, top_level, local_code, is_exported=False
                )

        return FileEntities(
            path=file.path, top_level=list(set(top_level)), local_code=local_code
        )

    def _read_file(self, relative_path: str) -> bytes | None:
        """Прочитать содержимое файла."""
        try:
            full_path = self.repo_path / relative_path
            return full_path.read_bytes()
        except (OSError, IOError):
            return None

    def _parse_changed_lines(self, diff: str) -> set[int]:
        """Извлечь номера изменённых строк из diff."""
        changed_lines = set()

        for line in diff.split("\n"):
            if line.startswith("@@"):
                # @@ -1,2 +3,4 @@
                try:
                    part = line.split("+")[1].split(" ")[0]
                    if "," in part:
                        start, count = map(int, part.split(","))
                        changed_lines.update(range(start, start + count))
                    else:
                        changed_lines.add(int(part))
                except Exception:
                    continue

        return changed_lines

    def _check_and_add_node(
        self,
        node,
        code: bytes,
        changed_lines: set[int],
        top_level: list[str],
        local_code: list[LocalCodeBlock],
        is_exported: bool,
    ):
        """Проверить и добавить узел если он затронут изменениями."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Проверяем пересечение с изменёнными строками
        if not any(l in changed_lines for l in range(start_line, end_line + 1)):
            return

        # Извлекаем код узла
        snippet = code[node.start_byte : node.end_byte].decode()
        local_code.append(
            LocalCodeBlock(code=snippet, start_line=start_line, end_line=end_line)
        )

        # Если экспортирован - добавляем имя
        if is_exported:
            if node.type == "export_statement":
                for child in node.children:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        top_level.append(name_node.text.decode())
                        break

                    if child.type in ("lexical_declaration", "variable_declaration"):
                        for c in child.children:
                            if c.type == "variable_declarator":
                                name = c.child_by_field_name("name")
                                if name:
                                    top_level.append(name.text.decode())
            else:
                name_node = node.child_by_field_name("name")
                if name_node:
                    top_level.append(name_node.text.decode())
