"""Lädt und validiert Schnitzeljagd-Dateien (Home-Assistant-Seite)."""

from __future__ import annotations

import os
import shutil
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.util.yaml import load_yaml

from .const import EXAMPLE_FILE
from .model import Hunt, HuntError, parse_hunt

EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "examples", EXAMPLE_FILE)


def _read(path: str) -> Any:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return load_yaml(path)


def _install_example(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copyfile(EXAMPLE_PATH, path)


async def async_install_example(hass: HomeAssistant, rel_path: str) -> None:
    """Kopiert die Beispieljagd (Funkel & Luna), falls die Datei noch fehlt."""
    path = hass.config.path(rel_path)
    if not await hass.async_add_executor_job(os.path.isfile, path):
        await hass.async_add_executor_job(_install_example, path)


async def async_load_hunt(hass: HomeAssistant, rel_path: str) -> Hunt:
    """Liest die Datei im Executor und validiert Aktionen im Event-Loop."""
    path = hass.config.path(rel_path)
    try:
        raw = await hass.async_add_executor_job(_read, path)
    except FileNotFoundError:
        raise
    except Exception as err:  # noqa: BLE001 - YAML-Syntaxfehler o. ä.
        raise HuntError(f"Datei konnte nicht gelesen werden: {err}") from err
    return parse_hunt(raw, validate_actions=cv.SCRIPT_SCHEMA)
