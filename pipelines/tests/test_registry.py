"""Tests for the pipeline registry scaffold."""

import pytest

from ragtrader_pipelines.registry import PipelineRegistry


def sample_pipeline() -> None:  # pragma: no cover - smoke stub
    return None


def test_register_and_retrieve_pipeline() -> None:
    registry = PipelineRegistry()
    registry.register("sample", sample_pipeline)

    assert "sample" in registry
    assert registry.get("sample") is sample_pipeline


def test_registering_same_pipeline_twice_raises() -> None:
    registry = PipelineRegistry()
    registry.register("sample", sample_pipeline)

    with pytest.raises(ValueError):
        registry.register("sample", sample_pipeline)
