# ppi_provenance.py — effektiver Messmodus fuer ppi_raw-Beat-zu-Beat-Intervalle

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/ppi_provenance.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ein Geraet kann mehrere Messmodi haben: eine Uhr misst dauerhaft optisch am Handgelenk, kann aber zusaetzlich eine EKG-Ableitung aufzeichnen, aus der Schlag-zu-Schlag-Intervalle berechnet werden. Beide landen in `ppi_raw` unter derselben `device_id` und damit demselben `sensor_type` aus der Geraeteregistry — Nachschlagen allein ueber das Geraet kann die beiden Modi nicht unterscheiden. Dieses Modul beantwortet stattdessen "wie wurde DIESES Intervall gewonnen", aus den Daten statt aus dem Geraet.

## Relevanz

Ohne dieses Modul stuft die Sensor-Bewertung EKG-abgeleitete Intervalle wie eine optische Messung ein (oder umgekehrt) und verzerrt die Gewichtung genau in die falsche Richtung — je nachdem, ob zuletzt optisch wie EKG oder EKG wie optisch behandelt wurde.

## Methode

`ppi_raw.source` traegt bei EKG-abgeleiteten Zeilen ein Praefix 'ecg_' (z.B. 'ecg_apple', 'ecg_garmin', 'ecg_logger', 'ecg_unknown') — gesetzt direkt beim Schreiben durch compute_ecg_rpeaks.py (R-Zacken-Erkennung aus ecg_sessions/ecg_samples, Quelle geraeteagnostisch aus ecg_sessions.source abgeleitet) bzw. import_ecg_logger.py (QRS-Erkennung aus einem Brustgurt-EKG-Rohsignal, source='ecg_logger'), unabhaengig vom sensor_type des liefernden Geraets. Das Praefix ist damit die einzige direkte, markenunabhaengige Angabe, WIE ein Intervall gewonnen wurde — im Gegensatz zu Marken- strings wie 'ecg_apple' selbst, die pro Hersteller verschieden heissen und bei einem neuen Geraet fehlen wuerden. Ein zweites Kriterium (zeitliche Ueberlappung von ppi_raw.datetime mit ecg_sessions[.datetime, +duration_s] fuer dieselbe person) liefert auf der Projekt-DB dieselben 227 von 227 EKG-abgeleiteten Zeilen, ist aber teurer (Join, plus Normalisierung zweier unterschiedlich formatierter Timestamp-Spalten — ecg_sessions.datetime traegt ein '+00:00'-Suffix, ppi_raw.datetime nicht; ein naiver String-Vergleich ohne datetime()-Normalisierung findet dadurch 0 Treffer statt 227) und haengt von ecg_sessions/-samples ab statt vom Ort der Wahrheit (der Zeile selbst). Deshalb: das source-Praefix ist das primaere Kriterium hier.

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `ok` | Mehrheit (>50%) der betrachteten Beats traegt das Praefix 'ecg_' -> Modus 'ecg' |

## Datenfluss

- **Liest:** `ppi_raw`, `(Spalte`, `source`, `datetime`, `person);`, `modules/device_registry`, `(Fallback-Sensorklasse`, `wenn`, `keine`, `EKG-Mehrheit`, `vorliegt)`
- **Schreibt:** `keine`

## Grenzen

Setzt voraus, dass jeder EKG-Ableitungspfad seine ppi_raw-Zeilen mit dem Praefix 'ecg_' markiert (aktuell: compute_ecg_rpeaks.py, import_ecg_logger.py — per Grep ueber alle INSERT-INTO-ppi_raw-Stellen verifiziert, s. compute_arrhythmia.py ALGO_ROUTING-Kommentar). Ein neuer Importpfad, der EKG-abgeleitete RR-Intervalle schreibt, MUSS dieses Praefix setzen — sonst faellt er unerkannt auf die Sensorklasse des Geraets zurueck (sichere Seite: eher zu vorsichtig als zu optimistisch bewertet). Mehrheitsregel statt "irgendein EKG-Beat zaehlt": ein Fenster/Tag mit vereinzelten EKG-Spotchecks inmitten durchgehender optischer Messung bleibt bei der optischen Sensorklasse, damit ein einzelner 30-s-EKG-Check nicht die ganze Periode aufwertet.

## Aufruf

```bash
from modules.ppi_provenance import mode_from_sources, window_mode, day_modes
from modules.sensor_confidence import grade_for
```
