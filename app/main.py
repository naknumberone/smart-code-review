"""Новый пайплайн ревью с диффом веток."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

from openai import AsyncOpenAI

from app.config import Config
from app.services.git_service import GitService, BranchDiffResult
from app.services.entity_service import EntityService
from app.services.impact import ImpactService
from app.services.review_service import ReviewService
from app.services.llm_service import LLMService
from app.services.budget_tracker import BudgetTracker
from app.services.prompts import SUMMARY_PROMPT

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class Pipeline:
    """Новый пайплайн для ревью ветки."""

    def __init__(self, config: Config):
        self.config = config
        self.git_service = GitService(repo_path=config.repo_path)
        self.entity_service = EntityService(repo_path=config.repo_path)
        self.impact_service = ImpactService(repo_path=config.repo_path)
        self.review_service = ReviewService()

        # Трекер бюджета
        self.budget_tracker = BudgetTracker(
            input_price_per_million=config.llm_price_per_million_input_tokens,
            output_price_per_million=config.llm_price_per_million_output_tokens,
        )

        # LLM service
        client = AsyncOpenAI(api_key=config.llm_api_key, base_url=config.llm_api_url)
        self.llm_service = LLMService(
            client=client, model=config.llm_model, budget_tracker=self.budget_tracker
        )

        # Папка для артефактов текущего ревью
        branch_name = self.git_service.repo.active_branch.name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.artifacts_dir = Path("__artifacts__") / f"{timestamp}.{branch_name}"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        """Запустить новый пайплайн."""
        logger.info("╔═══════════════════════════════════════════════════════════╗")
        logger.info("║          CODE REVIEW PIPELINE                             ║")
        logger.info("╚═══════════════════════════════════════════════════════════╝")

        # Шаг 1: Получаем diff ветки относительно main
        diff_result = await self.get_branch_diff()
        logger.info(
            f"Branch: {diff_result.branch_name} (from merge-base with {self.config.base_branch})"
        )
        logger.info(
            f"Commits: {diff_result.base_commit[:8]}..{diff_result.head_commit[:8]}\n"
        )
        self._log_diff_result(diff_result)

        # Шаг 2: Извлекаем сущности из изменённых файлов
        entities_result = await self.extract_entities(diff_result.files)
        self._log_entities_result(entities_result)

        # Шаг 3: Анализируем импакт изменённых сущностей
        impact_result = await self.analyze_impact(entities_result)
        self._log_impact_result(impact_result)

        # Шаг 4: Форматируем в stages
        stages = self.review_service.format_stages(
            diff_result, entities_result, impact_result
        )
        if self.config.max_stages > 0 and len(stages) > self.config.max_stages:
            logger.info(
                f"[4/7] Formatting stages: {len(stages)} stages created, limited to {self.config.max_stages}"
            )
            stages = stages[: self.config.max_stages]
        else:
            logger.info(f"[4/7] Formatting stages: {len(stages)} stages created")

        # Шаг 5: Создаём промпты
        prompts = self.review_service.format_prompts(
            stages, self.config.prompt_budget_chars
        )
        total_chars = sum(len(p) for p in prompts)
        logger.info(
            f"[5/7] Prompts created: {len(prompts)} packs, {total_chars:,} chars total"
        )

        # Сохраняем промпты
        for i, prompt in enumerate(prompts, 1):
            self._save_file(f"{i}.prompt.md", prompt)

        # Шаг 6: Отправляем на ревью
        reviews = await self.review_prompts(prompts)

        # Шаг 7: Генерируем финальное саммари
        final_review = await self.generate_final_summary(reviews)

        # Сохраняем результат
        self._save_file(
            "review.final.json", json.dumps(final_review, ensure_ascii=False, indent=2)
        )
        logger.info(
            f"[7/7] Final review: {len(final_review.get('comments', []))} comments\n"
        )

        # Выводим статистику бюджета
        self._log_budget_summary()

        logger.info("\n✓ Pipeline completed")

    def _log_diff_result(self, diff_result: BranchDiffResult) -> None:
        """Логировать результаты diff."""
        logger.info(f"[1/7] Branch diff: {len(diff_result.files)} files changed")

    def _log_entities_result(self, entities_result: list) -> None:
        """Логировать результаты извлечения сущностей."""
        total_exports = sum(len(e.top_level) for e in entities_result)
        total_blocks = sum(len(e.local_code) for e in entities_result)
        logger.info(
            f"[2/7] Entities extracted: {total_exports} exports, {total_blocks} code blocks"
        )

    def _log_impact_result(self, impact_result: dict) -> None:
        """Логировать результаты анализа impact."""
        total_entities = sum(len(impacts) for impacts in impact_result.values())
        total_callers = sum(
            len(impact.all_callers)
            for impacts in impact_result.values()
            for impact in impacts
        )
        affected_files = set()
        for impacts in impact_result.values():
            for impact in impacts:
                affected_files.update(impact.affected_files)

        logger.info(
            f"[3/7] Impact analyzed: {total_entities} entities, {total_callers} callers, {len(affected_files)} affected files"
        )

    def _log_budget_summary(self) -> None:
        """Вывести статистику бюджета."""
        summary = self.budget_tracker.get_summary()
        logger.info("───────────────────────────────────────────────────────────")
        logger.info(
            f"Budget: {summary['total_tokens']:,} tokens | ${summary['estimated_cost_usd']:.4f} USD"
        )
        logger.info(
            f"  ↳ Input: {summary['input_tokens']:,} | Output: {summary['output_tokens']:,}"
        )
        logger.info("───────────────────────────────────────────────────────────")

    def _save_file(self, filename: str, content: str) -> None:
        """Сохранить содержимое в файл в папке текущего ревью."""
        file_path = self.artifacts_dir / filename
        file_path.write_text(content, encoding="utf-8")

    async def get_branch_diff(self) -> BranchDiffResult:
        """
        Шаг 1: Получить diff ветки.

        Returns:
            BranchDiffResult со списком файлов и их диффов
        """
        result = self.git_service.get_branch_diff(
            branch=self.config.target_branch, base_branch=self.config.base_branch
        )
        return result

    async def extract_entities(self, files: list) -> list:
        """
        Шаг 2: Извлечь сущности из файлов.

        Args:
            files: список FileDiff из git service

        Returns:
            список FileEntities для каждого файла
        """
        result = self.entity_service.extract_entities(files)
        return result

    async def analyze_impact(self, entities_result: list) -> dict:
        """
        Шаг 3: Анализировать импакт изменённых сущностей.

        Args:
            entities_result: список FileEntities с path и top_level

        Returns:
            словарь {file_path: [EntityImpact, ...]}, где каждый EntityImpact содержит:
            - entity_name: имя сущности
            - file: путь к файлу
            - direct_callers: список CallerInfo с прямыми вызывающими
            - all_callers: список CallerInfo со всеми вызывающими (транзитивно до depth=5)
            - affected_files: список путей затронутых файлов

            CallerInfo содержит: file, line, name, code
        """
        result = self.impact_service.analyze_impact(entities_result)
        return result

    async def review_prompts(self, prompts: list[str]) -> list[str]:
        """
        Шаг 6: Отправить промпты на ревью параллельно.

        Args:
            prompts: список промптов

        Returns:
            список ответов от LLM
        """

        async def process_prompt(i: int, prompt: str) -> tuple[int, str]:
            review, usage = await self.llm_service.send(prompt)

            # Сохраняем каждый ревью
            self._save_file(f"{i}.review.md", review)
            logger.info(
                f"[6/7] Pack {i}/{len(prompts)}: ✓ {usage['total_tokens']:,} tokens"
            )

            return i, review

        # Запускаем все промпты параллельно
        tasks = [process_prompt(i, prompt) for i, prompt in enumerate(prompts, 1)]
        results = await asyncio.gather(*tasks)

        # Сортируем по индексу, чтобы вернуть в правильном порядке
        return [review for _, review in sorted(results)]

    async def generate_final_summary(self, reviews: list[str]) -> dict:
        """
        Шаг 7: Сгенерировать финальное саммари батчами.

        Args:
            reviews: список ревью от LLM

        Returns:
            финальное ревью в формате JSON
        """
        batch_size = self.config.finalize_batch_size

        async def finalize_batch(batch_num: int, batch: list[str]) -> tuple[int, str]:
            # Объединяем ревью из батча
            joined = "\n\n---\n\n".join(
                f"# Review Pack {start_idx + i + 1}\n\n{review}"
                for i, review in enumerate(batch)
            )

            summary_prompt = SUMMARY_PROMPT.format(reviews=joined)
            summary, usage = await self.llm_service.send(summary_prompt)

            # Сохраняем каждое батч-саммари
            self._save_file(f"{batch_num}.finalized.json", summary)
            logger.info(
                f"[7/7] Finalize batch {batch_num}/{total_batches}: ✓ {usage['total_tokens']:,} tokens"
            )

            return batch_num, summary

        # Разбиваем на батчи
        batches = [
            reviews[i : i + batch_size] for i in range(0, len(reviews), batch_size)
        ]
        total_batches = len(batches)

        # Параллельная финализация батчей
        tasks = []
        for batch_num, batch in enumerate(batches, 1):
            start_idx = (batch_num - 1) * batch_size
            tasks.append(finalize_batch(batch_num, batch))

        results = await asyncio.gather(*tasks)
        finalized_reviews = [summary for _, summary in sorted(results)]

        # Парсим JSON из всех батчей и объединяем комментарии
        all_comments = []
        for summary in finalized_reviews:
            try:
                data = self._parse_json_response(summary)
                all_comments.extend(data.get("comments", []))
            except Exception as e:
                logger.warning(f"Could not parse JSON from batch: {e}")

        return {"summary": "Final review", "comments": all_comments}

    def _parse_json_response(self, response: str) -> dict:
        """Распарсить JSON ответ от LLM, убирая markdown блоки если есть."""
        clean_response = response.strip()

        # Убираем markdown code blocks если есть
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")
            clean_response = "\n".join(lines[1:-1])

        return json.loads(clean_response)


if __name__ == "__main__":
    config = Config.model_validate(
        {}
    )  # https://github.com/pydantic/pydantic/issues/3753
    pipeline = Pipeline(config)
    asyncio.run(pipeline.run())
