import json
import re
import os

def migrate():
    # Load Excel data from the previously generated JSON
    excel_json_path = 'full_excel.json'
    if not os.path.exists(excel_json_path):
        print(f"Error: {excel_json_path} not found.")
        return

    with open(excel_json_path, 'r', encoding='utf-8') as f:
        excel_data = json.load(f)
    
    # Load existing JS data
    js_path = 'web/templates/js/market_structure.js'
    with open(js_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    # Extract the MARKET_STRUCTURES array
    # Find start
    start_pattern = r'const MARKET_STRUCTURES = \['
    start_match = re.search(start_pattern, js_content)
    if not start_match:
        print("Could not find MARKET_STRUCTURES array start")
        return
    
    # Find end of array - it ends with ];
    # We need to be careful with nested brackets.
    # Since we know the structure is an array of objects, we can look for the closing ];
    # that is followed by either whitespace or a comment or the next variable.
    
    # Simplified approach: find the first ]; after the start
    end_match = re.search(r'\];', js_content[start_match.start():])
    if not end_match:
        print("Could not find MARKET_STRUCTURES array end")
        return
    
    old_array_full_str = js_content[start_match.start() : start_match.start() + end_match.end()]
    
    # Extract objects from the old array string
    # We'll use a more robust regex for objects { ... }
    # This regex handles one level of nesting (for 'condition' and 'flags')
    obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    obj_matches = re.findall(obj_pattern, old_array_full_str)
    
    old_objects = []
    for obj_str in obj_matches:
        try:
            # Clean up JS-isms to make it valid JSON
            # 1. Replace single quotes with double quotes (though JS usually uses double here)
            # 2. Remove trailing commas
            clean_str = re.sub(r',\s*([\]\}])', r'\1', obj_str)
            # 3. Handle potential unquoted keys (though not expected here)
            # 4. Handle comments (remove them)
            clean_str = re.sub(r'//.*', '', clean_str)
            # This is still risky. Let's try a simpler approach if this fails.
            obj = json.loads(clean_str)
            old_objects.append(obj)
        except Exception as e:
            # If JSON parsing fails, we might need a more sophisticated JS-to-JSON converter
            # but let's see if this works.
            pass

    # Create a map of condition -> old object for easy lookup
    # Normalize conditions for comparison
    def normalize_cond(cond):
        if not cond: return ""
        # Ensure all keys are present and sorted
        keys = ["IV", "Gamma", "Zomma", "Delta", "Vex", "Vega", "Vomma", "Speed"]
        return "|".join([str(cond.get(k, "null")) for k in keys])

    old_map = {}
    for obj in old_objects:
        cond = obj.get('condition', {})
        cond_key = normalize_cond(cond)
        old_map[cond_key] = obj

    new_structures = []
    for i, row in enumerate(excel_data):
        condition = {
            "IV": row.get("IV ", "").strip(),
            "Gamma": row.get("Gamma", "").strip(),
            "Zomma": row.get("Zomma", "").strip(),
            "Delta": row.get("Delta", "").strip(),
            "Vex": row.get("Vex", "").strip(),
            "Vega": row.get("Vega", "").strip(),
            "Vomma": row.get("Vomma", "").strip(),
            "Speed": row.get("Speed", "").strip()
        }
        
        # Clean up values (Pos/Neg/null)
        for k in condition:
            if condition[k] == "nan" or condition[k] == "" or condition[k] is None:
                condition[k] = None
        
        cond_key = normalize_cond(condition)
        old_obj = old_map.get(cond_key, {})
        
        # Infer actionDirection
        action = row.get("Action", "")
        if action is None: action = ""
        action_direction = "N/A"
        upper_action = str(action).upper()
        if "SELL LEAN" in upper_action: action_direction = "SELL LEAN"
        elif "BUY LEAN" in upper_action: action_direction = "BUY LEAN"
        elif "BUY" in upper_action: action_direction = "BUY"
        elif "SELL" in upper_action: action_direction = "SELL"
        elif "AVOID SHORTS" in upper_action: action_direction = "BUY LEAN"
        elif "AVOID LONGS" in upper_action: action_direction = "SELL LEAN"
        elif "AVOID BUYS" in upper_action: action_direction = "SELL LEAN"
        elif "DORMANT" in upper_action: action_direction = "N/A"

        # Construct new object
        new_obj = {
            "id": i + 1,
            "name": row.get("Market Phenominum", ""),
            "condition": condition,
            "regime": row.get("Regime", ""),
            "action": action,
            "actionDirection": action_direction,
            "tilt": row.get("Tilt:", ""),
            "dealersAction": row.get("Dealers Action", ""),
            "charmNetNegative": row.get("Charm Net Negative", ""),
            "charmNetPositive": row.get("Charm Net Positive", ""),
            "vannaNetNegative": old_obj.get("vannaNetNegative", ""),
            "vannaNetPositive": old_obj.get("vannaNetPositive", ""),
            "zommaText": old_obj.get("zommaText", ""),
            "mxVannaLevelsWork": old_obj.get("mxVannaLevelsWork", ""),
            "vShapeRecovery": old_obj.get("vShapeRecovery", ""),
            "spreads": old_obj.get("spreads", None),
            "stochastic": old_obj.get("stochastic", None),
            "trendEliminator": old_obj.get("trendEliminator", None),
            "flags": old_obj.get("flags", { "max_vanna_level": False, "ib_bounce": False, "dadu_pinning": False })
        }
        
        # Default zommaText if missing
        if not new_obj["zommaText"]:
            zVal = condition.get("Zomma")
            if zVal == "Pos":
                new_obj["zommaText"] = "Zomma Dormant — Drains/ Weakens Gamma toward Zero if IV rises."
            elif zVal == "Neg":
                new_obj["zommaText"] = "Zomma Active — Drains/ Weakens Gamma toward Zero."

        new_structures.append(new_obj)

    # Format the array nicely
    # json.dumps gives us valid JSON, we'll wrap it in the JS variable declaration
    new_array_json = json.dumps(new_structures, indent=4, ensure_ascii=False)
    new_array_js = f"const MARKET_STRUCTURES = {new_array_json};"
    
    # Replace the old array with the new one in the file content
    # We use string replacement at the exact indices
    new_content = js_content[:start_match.start()] + new_array_js + js_content[start_match.start() + len(old_array_full_str):]
    
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Successfully updated {js_path} with {len(new_structures)} entries.")

if __name__ == "__main__":
    migrate()
