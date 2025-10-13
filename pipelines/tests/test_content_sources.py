import datetime as dt

import httpx
import pytest

from ragtrader_pipelines.content import (
    CoinDeskContentSource,
    CoinTelegraphContentSource,
    RedditContentSource,
    SourceFactoryError,
    default_content_sources,
)


def _coindesk_payload(published: str) -> dict[str, object]:
    return {
        "guid": "coindesk-abc123",
        "title": "Bitcoin Rally Charges Ahead",
        "link": "HTTPS://CoinDesk.com/Markets/Bitcoin-Rally/?utm_source=rss#section",
        "summary": "<p>Bitcoin pushes <strong>above</strong> $60K again.</p>",
        "published": published,
        "tickers": ["btc", "Eth"],
        "language": "en",
    }


def _cointelegraph_payload(published: str) -> dict[str, object]:
    return {
        "id": "cointelegraph-987",
        "headline": "Solana NFTs Gain Momentum",
        "url": "https://cointelegraph.com/news/solana-nfts-gain-momentum?ref=rss",
        "description": "<div>Solana-based collections attract new buyers.</div>",
        "published_at": published,
        "tags": ["SOL", "nft"],
        "language": "en",
    }


def _reddit_payload(timestamp: int) -> dict[str, object]:
    return {
        "id": "t3_xyz321",
        "title": "ETH whales scoop up more coins",
        "url": "https://www.reddit.com/r/ethfinance/comments/xyz321/eth_whales_scoop_up_more_coins/?utm_medium=web2x",
        "selftext": "<div>Traders discuss ETH and BTC accumulation.</div>",
        "created_utc": timestamp,
        "language": "en",
        "tickers": ["eth", "btc"],
    }


def test_coindesk_source_filters_out_of_window_articles() -> None:
    inside = _coindesk_payload("2024-05-01T16:34:56+00:00")
    outside = _coindesk_payload("2024-05-01T12:00:00+00:00")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/content/v2/headlines"
        assert request.headers.get("x-api-key") == "token"
        return httpx.Response(200, json={"data": {"items": [inside, outside]}})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(
        transport=transport, base_url="https://production.api.coindesk.com"
    )

    source = CoinDeskContentSource(api_key="token", client=client)
    start = dt.datetime(2024, 5, 1, 16, 0, tzinfo=dt.UTC)
    end = dt.datetime(2024, 5, 1, 18, 0, tzinfo=dt.UTC)

    articles = list(source.fetch(start, end))

    assert len(articles) == 1
    assert articles[0].source == "coindesk"
    assert articles[0].url == "https://www.coindesk.com/markets/bitcoin-rally/"


def test_cointelegraph_source_returns_recent_articles() -> None:
    payload = _cointelegraph_payload("2024-05-02 18:05:00+03:00")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/content/articles"
        return httpx.Response(200, json={"results": [payload]})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://cointelegraph.com")

    source = CoinTelegraphContentSource(client=client)
    start = dt.datetime(2024, 5, 2, 12, 0, tzinfo=dt.UTC)
    end = dt.datetime(2024, 5, 2, 18, 30, tzinfo=dt.UTC)

    articles = list(source.fetch(start, end))

    assert len(articles) == 1
    assert articles[0].source == "cointelegraph"
    assert articles[0].coins == ["SOL"]


def test_reddit_source_fetches_using_oauth_token() -> None:
    token_calls: list[httpx.Request] = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_calls.append(request)
        assert request.method == "POST"
        assert request.url.path == "/api/v1/access_token"
        assert request.headers.get("Authorization", "").startswith("Basic ")
        return httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})

    api_payload = _reddit_payload(1_714_459_545)

    def api_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/r/ethfinance/new"
        assert request.headers.get("Authorization") == "bearer abc"
        data = {"data": {"children": [{"data": api_payload}]}}
        return httpx.Response(200, json=data)

    token_client = httpx.Client(
        transport=httpx.MockTransport(token_handler), base_url="https://www.reddit.com"
    )
    api_client = httpx.Client(
        transport=httpx.MockTransport(api_handler), base_url="https://oauth.reddit.com"
    )

    source = RedditContentSource(
        client_id="client",
        client_secret="secret",
        token_client=token_client,
        api_client=api_client,
        subreddits=["ethfinance"],
    )

    start = dt.datetime(2024, 4, 30, 6, 0, tzinfo=dt.UTC)
    end = start + dt.timedelta(hours=4)

    articles = list(source.fetch(start, end))

    assert len(articles) == 1
    assert token_calls  # token was requested
    assert articles[0].source == "reddit"
    assert articles[0].coins == ["BTC", "ETH"]


def test_default_content_sources_requires_credentials() -> None:
    with pytest.raises(SourceFactoryError):
        default_content_sources(adapters=["coindesk"], env={})

    with pytest.raises(SourceFactoryError):
        default_content_sources(
            adapters=["reddit"], env={"CONTENT_REDDIT_CLIENT_ID": "x"}
        )
