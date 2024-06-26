"""Simple script to control the CRT fan via MQTT."""

from __future__ import annotations

from logging import DEBUG, getLogger
from pathlib import Path
from sys import path
from typing import Any

from dotenv import load_dotenv
from paho.mqtt.client import MQTTMessage
from paho.mqtt.subscribe import callback
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))
# pylint: disable=wrong-import-position
from application.handler.mqtt import (  # noqa: E402
    FAN_MQTT_TOPIC,
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)
from domain.model.const import FAN_PIN, PI  # noqa: E402

load_dotenv()


ON_VALUES = (True, 1, "1", "on", "true", "True")
OFF_VALUES = (False, 0, "0", "off", "false", "False")

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


@on_exception()
def on_message(_: Any, __: Any, message: MQTTMessage) -> None:
    """Process env vars on MQTT message.

    Args:
        message (MQTTMessage): the message object from the MQTT subscription
    """
    pin_value = message.payload.decode() in ON_VALUES
    LOGGER.debug("Setting pin to %s", str(pin_value))
    PI.write(FAN_PIN, pin_value)


@on_exception()
def setup_callback() -> None:
    """Create callback for MQTT receives.

    This is only in a function to allow decoration.
    """
    LOGGER.info("Creating callback function")
    callback(
        on_message,
        [FAN_MQTT_TOPIC],
        hostname=MQTT_HOST,
        auth={
            "username": MQTT_USERNAME,
            "password": MQTT_PASSWORD,
        },
    )


if __name__ == "__main__":
    setup_callback()
