"""Shared HTTP session with retries and a typed error for upstream failures."""
from __future__ import annotations

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class UpstreamError(Exception):
    """A third-party provider failed or returned something unusable."""

    def __init__(self, provider: str, message: str):
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.message = message


_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers["User-Agent"] = settings.USER_AGENT
        _session = s
    return _session


def get_json(provider: str, url: str, params: dict | None = None):
    try:
        resp = session().get(url, params=params, timeout=settings.HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise UpstreamError(provider, f"request failed ({exc.__class__.__name__})") from exc
    if resp.status_code >= 400:
        raise UpstreamError(provider, f"HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise UpstreamError(provider, "invalid JSON") from exc
