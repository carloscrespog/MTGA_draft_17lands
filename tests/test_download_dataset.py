import pytest
from unittest.mock import MagicMock, patch
from src.download_dataset import DownloadDatasetWindow, DownloadArgs
from src.constants import COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT


def test_add_set_parses_threshold():
    """
    Verify that __add_set correctly parses the threshold from the UI entry widget.
    """
    # Mock dependencies
    root = MagicMock()
    sets = MagicMock()
    config = MagicMock()

    window = DownloadDatasetWindow(root, sets, 1.0, {}, config, auto_enter=False)
    window.window = MagicMock()

    # Mock the DownloadArgs
    mock_args = MagicMock()
    mock_args.draft_set = MagicMock()
    mock_args.draft = MagicMock()
    mock_args.start = MagicMock()
    mock_args.end = MagicMock()
    mock_args.user_group = MagicMock()
    mock_args.enable_rate_limit = False  # Skip rate limit check

    # Mock the Entry widget for threshold
    mock_entry = MagicMock()
    mock_args.game_threshold = mock_entry

    # Scenario 1: Valid Integer Input
    mock_entry.get.return_value = "100"

    with patch("src.download_dataset.FileExtractor") as mock_extractor_cls:
        # We need to mock _setup_extractor to avoid UI calls
        window._setup_extractor = MagicMock()
        # Mock _handle_game_count... to stop execution flow
        window._handle_game_count_and_notify = MagicMock(return_value=False)

        # Access the private method for testing logic
        window._DownloadDatasetWindow__add_set(mock_args)

        # Verify FileExtractor was initialized with parsed value
        _, kwargs = mock_extractor_cls.call_args
        assert kwargs["threshold"] == 100

    # Scenario 2: Invalid Input (should fallback to default)
    mock_entry.get.return_value = "invalid"

    with patch("src.download_dataset.FileExtractor") as mock_extractor_cls:
        window._setup_extractor = MagicMock()
        window._handle_game_count_and_notify = MagicMock(return_value=False)

        window._DownloadDatasetWindow__add_set(mock_args)

        _, kwargs = mock_extractor_cls.call_args
        assert kwargs["threshold"] == COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT


def test_add_set_premium_uses_premium_download_path():
    root = MagicMock()
    sets = MagicMock()
    config = MagicMock()
    config.card_data.last_check = 0
    config.card_data.database_size = 0

    window = DownloadDatasetWindow(root, sets, 1.0, {}, config, auto_enter=False)
    window.window = MagicMock()
    window.__update_set_table = MagicMock()
    window.update_event_files_callback = MagicMock()

    mock_args = MagicMock()
    mock_args.enable_rate_limit = False
    mock_args.premium_download = True
    mock_args.color_ratings = None
    mock_args.game_threshold.get.return_value = "5000"
    mock_args.list_box = MagicMock()
    mock_args.sets = {}

    with patch("src.download_dataset.FileExtractor") as mock_extractor_cls, patch(
        "src.download_dataset.write_configuration"
    ):
        extractor = mock_extractor_cls.return_value
        extractor.download_premium_card_data.return_value = (True, "", 123)
        extractor.export_card_data.return_value = "MSH_PremierDraft_Top_Data.json"
        window._setup_extractor = MagicMock()
        window._DownloadDatasetWindow__update_set_table = MagicMock()

        window._DownloadDatasetWindow__add_set(mock_args)

    extractor.set_color_ratings.assert_called_once_with({})
    extractor.retrieve_17lands_color_ratings.assert_not_called()
    extractor.download_card_data.assert_not_called()
    extractor.download_premium_card_data.assert_called_once_with(0)
