"""Datenmodell und Parser für Schnitzeljagd-Definitionen (ohne Home-Assistant-Imports)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Actions = list[dict[str, Any]]


class HuntError(Exception):
    """Basisfehler für Definition und Spiellogik."""


class UnknownStation(HuntError):
    """Station existiert nicht."""


class UnknownTask(HuntError):
    """Aufgabe existiert nicht."""


class UnknownClip(HuntError):
    """Clip/Zusatzaktion existiert nicht."""


class TaskAlreadyDone(HuntError):
    """Aufgabe wurde bereits bestätigt."""


@dataclass(frozen=True)
class Clip:
    """Zusätzliche manuelle Aktion einer Station (z. B. "Finale Teil 1")."""

    id: str
    name: str
    actions: Actions = field(default_factory=list)
    icon: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Station:
    """Eine Station der Schnitzeljagd."""

    id: str
    name: str
    icon: str | None = None
    description: str = ""
    intro: Actions = field(default_factory=list)
    clips: tuple[Clip, ...] = ()


@dataclass(frozen=True)
class Task:
    """Eine Aufgabe, deren Erfolg per Haken bestätigt wird."""

    id: str
    name: str
    icon: str | None = None
    description: str = ""
    station: str | None = None
    on_complete: Actions = field(default_factory=list)
    next_station: str | None = None


@dataclass(frozen=True)
class Hunt:
    """Komplette Definition einer Schnitzeljagd."""

    name: str
    subtitle: str = ""
    icon: str | None = None
    stations: tuple[Station, ...] = ()
    tasks: tuple[Task, ...] = ()
    on_prepare: Actions = field(default_factory=list)
    on_stop: Actions = field(default_factory=list)
    on_reset: Actions = field(default_factory=list)
    treasure_task: str | None = None
    treasure_release: Actions = field(default_factory=list)

    def station(self, station_id: str) -> Station:
        for station in self.stations:
            if station.id == station_id:
                return station
        raise UnknownStation(f"Unbekannte Station: {station_id}")

    def task(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise UnknownTask(f"Unbekannte Aufgabe: {task_id}")

    def clip(self, station_id: str, clip_id: str) -> Clip:
        for clip in self.station(station_id).clips:
            if clip.id == clip_id:
                return clip
        raise UnknownClip(f"Unbekannter Clip {clip_id} in Station {station_id}")

    def station_label(self, station_id: str) -> str:
        """Anzeigename im Stil "1 · Esszimmer"."""
        return f"{station_id} · {self.station(station_id).name}"


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

Validator = Callable[[Any], Any]


def _actions(raw: Any, where: str, validate: Validator | None) -> Actions:
    """Normalisiert eine Aktionsliste (None, einzelnes Dict oder Liste)."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise HuntError(f"{where}: Aktionen müssen eine Liste von Einträgen sein")
    if validate is not None:
        try:
            raw = validate(raw)
        except Exception as err:  # noqa: BLE001 - voluptuous.Invalid o. ä.
            raise HuntError(f"{where}: ungültige Aktion ({err})") from err
    return list(raw)


def _text(raw: dict[str, Any], key: str, where: str, *, required: bool = False) -> str:
    value = raw.get(key)
    if value is None or str(value).strip() == "":
        if required:
            raise HuntError(f"{where}: '{key}' fehlt")
        return ""
    return str(value).strip()


def _opt_id(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    return None if value is None else str(value)


def parse_hunt(data: Any, validate_actions: Validator | None = None) -> Hunt:
    """Wandelt ein geladenes YAML-Dict in ein Hunt-Objekt um.

    `validate_actions` ist im Betrieb `cv.SCRIPT_SCHEMA`; in Tests entfällt es.
    """
    if not isinstance(data, dict):
        raise HuntError("Die Datei muss ein YAML-Objekt mit 'name' und 'stations' enthalten")

    name = _text(data, "name", "Schnitzeljagd", required=True)

    raw_stations = data.get("stations")
    if not isinstance(raw_stations, list) or not raw_stations:
        raise HuntError("'stations' muss eine nicht-leere Liste sein")

    stations: list[Station] = []
    for idx, raw in enumerate(raw_stations, start=1):
        if not isinstance(raw, dict):
            raise HuntError(f"Station #{idx}: muss ein Objekt sein")
        station_id = str(raw.get("id", idx))
        where = f"Station {station_id}"
        if any(s.id == station_id for s in stations):
            raise HuntError(f"{where}: ID doppelt vergeben")

        clips: list[Clip] = []
        for cidx, rawclip in enumerate(raw.get("clips") or [], start=1):
            if not isinstance(rawclip, dict):
                raise HuntError(f"{where}: Clip #{cidx} muss ein Objekt sein")
            clip_id = str(rawclip.get("id", f"clip{cidx}"))
            if any(c.id == clip_id for c in clips):
                raise HuntError(f"{where}: Clip-ID {clip_id} doppelt vergeben")
            clips.append(
                Clip(
                    id=clip_id,
                    name=_text(rawclip, "name", f"{where}/Clip {clip_id}", required=True),
                    actions=_actions(rawclip.get("actions"), f"{where}/Clip {clip_id}", validate_actions),
                    icon=rawclip.get("icon"),
                    description=_text(rawclip, "description", where),
                )
            )

        stations.append(
            Station(
                id=station_id,
                name=_text(raw, "name", where, required=True),
                icon=raw.get("icon"),
                description=_text(raw, "description", where),
                intro=_actions(raw.get("intro"), f"{where}/intro", validate_actions),
                clips=tuple(clips),
            )
        )

    station_ids = {s.id for s in stations}

    tasks: list[Task] = []
    for idx, raw in enumerate(data.get("tasks") or [], start=1):
        if not isinstance(raw, dict):
            raise HuntError(f"Aufgabe #{idx}: muss ein Objekt sein")
        task_id = str(raw.get("id", f"task{idx}"))
        where = f"Aufgabe {task_id}"
        if any(t.id == task_id for t in tasks):
            raise HuntError(f"{where}: ID doppelt vergeben")
        station = _opt_id(raw, "station")
        next_station = _opt_id(raw, "next_station")
        for label, ref in (("station", station), ("next_station", next_station)):
            if ref is not None and ref not in station_ids:
                raise HuntError(f"{where}: '{label}' verweist auf unbekannte Station {ref}")
        tasks.append(
            Task(
                id=task_id,
                name=_text(raw, "name", where, required=True),
                icon=raw.get("icon"),
                description=_text(raw, "description", where),
                station=station,
                on_complete=_actions(raw.get("on_complete"), f"{where}/on_complete", validate_actions),
                next_station=next_station,
            )
        )

    task_ids = {t.id for t in tasks}

    treasure_task: str | None = None
    treasure_release: Actions = []
    raw_treasure = data.get("treasure")
    if raw_treasure is not None:
        if not isinstance(raw_treasure, dict):
            raise HuntError("'treasure' muss ein Objekt sein")
        treasure_task = _opt_id(raw_treasure, "released_by")
        if treasure_task is not None and treasure_task not in task_ids:
            raise HuntError(f"treasure.released_by verweist auf unbekannte Aufgabe {treasure_task}")
        treasure_release = _actions(raw_treasure.get("release"), "treasure/release", validate_actions)

    return Hunt(
        name=name,
        subtitle=_text(data, "subtitle", "Schnitzeljagd"),
        icon=data.get("icon"),
        stations=tuple(stations),
        tasks=tuple(tasks),
        on_prepare=_actions(data.get("on_prepare"), "on_prepare", validate_actions),
        on_stop=_actions(data.get("on_stop"), "on_stop", validate_actions),
        on_reset=_actions(data.get("on_reset"), "on_reset", validate_actions),
        treasure_task=treasure_task,
        treasure_release=treasure_release,
    )
