"""Binary sensor entities: Aktiv and Heute-Gelaufen (read-only runtime state)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEY_AKTIV, KEY_HEUTE_GELAUFEN
from .coordinator import WarmwasserBoostCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [AktivSensor(coordinator), HeuteGelaufenSensor(coordinator)]
    )


class _BaseBinarySensor(BinarySensorEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WarmwasserBoostCoordinator, key: str) -> None:
        self._coordinator = coordinator
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None:
            self._restore(last.state == "on")
        self._coordinator.register_entity(self._key, self)

    def _restore(self, value: bool) -> None:
        raise NotImplementedError

    @property
    def is_on(self) -> bool:
        raise NotImplementedError


class AktivSensor(_BaseBinarySensor):
    _attr_name = "Boost aktiv"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, KEY_AKTIV)

    def _restore(self, value: bool) -> None:
        self._coordinator.boost_active = value

    @property
    def is_on(self) -> bool:
        return self._coordinator.boost_active


class HeuteGelaufenSensor(_BaseBinarySensor):
    _attr_name = "Heute gelaufen"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        super().__init__(coordinator, KEY_HEUTE_GELAUFEN)

    def _restore(self, value: bool) -> None:
        self._coordinator.heute_gelaufen = value

    @property
    def is_on(self) -> bool:
        return self._coordinator.heute_gelaufen
