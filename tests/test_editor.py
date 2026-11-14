"""Tests für Serialisierung und Bearbeitungslogik des UI-Editors."""

import copy
import importlib.util
import json
import pathlib
import sys
import types

import pytest
import yaml

PKG = pathlib.Path(__file__).parents[1] / "custom_components" / "schnitzeljagd"

pkg = sys.modules.get("sj_pkg") or types.ModuleType("sj_pkg")
pkg.__path__ = [str(PKG)]
sys.modules["sj_pkg"] = pkg
for _name in ("model", "engine", "editor"):
    _spec = importlib.util.spec_from_file_location(f"sj_pkg.{_name}", PKG / f"{_name}.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"sj_pkg.{_name}"] = _mod
    _spec.loader.exec_module(_mod)

from sj_pkg import editor  # noqa: E402
from sj_pkg.model import HuntError, hunt_to_dict, parse_hunt, unique_keys  # noqa: E402

EXAMPLE = PKG / "examples" / "funkel_luna.yaml"


@pytest.fixture
def stored():
    """Beispieljagd so, wie sie im Config-Entry gespeichert würde."""
    return hunt_to_dict(parse_hunt(yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))))


def test_roundtrip_is_stable_and_json_safe(stored):
    again = hunt_to_dict(parse_hunt(stored))
    assert again == stored
    assert json.loads(json.dumps(stored)) == stored  # keine Spezialtypen


def test_unique_keys_cover_stations_tasks_clips(stored):
    keys = unique_keys(parse_hunt(stored))
    assert {"start_1", "start_6", "task_schatz", "clip_6_finale_1", "progress"} <= keys
    assert len([k for k in keys if k.startswith("task_")]) == 7


def test_new_hunt_is_valid():
    hunt = parse_hunt(editor.new_hunt("Test"))
    assert hunt.name == "Test"
    assert [s.id for s in hunt.stations] == ["1"]


def test_station_add_edit_keeps_clips(stored):
    sid = editor.upsert_station(stored, None, {"name": "Garten", "intro": [{"service": "light.turn_on"}]})
    assert sid == "7"
    editor.upsert_station(stored, "6", {"name": "Wohnzimmer neu"})
    st = editor.find_station(stored, "6")
    assert st["name"] == "Wohnzimmer neu"
    assert st["clips"][0]["id"] == "finale_1"
    assert "intro" not in st  # leeres Feld entfernt
    parse_hunt(stored)


def test_station_delete_clears_task_links(stored):
    editor.delete_station(stored, "2")
    assert all(s["id"] != "2" for s in stored["stations"])
    nest = editor.find_task(stored, "nest")
    assert "next_station" not in nest
    assert "station" not in editor.find_task(stored, "rainbow_fixed")
    parse_hunt(stored)


def test_next_station_id_skips_used():
    hunt = {"stations": [{"id": "1", "name": "a"}, {"id": "3", "name": "b"}, {"id": "x", "name": "c"}]}
    assert editor.next_station_id(hunt) == "4"


def test_task_id_from_name_is_unique(stored):
    a = editor.upsert_task(stored, None, {"name": "Größe ändern!"})
    b = editor.upsert_task(stored, None, {"name": "Größe ändern!"})
    assert a == "groesse_aendern"
    assert b == "groesse_aendern_2"
    parse_hunt(stored)


def test_task_edit_replaces_fields(stored):
    editor.upsert_task(stored, "nest", {"name": "Nest neu", "station": "1"})
    task = editor.find_task(stored, "nest")
    assert task == {"id": "nest", "name": "Nest neu", "station": "1"}


def test_delete_task_removes_treasure_link(stored):
    editor.delete_task(stored, "schatz")
    assert "released_by" not in stored["treasure"]
    assert stored["treasure"]["release"]  # Freigabe-Aktionen bleiben
    parse_hunt(stored)


def test_clip_add_edit_delete(stored):
    cid = editor.upsert_clip(stored, "1", None, {"name": "Bonus", "actions": [{"delay": "00:00:01"}]})
    assert cid == "bonus"
    assert ("1|bonus", "1 · Esszimmer › Bonus") in editor.clip_options(stored)
    editor.upsert_clip(stored, "1", "bonus", {"name": "Bonus 2"})
    assert editor.find_clip(stored, "1", "bonus")["name"] == "Bonus 2"
    editor.delete_clip(stored, "1", "bonus")
    assert "clips" not in editor.find_station(stored, "1")
    with pytest.raises(KeyError):
        editor.find_clip(stored, "1", "bonus")


def test_general_global_and_treasure(stored):
    editor.set_general(stored, {"name": "Neu", "subtitle": ""})
    assert stored["name"] == "Neu" and "subtitle" not in stored
    editor.set_global_actions(stored, {"on_prepare": [{"delay": "00:00:01"}]})
    assert "on_stop" not in stored and stored["on_prepare"]
    editor.set_treasure(stored, {})
    assert "treasure" not in stored
    editor.set_treasure(stored, {"released_by": "nest"})
    assert parse_hunt(stored).treasure_task == "nest"


def test_deleting_all_stations_is_rejected_by_parser(stored):
    for sid in [s["id"] for s in stored["stations"]]:
        editor.delete_station(stored, sid)
    with pytest.raises(HuntError):
        parse_hunt(stored)


def test_editing_does_not_touch_original_copy(stored):
    snapshot = copy.deepcopy(stored)
    work = copy.deepcopy(stored)
    editor.delete_task(work, "nest")
    assert stored == snapshot
