"""Tests for FileDeduplicator."""
import pytest
import hashlib
from pathlib import Path
from media_organizer.organizer.deduplicator import FileDeduplicator
from media_organizer.core.logger import Logger


class TestHashFile:
    """Test _hash_file() method."""

    def test_hashes_file_correctly(self, tmp_path):
        """Test SHA-256 hash is computed correctly."""
        test_file = tmp_path / "test.jpg"
        content = b"test file content"
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(None, logger)

        path, file_hash = deduplicator._hash_file(str(test_file))
        assert file_hash == expected_hash

    def test_handles_missing_file(self, tmp_path):
        """Test returns None for non-existent file."""
        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(None, logger)

        path, file_hash = deduplicator._hash_file(str(tmp_path / "missing.jpg"))
        assert file_hash is None

    def test_handles_permission_error(self, tmp_path, mocker):
        """Test returns None when file cannot be read."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"content")

        mocker.patch('builtins.open', side_effect=PermissionError)

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(None, logger)

        path, file_hash = deduplicator._hash_file(str(test_file))
        assert file_hash is None

    def test_handles_large_file(self, tmp_path):
        """Test handles files larger than chunk size."""
        test_file = tmp_path / "large.jpg"
        # Create file larger than HASH_CHUNK_SIZE (65536)
        content = b"x" * 100000
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(None, logger)

        path, file_hash = deduplicator._hash_file(str(test_file))
        assert file_hash == expected_hash
        assert len(file_hash) == 64  # SHA-256 hex length

    def test_returns_path_with_hash(self, tmp_path):
        """Test returns tuple of (path, hash)."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"content")

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(None, logger)

        path, file_hash = deduplicator._hash_file(str(test_file))
        assert path == str(test_file)
        assert file_hash is not None


class TestDeduplicateFiles:
    """Test deduplicate_files() method."""

    def test_no_files_to_hash(self, test_db, tmp_path):
        """Test handles database with all files already hashed."""
        # Insert file with hash
        test_db.execute(
            "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
            ('/test/file.jpg', 'abc123', 1000.0, 5000, 'creator', 'pic', 1)
        )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        assert removed == 0
        assert saved == 0

    def test_hashes_unhashed_files(self, test_db, tmp_path, media_with_duplicates):
        """Test hashes files with NULL hash."""
        # Insert files without hashes
        for file in media_with_duplicates.rglob('*.jpg'):
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(file), None, 1000.0, file.stat().st_size, 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Check all files now have hashes
        unhashed = test_db.execute("SELECT COUNT(*) FROM files WHERE hash IS NULL").fetchone()[0]
        assert unhashed == 0

    def test_identifies_and_removes_duplicates(self, test_db, tmp_path):
        """Test finds and removes duplicate files."""
        # Create actual duplicate files
        creator1 = tmp_path / "creator1"
        creator1.mkdir()

        duplicate_content = b"duplicate"
        files = [
            creator1 / "dup1.jpg",
            creator1 / "dup2.jpg",
            creator1 / "dup3.jpg"
        ]
        for f in files:
            f.write_bytes(duplicate_content)

        # Insert into database
        for f in files:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, len(duplicate_content), 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Should remove 2 duplicates, keep 1
        assert removed == 2
        assert saved == len(duplicate_content) * 2

        # Check only 1 file remains in DB
        remaining = test_db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert remaining == 1

        # Check only 1 file exists on disk
        remaining_files = list(creator1.glob('*.jpg'))
        assert len(remaining_files) == 1

    def test_writes_dedup_log(self, test_db, tmp_path):
        """Test deleted files are logged."""
        creator1 = tmp_path / "creator1"
        creator1.mkdir()

        files = [creator1 / "dup1.jpg", creator1 / "dup2.jpg"]
        for f in files:
            f.write_bytes(b"dup")

        for f in files:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 3, 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)
        dedup_log = tmp_path / "dedup.log"

        deduplicator.deduplicate_files(dedup_log)

        assert dedup_log.exists()
        log_content = dedup_log.read_text()
        assert "dup" in log_content

    def test_keeps_first_occurrence_by_rowid(self, test_db, tmp_path):
        """Test keeps the file with lowest rowid when duplicates found."""
        creator1 = tmp_path / "creator1"
        creator1.mkdir()

        # Create files with specific order
        first = creator1 / "first.jpg"
        second = creator1 / "second.jpg"
        third = creator1 / "third.jpg"

        for f in [first, second, third]:
            f.write_bytes(b"duplicate")

        # Insert in order to control rowid
        for f in [first, second, third]:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 9, 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # First file should still exist
        assert first.exists()
        # Others should be deleted
        assert not second.exists()
        assert not third.exists()

    def test_handles_file_already_deleted(self, test_db, tmp_path):
        """Test handles FileNotFoundError gracefully."""
        creator1 = tmp_path / "creator1"
        creator1.mkdir()

        # Create one file
        existing = creator1 / "existing.jpg"
        existing.write_bytes(b"dup")

        # Insert two files with same hash, but second doesn't exist
        missing = creator1 / "missing.jpg"
        for f in [existing, missing]:
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), 'samehash', 1000.0, 3, 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        # Should not crash
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # Both should be removed from DB even though one was already missing
        remaining = test_db.execute("SELECT COUNT(*) FROM files WHERE hash='samehash'").fetchone()[0]
        assert remaining == 1

    def test_batch_processing(self, test_db, tmp_path, mocker):
        """Test processes hashes in batches."""
        # Mock BATCH_SIZE to test batching
        mocker.patch('media_organizer.organizer.deduplicator.BATCH_SIZE', 2)

        creator1 = tmp_path / "creator1"
        creator1.mkdir()

        # Create multiple files
        for i in range(5):
            f = creator1 / f"file{i}.jpg"
            f.write_bytes(f"content{i}".encode())
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 8, 'creator1', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # All should be hashed
        unhashed = test_db.execute("SELECT COUNT(*) FROM files WHERE hash IS NULL").fetchone()[0]
        assert unhashed == 0
