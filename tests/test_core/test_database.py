"""Tests for database module."""

import sqlite3
from pathlib import Path
from media_organizer.core.database import DatabaseManager
from media_organizer.core.logger import Logger


def test_database_init(test_db, tmp_path):
    """Test database initialization creates tables."""
    # Check tables exist
    cursor = test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]

    assert 'files' in tables
    assert 'creator_mappings' in tables
    assert 'scan_meta' in tables


def test_upsert_batch_inserts_new_files(test_db):
    """Test _upsert_batch inserts new files."""
    from media_organizer.core.database import DatabaseManager

    batch = [
        ('/path/to/file1.jpg', 1000.0, 5000, 'creator1', 'pic', 1),
        ('/path/to/file2.mp4', 2000.0, 10000, 'creator1', 'video', 1),
    ]

    # Create a minimal DatabaseManager instance for testing
    log_file = Path('/tmp/test.log')
    logger = Logger(log_file)
    db_manager = DatabaseManager.__new__(DatabaseManager)
    db_manager.logger = logger
    db_manager.db = test_db

    db_manager._upsert_batch(batch)
    test_db.commit()

    # Verify files were inserted
    cursor = test_db.execute("SELECT COUNT(*) FROM files")
    count = cursor.fetchone()[0]
    assert count == 2


def test_get_stats_from_db(test_db):
    """Test statistics retrieval from database."""
    # Insert test data
    test_db.executemany(
        "INSERT INTO files(path, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?)",
        [
            ('/path/file1.jpg', 1000.0, 5000, 'creator1', 'pic', 1),
            ('/path/file2.jpg', 1000.0, 8000, 'creator1', 'pic', 1),
            ('/path/file3.mp4', 1000.0, 15000, 'creator2', 'video', 1),
        ]
    )
    test_db.commit()

    # Create DatabaseManager instance
    log_file = Path('/tmp/test.log')
    logger = Logger(log_file)
    db_manager = DatabaseManager.__new__(DatabaseManager)
    db_manager.logger = logger
    db_manager.db = test_db

    stats = db_manager.get_stats_from_db(scan_id=1)

    assert len(stats) > 0
    assert any('creator1' in s for s in stats)
    assert any('creator2' in s for s in stats)
    assert any('TOTAL' in s for s in stats)
