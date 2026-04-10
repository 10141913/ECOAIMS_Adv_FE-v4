import datetime
import random
from typing import Any, Dict, List, Tuple


def _parse_hhmm(s: str) -> datetime.time:
    parts = (s or "00:00").split(":")
    h = int(parts[0]) if len(parts) > 0 else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return datetime.time(hour=max(0, min(23, h)), minute=max(0, min(59, m)))


def generate_candidates(
    zone: str,
    earliest_start: str,
    latest_start: str,
    durations_min: List[int],
    target_temp_range: Tuple[float, float],
    target_rh_range: Tuple[float, float],
) -> List[Dict[str, Any]]:
    seed = abs(hash((zone, earliest_start, latest_start))) % 10_000
    rnd = random.Random(seed)

    et = _parse_hhmm(earliest_start)
    lt = _parse_hhmm(latest_start)

    candidates: List[Dict[str, Any]] = []
    for i in range(1, 16):
        dur = int(rnd.choice(durations_min or [30, 60, 90]))
        target_t = rnd.uniform(target_temp_range[0], target_temp_range[1])
        target_rh = rnd.uniform(target_rh_range[0], target_rh_range[1])

        start_hour = rnd.randint(et.hour, max(et.hour, lt.hour))
        start_min = et.minute if start_hour == et.hour else rnd.choice([0, 15, 30, 45])
        start_time = f"{start_hour:02d}:{start_min:02d}"

        candidates.append(
            {
                "candidate_id": f"C{i:03d}",
                "start_time": start_time,
                "duration": dur,
                "target_t": round(target_t, 1),
                "target_rh": round(target_rh, 1),
            }
        )

    return candidates

