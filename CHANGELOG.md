# Changelog

## [Unreleased]

### Added
- Production-readiness improvements
- Modular Python package structure
- Comprehensive test suite (>80% coverage)
- Type checking with mypy
- Code formatting with black and ruff
- Security hardening (non-root user, input validation)
- Docker health checks
- Retry logic for DMR API

### Fixed
- Bare exception handlers replaced with specific exceptions
- Container security (non-root user)
- Path traversal validation

### Changed
- Refactored 835-line monolithic script into modular package
- Improved error handling and resource management

## [1.0.0] - 2025-02-12

### Added
- Initial release with SQLite backend
- Docker Model Runner integration
- Deduplication with SHA-256
- Automated folder organization
