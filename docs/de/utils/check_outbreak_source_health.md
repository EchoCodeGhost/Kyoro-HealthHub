# check_outbreak_source_health — Proaktive Erreichbarkeitspruefung aller Ausbruchsdatenquellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_outbreak_source_health.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Prueft bei jedem Lauf ALLE in import_outbreak_data.py registrierten Quellen (_FETCHERS) auf echte Erreichbarkeit -- auch die aktuell als "DEAD" auskommentierten (who_searo, crm, healthmap, ...), damit eine stille Reparatur auf Anbieterseite (wie bei who_paho, das faelschlich als tot markiert war) automatisch auffaellt statt per Zufall entdeckt zu werden. Meldet nur ZUSTANDSAENDERUNGEN (neu kaputt / neu wiederhergestellt) gegen die letzte Baseline, nicht den vollen Status jedes Laufs -- so bleibt die Ausgabe auch bei 20+ Quellen uebersichtlich.

## Relevanz

Ohne dieses Skript werden tote/blockierte Quellen (WHO SEARO/EURO/WPRO, HealthMap, CRM, ProMED) weiterhin nur per Zufall entdeckt -- genau das Muster, das zur Entdeckung von who_paho (faelschlich als tot markiert) und der echten WAHIS- Blockade-Ursache (Cloudflare, nicht Auth-Token, s. _WAHISDB_API-Kommentar in import_outbreak_data.py fuer die daraufhin gewaehlte Alternativquelle) fuehrte, aber eben zufaellig und nicht systematisch.

## Methode

Ruft jede Fetch-Funktion aus _FETCHERS unveraendert gegen eine eigene In-Memory-SQLite-Datenbank (utils/create_schema.py::SCHEMA) auf -- derselbe Code, dieselben Netzwerkaufrufe wie beim echten Import, aber ohne health.db zu beruehren. Alle Quellen werden ueber einen ProcessPoolExecutor PARALLEL geprueft (bis zu 12 gleichzeitig): sequenziell haette ein Lauf ueber ~20 Quellen, von denen mehrere erst nach ihrem vollen Netzwerk-Timeout (bis zu 30s bei toten Quellen wie CRM/WHO EURO) als kaputt erkannt werden, mehrere Minuten gedauert (in der Praxis beobachtet) -- parallel dominiert nur die langsamste einzelne Quelle die Gesamtlaufzeit. Jede Fetch-Funktion faengt eigene Netzwerkfehler bereits ab; viele probieren dabei mehrere Kandidaten-URLs durch und loggen fuer JEDEN fehlgeschlagenen Kandidaten eine generische "Fetch-Fehler ..."-Zeile, BEVOR ein spaeterer Kandidat evtl. doch noch erfolgreich ist (z.B. who_paho, cdc_travel, crm, alle WHO-Regionalbueros). Dieses Skript faengt stdout waehrend des Aufrufs ab, klassifiziert aber NICHT anhand jeder Fehler-Zeile (das gab live einen Fehlalarm bei who_paho, das eigentlich per zweitem Kandidaten funktioniert), sondern anhand des einzigen textuellen Markers, den JEDE Fetch-Funktion ausschliesslich als DEFINITIVEN Abschluss-Hinweis verwendet, nachdem wirklich alle Kandidaten erschoepft sind: "erreichbar"/"reachable" (z.B. "kein RSS erreichbar", "nicht erreichbar") -- s. _BROKEN_MARKERS- Kommentar fuer die per Grep verifizierte Herleitung. Dazu xml-fehler/json-fehler/db-fehler, die erst NACH erfolgreicher Kandidaten-Auswahl auftreten koennen und daher immer echtes Scheitern bedeuten. RATE_LIMITED (z.B. GDELT-429/"Please limit requests") wird als nicht aussagekraeftig behandelt und aendert die Baseline nicht; jeder unerwarteten Exception (inkl. dem eigenen SIGALRM-Timeout, s. check_source()) gilt ebenfalls als BROKEN. Persistiert IMMER (kein --update-Gate wie bei den themenspezifischen Freshness-Checkern) -- Erreichbarkeit ist ein objektiver Fakt, keine Interpretation, die menschliche Bestaetigung braucht.

## Datenfluss

- **Liest:** `Externe`, `URLs`, `aller`, `registrierten`, `Quellen;`, `outbreak_source_health_baseline.json`, `(lokaler`, `Zustand)`
- **Schreibt:** `outbreak_source_health_baseline.json (bei jedem Lauf, nicht nur mit --update)`

## Grenzen

Erkennt nur Erreichbarkeits-/Parsing-Bruch (Exception oder fehlermeldende Textmarker), keine inhaltliche Korrektheit -- eine Quelle, die 200 OK mit leerem/falschem Inhalt liefert, ohne dass die Fetch-Funktion das selbst erkennt, wird als OK gemeldet. Die RATE_LIMITED-Erkennung basiert auf einer festen Marker-Liste ("429", "too many requests", "please limit requests", "rate limit"); ein Anbieter mit abweichendem Wortlaut wuerde faelschlich als BROKEN gezaehlt. RKI SurvStat wird ueber _HEALTH_CHECK_KWARGS bewusst nur national statt fuer alle 16 Bundeslaender abgefragt (s. Kommentar dort) -- ein rein landesspezifischer Ausfall der SOAP-API wuerde dieser Check daher nicht erkennen, nur ein genereller. fetch_rki_survstat() gibt bei einem Netzwerkfehler auf SOAP-Ebene KEINEN "erreichbar"-Marker aus (nur bei einem inhaltlichen SOAP-Fault, s. _rki_soap_call()) -- eine echte Netzwerkstoerung wuerde daher nur ueber eine Exception (z.B. den SIGALRM-Timeout) erkannt, mit einer stillen Rueckgabe von 0 aber leicht uebersehen werden.

## Aufruf

```bash
python3 scripts/utils/check_outbreak_source_health.py
python3 scripts/utils/check_outbreak_source_health.py --quiet   # nur bei Aenderungen Ausgabe
```
