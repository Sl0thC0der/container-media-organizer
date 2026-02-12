# Container Media Organizer

Automated media library organization using Docker Model Runner for AI inference and SQLite for all persistent storage. Organizes 15,000+ files across multiple creators with proper folder structure and naming conventions.

## Overview

A containerized pipeline that scans a media library, identifies creators using AI, merges scattered content into standardized folders, deduplicates files by SHA-256 hash, and cleans up empty directories. All state is persisted in a single SQLite database.

## Prerequisites

- **Docker Desktop** with Model Runner enabled
- AI model pulled: `docker model pull ai/qwen3-vl`

## Quick Start

```bash
# Set your media library path
export MEDIA_PATH=/path/to/media/library   # Linux/macOS
set MEDIA_PATH=C:\path\to\library          # Windows CMD
$env:MEDIA_PATH="C:\path\to\library"       # Windows PowerShell

# Or create a .env file (recommended)
echo "MEDIA_PATH=/path/to/media/library" > .env

# Run organization pipeline
docker-compose up --abort-on-container-exit media-organizer

# Or run in background with scheduled daily runs (2 AM)
docker-compose --profile cron up -d
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_PATH` | *required* | Host path to your media library |
| `WORK_DIR` | `/media` | Library root inside the container |
| `DMR_URL` | `http://model-runner.docker.internal` | Docker Model Runner API URL |
| `DMR_MODEL` | `ai/qwen3-vl` | AI model for creator identification |

Create a `.env` file (gitignored) for convenience:
```env
MEDIA_PATH=C:\Users\YourName\Media
```

### Creator Mappings

Creator mappings are cached in `config/library.db`. To view or edit:

```bash
# View all mappings
sqlite3 config/library.db "SELECT * FROM creator_mappings;"

# Fix a mapping
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name='correct_name' WHERE folder_name='Some Folder';"

# Skip a folder (set to NULL)
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name=NULL WHERE folder_name='Skip This';"
```

## Pipeline

### Phase 1: Database Init (instant)
- Opens/creates `config/library.db` (SQLite, WAL mode)
- Auto-migrates legacy `all_hashes.csv` and `creator-mappings.json` on first run

### Phase 2: Filesystem Scan (~25s for 17k files)
- Single `rglob('*')` pass, `stat()` once per file
- UPSERT into `files` table in batches of 500
- Invalidates hash if mtime/size changed (forces rehash)

### Phase 3: AI Decision (5-15s, only if needed)
- Sends unknown folder names to Docker Model Runner (qwen3-vl)
- Saves decisions to DB for future runs
- **Skipped entirely if all folders are cached**

### Phase 4: Merge (10-30s)
- Moves and renames files into `creator/Pics/` and `creator/Video/`
- Continues numbering from highest existing
- Re-scans filesystem after merge to update DB

### Phase 5: Deduplication (incremental)
- Hashes only new/changed files (8 threads)
- Finds duplicates via SQL query
- Deletes duplicates from disk and DB

### Phase 6: Cleanup (<1s)
- Bottom-up empty folder removal (O(n))
- Purges stale DB entries from previous scans

## Troubleshooting

### DMR not available
```bash
docker model status
docker model pull ai/qwen3-vl
curl http://localhost:12434/engines/v1/models
```

### Wrong creator identification
Fix mappings in SQLite, then re-run:
```bash
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name='correct_name' WHERE folder_name='Wrong Folder';"
```

### Skip AI entirely
Pre-populate all creator mappings:
```bash
sqlite3 config/library.db "INSERT OR REPLACE INTO creator_mappings VALUES('folder_name', 'creator_name');"
```

## Documentation

- **README.md** (this file) - Quick start and user guide
- **CLAUDE.md** - Detailed architecture and development guide for Claude Code
- **archive/** - Historical workflow logs and migrated legacy files

## Project Structure

```
container-media-organizer/
├── .github/workflows/validate.yml   # CI/CD pipeline
├── src/media_organizer/             # Main package (modular structure)
│   ├── __init__.py
│   ├── config.py                    # Configuration and constants
│   ├── cli.py                       # CLI orchestrator
│   ├── models/                      # Data models and types
│   │   ├── __init__.py
│   │   └── types.py
│   ├── core/                        # Core functionality
│   │   ├── __init__.py
│   │   ├── logger.py                # Dual-output logging
│   │   └── database.py              # SQLite database manager
│   ├── scanner/                     # Filesystem scanning
│   │   ├── __init__.py
│   │   └── filesystem.py
│   ├── ai/                          # AI-powered identification
│   │   ├── __init__.py
│   │   ├── dmr_client.py            # Docker Model Runner client
│   │   └── identifier.py            # Creator identification
│   └── organizer/                   # File organization
│       ├── __init__.py
│       ├── merger.py                # File merging
│       ├── deduplicator.py          # SHA-256 deduplication
│       └── cleanup.py               # Empty folder removal
├── scripts/
│   └── organize.py                  # Backward compatibility wrapper
├── tests/                           # Test suite (>80% coverage)
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_config.py
│   ├── test_core/
│   ├── test_scanner/
│   ├── test_ai/
│   ├── test_organizer/
│   └── test_integration.py
├── config/
│   └── library.db                   # SQLite database (runtime, gitignored)
├── logs/                            # Timestamped logs (runtime, gitignored)
├── Dockerfile                       # Main container
├── Dockerfile.cron                  # Scheduled container
├── docker-compose.yml               # Orchestration
├── pyproject.toml                   # Package configuration
├── setup.py                         # Package installation
├── requirements.txt                 # Python dependencies
├── .yamllint.yml                    # YAML linting config
├── .gitattributes                   # Line ending configuration
├── CHANGELOG.md                     # Version history
├── CLAUDE.md                        # Claude Code instructions
├── LICENSE                          # MIT License
└── README.md                        # This file
```

## Development

### Setup

Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest` for testing
- `pytest-cov` for coverage reporting
- `pytest-mock` for mocking
- `mypy` for type checking
- `black` for code formatting
- `ruff` for linting
- `types-requests` for type stubs

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py -v

# Run integration tests (requires Docker Model Runner)
pytest tests/test_integration.py -v
```

### Code Quality

```bash
# Type checking
mypy src/ --strict

# Code formatting
black src/ tests/

# Linting
ruff check src/ tests/

# Fix auto-fixable linting issues
ruff check src/ tests/ --fix
```

### Package Structure

The project follows a modular package structure:

- **config.py**: All configuration, environment variables, and constants
- **core/**: Foundational components (logging, database)
- **models/**: Data classes and type definitions
- **scanner/**: Filesystem indexing
- **ai/**: Docker Model Runner integration and creator identification
- **organizer/**: File operations (merge, dedupe, cleanup)
- **cli.py**: Main workflow orchestrator

### Building and Testing Docker Image

```bash
# Build image
docker-compose build media-organizer

# Test import works
docker-compose run --rm media-organizer python3 -c "import media_organizer; print('OK')"

# Run full pipeline
docker-compose up media-organizer
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
