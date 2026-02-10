"""Сервис ревью для форматирования данных в промпты."""

import logging

from app.services.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# Константы для форматирования
STAGE_SEPARATOR = "\n\n---\n\n"
SYSTEM_PROMPT_OVERHEAD = 50  # Доп. символы для разделителей


class ReviewService:
    """Сервис для форматирования данных в промпты для LLM ревью."""

    def format_stages(self, diff_result, entities_result, impact_result) -> list:
        """
        Форматировать данные в stages для ревью.

        Stage = один измененный файл со всеми его данными:
        - diff, entities, impact

        Returns:
            Список stages, по одному на каждый обработанный файл
        """
        # Создаем словарь для быстрого поиска diff по пути
        diff_by_path = {f.path: f for f in diff_result.files}

        stages = []
        for file_entities in entities_result:
            stage = self._create_stage(
                file_entities,
                diff_by_path.get(file_entities.path),
                impact_result.get(file_entities.path, []),
            )
            stages.append(stage)

        return stages

    def _create_stage(self, file_entities, file_diff, impacts) -> dict:
        """Создать stage для одного файла."""
        stage = {
            "file": file_entities.path,
            "status": file_diff.status if file_diff else "M",
            "diff": file_diff.diff if file_diff else "",
            "changed_exports": self._format_changed_exports(
                file_entities.top_level, impacts
            ),
            "local_changes": self._format_local_changes(file_entities.local_code),
        }
        return stage

    def _format_changed_exports(
        self, top_level_names: list[str], impacts: list
    ) -> list:
        """Форматировать информацию об изменённых экспортах."""
        exports = []

        for entity_name in top_level_names:
            entity = {"name": entity_name, "impact": None}

            # Ищем impact для этой сущности
            for impact in impacts:
                if impact.entity_name == entity_name:
                    entity["impact"] = {
                        "usage_count": len(impact.all_callers),
                        "direct_usage_count": len(impact.direct_callers),
                        "affected_files": impact.affected_files,
                        "direct_callers": [
                            {
                                "file": c.file,
                                "line": c.line,
                                "end_line": c.end_line,
                                "name": c.name,
                                "code": c.code,
                            }
                            for c in impact.direct_callers
                        ],
                    }
                    break

            exports.append(entity)

        return exports

    def _format_local_changes(self, local_code) -> list:
        """Форматировать локальные изменения кода."""
        return [
            {
                "code": block.code,
                "start_line": block.start_line,
                "end_line": block.end_line,
            }
            for block in local_code
        ]

    def format_prompts(self, stages: list, budget_chars: int) -> list[str]:
        """
        Превратить stages в паки промптов.

        1. Каждый stage -> текстовый промпт
        2. Склеивание промптов в паки по budget_chars
        3. Добавление системного промпта к каждому паку

        Returns:
            Список строк-промптов (паков)
        """
        # Шаг 1: stage -> текст
        stage_prompts = [self._stage_to_prompt(stage) for stage in stages]

        # Шаг 2: склеивание в паки
        packs = self._pack_prompts(stage_prompts, budget_chars)

        # Шаг 3: добавляем системный промпт к каждому паку
        return [SYSTEM_PROMPT + STAGE_SEPARATOR + pack for pack in packs]

    def _pack_prompts(self, stage_prompts: list[str], budget_chars: int) -> list[str]:
        """Упаковать промпты в паки с учётом бюджета."""
        packs = []
        current_pack = ""
        system_size = len(SYSTEM_PROMPT) + SYSTEM_PROMPT_OVERHEAD

        for prompt in stage_prompts:
            if len(current_pack) + len(prompt) + system_size > budget_chars:
                # Пак заполнен, начинаем новый
                if current_pack:
                    packs.append(current_pack)
                current_pack = prompt
            else:
                # Добавляем в текущий пак
                if current_pack:
                    current_pack += STAGE_SEPARATOR
                current_pack += prompt

        # Добавляем последний пак
        if current_pack:
            packs.append(current_pack)

        return packs

    def _stage_to_prompt(self, stage: dict) -> str:
        """Превратить stage в текстовый промпт."""
        lines = [f"# File: {stage['file']} [{stage['status']}]", ""]

        lines.extend(self._format_diff_section(stage))
        lines.extend(self._format_local_code_section(stage))
        lines.extend(self._format_exports_section(stage))

        return "\n".join(lines)

    def _format_diff_section(self, stage: dict) -> list[str]:
        """Форматировать секцию с diff."""
        if not stage["diff"]:
            return []

        return ["## Changes (diff)", "```diff", stage["diff"], "```", ""]

    def _format_local_code_section(self, stage: dict) -> list[str]:
        """Форматировать секцию с локальным кодом."""
        if not stage["local_changes"]:
            return []

        lines = [
            "## Full Local Code Context",
            "",
            f"The complete code of modified entities for full context ({stage['file']}):",
            "",
        ]

        for i, change in enumerate(stage["local_changes"], 1):
            lines.append(
                f"### Code Block {i} (lines {change['start_line']}-{change['end_line']})"
            )
            lines.extend(self._format_code_block(change["code"], change["start_line"]))
            lines.append("")

        return lines

    def _format_exports_section(self, stage: dict) -> list[str]:
        """Форматировать секцию с экспортами и их использованием."""
        if not stage["changed_exports"]:
            return []

        lines = ["## Changed Exports & Their Usage"]

        for entity in stage["changed_exports"]:
            lines.append(f"### {entity['name']}")

            if entity["impact"]:
                lines.extend(self._format_impact_info(entity["impact"]))
            else:
                lines.append("- No impact data")

            lines.append("")

        return lines

    def _format_impact_info(self, impact: dict) -> list[str]:
        """Форматировать информацию об impact."""
        lines = [
            f"- **Usage count:** {impact['usage_count']} (direct: {impact['direct_usage_count']})",
            f"- **Affected files:** {len(impact['affected_files'])}",
        ]

        if impact["direct_callers"]:
            lines.append("")
            lines.append("**Direct callers:**")

            for caller in impact["direct_callers"]:
                lines.append(
                    f"- `{caller['file']}:{caller['line']}-{caller['end_line']}` - {caller['name']}"
                )
                lines.extend(self._format_code_block(caller["code"], caller["line"]))

        return lines

    def _format_code_block(self, code: str, start_line: int) -> list[str]:
        """Форматировать блок кода с номерами строк."""
        numbered_code = self._add_line_numbers(code, start_line)
        return ["```typescript", numbered_code, "```"]

    def _add_line_numbers(self, code: str, start_line: int) -> str:
        """Добавить номера строк к коду."""
        lines = code.split("\n")
        numbered = [f"{start_line + i}| {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)
