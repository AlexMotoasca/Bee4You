"""End-to-end check of a DEPLOYED backend with a real Supabase login.

Signs in as a test user, then on the live API:
  1. GET  /v1/me                       (login token verified via Supabase JWKS)
  2. POST /v1/sync/upload              (database via the pooler, RLS)
  3. POST /v1/voice/sessions + reply   (real Groq, Romanian)
  4. soft-deletes everything it created

Run from backend/:
    uv run python scripts/smoke_live.py
It asks for the publishable (anon) key and the test user's password. Nothing is saved.
"""

import getpass
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

API = os.environ.get("API_URL", "https://bee4you-backend.vercel.app")
SUPABASE = os.environ.get("SUPABASE_URL", "https://atrvkrxfcdtkoeyczjct.supabase.co")


def step(title: str) -> None:
    print(f"\n== {title}")


def fail(message: str, response: httpx.Response | None = None) -> None:
    print(f"FAILED: {message}")
    if response is not None:
        print(f"  HTTP {response.status_code}: {response.text[:500]}")
    sys.exit(1)


def now() -> str:
    return datetime.now(UTC).isoformat()


def sign_in(client: httpx.Client, anon_key: str, email: str, password: str) -> str:
    r = client.post(
        f"{SUPABASE}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": anon_key},
        json={"email": email, "password": password},
    )
    if r.status_code != 200:
        fail("Supabase sign-in", r)
    token: str = r.json()["access_token"]
    return token


def upload(
    client: httpx.Client, auth: dict[str, str], ops: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    r = client.post(f"{API}/v1/sync/upload", headers=auth, json={"ops": ops})
    if r.status_code != 200:
        fail("sync upload", r)
    results: list[dict[str, Any]] = r.json()["results"]
    return results


def main() -> None:
    anon_key = (
        os.environ.get("SUPABASE_ANON_KEY")
        or getpass.getpass(
            "Supabase publishable/anon key (Project Settings > API keys; input hidden): "
        ).strip()
    )
    email = input("Test user email: ").strip()
    password = getpass.getpass("Test user password (input hidden): ")

    created: list[tuple[str, str]] = []  # (table, id) to clean up, children first
    with httpx.Client(timeout=60) as client:
        step("Sign in with Supabase")
        token = sign_in(client, anon_key, email, password)
        auth = {"Authorization": f"Bearer {token}"}
        print("ok, got an access token")

        step("GET /v1/me")
        r = client.get(f"{API}/v1/me", headers=auth)
        if r.status_code != 200:
            fail("/v1/me", r)
        print("ok, user id", r.json()["id"])

        try:
            step("POST /v1/sync/upload (test apiary, hive, placement, item)")
            ids = {k: str(uuid.uuid4()) for k in ("apiary", "colony", "placement", "item")}
            stamp = now()
            results = upload(
                client,
                auth,
                [
                    {
                        "op": "PUT",
                        "table": "apiaries",
                        "id": ids["apiary"],
                        "data": {
                            "name": "Smoke test stupină",
                            "lat": 46.77,
                            "lng": 23.59,
                            "client_updated_at": stamp,
                        },
                    },
                    {
                        "op": "PUT",
                        "table": "colonies",
                        "id": ids["colony"],
                        "data": {
                            "label": "Smoke stup 901",
                            "number": 901,
                            "client_updated_at": stamp,
                        },
                    },
                    {
                        "op": "PUT",
                        "table": "colony_placements",
                        "id": ids["placement"],
                        "data": {
                            "colony_id": ids["colony"],
                            "apiary_id": ids["apiary"],
                            "started_at": stamp,
                            "client_updated_at": stamp,
                        },
                    },
                    {
                        "op": "PUT",
                        "table": "inventory_items",
                        "id": ids["item"],
                        "data": {
                            "name": "Smoke acid oxalic",
                            "category": "treatment",
                            "unit": "ml",
                            "client_updated_at": stamp,
                        },
                    },
                ],
            )
            created += [
                ("colony_placements", ids["placement"]),
                ("colonies", ids["colony"]),
                ("inventory_items", ids["item"]),
                ("apiaries", ids["apiary"]),
            ]
            for res in results:
                print(f"  {res['table']}: {res['status']} {res.get('error') or ''}")
            if any(res["status"] != "applied" for res in results):
                fail("not every row was applied")

            step("POST /v1/voice/sessions (Romanian, real Groq)")
            transcript = "Stupul 901, smoke acid oxalic, cinci mililitri"
            print(f'  said: "{transcript}"')
            r = client.post(
                f"{API}/v1/voice/sessions",
                headers=auth,
                json={"transcript": transcript, "locale": "ro-RO", "client_time": now()},
            )
            if r.status_code != 200:
                fail("voice session", r)
            turn = r.json()
            print(f"  assistant ({turn['status']}): {turn['speak']}")
            if turn["status"] != "confirm":
                fail("expected the assistant to read the entry back for confirmation")

            r = client.post(
                f"{API}/v1/voice/sessions/{turn['thread_id']}/reply",
                headers=auth,
                json={"text": "da"},
            )
            if r.status_code != 200:
                fail("voice reply", r)
            turn = r.json()
            print(f"  you: da\n  assistant ({turn['status']}): {turn['speak']}")
            if turn["status"] != "saved" or not turn.get("record"):
                fail("expected the treatment to be saved")
            created.insert(0, (turn["record"]["table"], turn["record"]["id"]))
            print(f"  saved {turn['record']['table']} {turn['record']['id']}")
        finally:
            if created:
                step("Clean up (soft delete)")
                results = upload(
                    client, auth, [{"op": "DELETE", "table": t, "id": i} for t, i in created]
                )
                print("  " + ", ".join(f"{res['table']}: {res['status']}" for res in results))

    print("\nALL GOOD: login, database and Groq all work on the deployed backend.")


if __name__ == "__main__":
    main()
