import json
from unittest.mock import Mock, patch

from src.tier_list import Meta, Rating, TierList


def test_from_limited_levelups_api_uses_set_specific_url_and_referer():
    response = Mock()
    response.json.return_value = {
        "name": "Marc set review HOB tierlist",
        "expansion": "HOB",
        "ratings": [
            {
                "name": "Long-Bodied Grey Dog",
                "tier": "D+",
                "comment": "",
            }
        ],
    }

    with patch("src.tier_list.requests.get", return_value=response) as mock_get:
        tier_list = TierList.from_limited_levelups_api("hob")

    assert tier_list.meta.set == "HOB"
    assert tier_list.ratings["Long-Bodied Grey Dog"].rating == "D+"
    mock_get.assert_called_once()
    url = mock_get.call_args.args[0]
    headers = mock_get.call_args.kwargs["headers"]
    assert url.endswith("/528d1c45d1f04b59abac2a897a8928c8")
    assert headers["referer"] == "https://limitedlevelups.com/tier-list/HOB"


def test_update_limited_levelups_replaces_selected_filename(tmp_path):
    with patch("src.tier_list.TIER_FOLDER", str(tmp_path)), patch(
        "src.tier_list.TierList.from_limited_levelups_api",
        return_value=TierList(
            meta=Meta(label="Marc set review SOS tierlist", set="SOS"),
            ratings={"Test Card": Rating(rating="B ", comment="")},
        ),
    ):
        assert TierList.update_limited_levelups("SOS", "Tier_SOS_existing.txt")

    data = json.loads((tmp_path / "Tier_SOS_existing.txt").read_text())
    assert data["meta"]["set"] == "SOS"
    assert data["ratings"]["Test Card"]["rating"] == "B "
