"""Sensoren: aktuelle Station und Fortschritt."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HuntEntity
from .manager import HuntManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager: HuntManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CurrentStationSensor(manager), ProgressSensor(manager)])


class CurrentStationSensor(HuntEntity, SensorEntity):
    _attr_translation_key = "current_station"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, manager: HuntManager) -> None:
        super().__init__(manager, "current_station")

    @property
    def native_value(self) -> str:
        return self.manager.hunt.station_label(self.manager.engine.current_station)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        station = self.manager.hunt.station(self.manager.engine.current_station)
        return {
            "station_id": station.id,
            "station_name": station.name,
            "description": station.description,
        }


class ProgressSensor(HuntEntity, SensorEntity):
    _attr_translation_key = "progress"
    _attr_icon = "mdi:progress-check"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: HuntManager) -> None:
        super().__init__(manager, "progress")

    @property
    def native_value(self) -> int:
        return self.manager.engine.progress

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        engine = self.manager.engine
        return {
            "completed": len(engine.completed),
            "total": engine.total_tasks,
            "open_tasks": [t.name for t in engine.hunt.tasks if t.id not in engine.completed],
        }
