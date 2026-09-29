import json
import pytest
from unittest.mock import MagicMock, patch
from src.download_dataset import DownloadDatasetWindow, DownloadArgs
from src.constants import COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT
from src import constants
from src.dataset import Dataset
from src.file_extractor import FileExtractor
from src.limited_sets import SetInfo
from src.utils import Result


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
    mock_args.premium_download = False
    mock_args.color_ratings = None

    # Mock the Entry widget for threshold
    mock_entry = MagicMock()
    mock_args.game_threshold = mock_entry

    # Scenario 1: Valid Integer Input
    mock_entry.get.return_value = "100"

    with patch("src.download_dataset.FileExtractor") as mock_extractor_cls, patch(
        "src.download_dataset.write_configuration"
    ), patch("src.download_dataset.retrieve_local_set_list", return_value=([], [])):
        mock_extractor_cls.return_value.retrieve_17lands_color_ratings.return_value = (True, 0)
        mock_extractor_cls.return_value.download_local_card_data.return_value = (False, "No matching local set", 0)
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

    with patch("src.download_dataset.FileExtractor") as mock_extractor_cls, patch(
        "src.download_dataset.write_configuration"
    ), patch("src.download_dataset.retrieve_local_set_list", return_value=([], [])):
        mock_extractor_cls.return_value.retrieve_17lands_color_ratings.return_value = (True, 0)
        mock_extractor_cls.return_value.download_local_card_data.return_value = (False, "No matching local set", 0)
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


@pytest.fixture
def normal_download():
    config = MagicMock()
    config.card_data.database_size = 0
    window = DownloadDatasetWindow(MagicMock(), {}, 1.0, {}, config, auto_enter=False)
    window.window = MagicMock()
    window._DownloadDatasetWindow__update_set_table = MagicMock()
    window.update_event_files_callback = MagicMock()
    set_info = MagicMock()
    set_info.seventeenlands = ["HOB"]
    args = DownloadArgs(
        draft_set=MagicMock(), draft=MagicMock(), start=MagicMock(), end=MagicMock(),
        user_group=MagicMock(), game_threshold=MagicMock(), button=MagicMock(),
        extra_button=MagicMock(), progress={}, list_box=MagicMock(),
        sets={"New Set": set_info}, status=MagicMock(), enable_rate_limit=False,
    )
    for field, value in (
        ("draft_set", "New Set"), ("draft", "PremierDraft"),
        ("start", "2023-01-01"), ("end", "2023-01-31"),
        ("user_group", "All"), ("game_threshold", "5000"),
    ):
        getattr(args, field).get.return_value = value

    with patch("src.download_dataset.FileExtractor") as extractor_class, patch(
        "src.download_dataset.write_configuration"
    ), patch(
        "src.download_dataset.retrieve_local_set_list", return_value=([], [])
    ) as local_sets, patch(
        "src.download_dataset.tkinter.messagebox.showwarning"
    ) as warning, patch(
        "src.download_dataset.tkinter.messagebox.askyesno", return_value=True
    ):
        extractor = extractor_class.return_value
        extractor.export_card_data.return_value = "HOB_PremierDraft_All_Data.json"
        extractor.download_local_card_data.return_value = (False, "No matching local set", 0)
        yield window, args, config, extractor, local_sets, warning


@pytest.mark.parametrize("color_ratings_available", [True, False])
def test_first_normal_download_saves_local_cards_without_statistics(
    normal_download, color_ratings_available
):
    window, args, config, extractor, _, warning = normal_download
    extractor.retrieve_17lands_color_ratings.return_value = (color_ratings_available, 0)
    completion = "Download Complete - Arena cards saved for tier lists; 17Lands statistics unavailable."
    extractor.download_card_data.return_value = (True, completion, 123)

    window._DownloadDatasetWindow__add_set(args)

    extractor.download_card_data.assert_called_once_with(0, allow_local_only=True)
    extractor.download_premium_card_data.assert_not_called()
    extractor.export_card_data.assert_called_once()
    window._DownloadDatasetWindow__update_set_table.assert_called_once_with(args.list_box, args.sets)
    window.update_event_files_callback.assert_called_once()
    assert config.card_data.latest_dataset == "HOB_PremierDraft_All_Data.json"
    assert config.card_data.database_size == 123
    assert args.progress["value"] == 100
    args.status.set.assert_called_with(completion)
    args.button.__setitem__.assert_called_with("state", "normal")
    args.extra_button.__setitem__.assert_called_with("state", "normal")
    warning.assert_not_called()


@pytest.mark.parametrize(
    "existing_set,existing_event,existing_group,existing_games,allow_local_only",
    [
        ("HOB", "PremierDraft", "All", 1000, False),
        ("HOB", "PremierDraft", "All", 0, True),
        ("OTHER", "PremierDraft", "All", 1000, True),
        ("HOB", "Sealed", "All", 1000, True),
        ("HOB", "PremierDraft", "Top", 1000, True),
    ],
)
def test_normal_download_preserves_existing_statistics_on_failure(
    normal_download, tmp_path, existing_set, existing_event, existing_group, existing_games,
    allow_local_only,
):
    window, args, config, extractor, local_sets, warning = normal_download
    existing_path = tmp_path / "existing_dataset.json"
    existing_path.write_text(json.dumps({
        "meta": {"version": 3},
        "card_ratings": {
            str(index): {"name": f"Card {index}", "deck_colors": {"All Decks": {"gihwr": 0}}}
            for index in range(100)
        },
    }), encoding="utf-8")
    local_sets.return_value = ([
        (existing_set, existing_event, existing_group, "2022-01-01", "2022-01-31", existing_games, str(existing_path))
    ], [])
    extractor.retrieve_17lands_color_ratings.return_value = (False, 0)
    extractor.download_card_data.return_value = (False, "Couldn't Collect 17Lands Data", 123)
    previous_dataset = config.card_data.latest_dataset

    window._DownloadDatasetWindow__add_set(args)

    extractor.download_card_data.assert_called_once_with(0, allow_local_only=allow_local_only)
    extractor.export_card_data.assert_not_called()
    window.update_event_files_callback.assert_not_called()
    assert config.card_data.latest_dataset == previous_dataset
    warning.assert_called_once()
    args.button.__setitem__.assert_called_with("state", "normal")
    args.extra_button.__setitem__.assert_called_with("state", "normal")


@pytest.mark.parametrize("game_count", [None, 0])
def test_normal_download_preserves_card_statistics_without_color_totals(
    normal_download, tmp_path, game_count
):
    window, args, config, extractor, local_sets, warning = normal_download
    existing_path = tmp_path / "HOB_PremierDraft_All_Data.json"
    meta = {"version": 3}
    if game_count is not None:
        meta["game_count"] = game_count
    existing_path.write_text(json.dumps({
        "meta": meta,
        "card_ratings": {
            str(index): {"name": f"Card {index}", "deck_colors": {"All Decks": {"gihwr": 55.0}}}
            for index in range(100)
        },
    }), encoding="utf-8")
    original = existing_path.read_bytes()
    local_sets.return_value = ([
        ("HOB", "PremierDraft", "All", "2023-01-01", "2023-01-31", 0, str(existing_path))
    ], [])
    extractor.retrieve_17lands_color_ratings.return_value = (False, 0)
    extractor.download_card_data.return_value = (False, "Couldn't Collect 17Lands Data", 123)

    window._DownloadDatasetWindow__add_set(args)

    extractor.download_card_data.assert_called_once_with(0, allow_local_only=False)
    extractor.export_card_data.assert_not_called()
    assert existing_path.read_bytes() == original
    warning.assert_called_once()


@pytest.mark.parametrize("statistics_result", [
    "unavailable", "partial_failure", "unexpected_error", "color_error", "invalid_statistics", "available"
])
def test_first_download_saves_before_statistics_requests(
    normal_download, tmp_path, monkeypatch, statistics_result
):
    window, args, config, _, _, warning = normal_download
    args.sets["New Set"] = SetInfo(arena=[constants.SET_SELECTION_ALL], seventeenlands=["HOB"])
    cache = tmp_path / "arena_cards.json"
    cards = {
        str(100000 + index): {
            "name": f"Card {index}", "cmc": 2, "mana_cost": "{1}{W}",
            "types": ["Creature"], "rarity": "common", "image": [], "colors": ["W"],
        }
        for index in range(100)
    }
    cache.write_text(json.dumps({"HOB": cards, "OTHER": {"999": {"name": "Unrelated"}}}), encoding="utf-8")
    sets_path = tmp_path / "Sets"
    sets_path.mkdir()
    monkeypatch.setattr(constants, "TEMP_CARD_DATA_FILE", str(cache))
    monkeypatch.setattr(constants, "SETS_FOLDER", str(sets_path))
    extractor = FileExtractor(None, None, None, None)
    target = sets_path / "HOB_PremierDraft_All_Data.json"
    original_saved = []

    def local_cards(previous_size):
        success = extractor._retrieve_stored_data(extractor.selected_sets.arena)
        return success, "", 123

    def color_request():
        # This is the first network request: a usable dataset must already exist.
        loaded = Dataset()
        assert loaded.open_file(str(target)) == Result.VALID
        assert set(loaded.get_card_ratings()) == set(cards)
        assert loaded.get_names_by_id([100000]) == ["Card 0"]
        assert loaded.get_data_by_id([100000])[0]["deck_colors"]["All Decks"]["gihwr"] == 0.0
        assert config.card_data.latest_dataset == target.name
        assert config.card_data.database_size == 123
        window.update_event_files_callback.assert_called_once()
        original_saved.append(target.read_bytes())
        if statistics_result == "color_error":
            raise RuntimeError("Color request failed")
        extractor.set_game_count(500)
        extractor.set_color_ratings({"W": 55.0})
        return True, 500

    def card_request(*unused):
        assert original_saved and target.read_bytes() == original_saved[0]
        if statistics_result == "unexpected_error":
            raise RuntimeError("Card request failed")
        if statistics_result == "unavailable":
            return False
        count = 100 if statistics_result == "available" else 1
        extractor.card_ratings = {
            f"Card {index}": {"ratings": [{"All Decks": {"gihwr": 60.0}}], "image": []}
            for index in range(count)
        }
        return statistics_result != "partial_failure"

    with patch("src.download_dataset.FileExtractor", return_value=extractor), patch.object(
        extractor, "_retrieve_local_arena_data", side_effect=local_cards
    ), patch.object(
        extractor, "retrieve_17lands_color_ratings", side_effect=color_request
    ) as colors, patch.object(
        extractor, "retrieve_17lands_data", side_effect=card_request
    ):
        window._DownloadDatasetWindow__add_set(args)

    colors.assert_called_once()
    assert original_saved
    loaded = Dataset()
    assert loaded.open_file(str(target)) == Result.VALID
    assert len(loaded.get_card_ratings()) == 100
    expected_rating = 60.0 if statistics_result == "available" else 0.0
    assert loaded.get_data_by_id([100000])[0]["deck_colors"]["All Decks"]["gihwr"] == expected_rating
    if statistics_result in {"partial_failure", "unexpected_error", "color_error", "invalid_statistics"}:
        assert target.read_bytes() == original_saved[0]
        assert "Arena cards saved" in args.status.set.call_args.args[0]
    assert config.card_data.latest_dataset == target.name
    assert args.progress["value"] == 100
    args.button.__setitem__.assert_called_with("state", "normal")
    warning.assert_not_called()
