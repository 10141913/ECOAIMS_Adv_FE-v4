import datetime
import logging
import json
from dash import Input, Output, State, html
from ecoaims_frontend.config import ENERGY_LIMITS, LIVE_DATA_SOURCE
from ecoaims_frontend.components.gauges import create_gauge_figure
from ecoaims_frontend.components.charts import create_trend_graph
from ecoaims_frontend.components.impact import create_co2_impact_panel
from ecoaims_frontend.components.tables import create_status_table
from ecoaims_frontend.components.renewable_comparison import create_renewable_comparison_card
from ecoaims_frontend.components.battery import create_battery_visual
from ecoaims_frontend.components.alerts import create_alert_notification
from ecoaims_frontend.components.sensor_health import create_sensor_health_card
from ecoaims_frontend.services.data_service import (
    allow_local_simulation,
    fetch_dashboard_kpi,
    format_monitoring_failure_detail,
    get_energy_data,
    get_last_dashboard_kpi_diagnostic,
    get_last_monitoring_diagnostic,
    get_last_monitoring_endpoint_contract,
    update_trend_data,
)
from ecoaims_frontend.services.live_data_service import get_live_sensor_data
from ecoaims_frontend.services.live_state_push_service import maybe_push_live_state
from ecoaims_frontend.services.operational_policy import effective_feature_decision
from ecoaims_frontend.services.readiness_service import get_backend_readiness
from ecoaims_frontend.services.monitoring_diag import fetch_monitoring_diag
from ecoaims_frontend.services.monitoring_history_update import request_history_seed
from ecoaims_frontend.services import contract_registry
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.ui.contract_error_ui import render_contract_mismatch_error
from ecoaims_frontend.ui.contract_negotiation_error import render_contract_negotiation_error
from ecoaims_frontend.ui.error_ui import error_banner, status_banner

logger = logging.getLogger(__name__)


def _time_from_payload_records(data: dict) -> str | None:
    try:
        if not isinstance(data, dict):
            return None
        recs = data.get("records")
        if not isinstance(recs, list) or not recs:
            return None
        last = recs[-1] if isinstance(recs[-1], dict) else None
        if not isinstance(last, dict):
            return None
        ts = last.get("timestamp")
        if not isinstance(ts, str) or not ts:
            return None
        s = ts.strip()
        try:
            if s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(s)
            # Convert to local timezone and format hh:mm:ss
            return dt.astimezone().strftime("%H:%M:%S")
        except Exception:
            # Fallback: try to extract HH:MM:SS from ISO string
            if "T" in s and len(s.split("T")[-1]) >= 8:
                return s.split("T")[-1][:8]
            return s
    except Exception:
        return None

def _brief_attempts(attempts, limit: int = 3) -> str:
    rows = attempts if isinstance(attempts, list) else []
    tail = rows[-limit:] if len(rows) > limit else rows
    parts = []
    for a in tail:
        if not isinstance(a, dict):
            continue
        url = a.get("url")
        status = a.get("status")
        cls = a.get("error_class")
        ms = a.get("elapsed_ms")
        parts.append(f"{url} status={status} class={cls} elapsed_ms={ms}")
    return "\n".join(parts)


def _extract_missing_fields(errors) -> list[str]:
    rows = errors if isinstance(errors, list) else []
    out = set()
    for e in rows:
        s = str(e)
        if ":missing:" in s:
            out.add(s.split(":missing:")[-1].strip())
        elif s.startswith("missing:"):
            out.add(s.split("missing:", 1)[1].strip())
    return sorted([x for x in out if x])


def _expected_contract_label_for_endpoint(endpoint_key: str) -> str:
    idx = contract_registry.get_registry_cache()
    endpoint_map = idx.get("endpoint_map") if isinstance(idx.get("endpoint_map"), dict) else {}
    meta = endpoint_map.get(endpoint_key) if isinstance(endpoint_map.get(endpoint_key), dict) else {}
    mid = str(meta.get("contract_manifest_id") or "").strip()
    mh = str(meta.get("contract_manifest_hash") or "").strip()
    if mid and mh:
        return f"{mid}@{mh}"
    if mid:
        return mid
    return "Unknown"


def _monitoring_contract_mismatch_component(readiness: dict | None = None) -> html.Div:
    readiness = readiness if isinstance(readiness, dict) else {}
    endpoint_contract = get_last_monitoring_endpoint_contract()
    diag = get_last_monitoring_diagnostic()
    errors = endpoint_contract.get("errors") if isinstance(endpoint_contract.get("errors"), list) else []
    missing_fields = _extract_missing_fields(errors)
    expected = readiness.get("registry_manifest_id") or readiness.get("contract_manifest_id") or _expected_contract_label_for_endpoint("GET /api/energy-data")
    expected_hash = readiness.get("registry_manifest_hash") or readiness.get("contract_manifest_hash")
    expected_label = f"{expected}@{expected_hash}" if expected_hash and "@" not in str(expected) else str(expected)
    details = {
        "component_label": "Energy Data Contract (/api/energy-data)",
        "expected_version": expected_label,
        "actual_version": "Unknown",
        "compatibility": {"reason": "runtime_endpoint_contract_mismatch"},
        "missing_fields": missing_fields,
        "operator_hint": "Fitur Monitoring tidak bisa memproses payload karena kontrak mismatch. Buka banner Backend di header untuk lihat registry/contract version, lalu jalankan make doctor-stack dan cek /api/startup-info serta /api/contracts/index.",
        "actions": {
            "retry_contract_negotiation": {"enabled": False, "hint": "Belum aktif: belum ada mekanisme negotiation/handshake otomatis di FE."},
            "switch_to_simulation": {"enabled": False, "hint": "Belum aktif: mode simulasi dikontrol oleh env/policy, bukan tombol UI."},
            "view_contract_details": {"enabled": False, "hint": "Belum aktif: gunakan endpoint /api/contracts/{manifest_id} dari backend untuk detail."},
        },
        "technical": {
            "endpoint": "GET /api/energy-data",
            "source": endpoint_contract.get("source"),
            "errors": errors,
            "diagnostic": diag,
        },
    }
    return render_contract_mismatch_error(details)


def _monitoring_contract_negotiation_component() -> html.Div:
    diag = get_last_monitoring_diagnostic()
    nego = diag.get("negotiation") if isinstance(diag, dict) else None
    return render_contract_negotiation_error(nego if isinstance(nego, dict) else (diag if isinstance(diag, dict) else {}))


def _is_contract_negotiation_blocked(last_diag: dict, last_contract: dict) -> bool:
    cls = str((last_diag or {}).get("class") or (last_diag or {}).get("warning_class") or "")
    if cls.startswith("contract_negotiation"):
        return True
    return str((last_contract or {}).get("status") or "") == "blocked"


def _pill(text: str, *, bg: str, fg: str = "#ffffff") -> html.Span:
    return html.Span(
        str(text),
        style={
            "display": "inline-block",
            "padding": "2px 8px",
            "borderRadius": "999px",
            "backgroundColor": bg,
            "color": fg,
            "fontSize": "12px",
            "fontWeight": "bold",
            "marginRight": "6px",
        },
    )


def _comparison_indicators(diag: dict) -> html.Div:
    d = diag if isinstance(diag, dict) else {}
    applied_limit = d.get("applied_limit")
    returned = d.get("returned_records_len")
    available = d.get("available_records_len")
    trimmed = d.get("trimmed")
    records_len = d.get("records_len")
    maybe_trimmed = bool(d.get("data_maybe_trimmed"))
    diag_count = d.get("diag_energy_data_records_count")
    gap = d.get("data_trim_gap")

    pills = []
    if isinstance(returned, int):
        pills.append(_pill(f"RETURNED={returned}", bg="#5d6d7e"))
    elif isinstance(records_len, int):
        pills.append(_pill(f"RETURNED={int(records_len)}", bg="#5d6d7e"))
    if isinstance(applied_limit, int):
        pills.append(_pill(f"LIMIT={applied_limit}", bg="#2e86c1"))
    if isinstance(available, int):
        pills.append(_pill(f"AVAILABLE={available}", bg="#7d3c98"))
    if isinstance(trimmed, bool) and trimmed:
        pills.append(_pill("TRIMMED=true", bg="#c0392b"))
    elif maybe_trimmed:
        pills.append(_pill("MAYBE_TRIMMED", bg="#d35400"))
    if isinstance(diag_count, int) and maybe_trimmed and isinstance(gap, int):
        pills.append(_pill(f"DIAG_COUNT={diag_count}", bg="#424949"))
        pills.append(_pill(f"GAP={gap}", bg="#424949"))

    if not pills:
        return html.Div()
    spaced = []
    for i, p in enumerate(pills):
        if i > 0:
            spaced.append(html.Span(" "))
        spaced.append(p)
    return html.Div(spaced, style={"marginBottom": "8px"})


def _fmt_audit_value(v) -> str:
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, int):
        return str(int(v))
    if v is None:
        return "n/a"
    return str(v)


def _comparison_audit_rows(diag: dict) -> html.Pre:
    d = diag if isinstance(diag, dict) else {}
    payload_records_len = d.get("payload_records_len")
    if not isinstance(payload_records_len, int):
        payload_records_len = d.get("records_len")
    returned_records_len = d.get("returned_records_len")
    if not isinstance(returned_records_len, int):
        returned_records_len = d.get("comparison_returned_records_len")
    applied_limit = d.get("applied_limit")
    available_records_len = d.get("available_records_len")
    trimmed = d.get("trimmed")
    lines = [
        f"payload_records_len={_fmt_audit_value(payload_records_len)}",
        f"returned_records_len={_fmt_audit_value(returned_records_len)}",
        f"applied_limit={_fmt_audit_value(applied_limit)}",
        f"available_records_len={_fmt_audit_value(available_records_len)}",
        f"trimmed={_fmt_audit_value(trimmed)}",
    ]
    return html.Pre(
        "\n".join(lines),
        style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "12px", "opacity": 0.9, "margin": "0 0 8px 0"},
    )


def _comparison_trim_warning(diag: dict) -> html.Div:
    d = diag if isinstance(diag, dict) else {}
    trimmed = d.get("trimmed")
    maybe_trimmed = bool(d.get("data_maybe_trimmed"))
    diag_count = d.get("diag_energy_data_records_count")
    returned = d.get("returned_records_len")
    if not isinstance(returned, int):
        returned = d.get("comparison_returned_records_len")
    gap = d.get("data_trim_gap")
    if isinstance(trimmed, bool) and trimmed:
        msg = "Peringatan operator: payload /api/energy-data dipangkas (trimmed=true). Cek LIMIT/RETURNED/AVAILABLE dan pastikan backend mengembalikan history yang cukup."
        return html.Div(msg, style={"border": "1px solid #c0392b", "backgroundColor": "#fdecea", "borderRadius": "6px", "padding": "8px 10px", "marginBottom": "8px"})
    if maybe_trimmed:
        msg = f"Peringatan operator: indikasi data dipotong oleh limit/window. diag_count={diag_count} returned_records_len={returned} gap={gap}. Cek LIMIT/RETURNED/AVAILABLE."
        return html.Div(msg, style={"border": "1px solid #d35400", "backgroundColor": "#fdf2e9", "borderRadius": "6px", "padding": "8px 10px", "marginBottom": "8px"})
    return html.Div()


def comparison_update_button_state(diag: dict) -> tuple[bool, dict, str | None]:
    backend_ok = bool((diag or {}).get("backend_ok"))
    comparison_ready = bool((diag or {}).get("comparison_ready"))
    reasons = (diag or {}).get("reasons") if isinstance((diag or {}).get("reasons"), list) else []
    min_hist = int((diag or {}).get("min_history_for_comparison") or 0)
    records_len = int((diag or {}).get("records_len") or (diag or {}).get("records_count") or 0)
    returned_len = int((diag or {}).get("returned_records_len") or (diag or {}).get("comparison_returned_records_len") or records_len)

    provenance = "diag_monitoring" if backend_ok else "diag_monitoring_failed"
    contract_ok = (diag or {}).get("energy_contract_ok")
    contract_src = (diag or {}).get("energy_contract_source")
    min_source = (diag or {}).get("min_history_source")
    btn_style = {"marginLeft": "0px"}
    link_style: dict = {"marginLeft": "10px", "textDecoration": "underline"}
    btn_disabled = True
    action_hint = None
    if backend_ok and not comparison_ready and any("insufficient_history_for_comparison" in str(x) for x in reasons):
        btn_disabled = False
        btn_style = {"marginLeft": "0px"}
        link_style = {"marginLeft": "10px", "textDecoration": "underline"}
        action_hint = f"Data historis belum cukup. payload_records_len={records_len} returned_records_len={returned_len} butuh minimal {min_hist} (threshold_source={min_source})."
    else:
        btn_style = {"display": "none"}
        link_style = {"display": "none"}
    _ = provenance, contract_ok, contract_src
    return btn_disabled, btn_style, link_style, action_hint


def comparison_status_banner(diag: dict) -> html.Div:
    backend_ok = bool((diag or {}).get("backend_ok"))
    comparison_ready = bool((diag or {}).get("comparison_ready"))
    reasons = (diag or {}).get("reasons") if isinstance((diag or {}).get("reasons"), list) else []
    min_hist = int((diag or {}).get("min_history_for_comparison") or 0)
    records_len = int((diag or {}).get("payload_records_len") or (diag or {}).get("records_len") or (diag or {}).get("records_count") or 0)
    returned_len = int((diag or {}).get("returned_records_len") or (diag or {}).get("comparison_returned_records_len") or records_len)
    applied_limit = (diag or {}).get("applied_limit")
    available_len = (diag or {}).get("available_records_len")
    trimmed_flag = (diag or {}).get("trimmed")
    diag_count = (diag or {}).get("diag_energy_data_records_count")
    maybe_trimmed = bool((diag or {}).get("data_maybe_trimmed"))
    trim_gap = (diag or {}).get("data_trim_gap")
    attempts = (diag or {}).get("attempts") if isinstance((diag or {}).get("attempts"), list) else []

    provenance = "diag_monitoring" if backend_ok else "diag_monitoring_failed"
    contract_ok = (diag or {}).get("energy_contract_ok")
    contract_src = (diag or {}).get("energy_contract_source")
    min_source = (diag or {}).get("min_history_source")

    trim_warn = ""
    if isinstance(trimmed_flag, bool) and trimmed_flag:
        trim_warn = " WARNING: trimmed=true (payload dipangkas)."
    elif maybe_trimmed:
        trim_warn = f" WARNING: indikasi data dipotong. diag_count={diag_count} returned_records_len={returned_len} gap={trim_gap}."
    audit = (
        f" payload_records_len={records_len}"
        f" returned_records_len={returned_len}"
        f" applied_limit={_fmt_audit_value(applied_limit)}"
        f" available_records_len={_fmt_audit_value(available_len)}"
        f" trimmed={_fmt_audit_value(trimmed_flag)}"
    )

    if backend_ok and (contract_ok is False) and any("runtime_endpoint_contract_mismatch" in str(x) for x in reasons):
        energy = (diag or {}).get("energy_data") if isinstance((diag or {}).get("energy_data"), dict) else {}
        actual_version = energy.get("contract_manifest_version") or energy.get("contract_version") or energy.get("schema_version") or "Unknown"
        expected = _expected_contract_label_for_endpoint("GET /api/energy-data")
        missing_fields = _extract_missing_fields((diag or {}).get("energy_contract_errors"))
        details = {
            "component_label": "Energy Data Contract (/api/energy-data)",
            "expected_version": expected,
            "actual_version": actual_version,
            "compatibility": {"reason": "Payload /api/energy-data tidak sesuai kontrak minimum"},
            "missing_fields": missing_fields,
            "operator_hint": "Comparison tidak bisa READY karena payload energy-data gagal validasi kontrak. Pastikan backend kanonik dan registry kontrak sinkron, lalu cek field yang hilang/tipe salah di Technical Details.",
            "actions": {
                "retry_contract_negotiation": {"enabled": False, "hint": "Belum aktif: belum ada negotiation/handshake runtime untuk endpoint ini."},
                "switch_to_simulation": {"enabled": False, "hint": "Belum aktif: gunakan ALLOW_LOCAL_SIMULATION_FALLBACK + DEBUG_MODE (dan non-canonical lane) jika ingin fallback simulasi."},
                "view_contract_details": {"enabled": False, "hint": "Belum aktif: buka /api/contracts/index dan /api/contracts/{manifest_id}."},
            },
            "technical": {
                "endpoint": "GET /api/energy-data",
                "energy_contract_source": contract_src,
                "energy_contract_errors": (diag or {}).get("energy_contract_errors"),
                "payload_keys": sorted([str(k) for k in energy.keys()]) if isinstance(energy, dict) else [],
            },
        }
        return html.Div([_comparison_indicators(diag), _comparison_trim_warning(diag), _comparison_audit_rows(diag), render_contract_mismatch_error(details)])

    if backend_ok and any("contract_negotiation_incompatible" in str(x) for x in reasons):
        nego = (diag or {}).get("negotiation") if isinstance((diag or {}).get("negotiation"), dict) else {}
        return html.Div([_comparison_indicators(diag), _comparison_trim_warning(diag), _comparison_audit_rows(diag), render_contract_negotiation_error(nego)])

    if backend_ok and not comparison_ready and any("insufficient_history_for_comparison" in str(x) for x in reasons):
        detail = f"provenance={provenance} reason=insufficient_history_for_comparison min_source={min_source} need_min_records={min_hist}{audit} diag_count={diag_count} energy_data_contract_ok={contract_ok} source={contract_src}"
        message = f"DEGRADED: Data tidak cukup untuk comparison. Butuh minimal={min_hist}.{audit}.{trim_warn}"
        return html.Div([_comparison_indicators(diag), _comparison_trim_warning(diag), _comparison_audit_rows(diag), status_banner("Monitoring", "Comparison degraded", detail=detail, message=message)])

    if backend_ok and comparison_ready:
        detail = f"provenance={provenance} status=ready min_source={min_source} need_min_records={min_hist}{audit} diag_count={diag_count} energy_data_contract_ok={contract_ok} source={contract_src}"
        message = f"READY: Threshold minimal={min_hist}.{audit}.{trim_warn}"
        return html.Div([_comparison_indicators(diag), _comparison_trim_warning(diag), _comparison_audit_rows(diag), status_banner("Monitoring", "Comparison ready", detail=detail, message=message)])

    if not backend_ok:
        brief = _brief_attempts(attempts)
        detail = f"provenance={provenance} reasons={reasons} energy_data_contract_ok={contract_ok} source={contract_src} last_attempts={brief}"
        message = "WAITING: backend tidak responsif atau /diag/monitoring tidak OK."
        return html.Div([_comparison_indicators(diag), _comparison_trim_warning(diag), _comparison_audit_rows(diag), status_banner("Monitoring", "Waiting for backend (Comparison)", detail=detail, message=message)])

    return html.Div()

def register_callbacks(app):
    """
    Registers all Dash callbacks to the application instance.
    
    Args:
        app (dash.Dash): The Dash application instance.
    """
    
    _dashboard_cache: dict = {"key": None, "out": None}

    def _compute_dashboard(n, current_trend_data, readiness):
        key = (
            int(n) if isinstance(n, int) else -1,
            int(len(current_trend_data or [])),
            str((readiness or {}).get("base_url") or "") if isinstance(readiness, dict) else "",
        )
        if _dashboard_cache.get("key") == key and _dashboard_cache.get("out") is not None:
            return _dashboard_cache.get("out")
        try:
            if n is None:
                empty_fig = {"data": [], "layout": {}}
                out = (empty_fig, empty_fig, "", empty_fig, empty_fig, empty_fig, html.Div(), "", "", "", current_trend_data or [])
                _dashboard_cache["key"] = key
                _dashboard_cache["out"] = out
                return out

            r = readiness if isinstance(readiness, dict) else get_backend_readiness()
            eff = effective_feature_decision("monitoring", r)

            if eff.get("final_mode") == "blocked":
                empty_fig = {"data": [], "layout": {}}
                msg = "\n".join([str(x) for x in (eff.get("reason_chain") or [])])
                out = (
                    empty_fig,
                    empty_fig,
                    html.Div(),
                    empty_fig,
                    empty_fig,
                    empty_fig,
                    status_banner("Monitoring", "Monitoring blocked", f"provenance={eff.get('provenance')}\n{msg}"),
                    html.Div(),
                    html.Div(),
                    html.Div(),
                    current_trend_data or [],
                )
                _dashboard_cache["key"] = key
                _dashboard_cache["out"] = out
                return out

            if eff.get("final_mode") == "placeholder" and (not allow_local_simulation()):
                empty_fig = {"data": [], "layout": {}}
                msg = format_monitoring_failure_detail("backend_unavailable_for_monitoring")
                last_diag = get_last_monitoring_diagnostic()
                last_contract = get_last_monitoring_endpoint_contract()
                if _is_contract_negotiation_blocked(last_diag, last_contract):
                    banner = _monitoring_contract_negotiation_component()
                elif str(last_diag.get("class") or "") == "runtime_endpoint_contract_mismatch" or str(last_contract.get("status") or "") == "mismatch":
                    banner = _monitoring_contract_mismatch_component(r)
                else:
                    banner = status_banner("Monitoring", "Waiting for backend (Monitoring)", msg) if isinstance(n, int) and n <= 2 else error_banner("Monitoring", "Gagal memuat data Monitoring", msg)
                out = (empty_fig, empty_fig, html.Div(), empty_fig, empty_fig, empty_fig, banner, html.Div(), html.Div(), html.Div(), current_trend_data or [])
                _dashboard_cache["key"] = key
                _dashboard_cache["out"] = out
                return out

            sensor_health_card = html.Div()

            if LIVE_DATA_SOURCE == 'hybrid' or LIVE_DATA_SOURCE == 'csv':
                live_data = get_live_sensor_data()
                sensor_health_card = create_sensor_health_card(live_data['health'])
                live_supply = live_data['supply']

                base_url = str(r.get("base_url") or "").rstrip("/")
                if base_url:
                    maybe_push_live_state(base_url=base_url, live_data=live_data, stream_id="default")

                fallback_data = get_energy_data(skip_backend=eff.get("final_mode") != "live", base_url=base_url)
                if not isinstance(fallback_data, dict) or not fallback_data:
                    empty_fig = {"data": [], "layout": {}}
                    msg = format_monitoring_failure_detail("backend_unavailable_for_hybrid_fallback")
                    last_diag = get_last_monitoring_diagnostic()
                    last_contract = get_last_monitoring_endpoint_contract()
                    if _is_contract_negotiation_blocked(last_diag, last_contract):
                        banner = _monitoring_contract_negotiation_component()
                    elif str(last_diag.get("class") or "") == "runtime_endpoint_contract_mismatch" or str(last_contract.get("status") or "") == "mismatch":
                        banner = _monitoring_contract_mismatch_component(r)
                    else:
                        banner = status_banner("Monitoring", "Waiting for backend (Monitoring)", msg) if isinstance(n, int) and n <= 2 else error_banner("Monitoring", "Gagal memuat data Monitoring", msg)
                    out = (empty_fig, empty_fig, html.Div(), empty_fig, empty_fig, empty_fig, banner, html.Div(), html.Div(), sensor_health_card, current_trend_data or [])
                    _dashboard_cache["key"] = key
                    _dashboard_cache["out"] = out
                    return out
                sm = fallback_data.get("state_meta") if isinstance(fallback_data, dict) else None
                if not isinstance(sm, dict):
                    sm = {}
                if not sm.get("timestamp"):
                    ts = fallback_data.get("data_timestamp") if isinstance(fallback_data, dict) else None
                    if isinstance(ts, str) and ts.strip():
                        sm = {**sm, "source": sm.get("source") or "energy_data", "timestamp": ts.strip()}
                sensor_health_card = create_sensor_health_card(
                    live_data.get("health") if isinstance(live_data, dict) else {},
                    state_meta=sm,
                )

                merged_data = {}
                state_meta = fallback_data.get("state_meta") if isinstance(fallback_data, dict) else None
                state_stale = bool(isinstance(state_meta, dict) and state_meta.get("stale") is True)

                def get_value(sensor_key, live_key, max_limit):
                    live_val = live_supply.get(live_key)
                    fb = fallback_data.get(sensor_key, {}) if isinstance(fallback_data, dict) else {}
                    fb_val = fb.get('value', 0) if isinstance(fb, dict) else 0
                    fb_src = fb.get('source', 'backend') if isinstance(fb, dict) else 'backend'

                    if str(fb_src) == 'backend_state' and not state_stale:
                        return {'value': fb_val, 'max': max_limit, 'source': fb_src}
                    if live_val is not None:
                        return {'value': live_val, 'max': max_limit, 'source': 'live'}
                    return {'value': fb_val, 'max': max_limit, 'source': fb_src}

                merged_data['solar'] = get_value('solar', 'Solar PV', ENERGY_LIMITS['solar'])
                merged_data['wind'] = get_value('wind', 'Wind Turbine', ENERGY_LIMITS['wind'])
                merged_data['grid'] = get_value('grid', 'PLN/Grid', ENERGY_LIMITS['grid'])
                merged_data['biofuel'] = get_value('biofuel', 'Biofuel', ENERGY_LIMITS['biofuel'])

                live_batt = live_supply.get('Battery')
                if live_batt is not None:
                    try:
                        live_batt = float(live_batt)
                    except Exception:
                        live_batt = None
                batt_fb = fallback_data.get('battery', {}) if isinstance(fallback_data, dict) else {}
                batt_fb_src = batt_fb.get('source') if isinstance(batt_fb, dict) else None
                if str(batt_fb_src) == 'backend_state' and not state_stale:
                    merged_data['battery'] = dict(batt_fb)
                elif live_batt is not None:
                    batt_max_live = float(ENERGY_LIMITS['battery'])
                    live_batt = max(0.0, min(float(live_batt), batt_max_live))
                    min_allowed = batt_max_live * 0.2
                    if live_batt <= 0.0 or (batt_max_live > 0 and live_batt < min_allowed):
                        live_batt = None
                    if live_batt is not None:
                        batt_status = batt_fb.get('status') if isinstance(batt_fb, dict) else None
                        if not isinstance(batt_status, str) or not batt_status.strip():
                            batt_status = "Unknown"
                        merged_data['battery'] = {
                            'value': live_batt,
                            'max': ENERGY_LIMITS['battery'],
                            'status': batt_status,
                            'source': 'live'
                        }
                    else:
                        batt = fallback_data.get('battery', {}) if isinstance(fallback_data, dict) else {}
                        batt_val = batt.get('value', 0) if isinstance(batt, dict) else 0
                        batt_max = batt.get('max', ENERGY_LIMITS['battery']) if isinstance(batt, dict) else ENERGY_LIMITS['battery']
                        batt_status = batt.get('status', 'Discharging') if isinstance(batt, dict) else 'Discharging'
                        batt_src = batt.get('source', 'backend') if isinstance(batt, dict) else 'backend'
                        merged_data['battery'] = {
                            'value': batt_val,
                            'max': batt_max,
                            'value_3h': batt.get('value_3h') if isinstance(batt, dict) else None,
                            'status': batt_status,
                            'source': batt_src,
                        }
                else:
                    batt = fallback_data.get('battery', {}) if isinstance(fallback_data, dict) else {}
                    batt_val = batt.get('value', 0) if isinstance(batt, dict) else 0
                    batt_max = batt.get('max', ENERGY_LIMITS['battery']) if isinstance(batt, dict) else ENERGY_LIMITS['battery']
                    batt_status = batt.get('status', 'Discharging') if isinstance(batt, dict) else 'Discharging'
                    batt_src = batt.get('source', 'backend') if isinstance(batt, dict) else 'backend'
                    merged_data['battery'] = {
                        'value': batt_val,
                        'max': batt_max,
                        'value_3h': batt.get('value_3h') if isinstance(batt, dict) else None,
                        'status': batt_status,
                        'source': batt_src,
                    }

                data = merged_data
            else:
                base_url = str(r.get("base_url") or "").rstrip("/")
                # Bypass fail-closed gating: jika backend OK menurut readiness/diag, selalu coba fetch backend nyata
                data = get_energy_data(skip_backend=False, base_url=base_url)
                if not isinstance(data, dict) or not data:
                    empty_fig = {"data": [], "layout": {}}
                    msg = format_monitoring_failure_detail("backend_unavailable_for_monitoring")
                    last_diag = get_last_monitoring_diagnostic()
                    last_contract = get_last_monitoring_endpoint_contract()
                    if _is_contract_negotiation_blocked(last_diag, last_contract):
                        banner = _monitoring_contract_negotiation_component()
                    elif str(last_diag.get("class") or "") == "runtime_endpoint_contract_mismatch" or str(last_contract.get("status") or "") == "mismatch":
                        banner = _monitoring_contract_mismatch_component(r)
                    else:
                        banner = status_banner("Monitoring", "Waiting for backend (Monitoring)", msg) if isinstance(n, int) and n <= 2 else error_banner("Monitoring", "Gagal memuat data Monitoring", msg)
                    out = (empty_fig, empty_fig, html.Div(), empty_fig, empty_fig, empty_fig, banner, html.Div(), html.Div(), html.Div(), current_trend_data or [])
                    _dashboard_cache["key"] = key
                    _dashboard_cache["out"] = out
                    return out

            current_time = _time_from_payload_records(data) or datetime.datetime.now().strftime("%H:%M:%S")
            total_consumption = (
                data['solar']['value'] +
                data['wind']['value'] +
                data['grid']['value'] +
                data.get('biofuel', {}).get('value', 0) +
                (data['battery']['value'] * 0.1)
            )
            renewable_supply = (
                data['solar']['value'] +
                data['wind']['value'] +
                data.get('biofuel', {}).get('value', 0)
            )

            trend_in = list(current_trend_data or [])
            trend_data = update_trend_data(trend_in, total_consumption, renewable_supply, current_time)

            solar_fig = create_gauge_figure(data['solar']['value'], data['solar']['max'], source=data['solar'].get('source', 'sim'))
            wind_fig = create_gauge_figure(data['wind']['value'], data['wind']['max'], source=data['wind'].get('source', 'sim'))
            battery_visual = create_battery_visual(
                data['battery']['value'],
                data['battery']['max'],
                data['battery'].get('status', 'Discharging'),
                soc_pct=data['battery'].get('soc_pct'),
                soc=data['battery'].get('soc'),
            )
            grid_fig = create_gauge_figure(data['grid']['value'], data['grid']['max'], source=data['grid'].get('source', 'sim'))
            biofuel_fig = create_gauge_figure(data['biofuel']['value'], data['biofuel']['max'], source=data['biofuel'].get('source', 'sim'))
            trend_fig = create_trend_graph(trend_data)
            alert_component = create_alert_notification(data, total_consumption, renewable_supply)
            co2_panel = create_co2_impact_panel(data['grid']['value'], total_consumption)
            status_table = create_status_table(data)

            out = (solar_fig, wind_fig, battery_visual, grid_fig, biofuel_fig, trend_fig, alert_component, co2_panel, status_table, sensor_health_card, trend_data)
            _dashboard_cache["key"] = key
            _dashboard_cache["out"] = out
            return out
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
            empty_fig = {"data": [], "layout": {}}
            out = (empty_fig, empty_fig, html.Div(), empty_fig, empty_fig, empty_fig, error_banner("Monitoring", "Gagal memuat data Monitoring", str(e)), html.Div(), html.Div(), html.Div(), current_trend_data or [])
            _dashboard_cache["key"] = key
            _dashboard_cache["out"] = out
            return out

    def _dash_idx(idx: int):
        def f(n, current_trend_data, readiness):
            out = _compute_dashboard(n, current_trend_data, readiness)
            return out[idx]
        return f

    @app.callback(Output('solar-gauge', 'figure'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_solar(n, current_trend_data, readiness):
        return _dash_idx(0)(n, current_trend_data, readiness)

    @app.callback(Output('wind-gauge', 'figure'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_wind(n, current_trend_data, readiness):
        return _dash_idx(1)(n, current_trend_data, readiness)

    @app.callback(Output('battery-visual-container', 'children'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_battery(n, current_trend_data, readiness):
        return _dash_idx(2)(n, current_trend_data, readiness)

    @app.callback(Output('grid-gauge', 'figure'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_grid(n, current_trend_data, readiness):
        return _dash_idx(3)(n, current_trend_data, readiness)

    @app.callback(Output('biofuel-gauge', 'figure'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_biofuel(n, current_trend_data, readiness):
        return _dash_idx(4)(n, current_trend_data, readiness)

    @app.callback(Output('trend-graph', 'figure'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_trend(n, current_trend_data, readiness):
        return _dash_idx(5)(n, current_trend_data, readiness)

    @app.callback(Output('alert-container', 'children'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_alerts(n, current_trend_data, readiness):
        return _dash_idx(6)(n, current_trend_data, readiness)

    @app.callback(Output('co2-content', 'children'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_co2(n, current_trend_data, readiness):
        return _dash_idx(7)(n, current_trend_data, readiness)

    @app.callback(Output('resource-status-table', 'children'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_resource_status(n, current_trend_data, readiness):
        return _dash_idx(8)(n, current_trend_data, readiness)

    @app.callback(Output('sensor-health-container', 'children'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_sensor_health(n, current_trend_data, readiness):
        return _dash_idx(9)(n, current_trend_data, readiness)

    @app.callback(Output('trend-data-store', 'data'), Input('interval-component', 'n_intervals'), [State('trend-data-store', 'data'), State("backend-readiness-store", "data")])
    def update_trend_store(n, current_trend_data, readiness):
        return _dash_idx(10)(n, current_trend_data, readiness)

    @app.callback(
        [
            Output("renewable-comparison-content", "children"),
            Output("renewable-comparison-status", "children"),
            Output("comparison-update-history-btn", "disabled"),
            Output("comparison-update-history-btn", "style"),
            Output("comparison-history-instructions-link", "style"),
            Output("comparison-update-history-result", "children"),
            Output("comparison-diagnostics-text", "value"),
            Output("comparison-update-click-store", "data"),
        ],
        [Input("interval-1h", "n_intervals"), Input("comparison-update-history-btn", "n_clicks")],
        [State("backend-readiness-store", "data"), State("comparison-update-click-store", "data")],
    )
    def update_comparison(n, n_clicks, readiness, last_click):
        """
        Callback to update the renewable comparison card every 1 hour.
        """
        try:
            r = readiness if isinstance(readiness, dict) else {}
            base = effective_base_url(r)

            click_now = int(n_clicks or 0)
            click_prev = int(last_click or 0)

            diag = fetch_monitoring_diag(base)
            diag_json = json.dumps(diag or {}, sort_keys=True, separators=(",", ":"))
            status = comparison_status_banner(diag)
            btn_disabled, btn_style, link_style, action_hint = comparison_update_button_state(diag)
            action_result = action_hint or ""

            if click_now > click_prev:
                desired_records = int(diag.get("min_history_for_comparison") or 0)
                if desired_records <= 0:
                    desired_records = 24
                seed = request_history_seed(base, stream_id="default", desired_records=desired_records)
                seed_json = json.dumps(seed or {}, sort_keys=True, separators=(",", ":"))
                diag = fetch_monitoring_diag(base)
                diag_json = json.dumps({**(diag or {}), "seed_attempt": seed} or {}, sort_keys=True, separators=(",", ":"))
                if seed.get("ok") is True:
                    action_result = f"Seed requested via {seed.get('seed_url')}. Refresh comparison otomatis."
                else:
                    action_result = f"Seed gagal: {seed.get('error_class')}. {seed.get('message')}"
                btn_disabled, btn_style, link_style, action_hint = comparison_update_button_state(diag)
                status = comparison_status_banner(diag)

            if (diag.get("backend_ok") is not True) or (diag.get("comparison_ready") is not True):
                return (
                    html.Div(),
                    status,
                    btn_disabled,
                    btn_style,
                    link_style,
                    action_result,
                    diag_json,
                    click_now,
                )

            r_eff = dict(r)
            if diag.get("backend_ok") is True:
                r_eff["backend_reachable"] = True
                if bool(r_eff.get("canonical_policy_required")) is not True:
                    if r_eff.get("backend_ready") is not True:
                        r_eff["backend_ready"] = True
                    if r_eff.get("contract_valid") is not True:
                        r_eff["contract_valid"] = True
                    if r_eff.get("registry_loaded") is not True:
                        r_eff["registry_loaded"] = True
                    caps = r_eff.get("capabilities") if isinstance(r_eff.get("capabilities"), dict) else {}
                    if not (isinstance(caps.get("comparison"), dict) and caps.get("comparison", {}).get("ready") is True):
                        caps["comparison"] = {"ready": True}
                    r_eff["capabilities"] = caps
            eff = effective_feature_decision("comparison", r_eff)
            if eff.get("final_mode") != "live":
                blocked = status_banner("Monitoring", "Comparison blocked", f"provenance={eff.get('provenance')}\n" + "\n".join([str(x) for x in (eff.get("reason_chain") or [])]))
                return html.Div(), blocked, True, {"display": "none"}, {"display": "none"}, "", diag_json, click_now

            base_url = str(r.get("base_url") or "").rstrip("/")
            data = get_energy_data(skip_backend=False, base_url=base_url)
            if not isinstance(data, dict) or not data:
                msg = _brief_attempts(diag.get("attempts"))
                last_diag = get_last_monitoring_diagnostic()
                last_contract = get_last_monitoring_endpoint_contract()
                if _is_contract_negotiation_blocked(last_diag, last_contract):
                    return html.Div(), _monitoring_contract_negotiation_component(), True, {"display": "none"}, {"display": "none"}, "", diag_json, click_now
                if str(last_diag.get("class") or "") == "runtime_endpoint_contract_mismatch" or str(last_contract.get("status") or "") == "mismatch":
                    return html.Div(), _monitoring_contract_mismatch_component(r), True, {"display": "none"}, {"display": "none"}, "", diag_json, click_now
                return (
                    html.Div(),
                    error_banner("Monitoring", "Gagal memuat komparasi energi terbarukan", msg or format_monitoring_failure_detail("backend_unavailable_for_monitoring_comparison")),
                    True,
                    {"display": "none"},
                    {"display": "none"},
                    "",
                    diag_json,
                    click_now,
                )

            status = comparison_status_banner(diag)
            return create_renewable_comparison_card(data), status, True, {"display": "none"}, {"display": "none"}, "", diag_json, click_now
        except Exception as e:
            logger.warning(f"Monitoring comparison update failed: {e}")
            empty = html.Div()
            return empty, error_banner("Monitoring", "Gagal memuat komparasi energi terbarukan", str(e)), True, {"display": "none"}, {"display": "none"}, "", "{}", int(n_clicks or 0)

    def _fmt_float(v, *, decimals: int = 2) -> str:
        try:
            if v is None:
                return "-"
            x = float(v)
            if decimals <= 0:
                return str(int(round(x)))
            return f"{x:.{decimals}f}"
        except Exception:
            return "-"

    def _kpi_card(title: str, value: str, *, unit: str | None = None, subtitle: str | None = None, badge: str | None = None) -> html.Div:
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(title, style={"fontSize": "12px", "color": "#566573"}),
                        html.Span(
                            badge,
                            style={
                                "fontSize": "10px",
                                "backgroundColor": "#ecf0f1",
                                "color": "#2c3e50",
                                "padding": "2px 8px",
                                "borderRadius": "999px",
                                "fontWeight": "bold",
                            },
                        )
                        if badge
                        else html.Span(),
                    ],
                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px", "gap": "10px"},
                ),
                html.Div(
                    [
                        html.Span(value, style={"fontSize": "22px", "fontWeight": "bold", "color": "#2c3e50"}),
                        html.Span((" " + unit) if unit else "", style={"fontSize": "12px", "color": "#566573", "marginLeft": "6px"}),
                    ]
                ),
                html.Div(subtitle or "", style={"fontSize": "11px", "color": "#7f8c8d", "marginTop": "6px"}) if subtitle else html.Div(),
            ],
            style={
                "border": "1px solid #ecf0f1",
                "borderRadius": "8px",
                "padding": "12px 14px",
                "backgroundColor": "#ffffff",
                "minWidth": "220px",
                "flex": "1",
            },
        )

    def _render_kpi_panel(payload: dict, *, base_url: str) -> html.Div:
        p = payload if isinstance(payload, dict) else {}
        kpi = p.get("kpi") if isinstance(p.get("kpi"), dict) else {}
        alerts = p.get("alerts") if isinstance(p.get("alerts"), list) else []

        updated_at = str(p.get("updated_at") or "").strip()
        contract_id = str(p.get("contract_manifest_id") or "").strip()
        contract_hash = str(p.get("contract_manifest_hash") or "").strip()
        stream_id = str(p.get("stream_id") or "").strip() or "default"

        eui_src_raw = kpi.get("eui_numerator_source") if isinstance(kpi.get("eui_numerator_source"), str) else (p.get("eui_numerator_source") if isinstance(p.get("eui_numerator_source"), str) else "")
        eui_src_key = str(eui_src_raw or "").strip().lower()
        if eui_src_key:
            if "sensor" in eui_src_key or "live" in eui_src_key:
                eui_src_badge = "Sensor/Live"
            elif "forecast" in eui_src_key or "demo" in eui_src_key:
                eui_src_badge = "Forecast/Demo"
            else:
                eui_src_badge = str(eui_src_raw).strip()[:24]
        else:
            eui_src_badge = None

        cards = [
            _kpi_card("Peak Load", _fmt_float(kpi.get("peak_load_kw")), unit="kW", subtitle="Target: -30% vs baseline (baseline required)"),
            _kpi_card("CO2 Emission", _fmt_float(kpi.get("total_emission")), unit="kg", subtitle="Target: -20% vs baseline (baseline required)"),
            _kpi_card(
                "EUI",
                _fmt_float(kpi.get("eui_kwh_per_m2") if "eui_kwh_per_m2" in kpi else (kpi.get("eui") if "eui" in kpi else None)),
                unit="kWh/m²",
                subtitle="Slot: butuh total_energy_kwh + building_area_m2",
                badge=eui_src_badge,
            ),
            _kpi_card("MAPE", _fmt_float(kpi.get("mape_pct") if "mape_pct" in kpi else (kpi.get("mape") if "mape" in kpi else None)), unit="%", subtitle="Slot: butuh forecast vs actual pada horizon yang sama"),
            _kpi_card("Renewable Fraction", _fmt_float(kpi.get("renewable_fraction"), decimals=3), unit="", subtitle="0–1 (fraction)"),
            _kpi_card("Total Cost", _fmt_float(kpi.get("total_cost")), unit="IDR", subtitle="Akumulasi biaya periode KPI"),
        ]

        alert_items = []
        for a in (alerts[-5:] if len(alerts) > 5 else alerts):
            if not isinstance(a, dict):
                continue
            ts = str(a.get("timestamp") or "").strip()
            code = str(a.get("code") or "").strip()
            sev = str(a.get("severity") or "").strip()
            msg = str(a.get("message") or "").strip()
            label = " ".join([x for x in [ts, sev, code] if x])
            alert_items.append(html.Li([html.Span(label, style={"fontFamily": "monospace", "fontSize": "11px"}), html.Div(msg, style={"fontSize": "12px", "color": "#2c3e50"})], style={"marginBottom": "6px"}))

        meta_line = " ".join([x for x in [f"base_url={base_url}", f"stream_id={stream_id}", f"updated_at={updated_at}" if updated_at else "", f"contract={contract_id}" if contract_id else "", f"hash={contract_hash[:16]}" if contract_hash else ""] if x])

        return html.Div(
            [
                html.Div(
                    [
                        html.Div("Tujuan & definisi metrik", style={"fontWeight": "bold", "marginBottom": "6px"}),
                        html.Div(
                            "KPI Dashboard (Monitoring) menampilkan KPI operasional “ringkas” dari GET /dashboard/kpi (umumnya dipakai untuk status cepat sistem/dispatch).",
                            style={"fontSize": "12px", "color": "#566573", "lineHeight": "1.6"},
                        ),
                        html.Div(
                            "Untuk memastikan perbedaan nilai dengan Reports, catat filter Reports (period, stream_id, zone_id, basis) lalu bandingkan dengan stream_id + updated_at di panel ini.",
                            style={"fontSize": "12px", "color": "#566573", "lineHeight": "1.6", "marginTop": "6px"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                html.Div(meta_line, style={"fontSize": "11px", "color": "#7f8c8d", "marginBottom": "10px", "fontFamily": "monospace"}),
                html.Div(cards, style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "alignItems": "stretch"}),
                html.Div(
                    [
                        html.Div("Alerts (from /dashboard/kpi)", style={"fontSize": "12px", "color": "#566573", "marginTop": "14px", "marginBottom": "6px"}),
                        html.Ul(alert_items, style={"margin": "0", "paddingLeft": "18px"}) if alert_items else html.Div("No alerts.", style={"fontSize": "12px", "color": "#7f8c8d"}),
                    ]
                ),
            ]
        )

    @app.callback(Output("kpi-dashboard-panel", "children"), Input("interval-component", "n_intervals"), [State("backend-readiness-store", "data")])
    def update_kpi_dashboard(n, readiness):
        try:
            if n is None:
                return html.Div()
            r = readiness if isinstance(readiness, dict) else get_backend_readiness()
            base_url = str((r or {}).get("base_url") or "").rstrip("/")
            if not base_url:
                return status_banner("Monitoring", "KPI Dashboard waiting", "base_url belum tersedia.")
            payload = fetch_dashboard_kpi(base_url=base_url, stream_id="default")
            if not isinstance(payload, dict) or not payload:
                diag = get_last_dashboard_kpi_diagnostic()
                detail = json.dumps(diag or {}, sort_keys=True, separators=(",", ":"))
                return status_banner("Monitoring", "KPI Dashboard unavailable", detail, message="GET /dashboard/kpi tidak tersedia atau gagal.")
            return _render_kpi_panel(payload, base_url=base_url)
        except Exception as e:
            return error_banner("Monitoring", "Gagal memuat KPI Dashboard", str(e))
