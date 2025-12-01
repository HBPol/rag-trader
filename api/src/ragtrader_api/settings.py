"""Configuration primitives for the API service."""

from __future__ import annotations

import base64
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import urlparse

from ragtrader_pipelines.coinbase import Granularity


class SettingsValidationError(ValueError):
    """Raised when API settings fail validation."""


_ALLOWED_ENVS: Final[set[str]] = {"dev", "staging", "prod"}
_DEFAULT_SCHEDULER_SYMBOLS: Final[tuple[str, ...]] = (
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
)
_GRANULARITY_ALIASES: Final[dict[str, Granularity]] = {
    "1M": Granularity.MIN_1,
    "ONE_MINUTE": Granularity.MIN_1,
    "MIN1": Granularity.MIN_1,
    "60": Granularity.MIN_1,
    "5M": Granularity.MIN_5,
    "FIVE_MINUTE": Granularity.MIN_5,
    "MIN5": Granularity.MIN_5,
    "300": Granularity.MIN_5,
    "15M": Granularity.MIN_15,
    "FIFTEEN_MINUTE": Granularity.MIN_15,
    "MIN15": Granularity.MIN_15,
    "900": Granularity.MIN_15,
    "60M": Granularity.MIN_60,
    "1H": Granularity.MIN_60,
    "HOUR": Granularity.MIN_60,
    "3600": Granularity.MIN_60,
    "6H": Granularity.HOUR_6,
    "HOUR6": Granularity.HOUR_6,
    "21600": Granularity.HOUR_6,
    "1D": Granularity.DAY_1,
    "DAY": Granularity.DAY_1,
    "86400": Granularity.DAY_1,
}
_MISSING: Final[object] = object()
_ENV_FILE_LOADED: bool = False


def _repo_root() -> Path:
    resolved = Path(__file__).resolve()
    for _ in range(4):
        resolved = resolved.parent
    return resolved


def _parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        key, value = match.groups()
        env[key] = value
    return env


_ENV_VAR_PATTERN = re.compile(
    r"\$(?:{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)}|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


def _expand_value(value: str, env: Mapping[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group("braced") or match.group("bare")
        if key is None:
            return match.group(0)
        return env.get(key, match.group(0))

    return _ENV_VAR_PATTERN.sub(_replace, value)


def _ensure_env_loaded() -> None:
    global _ENV_FILE_LOADED
    if _ENV_FILE_LOADED:
        return

    env_file = os.environ.get("RAGTRADER_API_ENV_FILE")
    candidates: list[Path] = []
    if env_file:
        candidates.append(Path(env_file).expanduser())

    repo_root = _repo_root()
    candidates.append(repo_root / ".env")
    candidates.append(repo_root / "api/.env")

    for candidate in candidates:
        if not candidate.exists():
            continue
        parsed = _parse_env_file(candidate)
        current_env: dict[str, str] = dict(os.environ)
        for key, value in parsed.items():
            expanded = _expand_value(value, current_env)
            actual = os.environ.setdefault(key, expanded)
            current_env[key] = actual
        break

    _ENV_FILE_LOADED = True


_ensure_env_loaded()


def _coerce_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_symbols(value: str | None) -> tuple[str, ...]:
    if value is None:
        return _DEFAULT_SCHEDULER_SYMBOLS
    parts = [item.strip().upper() for item in value.split(",")]
    symbols = tuple(symbol for symbol in parts if symbol)
    if not symbols:
        raise SettingsValidationError(
            "At least one symbol must be configured for polling."
        )
    return symbols


def _parse_granularity(value: str | None) -> Granularity:
    if not value:
        return Granularity.MIN_1
    normalized = value.strip().upper()
    if normalized in _GRANULARITY_ALIASES:
        return _GRANULARITY_ALIASES[normalized]
    try:
        return Granularity[normalized]
    except KeyError as exc:  # pragma: no cover - defensive branch
        allowed = ", ".join(
            sorted({g.name for g in Granularity} | set(_GRANULARITY_ALIASES))
        )
        raise SettingsValidationError(
            "Unsupported Coinbase granularity value. "
            f"Received {value!r}; expected one of: {allowed}."
        ) from exc


def _coerce_positive_int(value: str | None, *, default: int) -> int:
    candidate = value.strip() if value is not None else None
    raw = candidate if candidate else str(default)
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as exc:
        raise SettingsValidationError(
            "Lookback minutes must be an integer value."
        ) from exc
    if parsed <= 0:
        raise SettingsValidationError("Lookback minutes must be greater than zero.")
    return parsed


def _parse_cors_origins(value: Sequence[str] | str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = list(value)

    normalized: list[str] = []
    for item in raw_items:
        candidate = item.strip()
        if not candidate:
            continue
        parsed = urlparse(candidate)
        if not parsed.scheme or not parsed.netloc:
            raise SettingsValidationError(
                "CORS origins must be fully qualified URLs (including scheme)."
            )
        normalized.append(candidate)

    return tuple(dict.fromkeys(normalized))


def _parse_analytics_pairs_value(value: Sequence[str] | str | None) -> tuple[str, ...]:
    if value is None:
        raw_items: list[str] = []
    elif isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = list(value)

    normalized: list[str] = []
    for item in raw_items:
        candidate = item.strip()
        if not candidate:
            continue
        candidate = candidate.upper().replace("/", "-").replace(":", "-")
        if "-" not in candidate:
            raise SettingsValidationError(
                "Analytics pairs must include a '-' separator between symbols."
            )
        normalized.append(candidate)

    return tuple(dict.fromkeys(normalized))


def _parse_analytics_symbols_value(
    value: Sequence[str] | str | None,
) -> tuple[str, ...]:
    if value is None:
        raw_items: list[str] = []
    elif isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = list(value)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        candidate = item.strip().upper().replace("/", "-")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    return tuple(normalized)


def _symbols_from_pairs(pairs: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for pair in pairs:
        candidate = pair.replace("/", "-").replace(":", "-")
        if "-" not in candidate:
            continue
        base, quote = candidate.split("-", 1)
        for symbol in (base.strip().upper(), quote.strip().upper()):
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            normalized.append(symbol)
    return tuple(normalized)


def _parse_analytics_windows_value(
    value: Sequence[str] | str | None,
) -> tuple[str, ...]:
    if value is None:
        raw_items: list[str] = []
    elif isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = list(value)

    windows: list[str] = []
    for item in raw_items:
        candidate = item.strip()
        if not candidate:
            continue
        windows.append(candidate)

    if not windows:
        return ("1h",)

    return tuple(dict.fromkeys(windows))


def _parse_correlation_metric(value: str | None) -> str:
    candidate = (value or "pearson").strip().lower()
    if not candidate:
        raise SettingsValidationError("Analytics correlation metric must not be empty.")
    return candidate


def _parse_granger_significance(value: float | str | None) -> float:
    candidate: float | str
    if value is None:
        candidate = 0.05
    else:
        candidate = value

    try:
        parsed = float(candidate)
    except (TypeError, ValueError) as exc:
        raise SettingsValidationError(
            "Analytics Granger significance must be a numeric value."
        ) from exc

    if not 0 < parsed <= 1:
        raise SettingsValidationError(
            "Analytics Granger significance must be between 0 and 1."
        )

    return parsed


def _validate_positive_minutes(value: int, *, field: str) -> int:
    if value <= 0:
        raise SettingsValidationError(f"{field} must be greater than zero.")
    return value


def _load_secret_from_manager(name: str) -> str:
    try:
        import boto3  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency guard
        msg = (
            "boto3 must be installed to load secrets from AWS Secrets Manager. "
            "Install boto3 or provide RAGTRADER_SCHEDULER_DATABASE_DSN."
        )
        raise SettingsValidationError(msg) from exc

    client = boto3.client("secretsmanager")
    response: dict[str, Any] = client.get_secret_value(SecretId=name)
    secret_string = cast(str | None, response.get("SecretString"))
    if secret_string:
        return secret_string
    secret_binary = cast(bytes | str | None, response.get("SecretBinary"))
    if not secret_binary:
        raise SettingsValidationError("Secret did not contain a database DSN value.")
    if isinstance(secret_binary, bytes):
        decoded_bytes = secret_binary
    else:
        decoded_bytes = base64.b64decode(secret_binary)
    return decoded_bytes.decode("utf-8")


def _validate_url(candidate: str | None, *, allow_empty: bool = False) -> str | None:
    if candidate is None:
        if allow_empty:
            return None
        raise SettingsValidationError("A URL value is required but missing.")

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise SettingsValidationError(
            f"Unsupported URL scheme for value: {candidate!r}"
        )
    if not parsed.netloc:
        raise SettingsValidationError(f"URL must include a hostname: {candidate!r}")
    return candidate


def _validate_postgres_dsn(candidate: str | None, *, required: bool) -> str | None:
    if candidate is None:
        if required:
            raise SettingsValidationError(
                "POSTGRES_DSN is required when require_database is enabled."
            )
        return None

    parsed = urlparse(candidate)
    if not parsed.scheme.startswith("postgres"):
        raise SettingsValidationError("Postgres DSN must use the postgres scheme.")
    if not parsed.hostname:
        raise SettingsValidationError("Postgres DSN must include a hostname.")
    return candidate


@dataclass(slots=True)
class SchedulerSettings:
    """Structured configuration for the Coinbase polling job."""

    symbols: tuple[str, ...]
    granularity: Granularity
    lookback: timedelta
    database_dsn: str

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str],
        *,
        fallback_dsn: str | None,
    ) -> SchedulerSettings:
        symbols = _parse_symbols(env.get("RAGTRADER_SCHEDULER_COINBASE_SYMBOLS"))
        granularity = _parse_granularity(
            env.get("RAGTRADER_SCHEDULER_COINBASE_GRANULARITY")
        )
        lookback_minutes = _coerce_positive_int(
            env.get("RAGTRADER_SCHEDULER_COINBASE_LOOKBACK_MINUTES"),
            default=15,
        )
        database_dsn = env.get("RAGTRADER_SCHEDULER_DATABASE_DSN")
        if not database_dsn:
            secret_name = env.get("RAGTRADER_SCHEDULER_DATABASE_SECRET_NAME")
            if secret_name:
                database_dsn = _load_secret_from_manager(secret_name)
        if not database_dsn and fallback_dsn:
            database_dsn = fallback_dsn
        if not database_dsn:
            raise SettingsValidationError(
                "Scheduler configuration requires a Postgres DSN. Set "
                "RAGTRADER_SCHEDULER_DATABASE_DSN, provide "
                "RAGTRADER_SCHEDULER_DATABASE_SECRET_NAME, or configure "
                "RAGTRADER_API_POSTGRES_DSN."
            )

        return cls(
            symbols=symbols,
            granularity=granularity,
            lookback=timedelta(minutes=lookback_minutes),
            database_dsn=database_dsn,
        )


@dataclass(slots=True)
class ApiSettings:
    """Settings model with minimal validation and env var parsing."""

    env: str
    app_name: str
    version: str
    cors_origins: tuple[str, ...]
    postgres_dsn: str | None
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    use_qdrant_cloud: bool
    require_database: bool
    require_vector_store: bool
    analytics_pairs: tuple[str, ...]
    analytics_symbols: tuple[str, ...]
    analytics_windows: tuple[str, ...]
    analytics_correlation_metric: str
    analytics_max_age_minutes: int
    analytics_fallback_minutes: int
    analytics_granger_significance: float

    def __init__(
        self,
        *,
        env: str | None = None,
        app_name: str | None = None,
        version: str | None = None,
        cors_origins: Sequence[str] | None = None,
        postgres_dsn: str | None | object = _MISSING,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        qdrant_collection: str | None = None,
        use_qdrant_cloud: bool | None = None,
        require_database: bool | None = None,
        require_vector_store: bool | None = None,
        analytics_pairs: Sequence[str] | None = None,
        analytics_windows: Sequence[str] | None = None,
        analytics_symbols: Sequence[str] | None = None,
        analytics_correlation_metric: str | None = None,
        analytics_max_age_minutes: int | None = None,
        analytics_fallback_minutes: int | None = None,
        analytics_granger_significance: float | None = None,
    ) -> None:
        _ensure_env_loaded()
        env_vars = os.environ

        raw_env = env if env is not None else env_vars.get("RAGTRADER_API_ENV", "dev")
        if raw_env not in _ALLOWED_ENVS:
            raise SettingsValidationError(
                f"env must be one of {_ALLOWED_ENVS!r}; received {raw_env!r}."
            )

        raw_app_name = (
            app_name
            if app_name is not None
            else env_vars.get("RAGTRADER_API_APP_NAME", "ragtrader-api")
        )
        raw_version = (
            version
            if version is not None
            else env_vars.get("RAGTRADER_API_VERSION", "0.1.0")
        )
        parsed_cors_origins = _parse_cors_origins(cors_origins)
        if not parsed_cors_origins:
            raw_cors_from_env = env_vars.get("RAGTRADER_API_CORS_ORIGINS")
            if raw_cors_from_env:
                parsed_cors_origins = _parse_cors_origins(raw_cors_from_env)
        if not parsed_cors_origins and raw_env == "dev":
            parsed_cors_origins = ("http://localhost:5173",)
        if raw_env != "dev" and not parsed_cors_origins:
            raise SettingsValidationError(
                "Configure at least one CORS origin via RAGTRADER_API_CORS_ORIGINS"
                " for non-development environments."
            )

        raw_require_db = (
            require_database
            if require_database is not None
            else _coerce_bool(
                env_vars.get("RAGTRADER_API_REQUIRE_DATABASE"),
                default=True,
            )
        )
        raw_require_vector = (
            require_vector_store
            if require_vector_store is not None
            else _coerce_bool(
                env_vars.get("RAGTRADER_API_REQUIRE_VECTOR_STORE"),
                default=True,
            )
        )
        raw_use_qdrant_cloud = (
            use_qdrant_cloud
            if use_qdrant_cloud is not None
            else _coerce_bool(
                env_vars.get("RAGTRADER_API_USE_QDRANT_CLOUD"),
                default=True,
            )
        )

        if postgres_dsn is _MISSING:
            postgres_candidate = env_vars.get("RAGTRADER_API_POSTGRES_DSN")
        else:
            postgres_candidate = cast(str | None, postgres_dsn)

        if raw_require_db and not postgres_candidate:
            postgres_host = env_vars.get("POSTGRES_HOST")
            postgres_port = env_vars.get("POSTGRES_PORT")
            postgres_db = env_vars.get("POSTGRES_DB")
            postgres_user = env_vars.get("POSTGRES_USER")
            postgres_password = env_vars.get("POSTGRES_PASSWORD")

            missing_components = [
                name
                for name, value in {
                    "POSTGRES_HOST": postgres_host,
                    "POSTGRES_PORT": postgres_port,
                    "POSTGRES_DB": postgres_db,
                    "POSTGRES_USER": postgres_user,
                    "POSTGRES_PASSWORD": postgres_password,
                }.items()
                if not value
            ]
            if missing_components:
                missing_csv = ", ".join(sorted(missing_components))
                raise SettingsValidationError(
                    "Missing Postgres settings required to construct DSN: "
                    f"{missing_csv}."
                )

            postgres_candidate = (
                "postgresql+psycopg://"
                f"{postgres_user}:{postgres_password}@"
                f"{postgres_host}:{postgres_port}/{postgres_db}"
            )
        qdrant_candidate = (
            qdrant_url
            if qdrant_url is not None
            else env_vars.get("RAGTRADER_API_QDRANT_URL", "http://localhost:6333")
        )
        qdrant_key: str | None
        if qdrant_api_key is not None:
            qdrant_key = qdrant_api_key
        else:
            qdrant_key = env_vars.get("RAGTRADER_API_QDRANT_API_KEY")
            if qdrant_key is None:
                qdrant_key = env_vars.get("QDRANT_API_KEY")

        validated_postgres = _validate_postgres_dsn(
            postgres_candidate,
            required=raw_require_db,
        )
        validated_qdrant = _validate_url(
            qdrant_candidate,
            allow_empty=not raw_require_vector,
        )
        if validated_qdrant is None:
            raise SettingsValidationError(
                "Qdrant URL is required when require_vector_store is enabled."
            )
        if raw_require_vector and raw_use_qdrant_cloud and not qdrant_key:
            raise SettingsValidationError(
                "Qdrant API key is required when use_qdrant_cloud is enabled."
            )

        raw_collection = (
            qdrant_collection
            if qdrant_collection is not None
            else env_vars.get("RAGTRADER_API_QDRANT_COLLECTION", "rag-cluster")
        )
        if raw_require_vector and (
            raw_collection is None or not raw_collection.strip()
        ):
            raise SettingsValidationError(
                "Qdrant collection name required when require_vector_store is enabled."
            )
        parsed_collection = (raw_collection or "").strip()

        self.env = raw_env
        self.app_name = raw_app_name
        self.version = raw_version
        self.cors_origins = parsed_cors_origins
        self.postgres_dsn = validated_postgres
        self.qdrant_url = validated_qdrant
        self.qdrant_api_key = qdrant_key
        self.qdrant_collection = parsed_collection
        self.use_qdrant_cloud = raw_use_qdrant_cloud
        self.require_database = raw_require_db
        self.require_vector_store = raw_require_vector

        parsed_pairs = _parse_analytics_pairs_value(analytics_pairs)
        if not parsed_pairs:
            parsed_pairs = _parse_analytics_pairs_value(
                env_vars.get("RAGTRADER_API_ANALYTICS_PAIRS")
            )
        parsed_symbols = _parse_analytics_symbols_value(analytics_symbols)
        if not parsed_symbols:
            parsed_symbols = _parse_analytics_symbols_value(
                env_vars.get("RAGTRADER_API_ANALYTICS_SYMBOLS")
            )
        if not parsed_symbols and parsed_pairs:
            parsed_symbols = _symbols_from_pairs(parsed_pairs)
        parsed_windows = _parse_analytics_windows_value(analytics_windows)
        if not parsed_windows:
            parsed_windows = _parse_analytics_windows_value(
                env_vars.get("RAGTRADER_API_ANALYTICS_WINDOWS")
            )

        parsed_metric = _parse_correlation_metric(analytics_correlation_metric)
        env_metric = env_vars.get("RAGTRADER_API_ANALYTICS_CORRELATION_METRIC")
        if analytics_correlation_metric is None and env_metric is not None:
            parsed_metric = _parse_correlation_metric(env_metric)

        if analytics_max_age_minutes is not None:
            raw_max_age = _validate_positive_minutes(
                analytics_max_age_minutes, field="Analytics max age minutes"
            )
        else:
            raw_max_age = _coerce_positive_int(
                env_vars.get("RAGTRADER_API_ANALYTICS_MAX_AGE_MINUTES"), default=60
            )

        if analytics_fallback_minutes is not None:
            raw_fallback = _validate_positive_minutes(
                analytics_fallback_minutes, field="Analytics fallback minutes"
            )
        else:
            raw_fallback = _coerce_positive_int(
                env_vars.get("RAGTRADER_API_ANALYTICS_FALLBACK_MINUTES"), default=240
            )

        if raw_fallback < raw_max_age:
            raw_fallback = raw_max_age

        parsed_significance = _parse_granger_significance(
            analytics_granger_significance
        )
        env_significance = env_vars.get("RAGTRADER_API_ANALYTICS_GRANGER_SIGNIFICANCE")
        if analytics_granger_significance is None and env_significance is not None:
            parsed_significance = _parse_granger_significance(env_significance)

        self.analytics_pairs = parsed_pairs
        self.analytics_symbols = parsed_symbols
        self.analytics_windows = parsed_windows
        self.analytics_correlation_metric = parsed_metric
        self.analytics_max_age_minutes = raw_max_age
        self.analytics_fallback_minutes = raw_fallback
        self.analytics_granger_significance = parsed_significance

    def readiness_checks(self) -> dict[str, bool]:
        checks: dict[str, bool] = {
            "database": (not self.require_database) or (self.postgres_dsn is not None),
            "vector_store": (not self.require_vector_store)
            or (
                bool(self.qdrant_url)
                and bool(self.qdrant_collection)
                and (not self.use_qdrant_cloud or bool(self.qdrant_api_key))
            ),
        }
        return checks

    def readiness_errors(self) -> list[str]:
        return [name for name, ok in self.readiness_checks().items() if not ok]

    def health_payload(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": self.app_name,
            "environment": self.env,
            "version": self.version,
        }

    def scheduler_options(self) -> SchedulerSettings:
        return SchedulerSettings.from_env(os.environ, fallback_dsn=self.postgres_dsn)


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    return ApiSettings()


__all__ = [
    "ApiSettings",
    "SchedulerSettings",
    "SettingsValidationError",
    "get_settings",
]
