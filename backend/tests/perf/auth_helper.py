"""Shared auth helper for Locust performance tests."""

import uuid


def register_and_login(client):
    """Register a unique family and return the access token."""
    username = f"perf-{uuid.uuid4().hex[:12]}"
    password = "perftest123"

    resp = client.post("/api/auth/register", json={
        "username": username,
        "password": password,
        "display_name": f"Perf {username}",
    })

    if resp.status_code == 201:
        data = resp.json()
        return data["access_token"], data["family_id"]

    # If registration fails (e.g., duplicate), try login
    resp = client.post("/api/auth/login", json={
        "username": username,
        "password": password,
    })
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["family_id"]


def auth_headers(token: str) -> dict:
    """Return Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}
