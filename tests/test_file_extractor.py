import pytest
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from src.card_logic import CardResult
from src.dataset import Dataset
from src.file_extractor import (
    FileExtractor,
    decode_mana_cost,
    extract_types,
    initialize_card_data,
    check_date,
)
from src import constants
from src.limited_sets import SetInfo
from src.utils import Result, normalize_color_string
from src.constants import (
    COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT,
    DECK_COLORS,
)


@pytest.mark.parametrize(
    "encoded_cost, expected_decoded, expected_cmc",
    [
        ("o1oW", "{1}{W}", 2),
        ("o2oUoU", "{2}{U}{U}", 4),
        ("oXoGoG", "{X}{G}{G}", 3),
        ("o5", "{5}", 5),
        ("", "", 0),
        (None, "", 0),
        ("(o2oG)", "{2}{G}", 3),  # Test with parentheses
    ],
)
def test_decode_mana_cost(encoded_cost, expected_decoded, expected_cmc):
    """Tests the decode_mana_cost utility function for various mana cost formats."""
    decoded, cmc = decode_mana_cost(encoded_cost)
    assert decoded == expected_decoded
    assert cmc == expected_cmc


@pytest.mark.parametrize(
    "type_line, expected_types",
    [
        ("Creature — Human Soldier", ["Creature"]),
        ("Artifact Creature — Golem", ["Creature", "Artifact"]),
        ("Legendary Enchantment Artifact", ["Enchantment", "Artifact"]),
        ("Instant", ["Instant"]),
        ("Basic Land — Forest", ["Land"]),
        ("Vanguard", []),
    ],
)
def test_extract_types(type_line, expected_types):
    """Tests the extract_types utility function to correctly identify main card types."""
    types = extract_types(type_line)
    # Use sets for comparison to ignore order
    assert set(types) == set(expected_types)


def test_initialize_card_data():
    """Tests that a card data dictionary is correctly initialized with deck_colors."""
    card = {}
    initialize_card_data(card)
    assert constants.DATA_FIELD_DECK_COLORS in card
    assert constants.FILTER_OPTION_ALL_DECKS in card[constants.DATA_FIELD_DECK_COLORS]
    assert "W" in card[constants.DATA_FIELD_DECK_COLORS]
    assert "WUBRG" in card[constants.DATA_FIELD_DECK_COLORS]
    for color in constants.DECK_COLORS:
        assert color in card[constants.DATA_FIELD_DECK_COLORS]
        assert (
            constants.DATA_FIELD_GIHWR in card[constants.DATA_FIELD_DECK_COLORS][color]
        )
        assert (
            card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR]
            == 0.0
        )


@pytest.mark.parametrize(
    "date_str, expected_result",
    [
        ("2023-01-01", True),
        ("9999-12-31", False),  # Future date
        ("invalid-date", False),
        ("2023-13-01", False),  # Invalid month
    ],
)
def test_check_date(date_str, expected_result):
    """Tests the date validation utility function."""
    assert check_date(date_str) == expected_result


def test_initialize_card_data_keys_normalized():
    """
    Verify that initialize_card_data creates keys that match the normalized format.
    This prevents the 'missing W' bug from reappearing.
    """
    card_data = {}
    initialize_card_data(card_data)

    deck_colors_keys = card_data[constants.DATA_FIELD_DECK_COLORS].keys()

    for color in DECK_COLORS:
        # The keys in the initialized data must match the normalized version of the constants
        normalized_color = normalize_color_string(color)
        assert normalized_color in deck_colors_keys


@pytest.fixture
def file_extractor():
    """Fixture to create a FileExtractor instance with default values for testing."""
    # Mock UI dependencies for the constructor
    mock_progress = MagicMock()
    mock_status = MagicMock()
    mock_ui = MagicMock()

    extractor = FileExtractor(
        directory=None, progress=mock_progress, status=mock_status, ui=mock_ui
    )

    # Set default attributes usually set by UI interaction
    extractor.draft = "PremierDraft"
    extractor.start_date = "2023-01-01"
    extractor.end_date = "2023-01-31"
    extractor.user_group = constants.LIMITED_USER_GROUP_ALL

    return extractor


@patch("src.file_extractor.Seventeenlands")
def test_retrieve_17lands_color_ratings_passes_threshold(
    mock_seventeenlands_cls, file_extractor
):
    """
    Verify that FileExtractor passes its configured threshold to the Seventeenlands client.
    """
    mock_sl_instance = mock_seventeenlands_cls.return_value
    mock_sl_instance.download_color_ratings.return_value = ({}, 0)

    # Setup extractor with a custom threshold
    custom_threshold = 1234
    file_extractor.threshold = custom_threshold

    # Mock necessary attributes
    file_extractor.selected_sets = MagicMock()
    file_extractor.selected_sets.seventeenlands = ["SET"]

    # Run
    file_extractor.retrieve_17lands_color_ratings()

    # Verify call
    mock_sl_instance.download_color_ratings.assert_called_once()
    call_kwargs = mock_sl_instance.download_color_ratings.call_args.kwargs
    assert call_kwargs["threshold"] == custom_threshold


def test_file_extractor_default_threshold():
    """Verify FileExtractor defaults to the constant if no threshold is provided."""
    extractor = FileExtractor(None, None, None, None)
    assert extractor.threshold == COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT


@patch("src.file_extractor.Seventeenlands")
def test_retrieve_17lands_premium_data_sets_metadata(
    mock_seventeenlands_cls, file_extractor
):
    mock_sl_instance = mock_seventeenlands_cls.return_value
    cards = [
        {"name": "Card One", constants.DATA_FIELD_17LANDS_NGP: 10},
        {"name": "Card Two", constants.DATA_FIELD_17LANDS_NGP: 15},
    ]

    def populate_card_data(set_code, draft, user_group, card_data):
        card_data["Card One"] = {}
        card_data["Card Two"] = {}
        return cards

    mock_sl_instance.download_premium_card_data.side_effect = populate_card_data

    file_extractor.selected_sets = MagicMock()
    file_extractor.selected_sets.seventeenlands = ["MSH"]

    assert file_extractor.retrieve_17lands_premium_data(["MSH"])

    mock_sl_instance.download_premium_card_data.assert_called_once_with(
        "MSH",
        "PremierDraft",
        constants.LIMITED_USER_GROUP_ALL,
        file_extractor.card_ratings,
    )
    assert file_extractor.combined_data["meta"]["source"] == "17Lands Premium"
    assert file_extractor.combined_data["meta"]["time_period"] == "ALL_TIME"
    assert "game_count_note" in file_extractor.combined_data["meta"]
    assert file_extractor.combined_data["meta"]["game_count"] == 15


@patch("src.file_extractor.Seventeenlands")
def test_retrieve_17lands_premium_data_rejects_empty_response(
    mock_seventeenlands_cls, file_extractor
):
    mock_seventeenlands_cls.return_value.download_premium_card_data.return_value = []
    file_extractor.selected_sets = MagicMock()
    file_extractor.selected_sets.seventeenlands = ["HOB"]

    assert not file_extractor.retrieve_17lands_premium_data(["HOB"])


@patch("src.file_extractor.time.sleep")
@patch("src.file_extractor.Seventeenlands")
def test_retrieve_17lands_data_rejects_empty_response(
    mock_seventeenlands_cls, mock_sleep, file_extractor
):
    file_extractor.selected_sets = MagicMock()
    file_extractor.selected_sets.seventeenlands = ["HOB"]

    assert not file_extractor.retrieve_17lands_data(["HOB"], ["All Decks"])

    mock_seventeenlands_cls.return_value.download_card_ratings.assert_called_once()


@pytest.fixture
def local_set_extractor(file_extractor, tmp_path, monkeypatch):
    """Load an Arena card cache while isolating installation discovery and HTTP."""
    arena_cards = {
        str(100000 + index): {
            "name": f"New Card {index}",
            "cmc": 2,
            "mana_cost": "{1}{W}",
            "colors": ["W"],
            "types": ["Creature"],
            "rarity": "common",
            "image": [],
        }
        for index in range(100)
    }
    cache_path = tmp_path / "arena_cards.json"
    cache_path.write_text(
        json.dumps({"HOB": arena_cards, "OTHER": {"999": {"name": "Other Card"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(constants, "TEMP_CARD_DATA_FILE", str(cache_path))
    monkeypatch.setattr(constants, "SETS_FOLDER", str(tmp_path))
    monkeypatch.setattr("src.file_extractor.time.sleep", lambda _seconds: None)
    file_extractor.select_sets(SetInfo(arena=["HOB"], seventeenlands=["HOB"]))
    file_extractor.set_start_date("2023-01-01")
    file_extractor.set_end_date("2023-01-31")
    file_extractor.set_version(2)

    def load_arena_cards(_database_size):
        success = file_extractor._retrieve_stored_data(file_extractor.selected_sets.arena)
        return success, "", 123

    monkeypatch.setattr(file_extractor, "_retrieve_local_arena_data", load_arena_cards)
    return file_extractor


@pytest.mark.parametrize("request_fails", [False, True], ids=["empty", "unavailable"])
@pytest.mark.parametrize(
    "arena_codes, set_codes",
    [
        (["HOB"], ["HOB"]),
        ([constants.SET_SELECTION_ALL], ["HOB"]),
        ([constants.SET_SELECTION_ALL], ["hob"]),
    ],
    ids=["explicit_arena_set", "cached_all", "cached_all_lowercase"],
)
@patch("src.seventeenlands.requests.get")
def test_download_without_17lands_saves_arena_cards_for_tier_lists(
    mock_get, arena_codes, set_codes, request_fails, local_set_extractor, tmp_path
):
    local_set_extractor.select_sets(
        SetInfo(arena=arena_codes, seventeenlands=set_codes)
    )
    if request_fails:
        mock_get.side_effect = RuntimeError("17Lands is unavailable")
    else:
        mock_get.return_value.json.return_value = []

    # Color totals alone must not imply that this dataset has card statistics.
    local_set_extractor.set_game_count(500)
    local_set_extractor.set_color_ratings({"W": 55.0})

    success, message, database_size = local_set_extractor.download_card_data(0)

    assert success
    assert message
    assert database_size == 123
    assert local_set_extractor.combined_data["meta"]["game_count"] == 0
    filename = local_set_extractor.export_card_data()
    assert filename

    dataset = Dataset()
    assert dataset.open_file(str(tmp_path / filename)) == Result.VALID
    assert set(dataset.get_card_ratings()) == {
        str(100000 + index) for index in range(100)
    }
    assert dataset.get_names_by_id([100000]) == ["New Card 0"]
    assert dataset.get_ids_by_name(["New Card 0"]) == ["100000"]
    assert dataset.get_color_ratings() == {}
    card = dataset.get_data_by_id([100000])[0]
    assert card["mana_cost"] == "{1}{W}"
    assert card["colors"] == ["W"]
    for color in DECK_COLORS:
        assert card["deck_colors"][color]
        assert all(value == 0.0 for value in card["deck_colors"][color].values())

    tier = SimpleNamespace(
        ratings={"New Card 0": SimpleNamespace(rating="A ", comment="")}
    )
    calculator = CardResult(None, {"TIER_TEST": tier}, MagicMock(), 1)
    result = calculator.return_results([card], "All Decks", ["TIER_TEST"])
    assert result[0]["results"] == ["A "]


@pytest.mark.parametrize(
    "arena_codes", [["HOB"], [constants.SET_SELECTION_ALL]],
    ids=["explicit_arena_set", "cached_all"],
)
@patch("src.seventeenlands.requests.get")
def test_download_with_17lands_merges_available_statistics(
    mock_get, arena_codes, local_set_extractor
):
    local_set_extractor.selected_sets.arena = arena_codes
    mock_get.return_value.json.return_value = [
        {
            "name": "New Card 0",
            constants.DATA_FIELD_17LANDS_DICT[constants.DATA_FIELD_GIHWR]: 0.625,
            constants.DATA_FIELD_17LANDS_IMAGE: "https://example.com/card.jpg",
        },
        {
            "name": "Other Card",
            constants.DATA_FIELD_17LANDS_DICT[constants.DATA_FIELD_GIHWR]: 0.55,
        },
    ]
    local_set_extractor.set_game_count(500)
    local_set_extractor.set_color_ratings({"W": 55.0})

    success, _message, database_size = local_set_extractor.download_card_data(0)

    assert success
    assert database_size == 123
    assert local_set_extractor.combined_data["meta"]["game_count"] == 500
    assert local_set_extractor.combined_data["color_ratings"] == {"W": 55.0}
    cards = local_set_extractor.combined_data["card_ratings"]
    assert cards["100000"]["deck_colors"]["All Decks"]["gihwr"] == 62.5
    assert cards["100000"]["image"] == ["https://example.com/card.jpg"]
    if constants.SET_SELECTION_ALL in arena_codes:
        # Ratings define the pool when available, including other print sets.
        assert set(cards) == {"100000", "999"}
        assert cards["999"]["deck_colors"]["All Decks"]["gihwr"] == pytest.approx(55.0)
    else:
        assert len(cards) == 100
        assert cards["100001"]["deck_colors"]["All Decks"]["gihwr"] == 0.0


@pytest.mark.parametrize("allow_local_only", [False, True], ids=["existing_stats", "cube"])
@patch("src.seventeenlands.requests.get")
def test_download_without_ratings_rejects_disallowed_fallback(
    mock_get, allow_local_only, local_set_extractor
):
    mock_get.return_value.json.return_value = []
    if allow_local_only:
        local_set_extractor.select_sets(
            SetInfo(
                arena=[constants.SET_SELECTION_ALL],
                seventeenlands=["Cube - Powered"],
                set_code="CUBE",
            )
        )

    success, message, _database_size = local_set_extractor.download_card_data(
        0, allow_local_only=allow_local_only
    )

    assert not success
    assert "17Lands" in message
    assert not local_set_extractor.combined_data.get("card_ratings")


@pytest.mark.parametrize(
    "set_codes",
    [["MISSING"], ["OB"], ["HOB", "MISSING"]],
    ids=["missing_set", "substring_only", "one_of_multiple_sets_missing"],
)
@patch("src.seventeenlands.requests.get")
def test_all_arena_fallback_requires_every_exact_set(
    mock_get, set_codes, local_set_extractor
):
    mock_get.return_value.json.return_value = []
    local_set_extractor.select_sets(
        SetInfo(arena=[constants.SET_SELECTION_ALL], seventeenlands=set_codes)
    )

    success, message, _database_size = local_set_extractor.download_card_data(0)

    assert not success
    assert "17Lands" in message
    assert not local_set_extractor.combined_data.get("card_ratings")


@patch("src.seventeenlands.requests.get")
def test_download_does_not_accept_partial_failed_statistics(mock_get, local_set_extractor):
    response = MagicMock()
    response.json.return_value = [
        {
            "name": "New Card 0",
            constants.DATA_FIELD_17LANDS_DICT[constants.DATA_FIELD_GIHWR]: 0.625,
        }
    ]
    mock_get.side_effect = [response] + [RuntimeError("Request failed")] * (
        constants.CARD_RATINGS_ATTEMPT_MAX
    )

    success, message, _database_size = local_set_extractor.download_card_data(0)

    assert not success
    assert "17Lands" in message
    assert not local_set_extractor.combined_data.get("card_ratings")


@patch("src.seventeenlands.requests.get")
def test_download_without_local_cards_still_fails(mock_get, local_set_extractor):
    with patch.object(
        local_set_extractor,
        "_retrieve_local_arena_data",
        return_value=(False, "Unable to access local Arena data", 0),
    ):
        success, message, database_size = local_set_extractor.download_card_data(0)

    assert not success
    assert "local Arena data" in message
    assert database_size == 0
    mock_get.assert_not_called()


@patch("src.seventeenlands.requests.get", side_effect=RuntimeError("Request failed"))
def test_color_ratings_failure_resets_optional_statistics(mock_get, local_set_extractor):
    local_set_extractor.set_game_count(500)
    local_set_extractor.set_color_ratings({"W": 55.0})

    assert local_set_extractor.retrieve_17lands_color_ratings() == (False, 0)

    assert local_set_extractor.combined_data["color_ratings"] == {}
    assert local_set_extractor.combined_data["meta"]["game_count"] == 0


@pytest.mark.parametrize("arena_codes", [["HOB"], [constants.SET_SELECTION_ALL]])
@patch("src.seventeenlands.requests.get")
def test_local_dataset_is_saved_without_network(mock_get, arena_codes, local_set_extractor, tmp_path):
    local_set_extractor.selected_sets.arena = arena_codes
    local_set_extractor.set_game_count(500)
    local_set_extractor.set_color_ratings({"W": 55.0})
    local_set_extractor.card_ratings = {"stale": {}}

    success, message, size = local_set_extractor.download_local_card_data(0)
    assert success, message
    assert size == 123
    filename = local_set_extractor.export_card_data()
    assert filename
    loaded = Dataset()
    assert loaded.open_file(str(tmp_path / filename)) == Result.VALID
    assert len(loaded.get_card_ratings()) == 100
    assert loaded.get_names_by_id([100000]) == ["New Card 0"]
    assert loaded.get_color_ratings() == {}
    assert local_set_extractor.combined_data["meta"]["game_count"] == 0
    assert loaded.get_data_by_id([100000])[0]["deck_colors"]["All Decks"]["gihwr"] == 0.0
    mock_get.assert_not_called()


@patch("src.seventeenlands.requests.get")
def test_local_dataset_rejects_unknown_card_pool(mock_get, local_set_extractor):
    local_set_extractor.select_sets(SetInfo(arena=[constants.SET_SELECTION_ALL], seventeenlands=["Cube"]))
    success, _, _ = local_set_extractor.download_local_card_data(0)
    assert not success
    assert not local_set_extractor.combined_data.get("card_ratings")
    mock_get.assert_not_called()


@pytest.mark.parametrize("failure", ["invalid", "write", "replace"])
def test_failed_export_preserves_saved_cards(local_set_extractor, tmp_path, failure):
    success, _, _ = local_set_extractor.download_local_card_data(0)
    assert success
    filename = local_set_extractor.export_card_data()
    saved_path = tmp_path / filename
    original = saved_path.read_bytes()
    before = set(tmp_path.iterdir())
    if failure == "invalid":
        local_set_extractor.combined_data["card_ratings"] = {}
        assert local_set_extractor.export_card_data() == ""
    elif failure == "write":
        with patch("src.file_extractor.json.dump", side_effect=OSError("Disk full")):
            assert local_set_extractor.export_card_data() == ""
    else:
        with patch("src.file_extractor.os.replace", side_effect=PermissionError("Locked file")):
            assert local_set_extractor.export_card_data() == ""
    assert saved_path.read_bytes() == original
    assert set(tmp_path.iterdir()) == before
    loaded = Dataset()
    assert loaded.open_file(str(saved_path)) == Result.VALID
    assert loaded.get_names_by_id([100000]) == ["New Card 0"]


def test_invalid_initial_export_leaves_no_dataset(local_set_extractor, tmp_path):
    before = set(tmp_path.iterdir())
    local_set_extractor.combined_data["card_ratings"] = {}
    assert local_set_extractor.export_card_data() == ""
    assert set(tmp_path.iterdir()) == before
