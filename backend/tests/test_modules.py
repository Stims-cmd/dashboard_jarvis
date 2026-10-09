from tests.test_auth import login

EXPECTED = [
    {"id": "veille_cyber", "title": "Veille cyber"},
    {"id": "finances", "title": "Finances"},
    {"id": "osint", "title": "OSINT"},
    {"id": "leboncoin", "title": "Leboncoin"},
]


def test_modules_require_session(client):
    assert client.get("/api/modules").status_code == 401
    assert client.get("/api/modules/finances/status").status_code == 401


def test_modules_listed_in_order(client):
    login(client)
    assert client.get("/api/modules").json() == EXPECTED


def test_module_routes_mounted(client):
    login(client)
    for module in EXPECTED:
        response = client.get(f"/api/modules/{module['id']}/status")
        assert response.status_code == 200
