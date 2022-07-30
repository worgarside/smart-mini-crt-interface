"""
Module for holding all constants and functions to be used across the entire project
"""
from datetime import datetime
from json import dump, load
from logging import DEBUG, getLogger
from os import getenv
from os.path import abspath, dirname, exists, join
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from wg_utilities.exceptions import on_exception  # pylint: disable=no-name-in-module
from wg_utilities.functions import force_mkdir
from wg_utilities.loggers import add_file_handler, add_stream_handler

try:
    from pigpio import OUTPUT
    from pigpio import pi as rasp_pi
except (AttributeError, ImportError):
    from unittest.mock import MagicMock

    rasp_pi = MagicMock()
    OUTPUT = None

load_dotenv()


class ConfigInfo(TypedDict):
    """Typing for the local config object"""

    crtState: bool


# ################### CONSTANTS ################### #

TODAY_STR = datetime.today().strftime("%Y-%m-%d")

CRT_PIN = 26
FAN_PIN = 18
FAN_MQTT_TOPIC = "/crt-pi/fan/state"

CAST_NAME = getenv("TARGET_CHROMECAST_NAME", "HiFi System")

PI = rasp_pi()
PI.set_mode(CRT_PIN, OUTPUT)
PI.set_mode(FAN_PIN, OUTPUT)

# ################### DIRECTORIES / FILES ################### #

LOG_DIR = force_mkdir(join(str(Path.home()), "logs", "smart-mini-crt-interface"))

CONFIG_FILE = join(abspath(dirname(__file__)), "config.json")

_DEFAULT_CONFIG = {"crtState": True}

if not exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as _fout:
        dump(_DEFAULT_CONFIG, _fout)
else:
    with open(CONFIG_FILE, encoding="utf-8") as _fin:
        loaded_config = load(_fin)


# ################### LOGGING ################### #

LOGGER = getLogger(__name__)
LOGGER.setLevel(DEBUG)
add_stream_handler(LOGGER)
add_file_handler(LOGGER, logfile_path=f"{LOG_DIR}/const/{TODAY_STR}.log")

# ################### FUNCTIONS ################### #


@on_exception()  # type: ignore[misc]
def get_crt_config_state() -> bool:
    """Get a config value from the local config file

    Returns:
        bool: the value of the config option
    """

    LOGGER.debug("Getting config for CRT state")

    with open(CONFIG_FILE, encoding="utf-8") as fin:
        config: ConfigInfo = load(fin)

    state = config.get("crtState", True)

    LOGGER.debug("Value is `%s`", state)

    return state


@on_exception()  # type: ignore[misc]
def set_crt_config_state(value: bool) -> None:
    """Sets a config value in the local config file

    Args:
        value (bool): the value to set the config option to
    """

    LOGGER.debug("Setting config to `%s`", value)

    with open(CONFIG_FILE, encoding="utf-8") as fin:
        config: ConfigInfo = load(fin)

    config["crtState"] = value

    with open(CONFIG_FILE, "w", encoding="utf-8") as fout:
        dump(config, fout)


@on_exception()  # type: ignore[misc]
def switch_crt_on(force_switch_on: bool = False) -> None:
    """Switch the CRT on by setting the GPIO pin to HIGH

    Args:
        force_switch_on (bool): option to override the config option
    """

    if force_switch_on or (get_crt_config_state() and PI):
        LOGGER.debug("Switching display on")
        PI.write(CRT_PIN, True)
        set_crt_config_state(True)
    else:
        LOGGER.debug("Switching display on (but not really)")


@on_exception()  # type: ignore[misc]
def switch_crt_off(force_switch_off: bool = False) -> None:
    """Switch the CRT off by setting the GPIO pin to LOW

    Args:
        force_switch_off (bool): option to override the config option
    """

    if force_switch_off or (not get_crt_config_state() and PI):
        LOGGER.debug("Switching display off")
        PI.write(CRT_PIN, False)
        set_crt_config_state(False)
    else:
        LOGGER.debug("Switching display off (but not really)")
