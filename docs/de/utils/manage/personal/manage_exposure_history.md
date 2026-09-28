# manage_exposure_history.py — Expositionsanamnese verwalten (Zoonosen, Beruf, Sexualanamnese)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_exposure_history.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Dokumentiert Tierkontakte, berufliche Expositionen, Kindheitsumfeld und Sexualanamnese — wichtig für die Differenzialdiagnose ungeklärter Symptome (Zoonosen wie Q-Fieber, Brucella, Leptospira, Echinococcus, Toxoplasma; STI-Screening-Historie).

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/exposure_history.json (lokal, nicht im Repo). Ein einzelnes verschachteltes Objekt statt einer Liste: {{childhood_environment, animal_contacts[], occupational_exposures[], sexual_history{{multiple_partners, hpv_vaccination, sti_screening[], known_stis[]}}}}. Strg+C bricht jederzeit ohne Datenverlust ab.

## Datenfluss

- **Liest:** `~/.config/kyoro/exposure_history.json`
- **Schreibt:** `~/.config/kyoro/exposure_history.json`

## Grenzen

Keine automatische Risikoberechnung für dauerhafte/regelmäßige Kontakte — reine Dokumentation für Differenzialdiagnostik durch Ärzte. Ausnahme: bei einmaligem Tierkontakt (`exposure == "einmalig"`) gibt es sofort eine leichtgewichtige, heuristische Erreger-Hinweisliste (ANIMAL_SYNDROME_MAP gegen scripts/analysis/syndromes/*.json) direkt nach dem Speichern — kein Ersatz für die vollständige, geo-/zeitbasierte analyse_pathogen_exposure.py, sondern ein sofortiger erster Hinweis für akute Einzelereignisse (z. B. Tierunfall), die sonst bis zum nächsten manuellen Analyse-Lauf unbeachtet blieben.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_exposure_history.py show
python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
python3 scripts/utils/manage/personal/manage_exposure_history.py animal delete 2
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation delete 1
python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
python3 scripts/utils/manage/personal/manage_exposure_history.py sti delete 1
```
