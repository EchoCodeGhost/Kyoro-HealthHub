# Funktionale Kapazität — 6-Minuten-Gehtest (6MWT) Verlaufsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_functional_capacity.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Analysiert 6-Minuten-Gehtests (6MWT) als objektives Outcome-Maß: Gehstrecke, HR-Kinetik (Ruhe → Peak → Erholung), SpO2-Abfall, Borg-Anstrengung und PEM-Risiko am Folgetag.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Referenzwert nach Enright & Sherrill 1998 (Regressionsgleichung aus Alter, Körpergröße, Gewicht und einem Konfigurationsmerkmal, das über zwei Koeffizientensätze entscheidet — siehe _predicted_6mwt_m() im Quellcode), personalisiert über health_config.json und den zuletzt bekannten Gewichtswert aus body_composition/measurements. Fehlt eine dieser Angaben, greift der ATS-2002-Pauschalwert (~45 J, 170 cm, ~560 m) als Fallback — der Bericht kennzeichnet immer, welcher Modus verwendet wurde. MCID 30 m nach Polkey et al. 2013 (ursprünglich COPD, Primärquelle), bestätigt im ERS/ATS- Konsens-Review von Singh et al. 2014. Schweregrad-Klassifikation: < 40 % schwer, 40–60 % moderat, 60–80 % leicht, ≥ 80 % normal.

## Datenfluss

- **Liest:** `functional_tests`, `measurements`
- **Schreibt:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Grenzen

Selbst durchgeführter 6MWT ohne standardisierte Testbedingungen (Korridor, Anleitung). Enright & Sherrill 1998 wurde an einer überwiegend gesunden US-Erwachsenenkohorte validiert, nicht an ME/CFS/Long-COVID-Populationen. Gewicht ist der zuletzt bekannte Messwert, nicht zwingend tagesaktuell. Ohne vollständige Konfiguration (Alter/Größe/Gewicht/Profilmerkmal) fällt der Wert auf den generischen ATS-2002-Pauschalwert zurück, der nur für Personen nahe 45 J/170cm verlässlich ist. n=1.

## Referenzen

- American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102
- Enright PL, Sherrill DL (1998). Reference Equations for the Six-Minute Walk in Healthy Adults. American Journal of Respiratory and Critical Care Medicine, 158(5):1384-1387. doi:10.1164/ajrccm.158.5.9710086
- Singh SJ, Puhan MA, Andrianopoulos V, et al. (2014). An official systematic review of the European Respiratory Society/American Thoracic Society: measurement properties of field walking tests in chronic respiratory disease. European Respiratory Journal. doi:10.1183/09031936.00150414

## Aufruf

```bash
python analyse_functional_capacity.py
python analyse_functional_capacity.py --help
python analyse_functional_capacity.py --from 2024-01-01 --to 2024-12-31
```
