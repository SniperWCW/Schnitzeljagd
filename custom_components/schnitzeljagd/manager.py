"""Verbindet die Spiellogik mit Home Assistant (Skripte, Speicher, Events)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.script import Script
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    EVENT_STATION_CHANGED,
    EVENT_TASK_COMPLETED,
    SIGNAL_UPDATE,
)
from .engine import HuntEngine
from .model import Actions, Hunt

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class HuntManager:
    """Ein Manager pro Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, hunt: Hunt) -> None:
        self.hass = hass
        self.entry = entry
        self.hunt = hunt
        self.engine = HuntEngine(hunt)
        self.signal = SIGNAL_UPDATE.format(entry.entry_id)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._scripts: list[Script] = []

    # ------------------------------------------------------------------ #
    # Lebenszyklus
    # ------------------------------------------------------------------ #
    async def async_load(self) -> None:
        self.engine.restore(await self._store.async_load())

    async def async_unload(self) -> None:
        await self._stop_scripts()
        await self._store.async_save(self.engine.as_dict())

    # ------------------------------------------------------------------ #
    # Öffentliche Aktionen (werden von Services und Entities genutzt)
    # ------------------------------------------------------------------ #
    async def async_prepare(self) -> None:
        self._commit(self.engine.prepare(), "prepare")

    async def async_stop(self) -> None:
        # Laufende Clips/Sequenzen zuerst abbrechen, dann Stopp-Aktionen starten.
        await self._stop_scripts()
        self._commit(self.engine.stop(), "stop")

    async def async_reset(self) -> None:
        await self._stop_scripts()
        self._commit(self.engine.reset(), "reset")

    async def async_set_station(self, station_id: str) -> None:
        self.engine.set_station(station_id)
        self._fire_station_changed()
        self._commit([], "set_station")

    async def async_start_station(self, station_id: str | None = None) -> None:
        actions = self.engine.start_station(station_id)
        self._fire_station_changed()
        self._commit(actions, f"station {self.engine.current_station}")

    async def async_run_clip(self, station_id: str, clip_id: str) -> None:
        self._commit(self.engine.run_clip(station_id, clip_id), f"clip {clip_id}")

    async def async_complete_task(self, task_id: str) -> None:
        before = self.engine.current_station
        actions = self.engine.complete_task(task_id)
        self.hass.bus.async_fire(
            EVENT_TASK_COMPLETED,
            {"entry_id": self.entry.entry_id, "task": task_id, "progress": self.engine.progress},
        )
        if self.engine.current_station != before:
            self._fire_station_changed()
        self._commit(actions, f"task {task_id}")

    async def async_uncomplete_task(self, task_id: str) -> None:
        self.engine.uncomplete_task(task_id)
        self._commit([], "uncomplete")

    async def async_release_treasure(self) -> None:
        self._commit(self.engine.release_treasure(), "treasure")

    # ------------------------------------------------------------------ #
    # Intern
    # ------------------------------------------------------------------ #
    def _fire_station_changed(self) -> None:
        self.hass.bus.async_fire(
            EVENT_STATION_CHANGED,
            {"entry_id": self.entry.entry_id, "station": self.engine.current_station},
        )

    def _commit(self, actions: Actions, label: str) -> None:
        """Speichert den Zustand, informiert Entities, startet Aktionen im Hintergrund."""
        self._store.async_delay_save(self.engine.as_dict, 1)
        async_dispatcher_send(self.hass, self.signal)
        if actions:
            self.entry.async_create_background_task(
                self.hass,
                self._run(actions, label),
                name=f"{DOMAIN} {self.hunt.name} {label}",
            )

    async def _run(self, actions: Actions, label: str) -> None:
        script = Script(self.hass, actions, f"{self.hunt.name}: {label}", DOMAIN)
        self._scripts.append(script)
        variables = {
            "station": self.engine.current_station,
            "progress": self.engine.progress,
            "hunt": self.hunt.name,
        }
        try:
            await script.async_run(variables, Context())
        except Exception:  # noqa: BLE001 - ein Fehler darf die Jagd nicht stoppen
            _LOGGER.exception("Aktion '%s' der Schnitzeljagd ist fehlgeschlagen", label)
        finally:
            if script in self._scripts:
                self._scripts.remove(script)

    async def _stop_scripts(self) -> None:
        for script in list(self._scripts):
            await script.async_stop()
