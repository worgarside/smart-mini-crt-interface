"""
This module contains the class for controlling the CRT TV GUI
"""

from html import unescape
from io import BytesIO
from json import dumps
from logging import getLogger, DEBUG
from os import mkdir
from os.path import exists, join
from pathlib import Path
from re import compile as compile_regex
from tkinter import Label, Canvas, CENTER, Tk
from tkinter.font import Font

from PIL import Image, ImageTk
from dotenv import load_dotenv
from requests import get

from const import FH, SH

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
LOGGER.addHandler(FH)
LOGGER.addHandler(SH)


class CrtTv:
    """CRT TV class ofr controlling the GUI (not the power state)"""

    BG_COLOR = "#000000"
    STANDARD_ARGS = {"highlightthickness": 0, "bd": 0, "bg": BG_COLOR}
    CHAR_LIM = 31
    MAX_WAIT_TIME_MS = 10000
    ARTWORK_DIR = join(str(Path.home()), "crt_artwork")
    PATTERN = compile_regex(r"[^\w ]+")

    def __init__(self):
        if not exists(self.ARTWORK_DIR):
            mkdir(self.ARTWORK_DIR)

        self.artwork_path = None

        self.root = Tk()
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=self.BG_COLOR)

        crt_font = Font(family="Courier New", size=int(0.05 * self.screen_height))

        self.content_dict = {
            "images": {"tk_img": None, "artwork": ""},
            "widgets": {
                "canvas": Canvas(
                    self.root,
                    width=self.screen_width,
                    height=self.screen_height,
                    **self.STANDARD_ARGS,
                )
            },
            "coords": {
                "media_title": {
                    "x": 0.5 * self.screen_width,
                    "y": 0.8 * self.screen_height,
                    "anchor": CENTER,
                },
                "media_artist": {
                    "x": 0.5 * self.screen_width,
                    "y": 0.9 * self.screen_height,
                    "anchor": CENTER,
                },
            },
        }
        self.content_dict["widgets"]["canvas"].place(
            x=0, y=0, width=self.screen_width, height=self.screen_height
        )

        self.content_dict["widgets"]["artwork"] = Label(
            self.content_dict["widgets"]["canvas"], image="", **self.STANDARD_ARGS
        )

        self.content_dict["widgets"]["media_title"] = Label(
            self.content_dict["widgets"]["canvas"],
            text="",
            font=crt_font,
            fg="#ffffff",
            bg=self.BG_COLOR,
        )

        self.content_dict["widgets"]["media_artist"] = Label(
            self.content_dict["widgets"]["canvas"],
            text="",
            font=crt_font,
            fg="#ffffff",
            bg=self.BG_COLOR,
        )

        self.content_dict["widgets"]["artwork"].place(
            x=0.5 * self.screen_width,
            y=(0.5 * self.artwork_size) + (0.075 * self.screen_height),
            anchor=CENTER,
        )
        self.content_dict["widgets"]["media_title"].place(
            **self.content_dict["coords"]["media_title"]
        )
        self.content_dict["widgets"]["media_artist"].place(
            **self.content_dict["coords"]["media_artist"]
        )

    def update_display(self, payload):
        """Update the artwork and text on the GUI

        Args:
            payload (dict): the payload to use in updating the GUI
        """

        LOGGER.info("Updating display with payload:\t%s", dumps(payload))

        if not exists(
            artist_dir := join(
                self.ARTWORK_DIR,
                self.PATTERN.sub("", payload["media_artist"]).lower().replace(" ", "_"),
            )
        ):
            mkdir(artist_dir)
            LOGGER.info(
                "Created artwork directory for `%s`: `%s`",
                payload["media_artist"],
                artist_dir,
            )

        self.artwork_path = join(
            artist_dir,
            self.PATTERN.sub("", payload["album_name"] or payload["media_title"])
            .lower()
            .replace(" ", "_"),
        )

        try:
            with open(self.artwork_path, "rb") as fin:
                self.content_dict["images"]["tk_img"] = Image.open(BytesIO(fin.read()))
            LOGGER.debug("Retrieved artwork from `%s`", self.artwork_path)
        except FileNotFoundError:
            artwork_bytes = get(payload["artwork_url"]).content
            self.content_dict["images"]["tk_img"] = Image.open(BytesIO(artwork_bytes))

            with open(self.artwork_path, "wb") as fout:
                fout.write(artwork_bytes)

            LOGGER.info(
                "Saved artwork for `%s` by `%s` to `%s`",
                payload["album_name"],
                payload["media_artist"],
                self.artwork_path,
            )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error(
                "Unable to get artwork: `%s - %s`",
                type(exc).__name__,
                exc.__str__(),
            )

        self.content_dict["images"]["tk_img"] = self.content_dict["images"][
            "tk_img"
        ].resize((self.artwork_size, self.artwork_size), Image.ANTIALIAS)
        self.content_dict["images"]["artwork"] = ImageTk.PhotoImage(
            self.content_dict["images"]["tk_img"]
        )

        self.content_dict["widgets"]["artwork"].configure(
            image=self.content_dict["images"]["artwork"]
        )

        for k, v in payload.items():
            if k in self.content_dict["widgets"]:
                self.content_dict["widgets"][k].config(text=unescape(v))
                if len(self.content_dict["widgets"][k]["text"]) > self.CHAR_LIM:
                    self.content_dict["widgets"][k]["text"] = (
                        "  " + self.content_dict["widgets"][k]["text"] + "  "
                    ) * 3

                    self.hscroll_label(k)

    def hscroll_label(self, k):
        """Horizontally scroll a label on the GUI. Used when the text content is wider
        than the available screen space

        Args:
            k (str): the key to use in finding the label to scroll
        """

        self.content_dict["coords"][k]["x"] -= 2

        self.content_dict["coords"][k]["x"] = (
            0.5 * self.screen_width
            if self.content_dict["coords"][k]["x"]
            < (0.5 * self.screen_width)
            - (self.content_dict["widgets"][k].winfo_width() / 3)
            else self.content_dict["coords"][k]["x"]
        )

        self.content_dict["widgets"][k].place(**self.content_dict["coords"][k])

        if len(self.content_dict["widgets"][k]["text"]) > self.CHAR_LIM:
            self.content_dict["widgets"]["canvas"].after(10, self.hscroll_label, k)
        else:
            self.content_dict["coords"][k]["x"] = 0.5 * self.screen_width
            self.content_dict["widgets"][k].place(**self.content_dict["coords"][k])

    @property
    def screen_width(self):
        """
        Returns:
            int: the width of the CRT's screen
        """
        return self.root.winfo_screenwidth()

    @property
    def screen_height(self):
        """
        Returns:
            int: the height of the CRT's screen
        """
        return self.root.winfo_screenheight()

    @property
    def artwork_size(self):
        """
        Returns:
            int: the size of the artwork image on the screen in pixels
        """
        return int(0.65 * self.screen_height)
