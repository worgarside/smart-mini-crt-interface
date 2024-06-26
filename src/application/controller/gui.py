"""Module for holding the main controller function(s) for controlling the GUI."""

from __future__ import annotations

from json import dumps, loads
from logging import DEBUG, getLogger
from pathlib import Path
from sys import path
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import (  # noqa: E402
    CRT_DISPLAY_MQTT_TOPIC,
    HA_CRT_PI_STATE_FROM_HA_TOPIC,
    MQTT_CLIENT,
)
from domain.model.artwork_image import ArtworkImage  # noqa: E402
from domain.model.const import CRT_PIN  # noqa: E402
from domain.model.crt_tv import CrtTv  # noqa: E402

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)

CRT = CrtTv(CRT_PIN)


@on_exception()
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Process env vars on MQTT message.

    Args:
        message (MQTTMessage): the message object from the MQTT subscription

    Raises:
        ValueError: if the state-from-ha topic receives an invalid payload
    """

    if message.topic == HA_CRT_PI_STATE_FROM_HA_TOPIC:
        if message.payload.decode() == "on":
            CRT.switch_on()
        elif message.payload.decode() == "off":
            CRT.switch_off()
        else:
            raise ValueError(
                f"Invalid payload received from HA on topic `{message.topic}`: "
                f"{message.payload.decode()}",
            )
    elif message.topic == CRT_DISPLAY_MQTT_TOPIC:
        payload = loads(message.payload.decode())

        LOGGER.debug("Received payload: %s", dumps(payload))

        if payload["state"] == "off" or payload["album_artwork_url"] in (
            None,
            "",
            "None",
            "none",
            "null",
        ):
            CRT.switch_off(notify_ha=True)
            CRT.update_display_values(
                title=payload.get("title"),
                artist=payload.get("artist"),
                artwork_image=None,
            )
            CRT.album = payload.get("album")
        else:
            CRT.update_display_values(
                title=payload["title"],
                artist=payload["artist"],
                artwork_image=ArtworkImage(
                    artist=payload.get("artist"),
                    album=payload.get("album"),
                    url=payload.get("album_artwork_url"),
                ),
            )
            CRT.album = payload.get("album")
            CRT.switch_on(notify_ha=True)

        LOGGER.debug(CRT.current_state_log_output)


@on_exception()
def main() -> None:
    """Main function for this script."""

    LOGGER.info("Starting CRT Interface (%ix%i)", CRT.screen_width, CRT.screen_height)

    MQTT_CLIENT.on_message = on_message

    MQTT_CLIENT.subscribe(CRT_DISPLAY_MQTT_TOPIC)
    MQTT_CLIENT.subscribe(HA_CRT_PI_STATE_FROM_HA_TOPIC)
    MQTT_CLIENT.loop_start()

    LOGGER.debug("MQTT client connected, starting CRT mainloop")
    CRT.start_gui()
    MQTT_CLIENT.loop_stop(force=True)


if __name__ == "__main__":
    main()
