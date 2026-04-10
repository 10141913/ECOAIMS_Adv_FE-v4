import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass
class PrecoolingZoneState:
    zone: str
    mode: str = "monitoring"
    fallback_active: bool = False
    last_update: str = field(default_factory=now_iso)
    status: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)
    scenarios: Dict[str, Any] = field(default_factory=dict)
    kpi: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    audit: List[Dict[str, Any]] = field(default_factory=list)
    last_simulation: Dict[str, Any] = field(default_factory=dict)


class PrecoolingStore:
    def __init__(self):
        self._zones: Dict[str, PrecoolingZoneState] = {}

    def get(self, zone: str) -> PrecoolingZoneState:
        if zone not in self._zones:
            self._zones[zone] = PrecoolingZoneState(zone=zone)
        return self._zones[zone]

    def list_zones(self) -> List[str]:
        return sorted(self._zones.keys())

    def append_audit(self, zone: str, entry: Dict[str, Any]) -> None:
        st = self.get(zone)
        st.audit.insert(0, entry)
        st.audit = st.audit[:200]

    def append_alert(self, zone: str, entry: Dict[str, Any]) -> None:
        st = self.get(zone)
        st.alerts.insert(0, entry)
        st.alerts = st.alerts[:200]

    def touch(self, zone: str) -> None:
        st = self.get(zone)
        st.last_update = now_iso()


store = PrecoolingStore()

