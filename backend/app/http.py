"""Shared HTTP client for collectors (public APIs only)."""

import httpx2

USER_AGENT = "Jarvis/0.1 (personal dashboard)"


def make_http_client(transport: httpx2.BaseTransport | None = None) -> httpx2.Client:
    """Client with explicit timeouts and a few retries on connection errors.

    Tests pass an httpx2.MockTransport so no request leaves the machine.
    """
    return httpx2.Client(
        transport=transport or httpx2.HTTPTransport(retries=2),
        timeout=httpx2.Timeout(30.0, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
