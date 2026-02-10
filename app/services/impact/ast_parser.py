"""Парсинг AST для извлечения функций и зависимостей."""

import logging
from typing import cast
from tree_sitter_language_pack import get_parser, SupportedLanguage

from app.constants import LANGUAGE_MAP
from .models import FunctionInfo, DependencyInfo, ParsedFile
from .config import ImpactConfig

logger = logging.getLogger(__name__)


class ASTParser:
    """Парсер для извлечения функций и зависимостей из AST."""

    def __init__(self, config: ImpactConfig):
        self.config = config

    def parse_file(self, content: str, filename: str) -> ParsedFile:
        """
        Парсинг файла для извлечения функций и зависимостей.

        Returns:
            ParsedFile с функциями и зависимостями
        """
        lang = self._detect_language(filename)
        if not lang:
            return ParsedFile(functions=[], dependencies=[])

        parser = get_parser(cast(SupportedLanguage, lang))
        tree = parser.parse(bytes(content, "utf8"))

        return ParsedFile(
            functions=self._extract_functions(tree.root_node),
            dependencies=self._extract_dependencies(tree.root_node),
        )

    def _detect_language(self, filename: str):
        """Определить язык по расширению файла."""
        for ext, lang in LANGUAGE_MAP.items():
            if filename.endswith(f".{ext}"):
                return lang
        return None

    def _extract_functions(self, node) -> list[FunctionInfo]:
        """Извлечь функции из AST."""
        functions = []

        def visit(n):
            if n.type == "function_declaration":
                name_node = n.child_by_field_name("name")
                if name_node:
                    functions.append(
                        FunctionInfo(
                            name=name_node.text.decode(),
                            line=n.start_point[0] + 1,
                            end_line=n.end_point[0] + 1,
                            code=n.text.decode(),
                            calls=self._extract_calls(n),
                        )
                    )

            elif n.type == "class_declaration":
                name_node = n.child_by_field_name("name")
                if name_node:
                    functions.append(
                        FunctionInfo(
                            name=name_node.text.decode(),
                            line=n.start_point[0] + 1,
                            end_line=n.end_point[0] + 1,
                            code=n.text.decode(),
                            calls=self._extract_calls(n),
                        )
                    )

            elif n.type == "method_definition":
                name_node = n.child_by_field_name("name")
                if name_node:
                    functions.append(
                        FunctionInfo(
                            name=name_node.text.decode(),
                            line=n.start_point[0] + 1,
                            end_line=n.end_point[0] + 1,
                            code=n.text.decode(),
                            calls=self._extract_calls(n),
                        )
                    )

            elif n.type == "variable_declarator":
                name_node = n.child_by_field_name("name")
                value_node = n.child_by_field_name("value")

                if (
                    name_node
                    and value_node
                    and value_node.type
                    in ["arrow_function", "function_expression", "function"]
                ):
                    functions.append(
                        FunctionInfo(
                            name=name_node.text.decode(),
                            line=n.start_point[0] + 1,
                            end_line=n.end_point[0] + 1,
                            code=n.text.decode(),
                            calls=self._extract_calls(value_node),
                        )
                    )

            for child in n.children:
                visit(child)

        visit(node)
        return functions

    def _extract_calls(self, node) -> list[str]:
        """Извлечь вызовы функций из узла."""
        calls = set()

        def visit(n):
            if n.type == "call_expression":
                func = n.child_by_field_name("function")
                if func:
                    if func.type == "identifier":
                        calls.add(func.text.decode())
                    elif func.type == "member_expression":
                        prop = func.child_by_field_name("property")
                        if prop:
                            calls.add(prop.text.decode())

            elif n.type in ["jsx_element", "jsx_self_closing_element"]:
                for child in n.children:
                    if child.type == "jsx_opening_element":
                        for subchild in child.children:
                            if subchild.type == "identifier":
                                calls.add(subchild.text.decode())
                                break
                    elif child.type == "identifier":
                        calls.add(child.text.decode())
                        break

            for child in n.children:
                visit(child)

        visit(node)
        return list(calls)

    def _extract_dependencies(self, node) -> list[DependencyInfo]:
        """Извлечь импорты из AST."""
        deps = []

        def visit(n):
            if n.type == "import_statement":
                source = n.child_by_field_name("source")
                if source:
                    path = source.text.decode().strip("\"'")
                    # Считаем алиас "app/" внутренним (не external)
                    is_external = not (path.startswith(".") or path.startswith("app/"))
                    deps.append(DependencyInfo(source=path, is_external=is_external))

            for child in n.children:
                visit(child)

        visit(node)
        return deps
