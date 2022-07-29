"""
This module contains the class for controlling the CRT TV GUI
"""
from __future__ import annotations

from html import unescape
from io import BytesIO
from json import dumps
from logging import DEBUG, getLogger
from os import mkdir
from os.path import exists, join
from pathlib import Path
from re import compile as compile_regex
from time import sleep
from typing import Any, Literal, Optional, TypedDict

from dotenv import load_dotenv
from requests import get
from wg_utilities.exceptions import on_exception  # pylint: disable=no-name-in-module
from wg_utilities.loggers import add_file_handler, add_stream_handler

from const import LOG_DIR, TODAY_STR

try:
    from tkinter import CENTER, Canvas, Label, Tk
    from tkinter.font import Font

    from PIL import Image
    from PIL.ImageTk import PhotoImage
except ImportError:

    from unittest.mock import MagicMock

    class TkMagicMock(MagicMock):
        """MagicMock specifically for Tk class"""

        @staticmethod
        def mainloop(*_: Any, **__: Any) -> None:
            """Substitute for TK.mainloop for non-Tk configurations"""
            while True:
                print("loop")
                sleep(1)

    class ImageMagicMock(MagicMock):
        """MagicMock specifically for Image class"""

        def resize(self, *_: Any, **__: Any) -> None:
            """Placeholder for Image.resize"""

    Label = MagicMock()  # type: ignore[misc]
    Canvas = MagicMock()  # type: ignore[misc]
    Tk = TkMagicMock()  # type: ignore[misc]
    Font = MagicMock()  # type: ignore[misc]
    Image = MagicMock()
    ImageTk = MagicMock()

    CENTER = "center"

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/crt_tv/{TODAY_STR}.log")


class DisplayPayloadInfo(TypedDict):
    """Typing for the payload provided for the display"""

    artwork_url: Optional[str]
    media_title: str
    media_artist: str
    album_name: str


class StandardArgsInfo(TypedDict):
    """Typing for the standard Label/Canvas args"""

    highlightthickness: Literal[0]
    bd: Literal[0]
    bg: str


class CoordsItemInfo(TypedDict):
    """Typing for the individual coords objects"""

    x: float
    y: float
    anchor: Literal["center"]


class CoordsInfo(TypedDict):
    """Typing for the CrtTv.coords attribute"""

    artwork: CoordsItemInfo
    media_title: CoordsItemInfo
    media_artist: CoordsItemInfo


class WidgetsInfo(TypedDict):
    """Typing for the CrtTv.widgets attribute"""

    canvas: Canvas
    artwork: Label
    media_title: Label
    media_artist: Label


class CrtTv:
    """CRT TV class for controlling the GUI (not the power state)"""

    BG_COLOR = "#000000"
    STANDARD_ARGS: StandardArgsInfo = {"highlightthickness": 0, "bd": 0, "bg": BG_COLOR}
    CHAR_LIM = 31
    MAX_WAIT_TIME_MS = 10000
    ARTWORK_DIR = join(str(Path.home()), "crt_artwork")
    PATTERN = compile_regex(r"[^\w =\-\(\)<>,.]+")

    @on_exception()  # type: ignore[misc]
    def __init__(self) -> None:
        if not exists(self.ARTWORK_DIR):
            mkdir(self.ARTWORK_DIR)

        self.root = Tk()
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=self.BG_COLOR)

        crt_font = Font(family="Courier New", size=int(0.05 * self.screen_height))

        canvas_widget = Canvas(
            self.root,
            width=self.screen_width,
            height=self.screen_height,
            **self.STANDARD_ARGS,
        )

        canvas_widget.place(
            x=0, y=0, width=self.screen_width, height=self.screen_height
        )

        self.widgets: WidgetsInfo = {
            "canvas": canvas_widget,
            "artwork": Label(canvas_widget, image="", **self.STANDARD_ARGS),
            "media_title": Label(
                canvas_widget,
                text="",
                font=crt_font,
                fg="#ffffff",
                bg=self.BG_COLOR,
            ),
            "media_artist": Label(
                canvas_widget,
                text="",
                font=crt_font,
                fg="#ffffff",
                bg=self.BG_COLOR,
            ),
        }

        self.coords: CoordsInfo = {
            "artwork": {
                "x": 0.5 * self.screen_width,
                "y": (0.5 * self.artwork_size) + (0.075 * self.screen_height),
                "anchor": CENTER,
            },
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
        }

        for widget_name in ("artwork", "media_title", "media_artist"):
            self.widgets[widget_name].place(  # type: ignore[literal-required]
                **self.coords[widget_name]  # type: ignore[literal-required]
            )

    @on_exception()  # type: ignore[misc]
    def update_display(self, payload: DisplayPayloadInfo) -> None:
        """Update the artwork and text on the GUI

        Args:
            payload (DisplayPayloadInfo): the payload to use in updating the GUI

        Raises:
            FileNotFoundError: if the local file can't be found and no URL is provided
             in the payload
        """

        if all(bool(v) is False for v in payload.values()):
            LOGGER.warning("Empty payload provided, not updating display")
            return

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

        artwork_path = join(
            artist_dir,
            self.PATTERN.sub("", payload["album_name"] or payload["media_title"])
            .lower()
            .replace(" ", "_"),
        )

        try:
            with open(artwork_path, "rb") as fin:
                tk_img = Image.open(BytesIO(fin.read()))
            LOGGER.debug("Retrieved artwork from `%s`", artwork_path)
        except FileNotFoundError:
            if payload["artwork_url"] is None:
                raise

            artwork_bytes = get(payload["artwork_url"]).content
            tk_img = Image.open(BytesIO(artwork_bytes))

            with open(artwork_path, "wb") as fout:
                fout.write(artwork_bytes)

            LOGGER.info(
                "Saved artwork for `%s` by `%s` to `%s`",
                payload["album_name"],
                payload["media_artist"],
                artwork_path,
            )

        tk_img = tk_img.resize((self.artwork_size, self.artwork_size), Image.ANTIALIAS)

        self.widgets["artwork"].configure(image=PhotoImage(tk_img))

        # `k` can have other values, but only these two are relevant
        k: Literal["media_title", "media_artist"]
        v: str
        for k, v in payload.items():  # type: ignore[assignment]
            if k in ("media_artist", "media_title"):
                self.widgets[k].config(text=unescape(v))
                if len(self.widgets[k]["text"]) > self.CHAR_LIM:
                    self.widgets[k]["text"] = (
                        "  " + self.widgets[k]["text"] + "  "
                    ) * 3

                    self.hscroll_label(k)

    @on_exception()  # type: ignore[misc]
    def hscroll_label(self, k: Literal["media_artist", "media_title"]) -> None:
        """Horizontally scroll a label on the GUI. Used when the text content is wider
        than the available screen space

        Args:
            k (str): the key to use in finding the label to scroll
        """

        self.coords[k]["x"] -= 2

        self.coords[k]["x"] = (
            0.5 * self.screen_width
            if self.coords[k]["x"]
            < (0.5 * self.screen_width) - (self.widgets[k].winfo_width() / 3)
            else self.coords[k]["x"]
        )

        self.widgets[k].place(**self.coords[k])

        if len(self.widgets[k]["text"]) > self.CHAR_LIM:
            self.widgets["canvas"].after(10, self.hscroll_label, k)
        else:
            self.coords[k]["x"] = 0.5 * self.screen_width
            self.widgets[k].place(**self.coords[k])

    @property
    def screen_width(self) -> int:
        """
        Returns:
            int: the width of the CRT's screen
        """
        return self.root.winfo_screenwidth()

    @property
    def screen_height(self) -> int:
        """
        Returns:
            int: the height of the CRT's screen
        """
        return self.root.winfo_screenheight()

    @property
    def artwork_size(self) -> int:
        """
        Returns:
            int: the size of the artwork image on the screen in pixels
        """
        return int(0.65 * self.screen_height)
