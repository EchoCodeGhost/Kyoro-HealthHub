#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Verify the academic references (@refs) declared in module docstrings against
Perplexity's online search, and write a human-reviewable verification report.

This is a PRE-RELEASE gate, not a per-commit check: it needs network access and a
Perplexity API key, and references change rarely. Run it before publishing.

Only public citation strings (author, year, journal, DOI) are sent to the API —
no personal or health data.

Usage:
  python3 tools/verify_refs.py                 # verify all @refs, write report
  python3 tools/verify_refs.py --dry-run       # list refs + targets, no API calls
  python3 tools/verify_refs.py --only-broken   # only refs tools/check_doi_resolves.py
                                                # flagged as not resolving — cheaper,
                                                # since a DOI that already fails the free
                                                # existence check doesn't need a paid
                                                # semantic check to know something's wrong,
                                                # only to find out what the fix is

Requires  llm.perplexity_api_key  in ~/.config/kyoro/health_config.json.
"""

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from gen_docs import discover, parse_docstring  # noqa: E402
import ast  # noqa: E402

REPORT = REPO / "docs" / "references" / "verification_DE.md"

# Real DOI shape only ("10.xxxx/..."). Duplicated from check_doi_resolves.py's
# _DOI_RE rather than imported at module level, for the same reason that
# file's own import of collect_refs from here is done lazily inside a
# function — importing check_doi_resolves at module load time would create
# a circular import. Loosely matching "doi:<anything>" instead would treat
# deliberate non-DOI identifiers (WHO IRIS handles, "doi: nicht verfügbar"
# notes) as verifiable DOIs and send them to Perplexity as if broken.
_DOI_RE = re.compile(r"doi:\s*(10\.\d{4,9}/[^\s;]+)", re.IGNORECASE)

_SYSTEM = (
    "You verify academic citations. For the given citation and its claimed "
    "identifier (DOI or PMC ID), determine whether the identifier resolves to "
    "exactly that paper. Answer in this exact format:\n"
    "STATUS: OK | WRONG | UNCERTAIN\n"
    "CORRECT_ID: <the correct DOI/PMC if WRONG, else '-'>\n"
    "NOTE: <one short sentence, name the actual title the identifier points to>"
)


def collect_refs() -> dict[str, list[str]]:
    """{ reference line : [scripts that declare it] }."""
    refs: dict[str, list[str]] = {}
    for src in discover():
        doc = ast.get_docstring(ast.parse(src.read_text(encoding="utf-8")))
        for r in parse_docstring(doc).get("refs", []):
            rel = src.relative_to(REPO).as_posix()
            refs.setdefault(r.strip(), []).append(rel)
    return refs


def _extract_final_verdict(answer: str) -> str:
    """Some models ramble/self-correct before settling on an answer, repeating
    the STATUS/CORRECT_ID/NOTE block multiple times with "wait, let me
    recheck"-style reasoning in between (observed live: a single query about
    Mäkikallio et al. 1998 produced ~190 lines of repeated self-correction
    before verification.md truncated it at max_tokens). Writing that verbatim
    turns a report meant to be human-reviewable into noise. Split on each
    line starting with "STATUS:" and keep only the last chunk — the model's
    own final, settled answer — instead of the full reasoning trace."""
    parts = re.split(r"(?=^STATUS:)", answer, flags=re.MULTILINE)
    return parts[-1].strip() if len(parts) > 1 else answer.strip()


def _provider():
    from utils.llm_provider import _load_raw, _PerplexityProvider
    llm = _load_raw().get("llm", {})
    if not llm.get("perplexity_api_key"):
        sys.exit(
            "ERROR: llm.perplexity_api_key not set in ~/.config/kyoro/health_config.json.\n"
            "       Add it under the \"llm\" section, then re-run."
        )
    return _PerplexityProvider(llm)


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify docstring @refs via Perplexity.")
    ap.add_argument("--dry-run", action="store_true", help="list refs, no API calls")
    ap.add_argument("--only-broken", action="store_true",
                     help="restrict to refs whose DOI fails tools/check_doi_resolves.py "
                          "(Crossref/DataCite existence check) — cheaper than verifying "
                          "every ref when most already resolve fine")
    args = ap.parse_args()

    all_refs = collect_refs()
    # Only citations carrying a resolvable identifier are verifiable.
    refs = {r: s for r, s in all_refs.items() if _DOI_RE.search(r) or re.search(r"PMC\d", r)}
    skipped = {r: s for r, s in all_refs.items() if r not in refs}

    if args.only_broken:
        from check_doi_resolves import _extract_dois, _resolves  # local: avoids a
        # module-load-time circular import, since check_doi_resolves imports
        # collect_refs from this module
        broken = {}
        for ref, srcs in refs.items():
            dois = _extract_dois(ref)
            if dois and not any(_resolves(d, 10.0)[0] for d in dois):
                broken[ref] = srcs
        refs = broken
    if not refs and not skipped:
        print("No @refs found in converted docstrings.")
        return 0

    print(f"{len(refs)} verifiable / {len(all_refs)} total reference(s) "
          f"across {len(discover())} script(s).")
    if skipped:
        print(f"  ({len(skipped)} without DOI/PMC identifier — not sent to API)")
    if args.dry_run:
        for r, srcs in sorted(refs.items()):
            print(f"  - {r}\n      used by: {', '.join(sorted(set(srcs)))}")
        for r in sorted(skipped):
            print(f"  - [no identifier] {r}")
        return 0

    provider = _provider()
    lines = [
        "# Reference verification",
        "",
        "> Generated by `tools/verify_refs.py` via Perplexity. Human review required "
        "before release — the model can also err.",
        "",
    ]
    flagged = 0
    for ref, srcs in sorted(refs.items()):
        ident = re.search(r"(?:doi:\s*|PMC)\S+", ref)
        query = (
            f"Citation: {ref}\n"
            f"Claimed identifier: {ident.group(0) if ident else '(none stated)'}\n"
            "Does the identifier resolve to exactly this paper?"
        )
        try:
            answer = provider.chat(_SYSTEM, query, max_tokens=400).strip()
        except Exception as e:  # noqa: BLE001
            answer = f"STATUS: UNCERTAIN\nCORRECT_ID: -\nNOTE: API error: {e}"
        answer = _extract_final_verdict(answer)
        status = "UNCERTAIN"
        m = re.search(r"STATUS:\s*(OK|WRONG|UNCERTAIN)", answer)
        if m:
            status = m.group(1)
        if status != "OK":
            flagged += 1
        mark = {"OK": "OK  ", "WRONG": "FAIL", "UNCERTAIN": "?   "}[status]
        print(f"  {mark} {ref}")
        lines.append(f"## {ref}")
        lines.append("")
        lines.append(f"Declared in: {', '.join(sorted(set(srcs)))}")
        lines.append("")
        lines.append("```")
        lines.append(answer)
        lines.append("```")
        lines.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT.relative_to(REPO).as_posix()}  "
          f"({flagged} of {len(refs)} not confirmed OK)")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
