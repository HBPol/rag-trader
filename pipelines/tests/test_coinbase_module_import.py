"""Regression tests for importing the Coinbase module."""

import runpy
import sys
import warnings

import pytest


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_coinbase_module_executes_without_runtime_warnings() -> None:
    module_name = "ragtrader_pipelines.coinbase"
    original_module = sys.modules.get(module_name)
    sys.modules.pop(module_name, None)

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", category=RuntimeWarning)
            runpy.run_module(module_name, alter_sys=True)

        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert runtime_warnings == []
    finally:
        if original_module is not None:
            sys.modules[module_name] = original_module
        else:
            sys.modules.pop(module_name, None)
