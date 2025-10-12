"""End-to-end tests for the forthcoming content ingestion job orchestrator."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from ragtrader_pipelines.content import (
    ArticleCandidate,
    ContentAggregator,
    ContentIngestionJob,
    NormalizedArticleRecord,
    SentimentRecord,
)
from ragtrader_pipelines.sentiment import (
    SentimentAspect,
    SentimentLabel,
    SentimentResult,
    ZScoreCalculator,
)

# NOTE: This test module is expected to fail until ContentIngestionJob is implemented.


@dataclass(slots=True)
class FakeClock:
    """A simple callable clock returning a fixed ``datetime``."""

    now: dt.datetime

    def __call__(self) -> dt.datetime:  # pragma: no cover - trivial
        return self.now


class StubSource:
    """Stub implementation that records fetch windows and returns canned results."""

    def __init__(self, *, batches: Sequence[Iterable[ArticleCandidate]]) -> None:
        self._batches = [list(batch) for batch in batches]
        self.requests: list[tuple[dt.datetime, dt.datetime]] = []
        self._calls = 0

    def fetch(self, start: dt.datetime, end: dt.datetime) -> list[ArticleCandidate]:
        self.requests.append((start, end))
        batch = self._batches[min(self._calls, len(self._batches) - 1)]
        self._calls += 1
        return list(batch)


class StubClassifier:
    """Collect classify calls and return scripted ``SentimentResult`` objects."""

    def __init__(self, *, results: Sequence[SentimentResult]) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def classify(
        self, text: str, metadata: Mapping[str, Any] | None
    ) -> SentimentResult:
        if not self._results:
            raise AssertionError(
                "Unexpected classify call – no scripted result available"
            )
        payload = self._results.pop(0)
        self.calls.append((text, metadata or {}))
        return payload


class StubRepository:
    """Capture the payloads passed to ``upsert_article_with_sentiments``."""

    def __init__(self) -> None:
        self.upserts: list[
            tuple[NormalizedArticleRecord, tuple[SentimentRecord, ...]]
        ] = []

    def upsert_article_with_sentiments(
        self,
        *,
        article: NormalizedArticleRecord,
        sentiments: Iterable[SentimentRecord],
    ) -> int:
        payload = (article, tuple(sentiments))
        self.upserts.append(payload)
        return len(self.upserts)


def _polarity_for(label: SentimentLabel) -> float:
    """Return the expected numeric polarity for a sentiment label."""

    if label is SentimentLabel.BULLISH:
        return 1.0
    if label is SentimentLabel.BEARISH:
        return -1.0
    return 0.0


def test_content_ingestion_job_deduplicates_and_persists_results() -> None:
    """Verify the orchestrator coordinates fetching, scoring, and persistence."""

    now = dt.datetime(2024, 5, 20, 12, 0, tzinfo=dt.UTC)
    clock = FakeClock(now)
    aggregator = ContentAggregator(
        freshness_window=dt.timedelta(minutes=15),
        clock=clock,
    )
    zscores = ZScoreCalculator(window=2)

    primary_article = ArticleCandidate(
        source="coindesk",
        url="https://www.coindesk.com/markets/btc-rally/",
        title="Bitcoin Rally Gains Momentum",
        excerpt="BTC surges past resistance levels as demand grows.",
        coins=["BTC", "ETH"],
        published_ts=now - dt.timedelta(hours=1),
    )
    duplicate_article = ArticleCandidate(
        source="coindesk",
        url="https://www.coindesk.com/markets/btc-rally/",
        title="Bitcoin Rally Gains Momentum",
        excerpt="BTC surges past resistance levels as demand grows.",
        coins=["BTC", "ETH"],
        published_ts=primary_article.published_ts,
    )
    secondary_article = ArticleCandidate(
        source="cointelegraph",
        url="https://cointelegraph.com/news/eth-bearish-outlook/",
        title="Ethereum Faces Bearish Outlook",
        excerpt="Analysts warn of regulatory headwinds for ETH.",
        coins=["ETH"],
        published_ts=now - dt.timedelta(minutes=45),
    )

    source_alpha = StubSource(batches=[(primary_article, duplicate_article)])
    source_beta = StubSource(batches=[(duplicate_article, secondary_article)])

    classifier = StubClassifier(
        results=[
            SentimentResult(
                label=SentimentLabel.BULLISH,
                confidence=0.78,
                aspects=(SentimentAspect.HYPE,),
                coins=("BTC", "ETH"),
            ),
            SentimentResult(
                label=SentimentLabel.BEARISH,
                confidence=0.62,
                aspects=(SentimentAspect.REGULATORY, SentimentAspect.SECURITY),
                coins=("ETH",),
            ),
        ]
    )
    repository = StubRepository()

    job = ContentIngestionJob(
        sources={"alpha": source_alpha, "beta": source_beta},
        aggregator=aggregator,
        classifier=classifier,
        repository=repository,
        zscore_calculator=zscores,
        clock=clock,
    )

    lookback = dt.timedelta(hours=4)
    job.run(lookback=lookback)

    expected_window = (now - lookback, now)
    assert source_alpha.requests == [expected_window]
    assert source_beta.requests == [expected_window]

    assert len(classifier.calls) == 2
    first_call, second_call = classifier.calls
    assert primary_article.title in first_call[0]
    assert set(first_call[1]["coins"]) == set(primary_article.coins)
    assert secondary_article.title in second_call[0]
    assert set(second_call[1]["coins"]) == set(secondary_article.coins)

    assert len(repository.upserts) == 2

    first_article, first_sentiments = repository.upserts[0]
    assert first_article.source == primary_article.source
    assert first_article.url == primary_article.url
    assert first_article.title == primary_article.title
    assert first_article.excerpt == primary_article.excerpt
    assert first_article.coins == primary_article.coins
    assert first_article.published_ts == primary_article.published_ts

    assert {record.coin for record in first_sentiments} == {"BTC", "ETH"}
    for sentiment in first_sentiments:
        assert pytest.approx(float(sentiment.polarity)) == _polarity_for(
            SentimentLabel.BULLISH
        )
        assert pytest.approx(float(sentiment.confidence)) == 0.78
        assert all(aspect.islower() for aspect in sentiment.aspects)
        assert sentiment.ts == primary_article.published_ts
        assert sentiment.zscore_window == zscores.window

    second_article_record, second_sentiments = repository.upserts[1]
    assert second_article_record.source == secondary_article.source
    assert second_article_record.url == secondary_article.url
    assert second_article_record.title == secondary_article.title
    assert second_article_record.excerpt == secondary_article.excerpt
    assert second_article_record.coins == secondary_article.coins
    assert second_article_record.published_ts == secondary_article.published_ts

    assert {record.coin for record in second_sentiments} == {"ETH"}
    for sentiment in second_sentiments:
        assert pytest.approx(float(sentiment.polarity)) == _polarity_for(
            SentimentLabel.BEARISH
        )
        assert pytest.approx(float(sentiment.confidence)) == 0.62
        assert all(aspect.islower() for aspect in sentiment.aspects)
        assert sentiment.ts == secondary_article.published_ts
        assert sentiment.zscore_window == zscores.window


def test_content_ingestion_job_applies_rolling_zscores() -> None:
    """Ensure rolling z-scores are attached using the configured calculator."""

    now = dt.datetime(2024, 5, 20, 14, 30, tzinfo=dt.UTC)
    clock = FakeClock(now)
    aggregator = ContentAggregator(
        freshness_window=dt.timedelta(minutes=15),
        clock=clock,
    )
    zscores = ZScoreCalculator(window=2)

    first_article = ArticleCandidate(
        source="alpha",
        url="https://example.com/btc-bullish",
        title="BTC Bulls Charge Higher",
        excerpt="Bitcoin climbs after strong inflows.",
        coins=["BTC"],
        published_ts=now - dt.timedelta(minutes=50),
    )
    second_article = ArticleCandidate(
        source="beta",
        url="https://example.com/btc-correction",
        title="BTC Correction Looms",
        excerpt="Analysts expect a pullback following the rally.",
        coins=["BTC"],
        published_ts=now - dt.timedelta(minutes=20),
    )

    source = StubSource(batches=[(first_article, second_article)])
    classifier = StubClassifier(
        results=[
            SentimentResult(
                label=SentimentLabel.BULLISH,
                confidence=0.75,
                aspects=(SentimentAspect.HYPE,),
                coins=("BTC",),
            ),
            SentimentResult(
                label=SentimentLabel.BEARISH,
                confidence=0.6,
                aspects=(SentimentAspect.REGULATORY,),
                coins=("BTC",),
            ),
        ]
    )
    repository = StubRepository()

    job = ContentIngestionJob(
        sources={"source": source},
        aggregator=aggregator,
        classifier=classifier,
        repository=repository,
        zscore_calculator=zscores,
        clock=clock,
    )

    job.run(lookback=dt.timedelta(hours=6))

    assert len(repository.upserts) == 2
    _, first_sentiments = repository.upserts[0]
    _, second_sentiments = repository.upserts[1]

    assert len(first_sentiments) == 1
    first_record = first_sentiments[0]
    assert first_record.coin == "BTC"
    assert first_record.zscore_window == 2
    assert first_record.zscore is None

    assert len(second_sentiments) == 1
    second_record = second_sentiments[0]
    assert second_record.coin == "BTC"
    assert second_record.zscore_window == 2
    assert pytest.approx(float(second_record.zscore)) == -1.0
