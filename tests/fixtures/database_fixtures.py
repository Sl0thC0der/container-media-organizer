"""Database test fixtures and helpers."""
import sqlite3
from pathlib import Path
from typing import List
import pytest


@pytest.fixture
def populated_db(test_db):
    """Database with realistic test data."""
    test_db.executemany(
        "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
        [
            ('/media/creator1/pic1.jpg', 'abc123', 1000.0, 5000, 'creator1', 'pic', 1),
            ('/media/creator1/pic2.jpg', 'def456', 1001.0, 6000, 'creator1', 'pic', 1),
            ('/media/creator2/vid1.mp4', 'ghi789', 1002.0, 50000, 'creator2', 'video', 1),
        ]
    )
    test_db.executemany(
        "INSERT INTO creator_mappings(folder_name, creator_name) VALUES(?,?)",
        [
            ('Creator 1 Photos', 'creator1'),
            ('Creator 2 Videos', 'creator2'),
            ('Various Files', None),  # Container folder
        ]
    )
    test_db.commit()
    return test_db


@pytest.fixture
def db_with_duplicates(test_db):
    """Database with duplicate files (same hash)."""
    duplicate_hash = 'duplicate123'
    test_db.executemany(
        "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
        [
            ('/media/creator1/dup1.jpg', duplicate_hash, 1000.0, 5000, 'creator1', 'pic', 1),
            ('/media/creator1/dup2.jpg', duplicate_hash, 1000.0, 5000, 'creator1', 'pic', 1),
            ('/media/creator2/dup3.jpg', duplicate_hash, 1000.0, 5000, 'creator2', 'pic', 1),
        ]
    )
    test_db.commit()
    return test_db


@pytest.fixture
def db_with_unhashed_files(test_db):
    """Database with files needing hashing (NULL hashes)."""
    test_db.executemany(
        "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
        [
            ('/media/file1.jpg', None, 1000.0, 5000, 'creator1', 'pic', 1),
            ('/media/file2.jpg', None, 1001.0, 6000, 'creator1', 'pic', 1),
            ('/media/file3.mp4', 'existing', 1002.0, 7000, 'creator2', 'video', 1),
        ]
    )
    test_db.commit()
    return test_db


def assert_file_count(db: sqlite3.Connection, expected: int):
    """Helper to assert file count in database."""
    count = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    assert count == expected, f"Expected {expected} files, got {count}"


def assert_creator_mapping(db: sqlite3.Connection, folder: str, expected_creator: str):
    """Helper to assert creator mapping exists."""
    result = db.execute(
        "SELECT creator_name FROM creator_mappings WHERE folder_name=?",
        (folder,)
    ).fetchone()
    assert result is not None, f"No mapping for folder '{folder}'"
    assert result[0] == expected_creator, f"Expected '{expected_creator}', got '{result[0]}'"


def get_duplicate_hashes(db: sqlite3.Connection) -> List[str]:
    """Get list of hashes that have duplicates."""
    rows = db.execute("""
        SELECT hash FROM files
        WHERE hash IS NOT NULL
        GROUP BY hash HAVING COUNT(*) > 1
    """).fetchall()
    return [row[0] for row in rows]
