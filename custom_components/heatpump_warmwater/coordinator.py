"""Core coordinator: all boost logic, Modbus-wait sequences, end conditions."""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    BOOST_END_PV_DURATION_S,
    BOOST_END_PV_THRESHOLD_W,
    BOOST_END_SOC_DURATION_S,
    BOOST_END_SOC_THRESHOLD_PCT,
    BOOST_END_TEMP_HOLD_S,
    BOOST_MAX_DURATION_S,
    CONF_ENTITY_GRID_POWER,
    CONF_ENTITY_PV_FORECAST_NEXT,
    CONF_ENTITY_PV_FORECAST_THIS,
    CONF_ENTITY_PV_POWER,
    CONF_ENTITY_SOC,
    CONF_ENTITY_SOLCAST_TODAY_KWH,
    CONF_ENTITY_SOLCAST_TOMORROW_KWH,
    CONF_ENTITY_WP_ABSENK,
    CONF_ENTITY_WP_NORMAL,
    CONF_ENTITY_WW_ENERGY,
    CONF_ENTITY_WW_TEMP,
    DEFAULT_FRUHESTER_START_H,
    DEFAULT_MIN_FORECAST_TODAY_KWH,
    DEFAULT_MIN_FORECAST_TOMORROW_KWH,
    DEFAULT_MIN_GRID_SURPLUS_W,
    DEFAULT_NORMAL1_END_H,
    DEFAULT_NORMAL1_START_H,
    DEFAULT_NORMAL2_END_H,
    DEFAULT_NORMAL2_START_H,
    DEFAULT_WW_MIN_COMFORT,
    DEFAULT_ABSENK_RESET,
    DEFAULT_MIN_PV_FORECAST,
    DEFAULT_MIN_SOC,
    DEFAULT_RESET_TEMP,
    DEFAULT_START_SCHWELLE,
    DEFAULT_ZIEL_TEMP,
    MODBUS_WAIT_TIMEOUT,
    REASON_MANUELL,
    REASON_PV,
    REASON_SOC,
    REASON_SONNE,
    REASON_STARTUP,
    REASON_STARTUP_BOOST,
    REASON_TIMEOUT,
    REASON_ZIEL,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_STOPPING,
)

_LOGGER = logging.getLogger(__name__)


class WarmwasserBoostCoordinator:
    """Manages the WW PV-Boost logic (replaces 5 automations + 2 scripts)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # External entity IDs — options override initial data
        _data = {**entry.data, **entry.options}
        self._eid_ww_temp: str = _data[CONF_ENTITY_WW_TEMP]
        self._eid_pv_this: str = _data[CONF_ENTITY_PV_FORECAST_THIS]
        self._eid_pv_next: str = _data[CONF_ENTITY_PV_FORECAST_NEXT]
        self._eid_pv_power: str = _data[CONF_ENTITY_PV_POWER]
        self._eid_soc: str = _data[CONF_ENTITY_SOC]
        self._eid_ww_energy: str = _data.get(CONF_ENTITY_WW_ENERGY, "")
        self._eid_wp_normal: str = _data[CONF_ENTITY_WP_NORMAL]
        self._eid_wp_absenk: str = _data[CONF_ENTITY_WP_ABSENK]
        # Optional: improved start logic
        self._eid_solcast_today: str = _data.get(CONF_ENTITY_SOLCAST_TODAY_KWH, "")
        self._eid_solcast_tomorrow: str = _data.get(CONF_ENTITY_SOLCAST_TOMORROW_KWH, "")
        self._eid_grid_power: str = _data.get(CONF_ENTITY_GRID_POWER, "")

        # Configurable thresholds (written by Number entities after restore)
        self.ziel_temp: float = DEFAULT_ZIEL_TEMP
        self.reset_temp: float = DEFAULT_RESET_TEMP
        self.min_pv_forecast: float = DEFAULT_MIN_PV_FORECAST
        self.min_soc: float = DEFAULT_MIN_SOC
        self.start_schwelle: float = DEFAULT_START_SCHWELLE
        self.fruhester_start_h: int = DEFAULT_FRUHESTER_START_H
        self.min_forecast_today_kwh: float = DEFAULT_MIN_FORECAST_TODAY_KWH
        self.min_forecast_tomorrow_kwh: float = DEFAULT_MIN_FORECAST_TOMORROW_KWH
        self.min_grid_surplus_w: float = DEFAULT_MIN_GRID_SURPLUS_W
        self.ww_min_comfort: float = DEFAULT_WW_MIN_COMFORT
        self.normal1_start_h: int = DEFAULT_NORMAL1_START_H
        self.normal1_end_h: int = DEFAULT_NORMAL1_END_H
        self.normal2_start_h: int = DEFAULT_NORMAL2_START_H
        self.normal2_end_h: int = DEFAULT_NORMAL2_END_H

        # Auto-learned WW cooling rate from recorder history (°C/h)
        self._cached_cooling_rate: float | None = None

        # Control flags (written by Switch entities after restore)
        self.automatik: bool = True
        self.urlaub: bool = False

        # Runtime state (read by Sensor/BinarySensor entities)
        self.boost_active: bool = False
        self.heute_gelaufen: bool = False
        self.kwh_heute: float = 0.0
        self.kwh_startwert: float = 0.0
        self.kwh_reset_time: datetime = dt_util.now().replace(hour=0, minute=5, second=0, microsecond=0)
        self.last_start: datetime | None = None
        self.status: str = STATUS_IDLE

        # Internal tasks and listeners
        self._start_lock = asyncio.Lock()
        self._active_tasks: set[asyncio.Task] = set()  # all coordinator-spawned tasks
        self._timeout_task: asyncio.Task | None = None
        self._pv_low_task: asyncio.Task | None = None
        self._soc_low_task: asyncio.Task | None = None
        self._temp_reached_task: asyncio.Task | None = None
        self._unsub: list[CALLBACK_TYPE] = []
        self._entities: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Entity registration
    # ------------------------------------------------------------------ #

    def register_entity(self, key: str, entity: Any) -> None:
        self._entities[key] = entity

    def _notify(self, *keys: str) -> None:
        for key in keys:
            if key in self._entities:
                self._entities[key].async_write_ha_state()

    def _notify_all(self) -> None:
        for entity in self._entities.values():
            entity.async_write_ha_state()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def async_setup(self) -> None:
        """Register state listeners. Must be called after entities are set up."""
        tracked = [
            self._eid_ww_temp,
            self._eid_pv_this,
            self._eid_pv_next,
            self._eid_pv_power,
            self._eid_soc,
            "sun.sun",
        ]
        if self._eid_grid_power:
            tracked.append(self._eid_grid_power)
        self._unsub.append(
            async_track_state_change_event(
                self.hass, tracked, self._handle_sensor_change
            )
        )

        # Daily reset at 00:05
        self._unsub.append(
            async_track_time_change(
                self.hass, self._handle_daily_reset, hour=0, minute=5, second=0
            )
        )

        # Recheck every 30 min (:00 and :30)
        for minute in (0, 30):
            self._unsub.append(
                async_track_time_change(
                    self.hass, self._handle_recheck, minute=minute, second=0
                )
            )

        self._create_tracked_task(self._async_startup_healing())

        # Refresh cooling rate daily at 01:00 and once after startup
        self._unsub.append(
            async_track_time_change(
                self.hass, self._handle_cooling_rate_refresh, hour=1, minute=0, second=0
            )
        )

    async def async_unload(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()
        for task in list(self._active_tasks):
            task.cancel()
        self._active_tasks.clear()
        self._timeout_task = None
        self._pv_low_task = None
        self._soc_low_task = None
        self._temp_reached_task = None

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #

    @callback
    def _handle_sensor_change(self, event: Any) -> None:
        eid: str = event.data.get("entity_id", "")
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unavailable", "unknown"):
            return
        if self.boost_active:
            self._create_tracked_task(self._check_end_conditions(eid))
        else:
            self._create_tracked_task(self._check_start_conditions("state_change"))

    @callback
    def _handle_recheck(self, now: datetime) -> None:
        if not self.boost_active:
            self._create_tracked_task(self._check_start_conditions("recheck"))

    @callback
    def _handle_daily_reset(self, now: datetime) -> None:
        _LOGGER.debug("Daily reset")
        if self.boost_active and self._eid_ww_energy:
            self.kwh_startwert = self._float(self._eid_ww_energy) or 0.0
        self.kwh_reset_time = now
        self.heute_gelaufen = False
        self.kwh_heute = 0.0
        self._notify("heute_gelaufen", "kwh_heute")

    @callback
    def _handle_cooling_rate_refresh(self, now: datetime) -> None:
        self._create_tracked_task(self._async_refresh_cooling_rate())

    # ------------------------------------------------------------------ #
    # Start conditions
    # ------------------------------------------------------------------ #

    async def _check_start_conditions(self, trigger: str) -> None:
        if self._start_lock.locked():
            return
        async with self._start_lock:
            if self._should_start_forecast():
                await self._async_boost_start(f"Auto-Forecast: {trigger}")
            elif self._should_start_grid_surplus():
                await self._async_boost_start(f"Auto-Ueberschuss: {trigger}")

    def _common_preconditions(self) -> bool:
        """Shared guard: flags, WW-temp below threshold."""
        if self.status != STATUS_IDLE:
            return False
        if not self.automatik or self.urlaub or self.boost_active or self.heute_gelaufen:
            return False
        ww_temp = self._float(self._eid_ww_temp)
        if ww_temp is None or ww_temp >= self.start_schwelle:
            return False
        return True

    def _should_start_forecast(self) -> bool:
        """Forecast-based start: good hourly PV forecast + sufficient SoC."""
        if not self._common_preconditions():
            return False
        if dt_util.now().hour < self.fruhester_start_h:
            return False

        sun = self.hass.states.get("sun.sun")
        if sun:
            if sun.state == "below_horizon":
                return False
            try:
                if float(sun.attributes.get("elevation", 0)) <= 15.0:
                    return False
            except (ValueError, TypeError):
                return False

        pv_this = self._float(self._eid_pv_this)
        pv_next = self._float(self._eid_pv_next)
        soc = self._float(self._eid_soc)

        if pv_this is None or pv_this <= self.min_pv_forecast:
            return False
        if pv_next is None or pv_next <= self.min_pv_forecast:
            return False
        if soc is None or soc <= self.min_soc:
            return False

        # Today's and tomorrow's total forecast (computed once)
        today_kwh: float | None = self._float(self._eid_solcast_today) if self._eid_solcast_today else None
        if today_kwh is not None and today_kwh < self.min_forecast_today_kwh:
            return False

        # Tomorrow much better than today → postpone boost to tomorrow
        if today_kwh is not None and self._eid_solcast_tomorrow:
            tomorrow_kwh = self._float(self._eid_solcast_tomorrow)
            if (tomorrow_kwh is not None
                    and today_kwh < self.min_forecast_tomorrow_kwh
                    and tomorrow_kwh > self.min_forecast_tomorrow_kwh):
                return False

        # WW temp decay: delay if WW stays comfortable until next WP Normal cycle
        # AND PV improves in the next period (worth waiting)
        if self._ww_ok_until_next_normal_cycle() and pv_next > pv_this * 1.2:
            _LOGGER.debug(
                "Boost aufgeschoben: WW OK bis naechstem WP-Zyklus, PV steigt (%.0f->%.0f W)",
                pv_this, pv_next,
            )
            return False

        return True

    def _should_start_grid_surplus(self) -> bool:
        """Reactive start: currently exporting more than threshold to grid."""
        if not self._eid_grid_power:
            return False
        if not self._common_preconditions():
            return False

        # Sun must be above horizon (surplus should come from PV, not battery)
        sun = self.hass.states.get("sun.sun")
        if not sun or sun.state == "below_horizon":
            return False

        grid = self._float(self._eid_grid_power)
        if grid is None or grid > -self.min_grid_surplus_w:
            return False  # negative = export; not enough surplus

        soc = self._float(self._eid_soc)
        if soc is None or soc < self.min_soc:
            return False

        return True

    # ------------------------------------------------------------------ #
    # Boost start sequence
    # ------------------------------------------------------------------ #

    async def _async_boost_start(self, reason: str) -> None:
        _LOGGER.info("WW Boost Start: %s", reason)
        self.status = STATUS_STARTING
        self._notify("status")

        target = self.ziel_temp

        # 1. Raise Normal setpoint
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self._eid_wp_normal, "value": target},
            blocking=True,
        )

        # 2. Wait for Absenk.max attribute to follow (Modbus propagation)
        ok = await self._wait_attr(
            self._eid_wp_absenk, "max",
            lambda v: v >= target - 1,
            MODBUS_WAIT_TIMEOUT,
        )

        if not ok:
            _LOGGER.warning(
                "Boost-Start abgebrochen: Absenk.max Timeout (max=%s, Ziel=%.1f)",
                self._attr(self._eid_wp_absenk, "max"), target,
            )
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": self._eid_wp_normal, "value": self.reset_temp},
                blocking=True,
            )
            self.status = STATUS_IDLE
            self._notify("status")
            return

        # 3. Set Absenk setpoint
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self._eid_wp_absenk, "value": target - 1},
            blocking=True,
        )

        # 4. Energy snapshot (optional — skipped if no energy sensor configured)
        self.kwh_startwert = (self._float(self._eid_ww_energy) or 0.0) if self._eid_ww_energy else 0.0

        # 5. Set flags and notify entities
        self.boost_active = True
        self.heute_gelaufen = True
        self.last_start = dt_util.now()
        self.status = STATUS_RUNNING
        self._notify_all()

        # 6. Start 2.5h watchdog
        self._cancel_task("_timeout_task")
        self._timeout_task = self._create_tracked_task(self._boost_timeout())

        _LOGGER.info(
            "WW Boost aktiv (%s) — PV: %s W, SoC: %s%%, WW: %s°C, kWh-Start: %.3f",
            reason,
            self._float(self._eid_pv_this), self._float(self._eid_soc),
            self._float(self._eid_ww_temp), self.kwh_startwert,
        )
        self.hass.async_create_task(
            self.hass.services.async_call(
                "logbook", "log",
                {
                    "name": "WW-Ueberladung",
                    "message": (
                        f"Start ({reason}) — "
                        f"PV-Forecast: {self._float(self._eid_pv_this)} W "
                        f"(next: {self._float(self._eid_pv_next)} W), "
                        f"SoC: {self._float(self._eid_soc)} %, "
                        f"WW-Temp: {self._float(self._eid_ww_temp)} °C, "
                        f"kWh-Start: {self.kwh_startwert:.3f}"
                    ),
                },
            )
        )

    async def _boost_timeout(self) -> None:
        await asyncio.sleep(BOOST_MAX_DURATION_S)
        if self.boost_active:
            await self._async_boost_end(REASON_TIMEOUT)

    # ------------------------------------------------------------------ #
    # End conditions
    # ------------------------------------------------------------------ #

    async def _check_end_conditions(self, entity_id: str) -> None:
        if not self.boost_active:
            return

        if entity_id == "sun.sun":
            sun = self.hass.states.get("sun.sun")
            if sun and sun.state == "below_horizon":
                self._cancel_duration_tasks()
                await self._async_boost_end(REASON_SONNE)
            return

        if entity_id == self._eid_ww_temp:
            ww = self._float(self._eid_ww_temp)
            if ww is not None and ww >= self.ziel_temp:
                if self._temp_reached_task is None or self._temp_reached_task.done():
                    self._temp_reached_task = self._create_tracked_task(
                        self._temp_hold_check()
                    )
            else:
                self._cancel_task("_temp_reached_task")
            return

        if entity_id == self._eid_pv_power:
            pv = self._float(self._eid_pv_power)
            if pv is not None and pv < BOOST_END_PV_THRESHOLD_W:
                if self._pv_low_task is None or self._pv_low_task.done():
                    self._pv_low_task = self._create_tracked_task(
                        self._pv_low_timer()
                    )
            else:
                self._cancel_task("_pv_low_task")
            return

        if entity_id == self._eid_soc:
            soc = self._float(self._eid_soc)
            if soc is not None and soc < BOOST_END_SOC_THRESHOLD_PCT:
                if self._soc_low_task is None or self._soc_low_task.done():
                    self._soc_low_task = self._create_tracked_task(
                        self._soc_low_timer()
                    )
            else:
                self._cancel_task("_soc_low_task")

    async def _temp_hold_check(self) -> None:
        await asyncio.sleep(BOOST_END_TEMP_HOLD_S)
        if self.boost_active:
            ww = self._float(self._eid_ww_temp)
            if ww is not None and ww >= self.ziel_temp:
                self._cancel_duration_tasks()
                await self._async_boost_end(REASON_ZIEL)

    async def _pv_low_timer(self) -> None:
        await asyncio.sleep(BOOST_END_PV_DURATION_S)
        if self.boost_active:
            pv = self._float(self._eid_pv_power)
            if pv is not None and pv < BOOST_END_PV_THRESHOLD_W:
                self._cancel_duration_tasks()
                await self._async_boost_end(REASON_PV)

    async def _soc_low_timer(self) -> None:
        await asyncio.sleep(BOOST_END_SOC_DURATION_S)
        if self.boost_active:
            soc = self._float(self._eid_soc)
            if soc is not None and soc < BOOST_END_SOC_THRESHOLD_PCT:
                self._cancel_duration_tasks()
                await self._async_boost_end(REASON_SOC)

    def _cancel_duration_tasks(self) -> None:
        for name in ("_pv_low_task", "_soc_low_task", "_temp_reached_task"):
            self._cancel_task(name)

    def _create_persistent_notification(self, title: str, message: str, notification_id: str) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification", "create",
                {"title": title, "message": message, "notification_id": notification_id},
            )
        )

    # ------------------------------------------------------------------ #
    # Boost end sequence
    # ------------------------------------------------------------------ #

    async def _async_boost_end(self, reason: str) -> None:
        if not self.boost_active:
            return
        self.boost_active = False  # prevent re-entry before any await

        self._cancel_task("_timeout_task")
        self.status = STATUS_STOPPING
        self._notify("status")

        # kWh calculation (skipped for startup healing or if no energy sensor)
        if reason in (REASON_STARTUP, REASON_STARTUP_BOOST) or not self._eid_ww_energy:
            boost_kwh = 0.0
        else:
            energy_now = self._float(self._eid_ww_energy) or 0.0
            boost_kwh = max(0.0, energy_now - self.kwh_startwert)

        try:
            # 1. Reset Absenk to standby value
            try:
                await self.hass.services.async_call(
                    "number", "set_value",
                    {"entity_id": self._eid_wp_absenk, "value": DEFAULT_ABSENK_RESET},
                    blocking=True,
                )
            except Exception as err:
                _LOGGER.error("Boost-Ende: Absenk-Reset fehlgeschlagen (%s)", err)
                self._create_persistent_notification(
                    "WW-Ueberladung: Absenk-Reset fehlgeschlagen",
                    f"Absenk konnte nach Boost-Ende nicht auf {DEFAULT_ABSENK_RESET:.0f} Grad zurueckgesetzt werden: {err}. "
                    f"Bitte manuell pruefen.",
                    "ww_boost_absenk_reset_fehler",
                )

            # 2. Wait for Normal.min to drop (Modbus propagation after Absenk reset)
            reset = self.reset_temp
            ok = await self._wait_attr(
                self._eid_wp_normal, "min",
                lambda v: v <= reset + 1,
                MODBUS_WAIT_TIMEOUT,
            )
            if ok:
                try:
                    await self.hass.services.async_call(
                        "number", "set_value",
                        {"entity_id": self._eid_wp_normal, "value": reset},
                        blocking=True,
                    )
                except Exception as err:
                    _LOGGER.error("Boost-Ende: Normal-Reset fehlgeschlagen (%s)", err)
                    self._create_persistent_notification(
                        "WW-Ueberladung: Waermepumpe pruefen",
                        f"Normal-Sollwert konnte nach Boost-Ende nicht auf {reset:.0f} Grad zurueckgesetzt werden: {err}. "
                        f"Bitte manuell pruefen.",
                        "ww_boost_normal_reset_fehler",
                    )
            else:
                normal_min = self._attr(self._eid_wp_normal, "min")
                _LOGGER.warning(
                    "Normal-Sollwert Timeout nach Boost-Ende "
                    "(Normal.min=%s, Reset-Temp=%.1f). Bitte manuell pruefen.",
                    normal_min, reset,
                )
                self._create_persistent_notification(
                    "WW-Ueberladung: Waermepumpe pruefen",
                    (
                        f"Normal-Sollwert konnte nach Boost-Ende nicht zurueckgesetzt werden. "
                        f"Bitte WP-Sollwert manuell auf {reset:.0f} Grad pruefen. "
                        f"(Normal.min war: {normal_min} Grad)"
                    ),
                    "ww_boost_normal_reset_fehler",
                )
        finally:
            # Always restore accounting and status, even on unexpected exception
            self.kwh_heute += boost_kwh
            self.status = STATUS_IDLE
            self._notify_all()

            _LOGGER.info(
                "WW Boost Ende (%s) — WW: %s°C, PV: %s W, SoC: %s%%, "
                "Boost: %.3f kWh, Tag: %.3f kWh",
                reason,
                self._float(self._eid_ww_temp), self._float(self._eid_pv_power),
                self._float(self._eid_soc), boost_kwh, self.kwh_heute,
            )
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "logbook", "log",
                    {
                        "name": "WW-Ueberladung",
                        "message": (
                            f"Ende ({reason}) — "
                            f"WW: {self._float(self._eid_ww_temp)} °C, "
                            f"PV: {self._float(self._eid_pv_power)} W, "
                            f"SoC: {self._float(self._eid_soc)} %, "
                            f"Boost-kWh: {boost_kwh:.3f} kWh, "
                            f"Tagesbilanz: {self.kwh_heute:.3f} kWh"
                        ),
                    },
                )
            )

    # ------------------------------------------------------------------ #
    # Startup healing
    # ------------------------------------------------------------------ #

    async def _async_startup_healing(self) -> None:
        await asyncio.sleep(120)
        _LOGGER.debug("Startup-Heilung: Konsistenzpruefung...")
        # Estimate cooling rate in background after startup
        self._create_tracked_task(self._async_refresh_cooling_rate())

        normal = self._float(self._eid_wp_normal)
        if normal is None:
            return

        # Case 1: Normal elevated but boost marked as inactive
        if not self.boost_active and normal > self.reset_temp:
            _LOGGER.warning(
                "Startup-Heilung Fall 1: Normal=%.1f > Reset=%.1f, aktiv=False",
                normal, self.reset_temp,
            )
            self.boost_active = True  # allow _async_boost_end to proceed
            await self._async_boost_end(REASON_STARTUP)
            return

        # Case 2: Boost marked active but stop condition already met
        if self.boost_active:
            sun = self.hass.states.get("sun.sun")
            pv = self._float(self._eid_pv_power)
            sun_below = sun and sun.state == "below_horizon"
            pv_low = pv is not None and pv < BOOST_END_PV_THRESHOLD_W
            if sun_below or pv_low:
                _LOGGER.warning(
                    "Startup-Heilung Fall 2: aktiv=True, Sonne=%s, PV=%s W",
                    sun.state if sun else "unknown", pv,
                )
                await self._async_boost_end(REASON_STARTUP_BOOST)

    # ------------------------------------------------------------------ #
    # WW temperature decay model (auto-learned from recorder history)
    # ------------------------------------------------------------------ #

    async def _async_refresh_cooling_rate(self) -> None:
        rate = await self._estimate_cooling_rate()
        if rate is not None:
            self._cached_cooling_rate = rate
            _LOGGER.debug("WW Abkuehlrate aktualisiert: %.3f °C/h", rate)

    async def _estimate_cooling_rate(self) -> float | None:
        """Estimate tank cooling rate (°C/h) from recorder history (last 48h)."""
        # pylint: disable=import-outside-toplevel
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.history import get_significant_states

        now = dt_util.utcnow()
        start = now - timedelta(hours=48)
        try:
            recorder = get_instance(self.hass)
            states_dict: dict = await recorder.async_add_executor_job(
                lambda: get_significant_states(
                    self.hass, start, now, [self._eid_ww_temp],
                    None,
                    include_start_time_state=True,
                    significant_changes_only=False,
                )
            )
        except Exception as err:
            _LOGGER.debug("Recorder-Abfrage fehlgeschlagen: %s", err)
            return None

        states = states_dict.get(self._eid_ww_temp, [])
        if len(states) < 4:
            return None

        cooling_rates: list[float] = []
        for prev, curr in zip(states, states[1:]):
            try:
                t_prev = float(prev.state)
                t_curr = float(curr.state)
            except (ValueError, TypeError):
                continue
            dt_h = (curr.last_updated - prev.last_updated).total_seconds() / 3600
            if dt_h <= 0:
                continue
            if t_prev > t_curr:
                rate = (t_prev - t_curr) / dt_h
                if 0.05 < rate < 5.0:  # sanity range
                    cooling_rates.append(rate)

        if not cooling_rates:
            return None

        # Median is more robust than mean against consumption spikes
        median = statistics.median(cooling_rates)
        _LOGGER.debug(
            "Abkuehlrate: Median=%.3f °C/h aus %d Segmenten (min=%.3f max=%.3f)",
            median, len(cooling_rates), min(cooling_rates), max(cooling_rates),
        )
        return median

    def _minutes_until_next_normal_cycle(self) -> int:
        """Return minutes until the next WP Normal heating cycle starts."""
        now = dt_util.now()
        cur = now.hour * 60 + now.minute
        windows = [
            (self.normal1_start_h * 60, self.normal1_end_h * 60),
            (self.normal2_start_h * 60, self.normal2_end_h * 60),
        ]
        for start_m, end_m in windows:
            if start_m <= cur < end_m:
                return 0  # currently in a Normal window
        candidates = [s - cur for s, _ in windows if s > cur]
        if candidates:
            return min(candidates)
        # Wrap to next day
        first_start = min(s for s, _ in windows)
        return (24 * 60 - cur) + first_start

    def _ww_ok_until_next_normal_cycle(self) -> bool:
        """Return True if WW will stay above comfort threshold until WP heats naturally."""
        if not self._cached_cooling_rate or self._cached_cooling_rate <= 0:
            return False
        ww = self._float(self._eid_ww_temp)
        if ww is None:
            return False
        minutes_until_critical = (ww - self.ww_min_comfort) / self._cached_cooling_rate * 60
        minutes_until_normal = self._minutes_until_next_normal_cycle()
        # 30 min safety margin: WP needs time to heat after cycle starts
        ok = minutes_until_critical > minutes_until_normal + 30
        if ok:
            _LOGGER.debug(
                "WW %.1f°C OK: kritisch in %.0f min, WP-Zyklus in %d min (Marge: %.0f min)",
                ww, minutes_until_critical, minutes_until_normal,
                minutes_until_critical - minutes_until_normal - 30,
            )
        return ok

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def async_manual_start(self) -> None:
        if self.boost_active or self.urlaub or self.status != STATUS_IDLE:
            return
        await self._async_boost_start("Manuell")

    async def async_manual_end(self) -> None:
        if self.boost_active:
            self._cancel_duration_tasks()
            await self._async_boost_end(REASON_MANUELL)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _wait_attr(
        self,
        entity_id: str,
        attribute: str,
        condition: Callable[[float], bool],
        timeout: float,
    ) -> bool:
        """Event-driven wait for a state attribute to satisfy a condition."""
        current = self.hass.states.get(entity_id)
        if current:
            raw = current.attributes.get(attribute)
            if raw is not None:
                try:
                    if condition(float(raw)):
                        return True
                except (ValueError, TypeError):
                    pass

        evt = asyncio.Event()

        @callback
        def _listener(ha_event: Any) -> None:
            ns = ha_event.data.get("new_state")
            if ns:
                raw = ns.attributes.get(attribute)
                if raw is not None:
                    try:
                        if condition(float(raw)):
                            evt.set()
                    except (ValueError, TypeError):
                        pass

        unsub = async_track_state_change_event(self.hass, [entity_id], _listener)
        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            unsub()

    def _float(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown", "none"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _attr(self, entity_id: str, attribute: str, default: Any = None) -> Any:
        state = self.hass.states.get(entity_id)
        return state.attributes.get(attribute, default) if state else default

    def _cancel_task(self, attr_name: str) -> None:
        task: asyncio.Task | None = getattr(self, attr_name, None)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        setattr(self, attr_name, None)

    def _create_tracked_task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = self.hass.async_create_task(coro)
        self._active_tasks.add(task)
        def _on_done(t: asyncio.Task) -> None:
            self._active_tasks.discard(t)
            if not t.cancelled() and (exc := t.exception()):
                _LOGGER.error("Coordinator-Task fehlgeschlagen: %s", exc, exc_info=exc)
        task.add_done_callback(_on_done)
        return task
