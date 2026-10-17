from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch
import tkinter

from src.overlay import CreateCardToolTip, Overlay
from src import constants


def test_tooltip_displays_every_non_null_pair_and_both_flags(caplog):
    pairs = {pair: {"gihWr": 0.6 - index / 100} for index, pair in enumerate(
        ["WU", "UB", "BR", "RG", "WG", "WB", "UR", "BG", "WR", "UG"])}
    pairs["UG"]["gihWr"] = None
    pairs["WR"]["gihWr"] = 0.0
    with ExitStack() as stack:
        for name in ("tkinter.Toplevel", "tkinter.Frame", "tkinter.LabelFrame",
                     "tkinter.Label", "ImageTk.PhotoImage", "Style"):
            stack.enter_context(patch("src.overlay." + name))
        labels = stack.enter_context(patch("src.overlay.Label"))
        stack.enter_context(patch("src.overlay.identify_safe_coordinates", return_value=(0, 0)))
        tooltip = CreateCardToolTip(Mock(), Mock(), "Card", {}, [], False, 100,
                                    {"All.TableRow": "font"}, {}, [],
                                    {"synergy": True, "buildaround": True,
                                     "stats": {"pairs": pairs}})
        tooltip.position_near_cursor = Mock()
        tooltip._create_header = Mock()
        tooltip._CreateCardToolTip__format_stats_data = Mock(return_value=({}, 300, []))
        tooltip._CreateCardToolTip__display_tooltip()
    assert sum("image" in call.kwargs for call in labels.call_args_list) == 18
    texts = [call.kwargs.get("text", "") for call in labels.call_args_list]
    percentages = [text.strip() for text in texts if text.strip().endswith("%")]
    assert percentages == [f"{(0.6 - i / 100) * 100:.1f}%" for i in range(8)] + ["0.0%"]
    assert "\U0001f91d Synergy   \U0001f6e0\ufe0f Buildaround" in texts
    assert not [record for record in caplog.records if record.levelname == "ERROR"]


def test_hover_tracks_row_without_changing_selection_and_closes_previous_popup():
    app = Overlay.__new__(Overlay)
    app.tier_data = {}
    app.scale_factor = 100
    app.fonts_dict = {}
    app.configuration = Mock()
    app.configuration.settings.result_format = constants.RESULT_FORMAT_WIN_RATE
    app.draft = Mock()
    app.draft.set_data.get_card_archetypes_by_field.return_value = []
    table = Mock()
    table.identify_row.return_value = "row1"
    table.item.return_value = ["Card"]
    event = SimpleNamespace(type=tkinter.EventType.Motion, y=25)
    card = {constants.DATA_FIELD_NAME: "Card", constants.DATA_SECTION_IMAGES: []}
    with patch("src.overlay.CreateCardToolTip") as popup:
        app._Overlay__process_table_click(event, table, [card], [])
        popup.assert_not_called()
        event.type = tkinter.EventType.ButtonRelease
        app._Overlay__process_table_click(event, table, [card], [])
        event.type = tkinter.EventType.Motion
        app._Overlay__process_table_click(event, table, [card], [])
        assert popup.call_count == 1
        table.selection.assert_not_called()
        table.selection_set.assert_not_called()
        table.identify_row.return_value = ""
        app._Overlay__process_table_click(event, table, [card], [])
        popup.return_value.close.assert_called_once()


def test_popup_position_uses_cursor_monitor_and_actual_size():
    tooltip = CreateCardToolTip.__new__(CreateCardToolTip)
    tooltip.scale_factor = 1
    tooltip.widget = Mock()
    tooltip.widget.winfo_pointerxy.return_value = (2400, 700)
    tooltip.tw = Mock()
    tooltip.tw.winfo_reqwidth.return_value = 700
    tooltip.tw.winfo_reqheight.return_value = 500
    def monitor_info(handle, info_pointer):
        info = info_pointer._obj
        info.rcWork.left, info.rcWork.top = 1920, 0
        info.rcWork.right, info.rcWork.bottom = 3840, 1080
        return 1

    with patch("src.overlay.sys.platform", "win32"), patch("ctypes.windll") as dll:
        dll.user32.GetMonitorInfoW.side_effect = monitor_info
        tooltip.position_near_cursor()
    tooltip.tw.wm_geometry.assert_called_once_with("+2416+580")


def test_pending_image_does_not_block_popup_and_stops_after_close():
    tooltip = CreateCardToolTip.__new__(CreateCardToolTip)
    tooltip.widget = Mock()
    tooltip.tw = Mock()
    tooltip._image_executor = Mock()
    tooltip._image_cache = {}
    pending = tooltip._image_executor.submit.return_value
    pending.done.return_value = False
    label = Mock()
    tooltip._load_card_image(label, "https://example.com/card.jpg", (280, 380))
    pending.result.assert_not_called()
    label.configure.assert_not_called()
    tooltip.widget.after.assert_called_once()
    finish = tooltip.widget.after.call_args.args[1]
    tooltip.tw = None
    finish()
    assert tooltip.widget.after.call_count == 1
    pending.result.assert_not_called()
