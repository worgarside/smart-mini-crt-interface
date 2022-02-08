"""
This module contains the methods used in the API definition
"""

from logging import getLogger, DEBUG
from os import getenv

from flask import Flask

from const import (
    CONFIG_FILE,
    FH,
    SH,
    switch_crt_on,
    switch_crt_off,
    set_config,
    get_config,
)

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
LOGGER.addHandler(FH)
LOGGER.addHandler(SH)

LOGGER.debug("Config file is `%s`", CONFIG_FILE)

app = Flask(__name__)
app.config["DEBUG"] = True


@app.route("/crt/state", methods=["GET"])
def crt_state():
    """API endpoint for getting the CRT state"""

    LOGGER.info("API hit on `/crt/state`")

    return get_config(keys=["crt"])


@app.route("/crt/on", methods=["GET"])
def crt_on():
    """API endpoint for turning the CRT on"""

    LOGGER.info("API hit on `/crt/on`")

    set_config(True, keys=["crt", "state"])

    switch_crt_on()

    return "<p>CRT On</p>"


@app.route("/crt/off", methods=["GET"])
def crt_off():
    """API endpoint for turning the CRT off"""

    LOGGER.info("API hit on `/crt/off`")

    set_config(False, keys=["crt", "state"])

    switch_crt_off()

    return "<p>CRT Off</p>"


@app.route("/crt/toggle", methods=["GET"])
def crt_toggle():
    """API endpoint for toggling the CRT power state"""

    LOGGER.info("API hit on `/crt/toggle`")

    new_state = not get_config(keys=["crt", "state"])
    set_config(new_state, keys=["crt", "state"])

    if new_state:
        switch_crt_on()
    else:
        switch_crt_off()

    return f"""<p>CRT {"On" if new_state else "Off"}</p>"""


@app.route("/nanoleaf-mirror/state", methods=["GET"])
def nanoleaf_state():
    """API endpoint for getting the Nanoleaf artwork mirroring state"""

    LOGGER.info("API hit on `/nanoleaf-mirror/state`")

    return get_config(keys=["nanoleafControl"])


@app.route("/nanoleaf-mirror/on", methods=["GET"])
def nanoleaf_on():
    """API endpoint for turning Nanoleaf artwork mirroring on"""

    LOGGER.info("API hit on `/nanoleaf-mirror/on`")

    set_config(True, keys=["nanoleafControl", "state"])

    return "<p>Nanoleaf Control On</p>"


@app.route("/nanoleaf-mirror/off", methods=["GET"])
def nanoleaf_off():
    """API endpoint for turning Nanoleaf artwork mirroring off"""

    LOGGER.info("API hit on `/nanoleaf-mirror/off`")

    set_config(False, keys=["nanoleafControl", "state"])

    return "<p>Nanoleaf Control Off</p>"


@app.route("/nanoleaf-mirror/toggle", methods=["GET"])
def nanoleaf_toggle():
    """API endpoint for toggling Nanoleaf artwork mirroring"""

    LOGGER.info("API hit on `/nanoleaf-mirror/toggle`")

    new_state = not get_config(keys=["nanoleafControl", "state"])

    set_config(new_state, keys=["nanoleafControl", "state"])

    return "<p>Nanoleaf Control " + "On" if new_state else "Off" + "</p>"


@app.route("/effect", methods=["GET"])
def effect():
    """API endpoint for getting the current and previous effect dicts"""

    LOGGER.info("API hit on `/effect`")

    return get_config(keys=["effect"])


@app.route("/effect/current", methods=["GET"])
def effect_current():
    """API endpoint for getting the current effect dict"""

    LOGGER.info("API hit on `/effect/current`")

    return get_config(keys=["effect", "current"])


@app.route("/effect/previous", methods=["GET"])
def effect_previous():
    """API endpoint for getting the previous effect dict"""

    LOGGER.info("API hit on `/effect/previous`")

    return get_config(keys=["effect", "previous"])


@app.route("/config", methods=["GET"])
def config():
    """API endpoint for getting the config"""

    LOGGER.info("API hit on `/config`")

    return get_config(keys=[])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(getenv("CRT_API_PORT", "5000")))
