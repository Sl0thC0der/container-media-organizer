"""File deduplication using SHA-256 hashing."""

import hashlib
import sqlite3
from pathlib import Path
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import HASH_CHUNK_SIZE, HASH_WORKERS, BATCH_SIZE
from ..core.logger import Logger


class FileDeduplicator:
    """Deduplicates files using incremental hashing."""

    def __init__(self, db: sqlite3.Connection, logger: Logger) -> None:
        """Initialize file deduplicator."""
        self.db = db
        self.logger = logger

    def _hash_file(self, file_path: str) -> Tuple[str, Optional[str]]:
        """
        Hash a single file using SHA-256.

        Args:
            file_path: Path to file to hash

        Returns:
            Tuple of (path, hash_hex) or (path, None) if hashing failed
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(HASH_CHUNK_SIZE), b''):
                    sha256.update(chunk)
            return file_path, sha256.hexdigest()
        except (IOError, OSError, PermissionError):
            return file_path, None

    def deduplicate_files(self, dedup_log: Path) -> Tuple[int, int]:
        """
        Incremental DB-backed deduplication: hash only what's needed, find dupes via SQL.

        Args:
            dedup_log: Path to log file for deduplication records

        Returns:
            Tuple of (removed_count, saved_bytes)
        """
        # Step 1: Find files that need hashing (hash IS NULL)
        unhashed = self.db.execute("SELECT path FROM files WHERE hash IS NULL").fetchall()
        to_hash = [row[0] for row in unhashed]

        if to_hash:
            self.logger.log(f"[DEDUP] Hashing {len(to_hash)} new/changed files with {HASH_WORKERS} threads...", "cyan")
            hashed = 0
            hash_batch = []

            with ThreadPoolExecutor(max_workers=HASH_WORKERS) as executor:
                futures = {executor.submit(self._hash_file, p): p for p in to_hash}
                for future in as_completed(futures):
                    path_str, file_hash = future.result()
                    hashed += 1
                    if hashed % 500 == 0:
                        self.logger.log(f"[DEDUP] Hashed {hashed}/{len(to_hash)} files...", "cyan")

                    if file_hash is None:
                        self.logger.log(f"[WARN] Could not hash: {path_str}", "yellow")
                        continue

                    hash_batch.append((file_hash, path_str))
                    if len(hash_batch) >= BATCH_SIZE:
                        self.db.executemany("UPDATE files SET hash=? WHERE path=?", hash_batch)
                        self.db.commit()
                        hash_batch.clear()

            if hash_batch:
                self.db.executemany("UPDATE files SET hash=? WHERE path=?", hash_batch)
                self.db.commit()

            self.logger.log(f"[DEDUP] Hashed {hashed} files", "green")
        else:
            self.logger.log("[DEDUP] All files already hashed (cache hit)", "green")

        # Step 2: Find duplicates via SQL — keep the row with the lowest rowid per hash
        duplicates = self.db.execute("""
            SELECT f.path, f.hash, f.size
            FROM files f
            WHERE f.hash IS NOT NULL
              AND f.hash IN (SELECT hash FROM files WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*) > 1)
              AND f.rowid NOT IN (SELECT MIN(rowid) FROM files WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*) > 1)
        """).fetchall()

        saved_space = 0
        removed = 0

        if duplicates:
            self.logger.log(f"[DEDUP] Found {len(duplicates)} duplicates, removing...", "yellow")

            delete_batch = []
            for path_str, file_hash, size in duplicates:
                try:
                    Path(path_str).unlink()
                    saved_space += size
                    removed += 1
                    delete_batch.append((path_str,))

                    with open(dedup_log, 'a', encoding='utf-8') as f:
                        f.write(f"{path_str},{file_hash},{size}\n")
                except FileNotFoundError:
                    delete_batch.append((path_str,))
                except (PermissionError, OSError) as e:
                    self.logger.log(f"[ERROR] Could not remove {path_str}: {e}", "red")

            if delete_batch:
                self.db.executemany("DELETE FROM files WHERE path=?", delete_batch)
                self.db.commit()

            saved_gb = saved_space / (1024 ** 3)
            self.logger.log(f"[DEDUP] Removed {removed} duplicates, freed {saved_gb:.2f} GB", "green")
        else:
            self.logger.log("[DEDUP] No duplicates found (library clean)", "green")

        return removed, saved_space
