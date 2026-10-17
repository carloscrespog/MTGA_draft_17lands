from unittest.mock import Mock, patch
from src.mana_cells import ManaCells


def test_mana_cells_draw_pair_and_remove_when_row_disappears():
    table = Mock()
    table.get_children.return_value = ("row",)
    table.bbox.return_value = (10, 20, 60, 24)
    table.set.return_value = "UB"
    table.item.return_value = ("normal",)
    table.tag_configure.return_value = "#333333"
    table.selection.return_value = ()
    with patch("src.mana_cells.tkinter.Label") as label, patch("src.mana_cells.ImageTk.PhotoImage") as photo:
        cells = ManaCells(table, ["Column7"], 18)
        image = photo.call_args.args[0]
        assert image.size == (38, 18)
        label.return_value.configure.assert_called_with(image=photo.return_value, background="#333333")
        label.return_value.place.assert_called_with(x=10, y=20, width=60, height=24)
        table.get_children.return_value = ()
        cells.refresh()
        label.return_value.destroy.assert_called_once()
        cells.close()
        table.after_cancel.assert_called_once()
