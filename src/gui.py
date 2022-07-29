"""
Module for holding the main controller function(s) for controlling the GUI
"""
# pylint: disable=global-statement
from abc import ABC
from logging import DEBUG, getLogger
from os import environ, getenv
from re import sub
from time import sleep
from typing import List
from uuid import UUID

from dotenv import load_dotenv
from kasa import Discover, SmartPlug
from pychromecast import Chromecast
from pychromecast.controllers.media import (
    MEDIA_PLAYER_STATE_BUFFERING,
    MEDIA_PLAYER_STATE_IDLE,
    MEDIA_PLAYER_STATE_PAUSED,
    MEDIA_PLAYER_STATE_PLAYING,
    MEDIA_PLAYER_STATE_UNKNOWN,
    MediaImage,
    MediaStatus,
    MediaStatusListener,
)
from pychromecast.discovery import CastBrowser, SimpleCastListener
from pychromecast.error import UnsupportedNamespace
from pychromecast.models import CastInfo
from wg_utilities.loggers import add_file_handler, add_stream_handler
from zeroconf import Zeroconf

from const import CONFIG_FILE, LOG_DIR, TODAY_STR, switch_crt_off, switch_crt_on
from crt_tv import CrtTv, DisplayPayloadInfo

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/gui/{TODAY_STR}.log")

LOGGER.debug("Config file is `%s`", CONFIG_FILE)

#############
# Constants #
#############

CRT = CrtTv()

TARGET_CHROMECAST_NAME = environ["TARGET_CHROMECAST_NAME"]

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


class ChromecastMediaListener(MediaStatusListener, ABC):  # type: ignore[misc]
    """Class for listening to the Chromecast media status

    Args:
        cast (Chromecast): the Chromecast being monitored
    """

    def __init__(self, cast: Chromecast) -> None:
        self.cast = cast
        self.name = cast.name

        self._previous_payload: DisplayPayloadInfo = {
            "artwork_url": None,
            "media_artist": "",
            "media_title": "",
            "album_name": "",
        }
        self._previous_state = MEDIA_PLAYER_STATE_UNKNOWN

    def new_media_status(self, status: MediaStatus) -> None:
        """Method executed when the status of the Chromecast changes

        Args:
            status (MediaStatus): the new status of the Chromecast's media
        """

        if status.player_state == self._previous_state:
            LOGGER.debug("No change in state, returning...")
            return

        available_artwork_images: List[MediaImage] = sorted(
            status.images,
            key=lambda img: img.height,  # type: ignore[no-any-return]
            reverse=True,
        )

        payload: DisplayPayloadInfo = {
            "artwork_url": available_artwork_images[0].url
            if len(available_artwork_images) > 0
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


def add_callback(uuid: UUID, _: str) -> None:
    """Callback function for when a Chromecast is discovered

    Args:
        uuid (UUID): the CC's UUID
        _ (str) the name of the service

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


def remove_callback(uuid: UUID, _: str) -> None:
    """Callback function for when a discovered Chromecast disappears

    Args:
        uuid (UUID): the UUID of the removed Chromecast
        _ (str) the name of the service
    """

    global CHROMECAST

    cast_info: CastInfo = BROWSER.services.get(uuid)

    if (
        cast_info.friendly_name.lower().strip()
        == TARGET_CHROMECAST_NAME.lower().strip()
    ):
        CHROMECAST = None


def main() -> None:
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
