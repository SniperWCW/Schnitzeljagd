"""Config- und Options-Flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import CONF_FILE, CONF_INSTALL_EXAMPLE, DEFAULT_FILE, DOMAIN
from .loader import async_install_example, async_load_hunt
from .model import Hunt, HuntError


async def _validate(hass, rel_path: str, install_example: bool) -> tuple[Hunt | None, str | None, str]:
    """Gibt (Hunt, Fehlerschlüssel, Fehlertext) zurück."""
    try:
        if install_example:
            await async_install_example(hass, rel_path)
        return await async_load_hunt(hass, rel_path), None, ""
    except FileNotFoundError:
        return None, "file_not_found", ""
    except HuntError as err:
        return None, "invalid_hunt", str(err)


class SchnitzeljagdConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            rel_path = user_input[CONF_FILE].strip().lstrip("/")
            hunt, error, detail = await _validate(
                self.hass, rel_path, user_input[CONF_INSTALL_EXAMPLE]
            )
            if hunt is not None:
                await self.async_set_unique_id(rel_path)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=hunt.name, data={CONF_FILE: rel_path})
            errors["base"] = error or "invalid_hunt"
            placeholders["error"] = detail

        schema = vol.Schema(
            {
                vol.Required(CONF_FILE, default=DEFAULT_FILE): str,
                vol.Required(CONF_INSTALL_EXAMPLE, default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return SchnitzeljagdOptionsFlow()


class SchnitzeljagdOptionsFlow(OptionsFlow):
    """Pfad der Jagd-Datei ändern (Neuladen nach YAML-Änderung: Service reload_hunt)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            rel_path = user_input[CONF_FILE].strip().lstrip("/")
            hunt, error, detail = await _validate(self.hass, rel_path, False)
            if hunt is not None:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={CONF_FILE: rel_path}, title=hunt.name
                )
                return self.async_create_entry(data={})
            errors["base"] = error or "invalid_hunt"
            placeholders["error"] = detail

        schema = vol.Schema(
            {vol.Required(CONF_FILE, default=self.config_entry.data[CONF_FILE]): str}
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )
