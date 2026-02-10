"""Трекер бюджета для использования LLM."""


class BudgetTracker:
    """Отслеживание использования токенов и расчёт стоимости."""

    def __init__(self, input_price_per_million: float, output_price_per_million: float):
        """
        Инициализировать трекер бюджета.

        Args:
            input_price_per_million: Цена за 1М входных токенов (USD)
            output_price_per_million: Цена за 1М выходных токенов (USD)
        """
        self.input_tokens = 0
        self.output_tokens = 0
        self.input_price = input_price_per_million
        self.output_price = output_price_per_million

    def add_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """
        Добавить использование токенов из одного вызова LLM.

        Args:
            prompt_tokens: Количество токенов в промпте
            completion_tokens: Количество токенов в ответе
        """
        self.input_tokens += prompt_tokens
        self.output_tokens += completion_tokens

    def get_cost(self) -> float:
        """
        Рассчитать общую стоимость в USD.

        Returns:
            Общая стоимость в USD
        """
        return (
            self.input_tokens * self.input_price
            + self.output_tokens * self.output_price
        ) / 1_000_000

    def get_summary(self) -> dict:
        """
        Получить сводку использования и затрат.

        Returns:
            Словарь с total_tokens, input_tokens, output_tokens, estimated_cost_usd
        """
        return {
            "total_tokens": self.input_tokens + self.output_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": round(self.get_cost(), 4),
        }
