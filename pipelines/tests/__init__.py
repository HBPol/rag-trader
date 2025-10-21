"""Utilities for accessing test fixtures."""

from __future__ import annotations

from pathlib import Path

_TESTS_ROOT = Path(__file__).resolve().parent
_FIXTURES_ROOT = _TESTS_ROOT / "fixtures"
_ANALYTICS_ROOT = _FIXTURES_ROOT / "analytics"


def get_analytics_fixture_path(format_name: str) -> Path:
    """Return the path to an analytics fixture in the requested format."""

    normalized = format_name.lower()
    candidates = {
        "csv": _ANALYTICS_ROOT / "btc_eth_hourly_analytics.csv",
        "parquet": _ANALYTICS_ROOT / "btc_eth_hourly_analytics.parquet",
    }
    try:
        path = candidates[normalized]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(
            f"Unsupported analytics fixture format: {format_name}"
        ) from exc
    return path


__all__ = [
    "get_analytics_fixture_path",
]
