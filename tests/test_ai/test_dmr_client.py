"""Tests for DMR client."""

import pytest
from pathlib import Path
from media_organizer.ai.dmr_client import DMRClient
from media_organizer.core.logger import Logger


def test_dmr_client_creation(tmp_path):
    """Test DMR client can be created."""
    logger = Logger(tmp_path / "test.log")
    client = DMRClient(logger)

    assert client is not None
    assert client.logger == logger


def test_dmr_client_retry_logic(mocker, tmp_path):
    """Test DMR client retry logic with mocked requests."""
    logger = Logger(tmp_path / "test.log")
    client = DMRClient(logger)

    # Mock requests.post to fail twice, succeed third time
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'choices': [{'message': {'content': 'test response'}}]
    }

    mock_post = mocker.patch('requests.post')
    mock_post.side_effect = [
        mocker.Mock(status_code=500),  # First attempt fails
        mocker.Mock(status_code=500),  # Second attempt fails
        mock_response,                   # Third attempt succeeds
    ]

    # Should eventually succeed
    result = client.call_api("test prompt", max_retries=3)
    assert result == 'test response'
    assert mock_post.call_count == 3
