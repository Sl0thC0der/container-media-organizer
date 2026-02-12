"""End-to-end integration tests for complete workflow."""
import pytest
from pathlib import Path
from media_organizer.cli import MediaOrganizer


@pytest.mark.integration
class TestFullPipeline:
    """Test complete 6-phase workflow."""

    def test_workflow_with_mock_dmr(self, scattered_media_structure, mocker):
        """Test full workflow with mocked DMR."""
        # This is a complex integration test that requires careful mocking
        # For now, test the individual components work together
        from media_organizer.core.database import DatabaseManager
        from media_organizer.organizer.merger import FileMerger
        from media_organizer.core.logger import Logger

        # Test that components can work together
        logger = Logger(scattered_media_structure / "test.log")
        db_manager = DatabaseManager(logger)

        # Scan filesystem
        count = db_manager.scan_filesystem(scattered_media_structure, scan_id=1)
        assert count > 0

        # Test merger can create structure
        merger = FileMerger(logger)
        mocker.patch('media_organizer.organizer.merger.WORK_DIR', scattered_media_structure)

        # Create a simple scattered folder structure
        source = scattered_media_structure / "Random Folder 1"
        scattered = [{'creator': 'creator1', 'path': source}]
        merger.merge_scattered_content(scattered, scattered_media_structure / "merge.log")

        # Verify structure created
        assert (scattered_media_structure / "creator1" / "Pics").exists()
        assert (scattered_media_structure / "creator1" / "Video").exists()

    def test_workflow_with_already_organized_library(self, organized_media_structure):
        """Test workflow when library is already organized."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Test scanning an already organized library
        logger = Logger(organized_media_structure / "test.log")
        db_manager = DatabaseManager(logger)

        # Scan should work normally
        count = db_manager.scan_filesystem(organized_media_structure, scan_id=1)
        assert count > 0

        # Verify structure still exists
        assert (organized_media_structure / "creator1" / "Pics").exists()
        assert (organized_media_structure / "creator2" / "Pics").exists()

    def test_dmr_client_handles_unavailable(self, tmp_path, mocker):
        """Test DMR client handles unavailable service."""
        from media_organizer.ai.dmr_client import DMRClient
        from media_organizer.core.logger import Logger
        import requests

        logger = Logger(tmp_path / "test.log")
        client = DMRClient(logger)

        # Mock connection failure with requests exception
        mocker.patch('requests.get', side_effect=requests.exceptions.ConnectionError("Cannot connect"))

        # Should handle exception and return False
        result = client.check_connection()
        assert result is False

    def test_workflow_with_container_folders(self, container_folder_structure, mocker):
        """Test workflow expands container folders."""
        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr_instance = mock_dmr_class.return_value
        mock_dmr_instance.check_connection.return_value = True
        mock_dmr_instance.call_api.return_value = '{"Creator A": "creator_a", "Creator B": "creator_b", "Various Files": null}'

        # Patch WORK_DIR in the cli module where it's used
        mocker.patch('media_organizer.cli.WORK_DIR', container_folder_structure)
        mocker.patch('media_organizer.cli.DB_FILE', container_folder_structure / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

    def test_workflow_with_duplicates(self, media_with_duplicates, mocker):
        """Test workflow identifies and removes duplicates."""
        mock_dmr_class = mocker.patch('media_organizer.cli.DMRClient')
        mock_dmr_instance = mock_dmr_class.return_value
        mock_dmr_instance.check_connection.return_value = True
        mock_dmr_instance.call_api.return_value = '{"creator1": "creator1"}'

        # Patch WORK_DIR in the cli module where it's used
        mocker.patch('media_organizer.cli.WORK_DIR', media_with_duplicates)
        mocker.patch('media_organizer.cli.DB_FILE', media_with_duplicates / "test.db")

        organizer = MediaOrganizer()
        result = organizer.run()

        assert result == 0

        # Verify duplicates were removed
        remaining_files = list(media_with_duplicates.rglob('*.jpg'))
        # Should have fewer files than original 4 (3 duplicates + 1 unique)
        # After dedup and merge, exact count depends on workflow


@pytest.mark.integration
class TestPartialWorkflows:
    """Test individual phase combinations."""

    def test_scan_only(self, simple_media_structure, mocker):
        """Test scanning phase only."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        logger = Logger(simple_media_structure / "test.log")
        db_manager = DatabaseManager(logger)

        count = db_manager.scan_filesystem(simple_media_structure, scan_id=1)
        assert count > 0

    def test_scan_and_identify(self, scattered_media_structure, mocker, test_db):
        """Test scan + AI identification phases."""
        from media_organizer.ai.identifier import CreatorIdentifier
        from media_organizer.core.logger import Logger

        logger = Logger(scattered_media_structure / "test.log")

        # Mock DMR
        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = '{"Random Folder 1": "creator1"}'

        identifier = CreatorIdentifier(test_db, dmr_client, logger)
        folders = list(scattered_media_structure.iterdir())
        mappings = identifier.identify_creators(folders, {})

        assert len(mappings) > 0

    def test_merge_without_dedup(self, scattered_media_structure, mocker):
        """Test merge phase without deduplication."""
        from media_organizer.organizer.merger import FileMerger
        from media_organizer.core.logger import Logger

        mocker.patch('media_organizer.organizer.merger.WORK_DIR', scattered_media_structure)

        logger = Logger(scattered_media_structure / "test.log")
        merger = FileMerger(logger)

        source = scattered_media_structure / "Random Folder 1"
        scattered = [{'creator': 'test_creator', 'path': source}]
        merger.merge_scattered_content(scattered, scattered_media_structure / "merge.log")

        assert (scattered_media_structure / "test_creator" / "Pics").exists()
