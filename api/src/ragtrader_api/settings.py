"""Configuration primitives for the API service."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import urlparse


class SettingsValidationError(ValueError):
    """Raised when API settings fail validation."""


_ALLOWED_ENVS: Final[set[str]] = {"dev", "staging", "prod"}
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
        for key, value in _parse_env_file(candidate).items():
            os.environ.setdefault(key, value)
        break

    _ENV_FILE_LOADED = True


_ensure_env_loaded()


def _coerce_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
class ApiSettings:
    """Settings model with minimal validation and env var parsing."""

    env: str
    app_name: str
    version: str
    postgres_dsn: str | None
    qdrant_url: str
    qdrant_api_key: str | None
    use_qdrant_cloud: bool
    require_database: bool
    require_vector_store: bool

    def __init__(
        self,
        *,
        env: str | None = None,
        app_name: str | None = None,
        version: str | None = None,
        postgres_dsn: str | None | object = _MISSING,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        use_qdrant_cloud: bool | None = None,
        require_database: bool | None = None,
        require_vector_store: bool | None = None,
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
        qdrant_key = (
            qdrant_api_key
            if qdrant_api_key is not None
            else env_vars.get("RAGTRADER_API_QDRANT_API_KEY")
        )

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

        self.env = raw_env
        self.app_name = raw_app_name
        self.version = raw_version
        self.postgres_dsn = validated_postgres
        self.qdrant_url = validated_qdrant
        self.qdrant_api_key = qdrant_key
        self.use_qdrant_cloud = raw_use_qdrant_cloud
        self.require_database = raw_require_db
        self.require_vector_store = raw_require_vector

    def readiness_checks(self) -> dict[str, bool]:
        checks: dict[str, bool] = {
            "database": (not self.require_database) or (self.postgres_dsn is not None),
            "vector_store": (not self.require_vector_store)
            or (
                bool(self.qdrant_url)
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


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    return ApiSettings()


__all__ = [
    "ApiSettings",
    "SettingsValidationError",
    "get_settings",
]
