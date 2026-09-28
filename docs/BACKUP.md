<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Backup

> **Deutsche Version:** [BACKUP_DE.md](BACKUP_DE.md)

**No backup, no mercy.** Kyoro-HealthHub is deliberately local-first — but
that also means there's no cloud quietly backing things up for you in the
background. If a disk dies or a directory gets deleted by accident,
everything you didn't back up yourself is gone. That applies not just to
the databases, but to the key without which they can no longer be read.

---

## What needs to be backed up

### Critical — without these, the data is unrecoverable

| Path | Contents | Why critical |
|---|---|---|
| `data/` | `health.db`, `medicine.db`, `medicine_imaging.db` + associated image files (`data/skin/`, `data/fundus/`) | The actual health data. No way to replace it if it's gone. |
| `~/.config/kyoro/health_config.json` | Personal configuration, possibly API tokens, possibly the DB key (fallback method) | Without the config, the system can't be set back up without manually reconstructing everything |
| **The DB key** — location **depends on your setup** (see [SETUP.md](SETUP.md#database-key-and-security)):<br>• environment variable `KYORO_DB_KEY`<br>• system keyring<br>• `~/.config/kyoro/db.key`<br>• `health_config.json["db_key"]` | The SQLCipher key | **The most important point here.** If SQLCipher is enabled: a perfectly backed-up but keyless database is just useless ciphertext. Check which of the four methods you're using, and back up exactly that location. |

### Important — hard to fully reconstruct, sometimes impossible

| Path | Contents | Note |
|---|---|---|
| `imports/` | Raw device exports (Polar, Apple Health, lab result PDFs, manual CSVs, ...) | Some sources can be re-downloaded (e.g. current cloud APIs), others can't anymore (expired access, replaced devices, old exports no longer available from the provider) |
| `intern/` (if used) | Private notes, test protocols, draft letters to doctors | Exists nowhere else — pure loss without a backup |

### Nice-to-have — regenerable, but saves time

| Path | Contents | Note |
|---|---|---|
| `analyses/` | Generated reports, plots, LLM commentary | Can be regenerated via `compute_all.py` + `analyse_*.py`, but LLM commentary costs API time/money again |
| `exports/` | Generated doctor-export bundles | Can be regenerated any time via `export_health.py` |

---

## Backup strategy

- **Frequency:** after every major import run, at minimum weekly — the more often new health data comes in, the more often you should back up.
- **3-2-1 rule:** at least 3 copies, on at least 2 different media types (e.g. external drive + cloud storage), with 1 copy stored offsite (not in the same household/building).
- **Encrypt the backup destination itself.** The databases are encrypted with SQLCipher, but the config file and key file aren't necessarily — use an encrypted external drive or a cloud provider with encryption, not an open USB stick.
- **Keep the key separate from the database backup.** If both live in the same place (e.g. the same external drive) and that's lost, the benefit of separating key and data is gone. A second, independent copy of the key somewhere else (e.g. a password manager) is worthwhile.

### Test recovery regularly

A backup that's never been restored is just a guess. At least once a
quarter:

1. Copy the backup to a temporary location (don't overwrite the original)
2. Restore the key from its separate backup
3. Test the connection: `python3 scripts/health_config.py --test-db`
4. On success: `DB-Verbindung OK (N Tabellen/Views)` — the script always
   prints this German message regardless of `--lang`; only then does the
   backup count as verified

---

## Related

- [Database key and security](SETUP.md#database-key-and-security)
