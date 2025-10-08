"""External service reachability probes used by CI."""

from __future__ import annotations

import base64
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

try:  # pragma: no cover - exercised in environments with real requests installed
    import requests  # type: ignore[assignment]
    from requests import Response  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - our tests rely on the shim instead
    from . import _requests_shim as requests  # type: ignore[no-redef]

    Response = requests.Response  # type: ignore[assignment]

DEFAULT_RSS_FEEDS: tuple[str, ...] = (
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.reddit.com/r/CryptoCurrency/.rss",
)
RATE_LIMIT_STATUS = 429
DEFAULT_TIMEOUT_SECONDS = 10.0


class ProbeStatus(Enum):
    """Outcome of a reachability probe."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILURE = "failure"


@dataclass
class ProbeResult:
    """Result of a single reachability probe."""

    name: str
    status: ProbeStatus
    detail: str = ""


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def should_skip(flag: str, env: Mapping[str, str]) -> bool:
    return parse_bool(env.get(flag))


def build_rss_feeds(env: Mapping[str, str]) -> Sequence[str]:
    raw = env.get("REACHABILITY_RSS_FEEDS")
    if not raw:
        return DEFAULT_RSS_FEEDS

    feeds: list[str] = []
    for candidate in raw.replace("\n", ",").split(","):
        url = candidate.strip()
        if url:
            feeds.append(url)
    return feeds


def probe_url(
    name: str, url: str, *, headers: Mapping[str, str] | None = None, timeout: float
) -> ProbeResult:
    try:
        response: Response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return ProbeResult(name=name, status=ProbeStatus.FAILURE, detail=str(exc))

    if response.status_code == RATE_LIMIT_STATUS:
        return ProbeResult(
            name=name,
            status=ProbeStatus.SKIPPED,
            detail=f"HTTP {response.status_code} (rate limited)",
        )
    if response.status_code >= 400:
        return ProbeResult(
            name=name,
            status=ProbeStatus.FAILURE,
            detail=f"HTTP {response.status_code} for {url}",
        )
    return ProbeResult(
        name=name,
        status=ProbeStatus.SUCCESS,
        detail=f"HTTP {response.status_code} for {url}",
    )


def probe_coinbase(env: Mapping[str, str], timeout: float) -> ProbeResult:
    if should_skip("REACHABILITY_SKIP_COINBASE", env):
        return ProbeResult(
            name="coinbase",
            status=ProbeStatus.SKIPPED,
            detail="REACHABILITY_SKIP_COINBASE is set",
        )

    base_url = env.get("COINBASE_API_BASE", "https://api.exchange.coinbase.com").rstrip(
        "/"
    )
    url = f"{base_url}/time"
    return probe_url("coinbase", url, timeout=timeout)


def probe_qdrant(env: Mapping[str, str], timeout: float) -> ProbeResult:
    if should_skip("REACHABILITY_SKIP_QDRANT", env):
        return ProbeResult(
            name="qdrant",
            status=ProbeStatus.SKIPPED,
            detail="REACHABILITY_SKIP_QDRANT is set",
        )

    base_url = env.get("REACHABILITY_QDRANT_URL") or env.get("QDRANT_URL")
    if not base_url:
        return ProbeResult(
            name="qdrant",
            status=ProbeStatus.SKIPPED,
            detail="QDRANT_URL is not configured",
        )

    if "<" in base_url or ">" in base_url:
        return ProbeResult(
            name="qdrant",
            status=ProbeStatus.SKIPPED,
            detail="QDRANT_URL uses placeholder value",
        )

    base_url = base_url.rstrip("/")
    url = f"{base_url}/healthz"
    headers: dict[str, str] = {}
    api_key = env.get("QDRANT_API_KEY")
    if api_key:
        headers["api-key"] = api_key
    return probe_url("qdrant", url, headers=headers, timeout=timeout)


def probe_rss_feeds(env: Mapping[str, str], timeout: float) -> Iterable[ProbeResult]:
    feeds = build_rss_feeds(env)
    if should_skip("REACHABILITY_SKIP_RSS", env):
        for feed in feeds:
            yield ProbeResult(
                name=f"rss:{feed}",
                status=ProbeStatus.SKIPPED,
                detail="REACHABILITY_SKIP_RSS is set",
            )
        return

    if not feeds:
        yield ProbeResult(
            name="rss",
            status=ProbeStatus.SKIPPED,
            detail="No RSS feeds configured",
        )
        return

    headers: Mapping[str, str] | None = None
    credentials = env.get("RSS_BASIC_AUTH")
    if credentials:
        token = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {token}"}

    for feed in feeds:
        yield probe_url(name=f"rss:{feed}", url=feed, timeout=timeout, headers=headers)


def run_probes(env: Mapping[str, str] | None = None) -> list[ProbeResult]:
    env_map = dict(os.environ if env is None else env)

    if should_skip("REACHABILITY_SKIP_ALL", env_map):
        return [
            ProbeResult(
                name="reachability",
                status=ProbeStatus.SKIPPED,
                detail="REACHABILITY_SKIP_ALL is set",
            )
        ]

    timeout = float(
        env_map.get("REACHABILITY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    results: list[ProbeResult] = []
    results.append(probe_coinbase(env_map, timeout=timeout))
    results.extend(probe_rss_feeds(env_map, timeout=timeout))
    results.append(probe_qdrant(env_map, timeout=timeout))
    return results


def main() -> int:
    results = run_probes()
    for result in results:
        detail = f" - {result.detail}" if result.detail else ""
        print(f"[{result.status.value.upper()}] {result.name}{detail}")

    failures = [result for result in results if result.status is ProbeStatus.FAILURE]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
