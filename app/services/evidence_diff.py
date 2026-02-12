from typing import Any, Dict, List


def diff_decisions(ai: Dict[str, Any], human: Dict[str, Any]) -> List[Dict[str, Any]]:
    diffs = []
    keys = set(ai.keys()) | set(human.keys())
    for key in keys:
        if ai.get(key) != human.get(key):
            diffs.append(
                {
                    "field": key,
                    "ai": ai.get(key),
                    "human": human.get(key),
                }
            )
    return diffs
