#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Führt die sinnvollen Minutenfenster-Vergleiche (calibrate_windowed()) für
# die real registrierten Geräte/Quellen dieses Setups aus (siehe
# ~/.config/kyoro/registry.json: device_registry — die eigentliche
# Quelle, health_config.json hat keinen eigenen device_registry mehr).
#
# Zwei Vergleichsachsen (siehe compute_calibrate_sources.py device_a-Docstring):
#   - Geräte-Achse (--device-a/--device-b): einzelne Polar-Geräte
#     gegeneinander (H10-Brustgurt vs. Handgelenk). Setzt voraus, dass
#     scripts/migrations/pseudonymize_polar_device_serials.py bereits
#     gelaufen ist (bestehende ppi_raw.device-Werte sind sonst noch die
#     rohen Seriennummern, nicht diese device_ids).
#   - Quellen-Achse (--source-a/--source-b): cross-App-Vergleiche laut
#     source_priority (polar_gdpr, apple_health, oura_api, garmin_api).
#
# H10-Gerätewahl pro Zeitraum: mehrere H10-Einheiten im Einsatz (polar_h10,
# polar_h10_2, ...) -- welche Einheit in welchem Zeitraum aktiv war, steht
# in registry.json (date_from/date_to je device_id), nicht hier im Code.
#
# Schreibt NICHTS in die DB (calibrate_windowed ist reine Analyse/Report,
# kein --dry-run nötig).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

SCRIPT=scripts/compute/compute_calibrate_sources.py

echo "=== Geräte-Achse: H10 (Brustgurt, erste Einheit) vs. Handgelenk ==="
echo "    — der eigentlich interessante Dash-2009-Kalibrierungsfall"
python3 "$SCRIPT" --windowed --device-a polar_h10 --device-b polar_v3 --metric hrv_rmssd
echo

echo "=== Geräte-Achse: H10 (Brustgurt, zweite Einheit) vs. Handgelenk ==="
python3 "$SCRIPT" --windowed --device-a polar_h10_2 --device-b polar_loop --metric hrv_rmssd
echo

echo "=== Geräte-Achse: H10 (Brustgurt, erste Einheit) vs. Handgelenk (2) ==="
python3 "$SCRIPT" --windowed --device-a polar_h10 --device-b polar_ignite2 --metric hrv_rmssd
echo

echo "=== Quellen-Achse: Polar vs. Apple (Herzfrequenz) ==="
python3 "$SCRIPT" --windowed --source-a polar_gdpr --source-b apple_health --metric heart_rate
echo

echo "=== Quellen-Achse: Oura vs. Apple (Herzfrequenz) ==="
python3 "$SCRIPT" --windowed --source-a oura_api --source-b apple_health --metric heart_rate
echo

echo "=== Quellen-Achse: Garmin vs. Apple (Herzfrequenz) ==="
python3 "$SCRIPT" --windowed --source-a garmin_api --source-b apple_health --metric heart_rate
echo

echo "=== Quellen-Achse: Polar vs. Apple ECG-abgeleitete RR-Intervalle (RMSSD) ==="
python3 "$SCRIPT" --windowed --source-a polar_connect --source-b ecg_apple --metric hrv_rmssd
