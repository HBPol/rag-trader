# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Updated the CoinDesk content source to use the Data API endpoint and accept the
  `CONTENT_COINDESK_API_KEY` environment variable (falling back to the legacy
  RSS keys) for authentication.

## [0.1.0] - 2025-10-??

### Added
- Monorepo scaffold with API, pipelines, and web workspaces, plus shared tooling.
- Database engine helpers, Alembic migrations for instruments/OHLCV tables, and Docker wiring for the API service.
- Coinbase OHLCV ingestion job with CLI wiring, idempotent persistence, and documentation updates.
