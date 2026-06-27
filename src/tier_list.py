import tkinter
import requests
import os
import json
from datetime import datetime
from tkinter.ttk import Label, Button
from pydantic import BaseModel
from typing import Dict, Optional
from src.scaled_window import ScaledWindow, identify_safe_coordinates
from src.logger import create_logger
from src.constants import GRADE_ORDER_DICT, LETTER_GRADE_NA

# Constants for tier list storage and API
TIER_FOLDER = os.path.join(os.getcwd(), "Tier")
TIER_FILE_PREFIX = "Tier"
TIER_URL_17LANDS = "https://www.17lands.com/tier_list/"
TIER_URL_LLU_MSH = "https://limitedlevelups.com/api/tier-list/1c86af8656f7432c83d9f9bb9c92f9df"
TIER_FILE_LLU_MSH = "Tier_MSH_1782313253.txt"
TIER_VERSION = 3
LLU_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en;q=0.9,es;q=0.8,es-ES;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "referer": "https://limitedlevelups.com/tier-list/MSH",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
}

logger = create_logger()

# Ensure the tier folder exists
if not os.path.exists(TIER_FOLDER):
    os.makedirs(TIER_FOLDER)


def normalize_collection_date(date_str: str):
    """Return a normalized date string and sortable datetime for tier metadata."""
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            date_value = datetime.strptime(date_str, date_format)
            return date_value.strftime("%Y-%m-%d %H:%M:%S"), date_value
        except (TypeError, ValueError):
            continue
    return date_str, datetime.min

class Meta(BaseModel):
    """Metadata for a tier list."""
    collection_date: str = ""
    label: str = ""
    set: str = ""
    version: int = TIER_VERSION
    url: str = ""

class Rating(BaseModel):
    """Rating for a single card."""
    rating: str = ""
    comment: Optional[str] = None

class TierList(BaseModel):
    """Represents a tier list with metadata and card ratings."""
    meta: Meta = Meta()
    ratings: Dict[str, Rating] = {}

    @classmethod
    def from_api(cls, url: str):
        """Fetch a tier list from the 17Lands API."""
        try:
            if not url.startswith(TIER_URL_17LANDS):
                raise ValueError(f"URL must start with '{TIER_URL_17LANDS}'")
            code = url.split("/")[-1]
            api_url = f"https://www.17lands.com/data/tier_list/{code}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            meta = Meta(
                collection_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                label=data.get("name", ""),
                set=data.get("expansion", ""),
                version=TIER_VERSION,
                url=url
            )
            ratings = {}
            for card in data.get("ratings", []):
                name = card.get("name", "")
                tier = card.get("tier", "").ljust(2)
                if tier not in GRADE_ORDER_DICT:
                    tier = LETTER_GRADE_NA
                ratings[name] = Rating(
                    rating=tier,
                    comment=card.get("comment", "")
                )
            return cls(meta=meta, ratings=ratings)
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to fetch tier list from API: {e}")
            return None

    @classmethod
    def from_limited_levelups_api(cls, url: str = TIER_URL_LLU_MSH):
        """Fetch a tier list from the Limited Level-Ups API."""
        try:
            response = requests.get(url, headers=LLU_HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            meta = Meta(
                collection_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                label=data.get("name", ""),
                set=data.get("expansion", ""),
                version=TIER_VERSION,
                url=url
            )
            ratings = {}
            for card in data.get("ratings", []):
                name = card.get("name", "")
                if not name:
                    continue
                tier = card.get("tier", "").ljust(2)
                if tier not in GRADE_ORDER_DICT:
                    tier = LETTER_GRADE_NA
                ratings[name] = Rating(
                    rating=tier,
                    comment=card.get("comment", "")
                )
            return cls(meta=meta, ratings=ratings)
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to fetch tier list from Limited Level-Ups API: {e}")
            return None

    @classmethod
    def from_file(cls, file_path: str):
        """Load a tier list from a local file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = Meta(**data.get("meta", {}))
            ratings = {}
            for k, v in data.get("ratings", {}).items():
                rating_value = v.get("rating", "")
                if rating_value not in GRADE_ORDER_DICT:
                    rating_value = LETTER_GRADE_NA
                ratings[k] = Rating(rating=rating_value, comment=v.get("comment"))
            return cls(meta=meta, ratings=ratings)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Failed to load tier list from {file_path}: {e}")
            return None

    def to_file(self, file_path: str):
        """Save the tier list to a file in JSON format."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)
            return True
        except OSError as e:
            logger.error("Failed to save tier list to %s: %s", file_path, e)
            return False

    @classmethod
    def update_limited_levelups_msh(cls):
        """Update the local MSH tier file from the Limited Level-Ups API."""
        tier_list = cls.from_limited_levelups_api()
        if tier_list is None:
            return False

        file_path = os.path.join(TIER_FOLDER, TIER_FILE_LLU_MSH)
        return tier_list.to_file(file_path)

    @classmethod
    def retrieve_files(cls, code: str = ""):
        """
        Retrieve local tier list files, optionally filtered by set_code,
        and normalize date format.
        """
        file_list = []
        for file in os.listdir(TIER_FOLDER):
            file_location = os.path.join(TIER_FOLDER, file)
            try:
                name_segments = file.split("_")
                if len(name_segments) != 3 or name_segments[0] != TIER_FILE_PREFIX:
                    continue

                result = TierList.from_file(file_location)
                if not result:
                    logger.error(f"Invalid tier list at {file_location}")
                    continue

                if code and result.meta.set != code:
                    continue

                date_str, date_value = normalize_collection_date(
                    result.meta.collection_date
                )

                file_list.append((
                    result.meta.set,
                    result.meta.label,
                    date_str,
                    file,
                    date_value
                ))
            except Exception as error:
                logger.error(f"Failed to load tier list from {file_location}: {error}")
        file_list.sort(key=lambda x: x[4], reverse=True)
        file_list = [file[:4] for file in file_list]
        return file_list

    @classmethod
    def retrieve_data(cls, code: str):
        """
        Parse tier list files and return tier data and options.
        Returns:
            data (dict): label -> TierList
            options (dict): display string -> label
        """
        if not code:
            return {}, {}
        data = {}
        options = {}
        try:
            files = cls.retrieve_files(code)
            for idx, (_, _, _, filename) in enumerate(files):
                tier = TierList.from_file(os.path.join(TIER_FOLDER, filename))
                if not tier:
                    continue
                label = f"TIER{idx}"
                key = f"{label}: {tier.meta.label}"
                options[key] = label
                data[label] = tier
        except Exception as error:
            logger.error(f"Error in retrieve_tier_data: {error}")
        return data, options

class TierWindow(ScaledWindow):
    """Tkinter window for downloading and managing tier lists."""
    _instance_open = False

    def __init__(self, scale_factor: int, fonts_dict: Dict, update_callback=None):
        if TierWindow._instance_open:
            return
        TierWindow._instance_open = True
        super().__init__()
        self.scale_factor = scale_factor
        self.fonts_dict = fonts_dict
        self.update_callback = update_callback
        self.__enter()

    def __enter(self):
        """Initialize the window and its widgets."""
        self.window = tkinter.Toplevel()
        self.window.wm_title("Download Tier List")
        self.window.protocol("WM_DELETE_WINDOW", lambda window=self.window: self.__exit(window))
        self.window.resizable(width=False, height=True)
        self.window.attributes("-topmost", True)
        location_x, location_y = identify_safe_coordinates(
            self.window,
            self._scale_value(1000),
            self._scale_value(170),
            self._scale_value(250),
            self._scale_value(20)
        )
        self.window.wm_geometry(f"+{location_x}+{location_y}")

        tkinter.Grid.rowconfigure(self.window, 0, weight=1)

        try:
            headers = {
                "SET": {"width": .15, "anchor": tkinter.W},
                "LABEL": {"width": .30, "anchor": tkinter.W},
                "DOWNLOAD DATE/TIME": {"width": .25, "anchor": tkinter.CENTER},
                "FILE": {"width": .30, "anchor": tkinter.W},
            }

            # List box and scrollbar for displaying tier lists
            list_box_frame = tkinter.Frame(self.window)
            list_box_scrollbar = tkinter.Scrollbar(list_box_frame, orient=tkinter.VERTICAL)
            list_box_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
            self.list_box = self._create_header(
                "tier_list_table",
                list_box_frame,
                0,
                self.fonts_dict["Sets.TableRow"],
                headers,
                self._scale_value(700),
                True,
                True,
                "Set.Treeview",
                True
            )
            self.list_box.config(yscrollcommand=list_box_scrollbar.set)
            list_box_scrollbar.config(command=self.list_box.yview)

            # Entry fields and labels
            tier_label = Label(
                self.window,
                text="Label ",
                style="SetOptions.TLabel",
                anchor="e"
            )
            self._label_entry = tkinter.Entry(self.window)
            url_label = Label(
                self.window,
                text="URL ",
                style="SetOptions.TLabel",
                anchor="e"
            )
            self._url_entry = tkinter.Entry(self.window)
            self._status_text = tkinter.StringVar()
            self._status_label = Label(
                self.window,
                textvariable=self._status_text,
                style="Status.TLabel",
                anchor="c"
            )
            self._status_text.set("Retrieving Tier Lists")
            self._download_button = Button(
                self.window,
                command=self.__download_tier_list,
                text="DOWNLOAD"
            )
            self._update_llu_button = Button(
                self.window,
                command=self.__update_limited_levelups_tier_list,
                text="UPDATE MSH FROM LLU"
            )

            # Add placeholder text to the entry fields
            self.__add_placeholder(self._label_entry, "Enter Label Here!")
            self.__add_placeholder(self._url_entry, "https://www.17lands.com/tier_list/2b810f2420154ef9a11ad118fa7e4ae7")

            # Layout widgets
            list_box_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
            tier_label.grid(row=1, column=0, sticky="nsew")
            self._label_entry.grid(row=1, column=1, sticky="nsew")
            url_label.grid(row=2, column=0, sticky="nsew")
            self._url_entry.grid(row=2, column=1, sticky="nsew")
            self._download_button.grid(row=3, column=0, columnspan=2, sticky="nsew")
            self._update_llu_button.grid(row=4, column=0, columnspan=2, sticky="nsew")
            self._status_label.grid(row=5, column=0, columnspan=2, sticky="nsew")

            self.window.grid_columnconfigure(0, minsize=self._scale_value(80), weight=0)
            self.window.grid_columnconfigure(1, weight=1)

            self.list_box.pack(expand=True, fill="both")

            self.__update_tier_table()
            self._status_text.set("")
            self.window.update()
        except Exception as error:
            logger.error(error)

    def __exit(self, window):
        """Close the window and reset the singleton flag."""
        TierWindow._instance_open = False
        window.destroy()

    def __add_placeholder(self, entry, placeholder):
        """Add placeholder text to a Tkinter Entry widget."""
        if not hasattr(entry, "default_fg"):
            entry.default_fg = entry.cget("fg")

        def on_focus_in(event):
            if getattr(entry, "is_placeholder", False):
                entry.delete(0, tkinter.END)
                entry.config(fg=entry.default_fg)
                entry.is_placeholder = False

        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg='grey')
                entry.is_placeholder = True

        entry.insert(0, placeholder)
        entry.config(fg='grey')
        entry.is_placeholder = True
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def __download_tier_list(self):
        """Download a tier list from the API and save it locally."""
        try:
            self._status_text.set("Starting Download")
            self._download_button.config(state=tkinter.DISABLED)
            self.window.update()

            # Validate URL
            if not self._url_entry.get().startswith(TIER_URL_17LANDS) or self._url_entry.is_placeholder:
                self._status_text.set("Invalid URL")
                return
            # Validate label
            if not self._label_entry.get() or self._label_entry.is_placeholder:
                self._status_text.set("Invalid Label")
                return

            message_box = tkinter.messagebox.askyesno(
                title="Download",
                message="Make sure you also download the dataset so this application can read the Arena log.\n\n"
                "Would you like to continue downloading the tier list?"
            )
            if not message_box:
                self._status_text.set("Download Cancelled")
                return

            # Download the tier list from the API
            tier_list = TierList.from_api(self._url_entry.get())
            if tier_list is None:
                self._status_text.set("Failed to download tier list from API")
                return

            # Set the meta information
            tier_list.meta.label = self._label_entry.get()

            # Save the tier list to a file
            filename = f"{TIER_FILE_PREFIX}_{tier_list.meta.set}_{int(datetime.now().timestamp())}.txt"
            tier_list.to_file(os.path.join(TIER_FOLDER, filename))

            self.__update_tier_table()
            self.update_callback()
            self._status_text.set("Download Complete")
        except Exception as error:
            logger.error(f"Download Failed: {error}")
            self._status_text.set("Download Failed")
            return
        finally:
            self._download_button.config(state=tkinter.NORMAL)
            self.window.update()

    def __update_limited_levelups_tier_list(self):
        """Download the Limited Level-Ups MSH tier list and refresh the window."""
        try:
            self._status_text.set("Updating Limited Level-Ups Tier List")
            self._download_button.config(state=tkinter.DISABLED)
            self._update_llu_button.config(state=tkinter.DISABLED)
            self.window.update()

            if not TierList.update_limited_levelups_msh():
                self._status_text.set("Failed to update Limited Level-Ups tier list")
                return

            self.__update_tier_table()
            self.update_callback()
            self._status_text.set("Limited Level-Ups Tier List Updated")
        except Exception as error:
            logger.error(f"Limited Level-Ups tier list update failed: {error}")
            self._status_text.set("Limited Level-Ups Tier List Update Failed")
        finally:
            self._download_button.config(state=tkinter.NORMAL)
            self._update_llu_button.config(state=tkinter.NORMAL)
            self.window.update()

    def __update_tier_table(self):
        """Refresh the list of available tier lists in the UI."""
        # Delete the content of the list box
        self.list_box.delete(*self.list_box.get_children())
        self.window.update()

        # Retrieve the local tier lists
        file_list = TierList.retrieve_files()

        if file_list:
            self.list_box.config(height=min(len(file_list), 10))
        else:
            self.list_box.config(height=0)

        # Sort list by end date (descending)
        file_list.sort(key=lambda x: x[2], reverse=True)

        # Insert the sorted data into the list box
        for count, file in enumerate(file_list):
            row_tag = self._identify_table_row_tag(False, "", count)
            self.list_box.insert(
                "",
                index=count,
                iid=count,
                values=file,
                tag=(row_tag,)
            )
