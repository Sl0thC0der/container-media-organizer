# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A containerized media library organizer. Uses Docker Model Runner (AI) for creator identification and SQLite for all persistent storage. Organizes 15,000+ media files by creator with standardized folder structure and naming conventions.

## Commands

### "Organize my media library"
Run the full pipeline (merge, dedupe, cleanup). Requires Docker Desktop with Model Runner enabled and `ai/qwen3-vl` pulled.

```bash
# Set media library path first
export MEDIA_PATH=/path/to/media/library   # Linux/Mac
set MEDIA_PATH=C:\path\to\library          # Windows

# Run
docker-compose up --abort-on-container-exit media-organizer
```

Launchers: `run.bat` (Windows), `run.sh` (Linux/Mac), `run.ps1` (PowerShell)

### Build only
```bash
docker-compose build media-organizer
```

## Architecture

- **`scripts/organize.py`** — Single entry point. Pipeline: DB init -> scan -> AI decision (DMR, only for unknown folders) -> merge -> dedup -> cleanup.
- **`config/library.db`** — SQLite database (WAL mode). Stores file hashes, creator mappings, and scan metadata.
- **`logs/`** — Timestamped logs: `organize_*.log`, `merge_*.log`, `dedup_*.log`.

AI backend: Docker Model Runner (OpenAI-compatible API at `model-runner.docker.internal` inside containers, `localhost:12434` from host). Model defaults to `ai/qwen3-vl`. Override with `DMR_URL` and `DMR_MODEL` env vars.

Path resolution: inside the container, `WORK_DIR=/media` points to the library root (mounted via docker-compose). Outside Docker, set `WORK_DIR` explicitly.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_PATH` | *required* | Host path to the media library (used in docker-compose volume mount) |
| `WORK_DIR` | `/media` | Library root inside the container |
| `DMR_URL` | `http://model-runner.docker.internal` | Docker Model Runner API URL |
| `DMR_MODEL` | `ai/qwen3-vl` | AI model for creator identification |

## SQLite Schema

```sql
-- File index with incremental hashing
CREATE TABLE files (
    path TEXT PRIMARY KEY, hash TEXT, mtime REAL, size INTEGER,
    creator TEXT, filetype TEXT, scan_id INTEGER
);

-- AI-derived folder-to-creator mappings (cached across runs)
CREATE TABLE creator_mappings (
    folder_name TEXT PRIMARY KEY, creator_name TEXT
);

-- Run metadata
CREATE TABLE scan_meta (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT, finished_at TEXT, file_count INTEGER, total_bytes INTEGER
);
```

## Conventions

### Target folder structure (in the media library)
```
creator_name/
├── Pics/    # All images
└── Video/   # All videos
```

### File naming
- Pictures: `creator_pic_001.jpg`, `creator_pic_002.png`, ...
- Videos: `creator_vid_001.mp4`, `creator_vid_002.mkv`, ...
- Zero-padded 3+ digits, numbering continues from highest existing.

### File types
- **Pictures:** .jpg .jpeg .png .gif .webp .bmp .tiff
- **Videos:** .mp4 .mov .m4v .avi .mkv .wmv .mpg .mpeg .webm .flv

### Creator names
Lowercase with underscores (e.g., `fanny_targioni_tozzetti`).

## Special Rules
- Folders starting with `[` are external sources — skip during organization
- "Various Files" and garbled-name folders are containers — expand subfolders
- Deduplication uses SHA-256; keep first occurrence, delete duplicates
- Empty folders are deleted after merge
