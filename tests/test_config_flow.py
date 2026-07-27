"""Tests for the config flow and options flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heatpump_warmwater.const import DOMAIN
from tests.conftest import MOCK_CONFIG

_SETUP_PATCH = "custom_components.heatpump_warmwater.async_setup_entry"


def _register_states(hass):
    hass.states.async_set("sensor.ww_temp", "45.0")
    hass.states.async_set("sensor.pv_this", "2000")
    hass.states.async_set("sensor.pv_next", "2000")
    hass.states.async_set("sensor.pv_power", "2500")
    hass.states.async_set("sensor.soc", "80")
    hass.states.async_set("number.wp_normal", "45")
    hass.states.async_set("number.wp_absenk", "35")


async def test_step_user_success(hass):
    """Valid config creates an entry with title 'WW PV Boost'."""
    _register_states(hass)

    with patch(_SETUP_PATCH, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "WW PV Boost"
    assert result["data"] == MOCK_CONFIG


async def test_step_user_entity_not_found(hass):
    """Unknown entity ID produces entity_not_found error on that field."""
    _register_states(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    bad_config = dict(MOCK_CONFIG, entity_ww_temp="sensor.does_not_exist")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=bad_config
    )

    assert result["type"] == "form"
    assert result["errors"].get("entity_ww_temp") == "entity_not_found"


async def test_step_user_single_instance(hass):
    """A second setup attempt is aborted when an entry already exists."""
    _register_states(hass)
    existing = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_success(hass):
    """Options flow accepts updated entity IDs and creates a new options entry."""
    _register_states(hass)

    with patch(_SETUP_PATCH, return_value=True):
        setup_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            setup_result["flow_id"], user_input=MOCK_CONFIG
        )

    # Grab the created entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(_SETUP_PATCH, return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"

        updated = dict(MOCK_CONFIG, entity_pv_power="sensor.pv_power")
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=updated
        )

    assert result["type"] == "create_entry"
