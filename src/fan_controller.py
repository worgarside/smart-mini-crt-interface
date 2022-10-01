"""Simple script to control the CRT fan via MQTT"""
from logging import DEBUG, getLogger
from os import getenv
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from paho.mqtt.subscribe import callback
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_file_handler, add_stream_handler

from const import FAN_MQTT_TOPIC, FAN_PIN, LOG_DIR, PI, TODAY_STR

load_dotenv()

MQTT_AUTH_KWARGS = {
    "hostname": getenv("MQTT_HOST"),
    "auth": {
        "username": getenv("MQTT_USERNAME"),
        "password": getenv("MQTT_PASSWORD"),
    },
}

ON_VALUES = (True, 1, "1", "on", "true", "True")
OFF_VALUES = (False, 0, "0", "off", "false", "False")

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/fan_controller/{TODAY_STR}.log")

# noinspection PyIncorrectDocstring
@on_exception()  # type: ignore[misc]
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Callback method for updating env vars on MQTT message

    Args:
        message (MQTTMessage): the message object from the MQTT subscription
    """
    pin_value = message.payload.decode() in ON_VALUES
    LOGGER.debug("Setting pin to %s", str(pin_value))
    PI.write(FAN_PIN, pin_value)


@on_exception()  # type: ignore[misc]
def setup_callback() -> None:
    """Function to create callback for MQTT receives, only in a function to allow
    decoration"""
    LOGGER.info("Creating callback function")
    callback(on_message, FAN_MQTT_TOPIC, **MQTT_AUTH_KWARGS)


if __name__ == "__main__":
    setup_callback()
