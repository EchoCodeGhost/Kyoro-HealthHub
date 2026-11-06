#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
resolve_pseudonym.py — Pseudonyme (DEV-/PER-/PRV-/SRC-) menschenfreundlich zurückauflösen

@tier        infrastructure
@purpose.de  Löst ein oder mehrere Pseudonyme JEDER im Projekt verwendeten
             Art (DEV-/PER-/PRV-/SRC- aus identity.db, SN-/UID- aus
             identity.db-Nebentabellen, LOC- aus location_store.py) zum
             echten Wert auf -- ohne dafür Python-Snippets oder rohe
             sqlite3-Abfragen schreiben zu müssen
             (modules.identity_resolver.reverse_resolve() existiert schon,
             hatte aber keinen CLI-Einstiegspunkt für Menschen, die einfach
             nur "was bedeutet PRV-701ef95f?" fragen wollen). LOC-Tokens
             (GPS-Grid-Zellen) werden bewusst NICHT aufgelöst, siehe
             @limits -- die sind by design irreversibel, kein fehlendes
             Feature.
@purpose.en  Resolves one or more pseudonyms of EVERY type used in the
             project (DEV-/PER-/PRV-/SRC- from identity.db, SN-/UID- from
             identity.db side tables, LOC- from location_store.py) back to
             their real value -- without having to write Python snippets or
             raw sqlite3 queries (modules.identity_resolver.reverse_resolve()
             already existed, but had no CLI entry point for someone who
             just wants to ask "what does PRV-701ef95f mean?"). LOC- tokens
             (GPS grid cells) are deliberately NOT resolved, see @limits --
             they're irreversible by design, not a missing feature.
@method.de   Zwei Modi: Pseudonyme direkt als Argumente ("resolve_pseudonym.py
             PRV-701ef95f SRC-6d5bc39f"), ODER ohne Argumente von stdin lesen
             und per Regex ALLE Pseudonym-Treffer (unabhängig vom Präfix)
             im Text finden -- damit kann man z.B. eine ganze Kandidaten-
             JSON oder eine "grep icd_catalog_flag ..."-Ausgabe
             durchpipen, ohne die Pseudonyme vorher händisch
             heraussuchen zu müssen. Jedes gefundene Pseudonym wird GENAU
             EINMAL aufgelöst (Mehrfachtreffer werden deduplizert), die
             Zuordnung über modules.identity_resolver.reverse_resolve()
             (bestimmt die Tabelle automatisch aus dem Präfix).
@method.en   Two modes: pseudonyms given directly as arguments
             ("resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f"), OR with no
             arguments, read from stdin and regex-match ALL pseudonym hits
             (any prefix) in the text -- so you can pipe a whole candidate
             JSON or a "grep icd_catalog_flag ..." output through it
             without first hunting down the pseudonyms by hand. Each
             pseudonym found is resolved EXACTLY ONCE (duplicates are
             deduplicated), via modules.identity_resolver.reverse_resolve()
             (determines the table automatically from the prefix).
@reads       ~/.config/kyoro/identity.db (über modules.identity_resolver)
@writes      keine Tabellen (reiner Lookup nach stdout)
@limits.de   Löst nur auf, was in der lokalen identity.db steht -- ein
             Pseudonym aus einer anderen Installation/einem anderen Salt
             ergibt "nicht gefunden", keinen Fehler. Erkennt Pseudonyme rein
             per Muster (Präfix + 8 Hex-Zeichen) -- ein zufällig gleich
             aussehender String, der kein echtes Pseudonym ist, würde als
             "nicht gefunden" gemeldet, nicht als ungültiges Eingabeformat
             erkannt. LOC-Token (GPS-Grid-Zellen aus location_store.py)
             werden absichtlich NIE aufgelöst -- Präzision wird dort laut
             eigenem Moduldocstring "IMMER vor dem Schreiben angewendet und
             ist irreversibel", ein anderer Mechanismus als die 1:1-
             Pseudonyme in identity.db, kein Bug dieses Skripts.
@limits.en   Only resolves what's in the local identity.db -- a pseudonym
             from a different installation/different salt yields "not
             found", not an error. Detects pseudonyms purely by pattern
             (prefix + 8 hex chars) -- a coincidentally similar-looking
             string that isn't a real pseudonym would also be reported as
             "not found", not flagged as an invalid input format. LOC-
             tokens (GPS grid cells from location_store.py) are
             deliberately NEVER resolved -- per that module's own
             docstring, precision there is "ALWAYS applied before writing
             and is irreversible", a different mechanism than the 1:1
             pseudonyms in identity.db, not a bug in this script.

@relevance.de  Macht das Zurückauflösen von Pseudonymen alltagstauglich, essentiell damit Review-Arbeit an pseudonymisierten Kandidaten-JSONs nicht ständig Python-Snippets erfordert
@relevance.en  Makes resolving pseudonyms practical for everyday use, essential so review work on pseudonymized candidate JSONs doesn't constantly require Python snippets
@usage
    python3 resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f
    grep icd_catalog_flag kandidaten.json | python3 resolve_pseudonym.py
    cat kandidaten.json | python3 resolve_pseudonym.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.identity_resolver import reverse_resolve  # noqa: E402

# Hex-Teil case-insensitive -- identity.db-Hauptpseudonyme (DEV/PER/PRV/SRC)
# sind immer kleinschreibend (hashlib.hexdigest()), device_serial_map (SN-)
# dagegen grossschreibend -- ein einzelnes Muster fuer beide statt zwei.
PSEUDONYM_RE = re.compile(r"\b(?:DEV|PER|PRV|SRC|SN|UID|LOC)-[0-9a-fA-F]{8}\b")

_CATEGORY_LABELS_DE = {
    "DEV": "Gerät", "PER": "Person", "PRV": "Praxis/Labor", "SRC": "Quelldatei",
    "SN": "Geräte-Seriennummer", "UID": "App-/Dienst-Konto", "LOC": "GPS-Grid-Zelle",
}
_CATEGORY_LABELS_EN = {
    "DEV": "device", "PER": "person", "PRV": "practice/lab", "SRC": "source file",
    "SN": "device serial number", "UID": "app/service account", "LOC": "GPS grid cell",
}

# siehe @limits -- LOC ist absichtlich nie aufloesbar (UID war es wegen
# eines Spaltennamen-Bugs in identity_resolver.py's account_pseudo_map-
# Abfrage auch nicht, inzwischen dort gefixt).
_NOT_RESOLVABLE_DE = {
    "LOC": "bewusst irreversibel (Grid-Zellen-Token, keine 1:1-Zuordnung)",
}
_NOT_RESOLVABLE_EN = {
    "LOC": "deliberately irreversible (grid-cell token, not a 1:1 mapping)",
}


def resolve_and_print(pseudonyms: list[str], lang: str) -> None:
    labels = _CATEGORY_LABELS_DE if lang == "de" else _CATEGORY_LABELS_EN
    not_resolvable = _NOT_RESOLVABLE_DE if lang == "de" else _NOT_RESOLVABLE_EN
    width = max((len(p) for p in pseudonyms), default=0)
    for p in pseudonyms:
        category = p.split("-", 1)[0]
        label = labels.get(category, category)
        if category in not_resolvable:
            value = not_resolvable[category]
        else:
            real = reverse_resolve(p)
            value = real if real is not None else t("nicht gefunden", "not found")
        print(f"{p:<{width}}  ({label})  -> {value}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=t(
        "Pseudonyme jeder Art (DEV-/PER-/PRV-/SRC-/SN-/UID-/LOC-) zurückauflösen",
        "Resolve pseudonyms of any type (DEV-/PER-/PRV-/SRC-/SN-/UID-/LOC-) back to their real value",
    ))
    parser.add_argument("pseudonyms", nargs="*",
                         help=t("Ein oder mehrere Pseudonyme. Ohne Angabe: von stdin lesen und alle finden.",
                                "One or more pseudonyms. If omitted: read stdin and find all."))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de") or "de"

    if args.pseudonyms:
        found = args.pseudonyms
    else:
        text = sys.stdin.read()
        # dict.fromkeys statt set() -- Fundreihenfolge im Text bleibt erhalten,
        # leichter nachvollziehbar als eine beliebig sortierte Menge.
        found = list(dict.fromkeys(PSEUDONYM_RE.findall(text)))
        if not found:
            print(t("Keine Pseudonyme im Eingabetext gefunden.",
                    "No pseudonyms found in the input text."))
            return

    resolve_and_print(found, lang)


if __name__ == "__main__":
    main()
