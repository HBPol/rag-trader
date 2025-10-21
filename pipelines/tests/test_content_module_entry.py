"""Tests for the ragtrader_pipelines.content module entry point."""

from __future__ import annotations

import runpy
from unittest import mock

import pytest


def test_module_entry_dispatches_to_main():
    """Running the module should call ``content.main`` and exit with its code."""

    with mock.patch("ragtrader_pipelines.content.main", return_value=0) as patched_main:
        with pytest.raises(SystemExit) as excinfo:
            runpy.run_module("ragtrader_pipelines.content", run_name="__main__")

    patched_main.assert_called_once_with()
    assert excinfo.value.code == 0
