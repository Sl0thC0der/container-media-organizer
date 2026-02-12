"""Database management with SQLite."""

import json
import sqlite3
import time
from pathlib import Path
from typing import List

from ..config import (
    DB_FILE,
    LEGACY_HASH_FILE,
    LEGACY_MAPPING_FILE,
    WORK_DIR,
    BATCH_SIZE,
    PIC_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .logger import Logger


class DatabaseManager:
    """Manages SQLite database operations for media library."""

    def __init__(self, logger: Logger) -> None:
        """Initialize database manager."""
        self.logger = logger
        self.db: sqlite3.Connection = self._init_database()

    def _init_database(self) -> sqlite3.Connection:
        """Open/create the SQLite database, run migrations from legacy files."""
        db = sqlite3.connect(str(DB_FILE))
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")

        # Create tables (idempotent)
        db.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                path     TEXT PRIMARY KEY,
                hash     TEXT,
                mtime    REAL NOT NULL,
                size     INTEGER NOT NULL,
                creator  TEXT,
                filetype TEXT,
                scan_id  INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash);
            CREATE INDEX IF NOT EXISTS idx_files_creator ON files(creator);

            CREATE TABLE IF NOT EXISTS creator_mappings (
                folder_name  TEXT PRIMARY KEY,
                creator_name TEXT
            );

            CREATE TABLE IF NOT EXISTS scan_meta (
                scan_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                file_count  INTEGER,
                total_bytes INTEGER
            );
        """)

        # Migrate legacy CSV hash file
        if LEGACY_HASH_FILE.exists():
            self.logger.log(f"[MIGRATE] Importing {LEGACY_HASH_FILE.name} into SQLite...", "yellow")
            imported = 0
            try:
                with open(LEGACY_HASH_FILE, 'r', encoding='utf-8') as f:
                    header = f.readline()
                    batch = []
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(',', 3)
                        if len(parts) == 4:
                            file_hash, mtime, size, path_str = parts
                            batch.append((path_str, file_hash, float(mtime), int(size), 0))
                        if len(batch) >= BATCH_SIZE:
                            db.executemany(
                                "INSERT OR IGNORE INTO files(path, hash, mtime, size, scan_id) VALUES(?,?,?,?,?)",
                                batch
                            )
                            imported += len(batch)
                            batch.clear()
                    if batch:
                        db.executemany(
                            "INSERT OR IGNORE INTO files(path, hash, mtime, size, scan_id) VALUES(?,?,?,?,?)",
                            batch
                        )
                        imported += len(batch)
                db.commit()
                migrated_path = LEGACY_HASH_FILE.with_suffix('.csv.migrated')
                LEGACY_HASH_FILE.rename(migrated_path)
                self.logger.log(f"[MIGRATE] Imported {imported} hashes, renamed to {migrated_path.name}", "green")
            except (IOError, OSError, ValueError, UnicodeDecodeError, sqlite3.Error) as e:
                self.logger.log(f"[MIGRATE] CSV import failed: {e}", "red")

        # Migrate legacy JSON creator mappings
        if LEGACY_MAPPING_FILE.exists():
            self.logger.log(f"[MIGRATE] Importing {LEGACY_MAPPING_FILE.name} into SQLite...", "yellow")
            try:
                with open(LEGACY_MAPPING_FILE, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)
                batch = [(k, v) for k, v in mappings.items()]
                db.executemany(
                    "INSERT OR IGNORE INTO creator_mappings(folder_name, creator_name) VALUES(?,?)",
                    batch
                )
                db.commit()
                migrated_path = LEGACY_MAPPING_FILE.with_suffix('.json.migrated')
                LEGACY_MAPPING_FILE.rename(migrated_path)
                self.logger.log(f"[MIGRATE] Imported {len(batch)} mappings, renamed to {migrated_path.name}", "green")
            except (IOError, OSError, json.JSONDecodeError, sqlite3.Error) as e:
                self.logger.log(f"[MIGRATE] JSON import failed: {e}", "red")

        return db

    def scan_filesystem(self, work_dir: Path, scan_id: int) -> int:
        """Single rglob walk: stat once per file, UPSERT into DB in batches."""
        self.logger.log("[SCAN] Walking filesystem (single pass)...", "cyan")
        start = time.time()
        batch = []
        file_count = 0
        total_bytes = 0

        for entry in work_dir.rglob('*'):
            if not entry.is_file():
                continue
            path_str = str(entry)
            if '.claude' in path_str:
                continue
            # Skip bracket-prefixed folders
            try:
                rel = entry.relative_to(work_dir)
                top_folder = rel.parts[0] if rel.parts else ''
                if top_folder.startswith('['):
                    continue
            except ValueError:
                continue

            try:
                st = entry.stat()
            except OSError:
                continue

            ext = entry.suffix.lower()
            if ext in PIC_EXTENSIONS:
                filetype = 'pic'
            elif ext in VIDEO_EXTENSIONS:
                filetype = 'video'
            else:
                filetype = 'other'

            # Derive creator from path: work_dir / creator_name / ...
            creator = None
            if len(rel.parts) >= 2:
                creator = rel.parts[0]

            batch.append((path_str, st.st_mtime, st.st_size, creator, filetype, scan_id))
            file_count += 1
            total_bytes += st.st_size

            if len(batch) >= BATCH_SIZE:
                self._upsert_batch(batch)
                batch.clear()

        if batch:
            self._upsert_batch(batch)

        self.db.commit()
        elapsed = time.time() - start
        self.logger.log(f"[SCAN] Indexed {file_count} files ({total_bytes / (1024**3):.2f} GB) in {elapsed:.1f}s", "green")

        # Update scan_meta
        self.db.execute(
            "UPDATE scan_meta SET file_count=?, total_bytes=? WHERE scan_id=?",
            (file_count, total_bytes, scan_id)
        )
        self.db.commit()

        return file_count

    def _upsert_batch(self, batch: list) -> None:
        """Batch UPSERT: insert or update files, invalidate hash if mtime/size changed."""
        self.db.executemany("""
            INSERT INTO files(path, mtime, size, creator, filetype, scan_id)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET
                hash = CASE
                    WHEN excluded.mtime != files.mtime OR excluded.size != files.size
                    THEN NULL
                    ELSE files.hash
                END,
                mtime = excluded.mtime,
                size = excluded.size,
                creator = excluded.creator,
                filetype = excluded.filetype,
                scan_id = excluded.scan_id
        """, batch)

    def get_stats_from_db(self, scan_id: int) -> List[str]:
        """Get file statistics purely from the database — no filesystem access."""
        stats = []

        rows = self.db.execute(
            "SELECT creator, COUNT(*), SUM(size) FROM files WHERE scan_id=? AND creator IS NOT NULL GROUP BY creator ORDER BY creator",
            (scan_id,)
        ).fetchall()

        for creator, count, total_size in rows:
            size_mb = (total_size or 0) / (1024 * 1024)
            stats.append(f"  {creator}: {count} files, {size_mb:.1f} MB")

        row = self.db.execute(
            "SELECT COUNT(*), SUM(size) FROM files WHERE scan_id=?",
            (scan_id,)
        ).fetchone()
        total_count = row[0] or 0
        total_gb = (row[1] or 0) / (1024 ** 3)
        stats.append("  ---")
        stats.append(f"  TOTAL: {total_count} files, {total_gb:.2f} GB")

        return stats

    def close(self) -> None:
        """Close database connection."""
        if self.db:
            self.db.close()
