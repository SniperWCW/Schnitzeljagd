"""Änderungen an einer gespeicherten Jagd (reine Dict-Funktionen, ohne Home Assistant).

Die Options-Flow-Schritte rufen diese Funktionen auf; dadurch ist die gesamte
Bearbeitungslogik ohne laufende HA-Instanz testbar.
"""

from __future__ import annotations

import re
from typing import Any

Hunt = dict[str, Any]

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def slug(text: str) -> str:
    """Einfacher Slug für IDs: "Regenbogen repariert!" -> "regenbogen_repariert"."""
    text = text.lower().translate(_UMLAUTS)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "item"


def new_hunt(name: str, subtitle: str = "") -> Hunt:
    """Leere Jagd mit einer Starter-Station (eine Jagd braucht mindestens eine)."""
    hunt: Hunt = {"name": name, "stations": [{"id": "1", "name": "Station 1"}], "tasks": []}
    if subtitle:
        hunt["subtitle"] = subtitle
    return hunt


def _clean(form: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in form.items() if v not in (None, "", [])}


# ----------------------------------------------------------------------- #
# Abfragen
# ----------------------------------------------------------------------- #
def find_station(hunt: Hunt, station_id: str) -> Hunt:
    for station in hunt["stations"]:
        if station["id"] == station_id:
            return station
    raise KeyError(station_id)


def find_task(hunt: Hunt, task_id: str) -> Hunt:
    for task in hunt.get("tasks", []):
        if task["id"] == task_id:
            return task
    raise KeyError(task_id)


def station_options(hunt: Hunt) -> list[tuple[str, str]]:
    return [(s["id"], f"{s['id']} · {s['name']}") for s in hunt["stations"]]


def task_options(hunt: Hunt) -> list[tuple[str, str]]:
    return [(t["id"], t["name"]) for t in hunt.get("tasks", [])]


def clip_options(hunt: Hunt) -> list[tuple[str, str]]:
    """Wert "stationId|clipId", Label "1 · Esszimmer › Clipname"."""
    return [
        (f"{s['id']}|{c['id']}", f"{s['id']} · {s['name']} › {c['name']}")
        for s in hunt["stations"]
        for c in s.get("clips", [])
    ]


def next_station_id(hunt: Hunt) -> str:
    used = {s["id"] for s in hunt["stations"]}
    numbers = [int(i) for i in used if i.isdigit()]
    candidate = max(numbers, default=0) + 1
    while str(candidate) in used:
        candidate += 1
    return str(candidate)


def _unique(existing: set[str], base: str) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


# ----------------------------------------------------------------------- #
# Allgemein, globale Aktionen, Schatz
# ----------------------------------------------------------------------- #
def set_general(hunt: Hunt, form: dict[str, Any]) -> None:
    for key in ("subtitle", "icon"):
        if form.get(key):
            hunt[key] = form[key]
        else:
            hunt.pop(key, None)
    hunt["name"] = form["name"]


def set_global_actions(hunt: Hunt, form: dict[str, Any]) -> None:
    for key in ("on_prepare", "on_stop", "on_reset"):
        if form.get(key):
            hunt[key] = form[key]
        else:
            hunt.pop(key, None)


def set_treasure(hunt: Hunt, form: dict[str, Any]) -> None:
    treasure = _clean({"released_by": form.get("released_by"), "release": form.get("release")})
    if treasure:
        hunt["treasure"] = treasure
    else:
        hunt.pop("treasure", None)


# ----------------------------------------------------------------------- #
# Stationen
# ----------------------------------------------------------------------- #
def upsert_station(hunt: Hunt, station_id: str | None, form: dict[str, Any]) -> str:
    """Legt eine Station an (station_id=None) oder ändert sie. Gibt die ID zurück."""
    fields = _clean(
        {
            "name": form["name"],
            "icon": form.get("icon"),
            "description": form.get("description"),
            "intro": form.get("intro"),
        }
    )
    if station_id is None:
        station_id = next_station_id(hunt)
        hunt["stations"].append({"id": station_id, **fields})
    else:
        station = find_station(hunt, station_id)
        clips = station.get("clips")
        station.clear()
        station.update({"id": station_id, **fields})
        if clips:
            station["clips"] = clips
    return station_id


def delete_station(hunt: Hunt, station_id: str) -> None:
    """Löscht die Station samt Clips; Aufgaben verlieren nur ihren Verweis."""
    hunt["stations"] = [s for s in hunt["stations"] if s["id"] != station_id]
    for task in hunt.get("tasks", []):
        for key in ("station", "next_station"):
            if task.get(key) == station_id:
                del task[key]


# ----------------------------------------------------------------------- #
# Aufgaben
# ----------------------------------------------------------------------- #
def upsert_task(hunt: Hunt, task_id: str | None, form: dict[str, Any]) -> str:
    fields = _clean(
        {
            "name": form["name"],
            "icon": form.get("icon"),
            "description": form.get("description"),
            "station": form.get("station"),
            "next_station": form.get("next_station"),
            "on_complete": form.get("on_complete"),
        }
    )
    tasks = hunt.setdefault("tasks", [])
    if task_id is None:
        task_id = _unique({t["id"] for t in tasks}, slug(form["name"]))
        tasks.append({"id": task_id, **fields})
    else:
        task = find_task(hunt, task_id)
        task.clear()
        task.update({"id": task_id, **fields})
    return task_id


def delete_task(hunt: Hunt, task_id: str) -> None:
    hunt["tasks"] = [t for t in hunt.get("tasks", []) if t["id"] != task_id]
    treasure = hunt.get("treasure")
    if treasure and treasure.get("released_by") == task_id:
        del treasure["released_by"]
        if not treasure:
            del hunt["treasure"]


# ----------------------------------------------------------------------- #
# Clips (Zusatzaktionen einer Station)
# ----------------------------------------------------------------------- #
def upsert_clip(hunt: Hunt, station_id: str, clip_id: str | None, form: dict[str, Any]) -> str:
    station = find_station(hunt, station_id)
    fields = _clean(
        {
            "name": form["name"],
            "icon": form.get("icon"),
            "description": form.get("description"),
            "actions": form.get("actions"),
        }
    )
    clips = station.setdefault("clips", [])
    if clip_id is None:
        clip_id = _unique({c["id"] for c in clips}, slug(form["name"]))
        clips.append({"id": clip_id, **fields})
    else:
        for clip in clips:
            if clip["id"] == clip_id:
                clip.clear()
                clip.update({"id": clip_id, **fields})
                break
        else:
            raise KeyError(clip_id)
    return clip_id


def find_clip(hunt: Hunt, station_id: str, clip_id: str) -> Hunt:
    for clip in find_station(hunt, station_id).get("clips", []):
        if clip["id"] == clip_id:
            return clip
    raise KeyError(clip_id)


def delete_clip(hunt: Hunt, station_id: str, clip_id: str) -> None:
    station = find_station(hunt, station_id)
    station["clips"] = [c for c in station.get("clips", []) if c["id"] != clip_id]
    if not station["clips"]:
        del station["clips"]
