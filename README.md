# Heatpump Warmwater PV Boost

Home Assistant Custom Integration: PV-gesteuerter Warmwasser-Boost fuer Weishaupt-Waermepumpen mit Solcast-Prognose und Huawei EMMA Speicher.

Ersetzt 5 Automationen + 2 Skripte + 14 Helper durch eine einzige native HA-Integration.

## Voraussetzungen

- Home Assistant >= 2024.1
- Weishaupt Waermepumpe mit Modbus-Integration (`number.*_warmwasser_normal`, `number.*_warmwasser_absenk`)
- Solcast PV-Prognose (`sensor.*_forecast_this_hour`, `sensor.*_forecast_next_hour`)
- Huawei EMMA (`sensor.emma_pv_output_power`, `sensor.emma_state_of_capacity`)
- WW-Energiezaehler (`sensor.*_warmwasser_energie_heute`)

## Installation via HACS

1. HACS oeffnen
2. Integrations → Drei-Punkte-Menu → Custom repositories
3. URL: `https://github.com/CultUr/HeatpumpWarmwater` — Kategorie: Integration
4. Integration suchen und installieren
5. HA neu starten
6. Settings → Integrations → + → **WW PV Boost**
7. Entity-IDs konfigurieren (vorausgefuellt mit Dasing-Defaults)

## Entities

| Entity | Typ | Beschreibung |
|--------|-----|--------------|
| `switch.ww_boost_automatik` | Switch | Automatik ein/aus |
| `switch.ww_boost_urlaub` | Switch | Urlaubsmodus |
| `binary_sensor.ww_boost_aktiv` | Sensor | Boost laeuft gerade |
| `binary_sensor.ww_boost_heute_gelaufen` | Sensor | Boost heute gelaufen |
| `sensor.ww_boost_status` | Sensor | idle / starting / running / stopping |
| `sensor.ww_boost_kwh_heute` | Sensor | Boost-Energie heute (kWh) |
| `sensor.ww_boost_letzter_start` | Sensor | Zeitstempel letzter Start |
| `number.ww_boost_ziel_temp` | Number | Ziel-Temperatur (°C) |
| `number.ww_boost_reset_temp` | Number | Normal-Sollwert nach Boost (°C) |
| `number.ww_boost_schwelle` | Number | Start-Schwelle WW-Temp (°C) |
| `number.ww_boost_min_pv` | Number | Mindest-PV-Prognose (W) |
| `number.ww_boost_min_soc` | Number | Mindest-Akku-SoC (%) |
| `button.ww_boost_btn_start` | Button | Manuellen Boost starten |
| `button.ww_boost_btn_end` | Button | Boost manuell beenden |

## Boost-Logik

**Start (Automatik):** PV-Forecast (diese + naechste Stunde) > Min-PV, SoC > Min-SoC, Sonnenhoehe > 15 Grad, WW-Temp < Schwelle, nach Frueheststunde, nicht heute gelaufen, kein Urlaub.

**Modbus-Sequenz Start:** Normal-Sollwert hoch → warten bis Absenk.max folgt (max. 2 min) → Absenk-Sollwert setzen.

**Ende (eines von):** Ziel-Temp 3 min gehalten · Sonne unter Horizont · PV < 1500 W fuer 30 min · SoC < 30 % fuer 10 min · Timeout 2,5 h.

**Modbus-Sequenz Ende:** Absenk auf 35 °C → warten bis Normal.min folgt → Normal-Sollwert zurueck.

**Startup-Heilung:** 2 min nach HA-Neustart Inkonsistenz-Check (zwei Faelle).

## Lizenz

MIT
