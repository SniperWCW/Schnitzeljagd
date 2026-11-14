"""Erfolgshaken je Aufgabe: Einschalten löst die Erfolgsaktionen genau einmal aus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities(TaskSwitch(manager, task.id) for task in manager.hunt.tasks)


class TaskSwitch(HuntEntity, SwitchEntity):
    """An = Aufgabe erledigt.

    Ein erneutes Einschalten ist wirkungslos (Aktionen laufen nur einmal).
    Ausschalten nimmt den Haken ohne Aktion zurück, falls er aus Versehen gesetzt wurde.
    Erneutes Abspielen geht über die Stations-Buttons oder `schnitzeljagd.reset`.
    """

    def __init__(self, manager: HuntManager, task_id: str) -> None:
        super().__init__(manager, f"task_{task_id}")
        task = manager.hunt.task(task_id)
        self.task_id = task_id
        self._attr_name = task.name
        self._attr_icon = task.icon or "mdi:checkbox-marked-circle-outline"

    @property
    def is_on(self) -> bool:
        return self.manager.engine.is_done(self.task_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        task = self.manager.hunt.task(self.task_id)
        return {"station": task.station, "description": task.description}

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self.is_on:
            await self.manager.async_complete_task(self.task_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.is_on:
            await self.manager.async_uncomplete_task(self.task_id)
