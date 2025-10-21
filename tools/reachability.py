"""External service reachability probes used by CI."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

try:  # pragma: no cover - exercised in environments with real requests installed
    import requests  # type: ignore[assignment]
    from requests import Response  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - our tests rely on the shim instead
    from . import _requests_shim as requests  # type: ignore[no-redef]

    Response = requests.Response  # type: ignore[assignment]

DEFAULT_COINDESK_BASE_URL = "https://data-api.coindesk.com"
DEFAULT_COINDESK_ENDPOINT_PATH = "/news/v1/article/list?limit=1"
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


def should_skip_any(flags: Sequence[str], env: Mapping[str, str]) -> bool:
    return any(parse_bool(env.get(flag)) for flag in flags)


def first_non_empty(env: Mapping[str, str], *keys: str) -> str | None:
    for key in keys:
        value = env.get(key)
        if value and value.strip():
            return value.strip()
    return None


def build_coindesk_endpoints(env: Mapping[str, str]) -> Sequence[str]:
    raw = first_non_empty(
        env, "REACHABILITY_COINDESK_ENDPOINTS", "REACHABILITY_RSS_FEEDS"
    )
    if raw:
        endpoints: list[str] = []
        for candidate in raw.replace("\n", ",").split(","):
            url = candidate.strip()
            if url:
                endpoints.append(url)
        if endpoints:
            return endpoints

    base_url = (
        first_non_empty(
            env,
            "REACHABILITY_COINDESK_BASE_URL",
            "CONTENT_COINDESK_BASE_URL",
            "CONTENT_RSS_COINDESK_BASE_URL",
        )
        or DEFAULT_COINDESK_BASE_URL
    ).rstrip("/")

    endpoint_path = env.get(
        "REACHABILITY_COINDESK_ENDPOINT_PATH", DEFAULT_COINDESK_ENDPOINT_PATH
    )
    endpoint_path = endpoint_path.strip()
    if not endpoint_path:
        endpoint_path = DEFAULT_COINDESK_ENDPOINT_PATH

    if endpoint_path.startswith("http"):
        return [endpoint_path]

    if not endpoint_path.startswith("/"):
        endpoint_path = f"/{endpoint_path}"

    return [f"{base_url}{endpoint_path}"]


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


def probe_coindesk_api(env: Mapping[str, str], timeout: float) -> Iterable[ProbeResult]:
    endpoints = build_coindesk_endpoints(env)
    if should_skip_any(("REACHABILITY_SKIP_COINDESK", "REACHABILITY_SKIP_RSS"), env):
        for endpoint in endpoints:
            yield ProbeResult(
                name=f"coindesk:{endpoint}",
                status=ProbeStatus.SKIPPED,
                detail="CoinDesk reachability probe is disabled",
            )
        return

    if not endpoints:
        yield ProbeResult(
            name="coindesk",
            status=ProbeStatus.SKIPPED,
            detail="No CoinDesk endpoints configured",
        )
        return

    api_key = first_non_empty(
        env,
        "REACHABILITY_COINDESK_API_KEY",
        "CONTENT_COINDESK_API_KEY",
        "CONTENT_RSS_COINDESK_API_KEY",
    )
    if not api_key:
        for endpoint in endpoints:
            yield ProbeResult(
                name=f"coindesk:{endpoint}",
                status=ProbeStatus.SKIPPED,
                detail="CoinDesk API key is not configured",
            )
        return

    headers = {
        "accept": "application/json",
        "x-api-key": api_key,
    }

    for endpoint in endpoints:
        yield probe_url(
            name=f"coindesk:{endpoint}",
            url=endpoint,
            timeout=timeout,
            headers=headers,
        )


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
    results.extend(probe_coindesk_api(env_map, timeout=timeout))
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
