# Container Media Organizer

Automated media library organization using Docker Model Runner for AI inference and SQLite for all persistent storage. Organizes 15,000+ files across multiple creators with proper folder structure and naming conventions.

## Overview

A containerized pipeline that scans a media library, identifies creators using AI, merges scattered content into standardized folders, deduplicates files by SHA-256 hash, and cleans up empty directories. All state is persisted in a single SQLite database.

## Prerequisites

- **Docker Desktop** with Model Runner enabled
- AI model pulled: `docker model pull ai/qwen3-vl`

## Quick Start

### Windows
```batch
run.bat
```

### Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

### PowerShell
```powershell
.\run.ps1
```

### Manual
```bash
# Set media library path
export MEDIA_PATH=/path/to/media/library

# One-time run
docker-compose up --abort-on-container-exit media-organizer

# Background scheduled job (daily at 2 AM)
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

## Project Structure

```
container-media-organizer/
├── .github/workflows/validate.yml   # CI validation
├── docs/
│   └── architecture.md              # Pipeline and schema details
├── scripts/
│   └── organize.py                  # Main pipeline script
├── config/
│   └── library.db                   # SQLite database (runtime, gitignored)
├── logs/                            # Timestamped logs (runtime, gitignored)
├── Dockerfile                       # Main container
├── Dockerfile.cron                  # Scheduled container
├── docker-compose.yml               # Orchestration
├── requirements.txt                 # Python dependencies
├── run.bat                          # Windows launcher
├── run.sh                           # Linux/Mac launcher
├── run.ps1                          # PowerShell launcher
├── .env.example                     # Example environment config
├── CLAUDE.md                        # Claude Code instructions
├── CHANGELOG.md                     # Version history
├── LICENSE                          # MIT License
└── README.md                        # This file
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
