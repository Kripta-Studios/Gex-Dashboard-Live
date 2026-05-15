import json
import os
from pathlib import Path

# Path to the JS file where the master list is kept
PROJECT_ROOT = Path(__file__).parents[1]
JS_PATH = PROJECT_ROOT / "web" / "templates" / "js" / "market_structure.js"

def load_market_structures_from_js():
    """
    Extracts the MARKET_STRUCTURES array from the JS file to keep Python in sync.
    """
    if not JS_PATH.exists():
        # Fallback if file not found (should not happen in this environment)
        return []

    with open(JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the start and end of the MARKET_STRUCTURES array
    import re
    start_match = re.search(r"const MARKET_STRUCTURES = \[", content)
    if not start_match:
        return []

    # Find the matching closing ];
    # Since we control the JS format, we know it's a JSON-like array
    # We'll use a simple find for the end of the array.
    end_match = re.search(r"\];", content[start_match.start():])
    if not end_match:
        return []

    array_str = content[start_match.start() + 25 : start_match.start() + end_match.start() + 1]
    
    # The string is essentially JSON but might have some JS-isms
    # (though our migration script creates valid JSON)
    try:
        return json.loads(array_str)
    except Exception as e:
        print(f"[!] Error parsing MARKET_STRUCTURES from JS: {e}")
        # Fallback: try to clean it up a bit (remove comments, etc.)
        cleaned = re.sub(r"//.*", "", array_str)
        cleaned = re.sub(r",\s*([\]\}])", r"\1", cleaned)
        try:
            return json.loads(cleaned)
        except:
            return []

MARKET_STRUCTURES = load_market_structures_from_js()

def get_market_structure_by_id(ms_id):
    for s in MARKET_STRUCTURES:
        if s["id"] == ms_id:
            return s
    return None

def match_market_structure(iv_state, combo):
    """
    Match a greek sign-combo against the structures.
    iv_state: "High" | "Low"
    combo: dict mapping JS names to "Pos" | "Neg"
    """
    matches = []
    for s in MARKET_STRUCTURES:
        c = s["condition"]
        if c.get("IV") != iv_state:
            continue
        ok = True
        for field in ("Gamma", "Zomma", "Delta", "Vex", "Vega", "Vomma", "Speed"):
            wanted = c.get(field)
            if wanted is None: # wildcard
                continue
            if combo.get(field) != wanted:
                ok = False
                break
        if ok:
            matches.append(s)
    return matches
