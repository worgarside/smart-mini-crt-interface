"""
Module for holding the main controller function(s) for controlling the GUI
"""

from asyncio import run
from logging import getLogger, DEBUG
from os import getenv
from re import sub

from PIL import Image
from dotenv import load_dotenv
from kasa import SmartPlug
from nanoleafapi import Nanoleaf
from pychromecast import get_listed_chromecasts, UnsupportedNamespace
from pychromecast.controllers.media import (
    MediaStatusListener,
    MEDIA_PLAYER_STATE_PLAYING,
    MEDIA_PLAYER_STATE_BUFFERING,
    MEDIA_PLAYER_STATE_PAUSED,
    MEDIA_PLAYER_STATE_IDLE,
    MEDIA_PLAYER_STATE_UNKNOWN,
)
from pychromecast.controllers.receiver import CastStatusListener
from time import sleep
from traceback import format_exc

from const import (
    CONFIG_FILE,
    FH,
    SH,
    CAST_NAME,
    switch_crt_on,
    switch_crt_off,
    get_config,
)
from crt_tv import CrtTv

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
LOGGER.addHandler(FH)
LOGGER.addHandler(SH)

LOGGER.debug("Config file is `%s`", CONFIG_FILE)

#############
# Constants #
#############

CRT = CrtTv()

try:
    SHAPES = Nanoleaf(
        getenv("NANOLEAF_SHAPES_IP"), getenv("NANOLEAF_SHAPES_AUTH_TOKEN")
    )
except Exception as exc:
    LOGGER.error("%s - %s", type(exc).__name__, str(exc))
    LOGGER.exception(format_exc().replace("\n", "\t"))
    sleep(300)
    exit()

try:
    HIFI_AMP = SmartPlug(getenv("HIFI_AMP_KASA_IP"))
except Exception as exc:
    LOGGER.exception("%s - %s", type(exc).__name__, str(exc))
    LOGGER.exception(format_exc().replace("\n", "\t"))
    sleep(300)
    exit()


# pylint: disable=too-few-public-methods
class ChromecastStatusListener(CastStatusListener):
    """Class for listening to the Chromecast status. Currently unused.

    Args:
        cast (Chromecast): the Chromecast being monitored
    """

    def __init__(self, cast):
        self.cast = cast
        self.name = cast.name

    def new_cast_status(self, status):
        """Method executed when the status of the Chromecast changes

        Args:
            status (ChromecastStatus): the new status of the Chromecast
        """


# pylint: disable=too-few-public-methods
class ChromecastMediaListener(MediaStatusListener):
    """Class for listening to the Chromecast media status

    Args:
        cast (Chromecast): the Chromecast being monitored
    """

    def __init__(self, cast):
        self.cast = cast
        self.name = cast.name

        self._previous_payload = dict()
        self._previous_state = MEDIA_PLAYER_STATE_UNKNOWN

    def new_media_status(self, status):
        """Method executed when the status of the Chromecast changes

        Args:
            status (MediaStatus): the new status of the Chromecast's media
        """

        if status.player_state == self._previous_state:
            LOGGER.debug("No change in state, returning...")
            return

        payload = {
            "artwork_url": sorted(
                status.images, key=lambda img: img.height, reverse=True
            )[0].url
            if status.images
            else None,
            "media_title": sub(r".mp3$", "", status.title or ""),
            "media_artist": status.artist or "",
            "album_name": status.album_name,
        }

        if status.player_state in {
            MEDIA_PLAYER_STATE_PLAYING,
            MEDIA_PLAYER_STATE_PAUSED,
            MEDIA_PLAYER_STATE_BUFFERING,
            MEDIA_PLAYER_STATE_IDLE,
        }:
            LOGGER.info(
                "MediaStatus.player_state is `%s`. Switching on", status.player_state
            )
            switch_crt_on(self._previous_state == MEDIA_PLAYER_STATE_UNKNOWN)

            run(HIFI_AMP.turn_on())

            if payload != self._previous_payload:
                self._previous_payload = payload
                CRT.update_display(payload)

                if get_config(keys=["nanoleafControl", "state"]):
                    LOGGER.debug(
                        "Sending colors for `%s` to Nanoleaf Shapes", status.album_name
                    )
                    SHAPES.write_effect(
                        {
                            "command": "display",
                            "animType": "random",
                            "colorType": "HSB",
                            "animData": None,
                            "palette": get_n_colors_from_image(CRT.artwork_path),
                            "transTime": {"minValue": 50, "maxValue": 100},
                            "delayTime": {"minValue": 50, "maxValue": 100},
                            "loop": True,
                        }
                    )
            else:
                LOGGER.debug("No change to core payload")

        elif status.player_state in {
            MEDIA_PLAYER_STATE_UNKNOWN,
        }:
            LOGGER.info(
                "MediaStatus.player_state is `%s`. Switching off", status.player_state
            )
            switch_crt_off(
                force_switch_off=self._previous_state
                in {
                    MEDIA_PLAYER_STATE_PLAYING,
                    MEDIA_PLAYER_STATE_PAUSED,
                    MEDIA_PLAYER_STATE_BUFFERING,
                    MEDIA_PLAYER_STATE_IDLE,
                }
            )
        else:
            LOGGER.error(
                "`MediaStatus.player_state` in unexpected stater: `%s`",
                status.player_state,
            )

        self._previous_state = status.player_state


def get_n_colors_from_image(img_path, n=15):
    """Get the N most common colors from an image

    Args:
        img_path (str): the path to the image file
        n (int): the number of colors to retrieve from the image

    Returns:
        list: a list of the N most common colors in an image in the HSB format
    """
    pixels = Image.open(img_path).quantize(colors=n, method=0)

    return [
        {
            "hue": int((color_tuple[0] * 360) / 255),
            "saturation": int((color_tuple[1] * 100) / 255),
            "brightness": int((color_tuple[2] * 100) / 255),
        }
        for count, color_tuple in sorted(
            pixels.convert(mode="HSV").getcolors(),
            key=lambda elem: elem[0],
            reverse=True,
        )
    ][:n]


def run_interface():
    """Setup function for creating necessary resources and listeners"""

    chromecast = None
    LOGGER.info("Connecting to Chromecast...")

    while chromecast is None:
        try:
            _chromecasts, browser = get_listed_chromecasts(
                friendly_names=[CAST_NAME],
            )

            chromecast = _chromecasts.pop()
            # Start socket client's worker thread and wait for initial status update
            chromecast.wait()

            chromecast.media_controller.register_status_listener(
                ChromecastMediaListener(chromecast)
            )

            LOGGER.info("Chromecast connected and status listener registered")

            try:
                LOGGER.debug("Running force update")
                chromecast.media_controller.update_status()
            except UnsupportedNamespace as exc:
                LOGGER.error("%s - %s", type(exc).__name__, str(exc))
                LOGGER.exception(format_exc().replace("\n", "\t"))

            LOGGER.info("Status updated, starting TK mainloop")
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error(
                "Error connecting to Chromecast: `%s - %s`",
                type(exc).__name__,
                exc.__str__(),
            )
            LOGGER.exception(format_exc().replace("\n", "\t"))

            chromecast = None
            sleep(10)

    CRT.root.mainloop()

    LOGGER.info("TK mainloop exited, stopping Chromecast discovery")

    browser.stop_discovery()

    LOGGER.info("Exiting")


if __name__ == "__main__":
    run_interface()
