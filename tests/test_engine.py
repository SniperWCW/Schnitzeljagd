"""Tests für Parser und Spiellogik (laufen ohne Home Assistant)."""

import importlib.util
import pathlib
import sys
import types

import pytest
import yaml

PKG = pathlib.Path(__file__).parents[1] / "custom_components" / "schnitzeljagd"

# model.py/engine.py ohne den HA-abhängigen __init__.py laden: Mini-Paket "sj_pkg"
pkg = types.ModuleType("sj_pkg")
pkg.__path__ = [str(PKG)]
sys.modules["sj_pkg"] = pkg
for _name in ("model", "engine"):
    _spec = importlib.util.spec_from_file_location(f"sj_pkg.{_name}", PKG / f"{_name}.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"sj_pkg.{_name}"] = _mod
    _spec.loader.exec_module(_mod)

from sj_pkg.engine import HuntEngine  # noqa: E402
from sj_pkg.model import (  # noqa: E402
    HuntError,
    TaskAlreadyDone,
    UnknownStation,
    UnknownTask,
    parse_hunt,
)

EXAMPLE = PKG / "examples" / "funkel_luna.yaml"


@pytest.fixture
def hunt():
    return parse_hunt(yaml.safe_load(EXAMPLE.read_text(encoding="utf-8")))


@pytest.fixture
def engine(hunt):
    return HuntEngine(hunt)


def test_example_parses(hunt):
    assert hunt.name == "Funkel & Luna"
    assert len(hunt.stations) == 6
    assert len(hunt.tasks) == 7
    assert hunt.treasure_task == "schatz"
    assert hunt.clip("6", "finale_1").name == "Finale Teil 1 starten"
    assert hunt.station_label("1") == "1 · Esszimmer"


def test_progress_and_completion(engine):
    assert engine.progress == 0
    actions = engine.complete_task("nest")
    assert actions == []
    assert engine.current_station == "2"
    assert engine.progress == round(100 / 7)
    assert engine.running


def test_task_runs_only_once(engine):
    engine.complete_task("rainbow_fixed")
    with pytest.raises(TaskAlreadyDone):
        engine.complete_task("rainbow_fixed")


def test_uncomplete_allows_replay(engine):
    engine.complete_task("lava_field")
    engine.uncomplete_task("lava_field")
    assert not engine.is_done("lava_field")
    assert engine.complete_task("lava_field")  # Aktionen laufen wieder


def test_treasure_released_by_final_task(engine):
    assert not engine.treasure_released
    actions = engine.complete_task("schatz")
    assert engine.treasure_released
    services = [a["service"] for a in actions]
    assert services == ["media_player.play_media", "lock.unlock"]


def test_manual_treasure_release(engine):
    actions = engine.release_treasure()
    assert engine.treasure_released
    assert actions[0]["service"] == "lock.unlock"


def test_start_station_selects_and_returns_intro(engine, hunt):
    actions = engine.start_station("3")
    assert engine.current_station == "3"
    assert actions == hunt.station("3").intro


def test_unknown_ids(engine):
    with pytest.raises(UnknownStation):
        engine.set_station("99")
    with pytest.raises(UnknownTask):
        engine.complete_task("gibtsnicht")


def test_reset_and_stop(engine, hunt):
    engine.complete_task("nest")
    engine.complete_task("schatz")
    engine.prepare()
    stop_actions = engine.stop()
    assert not engine.running
    assert stop_actions == hunt.on_stop
    engine.reset()
    assert engine.completed == set()
    assert not engine.treasure_released
    assert engine.current_station == "1"
    assert engine.progress == 0


def test_persistence_roundtrip(engine, hunt):
    engine.complete_task("nest")
    engine.start_station("2")
    saved = engine.as_dict()

    fresh = HuntEngine(hunt)
    fresh.restore(saved)
    assert fresh.completed == {"nest"}
    assert fresh.current_station == "2"
    assert fresh.running


def test_restore_ignores_unknown_ids(hunt):
    engine = HuntEngine(hunt)
    engine.restore({"current_station": "42", "completed": ["nest", "weg"], "running": True})
    assert engine.current_station == "1"
    assert engine.completed == {"nest"}


@pytest.mark.parametrize(
    "data, fragment",
    [
        (None, "YAML-Objekt"),
        ({"stations": [{"name": "A"}]}, "'name' fehlt"),
        ({"name": "X", "stations": []}, "nicht-leere Liste"),
        ({"name": "X", "stations": [{"id": 1, "name": "A"}, {"id": "1", "name": "B"}]}, "doppelt"),
        (
            {"name": "X", "stations": [{"id": 1, "name": "A"}], "tasks": [{"id": "t", "name": "T", "station": "9"}]},
            "unbekannte Station",
        ),
        (
            {"name": "X", "stations": [{"id": 1, "name": "A"}], "treasure": {"released_by": "nope"}},
            "unbekannte Aufgabe",
        ),
        (
            {"name": "X", "stations": [{"id": 1, "name": "A", "intro": "kaputt"}]},
            "Liste von Einträgen",
        ),
    ],
)
def test_invalid_definitions(data, fragment):
    with pytest.raises(HuntError) as err:
        parse_hunt(data)
    assert fragment in str(err.value)


def test_single_action_dict_is_wrapped():
    hunt = parse_hunt(
        {"name": "X", "stations": [{"id": 1, "name": "A", "intro": {"service": "light.turn_on"}}]}
    )
    assert hunt.stations[0].intro == [{"service": "light.turn_on"}]


def test_validator_errors_are_wrapped():
    def boom(_):
        raise ValueError("kaputt")

    with pytest.raises(HuntError) as err:
        parse_hunt(
            {"name": "X", "stations": [{"id": 1, "name": "A", "intro": [{"x": 1}]}]},
            validate_actions=boom,
        )
    assert "ungültige Aktion" in str(err.value)
