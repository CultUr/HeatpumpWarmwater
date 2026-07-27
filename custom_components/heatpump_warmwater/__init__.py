"""Heatpump Warmwater PV Boost — integration entry point."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WarmwasserBoostCoordinator
from .dashboard import async_setup_dashboard

PLATFORMS = ["switch", "binary_sensor", "sensor", "number", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = WarmwasserBoostCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward setups first so entities can register and restore state
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Then start listeners (coordinator reads restored entity state)
    await coordinator.async_setup()

    # Dashboard setup: entity platform tasks are created (not awaited) inside
    # async_forward_entry_setups, so entity registry writes are not yet complete
    # when we return. Defer to ensure all entities are registered first.
    async def _setup_dashboard(event=None) -> None:
        await async_setup_dashboard(hass, entry)

    if hass.is_running:
        hass.async_create_task(_setup_dashboard())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _setup_dashboard)
        )

    # Reload on options change (entity IDs updated via options flow)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Unload platforms first (entities call async_will_remove_from_hass),
    # then tear down the coordinator.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok
