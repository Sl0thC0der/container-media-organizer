"""Filesystem test fixtures for creating realistic media library structures."""
from pathlib import Path
import pytest


@pytest.fixture
def simple_media_structure(temp_work_dir):
    """
    Creates a simple media library structure:
    temp_work_dir/
    ├── creator1/
    │   ├── pic1.jpg
    │   └── pic2.png
    └── creator2/
        └── video1.mp4
    """
    creator1 = temp_work_dir / "creator1"
    creator1.mkdir()
    (creator1 / "pic1.jpg").write_bytes(b"fake jpg content")
    (creator1 / "pic2.png").write_bytes(b"fake png content")

    creator2 = temp_work_dir / "creator2"
    creator2.mkdir()
    (creator2 / "video1.mp4").write_bytes(b"fake mp4 content")

    return temp_work_dir


@pytest.fixture
def scattered_media_structure(temp_work_dir):
    """
    Creates scattered (unorganized) media structure:
    temp_work_dir/
    ├── Random Folder 1/
    │   ├── image1.jpg
    │   └── subfolder/
    │       └── image2.jpg
    └── 2024-01-15 Creator Name - Event/
        ├── photo1.jpg
        └── video1.mp4
    """
    folder1 = temp_work_dir / "Random Folder 1"
    folder1.mkdir()
    (folder1 / "image1.jpg").write_bytes(b"jpg1")
    subfolder = folder1 / "subfolder"
    subfolder.mkdir()
    (subfolder / "image2.jpg").write_bytes(b"jpg2")

    folder2 = temp_work_dir / "2024-01-15 Creator Name - Event"
    folder2.mkdir()
    (folder2 / "photo1.jpg").write_bytes(b"photo")
    (folder2 / "video1.mp4").write_bytes(b"video")

    return temp_work_dir


@pytest.fixture
def organized_media_structure(temp_work_dir):
    """
    Creates properly organized structure:
    temp_work_dir/
    ├── creator1/
    │   ├── Pics/
    │   │   ├── creator1_pic_001.jpg
    │   │   └── creator1_pic_002.jpg
    │   └── Video/
    │       └── creator1_vid_001.mp4
    └── creator2/
        └── Pics/
            └── creator2_pic_001.png
    """
    creator1 = temp_work_dir / "creator1"
    pics1 = creator1 / "Pics"
    pics1.mkdir(parents=True)
    (pics1 / "creator1_pic_001.jpg").write_bytes(b"pic1")
    (pics1 / "creator1_pic_002.jpg").write_bytes(b"pic2")
    video1 = creator1 / "Video"
    video1.mkdir()
    (video1 / "creator1_vid_001.mp4").write_bytes(b"vid1")

    creator2 = temp_work_dir / "creator2"
    pics2 = creator2 / "Pics"
    pics2.mkdir(parents=True)
    (pics2 / "creator2_pic_001.png").write_bytes(b"pic1")

    return temp_work_dir


@pytest.fixture
def media_with_duplicates(temp_work_dir):
    """Creates structure with duplicate files (same content, different names)."""
    creator1 = temp_work_dir / "creator1"
    creator1.mkdir()

    # Same content, different names
    duplicate_content = b"duplicate file content"
    (creator1 / "original.jpg").write_bytes(duplicate_content)
    (creator1 / "copy1.jpg").write_bytes(duplicate_content)
    (creator1 / "copy2.jpg").write_bytes(duplicate_content)

    # Unique file
    (creator1 / "unique.jpg").write_bytes(b"unique content")

    return temp_work_dir


@pytest.fixture
def media_with_special_chars(temp_work_dir):
    """Creates files with special characters, unicode, spaces."""
    folder = temp_work_dir / "test_creator"
    folder.mkdir()

    # Various challenging filenames
    (folder / "file with spaces.jpg").write_bytes(b"content")
    (folder / "file_with_underscores.jpg").write_bytes(b"content")
    (folder / "file[brackets].jpg").write_bytes(b"content")
    (folder / "file(parens).jpg").write_bytes(b"content")

    return temp_work_dir


@pytest.fixture
def container_folder_structure(temp_work_dir):
    """
    Creates a container folder (Various Files) with subfolders:
    Various Files/
    ├── Creator A/
    │   └── pic1.jpg
    └── Creator B/
        └── pic2.jpg
    """
    container = temp_work_dir / "Various Files"
    container.mkdir()

    creatorA = container / "Creator A"
    creatorA.mkdir()
    (creatorA / "pic1.jpg").write_bytes(b"pic1")

    creatorB = container / "Creator B"
    creatorB.mkdir()
    (creatorB / "pic2.jpg").write_bytes(b"pic2")

    return temp_work_dir


@pytest.fixture
def bracket_prefixed_folders(temp_work_dir):
    """Creates folders starting with '[' that should be skipped."""
    normal = temp_work_dir / "normal_folder"
    normal.mkdir()
    (normal / "file1.jpg").write_bytes(b"content")

    bracketed = temp_work_dir / "[External Source]"
    bracketed.mkdir()
    (bracketed / "file2.jpg").write_bytes(b"content")

    return temp_work_dir


def create_large_media_library(base_path: Path, creators: int = 10, files_per_creator: int = 100):
    """Helper to create large media library for performance testing."""
    for i in range(creators):
        creator = base_path / f"creator{i:03d}"
        creator.mkdir()
        for j in range(files_per_creator):
            filename = f"file{j:04d}.jpg"
            (creator / filename).write_bytes(b"x" * 1024)  # 1KB each
