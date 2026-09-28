#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Lightweight, no-API-key check: does every DOI declared in a module's @refs
actually exist?

This is deliberately NOT a replacement for tools/verify_refs.py — that does
semantic verification (does the identifier point to *this specific* paper)
via Perplexity, needs an API key, and is explicitly a pre-release gate, not
a per-commit check. This script only asks a much cheaper question: does the
identifier exist at all? It queries the Crossref REST API
(api.crossref.org/works/{doi}) rather than following the doi.org redirect
directly — a direct doi.org GET was tried first and produced a ~61% false
positive rate live in this project, because several publishers behind the
redirect block non-browser HTTP clients (Cloudflare/bot-protection) and
return non-2xx even for DOIs that demonstrably exist. Crossref is the DOI
registration agency's own metadata API, has no such blocking, and answers
the "does it exist" question directly. Cheap enough to run regularly (CI,
a schedule, or by hand) without API cost or rate limits.

A clean run here is NOT proof the citations are correct — only that the
identifiers point to *something*. Semantic correctness is still
verify_refs.py's job.

Usage:
  python3 tools/check_doi_resolves.py
  python3 tools/check_doi_resolves.py --timeout 20
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "scripts"))

from verify_refs import collect_refs  # noqa: E402  (reuse the same @refs discovery)

_DOI_RE = re.compile(r"doi:\s*(10\.\d{4,9}/[^\s;]+)", re.IGNORECASE)
# Only matches the real DOI shape (registrant prefix "10.xxxx/..."), not
# every "doi:"-prefixed identifier — some @refs deliberately use "doi:" as
# a stand-in label for a URL-based identifier (WHO IRIS handles) or an
# explicit "doi: nicht verfügbar" note for sources that never had a DOI
# (see check_docstrings.py, which requires the literal substring "doi:" to
# be present even in that case). Matching those loosely as if they were
# DOIs and sending them to Crossref/DataCite produced 100% false "broken"
# reports here, since neither API can ever resolve a non-DOI string.


def _clean_doi(raw: str) -> str:
    """Strip trailing sentence punctuation without truncating DOIs that
    legitimately contain parentheses themselves — the common Elsevier
    style `10.1016/S0140-6736(06)69248-1` has one embedded, unlike the
    naive fix of excluding ')' from the match entirely, which chopped
    every such DOI off right after its opening paren. Only strip a
    trailing ')' while it is unbalanced against '(' already captured."""
    doi = raw.rstrip(".,;")
    while doi.count(")") > doi.count("("):
        doi = doi[:-1]
    return doi


def _extract_dois(ref: str) -> list[str]:
    """A single @refs entry can bundle several citations (seen live:
    "Williams et al. 2018 ..., doi:X; Mancia et al. 2013 ..., doi:Y; ...")
    — findall(), not search(), so none of them get silently skipped."""
    return [_clean_doi(doi) for doi in _DOI_RE.findall(ref)]


_UA = {"User-Agent": "Kyoro-HealthHub-ref-check/1.0 (mailto:noreply@localhost)"}


def _query(url: str, timeout: float) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — network errors of any shape count as "can't confirm"
        return False, f"error: {e}"


def _resolves(doi: str, timeout: float) -> tuple[bool, str]:
    """Crossref's own metadata API first, not the doi.org redirect:
    querying doi.org directly was tried first and produced a ~61%
    false-positive rate, because several publishers behind that redirect
    block non-browser HTTP clients (Cloudflare/bot-protection) and return
    non-2xx for DOIs that demonstrably exist. Crossref has no such
    blocking and answers "does this DOI exist" directly.

    Falls back to DataCite on a Crossref miss: Crossref only knows about
    DOIs registered through it (mainly journal articles). DOIs registered
    through DataCite instead — Zenodo records, software/dataset DOIs, seen
    live in this project's own calibration scripts — 404 on Crossref even
    though they are perfectly valid, so a Crossref-only check would falsely
    flag every one of them as broken."""
    ok, detail = _query(f"https://api.crossref.org/works/{doi}", timeout)
    if ok:
        return True, f"crossref: {detail}"
    ok2, detail2 = _query(f"https://api.datacite.org/dois/{doi}", timeout)
    if ok2:
        return True, f"datacite: {detail2}"
    return False, f"crossref: {detail}; datacite: {detail2}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--timeout", type=float, default=10.0,
                     help="Seconds per request (default: 10)")
    args = ap.parse_args()

    all_refs = collect_refs()
    dois: dict[str, list[tuple[str, list[str]]]] = {}
    for ref, srcs in all_refs.items():
        for doi in _extract_dois(ref):
            dois.setdefault(doi, []).append((ref, srcs))

    if not dois:
        print("No DOIs found in @refs.")
        return 0

    print(f"Checking {len(dois)} unique DOI(s)...")
    broken = []
    for doi in sorted(dois):
        ok, detail = _resolves(doi, args.timeout)
        print(f"  {'OK  ' if ok else 'FAIL'} {doi}  ({detail})")
        if not ok:
            broken.append((doi, detail))

    if broken:
        print(f"\n{len(broken)} of {len(dois)} DOI(s) do not resolve:")
        for doi, detail in broken:
            print(f"\n  {doi}  ({detail})")
            for ref, srcs in dois[doi]:
                print(f"    - {ref}")
                for s in sorted(set(srcs)):
                    print(f"        used by: {s}")
        return 1

    print("\nAll DOIs resolve. (Not a correctness check — see module docstring.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
