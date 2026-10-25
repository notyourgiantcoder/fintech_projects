"""Clerk session-token verification.

The browser sends Clerk's short-lived session JWT as `Authorization: Bearer <token>`.
We verify its RS256 signature against the instance's public JWKS (derived from the
publishable key), so no Clerk secret is needed on the server.

Dev mode (`FINBO_DEV_AUTH=1`) accepts requests without a token as one local user.
It is off unless set explicitly and must never be enabled on a deployed server.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import jwt
from fastapi import HTTPException, Request

DEV_USER_ID = "dev-user"
DEFAULT_AUTHORIZED_PARTIES = "http://localhost:5173,http://127.0.0.1:5173"

AuthMode = Literal["clerk", "dev", "unconfigured"]


@dataclass(frozen=True)
class User:
    id: str


def jwks_url_from_publishable_key(publishable_key: str) -> str:
    """pk_test_<base64("<frontend-api-host>$")> -> https://<host>/.well-known/jwks.json"""
    try:
        encoded = publishable_key.split("_", 2)[2]
        host = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode().rstrip("$")
    except (IndexError, ValueError, UnicodeDecodeError):
        raise ValueError("CLERK_PUBLISHABLE_KEY is not a valid Clerk publishable key") from None
    if not host or "/" in host:
        raise ValueError("CLERK_PUBLISHABLE_KEY is not a valid Clerk publishable key")
    return f"https://{host}/.well-known/jwks.json"


def auth_mode() -> AuthMode:
    if os.getenv("CLERK_PUBLISHABLE_KEY"):
        return "clerk"
    if os.getenv("FINBO_DEV_AUTH") == "1":
        return "dev"
    return "unconfigured"


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def _authorized_parties() -> set[str]:
    raw = os.getenv("CLERK_AUTHORIZED_PARTIES", DEFAULT_AUTHORIZED_PARTIES)
    return {p.strip().rstrip("/") for p in raw.split(",") if p.strip()}


def verify_token(token: str, publishable_key: str) -> User:
    try:
        signing_key = _jwks_client(jwks_url_from_publishable_key(publishable_key))
        key = signing_key.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"require": ["exp", "iat", "sub"]},
            leeway=5,
        )
    except (jwt.PyJWTError, ValueError) as e:
        raise HTTPException(401, f"Your session is invalid or expired ({type(e).__name__}).") from e
    azp = claims.get("azp")
    if azp and azp.rstrip("/") not in _authorized_parties():
        raise HTTPException(401, "This token was issued for a different site.")
    return User(id=claims["sub"])


def current_user(request: Request) -> User:
    """FastAPI dependency: the signed-in user, or 401."""
    mode = auth_mode()
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""

    if mode == "clerk":
        if not token:
            raise HTTPException(401, "Sign in to use Finbo.")
        return verify_token(token, os.environ["CLERK_PUBLISHABLE_KEY"])
    if mode == "dev":
        return User(id=DEV_USER_ID)
    raise HTTPException(
        503,
        "Sign-in is not configured. Set CLERK_PUBLISHABLE_KEY in .env (or "
        "FINBO_DEV_AUTH=1 for local development) and restart the server.",
    )
