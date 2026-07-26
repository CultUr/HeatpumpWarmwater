# Heatpump Warmwater PV Boost

Home Assistant Custom Integration: PV-gesteuerter Warmwasser-Boost fuer Waermepumpen.

Startet die Warmwasser-Aufheizung automatisch, wenn genug PV-Leistung und Akkukapazitaet vorhanden sind. Ersetzt 5 Automationen + 2 Skripte + 14 Helper durch eine einzige native HA-Integration.

## Voraussetzungen

- Home Assistant >= 2024.1
- Waermepumpe mit **zwei steuerbaren Sollwert-Entities** (Normal + Absenk) als `number.*`
- **PV-Forecast-Sensor** fuer aktuelle und naechste Stunde (Watt), z.B. Solcast
- **PV-Leistungs-Sensor** aktuell (Watt)
- **Akku-SoC-Sensor** (%), falls kein Speicher vorhanden: Dummy-Sensor mit festem Wert
- **WW-Temperatur-Sensor** (°C)
- **WW-Energie-Sensor** (kWh, Tageswert), optional — fuer Verbrauchsstatistik

## Installation via HACS

1. HACS oeffnen
2. Integrations → Drei-Punkte-Menu → Custom repositories
3. URL: `https://github.com/CultUr/HeatpumpWarmwater` — Kategorie: Integration
4. Integration suchen und installieren
5. HA neu starten
6. Settings → Integrations → + → **WW PV Boost**
7. Die 8 Entity-IDs in den Entity-Pickern auswaehlen

## Entities

| Entity | Typ | Beschreibung |
|--------|-----|--------------|
| `switch.ww_boost_automatik` | Switch | Automatik ein/aus |
| `switch.ww_boost_urlaub` | Switch | Urlaubsmodus (sperrt Boost) |
| `binary_sensor.ww_boost_aktiv` | Sensor | Boost laeuft gerade |
| `binary_sensor.ww_boost_heute_gelaufen` | Sensor | Boost heute bereits gelaufen |
| `sensor.ww_boost_status` | Sensor | idle / starting / running / stopping |
| `sensor.ww_boost_kwh_heute` | Sensor | Boost-Energie heute (kWh) |
| `sensor.ww_boost_letzter_start` | Sensor | Zeitstempel letzter Start |
| `number.ww_boost_ziel_temp` | Number | Ziel-Temperatur Boost (°C) |
| `number.ww_boost_reset_temp` | Number | Normal-Sollwert nach Boost-Ende (°C) |
| `number.ww_boost_schwelle` | Number | Max. WW-Temp zum Start (°C) |
| `number.ww_boost_min_pv` | Number | Mindest-PV-Prognose fuer Start (W) |
| `number.ww_boost_min_soc` | Number | Mindest-Akku-SoC fuer Start (%) |
| `number.ww_boost_fruehester_start` | Number | Frueheste Startstunde (0–23) |
| `button.ww_boost_btn_start` | Button | Manuellen Boost starten |
| `button.ww_boost_btn_end` | Button | Boost manuell beenden |

## Boost-Logik

**Start (Automatik):** PV-Forecast (aktuelle + naechste Stunde) > Min-PV, SoC > Min-SoC, Sonnenhoehe > 15°, WW-Temp < Schwelle, nach Frueheststunde, Boost heute noch nicht gelaufen, kein Urlaub.

**Modbus-Sequenz Start:** Normal-Sollwert erhoehen → warten bis Absenk.max-Attribut folgt (max. 2 min) → Absenk-Sollwert setzen. Timeout → Abbruch ohne Aenderung.

**Ende — eines der folgenden Kriterien:**
- Ziel-Temp 3 min gehalten
- Sonne unter Horizont
- PV-Leistung < 1500 W fuer 30 min
- SoC < 30 % fuer 10 min
- Timeout nach 2,5 h

**Modbus-Sequenz Ende:** Absenk auf 35 °C → warten bis Normal.min-Attribut folgt → Normal-Sollwert zuruecksetzen.

**Startup-Heilung:** 2 min nach HA-Neustart prueft die Integration auf zwei Inkonsistenz-Faelle (Boost-Flag und Sollwert stimmen nicht ueberein).

**Manueller Start:** Der manuelle Start-Button ignoriert `heute_gelaufen` bewusst — ein zweiter Boost am selben Tag ist damit als Override moeglich.

## Getestet mit

- Weishaupt Biblock WWP LB 12-A (Modbus via `weishaupt_modbus` HACS-Integration)
- Solcast PV-Prognose
- Huawei EMMA Energiemanagement + Speicher

## Lizenz

MIT
