"""Buttons: Spielsteuerung, Stationsclips und Zusatzaktionen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HuntEntity
from .manager import HuntManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: HuntManager = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = [
        ControlButton(manager, "prepare", "mdi:play-circle-outline", manager.async_prepare),
        ControlButton(manager, "stop", "mdi:stop-circle", manager.async_stop),
        ControlButton(manager, "reset", "mdi:restart", manager.async_reset),
        ControlButton(
            manager, "release_treasure", "mdi:treasure-chest", manager.async_release_treasure
        ),
    ]
    for station in manager.hunt.stations:
        entities.append(StationButton(manager, station.id))
        entities.extend(ClipButton(manager, station.id, clip.id) for clip in station.clips)
    async_add_entities(entities)


class ControlButton(HuntEntity, ButtonEntity):
    """Vorbereiten, Stoppen, Zurücksetzen, Schatz freigeben."""

    def __init__(
        self,
        manager: HuntManager,
        key: str,
        icon: str,
        press: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(manager, key)
        self._attr_translation_key = key
        self._attr_icon = icon
        self._press = press

    async def async_press(self) -> None:
        await self._press()


class StationButton(HuntEntity, ButtonEntity):
    """Startet den Einleitungsclip einer Station ("Szene starten")."""

    def __init__(self, manager: HuntManager, station_id: str) -> None:
        super().__init__(manager, f"start_{station_id}")
        station = manager.hunt.station(station_id)
        self.station_id = station_id
        self._attr_name = f"Station {station_id} · {station.name} starten"
        self._attr_icon = station.icon or "mdi:play-circle"

    async def async_press(self) -> None:
        await self.manager.async_start_station(self.station_id)


class ClipButton(HuntEntity, ButtonEntity):
    """Zusätzliche manuelle Aktion einer Station."""

    def __init__(self, manager: HuntManager, station_id: str, clip_id: str) -> None:
        super().__init__(manager, f"clip_{station_id}_{clip_id}")
        clip = manager.hunt.clip(station_id, clip_id)
        self.station_id = station_id
        self.clip_id = clip_id
        self._attr_name = f"Station {station_id} · {clip.name}"
        self._attr_icon = clip.icon or "mdi:movie-play"

    async def async_press(self) -> None:
        await self.manager.async_run_clip(self.station_id, self.clip_id)
