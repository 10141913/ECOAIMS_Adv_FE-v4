"""
Indoor API wrapper functions for ECO-AIMS Indoor Module.

Provides isolated HTTP calls to indoor backend endpoints with
timeout, error handling, and logging. All functions return
safe defaults on failure to prevent dashboard bricking.
"""

import csv
import io
import logging
from typing import Any

import requests

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL
from ecoaims_frontend.services.base_url_service import effective_base_url

logger = logging.getLogger(__name__)

_INDOOR_TIMEOUT_LATEST = 5
_INDOOR_TIMEOUT_ZONES = 5
_INDOOR_TIMEOUT_TIMESERIES = 10
_INDOOR_TIMEOUT_CSV_PREVIEW = 10   # timeout 10s agar UI tidak hang
_INDOOR_TIMEOUT_CSV_COMMIT = 10    # timeout 10s agar UI tidak hang
_INDOOR_TIMEOUT_CSV_STATUS = 10    # timeout 10s agar UI tidak hang
_INDOOR_TIMEOUT_MAINTENANCE = 3

# ── Column Mapping ──────────────────────────────
# Frontend CSV columns (user-facing) → Backend CSV columns (API expects)
_COLUMN_MAP = {
    "timestamp": "timestamp_utc",
    "zone_id": "zone_id",
    "temp_c": "zone_temp_c",
    "rh_pct": "zone_rh_pct",
    "co2_ppm": "co2_ppm",
}


def _remap_csv_columns(csv_bytes: bytes) -> bytes:
    """Remap frontend CSV column names to backend column names.

    Reads the CSV, renames columns using _COLUMN_MAP, and returns
    the transformed CSV as bytes. Columns not in the map are dropped.
    """
    raw = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))

    mapped_rows: list[dict[str, str]] = []
    for row in reader:
        mapped: dict[str, str] = {}
        for frontend_col, backend_col in _COLUMN_MAP.items():
            val = row.get(frontend_col, "").strip()
            if val:
                mapped[backend_col] = val
        if mapped:
            mapped_rows.append(mapped)

    if not mapped_rows:
        # Return original bytes if no rows could be mapped
        return csv_bytes

    output = io.StringIO()
    fieldnames = list(_COLUMN_MAP.values())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(mapped_rows)
    return output.getvalue().encode("utf-8")


def _indoor_base(readiness: dict | None = None) -> str:
    """Resolve the base URL for indoor API calls."""
    return effective_base_url(readiness if isinstance(readiness, dict) else {})


def _get_json(
    url: str,
    params: dict | None = None,
    timeout: int = 5,
    headers: dict | None = None,
) -> dict | None:
    """Safe GET → JSON helper. Returns None on any failure."""
    try:
        hdrs = dict(headers or {})
        print(f"DEBUG indoor_api._get_json: GET {url} timeout={timeout}s", flush=True)
        resp = requests.get(url, params=params, timeout=timeout, headers=hdrs or None)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("indoor_api timeout GET %s (timeout=%ss)", url, timeout)
        print(f"❌ DEBUG indoor_api._get_json: TIMEOUT GET {url} (timeout={timeout}s)", flush=True)
    except requests.exceptions.ConnectionError:
        logger.warning("indoor_api connection-error GET %s", url)
        print(f"❌ DEBUG indoor_api._get_json: CONNECTION-ERROR GET {url} — backend unreachable", flush=True)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        try:
            detail = exc.response.text[:1000]
        except Exception:
            detail = "N/A"
        logger.warning("indoor_api HTTP %s GET %s — detail: %s", status, url, detail)
        print(f"❌ DEBUG indoor_api._get_json: HTTP {status} GET {url} — response: {detail}", flush=True)
    except Exception as exc:
        logger.error("indoor_api unexpected error GET %s: %s", url, exc)
        print(f"❌ DEBUG indoor_api._get_json: UNEXPECTED ERROR GET {url}: {exc}", flush=True)
    return None


def _post_json(
    url: str,
    json_body: dict | None = None,
    files: dict | None = None,
    timeout: int = 30,
    headers: dict | None = None,
) -> dict | None:
    """Safe POST → JSON helper. Returns None on any failure.

    CRITICAL: When sending ``files`` (multipart), the ``Content-Type``
    header is removed from ``headers`` so that ``requests`` can set the
    correct multipart boundary.  If ``Content-Type: application/json``
    leaks through, the backend will not be able to parse the upload.

    On HTTP errors, logs the response body (server error detail) for debugging.
    """
    try:
        hdrs = dict(headers or {})
        if files:
            # ── CRITICAL FIX: hapus Content-Type agar requests dapat
            #    mengeset multipart boundary yang benar ────────────────
            hdrs.pop("Content-Type", None)
            print(f"DEBUG indoor_api._post_json: POST {url} (multipart, timeout={timeout}s)", flush=True)
            resp = requests.post(url, files=files, timeout=timeout, headers=hdrs or None)
        else:
            print(f"DEBUG indoor_api._post_json: POST {url} (json, timeout={timeout}s)", flush=True)
            resp = requests.post(url, json=json_body or {}, timeout=timeout, headers=hdrs or None)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("indoor_api timeout POST %s (timeout=%ss)", url, timeout)
        print(f"❌ DEBUG indoor_api._post_json: TIMEOUT POST {url} (timeout={timeout}s)", flush=True)
    except requests.exceptions.ConnectionError:
        logger.warning("indoor_api connection-error POST %s", url)
        print(f"❌ DEBUG indoor_api._post_json: CONNECTION-ERROR POST {url} — backend unreachable", flush=True)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text[:1000]
        logger.warning(
            "indoor_api HTTP %s POST %s — detail: %s", status, url, detail
        )
        print(f"❌ DEBUG indoor_api._post_json: HTTP {status} POST {url} — response: {detail}", flush=True)
    except Exception as exc:
        logger.error("indoor_api unexpected error POST %s: %s", url, exc)
        print(f"❌ DEBUG indoor_api._post_json: UNEXPECTED ERROR POST {url}: {exc}", flush=True)
    return None


# ──────────────────────────────────────────────
# Public API functions
# ──────────────────────────────────────────────


def fetch_zones(readiness: dict | None = None, headers: dict | None = None) -> list[dict]:
    """Fetch available indoor zones from backend.

    Returns a list of zone dicts (or empty list on failure).
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v1/data/indoor/zones"
    data = _get_json(url, timeout=_INDOOR_TIMEOUT_ZONES, headers=headers)
    if isinstance(data, dict):
        zones = data.get("zones")
        if isinstance(zones, list):
            return zones
    return []


def fetch_latest(
    zone_id: str,
    readiness: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """Fetch latest indoor sensor reading for a zone.

    Returns a dict or None on failure.
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v1/data/indoor/latest"
    return _get_json(url, params={"zone_id": zone_id}, timeout=_INDOOR_TIMEOUT_LATEST, headers=headers)


def fetch_timeseries(
    zone_id: str,
    hours: int = 24,
    readiness: dict | None = None,
    headers: dict | None = None,
) -> list[dict]:
    """Fetch indoor timeseries data for a zone.

    Returns a list of point dicts (or empty list on failure).
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v1/data/indoor/timeseries"
    data = _get_json(
        url,
        params={"zone_id": zone_id, "hours": hours},
        timeout=_INDOOR_TIMEOUT_TIMESERIES,
        headers=headers,
    )
    if isinstance(data, dict):
        points = data.get("points")
        if isinstance(points, list):
            return points
    return []


def upload_csv_preview(
    file_bytes: bytes,
    filename: str,
    readiness: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """Upload a CSV file via Phase-4 CSV Upload API (upload step only).

    Automatically remaps frontend column names to backend column names
    before sending the CSV to the API.

    POST /api/v4/csv/upload → returns {"job_id": ..., "upload_id": ..., "status": ...}

    The background service auto-processes the preview, so this function
    only handles the upload step. Use get_csv_status() to poll for results.

    Returns the upload result dict or None on failure.
    """
    base = _indoor_base(readiness)
    # Remap columns: frontend (timestamp, zone_id, temp_c, rh_pct, co2_ppm)
    # → backend (timestamp_utc, zone_id, zone_temp_c, zone_rh_pct, co2_ppm)
    mapped_bytes = _remap_csv_columns(file_bytes)
    print(f"DEBUG indoor_api.upload_csv_preview: filename={filename}, original_bytes={len(file_bytes)}, mapped_bytes={len(mapped_bytes)}", flush=True)
    logger.info("upload_csv_preview called: filename=%s, size=%d -> mapped=%d", filename, len(file_bytes), len(mapped_bytes))

    upload_url = f"{base}/api/v4/csv/upload"
    files = {"file": (filename, mapped_bytes, "text/csv")}
    print(f"DEBUG indoor_api.upload_csv_preview: POST {upload_url}", flush=True)
    upload_result = _post_json(upload_url, files=files, timeout=_INDOOR_TIMEOUT_CSV_PREVIEW, headers=headers)
    print(f"DEBUG indoor_api.upload_csv_preview: POST result={upload_result}", flush=True)

    if upload_result is None:
        logger.warning("indoor_api CSV upload failed (backend unreachable)")
        return None

    job_id = upload_result.get("job_id")
    upload_id = upload_result.get("upload_id")
    if not job_id:
        logger.warning("indoor_api CSV upload succeeded but no job_id returned: %s", upload_result)
        return {"error": "Upload succeeded but no job_id returned"}

    print(f"DEBUG indoor_api.upload_csv_preview: success job_id={job_id}, upload_id={upload_id}", flush=True)
    return {
        "job_id": job_id,
        "upload_id": upload_id or job_id,
        "status": upload_result.get("status", "uploaded"),
    }


def get_csv_status(
    job_id: str,
    readiness: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """Get the current status of a CSV upload job via Phase-4 API.

    GET /api/v4/csv/status/{job_id} → returns the full job status dict.

    The response includes:
      - job.status: one of PENDING, PROCESSING, PREVIEW_READY, COMMITTED, ERROR
      - job.stats: {total_rows, valid_rows, rejected_rows, ...}
      - job.preview_data: list of sample rows (when PREVIEW_READY)

    Returns the status dict or None on failure.
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v4/csv/status/{job_id}"
    print(f"DEBUG indoor_api.get_csv_status: GET {url}", flush=True)
    status_result = _get_json(url, timeout=_INDOOR_TIMEOUT_CSV_STATUS, headers=headers)
    print(f"DEBUG indoor_api.get_csv_status: result={status_result}", flush=True)
    if status_result is None:
        logger.warning("indoor_api CSV status check failed for job %s", job_id)
        return None
    return status_result


def commit_csv_upload(
    upload_id: str,
    readiness: dict | None = None,
    headers: dict | None = None,
) -> dict | None:
    """Commit a previously previewed CSV upload via Phase-4 CSV Upload API.

    Posts to POST /api/v4/csv/commit/{upload_id} to persist the data.

    Returns the commit result dict or None on failure.
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v4/csv/commit/{upload_id}"
    return _post_json(
        url, json_body={}, timeout=_INDOOR_TIMEOUT_CSV_COMMIT, headers=headers
    )


def fetch_maintenance_status(readiness: dict | None = None, headers: dict | None = None) -> dict | None:
    """Check if backend is in maintenance mode.

    Returns a dict or None on failure.
    """
    base = _indoor_base(readiness)
    url = f"{base}/api/v1/system/maintenance-status"
    return _get_json(url, timeout=_INDOOR_TIMEOUT_MAINTENANCE, headers=headers)
