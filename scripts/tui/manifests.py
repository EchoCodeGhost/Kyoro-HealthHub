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
@limits.de   Die Einträge für manuelle Importer und Werkzeuge fehlen noch. --person bleibt
             offen, bis die Frage zum Personenfeld geklärt ist.
@limits.en   Entries for manual importers and utilities are still missing. --person stays
             open until the question about the person field is settled.

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
    label: tuple[str, str] | None = None

    @property
    def display_label(self) -> str:
        return t(*self.label) if self.label else (self.flag or "")

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
class FloatField(Field):
    def to_args(self, value: Any) -> list[str]:
        return super().to_args(float(value))


@dataclass(frozen=True)
class DateField(Field):
    pass


@dataclass(frozen=True)
class ListField(Field):
    """Wiederholbares Flag; der Wert ist eine Liste."""

    def to_args(self, value: Any) -> list[str]:
        return [arg for item in value for arg in (self.flag, str(item))]


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
            if value is None or value == "" or value == []:
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


_FROM = ("Ab Datum", "From date")
_TO = ("Bis Datum", "To date")
_PLOT = ("Plots erzeugen", "Generate plots")
_NO_LLM = ("Ohne KI-Kommentar", "Without AI comment")
_DRY_RUN = ("Nur Vorschau, nichts schreiben", "Preview only, write nothing")
_SYNTHESIS_REPORT = ("Synthese-Bericht (Standard: neuester)", "Synthesis report (default: latest)")
_DRY_RUN_ONLY = frozenset({"--dry-run"})

COMPUTE_ON_DEMAND = "compute_on_demand"
ANALYSE_ON_DEMAND = "analyse_on_demand"

# Skripte hinter compute_all.py --on-demand und analyse_all.py --on-demand.
# Vorschau-Flags stehen in den Orchestratoren, damit dort das Logging entschieden wird.
ON_DEMAND_ENTRIES: tuple[ScriptEntry, ...] = (
    ScriptEntry(
        "compute/compute_body_composition_from_measurements.py",
        ("Körperzusammensetzung aus Messwerten", "Body composition from measurements"),
        COMPUTE_ON_DEMAND,
    ),
    ScriptEntry(
        "compute/compute_calibrate_sources.py",
        ("Datenquellen kalibrieren", "Calibrate data sources"),
        COMPUTE_ON_DEMAND,
        fields=(
            BoolField("--dry-run", label=_DRY_RUN),
            TextField("--metric", label=("Nur diese Metrik", "Only this metric")),
            BoolField("--windowed", label=("Minutenfenster statt Tageswerte", "Minute windows instead of daily values")),
            TextField("--source-a", label=("Erste Quelle", "First source")),
            TextField("--source-b", label=("Zweite Quelle", "Second source")),
            TextField("--device-a", label=("Erstes Gerät", "First device")),
            TextField("--device-b", label=("Zweites Gerät", "Second device")),
            IntField("--window-minutes", label=("Fenstergröße in Minuten", "Window size in minutes")),
            DateField("--date-from", label=_FROM),
            DateField("--date-to", label=_TO),
        ),
        no_write_flags=_DRY_RUN_ONLY,
    ),
    ScriptEntry(
        "compute/compute_histamine_triggers.py",
        ("Histamin-Auslöser ableiten", "Derive histamine triggers"),
        COMPUTE_ON_DEMAND,
        fields=(
            BoolField("--medium", label=("Auch mittlere Lebensmittel werten", "Also count medium foods")),
            FloatField("--hours", label=("Reaktionsfenster in Stunden", "Reaction window in hours")),
            BoolField("--rebuild", label=("Berechnete Auslöser neu aufbauen", "Rebuild computed triggers")),
            BoolField("--dry-run", label=_DRY_RUN),
        ),
        no_write_flags=_DRY_RUN_ONLY,
    ),
    ScriptEntry(
        "compute/compute_orthostatic_detection.py",
        ("Orthostase-Erkennung", "Orthostatic detection"),
        COMPUTE_ON_DEMAND,
        fields=(DateField("--date-from", label=_FROM), DateField("--date-to", label=_TO)),
    ),
    ScriptEntry(
        "compute/compute_orthostatic_detection_nightly.py",
        ("Orthostase-Erkennung, nächtlich", "Orthostatic detection, nightly"),
        COMPUTE_ON_DEMAND,
        fields=(DateField("--date-from", label=_FROM), DateField("--date-to", label=_TO)),
    ),
    ScriptEntry(
        "analysis/manual/analyse_clinical_addendum.py",
        ("Klinisches Addendum zum Konsil", "Clinical addendum to the synthesis"),
        ANALYSE_ON_DEMAND,
        fields=(
            PathField("--synthesis", label=_SYNTHESIS_REPORT),
            BoolField("--dry-run", label=("Nur Umfang zählen, kein KI-Aufruf", "Count size only, no AI call")),
        ),
        uses_llm=True,
        no_write_flags=_DRY_RUN_ONLY,
    ),
    ScriptEntry(
        "analysis/manual/analyse_ecg_session.py",
        ("Einzelne EKG-Sitzung", "Single ECG session"),
        ANALYSE_ON_DEMAND,
        fields=(
            BoolField("--list", label=("Sitzungen auflisten", "List sessions")),
            TextField("--session", label=("Zeitstempel der Sitzung", "Session timestamp")),
            DateField("--date", label=("Alle Sitzungen dieses Tages", "All sessions on this date")),
            BoolField("--plot", label=_PLOT),
            ChoiceField(
                "--context",
                label=("RR-Filterkontext", "RR filter context"),
                choices=("auto", "wake", "sleep", "training", "postexercise", "orthostatic",
                         "icu", "anesthesia", "sepsis", "pediatric"),
            ),
        ),
        no_write_flags=frozenset({"--list"}),
    ),
    ScriptEntry(
        "analysis/manual/analyse_lab_anomalies.py",
        ("Chronische Labor-Auffälligkeiten", "Chronic lab anomalies"),
        ANALYSE_ON_DEMAND,
        fields=(
            DateField("--from", label=_FROM),
            FloatField("--threshold", label=("Anteil außerhalb der Referenz", "Fraction outside the reference")),
            IntField("--min-measurements", label=("Mindestanzahl Messungen", "Minimum number of measurements")),
        ),
    ),
    ScriptEntry(
        "analysis/manual/analyse_lab_verlauf.py",
        ("Laborwerte im Verlauf", "Lab values over time"),
        ANALYSE_ON_DEMAND,
        fields=(
            DateField("--from", label=_FROM),
            DateField("--to", label=_TO),
            TextField("--kategorie", label=("Nur diese Kategorie", "Only this category")),
            ListField("--parameter", label=("Nur diese Parameter", "Only these parameters")),
            BoolField("--plot", label=_PLOT),
            BoolField("--no-llm", label=_NO_LLM),
            ListField("--exclude-source", label=("Quellen ausschließen", "Exclude sources")),
        ),
        uses_llm=True,
    ),
    ScriptEntry(
        "analysis/manual/analyse_reha_klinik_empfehlung.py",
        ("Empfehlung für Reha-Kliniken", "Rehab clinic recommendation"),
        ANALYSE_ON_DEMAND,
        fields=(
            TextField("--backend", label=("KI-Backend", "AI backend")),
            BoolField("--list-backends", label=("Backends auflisten", "List backends")),
            IntField("--top", label=("Anzahl Kliniken", "Number of clinics")),
            PathField("--synthesis", label=_SYNTHESIS_REPORT),
            TextField("--priorities", label=("Eigene Schwerpunkte, kommagetrennt", "Own priorities, comma-separated")),
            TextField("--question", label=("Zusätzliche Frage an die KI", "Additional question for the AI")),
            TextField("--sources", label=("Datenquellen, kommagetrennt", "Data sources, comma-separated")),
            TextField("--kostentraeger", label=("Kostenträger, kommagetrennt", "Payers, comma-separated")),
        ),
        uses_llm=True,
        no_write_flags=frozenset({"--list-backends"}),
    ),
    ScriptEntry(
        "analysis/manual/analyse_saliva_ph.py",
        ("Speichel-pH", "Saliva pH"),
        ANALYSE_ON_DEMAND,
        fields=(DateField("--from", label=_FROM), BoolField("--plot", label=_PLOT), BoolField("--no-llm", label=_NO_LLM)),
        uses_llm=True,
    ),
    ScriptEntry(
        "analysis/manual/analyse_skin.py",
        ("Hautläsionen", "Skin lesions"),
        ANALYSE_ON_DEMAND,
        fields=(
            BoolField("--analyse", label=("Neue Fotos per KI auswerten", "Evaluate new photos with AI")),
            IntField("--lesion", label=("Verlauf dieser Läsion", "Timeline of this lesion")),
            BoolField("--compare", label=("Veränderungen per KI vergleichen", "Compare changes with AI")),
            BoolField("--watch-list", label=("Nur Läsionen mit Handlungsbedarf", "Only lesions needing action")),
        ),
        uses_llm=True,
    ),
    # Interaktiv wegen der Kostenfrage. --yes und --no-scrub sind gesperrt.
    ScriptEntry(
        "analysis/manual/analyse_synthesis.py",
        ("Konsil-Gesamtbefund", "Synthesis report"),
        ANALYSE_ON_DEMAND,
        fields=(
            DateField("--since", label=("Analysen ab Datum", "Analyses since date")),
            IntField("--top", label=("Zeilen vom Berichtsanfang", "Lines from report start")),
            IntField("--bottom", label=("Zeilen vom Berichtsende", "Lines from report end")),
            BoolField("--dry-run", label=("Nur Umfang zählen, kein KI-Aufruf", "Count size only, no AI call")),
            BoolField("--no-panel", label=("Ohne Panel", "Without panel")),
        ),
        mode=ScriptMode.INTERACTIVE,
        uses_llm=True,
        no_write_flags=_DRY_RUN_ONLY,
    ),
    ScriptEntry(
        "analysis/manual/analyse_urine.py",
        ("Urin-Heimmonitoring", "Home urine monitoring"),
        ANALYSE_ON_DEMAND,
        fields=(DateField("--from", label=_FROM), BoolField("--plot", label=_PLOT), BoolField("--no-llm", label=_NO_LLM)),
        uses_llm=True,
    ),
    ScriptEntry(
        "analysis/manual/check_supplement_interactions.py",
        ("Supplement-Wechselwirkungen", "Supplement interactions"),
        ANALYSE_ON_DEMAND,
        fields=(ListField("--supplement", required=True, label=("Erwogene Supplemente", "Supplements under consideration")),),
        uses_llm=True,
    ),
    ScriptEntry(
        "analysis/manual/explain_synthesis.py",
        ("Konsil in Alltagssprache", "Synthesis in plain language"),
        ANALYSE_ON_DEMAND,
        fields=(PathField("--file", label=_SYNTHESIS_REPORT),),
        uses_llm=True,
    ),
)
