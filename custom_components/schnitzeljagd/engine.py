"""Spiellogik der Schnitzeljagd (ohne Home-Assistant-Imports, daher gut testbar).

Jede Methode ändert nur den Zustand und gibt die Aktionsliste zurück, die der
Manager anschließend als Home-Assistant-Skript ausführt.
"""

from __future__ import annotations

from typing import Any

from .model import Actions, Hunt, TaskAlreadyDone


class HuntEngine:
    """Hält den Spielzustand und entscheidet, was bei einer Eingabe passiert."""

    def __init__(self, hunt: Hunt) -> None:
        self.hunt = hunt
        self.running = False
        self.current_station: str = hunt.stations[0].id
        self.completed: set[str] = set()
        self.treasure_released = False

    # ------------------------------------------------------------------ #
    # Abfragen
    # ------------------------------------------------------------------ #
    @property
    def total_tasks(self) -> int:
        return len(self.hunt.tasks)

    @property
    def progress(self) -> int:
        """Fortschritt in Prozent (0-100)."""
        if not self.hunt.tasks:
            return 0
        return round(100 * len(self.completed) / len(self.hunt.tasks))

    def is_done(self, task_id: str) -> bool:
        return task_id in self.completed

    # ------------------------------------------------------------------ #
    # Spielsteuerung
    # ------------------------------------------------------------------ #
    def prepare(self) -> Actions:
        self.running = True
        return list(self.hunt.on_prepare)

    def stop(self) -> Actions:
        self.running = False
        return list(self.hunt.on_stop)

    def reset(self) -> Actions:
        self.running = False
        self.completed.clear()
        self.treasure_released = False
        self.current_station = self.hunt.stations[0].id
        return list(self.hunt.on_reset)

    def set_station(self, station_id: str) -> None:
        self.hunt.station(station_id)  # wirft UnknownStation
        self.current_station = station_id

    def start_station(self, station_id: str | None = None) -> Actions:
        """Wählt die Station aus und liefert ihren Einleitungsclip."""
        if station_id is not None:
            self.set_station(station_id)
        self.running = True
        return list(self.hunt.station(self.current_station).intro)

    def run_clip(self, station_id: str, clip_id: str) -> Actions:
        return list(self.hunt.clip(station_id, clip_id).actions)

    def complete_task(self, task_id: str) -> Actions:
        """Bestätigt eine Aufgabe (nur einmal) und liefert ihre Erfolgsaktionen."""
        task = self.hunt.task(task_id)
        if task_id in self.completed:
            raise TaskAlreadyDone(f"Aufgabe '{task.name}' ist bereits bestätigt")
        self.completed.add(task_id)
        self.running = True
        actions = list(task.on_complete)
        if task.next_station is not None:
            self.current_station = task.next_station
        if task_id == self.hunt.treasure_task:
            actions += self.release_treasure()
        return actions

    def uncomplete_task(self, task_id: str) -> None:
        """Nimmt einen versehentlichen Haken zurück, ohne Aktionen auszuführen."""
        self.hunt.task(task_id)
        self.completed.discard(task_id)

    def release_treasure(self) -> Actions:
        self.treasure_released = True
        return list(self.hunt.treasure_release)

    # ------------------------------------------------------------------ #
    # Persistenz
    # ------------------------------------------------------------------ #
    def as_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "current_station": self.current_station,
            "completed": sorted(self.completed),
            "treasure_released": self.treasure_released,
        }

    def restore(self, data: dict[str, Any] | None) -> None:
        """Stellt gespeicherten Zustand wieder her; unbekannte IDs werden ignoriert."""
        if not data:
            return
        self.running = bool(data.get("running", False))
        station = str(data.get("current_station", ""))
        if any(s.id == station for s in self.hunt.stations):
            self.current_station = station
        known = {t.id for t in self.hunt.tasks}
        self.completed = {str(t) for t in data.get("completed", []) if str(t) in known}
        self.treasure_released = bool(data.get("treasure_released", False))
