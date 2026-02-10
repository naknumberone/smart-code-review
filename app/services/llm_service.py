"""Сервис LLM для ревью кода."""

import logging
from openai import AsyncOpenAI

from app.services.budget_tracker import BudgetTracker

logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для взаимодействия с LLM."""

    def __init__(self, client: AsyncOpenAI, model: str, budget_tracker: BudgetTracker):
        self.client = client
        self.model = model
        self.budget_tracker = budget_tracker

    async def send(self, prompt: str) -> tuple[str, dict]:
        """
        Отправить промпт в LLM и вернуть ответ со статистикой использования.

        Returns:
            Кортеж (response_text, usage_dict), где usage_dict содержит:
            - prompt_tokens: количество входных токенов
            - completion_tokens: количество выходных токенов
            - total_tokens: всего использовано токенов
        """
        logger.info("Sending prompt to LLM...")

        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.7,
        )

        response = completion.choices[0].message.content or ""

        usage = {
            "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
            "completion_tokens": completion.usage.completion_tokens
            if completion.usage
            else 0,
            "total_tokens": completion.usage.total_tokens if completion.usage else 0,
        }

        self.budget_tracker.add_usage(
            usage["prompt_tokens"], usage["completion_tokens"]
        )

        logger.info("Received response from LLM\n")

        return response, usage
