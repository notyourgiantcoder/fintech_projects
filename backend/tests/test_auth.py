"""Clerk JWT verification, with a locally generated RSA key standing in for Clerk's JWKS."""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from finbo import auth
from finbo.api import app
from finbo.api.deps import set_store
from finbo.store import Store

HOST = "example-app.clerk.accounts.dev"
PUBLISHABLE_KEY = "pk_test_" + base64.b64encode(f"{HOST}$".encode()).decode().rstrip("=")
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token):
        return type("Key", (), {"key": PRIVATE_KEY.public_key()})()


def token(**overrides) -> str:
    now = int(time.time())
    claims = {"sub": "user_123", "iat": now, "exp": now + 60, "azp": "http://localhost:5173"}
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLERK_PUBLISHABLE_KEY", PUBLISHABLE_KEY)
    monkeypatch.delenv("FINBO_DEV_AUTH", raising=False)
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJwksClient())
    store = Store("sqlite://")
    set_store(store)
    yield TestClient(app)
    set_store(None)


def test_jwks_url_from_publishable_key():
    assert auth.jwks_url_from_publishable_key(PUBLISHABLE_KEY) == (
        f"https://{HOST}/.well-known/jwks.json"
    )
    with pytest.raises(ValueError):
        auth.jwks_url_from_publishable_key("not-a-key")


def test_valid_token_reaches_users_workspace(client):
    headers = {"Authorization": f"Bearer {token()}"}
    assert client.post("/api/me/setup", json={"market": "in"}, headers=headers).status_code == 200
    assert client.get("/api/me", headers=headers).json()["currency"] == "INR"


def test_missing_token(client):
    res = client.get("/api/me")
    assert res.status_code == 401 and "Sign in" in res.json()["detail"]


@pytest.mark.parametrize(
    "bad",
    [
        {"exp": int(time.time()) - 120},  # expired
        {"azp": "https://evil.example"},  # issued for another site
    ],
)
def test_rejected_tokens(client, bad):
    res = client.get("/api/me", headers={"Authorization": f"Bearer {token(**bad)}"})
    assert res.status_code == 401


def test_tampered_signature(client):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {"sub": "attacker", "iat": int(time.time()), "exp": int(time.time()) + 60},
        other,
        algorithm="RS256",
    )
    assert client.get("/api/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unconfigured_auth_is_explained(client, monkeypatch):
    monkeypatch.delenv("CLERK_PUBLISHABLE_KEY")
    res = client.get("/api/me")
    assert res.status_code == 503 and "CLERK_PUBLISHABLE_KEY" in res.json()["detail"]
