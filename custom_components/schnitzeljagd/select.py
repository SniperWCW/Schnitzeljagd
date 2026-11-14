"""Auswahl der aktuellen Station."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HuntEntity
from .manager import HuntManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: HuntManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StationSelect(manager)])


class StationSelect(HuntEntity, SelectEntity):
    _attr_translation_key = "station"
    _attr_icon = "mdi:map-marker"

    def __init__(self, manager: HuntManager) -> None:
        super().__init__(manager, "station")
        self._by_label = {manager.hunt.station_label(s.id): s.id for s in manager.hunt.stations}
        self._attr_options = list(self._by_label)

    @property
    def current_option(self) -> str:
        return self.manager.hunt.station_label(self.manager.engine.current_station)

    async def async_select_option(self, option: str) -> None:
        if option not in self._by_label:
            raise ServiceValidationError(f"Unbekannte Station: {option}")
        await self.manager.async_set_station(self._by_label[option])
