from pathlib import Path

import pandas as pd
import pytest

try:
    import great_expectations as gx
    from great_expectations.checkpoint import SimpleCheckpoint
    from great_expectations.core.batch import RuntimeBatchRequest
    from great_expectations.core.expectation_suite import ExpectationSuite
    from great_expectations.core.yaml_handler import YAMLHandler
    from great_expectations.data_context import AbstractDataContext
    from great_expectations.data_context.types.base import (
        DataContextConfig,
        FilesystemStoreBackendDefaults,
    )
except ImportError:  # pragma: no cover - optional dependency
    pytest.skip(
        "great_expectations is required for RAG data-quality tests",
        allow_module_level=True,
    )

from pipelines.tests import get_rag_fixture_path


def _build_context(tmp_path: Path) -> AbstractDataContext:
    store_defaults = FilesystemStoreBackendDefaults(root_directory=str(tmp_path))
    config = DataContextConfig(
        datasources={
            "rag_runtime": {
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
    return gx.get_context(project_config=config, context_root_dir=str(tmp_path))


def test_rag_fixture_passes_great_expectations(tmp_path: Path) -> None:
    csv_path = get_rag_fixture_path("articles_csv")
    suite_path = Path(__file__).parent / "data_quality" / "rag_suite.yml"

    df = pd.read_csv(csv_path)

    context = _build_context(tmp_path)
    suite_dict = YAMLHandler().load(suite_path.read_text())
    suite = ExpectationSuite(**suite_dict)
    context.add_or_update_expectation_suite(expectation_suite=suite)

    batch_request = RuntimeBatchRequest(
        datasource_name="rag_runtime",
        data_connector_name="runtime",
        data_asset_name="rag_articles",
        runtime_parameters={"batch_data": df},
        batch_identifiers={"default_identifier_name": "rag_fixture"},
    )

    validator = context.get_validator(
        batch_request=batch_request, expectation_suite_name=suite.expectation_suite_name
    )

    checkpoint = SimpleCheckpoint(
        name="rag_fixture_checkpoint",
        data_context=context,
    )

    result = checkpoint.run(
        validations=[
            {
                "batch_request": batch_request,
                "expectation_suite_name": suite.expectation_suite_name,
            }
        ]
    )

    assert result.success is True
    assert validator.active_batch_definition.batch_identifiers == {
        "default_identifier_name": "rag_fixture"
    }
