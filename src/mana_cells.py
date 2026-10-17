"""Mana images for Top Color cells in Tk treeviews."""
from pathlib import Path
import tkinter
from PIL import Image, ImageTk


class ManaCells:
    def __init__(self, table, columns, size):
        self.table = table
        self.columns = columns
        self.size = size
        self.labels = {}
        self.images = {}
        self.job = None
        self.refresh()

    def close(self):
        if self.job is not None:
            self.table.after_cancel(self.job)
            self.job = None
        for label in self.labels.values():
            label.destroy()
        self.labels.clear()

    def pair_image(self, pair):
        if pair not in self.images:
            image = Image.new("RGBA", (self.size * 2 + 2, self.size))
            for index, color in enumerate(pair):
                with Image.open(Path(__file__).resolve().parent.parent / "assets" / "mana" / f"{color}.png") as icon:
                    icon = icon.resize((self.size, self.size), Image.Resampling.LANCZOS)
                    image.alpha_composite(icon, (index * (self.size + 2), 0))
            self.images[pair] = ImageTk.PhotoImage(image, master=self.table)
        return self.images[pair]

    def refresh(self):
        self.job = None
        if not self.table.winfo_exists():
            return
        visible = set()
        for row in self.table.get_children():
            for column in self.columns:
                box = self.table.bbox(row, column)
                pair = self.table.set(row, column)
                if not box or len(pair) != 2 or not set(pair) <= set("WUBRG"):
                    continue
                key = (row, column)
                visible.add(key)
                label = self.labels.get(key)
                if label is None:
                    label = tkinter.Label(self.table, borderwidth=0, highlightthickness=0)
                    self.labels[key] = label
                    for sequence in ("<ButtonPress-1>", "<ButtonRelease-1>", "<Motion>", "<MouseWheel>"):
                        def forward(event, sequence=sequence):
                            options = dict(x=event.x_root - self.table.winfo_rootx(),
                                           y=event.y_root - self.table.winfo_rooty())
                            if sequence == "<MouseWheel>":
                                options["delta"] = event.delta
                            self.table.event_generate(sequence, **options)
                        label.bind(sequence, forward)
                tags = self.table.item(row, "tags")
                background = "#3d3d3d"
                for tag in tags:
                    background = self.table.tag_configure(tag, "background") or background
                if row in self.table.selection():
                    from tkinter.ttk import Style
                    background = Style(self.table).lookup(self.table.cget("style"), "background", ("selected",)) or background
                label.configure(image=self.pair_image(pair), background=background)
                x, y, width, height = box
                label.place(x=x, y=y, width=width, height=height)
        for key in self.labels.keys() - visible:
            self.labels.pop(key).destroy()
        self.job = self.table.after(80, self.refresh)
