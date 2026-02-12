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

### Build and rebuild
```bash
# Build fresh image
docker-compose build media-organizer

# Force rebuild (no cache)
docker-compose build --no-cache media-organizer
```

### Scheduled runs (cron)
```bash
# Start daily 2 AM job in background
docker-compose --profile cron up -d

# Stop cron job
docker-compose --profile cron down
```

### Direct SQLite access
```bash
# View all creator mappings
sqlite3 config/library.db "SELECT * FROM creator_mappings ORDER BY folder_name;"

# View file statistics by creator
sqlite3 config/library.db "SELECT creator, COUNT(*), SUM(size)/1048576 as mb FROM files GROUP BY creator;"

# View recent scans
sqlite3 config/library.db "SELECT * FROM scan_meta ORDER BY scan_id DESC LIMIT 5;"

# Fix incorrect mapping
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name='correct_name' WHERE folder_name='Wrong Name';"

# Mark folder as container (to expand subfolders)
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name=NULL WHERE folder_name='Various Files';"
```

### Debug and testing
```bash
# Run organize.py locally (outside Docker, for debugging)
export WORK_DIR=/path/to/media/library
python3 scripts/organize.py

# View logs in real-time
tail -f logs/organize_*.log

# Check Docker Model Runner status
docker model status
docker model list
curl http://localhost:12434/engines/v1/models
```

## Architecture

### Core Components

- **`scripts/organize.py`** (835 lines) — Single entry point. Six-phase pipeline runs in one process:
  1. **DB Init** — Opens SQLite, auto-migrates legacy CSV/JSON (only on first run)
  2. **Scan** — Single `rglob()` walk with batch UPSERT (500 files/batch)
  3. **AI Decision** — DMR API call for unknown folders (cached forever)
  4. **Merge** — Move & rename files into `creator/{Pics,Video}/` structure
  5. **Dedup** — Incremental SHA-256 hashing (8 threads), SQL duplicate detection
  6. **Cleanup** — Bottom-up empty folder removal, DB purge of stale entries

- **`config/library.db`** — SQLite database (WAL mode, ~50KB for 17k files). Three tables: `files`, `creator_mappings`, `scan_meta`. Hash invalidation on mtime/size change enables incremental deduplication.

- **`logs/`** — Timestamped logs with dual output (file + colored console): `organize_*.log`, `merge_*.log`, `dedup_*.log`.

### AI Backend

Docker Model Runner (DMR) is a Docker Desktop feature, not a separate container. Exposes OpenAI-compatible API:
- **Inside container:** `http://model-runner.docker.internal/engines/v1/`
- **From host:** `http://localhost:12434/engines/v1/`
- **Model:** `ai/qwen3-vl` (default, override with `DMR_MODEL`)

AI is only called for folders not in `creator_mappings` table. Once identified, mapping is cached permanently unless manually edited.

### Path Handling

- **Inside container:** `WORK_DIR=/media` (docker-compose volume mount from `$MEDIA_PATH`)
- **Outside container:** Set `WORK_DIR` to the actual library path for local testing
- Config and logs are always relative to script location (`Path(__file__).parent.parent`)

### Performance Notes

- **Scanning:** ~25s for 17k files (single rglob pass, stat once per file)
- **AI:** 5-15s (only if new folders found)
- **Hashing:** Incremental - only new/changed files (8 parallel threads)
- **Memory:** Container limited to 8GB, reserves 2GB (see docker-compose.yml)

## Environment Variables

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `MEDIA_PATH` | *none* | Host path to the media library (docker-compose mount) | Yes (Docker only) |
| `WORK_DIR` | `/media` | Library root path (inside container or local) | No |
| `DMR_URL` | `http://model-runner.docker.internal` | Docker Model Runner API endpoint | No |
| `DMR_MODEL` | `ai/qwen3-vl` | AI model for creator identification | No |

**Important:** `MEDIA_PATH` is only used by docker-compose for volume mounting. Inside the container and for local runs, the script uses `WORK_DIR`.

## SQLite Schema

```sql
-- File index with incremental hashing
CREATE TABLE files (
    path TEXT PRIMARY KEY,      -- Absolute path on disk
    hash TEXT,                  -- SHA-256 (NULL = needs hashing)
    mtime REAL,                 -- Modification time (invalidates hash)
    size INTEGER,               -- File size (invalidates hash)
    creator TEXT,               -- Top-level folder name
    filetype TEXT,              -- 'pic', 'video', 'other'
    scan_id INTEGER             -- Which scan indexed this file
);
CREATE INDEX idx_files_hash ON files(hash);
CREATE INDEX idx_files_creator ON files(creator);

-- AI-derived folder-to-creator mappings (cached across runs)
CREATE TABLE creator_mappings (
    folder_name TEXT PRIMARY KEY,  -- Original folder name
    creator_name TEXT              -- Normalized creator (NULL = container)
);

-- Run metadata
CREATE TABLE scan_meta (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,            -- ISO timestamp
    finished_at TEXT,           -- ISO timestamp
    file_count INTEGER,         -- Total files indexed
    total_bytes INTEGER         -- Total size in bytes
);
```

## Troubleshooting

### Pipeline fails immediately
**Problem:** `MEDIA_PATH` not set or invalid
```bash
# Check .env file or set manually
echo $MEDIA_PATH  # Linux/Mac
echo %MEDIA_PATH%  # Windows CMD

# Create .env file (gitignored)
echo "MEDIA_PATH=/path/to/library" > .env
```

### DMR connection errors
**Problem:** Docker Model Runner not available or model not pulled
```bash
# Check status
docker model status

# List available models
docker model list

# Pull required model (may take 5-10 minutes)
docker model pull ai/qwen3-vl

# Test API from host
curl http://localhost:12434/engines/v1/models
```

### Wrong creator identification
**Problem:** AI misidentified a folder
```bash
# View current mapping
sqlite3 config/library.db "SELECT * FROM creator_mappings WHERE folder_name='Wrong Folder';"

# Fix mapping
sqlite3 config/library.db "UPDATE creator_mappings SET creator_name='correct_name' WHERE folder_name='Wrong Folder';"

# Re-run organizer (will use corrected mapping)
docker-compose up media-organizer
```

### Files not being merged
**Problem:** Folder already has Pics/Video subdirectories (considered organized)
- The organizer only merges folders that lack `Pics/` or `Video/` subdirectories
- If a folder already has these, it's considered properly organized and skipped

### Deduplication not finding duplicates
**Problem:** Hash cache stale or files changed
```bash
# View hashed vs unhashed files
sqlite3 config/library.db "SELECT COUNT(*) as unhashed FROM files WHERE hash IS NULL;"
sqlite3 config/library.db "SELECT COUNT(*) as hashed FROM files WHERE hash IS NOT NULL;"

# Force rehash all files (WARNING: slow on large libraries)
sqlite3 config/library.db "UPDATE files SET hash=NULL;"
docker-compose up media-organizer
```

### Database corruption
**Problem:** WAL file out of sync or disk full
```bash
# Recover from WAL
sqlite3 config/library.db "PRAGMA wal_checkpoint(FULL);"

# Check integrity
sqlite3 config/library.db "PRAGMA integrity_check;"

# Last resort: rebuild from scratch (deletes all mappings!)
mv config/library.db config/library.db.backup
docker-compose up media-organizer
```

### Memory issues (OOM)
**Problem:** Container runs out of memory on very large libraries
```yaml
# Adjust in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 16G  # Increase from 8G
```
Or reduce batch sizes in organize.py (lines 223, 544).

### Files missing after run
**Problem:** Check dedup log for deleted duplicates
```bash
# View what was deleted
cat logs/dedup_*.log

# See duplicate groups before deletion
sqlite3 config/library.db "SELECT hash, COUNT(*) as count FROM files GROUP BY hash HAVING count > 1;"
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
- Deduplication uses SHA-256; keep first occurrence (lowest rowid), delete duplicates
- Empty folders are deleted after merge (bottom-up traversal)
- `.claude/` directories are always skipped during scanning

## Key Code Locations

When modifying the organizer, these are the critical sections in `scripts/organize.py`:

- **Lines 23-46:** Configuration (paths, extensions, DMR settings)
- **Lines 53-81:** Logger class (dual file+console output)
- **Lines 87-175:** Database init and legacy migration (CSV/JSON import)
- **Lines 178-261:** Filesystem scanning and batch UPSERT with hash invalidation
- **Lines 288-306:** Creator mappings (DB-backed cache)
- **Lines 312-373:** Docker Model Runner API client
- **Lines 379-427:** AI creator identification with JSON parsing
- **Lines 433-501:** File merging and renaming logic
- **Lines 507-597:** Incremental deduplication (hash + SQL + cleanup)
- **Lines 604-630:** Empty folder removal (O(n) bottom-up)
- **Lines 637-818:** Main workflow orchestration

## Common Modifications

### Adding new file types
Edit lines 40-42 to add extensions:
```python
PIC_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.wmv', '.mpg', '.mpeg', '.webm', '.flv', '.ts'}
```

### Changing skip patterns
Edit line 196 to modify folder exclusion logic:
```python
if top_folder.startswith('[') or top_folder.startswith('_'):
    continue
```

### Adjusting batch sizes
- Scan batch: line 223 (`if len(batch) >= 500`)
- Hash batch: line 544 (`if len(hash_batch) >= 500`)
- Increase for better throughput, decrease for lower memory usage

### Modifying AI prompt
The creator identification prompt is at lines 388-404. Key sections:
- Known creators context (helps model reuse existing names)
- Extraction rules (dates, underscores, lowercase)
- Expected JSON format

### Changing hash algorithm
Replace SHA-256 with faster algorithm (lines 510-514):
```python
# Replace sha256 with blake2b for 2x speed
hasher = hashlib.blake2b()
```
Note: Changing algorithm invalidates all existing hashes in DB.
