"""Switch entities: Automatik and Urlaub (replace input_boolean helpers)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEY_AUTOMATIK, KEY_URLAUB
from .coordinator import WarmwasserBoostCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AutomatikSwitch(coordinator), UrlaubSwitch(coordinator)])


class _BaseSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WarmwasserBoostCoordinator, key: str) -> None:
        self._coordinator = coordinator
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.entry.entry_id)},
            name="WW PV Boost",
        )

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None:
            self._apply_state(last.state == "on")
        self._coordinator.register_entity(self._key, self)

    def _apply_state(self, value: bool) -> None:
        raise NotImplementedError

    @property
    def is_on(self) -> bool:
        raise NotImplementedError

    async def async_turn_on(self, **kwargs) -> None:  # noqa: ANN003
        self._apply_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:  # noqa: ANN003
        self._apply_state(False)
        self.async_write_ha_state()


class AutomatikSwitch(_BaseSwitch):
    _attr_name = "Automatik"
    _attr_icon = "mdi:auto-mode"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, KEY_AUTOMATIK)

    def _apply_state(self, value: bool) -> None:
        self._coordinator.automatik = value

    @property
    def is_on(self) -> bool:
        return self._coordinator.automatik


class UrlaubSwitch(_BaseSwitch):
    _attr_name = "Urlaub"
    _attr_icon = "mdi:airplane"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, KEY_URLAUB)

    def _apply_state(self, value: bool) -> None:
        self._coordinator.urlaub = value

    @property
    def is_on(self) -> bool:
        return self._coordinator.urlaub
