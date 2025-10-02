from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME
from .const import (
    DOMAIN,
    CONF_API_KEY, CONF_API_SECRET, CONF_PROJECT_ID, CONF_DEVICE_ID,
    CONF_AMMETER_ID, CONF_BASE_URL,
    DEFAULT_BASE_URL,
)


class WhesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            # Basisvalidatie
            for field in (
                    CONF_API_KEY,
                    CONF_API_SECRET,
                    CONF_PROJECT_ID,
                    CONF_DEVICE_ID,
                    CONF_AMMETER_ID,
            ):
                if not str(user_input.get(field, "")).strip():
                    errors[field] = "required"

            base_url = (user_input.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
            if not base_url.startswith("http"):
                errors[CONF_BASE_URL] = "invalid_url"

            if not errors:
                # Uniek per combo project/device/ammeter
                unique = (
                    f"{user_input.get(CONF_PROJECT_ID)}:"
                    f"{user_input.get(CONF_DEVICE_ID)}:"
                    f"{user_input.get(CONF_AMMETER_ID)}"
                )
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_API_KEY: user_input[CONF_API_KEY].strip(),
                    CONF_API_SECRET: user_input[CONF_API_SECRET].strip(),
                    CONF_PROJECT_ID: user_input[CONF_PROJECT_ID].strip(),
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID].strip(),
                    CONF_AMMETER_ID: user_input[CONF_AMMETER_ID].strip(),
                    CONF_BASE_URL: base_url,
                }
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or "WHES Battery", data=data
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default="WHES Battery"): str,
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Required(CONF_PROJECT_ID): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_AMMETER_ID): str,
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
