"""Tests for the external service reachability probes."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from tools import reachability
from tools.reachability import ProbeStatus

requests = reachability.requests


def make_response(url: str, status: int) -> requests.Response:
    if hasattr(requests.Response, "__annotations__") and "status_code" in getattr(
        requests.Response, "__annotations__", {}
    ):
        return requests.Response(status_code=status, text="", headers={}, url=url)

    response = requests.Response()
    response.status_code = status
    if hasattr(response, "_content"):
        response._content = b""
    response.url = url
    return response


def collect_statuses(
    results: Iterable[reachability.ProbeResult],
) -> dict[str, reachability.ProbeResult]:
    return {result.name: result for result in results}


def test_run_probes_success(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
        "https://vector.example.com/healthz": make_response(
            "https://vector.example.com/healthz", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["coinbase"].status is ProbeStatus.SUCCESS
    assert (
        statuses["coindesk:https://data.example.com/news"].status is ProbeStatus.SUCCESS
    )
    assert statuses["qdrant"].status is ProbeStatus.SUCCESS


def test_qdrant_probe_prefers_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "REACHABILITY_QDRANT_URL": "https://override.example.com",
        "RAGTRADER_API_QDRANT_URL": "https://api.example.com/qdrant",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
        "https://override.example.com/healthz": make_response(
            "https://override.example.com/healthz", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["qdrant"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].detail.endswith("override.example.com/healthz")


def test_qdrant_probe_defaults_to_api_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "RAGTRADER_API_QDRANT_URL": "https://api.example.com/qdrant",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
        "https://api.example.com/qdrant/healthz": make_response(
            "https://api.example.com/qdrant/healthz", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["qdrant"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].detail.endswith("api.example.com/qdrant/healthz")


def test_qdrant_probe_respects_local_override(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "RAGTRADER_USE_LOCAL_QDRANT": "true",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
        "http://localhost:6333/healthz": make_response(
            "http://localhost:6333/healthz", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["qdrant"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].detail.endswith("localhost:6333/healthz")


def test_run_probes_rate_limit_emits_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 429
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
        "https://vector.example.com/healthz": make_response(
            "https://vector.example.com/healthz", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["coinbase"].status is ProbeStatus.SKIPPED
    assert "rate limited" in statuses["coinbase"].detail
    assert (
        statuses["coindesk:https://data.example.com/news"].status is ProbeStatus.SUCCESS
    )
    assert statuses["qdrant"].status is ProbeStatus.SUCCESS


def test_run_probes_failure_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
        "CONTENT_COINDESK_API_KEY": "token",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://data.example.com/news": make_response(
            "https://data.example.com/news", 200
        ),
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        if url == "https://vector.example.com/healthz":
            raise requests.ConnectionError("boom")
        return responses[url]

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = reachability.run_probes(env)
    statuses = collect_statuses(results)

    assert statuses["coinbase"].status is ProbeStatus.SUCCESS
    assert (
        statuses["coindesk:https://data.example.com/news"].status is ProbeStatus.SUCCESS
    )
    assert statuses["qdrant"].status is ProbeStatus.FAILURE
    assert "boom" in statuses["qdrant"].detail


def test_coindesk_probe_skips_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "REACHABILITY_COINDESK_ENDPOINTS": "https://data.example.com/news",
    }

    def fake_get(url: str, headers=None, timeout=None):  # type: ignore[override]
        raise AssertionError("Should not perform request without API key")

    monkeypatch.setattr(reachability.requests, "get", fake_get)

    results = list(reachability.probe_coindesk_api(env, timeout=5.0))
    assert results == [
        reachability.ProbeResult(
            name="coindesk:https://data.example.com/news",
            status=ProbeStatus.SKIPPED,
            detail="CoinDesk API key is not configured",
        )
    ]
