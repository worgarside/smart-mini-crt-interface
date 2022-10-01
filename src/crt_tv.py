"""
This module contains the class for controlling the CRT TV GUI
"""
from __future__ import annotations

from html import unescape
from logging import DEBUG, getLogger
from time import sleep
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_file_handler, add_stream_handler

from artwork_image import ArtworkImage
from const import LOG_DIR, PI, TODAY_STR

try:
    # pylint: disable=unused-import
    from tkinter import CENTER, Canvas, Label, Tk
    from tkinter.font import Font

    from pigpio import OUTPUT
    from pigpio import pi as rasp_pi
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

    rasp_pi = MagicMock()
    OUTPUT = None

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/crt_tv/{TODAY_STR}.log")


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
    """Typing for the `CrtTv.widgets` attribute"""

    canvas: Canvas
    artwork: Label
    media_title: Label
    media_artist: Label


class CrtTv:
    """CRT TV class for controlling the GUI (not the power state)"""

    BG_COLOR = "#000000"
    STANDARD_ARGS: StandardArgsInfo = {"highlightthickness": 0, "bd": 0, "bg": BG_COLOR}
    CHAR_LIM = 31

    # @on_exception()  # type: ignore[misc]
    def __init__(self, gpio_pin: int) -> None:
        self.root = Tk()
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=self.BG_COLOR)

        self.gpio_pin = gpio_pin

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

        self.artwork_image: PhotoImage

        for widget_name in ("artwork", "media_title", "media_artist"):
            self.widgets[widget_name].place(  # type: ignore[literal-required]
                **self.coords[widget_name]  # type: ignore[literal-required]
            )

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

    def switch_on(self) -> None:
        """Switch on the CRT TV"""
        PI.write(self.gpio_pin, True)

    def switch_off(self) -> None:
        """Switch off the CRT TV"""
        PI.write(self.gpio_pin, False)

    def toggle_state(self) -> None:
        """Toggle the power state of the CRT TV"""
        PI.write(self.gpio_pin, not self.power_state)

    # @on_exception()  # type: ignore[misc]
    def update_display(
        self, title: str, artist: str, artwork_image: ArtworkImage
    ) -> None:
        """Update the display with the new media information

        Args:
            title (str): the song title
            artist (str): the artist(s) name)
            artwork_image (ArtworkImage): the artwork image instance
        """

        LOGGER.debug("Updating display with title `%s`, artist `%s`", title, artist)

        self.artwork_image = PhotoImage(artwork_image.get_image(self.artwork_size))
        self.widgets["artwork"].configure(image=self.artwork_image)

        k: Literal["media_title", "media_artist"]
        for k, v in (  # type: ignore[assignment]
            ("media_title", title),
            ("media_artist", artist),
        ):
            self.widgets[k].config(text=unescape(v))
            if len(self.widgets[k]["text"]) > self.CHAR_LIM:
                self.widgets[k]["text"] = ("  " + self.widgets[k]["text"] + "  ") * 3

                self.hscroll_label(k)

    @property
    def artwork_size(self) -> int:
        """
        Returns:
            int: the size of the artwork image on the screen in pixels
        """
        return int(0.65 * self.screen_height)

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
    def power_state(self) -> bool:
        """
        Returns:
            bool: the power state of the CRT (GPIO pin)
        """
        return bool(PI.read(self.gpio_pin))


if __name__ == "__main__":
    CrtTv(26).switch_on()
    print(CrtTv(26).power_state)
