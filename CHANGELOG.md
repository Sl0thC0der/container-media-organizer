# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-11

### Added
- Extracted to standalone repository from `.claude/organize/`
- Configurable `MEDIA_PATH` environment variable (replaces hardcoded relative path)
- `.env.example` for configuration
- Architecture documentation in `docs/`
- CI workflow for repository validation

### Changed
- `WORK_DIR` default changed from relative path traversal to `/media` (Docker mount point)
- `docker-compose.yml` uses `${MEDIA_PATH}` instead of `../..` relative volume
- Launcher scripts (`run.bat`, `run.sh`, `run.ps1`) updated for standalone use with `MEDIA_PATH`

## [0.1.0] - 2026-02-07

### Added
- SQLite migration from CSV hash cache and JSON creator mappings
- Single `library.db` for all persistent state (WAL mode)
- Incremental deduplication (hash only new/changed files)
- 6-phase pipeline: DB init, scan, AI decision, merge, dedup, cleanup
- Docker Model Runner integration for AI-powered creator identification
- Multi-threaded SHA-256 hashing (8 threads)
- Bottom-up empty folder removal (O(n))
- Batch UPSERT with hash invalidation on mtime/size change
- Containerized execution via Docker Compose
- Launcher scripts for Windows, Linux/Mac, and PowerShell
