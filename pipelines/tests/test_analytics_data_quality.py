from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from great_expectations.checkpoint import SimpleCheckpoint
from great_expectations.core.batch import RuntimeBatchRequest
from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.core.yaml_handler import YAMLHandler
from great_expectations.data_context import BaseDataContext
from great_expectations.data_context.types.base import (
    DataContextConfig,
    FilesystemStoreBackendDefaults,
)

from pipelines.tests import get_analytics_fixture_path

pytest.importorskip("great_expectations")


def _build_context(tmp_path: Path) -> BaseDataContext:
    store_defaults = FilesystemStoreBackendDefaults(root_directory=str(tmp_path))
    config = DataContextConfig(
        datasources={
            "analytics_runtime": {
                "class_name": "Datasource",
                "execution_engine": {"class_name": "PandasExecutionEngine"},
                "data_connectors": {
                    "runtime": {
                        "class_name": "RuntimeDataConnector",
                        "batch_identifiers": ["default_identifier_name"],
                    }
                },
            }
        },
        expectations_store_name="expectations_store",
        validations_store_name="validations_store",
        evaluation_parameter_store_name="evaluation_parameter_store",
        checkpoint_store_name="checkpoint_store",
        store_backend_defaults=store_defaults,
        data_docs_sites={},
        anonymous_usage_statistics={"enabled": False},
    )
    return BaseDataContext(project_config=config)


def test_analytics_fixture_passes_great_expectations(tmp_path: Path) -> None:
    csv_path = get_analytics_fixture_path("csv")
    suite_path = Path(__file__).parent / "data_quality" / "analytics_suite.yml"

    df = pd.read_csv(csv_path)

    context = _build_context(tmp_path)
    suite_dict = YAMLHandler().load(suite_path.read_text())
    suite = ExpectationSuite(**suite_dict)
    context.add_or_update_expectation_suite(expectation_suite=suite)

    batch_request = RuntimeBatchRequest(
        datasource_name="analytics_runtime",
        data_connector_name="runtime",
        data_asset_name="btc_eth_hourly_analytics",
        runtime_parameters={"batch_data": df},
        batch_identifiers={"default_identifier_name": "fixture"},
    )

    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite.expectation_suite_name,
    )

    checkpoint = SimpleCheckpoint(
        name="analytics_fixture_checkpoint",
        data_context=context,
        validations=[
            {
                "batch_request": batch_request,
                "expectation_suite_name": suite.expectation_suite_name,
            }
        ],
    )

    result = checkpoint.run()
    assert result.success is True
    assert validator.active_batch_definition.batch_identifiers == {
        "default_identifier_name": "fixture"
    }
