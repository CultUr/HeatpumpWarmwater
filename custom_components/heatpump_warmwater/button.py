"""Button entities: manual boost start and stop."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import WarmwasserBoostCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ManuellerStartButton(coordinator), ManuellesEndeButton(coordinator)]
    )


class _BaseButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WarmwasserBoostCoordinator, uid_suffix: str) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{uid_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry.entry_id)},
            name="WW PV Boost",
        )


class ManuellerStartButton(_BaseButton):
    _attr_name = "Manuell starten"
    _attr_icon = "mdi:play-circle"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, "btn_start")

    async def async_press(self) -> None:
        await self._coordinator.async_manual_start()


class ManuellesEndeButton(_BaseButton):
    _attr_name = "Manuell beenden"
    _attr_icon = "mdi:stop-circle"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, "btn_end")

    async def async_press(self) -> None:
        await self._coordinator.async_manual_end()
