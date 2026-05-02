from typing import Any, Dict, Optional, Tuple
import requests
from ecoaims_frontend.services.http_trace import trace_headers

def _merge_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merge trace headers with optional extra headers (e.g. JWT auth)."""
    hdrs: Dict[str, str] = {}
    th = trace_headers()
    if th:
        hdrs.update(th)
    if extra:
        hdrs.update(extra)
    return hdrs

def _format_http_error(path: str, e: requests.HTTPError) -> str:
    try:
        status = e.response.status_code
        text = (e.response.text or "").strip()[:300]
        return f"endpoint_http_error:{path} status={status} body={text}"
    except Exception:
        return f"endpoint_http_error:{path} {str(e)}"

def _build_url(path: str, *, base_url: Optional[str]) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}{path}"

def get_runtime_config(*, base_url: Optional[str], headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    url = _build_url("/api/system/runtime-config", base_url=base_url)
    try:
        hdrs = _merge_headers(headers)
        resp = requests.get(url, timeout=4.0, headers=hdrs)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None, "invalid_json_shape"
        return data, None
    except requests.Timeout:
        return None, "timeout:/api/system/runtime-config"
    except requests.HTTPError as e:
        return None, _format_http_error("/api/system/runtime-config", e)
    except requests.RequestException as e:
        return None, f"request_error:/api/system/runtime-config {str(e)}"
    except ValueError:
        return None, "invalid_json"

def post_live_energy_file(file_content_base64: str, filename: Optional[str], *, base_url: Optional[str], headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    url = _build_url("/api/system/runtime-config/live-energy-file", base_url=base_url)
    payload = {"file_content_base64": file_content_base64}
    if isinstance(filename, str) and filename.strip():
        payload["filename"] = filename.strip()
    try:
        hdrs = _merge_headers(headers)
        resp = requests.post(url, json=payload, timeout=6.0, headers=hdrs)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None, "invalid_json_shape"
        return data, None
    except requests.Timeout:
        return None, "timeout:/api/system/runtime-config/live-energy-file"
    except requests.HTTPError as e:
        return None, _format_http_error("/api/system/runtime-config/live-energy-file", e)
    except requests.RequestException as e:
        return None, f"request_error:/api/system/runtime-config/live-energy-file {str(e)}"
    except ValueError:
        return None, "invalid_json"

def post_live_energy_enabled(enabled: bool, *, base_url: Optional[str], headers: Optional[Dict[str, str]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    url = _build_url("/api/system/runtime-config/live-energy-file", base_url=base_url)
    payload = {"enabled": bool(enabled)}
    try:
        hdrs = _merge_headers(headers)
        resp = requests.post(url, json=payload, timeout=6.0, headers=hdrs)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            return None, "invalid_json_shape"
        return data, None
    except requests.Timeout:
        return None, "timeout:/api/system/runtime-config/live-energy-file"
    except requests.HTTPError as e:
        return None, _format_http_error("/api/system/runtime-config/live-energy-file", e)
    except requests.RequestException as e:
        return None, f"request_error:/api/system/runtime-config/live-energy-file {str(e)}"
    except ValueError:
        return None, "invalid_json"
