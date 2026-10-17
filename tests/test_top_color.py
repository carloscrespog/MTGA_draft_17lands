from src.card_logic import CardResult
from src.tier_list import TierList
from src import constants


def test_top_color_uses_llu_pairs_ignores_null_and_retains_zero():
    card = {"name": "Card", "deck_colors": {"WU": {"gihwr": 99}}}
    tier = TierList(card_stats={"cards": {"Card": {"pairs": {
        "WU": {"gihWr": None}, "UB": {"gihWr": 0.57}, "BG": {"gihWr": 0.61}}}}})
    results = CardResult(None, {"TIER0": tier}, None, 0)
    assert results.return_results([card], ["WU"], [constants.DATA_FIELD_TOP_COLOR])[0]["results"] == ["BG"]
    tier.card_stats["cards"]["Card"]["pairs"] = {"UB": {"gihWr": 0.0}}
    assert results.return_results([card], [], [constants.DATA_FIELD_TOP_COLOR])[0]["results"] == ["UB"]


def test_top_color_fallback_and_no_data():
    results = CardResult(None, {}, None, 0)
    cards = [{"name": "Card", "deck_colors": {"All Decks": {"gihwr": 70},
              "WU": {"gihwr": 54}, "BR": {"gihwr": 58}}}, {"name": "Missing"}]
    assert [card["results"] for card in results.return_results(cards, [], [constants.DATA_FIELD_TOP_COLOR])] == [["BR"], [""]]
