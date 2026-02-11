# Architecture

## Pipeline Overview

The organizer runs as a 6-phase pipeline in a single Python process inside a Docker container.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. DB Init  │───▶│  2. Scan FS  │───▶│  3. AI (DMR) │
│  + Migrate   │    │  rglob+stat  │    │  (if needed) │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                    ┌──────────────┐    ┌───────▼──────┐
                    │  5. Dedup    │◀───│  4. Merge    │
                    │  SHA-256+SQL │    │  Move+Rename │
                    └──────┬───────┘    └──────────────┘
                           │
                    ┌──────▼───────┐
                    │  6. Cleanup  │
                    │  Empty dirs  │
                    └──────────────┘
```

## SQLite Schema

All persistent state lives in `config/library.db` (WAL mode for crash safety).

### `files` table
Every media file in the library. Hash is `NULL` until computed (lazy hashing).

```sql
CREATE TABLE files (
    path     TEXT PRIMARY KEY,  -- Absolute path on disk
    hash     TEXT,              -- SHA-256 hex digest (NULL = needs hashing)
    mtime    REAL NOT NULL,     -- Last modification time (from stat)
    size     INTEGER NOT NULL,  -- File size in bytes
    creator  TEXT,              -- Derived from path (top-level folder name)
    filetype TEXT,              -- 'pic', 'video', or 'other'
    scan_id  INTEGER NOT NULL   -- Which scan indexed this file
);
```

Hash invalidation: when a file's mtime or size changes, its hash is set to `NULL`, forcing a rehash on the next dedup pass.

### `creator_mappings` table
AI-derived folder-to-creator mappings, cached across runs.

```sql
CREATE TABLE creator_mappings (
    folder_name  TEXT PRIMARY KEY,  -- Original folder name on disk
    creator_name TEXT               -- Normalized creator (NULL = container folder)
);
```

### `scan_meta` table
Metadata for each pipeline run.

```sql
CREATE TABLE scan_meta (
    scan_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    file_count  INTEGER,
    total_bytes INTEGER
);
```

## Docker Model Runner Integration

The AI component uses Docker Model Runner (DMR), which exposes an OpenAI-compatible API:

- **Inside container:** `http://model-runner.docker.internal/engines/v1/`
- **From host:** `http://localhost:12434/engines/v1/`

The default model is `ai/qwen3-vl` (vision-capable, but used text-only here).

API flow:
1. `GET /engines/v1/models` — verify model is loaded
2. `POST /engines/v1/chat/completions` — send folder names, receive JSON mapping

The AI is only called for folders not already in `creator_mappings`. Once identified, the mapping is saved and never queried again.

## Volume Mounts

```yaml
volumes:
  - ${MEDIA_PATH}:/media      # The media library (read-write)
  - ./config:/app/config       # SQLite database (persistent)
  - ./logs:/app/logs           # Log files (persistent)
```

## Deduplication Strategy

1. **Incremental hashing:** Only files with `hash IS NULL` are hashed (new or modified files)
2. **8-thread parallel hashing:** Uses `ThreadPoolExecutor` for I/O-bound SHA-256
3. **SQL-based duplicate detection:** Finds groups with `COUNT(*) > 1` per hash, keeps lowest `rowid`
4. **Atomic cleanup:** Deletes file from disk, then removes DB row in batch

## File Naming Convention

All files are renamed during merge:
- Pictures: `{creator}_pic_{NNN}.{ext}` into `{creator}/Pics/`
- Videos: `{creator}_vid_{NNN}.{ext}` into `{creator}/Video/`

Numbering continues from the highest existing number in the target directory.
