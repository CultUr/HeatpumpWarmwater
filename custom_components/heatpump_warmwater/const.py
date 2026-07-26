"""Constants for the Heatpump Warmwater PV Boost integration."""
from __future__ import annotations

DOMAIN = "heatpump_warmwater"

# Config entry data keys (set via Config Flow, immutable after setup)
CONF_ENTITY_WW_TEMP = "entity_ww_temp"
CONF_ENTITY_PV_FORECAST_THIS = "entity_pv_forecast_this_hour"
CONF_ENTITY_PV_FORECAST_NEXT = "entity_pv_forecast_next_hour"
CONF_ENTITY_PV_POWER = "entity_pv_power"
CONF_ENTITY_SOC = "entity_soc"
CONF_ENTITY_WW_ENERGY = "entity_ww_energy"
CONF_ENTITY_WP_NORMAL = "entity_wp_normal"
CONF_ENTITY_WP_ABSENK = "entity_wp_absenk"

# Default threshold values (adjustable via Number entities at runtime)
DEFAULT_ZIEL_TEMP = 53.0          # °C
DEFAULT_RESET_TEMP = 45.0         # °C
DEFAULT_MIN_PV_FORECAST = 1500.0  # W
DEFAULT_MIN_SOC = 60.0            # %
DEFAULT_START_SCHWELLE = 48.0     # °C — boost only if WW temp is below this
DEFAULT_FRUHESTER_START_H = 11    # hour 0-23 (frühester Start)

# Modbus wait timeout
MODBUS_WAIT_TIMEOUT = 120.0  # seconds

# End-trigger thresholds and durations
BOOST_END_PV_THRESHOLD_W = 1500
BOOST_END_SOC_THRESHOLD_PCT = 30
BOOST_END_PV_DURATION_S = 1800   # 30 min
BOOST_END_SOC_DURATION_S = 600   # 10 min
BOOST_END_TEMP_HOLD_S = 180      # 3 min: WW temp must stay >= Ziel
BOOST_MAX_DURATION_S = 9000      # 2.5 h

# Status values for sensor.ww_boost_status
STATUS_IDLE = "idle"
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_STOPPING = "stopping"

# End reasons (shown in Logbook)
REASON_ZIEL = "Ziel erreicht"
REASON_SONNE = "Sonne weg"
REASON_PV = "PV weg"
REASON_SOC = "Akku leer"
REASON_TIMEOUT = "Timeout 2.5h"
REASON_MANUELL = "Manuell beendet"
REASON_STARTUP = "Startup-Heilung"
REASON_STARTUP_BOOST = "Startup-Heilung: Neustart waehrend Boost"

# Entity registration keys (coordinator._entities dict)
KEY_AUTOMATIK = "automatik"
KEY_URLAUB = "urlaub"
KEY_AKTIV = "aktiv"
KEY_HEUTE_GELAUFEN = "heute_gelaufen"
KEY_STATUS = "status"
KEY_KWH = "kwh_heute"
KEY_LETZTER_START = "letzter_start"
KEY_ZIEL_TEMP = "ziel_temp"
KEY_RESET_TEMP = "reset_temp"
KEY_MIN_PV = "min_pv"
KEY_MIN_SOC = "min_soc"
KEY_SCHWELLE = "schwelle"
KEY_FRUHESTER = "fruhester_start_h"
