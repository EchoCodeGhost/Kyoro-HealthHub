# check_climate_context_source_freshness — Erkennt Aktualisierungen der Vektor-/Klimaeignungs-Kartenquellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_climate_context_source_freshness.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prüft, ob sich die offiziellen Kartenquellen geändert haben, auf denen die "KLIMAWANDEL-BEZUG"-Aussagen in den Syndrom-Dateien (scripts/analysis/syndromes/*.json — Zecken-Cluster, Stechmücken- übertragene Erreger, Bayern-Übersichtsseite) inhaltlich beruhen, damit eine veraltete Verbreitungsannahme (z.B. "Ixodes ricinus breitet sich nach Norden aus") nicht unbemerkt stehen bleibt, wenn die zugrunde liegende Kartierung längst weiterentwickelt wurde.

## Relevanz

Ohne diese Prüfung würden die im September 2026 neu ergänzten Klimawandel-Kontexte (Zecken-Cluster, Usutu, aviäre Influenza, Alpha-Gal) mit der Zeit rein auf dem Wissensstand ihrer Entstehung einfrieren, obwohl gerade Vektor-Verbreitungskarten (s. ECDC-Zeckenkarten: 50 neue Verwaltungseinheiten mit Zeckennachweis allein im Update von Juni 2026) sich schnell weiterentwickeln.

## Methode

Lädt für jede bekannte Quelle (ECDC VectorNet Zecken-/Stechmücken- Verbreitungskarten, LGL-Bayern-Übersichtsseite Klimawandel & Infektionskrankheiten) die Rohbytes per HTTP und bildet einen SHA-256-Hash, analog zu check_tigermuecke_source_freshness.py. Vergleicht diesen gegen den zuletzt bestätigten Hash in climate_context_source_baseline.json. Anders als der Tigermücken- oder FSME-Checker gibt es hier KEINE feste Liste betroffener Dateien zum Aktualisieren — stattdessen wird bei einer Änderung auf den Marker-String "KLIMAWANDEL-BEZUG" verwiesen (case- insensitiv "klimawandel" für die älteren, vor dieser Konvention geschriebenen Dateien wie candida_auris.json/zika.json), den jede betroffene Syndrom-Datei im system_prompt trägt: eine feste Dateiliste würde bei jeder neuen Klimaaussage in einer weiteren Syndrom-Datei sofort veralten, ein Grep über den Marker nicht.

## Datenfluss

- **Liest:** `Externe`, `URLs`, `(ECDC`, `VectorNet`, `LGL`, `Bayern);`, `climate_context_source_baseline.json`, `(lokaler`, `Zustand)`
- **Schreibt:** `climate_context_source_baseline.json (nur mit --update)`

## Grenzen

Deckt nur die drei Quellen ab, die eine konkrete, stabil erreichbare Karten-/Übersichtsseite haben (ECDC Zecken-/ Stechmückenkarten, LGL-Übersichtsseite). Reine Literaturzitate ohne trackbare Live-Quelle (z.B. Gray et al. 2009, Medlock et al. 2013, Tersago et al. 2009 für die Hantavirus-Mastjahr-Korrelation, Walker 2018 für Legionellose) werden bewusst NICHT überwacht — es gibt keine URL, deren Änderung etwas über die Gültigkeit eines publizierten Papers aussagen würde. Ein geänderter Hash heisst nur "die Seite hat sich irgendwie verändert", nicht zwingend, dass sich Verbreitungsdaten inhaltlich geändert haben (wie beim Tigermücken-Checker). Ersetzt keine gelegentliche manuelle Literatur-Sichtung der reinen Zitate, verhindert nur, dass die kartenbasierten Aussagen unbemerkt veralten.

## Aufruf

```bash
python3 scripts/utils/check_climate_context_source_freshness.py
python3 scripts/utils/check_climate_context_source_freshness.py --update
```
