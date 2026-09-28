#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_master_schema.py — Praxisweite Verwaltungsdatenbank erstellen/aktualisieren

@tier        infrastructure
@purpose.de  Erstellt oder migriert ~/.config/kyoro-master/master.db.
             Diese Datenbank hält betreiberweite Verwaltungsdaten (welche
             Patient:innen-Instanzen existieren, gemeinsam genutzte
             Praxisgeräte) — im Gegensatz zu identity.db, das pro Instanz
             existiert und Pseudonym-Zuordnungen für genau eine Person hält.
@purpose.en  Creates or migrates ~/.config/kyoro-master/master.db.
             This database holds practice-wide administrative data (which
             patient instances exist, shared practice devices) — unlike
             identity.db, which exists per instance and holds pseudonym
             mappings for exactly one person.
@method.de   Tabellen: patient_number_map (Patientenregistratur),
             practice_devices (Geräte-Katalog).
@method.en   Tables: patient_number_map (patient registry),
             practice_devices (device catalog).
@reads       ~/.config/kyoro-master/master.db
@writes      ~/.config/kyoro-master/master.db
@limits.de   Einmalig aufrufen. Wiederholte Ausführung ist idempotent.
             Liegt IMMER im echten Betreiber-Home, folgt NIE
             KYORO_ACTIVE_PATIENT_DIR — sonst würde die Patientenliste
             selbst in einer Patienten-Instanz verschwinden.

@relevance.de  Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur
@relevance.en  Enables creation of database schemas, essential for data organization and structure
@limits.en   Call once. Repeated execution is idempotent. ALWAYS lives in
             the real operator home, NEVER follows KYORO_ACTIVE_PATIENT_DIR
             — otherwise the patient list itself would disappear inside a
             patient instance.
@usage
    python -m utils.create_master_schema
    python3 scripts/utils/create_master_schema.py  # from repo root
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from health_config import KYORO_MASTER_DIR

_MASTER_DB = KYORO_MASTER_DIR / "master.db"

_DDL = """
CREATE TABLE IF NOT EXISTS patient_number_map (
    patient_pseudo TEXT PRIMARY KEY,
    patient_number TEXT NOT NULL,
    practice_id    TEXT,
    instance_dir   TEXT NOT NULL,
    active         INTEGER DEFAULT 1,
    created_at     TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pnm_number
    ON patient_number_map(patient_number, practice_id);

CREATE TABLE IF NOT EXISTS practice_devices (
    device_id_hint TEXT PRIMARY KEY,
    brand          TEXT NOT NULL,
    model          TEXT NOT NULL,
    serial         TEXT NOT NULL,
    sensor_type    TEXT NOT NULL,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS research_consent (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_pseudo  TEXT NOT NULL,
    consent_scope   TEXT NOT NULL,
    consent_given_at TEXT NOT NULL,
    revoked_at      TEXT,
    notes           TEXT,
    FOREIGN KEY (patient_pseudo) REFERENCES patient_number_map(patient_pseudo)
);
CREATE INDEX IF NOT EXISTS idx_research_consent_lookup
    ON research_consent(patient_pseudo, consent_scope);
"""


def create_or_upgrade(db_path: pathlib.Path = _MASTER_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    for stmt in _DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            con.execute(stmt)
    con.commit()
    con.close()
    db_path.chmod(0o600)


if __name__ == "__main__":
    create_or_upgrade()
