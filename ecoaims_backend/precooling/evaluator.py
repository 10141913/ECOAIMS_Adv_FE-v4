from typing import Any, Dict, List


def evaluate_scenarios(baseline: Dict[str, Any], rule_based: Dict[str, Any], laeopf: Dict[str, Any]) -> List[Dict[str, Any]]:
    metrics = ["energy_kwh", "peak_kw", "cost_idr", "co2_kg", "comfort_compliance", "shr", "exergy_efficiency", "ipei"]
    rows: List[Dict[str, Any]] = []
    for m in metrics:
        rows.append(
            {
                "metric": m,
                "baseline": baseline.get(m, "-"),
                "rule_based": rule_based.get(m, "-"),
                "laeopf": laeopf.get(m, "-"),
            }
        )
    return rows

