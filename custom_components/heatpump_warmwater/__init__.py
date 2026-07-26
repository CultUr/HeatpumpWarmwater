"""Heatpump Warmwater PV Boost — integration entry point."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WarmwasserBoostCoordinator

PLATFORMS = ["switch", "binary_sensor", "sensor", "number", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = WarmwasserBoostCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward setups first so entities can register and restore state
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Then start listeners (coordinator reads restored entity state)
    await coordinator.async_setup()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Unload platforms first (entities call async_will_remove_from_hass),
    # then tear down the coordinator.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok
