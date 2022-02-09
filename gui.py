"""
Module for holding the main controller function(s) for controlling the GUI
"""
# pylint: disable=global-statement
from logging import getLogger, DEBUG
from os import getenv
from re import sub

from PIL import Image
from dotenv import load_dotenv
from kasa import SmartPlug, Discover
from nanoleafapi import Nanoleaf
from pychromecast import (
    CastBrowser,
    Chromecast,
    CastInfo,
    SimpleCastListener,
    UnsupportedNamespace,
)
from pychromecast.controllers.media import (
    MediaStatusListener,
    MEDIA_PLAYER_STATE_PLAYING,
    MEDIA_PLAYER_STATE_BUFFERING,
    MEDIA_PLAYER_STATE_PAUSED,
    MEDIA_PLAYER_STATE_IDLE,
    MEDIA_PLAYER_STATE_UNKNOWN,
)
from time import sleep

from zeroconf import Zeroconf

from const import (
    CONFIG_FILE,
    FH,
    SH,
    switch_crt_on,
    switch_crt_off,
    get_config,
    set_config,
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

SHAPES = Nanoleaf(getenv("NANOLEAF_SHAPES_IP"), getenv("NANOLEAF_SHAPES_AUTH_TOKEN"))

TARGET_CHROMECAST_NAME = getenv("TARGET_CHROMECAST_NAME")

BROWSER: CastBrowser = None  # noqa
CHROMECAST: Chromecast = None  # noqa

ZCONF = Zeroconf()


if int(getenv("CONTROL_HIFI_AMP", "0")) == 1:
    from asyncio import run

    for ip, device in run(Discover.discover()).items():
        if device.alias.lower() == "hifi amp":
            LOGGER.info("Found HiFi Amp on IP `%s`", ip)
            HIFI_AMP = SmartPlug(ip)
            break

        LOGGER.debug("Found `%s`, continuing search...", device.alias.lower())
    else:
        run(Discover.discover())
        raise Exception("Unable to find HiFi Amp SmartPlug")
else:
    HIFI_AMP = None


# pylint: disable=too-few-public-methods
class ChromecastMediaListener(MediaStatusListener):
    """Class for listening to the Chromecast media status

    Args:
        cast (Chromecast): the Chromecast being monitored
    """

    def __init__(self, cast):
        self.cast = cast
        self.name = cast.name

        self._previous_payload = {}
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

            if HIFI_AMP:
                run(HIFI_AMP.turn_on())

            if payload != self._previous_payload:
                self._previous_payload = payload
                CRT.update_display(payload)

                if get_config(keys=["nanoleafControl", "state"]):
                    LOGGER.debug(
                        "Sending colors for `%s` to Nanoleaf Shapes", status.album_name
                    )
                    set_config(
                        get_config(keys=["effect", "current"]),
                        keys=["effect", "previous"],
                    )
                    set_config(
                        get_config(keys=["media_payload", "current"]),
                        keys=["media_payload", "previous"],
                    )
                    effect_dict = {
                        "command": "display",
                        "animType": "random",
                        "colorType": "HSB",
                        "animData": None,
                        "palette": get_n_colors_from_image(CRT.artwork_path),
                        "transTime": {"minValue": 50, "maxValue": 100},
                        "delayTime": {"minValue": 50, "maxValue": 100},
                        "loop": True,
                    }
                    set_config(effect_dict, keys=["effect", "current"])
                    set_config(payload, keys=["media_payload", "current"])
                    SHAPES.write_effect(effect_dict=effect_dict)
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


def add_callback(uuid, _):
    """Callback function for when a Chromecast is discovered

    Args:
        uuid (UUID): the CC's UUID

    """
    global CHROMECAST

    if CHROMECAST:
        return

    cast_info: CastInfo = BROWSER.services.get(uuid)

    if not cast_info:
        print(f"No service found with UUID {uuid} in browser")
        return

    print(f"Found {cast_info.friendly_name} with UUID {uuid}")

    if (
        cast_info.friendly_name.lower().strip()
        == TARGET_CHROMECAST_NAME.lower().strip()
    ):
        CHROMECAST = Chromecast(
            cast_info=cast_info,
            zconf=ZCONF,
        )


def remove_callback(uuid, _):
    """Callback function for when a discovered Chromecast disappears

    Args:
        uuid (UUID): the UUID of the removed Chromecast
    """

    global CHROMECAST

    cast_info: CastInfo = BROWSER.services.get(uuid)

    if (
        cast_info.friendly_name.lower().strip()
        == TARGET_CHROMECAST_NAME.lower().strip()
    ):
        CHROMECAST = None


def main():
    """Main function for this script"""
    global BROWSER

    BROWSER = CastBrowser(
        SimpleCastListener(
            add_callback=add_callback,
            remove_callback=remove_callback,
        ),
        zeroconf_instance=ZCONF,
    )
    BROWSER.start_discovery()

    while not CHROMECAST:
        print(
            f"Found {BROWSER.count} devices so far: `"
            + "`, `".join(
                cast_info.friendly_name for cast_info in BROWSER.services.values()
            )
            + "`"
        )
        sleep(1)

    CHROMECAST.wait()
    CHROMECAST.media_controller.register_status_listener(
        ChromecastMediaListener(CHROMECAST)
    )

    try:
        LOGGER.debug("Running force update")
        CHROMECAST.media_controller.update_status()
    except UnsupportedNamespace as exc:
        LOGGER.error("%s - %s", type(exc).__name__, str(exc))

    CRT.root.mainloop()

    # Shut down discovery
    BROWSER.stop_discovery()


if __name__ == "__main__":
    main()
