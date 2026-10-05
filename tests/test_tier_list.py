import json
import tkinter
from unittest.mock import Mock, patch

import pytest
import requests

from src.constants import LETTER_GRADE_NA
from src.tier_list import Meta, Rating, TierList, TierWindow, TIER_URL_LLU


ALEX_ID = 'df75c79fba154f21b4a8bf751b8aa0a4'
MARC_ID = '317fe1336cac48c8b3a2d731a844ccbe'
HOB_ID = '528d1c45d1f04b59abac2a897a8928c8'
PAGE = 'https://limitedlevelups.com/tier-list/OTJ'
ASSET = 'https://limitedlevelups.com/assets/index-new-hash.js'


def response(data=None, text=''):
    result = Mock(text=text)
    result.json.return_value = data
    return result


def payload(name='LLU Alex', expansion='OTJ'):
    return {
        'name': name,
        'expansion': expansion,
        'ratings': [{'name': 'Test Card', 'tier': 'B', 'comment': 'Useful comment'}],
    }


def otj_responses():
    return [
        response(text='<script type="module" crossorigin src="/assets/index-new-hash.js"></script>'),
        response(text='const lists={OTJ:[{name:"Alex",uid:"' + ALEX_ID + '"},{name:"Marc",uid:"' + MARC_ID + '"}]};'),
        response(payload()),
        response(payload('LLU Marc')),
    ]


def saved_tier(source_id, name):
    return TierList(
        meta=Meta(label=name, set='OTJ', url=TIER_URL_LLU + source_id),
        ratings={'Old Card': Rating(rating='C ')},
    )


def test_from_limited_levelups_api_uses_discovered_url_and_referer():
    responses = [
        response(text='<script type="module" src="/assets/current.js"></script>'),
        response(text='const lists={HOB:"' + HOB_ID + '"};'),
        response(payload('Marc set review HOB tierlist', 'HOB')),
    ]
    with patch('src.tier_list.requests.get', side_effect=responses) as get:
        tier_list = TierList.from_limited_levelups_api(' hob ')

    assert tier_list.meta.set == 'HOB'
    assert tier_list.ratings['Test Card'].rating == 'B '
    assert len(get.call_args_list) == 3
    assert get.call_args.args[0] == TIER_URL_LLU + HOB_ID
    assert get.call_args.kwargs['headers']['referer'] == 'https://limitedlevelups.com/tier-list/HOB'


def test_full_otj_update_fetches_both_lists_and_reuses_files(tmp_path):
    selected = tmp_path / 'Tier_OTJ_existing.txt'
    selected.write_text('existing data', encoding='utf-8')
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses() + otj_responses()
    ) as get:
        assert TierList.update_limited_levelups(' otj ', selected.name)
        assert TierList.update_limited_levelups('OTJ', selected.name)
        assert len(TierList.retrieve_files('OTJ')) == 2
        data, options = TierList.retrieve_data('OTJ')

    assert [call.args[0] for call in get.call_args_list[:4]] == [
        PAGE, ASSET, TIER_URL_LLU + ALEX_ID, TIER_URL_LLU + MARC_ID,
    ]
    for call in get.call_args_list:
        assert call.kwargs['headers']['referer'] == PAGE
        assert call.kwargs['timeout'] == 10
    assert {tier.meta.label for tier in data.values()} == {'LLU Alex', 'LLU Marc'}
    assert len(options) == 2
    assert {file.name for file in tmp_path.iterdir()} == {selected.name, f'Tier_OTJ_{MARC_ID}.txt'}
    assert json.loads(selected.read_text())['meta']['url'] == TIER_URL_LLU + ALEX_ID
    assert json.loads(selected.read_text())['ratings']['Test Card']['comment'] == 'Useful comment'


def test_update_limited_levelups_replaces_selected_filename(tmp_path):
    tier = TierList(
        meta=Meta(label='SOS set review', set='SOS', url=TIER_URL_LLU + HOB_ID),
        ratings={'Test Card': Rating(rating='B ', comment='')},
    )
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.TierList.from_limited_levelups_apis', return_value=[tier]
    ):
        assert TierList.update_limited_levelups('SOS', 'Tier_SOS_existing.txt')
    data = json.loads((tmp_path / 'Tier_SOS_existing.txt').read_text())
    assert data['meta']['set'] == 'SOS'
    assert data['ratings']['Test Card']['rating'] == 'B '


def test_selecting_marc_preserves_author_and_updates_existing_alex_file(tmp_path):
    selected = tmp_path / 'Tier_OTJ_marc.txt'
    alex = tmp_path / 'Tier_OTJ_alex.txt'
    saved_tier(MARC_ID, 'Old Marc').to_file(str(selected))
    saved_tier(ALEX_ID, 'Old Alex').to_file(str(alex))
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses()
    ):
        assert TierList.update_limited_levelups('OTJ', selected.name)
    assert json.loads(selected.read_text())['meta']['label'] == 'LLU Marc'
    assert json.loads(alex.read_text())['meta']['label'] == 'LLU Alex'
    assert len(list(tmp_path.iterdir())) == 2


def test_existing_17lands_source_id_is_reused(tmp_path):
    existing = saved_tier(MARC_ID, 'Marc review')
    existing.meta.url = 'https://www.17lands.com/tier_list/' + MARC_ID
    selected = tmp_path / 'Tier_OTJ_17lands.txt'
    existing.to_file(str(selected))
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses()
    ):
        assert TierList.update_limited_levelups('OTJ', selected.name)
    assert json.loads(selected.read_text())['meta']['url'] == TIER_URL_LLU + MARC_ID
    assert (tmp_path / f'Tier_OTJ_{ALEX_ID}.txt').is_file()
    assert len(list(tmp_path.iterdir())) == 2


def test_refresh_from_unrelated_row_does_not_duplicate_existing_sources(tmp_path):
    selected = tmp_path / 'Tier_OTJ_custom.txt'
    original = saved_tier('0' * 32, 'Custom tier')
    original.to_file(str(selected))
    before = selected.read_bytes()
    for source_id, name in [(ALEX_ID, 'Alex'), (MARC_ID, 'Marc')]:
        saved_tier(source_id, name).to_file(str(tmp_path / f'Tier_OTJ_{source_id}.txt'))
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses()
    ):
        assert TierList.update_limited_levelups('OTJ', selected.name)
    assert selected.read_bytes() == before
    assert len(list(tmp_path.iterdir())) == 3


def test_update_without_selected_filename_creates_stable_files(tmp_path):
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses() + otj_responses()
    ):
        assert TierList.update_limited_levelups('OTJ')
        assert TierList.update_limited_levelups('OTJ')
    assert {file.name for file in tmp_path.iterdir()} == {
        f'Tier_OTJ_{ALEX_ID}.txt', f'Tier_OTJ_{MARC_ID}.txt',
    }


@pytest.mark.parametrize('failed_stage', [0, 1, 2, 3])
def test_network_failure_preserves_existing_files(tmp_path, failed_stage):
    selected = tmp_path / 'Tier_OTJ_existing.txt'
    selected.write_bytes(b'existing data')
    responses = otj_responses()
    responses[failed_stage].raise_for_status.side_effect = requests.HTTPError('503')
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=responses
    ):
        assert not TierList.update_limited_levelups('OTJ', selected.name)
    assert selected.read_bytes() == b'existing data'
    assert list(tmp_path.iterdir()) == [selected]


@pytest.mark.parametrize('invalid', [
    None, [], {'expansion': 'MKM', 'ratings': []}, {'expansion': 'OTJ'},
    {'expansion': 'OTJ', 'ratings': {}}, {'expansion': 'OTJ', 'ratings': []},
    {'expansion': 'OTJ', 'ratings': [None]},
    {'expansion': 'OTJ', 'ratings': [{'name': ['invalid'], 'tier': 'B'}]},
])
def test_invalid_second_payload_preserves_existing_file(tmp_path, invalid):
    selected = tmp_path / 'Tier_OTJ_existing.txt'
    selected.write_bytes(b'existing data')
    responses = otj_responses()
    responses[-1].json.return_value = invalid
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=responses
    ):
        assert not TierList.update_limited_levelups('OTJ', selected.name)
    assert selected.read_bytes() == b'existing data'
    assert list(tmp_path.iterdir()) == [selected]


def test_grade_normalization_preserves_comments_and_bonus_cards():
    responses = otj_responses()
    responses[2].json.return_value['ratings'] = [
        {'name': 'Bonus Card', 'expansion': 'BIG', 'tier': 'A', 'comment': 'Keep me'},
        {'name': 'Unknown', 'tier': 'invalid'},
        {'name': 'Unrated', 'tier': None},
        {'name': '', 'tier': 'B'},
    ]
    with patch('src.tier_list.requests.get', side_effect=responses):
        tier = TierList.from_limited_levelups_api('OTJ')
    assert tier.ratings['Bonus Card'] == Rating(rating='A ', comment='Keep me')
    assert tier.ratings['Unknown'].rating == LETTER_GRADE_NA
    assert tier.ratings['Unrated'].rating == LETTER_GRADE_NA
    assert '' not in tier.ratings


def test_staging_failure_preserves_selected_file_and_cleans_temporary_files(tmp_path):
    selected = tmp_path / 'Tier_OTJ_existing.txt'
    selected.write_bytes(b'existing data')
    with patch('src.tier_list.TIER_FOLDER', str(tmp_path)), patch(
        'src.tier_list.requests.get', side_effect=otj_responses()
    ), patch.object(TierList, 'to_file', side_effect=[True, False]):
        assert not TierList.update_limited_levelups('OTJ', selected.name)
    assert selected.read_bytes() == b'existing data'
    assert list(tmp_path.iterdir()) == [selected]


@pytest.mark.parametrize('succeeds', [True, False])
def test_update_button_allows_otj_and_restores_controls(succeeds):
    window = TierWindow.__new__(TierWindow)
    window.window = Mock()
    window._status_text = Mock()
    window._download_button = Mock()
    window._update_llu_button = Mock()
    window.update_callback = Mock()
    window._TierWindow__get_selected_tier_row = Mock(return_value=['otj', 'OTJ', '', 'Tier_OTJ_existing.txt'])
    window._TierWindow__update_tier_table = Mock()
    with patch.object(TierList, 'update_limited_levelups', return_value=succeeds) as update:
        window._TierWindow__update_limited_levelups_tier_list()
    update.assert_called_once_with('OTJ', 'Tier_OTJ_existing.txt')
    window._download_button.config.assert_called_with(state=tkinter.NORMAL)
    window._update_llu_button.config.assert_called_with(state=tkinter.NORMAL)
    assert window.update_callback.call_count == int(succeeds)
    assert window._TierWindow__update_tier_table.call_count == int(succeeds)
    assert ('updated' if succeeds else 'Failed') in window._status_text.set.call_args.args[0]
