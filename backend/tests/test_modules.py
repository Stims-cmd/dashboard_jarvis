from tests.test_auth import login

EXPECTED = [
    {"id": "veille_cyber", "title": "Veille cyber"},
    {"id": "finances", "title": "Finances"},
    {"id": "osint", "title": "OSINT"},
    {"id": "leboncoin", "title": "Leboncoin"},
]


def test_modules_require_session(client):
    assert client.get("/api/modules").status_code == 401
    assert client.get("/api/modules/osint/status").status_code == 401


def test_modules_listed_in_order(client):
    login(client)
    assert client.get("/api/modules").json() == EXPECTED


def test_module_routes_mounted(client):
    login(client)
    # One read-only route per module: 200 proves the router is mounted under its prefix.
    for path in (
        "/api/modules/veille_cyber/status",
        "/api/modules/finances/overview",
        "/api/modules/osint/status",
        "/api/modules/leboncoin/status",
    ):
        assert client.get(path).status_code == 200, path
