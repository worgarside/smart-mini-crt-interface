"""Module for holding the main controller function(s) for controlling the GUI."""

from __future__ import annotations

from contextlib import suppress
from json import dumps, loads
from typing import TYPE_CHECKING, Any

from models import ArtworkImage, CrtTv
from wg_utilities.decorators import process_exception
from wg_utilities.loggers import add_warehouse_handler, get_streaming_logger
from wg_utilities.utils import mqtt

if TYPE_CHECKING:
    from paho.mqtt.client import MQTTMessage


LOGGER = get_streaming_logger(__name__)
add_warehouse_handler(LOGGER)

CRT = CrtTv()


@mqtt.CLIENT.message_callback()
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Process an incoming message and display the content."""
    payload = loads(message.payload.decode())

    LOGGER.debug("Received payload: %s", dumps(payload))

    if payload["state"] == "off" or payload["album_artwork_url"] in {
        None,
        "",
        "None",
        "none",
        "null",
    }:
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

    LOGGER.debug(CRT.current_state_log_output)


@process_exception(logger=LOGGER)
def main() -> None:
    """Main function for this script."""
    LOGGER.info("Starting CRT Interface (%ix%i)", CRT.screen_width, CRT.screen_height)

    mqtt.CLIENT.connect(mqtt.MQTT_HOST)

    mqtt.CLIENT.subscribe("/crtpi/crt-interface/content", qos=1)
    mqtt.CLIENT.loop_start()

    with suppress(KeyboardInterrupt):
        LOGGER.debug("MQTT client connected, starting CRT mainloop")
        CRT.start_gui()

    mqtt.CLIENT.loop_stop()


if __name__ == "__main__":
    main()
