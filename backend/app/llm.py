"""Thin wrapper around the Claude API, reserved for summaries and analysis.

Every call is logged in the llm_calls table (model, tokens, web searches, estimated cost)
to track spending. Prompts and answers are never logged. Only send public or non-personal
data.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
# Web search: $10 per 1,000 searches, on top of tokens (checked 2026-10-15).
WEB_SEARCH_USD = 0.01
# Basic web search version: supported by every current model, Haiku included.
WEB_SEARCH_TOOL = "web_search_20250305"
# A long search turn can be paused by the API ("pause_turn"): resume it at most this often.
MAX_RESUMES = 2


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int, web_searches: int = 0
) -> float | None:
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    tokens = (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
    return tokens + web_searches * WEB_SEARCH_USD


@dataclass(frozen=True)
class Source:
    url: str
    title: str


@dataclass(frozen=True)
class Research:
    text: str
    sources: list[Source]  # pages Claude cited, or else the pages it found


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
        response = self._create(
            purpose,
            max_tokens=max_tokens,
            system=system,
            # Summaries are simple tasks: low effort keeps thinking (and cost) small.
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if response is None or not self._usable(purpose, response):
            return None
        return _text(response.content) or None

    def research(
        self,
        purpose: str,
        system: str,
        prompt: str,
        max_searches: int = 4,
        blocked_domains: list[str] | None = None,
        max_tokens: int = 8000,
    ) -> Research | None:
        """Like complete(), but Claude may search the web (run by Anthropic, not by us).

        Search results are untrusted web content: the system prompt must say so.
        """
        tool: dict[str, Any] = {
            "type": WEB_SEARCH_TOOL,
            "name": "web_search",
            "max_uses": max_searches,
        }
        if blocked_domains:
            tool["blocked_domains"] = blocked_domains
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        content: list[Any] = []
        for _ in range(MAX_RESUMES + 1):
            response = self._create(
                purpose,
                max_tokens=max_tokens,
                system=system,
                output_config={"effort": "medium"},
                tools=[tool],
                messages=messages,
            )
            if response is None:
                return None
            content += response.content
            if response.stop_reason != "pause_turn":
                break
            # Send the paused turn back unchanged: the API resumes where it stopped.
            messages = [messages[0], {"role": "assistant", "content": response.content}]
        if not self._usable(purpose, response):
            return None
        text = _text(content)
        return Research(text=text, sources=_sources(content)) if text else None

    def _create(self, purpose: str, **kwargs: Any) -> Any:
        """One API call, logged. None if disabled or the call failed."""
        if self._client is None:
            return None
        try:
            response = self._client.messages.create(model=self.model, **kwargs)
        except anthropic.APIError as error:
            logger.warning("llm call failed (%s): %s", purpose, type(error).__name__)
            return None

        usage = response.usage
        server_tools = getattr(usage, "server_tool_use", None)
        searches = getattr(server_tools, "web_search_requests", 0) or 0
        self._db.add(
            LlmCall(
                created_at=datetime.now(UTC),
                purpose=purpose,
                model=self.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                web_searches=searches,
                stop_reason=response.stop_reason,
                cost_usd=estimate_cost(
                    self.model, usage.input_tokens, usage.output_tokens, searches
                ),
            )
        )
        self._db.commit()
        return response

    @staticmethod
    def _usable(purpose: str, response: Any) -> bool:
        if response.stop_reason == "refusal":
            logger.warning("llm refused (%s)", purpose)
            return False
        if response.stop_reason == "max_tokens":
            logger.warning("llm answer truncated (%s)", purpose)
        return True


def _text(content: list[Any]) -> str:
    return "".join(block.text for block in content if block.type == "text").strip()


def _sources(content: list[Any]) -> list[Source]:
    """Cited pages first; if Claude cited nothing, every page the searches returned."""
    cited: dict[str, Source] = {}
    found: dict[str, Source] = {}
    for block in content:
        if block.type == "text":
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                if url:
                    cited.setdefault(url, Source(url, getattr(citation, "title", None) or url))
        elif block.type == "web_search_tool_result" and isinstance(block.content, list):
            # On a search error, content is a single error object instead of a list.
            for result in block.content:
                found.setdefault(result.url, Source(result.url, result.title or result.url))
    return list((cited or found).values())
