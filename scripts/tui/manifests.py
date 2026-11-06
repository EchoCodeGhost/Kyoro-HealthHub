# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Manifest-Typen und Ausschlüsse der Pipeline-TUI.

@tier        infrastructure
@purpose.de  Beschreibt Skripte ohne eigenes Register und legt fest, welche Flags die TUI
             übergeben darf und welche Werkzeuge sie nie anbietet.
@purpose.en  Describes scripts without a registry of their own, and defines which flags
             the TUI may pass and which tools it never offers.
@method.de   Allowlist: build_args() erzeugt Argumente nur aus deklarierten Feldern, und ein
             Eintrag mit gesperrtem Flag lässt sich gar nicht erst anlegen. Pfade in EXCLUDED
             sind relativ zu scripts/; * passt auch über Verzeichnisse hinweg.
@method.en   Allowlist: build_args() creates arguments only from declared fields, and an
             entry with a blocked flag cannot be created at all. Paths in EXCLUDED are
             relative to scripts/; * also matches across directories.
@reads       Keine Tabellen
@writes      Keine Tabellen
@limits.de   Enthält nur Typen und Ausschlüsse. Die Einträge pro Skript folgen getrennt.
@limits.en   Holds types and exclusions only. The entries per script follow separately.

@relevance.de  Verhindert, dass die Oberfläche Schutzmaßnahmen abschwächt
@relevance.en  Prevents the interface from weakening protections
@usage
    entry = ScriptEntry("analysis/manual/analyse_ecg_session.py", ("EKG", "ECG"), "analyse_manual",
                        fields=(IntField("--session", required=True), BoolField("--plot")))
    entry.build_args({"--session": 42, "--plot": True})
    is_excluded("utils/decrypt_db.py")
"""

from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from modules.i18n import t


class ScriptMode(Enum):
    PIPED = "piped"
    INTERACTIVE = "interactive"
    SERVICE = "service"


class PathKind(Enum):
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True)
class Field:
    """Ein Argument. flag=None ist ein positionales Argument."""

    flag: str | None
    required: bool = False

    def to_args(self, value: Any) -> list[str]:
        text = str(value)
        return [text] if self.flag is None else [self.flag, text]


@dataclass(frozen=True)
class BoolField(Field):
    def to_args(self, value: Any) -> list[str]:
        return [self.flag] if value else []


@dataclass(frozen=True)
class TextField(Field):
    pass


@dataclass(frozen=True)
class IntField(Field):
    def to_args(self, value: Any) -> list[str]:
        return super().to_args(int(value))


@dataclass(frozen=True)
class DateField(Field):
    pass


@dataclass(frozen=True)
class ChoiceField(Field):
    choices: tuple[str, ...] = ()

    def to_args(self, value: Any) -> list[str]:
        if value not in self.choices:
            raise ValueError(f"{self.flag}: {value!r} is not one of {self.choices}")
        return super().to_args(value)


@dataclass(frozen=True)
class PathField(Field):
    kind: PathKind = PathKind.FILE


# Schwächen den Schutz, legen Geheimnisse offen oder umgehen Rückfragen der Skripte.
BLOCKED_FLAGS = frozenset({
    "--no-scrub", "--host", "--writable", "--api-key", "--show-mappings",
    "--fix", "--no-backup", "--accept-terms", "--yes", "--no-confirm",
})


@dataclass(frozen=True)
class ScriptEntry:
    script: str
    label: tuple[str, str]
    group: str
    fields: tuple[Field, ...] = ()
    mode: ScriptMode = ScriptMode.PIPED
    uses_llm: bool = False
    confirm: bool = False
    no_write_flags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        blocked = {f.flag for f in self.fields} & BLOCKED_FLAGS
        if blocked:
            raise ValueError(f"{self.script}: blocked flags {sorted(blocked)}")
        declared = {f.flag for f in self.fields if f.flag}
        unknown = self.no_write_flags - declared
        if unknown:
            raise ValueError(f"{self.script}: no_write_flags not declared {sorted(unknown)}")

    @property
    def display_label(self) -> str:
        return t(*self.label)

    def build_args(self, values: dict[str | None, Any]) -> list[str]:
        """Baut die Argumente. Nicht deklarierte Felder und fehlende Pflichtfelder sind Fehler."""
        declared = {f.flag: f for f in self.fields}
        undeclared = [flag for flag in values if flag not in declared]
        if undeclared:
            raise ValueError(f"{self.script}: undeclared flags {undeclared}")
        args: list[str] = []
        for f in self.fields:
            value = values.get(f.flag)
            if value in (None, ""):
                if f.required:
                    raise ValueError(f"{self.script}: {f.flag or 'positional argument'} is required")
                continue
            args += f.to_args(value)
        return args


# Skript oder Muster, relativ zu scripts/ → Grund
EXCLUDED: dict[str, str] = {
    "utils/decrypt_db.py": "writes a decrypted copy of a database",
    "utils/scrub_*.py": "rewrites data or source files in place",
    "utils/migrate_*.py": "one-time data migration",
    "migrations/*": "one-time data migration",
    "utils/pseudonymize_*.py": "rewrites identifiers in the databases",
    "utils/reduce_gps_precision.py": "irreversibly rewrites location data",
    "utils/create_*schema.py": "schema setup and migration",
    "utils/apply_icd_corrections.py": "rewrites clinical codes",
    "utils/promote_anamnese_findings.py": "writes interview findings into clinical data",
    "calibration/*": "research and calibration tooling",
    "medical/*": "specialist tooling outside the pipeline",
    "cluster/*": "cluster infrastructure outside the pipeline",
}


def is_excluded(script: str) -> str | None:
    """Gibt den Ausschlussgrund zurück, oder None, wenn das Skript nicht ausgeschlossen ist."""
    relative = Path(script).as_posix()
    for pattern, reason in EXCLUDED.items():
        if fnmatchcase(relative, pattern):
            return reason
    return None
