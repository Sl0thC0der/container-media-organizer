#!/usr/bin/env python3
"""
Media Library Organization with Docker Model Runner
6-phase pipeline using SQLite for all persistent storage.
Replaces CSV hash cache and JSON creator mappings with a single library.db.
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import requests
import shutil
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

# ============================================
# CONFIGURATION
# ============================================

WORK_DIR = Path(os.getenv("WORK_DIR", "/media"))
CONFIG_DIR = Path(__file__).parent.parent / "config"
LOG_DIR = Path(__file__).parent.parent / "logs"
DB_FILE = CONFIG_DIR / "library.db"

# Legacy files (for migration)
LEGACY_MAPPING_FILE = CONFIG_DIR / "creator-mappings.json"
LEGACY_HASH_FILE = CONFIG_DIR / "all_hashes.csv"

# Docker Model Runner API (OpenAI-compatible)
DMR_URL = os.getenv("DMR_URL", "http://model-runner.docker.internal")
DMR_MODEL = os.getenv("DMR_MODEL", "ai/qwen3-vl")

# File type definitions
PIC_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.wmv', '.mpg', '.mpeg', '.webm', '.flv'}
ALL_MEDIA_EXTENSIONS = PIC_EXTENSIONS | VIDEO_EXTENSIONS

# Ensure directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================
# LOGGING
# ============================================

class Logger:
    """Dual-output logger: writes to file and colored console."""

    COLORS = {
        'cyan': '\033[96m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'gray': '\033[90m',
        'white': '\033[97m',
        'reset': '\033[0m',
    }

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str, color: Optional[str] = None):
        timestamp = datetime.now().strftime('%H:%M:%S')
        line = f"{timestamp} {msg}"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        if color and color in self.COLORS:
            print(f"{self.COLORS[color]}{line}{self.COLORS['reset']}")
        else:
            print(line)


# ============================================
# SQLITE DATABASE
# ============================================

def init_database(logger: Logger) -> sqlite3.Connection:
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
        logger.log(f"[MIGRATE] Importing {LEGACY_HASH_FILE.name} into SQLite...", "yellow")
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
                    if len(batch) >= 500:
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
            logger.log(f"[MIGRATE] Imported {imported} hashes, renamed to {migrated_path.name}", "green")
        except Exception as e:
            logger.log(f"[MIGRATE] CSV import failed: {e}", "red")

    # Migrate legacy JSON creator mappings
    if LEGACY_MAPPING_FILE.exists():
        logger.log(f"[MIGRATE] Importing {LEGACY_MAPPING_FILE.name} into SQLite...", "yellow")
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
            logger.log(f"[MIGRATE] Imported {len(batch)} mappings, renamed to {migrated_path.name}", "green")
        except Exception as e:
            logger.log(f"[MIGRATE] JSON import failed: {e}", "red")

    return db


def scan_filesystem(db: sqlite3.Connection, work_dir: Path, scan_id: int, logger: Logger) -> int:
    """Single rglob walk: stat once per file, UPSERT into DB in batches."""
    logger.log("[SCAN] Walking filesystem (single pass)...", "cyan")
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

        if len(batch) >= 500:
            _upsert_batch(db, batch)
            batch.clear()

    if batch:
        _upsert_batch(db, batch)

    db.commit()
    elapsed = time.time() - start
    logger.log(f"[SCAN] Indexed {file_count} files ({total_bytes / (1024**3):.2f} GB) in {elapsed:.1f}s", "green")

    # Update scan_meta
    db.execute(
        "UPDATE scan_meta SET file_count=?, total_bytes=? WHERE scan_id=?",
        (file_count, total_bytes, scan_id)
    )
    db.commit()

    return file_count


def _upsert_batch(db: sqlite3.Connection, batch: list):
    """Batch UPSERT: insert or update files, invalidate hash if mtime/size changed."""
    db.executemany("""
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


def get_stats_from_db(db: sqlite3.Connection, scan_id: int, logger: Logger) -> List[str]:
    """Get file statistics purely from the database — no filesystem access."""
    stats = []

    rows = db.execute(
        "SELECT creator, COUNT(*), SUM(size) FROM files WHERE scan_id=? AND creator IS NOT NULL GROUP BY creator ORDER BY creator",
        (scan_id,)
    ).fetchall()

    for creator, count, total_size in rows:
        size_mb = (total_size or 0) / (1024 * 1024)
        stats.append(f"  {creator}: {count} files, {size_mb:.1f} MB")

    row = db.execute(
        "SELECT COUNT(*), SUM(size) FROM files WHERE scan_id=?",
        (scan_id,)
    ).fetchone()
    total_count = row[0] or 0
    total_gb = (row[1] or 0) / (1024 ** 3)
    stats.append("  ---")
    stats.append(f"  TOTAL: {total_count} files, {total_gb:.2f} GB")

    return stats


# ============================================
# CREATOR MAPPINGS (DB-backed)
# ============================================

def load_creator_mappings(db: sqlite3.Connection) -> Dict[str, Optional[str]]:
    """Load creator mappings from the database."""
    rows = db.execute("SELECT folder_name, creator_name FROM creator_mappings").fetchall()
    return {folder: creator for folder, creator in rows}


def save_creator_mappings(db: sqlite3.Connection, mappings: Dict[str, Optional[str]]):
    """Save creator mappings to the database (upsert)."""
    db.executemany(
        "INSERT INTO creator_mappings(folder_name, creator_name) VALUES(?,?) "
        "ON CONFLICT(folder_name) DO UPDATE SET creator_name=excluded.creator_name",
        list(mappings.items())
    )
    db.commit()


# ============================================
# DOCKER MODEL RUNNER API
# ============================================

def check_dmr_connection(logger: Logger) -> bool:
    """Check if Docker Model Runner is available and has the required model."""
    try:
        response = requests.get(f"{DMR_URL}/engines/v1/models", timeout=5)
        if response.status_code == 200:
            models = response.json().get('data', [])
            model_ids = [m.get('id', '') for m in models]

            if any(DMR_MODEL in mid for mid in model_ids):
                logger.log(f"[DMR] Connected - using {DMR_MODEL}", "green")
                return True
            else:
                logger.log(f"[DMR] Model {DMR_MODEL} not found. Available: {model_ids}", "yellow")
                logger.log(f"[DMR] Pull model: docker model pull {DMR_MODEL}", "yellow")
                return False
        else:
            logger.log(f"[DMR] API returned {response.status_code}", "red")
            return False
    except requests.exceptions.RequestException as e:
        logger.log(f"[ERROR] Docker Model Runner not available: {e}", "red")
        logger.log("[DMR] Check status: docker model status", "yellow")
        logger.log(f"[DMR] Pull model: docker model pull {DMR_MODEL}", "yellow")
        return False


def call_dmr_api(prompt: str, logger: Logger) -> Optional[str]:
    """Call Docker Model Runner API with a text prompt (OpenAI-compatible)."""
    try:
        payload = {
            "model": DMR_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        logger.log(f"[DMR] Sending request to {DMR_URL}/engines/v1/chat/completions...", "cyan")
        start_time = time.time()

        response = requests.post(
            f"{DMR_URL}/engines/v1/chat/completions",
            json=payload,
            timeout=120
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content'].strip()
            logger.log(f"[DMR] Response received in {elapsed:.1f} seconds", "green")
            return answer
        else:
            logger.log(f"[ERROR] DMR API error: {response.status_code} - {response.text}", "red")
            return None

    except requests.exceptions.Timeout:
        logger.log("[ERROR] DMR request timed out after 120 seconds", "red")
        return None
    except Exception as e:
        logger.log(f"[ERROR] DMR API call failed: {e}", "red")
        return None


# ============================================
# AI CREATOR IDENTIFICATION
# ============================================

def identify_creators_with_ai(folders: List[Path], mappings: Dict[str, Optional[str]], logger: Logger) -> Dict[str, Optional[str]]:
    """Use Docker Model Runner to identify creator names from ambiguous folders."""
    folder_list = []
    for folder in folders:
        subfolders = [d.name for d in folder.iterdir() if d.is_dir()][:5]
        folder_list.append(f"- {folder.name} (contains: {', '.join(subfolders)})")

    known_creators = {v for v in mappings.values() if v and v != ""}

    prompt = f"""Identify which creators these folders belong to. Return ONLY a JSON object mapping folder names to creator names.

Known creators: {', '.join(sorted(known_creators))}

Folders:
{chr(10).join(folder_list)}

Rules:
- If a folder contains subfolders for a creator, the creator name is the subfolder name
- If a folder has a date prefix like "2026-01-02 CreatorName - ...", extract just the creator name
- Use lowercase with underscores for creator names (e.g., "fanny_targioni_tozzetti")
- Return format: {{"folder_name": "creator_name"}}
- For container folders like "Various Files", return null

Return ONLY the JSON object, no explanation.

Example: {{"Various Files": null, "2026-01-02 Avery - Bon Voyage": "avery"}}"""

    response = call_dmr_api(prompt, logger)

    if not response:
        logger.log("[ERROR] AI call failed, using empty mappings", "red")
        return {}

    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            new_mappings = json.loads(json_str)
            logger.log(f"[AI] Identified {len(new_mappings)} folders", "green")
            return new_mappings
        else:
            logger.log(f"[ERROR] No JSON found in response: {response[:200]}", "red")
            return {}
    except json.JSONDecodeError as e:
        logger.log(f"[ERROR] Failed to parse AI response: {e}", "red")
        logger.log(f"[DEBUG] Response was: {response[:200]}...", "yellow")
        return {}


# ============================================
# FILE OPERATIONS
# ============================================

def get_highest_number(directory: Path, pattern: str) -> int:
    """Find the highest number in filenames matching pattern."""
    max_num = 0
    if not directory.exists():
        return 0

    for file in directory.iterdir():
        if file.is_file():
            match = re.match(pattern, file.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

    return max_num


def merge_scattered_content(scattered_folders: List[Dict], logger: Logger, merge_log: Path):
    """Merge scattered content into proper creator folders."""
    for scattered in scattered_folders:
        creator_name = scattered['creator']
        source_path = scattered['path']

        creator_dir = WORK_DIR / creator_name
        pics_dir = creator_dir / "Pics"
        video_dir = creator_dir / "Video"

        if not creator_dir.exists():
            creator_dir.mkdir(parents=True)
            logger.log(f"  Created {creator_name}/", "green")

        pics_dir.mkdir(exist_ok=True)
        video_dir.mkdir(exist_ok=True)

        pic_pattern = rf"{re.escape(creator_name)}_pic_(\d+)\."
        vid_pattern = rf"{re.escape(creator_name)}_vid_(\d+)\."

        max_pic = get_highest_number(pics_dir, pic_pattern)
        max_vid = get_highest_number(video_dir, vid_pattern)

        pic_num = max_pic
        vid_num = max_vid

        for file in source_path.rglob('*'):
            if not file.is_file():
                continue

            ext = file.suffix.lower()

            if ext in PIC_EXTENSIONS:
                pic_num += 1
                new_name = f"{creator_name}_pic_{pic_num:03d}{ext}"
                dest_path = pics_dir / new_name
                shutil.move(str(file), str(dest_path))

                with open(merge_log, 'a', encoding='utf-8') as f:
                    f.write(f"{file} -> {dest_path}\n")

            elif ext in VIDEO_EXTENSIONS:
                vid_num += 1
                new_name = f"{creator_name}_vid_{vid_num:03d}{ext}"
                dest_path = video_dir / new_name
                shutil.move(str(file), str(dest_path))

                with open(merge_log, 'a', encoding='utf-8') as f:
                    f.write(f"{file} -> {dest_path}\n")

        logger.log(f"  Merged {creator_name}: {pic_num - max_pic} pics, {vid_num - max_vid} videos", "green")


# ============================================
# DEDUPLICATION (DB-backed, incremental)
# ============================================

def _hash_file(file_path: str) -> Tuple[str, Optional[str]]:
    """Hash a single file, returns (path_str, hash_hex)."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return file_path, sha256.hexdigest()
    except Exception:
        return file_path, None


def deduplicate_files(db: sqlite3.Connection, logger: Logger, dedup_log: Path) -> Tuple[int, int]:
    """Incremental DB-backed deduplication: hash only what's needed, find dupes via SQL."""

    # Step 1: Find files that need hashing (hash IS NULL)
    unhashed = db.execute("SELECT path FROM files WHERE hash IS NULL").fetchall()
    to_hash = [row[0] for row in unhashed]

    if to_hash:
        logger.log(f"[DEDUP] Hashing {len(to_hash)} new/changed files with 8 threads...", "cyan")
        hashed = 0
        hash_batch = []

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_hash_file, p): p for p in to_hash}
            for future in as_completed(futures):
                path_str, file_hash = future.result()
                hashed += 1
                if hashed % 500 == 0:
                    logger.log(f"[DEDUP] Hashed {hashed}/{len(to_hash)} files...", "cyan")

                if file_hash is None:
                    logger.log(f"[WARN] Could not hash: {path_str}", "yellow")
                    continue

                hash_batch.append((file_hash, path_str))
                if len(hash_batch) >= 500:
                    db.executemany("UPDATE files SET hash=? WHERE path=?", hash_batch)
                    db.commit()
                    hash_batch.clear()

        if hash_batch:
            db.executemany("UPDATE files SET hash=? WHERE path=?", hash_batch)
            db.commit()

        logger.log(f"[DEDUP] Hashed {hashed} files", "green")
    else:
        logger.log("[DEDUP] All files already hashed (cache hit)", "green")

    # Step 2: Find duplicates via SQL — keep the row with the lowest rowid per hash
    duplicates = db.execute("""
        SELECT f.path, f.hash, f.size
        FROM files f
        WHERE f.hash IS NOT NULL
          AND f.hash IN (SELECT hash FROM files WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*) > 1)
          AND f.rowid NOT IN (SELECT MIN(rowid) FROM files WHERE hash IS NOT NULL GROUP BY hash HAVING COUNT(*) > 1)
    """).fetchall()

    saved_space = 0
    removed = 0

    if duplicates:
        logger.log(f"[DEDUP] Found {len(duplicates)} duplicates, removing...", "yellow")

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
            except Exception as e:
                logger.log(f"[ERROR] Could not remove {path_str}: {e}", "red")

        if delete_batch:
            db.executemany("DELETE FROM files WHERE path=?", delete_batch)
            db.commit()

        saved_gb = saved_space / (1024 ** 3)
        logger.log(f"[DEDUP] Removed {removed} duplicates, freed {saved_gb:.2f} GB", "green")
    else:
        logger.log("[DEDUP] No duplicates found (library clean)", "green")

    return removed, saved_space


# ============================================
# CLEANUP
# ============================================

def remove_empty_folders(work_dir: Path, logger: Logger) -> int:
    """Remove empty folders in a single bottom-up pass (O(n), not O(n²))."""
    logger.log("[CLEANUP] Removing empty folders...", "cyan")

    # Collect all directories, sort deepest-first by path depth
    all_dirs = []
    for entry in work_dir.rglob('*'):
        if entry.is_dir() and '.claude' not in str(entry):
            all_dirs.append(entry)

    all_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    removed = 0
    for folder in all_dirs:
        try:
            if not any(folder.iterdir()):
                folder.rmdir()
                logger.log(f"  Removed: {folder.name}", "yellow")
                removed += 1
        except Exception:
            pass

    if removed == 0:
        logger.log("[CLEANUP] No empty folders found", "green")
    else:
        logger.log(f"[CLEANUP] Removed {removed} empty folders", "green")

    return removed


# ============================================
# MAIN WORKFLOW
# ============================================

def main():
    """Main organization workflow: DB init -> scan -> AI (DMR) -> merge -> dedup -> cleanup"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = LOG_DIR / f"organize_{timestamp}.log"
    merge_log = LOG_DIR / f"merge_{timestamp}.log"
    dedup_log = LOG_DIR / f"dedup_{timestamp}.log"

    logger = Logger(log_file)

    logger.log("=" * 44, "cyan")
    logger.log(" MEDIA LIBRARY ORGANIZATION (DMR + SQLite)", "cyan")
    logger.log("=" * 44, "cyan")
    logger.log("")

    # Step 1: Initialize database (auto-migrates legacy CSV/JSON)
    db = init_database(logger)
    logger.log(f"[DB] Opened {DB_FILE}", "green")

    # Create a scan record
    db.execute(
        "INSERT INTO scan_meta(started_at) VALUES(?)",
        (datetime.now().isoformat(),)
    )
    db.commit()
    scan_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        # Step 2: Check Docker Model Runner
        if not check_dmr_connection(logger):
            logger.log("", "red")
            logger.log("[ERROR] Docker Model Runner not available. Setup:", "red")
            logger.log("  1. Enable Docker Model Runner in Docker Desktop settings", "yellow")
            logger.log("  2. docker model status", "yellow")
            logger.log(f"  3. docker model pull {DMR_MODEL}", "yellow")
            sys.exit(1)

        # Step 3: Load creator mappings from DB
        creator_mappings = load_creator_mappings(db)
        logger.log(f"[CACHE] Loaded {len(creator_mappings)} creator mappings", "green")

        # Step 4: Scan filesystem (single rglob pass)
        logger.log("")
        scan_filesystem(db, WORK_DIR, scan_id, logger)

        # Step 5: "Before" stats from DB (instant, no filesystem access)
        logger.log("")
        before_stats = get_stats_from_db(db, scan_id, logger)
        logger.log("[BEFORE] Current state:", "yellow")
        for stat in before_stats:
            logger.log(stat)
        logger.log("")

        # Step 6: Find scattered/ambiguous folders
        scattered_folders = []
        ambiguous_folders = []

        for folder in WORK_DIR.iterdir():
            if not folder.is_dir():
                continue
            if folder.name == '.claude' or folder.name.startswith('['):
                continue

            has_pics = (folder / "Pics").exists()
            has_video = (folder / "Video").exists()

            if not (has_pics or has_video):
                if folder.name in creator_mappings:
                    scattered_folders.append({
                        'path': folder,
                        'name': folder.name,
                        'creator': creator_mappings[folder.name]
                    })
                    logger.log(f"[KNOWN] {folder.name} -> {creator_mappings[folder.name]}", "green")
                else:
                    ambiguous_folders.append(folder)
                    logger.log(f"[UNKNOWN] {folder.name} - needs AI identification", "yellow")

        # Step 6.5: Handle container folders
        expanded_folders = []
        for scattered in scattered_folders:
            if scattered['creator'] is None or scattered['creator'] == "":
                logger.log(f"[CONTAINER] {scattered['name']} is a container, expanding subfolders...", "yellow")

                for subfolder in scattered['path'].iterdir():
                    if not subfolder.is_dir():
                        continue

                    creator_name = subfolder.name.lower()
                    creator_name = re.sub(r'\s+', '_', creator_name)
                    creator_name = re.sub(r'[^a-z0-9_]', '', creator_name)

                    expanded_folders.append({
                        'path': subfolder,
                        'name': subfolder.name,
                        'creator': creator_name
                    })
                    logger.log(f"  Found: {subfolder.name} -> {creator_name}", "green")
            else:
                expanded_folders.append(scattered)

        scattered_folders = expanded_folders

        # Step 7: AI decision (only if needed)
        if ambiguous_folders:
            logger.log("")
            logger.log(f"[AI] Identifying {len(ambiguous_folders)} ambiguous folders...", "cyan")

            new_mappings = identify_creators_with_ai(ambiguous_folders, creator_mappings, logger)
            logger.log(f"[AI] Identified {len(new_mappings)} creators", "green")

            for folder in ambiguous_folders:
                if folder.name in new_mappings and new_mappings[folder.name]:
                    scattered_folders.append({
                        'path': folder,
                        'name': folder.name,
                        'creator': new_mappings[folder.name]
                    })
                    logger.log(f"  {folder.name} -> {new_mappings[folder.name]}", "green")

            for key, value in new_mappings.items():
                creator_mappings[key] = value

            save_creator_mappings(db, creator_mappings)
            logger.log("[CACHE] Saved mappings to DB", "green")
        else:
            logger.log("[SKIP] No ambiguous folders, AI not needed!", "green")

        # Step 8: Merge scattered content
        merge_happened = False
        if scattered_folders:
            logger.log("")
            logger.log(f"[MERGE] Processing {len(scattered_folders)} scattered folders...", "cyan")
            merge_scattered_content(scattered_folders, logger, merge_log)
            merge_happened = True
        else:
            logger.log("[SKIP] No scattered content to merge", "green")

        # Step 9: Re-scan after merge (only if merge happened)
        if merge_happened:
            logger.log("")
            scan_filesystem(db, WORK_DIR, scan_id, logger)

        # Step 10+11: Hash new/changed files + find & remove duplicates
        logger.log("")
        dup_count, dup_size = deduplicate_files(db, logger, dedup_log)

        # Step 12: Cleanup empty folders
        logger.log("")
        remove_empty_folders(WORK_DIR, logger)

        # Step 13: Purge stale DB rows (files from previous scans that no longer exist)
        stale = db.execute("DELETE FROM files WHERE scan_id != ?", (scan_id,)).rowcount
        db.commit()
        if stale:
            logger.log(f"[DB] Purged {stale} stale entries from previous scans", "green")

        # Step 14: "After" stats from DB (instant)
        logger.log("")
        logger.log("[AFTER] Final state:", "yellow")
        after_stats = get_stats_from_db(db, scan_id, logger)
        for stat in after_stats:
            logger.log(stat)

        # Finalize scan record
        db.execute(
            "UPDATE scan_meta SET finished_at=? WHERE scan_id=?",
            (datetime.now().isoformat(), scan_id)
        )
        db.commit()

        logger.log("")
        logger.log("=" * 44, "cyan")
        logger.log(f" Finished: {datetime.now()}", "cyan")
        logger.log("=" * 44, "cyan")
        logger.log("")
        logger.log("Logs:", "white")
        logger.log(f"  Main: {log_file}", "gray")
        logger.log(f"  Merge: {merge_log}", "gray")
        logger.log(f"  Dedup: {dedup_log}", "gray")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\033[93m{timestamp} [CANCELLED] Organization stopped by user\033[0m")
        sys.exit(130)
    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\033[91m{timestamp} [ERROR] Unexpected error: {e}\033[0m")
        import traceback
        traceback.print_exc()
        sys.exit(1)
