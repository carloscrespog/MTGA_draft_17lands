"""Regression coverage for discovering LLU lists from the published website."""
from unittest.mock import Mock, patch

import pytest
import requests

from src.limited_levelups import discover_tier_list_ids


ORIGIN = "https://limitedlevelups.com"
PAGE = f"{ORIGIN}/tier-list/OTJ"
ASSET = f"{ORIGIN}/assets/index-new-deployment.js"
ALEX_ID = "df75c79fba154f21b4a8bf751b8aa0a4"
MARC_ID = "317fe1336cac48c8b3a2d731a844ccbe"
PRIMARY_ID = "0123456789abcdef0123456789abcdef"
OTHER_ID = "ffffffffffffffffffffffffffffffff"
HTML = '<html><script type="module" crossorigin src="/assets/index-new-deployment.js"></script></html>'
OTJ_BUNDLE = (
    'const graders={OTJ:[{name:"Alex",uid:"' + ALEX_ID
    + '"},{name:"Marc",uid:"' + MARC_ID + '"}]};'
)


def response_with_text(text):
    return Mock(text=text)


def test_discovers_both_otj_lists_from_current_html_asset():
    """Each deployment's script URL is discovered from the requested set page."""
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(HTML), response_with_text(OTJ_BUNDLE)],
    ) as get:
        result = discover_tier_list_ids(" otj ")

    assert result == [ALEX_ID, MARC_ID]
    assert [call.args[0] for call in get.call_args_list] == [PAGE, ASSET]
    for call in get.call_args_list:
        assert call.kwargs["timeout"] == 10
    assert get.call_args_list[1].kwargs["headers"]["referer"] == PAGE


def test_primary_list_precedes_graders_even_when_declared_later():
    """Sets with a current primary list still expose both authors' review lists."""
    bundle = OTJ_BUNDLE + 'const primary={OTJ:"' + PRIMARY_ID + '"};'
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(HTML), response_with_text(bundle)],
    ):
        assert discover_tier_list_ids("OTJ") == [PRIMARY_ID, ALEX_ID, MARC_ID]


def test_single_list_set_is_discovered_without_static_configuration():
    page = f"{ORIGIN}/tier-list/Y24OTJ"
    bundle = 'const primary={Y24OTJ:"' + PRIMARY_ID + '"};'
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(HTML), response_with_text(bundle)],
    ) as get:
        assert discover_tier_list_ids("y24otj") == [PRIMARY_ID]
    assert get.call_args_list[0].args[0] == page


def test_discovery_only_returns_the_requested_sets_ids():
    bundle = (
        'const primary={Y24OTJ:"' + OTHER_ID + '",MKM:"' + OTHER_ID + '"};'
        'const sets={OTJ:{name:"Outlaws of Thunder Junction",image:"' + OTHER_ID + '"}};'
        'const graders={MKM:[{name:"Other",uid:"' + OTHER_ID + '"}],'
        'OTJ:[{name:"Alex",uid:"' + ALEX_ID + '"}],'
        'OTJX:[{name:"Other",uid:"' + OTHER_ID + '"}]};'
    )
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(HTML), response_with_text(bundle)],
    ):
        assert discover_tier_list_ids("OTJ") == [ALEX_ID]


def test_supports_quoted_keys_single_quotes_and_whitespace():
    html = "<script src='/assets/index-new-deployment.js' crossorigin type='module'></script>"
    bundle = (
        "const primary = { 'OTJ' : '" + PRIMARY_ID + "' };\n"
        "const graders = { \"OTJ\" : [\n"
        " { 'name' : 'Alex', 'uid' : '" + ALEX_ID + "' },\n"
        " { \"name\" : \"Marc\", \"uid\" : \"" + MARC_ID + "\" }\n"
        "] };"
    )
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(html), response_with_text(bundle)],
    ):
        assert discover_tier_list_ids("OTJ") == [PRIMARY_ID, ALEX_ID, MARC_ID]


def test_deduplicates_script_urls_and_tier_list_ids():
    second_asset = f"{ORIGIN}/assets/tier-config.js"
    html = (
        HTML
        + '<script type="module" src="/assets/index-new-deployment.js"></script>'
        + '<script type="module" src="/assets/tier-config.js"></script>'
    )
    first_bundle = 'const primary={OTJ:"' + ALEX_ID + '"};' + OTJ_BUNDLE
    second_bundle = 'const repeated={OTJ:"' + ALEX_ID + '"};' + OTJ_BUNDLE
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[
            response_with_text(html),
            response_with_text(first_bundle),
            response_with_text(second_bundle),
        ],
    ) as get:
        assert discover_tier_list_ids("OTJ") == [ALEX_ID, MARC_ID]
    assert [call.args[0] for call in get.call_args_list] == [PAGE, ASSET, second_asset]


def test_ignores_nonmodule_and_external_scripts():
    html = (
        '<script src="/assets/unrelated.js"></script>'
        '<script type="module" src="https://other.example/tier-list.js"></script>'
        + HTML
    )
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(html), response_with_text(OTJ_BUNDLE)],
    ) as get:
        assert discover_tier_list_ids("OTJ") == [ALEX_ID, MARC_ID]
    assert [call.args[0] for call in get.call_args_list] == [PAGE, ASSET]


@pytest.mark.parametrize("set_code", ["", " ", "O", "ABCDEFGHIJK", "../OTJ", "OTJ?x=1", "OTJ/evil", "OTJ;alert(1)"])
def test_invalid_set_codes_are_rejected_before_network_access(set_code):
    with patch("src.limited_levelups.requests.get") as get:
        with pytest.raises(ValueError):
            discover_tier_list_ids(set_code)
    get.assert_not_called()


def test_missing_module_script_is_reported():
    with patch(
        "src.limited_levelups.requests.get",
        return_value=response_with_text('<html><script src="/legacy.js"></script></html>'),
    ) as get:
        with pytest.raises(ValueError):
            discover_tier_list_ids("OTJ")
    get.assert_called_once()


def test_missing_set_is_reported_instead_of_importing_other_sets():
    bundle = 'const primary={MKM:"' + OTHER_ID + '"};const metadata={OTJ:{name:"Outlaws"}};'
    with patch(
        "src.limited_levelups.requests.get",
        side_effect=[response_with_text(HTML), response_with_text(bundle)],
    ):
        with pytest.raises(ValueError):
            discover_tier_list_ids("OTJ")


@pytest.mark.parametrize("failure_stage", ["page", "script"])
def test_http_failures_propagate(failure_stage):
    failure = requests.HTTPError("503 Service Unavailable")
    failed_response = response_with_text(HTML if failure_stage == "page" else OTJ_BUNDLE)
    failed_response.raise_for_status.side_effect = failure
    responses = [failed_response] if failure_stage == "page" else [response_with_text(HTML), failed_response]
    with patch("src.limited_levelups.requests.get", side_effect=responses):
        with pytest.raises(requests.HTTPError) as caught:
            discover_tier_list_ids("OTJ")
    assert caught.value is failure
