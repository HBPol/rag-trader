"""Shared helpers for validating and normalising coin tickers."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from functools import lru_cache

try:  # pragma: no cover - optional dependency during packaging
    from ragtrader_api.settings import (
        _DEFAULT_SCHEDULER_SYMBOLS as _API_DEFAULT_SCHEDULER_SYMBOLS,
    )
except Exception:  # pragma: no cover - defensive import guard
    _API_DEFAULT_SCHEDULER_SYMBOLS = ("BTC-USD", "ETH-USD", "SOL-USD")

_EXTRA_TICKERS_ENV = "RAGTRADER_CONTENT_ACCEPTED_TICKERS"

_CURATED_FALLBACK_TICKERS: frozenset[str] = frozenset(
    {
        # Core majors we ingest or analyse across the project.
        "AAVE",
        "ADA",
        "ARB",
        "ATOM",
        "AVAX",
        "BNB",
        "BTC",
        "COMP",
        "CORE",
        "DOGE",
        "DOT",
        "ETH",
        "FTM",
        "LINK",
        "LTC",
        "MATIC",
        "MKR",
        "OP",
        "SOL",
        "SUI",
        "UNI",
        "USDC",
        "USDT",
        "XRP",
    }
)

_TOKEN_CHUNK_PATTERN = re.compile(r"[A-Z0-9]{2,10}")
_SEPARATOR_PATTERN = re.compile(r"[\s,/]+")


def _iter_scheduler_symbols() -> Iterator[str]:
    raw = os.environ.get("RAGTRADER_SCHEDULER_COINBASE_SYMBOLS")
    if raw:
        for part in raw.split(","):
            candidate = part.strip()
            if candidate:
                yield candidate
    else:
        yield from _API_DEFAULT_SCHEDULER_SYMBOLS


def _extra_tickers() -> Iterable[str]:
    raw = os.environ.get(_EXTRA_TICKERS_ENV)
    if not raw:
        return ()
    return (part.strip() for part in raw.split(",") if part.strip())


def _extract_base_symbols(symbols: Iterable[str]) -> set[str]:
    bases: set[str] = set()
    for symbol in symbols:
        cleaned = str(symbol).strip().upper().replace("/", "-")
        if not cleaned:
            continue
        base = cleaned.split("-", 1)[0]
        alnum = re.sub(r"[^A-Z0-9]", "", base)
        if _TOKEN_CHUNK_PATTERN.fullmatch(alnum):
            bases.add(alnum)
    return bases


@lru_cache(maxsize=1)
def _compute_known_tickers() -> frozenset[str]:
    tickers: set[str] = set(_CURATED_FALLBACK_TICKERS)
    tickers.update(_extract_base_symbols(_iter_scheduler_symbols()))
    tickers.update(_extract_base_symbols(_extra_tickers()))
    return frozenset(tickers)


KNOWN_TICKERS: frozenset[str] = _compute_known_tickers()


def _tokenise_candidate(value: str) -> Iterator[str]:
    normalised = value.upper().replace("-", " ").replace("/", " ")
    normalised = re.sub(r"[^A-Z0-9\s]", " ", normalised)
    for chunk in _SEPARATOR_PATTERN.split(normalised):
        if chunk:
            yield chunk


def normalise_supported_ticker(token: object) -> str | None:
    """Return a supported ticker derived from ``token`` when available."""

    if token is None:
        return None
    candidate = str(token).strip()
    if not candidate:
        return None

    for chunk in _tokenise_candidate(candidate):
        alnum = re.sub(r"[^A-Z0-9]", "", chunk)
        if not alnum:
            continue
        if alnum in KNOWN_TICKERS:
            return alnum

    alnum = re.sub(r"[^A-Z0-9]", "", candidate.upper())
    if alnum in KNOWN_TICKERS:
        return alnum
    return None


def is_supported_ticker(token: object) -> bool:
    """Check whether ``token`` represents one of the curated tickers."""

    return normalise_supported_ticker(token) is not None


__all__ = ["KNOWN_TICKERS", "is_supported_ticker", "normalise_supported_ticker"]
