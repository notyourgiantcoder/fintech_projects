"""Shared outbound HTTP: timeouts, a small TTL cache, and SSRF protection.

Free data sources rate-limit aggressively, so identical requests within the TTL are
served from memory. URLs chosen by an LLM (the article reader) must pass `check_public_url`
first, so an agent can't be steered into fetching internal services. (The check resolves
the host separately from the request, so a DNS-rebinding attacker could still race it;
a deployment that matters should also block private ranges at the network level.)
"""

from __future__ import annotations

import ipaddress
import os
import socket
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx

T = TypeVar("T")

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_BYTES = 2_000_000


def _contact() -> str:
    # SEC EDGAR and Wikipedia both ask clients to identify themselves with a contact
    # (an email address or URL). Without one, those two sources may refuse requests.
    return os.getenv("FINBO_CONTACT", "").strip()


def user_agent() -> str:
    contact = _contact()
    return f"Finbo/0.4 ({contact})" if contact else "Finbo/0.4"


def reader_user_agent() -> str:
    """For page reads: news sites expect a browser-style agent."""
    contact = _contact()
    suffix = f"; {contact}" if contact else ""
    return f"Mozilla/5.0 (compatible; Finbo/0.4{suffix})"


def client(agent: str | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": agent or user_agent()},
        follow_redirects=False,
    )


class TTLCache:
    def __init__(self, ttl_seconds: float, max_items: int = 512) -> None:
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Any, factory: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        value = factory()
        with self._lock:
            if len(self._data) >= self.max_items:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class UnsafeUrlError(ValueError):
    pass


def check_public_url(url: str, resolve: Callable[[str], list[str]] | None = None) -> str:
    """Allow only http(s) URLs whose host resolves exclusively to public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise UnsafeUrlError("Only http and https links can be read.")
    if parts.username or parts.password:
        raise UnsafeUrlError("Links with credentials can't be read.")
    resolve = resolve or _resolve
    try:
        addresses = resolve(parts.hostname)
    except OSError:
        raise UnsafeUrlError(f"Couldn't resolve {parts.hostname}.") from None
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeUrlError("That link points to a private or internal address.")
    return url


def _resolve(host: str) -> list[str]:
    return sorted({info[4][0] for info in socket.getaddrinfo(host, None)})


def fetch_public(
    url: str,
    http: httpx.Client | None = None,
    max_redirects: int = 3,
    resolve: Callable[[str], list[str]] | None = None,
) -> httpx.Response:
    """GET a public URL, re-checking every redirect hop and capping the body size."""
    own = http is None
    http = http or client(reader_user_agent())
    try:
        current = url
        for _ in range(max_redirects + 1):
            check_public_url(current, resolve)
            with http.stream("GET", current) as res:
                if res.is_redirect:
                    location = res.headers.get("location", "")
                    current = str(httpx.URL(current).join(location))
                    continue
                body = b""
                for chunk in res.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise UnsafeUrlError("The page is larger than 2 MB.")
                # iter_bytes() already decompressed the body, so drop the encoding
                # headers or httpx would try to decompress it a second time.
                headers = {
                    k: v
                    for k, v in res.headers.items()
                    if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
                }
                return httpx.Response(
                    res.status_code, headers=headers, content=body, request=res.request
                )
        raise UnsafeUrlError("Too many redirects.")
    finally:
        if own:
            http.close()
