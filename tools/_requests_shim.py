"""Minimal requests-compatible shim using urllib for offline testing."""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping
from urllib import error, request


class RequestException(Exception):
    """Base exception for shimmed requests errors."""


class ConnectionError(RequestException):
    """Raised when the shim cannot establish a connection."""


@dataclasses.dataclass
class Response:
    status_code: int
    text: str
    headers: Mapping[str, str]
    url: str


def get(url: str, headers: Mapping[str, str] | None = None, timeout: float | None = None) -> Response:
    req = request.Request(url, headers=headers or {})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            headers_map = dict(resp.headers.items())
            return Response(status_code=resp.getcode(), text=body.decode("utf-8", "replace"), headers=headers_map, url=url)
    except error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        headers_map = dict(getattr(exc, "headers", {}) or {})
        return Response(status_code=exc.code, text=body.decode("utf-8", "replace"), headers=headers_map, url=url)
    except error.URLError as exc:  # pragma: no cover - exercised via tests raising ConnectionError
        raise ConnectionError(str(exc)) from exc


def __getattr__(name: str) -> Any:  # pragma: no cover - compatibility for unexpected attributes
    raise AttributeError(f"requests shim does not implement attribute: {name}")
