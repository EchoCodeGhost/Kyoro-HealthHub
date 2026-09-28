<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Messprotokoll: Inhalation + SpO2-Verlauf

> **English version:** [INHALATION_RESPONSE_PROTOCOL.md](INHALATION_RESPONSE_PROTOCOL.md)

**Zweck:** Dokumentation der SpO2/HR-Reaktion auf eine inhalative Behandlung (z.B. Kochsalz-/Ectoin-Inhalation, Bronchodilatator)
**Gerät:** Finger-Pulsoximeter (Medizinprodukt)
**Parallelaufzeichnung:** Wearable-Tag "Inhalation/Atemtherapie" setzen, falls verfügbar (für Nacht-SpO2-Korrelation)

---

## Standardablauf

| Schritt | Zeitpunkt | Aktion |
|---------|-----------|--------|
| 1 | T−5 Min | Ruhig sitzen, Pulsoximeter anlegen (Zeigefinger oder Mittelfinger) |
| 2 | T−2 Min | **Baseline ablesen:** SpO2 + HR notieren (Wert soll stabil sein, nicht schwanken) |
| 3 | T=0 | Inhalation starten, Pulsoximeter bleibt am Finger |
| 4 | Während | Auffällige Veränderungen notieren (SpO2 fällt/steigt, HR-Reaktion) |
| 5 | T+5 Min | Erster Nachwert direkt nach Inhalationsende |
| 6 | T+15 Min | Zweiter Nachwert |
| 7 | T+30 Min | Dritter Nachwert (optional, wenn Zeit) |
| 8 | Abend | Wearable-Tag "Inhalation/Atemtherapie" setzen, falls verfügbar |

---

## Messdokumentation (Vorlage)

### Datum: ________ Uhrzeit Start: ________

**Körperzustand vor Inhalation:**
- Atemgefühl: ☐ frei  ☐ leicht eingeschränkt  ☐ deutlich eingeschränkt  ☐ Engegefühl
- Schleimgefühl: ☐ keiner  ☐ wenig  ☐ viel  ☐ zäh
- Allgemeine Beschwerden: ___________________________________

**Messwerte:**

| Zeitpunkt | SpO2 (%) | HR (bpm) | Bemerkung |
|-----------|----------|----------|-----------|
| T−2 Min (Baseline) | | | |
| Während Inhalation | | | z.B. "Husten", "Schleim löst sich" |
| T+5 Min | | | |
| T+15 Min | | | |
| T+30 Min (opt.) | | | |

**Atemgefühl nach Inhalation:**
- ☐ deutlich freier  ☐ etwas freier  ☐ unverändert  ☐ schlechter

**Sonstiges:**
___________________________________

*(Abschnitt für jede weitere Messung kopieren.)*

---

## Auswertungshinweise

**Was ein positiver Befund wäre:**
- SpO2 T+5 oder T+15 ≥ 1–2 Punkte über Baseline → Atemwegsobstruktion durch Schleim/Inflammation belegt
- Effekt hält ≥ 1 Tag (Nacht-SpO2 die folgende Nacht höher) → die Inhalation wirkt über Nacht nach

**Was auf eine entzündliche/reaktive Atemwegskomponente hindeuten kann** (z.B. bei Mastzellerkrankungen, Asthma, COPD):
- Baseline-SpO2 variiert von Tag zu Tag um ≥ 2 Punkte (ohne körperliche Ursache)
- SpO2 fällt typisch abends/nachts und ist morgens niedriger
- Inhalation bricht das Muster für mehrere Tage

**Für die Arztdokumentation:**
- Dieses Protokoll + Wearable-Tagesverlauf + Nacht-SpO2-Trend zusammen zum Rheumatologen / Pulmologen mitbringen
- Bei nächtlichen Auffälligkeiten: Polygraphie-Indikation prüfen (Schlafapnoe vs. nächtliche Bronchokonstriktion als Differentialdiagnose)

---

## Eintragen in Kyoro-HealthHub

Messwerte lassen sich über die Symptom-/Notiz-Importpfade dokumentieren; für eine strukturierte Auswertung Wearable-SpO2-Daten und Inhalationszeitpunkte über den Tageszeit-Tag korrelieren (siehe `scripts/analysis/` für passende Analyse-Skripte je nach verwendetem Gerät).
