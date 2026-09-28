<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Backup

> **English version:** [BACKUP.md](BACKUP.md)

**Kein Backup, keine Gnade!** Kyoro-HealthHub ist absichtlich local-first —
das heißt aber auch: es gibt keine Cloud, die im Hintergrund für dich
sichert. Wenn die Festplatte stirbt oder ein Verzeichnis versehentlich
gelöscht wird, ist alles weg, was du nicht selbst gesichert hast. Das
betrifft nicht nur die Datenbanken, sondern auch den Schlüssel, ohne den
sie nicht mehr lesbar sind.

---

## Was gesichert werden muss

### Kritisch — ohne diese Teile sind die Daten unwiederbringlich verloren

| Pfad | Inhalt | Warum kritisch |
|---|---|---|
| `data/` | `health.db`, `medicine.db`, `medicine_imaging.db` + zugehörige Bilddateien (`data/skin/`, `data/fundus/`) | Die eigentlichen Gesundheitsdaten. Kein Ersatz möglich, wenn weg. |
| `~/.config/kyoro/health_config.json` | Persönliche Konfiguration, ggf. API-Tokens, ggf. der DB-Schlüssel (Fallback-Methode) | Ohne Konfiguration lässt sich das System nicht neu aufsetzen, ohne alles händisch zu rekonstruieren |
| **Der DB-Schlüssel** — Speicherort **hängt von deinem Setup ab** (s. [SETUP_DE.md](SETUP_DE.md#datenbankschlüssel-und-sicherheit)):<br>• Umgebungsvariable `KYORO_DB_KEY`<br>• System-Keyring<br>• `~/.config/kyoro/db.key`<br>• `health_config.json["db_key"]` | Der SQLCipher-Schlüssel | **Der wichtigste Punkt hier.** Wenn SQLCipher aktiv ist: eine perfekt gesicherte, aber schlüssellose Datenbank ist nutzloser Geheimtext. Prüfe, welche der vier Methoden du nutzt, und sichere genau diesen Ort. |

### Wichtig — schwer bis unmöglich vollständig zu rekonstruieren

| Pfad | Inhalt | Hinweis |
|---|---|---|
| `imports/` | Rohe Geräte-Exporte (Polar, Apple Health, Laborbefund-PDFs, manuelle CSVs, …) | Manche Quellen sind erneut herunterladbar (z. B. aktuelle Cloud-APIs), andere nicht mehr (abgelaufene Zugänge, gewechselte Geräte, alte Exporte, die es beim Anbieter nicht mehr gibt) |
| `intern/` (falls genutzt) | Private Notizen, Testprotokolle, Arztbrief-Entwürfe | Nirgendwo sonst vorhanden — reiner Verlust ohne Backup |

### Nice-to-have — regenerierbar, aber Aufwand spart Zeit

| Pfad | Inhalt | Hinweis |
|---|---|---|
| `analyses/` | Generierte Reports, Plots, LLM-Kommentare | Lässt sich über `compute_all.py` + `analyse_*.py` neu erzeugen, aber LLM-Kommentare kosten erneut API-Zeit/-Geld |
| `exports/` | Generierte Arzt-Export-Bundles | Lässt sich jederzeit neu über `export_health.py` erzeugen |

---

## Backup-Strategie

- **Häufigkeit:** nach jedem größeren Import-Lauf, mindestens aber wöchentlich — je öfter neue Gesundheitsdaten reinkommen, desto öfter sichern.
- **3-2-1-Regel:** mindestens 3 Kopien, auf mindestens 2 verschiedenen Medientypen (z. B. externe Platte + Cloud-Speicher), davon 1 Kopie räumlich getrennt (nicht im selben Haushalt/Gebäude).
- **Backup-Ziel selbst verschlüsseln.** Die Datenbanken sind mit SQLCipher verschlüsselt, aber Konfigurationsdatei und Schlüsseldatei sind es nicht zwangsläufig — nutze ein verschlüsseltes externes Laufwerk oder einen Cloud-Anbieter mit Verschlüsselung, nicht einen offenen USB-Stick.
- **Schlüssel getrennt vom Datenbank-Backup aufbewahren.** Wenn beides am selben Ort liegt (z. B. derselbe externe Datenträger) und dieser verloren geht, ist der Vorteil der Trennung von Schlüssel und Daten dahin. Eine zweite, unabhängige Kopie des Schlüssels an einem anderen Ort (z. B. Passwort-Manager) ist sinnvoll.

### Recovery regelmäßig testen

Ein Backup, das nie zurückgespielt wurde, ist nur eine Vermutung. Mindestens
einmal pro Quartal:

1. Backup an einen temporären Ort kopieren (nicht das Original überschreiben)
2. Schlüssel aus dem separaten Backup einspielen
3. Verbindung testen: `python3 scripts/health_config.py --test-db`
4. Bei Erfolg: `DB-Verbindung OK (N Tabellen/Views)` — die Meldung ist immer
   deutsch, unabhängig von `--lang`; erst dann gilt das Backup als verifiziert

---

## Verwandt

- [Datenbankschlüssel und Sicherheit](SETUP_DE.md#datenbankschlüssel-und-sicherheit)
