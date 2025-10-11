.PHONY: test test-api test-pipelines test-frontend

# Aggregated test entry point for the Python and frontend packages.
test: test-api test-pipelines test-frontend

# Run the API service's pytest suite with coverage gates aligned to CI.
test-api:
	@echo "[api] Running pytest with coverage enforcement"
	@cd api && PYTHONPATH=src pytest --cov=ragtrader_api --cov-report=term --cov-report=xml --cov-fail-under=80

# Run the pipelines package pytest suite with matching coverage enforcement.
test-pipelines:
	@echo "[pipelines] Running pytest with coverage enforcement"
	@cd pipelines && PYTHONPATH=src pytest --cov=ragtrader_pipelines --cov-report=term --cov-report=xml --cov-fail-under=80

# Run the frontend Vitest suite with coverage thresholds configured in vitest.config.ts.
test-frontend:
	@echo "[web] Running Vitest with coverage enforcement"
	@cd web && pnpm test -- --coverage
