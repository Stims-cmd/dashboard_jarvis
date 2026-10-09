from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def login(client, username=TEST_USERNAME, password=TEST_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_success_sets_secure_cookie(client):
    response = login(client)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "jarvis_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert client.get("/api/auth/me").json() == {"username": TEST_USERNAME}


def test_wrong_password_rejected(client):
    response = login(client, password="wrong password")
    assert response.status_code == 401
    assert "jarvis_session" not in client.cookies


def test_wrong_username_rejected(client):
    assert login(client, username="someone").status_code == 401


def test_forged_cookie_rejected(client):
    client.cookies.set("jarvis_session", "forged-token")
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(client):
    login(client)
    token = client.cookies["jarvis_session"]
    assert client.post("/api/auth/logout").status_code == 204
    # Replaying the old token must fail: the session was deleted server-side.
    client.cookies.set("jarvis_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_rate_limit_after_five_failures(client):
    for _ in range(5):
        assert login(client, password="wrong password").status_code == 401
    # Even the right password is refused while blocked.
    assert login(client).status_code == 429


def test_session_cookie_is_secure_when_configured(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    secure_settings = settings.model_copy(update={"cookie_secure": True})
    with TestClient(create_app(secure_settings)) as client:
        response = login(client)
    assert "secure" in response.headers["set-cookie"].lower()
