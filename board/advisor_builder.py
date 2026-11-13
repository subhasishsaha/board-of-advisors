import json
import re
from typing import Any, Dict, List

def parse_advisors_json(raw_text: str) -> List[Dict[str, Any]]:
    """Robustly parse a JSON array of advisor definitions from LLM output."""
    text = raw_text.strip()
    
    # Strip markdown code blocks if present
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        clean_json = match.group(1)
    else:
        # Fallback to finding outermost brackets
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            clean_json = text[start : end + 1]
        else:
            clean_json = text

    data = json.loads(clean_json)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array of advisors")

    # Enforce maximum 10 advisors and sanitize
    advisors = []
    available_colors = [
        "bright_magenta", "bright_cyan", "bright_green", "bright_yellow",
        "bright_blue", "gold1", "plum2", "dark_orange3", "turquoise2", "spring_green1"
    ]

    for idx, item in enumerate(data[:10]):
        name = item.get("name", f"Advisor {idx+1}").strip()
        tag = item.get("tag", "").strip()
        if not tag:
            # Generate tag from first name
            first_name = re.sub(r"[^\w]", "", name.split()[0])
            tag = f"@{first_name}"
        elif not tag.startswith("@"):
            tag = f"@{tag}"

        adv_id = item.get("id") or re.sub(r"[^\w]", "_", name.lower())
        avatar = item.get("avatar") or "👤"
        color = item.get("color") or available_colors[idx % len(available_colors)]
        role = item.get("role", "Strategic Advisor").strip()
        persona = item.get("persona", "").strip()
        bio = item.get("bio", "").strip()
        core_beliefs = item.get("core_beliefs") or []

        advisors.append({
            "id": adv_id,
            "name": name,
            "tag": tag,
            "role": role,
            "avatar": avatar,
            "color": color,
            "bio": bio,
            "persona": persona,
            "core_beliefs": core_beliefs,
        })

    return advisors
