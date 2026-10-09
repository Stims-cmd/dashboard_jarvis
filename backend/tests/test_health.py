def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_api_keys_are_ignored(settings):
    data = settings.model_dump() | {"ANTHROPIC_API_KEY": "", "nvd_api_key": "  "}
    data.pop("anthropic_api_key")
    reloaded = type(settings)(**data, _env_file=None)
    assert reloaded.anthropic_api_key is None
    assert reloaded.nvd_api_key is None
