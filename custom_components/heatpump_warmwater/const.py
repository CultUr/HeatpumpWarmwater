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
# Optional: Solcast daily totals and grid power for improved start logic
CONF_ENTITY_SOLCAST_TODAY_KWH = "entity_solcast_today_kwh"
CONF_ENTITY_SOLCAST_TOMORROW_KWH = "entity_solcast_tomorrow_kwh"
CONF_ENTITY_GRID_POWER = "entity_grid_power"

# Default threshold values (adjustable via Number entities at runtime)
DEFAULT_ZIEL_TEMP = 53.0          # °C
DEFAULT_RESET_TEMP = 45.0         # °C
DEFAULT_MIN_PV_FORECAST = 1500.0  # W
DEFAULT_MIN_SOC = 60.0            # %
DEFAULT_START_SCHWELLE = 48.0     # °C — boost only if WW temp is below this
DEFAULT_FRUHESTER_START_H = 11    # hour 0-23 (frühester Start)
DEFAULT_MIN_FORECAST_TODAY_KWH = 6.0    # kWh — Mindestertrag heute für Forecast-Start
DEFAULT_MIN_FORECAST_TOMORROW_KWH = 15.0  # kWh — "morgen viel besser" → heute aufschieben
DEFAULT_MIN_GRID_SURPLUS_W = 1000.0     # W Einspeisung ins Netz → reaktiver Start
DEFAULT_ABSENK_RESET = 35.0            # °C — Absenk-Standby nach Boost-Ende
DEFAULT_WW_MIN_COMFORT = 42.0           # °C — WW-Mindesttemperatur vor dringendem Boost
DEFAULT_NORMAL1_START_H = 5             # WP Normal-Fenster 1 Start (Stunde)
DEFAULT_NORMAL1_END_H = 8               # WP Normal-Fenster 1 Ende (Stunde)
DEFAULT_NORMAL2_START_H = 11            # WP Normal-Fenster 2 Start (Stunde)
DEFAULT_NORMAL2_END_H = 16              # WP Normal-Fenster 2 Ende (Stunde)

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
KEY_MIN_TODAY_KWH = "min_forecast_today_kwh"
KEY_MIN_TOMORROW_KWH = "min_forecast_tomorrow_kwh"
KEY_MIN_GRID_SURPLUS = "min_grid_surplus_w"
KEY_WW_MIN_COMFORT = "ww_min_comfort"
KEY_NORMAL1_START = "normal1_start_h"
KEY_NORMAL1_END = "normal1_end_h"
KEY_NORMAL2_START = "normal2_start_h"
KEY_NORMAL2_END = "normal2_end_h"
