"""Automatic Lovelace dashboard creation for WW PV Boost."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ENTITY_PV_FORECAST_THIS,
    CONF_ENTITY_PV_POWER,
    CONF_ENTITY_SOC,
    CONF_ENTITY_WW_TEMP,
    DOMAIN,
    KEY_AKTIV,
    KEY_AUTOMATIK,
    KEY_FRUHESTER,
    KEY_HEUTE_GELAUFEN,
    KEY_KWH,
    KEY_LETZTER_START,
    KEY_MIN_GRID_SURPLUS,
    KEY_MIN_PV,
    KEY_MIN_SOC,
    KEY_MIN_SOC_GRID,
    KEY_MIN_TODAY_KWH,
    KEY_MIN_TOMORROW_KWH,
    KEY_NORMAL1_END,
    KEY_NORMAL1_START,
    KEY_NORMAL2_END,
    KEY_NORMAL2_START,
    KEY_RESET_TEMP,
    KEY_SCHWELLE,
    KEY_STATUS,
    KEY_URLAUB,
    KEY_WW_MIN_COMFORT,
    KEY_ZIEL_TEMP,
)

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL = "ww-pv-boost"
_DASHBOARDS_STORE = "lovelace_dashboards"
_STORE_VERSION = 1


async def async_setup_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create the WW PV Boost Lovelace dashboard if not already present."""
    try:
        em = _collect_entity_ids(hass, entry)
        await _ensure_registered(hass)
        await _ensure_config(hass, em)
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.warning("WW Boost Dashboard Setup fehlgeschlagen: %s", err)


def _collect_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str]:
    registry = er.async_get(hass)

    def own(domain: str, key: str) -> str:
        return registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}") or ""

    _data = {**entry.data, **entry.options}

    return {
        # Integration-owned entities
        "automatik":        own("switch",        KEY_AUTOMATIK),
        "urlaub":           own("switch",        KEY_URLAUB),
        "aktiv":            own("binary_sensor", KEY_AKTIV),
        "heute_gelaufen":   own("binary_sensor", KEY_HEUTE_GELAUFEN),
        "status":           own("sensor",        KEY_STATUS),
        "kwh_heute":        own("sensor",        KEY_KWH),
        "letzter_start":    own("sensor",        KEY_LETZTER_START),
        "btn_start":        own("button",        "btn_start"),
        "btn_end":          own("button",        "btn_end"),
        "ziel_temp":        own("number",        KEY_ZIEL_TEMP),
        "reset_temp":       own("number",        KEY_RESET_TEMP),
        "schwelle":         own("number",        KEY_SCHWELLE),
        "ww_min_comfort":   own("number",        KEY_WW_MIN_COMFORT),
        "min_pv":           own("number",        KEY_MIN_PV),
        "min_soc":          own("number",        KEY_MIN_SOC),
        "fruhester":        own("number",        KEY_FRUHESTER),
        "min_today_kwh":    own("number",        KEY_MIN_TODAY_KWH),
        "min_tomorrow_kwh": own("number",        KEY_MIN_TOMORROW_KWH),
        "min_grid_surplus": own("number",        KEY_MIN_GRID_SURPLUS),
        "min_soc_grid":     own("number",        KEY_MIN_SOC_GRID),
        "normal1_start":    own("number",        KEY_NORMAL1_START),
        "normal1_end":      own("number",        KEY_NORMAL1_END),
        "normal2_start":    own("number",        KEY_NORMAL2_START),
        "normal2_end":      own("number",        KEY_NORMAL2_END),
        # External sensors from user config
        "ext_ww_temp":      _data.get(CONF_ENTITY_WW_TEMP, ""),
        "ext_pv_power":     _data.get(CONF_ENTITY_PV_POWER, ""),
        "ext_pv_forecast":  _data.get(CONF_ENTITY_PV_FORECAST_THIS, ""),
        "ext_soc":          _data.get(CONF_ENTITY_SOC, ""),
    }


async def _ensure_registered(hass: HomeAssistant) -> None:
    store: Store = Store(hass, _STORE_VERSION, _DASHBOARDS_STORE)
    data: dict[str, Any] = await store.async_load() or {"items": []}
    items: list[dict[str, Any]] = data.get("items", [])

    if any(d.get("url_path") == DASHBOARD_URL for d in items):
        return

    items.append({
        "id": uuid.uuid4().hex,
        "url_path": DASHBOARD_URL,
        "require_admin": False,
        "mode": "storage",
        "title": "WW PV Boost",
        "icon": "mdi:water-thermometer-outline",
        "show_in_sidebar": True,
    })
    data["items"] = items
    await store.async_save(data)
    _LOGGER.info("WW PV Boost Dashboard registriert (/%s)", DASHBOARD_URL)


async def _ensure_config(hass: HomeAssistant, em: dict[str, str]) -> None:
    store: Store = Store(hass, _STORE_VERSION, f"lovelace.{DASHBOARD_URL}")
    if await store.async_load():
        return  # User may have customized it — never overwrite
    await store.async_save({"config": _build_config(em)})
    _LOGGER.info("WW PV Boost Dashboard Konfiguration gespeichert")


def _rows(*items: dict[str, str]) -> list[dict[str, str]]:
    return [row for row in items if row.get("entity")]


def _build_config(em: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "WW PV Boost",
        "views": [
            {
                "title": "Uebersicht",
                "path": "overview",
                "icon": "mdi:water-thermometer-outline",
                "cards": _overview_cards(em),
            },
            {
                "title": "Konfiguration",
                "path": "config",
                "icon": "mdi:cog-outline",
                "cards": _config_cards(em),
            },
        ],
    }


def _overview_cards(em: dict[str, str]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []

    # Gauges: WW-Temp | PV | SoC
    gauges: list[dict[str, Any]] = []
    if em.get("ext_ww_temp"):
        gauges.append({
            "type": "gauge",
            "entity": em["ext_ww_temp"],
            "name": "WW-Temperatur",
            "unit": "°C",
            "min": 20,
            "max": 65,
            "needle": True,
            "severity": {"green": 45, "yellow": 38, "red": 0},
        })
    if em.get("ext_pv_power"):
        gauges.append({
            "type": "gauge",
            "entity": em["ext_pv_power"],
            "name": "PV-Leistung",
            "min": 0,
            "max": 12000,
            "needle": True,
            "severity": {"green": 3000, "yellow": 1000, "red": 0},
        })
    if em.get("ext_soc"):
        gauges.append({
            "type": "gauge",
            "entity": em["ext_soc"],
            "name": "Akku-SoC",
            "min": 0,
            "max": 100,
            "needle": True,
            "severity": {"green": 60, "yellow": 30, "red": 0},
        })
    if gauges:
        cards.append({"type": "horizontal-stack", "cards": gauges})

    # Status + Control side by side
    status_rows = _rows(
        {"entity": em.get("status", ""),          "name": "Status"},
        {"entity": em.get("aktiv", ""),            "name": "Boost aktiv"},
        {"entity": em.get("heute_gelaufen", ""),   "name": "Heute gelaufen"},
        {"entity": em.get("kwh_heute", ""),        "name": "kWh heute"},
        {"entity": em.get("letzter_start", ""),    "name": "Letzter Start"},
        {"entity": em.get("ext_pv_forecast", ""),  "name": "PV-Forecast aktuelle Std."},
    )
    control_rows = _rows(
        {"entity": em.get("automatik", ""),  "name": "Automatik"},
        {"entity": em.get("urlaub", ""),     "name": "Urlaub"},
        {"entity": em.get("btn_start", ""),  "name": "Manuell starten"},
        {"entity": em.get("btn_end", ""),    "name": "Manuell beenden"},
    )

    side: list[dict[str, Any]] = []
    if status_rows:
        side.append({"type": "entities", "title": "Status", "entities": status_rows})
    if control_rows:
        side.append({"type": "entities", "title": "Steuerung", "entities": control_rows})

    if len(side) == 2:
        cards.append({"type": "horizontal-stack", "cards": side})
    elif side:
        cards.extend(side)

    return cards


def _config_cards(em: dict[str, str]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []

    temp_rows = _rows(
        {"entity": em.get("ziel_temp", ""),       "name": "Ziel-Temperatur"},
        {"entity": em.get("reset_temp", ""),      "name": "Reset-Temperatur"},
        {"entity": em.get("schwelle", ""),        "name": "Start-Schwelle WW"},
        {"entity": em.get("ww_min_comfort", ""),  "name": "WW Mindestkomfort"},
    )
    if temp_rows:
        cards.append({"type": "entities", "title": "Temperaturen & Schwellen", "entities": temp_rows})

    pv_rows = _rows(
        {"entity": em.get("min_pv", ""),            "name": "Min PV-Forecast (W)"},
        {"entity": em.get("min_soc", ""),            "name": "Min Akku-SoC (Forecast-Start)"},
        {"entity": em.get("fruhester", ""),          "name": "Fruehester Start (Stunde)"},
        {"entity": em.get("min_today_kwh", ""),      "name": "Min Tages-Forecast heute (kWh)"},
        {"entity": em.get("min_tomorrow_kwh", ""),   "name": "Aufschub wenn morgen besser (kWh)"},
        {"entity": em.get("min_grid_surplus", ""),   "name": "Min Einspeisung Reaktiv-Start (W)"},
        {"entity": em.get("min_soc_grid", ""),       "name": "Min SoC Reaktiv-Start (%)"},
    )
    if pv_rows:
        cards.append({"type": "entities", "title": "PV & Startbedingungen", "entities": pv_rows})

    schedule_rows = _rows(
        {"entity": em.get("normal1_start", ""),  "name": "Normal-Fenster 1 Start (h)"},
        {"entity": em.get("normal1_end", ""),    "name": "Normal-Fenster 1 Ende (h)"},
        {"entity": em.get("normal2_start", ""),  "name": "Normal-Fenster 2 Start (h)"},
        {"entity": em.get("normal2_end", ""),    "name": "Normal-Fenster 2 Ende (h)"},
    )
    if schedule_rows:
        cards.append({"type": "entities", "title": "WP Zeitplan (Normal-Fenster)", "entities": schedule_rows})

    return cards
