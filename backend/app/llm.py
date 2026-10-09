"""Thin wrapper around the Claude API, reserved for summaries and analysis.

Every call is logged in the llm_calls table (model, tokens, estimated cost) to track
spending. Prompts and answers are never logged. Only send public or non-personal data.
"""

import logging
from datetime import UTC, datetime

import anthropic
from sqlalchemy.orm import Session

from app.config import Settings
from app.core_models import LlmCall

logger = logging.getLogger(__name__)

# USD per million tokens (input, output). Check https://www.anthropic.com/pricing
# when changing the model: the estimate is only as good as this table.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000


class LlmClient:
    def __init__(self, settings: Settings, db: Session, client: anthropic.Anthropic | None = None):
        self.model = settings.llm_model
        self._db = db
        key = settings.anthropic_api_key
        if client is None and key is not None:
            client = anthropic.Anthropic(api_key=key.get_secret_value())
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def complete(
        self, purpose: str, system: str, prompt: str, max_tokens: int = 8000
    ) -> str | None:
        """Return Claude's text answer, or None if disabled, refused or failed."""
        if self._client is None:
            return None
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                # Summaries are simple tasks: low effort keeps thinking (and cost) small.
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as error:
            logger.warning("llm call failed (%s): %s", purpose, type(error).__name__)
            return None

        usage = response.usage
        self._db.add(
            LlmCall(
                created_at=datetime.now(UTC),
                purpose=purpose,
                model=self.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                stop_reason=response.stop_reason,
                cost_usd=estimate_cost(self.model, usage.input_tokens, usage.output_tokens),
            )
        )
        self._db.commit()

        if response.stop_reason == "refusal":
            logger.warning("llm refused (%s)", purpose)
            return None
        if response.stop_reason == "max_tokens":
            logger.warning("llm answer truncated (%s)", purpose)
        text = "".join(block.text for block in response.content if block.type == "text")
        return text.strip() or None
