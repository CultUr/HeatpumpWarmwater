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
        "ext_ww_temp":      _data.get(CONF_ENTITY_WW_TEMP),
        "ext_pv_power":     _data.get(CONF_ENTITY_PV_POWER),
        "ext_pv_forecast":  _data.get(CONF_ENTITY_PV_FORECAST_THIS),
        "ext_soc":          _data.get(CONF_ENTITY_SOC),
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
    existing = await store.async_load()
    if existing:
        # Skip only if config already has content — first write may have been empty
        # (entities not yet in registry during initial platform setup)
        views = existing.get("config", {}).get("views", [])
        if any(v.get("cards") or v.get("sections") for v in views):
            return
    await store.async_save({"config": _build_config(em)})
    _LOGGER.info("WW PV Boost Dashboard Konfiguration gespeichert")


def _tile(*pairs: tuple[str | None, str]) -> list[dict[str, Any]]:
    return [{"type": "tile", "entity": eid, "name": name} for eid, name in pairs if eid]


def _tile_num(*pairs: tuple[str | None, str]) -> list[dict[str, Any]]:
    return [
        {"type": "tile", "entity": eid, "name": name, "features": [{"type": "numeric-input", "style": "buttons"}]}
        for eid, name in pairs if eid
    ]


def _section(heading: str, icon: str, cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "grid", "cards": [{"type": "heading", "heading": heading, "icon": icon}, *cards]}


def _build_config(em: dict[str, str]) -> dict[str, Any]:
    return {
        "title": "WW PV Boost",
        "views": [
            {
                "title": "Uebersicht",
                "path": "overview",
                "icon": "mdi:water-thermometer-outline",
                "type": "sections",
                "max_columns": 3,
                "sections": _overview_sections(em),
            },
            {
                "title": "Konfiguration",
                "path": "config",
                "icon": "mdi:cog-outline",
                "type": "sections",
                "max_columns": 3,
                "sections": _config_sections(em),
            },
        ],
    }


def _overview_sections(em: dict[str, str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    anlage = _tile(
        (em.get("ext_ww_temp"), "WW-Temperatur"),
        (em.get("ext_pv_power"), "PV-Leistung"),
        (em.get("ext_soc"), "Akku-SoC"),
    )
    if anlage:
        sections.append(_section("Anlage", "mdi:solar-power", anlage))

    status = _tile(
        (em.get("status"),          "Status"),
        (em.get("aktiv"),           "Boost aktiv"),
        (em.get("heute_gelaufen"),  "Heute gelaufen"),
        (em.get("kwh_heute"),       "kWh heute"),
        (em.get("letzter_start"),   "Letzter Start"),
        (em.get("ext_pv_forecast"), "PV-Forecast heute"),
    )
    if status:
        sections.append(_section("Status", "mdi:information-outline", status))

    control = _tile(
        (em.get("automatik"), "Automatik"),
        (em.get("urlaub"),    "Urlaub"),
        (em.get("btn_start"), "Manuell starten"),
        (em.get("btn_end"),   "Manuell beenden"),
    )
    if control:
        sections.append(_section("Steuerung", "mdi:tune", control))

    return sections


def _config_sections(em: dict[str, str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []

    temp = [
        {"type": "tile", "entity": eid, "name": name, "features": [{"type": "numeric-input", "style": "slider"}]}
        for eid, name in [
            (em.get("ziel_temp"),      "Ziel-Temperatur"),
            (em.get("reset_temp"),     "Reset-Temperatur"),
            (em.get("schwelle"),       "Start-Schwelle WW"),
            (em.get("ww_min_comfort"), "WW Mindestkomfort"),
        ] if eid
    ]
    if temp:
        sections.append(_section("Temperaturen & Schwellen", "mdi:thermometer", temp))

    pv = _tile_num(
        (em.get("min_pv"),           "Min PV-Forecast (W)"),
        (em.get("min_soc"),          "Min Akku-SoC (%)"),
        (em.get("fruhester"),        "Fruehester Start (h)"),
        (em.get("min_today_kwh"),    "Min Tages-Forecast (kWh)"),
        (em.get("min_tomorrow_kwh"), "Aufschub morgen besser (kWh)"),
        (em.get("min_grid_surplus"), "Min Einspeisung Reaktiv (W)"),
        (em.get("min_soc_grid"),     "Min SoC Reaktiv (%)"),
    )
    if pv:
        sections.append(_section("PV & Startbedingungen", "mdi:solar-panel", pv))

    schedule = _tile_num(
        (em.get("normal1_start"), "Fenster 1 Start (h)"),
        (em.get("normal1_end"),   "Fenster 1 Ende (h)"),
        (em.get("normal2_start"), "Fenster 2 Start (h)"),
        (em.get("normal2_end"),   "Fenster 2 Ende (h)"),
    )
    if schedule:
        sections.append(_section("WP Normal-Fenster", "mdi:clock-time-four-outline", schedule))

    return sections
