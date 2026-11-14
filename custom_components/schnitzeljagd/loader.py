"""Lädt und validiert Schnitzeljagd-Dateien (Home-Assistant-Seite)."""

from __future__ import annotations

import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.util.yaml import load_yaml

from .const import CONF_HUNT, EXAMPLE_FILE
from .model import Hunt, HuntError, hunt_to_dict, parse_hunt

EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "examples", EXAMPLE_FILE)


def _read(path: str) -> Any:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return load_yaml(path)


async def async_read_raw(hass: HomeAssistant, rel_path: str) -> Any:
    """Liest eine YAML-Datei (relativ zum Konfigurationsordner oder absolut)."""
    path = hass.config.path(rel_path)
    try:
        return await hass.async_add_executor_job(_read, path)
    except FileNotFoundError:
        raise
    except Exception as err:  # noqa: BLE001 - YAML-Syntaxfehler o. ä.
        raise HuntError(f"Datei konnte nicht gelesen werden: {err}") from err


async def async_import_yaml(hass: HomeAssistant, rel_path: str) -> dict[str, Any]:
    """Liest und prüft eine YAML-Jagd und gibt sie als speicherbares Dict zurück."""
    raw = await async_read_raw(hass, rel_path)
    parse_hunt(raw, validate_actions=cv.SCRIPT_SCHEMA)  # wirft HuntError bei Fehlern
    return hunt_to_dict(parse_hunt(raw))


async def async_import_example(hass: HomeAssistant) -> dict[str, Any]:
    """Die mitgelieferte Beispieljagd (Funkel & Luna) als speicherbares Dict."""
    return await async_import_yaml(hass, EXAMPLE_PATH)


def hunt_from_entry(entry: ConfigEntry) -> Hunt:
    """Baut die Jagd aus den im Config-Entry gespeicherten Daten (validiert Aktionen)."""
    return parse_hunt(entry.options[CONF_HUNT], validate_actions=cv.SCRIPT_SCHEMA)


async def async_load_hunt(hass: HomeAssistant, rel_path: str) -> Hunt:
    """Altes Verhalten (Version 0.1/0.2): Jagd direkt aus einer YAML-Datei."""
    raw = await async_read_raw(hass, rel_path)
    return parse_hunt(raw, validate_actions=cv.SCRIPT_SCHEMA)
