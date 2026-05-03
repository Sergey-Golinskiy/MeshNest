async def test_login_invalid_credentials(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "nope@test.local", "password": "x" * 12},
    )
    assert r.status_code == 401


async def test_login_success(client, admin_user):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-password-123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == admin_user.email
    assert body["user"]["role"] == "admin"


async def test_me_requires_token(client):
    r = await client.get("/api/v1/me")
    assert r.status_code == 401


async def test_me_with_token(client, admin_token):
    r = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "admin@test.local"


async def test_invite_create_redeem_flow(client, admin_token):
    # 1. admin создаёт invite
    r = await client.post(
        "/api/v1/admin/invites",
        json={"role": "viewer", "expires_in_days": 7},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    invite = r.json()
    token = invite["token"]
    assert invite["role"] == "viewer"

    # 2. info — valid
    r = await client.get(f"/api/v1/auth/invite/{token}/info")
    assert r.status_code == 200
    assert r.json()["valid"] is True

    # 3. redeem
    r = await client.post(
        f"/api/v1/auth/invite/{token}/redeem",
        json={
            "email": "newuser@test.local",
            "password": "supersecret-password-12",
            "display_name": "Newbie",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "viewer"
    assert body["access_token"]

    # 4. второй раз тот же token — fail
    r = await client.post(
        f"/api/v1/auth/invite/{token}/redeem",
        json={
            "email": "another@test.local",
            "password": "another-password-12",
            "display_name": "x",
        },
    )
    assert r.status_code == 400


async def test_refresh_token(client, admin_user):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-password-123"},
    )
    refresh = r.json()["refresh_token"]
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_unauthorized_models_list(client):
    r = await client.get("/api/v1/models")
    assert r.status_code == 401
