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
        "REACHABILITY_RSS_FEEDS": "https://rss.example.com/feed",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://rss.example.com/feed": make_response(
            "https://rss.example.com/feed", 200
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
    assert statuses["rss:https://rss.example.com/feed"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].status is ProbeStatus.SUCCESS


def test_run_probes_rate_limit_emits_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_RSS_FEEDS": "https://rss.example.com/feed",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 429
        ),
        "https://rss.example.com/feed": make_response(
            "https://rss.example.com/feed", 200
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
    assert statuses["rss:https://rss.example.com/feed"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].status is ProbeStatus.SUCCESS


def test_run_probes_failure_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "COINBASE_API_BASE": "https://example.com/coinbase",
        "REACHABILITY_RSS_FEEDS": "https://rss.example.com/feed",
        "QDRANT_URL": "https://vector.example.com",
    }

    responses = {
        "https://example.com/coinbase/time": make_response(
            "https://example.com/coinbase/time", 200
        ),
        "https://rss.example.com/feed": make_response(
            "https://rss.example.com/feed", 200
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
    assert statuses["rss:https://rss.example.com/feed"].status is ProbeStatus.SUCCESS
    assert statuses["qdrant"].status is ProbeStatus.FAILURE
    assert "boom" in statuses["qdrant"].detail
