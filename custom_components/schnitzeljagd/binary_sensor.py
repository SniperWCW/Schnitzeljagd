"""Binäre Sensoren: Spiel läuft, Schatz freigegeben."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
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
    async_add_entities([RunningSensor(manager), TreasureSensor(manager)])


class RunningSensor(HuntEntity, BinarySensorEntity):
    _attr_translation_key = "running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, manager: HuntManager) -> None:
        super().__init__(manager, "running")

    @property
    def is_on(self) -> bool:
        return self.manager.engine.running


class TreasureSensor(HuntEntity, BinarySensorEntity):
    """An = Schatz freigegeben (Device-Class "lock": an bedeutet entriegelt)."""

    _attr_translation_key = "treasure"
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, manager: HuntManager) -> None:
        super().__init__(manager, "treasure")

    @property
    def is_on(self) -> bool:
        return self.manager.engine.treasure_released
