"""
Module for holding all constants and functions to be used across the entire project
"""

from datetime import datetime
from json import dump, load
from logging import StreamHandler, FileHandler, Formatter, getLogger, DEBUG
from os import mkdir, getenv
from os.path import exists, join, abspath, dirname
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import load_dotenv
from sys import stdout

try:
    from pigpio import pi as rasp_pi, OUTPUT
except (AttributeError, ImportError):
    rasp_pi = MagicMock()
    OUTPUT = None

load_dotenv()

# ################### CONSTANTS ################### #

TODAY_STR = datetime.today().strftime("%Y-%m-%d")

CRT_PIN = int(getenv("CRT_PIN", "-1"))

CAST_NAME = "HiFi System"

PI = rasp_pi()
PI.set_mode(CRT_PIN, OUTPUT)

# ################### DIRECTORIES / FILES ################### #

LOG_DIR = join(str(Path.home()), "logs", "smart-mini-crt-interface")

for _dir in [join(str(Path.home()), "logs"), LOG_DIR]:
    if not exists(_dir):
        mkdir(_dir)

CONFIG_FILE = join(abspath(dirname(__file__)), "config.json")

_DEFAULT_CONFIG = {"crt": {"state": True}, "nanoleafControl": {"state": True}}

if not exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as _fout:
        dump(_DEFAULT_CONFIG, _fout)
else:

    def _add_keys_to_dict(input_dict, output_dict):
        for k, v in input_dict.items():
            if k not in output_dict:
                output_dict[k] = v
            elif isinstance(v, dict):
                _add_keys_to_dict(v, output_dict[k])

    with open(CONFIG_FILE) as _fin:
        loaded_config = load(_fin)

    _add_keys_to_dict(_DEFAULT_CONFIG, loaded_config)

    with open(CONFIG_FILE, "w") as _fout:
        dump(loaded_config, _fout)

# ################### LOGGING ################### #

SH = StreamHandler(stdout)
FH = FileHandler(f"{LOG_DIR}/{TODAY_STR}.log")

FORMATTER = Formatter(
    "%(asctime)s\t%(name)s\t[%(levelname)s]\t%(message)s", "%Y-%m-%d %H:%M:%S"
)

FH.setFormatter(FORMATTER)
SH.setFormatter(FORMATTER)

_LOGGER = getLogger(__name__)
_LOGGER.setLevel(DEBUG)
_LOGGER.addHandler(FH)
_LOGGER.addHandler(SH)


# ################### FUNCTIONS ################### #


def get_config(*, keys):
    """Get a config value from the local config file

    Args:
        keys (list): the keys to use when traversing the config dictionary

    Returns:
        bool: the value of the config option
    """

    _LOGGER.debug("Getting config for `%s`", ".".join(keys))

    with open(CONFIG_FILE) as fin:
        config = load(fin)

    for key in keys:
        config = config.get(key, {})

    _LOGGER.debug("Value is `%s`", config)

    return config


def set_config(value, *, keys):
    """Sets a config value in the local config file

    Args:
        value (bool): the value to set the config option to
        keys (list): the list of keys to traverse the config dict with
    """

    _LOGGER.debug("Setting config to `%s` for `%s`", value, ".".join(keys))

    with open(CONFIG_FILE) as fin:
        config = load(fin)

    target_key = keys.pop()

    subconfig = None
    for i, key in enumerate(keys):
        if i == 0:
            subconfig = config.get(key, {})
        else:
            subconfig = subconfig.get(key, {})

    (subconfig or config)[target_key] = value

    with open(CONFIG_FILE, "w") as fout:
        dump(config, fout)


def switch_crt_on(force_switch_on=False):
    """Switch the CRT on by setting the GPIO pin to HIGH

    Args:
        force_switch_on (bool): option to override the config option
    """

    if force_switch_on or (get_config(keys=["crt", "state"]) and PI):
        _LOGGER.debug("Switching display on")
        PI.write(CRT_PIN, True)
        set_config(True, keys=["crt", "state"])
    else:
        _LOGGER.debug("Switching display on (but not really)")


def switch_crt_off(force_switch_off=False):
    """Switch the CRT off by setting the GPIO pin to LOW

    Args:
        force_switch_off (bool): option to override the config option
    """

    if force_switch_off or (not get_config(keys=["crt", "state"]) and PI):
        _LOGGER.debug("Switching display off")
        PI.write(CRT_PIN, False)
        set_config(False, keys=["crt", "state"])
    else:
        _LOGGER.debug("Switching display off (but not really)")
