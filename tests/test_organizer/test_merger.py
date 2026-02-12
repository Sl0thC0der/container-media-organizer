"""Tests for FileMerger."""
import pytest
from pathlib import Path
from media_organizer.organizer.merger import FileMerger
from media_organizer.core.logger import Logger


class TestGetHighestNumber:
    """Test get_highest_number() method."""

    def test_empty_directory_returns_zero(self, tmp_path):
        """Test returns 0 for empty directory."""
        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        pics_dir = tmp_path / "Pics"
        pics_dir.mkdir()

        result = merger.get_highest_number(pics_dir, r"test_pic_(\d+)\.")
        assert result == 0

    def test_finds_highest_numbered_file(self, tmp_path):
        """Test correctly identifies highest number."""
        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        pics_dir = tmp_path / "Pics"
        pics_dir.mkdir()
        (pics_dir / "creator_pic_001.jpg").touch()
        (pics_dir / "creator_pic_005.jpg").touch()
        (pics_dir / "creator_pic_003.jpg").touch()

        result = merger.get_highest_number(pics_dir, r"creator_pic_(\d+)\.")
        assert result == 5

    def test_nonexistent_directory_returns_zero(self, tmp_path):
        """Test handles non-existent directory."""
        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        result = merger.get_highest_number(tmp_path / "nonexistent", r"test_(\d+)\.")
        assert result == 0

    def test_ignores_non_matching_files(self, tmp_path):
        """Test only counts files matching pattern."""
        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        pics_dir = tmp_path / "Pics"
        pics_dir.mkdir()
        (pics_dir / "creator_pic_010.jpg").touch()
        (pics_dir / "random_file.jpg").touch()
        (pics_dir / "creator_vid_020.mp4").touch()

        result = merger.get_highest_number(pics_dir, r"creator_pic_(\d+)\.")
        assert result == 10

    def test_handles_multi_digit_numbers(self, tmp_path):
        """Test handles numbers larger than 3 digits."""
        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        pics_dir = tmp_path / "Pics"
        pics_dir.mkdir()
        (pics_dir / "creator_pic_1234.jpg").touch()

        result = merger.get_highest_number(pics_dir, r"creator_pic_(\d+)\.")
        assert result == 1234


class TestMergeScatteredContent:
    """Test merge_scattered_content() method."""

    def test_creates_pics_and_video_directories(self, tmp_path, mocker):
        """Test creates Pics/ and Video/ subdirectories."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source_folder"
        source.mkdir()
        (source / "pic.jpg").write_bytes(b"content")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'test_creator', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        assert (tmp_path / "test_creator" / "Pics").exists()
        assert (tmp_path / "test_creator" / "Video").exists()

    def test_renames_files_with_sequential_numbers(self, tmp_path, mocker):
        """Test files are renamed with sequential numbers."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source"
        source.mkdir()
        (source / "random1.jpg").write_bytes(b"pic1")
        (source / "random2.jpg").write_bytes(b"pic2")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        pics_dir = tmp_path / "creator1" / "Pics"
        files = sorted(pics_dir.iterdir())
        assert len(files) == 2
        assert files[0].name == "creator1_pic_001.jpg"
        assert files[1].name == "creator1_pic_002.jpg"

    def test_continues_numbering_from_existing_files(self, tmp_path, mocker):
        """Test numbering continues from highest existing number."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        # Create existing organized structure
        creator_dir = tmp_path / "creator1"
        pics_dir = creator_dir / "Pics"
        pics_dir.mkdir(parents=True)
        (pics_dir / "creator1_pic_010.jpg").write_bytes(b"existing")

        # Create source to merge
        source = tmp_path / "source"
        source.mkdir()
        (source / "new_pic.jpg").write_bytes(b"new")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        # Should start from 011
        assert (pics_dir / "creator1_pic_011.jpg").exists()

    def test_separates_pics_and_videos(self, tmp_path, mocker):
        """Test pictures and videos go to different directories."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source"
        source.mkdir()
        (source / "image.jpg").write_bytes(b"pic")
        (source / "clip.mp4").write_bytes(b"vid")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        assert (tmp_path / "creator1" / "Pics" / "creator1_pic_001.jpg").exists()
        assert (tmp_path / "creator1" / "Video" / "creator1_vid_001.mp4").exists()

    def test_writes_merge_log(self, tmp_path, mocker):
        """Test merge operations are logged."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.jpg").write_bytes(b"content")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)
        merge_log = tmp_path / "merge.log"

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, merge_log)

        log_content = merge_log.read_text()
        assert "source" in log_content or "file.jpg" in log_content
        assert "creator1_pic_001.jpg" in log_content

    def test_handles_nested_source_files(self, tmp_path, mocker):
        """Test processes files in subdirectories with rglob."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source"
        source.mkdir()
        subfolder = source / "subfolder"
        subfolder.mkdir()
        (subfolder / "nested.jpg").write_bytes(b"nested")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        # Should find and merge nested file
        assert (tmp_path / "creator1" / "Pics" / "creator1_pic_001.jpg").exists()

    def test_preserves_file_extensions(self, tmp_path, mocker):
        """Test preserves original file extensions."""
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', tmp_path)

        source = tmp_path / "source"
        source.mkdir()
        (source / "image.png").write_bytes(b"png")
        (source / "video.mkv").write_bytes(b"mkv")

        logger = Logger(tmp_path / "test.log")
        merger = FileMerger(logger)

        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, tmp_path / "merge.log")

        assert (tmp_path / "creator1" / "Pics" / "creator1_pic_001.png").exists()
        assert (tmp_path / "creator1" / "Video" / "creator1_vid_001.mkv").exists()
