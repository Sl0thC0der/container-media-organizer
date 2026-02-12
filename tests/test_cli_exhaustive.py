"""Exhaustive CLI tests for 100% coverage."""
import pytest
from pathlib import Path
from media_organizer.cli import MediaOrganizer


class TestCLIDMRUnavailable:
    """Test DMR unavailable error messages (lines 61-66)."""

    def test_dmr_unavailable_shows_all_error_lines(self, tmp_path, mocker, capsys):
        """Test all DMR error message lines are executed."""
        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = False

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 1

        # Capture all output
        captured = capsys.readouterr()
        log_content = organizer.logger.log_file.read_text() + captured.out + captured.err

        # Verify all error lines
        assert "Docker Model Runner not available" in log_content
        assert "Enable Docker Model Runner" in log_content
        assert "docker model status" in log_content
        assert "docker model pull" in log_content


class TestCLIFileAndFolderChecks:
    """Test file/folder skip logic (lines 92, 94)."""

    def test_skips_non_directory_items(self, tmp_path, mocker):
        """Test skips files (line 92: if not folder.is_dir())."""
        # Create a file in WORK_DIR
        (tmp_path / "file.txt").write_text("content")

        # Create a real folder
        folder = tmp_path / "real_folder"
        folder.mkdir()
        (folder / "pic.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        mock_dmr.call_api.return_value = '{"real_folder": "creator"}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

    def test_skips_bracketed_and_claude_folders(self, tmp_path, mocker):
        """Test skips folders starting with '[' and '.claude' (line 94)."""
        # Create bracketed folder
        bracketed = tmp_path / "[External]"
        bracketed.mkdir()

        # Create .claude folder
        claude = tmp_path / ".claude"
        claude.mkdir()

        # Create normal folder
        normal = tmp_path / "normal"
        normal.mkdir()
        (normal / "pic.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        mock_dmr.call_api.return_value = '{"normal": "creator"}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0


class TestCLIUnknownFolders:
    """Test unknown folder identification (lines 108-109)."""

    def test_logs_unknown_folders_needing_ai(self, tmp_path, mocker, capsys):
        """Test unknown folders are logged (lines 108-109)."""
        # Create unknown folder (not in mappings, no Pics/Video)
        unknown = tmp_path / "Unknown Folder"
        unknown.mkdir()
        (unknown / "file.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        # Return mapping for it
        mock_dmr.call_api.return_value = '{"Unknown Folder": "identified"}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Check that UNKNOWN was logged
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out
        assert "[UNKNOWN]" in combined or "needs AI identification" in combined


class TestCLIContainerExpansion:
    """Test container folder expansion (line 119)."""

    def test_skips_non_directory_in_container(self, tmp_path, mocker):
        """Test skips files within container folders (line 119)."""
        # Create container folder
        container = tmp_path / "Container"
        container.mkdir()

        # Add a file (not directory) - should be skipped
        (container / "file.txt").write_text("content")

        # Add a subfolder - should be expanded
        subfolder = container / "Creator"
        subfolder.mkdir()
        (subfolder / "pic.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        # Return null for container
        mock_dmr.call_api.return_value = '{"Container": null}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0


class TestCLIAIWorkflow:
    """Test AI identification workflow (lines 138-157)."""

    def test_ai_workflow_all_paths(self, tmp_path, mocker, capsys):
        """Test complete AI workflow including all lines 138-157."""
        # Create multiple ambiguous folders
        folder1 = tmp_path / "Ambiguous 1"
        folder1.mkdir()
        (folder1 / "pic.jpg").write_bytes(b"content")

        folder2 = tmp_path / "Ambiguous 2"
        folder2.mkdir()
        (folder2 / "pic.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        # Return mappings including some with null
        mock_dmr.call_api.return_value = '{"Ambiguous 1": "creator1", "Ambiguous 2": null}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Verify AI workflow was executed
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out

        # Lines 138-139
        assert "[AI] Identifying" in combined
        assert "ambiguous folders" in combined

        # Lines 142
        assert "[AI] Identified" in combined

        # Lines 157
        assert "Saved mappings" in combined


class TestCLINoScatteredContent:
    """Test no scattered content path (line 170)."""

    def test_logs_no_scattered_content(self, tmp_path, mocker, capsys):
        """Test logs when no scattered content found (line 170)."""
        # Create organized structure
        creator = tmp_path / "creator1"
        (creator / "Pics").mkdir(parents=True)
        (creator / "Video").mkdir(parents=True)
        (creator / "Pics" / "pic.jpg").write_bytes(b"content")

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Check for "No scattered content" message
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out
        assert "No scattered content" in combined or "No ambiguous folders" in combined


class TestCLIFinalStatistics:
    """Test final statistics output (lines 222-232)."""

    def test_prints_final_statistics_all_lines(self, tmp_path, mocker, capsys):
        """Test final statistics block (lines 222-232)."""
        # Create simple library
        creator = tmp_path / "creator1"
        creator.mkdir()
        (creator / "pic1.jpg").write_bytes(b"a" * 1000)
        (creator / "pic2.jpg").write_bytes(b"b" * 2000)

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        mock_dmr.call_api.return_value = '{"creator1": "creator1"}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Verify statistics output
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out

        # Should show final state
        assert "[AFTER]" in combined or "Final state" in combined
        assert "TOTAL" in combined
        assert "files" in combined.lower()


class TestCLIErrorHandling:
    """Test error handling paths (lines 237-238, 242)."""

    def test_handles_exception_during_workflow(self, tmp_path, mocker, capsys):
        """Test exception handling (line 242)."""
        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value

        # Make it raise an exception
        mock_dmr.check_connection.side_effect = RuntimeError("Test error")

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        # Should return error code
        assert result == 1

        # Should log error
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out + captured.err
        assert "ERROR" in combined or "error" in combined.lower()


class TestCLICompleteWorkflow:
    """Test complete workflow to ensure all paths are covered."""

    def test_full_workflow_with_all_scenarios(self, tmp_path, mocker, capsys):
        """Test complete workflow touching all CLI paths."""
        # Create diverse folder structure
        # 1. Known folder (will be scattered)
        known = tmp_path / "Known Folder"
        known.mkdir()
        (known / "pic.jpg").write_bytes(b"content")

        # 2. Container folder
        container = tmp_path / "Container"
        container.mkdir()
        sub1 = container / "Sub1"
        sub1.mkdir()
        (sub1 / "pic.jpg").write_bytes(b"content")
        # Add a file in container to test line 119
        (container / "readme.txt").write_text("info")

        # 3. Unknown folder
        unknown = tmp_path / "Unknown"
        unknown.mkdir()
        (unknown / "pic.jpg").write_bytes(b"content")

        # 4. Already organized
        organized = tmp_path / "organized"
        (organized / "Pics").mkdir(parents=True)
        (organized / "Pics" / "pic.jpg").write_bytes(b"content")

        # 5. File in root (should be skipped)
        (tmp_path / "file.txt").write_text("content")

        # 6. Bracketed folder (should be skipped)
        bracketed = tmp_path / "[Skip]"
        bracketed.mkdir()

        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr = mock_dmr_class.return_value
        mock_dmr.check_connection.return_value = True
        mock_dmr.call_api.return_value = '{"Known Folder": "known_creator", "Container": null, "Unknown": "unknown_creator"}'

        mocker.patch('media_organizer.cli.WORK_DIR', tmp_path)
        mocker.patch('media_organizer.cli.DB_FILE', tmp_path / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Verify comprehensive output
        captured = capsys.readouterr()
        combined = organizer.logger.log_file.read_text() + captured.out

        # Should have AI identification
        assert "[AI]" in combined

        # Should have merge
        assert "[MERGE]" in combined or "Merged" in combined

        # Should have final stats
        assert "TOTAL" in combined
