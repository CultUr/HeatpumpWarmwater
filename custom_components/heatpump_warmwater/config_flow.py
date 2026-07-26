"""Config Flow: select external entity IDs for WW Boost integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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

# Defaults pre-filled with the Weishaupt/EMMA/Solcast entity IDs from Dasing
_DEFAULTS: dict[str, str] = {
    CONF_ENTITY_WW_TEMP: "sensor.wh_warmwasser_warmwassertemperatur",
    CONF_ENTITY_PV_FORECAST_THIS: "sensor.solcast_pv_forecast_dach_forecast_this_hour",
    CONF_ENTITY_PV_FORECAST_NEXT: "sensor.solcast_pv_forecast_dach_forecast_next_hour",
    CONF_ENTITY_PV_POWER: "sensor.emma_pv_output_power",
    CONF_ENTITY_SOC: "sensor.emma_state_of_capacity",
    CONF_ENTITY_WW_ENERGY: "sensor.wh_statistik_warmwasser_energie_heute",
    CONF_ENTITY_WP_NORMAL: "number.wh_warmwasser_warmwasser_normal",
    CONF_ENTITY_WP_ABSENK: "number.wh_warmwasser_warmwasser_absenk",
}


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
            vol.Required(
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


class HeatpumpWarmwaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Heatpump Warmwater PV Boost."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="WW PV Boost", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(_DEFAULTS))
