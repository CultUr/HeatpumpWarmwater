"""Shared fixtures and helpers for heatpump_warmwater tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heatpump_warmwater.const import DOMAIN
from custom_components.heatpump_warmwater.coordinator import WarmwasserBoostCoordinator

pytest_plugins = "pytest_homeassistant_custom_component"

MOCK_CONFIG = {
    "entity_ww_temp": "sensor.ww_temp",
    "entity_pv_forecast_this_hour": "sensor.pv_this",
    "entity_pv_forecast_next_hour": "sensor.pv_next",
    "entity_pv_power": "sensor.pv_power",
    "entity_soc": "sensor.soc",
    "entity_wp_normal": "number.wp_normal",
    "entity_wp_absenk": "number.wp_absenk",
}


def make_state(value, attrs=None):
    """Return a mock HA state object."""
    state = MagicMock()
    state.state = str(value)
    state.attributes = attrs or {}
    return state


def make_coord(extra_states=None):
    """Build a WarmwasserBoostCoordinator with a mocked hass."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = dict(MOCK_CONFIG)
    entry.options = {}

    states_map = extra_states or {}
    hass.states.get = lambda eid: states_map.get(eid)

    coord = WarmwasserBoostCoordinator(hass, entry)
    return coord, states_map


@pytest.fixture
def mock_config_entry():
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
