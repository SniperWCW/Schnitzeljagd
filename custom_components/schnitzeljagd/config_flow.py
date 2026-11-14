"""Config-Flow (Anlegen) und Options-Flow (kompletter Editor für die Jagd)."""

from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    ActionSelector,
    IconSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from . import editor
from .const import CONF_FILE, CONF_HUNT, DEFAULT_FILE, DOMAIN
from .loader import async_import_example, async_import_yaml
from .model import HuntError, parse_hunt

TEXT = TextSelector()
MULTILINE = TextSelector(TextSelectorConfig(multiline=True))


def _select(options: list[tuple[str, str]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=value, label=label) for value, label in options],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _check_actions(*sequences: Any) -> str | None:
    """Gibt None zurück, wenn alle Aktionslisten gültig sind, sonst die Fehlermeldung."""
    for seq in sequences:
        if not seq:
            continue
        try:
            cv.SCRIPT_SCHEMA(seq)
        except Exception as err:  # noqa: BLE001 - voluptuous.Invalid o. ä.
            return str(err)
    return None


async def _import_file(hass, rel_path: str) -> tuple[dict | None, str | None, str]:
    """(Jagd-Dict, Fehlerschlüssel, Fehlertext) beim Import einer YAML-Datei."""
    try:
        return await async_import_yaml(hass, rel_path), None, ""
    except FileNotFoundError:
        return None, "file_not_found", ""
    except HuntError as err:
        return None, "invalid_hunt", str(err)


# =========================================================================== #
# Config-Flow
# =========================================================================== #
class SchnitzeljagdConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["new", "example", "yaml"])

    async def async_step_new(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            hunt = editor.new_hunt(user_input["name"].strip(), user_input.get("subtitle", ""))
            return self.async_create_entry(title=hunt["name"], data={}, options={CONF_HUNT: hunt})
        schema = vol.Schema({vol.Required("name"): str, vol.Optional("subtitle"): str})
        return self.async_show_form(step_id="new", data_schema=schema)

    async def async_step_example(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            hunt = await async_import_example(self.hass)
            return self.async_create_entry(title=hunt["name"], data={}, options={CONF_HUNT: hunt})
        return self.async_show_form(step_id="example", data_schema=vol.Schema({}))

    async def async_step_yaml(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            hunt, error, detail = await _import_file(self.hass, user_input[CONF_FILE].strip().lstrip("/"))
            if hunt is not None:
                return self.async_create_entry(title=hunt["name"], data={}, options={CONF_HUNT: hunt})
            errors["base"] = error or "invalid_hunt"
            placeholders["error"] = detail
        schema = vol.Schema({vol.Required(CONF_FILE, default=DEFAULT_FILE): str})
        return self.async_show_form(
            step_id="yaml",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return SchnitzeljagdOptionsFlow()


# =========================================================================== #
# Options-Flow: Editor
# =========================================================================== #
class SchnitzeljagdOptionsFlow(OptionsFlow):
    """Menügeführter Editor. Änderungen gelten erst nach „Speichern und beenden“."""

    def __init__(self) -> None:
        self._hunt: dict[str, Any] | None = None
        self._sel: str | None = None  # gerade bearbeitete Station/Aufgabe/Clip

    # ---------------------------------------------------------------- Menü
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._hunt is None:
            stored = self.config_entry.options.get(CONF_HUNT)
            if stored is None:  # Eintrag aus Version 0.1/0.2: YAML einmalig übernehmen
                stored, error, detail = await _import_file(self.hass, self.config_entry.data[CONF_FILE])
                if stored is None:
                    return self.async_abort(reason=error or "invalid_hunt")
            self._hunt = copy.deepcopy(stored)
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "stations", "tasks", "clips", "global_actions", "treasure", "import_yaml", "finish"],
            description_placeholders={"overview": self._overview()},
        )

    def _overview(self) -> str:
        h = self._hunt
        done = len(h.get("tasks", []))
        return f"{h['name']}: {len(h['stations'])} Stationen, {done} Aufgaben"

    def _suggest(self, schema: vol.Schema, user_input: dict[str, Any] | None, current: dict[str, Any] | None):
        return self.add_suggested_values_to_schema(schema, user_input if user_input is not None else current)

    # ------------------------------------------------------------ Allgemein
    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            editor.set_general(self._hunt, user_input)
            return await self.async_step_init()
        schema = vol.Schema(
            {
                vol.Required("name"): TEXT,
                vol.Optional("subtitle"): TEXT,
                vol.Optional("icon"): IconSelector(),
            }
        )
        return self.async_show_form(step_id="general", data_schema=self._suggest(schema, None, self._hunt))

    # -------------------------------------------------- Globale Aktionen
    async def async_step_global_actions(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(*user_input.values())
            if err is None:
                editor.set_global_actions(self._hunt, user_input)
                return await self.async_step_init()
            errors["base"], placeholders["error"] = "invalid_actions", err
        schema = vol.Schema(
            {
                vol.Optional("on_prepare"): ActionSelector(),
                vol.Optional("on_stop"): ActionSelector(),
                vol.Optional("on_reset"): ActionSelector(),
            }
        )
        return self.async_show_form(
            step_id="global_actions",
            data_schema=self._suggest(schema, user_input, self._hunt),
            errors=errors,
            description_placeholders=placeholders,
        )

    # ---------------------------------------------------------------- Schatz
    async def async_step_treasure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("release"))
            if err is None:
                editor.set_treasure(self._hunt, user_input)
                return await self.async_step_init()
            errors["base"], placeholders["error"] = "invalid_actions", err
        fields: dict[Any, Any] = {}
        tasks = editor.task_options(self._hunt)
        if tasks:
            fields[vol.Optional("released_by")] = _select(tasks)
        fields[vol.Optional("release")] = ActionSelector()
        current = self._hunt.get("treasure", {})
        return self.async_show_form(
            step_id="treasure",
            data_schema=self._suggest(vol.Schema(fields), user_input, current),
            errors=errors,
            description_placeholders=placeholders,
        )

    # -------------------------------------------------------------- Stationen
    def _station_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("name"): TEXT,
                vol.Optional("icon"): IconSelector(),
                vol.Optional("description"): MULTILINE,
                vol.Optional("intro"): ActionSelector(),
            }
        )

    def _list_menu(self, step_id: str, has_items: bool, kind: str) -> ConfigFlowResult:
        options = [f"{kind}_add"]
        if has_items:
            options += [f"{kind}_edit", f"{kind}_delete"]
        options.append("init")
        return self.async_show_menu(
            step_id=step_id,
            menu_options=options,
            description_placeholders={"overview": self._overview()},
        )

    async def async_step_stations(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self._list_menu("stations", bool(self._hunt["stations"]), "station")

    async def async_step_station_add(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("intro"))
            if err is None:
                editor.upsert_station(self._hunt, None, user_input)
                return await self.async_step_stations()
            errors["base"], placeholders["error"] = "invalid_actions", err
        return self.async_show_form(
            step_id="station_add",
            data_schema=self._suggest(self._station_schema(), user_input, None),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_station_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._sel = user_input["station"]
            return await self.async_step_station_edit_form()
        schema = vol.Schema({vol.Required("station"): _select(editor.station_options(self._hunt))})
        return self.async_show_form(step_id="station_edit", data_schema=schema)

    async def async_step_station_edit_form(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("intro"))
            if err is None:
                editor.upsert_station(self._hunt, self._sel, user_input)
                return await self.async_step_stations()
            errors["base"], placeholders["error"] = "invalid_actions", err
        current = editor.find_station(self._hunt, self._sel)
        return self.async_show_form(
            step_id="station_edit_form",
            data_schema=self._suggest(self._station_schema(), user_input, current),
            errors=errors,
            description_placeholders={**placeholders, "station": current["name"]},
        )

    async def async_step_station_delete(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if len(self._hunt["stations"]) <= 1:
                errors["base"] = "last_station"
            else:
                editor.delete_station(self._hunt, user_input["station"])
                return await self.async_step_stations()
        schema = vol.Schema({vol.Required("station"): _select(editor.station_options(self._hunt))})
        return self.async_show_form(step_id="station_delete", data_schema=schema, errors=errors)

    # --------------------------------------------------------------- Aufgaben
    def _task_schema(self) -> vol.Schema:
        fields: dict[Any, Any] = {vol.Required("name"): TEXT}
        stations = editor.station_options(self._hunt)
        fields[vol.Optional("station")] = _select(stations)
        fields[vol.Optional("icon")] = IconSelector()
        fields[vol.Optional("description")] = MULTILINE
        fields[vol.Optional("next_station")] = _select(stations)
        fields[vol.Optional("on_complete")] = ActionSelector()
        return vol.Schema(fields)

    async def async_step_tasks(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self._list_menu("tasks", bool(self._hunt.get("tasks")), "task")

    async def async_step_task_add(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("on_complete"))
            if err is None:
                editor.upsert_task(self._hunt, None, user_input)
                return await self.async_step_tasks()
            errors["base"], placeholders["error"] = "invalid_actions", err
        return self.async_show_form(
            step_id="task_add",
            data_schema=self._suggest(self._task_schema(), user_input, None),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_task_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._sel = user_input["task"]
            return await self.async_step_task_edit_form()
        schema = vol.Schema({vol.Required("task"): _select(editor.task_options(self._hunt))})
        return self.async_show_form(step_id="task_edit", data_schema=schema)

    async def async_step_task_edit_form(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("on_complete"))
            if err is None:
                editor.upsert_task(self._hunt, self._sel, user_input)
                return await self.async_step_tasks()
            errors["base"], placeholders["error"] = "invalid_actions", err
        current = editor.find_task(self._hunt, self._sel)
        return self.async_show_form(
            step_id="task_edit_form",
            data_schema=self._suggest(self._task_schema(), user_input, current),
            errors=errors,
            description_placeholders={**placeholders, "task": current["name"]},
        )

    async def async_step_task_delete(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            editor.delete_task(self._hunt, user_input["task"])
            return await self.async_step_tasks()
        schema = vol.Schema({vol.Required("task"): _select(editor.task_options(self._hunt))})
        return self.async_show_form(step_id="task_delete", data_schema=schema)

    # ------------------------------------------------------------------ Clips
    def _clip_schema(self, with_station: bool) -> vol.Schema:
        fields: dict[Any, Any] = {}
        if with_station:
            fields[vol.Required("station")] = _select(editor.station_options(self._hunt))
        fields[vol.Required("name")] = TEXT
        fields[vol.Optional("icon")] = IconSelector()
        fields[vol.Optional("description")] = MULTILINE
        fields[vol.Optional("actions")] = ActionSelector()
        return vol.Schema(fields)

    async def async_step_clips(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self._list_menu("clips", bool(editor.clip_options(self._hunt)), "clip")

    async def async_step_clip_add(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("actions"))
            if err is None:
                editor.upsert_clip(self._hunt, user_input["station"], None, user_input)
                return await self.async_step_clips()
            errors["base"], placeholders["error"] = "invalid_actions", err
        return self.async_show_form(
            step_id="clip_add",
            data_schema=self._suggest(self._clip_schema(True), user_input, None),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_clip_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._sel = user_input["clip"]
            return await self.async_step_clip_edit_form()
        schema = vol.Schema({vol.Required("clip"): _select(editor.clip_options(self._hunt))})
        return self.async_show_form(step_id="clip_edit", data_schema=schema)

    async def async_step_clip_edit_form(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        station_id, clip_id = self._sel.split("|", 1)
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            err = _check_actions(user_input.get("actions"))
            if err is None:
                editor.upsert_clip(self._hunt, station_id, clip_id, user_input)
                return await self.async_step_clips()
            errors["base"], placeholders["error"] = "invalid_actions", err
        current = editor.find_clip(self._hunt, station_id, clip_id)
        return self.async_show_form(
            step_id="clip_edit_form",
            data_schema=self._suggest(self._clip_schema(False), user_input, current),
            errors=errors,
            description_placeholders={**placeholders, "clip": current["name"]},
        )

    async def async_step_clip_delete(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            station_id, clip_id = user_input["clip"].split("|", 1)
            editor.delete_clip(self._hunt, station_id, clip_id)
            return await self.async_step_clips()
        schema = vol.Schema({vol.Required("clip"): _select(editor.clip_options(self._hunt))})
        return self.async_show_form(step_id="clip_delete", data_schema=schema)

    # ---------------------------------------------------------- YAML-Import
    async def async_step_import_yaml(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            hunt, error, detail = await _import_file(self.hass, user_input[CONF_FILE].strip().lstrip("/"))
            if hunt is not None:
                self._hunt = hunt
                return await self.async_step_init()
            errors["base"] = error or "invalid_hunt"
            placeholders["error"] = detail
        schema = vol.Schema({vol.Required(CONF_FILE, default=DEFAULT_FILE): str})
        return self.async_show_form(
            step_id="import_yaml",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )

    # --------------------------------------------------------------- Speichern
    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        try:
            parse_hunt(self._hunt, validate_actions=cv.SCRIPT_SCHEMA)
        except HuntError as err:
            return self.async_show_form(
                step_id="finish_error",
                data_schema=vol.Schema({}),
                description_placeholders={"error": str(err)},
            )
        self.hass.config_entries.async_update_entry(self.config_entry, title=self._hunt["name"])
        return self.async_create_entry(data={CONF_HUNT: self._hunt})

    async def async_step_finish_error(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_init()
