"""Tests for the top-level ``ragtrader_pipelines`` package exports.

These tests make sure that the lazy ``__getattr__`` implementation in
``ragtrader_pipelines.__init__`` exposes the expected classes without forcing
the rest of the application to import eagerly.  Only a few representative
objects from each export category need to be checked to cover the different
branches.
"""

import pytest


def test_content_export_is_resolved_from_submodule():
    import ragtrader_pipelines as pkg
    from ragtrader_pipelines.content import ContentAggregator

    # Accessing ``ContentAggregator`` via the package should go through
    # ``__getattr__`` and return the exact same object that lives inside the
    # ``content`` submodule.
    assert pkg.ContentAggregator is ContentAggregator


def test_coinbase_export_is_resolved_from_submodule():
    import ragtrader_pipelines as pkg
    from ragtrader_pipelines.coinbase import CoinbaseClient

    assert pkg.CoinbaseClient is CoinbaseClient


def test_dir_lists_known_exports():
    import ragtrader_pipelines as pkg

    available = dir(pkg)
    assert "ContentAggregator" in available
    assert "CoinbaseClient" in available
    assert "SentimentClassifier" in available
    assert "rolling_pearson" in available


def test_getattr_raises_for_unknown_symbol():
    import ragtrader_pipelines as pkg

    with pytest.raises(AttributeError):
        _ = pkg.does_not_exist  # noqa: B018 - accessing attribute for test only
