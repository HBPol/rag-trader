from datetime import UTC

import pandas as pd

from ragtrader_pipelines.analytics_job import _infer_interval


def test_infer_interval_handles_timezone_aware_index() -> None:
    index = pd.date_range("2024-01-01T00:00:00+00:00", periods=3, freq="1h", tz=UTC)
    series = pd.Series([1.0, 2.0, 3.0], index=index)

    result = _infer_interval(series)

    assert result == pd.Timedelta(hours=1)
