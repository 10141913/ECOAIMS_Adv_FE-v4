import csv
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request, Body, Response
from fastapi.routing import APIRoute
import gzip
import json
from pydantic import BaseModel, Field

class GzipRequestRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def custom(request: Request) -> Response:
            if request.headers.get("content-encoding", "").lower() == "gzip":
                body = await request.body()
                decompressed = gzip.decompress(body)
                async def receive():
                    return {"type": "http.request", "body": decompressed}
                request._receive = receive
            return await original(request)
        return custom

router = APIRouter(tags=["energy"], route_class=GzipRequestRoute)


ENERGY_LIMITS = {
    "solar": 100.0,
    "wind": 150.0,
    "battery": 200.0,
    "grid": 100.0,
    "biofuel": 50.0,
}


def _read_latest_supply(output_dir: str) -> Dict[str, float]:
    path = os.path.join(output_dir, "live_supply.csv")
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"timestamp", "sensor_id", "value"}.issubset(set(reader.fieldnames)):
            return {}
        latest: Dict[str, Dict[str, Any]] = {}
        for row in reader:
            sid = row.get("sensor_id")
            if not isinstance(sid, str) or not sid:
                continue
            latest[sid] = row
        out: Dict[str, float] = {}
        for sid, row in latest.items():
            try:
                out[sid] = float(row.get("value"))
            except (TypeError, ValueError):
                continue
        return out


def _make_item(value: float, max_value: float, source: str) -> Dict[str, Any]:
    return {"value": float(value), "max": float(max_value), "value_3h": float(value) * 3.0, "source": source}


@router.get("/api/energy-data")
def energy_data(stream_id: str = Query(default="default"), limit: int = Query(default=12, ge=1, le=200)) -> Dict[str, Any]:
    base_dir = os.getcwd()
    output_dir = os.path.join(base_dir, "output")
    live = _read_latest_supply(output_dir)

    if live:
        solar_val = float(live.get("pv", 0.0))
        wind_val = float(live.get("wt", 0.0))
        bio_val = float(live.get("biofuel", 0.0))
        grid_val = float(live.get("grid", 0.0))
        batt_val = float(live.get("battery", 0.0))
        source = "live"
    else:
        solar_val = random.uniform(0, ENERGY_LIMITS["solar"])
        wind_val = random.uniform(0, ENERGY_LIMITS["wind"])
        grid_val = random.uniform(10, ENERGY_LIMITS["grid"] * 0.9)
        bio_val = random.uniform(0, ENERGY_LIMITS["biofuel"])
        batt_val = random.uniform(-ENERGY_LIMITS["battery"] * 0.2, ENERGY_LIMITS["battery"] * 0.9)
        source = "sim"

    batt_max_kwh = float(ENERGY_LIMITS["battery"])
    batt_power_kw = float(batt_val)
    batt_energy_kwh = None
    batt_soc_pct = None

    if 0.0 <= batt_val <= batt_max_kwh:
        batt_energy_kwh = float(batt_val)
        batt_soc_pct = (batt_energy_kwh / batt_max_kwh) * 100.0 if batt_max_kwh > 0 else 0.0
        batt_power_kw = 0.0

    if batt_soc_pct is None:
        batt_soc_pct = 60.0

    batt_soc_pct = max(20.0, min(80.0, float(batt_soc_pct)))
    if batt_energy_kwh is None:
        batt_energy_kwh = (batt_soc_pct / 100.0) * batt_max_kwh if batt_max_kwh > 0 else 0.0

    if batt_power_kw < 0:
        battery_status = "Charging"
    elif batt_power_kw > 0:
        battery_status = "Discharging"
    else:
        battery_status = "Idle"

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    sid = str(stream_id or "default")
    records = []
    for i in range(int(limit)):
        ts = now
        records.append({
            "timestamp": ts.isoformat(),
            "solar": float(solar_val),
            "wind": float(wind_val),
            "battery": float(batt_energy_kwh),
            "battery_power_kw": float(batt_power_kw),
            "grid": float(grid_val),
            "biofuel": float(bio_val),
            "stream_id": sid,
        })

    battery_item = {
        "value": float(batt_energy_kwh),
        "max": float(batt_max_kwh),
        "value_3h": float(batt_energy_kwh),
        "source": source,
        "status": battery_status,
        "soc_pct": float(batt_soc_pct),
        "power_kw": float(batt_power_kw),
    }

    return {
        "solar": _make_item(solar_val, ENERGY_LIMITS["solar"], source),
        "wind": _make_item(wind_val, ENERGY_LIMITS["wind"], source),
        "battery": battery_item,
        "grid": _make_item(grid_val, ENERGY_LIMITS["grid"], source),
        "biofuel": _make_item(bio_val, ENERGY_LIMITS["biofuel"], source),
        "stream_id": sid,
        "data_available": True,
        "records": records,
        "applied_limit": int(limit),
        "returned_records_len": int(len(records)),
        "available_records_len": int(len(records)),
        "trimmed": False,
    }



class OptimizeRequest(BaseModel):
    priority: str = Field(default="renewable")
    battery_SOC: float = Field(default=50.0, ge=0.0, le=100.0)
    grid_limit: float = Field(default=100.0, ge=0.0)
    renewable_energy_avail: Optional[float] = None
    solar_available: float = Field(default=50.0, ge=0.0)
    wind_available: float = Field(default=30.0, ge=0.0)
    demand_energy: float = Field(default=100.0, ge=0.0)


@router.post("/optimize")
async def optimize(request: Request, req: OptimizeRequest | None = Body(default=None)) -> Dict[str, Any]:
    req = req or OptimizeRequest()
    priority = (req.priority or "renewable").lower()
    solar_available = float(req.solar_available or 0.0)
    wind_available = float(req.wind_available or 0.0)
    grid_limit = float(req.grid_limit or 0.0)
    total_demand = float(req.demand_energy or 0.0)
    battery_available = float(ENERGY_LIMITS["battery"]) * (float(req.battery_SOC or 0.0) / 100.0)

    usage = {"Solar PV": 0.0, "Wind Turbine": 0.0, "Battery": 0.0, "PLN/Grid": 0.0}
    remaining = total_demand

    if priority == "renewable":
        solar_use = min(remaining, solar_available)
        usage["Solar PV"] = solar_use
        remaining -= solar_use

        wind_use = min(remaining, wind_available)
        usage["Wind Turbine"] = wind_use
        remaining -= wind_use

        batt_use = min(remaining, battery_available)
        usage["Battery"] = batt_use
        remaining -= batt_use

        grid_use = min(remaining, grid_limit)
        usage["PLN/Grid"] = grid_use
        remaining -= grid_use

        recommendation = (
            "Strategi ini memaksimalkan penggunaan energi hijau. "
            "Sangat baik untuk mengurangi jejak karbon, namun pastikan kapasitas baterai mencukupi saat malam hari."
        )
    elif priority == "battery":
        batt_use = min(remaining, battery_available)
        usage["Battery"] = batt_use
        remaining -= batt_use

        solar_use = min(remaining, solar_available)
        usage["Solar PV"] = solar_use
        remaining -= solar_use

        wind_use = min(remaining, wind_available)
        usage["Wind Turbine"] = wind_use
        remaining -= wind_use

        grid_use = min(remaining, grid_limit)
        usage["PLN/Grid"] = grid_use
        remaining -= grid_use

        recommendation = (
            f"Anda memprioritaskan penggunaan baterai (Target: {float(req.battery_SOC):.0f}% kapasitas). "
            "Ini efektif untuk 'Peak Shaving' saat tarif listrik grid mahal, tetapi dapat memperpendek umur siklus baterai jika sering dilakukan."
        )
    else:
        grid_use = min(remaining, grid_limit)
        usage["PLN/Grid"] = grid_use
        remaining -= grid_use

        solar_use = min(remaining, solar_available)
        usage["Solar PV"] = solar_use
        remaining -= solar_use

        wind_use = min(remaining, wind_available)
        usage["Wind Turbine"] = wind_use
        remaining -= wind_use

        batt_use = min(remaining, battery_available)
        usage["Battery"] = batt_use
        remaining -= batt_use

        recommendation = (
            "Prioritas Grid dipilih. Ini menjamin kestabilan pasokan tertinggi, "
            "namun mungkin meningkatkan biaya operasional dan emisi CO2. Energi terbarukan hanya digunakan sebagai pelengkap."
        )

    return {"energy_distribution": usage, "recommendation": recommendation}
