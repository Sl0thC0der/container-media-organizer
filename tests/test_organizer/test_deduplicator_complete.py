"""Complete coverage tests for FileDeduplicator edge cases."""
import pytest
from pathlib import Path
from media_organizer.organizer.deduplicator import FileDeduplicator
from media_organizer.core.logger import Logger


class TestDeduplicatorProgressLogging:
    """Test progress logging during hashing."""

    def test_logs_progress_every_500_files(self, test_db, tmp_path):
        """Test progress is logged every 500 files."""
        # Create 501 files to trigger progress logging
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        for i in range(501):
            f = media_dir / f"file{i:04d}.jpg"
            f.write_bytes(b"content" + str(i).encode())
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 7, 'creator', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        # Hash files - should log progress at 500
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Verify progress was logged
        log_content = logger.log_file.read_text()
        assert "500/" in log_content


class TestDeduplicatorDeletionErrors:
    """Test handling of file deletion errors."""

    def test_handles_permission_error_on_delete(self, test_db, tmp_path, mocker):
        """Test handles PermissionError when deleting duplicate."""
        # Create duplicate files
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        duplicate_content = b"duplicate"
        f1 = media_dir / "dup1.jpg"
        f2 = media_dir / "dup2.jpg"
        f1.write_bytes(duplicate_content)
        f2.write_bytes(duplicate_content)

        # Insert with same hash (simulate already hashed)
        dup_hash = "abc123"
        for f in [f1, f2]:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), dup_hash, 1000.0, len(duplicate_content), 'creator', 'pic', 1)
            )
        test_db.commit()

        # Mock os.remove to raise PermissionError for one file
        original_remove = Path.unlink
        def mock_unlink(self, *args, **kwargs):
            if "dup2" in str(self):
                raise PermissionError("Access denied")
            return original_remove(self, *args, **kwargs)

        mocker.patch.object(Path, 'unlink', mock_unlink)

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        # Should handle error gracefully
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Check error was logged
        log_content = logger.log_file.read_text()
        assert "ERROR" in log_content or "Could not remove" in log_content

    def test_handles_os_error_on_delete(self, test_db, tmp_path, mocker):
        """Test handles OSError when deleting duplicate."""
        # Create duplicate files
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        duplicate_content = b"duplicate"
        f1 = media_dir / "dup1.jpg"
        f2 = media_dir / "dup2.jpg"
        f1.write_bytes(duplicate_content)
        f2.write_bytes(duplicate_content)

        # Insert with same hash
        dup_hash = "xyz789"
        for f in [f1, f2]:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), dup_hash, 1000.0, len(duplicate_content), 'creator', 'pic', 1)
            )
        test_db.commit()

        # Mock os.remove to raise OSError
        original_remove = Path.unlink
        def mock_unlink(self, *args, **kwargs):
            if "dup2" in str(self):
                raise OSError("Disk error")
            return original_remove(self, *args, **kwargs)

        mocker.patch.object(Path, 'unlink', mock_unlink)

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        # Should handle error gracefully
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Check error was logged
        log_content = logger.log_file.read_text()
        assert "ERROR" in log_content or "Could not remove" in log_content
