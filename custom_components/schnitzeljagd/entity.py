"""Gemeinsame Basisklasse aller Entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import HuntManager


class HuntEntity(Entity):
    """Entity, die sich bei jeder Zustandsänderung der Jagd aktualisiert."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: HuntManager, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name=manager.hunt.name,
            manufacturer="Schnitzeljagd",
            model=manager.hunt.subtitle or "Schnitzeljagd",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.manager.signal, self.async_write_ha_state)
        )
