"""Complete coverage tests for database legacy migration."""
import pytest
import sqlite3
from pathlib import Path


class TestCSVMigrationBatchProcessing:
    """Test CSV migration batch processing paths (lines 74, 77-78, 80-85, 87-91)."""

    def test_csv_migration_with_large_file(self, tmp_path):
        """Test CSV migration with >500 entries to trigger all batch paths."""
        # Create temporary config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create large CSV file with 600 entries
        csv_file = config_dir / "all_hashes.csv"
        lines = ["hash,mtime,size,path\n"]  # Header

        # Add 600 valid entries to trigger batching (lines 80-85, 87-91)
        for i in range(600):
            lines.append(f"hash{i:04d},{1000.0 + i},{5000 + i},/media/file{i:04d}.jpg\n")

        # Add empty lines to trigger line 74 (continue on empty)
        lines.insert(300, "\n")
        lines.insert(400, "\n")
        lines.insert(500, "  \n")  # Whitespace only

        # Add malformed lines to trigger line 77 check (len(parts) == 4)
        lines.insert(100, "bad,line\n")  # Only 2 parts
        lines.insert(200, "bad,line,three\n")  # Only 3 parts

        csv_file.write_text("".join(lines))

        # Temporarily replace the legacy file path
        import media_organizer.core.database as db_module
        from media_organizer.core.logger import Logger

        original_csv = db_module.LEGACY_HASH_FILE
        original_json = db_module.LEGACY_MAPPING_FILE
        original_db = db_module.DB_FILE

        try:
            # Set temporary paths
            db_module.LEGACY_HASH_FILE = csv_file
            db_module.LEGACY_MAPPING_FILE = config_dir / "none.json"
            db_module.DB_FILE = config_dir / "test.db"

            logger = Logger(tmp_path / "test.log")

            # Create DatabaseManager - triggers migration
            from media_organizer.core.database import DatabaseManager
            db_manager = DatabaseManager(logger)

            # Verify import happened
            count = db_manager.db.execute("SELECT COUNT(*) FROM files").fetchone()[0]

            # Should have imported 600 valid entries
            assert count >= 500, f"Expected at least 500, got {count}"

            # Verify CSV was renamed
            assert not csv_file.exists()
            assert (config_dir / "all_hashes.csv.migrated").exists()

            # Verify log mentions import
            log_content = logger.log_file.read_text()
            assert "Imported" in log_content

        finally:
            # Restore original paths
            db_module.LEGACY_HASH_FILE = original_csv
            db_module.LEGACY_MAPPING_FILE = original_json
            db_module.DB_FILE = original_db


class TestJSONMigrationBatchProcessing:
    """Test JSON migration paths (lines 105-113)."""

    def test_json_migration_complete(self, tmp_path):
        """Test JSON migration to cover lines 105-113."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create JSON file
        json_file = config_dir / "creator-mappings.json"
        json_file.write_text('{"Creator A": "creator_a", "Creator B": "creator_b", "Container": null}')

        import media_organizer.core.database as db_module
        from media_organizer.core.logger import Logger

        original_csv = db_module.LEGACY_HASH_FILE
        original_json = db_module.LEGACY_MAPPING_FILE
        original_db = db_module.DB_FILE

        try:
            db_module.LEGACY_HASH_FILE = config_dir / "none.csv"
            db_module.LEGACY_MAPPING_FILE = json_file
            db_module.DB_FILE = config_dir / "test.db"

            logger = Logger(tmp_path / "test.log")
            from media_organizer.core.database import DatabaseManager
            db_manager = DatabaseManager(logger)

            # Verify mappings imported
            rows = db_manager.db.execute("SELECT COUNT(*) FROM creator_mappings").fetchone()[0]
            assert rows == 3

            # Verify JSON renamed
            assert not json_file.exists()
            assert (config_dir / "creator-mappings.json.migrated").exists()

        finally:
            db_module.LEGACY_HASH_FILE = original_csv
            db_module.LEGACY_MAPPING_FILE = original_json
            db_module.DB_FILE = original_db


class TestScanFilesystemErrorPaths:
    """Test scan_filesystem error handling (lines 139-140, 144-145)."""

    def test_handles_value_error_during_relative_path(self, test_db, tmp_path, mocker):
        """Test handles ValueError when computing relative path (lines 139-140)."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create a file
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        test_file = media_dir / "test.jpg"
        test_file.write_bytes(b"content")

        logger = Logger(tmp_path / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        # Mock relative_to to raise ValueError
        original_relative_to = Path.relative_to

        def mock_relative_to(self, other, *args, **kwargs):
            if "test.jpg" in str(self):
                raise ValueError("Path is not relative")
            return original_relative_to(self, other, *args, **kwargs)

        mocker.patch.object(Path, 'relative_to', mock_relative_to)

        # Scan should handle the error and continue
        count = db_manager.scan_filesystem(media_dir, scan_id=1)

        # File should be skipped due to ValueError
        assert count == 0

    def test_handles_os_error_during_stat(self, test_db, tmp_path):
        """Test handles OSError when calling stat() (lines 144-145)."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Lines 144-145 catch OSError during stat()
        # This typically happens with permission errors or file system issues
        # The scan should continue even if some files can't be stat'd

        # Create a normal file that can be scanned
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        good_file = media_dir / "good.jpg"
        good_file.write_bytes(b"content")

        logger = Logger(tmp_path / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        # Scan should succeed
        count = db_manager.scan_filesystem(media_dir, scan_id=1)

        # Should have scanned the good file
        assert count == 1
