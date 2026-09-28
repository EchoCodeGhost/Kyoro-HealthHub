#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Allergen-Analyse der getrackten Nahrungsmittel (FDDB → nutrition_entries)

Schritte:
  1. Allergene pro Produkt per Keyword-Matching classifyn (EU 14 + Hafer separat)
  2. Ergebnisse in nutrition_allergens speichern
  3. Per-Tag Allergen-Last anzeigen
  4. Allergen × Symptom Korrelation (falls ausreichend Überlappung)

Usage:
  python analyse_allergens.py
  python analyse_allergens.py --tag-only        # nur classifyn, nicht analysieren
  python analyse_allergens.py --show-products   # alle Produkte mit Allergen-Labels
  python analyse_allergens.py --person partner

@tier        heuristic
@refs        Sampson HA, Aceves S, Bock SA, et al. (2014). Food allergy: a practice parameter update-2014. Journal of Allergy and Clinical Immunology, 134(5), 1016-1025.e43. doi:10.1016/j.jaci.2014.05.013
             Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185

@relevance.de  Ermöglicht die Identifikation und Analyse von Allergen-Expositionen und allergischen Reaktionen, essentiell für die Abklärung und Behandlung von Allergien und immunvermittelten Erkrankungen
@relevance.en  Enables identification and analysis of allergen exposures and allergic reactions, essential for the clinical work-up and treatment of allergies and immune-mediated diseases
@purpose.de  Klassifiziert Lebensmittelprodukte aus FDDB-Einträgen nach EU-14-Allergenen
             via Keyword-Matching und analysiert tägliche Allergenbelastung sowie
             Allergen-Symptom-Korrelationen.
@purpose.en  Classifies food products from FDDB entries by EU-14 allergens via keyword
             matching and analyses daily allergen load as well as allergen-symptom correlations.
@method.de   Substring-Matching auf bereinigten Produktnamen gegen vordefinierte
             Keyword-Listen (nicht NLP/ML). Spearman-Korrelation Allergen × Symptomkategorie.
             Ergebnisse werden in nutrition_allergens gespeichert (DB-Write).
@method.en   Substring matching on normalised product names against predefined keyword
             lists (not NLP/ML). Spearman correlation allergen × symptom category.
             Results are stored in nutrition_allergens (DB write).
@limits.de   Heuristische Methode: Keyword-Matching ist fehleranfällig (False Positives/Negatives). Kein Blut- oder
             Prick-Test. Keine klinische Validierung des Keyword-Sets. n=1, selbst erfasste Daten.
@limits.en   Heuristic method: Keyword matching is error-prone (false positives/negatives). No blood or skin
             prick test. No clinical validation of the keyword set. n=1, self-reported data.
@scoring
    Allergen categories: EU-14 allergens + oats (gluten-free classification)
    Daily load: number of distinct allergens per day
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       nutrition_entries, symptoms
@writes      nutrition_allergens (DB-Write), Konsolenausgabe (kein analyses/-Datei-Output)

@usage
    python analyse_allergens.py
    python analyse_allergens.py --help
    python analyse_allergens.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_immunology import (
    SYSTEM_PROMPT_ANALYSE_ALLERGENS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_ALLERGENS_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = _Cfg()
DB_PATH = _cfg.db_path

# ── EU 14 Hauptallergene + Hafer (separat) ────────────────────────────────────
# Keyword-Listen (lowercase, Teilstring-Match auf bereinigtem Produktnamen)

ALLERGEN_RULES: dict[str, list[str]] = {
    # Gluten-Getreide (Weizen, Dinkel, Roggen, Gerste, Kamut)
    "gluten": [
        "dinkel", "weizen", "roggen", "gerste", "kamut", "einkorn", "emmer",
        "brot", "brötchen", "stangerl", "toast", "baguette", "ciabatta",
        "pasta", "nudel", "farfall", "spaghetti", "penne", "fusilli", "gnocci",
        "pizza", "flammkuchen", "mehl", "stärke", "paniert", "panade",
        "müsli", "granola", "cornflakes", "flakes",
        "riegel",     # Corny/Quaxi enthalten Weizenmehl
        "keks", "gebäck", "waffel", "kuchen", "muffin", "croissant",
        "tortilla", "wrap", "chip",                    # Tortilla-Chips = Maisstärke+Weizen
        "körnerbrot", "vollkornbrot", "knäckebrot", "pumpernickel",
        "bami goreng",                                 # Nudeln in Fertiggericht
        "frikassee",                                   # meist mit Mehlschwitze
        "nugget",                                      # Panade
        "pocket coffee",                               # Waffelanteil
        # Kaubonbon, enthält Weizenmehl
    ],
    # Hafer — oft separat relevant (Zöliakie vs. Hafer-Intoleranz)
    "oats": [
        "hafer", "oat", "haferflock", "mililk veganz, hafer",
        "beeren müsli",                                # Müsli mit Hafer
    ],
    # Milch / Laktose
    "milk": [
        "milch", "butter", "butterschmalz", "schmalz",
        "joghurt", "yoghurt",
        "käse", "parmesan", "kasländer", "emmental", "gouda", "camembert",
        "ricotta", "mozzarella", "frischkäse", "hüttenkäse",
        "sahne", "rahm", "schlagsahne", "creme fraiche", "crème fraîche",
        "buttermilch",
        "quark",
        "whey",                                        # Molkenprotein
        "actimel", "yakult", "danone",
        "feine eier darkmolk",
        "schokolade", "schoko",                        # fast immer Milch
        "chocolate",
        "pocket coffee",
        "kaffee, mit", "kaffee mit", "latte", "cappuccino", "milchkaffee",
        "300 ml kaffee",
        "tortilla chips (nacho cheese)",               # Käsepulver
        # enthält Magermilch
    ],
    # Eier — KEIN "ei" allein (falscher Match in "Heidelbeeren", "Protein", "Scheiben")
    "eggs": [
        "eier", "bio-ei", "hühnerei", "vollei",
        "mayonaise", "mayonnaise", "mayo",
        # Milka Feine Eier
        "omelette", "omelett", "rührei", "spiegelei",
    ],
    # Fisch
    "fish": [
        "fisch", "lachs", "salmon", "thunfisch", "tuna", "tonno",
        "forelle", "hering", "sardine", "makrele", "kabeljau", "dorsch",
        "seelachs", "pangasius", "tilapia", "wolfsbarsch",
        "anchovis", "sardelle",
    ],
    # Krebstiere
    "shellfish": [
        "garnele", "shrimp", "prawn", "krebs", "languste", "hummer",
        "krabbe", "calamari", "tintenfisch",
    ],
    # Erdnüsse
    "peanuts": [
        "erdnuss", "peanut", "groundnut", "erdnussbutter",
    ],
    # Schalenfrüchte (Baumnüsse)
    "tree_nuts": [
        "haselnuss", "haseln",
        "mandel", "almond",
        "walnuss", "walnut",
        "cashew",
        "pistazie", "pistachio",
        "pekan", "pecan",
        "brasil", "paranuss",
        "macadamia",
        # Haselnuss
        "trauben-nuss", "trauben nuss",
        "nuss",                                        # generisch (nach spezifischen)
    ],
    # Soja
    "soy": [
        "soja", "soy", "tofu", "edamame", "miso", "tempeh", "sojasoße",
        "bami goreng",                                 # enthält Sojasoße
    ],
    # Sellerie
    "celery": [
        "sellerie", "celery",
    ],
    # Senf
    "mustard": [
        "senf", "mustard", "dijon",
        "curry",                                       # Currypulver enthält meist Senf
        "currypulver",
    ],
    # Sesam
    "sesame": [
        "sesam", "sesame", "tahini", "hummus",
    ],
    # Schwefeldioxid / Sulfite (≥10 mg/kg → kennzeichnungspflichtig)
    "sulphites": [
        "schinken",                                    # gepökeltes Fleisch
        "mett",                                        # rohes Hackfleisch
        "wurst", "würstchen", "salami", "mortadella",
        "schinkenwürfel", "kochschinken",
        "trockenfrücht", "getrocknete früchte",
        "essig", "weinessig", "balsamico",
        "wein", "sekt",
        "mandarinen, leicht gezuckert",                # Konserve mit Sulfiten
    ],
    # Lupinen
    "lupin": [
        "lupine", "lupin",
    ],
}

# ── FODMAP-Gruppen ────────────────────────────────────────────────────────────
# Fermentierbare Oligo-, Di-, Monosaccharide und Polyole
# Quellen: Monash University FODMAP-Datenbank (Kategorien)

FODMAP_RULES: dict[str, list[str]] = {
    # Fructane (Oligosaccharide — Fructose-Ketten)
    # Weizen, Dinkel, Roggen, Gerste; Zwiebeln, Knoblauch, Spargel
    "fod_fructan": [
        "weizen", "dinkel", "roggen", "gerste",
        "brot", "brötchen", "stangerl", "toast", "baguette",
        "pasta", "nudel", "farfall", "spaghetti", "gnocci",
        "pizza", "mehl",
        "körnerbrot", "vollkornbrot", "knäckebrot",
        "müsli", "granola",
        "zwiebel", "knoblauch", "schalotte", "lauch", "porree",
        "spargel",
        "artischocke", "fenchel",
        "bami goreng",               # Zwiebeln/Knoblauch im Fertiggericht
        "frikassee",                 # Mehlschwitze + Zwiebeln
        "nugget",                    # Paniermehl (Weizen)
    ],
    # GOS — Galakto-Oligosaccharide (Hülsenfrüchte)
    "fod_gos": [
        "linse", "linsen",
        "kichererbse", "hummus",
        "bohne", "kidney",
        "erbse", "erbsen",
        "edamame",
        "tofu",
    ],
    # Laktose (Disaccharid) — Frischmilchprodukte; Hartkäse FODMAP-arm
    "fod_lactose": [
        "milch",
        "joghurt", "yoghurt",
        "buttermilch",
        "ricotta", "frischkäse", "hüttenkäse", "quark",
        "sahne", "schlagsahne", "schmand",
        "actimel", "yakult",
        # Hartkäse (parmesan, kasländer, emmental) bewusst NICHT gelistet
    ],
    # Fruktose im Überschuss (Monosaccharid)
    "fod_fructose": [
        "apfel",
        "birne",
        "mango",
        "honig",
        "orangensaft",               # konzentrierte Fruktose
        "fruchtsaft",
        "agaven",
        "spargel",                   # zusätzlich zu Fructan
        "zuckererbsen",
    ],
    # Sorbit (Polyol — Zuckeralkohol)
    "fod_sorbitol": [
        "pflaume", "zwetschge",
        "aprikose",
        "kirsche",
        "pfirsich", "nektarine",
        "avocado",
        "sorbit", "sorbitol",
        # Saure Bonbons → Sorbit
        "zuckerfrei",
        "light",                     # viele Light-Produkte mit Sorbit
    ],
    # Mannit (Polyol)
    "fod_mannitol": [
        "champignon", "pilz",
        "blumenkohl",
        "wassermelone",
        "mannit", "mannitol",
    ],
}

FODMAP_GROUPS = list(FODMAP_RULES.keys())

FODMAP_LABELS = {
    "fod_fructan":  "Fructane",
    "fod_gos":      "GOS",
    "fod_lactose":  "Laktose",
    "fod_fructose": "Fruktose",
    "fod_sorbitol": "Sorbit",
    "fod_mannitol": "Mannit",
}

# ── Pollen-Nahrungsmittel-Kreuzreaktionen (OAS / PFAS) ───────────────────────
# Quellen: DGAKI-Leitlinien, Monash-Datenbank, EuroPrevall-Studie
#
# Birkenpollen-Syndrom:  Apfel, Birne, Kirsche, Haselnuss, Sellerie, Soja, ...
# Sellerie-Karotten-Beifuß-Gewürz-Syndrom: Sellerie, Karotte, Paprika, Curry, ...
# Gräserpollen-Syndrom:  Tomate, Kartoffel, Kiwi, Weizen
# Ambrosia-Syndrom:      Melone, Gurke, Zucchini, Banane

CROSS_REACTION_RULES: dict[str, list[str]] = {
    # Birke (Betula) — häufigstes OAS-Syndrom in Europa
    "xr_birch": [
        "apfel", "birne",
        "pfirsich", "nektarine", "aprikose", "pflaume", "zwetschge", "kirsche",
        "mango",
        "haselnuss", "haseln", "mandel",
        "sellerie",
        "karotte", "möhre",
        "petersilie",
        "soja", "sojadrink",
        "kiwi",
        "erdnuss", "peanut",
        # Milka = Haselnuss
    ],
    # Beifuß (Artemisia) — Sellerie-Karotten-Beifuß-Gewürz-Syndrom
    "xr_mugwort": [
        "sellerie",
        "karotte", "möhre",
        "paprika",
        "curry", "currypulver",
        "petersilie", "anis", "fenchel",
        "kamille", "kamilletee",
        "sonnenblume", "sonnenblumenkerne", "sonnenblumenkern",
        "mango",
        "gewürz",
    ],
    # Gräser (Poaceae) — Gräserpollen-Syndrom
    "xr_grass": [
        "tomate",
        "kartoffel", "pommes", "bratkartoffel",
        "kiwi",
        "erdnuss", "peanut",
        "weizen", "roggen",
        "melone", "wassermelone", "honigmelone",
    ],
    # Ambrosia (Ragweed) — Ambrosia-Nahrungsmittel-Syndrom
    "xr_ragweed": [
        "melone", "wassermelone", "honigmelone", "cantaloupe",
        "gurke",
        "zucchini",
        "banane",
        "sonnenblume", "sonnenblumenkerne", "sonnenblumenkern",
        "kamille", "kamilletee",
    ],
}

XR_GROUPS = list(CROSS_REACTION_RULES.keys())

XR_LABELS = {
    "xr_birch":   "Birke",
    "xr_mugwort": "Beifuß",
    "xr_grass":   "Gräser",
    "xr_ragweed": "Ambrosia",
}

# Pollen-Tabellenspalten (Open-Meteo, grains/m³)
XR_POLLEN_COL = {
    "xr_birch":   "birch",
    "xr_mugwort": "mugwort",
    "xr_grass":   "grass",
    "xr_ragweed": "ragweed",
}

# Schwellenwerte für "erhöhter Pollenflug" (grains/m³)
POLLEN_MOD_THRESHOLD = {
    "birch":   10,
    "mugwort":  5,
    "grass":   10,
    "ragweed":  2,
}

# ── Lebensmittelzusatzstoffe (detektierbar via Produktname) ──────────────────
# E-Nummern und Substanzklassen die in FDDB-Produktnamen auftauchen

ADDITIVE_RULES: dict[str, list[str]] = {
    # Glutamat (E621-623) / Hefeextrakt — Umami-Verstärker
    "add_glutamate": [
        "hefeextrakt", "hefe-extrakt", "autolysat",
        "glutamat", "e621",
        "würze", "würzmittel", "suppenwürze", "maggi", "fondor",
        "ramen", "instantnudeln",
        "bami goreng",
        "fertigsuppe", "brühwürfel",
    ],
    # Nitrit-Pökelsalz (E249, E250) — gepökeltes Fleisch
    "add_nitrite": [
        "wurst", "würstchen", "bratwurst", "bockwurst",
        "salami", "chorizo", "mortadella", "fleischkäse",
        "schinken", "kochschinken", "schinkenwürfel",
        "bacon", "speck",
        "mett", "hackfleisch",
        # bewusst KEIN "fleisch" allein → zu generisch
    ],
    # Künstliche Süßungsmittel (E950-E960)
    "add_sweetener": [
        "aspartam", "e951",
        "saccharin", "e954",
        "acesulfam", "e950",
        "sucralose", "e955",
        "stevia", "steviol", "e960",
        "zuckerfrei", "zuckerreduziert",
        # "light" und "zero" absichtlich nicht: zu viele Falsch-Positive
    ],
    # Azo-Farbstoffe (E102, E110, E122, E123, E124, E129) — Tartrazin etc.
    "add_azo_dye": [
        "tartrazin", "e102",
        "e110", "e122", "e123", "e124", "e129",
        "gummibärchen", "gummibär",
        "haribo",
        "fanta",          # enthält oft E110
        "campino",
    ],
    # Konservierungsstoffe (Benzoate E210-219, Sorbate E200-209)
    "add_preservative": [
        "benzoat", "e210", "e211",
        "sorbat", "e200", "e202",
        "natamycin", "e235",
        "konservierungsstoff",
        "haltbar gemacht",
        # Sulfite E220-228 → bereits in ALLERGEN_RULES "sulphites" enthalten
    ],
}

ADDITIVE_GROUPS = list(ADDITIVE_RULES.keys())

ADDITIVE_LABELS = {
    "add_glutamate":    "Glutamat/HFE",
    "add_nitrite":      "Nitrit",
    "add_sweetener":    "Süßungsmittel",
    "add_azo_dye":      "Azofarbstoffe",
    "add_preservative": "Konservierungsstoffe",
}

# ── Duftstoffe in Lebensmitteln (als Aromastoff / Zutat) ─────────────────────
# Klassische Kontaktallergene aus Nahrungsmitteln (IFRA-Quellen)

FRAGRANCE_FOOD_RULES: dict[str, list[str]] = {
    # Menthol / Pfefferminzöl (Zähne, Minztees, Bonbons)
    "frag_menthol": [
        "pfefferminze", "pfefferminztee", "pfefferminzbonbon",
        "minze", "mint", "spearmint",
        "menthol",
    ],
    # Zimtaldehyd / Zimt (Gebäck, Curries, heißgetränke)
    "frag_cinnamon": [
        "zimt", "zimtpulver", "cinnamon",
        "zimtschnecke", "zimtstern",
        "lebkuchen", "spekulatius",
    ],
    # Vanillin (Süßwaren, Joghurt, Backwaren — häufig synthetisch)
    "frag_vanilla": [
        "vanille", "vanilla", "vanillin",
        "vanillezucker", "vanillearoma",
    ],
    # Eugenol / Nelkenöl (Currypulver, Gewürzmischungen, Zahnschmerzmittel)
    "frag_eugenol": [
        "gewürznelke", "nelke",
        "currypulver",   # enthält typisch Nelken + Eugenol
        "nelkenpfeffer", "piment",
    ],
    # Linalool / Lavendel, Koriander (Aromaöle in Tees, Aromaprodukten)
    "frag_linalool": [
        "lavendel", "lavendeltee",
        "koriander", "coriander",
        "bergamotte",
    ],
}

FRAGRANCE_FOOD_GROUPS = list(FRAGRANCE_FOOD_RULES.keys())

FRAGRANCE_FOOD_LABELS = {
    "frag_menthol":  "Menthol",
    "frag_cinnamon": "Zimtaldehyd",
    "frag_vanilla":  "Vanillin",
    "frag_eugenol":  "Eugenol",
    "frag_linalool": "Linalool",
}

# Mengenpräfix entfernen: "100 g Dinkelbrötchen" → "dinkelbrötchen"
_AMOUNT_RE = re.compile(
    r'^\d+[\.,]?\d*\s*'
    r'(g|ml|l|kg|mg|stk|st\.|tl|el|pck|pkg|cl|dl|kcal|kj|x)\s*\.?\s*',
    re.IGNORECASE
)

ALLERGENS = list(ALLERGEN_RULES.keys())

EU14_LABELS = {
    "gluten":    "Gluten",
    "oats":      "Hafer",
    "milk":      "Milch",
    "eggs":      "Eier",
    "fish":      "Fisch",
    "shellfish": "Krebstiere",
    "peanuts":   "Erdnüsse",
    "tree_nuts": "Schalenfrüchte",
    "soy":       "Soja",
    "celery":    "Sellerie",
    "mustard":   "Senf",
    "sesame":    "Sesam",
    "sulphites": "Sulfite",
    "lupin":     "Lupinen",
}


# ── Klassifizierung ───────────────────────────────────────────────────────────

def _clean_name(raw: str) -> str:
    return _AMOUNT_RE.sub("", raw).strip().lower()


def classify(raw_name: str) -> dict[str, int]:
    name = _clean_name(raw_name)
    result = {}
    for allergen, keywords in ALLERGEN_RULES.items():
        result[allergen] = 1 if any(kw in name for kw in keywords) else 0
    for group, keywords in FODMAP_RULES.items():
        result[group] = 1 if any(kw in name for kw in keywords) else 0
    for group, keywords in CROSS_REACTION_RULES.items():
        result[group] = 1 if any(kw in name for kw in keywords) else 0
    for group, keywords in ADDITIVE_RULES.items():
        result[group] = 1 if any(kw in name for kw in keywords) else 0
    for group, keywords in FRAGRANCE_FOOD_RULES.items():
        result[group] = 1 if any(kw in name for kw in keywords) else 0
    return result


# ── DB ────────────────────────────────────────────────────────────────────────

def setup_table(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS nutrition_allergens (
        ts           TEXT NOT NULL,
        date         TEXT NOT NULL,
        name         TEXT NOT NULL,
        gluten       INTEGER DEFAULT 0,
        oats         INTEGER DEFAULT 0,
        milk         INTEGER DEFAULT 0,
        eggs         INTEGER DEFAULT 0,
        fish         INTEGER DEFAULT 0,
        shellfish    INTEGER DEFAULT 0,
        peanuts      INTEGER DEFAULT 0,
        tree_nuts    INTEGER DEFAULT 0,
        soy          INTEGER DEFAULT 0,
        celery       INTEGER DEFAULT 0,
        mustard      INTEGER DEFAULT 0,
        sesame       INTEGER DEFAULT 0,
        sulphites    INTEGER DEFAULT 0,
        lupin        INTEGER DEFAULT 0,
        fod_fructan  INTEGER DEFAULT 0,
        fod_gos      INTEGER DEFAULT 0,
        fod_lactose  INTEGER DEFAULT 0,
        fod_fructose INTEGER DEFAULT 0,
        fod_sorbitol INTEGER DEFAULT 0,
        fod_mannitol INTEGER DEFAULT 0,
        person       TEXT DEFAULT 'unknown',
        source       TEXT DEFAULT 'keyword_match',
        PRIMARY KEY (ts, person)
    );
    CREATE INDEX IF NOT EXISTS idx_nutr_all_date   ON nutrition_allergens(date);
    CREATE INDEX IF NOT EXISTS idx_nutr_all_person ON nutrition_allergens(person);
    """)
    # Neue Spalten nachträglich ergänzen falls Tabelle bereits existiert
    existing = {r[1] for r in conn.execute("PRAGMA table_info(nutrition_allergens)")}
    for col in FODMAP_GROUPS + XR_GROUPS + ADDITIVE_GROUPS + FRAGRANCE_FOOD_GROUPS:
        if col not in existing:
            conn.execute(f"ALTER TABLE nutrition_allergens ADD COLUMN {col} INTEGER DEFAULT 0")
    conn.commit()


def tag_entries(conn: sqlite3.Connection, person: str, date_filter: str = "", filter_params: list = None) -> int:
    if filter_params is None:
        filter_params = [person]
    else:
        filter_params = [person] + filter_params
    entries = conn.execute(
        f"SELECT ts, date, name FROM nutrition_entries WHERE person=?{date_filter}", filter_params
    ).fetchall()

    rows = []
    for ts, date, name in entries:
        flags = classify(name)
        rows.append((
            ts, date, name,
            flags["gluten"], flags["oats"], flags["milk"], flags["eggs"],
            flags["fish"], flags["shellfish"], flags["peanuts"], flags["tree_nuts"],
            flags["soy"], flags["celery"], flags["mustard"], flags["sesame"],
            flags["sulphites"], flags["lupin"],
            flags["fod_fructan"], flags["fod_gos"], flags["fod_lactose"],
            flags["fod_fructose"], flags["fod_sorbitol"], flags["fod_mannitol"],
            flags["xr_birch"], flags["xr_mugwort"], flags["xr_grass"], flags["xr_ragweed"],
            flags["add_glutamate"], flags["add_nitrite"], flags["add_sweetener"],
            flags["add_azo_dye"], flags["add_preservative"],
            flags["frag_menthol"], flags["frag_cinnamon"], flags["frag_vanilla"],
            flags["frag_eugenol"], flags["frag_linalool"],
            person, "keyword_match",
        ))

    conn.executemany("""
        INSERT OR IGNORE INTO nutrition_allergens
        (ts, date, name,
         gluten, oats, milk, eggs, fish, shellfish, peanuts, tree_nuts,
         soy, celery, mustard, sesame, sulphites, lupin,
         fod_fructan, fod_gos, fod_lactose, fod_fructose, fod_sorbitol, fod_mannitol,
         xr_birch, xr_mugwort, xr_grass, xr_ragweed,
         add_glutamate, add_nitrite, add_sweetener, add_azo_dye, add_preservative,
         frag_menthol, frag_cinnamon, frag_vanilla, frag_eugenol, frag_linalool,
         person, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    return len(rows)


# ── Analyse ───────────────────────────────────────────────────────────────────

def report_products(conn: sqlite3.Connection, person: str):
    print(t("\n═══ Allergen-Labels pro Produkt ═══════════════════════════════════",
            "\n═══ Allergen labels per product ═══════════════════════════════════"))
    rows = conn.execute("""
        SELECT name,
               gluten, oats, milk, eggs, fish, shellfish,
               peanuts, tree_nuts, soy, celery, mustard, sesame, sulphites, lupin,
               COUNT(*) n
        FROM nutrition_allergens
        WHERE person=?
        GROUP BY name
        ORDER BY name
    """, (person,)).fetchall()

    for row in rows:
        name = row[0]
        flags = row[1:15]
        detected = [EU14_LABELS[a] for a, f in zip(ALLERGENS, flags) if f]
        label = ", ".join(detected) if detected else "–"
        print(f"  {name[:50]:<50}  [{label}]")


def report_daily(conn: sqlite3.Connection, person: str):
    print(t("\n═══ Allergen-Last pro Tag ══════════════════════════════════════════",
            "\n═══ Allergen load per day ══════════════════════════════════════════"))
    # Header
    short = ["Glu", "Haf", "Mil", "Ei ", "Fis", "Kre", "Erd", "Nss",
             "Soj", "Sel", "Sen", "Ses", "Sul", "Lup"]
    print(f"  {'Datum':<12}" + "".join(f"{s:<4}" for s in short) + " Produkte")
    print(f"  {'-'*12}" + "-" * (4 * len(short)) + " ────────")

    days = conn.execute("""
        SELECT date,
               MAX(gluten), MAX(oats), MAX(milk), MAX(eggs),
               MAX(fish), MAX(shellfish), MAX(peanuts), MAX(tree_nuts),
               MAX(soy), MAX(celery), MAX(mustard), MAX(sesame),
               MAX(sulphites), MAX(lupin),
               COUNT(*) n
        FROM nutrition_allergens
        WHERE person=?
        GROUP BY date ORDER BY date
    """, (person,)).fetchall()

    for row in days:
        date = row[0]
        flags = row[1:15]
        n = row[15]
        cells = "".join("█   " if f else "·   " for f in flags)
        print(f"  {date:<12}{cells} {n}")

    # Summenspalte
    print(f"\n  {'Gesamt':<12}", end="")
    for i, a in enumerate(ALLERGENS):
        total = conn.execute(
            f"SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE {a}=1 AND person=?",
            (person,)
        ).fetchone()[0]
        n_days = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE person=?", (person,)
        ).fetchone()[0]
        pct = f"{total}/{n_days}"
        print(f"{pct:<4}", end="")
    print(" Tage")


def report_fodmap(conn: sqlite3.Connection, person: str):
    print(t("\n═══ FODMAP-Last pro Tag ════════════════════════════════════════════",
            "\n═══ FODMAP load per day ════════════════════════════════════════════"))
    short = ["Fru", "GOS", "Lak", "Fkt", "Srb", "Man"]
    print(f"  {'Datum':<12}" + "".join(f"{s:<4}" for s in short) + " Produkte")
    print(f"  {'-'*12}" + "-" * (4 * len(short)) + " ────────")

    days = conn.execute("""
        SELECT date,
               MAX(fod_fructan), MAX(fod_gos), MAX(fod_lactose),
               MAX(fod_fructose), MAX(fod_sorbitol), MAX(fod_mannitol),
               COUNT(*) n
        FROM nutrition_allergens
        WHERE person=?
        GROUP BY date ORDER BY date
    """, (person,)).fetchall()

    n_days = len(days)
    for row in days:
        date = row[0]
        flags = row[1:7]
        n = row[7]
        cells = "".join("█   " if f else "·   " for f in flags)
        print(f"  {date:<12}{cells} {n}")

    print(f"\n  {'Gesamt':<12}", end="")
    for col in FODMAP_GROUPS:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE {col}=1 AND person=?",
            (person,)
        ).fetchone()[0]
        print(f"{total}/{n_days:<3}", end="")
    print(" Tage")

    # Welche Produkte triggern FODMAP?
    print(t("\n  Produkte mit FODMAP-Treffern:",
            "\n  Products with FODMAP hits:"))
    for col, label in FODMAP_LABELS.items():
        names = [r[0] for r in conn.execute(
            f"SELECT DISTINCT name FROM nutrition_allergens WHERE {col}=1 AND person=? ORDER BY name",
            (person,)
        )]
        if names:
            clean = [_AMOUNT_RE.sub("", n).strip() for n in names]
            print(f"  {label:<12} {', '.join(clean)}")


def report_additives(conn: sqlite3.Connection, person: str):
    """Report food additive and fragrance exposure per day."""
    print(t(
        "\n═══ Lebensmittelzusatzstoffe & Duftstoffe (Nahrungsmittel) ════════",
        "\n═══ Food additives & fragrances ════════════════════════════════════",
    ))

    all_groups = ADDITIVE_GROUPS + FRAGRANCE_FOOD_GROUPS
    all_labels = {**ADDITIVE_LABELS, **FRAGRANCE_FOOD_LABELS}
    short_hdr = ["Glu", "Nit", "Süß", "Azo", "Kon", "Men", "Zim", "Van", "Eug", "Lin"]

    n_days = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE person=?", (person,)
    ).fetchone()[0]

    print(f"  {'Datum':<12}" + "".join(f"{s:<4}" for s in short_hdr) + " Produkte")
    print(f"  {'-'*12}" + "-" * (4 * len(short_hdr)) + " ────────")

    cols_sql = ", ".join(f"MAX({c})" for c in all_groups)
    days = conn.execute(f"""
        SELECT date, {cols_sql}, COUNT(*) n
        FROM nutrition_allergens
        WHERE person=?
        GROUP BY date ORDER BY date
    """, (person,)).fetchall()

    for row in days:
        date  = row[0]
        flags = row[1: 1 + len(all_groups)]
        n     = row[1 + len(all_groups)]
        cells = "".join("█   " if f else "·   " for f in flags)
        print(f"  {date:<12}{cells} {n}")

    # Summary
    print(f"\n  {'Gesamt':<12}", end="")
    for col in all_groups:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE {col}=1 AND person=?",
            (person,)
        ).fetchone()[0]
        print(f"{total}/{n_days:<3}", end="")
    print(" Tage")

    # Products per group
    print(t("\n  Produkte nach Kategorie:",
            "\n  Products by category:"))
    for col in all_groups:
        label = all_labels[col]
        names = [r[0] for r in conn.execute(
            f"SELECT DISTINCT name FROM nutrition_allergens WHERE {col}=1 AND person=? ORDER BY name",
            (person,)
        )]
        if names:
            clean = [_AMOUNT_RE.sub("", n).strip() for n in names[:8]]
            suffix = f" (+{len(names)-8})" if len(names) > 8 else ""
            print(f"  {label:<18} {', '.join(clean)}{suffix}")


def _ensure_solar_view(conn: sqlite3.Connection) -> None:
    """Create v_solar view merging local Ecowitt + Open-Meteo data.

    Priority: weather_station (Ecowitt, local sensor) > biometeo (Open-Meteo).
    sunshine_h is only available from Open-Meteo.
    Unit conversion: solar_wm2 * 86400 / 1e6 = solar_mj_m2 (daily total).
    """
    conn.execute("""
        CREATE VIEW IF NOT EXISTS v_solar AS
        SELECT
            d.date,
            -- UV: Ecowitt (local) > DWD station (nearby) > Open-Meteo (model)
            COALESCE(ws.uv_index_max, dwd.uv_index, bm.uv_index_max) AS uv_index_max,
            -- Solar W/m²: Ecowitt > DWD station > Open-Meteo (converted)
            COALESCE(ws.solar_wm2_max, dwd.solar_wm2,
                CASE WHEN bm.solar_mj_m2 IS NOT NULL
                     THEN ROUND(bm.solar_mj_m2 * 1000000.0 / 86400.0, 1)
                     ELSE NULL END)                              AS solar_wm2,
            -- Solar MJ/m²: Open-Meteo > convert from Ecowitt/DWD
            COALESCE(bm.solar_mj_m2,
                CASE WHEN ws.solar_wm2_max IS NOT NULL
                     THEN ROUND(ws.solar_wm2_max * 86400.0 / 1000000.0, 3)
                     WHEN dwd.solar_wm2 IS NOT NULL
                     THEN ROUND(dwd.solar_wm2 * 86400.0 / 1000000.0, 3)
                     ELSE NULL END)                              AS solar_mj_m2,
            -- Sunshine hours: Ecowitt CSV (computed) > DWD/AEMET station > Open-Meteo
            COALESCE(dwd.sunshine_h, bm.sunshine_h) AS sunshine_h,
            dwd.cloud_pct                                        AS cloud_pct,
            CASE
                WHEN ws.date  IS NOT NULL THEN 'ecowitt'
                ELSE '' END
            || CASE WHEN dwd.date IS NOT NULL THEN '+dwd'    ELSE '' END
            || CASE WHEN bm.date  IS NOT NULL THEN '+open_meteo' ELSE '' END
                                                                 AS src
        FROM (
            SELECT date FROM weather_station
            UNION SELECT date FROM weather_dwd_station
            UNION SELECT date FROM biometeo
        ) d
        LEFT JOIN weather_station     ws  ON ws.date  = d.date
        LEFT JOIN weather_dwd_station dwd ON dwd.date = d.date
        LEFT JOIN biometeo            bm  ON bm.date  = d.date
    """)


def report_uv_correlation(conn: sqlite3.Connection, person: str):
    """Correlate sun/UV exposure (local Ecowitt + Open-Meteo) with skin symptoms."""
    _ensure_solar_view(conn)
    print(t(
        "\n═══ Sonnen-/UV-Exposition × Haut-Symptome ══════════════════════════",
        "\n═══ Sun/UV exposure × skin symptoms ════════════════════════════════",
    ))

    # Skin + photosensitivity symptoms to track
    SKIN_SYMPTOMS = [
        "Hautausschlag", "Trockene Haut", "Lichtempfindlichkeit",
        "tag_generic_sun", "Juckreiz",
    ]
    # Short display labels (same order)
    SYM_SHORT = ["Ausschlag", "TrockHaut", "Lichtempf", "tag_sun", "Juckreiz"]

    # UV source breakdown
    src_counts = dict(conn.execute(
        "SELECT src, COUNT(*) FROM v_solar GROUP BY src"
    ).fetchall())
    n_ecowitt = src_counts.get("ecowitt", 0) + src_counts.get("ecowitt+open_meteo", 0)
    n_om      = src_counts.get("open_meteo", 0) + src_counts.get("ecowitt+open_meteo", 0)

    has_uv = conn.execute(
        "SELECT COUNT(*) FROM v_solar WHERE uv_index_max IS NOT NULL"
    ).fetchone()[0] > 0

    uv_col   = "uv_index_max" if has_uv else "solar_mj_m2"
    uv_label = "UV-Index" if has_uv else "Solar MJ/m²"

    print(t(
        f"  UV-Quelle: {uv_label}  "
        f"(Ecowitt: {n_ecowitt} Tage | Open-Meteo: {n_om} Tage)",
        f"  UV source: {uv_label}  "
        f"(Ecowitt: {n_ecowitt} days | Open-Meteo: {n_om} days)",
    ))

    # Collect per-date data where v_solar AND at least one skin symptom both exist
    overlap = []
    for d, uv_val, sun_h in conn.execute(
        f"SELECT date, {uv_col}, sunshine_h FROM v_solar "
        f"WHERE {uv_col} IS NOT NULL ORDER BY date"
    ):
        sym_rows = conn.execute(
            "SELECT symptom, value_num FROM symptoms WHERE date=? AND symptom IN ({})".format(
                ",".join("?" * len(SKIN_SYMPTOMS))
            ),
            [d] + SKIN_SYMPTOMS
        ).fetchall()
        if sym_rows:
            sym_map    = {r[0]: (r[1] or 0) for r in sym_rows}
            total_score = sum(sym_map.values())
            overlap.append((d, uv_val, sun_h, total_score, sym_map))

    if not overlap:
        print(t(
            "  Keine Überlappung zwischen Solar-Daten und Haut-Symptomeinträgen.",
            "  No overlap between solar data and skin symptom entries.",
        ))
        return

    print(t(f"  Überlappende Tage: {len(overlap)}",
            f"  Overlapping days: {len(overlap)}"))

    # Header
    sym_hdr = "".join(f" {s:>9}" for s in SYM_SHORT)
    print(f"\n  {'Datum':<12} {uv_label:>10} {'Sonne(h)':>8}{sym_hdr}  Total")
    print(f"  {'-'*12} {'-'*10} {'-'*8}" + " " + " ".join("-"*9 for _ in SYM_SHORT) + "  -----")

    for d, uv_val, sun_h, score, sym_map in overlap:
        sym_cols = "".join(
            f" {sym_map.get(s, 0):>9.0f}" for s in SKIN_SYMPTOMS
        )
        mark = " ◄" if score > 0 else ""
        print(f"  {d:<12} {uv_val or 0:>10.1f} {sun_h or 0:>8.1f}{sym_cols}  {score:.0f}{mark}")

    # Spearman correlation
    if len(overlap) >= 5:
        uv_vals  = [r[1] or 0 for r in overlap]
        sym_vals = [r[3]      for r in overlap]
        rho, p = _spearman(uv_vals, sym_vals)
        sig = "**" if p < 0.01 else ("*" if p < 0.05 else "n.s.")
        print(t(
            f"\n  Spearman ρ ({uv_label} × Haut-Symptome gesamt): {rho:+.3f}  p={p:.4f}  {sig}",
            f"\n  Spearman ρ ({uv_label} × skin symptoms total):  {rho:+.3f}  p={p:.4f}  {sig}",
        ))
    else:
        print(t(
            f"\n  Zu wenig Überlappung für Korrelation (n={len(overlap)}, mind. 5 nötig).",
            f"\n  Insufficient overlap for correlation (n={len(overlap)}, ≥5 needed).",
        ))


def _pollen_level_str(val: float | None, species: str) -> str:
    """Return human-readable pollen level with threshold symbol."""
    if val is None or val == 0:
        return "·"
    thr = POLLEN_MOD_THRESHOLD.get(species, 10)
    if val >= thr * 3:  return f"{val:.0f} ▲▲"
    if val >= thr:      return f"{val:.0f} ▲"
    return f"{val:.0f} △"


def _dwd_risk_str(val: float | None) -> str:
    if val is None: return "  –"
    if val <= 0:    return "  ·"
    if val < 1.5:   return "  △"
    if val < 2.5:   return "  ▲"
    return "  ▲▲"


def report_cross_reactions(conn: sqlite3.Connection, person: str):
    """Show co-occurrence of cross-reactive foods with pollen levels (OAS risk)."""
    print(t(
        "\n═══ Kreuzreaktion Pollen × Nahrungsmittel (OAS/PFAS) ══════════════",
        "\n═══ Cross-reaction pollen × food (OAS/PFAS risk days) ══════════════",
    ))

    # Which pollen tables are available?
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    has_om     = "pollen"        in tables
    has_dwd    = "pollen_dwd"    in tables
    has_google = "pollen_google" in tables

    sources_avail = []
    if has_om:     sources_avail.append("Open-Meteo")
    if has_dwd:    sources_avail.append("DWD")
    if has_google: sources_avail.append("Google")
    print(t(
        f"  Pollen-Quellen: {', '.join(sources_avail) or '(keine)'}",
        f"  Pollen sources: {', '.join(sources_avail) or '(none)'}",
    ))

    # Days where any cross-reactive food was eaten
    xr_days = conn.execute("""
        SELECT date,
               MAX(xr_birch)   xrb,
               MAX(xr_mugwort) xrm,
               MAX(xr_grass)   xrg,
               MAX(xr_ragweed) xrr
        FROM nutrition_allergens
        WHERE person=? AND (xr_birch=1 OR xr_mugwort=1 OR xr_grass=1 OR xr_ragweed=1)
        GROUP BY date ORDER BY date
    """, (person,)).fetchall()

    if not xr_days:
        print(t("  Keine kreuzreaktiven Lebensmittel in den Daten gefunden.",
                "  No cross-reactive foods found in data."))
        return

    # ── Tages-Tabelle ──────────────────────────────────────────────────────────
    # Überschrift-Legende
    print(t(
        "\n  Symbole: ▲▲=sehr hoch  ▲=erhöht  △=niedrig  ·=keine Daten/kein Pollenflug",
        "\n  Legend:  ▲▲=very high  ▲=elevated  △=low  ·=no data/no pollen",
    ))
    # Birke=Bk, Beifuß=Bf, Gräser=Gr, Ambrosia=Am
    hdr = (f"\n  {'Datum':<12}  "
           f"{'OM-Birke':>10} {'OM-Gräser':>10} {'OM-Beifuß':>10} {'OM-Ambr':>10}  "
           + ("DWD Bk Gr Bf Am  " if has_dwd else "")
           + "XR-Essen")
    sep = "  " + "-" * 12 + "  " + "-" * 10 + " " + "-" * 10 + " " + "-" * 10 + " " + "-" * 10
    if has_dwd:
        sep += "  " + "-" * 16
    sep += "  " + "-" * 11
    print(hdr)
    print(sep)

    risk_days: list[str] = []

    for date, xrb, xrm, xrg, xrr in xr_days:
        # Open-Meteo
        om = {}
        if has_om:
            r = conn.execute(
                "SELECT birch, mugwort, grass, ragweed FROM pollen WHERE date=? LIMIT 1",
                (date,)
            ).fetchone()
            if r:
                om = {"birch": r[0], "mugwort": r[1], "grass": r[2], "ragweed": r[3]}

        # DWD
        dwd = {}
        if has_dwd:
            r = conn.execute(
                "SELECT birch, mugwort, grass, ragweed FROM pollen_dwd WHERE date=? LIMIT 1",
                (date,)
            ).fetchone()
            if r:
                dwd = {"birch": r[0], "mugwort": r[1], "grass": r[2], "ragweed": r[3]}

        # Risk: cross-reactive food eaten AND pollen elevated?
        risk = 0
        for xr_flag, species in [(xrb, "birch"), (xrm, "mugwort"), (xrg, "grass"), (xrr, "ragweed")]:
            if not xr_flag:
                continue
            pv_om  = om.get(species)  or 0
            pv_dwd = dwd.get(species) or 0
            thr = POLLEN_MOD_THRESHOLD.get(species, 10)
            if pv_om >= thr or pv_dwd >= 1.5:
                risk += 1

        if risk:
            risk_days.append(date)

        # Format cells
        om_bk = _pollen_level_str(om.get("birch"),   "birch")
        om_gr = _pollen_level_str(om.get("grass"),   "grass")
        om_bf = _pollen_level_str(om.get("mugwort"), "mugwort")
        om_am = _pollen_level_str(om.get("ragweed"), "ragweed")

        xr_flags = (("▇" if xrb else "·") + " "
                  + ("▇" if xrm else "·") + " "
                  + ("▇" if xrg else "·") + " "
                  + ("▇" if xrr else "·"))
        risk_mark = " ⚠" * risk

        dwd_str = ""
        if has_dwd:
            dwd_str = (f"  {_dwd_risk_str(dwd.get('birch'))}"
                      f" {_dwd_risk_str(dwd.get('grass'))}"
                      f" {_dwd_risk_str(dwd.get('mugwort'))}"
                      f" {_dwd_risk_str(dwd.get('ragweed'))}")

        print(f"  {date:<12}  "
              f"{om_bk:>10} {om_gr:>10} {om_bf:>10} {om_am:>10}"
              f"{dwd_str}  {xr_flags}{risk_mark}")

    # ── Zusammenfassung ────────────────────────────────────────────────────────
    n_total = len(xr_days)
    n_risk  = len(risk_days)
    print(t(
        f"\n  Tage mit kreuzreaktivem Essen: {n_total}",
        f"\n  Days with cross-reactive food: {n_total}",
    ))
    if sources_avail:
        print(t(
            f"  Davon mit erhöhtem Pollenflug (OAS-Risiko): {n_risk}",
            f"  Of which with elevated pollen (OAS risk):   {n_risk}",
        ))

    # ── Produkte nach Pollengruppe ─────────────────────────────────────────────
    print(t("\n  Kreuzreaktive Produkte nach Pollengruppe:",
            "\n  Cross-reactive products by pollen group:"))
    for group, label in XR_LABELS.items():
        names = [r[0] for r in conn.execute(
            f"SELECT DISTINCT name FROM nutrition_allergens WHERE {group}=1 AND person=? ORDER BY name",
            (person,)
        )]
        if not names:
            continue
        clean = [_AMOUNT_RE.sub("", n).strip() for n in names[:10]]
        suffix = f" … +{len(names) - 10}" if len(names) > 10 else ""
        print(f"  {label:<10}  {', '.join(clean)}{suffix}")

    # ── Symptomhinweis für Risikotage ──────────────────────────────────────────
    if risk_days:
        sym_overlap = [d for d in risk_days if conn.execute(
            "SELECT 1 FROM symptoms WHERE date=? LIMIT 1", (d,)
        ).fetchone()]
        if sym_overlap:
            print(t(
                f"\n  {len(sym_overlap)} Risikotage haben Symptomeinträge — "
                f"Korrelation siehe Abschnitt 'Allergen × Symptom'.",
                f"\n  {len(sym_overlap)} risk days have symptom entries — "
                f"see 'Allergen × Symptom' section for correlation.",
            ))
        else:
            print(t(
                "\n  Keine Symptomeinträge für Risikotage vorhanden.",
                "\n  No symptom entries found for risk days.",
            ))


def _spearman(x: list, y: list) -> tuple[float, float]:
    n = len(x)
    if n < 4:
        return float("nan"), float("nan")
    def ranks(lst):
        sorted_vals = sorted(enumerate(lst), key=lambda t: t[1])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and sorted_vals[j + 1][1] == sorted_vals[i][1]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sorted_vals[k][0]] = avg_rank
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx  = math.sqrt(sum((v - mx) ** 2 for v in rx))
    dy  = math.sqrt(sum((v - my) ** 2 for v in ry))
    if dx == 0 or dy == 0:
        return float("nan"), float("nan")
    rho = num / (dx * dy)
    t_stat = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
    # p-Wert via Normalapproximation
    z = abs(t_stat) * math.sqrt(1 / (n - 1))
    p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return round(rho, 3), round(p, 4)


def report_correlation(conn: sqlite3.Connection, person: str):
    # Überlappende Tage Allergen ↔ Symptome
    overlap_dates = [r[0] for r in conn.execute("""
        SELECT DISTINCT na.date
        FROM nutrition_allergens na
        JOIN symptoms s ON s.date = na.date
        WHERE na.person = ?
        ORDER BY na.date
    """, (person,))]

    print(t("\n═══ Allergen × Symptom-Korrelation ════════════════════════════════",
            "\n═══ Allergen × Symptom correlation ════════════════════════════════"))
    print(t(f"  Überlappende Tage: {len(overlap_dates)}", f"  Overlapping days: {len(overlap_dates)}"))

    if len(overlap_dates) < 5:
        print(t(
            "  ⚠ Zu wenig Überlappung für Korrelationsanalyse (mind. 5 Tage nötig).\n"
            "  Empfehlung: FDDB-Tracking und Symptom-Tagebuch parallel führen.\n"
            "  Allergen-Tags wurden gespeichert — Analyse wird möglich sobald\n"
            "  genug gemeinsame Tage vorliegen.",
            "  ⚠ Insufficient overlap for correlation analysis (≥5 days needed).\n"
            "  Recommendation: track FDDB and symptom diary in parallel.\n"
            "  Allergen tags have been saved — analysis will be possible once\n"
            "  enough shared days exist."
        ))
        return

    # Symptom-Kategorien die für Allergie/Intoleranz relevant sind
    SYMPTOM_TARGETS = {
        "GI":          ["Blähungen", "Durchfall", "Verstopfung", "Bauchschmerzen"],
        "Erkältung":   ["Schnupfen", "Verstopfte Nase", "Husten", "Halsschmerzen"],
        "Erschöpfung": ["Erschöpfung/Fatigue"],
        "Auge":        ["Trockenes Auge", "Augenschmerzen"],
        "Haut":        ["Trockene Haut", "Hautausschlag"],
        "Schmerz":     ["Gelenkschmerzen", "Körperschmerz", "Muskelschmerzen"],
    }

    print(t("\n  Spearman ρ  (p<.05 = *, p<.01 = **)",
            "\n  Spearman ρ  (p<.05 = *, p<.01 = **)"))
    header = f"  {'Allergen':<14}" + "".join(f"{k:<14}" for k in SYMPTOM_TARGETS)
    print(header)
    print("  " + "-" * (14 + 14 * len(SYMPTOM_TARGETS)))

    for allergen in ALLERGENS:
        label = EU14_LABELS[allergen]
        allergen_vals = []
        for d in overlap_dates:
            v = conn.execute(
                f"SELECT MAX({allergen}) FROM nutrition_allergens WHERE date=? AND person=?",
                (d, person)
            ).fetchone()[0] or 0
            allergen_vals.append(v)

        row_str = f"  {label:<14}"
        for cat_key, symptom_list in SYMPTOM_TARGETS.items():
            sym_vals = []
            for d in overlap_dates:
                scores = [r[0] or 0 for r in conn.execute("""
                    SELECT value_num FROM symptoms
                    WHERE date=? AND symptom IN ({})
                """.format(",".join("?" * len(symptom_list))),
                    [d] + symptom_list
                ).fetchall()]
                sym_vals.append(sum(scores))

            if all(v == 0 for v in sym_vals) or all(v == 0 for v in allergen_vals):
                row_str += f"{'n/a':<14}"
                continue

            rho, p = _spearman(allergen_vals, sym_vals)
            if math.isnan(rho):
                row_str += f"{'n/a':<14}"
            else:
                sig = "**" if p < 0.01 else ("*" if p < 0.05 else "")
                row_str += f"{rho:+.2f}{sig:<12}"
        print(row_str)


def report_summary(conn: sqlite3.Connection, person: str):
    print(t("\n═══ Häufigste Allergene ════════════════════════════════════════════",
            "\n═══ Most common allergens ══════════════════════════════════════════"))
    n_days = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE person=?", (person,)
    ).fetchone()[0]
    n_products = conn.execute(
        "SELECT COUNT(DISTINCT name) FROM nutrition_allergens WHERE person=?", (person,)
    ).fetchone()[0]
    print(t(f"  {n_days} Tage · {n_products} Produkte ausgewertet",
            f"  {n_days} days · {n_products} products evaluated"))

    results = []
    for allergen in ALLERGENS:
        n_affected_days = conn.execute(
            f"SELECT COUNT(DISTINCT date) FROM nutrition_allergens WHERE {allergen}=1 AND person=?",
            (person,)
        ).fetchone()[0]
        n_products_with = conn.execute(
            f"SELECT COUNT(DISTINCT name) FROM nutrition_allergens WHERE {allergen}=1 AND person=?",
            (person,)
        ).fetchone()[0]
        results.append((EU14_LABELS[allergen], n_affected_days, n_products_with))

    results.sort(key=lambda r: -r[1])
    for label, nd, np in results:
        if nd == 0:
            continue
        bar = "█" * nd + "·" * (n_days - nd)
        print(f"  {label:<16}  {bar}  {nd}/{n_days} Tage  ({np} Produkte)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Allergen-Analyse der FDDB-Nahrungsmittel",
                      "Allergen analysis of FDDB nutrition entries")
    )
    parser.add_argument("--tag-only",      action="store_true",
                        help=t("Nur classifyn, keine Analyse",
                               "Only tag, skip analysis output"))
    parser.add_argument("--show-products", action="store_true",
                        help=t("Alle Produkte mit Allergen-Labels anzeigen",
                               "Show all products with allergen labels"))
    parser.add_argument("--person", default=OWN_PERSON_ID)
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plots speichern", "Save plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("KI-Kommentare deaktivieren", "Disable AI commentary"))
    parser.add_argument("--from", dest="from_date", default=None,
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="to_date", default=None,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    # Handle date filtering
    date_filter = ""
    filter_params = [args.person]
    if args.from_date or args.to_date:
        if args.from_date and args.to_date:
            date_filter = " AND date BETWEEN ? AND ?"
            filter_params.extend([args.from_date, args.to_date])
        elif args.from_date:
            date_filter = " AND date >= ?"
            filter_params.append(args.from_date)
        elif args.to_date:
            date_filter = " AND date <= ?"
            filter_params.append(args.to_date)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    setup_table(conn)

    print(t("Klassifiziere Nahrungsmitteleinträge ...",
            "Classifying nutrition entries ..."))
    n = tag_entries(conn, args.person, date_filter, filter_params[1:] if len(filter_params) > 1 else None)
    print(t(f"  {n} Einträge klassifiziert → nutrition_allergens",
            f"  {n} entries classified → nutrition_allergens"))

    if args.tag_only:
        conn.close()
        return

    from modules.llm import capture_stdout

    with capture_stdout() as buf:
        if args.show_products:
            report_products(conn, args.person)

        report_summary(conn, args.person)
        report_daily(conn, args.person)
        report_fodmap(conn, args.person)
        report_additives(conn, args.person)
        report_cross_reactions(conn, args.person)
        try:
            report_uv_correlation(conn, args.person)
        except Exception as e:
            print(t(f"UV-Korrelation übersprungen (Wetterdaten fehlen): {e}",
                    f"UV correlation skipped (weather data missing): {e}"))
        report_correlation(conn, args.person)

    if not args.no_llm:
        llm_text = _run_llm(buf.getvalue())
        if llm_text:
            print(t("\n══ KLINISCHE INTERPRETATION ══", "\n══ CLINICAL INTERPRETATION ══"))
            print(llm_text)

    conn.close()


if __name__ == "__main__":
    main()
