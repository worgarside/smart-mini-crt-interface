"""
Module for holding the main controller function(s) for controlling the GUI
"""
from json import dumps, loads
from logging import DEBUG, getLogger
from os import getenv
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import Client, MQTTMessage
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_file_handler, add_stream_handler

from artwork_image import ArtworkImage
from const import (
    CRT_DISPLAY_MQTT_TOPIC,
    CRT_PIN,
    HA_CRT_PI_STATE_FROM_HA_TOPIC,
    LOG_DIR,
    TODAY_STR,
)
from crt_tv import CrtTv

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/crt_interface/{TODAY_STR}.log")


CRT = CrtTv(CRT_PIN)
MQTT_CLIENT = Client()
MQTT_CLIENT.username_pw_set(
    username=getenv("MQTT_USERNAME"), password=getenv("MQTT_PASSWORD")
)

MQTT_HOST = getenv("MQTT_HOST")


@on_exception()  # type: ignore[misc]
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Callback method for updating env vars on MQTT message

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


@on_exception()  # type: ignore[misc]
def on_connect(
    client: Client, userdata: dict[str, object], flags: dict[str, object], rc: int
) -> None:
    """Called when the broker responds to our connection request.

    Args:
        client (Client): the client instance for this callback
        userdata (dict): the private user data as set in Client() or userdata_set()
        flags (dict): response flags sent by the broker
        rc (int): the connection result
    """
    _ = client, userdata, flags, rc
    LOGGER.debug("MQTT Client connected")


@on_exception()  # type: ignore[misc]
def on_disconnect(client: Client, userdata: dict[str, object], rc: int) -> None:
    """Called when the client disconnects from the broker

    Args:
        client (Client): the client instance for this callback
        userdata (dict): the private user data as set in Client() or userdata_set()
        rc (int): the connection result
    """
    _ = client, userdata, rc

    LOGGER.debug("MQTT Client disconnected")
    MQTT_CLIENT.connect(MQTT_HOST)


@on_exception()  # type: ignore[misc]
def main() -> None:
    """Main function for this script"""

    MQTT_CLIENT.on_connect = on_connect
    MQTT_CLIENT.on_disconnect = on_disconnect
    MQTT_CLIENT.on_message = on_message

    MQTT_CLIENT.connect(MQTT_HOST)
    MQTT_CLIENT.subscribe(CRT_DISPLAY_MQTT_TOPIC)
    MQTT_CLIENT.subscribe(HA_CRT_PI_STATE_FROM_HA_TOPIC)
    MQTT_CLIENT.loop_start()

    LOGGER.debug("MQTT client connected, starting CRT mainloop")
    CRT.start_gui()
    MQTT_CLIENT.loop_stop(force=True)


if __name__ == "__main__":
    main()
