import datetime as dt
from collections.abc import Mapping

import pytest

from ragtrader_pipelines.content import SourceFactoryError, build_arg_parser, main


class DummySource:
    def fetch(self, start: dt.datetime, end: dt.datetime):
        return []


def test_build_arg_parser_accepts_adapters_and_factory() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        ["--adapters", "coindesk,reddit", "--source-factory", "pkg:factory"]
    )

    assert args.adapters == "coindesk,reddit"
    assert args.source_factory == "pkg:factory"


def test_main_uses_default_factory_when_not_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///memory")
    monkeypatch.setenv("CONTENT_DEDUPE_URL", "redis://localhost/0")

    captured: dict[str, object] = {}

    def fake_default_content_sources(
        *, adapters, env, clock, **_: object
    ) -> Mapping[str, DummySource]:
        captured["adapters"] = adapters
        captured["env_database"] = env.get("DATABASE_URL")
        sources = {"coindesk": DummySource()}
        captured["sources_returned"] = sources
        return sources

    def fake_create_engine(url: str, *, future: bool) -> object:
        captured["engine_url"] = url
        captured["engine_future"] = future
        return object()

    class DummyRepository:
        def __init__(self, engine: object) -> None:
            captured["repository_engine"] = engine

    sentinel_cache = object()

    def fake_build_cache(url: str | None) -> object:
        captured["dedupe_url"] = url
        return sentinel_cache

    job_state: dict[str, object] = {}

    class DummyJob:
        def __init__(
            self,
            *,
            sources,
            aggregator,
            classifier,
            repository,
            zscore_calculator,
            clock,
        ) -> None:
            job_state["sources"] = sources
            job_state["aggregator"] = aggregator
            job_state["repository"] = repository
            job_state["zscore_window"] = zscore_calculator.window
            job_state["clock"] = clock

        def run(self, *, lookback: dt.timedelta) -> None:
            job_state["lookback"] = lookback

    monkeypatch.setattr(
        "ragtrader_pipelines.content.default_content_sources",
        fake_default_content_sources,
    )
    monkeypatch.setattr("ragtrader_pipelines.content.create_engine", fake_create_engine)
    monkeypatch.setattr(
        "ragtrader_pipelines.content.SqlAlchemyContentRepository", DummyRepository
    )
    monkeypatch.setattr(
        "ragtrader_pipelines.content._maybe_build_dedupe_cache", fake_build_cache
    )
    monkeypatch.setattr("ragtrader_pipelines.content.ContentIngestionJob", DummyJob)

    result = main(
        [
            "--adapters",
            "coindesk,reddit",
            "--lookback-minutes",
            "90",
            "--freshness-minutes",
            "45",
            "--zscore-window",
            "3",
        ]
    )

    assert result == 0
    assert captured["adapters"] == ["coindesk", "reddit"]
    assert captured["env_database"] == "sqlite:///memory"
    assert captured["engine_url"] == "sqlite:///memory"
    assert captured["engine_future"] is True
    assert job_state["lookback"] == dt.timedelta(minutes=90)
    assert job_state["zscore_window"] == 3
    assert job_state["sources"] == captured["sources_returned"]
    assert job_state["aggregator"]._freshness_window == dt.timedelta(minutes=45)
    assert job_state["aggregator"]._cache is sentinel_cache
    assert captured["dedupe_url"] == "redis://localhost/0"


def test_main_exits_when_default_factory_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///memory")

    def fake_default_content_sources(**_: object) -> Mapping[str, DummySource]:
        raise SourceFactoryError("missing credentials")

    monkeypatch.setattr(
        "ragtrader_pipelines.content.default_content_sources",
        fake_default_content_sources,
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["--adapters", "coindesk"])

    assert "missing credentials" in str(excinfo.value)
