from typing import Any, Dict

from ecoaims_backend.precooling.psychrometrics import psychrometric_state


def compute_latent_state(outdoor_temp_c: float, outdoor_rh: float, target_temp_c: float, target_rh: float) -> Dict[str, Any]:
    outdoor = psychrometric_state(outdoor_temp_c, outdoor_rh)
    target = psychrometric_state(target_temp_c, target_rh)

    latent_load = max(0.0, (outdoor["humidity_ratio"] - target["humidity_ratio"])) * 1200.0
    sensible_load = max(0.0, outdoor_temp_c - target_temp_c) * 0.9
    shr = sensible_load / max(1e-6, sensible_load + latent_load)

    return {
        "rh_actual": round(outdoor_rh, 1),
        "rh_target": round(target_rh, 1),
        "dew_point": round(outdoor["dew_point_c"], 2),
        "humidity_ratio": round(outdoor["humidity_ratio"], 5),
        "latent_load": round(latent_load, 2),
        "sensible_load": round(sensible_load, 2),
        "shr": round(shr, 3),
        "outdoor": outdoor,
        "target": target,
    }

