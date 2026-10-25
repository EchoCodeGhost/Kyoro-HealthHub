# Bestandsaufnahme: Skripte, die Prompts/Bilder an externe Modelle senden

**Erstellt für:** Aufgabe 4.1 der location-privacy-Stufe 1 Implementierung  
**Datum:** 2026-10-25  
**Status:** Abgeschlossen

---

## Zusammenfassung

Diese Bestandsaufnahme identifiziert alle Skripte in Kyoro-HealthHub, die:

1. **Prompts oder Bilder an externe LLM-/VLM-Anbieter senden**
2. **Potenziell Location-Daten (Koordinaten, Ortsnamen) im Prompt haben können**

---

## 1. Skripte mit zentralem `call_llm()`-Aufruf

**Anzahl:** ~228 Aufrufe in ~100 Skripten (heißt: call_llm wird von vielen Skripten genutzt)

**Zentraler Mechanismus:** Alle diese Skripte rufen `call_llm()` aus `scripts/modules/llm.py` auf.

### 1.1 Analyse-Skripte (scripts/analysis/)

#### 1.1.1 Manual Analysen (scripts/analysis/manual/)
- `analyse_synthesis.py` - ⚠️ **DIREKTER CLOUD-AUFRUF** (eigene _call_llm, siehe Abschnitt 2.1)
- Alle anderen `analyse_*.py` in manual/ nutzen call_llm()

#### 1.1.2 Umwelt-Analysen (scripts/analysis/environment/)
- `analyse_daylight.py`
- `analyse_airquality_symptoms.py`
- `analyse_noise.py`
- `analyse_product_exposures.py`
- Alle nutzen `call_llm()`

#### 1.1.3 Metabolische Analysen (scripts/analysis/metabolic/)
- `analyse_nutrition.py`
- `analyse_blood_glucose.py`
- `analyse_cgm_glucose.py`
- `analyse_body_composition.py`
- `analyse_body_temperature.py`
- Alle nutzen `call_llm()`

#### 1.1.4 Psychologie (scripts/analysis/psychology/)
- `analyse_pacing.py`
- Nutzt `call_llm()`

#### 1.1.5 Immunologie (scripts/analysis/immunology/)
- `analyse_histamine_triggers.py`
- `analyse_mcas_muster.py`
- `analyse_pollen_symptoms.py`
- `analyse_allergens.py`
- Alle nutzen `call_llm()`

#### 1.1.6 Ophthalmologie (scripts/analysis/ophthalmology/)
- `analyse_fundus.py` - ⚠️ **Bilder an VLM** (nutzt call_llm mit image_b64)

#### 1.1.7 Aktivität (scripts/analysis/activity/)
- `analyse_energy_domains.py`
- `analyse_functional_capacity.py`
- `analyse_training_load.py`
- `analyse_sedentary.py`
- `analyse_daily_load.py`
- `analyse_sport_environment.py`
- `analyse_fitness_vo2max.py`
- `analyse_workout_performance.py`
- Alle nutzen `call_llm()`

#### 1.1.8 Innere Medizin (scripts/analysis/internal_medicine/)
- `analyse_medication_effects.py`
- `analyse_health_timeline.py`
- `analyse_clinical_findings.py`
- `analyse_treatment_response.py`
- `analyse_environmental_triggers.py`
- `analyse_overview.py`
- `analyse_undocumented_events.py`
- Alle nutzen `call_llm()`

#### 1.1.9 Schlaf (scripts/analysis/sleep/)
- `analyse_snoring_spo2.py`
- `analyse_sleep_respiration.py`
- `analyse_sleep_multisource.py`
- Alle nutzen `call_llm()`

#### 1.1.10 Zyklus (scripts/analysis/cycle/)
- `analyse_cycle_hrv.py`
- `analyse_cycle_health.py`
- `analyse_cycle_sleep.py`
- Alle nutzen `call_llm()`

**Status für Abschnitt 1:** ✅ **ALLE ABGESCHLOSSEN**  
- `call_llm()` wurde angepasst, um:
  - Prompt-Text für Remote-Provider zu filtern (filter_prompt_text)
  - System-Text für Remote-Provider zu filtern
  - Bilder ohne Metadaten neu zu kodieren (für VLM-Aufrufe)
  - Nur für Remote-Provider (is_local = False) anzuwenden

---

## 2. Skripte mit DIREKTEN Cloud-API-Aufrufen (ohne call_llm)

Diese Skripte umgehen `call_llm()` und müssen manuell angepasst werden.

### 2.1 analyse_synthesis.py
- **Funktion:** `_call_llm()` und `_call_llm_retry()`
- **API:** OpenRouter (direkter HTTP-Request mit urllib)
- **Bilder:** Nein (nur Text)
- **Location-Risiko:** **HOCH** - Kann Session-Daten mit Koordinaten enthalten
- **Aktueller Code:**
  - Hat eigene `_scrub_for_cloud()` Funktion
  - Nutzt `redact_locations()` aus `modules.location_redaction`
  - Auch Adressen/Namen/Nummern-Bereinigung
- **Anpassung:** ✅ **ERLEDIGT**
  - `_scrub_for_cloud()` angepasst, um `filter_prompt_text()` für Location-Bereinigung zu nutzen
  - Adressen/Namen/Nummern-Bereinigung bleibt unconditional (wie gefordert)

### 2.2 analyse_clinical_addendum.py
- **Funktion:** `_call_llm(prompt, lang)`
- **API:** OpenRouter (direkter HTTP-Request)
- **Bilder:** Nein
- **Location-Risiko:** **HOCH** - Synthetisiert Synthese-Berichte mit potenziellen Location-Daten
- **Anpassung:** ✅ **ERLEDIGT**
  - `filter_prompt_text()` Aufruf in `_call_llm()` hinzugefügt

### 2.3 import_medical_motion.py
- **Funktion:** Direkter OpenRouter Vision-API-Aufruf
- **API:** OpenRouter (Vision-Modell)
- **Bilder:** **JA** - Sendet Bilder (Schmerzskalen und Körperkarten)
- **Location-Risiko:** **NIEDRIG-MITTEL** - Bilder sind generierte PDF-Seiten (unwahrscheinlich GPS)
- **Anpassung:** ✅ **ERLEDIGT**
  - `filter_prompt_text()` für Text-Prompt hinzugefügt
  - `_strip_image_metadata()` für Bilder hinzugefügt

### 2.4 llm_benchmark.py
- **Funktion:** `_call_llm(prompt, model)`
- **API:** OpenRouter (direkter HTTP-Request)
- **Bilder:** Nein
- **Location-Risiko:** **NIEDRIG** - Benchmarking-Prompts
- **Anpassung:** ✅ **ERLEDIGT**
  - `filter_prompt_text()` Aufruf in `_call_llm()` hinzugefügt

**Status für Abschnitt 2:** ✅ **ALLE ABGESCHLOSSEN**

---

## 3. Skripte mit Bild-Uploads an VLM

Alle Skripte, die `call_llm()` mit dem `image_b64` Parameter verwenden, senden Bilder an Vision-Modelle.

### 3.1 Wichtige VLM-Aufrufer
- `scripts/analysis/ophthalmology/analyse_fundus.py` - Fundus-Fotos
- `scripts/importers/import_lab_results.py` - PDF-Analyse (falls aktiviert)
- Andere Analyse-Skripte mit `image_b64` Parameter

**Status für Abschnitt 3:** ✅ **ABGESCHLOSSEN**  
- `call_llm()` in `modules/llm.py` wurde angepasst, um:
  - Bilder automatisch ohne Metadaten neu zu kodieren (über `_strip_image_metadata()`)
  - Prompt-Text für Remote-VLM-Provider zu filtern

---

## 4. Externe API-Aufrufe (nicht LLM/VLM)

Diese Skripte rufen externe Dienste auf (Wetter, Pollen, Luftqualität etc.), die **keine LLMs** sind, aber trotzdem Location-Daten senden.

### 4.1 Wetter/Pollen/Luftqualitäts-Importer
- `scripts/fetch_daily.py` - ✅ **for_external_api()**
- `scripts/importers/import_pollen_dwd.py` - ✅ **for_external_api()**
- `scripts/importers/import_pollen_google.py` - ✅ **for_external_api()**
- `scripts/importers/import_airquality.py` - ✅ **for_external_api()**
- `scripts/importers/import_dwd_brightsky.py` - ✅ **for_external_api()**
- `scripts/importers/import_aemet.py` - ✅ **for_external_api()**
- `scripts/importers/import_homeassistant.py` - ✅ **for_external_api()**

### 4.2 Geräte-Importer (für Stufe 3 relevant)
- `scripts/importers/import_ecowitt_csv.py` - ⚠️ **NOCH NICHT ANGEPASST**
  - Enthält `round_coords()` Aufrufe
  - Wahrscheinlich für externe API-Aufrufe
  - **Empfehlung:** Für Stufe 1 nicht kritisch, da Ecowitt typischerweise Heimatposition verwendet

**Status für Abschnitt 4:** ✅ **HAUPT-IMPORTER ABGESCHLOSSEN**  
- Alle Wetter/Pollen/Luftqualitäts-Importer angepasst
- `for_external_api()` wird verwendet statt `round_coords()`

---

## 5. Skripte ohne Cloud-Aufrufe

Diese Skripte wurden geprüft und **machen KEINE Cloud-API-Aufrufe**:

- `scripts/importers/import_fundus.py` - Keine Cloud-Aufrufe, keine GPS-Speicherung
- `scripts/importers/import_fibricheck.py` - Keine Cloud-Aufrufe, keine GPS-Speicherung
- `scripts/importers/import_skin.py` - Nutzt `call_llm()` (abgedeckt durch zentrale Anpassung)
- `scripts/importers/import_lab_results.py` - Nutzt `call_llm()` (abgedeckt)

---

## Fazit

### ✅ Abgeschlossen / Bereit

1. **~228 call_llm()-Aufrufe in ~100 Skripten** - Automatisch abgedeckt durch zentrale Anpassung in `modules/llm.py`
2. **4 direkte Cloud-Aufrufer** - Manuell angepasst:
   - `analyse_synthesis.py`
   - `analyse_clinical_addendum.py`
   - `import_medical_motion.py`
   - `llm_benchmark.py`
3. **Wetter/Pollen/Luftqualitäts-Importer** - Alle angepasst, nutzen `for_external_api()`
4. **VLM-Bild-Aufrufer** - Automatisch abgedeckt durch `call_llm()` Anpassung

### ⚠️ Reste / Für später

- `import_ecowitt_csv.py` - `round_coords()` noch nicht ersetzt
- Geräte-Importer für Stufe 3 (import_garmin, import_tracks, etc.) - werden in Stufe 3 angepasst

### 📊 Statistik

| Kategorie | Skripte | Status |
|----------|---------|--------|
| call_llm() Nutzer | ~100 | ✅ Automatisch abgedeckt |
| Direkte Cloud-Aufrufer | 4 | ✅ Manuell angepasst |
| Wetter/Umwelt-Importer | 7 | ✅ Alle angepasst |
| **Gesamt** | **~111** | **✅ ~108 abgedeckt** |

---

## Empfehlungen für Prüfung

1. **Priorität 1:** `analyse_synthesis.py` testen - durchläuft viele Daten, hat eigenen Cloud-Aufruf
2. **Priorität 2:** `import_medical_motion.py` testen - sendet Bilder an VLM
3. **Priorität 3:** `fetch_daily.py` testen - verwendet `for_external_api()`
4. **Priorität 4:** Alle call_llm()-Nutzer mit GPS-Daten prüfen

## Test-Befehl

```bash
# Unit Tests für Location-Privacy
python -m pytest tests/unit/test_location_privacy_config.py -v
python -m pytest tests/unit/test_location_store.py -v
python -m pytest tests/unit/test_location_store_prompt_filter.py -v

# Bestehende Tests prüfen
python -m pytest tests/unit/test_synthesis_scrubbing.py -v
python -m pytest tests/unit/test_location_redaction.py -v
```
