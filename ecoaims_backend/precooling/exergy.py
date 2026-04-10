from typing import Any, Dict


def compute_exergy(latent_load: float, sensible_load: float) -> Dict[str, Any]:
    ex_in = sensible_load * 1.2 + latent_load * 0.015
    ex_out = sensible_load * 0.9 + latent_load * 0.010
    loss = max(0.0, ex_in - ex_out)
    eff = ex_out / max(1e-6, ex_in)
    return {
        "input": round(ex_in, 3),
        "output": round(ex_out, 3),
        "loss": round(loss, 3),
        "efficiency": round(eff, 3),
    }

