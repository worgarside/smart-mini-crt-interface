"""Periodically report readings from the DHT22 sensor to Home Assistant."""

from __future__ import annotations

from json import dumps
from logging import DEBUG, getLogger
from pathlib import Path
from sys import path
from time import sleep

from paho.mqtt.publish import single
from pigpio import pi  # type: ignore[import-not-found]
from wg_utilities.devices.dht22 import DHT22Sensor
from wg_utilities.exceptions import on_exception
from wg_utilities.loggers import add_stream_handler

path.append(str(Path(__file__).parents[2]))

# pylint: disable=wrong-import-position
from application.handler.mqtt import (  # noqa: E402
    MQTT_HOST,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)


DHT22_PIN = 6
LOOP_DELAY_SECONDS = 30


@on_exception()
def main() -> None:
    """Take temp/humidity readings, write them to the LCD, upload them to HA."""

    dht22 = DHT22Sensor(pi(), DHT22_PIN)

    while True:
        dht22.trigger()

        payload = {}

        if (temp_reading := dht22.temperature) > 0:
            payload["temperature"] = round(temp_reading, 2)

        if (rhum_reading := dht22.humidity) > 0:
            payload["humidity"] = round(rhum_reading, 2)

        single(
            "/homeassistant/crtpi/dht22",
            payload=dumps(payload),
            hostname=MQTT_HOST,
            auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        )
        sleep(LOOP_DELAY_SECONDS)


if __name__ == "__main__":
    main()
