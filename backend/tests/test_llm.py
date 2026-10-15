from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core_models import LlmCall
from app.db import make_engine, make_session_factory, run_migrations
from app.llm import LlmClient, estimate_cost


class FakeMessages:
    def __init__(self, stop_reason="end_turn", text="Résumé du jour"):
        self.stop_reason = stop_reason
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=self.text),
            ],
        )


@pytest.fixture
def db(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'llm.db'}")
    run_migrations(engine)
    with make_session_factory(engine)() as session:
        yield session


def test_disabled_without_key(settings, db):
    llm = LlmClient(settings, db)
    assert not llm.enabled
    assert llm.complete("test", "system", "prompt") is None


def test_call_is_logged_without_content(settings, db):
    messages = FakeMessages()
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=messages))
    assert llm.complete("digest", "system", "prompt") == "Résumé du jour"

    call = db.scalars(select(LlmCall)).one()
    assert (call.purpose, call.model) == ("digest", "claude-haiku-5-5")
    assert (call.input_tokens, call.output_tokens) == (1000, 200)
    assert call.cost_usd == pytest.approx(0.0002)
    assert messages.calls[0]["output_config"] == {"effort": "low"}


def test_refusal_returns_none_but_is_logged(settings, db):
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=FakeMessages("refusal")))
    assert llm.complete("digest", "system", "prompt") is None
    assert db.scalars(select(LlmCall)).one().stop_reason == "refusal"


def test_unknown_model_has_no_cost():
    assert estimate_cost("some-future-model", 10, 10) is None


# --- Web search -------------------------------------------------------------


def text_block(text, urls=()):
    citations = [SimpleNamespace(type="web_search_result_location", url=u, title=u) for u in urls]
    return SimpleNamespace(type="text", text=text, citations=citations or None)


def search_block(*urls):
    results = [SimpleNamespace(type="web_search_result", url=u, title=f"Page {u}") for u in urls]
    return SimpleNamespace(type="web_search_tool_result", content=results)


class ScriptedMessages:
    """Returns the given (stop_reason, content, searches) responses in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        stop_reason, content, searches = self.responses.pop(0)
        return SimpleNamespace(
            stop_reason=stop_reason,
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=200,
                server_tool_use=SimpleNamespace(web_search_requests=searches),
            ),
            content=content,
        )


def test_research_logs_searches_and_returns_cited_sources(settings, db):
    messages = ScriptedMessages(
        (
            "end_turn",
            [
                search_block("https://a.example", "https://b.example"),
                text_block("Modèle fiable", ["https://b.example"]),
                text_block(" en général."),
            ],
            2,
        )
    )
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=messages))
    result = llm.research("lbc.analysis", "system", "prompt", blocked_domains=["leboncoin.fr"])

    assert result.text == "Modèle fiable en général."
    assert [s.url for s in result.sources] == ["https://b.example"]
    tool = messages.calls[0]["tools"][0]
    assert (tool["name"], tool["max_uses"], tool["blocked_domains"]) == (
        "web_search",
        4,
        ["leboncoin.fr"],
    )
    call = db.scalars(select(LlmCall)).one()
    assert call.web_searches == 2
    assert call.cost_usd == pytest.approx(0.0002 + 0.02)


def test_research_without_citations_lists_found_pages(settings, db):
    messages = ScriptedMessages(
        ("end_turn", [search_block("https://a.example"), text_block("ok")], 1)
    )
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=messages))
    assert [s.url for s in llm.research("t", "s", "p").sources] == ["https://a.example"]


def test_research_resumes_a_paused_turn(settings, db):
    paused = [text_block("Je cherche. ")]
    messages = ScriptedMessages(("pause_turn", paused, 1), ("end_turn", [text_block("Fini")], 1))
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=messages))

    assert llm.research("t", "s", "p").text == "Je cherche. Fini"
    assert messages.calls[1]["messages"][1] == {"role": "assistant", "content": paused}
    assert len(db.scalars(select(LlmCall)).all()) == 2


def test_research_ignores_search_errors(settings, db):
    error = SimpleNamespace(
        type="web_search_tool_result", content=SimpleNamespace(error_code="unavailable")
    )
    messages = ScriptedMessages(("end_turn", [error, text_block("Sans source")], 0))
    llm = LlmClient(settings, db, client=SimpleNamespace(messages=messages))
    result = llm.research("t", "s", "p")
    assert (result.text, result.sources) == ("Sans source", [])


def test_research_refusal_returns_none(settings, db):
    messages = ScriptedMessages(("refusal", [], 0))
    assert (
        LlmClient(settings, db, client=SimpleNamespace(messages=messages)).research("t", "s", "p")
        is None
    )
