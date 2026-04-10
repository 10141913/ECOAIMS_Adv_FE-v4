from typing import Any, Dict, List, Tuple


def validate_simulate_request(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["Payload harus JSON object"]

    zone = payload.get("zone")
    if zone is not None and not isinstance(zone, str):
        errors.append("zone harus string")

    window = payload.get("window", {})
    if window and not isinstance(window, dict):
        errors.append("window harus object")

    weights = payload.get("weights", {})
    if weights and not isinstance(weights, dict):
        errors.append("weights harus object")

    return (len(errors) == 0), errors

