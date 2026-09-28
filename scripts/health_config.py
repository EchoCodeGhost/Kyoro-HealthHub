#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
health_config.py — Zentrale Konfiguration für alle Health-Skripte

@tier        infrastructure
@purpose.de  Verwaltet die zentrale Konfiguration für alle Health-Skripte
@purpose.en  Manages central configuration for all health scripts
@method.de   Lädt die Nutzerkonfiguration aus ~/.config/kyoro/health_config.json.
             Alle Skripte importieren dieses Modul statt Werte hart zu kodieren.
             Unterstützt Erst Einrichtung und Anzeige der Konfiguration.
             Beim Import: verdrahtet automatisch eine Chain-of-Custody-Sicherung
             für das gesamte KYORO_CONFIG_DIR (git-committet jede Änderung,
             vor UND nach diesem Skriptlauf, s. modules/config_backup.py) —
             ohne dass ein aufrufendes Skript davon wissen muss.
@method.en   Loads user configuration from ~/.config/kyoro/health_config.json.
             All scripts import this module instead of hardcoding values.
             Supports initial setup and configuration display.
             On import: automatically wires up chain-of-custody tracking
             for the whole KYORO_CONFIG_DIR (git-commits any change, both
             before and after this script's run, see
             modules/config_backup.py) — no calling script needs to know.
@reads       ~/.config/kyoro/health_config.json, ~/.config/kyoro/identity.db
@writes      ~/.config/kyoro/health_config.json (bei --setup); .git-Repo +
             Commits im KYORO_CONFIG_DIR (automatisch, s.o.)
@limits.de   Konfiguration ist nutzerspezifisch. Keine Validierung der Werte.
             Die automatische Chain-of-Custody-Sicherung ist unter pytest
             deaktiviert (s. modules/config_backup.py-Docstring).

@relevance.de  Ermöglicht die Konfigurationsverwaltung, essentiell für die Systemeinstellungen
@relevance.en  Enables configuration management, essential for system settings
@limits.en   Configuration is user-specific. No validation of values.
             The automatic chain-of-custody tracking is disabled under
             pytest (see modules/config_backup.py's docstring).
@usage
    python3 health_config.py --setup    # Erstmalig einrichten
    python3 health_config.py --show     # Konfiguration anzeigen
"""

import json
import os as _os
import sys
from functools import lru_cache
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from modules.i18n import t

_ACTIVE_PATIENT_DIR = _os.environ.get("KYORO_ACTIVE_PATIENT_DIR")
_BASE_HOME = Path(_ACTIVE_PATIENT_DIR) if _ACTIVE_PATIENT_DIR else Path.home()
KYORO_CONFIG_DIR = _BASE_HOME / ".config" / "kyoro"
KYORO_MASTER_DIR = Path.home() / ".config" / "kyoro-master"
CONFIG_PATH      = KYORO_CONFIG_DIR / "health_config.json"
_IDENTITY_DB     = KYORO_CONFIG_DIR / "identity.db"
_KEY_FILE        = KYORO_CONFIG_DIR / "db.key"


def _load_own_person_id() -> str:
    """Load the pseudonym for the main user ('self') using identity_resolver.

    No local fallback hash here on purpose: identity_resolver salts its
    hashes with a locally-generated secret (see its docstring) so that
    low-cardinality inputs like 'self'/'partner' can't be dictionary-attacked
    by anyone with only the pseudonym. A fallback that recomputed an unsalted
    hash would (a) reintroduce that exact vulnerability and (b) silently
    diverge from the real resolver's output, splitting 'self's data across
    two different person pseudonyms without anyone noticing. Fail loudly
    instead.
    """
    import sys
    from pathlib import Path
    scripts_dir = Path(__file__).parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from modules.identity_resolver import resolve_person
    return resolve_person("self")


_OWN_PERSON_ID_CACHE: "str | None" = None


def get_own_person_id() -> str:
    global _OWN_PERSON_ID_CACHE
    if _OWN_PERSON_ID_CACHE is None:
        _OWN_PERSON_ID_CACHE = _load_own_person_id()
    return _OWN_PERSON_ID_CACHE


def __getattr__(name: str):
    if name == "OWN_PERSON_ID":
        return get_own_person_id()
    raise AttributeError(name)


def _apply_config_language() -> None:
    """Read 'language' from config and apply via i18n.set_lang() unless KYORO_LANG is set."""
    import os
    if os.environ.get("KYORO_LANG"):
        return
    try:
        raw = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        lang = raw.get("language", "de")
        from modules.i18n import set_lang
        set_lang(lang)
    except Exception:
        pass


_apply_config_language()


def _auto_track_config_changes() -> None:
    """Chain-of-custody: sweep KYORO_CONFIG_DIR into its local git repo
    automatically, without any caller needing to know config_backup.py
    exists. Two sweeps: one now (catches changes already sitting there
    before this process started — a manual edit, another tool, a script
    that predates this feature) and one registered via atexit (catches
    whatever this process itself writes, even if it never calls
    commit_config_change()/commit_config_dir() explicitly). Fires for
    every script that imports health_config — which is effectively every
    Kyoro script, per this module's own docstring.

    Skipped under pytest: a documented past incident (see
    tests/unit/test_config_backup.py's docstring) had a not-fully-isolated
    test write synthetic data directly into the real ~/.config/kyoro/*.json
    files — an automatic git sweep firing on every test-suite run would
    make that class of leak commit itself into the user's real personal
    repo instead of surfacing as a visible problem."""
    if "pytest" in sys.modules:
        return
    if not KYORO_CONFIG_DIR.exists():
        return
    try:
        from modules.config_backup import ensure_git_repo, commit_config_dir
    except ImportError:
        return

    script_name = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "unknown"
    ensure_git_repo(KYORO_CONFIG_DIR)
    commit_config_dir(KYORO_CONFIG_DIR,
                       f"auto: pre-existing change detected before {script_name} ran")

    import atexit

    def _commit_on_exit() -> None:
        commit_config_dir(KYORO_CONFIG_DIR, f"auto: change by {script_name}")

    atexit.register(_commit_on_exit)


_auto_track_config_changes()


# ── Default Werte (werden durch Config überschrieben) ─────────────────────────
DEFAULTS = {
    "language": "de",
    "user": {
        "name":      "Unbekannt",
        "birthdate": None,
        "gender":    None,
        "height_cm": None,
        "timezone":  "UTC",
    },
    "paths": {
        "db":                str(_BASE_HOME / "Kyoro-HealthHub" / "data" / "health.db"),
        "medicine_db":       str(_BASE_HOME / "Kyoro-HealthHub" / "data" / "medicine.db"),
        "medicine_imaging_db": str(_BASE_HOME / "Kyoro-HealthHub" / "data" / "medicine_imaging.db"),
        "data_root":         str(_BASE_HOME / "Kyoro-HealthHub" / "imports"),
        "analyses":     str(_BASE_HOME / "Kyoro-HealthHub" / "analyses"),
        "manual":       str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "manual"),
        "polar":        str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "polar"),
        "apple_xml":    str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "apple_health" / "Export.xml"),
        "beurer":       str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "beurer"),
        "omron":        str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "omron"),
        "migraine":     str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "migraine"),
        "symptom_diary": str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "symptom_diary"),
        "garmin":       str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "garmin"),
        "garmin_gdpr":  str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "garmin_gdpr"),
        "kubios":       str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "kubios"),
        "camerahRV":    str(_BASE_HOME / "Kyoro-HealthHub" / "imports" / "camerahRV"),
    },
    "location": {
        "name": "Unbekannt",
        "lat":  None,
        "lon":  None,
    },
    "devices": {
        "polar":         True,
        "apple_health":  True,
        "oura":          False,
        "garmin":        False,
        "beurer":        False,
        "omron":         False,
        "migraine_app":  False,
        "symptom_diary": False,
        "sleep_cycle":   False,
        "fddb":          False,
    },
    "models": {
        "llm_path":   "/opt/voice-assistant/qwen3-30b-a3b-genai",
        "llm_device": "GPU",
    },
    "llm": {
        "provider": "openvino",
    },
    "db_key": None,
    "device_registry": [],
    "travel_history": [],
    "persons": [],
    "source_priority": [],
    "clinical": {
        "hrv_baseline_from":   None,
        "hrv_baseline_to":     None,
        "events":              [],
        "known_risk_exposures": [],
        "data_start":          None,
        "infection_date":      None,
        "max_hr":              None,
        # Formal gemessene aerobe/anaerobe Schwelle (Spiroergometrie/VT1 oder
        # Laktatstufentest/LT1) — hat Vorrang vor dem HRV-abgeleiteten HRVT1-
        # Schaetzwert in compute_pem.py, s. Config.measured_at_bpm.
        "measured_at_bpm":     None,
        "measured_at_date":    None,
        "measured_at_method":  None,  # "cpet" | "lactate"
        "baseline_method":     "device_top",  # all_iqr | all_top | device_iqr | device_top
        "baseline_device":     [],  # Geräte-Filter für device_top/device_iqr; leer = alle Geräte (kein Filter)
        "baseline_top_pct":    25,            # Prozent "beste Tage" für *_top Methoden
        "arrhythmia": {
            "cv_threshold":   0.15,
            "min_windows":    2,
            "tpr_threshold":  0.5743,  # AFDB-kalibriert (MIT-BIH AF Database); AUC 0.882
            "rmssd_confirm":  30,
            # Dash 2009 — für PPG-Sensoren (Oura, optische Sensoren)
            # H_norm: normalisierte Shannon-Entropie des RR-Histogramms (0–1)
            # Ref: Dash et al. 2009, doi:10.1007/s10439-009-9740-z
            "dash2009_h_threshold":  0.35,  # H_norm > 0.35 → AF-verdächtig
            "dash2009_cv_threshold": 0.08,  # CV_RR  > 0.08 → AF-verdächtig
        },
    }
}


@lru_cache(maxsize=1)
def load() -> dict:
    """Loads Configuration, merged with Defaults. Result is cached per process."""
    if not CONFIG_PATH.exists():
        return _deep_merge(DEFAULTS, {})
    try:
        user_cfg = json.loads(CONFIG_PATH.read_text())
        return _deep_merge(DEFAULTS, user_cfg)
    except Exception as e:
        print(t(f"Warnung: Config konnte nicht geladen werden ({e}), nutze Defaults.", f"Warning: Config could not be loaded ({e}), using defaults."))
        return _deep_merge(DEFAULTS, {})


_SECRET_KEY_PATTERN = ("key", "token", "secret", "password", "api_token", "apikey")


def _mask_secrets(value):
    """Return a deep copy of ``value`` with any *_key/_token/_secret/_password/api_token
    field masked. Used for ``--show`` so we never print credentials to a terminal
    or paste-buffer."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            lk = str(k).lower()
            if v and isinstance(v, str) and any(p in lk for p in _SECRET_KEY_PATTERN):
                out[k] = "***"
            else:
                out[k] = _mask_secrets(v)
        return out
    if isinstance(value, list):
        return [_mask_secrets(v) for v in value]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _normalize_family_history_entry(raw: dict) -> list[dict]:
    """Normalize a legacy inline family_history entry (relation/conditions[]/
    deceased/cause_of_death, as documented in health_config.example.json) into
    canonical entries (relative/side/condition/status/age_onset/notes, as
    written by manage_family_history.py). Already-canonical entries (identified
    by the 'relative' key) pass through unchanged. One legacy entry with
    multiple conditions expands into one canonical entry per condition."""
    if "relative" in raw:
        return [raw]

    relative = raw.get("relation", "")
    conditions = raw.get("conditions", [])
    if not conditions:
        return []

    death_cause = raw.get("cause_of_death") or raw.get("death_cause")
    notes_parts = []
    if raw.get("deceased"):
        death_year = raw.get("death_year")
        deceased_val = death_year if death_year else raw["deceased"]
        notes_parts.append(f"verstorben {deceased_val}")
    if death_cause:
        notes_parts.append(f"Todesursache: {death_cause}")
    notes = "; ".join(notes_parts) or None

    return [
        {
            "relative": relative,
            "side": "unbekannt",
            "condition": cond,
            "status": "bestätigt",
            "notes": notes,
        }
        for cond in conditions
    ]


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    CONFIG_PATH.chmod(0o600)
    load.cache_clear()


# ── Convenience-Properties ────────────────────────────────────────────────────
class Config:
    """Typisierter Zugriff auf Configurationswerte."""
    def __init__(self):
        self._cfg = load()

    # User
    @property
    def name(self) -> str:
        return self._cfg["user"]["name"]

    @property
    def birthdate(self) -> str | None:
        return self._cfg["user"]["birthdate"]

    @property
    def age(self) -> int | None:
        bday = self._cfg["user"]["birthdate"]
        if not bday:
            return None
        from datetime import date, datetime
        try:
            bd = datetime.strptime(bday, "%Y-%m-%d").date()
        except ValueError:
            return None
        today = date.today()
        # Whole calendar years; correct around the birthday and unaffected by leap days.
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

    @property
    def gender(self) -> str | None:
        return self._cfg["user"]["gender"]

    @property
    def height_cm(self) -> int | None:
        return self._cfg["user"]["height_cm"]

    @property
    def country(self) -> str | None:
        """ISO 3166-1 alpha-2 (e.g. "DE"). Not yet read by any guideline
        script — see local feature backlog BACK-32. .get() (not required, unlike
        gender/height_cm) so existing configs predating this field don't
        crash."""
        return self._cfg["user"].get("country")

    @property
    def region(self) -> str | None:
        """State/Bundesland, free text (e.g. "Bayern"). Optional — country
        alone is enough for guideline selection; region is for future
        finer-grained use. Not yet read anywhere, see BACK-32."""
        return self._cfg["user"].get("region")

    @property
    def home_timezone(self) -> str:
        return self._cfg["user"].get("timezone") or "UTC"

    # Paths
    # .expanduser() everywhere below: config values (including the shipped
    # template) may contain a literal "~", which Path() does NOT expand on
    # its own — leaving it un-expanded means e.g. sqlite3.connect() gets a
    # literal "~" directory name instead of the real home directory.
    @property
    def db_path(self) -> Path:
        return Path(self._cfg["paths"]["db"]).expanduser()

    @property
    def medicine_db_path(self) -> Path:
        return Path(self._cfg["paths"].get("medicine_db",
            str(_BASE_HOME / "Kyoro-HealthHub" / "data" / "medicine.db"))).expanduser()

    @property
    def medicine_imaging_db_path(self) -> Path:
        return Path(self._cfg["paths"].get("medicine_imaging_db",
            str(_BASE_HOME / "Kyoro-HealthHub" / "data" / "medicine_imaging.db"))).expanduser()

    @property
    def data_root(self) -> Path:
        return Path(self._cfg["paths"]["data_root"]).expanduser()

    @property
    def analyses_dir(self) -> Path:
        env = _os.environ.get("KYORO_ANALYSES_DIR")
        if env:
            return Path(env).expanduser()
        p = self._cfg["paths"]
        return Path(p.get("analyses") or p.get("diagnosen", "~/analyses")).expanduser()

    @property
    def manual_dir(self) -> Path:
        p = self._cfg["paths"]
        return Path(p.get("manual") or p.get("manuell", "~/manual")).expanduser()

    @property
    def polar_dir(self) -> Path:
        return Path(self._cfg["paths"]["polar"]).expanduser()

    @property
    def apple_xml(self) -> Path:
        return Path(self._cfg["paths"]["apple_xml"]).expanduser()

    @property
    def beurer_dir(self) -> Path:
        return Path(self._cfg["paths"]["beurer"]).expanduser()

    @property
    def omron_dir(self) -> Path:
        return Path(self._cfg["paths"]["omron"]).expanduser()

    @property
    def withings_dir(self) -> Path:
        p = self._cfg["paths"]
        return Path(p.get("withings", "~/Kyoro-HealthHub/imports/withings")).expanduser()

    @property
    def migraine_dir(self) -> Path:
        p = self._cfg["paths"]
        return Path(p.get("migraine") or p.get("migraene", "~/migraine")).expanduser()

    @property
    def symptom_diary_dir(self) -> Path:
        p = self._cfg["paths"]
        return Path(p.get("symptom_diary") or p.get("symptome", "~/symptom_diary")).expanduser()

    @property
    def garmin_dir(self) -> Path:
        return Path(self._cfg["paths"]["garmin"]).expanduser()

    @property
    def garmin_gdpr_dir(self) -> Path:
        p = self._cfg["paths"]
        return Path(p.get("garmin_gdpr", "~/Kyoro-HealthHub/imports/garmin_gdpr")).expanduser()

    @property
    def kubios_dir(self) -> Path:
        return Path(self._cfg["paths"]["kubios"]).expanduser()

    @property
    def camerahRV_dir(self) -> Path:
        return Path(self._cfg["paths"]["camerahRV"]).expanduser()

    @property
    def garmin_gpsmap_dir(self) -> Path | None:
        p = self._cfg["paths"].get("garmin_gpsmap")
        return Path(p) if p else None

    @property
    def polar_gpx_dir(self) -> Path | None:
        p = self._cfg["paths"].get("polar_gpx")
        return Path(p) if p else None

    # Location
    @property
    def home_name(self) -> str:
        return self._cfg["location"]["name"]

    @property
    def home_lat(self) -> float | None:
        return self._cfg["location"]["lat"]

    @property
    def home_lon(self) -> float | None:
        return self._cfg["location"]["lon"]

    def location_for_date(self, date: str) -> tuple[str, float | None, float | None]:
        """Return (name, lat, lon) for the user's actual location on a given date (YYYY-MM-DD).

        Priority: travel_history > location_history > current location.
        travel_history entries represent trips that override the home location.
        location_history entries represent past residences.
        All date ranges are inclusive.
        """
        for entry in self.travel_history:
            d_from = entry.get("date_from", "")
            d_to   = entry.get("date_to",   "")
            if d_from <= date <= (d_to or date):
                return entry.get("name", ""), entry.get("lat"), entry.get("lon")
        for entry in self._cfg.get("location_history", []):
            d_from = entry.get("date_from", "")
            d_to   = entry.get("date_to",   "")
            if d_from <= date <= d_to:
                return entry.get("name", ""), entry.get("lat"), entry.get("lon")
        loc = self._cfg.get("location", {})
        return loc.get("name", ""), loc.get("lat"), loc.get("lon")

    # Devices (importer enable/disable flags)
    def has_device(self, device: str) -> bool:
        return self._cfg["devices"].get(device, False)

    # Device + App registry — external ~/.config/kyoro/registry.json (primary)
    def _registry(self) -> dict:
        import json as _json
        f = KYORO_CONFIG_DIR / "registry.json"
        if f.exists():
            try:
                return _json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @property
    def device_registry(self) -> list[dict]:
        return self._registry().get("device_registry") or self._cfg.get("device_registry", [])

    @property
    def app_registry(self) -> list[dict]:
        return self._registry().get("app_registry") or self._cfg.get("app_registry", [])

    @property
    def travel_history(self) -> list[dict]:
        """Visited regions from ~/.config/kyoro/travel_history.json (primary) merged with
        inline travel_history in health_config.json (fallback/supplement)."""
        import json as _json
        separate_file = KYORO_CONFIG_DIR / "travel_history.json"
        external: list[dict] = []
        if separate_file.exists():
            try:
                external = _json.loads(separate_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        inline = self._cfg.get("travel_history", [])
        # Deduplicate by (name, date_from): external takes precedence
        seen = {(e.get("name"), e.get("date_from")) for e in external}
        merged = list(external)
        for e in inline:
            if (e.get("name"), e.get("date_from")) not in seen:
                merged.append(e)
        return merged

    @property
    def family_history(self) -> list[dict]:
        """First-degree relatives' conditions from ~/.config/kyoro/family_history.json
        (primary, canonical schema: relative/side/condition/status/age_onset/notes —
        written by manage_family_history.py) merged with inline family_history[] in
        health_config.json (fallback, legacy schema: relation/conditions[]/deceased/
        cause_of_death — normalized to the canonical schema on read)."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "family_history.json"
        external: list[dict] = []
        if external_file.exists():
            try:
                external = _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        seen = {(e.get("relative"), e.get("condition")) for e in external}
        merged = list(external)
        for raw in self._cfg.get("family_history", []):
            for entry in _normalize_family_history_entry(raw):
                if (entry.get("relative"), entry.get("condition")) not in seen:
                    merged.append(entry)
        return merged

    @property
    def exposure_factors(self) -> list[dict]:
        """Lifestyle exposure factors from ~/.config/kyoro/exposure_profile.json
        (primary) merged with inline clinical.exposure_factors (fallback).
        Used for infectious disease risk stratification in differential reports."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "exposure_profile.json"
        external: list[dict] = []
        if external_file.exists():
            try:
                external = _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        inline = self._cfg.get("clinical", {}).get("exposure_factors", [])
        seen = {(e.get("type"), e.get("detail")) for e in external}
        merged = list(external)
        for e in inline:
            if (e.get("type"), e.get("detail")) not in seen:
                merged.append(e)
        return merged

    @property
    def allergies(self) -> list[dict]:
        """Known allergies/intolerances from ~/.config/kyoro/allergies.json
        (primary) merged with inline allergies[] in health_config.json (fallback)."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "allergies.json"
        external: list[dict] = []
        if external_file.exists():
            try:
                external = _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        inline = self._cfg.get("allergies", [])
        seen = {(e.get("allergen"), e.get("type")) for e in external}
        merged = list(external)
        for e in inline:
            if (e.get("allergen"), e.get("type")) not in seen:
                merged.append(e)
        return merged

    @property
    def exposure_history(self) -> dict:
        """Zoonosis/occupational/sexual exposure history from
        ~/.config/kyoro/exposure_history.json (primary) with fallback to
        inline exposure_history{} in health_config.json.
        Schema: {childhood_environment, animal_contacts[], occupational_exposures[],
        sexual_history{multiple_partners, hpv_vaccination, sti_screening[], known_stis[]}}."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "exposure_history.json"
        if external_file.exists():
            try:
                return _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._cfg.get("exposure_history", {})

    @property
    def persons_list(self) -> list[dict]:
        return self._cfg.get("persons", [])

    @property
    def source_priority_list(self) -> list[dict]:
        return self._cfg.get("source_priority", [])

    @property
    def synthesis_panel(self) -> dict:
        """Konsil-Panel-Konfiguration für analyse_synthesis.py aus
        ~/.config/kyoro/synthesis_panel.json (primär) mit Fallback auf
        inline clinical.synthesis_panel (health_config.json).
        Schema: {enabled: bool, members: [str], chair_model: str}."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "synthesis_panel.json"
        if external_file.exists():
            try:
                return _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self._cfg.get("synthesis_panel", {})

    # Models
    @property
    def llm_path(self) -> Path:
        return Path(self._cfg["models"]["llm_path"])

    @property
    def llm_device(self) -> str:
        return self._cfg["models"]["llm_device"]

    @property
    def llm_provider(self) -> str:
        return self._cfg.get("llm", {}).get("provider", "openvino")

    # Clinical events list
    @property
    def events(self) -> list[dict]:
        """Ordered list of clinical events from ~/.config/kyoro/clinical_events.json
        (primary) merged with inline clinical.events in health_config.json (fallback).
        Sorted by date ascending."""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "clinical_events.json"
        external: list[dict] = []
        if external_file.exists():
            try:
                external = _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        inline = self._cfg.get("clinical", {}).get("events", [])
        seen = {(e.get("name"), e.get("date")) for e in external}
        merged = list(external)
        for e in inline:
            if (e.get("name"), e.get("date")) not in seen:
                merged.append(e)
        return sorted(merged, key=lambda e: e.get("date") or "")

    def events_of_type(self, *types: str) -> list[dict]:
        """Return all events whose type matches any of the given types."""
        return [e for e in self.events if e.get("type") in types]

    @property
    def known_risk_exposures(self) -> list[dict]:
        """Personal chronic/cumulative risk exposures from ~/.config/kyoro/known_risk_exposures.json
        (primary) or inline clinical.known_risk_exposures (fallback).
        Each entry: {slug, description, level: high|medium|low, notes?}"""
        import json as _json
        external_file = KYORO_CONFIG_DIR / "known_risk_exposures.json"
        external: list[dict] = []
        if external_file.exists():
            try:
                external = _json.loads(external_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        inline = self._cfg.get("clinical", {}).get("known_risk_exposures", [])
        seen = {(e.get("slug"), e.get("description")) for e in external}
        merged = list(external)
        for e in inline:
            if (e.get("slug"), e.get("description")) not in seen:
                merged.append(e)
        return merged

    # Clinical
    @property
    def baseline_method(self) -> str:
        return self._cfg.get("clinical", {}).get("baseline_method", "device_top")

    @property
    def baseline_device(self) -> str | None:
        return self._cfg.get("clinical", {}).get("baseline_device")

    @property
    def baseline_top_pct(self) -> int:
        return self._cfg.get("clinical", {}).get("baseline_top_pct", 25)

    @property
    def hrv_baseline_from(self) -> str | None:
        return self._cfg["clinical"]["hrv_baseline_from"]

    @property
    def hrv_baseline_to(self) -> str | None:
        return self._cfg["clinical"]["hrv_baseline_to"]

    @property
    def data_start(self) -> str | None:
        """Earliest data date for pre-event baseline periods (e.g. '2020-01-01')."""
        return self._cfg.get("clinical", {}).get("data_start")

    @property
    def infection_date(self) -> str | None:
        """Index-Infektion für postinfektiöse Analysen (PEM, ME/CFS, Post-COVID).

        NICHT einfach die erste Infektion der Ereignisliste. Genau das tat diese
        Property vorher — und lieferte damit den Keuchhusten von 1985, obwohl
        clinical.infection_date explizit auf die COVID-Infektion gesetzt war. Alle
        acht postinfektiösen Analysen rechneten gegen 1985: das Vorher/Nachher
        hatte null Tage im "Vorher", der Vergleich war leer. Die Skripte liefen
        fehlerfrei durch — der Fehler war unsichtbar.

        Reihenfolge:
          1. clinical.infection_date — explizit gesetzt schlägt abgeleitet.
          2. Ein Ereignis mit "index": true.
          3. Erste Infektion NACH data_start, damit Kindheitsinfekte ohne jede
             Messdatenhistorie nicht gewinnen.
          4. Sonst die früheste Infektion.
        """
        explicit = self._cfg.get("clinical", {}).get("infection_date")
        if explicit:
            return explicit

        infections = sorted(
            (e["date"], e) for e in self.events if e.get("type") == "infection"
        )
        if not infections:
            return None

        for date, e in infections:
            if e.get("index"):
                return date

        ds = self.data_start
        if ds:
            after = [d for d, _ in infections if d > ds]
            if after:
                return after[0]

        return infections[0][0]

    @property
    def max_hr(self) -> int | None:
        """User's maximum heart rate in bpm for HR-zone calculations."""
        v = self._cfg.get("clinical", {}).get("max_hr")
        return int(v) if v is not None else None

    @property
    def measured_at_bpm(self) -> int | None:
        """Formal gemessene aerobe/anaerobe Schwelle (Spiroergometrie/VT1 oder
        Laktatstufentest/LT1) in bpm, falls in der Config eingetragen. Hat in
        compute_pem.py Vorrang vor dem HRV-abgeleiteten HRVT1-Schaetzwert
        (DFA-alpha1-Kreuzungspunkt), dessen Zuverlaessigkeit bei autonomer
        Dysfunktion nicht gesichert ist. Direkt gemessen statt geschaetzt."""
        v = self._cfg.get("clinical", {}).get("measured_at_bpm")
        return int(v) if v is not None else None

    @property
    def measured_at_info(self) -> dict:
        """Datum + Methode ('cpet'|'lactate') der measured_at_bpm-Messung, fuer
        Anzeige/Nachvollziehbarkeit in Berichten."""
        c = self._cfg.get("clinical", {})
        return {
            "bpm":    self.measured_at_bpm,
            "date":   c.get("measured_at_date"),
            "method": c.get("measured_at_method"),
        }

    @property
    def arrhythmia_cv_threshold(self) -> float:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("cv_threshold", 0.15)

    @property
    def arrhythmia_min_windows(self) -> int:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("min_windows", 2)

    @property
    def arrhythmia_tpr_threshold(self) -> float:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("tpr_threshold", 0.60)

    @property
    def arrhythmia_rmssd_confirm(self) -> float:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("rmssd_confirm", 30)

    @property
    def arrhythmia_dash2009_h_threshold(self) -> float:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("dash2009_h_threshold", 0.35)

    @property
    def arrhythmia_dash2009_cv_threshold(self) -> float:
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("dash2009_cv_threshold", 0.08)

    @property
    def arrhythmia_dash2009_calibration_mode(self) -> str:
        """'alternative' (self bevorzugt falls genug Fenster, sonst public, sonst Code-Default),
        'additive' (gewichteter Mittelwert public+self), 'public', 'self', oder 'off'."""
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("dash2009_calibration_mode", "alternative")

    @property
    def arrhythmia_sampen_threshold(self) -> float:
        # Default: AFDB-kalibriert via calibrate_afib_thresholds.py (AUC 0.853)
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("sampen_threshold", 1.5873)

    @property
    def arrhythmia_sampen_cv_threshold(self) -> float:
        # Default: AFDB-kalibriert cv_rr threshold (AUC 0.916)
        return self._cfg.get("clinical", {}).get("arrhythmia", {}).get("sampen_cv_threshold", 0.1476)

    # ── AFES / Geräte-Klassifizierung (Privacy: gehört in lokale Config, nicht in Code) ──
    @property
    def afes_excl_coarse_hr_devices(self) -> tuple[str, ...]:
        """device_ids, deren HR-Stream zu grob ist (z.B. Smart-Recording-Mittelung)
        und deshalb aus HR-basierten AFES-Komponenten auszuschließen ist."""
        v = self._cfg.get("clinical", {}).get("afes", {}).get("exclude_coarse_hr_devices", [])
        return tuple(v) if isinstance(v, (list, tuple)) else ()

    @property
    def afes_wrist_hr_devices(self) -> tuple[str, ...]:
        """Kontinuierliche Handgelenk-Sensoren für intraday HR-Spanne /
        symbolische Entropie. Override via clinical.afes.wrist_hr_devices;
        sonst automatisch aus device_registry abgeleitet (sensor_type
        ∈ {optical_wrist, optical_wrist_gps, ring})."""
        v = self._cfg.get("clinical", {}).get("afes", {}).get("wrist_hr_devices")
        if isinstance(v, (list, tuple)) and v:
            return tuple(v)
        wrist_types = {"optical_wrist", "optical_wrist_gps", "ring"}
        return tuple(
            d["device_id"] for d in self.device_registry
            if d.get("device_id") and (d.get("sensor_type") or "") in wrist_types
        )

    @property
    def afes_sleep_device_priority(self) -> tuple[str, ...]:
        """Geräte-Priorität für Sleep-Session-Erkennung (Nightdip-Komponente)."""
        v = self._cfg.get("clinical", {}).get("afes", {}).get("sleep_device_priority", [])
        return tuple(v) if isinstance(v, (list, tuple)) else ()

    @property
    def sleep_source_priority(self) -> tuple[str, ...]:
        """Quellen-Priorität (session.source-Werte) für die Auswahl der besten
        Schlaf-Session pro Nacht, z.B. bei der BP-Dipping-Analyse. Unbekannte
        Quellen fallen automatisch ans Ende (kein Crash bei leerer Liste)."""
        v = self._cfg.get("clinical", {}).get("sleep_source_priority", [])
        return tuple(v) if isinstance(v, (list, tuple)) else ()

    @property
    def polar_wrist_date_reassignments(self) -> list[dict]:
        """Ein-/Zweizeilige Datumsgrenzen für scripts/migrations/
        fix_polar_wrist_device_attribution.py — nur nötig, wenn historische
        Polar-Wrist-Daten fälschlich einem Platzhalter-device_id zugeordnet
        wurden (keine per-entry Geräte-ID im Export). Jeder Eintrag:
        {"new_device_id": str, "date_condition": str (rohe SQL-Bedingung auf
        die Spalte 'date', z.B. \"date >= '2022-01-01' AND date < '2023-10-01'\")}.
        Leer = Migration ist No-Op (kein Fehler)."""
        v = self._cfg.get("clinical", {}).get("polar_wrist_date_reassignments", [])
        return list(v) if isinstance(v, (list, tuple)) else []

    @property
    def afes_ecg_quality_devices(self) -> tuple[str, ...]:
        """Chest-strap / ECG-Qualitäts-Geräte für AF-Pre-Signal-Filter.
        Override via clinical.afes.ecg_quality_devices;
        sonst automatisch aus device_registry abgeleitet (sensor_type == 'chest_strap')."""
        v = self._cfg.get("clinical", {}).get("afes", {}).get("ecg_quality_devices")
        if isinstance(v, (list, tuple)) and v:
            return tuple(v)
        return tuple(
            d["device_id"] for d in self.device_registry
            if d.get("device_id") and d.get("sensor_type") == "chest_strap"
        )

    # ── Pacing / Energiemanagement ────────────────────────────────────────────
    @property
    def pacing_domain_weights(self) -> dict[str, float]:
        """Gewichtung der Energiedomänen (physical, sensory, cognitive, social).
        Override via clinical.pacing.domain_weights."""
        defaults = {"physical": 1.0, "sensory": 0.6, "cognitive": 0.8, "social": 0.7}
        cfg_w = self._cfg.get("clinical", {}).get("pacing", {}).get("domain_weights", {})
        return {**defaults, **{k: float(v) for k, v in cfg_w.items()}}

    @property
    def pacing_subjective_scale(self) -> float:
        """Scale-Faktor für subjektive 0–10 Scores → Gesamtpensum-Einheiten.
        Override via clinical.pacing.subjective_scale (Standard: 30)."""
        return float(self._cfg.get("clinical", {}).get("pacing", {}).get("subjective_scale", 30.0))

    @property
    def pacing_level_thresholds(self) -> dict[str, float]:
        """Schwellen für Belastungsstufen gelb/rot.
        Override via clinical.pacing.level_thresholds."""
        defaults = {"yellow": 400.0, "red": 700.0}
        cfg_t = self._cfg.get("clinical", {}).get("pacing", {}).get("level_thresholds", {})
        return {**defaults, **{k: float(v) for k, v in cfg_t.items()}}

    @property
    def pem_config(self) -> dict:
        """PEM Evidence Score Schwellwerte. Override via clinical.pem."""
        return self._cfg.get("clinical", {}).get("pem", {})

    @property
    def reference_devices(self) -> dict:
        """Pro Metrik konfiguriertes Referenz-/Kalibrierungs-Gerät (device_id).
        Override via clinical.reference_devices, z.B.
        {"hrv": "DEV-xxxxxxxx", "spo2": "DEV-yyyyyyyy"}. Leeres Dict (Standard)
        heisst: jede Metrik faellt auf den projekteigenen hartcodierten Anker
        zurueck (s. compute_calibrate_sources.ANCHORS, compute_pem.py HRV-
        Quellenhierarchie) — nicht konfiguriert ist der Normalfall, kein Fehler."""
        return self._cfg.get("clinical", {}).get("reference_devices", {})

    def resolve_reference_device(self, metric: str, default: "str | None") -> "str | None":
        """Konfigurierte device_id fuer `metric` aus reference_devices, sonst `default`.

        `default` ist der projekteigene hartcodierte Anker (z.B. ANCHORS-Eintrag
        oder oura_device_id) — dieser Aufruf aendert am Verhalten nichts fuer
        Installationen ohne reference_devices-Eintrag."""
        return self.reference_devices.get(metric) or default

    def device_source_apps(self, device_id: str) -> "list[str] | None":
        """source_app-Werte des Geraets `device_id` laut device_registry.

        Mehrere source_app-Werte pro Geraet sind moeglich (z.B. PDF-Import UND
        App-Screenshot-Import desselben physischen Geraets unter zwei
        unterschiedlichen source_app-Strings) — deshalb Liste, kein Einzelwert.
        None wenn das Geraet existiert, aber (noch) kein source_apps-Feld hat
        (Aufrufer muss das als "kann nicht aufgeloest werden" behandeln, nicht
        als leere Liste). Wirft ValueError, wenn device_id in keinem
        device_registry-Eintrag vorkommt — ein konfigurierter, aber
        nichtexistenter Anker soll auffallen, nicht still ignoriert werden."""
        for d in self.device_registry:
            if d.get("device_id") == device_id:
                apps = d.get("source_apps")
                return list(apps) if apps else None
        raise ValueError(
            f"reference_devices verweist auf device_id={device_id!r}, "
            f"das in keinem device_registry-Eintrag vorkommt."
        )

    @property
    def oura_device_id(self) -> str:
        """device_id für Oura-Ring-Importer. Automatisch aus device_registry abgeleitet
        (brand == 'Oura'); Fallback 'oura_4'."""
        for d in self.device_registry:
            if d.get("brand", "").lower() == "oura":
                return str(d["device_id"])
        return "oura_4"

    @property
    def garmin_gdpr_device_id(self) -> str:
        """device_id für GDPR-Import. Override via paths.garmin_gdpr_device_id;
        sonst automatisch aus device_registry abgeleitet (brand == 'Garmin',
        sensor_type ∈ {optical_wrist, optical_wrist_gps})."""
        v = self._cfg.get("paths", {}).get("garmin_gdpr_device_id")
        if v:
            return str(v)
        gps_types = {"optical_wrist", "optical_wrist_gps"}
        for d in self.device_registry:
            if (d.get("brand", "").lower() == "garmin"
                    and (d.get("sensor_type") or "") in gps_types):
                return str(d["device_id"])
        return "garmin_watch"

    @property
    def footpod_device_id(self) -> str:
        """device_id für Laufleistungsmesser-Importer (z.B. Stryd). Bewusst nicht
        markengebunden — automatisch aus device_registry abgeleitet
        (sensor_type == 'footpod'), damit auch andere Laufleistungsmesser
        (RunScribe, Milestone Pod, ...) ohne Codeänderung funktionieren.
        Fallback 'footpod_1', falls kein passendes Gerät registriert ist."""
        for d in self.device_registry:
            if (d.get("sensor_type") or "") == "footpod":
                return str(d["device_id"])
        return "footpod_1"


# ── Setup ─────────────────────────────────────────────────────────────────────
def setup():
    """Interaktiver Setup — erstellt ~/.config/kyoro/health_config.json."""
    print("=== Health System Konfiguration ===\n")
    cfg = load()

    def ask(prompt, default=None):
        hint = f" [{default}]" if default else ""
        val = input(f"{prompt}{hint}: ").strip()
        return val if val else default

    # User
    cfg["user"]["name"]      = ask("Vorname", cfg["user"]["name"])
    cfg["user"]["birthdate"] = ask("Geburtsdatum (YYYY-MM-DD)", cfg["user"]["birthdate"])
    cfg["user"]["gender"]    = ask("Geschlecht (weiblich/männlich/divers)", cfg["user"]["gender"])
    if ask("Körpergröße eingeben? (j/n)", "j") == "j":
        raw = ask("Körpergröße (cm)", cfg["user"]["height_cm"] or "")
        try:
            cfg["user"]["height_cm"] = int(raw) if raw else cfg["user"]["height_cm"]
        except ValueError:
            print(t("Ungültige Eingabe — Wert nicht geändert.",
                    "Invalid input — value unchanged."))

    # Paths
    print("\n--- Verzeichnisse ---")
    cfg["paths"]["db"]       = ask("Datenbankpfad (health.db)", cfg["paths"]["db"])
    cfg["paths"]["data_root"]= ask("Datenwurzel", cfg["paths"]["data_root"])
    cfg["paths"]["analyses"] = ask("Ausgabe-Verzeichnis (analyses)",
                                    cfg["paths"].get("analyses", DEFAULTS["paths"]["analyses"]))

    # Location
    print("\n--- Heimatstandort ---")
    cfg["location"]["name"]  = ask("Ortsname", cfg["location"]["name"])
    cfg["location"]["lat"]   = float(ask("Breitengrad (lat)", cfg["location"]["lat"] or ""))
    cfg["location"]["lon"]   = float(ask("Längengrad (lon)", cfg["location"]["lon"] or ""))

    save(cfg)
    print(t(f"\nGespeichert: {CONFIG_PATH}", f"\nSaved: {CONFIG_PATH}"))


def _migrate_key():
    """Verschiebt db_key aus health_config.json in ~/.config/kyoro/db.key."""
    cfg_path = CONFIG_PATH
    cfg = json.loads(cfg_path.read_text("utf-8"))
    key = cfg.get("db_key")

    if not key:
        print("Kein db_key in health_config.json — nichts zu migrieren.")
        if _KEY_FILE.exists():
            print(f"{_KEY_FILE} existiert bereits.")
        return

    if _KEY_FILE.exists():
        existing = _KEY_FILE.read_text("utf-8").strip()
        if existing == key:
            print(f"{_KEY_FILE} ist bereits aktuell. Entferne db_key aus Config …")
        else:
            print(f"FEHLER: {_KEY_FILE} existiert aber enthält anderen Key. Abbruch.")
            sys.exit(1)
    else:
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _KEY_FILE.write_text(key + "\n", encoding="utf-8")
        _KEY_FILE.chmod(0o600)
        print(f"Key gespeichert in {_KEY_FILE} (chmod 600)")

    # db_key aus config entfernen
    cfg["db_key"] = None
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"db_key aus {cfg_path} entfernt.")
    print("Test: python3 scripts/health_config.py --test-db")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Health System Konfiguration")
    parser.add_argument("--setup",       action="store_true", help="Konfiguration einrichten")
    parser.add_argument("--show",        action="store_true", help="Aktuelle Konfiguration anzeigen")
    parser.add_argument("--migrate-key", action="store_true",
                        help="db_key aus health_config.json → ~/.config/kyoro/db.key (sicherer)")
    parser.add_argument("--test-db",     action="store_true", help="DB-Verbindung testen")
    args = parser.parse_args()

    if args.setup:
        setup()
    elif args.show:
        cfg = load()
        print(json.dumps(_mask_secrets(cfg), indent=2, ensure_ascii=False))
    elif args.migrate_key:
        _migrate_key()
    elif args.test_db:
        try:
            from modules.db import open_db
            conn = open_db()
            n = conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
            conn.close()
            print(f"DB-Verbindung OK ({n} Tabellen/Views)")
        except Exception as e:
            print(f"FEHLER: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
