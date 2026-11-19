import time

import httpx


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_me_returns_user(client: httpx.AsyncClient, make_token, user_id) -> None:
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(user_id)
    assert body["role"] == "authenticated"


async def test_me_without_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_expired_token(client: httpx.AsyncClient, make_token) -> None:
    token = make_token(exp=int(time.time()) - 10)
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_wrong_audience(client: httpx.AsyncClient, make_token) -> None:
    token = make_token(aud="something-else")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_wrong_issuer(client: httpx.AsyncClient, make_token) -> None:
    token = make_token(iss="https://evil.example.com/auth/v1")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_anon_role_rejected(client: httpx.AsyncClient, make_token) -> None:
    token = make_token(role="anon")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_tampered_signature(client: httpx.AsyncClient, make_token) -> None:
    token = make_token()[:-4] + "AAAA"
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
