# RAGTrader Pipelines

This package contains the batch and streaming data jobs that power
RAGTrader. Subsequent issues will add Coinbase ingestion, news scraping,
and analytics computations. The scaffolding here provides a registry and
quality gates for future work.

## Development

```bash
pip install -e .[dev]
pytest
```
