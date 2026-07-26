"""Sensor entities: Status, kWh heute, Letzter Start."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEY_KWH, KEY_LETZTER_START, KEY_STATUS
from .coordinator import WarmwasserBoostCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            StatusSensor(coordinator),
            KwhHeuteSensor(coordinator),
            LetzterStartSensor(coordinator),
        ]
    )


class StatusSensor(SensorEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{KEY_STATUS}"

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unavailable", "unknown"):
            self._coordinator.status = last.state
        self._coordinator.register_entity(KEY_STATUS, self)

    @property
    def native_value(self) -> str:
        return self._coordinator.status


class KwhHeuteSensor(SensorEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "kWh heute"
    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{KEY_KWH}"

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unavailable", "unknown", "None"):
            try:
                self._coordinator.kwh_heute = float(last.state)
            except (ValueError, TypeError):
                pass
        self._coordinator.register_entity(KEY_KWH, self)

    @property
    def native_value(self) -> float:
        return round(self._coordinator.kwh_heute, 3)


class LetzterStartSensor(SensorEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Letzter Start"
    _attr_icon = "mdi:clock-start"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: WarmwasserBoostCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{KEY_LETZTER_START}"

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unavailable", "unknown", "None"):
            try:
                self._coordinator.last_start = datetime.fromisoformat(last.state)
            except (ValueError, TypeError):
                pass
        self._coordinator.register_entity(KEY_LETZTER_START, self)

    @property
    def native_value(self) -> datetime | None:
        return self._coordinator.last_start
