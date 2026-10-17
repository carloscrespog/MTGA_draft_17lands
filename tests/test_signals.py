import pytest
from unittest.mock import MagicMock
from src.signals import SignalCalculator
from src import constants


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # get_metrics returns (mean, std)
    metrics.get_metrics.return_value = (55.0, 0.0)
    return metrics


def test_signal_calculation_logic(mock_metrics):
    calculator = SignalCalculator(mock_metrics)

    # Current Pick: 5
    current_pick = 5

    # 1. Good Card, Late (Signal!)
    # White Card: 60% WR (5% > Avg), ATA 2.0 (3 picks late)
    # Score = 3.0 * 5.0 = 15.0
    card_signal = {
        constants.DATA_FIELD_COLORS: ["W"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 60.0,
                constants.DATA_FIELD_ATA: 2.0,
            }
        },
    }

    # 2. Bad Card, Late (Noise - Should be ignored)
    # Blue Card: 50% WR (5% < Avg), ATA 2.0
    card_bad = {
        constants.DATA_FIELD_COLORS: ["U"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 50.0,
                constants.DATA_FIELD_ATA: 2.0,
            }
        },
    }

    # 3. Good Card, Early (Normal - Should be ignored)
    # Red Card: 60% WR, ATA 7.0 (Seen at pick 5, so it's early/on time)
    card_early = {
        constants.DATA_FIELD_COLORS: ["R"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 60.0,
                constants.DATA_FIELD_ATA: 7.0,
            }
        },
    }

    # 4. Multi-Color Good Card, Late
    # Green/Black: 57% WR (2% > Avg), ATA 4.0 (1 pick late)
    # Score = 1.0 * 2.0 = 2.0 (Added to G and B)
    card_gold = {
        constants.DATA_FIELD_COLORS: ["G", "B"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 57.0,
                constants.DATA_FIELD_ATA: 4.0,
            }
        },
    }

    pack = [card_signal, card_bad, card_early, card_gold]

    scores = calculator.calculate_pack_signals(pack, current_pick)

    # Assertions
    assert scores["W"] == 15.0
    assert scores["U"] == 0.0  # Bad card ignored
    assert scores["R"] == 0.0  # Early card ignored
    assert scores["G"] == 2.0  # Gold card contribution
    assert scores["B"] == 2.0  # Gold card contribution


def test_pair_signals_use_each_pairs_rate_and_llu_ata(mock_metrics):
    calculator = SignalCalculator(mock_metrics)
    cards = [{"name": "Card", "deck_colors": {"All Decks": {"ata": 8}}}]
    stats = {"Card": {"ata": 2, "pairs": {
        "WU": {"gihWr": 0.60}, "UB": {"gihWr": 0.57},
        "BR": {"gihWr": 0.50}, "RG": {"gihWr": None}}}}
    scores = calculator.calculate_pack_pair_signals(cards, 5, stats)
    assert scores["WU"] == pytest.approx(15)
    assert scores["UB"] == pytest.approx(6)
    assert scores["BR"] == scores["RG"] == 0
    assert len(scores) == 10
    assert not any(calculator.calculate_pack_pair_signals(cards, 2, stats).values())


def test_pair_signals_fallback_and_invalid_data(mock_metrics):
    calculator = SignalCalculator(mock_metrics)
    cards = [{"name": "Card", "deck_colors": {
        "All Decks": {"ata": 2}, "UW": {"gihwr": 59},
        "UB": {"gihwr": 58}, "BR": {"gihwr": float("nan")}}},
        {"name": "Missing"},
        {"name": "Invalid", "deck_colors": {"All Decks": {"ata": float("nan")}}}]
    stats = {"Card": {"pairs": {"WU": {"gihWr": None}, "UB": {"gihWr": 0}}}}
    scores = calculator.calculate_pack_pair_signals(cards, 5, stats)
    assert scores["WU"] == 12
    assert scores["UB"] == 0  # A real zero is not missing data.
    assert scores["BR"] == 0


def test_pair_signal_display_accumulates_p1_p3_and_clears(mock_metrics):
    from src.overlay import Overlay

    overlay = MagicMock()
    overlay.set_metrics = mock_metrics
    overlay.tier_data = {}
    overlay.draft.set_data.get_color_ratings.return_value = {}
    overlay.draft.retrieve_draft_history.return_value = [
        {"Pack": 1, "Pick": 5, "Cards": [1]},
        {"Pack": 2, "Pick": 10, "Cards": [1]},
        {"Pack": 3, "Pick": 6, "Cards": [1]},
    ]
    overlay.draft.set_data.get_data_by_id.return_value = [
        {"name": "Card", "deck_colors": {"All Decks": {"ata": 2}, "WU": {"gihwr": 60}}}
    ]
    Overlay._Overlay__update_signals(overlay)
    rows = [call.kwargs["values"] for call in overlay.pair_signal_table.insert.call_args_list]
    assert rows[0] == ("WU", "35.0")
    assert len(rows) == 10
    assert overlay.draft.set_data.get_data_by_id.call_count == 2
    overlay.draft.retrieve_draft_history.return_value = []
    overlay.pair_signal_table.get_children.return_value = ["old"]
    Overlay._Overlay__update_signals(overlay)
    overlay.pair_signal_table.config.assert_called_with(height=0)
    overlay.pair_signal_table.delete.assert_called_with("old")


def test_pair_signals_normalize_against_deck_win_rates(mock_metrics):
    calculator = SignalCalculator(mock_metrics, {"UW": 58, "UB": 53, "BR": 0})
    cards = [{"name": "Card", "deck_colors": {"All Decks": {"ata": 2}}}]
    stats = {"Card": {"pairs": {pair: {"gihWr": 0.57}
                                for pair in ("WU", "UB", "BR", "RG")}}}
    scores = calculator.calculate_pack_pair_signals(cards, 5, stats)
    assert scores["WU"] == 0
    assert scores["UB"] == pytest.approx(12)
    assert scores["BR"] == pytest.approx(6)
    assert scores["RG"] == pytest.approx(6)
