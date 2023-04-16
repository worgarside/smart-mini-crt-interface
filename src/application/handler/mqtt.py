"""Main controller function(s) for controlling the GUI."""
from __future__ import annotations

from logging import DEBUG, getLogger
from os import environ, getenv
from random import uniform
from sys import exit as sys_exit
from time import sleep

from dotenv import load_dotenv
from paho.mqtt.client import Client
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

load_dotenv()

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


MQTT_CLIENT = Client()
MQTT_USERNAME = environ["MQTT_USERNAME"]
MQTT_PASSWORD = environ["MQTT_PASSWORD"]
MQTT_CLIENT.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
MQTT_HOST = getenv("MQTT_HOST", "homeassistant.local")

FAN_MQTT_TOPIC = "/crt-pi/fan/state"
CRT_DISPLAY_MQTT_TOPIC = "/crt-pi/display/update_display"

FORCE_HA_UPDATE_TOPIC = "/home-assistant/script/crt_pi_update_display/run"
HA_CRT_PI_STATE_FROM_CRT_TOPIC = "/home-assistant/crt-pi/state-from-crt"
HA_CRT_PI_STATE_FROM_HA_TOPIC = "/home-assistant/crt-pi/state-from-ha"


@on_exception()
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


@on_exception()
def on_disconnect(client: Client, userdata: dict[str, object], rc: int) -> None:
    """Called when the client disconnects from the broker.

    Args:
        client (Client): the client instance for this callback
        userdata (dict): the private user data as set in Client() or userdata_set()
        rc (int): the connection result
    """
    _ = client, userdata, rc

    LOGGER.debug("MQTT Client disconnected")
    try:
        for i in range(5):
            MQTT_CLIENT.connect(MQTT_HOST)
            if MQTT_CLIENT.is_connected():
                break
            LOGGER.error("MQTT Client failed to connect, retrying...")
            sleep(i * (1 + uniform(0, 1)))
        else:
            raise ConnectionError("MQTT Client failed to connect")
    except ConnectionError:
        # The above doesn't seem to cause a non-zero exit code, so we'll do it manually
        sys_exit(1)


MQTT_CLIENT.on_connect = on_connect
MQTT_CLIENT.on_disconnect = on_disconnect
MQTT_CLIENT.connect(MQTT_HOST)
