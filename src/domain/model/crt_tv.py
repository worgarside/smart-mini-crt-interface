"""
This module contains the class for controlling the CRT TV GUI
"""
from __future__ import annotations

from html import unescape
from logging import DEBUG, getLogger
from os import getenv
from pathlib import Path
from textwrap import dedent
from time import sleep
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from paho.mqtt.publish import single
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

from application.handler.mqtt import (
    FORCE_HA_UPDATE_TOPIC,
    HA_CRT_PI_STATE_FROM_CRT_TOPIC,
)
from domain.model.artwork_image import ArtworkImage
from domain.model.const import PI

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

try:
    # pylint: disable=unused-import
    from tkinter import CENTER, Canvas, Label, Tk
    from tkinter.font import Font

    from PIL import Image

    # noinspection PyUnresolvedReferences
    from PIL.ImageTk import PhotoImage
except ImportError as exc:
    LOGGER.warning(
        "Unable to import TK/PIL dependencies, using mocks instead: %s", repr(exc)
    )
    from unittest.mock import MagicMock

    class TkMagicMock(MagicMock):
        """MagicMock specifically for Tk class"""

        @staticmethod
        def mainloop(*_: Any, **__: Any) -> None:
            """Substitute for TK.mainloop for non-Tk configurations"""
            while True:
                print("loop")
                sleep(1)

    Label = MagicMock()  # type: ignore[misc]
    Canvas = MagicMock()  # type: ignore[misc]
    Tk = TkMagicMock()  # type: ignore[misc]
    Font = MagicMock()  # type: ignore[misc]
    Image = MagicMock()
    ImageTk = MagicMock()

    CENTER = "center"

try:
    # pylint: disable=unused-import
    from pigpio import OUTPUT
    from pigpio import pi as rasp_pi
except ImportError as exc:
    LOGGER.warning(
        "Unable to import GPIO dependencies, using mocks instead: %s", repr(exc)
    )
    from unittest.mock import MagicMock

    rasp_pi = MagicMock()
    OUTPUT = None

_DEFAULT = object()

MQTT_AUTH_KWARGS = {
    "hostname": getenv("MQTT_HOST"),
    "auth": {
        "username": getenv("MQTT_USERNAME"),
        "password": getenv("MQTT_PASSWORD"),
    },
}


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

    NULL_IMAGE = ArtworkImage(
        "null", "null", str(Path(__file__).parent.parent / "assets" / "null.png")
    )

    @on_exception()  # type: ignore[misc]
    def __init__(self, gpio_pin: int, force_ha_update: bool = True) -> None:
        self._root = Tk()
        self._root.attributes("-fullscreen", True)
        self._root.configure(bg=self.BG_COLOR)

        self.gpio_pin = gpio_pin

        crt_font = Font(family="Courier New", size=int(0.05 * self.screen_height))

        canvas_widget = Canvas(
            self._root,
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

        # noinspection PyTypeChecker
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

        self._title: str
        self._artist: str
        self._album: str
        self._artwork_image: ArtworkImage = self.NULL_IMAGE

        # This is needed to allow the persistence of the PhotoImage instance, otherwise
        # the image isn't displayed
        self._artwork_photoimage: PhotoImage

        for widget_name in ("artwork", "media_title", "media_artist"):
            self.widgets[widget_name].place(  # type: ignore[literal-required]
                **self.coords[widget_name]  # type: ignore[literal-required]
            )

        if force_ha_update:
            single(FORCE_HA_UPDATE_TOPIC, payload=True, **MQTT_AUTH_KWARGS)

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

    @on_exception()  # type: ignore[misc]
    def refresh_display_output(
        self,
    ) -> None:
        """Refresh the display to display current property values"""

        LOGGER.debug(
            "Updating display with title `%s`, artist `%s`, artwork `%s`",
            self.title,
            self.artist,
            str(self.artwork_image),
        )

        # noinspection PyAttributeOutsideInit
        self._artwork_photoimage = PhotoImage(
            self.artwork_image.get_image(self.artwork_size)
        )
        self.widgets["artwork"].configure(image=self._artwork_photoimage)

        k: Literal["media_title", "media_artist"]
        for k, v in (  # type: ignore[assignment]
            ("media_title", self.title),
            ("media_artist", self.artist),
        ):
            self.widgets[k].config(text=unescape(v))
            if len(self.widgets[k]["text"]) > self.CHAR_LIM:
                # Add the text three times to allow for wrap-around effect
                self.widgets[k]["text"] = ("  " + self.widgets[k]["text"] + "  ") * 3

                self.hscroll_label(k)

    def start_gui(self) -> None:
        """Start the Tk mainloop, this blocks until the GUI is closed"""
        # TODO make this optionally async so other things can run in the background?
        self._root.mainloop()

    def switch_on(self, *, notify_ha: bool = False) -> None:
        """Switch on the CRT TV

        Args:
            notify_ha (bool): Whether to notify Home Assistant of the state change.
                Defaults to False.
        """
        LOGGER.debug("Switching on CRT TV")
        PI.write(self.gpio_pin, True)
        if notify_ha:
            single(HA_CRT_PI_STATE_FROM_CRT_TOPIC, payload=True, **MQTT_AUTH_KWARGS)

    def switch_off(self, *, notify_ha: bool = False) -> None:
        """Switch off the CRT TV

        Args:
            notify_ha (bool): Whether to notify Home Assistant of the state change.
        """
        LOGGER.debug("Switching off CRT TV")
        PI.write(self.gpio_pin, False)
        if notify_ha:
            single(HA_CRT_PI_STATE_FROM_CRT_TOPIC, payload=False, **MQTT_AUTH_KWARGS)

    def toggle_state(self, *, notify_ha: bool = False) -> None:
        """Toggle the power state of the CRT TV

        Args:
            notify_ha (bool): Whether to notify Home Assistant of the state change.
        """
        new_state = not self.power_state

        LOGGER.debug("Toggling CRT TV power state to %s", new_state)

        PI.write(self.gpio_pin, new_state)

        if notify_ha:
            single(
                HA_CRT_PI_STATE_FROM_CRT_TOPIC, payload=new_state, **MQTT_AUTH_KWARGS
            )

    # noinspection PyAttributeOutsideInit
    def update_display_values(
        self,
        *,
        title: str | None = _DEFAULT,  # type: ignore[assignment]
        artist: str | None = _DEFAULT,  # type: ignore[assignment]
        artwork_image: ArtworkImage | None = _DEFAULT,
    ) -> None:
        """Update the display with the new media information. An object instance is used
         as a default so that the values can be removed by setting them to `None`

        Args:
            title (str): the song title
            artist (str): the artist(s) name)
            artwork_image (ArtworkImage): the artwork image instance
        """

        if title is not _DEFAULT:
            self._title = title or ""

        if artist is not _DEFAULT:
            self._artist = artist or ""

        if artwork_image is not _DEFAULT:
            self._artwork_image = artwork_image or self.NULL_IMAGE

        self.refresh_display_output()

    @property
    def album(self) -> str:
        """The album name"""
        if not hasattr(self, "_album"):
            # noinspection PyAttributeOutsideInit
            self._album = ""

        return self._album

    @album.setter
    def album(self, value: str | None) -> None:
        """Set the album name"""
        # noinspection PyAttributeOutsideInit
        self._album = value or ""
        self.refresh_display_output()

    @property
    def artist(self) -> str:
        """The artist property"""
        if not hasattr(self, "_artist"):
            # noinspection PyAttributeOutsideInit
            self._artist = ""

        return self._artist

    @artist.setter
    def artist(self, value: str | None) -> None:
        """The artist property setter"""
        # noinspection PyAttributeOutsideInit
        self._artist = value or ""
        self.refresh_display_output()

    @property
    def artwork_image(self) -> ArtworkImage:
        """The artwork image"""
        return self._artwork_image

    @artwork_image.setter
    def artwork_image(self, value: ArtworkImage | None) -> None:
        """The artwork image"""
        self._artwork_image = value or self.NULL_IMAGE
        self.refresh_display_output()

    @property
    def artwork_size(self) -> int:
        """
        Returns:
            int: the size of the artwork image on the screen in pixels
        """
        return int(0.65 * self.screen_height)

    @property
    def current_state_log_output(self) -> str:
        """
        Returns:
            str: a useful output of the current state of the CRT for logging
        """

        return dedent(
            f"""
        Title:   {self.title}
        Artist:  {self.artist}
        Album:   {self.album}
        Artwork: {self.artwork_image!r}

        State:   {self.power_state}
        """
        ).strip()

    @property
    def screen_width(self) -> int:
        """
        Returns:
            int: the width of the CRT's screen
        """
        return self._root.winfo_screenwidth()

    @property
    def screen_height(self) -> int:
        """
        Returns:
            int: the height of the CRT's screen
        """
        return self._root.winfo_screenheight()

    @property
    def title(self) -> str:
        """The title property"""
        if not hasattr(self, "_title"):
            # noinspection PyAttributeOutsideInit
            self._title = ""

        return self._title

    @title.setter
    def title(self, value: str | None) -> None:
        """The title property setter"""
        # noinspection PyAttributeOutsideInit
        self._title = value or ""
        self.refresh_display_output()

    @property
    def power_state(self) -> bool:
        """
        Returns:
            bool: the power state of the CRT (GPIO pin)
        """
        return bool(PI.read(self.gpio_pin))
