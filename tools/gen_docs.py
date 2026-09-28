#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Generate bilingual per-script documentation from structured module docstrings.

The module docstring is the SINGLE SOURCE OF TRUTH. This tool renders it into
docs/<lang>/<subdir>/<script>.md — it never carries content of its own.

Field convention (inside the module docstring):

  <first line>            free title (neutral)
  @tier        one of: validated | research | calibrated | heuristic | experimental | infrastructure
  @purpose.de  / @purpose.en    prose (bilingual)
  @method.de   / @method.en     prose (bilingual)
  @limits.de   / @limits.en     prose (bilingual)
  @thresholds  block of lines "VALUE :: de=... :: en=..."
                 VALUE (the clinical number) appears exactly ONCE — never
                 duplicated across languages; only the gloss is bilingual.
  @reads       comma/space separated table names (neutral)
  @writes      "table: col TYPE, col TYPE, ..." (neutral)
  @refs        one reference per line, ideally with doi: (neutral)
  @usage       CLI invocations, one per line (neutral)

Also generates docs/generated/data_flow.md: a Mermaid data-flow diagram per
pipeline stage (importers/compute/analysis/other, per CLAUDE.md's
Architecture section), built from the same @reads/@writes/@tier fields as
the per-script docs above -- kept in this file rather than a second,
separately-maintained docstring parser after one such duplicate parser
(scripts/generate_docstring_docs.py, since removed) silently diverged from
a bugfix made here and re-introduced the same bug it had already fixed.

Modes:
  gen_docs.py [paths...]   regenerate docs (default: the reference script)
  gen_docs.py --check      regenerate in memory; exit 1 if committed docs differ
                           or a required field is missing (CI gate, no writes)
"""

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LANGS = ("de", "en")

# Section labels live here (the i18n layer for docs). Neutral content is not
# translated; only these fixed labels differ per language.
LABELS = {
    "purpose":    {"de": "Zweck",         "en": "Purpose"},
    "relevance":  {"de": "Relevanz",      "en": "Relevance"},
    "method":     {"de": "Methode",       "en": "Method"},
    "scoring":    {"de": "Berechnung",    "en": "Scoring"},
    "thresholds": {"de": "Schwellenwerte", "en": "Thresholds"},
    "dataflow":   {"de": "Datenfluss",    "en": "Data flow"},
    "reads":      {"de": "Liest",         "en": "Reads"},
    "writes":     {"de": "Schreibt",      "en": "Writes"},
    "refs":       {"de": "Referenzen",    "en": "References"},
    "limits":     {"de": "Grenzen",       "en": "Limitations"},
    "usage":      {"de": "Aufruf",        "en": "Usage"},
    "thr_value":  {"de": "Wert",          "en": "Value"},
    "thr_mean":   {"de": "Bedeutung",     "en": "Meaning"},
    "tier":       {"de": "Evidenzstufe",  "en": "Evidence tier"},
    "banner":     {
        "de": "GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.",
        "en": "GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.",
    },
}

TIER_BADGE = {
    "validated":      {"de": "validiert (klinische Validierungsstudie vorhanden: "
                              "Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)",
                       "en": "validated (clinical validation study exists: "
                              "sensitivity/specificity or endpoints prospectively established)"},
    "research":       {"de": "Forschung (peer-reviewte Literaturbasis, "
                              "aber keine formale klinische Validierungsstudie mit Endpunkten)",
                       "en": "research (peer-reviewed literature basis, "
                              "but no formal clinical validation study with endpoints)"},
    "calibrated":     {"de": "kalibriert (Literaturbasis + Parameter auf persönliche "
                              "Baselines angepasst, keine externe Validierung)",
                       "en": "calibrated (literature-based + parameters tuned to personal "
                              "baselines, no external validation)"},
    "heuristic":      {"de": "Heuristik (deliberate Designentscheidung aus Domänenwissen, "
                              "keine formale Literatur- oder Validierungsbasis)",
                       "en": "heuristic (deliberate design from domain knowledge, "
                              "no formal literature or validation basis)"},
    "experimental":   {"de": "experimentell (explorativ, kein stabiles konzeptionelles "
                              "Fundament, hypothesengenerierend)",
                       "en": "experimental (exploratory, no stable conceptual foundation, "
                              "hypothesis-generating)"},
    "infrastructure": {"de": "Infrastruktur (keine klinische Aussage)",
                       "en": "infrastructure (no clinical claim)"},
}

PROSE_FIELDS = ("purpose", "relevance", "method", "limits")
REQUIRED_FIELDS = ("tier", "purpose", "relevance", "method", "limits")  # enforced by --check

_FIELD_RE = re.compile(r"^@(?P<name>[a-z_]+)(?:\.(?P<lang>de|en))?\b(?P<rest>.*)$")

# A continuation line inside @refs starts a NEW reference only if it looks
# like one (author/org name, or a publication year in parens near the
# start) -- otherwise it's a word-wrapped continuation of the previous
# reference's text and gets folded back onto it. Without this, a citation
# like "Munster K et al. (2012). ... women aged\n  20-34. doi:X" (wrapped
# purely for line length) gets silently split into two disconnected
# "references" -- one without a DOI, one that's a meaningless fragment --
# which breaks both the generated docs (two orphaned bullets) and any
# semantic verification of the DOI (fed a fragment instead of the citation).
_REF_START_RE = re.compile(
    r"^(?:"
    r"(?:van|von|de|der|den|la|le)\s+)?[A-ZÄÖÜ][\wÀ-ÿ.'-]*"
    r"(?:,?\s+(?:[A-ZÄÖÜ]\.?\s*)*)?(?:et al\.?|&|,)\s"
    r"|(?:WHO|ADA|ACOG|ACSM|FDA|DGN|DSG|NICE|IOM|NAM|ATS|RKI|ESC|WAO|EAACI|AWMF|FIGO|DICOM|IARC"
    r"|Zenodo|PhysioNet)\b"
)
# A publication year, anywhere before a doi:/PMC/PMID/ISBN identifier marker
# (never after -- a year embedded inside a DOI string itself, e.g.
# "10.1136/jech.2010.128249", must not count). Not anchored to the very
# start of the line: "Bohannon RW 1997, Gait Posture..." has no parens
# around its year and "de Zambotti et al. 2018..." starts with a lowercase
# name particle, so a narrow start-of-line check missed both and merged
# them into the wrong preceding reference.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_IDENTIFIER_MARKER_RE = re.compile(r"\bdoi:|\bPMC\d|\bPMID:|\bISBN\b", re.IGNORECASE)
# A line that's just "(YYYY). Title..." with nothing before the parenthesized
# year is never the start of a real reference -- every citation style here
# names authors first. It IS the common second line of an author list
# wrapped onto its own line ("Author A, Author B\n(YYYY). Title..."), so
# without this exclusion the unanchored _YEAR_RE match below wrongly treats
# it as a new reference and splits the author list from its own year/title/DOI.
_YEAR_ONLY_CONTINUATION_RE = re.compile(r"^\(\d{4}\)")


def _looks_like_new_ref(line: str) -> bool:
    if _YEAR_ONLY_CONTINUATION_RE.match(line):
        return False
    head = _IDENTIFIER_MARKER_RE.split(line, maxsplit=1)[0]
    return bool(_YEAR_RE.search(head)) or bool(_REF_START_RE.match(line))


def _merge_wrapped_refs(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for ln in lines:
        if not merged or _looks_like_new_ref(ln):
            merged.append(ln)
        else:
            merged[-1] = merged[-1] + " " + ln
    return merged


def parse_docstring(doc: str) -> dict:
    """Segment a structured docstring into a field dict."""
    lines = doc.splitlines()
    title = ""
    for ln in lines:
        if ln.strip() and not ln.lstrip().startswith("@"):
            title = ln.strip()
            break

    # Each segment: (name, lang, inline, raw_lines). inline = text on the @field
    # line itself; raw_lines = continuation lines (rstripped, indentation kept).
    # A blank line always ends the current field's continuation -- untagged
    # prose after a field (e.g. leftover text not using a real @tag) must not
    # be silently absorbed into whichever field happened to precede it.
    segments: list[tuple[str, str | None, str, list[str]]] = []
    cur: list | None = None
    for ln in lines:
        m = _FIELD_RE.match(ln.strip())
        # A bare "@purpose"/"@method"/"@limits" (no .de/.en suffix) is never a
        # real field start in this project's convention -- always paired with a
        # language suffix. Without this guard, an inline cross-reference like
        # "... see @limits for the caveat" at the start of a wrapped
        # continuation line is misread as a new field, silently truncating the
        # real one (e.g. compute_orthostatic_detection.py's @method.de lost
        # everything after "... see @limits ..." until this was caught).
        if m and m.group("name") in PROSE_FIELDS and not m.group("lang"):
            m = None
        if m:
            if cur:
                segments.append(tuple(cur))
            cur = [m.group("name"), m.group("lang"), m.group("rest").strip(), []]
        elif not ln.strip():
            if cur:
                segments.append(tuple(cur))
            cur = None
        elif cur is not None:
            cur[3].append(ln.rstrip())
    if cur:
        segments.append(tuple(cur))

    # A field can legitimately span more than one segment now that a blank
    # line closes a segment (e.g. an @refs block with a blank line between
    # citation groups) -- merge same-named segments instead of letting a
    # later one silently overwrite an earlier one.
    fields: dict = {}
    for name, lang, inline, raw in segments:
        stripped = ([inline] if inline else []) + [l.strip() for l in raw]
        block = ([inline] if inline else []) + _dedent(raw)
        if name in PROSE_FIELDS:
            fields.setdefault(name, {})
            if lang:
                joined = " ".join(stripped)
                existing = fields[name].get(lang)
                fields[name][lang] = f"{existing} {joined}" if existing else joined
        elif name == "thresholds":
            fields.setdefault("thresholds", [])
            fields["thresholds"].extend(_parse_thresholds(stripped))
        elif name in ("refs", "usage", "scoring"):
            fields.setdefault(name, [])
            fields[name].extend(block)
        elif name == "reads":
            fields.setdefault("reads", [])
            fields["reads"].extend(t for t in re.split(r"[,\s]+", " ".join(stripped)) if t)
            # Comma-only split for the aggregate data-flow diagram: some
            # scripts' @reads violates the "comma/space separated table
            # names" convention with a free-text phrase instead (e.g. "23andMe
            # SNP export file (.vcf...)") -- the word-split above is correct
            # for those single-word real table names in the per-script docs'
            # "Liest:" line, but fragments a phrase like that into meaningless
            # single-word nodes ("(.vcf", "23andMe", ...) in the diagram.
            fields.setdefault("reads_raw", [])
            fields["reads_raw"].extend(t.strip() for t in " ".join(stripped).split(",") if t.strip())
        elif name == "writes":
            fields.setdefault("writes", [])
            fields["writes"].extend(block)
        elif name == "tier":
            fields["tier"] = " ".join(stripped).strip()
    if "refs" in fields:
        fields["refs"] = _merge_wrapped_refs(fields["refs"])
    fields["title"] = title
    return fields


def _dedent(lines: list[str]) -> list[str]:
    """Remove the common leading indentation from continuation lines."""
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return [l[cut:] for l in lines]


def _parse_thresholds(body: list[str]) -> list[dict]:
    rows = []
    for ln in body:
        parts = [p.strip() for p in ln.split("::")]
        value = parts[0]
        gloss = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                gloss[k.strip()] = v.strip()
        rows.append({"value": value, "gloss": gloss})
    return rows


def render(fields: dict, lang: str, source_rel: str) -> str:
    L = lambda k: LABELS[k][lang]
    out: list[str] = []
    out.append(f"# {fields.get('title', '')}")
    out.append("")
    out.append(f"> {L('banner')}  ")
    out.append(f"> Source: `{source_rel}`")
    out.append("")

    tier = fields.get("tier")
    if tier in TIER_BADGE:
        out.append(f"**{L('tier')}:** {TIER_BADGE[tier][lang]}")
        out.append("")

    for f in ("purpose", "relevance", "method"):
        val = fields.get(f, {}).get(lang)
        if val:
            out.append(f"## {L(f)}")
            out.append("")
            out.append(val)
            out.append("")

    if fields.get("scoring"):
        out.append(f"## {L('scoring')}")
        out.append("")
        out.append("```")
        out.extend(fields["scoring"])
        out.append("```")
        out.append("")

    thr = fields.get("thresholds")
    if thr:
        out.append(f"## {L('thresholds')}")
        out.append("")
        out.append(f"| {L('thr_value')} | {L('thr_mean')} |")
        out.append("|---|---|")
        for row in thr:
            out.append(f"| `{row['value']}` | {row['gloss'].get(lang, '')} |")
        out.append("")

    if fields.get("reads") or fields.get("writes"):
        out.append(f"## {L('dataflow')}")
        out.append("")
        if fields.get("reads"):
            tbls = ", ".join(f"`{t}`" for t in fields["reads"])
            out.append(f"- **{L('reads')}:** {tbls}")
        writes = fields.get("writes") or []
        if len(writes) == 1:
            out.append(f"- **{L('writes')}:** `{writes[0]}`")
        elif writes:
            out.append(f"- **{L('writes')}:**")
            out.append("")
            out.append("  ```")
            out.extend(f"  {w}" for w in writes)
            out.append("  ```")
        out.append("")

    limits = fields.get("limits", {}).get(lang)
    if limits:
        out.append(f"## {L('limits')}")
        out.append("")
        out.append(limits)
        out.append("")

    if fields.get("refs"):
        out.append(f"## {L('refs')}")
        out.append("")
        for r in fields["refs"]:
            out.append(f"- {r}")
        out.append("")

    if fields.get("usage"):
        out.append(f"## {L('usage')}")
        out.append("")
        out.append("```bash")
        out.extend(fields["usage"])
        out.append("```")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def doc_path(source: Path, lang: str) -> Path:
    rel = source.relative_to(REPO / "scripts").with_suffix(".md")
    return REPO / "docs" / lang / rel


def process(source: Path, check: bool) -> list[str]:
    """Return list of problems (empty = OK)."""
    problems: list[str] = []
    rel = source.relative_to(REPO).as_posix()
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        doc = ast.get_docstring(tree)
    except Exception as e:  # noqa: BLE001
        return [f"{rel}: cannot parse ({e})"]
    if not doc:
        return [f"{rel}: no module docstring"]

    fields = parse_docstring(doc)

    for req in REQUIRED_FIELDS:
        if req == "tier":
            if fields.get("tier") not in TIER_BADGE:
                problems.append(f"{rel}: @tier missing or invalid "
                                f"(need one of {'/'.join(TIER_BADGE)})")
        else:
            for lang in LANGS:
                if not fields.get(req, {}).get(lang):
                    problems.append(f"{rel}: @{req}.{lang} missing")

    for lang in LANGS:
        target = doc_path(source, lang)
        content = render(fields, lang, rel)
        if check:
            existing = target.read_text(encoding="utf-8") if target.exists() else None
            if existing != content:
                problems.append(f"{target.relative_to(REPO).as_posix()}: out of date")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    return problems


def discover() -> list[Path]:
    """All scripts already converted to the field convention (docstring has @tier)."""
    found = []
    for f in sorted((REPO / "scripts").rglob("*.py")):
        if f.name == "__init__.py":
            continue
        try:
            doc = ast.get_docstring(ast.parse(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
        if doc and re.search(r"^@tier\b", doc, re.M):
            found.append(f)
    return found


def check_orphaned_docs() -> list[str]:
    """Check for documentation files without corresponding source scripts.
    
    Returns list of orphaned doc paths relative to REPO.
    """
    orphans = []
    for lang in LANGS:
        docs_dir = REPO / "docs" / lang
        if not docs_dir.exists():
            continue
        # Walk through all .md files in docs/de/**/*.md and docs/en/**/*.md
        for md_file in docs_dir.rglob("*.md"):
            # Convert docs/de/analysis/cardiovascular/x.md 
            # to scripts/analysis/cardiovascular/x.py
            rel_from_docs = md_file.relative_to(docs_dir)
            rel_from_repo = md_file.relative_to(REPO)
            
            # Build expected source path: docs/de/.../x.md -> scripts/.../x.py
            parts = rel_from_docs.parts
            script_rel = Path("scripts") / Path(*parts[:-1]) / Path(parts[-1]).with_suffix(".py")
            script_path = REPO / script_rel
            
            if not script_path.exists():
                orphans.append(rel_from_repo.as_posix())
    return orphans


def _tracked_scripts() -> list[Path]:
    """Git-tracked .py files under scripts/ -- deliberately narrower than
    discover()'s rglob: a gitignored/experimental script not yet ready for
    commit must not leak into the publicly tracked aggregate diagram just
    because it happens to sit in the local working tree."""
    result = subprocess.run(
        ["git", "-C", str(REPO / "scripts"), "ls-files"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return []
    return [REPO / "scripts" / line for line in result.stdout.splitlines()
            if line.endswith(".py") and Path(line).name != "__init__.py"]


# Pipeline stages from CLAUDE.md's Architecture section (imports/ ->
# import_all.py -> compute_all.py -> analyse_all.py), in display order. The
# scripts/-subdirectory name is the grouping key.
_PIPELINE_STAGES = [
    ("importers", "Importer (Rohdaten -> DB)"),
    ("compute", "Compute (DB -> abgeleitete Tabellen)"),
    ("analysis", "Analyse (abgeleitete Tabellen -> Reports)"),
]
_OTHER_STAGE_LABEL = "Sonstige (Utils, Query, Exporters, Migrations, ...)"

DATA_FLOW_PATH = REPO / "docs" / "generated" / "data_flow.md"


def _pipeline_stage(source: Path) -> str:
    rel_parts = source.relative_to(REPO / "scripts").parts
    return rel_parts[0] if len(rel_parts) > 1 else "_root"


def _render_stage_diagram(title: str, entries: "list[tuple[str, str, list[str], list[str]]]") -> str:
    """entries: list of (name, tier, reads, writes)."""
    md = f"## {title}\n\n"
    md += "```mermaid\n"
    md += "flowchart TB\n"
    md += "    subgraph Input[Eingabetabellen]\n"

    all_reads: set[str] = set()
    for _, _, reads, _ in entries:
        all_reads.update(reads)
    for table in sorted(all_reads):
        md += f"        {table}\n"

    md += "    end\n\n"
    md += "    subgraph Scripts[Verarbeitung]\n"

    by_tier: dict[str, list[str]] = defaultdict(list)
    for name, tier, _, _ in entries:
        by_tier[tier or "unclassified"].append(name)
    for tier in sorted(by_tier.keys()):
        md += f"        subgraph {tier}[{tier}]\n"
        for name in sorted(by_tier[tier]):
            md += f"            {name}\n"
        md += "        end\n"

    md += "    end\n\n"
    md += "    subgraph Output[Ausgabtabellen]\n"

    all_writes: set[str] = set()
    for _, _, _, writes in entries:
        all_writes.update(writes)
    for table in sorted(all_writes):
        md += f"        {table}\n"

    md += "    end\n"
    md += "```\n\n"
    return md


def generate_data_flow_diagram() -> str:
    """Mermaid data-flow diagram, one flowchart per pipeline stage.

    A single diagram over all ~385 scripts exceeds Mermaid's default
    maxTextSize (50000 chars) and stops rendering ("Maximum text size in
    diagram exceeded"). Splitting by pipeline stage keeps every individual
    diagram small and renderable as the script count keeps growing.
    """
    by_stage: "dict[str, list[tuple[str, str, list[str], list[str]]]]" = defaultdict(list)
    for source in _tracked_scripts():
        try:
            doc = ast.get_docstring(ast.parse(source.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
        if not doc:
            continue
        fields = parse_docstring(doc)
        entry = (source.stem, fields.get("tier"), fields.get("reads_raw", []), fields.get("writes", []))
        by_stage[_pipeline_stage(source)].append(entry)

    md = "# Datenfluss-Diagramm\n\n"
    md += "*Mermaid-Code für Visualisierung, aufgeteilt nach Pipeline-Stufe*\n\n"

    for stage_dir, title in _PIPELINE_STAGES:
        stage_entries = by_stage.pop(stage_dir, [])
        if stage_entries:
            md += _render_stage_diagram(title, stage_entries)

    other_entries = [e for group in by_stage.values() for e in group]
    if other_entries:
        md += _render_stage_diagram(_OTHER_STAGE_LABEL, other_entries)

    return md


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate bilingual docs from docstrings.")
    ap.add_argument("paths", nargs="*",
                    help="script files (default: all converted scripts, auto-discovered)")
    ap.add_argument("--check", action="store_true",
                    help="fail if docs are stale or required fields missing (no writes)")
    args = ap.parse_args()

    if args.paths:
        sources = [Path(p).resolve() for p in args.paths]
    else:
        sources = discover()

    problems: list[str] = []
    for src in sources:
        problems.extend(process(src, args.check))

    # Check for orphaned docs (generated docs without source scripts)
    if not args.paths:  # Only check orphans on full run, not with explicit paths
        orphans = check_orphaned_docs()
        if args.check:
            # In check mode, add orphans to problems list
            for orphan in orphans:
                problems.append(f"{orphan}: orphaned (no source script)")
        elif orphans:
            # In generation mode without paths, print warning list
            print("WARNING: orphaned documentation files found (no source script):", file=sys.stderr)
            for orphan in orphans:
                print(f"  {orphan}", file=sys.stderr)
            print("  Run 'git rm <file>' to remove them.", file=sys.stderr)

        # Aggregate data-flow diagram (only on a full run, same as orphans).
        # Skipped entirely while docs/generated/ is gitignored (2026-09-28,
        # generator has no bilingual output yet) -- otherwise --check would
        # permanently report the untracked file as "out of date" on every
        # fresh checkout, since there is nothing to compare it against.
        is_gitignored = subprocess.run(
            ["git", "check-ignore", "-q", str(DATA_FLOW_PATH)],
            cwd=REPO, check=False,
        ).returncode == 0
        if not is_gitignored:
            diagram = generate_data_flow_diagram()
            rel = DATA_FLOW_PATH.relative_to(REPO).as_posix()
            if args.check:
                existing = DATA_FLOW_PATH.read_text(encoding="utf-8") if DATA_FLOW_PATH.exists() else None
                if existing != diagram:
                    problems.append(f"{rel}: out of date")
            else:
                DATA_FLOW_PATH.parent.mkdir(parents=True, exist_ok=True)
                DATA_FLOW_PATH.write_text(diagram, encoding="utf-8")

    if problems:
        for p in problems:
            print(("STALE " if args.check else "FAIL  ") + p, file=sys.stderr)
        return 1
    action = "checked" if args.check else "generated"
    print(f"OK: {action} docs for {len(sources)} script(s) x {len(LANGS)} language(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
