import pyotp
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import totp
from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
NOW = 1_800_000_000.0  # fixed clock, on a step boundary


def make_settings(base: Settings, secret: str) -> Settings:
    """Full validation, as when the secret comes from .env."""
    return Settings(**(base.model_dump() | {"totp_secret": secret}), _env_file=None)


def code_at(offset_steps: int = 0) -> str:
    return pyotp.TOTP(SECRET).at(NOW + offset_steps * totp.STEP_SECONDS)


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr(totp.time, "time", lambda: NOW)


@pytest.fixture
def totp_client(settings, frozen_time):
    with TestClient(create_app(make_settings(settings, SECRET))) as client:
        yield client


def login(client, code="", password=TEST_PASSWORD):
    return client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": password, "code": code},
    )


# --- verify_code -------------------------------------------------------------


def test_current_and_adjacent_steps_accepted():
    step = int(NOW // totp.STEP_SECONDS)
    for offset in (-1, 0, 1):
        assert totp.verify_code(SECRET, code_at(offset), None, now=NOW) == step + offset


def test_codes_two_steps_away_refused():
    assert totp.verify_code(SECRET, code_at(-2), None, now=NOW) is None
    assert totp.verify_code(SECRET, code_at(2), None, now=NOW) is None


def test_used_step_refused():
    step = totp.verify_code(SECRET, code_at(), None, now=NOW)
    assert totp.verify_code(SECRET, code_at(), step, now=NOW) is None
    # An older code is refused too once a newer one was used.
    assert totp.verify_code(SECRET, code_at(-1), step, now=NOW) is None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", " 123456"])
def test_malformed_codes_refused(code):
    assert totp.verify_code(SECRET, code, None, now=NOW) is None


# --- settings ----------------------------------------------------------------


def test_empty_secret_means_disabled(settings):
    assert make_settings(settings, "  ").totp_secret is None


@pytest.mark.parametrize("secret", ["not base32!", "JBSWY3DP"])  # invalid, too short
def test_bad_secret_rejected(settings, secret):
    with pytest.raises(ValidationError):
        make_settings(settings, secret)


# --- login route -------------------------------------------------------------


def test_config_reports_totp(client, totp_client):
    assert client.get("/api/auth/config").json() == {"totp": False}
    assert totp_client.get("/api/auth/config").json() == {"totp": True}


def test_login_without_totp_needs_no_code(client):
    assert login(client).status_code == 204


def test_login_with_valid_code(totp_client):
    assert login(totp_client, code=code_at()).status_code == 204
    assert totp_client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("code", ["", "000000", "abc"])
def test_login_refuses_missing_or_wrong_code(totp_client, code):
    if code == code_at():  # pragma: no cover - 1 in a million
        pytest.skip("fixed code collides with the real one")
    response = login(totp_client, code=code)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_good_code_with_wrong_password_refused(totp_client):
    assert login(totp_client, code=code_at(), password="wrong password").status_code == 401


def test_code_cannot_be_replayed(totp_client):
    code = code_at()
    assert login(totp_client, code=code).status_code == 204
    totp_client.cookies.clear()
    assert login(totp_client, code=code).status_code == 401


def test_wrong_codes_trigger_rate_limit(totp_client):
    for _ in range(5):
        assert login(totp_client, code="000000").status_code == 401
    assert login(totp_client, code=code_at()).status_code == 429
