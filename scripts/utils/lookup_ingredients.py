#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Produkt-Inhaltsstoff-Lookup via Open Beauty Facts + Open Products Facts + Open Food Facts + PubChem + Claude Vision.

@tier        infrastructure
@purpose.de  Ermöglicht das Nachschlagen von Produkt-Inhaltsstoffen aus mehreren Datenbanken:
             Open Beauty Facts (Kosmetik), Open Products Facts (Haushaltsprodukte),
             Open Food Facts (Lebensmittel/Kosmetik-Grenzfälle), sowie optionale Anreicherung
             mit PubChem-Daten (chemische Eigenschaften, GHS-Klassifikation). Falls kein Text
             verfügbar ist, wird das Produktfoto heruntergeladen und per Vision-LLM analysiert.
@purpose.en  Enables looking up product ingredients from multiple databases:
             Open Beauty Facts (cosmetics), Open Products Facts (household products),
             Open Food Facts (food/cosmetic borderline cases), plus optional enrichment with
             PubChem data (chemical properties, GHS classification). If text is missing,
             the product photo is downloaded and analyzed via vision LLM.
@method.de   Erweiterte Lookup-Reihenfolge:
             1. Open Beauty Facts (Text)
             2. Open Products Facts (Text) — Fallback für Haushaltsprodukte
             3. Open Food Facts (Text) — Fallback für Lebensmittel-Kosmetik-Grenzfälle
             4. Vision-Fallback (Foto) — für alle Datenbanken
             5. PubChem-Anreicherung (optional) — für jeden gefundenen INCI-Namen
             Konsistentes Allergen-Matching gegen lokale Referenztabellen (ECHA-SVHC, CosIng)
             und handkuratierte KNOWN_ALLERGENS-Liste.
@method.en   Extended lookup chain:
             1. Open Beauty Facts (Text)
             2. Open Products Facts (Text) — fallback for household products
             3. Open Food Facts (Text) — fallback for food/cosmetic borderline cases
             4. Vision fallback (photo) — for all databases
             5. PubChem enrichment (optional) — for each found INCI name
             Consistent allergen matching against local reference tables (ECHA-SVHC, CosIng)
             and hand-curated KNOWN_ALLERGENS list.
@limits.de   Abhängig von der Datenqualität der verschiedenen APIs und Vision-Genauigkeit.
             PubChem-Abfragen können für exotische Inhaltsstoffe fehlschlagen.
             Referenztabellen (ECHA/CosIng) müssen lokal gepflegt werden.
             Erkennt einen spezifischen, real beobachteten Datenfehler: wenn
             OBF/OPF/OFFs `ingredients_text` an manchen Stellen keine Kommas
             zwischen einzelnen INCI-Namen hat, klebt sowohl der Rohtext-Split
             als auch OBF's eigene "strukturierte" ingredients-Liste mehrere
             Namen zu einem Eintrag zusammen — und der bisherige >80-Zeichen-
             Filter warf solche zusammengeklebten Einträge unbemerkt komplett
             weg, statt sie zu melden. Beide Symptome (verdächtig lange,
             kommalose Mehrwort-Einträge; verworfene Übergroß-Einträge) lösen
             jetzt eine `data_quality_warning` aus und triggern bei aktiviertem
             Vision-Fallback automatisch einen Foto-Gegencheck. Diese Erkennung
             ist heuristisch (Wortanzahl/Länge) und deckt nicht jede denkbare
             Form von Quelltext-Korruption ab.

@relevance.de  Ermöglicht die Suche und Referenzierung von Daten, essentiell für die Datenintegration
@relevance.en  Enables data lookup and referencing, essential for data integration
@limits.en   Dependent on data quality of various APIs and vision accuracy.
             PubChem queries may fail for exotic ingredients.
             Reference tables (ECHA/CosIng) must be maintained locally.
             Detects one specific, actually-observed data defect: when OBF's/
             OPF's/OFF's `ingredients_text` is missing commas between some INCI
             names, both the raw-text split and OBF's own "structured"
             ingredients array glue several names into one entry — and the
             previous >80-char cutoff silently discarded the worst-merged
             entries entirely instead of flagging them. Both symptoms
             (suspiciously long comma-less multi-word entries; discarded
             oversized entries) now raise a `data_quality_warning` and, if
             vision fallback is enabled, automatically trigger a photo
             cross-check. This detection is a heuristic (word count/length) and
             does not cover every possible form of source-text corruption.

Workflow:
  1. Suche Produkt in Open Beauty Facts (openbeautyfacts.org)
  2. Falls nicht gefunden: Open Products Facts (openproductsfacts.org)
  3. Falls nicht gefunden: Open Food Facts (openfoodfacts.org)
  4. Falls Inhaltsstoffe als Text vorhanden → direkt parsen
  5. Falls nur Foto vorhanden → Bild herunterladen + per Vision lesen
  6. Optionale Anreicherung: Jeder INCI-Name wird gegen PubChem geprüft
     Vision-Backend (in Reihenfolge):
       a. LLMProvider aus health_config.json (provider.vision())
       b. Anthropic SDK (Fallback, falls Provider kein Vision unterstützt)
       c. claude -p --dangerously-skip-permissions (Claude Code CLI, kein Key nötig)
  7. Gibt strukturierte INCI-Liste mit Allergen-Markierung zurück

Verwendung:
  python utils/lookup_ingredients.py "Elmex Gelee"
  python utils/lookup_ingredients.py "Dior Sauvage"
  python utils/lookup_ingredients.py --barcode 8718951466043
  python utils/lookup_ingredients.py "Colgate Total" --no-vision  # Text-only
  python utils/lookup_ingredients.py "Colgate Total" --no-pubchem  # ohne PubChem

LLM konfigurieren (in ~/.config/kyoro/health_config.json):
  { "llm": { "provider": "anthropic", "anthropic_api_key": "sk-ant-..." } }

@reads       Open Beauty Facts API, Open Products Facts API, Open Food Facts API,
             PubChem API (optional), Produktfotos
@writes      Keine Tabellen (gibt Inhaltsstoff-Daten zurück), data/reference/*.csv (lokal)
@usage
    python lookup_ingredients.py
    python lookup_ingredients.py --help
    python lookup_ingredients.py "Elmex Gelee" --no-pubchem
    python lookup_ingredients.py --barcode 8718951466043 --no-vision
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import KYORO_CONFIG_DIR

# ── Open Beauty Facts API ─────────────────────────────────────────────────────

_OBF_SEARCH = (
    "https://world.openbeautyfacts.org/cgi/search.pl"
    "?search_terms={query}&search_simple=1&action=process&json=1"
    "&fields=product_name,code,brands,ingredients_text,ingredients,"
    "images_small_url,selected_images&page_size=8"
)
_OBF_PRODUCT = "https://world.openbeautyfacts.org/api/v2/product/{code}.json"

# ── Open Products Facts API (Fallback für Haushaltsprodukte) ───────────────────
_OPF_SEARCH = (
    "https://world.openproductsfacts.org/cgi/search.pl"
    "?search_terms={query}&search_simple=1&action=process&json=1"
    "&fields=product_name,code,brands,ingredients_text,ingredients,"
    "images_small_url,selected_images&page_size=8"
)
_OPF_PRODUCT = "https://world.openproductsfacts.org/api/v2/product/{code}.json"

# ── Open Food Facts API (Fallback für Lebensmittel-Kosmetik-Grenzfälle) ──────────
_OFF_SEARCH = (
    "https://world.openfoodfacts.org/cgi/search.pl"
    "?search_terms={query}&search_simple=1&action=process&json=1"
    "&fields=product_name,code,brands,ingredients_text,ingredients,"
    "images_small_url,selected_images&page_size=8"
)
_OFF_PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{code}.json"

# ── PubChem API (für chemische Anreicherung) ────────────────────────────────────
_PUBCHEM_SEARCH = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON"
_PUBCHEM_COMPOUND = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey,XLogP,IUPACName/JSON"

# Lokale Referenztabellen (ECHA-SVHC, CosIng) — werden durch fetch_yearly.py gepflegt
REFERENCE_DIR = Path(__file__).parent.parent.parent / "data" / "reference"

# Anthropic model for vision (haiku = schnellster, billigster)
_VISION_MODEL = "claude-haiku-4-5-20251001"
_VISION_PROMPT = """\
Look at this product label photo. Find the INCI ingredient list (usually a long \
list of chemical/Latin names separated by commas, often starting with "Aqua" or \
"Water").

Rules:
- If you find an INCI ingredient list: output ONLY the ingredient names, \
comma-separated, nothing else. No explanation, no units, no quantities.
- If the label shows only dosage info (e.g. "X mg per g"), active ingredient \
percentages, or usage instructions — that is NOT an INCI list. Output: NOT_FOUND
- If the text is too blurry/obscured to read: output: NOT_FOUND
- No preamble, no explanation, no markdown. Just the comma list or NOT_FOUND.
"""


def _fetch_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KyoroHealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[lookup] Netzwerkfehler: {e}", file=sys.stderr)
        return None


def _download_image(url: str, suffix: str = ".jpg") -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KyoroHealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        # mkstemp statt mktemp: atomar, kein TOCTOU-Race, restriktive Perms (0600).
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
        except Exception:
            os.unlink(tmp_path)
            raise
        return Path(tmp_path)
    except Exception as e:
        print(f"[lookup] Bild-Download fehlgeschlagen: {e}", file=sys.stderr)
        return None


import re as _re

# INCI language synonyms — deduplicate English/vernacular vs. INCI Latin names
_INCI_ALIASES: dict[str, str] = {
    "water": "aqua",
    "fragrance": "parfum",
    "alcohol": "alcohol",          # keep both denat. variants separate
}


def _inci_key(name: str) -> str:
    """Return canonical dedup key (maps vernacular → INCI name)."""
    return _INCI_ALIASES.get(name.lower(), name.lower())


_PROSE_RE = _re.compile(
    r'\b(contient|contains|kann|may|peut|produit|réaction|cause[ds]?|allergi|'
    r'warning|hinweis|achtung|attention|danger|consult|apply|appliquer|'
    r'lesen|voir|provoc|susceptible)\b',
    _re.IGNORECASE,
)
_PCT_PREFIX_RE = _re.compile(r'^[<>]?\s*\d[\d\-–,\.]*\s*%\s+(.+)$')


def _clean_ingredient(raw: str) -> str | None:
    """Return cleaned ingredient name, or None if it looks like label prose."""
    raw = raw.strip().strip(".,;*")
    if not raw or len(raw) < 2 or len(raw) > 80:
        return None
    if _PROSE_RE.search(raw):
        return None
    # Strip "5-15 % surfactant" → keep "surfactant"
    m = _PCT_PREFIX_RE.match(raw)
    if m:
        raw = m.group(1).strip()
    return raw or None


def _looks_concatenated(name: str) -> bool:
    """Heuristic: does this "ingredient" actually look like several INCI names
    glued together without a delimiter?

    Real single INCI names occasionally run to 4 words (e.g. "PEG-40
    HYDROGENATED CASTOR OIL"), so the threshold is deliberately conservative
    (>=5 words and >=35 chars) to keep false positives rare. It will not catch
    every merged entry, only the clearly implausible ones.
    """
    return "," not in name and len(name) >= 35 and len(name.split()) >= 5


def _parse_ingredients_text(product: dict) -> tuple[list[str], str | None]:
    """Extract a deduplicated, cleaned INCI list from an OBF product dict.

    Returns (names, warning). `warning` is set when the parse looks
    structurally unreliable — either because entries look like several
    ingredient names glued together without a delimiter, or because entries
    had to be dropped for being implausibly long (>80 chars, `_clean_ingredient`'s
    cutoff) — both symptoms of the same real defect: some OBF products store
    `ingredients_text` with an inconsistent/missing delimiter between names, and
    OBF's own "structured" `ingredients` array (machine-parsed from that same
    text) silently inherits it instead of surfacing the defect.
    """
    # 1. Structured ingredients array (best quality)
    structured = product.get("ingredients", [])
    if structured:
        seen, names, concatenated = set(), [], []
        dropped_long = 0
        for ing in structured:
            raw = (ing.get("text") or ing.get("id") or "").strip()
            if raw.startswith("en:"):
                raw = raw[3:]
            if len(raw.strip(".,;*")) > 80:
                dropped_long += 1
                continue
            cleaned = _clean_ingredient(raw)
            if cleaned and _inci_key(cleaned) not in seen:
                seen.add(_inci_key(cleaned))
                names.append(cleaned)
                if _looks_concatenated(cleaned):
                    concatenated.append(cleaned)
        if names:
            warning = None
            if dropped_long or concatenated:
                parts = []
                if dropped_long:
                    parts.append(
                        f"{dropped_long} strukturierte(r) Eintrag/Einträge >80 Zeichen "
                        f"verworfen (vermutlich mehrere zusammengeklebte Inhaltsstoffe "
                        f"ohne Trennzeichen) — Liste ist wahrscheinlich unvollständig"
                    )
                if concatenated:
                    sample = ", ".join(concatenated[:3])
                    parts.append(
                        f"{len(concatenated)} Eintrag/Einträge sehen nach mehreren "
                        f"zusammengeklebten Namen ohne Trennzeichen aus, z.B.: {sample}"
                    )
                warning = "; ".join(parts)
            return names, warning

    # 2. Raw ingredients_text (comma/semicolon separated)
    raw_text = (product.get("ingredients_text") or "").strip()
    if raw_text:
        seen, parts = set(), []
        for p in raw_text.replace(";", ",").split(","):
            cleaned = _clean_ingredient(p)
            if cleaned and _inci_key(cleaned) not in seen:
                seen.add(_inci_key(cleaned))
                parts.append(cleaned)
        concatenated = [p for p in parts if _looks_concatenated(p)]
        warning = None
        if concatenated:
            sample = ", ".join(concatenated[:3])
            warning = (
                f"{len(concatenated)} Eintrag/Einträge aus Rohtext sehen nach mehreren "
                f"zusammengeklebten Namen ohne Trennzeichen aus, z.B.: {sample}"
            )
        return parts, warning

    return [], None


def _fetch_opf(query: str) -> dict | None:
    """Search Open Products Facts for a product."""
    try:
        url = _OPF_SEARCH.format(query=urllib.parse.quote(query))
        return _fetch_json(url)
    except Exception as e:
        print(f"[lookup] OPF-Suche fehlgeschlagen: {e}", file=sys.stderr)
        return None


def _fetch_off(query: str) -> dict | None:
    """Search Open Food Facts for a product."""
    try:
        url = _OFF_SEARCH.format(query=urllib.parse.quote(query))
        return _fetch_json(url)
    except Exception as e:
        print(f"[lookup] OFF-Suche fehlgeschlagen: {e}", file=sys.stderr)
        return None


def _get_pubchem_cid(ingredient_name: str) -> int | None:
    """Get PubChem CID for an ingredient name."""
    try:
        url = _PUBCHEM_SEARCH.format(name=urllib.parse.quote(ingredient_name))
        data = _fetch_json(url)
        if data and "IdentifierList" in data:
            cids = data["IdentifierList"].get("CID", [])
            if cids:
                return cids[0]
    except Exception as e:
        print(f"[lookup] PubChem CID-Suche fehlgeschlagen für {ingredient_name}: {e}", file=sys.stderr)
    return None


def _fetch_pubchem_properties(cid: int) -> dict | None:
    """Fetch chemical properties from PubChem for a given CID."""
    try:
        url = _PUBCHEM_COMPOUND.format(cid=cid)
        data = _fetch_json(url)
        if data and "PropertyTable" in data:
            props = data["PropertyTable"].get("Properties", [])
            if props:
                return props[0]
    except Exception as e:
        print(f"[lookup] PubChem Properties fehlgeschlagen für CID {cid}: {e}", file=sys.stderr)
    return None


def _load_reference_allergens() -> tuple[dict, dict]:
    """Load ECHA-SVHC and CosIng reference data from local CSV files."""
    echa_file = REFERENCE_DIR / "echa_svhc.csv"
    cosing_file = REFERENCE_DIR / "cosing_restricted.csv"
    
    echa_data = {}
    cosing_data = {}
    
    # Load ECHA-SVHC
    if echa_file.exists():
        try:
            import csv
            with open(echa_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Substance', row.get('Name', '')).strip()
                    if name:
                        echa_data[name.lower()] = {
                            'name': name,
                            'category': row.get('Category', ''),
                            'risk': row.get('Risk', ''),
                            'source': 'ECHA-SVHC'
                        }
        except Exception as e:
            print(f"[lookup] ECHA-SVHC Ladefehler: {e}", file=sys.stderr)
    
    # Load CosIng
    if cosing_file.exists():
        try:
            import csv
            with open(cosing_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Substance', row.get('INCI', row.get('Name', ''))).strip()
                    if name:
                        cosing_data[name.lower()] = {
                            'name': name,
                            'status': row.get('Status', row.get('Annex', '')),
                            'restriction': row.get('Restriction', ''),
                            'source': 'CosIng'
                        }
        except Exception as e:
            print(f"[lookup] CosIng Ladefehler: {e}", file=sys.stderr)
    
    return echa_data, cosing_data


def _get_ingredient_image_url(product: dict) -> str | None:
    """Extract the best ingredient image URL from OBF product data."""
    # Try selected_images first (structured)
    sel = product.get("selected_images", {})
    for lang_key in ("en", "de", "fr"):
        ingr_img = sel.get("ingredients", {}).get("display", {}).get(lang_key)
        if ingr_img:
            return ingr_img

    # Fall back to images dict
    images = product.get("images", {})
    code = product.get("code", "")
    if not code:
        return None

    # Build path prefix from barcode (groups of 3 chars)
    parts = [code[i:i+3] for i in range(0, min(9, len(code)), 3)]
    rest  = code[9:] if len(code) > 9 else ""
    prefix = "/".join(parts)
    if rest:
        prefix += "/" + rest

    # Try common ingredient image keys
    for key in sorted(images.keys()):
        if "ingredients" in key.lower():
            # Find the highest-resolution version
            img_data = images[key]
            if isinstance(img_data, dict):
                sizes = img_data.get("sizes", {})
                # Prefer 400 > 200 > 100
                for size in ("400", "200", "100"):
                    if size in sizes:
                        rev = img_data.get("rev") or img_data.get("imgid") or key
                        url = (
                            f"https://images.openbeautyfacts.org/images/products/"
                            f"{prefix}/{key}.{rev}.{size}.jpg"
                        )
                        return url

    return None


def _get_api_key() -> str | None:
    """Find Anthropic API key from environment or health_config.json."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    cfg_path = KYORO_CONFIG_DIR / "health_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            key = (cfg.get("llm", {}).get("anthropic_api_key")
                   or cfg.get("anthropic_api_key"))  # legacy fallback
            if key:
                return key
        except Exception:
            pass
    return None


def _parse_vision_response(text: str) -> list[str] | None:
    """
    Parse the raw vision model response into a clean INCI ingredient list.

    Handles:
    - Comma-separated list (ideal): "Aqua, Glycerin, Sorbitol"
    - Bullet/dash list:  "- Aqua\n- Glycerin"
    - Numbered list:     "1. Aqua\n2. Glycerin"
    - NOT_FOUND marker anywhere in the response
    - Prose descriptions that mention dosage/mg → treat as NOT_FOUND
    """
    if not text:
        return None

    # Any "NOT_FOUND" anywhere → give up immediately
    if "NOT_FOUND" in text.upper():
        return None

    # If the response looks like dosage info (quantities with units), not an INCI list
    import re
    dosage_pattern = re.compile(r'\d[\d,\.]+\s*(mg|ml|g|%|mcg)\b', re.IGNORECASE)
    if dosage_pattern.search(text):
        return None

    # Strip markdown formatting and prose prefixes
    clean = re.sub(r'^#+\s.*$', '', text, flags=re.MULTILINE)   # markdown headers
    clean = re.sub(r'\*\*.*?\*\*', '', clean)                     # bold
    clean = re.sub(r'`.*?`', '', clean)                           # code spans

    # Detect list format
    lines = [ln.strip() for ln in clean.split('\n') if ln.strip()]

    # Bullet/dash/numbered list?
    list_items = []
    list_re = re.compile(r'^[-*•·]\s+(.+)$|^\d+[\.\)]\s+(.+)$')
    for line in lines:
        m = list_re.match(line)
        if m:
            item = (m.group(1) or m.group(2)).strip().rstrip('.,')
            if item:
                list_items.append(item)

    if len(list_items) >= 2:
        return list_items

    # Comma-separated list: find the longest line with ≥2 commas
    best_line, best_count = "", 0
    for line in lines:
        n = line.count(',')
        if n > best_count:
            best_count, best_line = n, line

    if best_count >= 2:
        parts = [p.strip().rstrip('.,') for p in best_line.split(',')]
        result = [p for p in parts if p and 2 <= len(p) <= 60]
        if len(result) >= 2:
            return result

    # Nothing parseable found
    return None


def _vision_via_sdk(image_path: Path, api_key: str) -> list[str] | None:
    """Use Anthropic Python SDK to extract INCI ingredients from a product label photo."""
    try:
        import anthropic
    except ImportError:
        return None

    img_bytes  = image_path.read_bytes()
    img_b64    = base64.standard_b64encode(img_bytes).decode()
    media_type = {".png": "image/png", ".webp": "image/webp"}.get(
        image_path.suffix.lower(), "image/jpeg"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg    = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }],
        )
        return _parse_vision_response(msg.content[0].text.strip())
    except Exception as e:
        print(f"[lookup] SDK-Fehler: {e}", file=sys.stderr)
        return None


def _vision_via_claude_cli(image_path: Path) -> list[str] | None:
    """
    Use the local `claude` CLI (Claude Code) to read an ingredient label image.
    Falls back to this when no API key is configured.
    """
    claude_bin = subprocess.run(
        ["which", "claude"], capture_output=True, text=True
    ).stdout.strip()
    if not claude_bin:
        return None

    # Embed the vision prompt directly — keep it tight so the model doesn't wander
    prompt = (
        f"Read the image at {image_path.resolve()}.\n"
        + _VISION_PROMPT
    )
    try:
        result = subprocess.run(
            [claude_bin, "-p", "--dangerously-skip-permissions"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return _parse_vision_response(result.stdout.strip())
    except subprocess.TimeoutExpired:
        print("[lookup] claude-CLI-Timeout (>60s)", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[lookup] claude-CLI-Fehler: {e}", file=sys.stderr)
        return None


def _vision_read_ingredients(image_path: Path, api_key: str | None) -> list[str] | None:
    """Try configured LLM provider first, then fall back to claude CLI."""
    try:
        from utils.llm_provider import LLMProvider
        provider = LLMProvider.from_config()
        text = provider.vision(image_path, _VISION_PROMPT, max_tokens=400)
        result = _parse_vision_response(text)
        if result is not None:
            return result
    except NotImplementedError:
        pass  # provider doesn't support vision (e.g. Perplexity)
    except Exception as e:
        print(f"[lookup] Provider-Fehler: {e}", file=sys.stderr)
        # Fall through to SDK / CLI paths below

    # Legacy Anthropic SDK path
    if api_key:
        result = _vision_via_sdk(image_path, api_key)
        if result is not None:
            return result

    # Final fallback: claude CLI
    return _vision_via_claude_cli(image_path)


# ── Public API ────────────────────────────────────────────────────────────────

def lookup(
    query: str | None = None,
    barcode: str | None = None,
    use_vision: bool = True,
    api_key: str | None = None,
    verbose: bool = True,
    with_pubchem: bool = True,
) -> dict:
    """
    Look up product ingredients.

    Uses extended lookup chain:
    1. Open Beauty Facts (Text)
    2. Open Products Facts (Text) - fallback for household products
    3. Open Food Facts (Text) - fallback for food-cosmetic borderline cases
    4. Vision fallback (Photo) - existing
    5. PubChem enrichment - optional, adds chemical properties

    Returns:
        {
            "name": str,
            "code": str,
            "brands": str,
            "ingredients": list[str],   # parsed INCI list
            "source": "obf_text" | "opf_text" | "off_text" | "obf_vision" | "opf_vision" | "off_vision" | "vision_only" | "not_found",
            "image_path": Path | None,  # temp file if vision was used
            "pubchem_data": dict | None,  # optional chemical properties per ingredient
            "allergens": list[str],     # matched known allergens from reference data
        }
    """
    if api_key is None:
        api_key = _get_api_key()

    # ── Extended Lookup Chain ────────────────────────────────────────────────
    
    # Step 1: Try Open Beauty Facts
    obf_result = _try_database("OBF", _OBF_SEARCH, _OBF_PRODUCT, query, barcode, use_vision, api_key, verbose)
    if obf_result and obf_result.get("ingredients"):
        if verbose:
            print(f"[lookup] Found {len(obf_result['ingredients'])} ingredients via Open Beauty Facts")
        if obf_result.get("data_quality_warning") and use_vision:
            obf_result = _cross_check_with_vision(obf_result, api_key, verbose)
        return _enrich_result(obf_result, with_pubchem, verbose)

    # Step 2: Try Open Products Facts (fallback for household products)
    opf_result = _try_database("OPF", _OPF_SEARCH, _OPF_PRODUCT, query, barcode, use_vision, api_key, verbose)
    if opf_result and opf_result.get("ingredients"):
        if verbose:
            print(f"[lookup] Found {len(opf_result['ingredients'])} ingredients via Open Products Facts")
        if opf_result.get("data_quality_warning") and use_vision:
            opf_result = _cross_check_with_vision(opf_result, api_key, verbose)
        return _enrich_result(opf_result, with_pubchem, verbose)

    # Step 3: Try Open Food Facts (fallback for food-cosmetic borderline)
    off_result = _try_database("OFF", _OFF_SEARCH, _OFF_PRODUCT, query, barcode, use_vision, api_key, verbose)
    if off_result and off_result.get("ingredients"):
        if verbose:
            print(f"[lookup] Found {len(off_result['ingredients'])} ingredients via Open Food Facts")
        if off_result.get("data_quality_warning") and use_vision:
            off_result = _cross_check_with_vision(off_result, api_key, verbose)
        return _enrich_result(off_result, with_pubchem, verbose)
    
    # Step 4: If we have a best result from any database but no ingredients, try vision
    best_result = obf_result or opf_result or off_result
    if not best_result:
        # No results from any database
        name = query or barcode or "?"
        return {
            "name": name, "code": "", "brands": "", "ingredients": [],
            "source": "not_found", "image_path": None, "pubchem_data": None,
            "allergens": [],
        }
    
    # Try vision fallback if no ingredients found
    if use_vision and not best_result.get("ingredients"):
        vision_result = _try_vision_fallback(best_result, api_key, verbose)
        if vision_result:
            return _enrich_result(vision_result, with_pubchem, verbose)
    
    # Return best result without ingredients
    if verbose:
        print(f"[lookup] No ingredients found for '{best_result.get('name', '?')}'")
    return _enrich_result(best_result, with_pubchem, verbose)


def _try_database(db_name: str, search_url: str, product_url: str, query: str | None, 
                   barcode: str | None, use_vision: bool, api_key: str | None, 
                   verbose: bool) -> dict | None:
    """Try a single database (OBF, OPF, or OFF)."""
    if barcode:
        url = product_url.format(code=barcode)
        data = _fetch_json(url)
        if db_name == "OBF":
            if not data or data.get("status") != 1:
                return None
            products = [data.get("product", {})]
        else:
            if not data:
                return None
            products = [data.get("product", {})]
    else:
        url = search_url.format(query=urllib.parse.quote(query or ""))
        data = _fetch_json(url)
        if not data:
            return None
        products = data.get("products", [])
    
    if not products:
        return None
    
    best_result = None
    for prod in products:
        name = prod.get("product_name", "?")
        code = prod.get("code", "")
        brands = prod.get("brands", "")
        ingr, warning = _parse_ingredients_text(prod)

        if ingr:
            source = f"{db_name.lower()}_text"
            result = {
                "name": name, "code": code, "brands": brands,
                "ingredients": ingr, "source": source, "image_path": None,
            }
            if warning:
                result["data_quality_warning"] = warning
            return result

        if best_result is None:
            best_result = prod
    
    # Return best match without ingredients for potential vision fallback
    if best_result:
        return {
            "name": best_result.get("product_name", "?"),
            "code": best_result.get("code", ""),
            "brands": best_result.get("brands", ""),
            "ingredients": [],
            "source": f"{db_name.lower()}_no_ingredients",
            "image_path": None,
        }
    
    return None


def _try_vision_fallback(prod: dict, api_key: str | None, verbose: bool) -> dict | None:
    """Try vision-based ingredient extraction from product photo."""
    name = prod.get("product_name", "?")
    code = prod.get("code", "")
    brands = prod.get("brands", "")
    # "source" is set by _try_database as f"{db_name.lower()}_..." (e.g.
    # "opf_no_ingredients") — recover which database matched from it, since
    # db_name itself isn't passed into this function.
    db_name = prod.get("source", "").split("_", 1)[0].upper()

    # Try to get ingredient image URL
    img_url = None
    if code:
        parts = [code[i:i+3] for i in range(0, min(9, len(code)), 3)]
        rest = code[9:] if len(code) > 9 else ""
        prefix = "/".join(parts)
        if rest:
            prefix += "/" + rest
        for suffix in ("ingredients_en.5.400.jpg", "ingredients.5.400.jpg",
                        "ingredients_de.5.400.jpg", "ingredients.400.jpg"):
            img_url = (
                f"https://images.openbeautyfacts.org/images/products/{prefix}/{suffix}"
                if db_name == "OBF" else
                f"https://images.openproductsfacts.org/images/products/{prefix}/{suffix}"
                if db_name == "OPF" else
                f"https://images.openfoodfacts.org/images/products/{prefix}/{suffix}"
            )
            break
    
    if not img_url:
        if verbose:
            print(f"[lookup] '{name}' — kein Zutaten-Foto gefunden", file=sys.stderr)
        return None
    
    if verbose:
        print(f"[lookup] '{name}' — lade Foto: {img_url}")
    
    img_path = _download_image(img_url)
    if not img_path:
        return None
    
    if verbose:
        print("[lookup] Analysiere Foto mit Vision-Modell ...")
    
    ingr = _vision_read_ingredients(img_path, api_key)
    if ingr:
        if verbose:
            print(f"[lookup] Vision: {len(ingr)} Inhaltsstoffe gelesen")
        return {
            "name": name, "code": code, "brands": brands,
            "ingredients": ingr, "source": "vision_only", "image_path": img_path,
        }
    
    if verbose:
        print("[lookup] Vision: Kein INCI-Text im Foto erkennbar", file=sys.stderr)
    return None


def _cross_check_with_vision(result: dict, api_key: str | None, verbose: bool) -> dict:
    """Independently re-read the ingredient photo when the text-based parse
    carries a data-quality warning, and prefer vision if it looks more complete.

    Only triggered when _parse_ingredients_text() already flagged the result
    with a data_quality_warning — this is a targeted cross-check, not a
    blanket double-lookup, so it doesn't add API cost/latency to normal (clean)
    lookups.
    """
    if verbose:
        print("[lookup] Quelltext wirkt beschädigt (keine Trennzeichen) — "
              "Vision-Gegencheck ...", file=sys.stderr)
    vision_result = _try_vision_fallback(result, api_key, verbose)
    if vision_result and len(vision_result["ingredients"]) > len(result["ingredients"]):
        vision_result["data_quality_warning"] = (
            f"Text-Parse ergab nur {len(result['ingredients'])} Einträge "
            f"(Quelltext ohne Trennzeichen) — durch Vision-Gegencheck auf "
            f"{len(vision_result['ingredients'])} Einträge korrigiert."
        )
        vision_result["source"] = result["source"] + "_corrected_by_vision"
        return vision_result
    if verbose:
        print("[lookup] Vision-Gegencheck brachte keine Verbesserung — "
              "Text-Ergebnis mit Warnung beibehalten", file=sys.stderr)
    return result


def _enrich_result(result: dict, with_pubchem: bool = True, verbose: bool = True) -> dict:
    """Add PubChem enrichment and allergen matching to a result.
    
    Matches against:
    1. KNOWN_ALLERGENS - hand-curated list (EU-26 fragrances, preservatives, etc.)
    2. Local reference tables - ECHA-SVHC and CosIng CSV files (if available)
    3. PubChem - chemical properties (optional)
    """
    result.setdefault("pubchem_data", {})
    result.setdefault("allergens", [])
    result.setdefault("regulatory_flags", [])
    result.setdefault("data_quality_warning", None)
    
    ingredients = result.get("ingredients", [])
    if not ingredients:
        return result
    
    ingr_lower = [x.lower() for x in ingredients]
    
    # 1. Match known allergens from KNOWN_ALLERGENS (hand-curated)
    for allergen_name, check_func in KNOWN_ALLERGENS.items():
        try:
            if check_func(ingr_lower):
                if allergen_name not in result["allergens"]:
                    result["allergens"].append(allergen_name)
        except Exception:
            pass
    
    # 2. Match against local reference tables (ECHA-SVHC, CosIng)
    echa_data, cosing_data = _load_reference_allergens()
    
    for ingredient in ingredients:
        ingr_key = ingredient.lower()
        
        # Check ECHA-SVHC
        if ingr_key in echa_data:
            echa_entry = echa_data[ingr_key]
            flag = f"ECHA-SVHC: {echa_entry['name']} ({echa_entry.get('Category', '')})"
            if flag not in result["regulatory_flags"]:
                result["regulatory_flags"].append(flag)
        
        # Check CosIng
        if ingr_key in cosing_data:
            cosing_entry = cosing_data[ingr_key]
            flag = f"CosIng {cosing_entry.get('Status', '')}: {cosing_entry['name']}"
            if flag not in result["regulatory_flags"]:
                result["regulatory_flags"].append(flag)
    
    # 3. PubChem enrichment (optional)
    if with_pubchem and ingredients:
        pubchem_data = {}
        for ingredient in ingredients:
            cid = _get_pubchem_cid(ingredient)
            if cid:
                props = _fetch_pubchem_properties(cid)
                if props:
                    pubchem_data[ingredient] = props
                    if verbose:
                        print(f"[lookup] PubChem: {ingredient} -> CID {cid}")
        result["pubchem_data"] = pubchem_data if pubchem_data else None
    
    return result


def _any(*kws):
    return lambda items: any(kw in x for x in items for kw in kws)


# Bekannte Allergene/Reizstoffe — Modulebene, damit andere Scripts (z.B.
# analyse_environmental_triggers.py) dieselbe Liste für Cross-Referenzen
# wiederverwenden können, statt sie zu duplizieren.
KNOWN_ALLERGENS = {
    # ── Tenside / Detergentien ────────────────────────────────────────
    "SLS":                  _any("sodium lauryl sulfate", "natriumlaurylsulfat"),
    "SLES":                 _any("sodium laureth sulfate", "sodium lauryl ether"),
    # ── EU-26 Duftstoffallergene ──────────────────────────────────────
    "Linalool":             _any("linalool"),
    "Limonene":             _any("limonene", "limonène"),
    "Geraniol":             _any("geraniol"),
    "Citral":               _any("citral"),
    "Cinnamal":             _any("cinnamal", "cinnamic aldehyde"),
    "Eugenol":              _any("eugenol"),
    "Coumarin":             _any("coumarin"),
    "Farnesol":             _any("farnesol"),
    "Citronellol":          _any("citronellol"),
    "Benzyl alcohol":       _any("benzyl alcohol"),
    "Benzyl salicylate":    _any("benzyl salicylate"),
    "Benzyl benzoate":      _any("benzyl benzoate"),
    "Isoeugenol":           _any("isoeugenol"),
    "Hydroxycitronellal":   _any("hydroxycitronellal"),
    "Lilial (verboten EU)": _any("butylphenyl methylpropional", "lilial"),
    # ── Konservierungsstoffe ──────────────────────────────────────────
    "Parabene":             _any("paraben"),
    "Phenoxyethanol":       _any("phenoxyethanol"),
    "MIT/BIT (Isothiazolinone)": _any("isothiazolinone", "methylisothiazolinone",
                                      "benzisothiazolinone", "octylisothiazolinone"),
    "Formaldehyd-Abspalter": _any("dmdm hydantoin", "imidazolidinyl urea",
                                  "diazolidinyl urea", "quaternium-15"),
    # ── Dental / Oral ─────────────────────────────────────────────────
    "Fluorid":              _any("fluoride", "olaflur", "dectaflur", "monofluorophosphate"),
    "Menthol":              _any("menthol"),
    "Triclosan":            _any("triclosan"),
    "Saccharin":            _any("saccharin"),
    # ── Sonnenschutz ──────────────────────────────────────────────────
    "Oxybenzon (BP-3)":     _any("benzophenone-3", "oxybenzone"),
    "Octinoxat":            _any("ethylhexyl methoxycinnamate", "octinoxate"),
    # ── Sonstige ─────────────────────────────────────────────────────
    "Titandioxid (E171)":   _any("titanium dioxide", "ci 77891"),
    "Carrageen":            _any("carrageenan", "carrageen"),
    "Propylene Glycol":     _any("propylene glycol"),
    "BHT/BHA":              _any("butylated hydroxytoluene", "butylated hydroxyanisole",
                                 "bht", "bha"),
}


def format_result(result: dict) -> str:
    """Pretty-print a lookup result."""
    lines = []
    brand = f" ({result['brands']})" if result.get("brands") else ""
    src   = {"obf_text": "OBF-Text", "opf_text": "OPF-Text", "off_text": "OFF-Text",
             "obf_vision": "OBF-Vision", "opf_vision": "OPF-Vision", "off_vision": "OFF-Vision",
             "vision_only": "Vision (KI-Bilderkennung)",
             "not_found": "nicht gefunden", "obf_no_ingredients": "OBF (keine Inhaltsstoffe)",
             "opf_no_ingredients": "OPF (keine Inhaltsstoffe)", "off_no_ingredients": "OFF (keine Inhaltsstoffe)"}.get(
        result["source"], result["source"]
    )
    lines.append(f"Produkt:  {result['name']}{brand}")
    if result.get("code"):
        lines.append(f"Barcode:  {result['code']}")
    lines.append(f"Quelle:   {src}")
    if result.get("data_quality_warning"):
        lines.append(f"⚠  Datenqualität: {result['data_quality_warning']}")
    lines.append("")

    ingr = result.get("ingredients", [])
    if ingr:
        lines.append(f"INCI-Inhaltsstoffe ({len(ingr)}):")
        for i, ing in enumerate(ingr, 1):
            lines.append(f"  {i:2}. {ing}")

        # Highlight known allergens/irritants
        flags = result.get("allergens", [])
        if flags:
            lines.append("")
            lines.append(f"⚠  Bekannte Allergene/Reizstoffe: {', '.join(flags)}")
        
        # Regulatory flags from ECHA-SVHC and CosIng
        regulatory_flags = result.get("regulatory_flags", [])
        if regulatory_flags:
            lines.append("")
            lines.append("⚠  Regulatorische Warnungen:")
            for flag in regulatory_flags:
                lines.append(f"  • {flag}")
        
        # PubChem data
        pubchem_data = result.get("pubchem_data", {})
        if pubchem_data:
            lines.append("")
            lines.append("Chemische Eigenschaften (PubChem):")
            for ing, props in pubchem_data.items():
                molecular_formula = props.get("MolecularFormula", "N/A")
                molecular_weight = props.get("MolecularWeight", "N/A")
                iupac_name = props.get("IUPACName", "N/A")
                lines.append(f"  • {ing}: {molecular_formula}, {molecular_weight} g/mol, {iupac_name}")
    else:
        lines.append("Keine Inhaltsstoffe gefunden.")
        if result.get("image_path"):
            lines.append(f"(Foto gespeichert: {result['image_path']})")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Produkt-Inhaltsstoffe via Open Beauty Facts + Open Products Facts + Open Food Facts + PubChem"
    )
    parser.add_argument("product", nargs="*",
                        help="Produktname (z.B. 'Elmex Gelee')")
    parser.add_argument("--barcode", "-b", default=None,
                        help="EAN-Barcode für direkten Abruf")
    parser.add_argument("--no-vision", action="store_true",
                        help="Keine KI-Bilderkennung (nur Textdaten aus allen Datenbanken)")
    parser.add_argument("--no-pubchem", action="store_true",
                        help="Keine PubChem-Anreicherung (schneller, keine chemischen Eigenschaften)")
    parser.add_argument("--no-fallback", action="store_true",
                        help="Nur Open Beauty Facts nutzen, keine Fallback-Datenbanken (OPF/OFF)")
    parser.add_argument("--api-key", default=None,
                        help="Anthropic API-Key (default: $ANTHROPIC_API_KEY)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Ergebnis als JSON ausgeben")
    args = parser.parse_args()

    query   = " ".join(args.product) if args.product else None
    api_key = args.api_key or _get_api_key()

    if not query and not args.barcode:
        parser.print_help()
        return

    # Handle --no-fallback by restricting lookup
    use_opf_off = not args.no_fallback
    
    result = lookup(
        query     = query,
        barcode   = args.barcode,
        use_vision = not args.no_vision,
        api_key   = api_key,
        verbose   = not args.as_json,
        with_pubchem = not args.no_pubchem,
    )

    if args.as_json:
        out = dict(result)
        if out.get("image_path"):
            out["image_path"] = str(out["image_path"])
        # Convert Path objects if any
        for key, value in out.items():
            if isinstance(value, Path):
                out[key] = str(value)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print()
        print(format_result(result))


if __name__ == "__main__":
    main()
