from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import *
from .coordinator import validate_credentials

class WhesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            ok, err = await validate_credentials(self.hass, user_input)
            if ok:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME_PREFIX, DEFAULT_NAME_PREFIX),
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_API_SECRET: user_input[CONF_API_SECRET],
                        CONF_PROJECT_ID: user_input[CONF_PROJECT_ID],
                        CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                        CONF_AMMETER_ID: user_input[CONF_AMMETER_ID],
                        CONF_BASE_URL: user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                        CONF_SAMPLE_BY: user_input.get(CONF_SAMPLE_BY, DEFAULT_SAMPLE_BY),
                        CONF_NAME_PREFIX: user_input.get(CONF_NAME_PREFIX, DEFAULT_NAME_PREFIX),
                        CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    },
                )
            errors["base"] = err or "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_API_SECRET): str,
            vol.Required(CONF_PROJECT_ID): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_AMMETER_ID): str,
            vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
            vol.Optional(CONF_SAMPLE_BY, default=DEFAULT_SAMPLE_BY): str,
            vol.Optional(CONF_NAME_PREFIX, default=DEFAULT_NAME_PREFIX): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, user_input=None) -> FlowResult:
        # Simple reauth: ask for key/secret again
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return WhesOptionsFlow(config_entry)

class WhesOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            data = {**self.entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.entry, data=data)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Optional(CONF_SAMPLE_BY, default=self.entry.data.get(CONF_SAMPLE_BY, DEFAULT_SAMPLE_BY)): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=self.entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            vol.Optional(CONF_NAME_PREFIX, default=self.entry.data.get(CONF_NAME_PREFIX, DEFAULT_NAME_PREFIX)): str,
            vol.Optional(CONF_BASE_URL, default=self.entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
            # (bewust geen IDs/keys hier; dat doe je liever via Reconfigure)
        })
        return self.async_show_form(step_id="init", data_schema=schema)
