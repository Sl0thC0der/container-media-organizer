"""CLI orchestrator for media organization workflow."""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from .config import WORK_DIR, LOG_DIR, DB_FILE
from .core.logger import Logger
from .core.database import DatabaseManager
from .scanner.filesystem import FilesystemScanner
from .ai.dmr_client import DMRClient
from .ai.identifier import CreatorIdentifier
from .organizer.merger import FileMerger
from .organizer.deduplicator import FileDeduplicator
from .organizer.cleanup import FolderCleanup


class MediaOrganizer:
    """Orchestrates the complete media organization workflow."""

    def __init__(self) -> None:
        """Initialize the media organizer."""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file = LOG_DIR / f"organize_{timestamp}.log"
        self.merge_log = LOG_DIR / f"merge_{timestamp}.log"
        self.dedup_log = LOG_DIR / f"dedup_{timestamp}.log"

        self.logger = Logger(log_file)
        self.log_file = log_file

    def run(self) -> int:
        """
        Run the complete organization workflow.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.logger.log("=" * 44, "cyan")
        self.logger.log(" MEDIA LIBRARY ORGANIZATION (DMR + SQLite)", "cyan")
        self.logger.log("=" * 44, "cyan")
        self.logger.log("")

        try:
            # Step 1: Initialize database (auto-migrates legacy CSV/JSON)
            db_manager = DatabaseManager(self.logger)
            self.logger.log(f"[DB] Opened {DB_FILE}", "green")

            # Create a scan record
            db_manager.db.execute(
                "INSERT INTO scan_meta(started_at) VALUES(?)",
                (datetime.now().isoformat(),)
            )
            db_manager.db.commit()
            scan_id = db_manager.db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Step 2: Check Docker Model Runner
            dmr_client = DMRClient(self.logger)
            if not dmr_client.check_connection():
                self.logger.log("", "red")
                self.logger.log("[ERROR] Docker Model Runner not available. Setup:", "red")
                self.logger.log("  1. Enable Docker Model Runner in Docker Desktop settings", "yellow")
                self.logger.log("  2. docker model status", "yellow")
                self.logger.log("  3. docker model pull ai/qwen3-vl", "yellow")
                return 1

            # Step 3: Load creator mappings from DB
            creator_id = CreatorIdentifier(db_manager.db, dmr_client, self.logger)
            creator_mappings = creator_id.load_mappings()
            self.logger.log(f"[CACHE] Loaded {len(creator_mappings)} creator mappings", "green")

            # Step 4: Scan filesystem (single rglob pass)
            self.logger.log("")
            scanner = FilesystemScanner(db_manager, self.logger)
            scanner.scan(WORK_DIR, scan_id)

            # Step 5: "Before" stats from DB (instant, no filesystem access)
            self.logger.log("")
            before_stats = db_manager.get_stats_from_db(scan_id)
            self.logger.log("[BEFORE] Current state:", "yellow")
            for stat in before_stats:
                self.logger.log(stat)
            self.logger.log("")

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
                        self.logger.log(f"[KNOWN] {folder.name} -> {creator_mappings[folder.name]}", "green")
                    else:
                        ambiguous_folders.append(folder)
                        self.logger.log(f"[UNKNOWN] {folder.name} - needs AI identification", "yellow")

            # Step 6.5: Handle container folders
            expanded_folders = []
            for scattered in scattered_folders:
                if scattered['creator'] is None or scattered['creator'] == "":
                    self.logger.log(f"[CONTAINER] {scattered['name']} is a container, expanding subfolders...", "yellow")

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
                        self.logger.log(f"  Found: {subfolder.name} -> {creator_name}", "green")
                else:
                    expanded_folders.append(scattered)

            scattered_folders = expanded_folders

            # Step 7: AI decision (only if needed)
            if ambiguous_folders:
                self.logger.log("")
                self.logger.log(f"[AI] Identifying {len(ambiguous_folders)} ambiguous folders...", "cyan")

                new_mappings = creator_id.identify_creators(ambiguous_folders, creator_mappings)
                self.logger.log(f"[AI] Identified {len(new_mappings)} creators", "green")

                for folder in ambiguous_folders:
                    if folder.name in new_mappings and new_mappings[folder.name]:
                        scattered_folders.append({
                            'path': folder,
                            'name': folder.name,
                            'creator': new_mappings[folder.name]
                        })
                        self.logger.log(f"  {folder.name} -> {new_mappings[folder.name]}", "green")

                for key, value in new_mappings.items():
                    creator_mappings[key] = value

                creator_id.save_mappings(creator_mappings)
                self.logger.log("[CACHE] Saved mappings to DB", "green")
            else:
                self.logger.log("[SKIP] No ambiguous folders, AI not needed!", "green")

            # Step 8: Merge scattered content
            merge_happened = False
            if scattered_folders:
                self.logger.log("")
                self.logger.log(f"[MERGE] Processing {len(scattered_folders)} scattered folders...", "cyan")
                merger = FileMerger(self.logger)
                merger.merge_scattered_content(scattered_folders, self.merge_log)
                merge_happened = True
            else:
                self.logger.log("[SKIP] No scattered content to merge", "green")

            # Step 9: Re-scan after merge (only if merge happened)
            if merge_happened:
                self.logger.log("")
                scanner.scan(WORK_DIR, scan_id)

            # Step 10+11: Hash new/changed files + find & remove duplicates
            self.logger.log("")
            deduplicator = FileDeduplicator(db_manager.db, self.logger)
            dup_count, dup_size = deduplicator.deduplicate_files(self.dedup_log)

            # Step 12: Cleanup empty folders
            self.logger.log("")
            cleanup = FolderCleanup(self.logger)
            cleanup.remove_empty_folders(WORK_DIR)

            # Step 13: Purge stale DB rows (files from previous scans that no longer exist)
            stale = db_manager.db.execute("DELETE FROM files WHERE scan_id != ?", (scan_id,)).rowcount
            db_manager.db.commit()
            if stale:
                self.logger.log(f"[DB] Purged {stale} stale entries from previous scans", "green")

            # Step 14: "After" stats from DB (instant)
            self.logger.log("")
            self.logger.log("[AFTER] Final state:", "yellow")
            after_stats = db_manager.get_stats_from_db(scan_id)
            for stat in after_stats:
                self.logger.log(stat)

            # Finalize scan record
            db_manager.db.execute(
                "UPDATE scan_meta SET finished_at=? WHERE scan_id=?",
                (datetime.now().isoformat(), scan_id)
            )
            db_manager.db.commit()

            self.logger.log("")
            self.logger.log("=" * 44, "cyan")
            self.logger.log(f" Finished: {datetime.now()}", "cyan")
            self.logger.log("=" * 44, "cyan")
            self.logger.log("")
            self.logger.log("Logs:", "white")
            self.logger.log(f"  Main: {self.log_file}", "gray")
            self.logger.log(f"  Merge: {self.merge_log}", "gray")
            self.logger.log(f"  Dedup: {self.dedup_log}", "gray")

            # Close database connection
            db_manager.close()

            return 0

        except KeyboardInterrupt:
            print()
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"\033[93m{timestamp} [CANCELLED] Organization stopped by user\033[0m")
            return 130
        except Exception as e:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"\033[91m{timestamp} [ERROR] Unexpected error: {e}\033[0m")
            import traceback
            traceback.print_exc()
            return 1


def main() -> int:
    """Main entry point for CLI."""
    organizer = MediaOrganizer()
    return organizer.run()


if __name__ == "__main__":
    sys.exit(main())
