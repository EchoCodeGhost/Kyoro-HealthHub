# Sicherheitsrichtlinie

> **English version:** [SECURITY.md](SECURITY.md)

Kyoro-HealthHub ist eine lokal-first Gesundheitsdaten-Pipeline (s.
[README.md](../README.md)). Es gibt keinen zentralen Server: Die relevante
Angriffsfläche ist hier lokal — entschlüsselte temporäre Dateien, exponierte
lokale Dienste (z. B. der Datasette-Browser), Path-Traversal in
Importern/Exportern, sowie Privacy-/Pseudonymisierungs-Fehler — kein
gehostetes Backend.

## Unterstützte Versionen

Dieses Projekt nutzt keine versionierten Releases (s. die
"Versioning and changelogs"-Konvention in [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md)).
Nur der aktuelle `main`-Branch wird gepflegt — bitte Findings gegen den
neuesten Commit melden.

## Eine Sicherheitslücke melden

Bitte GitHubs privates Vulnerability-Reporting nutzen statt eines
öffentlichen Issues: im Repository auf den **Security**-Tab →
**Report a vulnerability**. Das öffnet ein privates Advisory, das nur für
Maintainer sichtbar ist, bis es behoben ist.

> **Aktuell nicht verfügbar:** Dieses Repository ist privat, und GitHub
> bietet privates Vulnerability-Reporting bei privaten Repos nur mit
> aktiviertem GitHub Advanced Security an (hier nicht der Fall — s. Details
> unten). Der **Report a vulnerability**-Button erscheint im Security-Tab
> erst, sobald das Repository öffentlich ist. Bis dahin bitte den
> Fallback unten nutzen.

**Fallback bis dahin:** ein reguläres Issue mit möglichst wenig technischen
Details öffnen und um einen privaten Kanal für den Rest bitten.

## Umfang

Im Umfang:
- Lokale Datenexposition (weltlesbare temporäre Dateien, an `0.0.0.0` statt
  nur `localhost` gebundene Dienste, entschlüsselte Datenbank-Artefakte, die
  auf der Platte liegen bleiben)
- Umgehung von Pseudonymisierung/Anonymisierung (Geräte-IDs, Personen-IDs
  oder andere Identifier, die nie im Klartext auftauchen sollten, aber doch
  durchsickern)
- SQL-Injection, Path-Traversal oder Command-Injection in Importern,
  Exportern oder Query-Tools
- Geloggte, committete oder anderweitig exponierte Secrets (API-Keys,
  DB-Verschlüsselungsschlüssel)
- Privacy-Regel-Verstöße im *tatsächlichen Verhalten der Pipeline* (im
  Gegensatz zur Inhaltsprüfung von Docstrings/Kommentaren, die bereits
  `check_compliance.py` und `check_source_privacy.py` abdecken — s.
  CONTRIBUTING_DE.md)

Nicht im Umfang:
- Sicherheit von Drittanbieter-Geräte-APIs oder Cloud-Diensten, die dieses
  Projekt einbindet (Polar, Oura, Garmin, etc.) — bitte beim jeweiligen
  Hersteller melden
- Allgemeine Bugs ohne Sicherheits-/Privacy-Bezug — dafür ein reguläres
  Issue nutzen
- Fehlende Features oder Hardening-Vorschläge ohne konkretes ausnutzbares
  Szenario — stattdessen ein reguläres Issue oder eine Diskussion eröffnen

## Was zu erwarten ist

Dies ist ein individuell gepflegtes, nicht-kommerzielles Projekt —
Reaktionszeiten sind Best-Effort, keine SLA. Bestätigte Sicherheitslücken
werden behoben und (sofern gewünscht, sonst anonym) in der Commit-Message
des Fixes anerkannt.

## Bekannte Dependency-Advisories (akzeptiert, nicht umsetzbar)

**`setuptools` — CVE-2026-59890 / GHSA-h35f-9h28-mq5c** (`MANIFEST.in`-
Exclusion-Bypass durch NFC/NFD-Unicode-Normalisierungs-Kollision beim Bauen
eines sdist auf macOS APFS/HFS+): Dieses Repository hat weder `setup.py`
noch `pyproject.toml` noch `MANIFEST.in`. Es wird nie als eigenes sdist
gebaut oder veröffentlicht, daher greift der betroffene Code-Pfad — ein
Maintainer veröffentlicht ein Paket, dessen `MANIFEST.in`-Exclusions
stillschweigend umgangen werden — hier gar nicht. `setuptools` steht in
`requirements-lock.txt` nur als transitive Build-Abhängigkeit für
Drittanbieter-Pakete, die via `pip` installiert werden.

Der Pin lässt sich ohnehin aktuell nicht über die gefixte Version anheben:
er wird bewusst unterhalb der von `neurokit2` selbst gesetzten Obergrenze
gehalten (`setuptools<82.0.0`, aus `neurokit2`s eigenen Paket-Metadaten,
nicht von diesem Projekt), damit `pip install -r requirements-lock.txt`
auflösbar bleibt. Neu bewerten, sobald ein `neurokit2`-Release diese
Obergrenze anhebt.

## Hinweis zur privaten Repository-Phase

GitHubs privates Vulnerability-Reporting braucht bei privaten Repositories
GitHub Advanced Security, was hier nicht aktiviert ist. Es wird ohne
Zusatzkosten verfügbar, sobald dieses Repository öffentlich ist — bis dahin
bitte den regulären Issue-Fallback oben nutzen.
