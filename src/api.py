"""
This module contains the methods used in the API definition
"""
from json import dumps
from logging import DEBUG, getLogger
from os import getenv

from flask import Flask
from wg_utilities.loggers import add_file_handler, add_stream_handler

from const import (
    FAN_PIN,
    LOG_DIR,
    PI,
    TODAY_STR,
    get_crt_config_state,
    set_crt_config_state,
    switch_crt_off,
    switch_crt_on,
)

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/api/{TODAY_STR}.log")

app = Flask(__name__)
app.config["DEBUG"] = False


@app.route("/crt/state", methods=["GET"])
def crt_state() -> str:
    """API endpoint for getting the CRT state"""

    LOGGER.info("API hit on `/crt/state`")

    return dumps({"state": get_crt_config_state()})


@app.route("/crt/fan", methods=["GET"])
def crt_fan() -> str:
    """API endpoint for getting the CRT state"""

    LOGGER.info("API hit on `/crt/fan`")

    return dumps({"state": PI.read(FAN_PIN)})


@app.route("/crt/on", methods=["GET"])
def crt_on() -> str:
    """API endpoint for turning the CRT on"""

    LOGGER.info("API hit on `/crt/on`")

    set_crt_config_state(True)

    switch_crt_on()

    return "<p>CRT On</p>"


@app.route("/crt/off", methods=["GET"])
def crt_off() -> str:
    """API endpoint for turning the CRT off"""

    LOGGER.info("API hit on `/crt/off`")

    set_crt_config_state(False)

    switch_crt_off()

    return "<p>CRT Off</p>"


@app.route("/crt/toggle", methods=["GET"])
def crt_toggle() -> str:
    """API endpoint for toggling the CRT power state"""

    LOGGER.info("API hit on `/crt/toggle`")

    new_state = not get_crt_config_state()
    set_crt_config_state(new_state)

    if new_state:
        switch_crt_on()
    else:
        switch_crt_off()

    return f"""<p>CRT {"On" if new_state else "Off"}</p>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(getenv("CRT_API_PORT", "5000")), debug=False)
