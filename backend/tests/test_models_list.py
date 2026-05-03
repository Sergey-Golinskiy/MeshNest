"""Smoke tests для library endpoints на пустой DB."""


async def test_empty_models_list(client, admin_token):
    r = await client.get(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_categories_empty(client, admin_token):
    r = await client.get(
        "/api/v1/categories",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_tags_empty(client, admin_token):
    r = await client.get(
        "/api/v1/tags",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_get_unknown_model_404(client, admin_token):
    r = await client.get(
        "/api/v1/models/does-not-exist",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
