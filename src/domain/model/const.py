"""All constants and functions to be used across the entire project."""
from __future__ import annotations

try:
    from pigpio import OUTPUT  # type: ignore[import-not-found]
    from pigpio import pi as rasp_pi
except (AttributeError, ImportError):
    from unittest.mock import MagicMock

    rasp_pi = MagicMock()
    OUTPUT = None

CRT_PIN = 26
FAN_PIN = 18

PI = rasp_pi()
PI.set_mode(CRT_PIN, OUTPUT)
PI.set_mode(FAN_PIN, OUTPUT)
