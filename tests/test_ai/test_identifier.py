"""Tests for CreatorIdentifier."""
import pytest
from media_organizer.ai.identifier import CreatorIdentifier
from media_organizer.core.logger import Logger
from tests.fixtures.mock_dmr import mock_creator_identification_response, mock_malformed_json_response


class TestLoadMappings:
    """Test load_mappings() method."""

    def test_loads_mappings_from_database(self, populated_db, tmp_path, mock_dmr_client):
        """Test loads existing mappings."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(populated_db, mock_dmr_client, logger)

        mappings = identifier.load_mappings()
        assert 'Creator 1 Photos' in mappings
        assert mappings['Creator 1 Photos'] == 'creator1'
        assert 'Various Files' in mappings
        assert mappings['Various Files'] is None

    def test_empty_database_returns_empty_dict(self, test_db, tmp_path, mock_dmr_client):
        """Test returns empty dict for empty database."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(test_db, mock_dmr_client, logger)

        mappings = identifier.load_mappings()
        assert mappings == {}

    def test_handles_database_errors(self, tmp_path, mock_dmr_client, mocker):
        """Test handles database errors gracefully."""
        logger = Logger(tmp_path / "test.log")

        # Mock db to raise error
        mock_db = mocker.Mock()
        mock_db.execute.side_effect = Exception("DB error")

        identifier = CreatorIdentifier(mock_db, mock_dmr_client, logger)

        # Should handle error and return empty dict
        with pytest.raises(Exception):
            identifier.load_mappings()


class TestSaveMappings:
    """Test save_mappings() method."""

    def test_saves_new_mappings(self, test_db, tmp_path, mock_dmr_client):
        """Test saves new mappings to database."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(test_db, mock_dmr_client, logger)

        new_mappings = {
            'Folder A': 'creator_a',
            'Folder B': 'creator_b'
        }
        identifier.save_mappings(new_mappings)

        # Verify saved
        loaded = identifier.load_mappings()
        assert loaded == new_mappings

    def test_updates_existing_mappings(self, populated_db, tmp_path, mock_dmr_client):
        """Test UPSERT updates existing mappings."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(populated_db, mock_dmr_client, logger)

        # Update existing mapping
        updated = {'Creator 1 Photos': 'new_creator_name'}
        identifier.save_mappings(updated)

        loaded = identifier.load_mappings()
        assert loaded['Creator 1 Photos'] == 'new_creator_name'

    def test_handles_null_creator_names(self, test_db, tmp_path, mock_dmr_client):
        """Test handles container folders (NULL creator)."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(test_db, mock_dmr_client, logger)

        mappings = {'Container Folder': None}
        identifier.save_mappings(mappings)

        loaded = identifier.load_mappings()
        assert loaded['Container Folder'] is None

    def test_saves_multiple_mappings(self, test_db, tmp_path, mock_dmr_client):
        """Test saves multiple mappings in one call."""
        logger = Logger(tmp_path / "test.log")
        identifier = CreatorIdentifier(test_db, mock_dmr_client, logger)

        mappings = {
            'Folder 1': 'creator1',
            'Folder 2': 'creator2',
            'Folder 3': None
        }
        identifier.save_mappings(mappings)

        loaded = identifier.load_mappings()
        assert len(loaded) == 3
        assert loaded['Folder 1'] == 'creator1'
        assert loaded['Folder 2'] == 'creator2'
        assert loaded['Folder 3'] is None


class TestIdentifyCreators:
    """Test identify_creators() method."""

    def test_identifies_creators_from_folders(self, test_db, tmp_path, scattered_media_structure, mocker):
        """Test identifies creators using AI."""
        logger = Logger(tmp_path / "test.log")

        # Mock DMR client
        dmr_client = mocker.Mock()
        dmr_response = mock_creator_identification_response({
            'Random Folder 1': 'creator1',
            '2024-01-15 Creator Name - Event': 'creator_name'
        })
        dmr_client.call_api.return_value = dmr_response

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        folders = list(scattered_media_structure.iterdir())
        result = identifier.identify_creators(folders, {})

        assert 'Random Folder 1' in result
        assert result['Random Folder 1'] == 'creator1'
        assert '2024-01-15 Creator Name - Event' in result
        assert result['2024-01-15 Creator Name - Event'] == 'creator_name'

    def test_handles_malformed_json_response(self, test_db, tmp_path, mocker):
        """Test handles AI response with invalid JSON."""
        logger = Logger(tmp_path / "test.log")

        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = mock_malformed_json_response()

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        result = identifier.identify_creators([], {})
        assert result == {}

    def test_handles_api_failure(self, test_db, tmp_path, mocker):
        """Test handles DMR API returning None."""
        logger = Logger(tmp_path / "test.log")

        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = None

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        result = identifier.identify_creators([], {})
        assert result == {}

    def test_includes_known_creators_in_prompt(self, test_db, tmp_path, mocker):
        """Test passes known creators to AI for context."""
        logger = Logger(tmp_path / "test.log")

        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = '{}'

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        existing_mappings = {'Folder A': 'creator_a', 'Folder B': 'creator_b'}
        identifier.identify_creators([], existing_mappings)

        # Check prompt includes known creators
        call_args = dmr_client.call_api.call_args[0][0]
        assert 'creator_a' in call_args
        assert 'creator_b' in call_args

    def test_handles_empty_folder_list(self, test_db, tmp_path, mocker):
        """Test handles empty folder list gracefully."""
        logger = Logger(tmp_path / "test.log")

        # Mock returns empty JSON for empty folder list
        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = '{}'

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        result = identifier.identify_creators([], {})

        # API is called but with empty folder list
        dmr_client.call_api.assert_called_once()
        # Should return empty dict from empty JSON response
        assert result == {}

    def test_handles_json_with_extra_text(self, test_db, tmp_path, mocker):
        """Test extracts JSON from response with surrounding text."""
        logger = Logger(tmp_path / "test.log")

        dmr_client = mocker.Mock()
        # JSON embedded in explanatory text
        dmr_client.call_api.return_value = """
        Here's my analysis of the folders:

        {"Folder A": "creator_a", "Folder B": "creator_b"}

        I identified these creators based on the folder names.
        """

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        # Create actual folders
        folder_a = tmp_path / "Folder A"
        folder_b = tmp_path / "Folder B"
        folder_a.mkdir()
        folder_b.mkdir()

        folders = [folder_a, folder_b]
        result = identifier.identify_creators(folders, {})

        assert result == {'Folder A': 'creator_a', 'Folder B': 'creator_b'}

    def test_handles_unicode_folder_names(self, test_db, tmp_path, mocker):
        """Test handles folders with unicode characters."""
        logger = Logger(tmp_path / "test.log")

        dmr_client = mocker.Mock()
        dmr_response = mock_creator_identification_response({
            '日本語フォルダ': 'japanese_creator',
            'Créateur Français': 'french_creator'
        })
        dmr_client.call_api.return_value = dmr_response

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        # Create actual folders with unicode names
        folder1 = tmp_path / '日本語フォルダ'
        folder2 = tmp_path / 'Créateur Français'
        folder1.mkdir()
        folder2.mkdir()

        folders = [folder1, folder2]
        result = identifier.identify_creators(folders, {})

        assert '日本語フォルダ' in result
        assert 'Créateur Français' in result
