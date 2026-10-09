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
