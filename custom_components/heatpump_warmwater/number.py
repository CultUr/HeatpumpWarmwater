"""Number entities: configurable thresholds (replace input_number helpers)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_FRUHESTER_START_H,
    DEFAULT_MIN_PV_FORECAST,
    DEFAULT_MIN_SOC,
    DEFAULT_RESET_TEMP,
    DEFAULT_START_SCHWELLE,
    DEFAULT_ZIEL_TEMP,
    DOMAIN,
    KEY_FRUHESTER,
    KEY_MIN_PV,
    KEY_MIN_SOC,
    KEY_RESET_TEMP,
    KEY_SCHWELLE,
    KEY_ZIEL_TEMP,
)
from .coordinator import WarmwasserBoostCoordinator


@dataclass(frozen=True, kw_only=True)
class WwNumberDescription(NumberEntityDescription):
    default: float = 0.0
    coord_attr: str = ""


_NUMBERS: list[WwNumberDescription] = [
    WwNumberDescription(
        key=KEY_ZIEL_TEMP,
        name="Ziel-Temperatur",
        icon="mdi:thermometer-high",
        native_min_value=45.0,
        native_max_value=65.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        default=DEFAULT_ZIEL_TEMP,
        coord_attr="ziel_temp",
    ),
    WwNumberDescription(
        key=KEY_RESET_TEMP,
        name="Reset-Temperatur",
        icon="mdi:thermometer-low",
        native_min_value=40.0,
        native_max_value=55.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        default=DEFAULT_RESET_TEMP,
        coord_attr="reset_temp",
        entity_category=EntityCategory.CONFIG,
    ),
    WwNumberDescription(
        key=KEY_SCHWELLE,
        name="Start-Schwelle WW",
        icon="mdi:thermometer-chevron-down",
        native_min_value=40.0,
        native_max_value=60.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        default=DEFAULT_START_SCHWELLE,
        coord_attr="start_schwelle",
        entity_category=EntityCategory.CONFIG,
    ),
    WwNumberDescription(
        key=KEY_MIN_PV,
        name="Min PV-Forecast",
        icon="mdi:solar-power",
        native_min_value=500.0,
        native_max_value=5000.0,
        native_step=100.0,
        native_unit_of_measurement="W",
        mode=NumberMode.BOX,
        default=DEFAULT_MIN_PV_FORECAST,
        coord_attr="min_pv_forecast",
        entity_category=EntityCategory.CONFIG,
    ),
    WwNumberDescription(
        key=KEY_MIN_SOC,
        name="Min Akku-SoC",
        icon="mdi:battery-charging",
        native_min_value=30.0,
        native_max_value=95.0,
        native_step=1.0,
        native_unit_of_measurement="%",
        mode=NumberMode.BOX,
        default=DEFAULT_MIN_SOC,
        coord_attr="min_soc",
        entity_category=EntityCategory.CONFIG,
    ),
    WwNumberDescription(
        key=KEY_FRUHESTER,
        name="Fruehester Start (Stunde)",
        icon="mdi:clock-time-eleven",
        native_min_value=0.0,
        native_max_value=23.0,
        native_step=1.0,
        native_unit_of_measurement="h",
        mode=NumberMode.BOX,
        default=float(DEFAULT_FRUHESTER_START_H),
        coord_attr="fruhester_start_h",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WarmwasserBoostCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WwNumber(coordinator, desc) for desc in _NUMBERS])


class WwNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WarmwasserBoostCoordinator,
        description: WwNumberDescription,
    ) -> None:
        self._coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._value: float = description.default

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unavailable", "unknown", "None"):
            try:
                self._value = float(last.state)
            except (ValueError, TypeError):
                pass
        desc: WwNumberDescription = self.entity_description  # type: ignore[assignment]
        val = int(self._value) if desc.coord_attr == "fruhester_start_h" else self._value
        setattr(self._coordinator, desc.coord_attr, val)
        self._coordinator.register_entity(desc.key, self)

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        desc: WwNumberDescription = self.entity_description  # type: ignore[assignment]
        val = int(value) if desc.coord_attr == "fruhester_start_h" else value
        setattr(self._coordinator, desc.coord_attr, val)
        self.async_write_ha_state()
