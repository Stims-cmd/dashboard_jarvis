"""Test fixtures: an app with a temporary SQLite database and a known password."""

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_USERNAME = "tester"
TEST_PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session")
def password_hash() -> str:
    return PasswordHasher().hash(TEST_PASSWORD)


@pytest.fixture
def settings(tmp_path, password_hash) -> Settings:
    return Settings(
        secret_key="x" * 32,
        admin_username=TEST_USERNAME,
        password_hash=password_hash,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        cookie_secure=False,
        # Never call the real Claude API from tests, even if .env defines a key.
        anthropic_api_key=None,
        _env_file=None,
    )


@pytest.fixture
def client(settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
