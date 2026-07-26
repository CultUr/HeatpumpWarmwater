"""Config Flow + Options Flow: select external entity IDs for WW Boost."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_ENTITY_PV_FORECAST_NEXT,
    CONF_ENTITY_PV_FORECAST_THIS,
    CONF_ENTITY_PV_POWER,
    CONF_ENTITY_SOC,
    CONF_ENTITY_WP_ABSENK,
    CONF_ENTITY_WP_NORMAL,
    CONF_ENTITY_WW_ENERGY,
    CONF_ENTITY_WW_TEMP,
    DOMAIN,
)


def _schema(defaults: dict[str, str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_ENTITY_WW_TEMP,
                default=defaults.get(CONF_ENTITY_WW_TEMP, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ENTITY_PV_FORECAST_THIS,
                default=defaults.get(CONF_ENTITY_PV_FORECAST_THIS, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ENTITY_PV_FORECAST_NEXT,
                default=defaults.get(CONF_ENTITY_PV_FORECAST_NEXT, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ENTITY_PV_POWER,
                default=defaults.get(CONF_ENTITY_PV_POWER, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ENTITY_SOC,
                default=defaults.get(CONF_ENTITY_SOC, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_ENTITY_WW_ENERGY,
                default=defaults.get(CONF_ENTITY_WW_ENERGY, ""),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_ENTITY_WP_NORMAL,
                default=defaults.get(CONF_ENTITY_WP_NORMAL, ""),
            ): EntitySelector(EntitySelectorConfig(domain="number")),
            vol.Required(
                CONF_ENTITY_WP_ABSENK,
                default=defaults.get(CONF_ENTITY_WP_ABSENK, ""),
            ): EntitySelector(EntitySelectorConfig(domain="number")),
        }
    )


def _validate_entities(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key, eid in data.items():
        if not eid:  # optional field left empty
            continue
        if not hass.states.get(eid):
            errors[key] = "entity_not_found"
    return errors


class HeatpumpWarmwaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Heatpump Warmwater PV Boost."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeatpumpWarmwaterOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            errors = _validate_entities(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="WW PV Boost", data=user_input)
            return self.async_show_form(
                step_id="user", data_schema=_schema(user_input), errors=errors
            )

        return self.async_show_form(step_id="user", data_schema=_schema({}))


class HeatpumpWarmwaterOptionsFlow(OptionsFlow):
    """Options flow: update entity IDs after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            errors = _validate_entities(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
            return self.async_show_form(
                step_id="init",
                data_schema=_schema({**current, **user_input}),
                errors=errors,
            )

        return self.async_show_form(step_id="init", data_schema=_schema(current))
