"""Schnitzeljagd – Schatzsuche-Steuerung für Home Assistant."""

from __future__ import annotations

import logging

from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENTRY,
    ATTR_STATION,
    ATTR_TASK,
    CONF_FILE,
    CONF_HUNT,
    DOMAIN,
    PLATFORMS,
    SERVICE_COMPLETE_TASK,
    SERVICE_PREPARE,
    SERVICE_RELEASE_TREASURE,
    SERVICE_RELOAD,
    SERVICE_RESET,
    SERVICE_SET_STATION,
    SERVICE_START_STATION,
    SERVICE_STOP,
)
from .loader import async_load_hunt, hunt_from_entry
from .manager import HuntManager
from .model import HuntError, unique_keys

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_BASE = {vol.Optional(ATTR_ENTRY): cv.string}

CARD_URL = f"/{DOMAIN}_static/schnitzeljagd-card.js"
CARD_FILE = Path(__file__).parent / "frontend" / "schnitzeljagd-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Stellt die mitgelieferte Lovelace-Karte bereit (`custom:schnitzeljagd-card`)."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    return True


def _manager(hass: HomeAssistant, call: ServiceCall) -> HuntManager:
    managers: dict[str, HuntManager] = hass.data.get(DOMAIN, {})
    if not managers:
        raise ServiceValidationError("Keine Schnitzeljagd eingerichtet")
    entry_id = call.data.get(ATTR_ENTRY)
    if entry_id is None:
        if len(managers) > 1:
            raise ServiceValidationError(
                "Mehrere Schnitzeljagden eingerichtet – 'config_entry' angeben"
            )
        return next(iter(managers.values()))
    if entry_id not in managers:
        raise ServiceValidationError(f"Unbekannte Schnitzeljagd: {entry_id}")
    return managers[entry_id]


def _wrap(handler):
    """Übersetzt Spielfehler in saubere Service-Fehlermeldungen."""

    async def inner(hass: HomeAssistant, call: ServiceCall) -> None:
        try:
            await handler(_manager(hass, call), call)
        except HuntError as err:
            raise ServiceValidationError(str(err)) from err

    return inner


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_PREPARE):
        return

    async def prepare(m: HuntManager, call: ServiceCall) -> None:
        await m.async_prepare()

    async def stop(m: HuntManager, call: ServiceCall) -> None:
        await m.async_stop()

    async def reset(m: HuntManager, call: ServiceCall) -> None:
        await m.async_reset()

    async def set_station(m: HuntManager, call: ServiceCall) -> None:
        await m.async_set_station(str(call.data[ATTR_STATION]))

    async def start_station(m: HuntManager, call: ServiceCall) -> None:
        station = call.data.get(ATTR_STATION)
        await m.async_start_station(None if station is None else str(station))

    async def complete_task(m: HuntManager, call: ServiceCall) -> None:
        await m.async_complete_task(str(call.data[ATTR_TASK]))

    async def release_treasure(m: HuntManager, call: ServiceCall) -> None:
        await m.async_release_treasure()

    async def reload_hunt(m: HuntManager, call: ServiceCall) -> None:
        await hass.config_entries.async_reload(m.entry.entry_id)

    services = {
        SERVICE_PREPARE: (prepare, vol.Schema(_BASE)),
        SERVICE_STOP: (stop, vol.Schema(_BASE)),
        SERVICE_RESET: (reset, vol.Schema(_BASE)),
        SERVICE_RELEASE_TREASURE: (release_treasure, vol.Schema(_BASE)),
        SERVICE_RELOAD: (reload_hunt, vol.Schema(_BASE)),
        SERVICE_SET_STATION: (
            set_station,
            vol.Schema({**_BASE, vol.Required(ATTR_STATION): cv.string}),
        ),
        SERVICE_START_STATION: (
            start_station,
            vol.Schema({**_BASE, vol.Optional(ATTR_STATION): cv.string}),
        ),
        SERVICE_COMPLETE_TASK: (
            complete_task,
            vol.Schema({**_BASE, vol.Required(ATTR_TASK): cv.string}),
        ),
    }

    for name, (handler, schema) in services.items():
        wrapped = _wrap(handler)

        async def _service(call: ServiceCall, _w=wrapped) -> None:
            await _w(hass, call)

        hass.services.async_register(DOMAIN, name, _service, schema=schema)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Lädt die Jagd-Datei und richtet Plattformen und Services ein."""
    try:
        if CONF_HUNT in entry.options:
            hunt = hunt_from_entry(entry)
        else:  # Einträge aus Version 0.1/0.2 lesen weiterhin die YAML-Datei
            hunt = await async_load_hunt(hass, entry.data[CONF_FILE])
    except FileNotFoundError as err:
        raise ConfigEntryNotReady(f"Jagd-Datei nicht gefunden: {err}") from err
    except HuntError as err:
        _LOGGER.error("Schnitzeljagd-Datei ungültig: %s", err)
        raise ConfigEntryNotReady(str(err)) from err

    manager = HuntManager(hass, entry, hunt)
    await manager.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    await _async_register_services(hass)
    _remove_orphaned_entities(hass, entry, manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_change))
    return True


def _remove_orphaned_entities(hass: HomeAssistant, entry: ConfigEntry, manager: HuntManager) -> None:
    """Entfernt Entities gelöschter Stationen, Aufgaben und Clips aus der Registry."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    valid = {prefix + key for key in unique_keys(manager.hunt)}
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ent.unique_id not in valid:
            registry.async_remove(ent.entity_id)


async def _async_reload_on_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if entry.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: HuntManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_unload()
        if not hass.data[DOMAIN]:
            for name in (
                SERVICE_PREPARE,
                SERVICE_STOP,
                SERVICE_RESET,
                SERVICE_SET_STATION,
                SERVICE_START_STATION,
                SERVICE_COMPLETE_TASK,
                SERVICE_RELEASE_TREASURE,
                SERVICE_RELOAD,
            ):
                hass.services.async_remove(DOMAIN, name)
    return unloaded
