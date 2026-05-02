import datetime
import json
import re
import requests
from typing import Any, Dict, List, Optional, Tuple

import dash
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update

from ecoaims_frontend.components.precooling.styles import PREC_COLORS
from ecoaims_frontend.services.precooling_api import (
    get_alerts,
    get_audit,
    get_kpi,
    get_last_precooling_endpoint_contract,
    get_schedule,
    get_scenarios,
    get_status,
    get_zones,
    pretty_zone_label,
    build_simulate_request,
    post_apply,
    post_force_fallback,
    post_precooling_selector_preview,
    post_selector_preview,
    post_simulate,
)
from ecoaims_frontend.services.precooling_normalizer import (
    normalize_alerts,
    normalize_audit,
    normalize_kpi,
    normalize_schedule,
    normalize_scenarios,
    normalize_simulate_result,
    normalize_status,
    normalize_status_overview,
)
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.ui.runtime_contract_banner import render_runtime_endpoint_contract_mismatch_banner
from ecoaims_frontend.utils import get_headers


def _now_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _selector_enabled(v: Any) -> bool:
    return isinstance(v, list) and "on" in v


def _as_float(v: Any) -> float | None:
    try:
        return float(v)
    except Exception:
        return None


def _render_selector_note_banner(note: dict | None) -> html.Div | None:
    n = note if isinstance(note, dict) else None
    if not n:
        return None

    code = n.get("code") if isinstance(n.get("code"), str) else None
    message = n.get("message") if isinstance(n.get("message"), str) else None
    suggestion = n.get("suggestion") if isinstance(n.get("suggestion"), str) else None

    def _s(v: Any) -> str | None:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    horizon_start = _s(n.get("horizon_start"))
    horizon_end = _s(n.get("horizon_end"))
    window_earliest = _s(n.get("window_earliest"))
    window_latest = _s(n.get("window_latest"))
    effective_earliest = _s(n.get("effective_earliest"))
    effective_latest = _s(n.get("effective_latest"))

    bits: list[Any] = []
    if message:
        bits.append(html.Div(message, style={"fontWeight": "bold"}))
    if code:
        bits.append(html.Div(f"code={code}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "2px"}))
    if horizon_start or horizon_end:
        bits.append(html.Div(f"horizon={horizon_start or '-'} → {horizon_end or '-'}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "4px"}))
    if window_earliest or window_latest:
        bits.append(html.Div(f"window={window_earliest or '-'} → {window_latest or '-'}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "2px"}))
    if effective_earliest or effective_latest:
        bits.append(html.Div(f"effective_window={effective_earliest or '-'} → {effective_latest or '-'}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "2px"}))
    if suggestion:
        bits.append(html.Div(f"suggestion={suggestion}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "4px"}))

    if not bits:
        return None
    return html.Div(bits, style={"padding": "8px 10px", "borderRadius": "8px", "border": "1px solid #f1c40f", "backgroundColor": "#fff8e1", "color": "#6e5b00"})


def _extract_selector_preview_notes(resp: dict) -> tuple[dict | None, list[str], str]:
    r = resp if isinstance(resp, dict) else {}
    selector_note = r.get("selector_note") if isinstance(r.get("selector_note"), dict) else None
    audit_notes = r.get("audit_notes") if isinstance(r.get("audit_notes"), list) else []
    backend_notes: list[str] = []
    for it in audit_notes:
        if not isinstance(it, dict):
            continue
        if str(it.get("status") or "").strip() != "backend_note":
            continue
        note = it.get("note")
        if isinstance(note, str) and note.strip():
            backend_notes.append(note.strip())
    safe_message = "Preview OK"
    return selector_note, backend_notes, safe_message


def _extract_selector_snapshot(payload: dict) -> dict | None:
    d = payload if isinstance(payload, dict) else {}
    audit_trail = d.get("audit_trail") if isinstance(d.get("audit_trail"), list) else []
    for it in audit_trail:
        if isinstance(it, dict) and str(it.get("status") or "").strip() == "selector_snapshot" and isinstance(it.get("selector_snapshot"), dict):
            return it.get("selector_snapshot")
    audit = d.get("audit") if isinstance(d.get("audit"), dict) else {}
    audit_trail = audit.get("audit_trail") if isinstance(audit.get("audit_trail"), list) else []
    for it in audit_trail:
        if isinstance(it, dict) and str(it.get("status") or "").strip() == "selector_snapshot" and isinstance(it.get("selector_snapshot"), dict):
            return it.get("selector_snapshot")
    job = d.get("job") if isinstance(d.get("job"), dict) else None
    if isinstance(job, dict) and isinstance(job.get("selector_snapshot"), dict):
        return job.get("selector_snapshot")
    snap = d.get("selector_snapshot")
    if isinstance(snap, dict):
        return snap
    meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
    snap = meta.get("selector_snapshot")
    if isinstance(snap, dict):
        return snap
    insight = d.get("optimization_insight") if isinstance(d.get("optimization_insight"), dict) else {}
    snap = insight.get("selector_snapshot") if isinstance(insight.get("selector_snapshot"), dict) else None
    if isinstance(snap, dict):
        return snap
    return None


def _render_selector_audit_panel(payload: dict) -> html.Div:
    snap = _extract_selector_snapshot(payload)
    if not isinstance(snap, dict) or not snap:
        return html.Div("selector_snapshot: (tidak tersedia)", style={"color": "#7f8c8d"})

    selected_index = snap.get("selected_index")
    strategy = snap.get("strategy") or snap.get("selector_backend") or snap.get("backend")
    selected_candidate_score = snap.get("selected_candidate_score") if isinstance(snap.get("selected_candidate_score"), (int, float, str)) else None
    fallback_used = bool(snap.get("fallback_used")) if "fallback_used" in snap else False
    reason = snap.get("reason") or snap.get("fallback_reason")
    reward = snap.get("reward_components") if isinstance(snap.get("reward_components"), dict) else {}

    badges = []
    if fallback_used:
        badges.append(
            html.Span(
                "FALLBACK",
                style={"backgroundColor": "#f39c12", "color": "white", "padding": "2px 8px", "borderRadius": "999px", "fontSize": "11px", "fontWeight": "bold"},
            )
        )

    header_bits = []
    if selected_index is not None:
        header_bits.append(f"selected_index={selected_index}")
    if strategy:
        header_bits.append(f"strategy={strategy}")
    if selected_candidate_score is not None:
        header_bits.append(f"selected_candidate_score={selected_candidate_score}")
    head = " | ".join([str(x) for x in header_bits if x])

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Audit: selector_snapshot", style={"fontWeight": "bold", "color": "#2c3e50"}),
                    html.Div(badges, style={"display": "flex", "gap": "8px"}) if badges else None,
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
            ),
            html.Div(head, style={"marginTop": "6px", "fontFamily": "monospace", "fontSize": "12px", "color": "#566573"}) if head else None,
            html.Div(f"reason={reason}", style={"marginTop": "6px", "fontFamily": "monospace", "fontSize": "12px", "color": "#566573"}) if reason else None,
            html.Div(
                [
                    html.Div("reward_components", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                    html.Pre(json.dumps(reward or {}, indent=2, sort_keys=True, ensure_ascii=False), style={"margin": "0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"}),
                ],
                style={"marginTop": "8px", "padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
            )
            if reward
            else None,
        ],
        style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
    )


def _golden_sample_filename(*, zone: str, ts: datetime.datetime) -> str:
    z = (zone or "all").strip() or "all"
    safe = []
    for ch in z:
        safe.append(ch if ch.isalnum() or ch in {"_", "-"} else "_")
    safe_zone = "".join(safe).strip("_") or "all"
    return f"precooling_golden_sample_{safe_zone}_{ts.strftime('%Y%m%d_%H%M%S')}.json"


def _build_precooling_golden_sample_bundle(
    *,
    base_url: str,
    zone: str,
    mode: str,
    simulate_request_diag: Dict[str, Any],
    simulate_result: Dict[str, Any],
    doctor: Optional[Dict[str, Any]],
    doctor_error: Optional[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "generated_at": datetime.datetime.now().isoformat(),
        "feature": "precooling",
        "base_url": base_url,
        "endpoint": "POST /api/precooling/simulate",
        "selected_zone": zone,
        "selected_mode": mode,
        "simulate_request_diag": simulate_request_diag or {},
        "simulate_response": simulate_result or {},
    }
    if isinstance(doctor, dict):
        out["doctor"] = doctor
    if doctor_error:
        out["doctor_error"] = doctor_error
    return out


def _zone_discovery_banner(err: Optional[str], used_fallback: bool) -> Tuple[Any, Dict[str, Any]]:
    if not err:
        return "", {"display": "none"}
    hint = "Memakai fallback zone (sementara)." if used_fallback else "Memakai data terakhir (cache)."
    detail = str(err).strip()
    if len(detail) > 240:
        detail = detail[:240] + "…"
    return (
        html.Div(
            [
                html.Div("Zone discovery gagal.", style={"fontWeight": "bold"}),
                html.Div(hint),
                html.Div(detail, style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "4px"}),
            ]
        ),
        {"padding": "8px 10px", "borderRadius": "8px", "border": "1px solid #f1c40f", "backgroundColor": "#fff8e1", "color": "#6e5b00"},
    )


def _last_update_display(raw_status: Optional[Dict[str, Any]]) -> str:
    if isinstance(raw_status, dict):
        ts = raw_status.get("last_update") or raw_status.get("generated_at")
        if isinstance(ts, str) and ts:
            return ts
    return _now_str()


def _empty_fig(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        height=260,
        margin=dict(l=30, r=30, t=40, b=30),
        title=title,
    )
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text=message,
        showarrow=False,
        font=dict(color=PREC_COLORS["muted"], size=12),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _comfort_compliance_gauge_fig(kpi: Dict[str, Any]) -> go.Figure:
    raw = kpi.get("comfort_compliance")
    try:
        val = float(raw)
    except Exception:
        return _empty_fig("Comfort Compliance", "Belum ada hasil simulasi")
    val = max(0.0, min(100.0, val))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=val,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": PREC_COLORS["cooling"]},
                "steps": [
                    {"range": [0, 60], "color": "#fdecea"},
                    {"range": [60, 85], "color": "#fff8e1"},
                    {"range": [85, 100], "color": "#e8f5e9"},
                ],
            },
            title={"text": "Comfort Compliance"},
        )
    )
    fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=60, b=30))
    return fig


def _badge_style(kind: str) -> Dict[str, Any]:
    if kind == "OK":
        bg = PREC_COLORS["renewable"]
    elif kind == "WARNING":
        bg = PREC_COLORS["battery"]
    elif kind == "OFFLINE":
        bg = PREC_COLORS["alert"]
    else:
        bg = "#bdc3c7"
    return {
        "display": "inline-block",
        "padding": "4px 10px",
        "borderRadius": "999px",
        "backgroundColor": bg,
        "color": "white",
        "fontWeight": "bold",
        "fontSize": "12px",
        "minWidth": "100px",
        "textAlign": "center",
    }


def _override_badge(state: str) -> Tuple[Any, Dict[str, Any]]:
    s = (state or "").strip().lower()
    if s in {"active"}:
        bg = PREC_COLORS["renewable"]
        label = "ACTIVE"
    elif s in {"pending"}:
        bg = PREC_COLORS["battery"]
        label = "PENDING"
    elif s in {"rejected"}:
        bg = PREC_COLORS["alert"]
        label = "REJECTED"
    elif s in {"expired"}:
        bg = "#7f8c8d"
        label = "EXPIRED"
    else:
        bg = "#bdc3c7"
        label = "DISABLED"
    return (
        html.Div(label, style={"display": "inline-block", "padding": "4px 10px", "borderRadius": "999px", "backgroundColor": bg, "color": "white", "fontWeight": "bold", "fontSize": "12px"}),
        {},
    )


def _safe_list(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def _get_payload_numbers(text: str) -> List[float]:
    items = []
    for raw in (text or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            items.append(float(raw))
        except ValueError:
            continue
    return items


def _hero_card(status: Dict[str, Any], *, selected_zones_label: str, primary_zone_label: str, optimizer_backend_ui: str | None = None) -> html.Div:
    items = [
        ("Status", status.get("status_today", status.get("status", "Unknown"))),
        ("Zona Dipilih", selected_zones_label),
        ("Zona Aktif (Primary)", primary_zone_label),
        ("Start", status.get("start_time", "-")),
        ("End", status.get("end_time", "-")),
        ("Durasi", status.get("duration", "-")),
        ("Target T", status.get("target_temperature", "-")),
        ("Target RH", status.get("target_rh", "-")),
        ("Energy Source", status.get("recommended_energy_source", "-")),
        ("Optimizer Backend (UI)", (optimizer_backend_ui or "-")),
        ("Objective", status.get("optimization_objective", "-")),
        ("Confidence", status.get("confidence_score", "-")),
        ("Comfort Risk", status.get("comfort_risk", "-")),
        ("Constraint", status.get("constraint_status", "-")),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(k, style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            html.Div(str(v), style={"fontWeight": "bold", "color": PREC_COLORS["text"]}),
                        ],
                        style={
                            "padding": "10px",
                            "borderRadius": "8px",
                            "border": f"1px solid {PREC_COLORS['border']}",
                            "backgroundColor": "white",
                            "flex": "1",
                            "minWidth": "160px",
                        },
                    )
                    for k, v in items
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
            )
        ]
    )


def _kpi_card(title: str, value: str, color: str) -> html.Div:
    return html.Div(
        [
            html.Div(title, style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
            html.Div(value, style={"fontSize": "18px", "fontWeight": "bold", "color": color}),
        ],
        style={
            "padding": "10px 12px",
            "borderRadius": "10px",
            "backgroundColor": "white",
            "border": f"1px solid {PREC_COLORS['border']}",
            "minWidth": "190px",
        },
    )


def _quick_kpis(kpi: Dict[str, Any]) -> List[html.Div]:
    return [
        _kpi_card("Predicted Peak Reduction", str(kpi.get("peak_reduction", "-")), PREC_COLORS["cooling"]),
        _kpi_card("Predicted Energy Saving", str(kpi.get("energy_saving", "-")), PREC_COLORS["renewable"]),
        _kpi_card("Predicted Cost Saving", str(kpi.get("cost_saving", "-")), PREC_COLORS["ai"]),
        _kpi_card("Predicted CO2 Reduction", str(kpi.get("co2_reduction", "-")), PREC_COLORS["renewable"]),
        _kpi_card("Comfort Compliance", str(kpi.get("comfort_compliance", "-")), PREC_COLORS["cooling"]),
        _kpi_card("Battery Impact", str(kpi.get("battery_impact", "-")), PREC_COLORS["battery"]),
    ]


def _explainability_box(status: Dict[str, Any]) -> html.Div:
    reasons = status.get("explainability", status.get("reasons", []))
    reasons_list = []
    if isinstance(reasons, list):
        reasons_list = [str(x) for x in reasons if x]
    if not reasons_list:
        reasons_list = [
            "Belum ada data explainability dari backend.",
            "Periksa koneksi Precooling Engine atau jalankan simulasi untuk menghasilkan rekomendasi.",
        ]
    last = get_last_precooling_endpoint_contract()
    normalized = last.get("normalized") if isinstance(last, dict) else None
    normalized = normalized if isinstance(normalized, dict) else {}
    banners = [render_runtime_endpoint_contract_mismatch_banner(v) for v in normalized.values() if isinstance(v, dict)]
    if banners:
        return html.Div(
            [
                html.Div(banners),
                html.Ul([html.Li(x) for x in reasons_list], style={"margin": "0", "paddingLeft": "18px", "lineHeight": "1.7"}),
            ]
        )
    return html.Ul([html.Li(x) for x in reasons_list], style={"margin": "0", "paddingLeft": "18px", "lineHeight": "1.7"})


def _timeline_from_schedule(schedule: Dict[str, Any]) -> go.Figure:
    slots = _safe_list(schedule.get("slots", schedule.get("schedule", [])))
    if not slots:
        return _empty_fig("Precooling Timeline", "Belum ada schedule precooling")
    xs = []
    ys = []
    temps = []
    rhs = []
    for s in slots:
        xs.append(s.get("time", s.get("time_slot", "")))
        ys.append(s.get("estimated_load", s.get("load_kw", 0)))
        temps.append(s.get("temperature_setpoint", s.get("t_set", None)))
        rhs.append(s.get("rh_setpoint", s.get("rh_set", None)))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=xs, y=ys, name="Estimated Load", marker_color=PREC_COLORS["cooling"]))
    fig.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=40), title="Timeline (24h)")
    fig.update_xaxes(title="Time", tickangle=-45)
    fig.update_yaxes(title="kW")
    return fig


def _datatable_from_rows(rows: List[Dict[str, Any]], preferred_cols: Optional[List[str]] = None) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    if not rows:
        return [], []
    keys = preferred_cols or list(rows[0].keys())
    columns = [{"name": k, "id": k} for k in keys]
    data = []
    for r in rows:
        row = {k: r.get(k, "") for k in keys}
        data.append(row)
    return columns, data


def _scenario_cards(scenarios: Dict[str, Any]) -> List[html.Div]:
    items = scenarios.get("scenarios")
    if isinstance(items, dict):
        items = [items]
    items_list = _safe_list(items)
    if not items_list:
        items_list = [
            {"name": "Baseline", "peak": "-", "cost": "-", "co2": "-", "comfort": "-"},
            {"name": "Rule-Based Precooling", "peak": "-", "cost": "-", "co2": "-", "comfort": "-"},
            {"name": "LAEOPF Optimized", "peak": "-", "cost": "-", "co2": "-", "comfort": "-"},
        ]
    cards = []
    for it in items_list[:3]:
        cards.append(
            html.Div(
                [
                    html.Div(it.get("name", "Scenario"), style={"fontWeight": "bold", "color": PREC_COLORS["text"]}),
                    html.Div(f"Peak: {it.get('peak', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px", "marginTop": "6px"}),
                    html.Div(f"Cost: {it.get('cost', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"CO2: {it.get('co2', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"Comfort: {it.get('comfort', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                ],
                style={
                    "padding": "12px",
                    "borderRadius": "10px",
                    "backgroundColor": "white",
                    "border": f"1px solid {PREC_COLORS['border']}",
                    "minWidth": "260px",
                    "flex": "1",
                },
            )
        )
    return cards


def _objective_breakdown_fig(insight: Dict[str, Any]) -> go.Figure:
    obj = insight.get("objective", insight.get("objective_breakdown", {}))
    if not isinstance(obj, dict) or not obj:
        obj = {"Cost": 0.0, "CO2": 0.0, "Peak": 0.0, "Comfort": 0.0, "Battery Health": 0.0}
    labels = list(obj.keys())
    values = [float(obj.get(k, 0) or 0) for k in labels]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.45)])
    fig.update_layout(template="plotly_white", height=260, margin=dict(l=20, r=20, t=40, b=20), title="Objective Breakdown")
    return fig


def _selected_candidate_box(candidate: Optional[Dict[str, Any]], insight: Optional[Dict[str, Any]] = None) -> html.Div:
    picked = candidate if isinstance(candidate, dict) and candidate else {}
    if not picked and isinstance(insight, dict):
        picked = insight.get("selected_candidate") if isinstance(insight.get("selected_candidate"), dict) else {}
    if not picked:
        return html.Div(
            [
                html.Div("Belum ada kandidat terpilih.", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                html.Div(
                    "Pilih 1 baris pada Candidate Ranking untuk mengaktifkan Apply Recommendation.",
                    style={"color": PREC_COLORS["muted"], "fontSize": "12px", "marginTop": "6px"},
                ),
            ]
        )
    keys = [
        ("candidate_id", "Candidate ID"),
        ("rank", "Rank"),
        ("score", "Score"),
        ("start_time", "Start Time"),
        ("duration", "Duration (min)"),
        ("target_t", "Target T (°C)"),
        ("target_rh", "Target RH (%)"),
        ("feasible", "Feasible"),
        ("risk", "Risk"),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(label, style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            html.Div(str(picked.get(k, "-")), style={"fontWeight": "bold", "color": PREC_COLORS["text"]}),
                        ],
                        style={
                            "padding": "10px",
                            "borderRadius": "8px",
                            "border": f"1px solid {PREC_COLORS['border']}",
                            "backgroundColor": "white",
                            "flex": "1",
                            "minWidth": "140px",
                        },
                    )
                    for k, label in keys
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
            )
        ]
    )


def _fig_from_sim_or_scenarios(sim_result: Dict[str, Any], scenarios: Dict[str, Any], key: str, title: str, message: str) -> Any:
    fig = sim_result.get(key)
    if isinstance(fig, dict) and fig.get("data") is not None:
        return fig
    if isinstance(fig, go.Figure):
        return fig
    items = scenarios.get("scenarios") if isinstance(scenarios, dict) else None
    items_list = _safe_list(items)
    if not items_list:
        return _empty_fig(title, message)
    name_key = "name"
    metric_map = {
        "fig_peak": ("peak_kw", "Peak (kW)"),
        "fig_comfort": ("comfort_compliance", "Comfort Compliance"),
        "fig_scatter": ("cost_idr", "Cost (IDR)"),
    }
    metric, y_label = metric_map.get(key, (None, None))
    if metric == "cost_idr":
        xs = [float(i.get("cost_idr", 0) or 0) for i in items_list[:3]]
        ys = [float(i.get("co2_kg", 0) or 0) for i in items_list[:3]]
        labels = [str(i.get(name_key, "Scenario")) for i in items_list[:3]]
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=labels, textposition="top center"))
        fig2.update_layout(
            template="plotly_white",
            height=260,
            margin=dict(l=30, r=30, t=40, b=30),
            title=title,
            xaxis_title="Cost (IDR)",
            yaxis_title="CO2 (kg)",
        )
        return fig2
    if metric:
        ys = [float(i.get(metric, 0) or 0) for i in items_list[:3]]
        xs = [str(i.get(name_key, "Scenario")) for i in items_list[:3]]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=xs, y=ys, marker_color=[PREC_COLORS["cooling"], PREC_COLORS["battery"], PREC_COLORS["renewable"]]))
        fig2.update_layout(template="plotly_white", height=260, margin=dict(l=30, r=30, t=40, b=30), title=title, yaxis_title=y_label)
        return fig2
    return _empty_fig(title, message)


def register_precooling_callbacks(app):
    def _expand_zone_scope(zone_id: str | None) -> list[str]:
        zid = str(zone_id or "").strip()
        if not zid or zid == "all":
            return []
        if zid.lower().startswith("floor") and zid.lower().endswith("_all"):
            base = zid[:-4]
            return [f"{base}_a", f"{base}_b", f"{base}_c"]
        return [zid]

    def _augment_zone_items_with_all(zone_items: list[dict[str, str]]) -> list[dict[str, str]]:
        zone_ids_raw = [str(it.get("zone_id") or "").strip() for it in zone_items if isinstance(it, dict)]
        if set(zone_ids_raw) == {"zone_a", "zone_b", "zone_c"}:
            zone_map = {"zone_a": "a", "zone_b": "b", "zone_c": "c"}
            expanded: list[dict[str, str]] = []
            for floor in range(1, 4):
                for zid in zone_ids_raw:
                    short = zone_map.get(zid)
                    if not short:
                        continue
                    new_zid = f"floor{floor}_{short}"
                    expanded.append({"zone_id": new_zid, "label": pretty_zone_label(new_zid)})
            zone_items = expanded

        floors: set[int] = set()
        for it in zone_items:
            zid = str(it.get("zone_id") or "").strip()
            if not zid.lower().startswith("floor"):
                continue
            parts = zid.split("_", 1)
            if len(parts) != 2:
                continue
            try:
                floors.add(int(parts[0][5:]))
            except Exception:
                continue
        if not floors:
            return zone_items
        out = list(zone_items)
        for floor in sorted(floors):
            zid_all = f"floor{floor}_all"
            out.append({"zone_id": zid_all, "label": pretty_zone_label(zid_all)})
        return out

    def _sort_zone_items(zone_items: list[dict[str, str]]) -> list[dict[str, str]]:
        def _sort_key(zid: str):
            s = str(zid or "").strip()
            if not s:
                return (999, 999, "")
            parts = s.split("_", 1)
            if len(parts) != 2 or not parts[0].lower().startswith("floor"):
                return (999, 999, s)
            try:
                floor = int(parts[0][5:])
            except Exception:
                floor = 999
            z = parts[1].lower()
            order = {"all": 0, "a": 1, "b": 2, "c": 3}.get(z, 99)
            return (floor, order, s)

        return sorted(zone_items, key=lambda it: _sort_key(str(it.get("zone_id"))))

    @app.callback(
        [
            Output("precooling-override-state-badge", "children"),
            Output("precooling-override-state-details", "children"),
        ],
        [Input("precooling-status-store", "data"), Input("precooling-selected-zone", "data")],
    )
    def render_manual_override_state(status, zone):
        st = status if isinstance(status, dict) else {}
        zid = str(zone or "").strip()
        state = str(st.get("manual_override_state") or "disabled")
        expires = st.get("manual_override_expires_at")
        reason = st.get("manual_override_reason")
        setpoints = st.get("manual_override_setpoints") if isinstance(st.get("manual_override_setpoints"), dict) else {}

        badge, _ = _override_badge(state)
        details_lines = [f"zone={zid}" if zid else "zone=-"]
        if isinstance(expires, str) and expires and expires != "-":
            details_lines.append(f"expires_at={expires}")
        t = setpoints.get("temperature_setpoint_c")
        rh = setpoints.get("rh_setpoint_pct")
        hv = setpoints.get("hvac_mode")
        src = setpoints.get("energy_source")
        if t is not None or rh is not None:
            details_lines.append(f"setpoints: T={t}C RH={rh}%")
        if hv:
            details_lines.append(f"hvac_mode={hv}")
        if src:
            details_lines.append(f"energy_source={src}")
        if isinstance(reason, str) and reason.strip():
            details_lines.append(f"reason={reason.strip()}")

        return badge, html.Div([html.Div(x) for x in details_lines])

    @app.callback(
        [
            Output("precooling-zones-store", "data"),
            Output("precooling-zone-discovery-banner", "children"),
            Output("precooling-zone-discovery-banner", "style"),
        ],
        [Input("backend-readiness-store", "data"), Input("precooling-interval", "n_intervals")],
        [State("precooling-zones-store", "data"), State("token-store", "data")],
    )
    def refresh_precooling_zones(readiness, n, cached, token_data):
        base_url = effective_base_url(readiness)
        prec_headers = get_headers(token_data)
        cache = cached if isinstance(cached, dict) else {}
        cache_base = cache.get("base_url")
        cache_zones = cache.get("zones") if isinstance(cache.get("zones"), list) else []
        if cache_base == base_url and cache_zones and isinstance(n, int) and (n % 30) != 0:
            zone_items = [z for z in cache_zones if isinstance(z, dict) and isinstance(z.get("zone_id"), str)]
            return {"base_url": base_url, "zones": zone_items}, dash.no_update, dash.no_update

        data, err = get_zones(base_url=base_url, headers=prec_headers)
        zones = data.get("zones") if isinstance(data, dict) else None
        zones_list = zones if isinstance(zones, list) else []
        zone_items = []
        for z in zones_list:
            if not isinstance(z, dict):
                continue
            zid = z.get("zone_id")
            if not isinstance(zid, str) or not zid.strip():
                continue
            raw_label = z.get("label") if isinstance(z.get("label"), str) and z.get("label").strip() else ""
            label = raw_label if raw_label and raw_label.strip() and raw_label.strip() != zid.strip() else pretty_zone_label(zid.strip())
            zone_items.append({"zone_id": zid.strip(), "label": label or zid.strip()})
        zone_items = _sort_zone_items(_augment_zone_items_with_all(zone_items))

        used_static_fallback = False
        if err and not zone_items and cache_zones:
            zone_items = [{"zone_id": str(z.get("zone_id")), "label": str(z.get("label") or z.get("zone_id"))} for z in cache_zones if isinstance(z, dict) and z.get("zone_id")]
        if err and not zone_items:
            used_static_fallback = True
            zone_items = [{"zone_id": "zone_a", "label": "Zone A (fallback)"}]

        store_out = {"base_url": base_url, "zones": zone_items}
        banner_children, banner_style = _zone_discovery_banner(err, used_static_fallback)
        return store_out, banner_children, banner_style

    def _active_floor(value: Any) -> str:
        v = str(value or "").strip()
        return v if v in {"1", "2", "3"} else "1"

    def _normalize_floor_zone_map(data: Any) -> dict[str, list[str]]:
        base = {"1": ["a"], "2": [], "3": []}
        raw = data if isinstance(data, dict) else {}
        out: dict[str, list[str]] = {"1": list(base["1"]), "2": [], "3": []}
        order = {"a": 0, "b": 1, "c": 2}
        for k, v in raw.items():
            fk = str(k).strip()
            if fk not in out:
                continue
            items = v if isinstance(v, list) else []
            zs: list[str] = []
            for x in items:
                z = str(x).strip().lower()
                if z in order and z not in zs:
                    zs.append(z)
            out[fk] = sorted(zs, key=lambda z: order.get(z, 99))
        return out

    def _target_zone_ids_from_map(floor_zone_map: dict[str, list[str]]) -> list[str]:
        order = {"a": 0, "b": 1, "c": 2}
        out: list[str] = []
        for f in ["1", "2", "3"]:
            zs = floor_zone_map.get(f) if isinstance(floor_zone_map.get(f), list) else []
            zs2 = [str(z).strip().lower() for z in zs if str(z).strip().lower() in order]
            zs2 = sorted(set(zs2), key=lambda z: order.get(z, 99))
            for z in zs2:
                out.append(f"floor{f}_{z}")
        return out

    def _primary_zone_id_from_map(active_floor: str, floor_zone_map: dict[str, list[str]], targets: list[str]) -> str:
        order = {"a": 0, "b": 1, "c": 2}
        zs = floor_zone_map.get(active_floor) if isinstance(floor_zone_map.get(active_floor), list) else []
        zs2 = [str(z).strip().lower() for z in zs if str(z).strip().lower() in order]
        zs2 = sorted(set(zs2), key=lambda z: order.get(z, 99))
        if zs2:
            return f"floor{active_floor}_{zs2[0]}"
        if targets:
            return str(targets[0])
        return "floor1_a"

    def _valid_zone_id(zid: Any) -> bool:
        s = str(zid or "").strip().lower()
        return bool(re.match(r"^floor[123]_[abc]$", s))

    def _resolve_default_zone_id(zones_store: Any) -> str:
        zs = zones_store if isinstance(zones_store, dict) else {}
        items = zs.get("zones") if isinstance(zs.get("zones"), list) else []
        for it in items:
            if isinstance(it, dict) and _valid_zone_id(it.get("zone_id")):
                return str(it.get("zone_id")).strip()
        return "floor1_a"

    def _resolve_targets_or_error(floor_value: Any, floor_zone_map: Any) -> tuple[list[str], str | None]:
        floor = _active_floor(floor_value)
        fm = _normalize_floor_zone_map(floor_zone_map)
        active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not active_zones:
            return [], f"Pilih minimal 1 zone untuk Lantai {floor}."
        zone_ids = _target_zone_ids_from_map(fm)
        if not zone_ids:
            return [], "Zone belum dipilih."
        return zone_ids, None

    @app.callback(
        [
            Output("precooling-floor-zone-map", "data"),
            Output("precooling-zone", "value"),
            Output("precooling-zone-selection-error", "children"),
        ],
        [
            Input("precooling-floor", "value"),
            Input("precooling-zone", "value"),
            Input("precooling-clear-zones-btn", "n_clicks"),
        ],
        [State("precooling-floor-zone-map", "data")],
    )
    def sync_precooling_floor_zone_map(floor_value, zone_value, clear_n, map_data):
        floor = _active_floor(floor_value)
        fm = _normalize_floor_zone_map(map_data)
        def _err_msg(zs: list[str] | None) -> str:
            return f"Pilih minimal 1 zone untuk Lantai {floor}." if not (zs or []) else ""

        triggered = getattr(getattr(dash, "ctx", None), "triggered_id", None)
        if triggered == "precooling-clear-zones-btn":
            fm[floor] = []
            return fm, [], _err_msg([])
        if triggered == "precooling-floor":
            current = list(fm.get(floor) or [])
            return fm, current, _err_msg(current)
        if triggered == "precooling-zone":
            items = zone_value if isinstance(zone_value, list) else []
            order = {"a": 0, "b": 1, "c": 2}
            zs = []
            for x in items:
                z = str(x).strip().lower()
                if z in order and z not in zs:
                    zs.append(z)
            fm[floor] = sorted(zs, key=lambda z: order.get(z, 99))
            current = list(fm.get(floor) or [])
            return fm, current, _err_msg(current)
        _ = clear_n
        current = list(fm.get(floor) or [])
        return fm, current, _err_msg(current)

    @app.callback(
        [
            Output("precooling-selected-zone", "data"),
            Output("precooling-selected-mode", "data"),
            Output("precooling-status-store", "data"),
            Output("precooling-schedule-store", "data"),
            Output("precooling-scenarios-store", "data"),
            Output("precooling-kpi-store", "data"),
            Output("precooling-alerts-store", "data"),
            Output("precooling-audit-store", "data"),
            Output("precooling-last-update", "children"),
            Output("precooling-data-health-badge", "children"),
            Output("precooling-data-health-badge", "style"),
        ],
        [
            Input("precooling-interval", "n_intervals"),
            Input("precooling-mode-dropdown", "value"),
            Input("precooling-floor", "value"),
            Input("precooling-floor-zone-map", "data"),
            Input("precooling-zones-store", "data"),
            Input("precooling-refresh-signal", "data"),
        ],
        [State("backend-readiness-store", "data"), State("token-store", "data")],
    )
    def refresh_precooling_data(n, mode, floor_value, floor_zone_map, zones_store, refresh_signal, readiness, token_data):
        mode_val = mode or "monitoring"
        try:
            base_url = effective_base_url(readiness)
            prec_headers = get_headers(token_data)
            active_floor = _active_floor(floor_value)
            fm = _normalize_floor_zone_map(floor_zone_map)
            selected_zone_ids = [z for z in _target_zone_ids_from_map(fm) if _valid_zone_id(z)]
            default_zone = _resolve_default_zone_id(zones_store)
            zone_val = _primary_zone_id_from_map(active_floor, fm, selected_zone_ids)
            if not _valid_zone_id(zone_val):
                zone_val = default_zone
            zone_ids = selected_zone_ids if selected_zone_ids else [zone_val]

            if not zone_ids or any(not _valid_zone_id(z) for z in zone_ids):
                badge = "WARNING"
                status = normalize_status({"data_health": badge, "zone_id": zone_val, "active_zones": ",".join(zone_ids or [zone_val]), "reasons": ["waiting_for_valid_zone_id"]})
                empty = {}
                return (zone_val, mode_val, status, empty, empty, empty, empty, empty, _now_str(), badge, _badge_style(badge))

            def _num(x: Any) -> float:
                try:
                    return float(x)
                except Exception:
                    return 0.0

            def _avg(vals: list[float]) -> float:
                if not vals:
                    return 0.0
                return float(sum(vals) / max(1, len(vals)))

            if len(zone_ids) == 1:
                zid = zone_ids[0]
                raw_status, err_status = get_status(zid, base_url=base_url, headers=prec_headers)
                raw_schedule, err_schedule = get_schedule(zid, base_url=base_url, headers=prec_headers)
                raw_scenarios, err_scenarios = get_scenarios(zid, base_url=base_url, headers=prec_headers)
                raw_kpi, err_kpi = get_kpi(zid, base_url=base_url, headers=prec_headers)
                raw_alerts, err_alerts = get_alerts(zid, base_url=base_url, headers=prec_headers)
                raw_audit, err_audit = get_audit(zid, base_url=base_url, headers=prec_headers)
                if isinstance(raw_status, dict):
                    raw_status = {**raw_status, "active_zones": ",".join(zone_ids)}
            else:
                status_list: list[dict[str, Any]] = []
                kpi_list: list[dict[str, Any]] = []
                scenarios_list: list[dict[str, Any]] = []
                alerts_rows: list[dict[str, Any]] = []
                audit_rows: list[dict[str, Any]] = []
                errors: list[str] = []

                for zid in zone_ids:
                    st, e1 = get_status(zid, base_url=base_url, headers=prec_headers)
                    sc, e2 = get_scenarios(zid, base_url=base_url, headers=prec_headers)
                    kk, e3 = get_kpi(zid, base_url=base_url, headers=prec_headers)
                    al, e4 = get_alerts(zid, base_url=base_url, headers=prec_headers)
                    au, e5 = get_audit(zid, base_url=base_url, headers=prec_headers)
                    for e in (e1, e2, e3, e4, e5):
                        if e:
                            errors.append(str(e))
                    if isinstance(st, dict):
                        status_list.append({**st, "zone_id": zid})
                    if isinstance(sc, dict):
                        scenarios_list.append({**sc, "zone_id": zid})
                    if isinstance(kk, dict):
                        kpi_list.append({**kk, "zone_id": zid})
                    if isinstance(al, dict) and isinstance(al.get("alerts"), list):
                        for r in al.get("alerts") or []:
                            if isinstance(r, dict):
                                alerts_rows.append({**r, "zone_id": r.get("zone_id") or zid})
                    if isinstance(au, dict) and isinstance(au.get("audit"), list):
                        for r in au.get("audit") or []:
                            if isinstance(r, dict):
                                audit_rows.append({**r, "zone_id": r.get("zone_id") or zid})

                raw_status = {
                    "zone_id": zone_val,
                    "active_zones": ",".join(zone_ids),
                    "data_health": "WARNING" if errors else "OK",
                    "reasons": errors,
                }
                raw_schedule = {"zone_id": zone_val, "schedule": None}

                scenarios_map: dict[str, dict[str, Any]] = {}
                for item in scenarios_list:
                    rows = item.get("scenarios") if isinstance(item.get("scenarios"), list) else []
                    for r in rows:
                        if not isinstance(r, dict):
                            continue
                        name = str(r.get("name") or "").strip() or "Scenario"
                        agg = scenarios_map.get(name) or {"name": name, "peak_kw": 0.0, "cost_rp": 0.0, "co2_kg": 0.0, "comfort": [], "shr": [], "exergy_eff": [], "ipei": []}
                        agg["peak_kw"] = float(agg.get("peak_kw") or 0.0) + _num(r.get("peak_kw"))
                        agg["cost_rp"] = float(agg.get("cost_rp") or 0.0) + _num(r.get("cost_rp"))
                        agg["co2_kg"] = float(agg.get("co2_kg") or 0.0) + _num(r.get("co2_kg"))
                        if r.get("comfort_compliance") is not None:
                            agg["comfort"].append(_num(r.get("comfort_compliance")))
                        if r.get("shr") is not None:
                            agg["shr"].append(_num(r.get("shr")))
                        if r.get("exergy_efficiency") is not None:
                            agg["exergy_eff"].append(_num(r.get("exergy_efficiency")))
                        if r.get("ipei") is not None:
                            agg["ipei"].append(_num(r.get("ipei")))
                        scenarios_map[name] = agg
                scenarios_out: list[dict[str, Any]] = []
                for name, agg in scenarios_map.items():
                    scenarios_out.append(
                        {
                            "name": name,
                            "peak_kw": float(agg.get("peak_kw") or 0.0),
                            "cost_rp": float(agg.get("cost_rp") or 0.0),
                            "co2_kg": float(agg.get("co2_kg") or 0.0),
                            "comfort_compliance": _avg([float(x) for x in (agg.get("comfort") or [])]),
                            "shr": _avg([float(x) for x in (agg.get("shr") or [])]),
                            "exergy_efficiency": _avg([float(x) for x in (agg.get("exergy_eff") or [])]),
                            "ipei": _avg([float(x) for x in (agg.get("ipei") or [])]),
                        }
                    )
                raw_scenarios = {"zone_id": zone_val, "scenarios": scenarios_out, "compare_table": []}

                raw_kpi = {
                    "zone_id": zone_val,
                    "energy_saving_kwh": sum(_num(it.get("energy_saving_kwh")) for it in kpi_list),
                    "peak_reduction_kw": sum(_num(it.get("peak_reduction_kw")) for it in kpi_list),
                    "cost_saving_rp": sum(_num(it.get("cost_saving_rp")) for it in kpi_list),
                    "co2_reduction_kg": sum(_num(it.get("co2_reduction_kg")) for it in kpi_list),
                    "comfort_compliance_pct": _avg([_num(it.get("comfort_compliance_pct")) for it in kpi_list if it.get("comfort_compliance_pct") is not None]),
                    "latent_load_kwh": sum(_num(it.get("latent_load_kwh")) for it in kpi_list),
                    "shr_avg": _avg([_num(it.get("shr_avg")) for it in kpi_list if it.get("shr_avg") is not None]),
                    "exergy_efficiency": _avg([_num(it.get("exergy_efficiency")) for it in kpi_list if it.get("exergy_efficiency") is not None]),
                    "ipei": _avg([_num(it.get("ipei")) for it in kpi_list if it.get("ipei") is not None]),
                }

                raw_alerts = {"zone_id": zone_val, "alerts": alerts_rows}
                raw_audit = {"zone_id": zone_val, "audit": audit_rows}
                err_status = None
                err_schedule = None
                err_scenarios = None
                err_kpi = None
                err_alerts = None
                err_audit = None

            errors = [e for e in [err_status, err_schedule, err_scenarios, err_kpi, err_alerts, err_audit] if e]
            invalid_zone = any(isinstance(e, str) and "invalid_zone_id" in e for e in errors)
            if invalid_zone:
                msg = f"Zone invalid, fallback ke {default_zone}"
                zone_val = default_zone
                badge = "WARNING"
                status = normalize_status({"data_health": badge, "zone_id": zone_val, "active_zones": zone_val, "reasons": [msg]})
                empty = {}
                return (zone_val, mode_val, status, empty, empty, empty, empty, empty, _now_str(), badge, _badge_style(badge))

            if all(x is None for x in [raw_status, raw_schedule, raw_scenarios, raw_kpi, raw_alerts, raw_audit]):
                badge = "OFFLINE"
            elif errors:
                badge = "WARNING"
            else:
                if isinstance(raw_status, dict) and raw_status.get("data_health") in ["OK", "WARNING", "OFFLINE"]:
                    badge = raw_status.get("data_health")
                else:
                    badge = "OK"

            if errors and not isinstance(raw_status, dict):
                raw_status = {"data_health": badge, "generated_at": _now_str(), "reasons": errors}
            elif errors and isinstance(raw_status, dict) and not raw_status.get("reasons"):
                raw_status = {**raw_status, "reasons": errors, "data_health": raw_status.get("data_health") or badge}

            status = normalize_status(raw_status)
            schedule = normalize_schedule(raw_schedule)
            scenarios = normalize_scenarios(raw_scenarios)
            kpi = normalize_kpi(raw_kpi)
            alerts = normalize_alerts(raw_alerts)
            audit = normalize_audit(raw_audit)

            return (
                zone_val,
                mode_val,
                status,
                schedule,
                scenarios,
                kpi,
                alerts,
                audit,
                _last_update_display(raw_status),
                badge,
                _badge_style(badge),
            )
        except Exception:
            badge = "OFFLINE"
            return (
                zone_val,
                mode_val,
                {},
                {},
                {},
                {},
                {},
                {},
                _now_str(),
                badge,
                _badge_style(badge),
            )

    @app.callback(
        [
            Output("precooling-hero-card", "children"),
            Output("precooling-quick-kpi-row", "children"),
            Output("precooling-explainability-box", "children"),
            Output("precooling-schedule-timeline", "figure"),
            Output("precooling-schedule-table", "columns"),
            Output("precooling-schedule-table", "data"),
            Output("precooling-control-summary", "children"),
            Output("precooling-scenario-cards", "children"),
            Output("precooling-scenario-compare-table", "columns"),
            Output("precooling-scenario-compare-table", "data"),
            Output("precooling-peak-compare-chart", "figure"),
            Output("precooling-load-profile-chart", "figure"),
            Output("precooling-cost-co2-scatter", "figure"),
            Output("precooling-comfort-chart", "figure"),
            Output("precooling-thermal-state", "children"),
            Output("precooling-latent-state", "children"),
            Output("precooling-psychrometric-mini", "figure"),
            Output("precooling-exergy-panel", "children"),
            Output("precooling-objective-breakdown", "figure"),
            Output("precooling-constraint-matrix", "columns"),
            Output("precooling-constraint-matrix", "data"),
            Output("precooling-candidate-ranking", "columns"),
            Output("precooling-candidate-ranking", "data"),
            Output("precooling-selected-candidate", "children"),
            Output("precooling-kpi-master-cards", "children"),
            Output("precooling-before-after-load", "figure"),
            Output("precooling-before-after-temp", "figure"),
            Output("precooling-before-after-rh", "figure"),
            Output("precooling-uncertainty-panel", "children"),
            Output("precooling-model-status", "children"),
            Output("precooling-alerts-table", "columns"),
            Output("precooling-alerts-table", "data"),
            Output("precooling-audit-table", "columns"),
            Output("precooling-audit-table", "data"),
        ],
        [
            Input("precooling-status-store", "data"),
            Input("precooling-schedule-store", "data"),
            Input("precooling-scenarios-store", "data"),
            Input("precooling-kpi-store", "data"),
            Input("precooling-alerts-store", "data"),
            Input("precooling-audit-store", "data"),
            Input("precooling-sim-result-store", "data"),
            Input("precooling-simulate-request-store", "data"),
            Input("precooling-selected-candidate-store", "data"),
            Input("precooling-selected-zone", "data"),
            Input("precooling-selected-mode", "data"),
            Input("optimizer-backend-store", "data"),
            Input("precooling-floor-zone-map", "data"),
        ],
    )
    def render_precooling_panels(status, schedule, scenarios, kpi, alerts, audit, sim_result, simulate_req, selected_candidate, zone, mode, optimizer_backend_store, floor_zone_map):
        try:
            status = status or {}
            schedule = schedule or {}
            scenarios = scenarios or {}
            kpi = kpi or {}
            alerts = alerts or {}
            audit = audit or {}
            sim_result = sim_result or {}
            simulate_req = simulate_req or {}

            if isinstance(sim_result, dict) and isinstance(sim_result.get("status"), dict):
                if "status_today" in sim_result.get("status"):
                    status = sim_result.get("status")
                else:
                    status = normalize_status(sim_result.get("status"))
            if isinstance(sim_result, dict) and sim_result.get("kpi"):
                kpi = normalize_kpi(sim_result.get("kpi"))
            if isinstance(sim_result, dict) and sim_result.get("schedule"):
                schedule = normalize_schedule(sim_result.get("schedule"))
            if isinstance(sim_result, dict) and sim_result.get("scenarios"):
                scenarios = normalize_scenarios(sim_result.get("scenarios"))
            if isinstance(sim_result, dict) and "explainability" in sim_result and isinstance(status, dict):
                exp = sim_result.get("explainability")
                if isinstance(exp, list):
                    status["explainability"] = [str(x) for x in exp if x]
                elif isinstance(exp, dict):
                    reasons = exp.get("reason")
                    warnings = exp.get("warnings")
                    if isinstance(reasons, list) and reasons:
                        status["explainability"] = [str(x) for x in reasons if x]
                    elif isinstance(warnings, list) and warnings:
                        status["explainability"] = [f"warning:{x}" for x in warnings if x]
                    else:
                        confidence = exp.get("confidence_score")
                        fallback_used = exp.get("fallback_used")
                        lines = ["Explainability tersedia tetapi belum ada alasan (reason) dari backend."]
                        if confidence is not None:
                            lines.append(f"confidence_score={confidence}")
                        if fallback_used is not None:
                            lines.append(f"fallback_used={fallback_used}")
                        status["explainability"] = lines

            if isinstance(status, dict) and isinstance(sim_result, dict):
                raw_payload = simulate_req.get("raw_payload") if isinstance(simulate_req, dict) else None
                overview = normalize_status_overview(sim_result, raw_payload if isinstance(raw_payload, dict) else None)
                if isinstance(overview, dict) and overview:
                    status = {**status, **overview}

            obs = optimizer_backend_store if isinstance(optimizer_backend_store, dict) else {}
            obv = obs.get("value")
            obv = str(obv).strip() if isinstance(obv, str) and obv.strip() else "-"
            fm = _normalize_floor_zone_map(floor_zone_map)
            selected_zone_ids = _target_zone_ids_from_map(fm)
            selected_zones_label = ",".join(selected_zone_ids) if selected_zone_ids else "-"
            primary_zone_label = str(zone or "").strip() or "-"
            hero = _hero_card(status, selected_zones_label=selected_zones_label, primary_zone_label=primary_zone_label, optimizer_backend_ui=obv)
            quick = _quick_kpis(kpi)
            explain = _explainability_box(status)

            timeline_fig = _timeline_from_schedule(schedule)
            slots = _safe_list(schedule.get("slots", schedule.get("schedule", [])))
            schedule_cols, schedule_data = _datatable_from_rows(
                slots,
                preferred_cols=[
                    "time_slot",
                    "temperature_setpoint",
                    "rh_setpoint",
                    "hvac_mode",
                    "energy_source",
                    "estimated_load",
                ],
            )
            if not schedule_cols and slots:
                schedule_cols, schedule_data = _datatable_from_rows(slots)

            control_summary = html.Div(
                [
                    html.Div(f"Current Mode: {mode}", style={"fontWeight": "bold", "color": PREC_COLORS["text"]}),
                    html.Div(f"Selected Zones: {selected_zones_label}", style={"color": PREC_COLORS["muted"], "marginTop": "4px"}),
                    html.Div(
                        f"Strategy: {status.get('strategy_type', status.get('strategy', 'LAEOPF/Advisory'))}",
                        style={"color": PREC_COLORS["muted"], "marginTop": "4px"},
                    ),
                ]
            )

            scenario_cards = _scenario_cards(scenarios)
            compare_rows = _safe_list(scenarios.get("comparison", scenarios.get("compare_table", [])))
            compare_cols, compare_data = _datatable_from_rows(compare_rows)
            if not compare_cols:
                compare_cols = [{"name": "Metric", "id": "metric"}, {"name": "Baseline", "id": "baseline"}, {"name": "Rule-Based", "id": "rule_based"}, {"name": "LAEOPF", "id": "laeopf"}]
                compare_data = []

            peak_fig = _fig_from_sim_or_scenarios(sim_result, scenarios, "fig_peak", "Peak Comparison", "Belum ada hasil simulasi")
            load_fig = sim_result.get("fig_load") if isinstance(sim_result, dict) else None
            if not (isinstance(load_fig, dict) and load_fig.get("data") is not None) and not isinstance(load_fig, go.Figure):
                load_fig = _empty_fig("Load Profile", "Belum ada hasil simulasi")
            scatter_fig = _fig_from_sim_or_scenarios(sim_result, scenarios, "fig_scatter", "Cost vs CO2", "Belum ada hasil simulasi")
            comfort_fig = _fig_from_sim_or_scenarios(sim_result, scenarios, "fig_comfort", "Comfort Compliance", "Belum ada hasil simulasi")
            if isinstance(comfort_fig, dict) and isinstance(comfort_fig.get("data"), list) and not comfort_fig.get("data"):
                comfort_fig = _comfort_compliance_gauge_fig(kpi)
            if isinstance(comfort_fig, go.Figure) and len(getattr(comfort_fig, "data", []) or []) == 0:
                comfort_fig = _comfort_compliance_gauge_fig(kpi)

            thermal = status.get("thermal_state", {})
            if not isinstance(thermal, dict):
                thermal = {}
            latent = status.get("latent_state", {})
            if not isinstance(latent, dict):
                latent = {}

            thermal_child = html.Div(
                [
                    html.Div("Zone Thermal State", style={"fontWeight": "bold", "color": PREC_COLORS["cooling"]}),
                    html.Div(f"Current T: {thermal.get('current_temp', '-')}", style={"color": PREC_COLORS["muted"], "marginTop": "6px"}),
                    html.Div(f"Thermal Mass T: {thermal.get('thermal_mass_temp', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Predicted Rebound: {thermal.get('rebound_temp', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Indoor-Outdoor ΔT: {thermal.get('delta_to', '-')}", style={"color": PREC_COLORS["muted"]}),
                ],
                style={"padding": "14px", "borderRadius": "10px", "backgroundColor": "white", "border": f"1px solid {PREC_COLORS['border']}"},
            )
            latent_child = html.Div(
                [
                    html.Div("Humidity & Latent Load", style={"fontWeight": "bold", "color": PREC_COLORS["ai"]}),
                    html.Div(f"RH Actual: {latent.get('rh_actual', '-')}", style={"color": PREC_COLORS["muted"], "marginTop": "6px"}),
                    html.Div(f"RH Target: {latent.get('rh_target', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Dew Point: {latent.get('dew_point', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Latent Load: {latent.get('latent_load', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Sensible Load: {latent.get('sensible_load', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"SHR: {latent.get('shr', '-')}", style={"color": PREC_COLORS["muted"]}),
                ],
                style={"padding": "14px", "borderRadius": "10px", "backgroundColor": "white", "border": f"1px solid {PREC_COLORS['border']}"},
            )

            psycho_fig = _empty_fig("Psychrometric", "Data latent/psychrometric belum tersedia")
            exergy = status.get("exergy", status.get("exergy_analysis", {}))
            if not isinstance(exergy, dict):
                exergy = {}
            exergy_child = html.Div(
                [
                    html.Div("Advanced metric / beta", style={"color": PREC_COLORS["muted"], "fontSize": "12px", "marginBottom": "8px"}),
                    html.Div(f"Exergy Input: {exergy.get('input', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Exergy Output: {exergy.get('output', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Exergy Loss: {exergy.get('loss', '-')}", style={"color": PREC_COLORS["muted"]}),
                    html.Div(f"Exergy Efficiency: {exergy.get('efficiency', '-')}", style={"color": PREC_COLORS["muted"]}),
                ]
            )

            insight = sim_result.get("optimization_insight", status.get("optimization_insight", {}))
            if not isinstance(insight, dict):
                insight = {}
            obj_fig = _objective_breakdown_fig(insight)
            constraint_rows = _safe_list(insight.get("constraints", insight.get("constraint_matrix", [])))
            constraint_cols, constraint_data = _datatable_from_rows(constraint_rows)
            if not constraint_cols:
                constraint_cols = [{"name": "Constraint", "id": "constraint"}, {"name": "Status", "id": "status"}, {"name": "Note", "id": "note"}]
                constraint_data = []
            candidates = _safe_list(insight.get("candidates", insight.get("candidate_ranking", [])))
            candidate_cols, candidate_data = _datatable_from_rows(candidates)
            if not candidate_cols:
                candidate_cols = [
                    {"name": "Candidate ID", "id": "candidate_id"},
                    {"name": "Start Time", "id": "start_time"},
                    {"name": "Duration", "id": "duration"},
                    {"name": "Target T", "id": "target_t"},
                    {"name": "Target RH", "id": "target_rh"},
                    {"name": "Score", "id": "score"},
                    {"name": "Feasible", "id": "feasible"},
                    {"name": "Risk", "id": "risk"},
                    {"name": "Rank", "id": "rank"},
                ]
                candidate_data = []
            selected_box = _selected_candidate_box(selected_candidate, insight=insight)

            kpi_master = [
                _kpi_card("E_total", str(kpi.get("E_total", "-")), PREC_COLORS["cooling"]),
                _kpi_card("Peak reduction", str(kpi.get("peak_reduction", "-")), PREC_COLORS["cooling"]),
                _kpi_card("Cost saving", str(kpi.get("cost_saving", "-")), PREC_COLORS["renewable"]),
                _kpi_card("CO2 reduction", str(kpi.get("co2_reduction", "-")), PREC_COLORS["renewable"]),
                _kpi_card("Comfort compliance", str(kpi.get("comfort_compliance", "-")), PREC_COLORS["ai"]),
                _kpi_card("Exergy efficiency", str(kpi.get("exergy_efficiency", "beta")), PREC_COLORS["ai"]),
                _kpi_card("IPEI", str(kpi.get("ipei", "beta")), PREC_COLORS["ai"]),
            ]

            before_after_load = sim_result.get("fig_load") if isinstance(sim_result, dict) else None
            if not (isinstance(before_after_load, dict) and before_after_load.get("data") is not None) and not isinstance(before_after_load, go.Figure):
                before_after_load = _empty_fig("Load: Baseline vs Optimized", "Belum ada hasil simulasi")
            before_after_temp = sim_result.get("fig_before_after_temp") if isinstance(sim_result, dict) else None
            if not (isinstance(before_after_temp, dict) and before_after_temp.get("data") is not None) and not isinstance(before_after_temp, go.Figure):
                before_after_temp = _empty_fig("Temperature: Baseline vs Optimized", "Belum ada hasil simulasi")
            before_after_rh = sim_result.get("fig_before_after_rh") if isinstance(sim_result, dict) else None
            if not (isinstance(before_after_rh, dict) and before_after_rh.get("data") is not None) and not isinstance(before_after_rh, go.Figure):
                before_after_rh = _empty_fig("RH: Baseline vs Optimized", "Belum ada hasil simulasi")

            unc = kpi.get("uncertainty", {})
            if not isinstance(unc, dict):
                unc = {}
            uncertainty_child = html.Div(
                [
                    html.Div(f"Forecast confidence: {unc.get('forecast_confidence', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"Sensor completeness: {unc.get('sensor_completeness', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"Drift risk: {unc.get('drift_risk', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"Data freshness: {unc.get('data_freshness', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                ]
            )
            model = kpi.get("model_status", {})
            if not isinstance(model, dict):
                model = {}
            model_child = html.Div(
                [
                    html.Div(f"Model: {model.get('status', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    html.Div(f"Retraining: {model.get('retraining', '-')}", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                ]
            )

            alert_rows = _safe_list(alerts.get("alerts", alerts.get("data", [])))
            alert_cols, alert_data = _datatable_from_rows(alert_rows)
            if not alert_cols:
                alert_cols = [{"name": "timestamp", "id": "timestamp"}, {"name": "severity", "id": "severity"}, {"name": "type", "id": "type"}, {"name": "zone", "id": "zone"}, {"name": "description", "id": "description"}, {"name": "action", "id": "action"}]
                alert_data = []

            audit_rows = _safe_list(audit.get("audit", audit.get("data", [])))
            audit_cols, audit_data = _datatable_from_rows(audit_rows)
            if not audit_cols:
                audit_cols = [{"name": "timestamp", "id": "timestamp"}, {"name": "action", "id": "action"}, {"name": "actor", "id": "actor"}, {"name": "scenario", "id": "scenario"}, {"name": "result", "id": "result"}, {"name": "note", "id": "note"}]
                audit_data = []

            return (
                hero,
                quick,
                explain,
                timeline_fig,
                schedule_cols,
                schedule_data,
                control_summary,
                scenario_cards,
                compare_cols,
                compare_data,
                peak_fig,
                load_fig,
                scatter_fig,
                comfort_fig,
                thermal_child,
                latent_child,
                psycho_fig,
                exergy_child,
                obj_fig,
                constraint_cols,
                constraint_data,
                candidate_cols,
                candidate_data,
                selected_box,
                kpi_master,
                before_after_load,
                before_after_temp,
                before_after_rh,
                uncertainty_child,
                model_child,
                alert_cols,
                alert_data,
                audit_cols,
                audit_data,
            )
        except Exception:
            msg = html.Div("Precooling panel error. Check backend connectivity and server logs.", style={"color": PREC_COLORS["alert"], "fontWeight": "bold"})
            empty = _empty_fig("Precooling", "Callback error")
            cols, data = [], []
            return (
                msg,
                [],
                msg,
                empty,
                cols,
                data,
                msg,
                [],
                cols,
                data,
                empty,
                empty,
                empty,
                empty,
                msg,
                msg,
                empty,
                msg,
                empty,
                cols,
                data,
                cols,
                data,
                msg,
                msg,
                empty,
                empty,
                empty,
                msg,
                msg,
                cols,
                data,
                cols,
                data,
            )

    @app.callback(
        Output("precooling-selected-candidate-store", "data"),
        Input("precooling-candidate-ranking", "selected_rows"),
        State("precooling-candidate-ranking", "data"),
    )
    def select_candidate(selected_rows, table_data):
        if not selected_rows:
            return {}
        idx = selected_rows[0]
        if isinstance(table_data, list) and 0 <= idx < len(table_data) and isinstance(table_data[idx], dict):
            return table_data[idx]
        return {}

    @app.callback(
        [Output("precooling-apply-btn", "disabled"), Output("precooling-apply-btn", "style"), Output("precooling-apply-btn", "title")],
        Input("precooling-selected-candidate-store", "data"),
        State("precooling-apply-btn", "style"),
    )
    def toggle_apply_button(candidate, current_style):
        style = dict(current_style or {})
        has_candidate = isinstance(candidate, dict) and bool(candidate)
        style["opacity"] = "1.0" if has_candidate else "0.6"
        title = "" if has_candidate else "Pilih 1 recommendation pada tabel Candidate Ranking terlebih dahulu."
        return (not has_candidate), style, title

    @app.callback(
        [
            Output("precooling-earliest-start", "value", allow_duplicate=True),
            Output("precooling-latest-start", "value", allow_duplicate=True),
            Output("precooling-duration-options", "value", allow_duplicate=True),
            Output("precooling-target-t-range", "value", allow_duplicate=True),
            Output("precooling-target-rh-range", "value", allow_duplicate=True),
            Output("precooling-w-cost", "value", allow_duplicate=True),
            Output("precooling-w-co2", "value", allow_duplicate=True),
            Output("precooling-w-comfort", "value", allow_duplicate=True),
            Output("precooling-w-battery", "value", allow_duplicate=True),
            Output("precooling-settings-snapshot-store", "data"),
        ],
        Input("precooling-status-store", "data"),
        [
            State("precooling-settings-snapshot-store", "data"),
            State("precooling-earliest-start", "value"),
            State("precooling-latest-start", "value"),
            State("precooling-duration-options", "value"),
            State("precooling-target-t-range", "value"),
            State("precooling-target-rh-range", "value"),
        ],
        prevent_initial_call=True,
    )
    def sync_builder_defaults(status, prev_snapshot, earliest, latest, durations, t_range, rh_range):
        status = status or {}
        snap = status.get("settings_snapshot") if isinstance(status, dict) else None
        if not isinstance(snap, dict) or not snap:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, prev_snapshot or {}

        if isinstance(prev_snapshot, dict) and prev_snapshot == snap:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, prev_snapshot

        tw = snap.get("time_window") if isinstance(snap.get("time_window"), dict) else {}
        comfort = snap.get("comfort_limits") if isinstance(snap.get("comfort_limits"), dict) else {}
        w = snap.get("objective_weights") if isinstance(snap.get("objective_weights"), dict) else {}

        e = tw.get("earliest_start_time") or earliest or "05:00"
        l = tw.get("latest_start_time") or latest or "10:00"
        min_d = int(tw.get("min_duration_min") or 30)
        max_d = int(tw.get("max_duration_min") or 120)
        mid_d = max(min_d, min(max_d, int((min_d + max_d) / 2)))
        dur_str = f"{min_d},{mid_d},{max_d}"

        tmin = comfort.get("min_indoor_temp_c", 22)
        tmax = comfort.get("max_indoor_temp_c", 27)
        tr_str = f"{tmin},{tmax}"
        rhmin = comfort.get("min_rh_pct", 45)
        rhmax = comfort.get("max_rh_pct", 65)
        rr_str = f"{rhmin},{rhmax}"

        return (
            str(e),
            str(l),
            dur_str,
            tr_str,
            rr_str,
            float(w.get("weight_cost", 0.35) or 0.35),
            float(w.get("weight_co2", 0.25) or 0.25),
            float(w.get("weight_comfort", 0.25) or 0.25),
            float(w.get("weight_battery_health", 0.15) or 0.15),
            snap,
        )

    @app.callback(
        [Output("precooling-selector-preview-output", "children"), Output("precooling-selector-preview-raw", "value")],
        Input("precooling-selector-preview-btn", "n_clicks"),
        [
            State("precooling-selector-enable", "value"),
            State("precooling-selector-backend", "value"),
            State("precooling-selector-epsilon", "value"),
            State("precooling-selector-min-candidates", "value"),
            State("precooling-selector-return-candidates", "value"),
            State("precooling-sim-result-store", "data"),
            State("precooling-simulate-request-store", "data"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def preview_selector(_n, selector_enable, selector_backend, epsilon, min_candidates, return_candidates, sim_result, simulate_req, readiness, token_data):
        if not _selector_enabled(selector_enable):
            msg = "Selector masih OFF. Aktifkan toggle lalu klik Preview Selector."
            return html.Div(msg, style={"color": "#7f8c8d", "fontWeight": "bold"}), "{}"

        sr = sim_result if isinstance(sim_result, dict) else {}
        insight = sr.get("optimization_insight") if isinstance(sr.get("optimization_insight"), dict) else {}
        candidates = insight.get("candidates") if isinstance(insight.get("candidates"), list) else []
        cand_dicts = [c for c in candidates if isinstance(c, dict)]

        feasible_count = 0
        for c in cand_dicts:
            v = c.get("feasible")
            if isinstance(v, bool) and v:
                feasible_count += 1
            elif isinstance(v, (int, float)) and float(v) > 0:
                feasible_count += 1

        req = simulate_req if isinstance(simulate_req, dict) else {}
        raw_payload = req.get("raw_payload") if isinstance(req.get("raw_payload"), dict) else {}
        zone_id = raw_payload.get("zone_id") or raw_payload.get("zone")
        if not (isinstance(zone_id, str) and zone_id.strip()):
            msg = "Preview butuh zone_id dari payload simulate. Jalankan Simulate sekali dulu (atau pastikan zone sudah terpilih)."
            return html.Div(msg, style={"color": "#c0392b", "fontWeight": "bold"}), json.dumps({"ok": False, "error": msg}, indent=2, sort_keys=True, ensure_ascii=False)

        eps = _as_float(epsilon)
        mn = None
        if isinstance(min_candidates, (int, float)):
            try:
                mn = int(min_candidates)
            except Exception:
                mn = None
        payload: Dict[str, Any] = dict(raw_payload)
        payload["selector_enabled"] = True
        payload["selector_backend"] = str(selector_backend or "grid")
        if eps is not None:
            payload["selector_epsilon"] = float(eps)
        if mn is not None:
            payload["selector_min_candidates"] = int(mn)

        base_url = effective_base_url(readiness)
        prec_headers = get_headers(token_data)
        try:
            want_candidates = _selector_enabled(return_candidates)
            resp = post_precooling_selector_preview(str(zone_id).strip(), payload, return_candidates=want_candidates, base_url=base_url, headers=prec_headers)
            if not isinstance(resp, dict):
                raw = json.dumps({"ok": False, "error": "Respons preview selector tidak valid", "base_url": base_url, "zone_id": str(zone_id).strip()}, indent=2, sort_keys=True, ensure_ascii=False)
                return html.Div("Respons preview selector tidak valid", style={"color": "#c0392b", "fontWeight": "bold"}), raw
            if not resp.get("ok"):
                err = resp.get("error")
                sc = resp.get("status_code")
                msg = f"Preview selector gagal: {err}" if err else "Preview selector gagal"
                msg = f"{msg} (status_code={sc})" if sc is not None else msg
                raw = json.dumps({**resp, "base_url": base_url, "zone_id": str(zone_id).strip(), "payload": payload}, indent=2, sort_keys=True, ensure_ascii=False)
                banner = html.Div(msg, style={"color": "#c0392b", "fontWeight": "bold"})
                return banner, raw

            snap = _extract_selector_snapshot(resp) or (resp.get("selector_snapshot") if isinstance(resp.get("selector_snapshot"), dict) else {})
            selector_note, backend_notes, _safe_message = _extract_selector_preview_notes(resp)
            note_banner = _render_selector_note_banner(selector_note)
            backend_note_banner = (
                html.Div(
                    [html.Div("Catatan backend:", style={"fontWeight": "bold"}), html.Ul([html.Li(n) for n in backend_notes], style={"margin": "6px 0 0 18px"})],
                    style={"padding": "8px 10px", "borderRadius": "8px", "border": "1px solid #f1c40f", "backgroundColor": "#fff8e1", "color": "#6e5b00", "marginTop": "8px"},
                )
                if backend_notes
                else None
            )

            selected_index = resp.get("selected_index")
            if selected_index is None and isinstance(snap, dict):
                selected_index = snap.get("selected_index")
            selected_candidate = resp.get("selected_candidate") if isinstance(resp.get("selected_candidate"), dict) else None

            head = []
            head.append(f"candidates_count={len(cand_dicts)}")
            head.append(f"feasible_count={feasible_count}")
            if selected_index is not None:
                head.append(f"selected_index={selected_index}")

            candidates_summary = None
            for k in ["candidates_summary", "top_candidates", "candidates"]:
                v = resp.get(k)
                if isinstance(v, list) and v:
                    candidates_summary = v
                    break

            out = html.Div(
                [
                    html.Div(" | ".join(head), style={"fontFamily": "monospace", "fontSize": "12px", "color": "#566573"}),
                    note_banner,
                    backend_note_banner,
                    html.Div(
                        [
                            html.Div("Selected candidate (summary)", style={"fontWeight": "bold", "color": "#2c3e50", "marginTop": "8px"}),
                            html.Pre(
                                json.dumps(selected_candidate or {}, indent=2, sort_keys=True, ensure_ascii=False),
                                style={"margin": "6px 0 0 0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"},
                            ),
                        ],
                        style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc", "marginTop": "8px"},
                    ),
                    html.Div(
                        [
                            html.Div("selector_snapshot", style={"fontWeight": "bold", "color": "#2c3e50", "marginTop": "8px"}),
                            html.Pre(
                                json.dumps(snap or {}, indent=2, sort_keys=True, ensure_ascii=False),
                                style={"margin": "6px 0 0 0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"},
                            ),
                        ],
                        style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc", "marginTop": "8px"},
                    ),
                    html.Div(
                        [
                            html.Div("top candidates_summary", style={"fontWeight": "bold", "color": "#2c3e50", "marginTop": "8px"}),
                            html.Pre(
                                json.dumps((candidates_summary or [])[:8], indent=2, sort_keys=True, ensure_ascii=False),
                                style={"margin": "6px 0 0 0", "fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap"},
                            ),
                        ],
                        style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc", "marginTop": "8px"},
                    )
                    if want_candidates and isinstance(candidates_summary, list) and candidates_summary
                    else None,
                ]
            )
            raw = json.dumps(resp, indent=2, sort_keys=True, ensure_ascii=False)
            return out, raw
        except Exception as e:
            raw = json.dumps({"ok": False, "error": str(e)[:400], "base_url": base_url, "zone_id": str(zone_id).strip(), "payload": payload}, indent=2, sort_keys=True, ensure_ascii=False)
            return html.Div(str(e), style={"color": "#c0392b", "fontWeight": "bold"}), raw

    @app.callback(
        Output("precooling-selector-audit", "children"),
        Input("precooling-sim-result-store", "data"),
    )
    def render_selector_audit(sim_result):
        sr = sim_result if isinstance(sim_result, dict) else {}
        return _render_selector_audit_panel(sr)

    @app.callback(
        [
            Output("precooling-sim-result-store", "data", allow_duplicate=True),
            Output("precooling-action-feedback", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
            Output("precooling-simulate-request-store", "data", allow_duplicate=True),
        ],
        [Input("precooling-run-sim-btn", "n_clicks"), Input("precooling-run-compare-btn", "n_clicks")],
        [
            State("precooling-floor", "value"),
            State("precooling-floor-zone-map", "data"),
            State("precooling-earliest-start", "value"),
            State("precooling-latest-start", "value"),
            State("precooling-duration-options", "value"),
            State("precooling-target-t-range", "value"),
            State("precooling-target-rh-range", "value"),
            State("precooling-w-cost", "value"),
            State("precooling-w-co2", "value"),
            State("precooling-w-comfort", "value"),
            State("precooling-w-battery", "value"),
            State("precooling-optimizer-backend", "value"),
            State("precooling-selector-enable", "value"),
            State("precooling-selector-backend", "value"),
            State("precooling-selector-epsilon", "value"),
            State("precooling-selector-min-candidates", "value"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
        running=[
            (Output("precooling-run-sim-btn", "disabled"), True, False),
            (Output("precooling-run-sim-btn", "children"), "Running...", "Run Simulation"),
            (Output("precooling-run-compare-btn", "disabled"), True, False),
            (Output("precooling-run-compare-btn", "children"), "Running...", "Run Comparison"),
        ],
    )
    def run_simulation(n_clicks_sim, n_clicks_compare, floor_value, floor_zone_map, earliest, latest, durations, t_range, rh_range, w_cost, w_co2, w_comfort, w_battery, optimizer_backend, selector_enable, selector_backend, selector_epsilon, selector_min_candidates, readiness, token_data):
        try:
            floor = _active_floor(floor_value)
            fm = _normalize_floor_zone_map(floor_zone_map)
            active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
            if not active_zones:
                return dash.no_update, f"Pilih minimal 1 zone untuk Lantai {floor}.", {"ts": _now_str()}, {"error": "zone_empty_for_active_floor", "floor": floor, "floor_zone_map": fm}

            zone_ids = _target_zone_ids_from_map(fm)
            if not zone_ids:
                return dash.no_update, "Zone belum dipilih.", {"ts": _now_str()}, {"error": "zone_scope_empty", "floor_zone_map": fm}
            primary_zid = zone_ids[0]
            payload = {
                "zone_id": primary_zid,
                "window": {"earliest_start": earliest, "latest_start": latest},
                "durations_min": _get_payload_numbers(durations),
                "target_temp_range": _get_payload_numbers(t_range),
                "target_rh_range": _get_payload_numbers(rh_range),
                "weights": {"cost": w_cost, "co2": w_co2, "comfort": w_comfort, "battery_health": w_battery},
            }
            if isinstance(optimizer_backend, str) and optimizer_backend.strip():
                payload["optimizer_backend"] = optimizer_backend.strip()
            if _selector_enabled(selector_enable):
                payload["selector_enabled"] = True
                if isinstance(selector_backend, str) and selector_backend.strip():
                    payload["selector_backend"] = selector_backend.strip()
                eps = _as_float(selector_epsilon)
                if eps is not None:
                    payload["selector_epsilon"] = float(eps)
                if isinstance(selector_min_candidates, (int, float)):
                    try:
                        payload["selector_min_candidates"] = int(selector_min_candidates)
                    except Exception:
                        pass
            base_url = effective_base_url(readiness)
            prec_headers = get_headers(token_data)
            req = build_simulate_request(payload, base_url=base_url)
            diag = {"endpoint": "POST /api/precooling/simulate", "base_url": base_url, "raw_payload": payload, "request": req, "targets": zone_ids, "ts": _now_str()}

            errors: list[str] = []
            primary_data, primary_err = post_simulate(payload, base_url=base_url, headers=prec_headers)
            if primary_err:
                return dash.no_update, f"Simulasi Gagal, silakan coba lagi. Detail: {primary_err}", {"ts": _now_str()}, diag
            for zid in zone_ids[1:]:
                p2 = dict(payload)
                p2["zone_id"] = zid
                _, e2 = post_simulate(p2, base_url=base_url, headers=prec_headers)
                if e2:
                    errors.append(str(e2))

            result = normalize_simulate_result(primary_data)
            triggered = getattr(getattr(dash, "ctx", None), "triggered_id", None)
            msg = "Simulasi berhasil dijalankan." if triggered == "precooling-run-sim-btn" else "Comparison berhasil dijalankan."
            if errors:
                msg = f"{msg} Warning: {len(errors)} zone gagal diproses."
            return result, msg, {"ts": _now_str()}, diag
        except Exception as e:
            return dash.no_update, f"Simulasi Gagal, silakan coba lagi. Detail error: {str(e)}", {"ts": _now_str()}, {"error": str(e)}

    @app.callback(
        Output("precooling-fallback-confirm", "displayed"),
        [Input("precooling-force-fallback-btn", "n_clicks"), Input("precooling-safety-fallback-btn", "n_clicks")],
        prevent_initial_call=True,
    )
    def ask_force_fallback(n1, n2):
        return True

    @app.callback(
        [
            Output("precooling-action-feedback", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
        ],
        Input("precooling-fallback-confirm", "submit_n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
    )
    def confirm_force_fallback(n, floor_value, floor_zone_map, readiness, token_data):
        base_url = effective_base_url(readiness)
        prec_headers = get_headers(token_data)
        floor = _active_floor(floor_value)
        fm = _normalize_floor_zone_map(floor_zone_map)
        active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not active_zones:
            return f"Pilih minimal 1 zone untuk Lantai {floor}.", {"ts": _now_str()}
        zone_ids = _target_zone_ids_from_map(fm)
        if not zone_ids:
            return "Zone belum dipilih.", {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_force_fallback({"zone_id": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal force fallback: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Force fallback berhasil diterapkan.", {"ts": _now_str()}

    @app.callback(
        [
            Output("precooling-sim-result-store", "data", allow_duplicate=True),
            Output("precooling-scenario-feedback", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
            Output("precooling-simulate-request-store", "data", allow_duplicate=True),
        ],
        Input("precooling-generate-candidates-btn", "n_clicks"),
        [
            State("precooling-floor", "value"),
            State("precooling-floor-zone-map", "data"),
            State("precooling-earliest-start", "value"),
            State("precooling-latest-start", "value"),
            State("precooling-duration-options", "value"),
            State("precooling-target-t-range", "value"),
            State("precooling-target-rh-range", "value"),
            State("precooling-w-cost", "value"),
            State("precooling-w-co2", "value"),
            State("precooling-w-comfort", "value"),
            State("precooling-w-battery", "value"),
            State("precooling-optimizer-backend", "value"),
            State("precooling-selector-enable", "value"),
            State("precooling-selector-backend", "value"),
            State("precooling-selector-epsilon", "value"),
            State("precooling-selector-min-candidates", "value"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
        running=[
            (Output("precooling-generate-candidates-btn", "disabled"), True, False),
            (Output("precooling-generate-candidates-btn", "children"), "Generating...", "Generate Candidates"),
        ],
    )
    def generate_candidates(n_clicks, floor_value, floor_zone_map, earliest, latest, durations, t_range, rh_range, w_cost, w_co2, w_comfort, w_battery, optimizer_backend, selector_enable, selector_backend, selector_epsilon, selector_min_candidates, readiness, token_data):
        try:
            floor = _active_floor(floor_value)
            fm = _normalize_floor_zone_map(floor_zone_map)
            active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
            if not active_zones:
                return dash.no_update, f"Pilih minimal 1 zone untuk Lantai {floor}.", {"ts": _now_str()}, {"error": "zone_empty_for_active_floor", "floor": floor, "floor_zone_map": fm}

            zone_ids = _target_zone_ids_from_map(fm)
            if not zone_ids:
                return dash.no_update, "Zone belum dipilih.", {"ts": _now_str()}, {"error": "zone_scope_empty", "floor_zone_map": fm}
            primary_zid = zone_ids[0]
            payload = {
                "zone_id": primary_zid,
                "scenario_type": "candidates_only",
                "window": {"earliest_start": earliest, "latest_start": latest},
                "durations_min": _get_payload_numbers(durations),
                "target_temp_range": _get_payload_numbers(t_range),
                "target_rh_range": _get_payload_numbers(rh_range),
                "weights": {"cost": w_cost, "co2": w_co2, "comfort": w_comfort, "battery_health": w_battery},
            }
            if isinstance(optimizer_backend, str) and optimizer_backend.strip():
                payload["optimizer_backend"] = optimizer_backend.strip()
            if _selector_enabled(selector_enable):
                payload["selector_enabled"] = True
                if isinstance(selector_backend, str) and selector_backend.strip():
                    payload["selector_backend"] = selector_backend.strip()
                eps = _as_float(selector_epsilon)
                if eps is not None:
                    payload["selector_epsilon"] = float(eps)
                if isinstance(selector_min_candidates, (int, float)):
                    try:
                        payload["selector_min_candidates"] = int(selector_min_candidates)
                    except Exception:
                        pass
            base_url = effective_base_url(readiness)
            prec_headers = get_headers(token_data)
            req = build_simulate_request(payload, base_url=base_url)
            diag = {"endpoint": "POST /api/precooling/simulate", "base_url": base_url, "raw_payload": payload, "request": req, "targets": zone_ids, "ts": _now_str()}

            errors: list[str] = []
            primary_data, primary_err = post_simulate(payload, base_url=base_url, headers=prec_headers)
            if primary_err:
                return dash.no_update, f"Simulasi Gagal, silakan coba lagi. Detail: {primary_err}", {"ts": _now_str()}, diag
            for zid in zone_ids[1:]:
                p2 = dict(payload)
                p2["zone_id"] = zid
                _, e2 = post_simulate(p2, base_url=base_url, headers=prec_headers)
                if e2:
                    errors.append(str(e2))

            result = normalize_simulate_result(primary_data)
            msg = "Candidates berhasil digenerate."
            if errors:
                msg = f"{msg} Warning: {len(errors)} zone gagal diproses."
            return result, msg, {"ts": _now_str()}, diag
        except Exception as e:
            return dash.no_update, f"Simulasi Gagal, silakan coba lagi. Detail error: {str(e)}", {"ts": _now_str()}, {"error": str(e)}

    @app.callback(
        Output("precooling-simulate-request-text", "value"),
        Input("precooling-simulate-request-store", "data"),
    )
    def render_simulate_request_debug(data):
        d = data if isinstance(data, dict) else {}
        try:
            return json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(d)

    @app.callback(
        [
            Output("precooling-action-feedback", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
        ],
        Input("precooling-save-scenario-btn", "n_clicks"),
        [
            State("precooling-floor", "value"),
            State("precooling-floor-zone-map", "data"),
            State("precooling-selected-candidate-store", "data"),
            State("precooling-earliest-start", "value"),
            State("precooling-latest-start", "value"),
            State("precooling-duration-options", "value"),
            State("precooling-target-t-range", "value"),
            State("precooling-target-rh-range", "value"),
            State("precooling-w-cost", "value"),
            State("precooling-w-co2", "value"),
            State("precooling-w-comfort", "value"),
            State("precooling-w-battery", "value"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
        running=[(Output("precooling-save-scenario-btn", "children"), "Saving...", "Save Scenario")],
    )
    def save_scenario(n, floor_value, floor_zone_map, candidate, earliest, latest, durations, t_range, rh_range, w_cost, w_co2, w_comfort, w_battery, readiness, token_data):
        floor = _active_floor(floor_value)
        prec_headers = get_headers(token_data)
        fm = _normalize_floor_zone_map(floor_zone_map)
        active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not active_zones:
            return f"Pilih minimal 1 zone untuk Lantai {floor}.", {"ts": _now_str()}
        zid = f"floor{floor}_{str(active_zones[0]).strip().lower()}"
        scenario_payload = {
            "zone_id": zid,
            "name": "builder",
            "candidate": candidate or {},
            "window": {"earliest_start": earliest, "latest_start": latest},
            "durations_min": _get_payload_numbers(durations),
            "target_temp_range": _get_payload_numbers(t_range),
            "target_rh_range": _get_payload_numbers(rh_range),
            "weights": {"cost": w_cost, "co2": w_co2, "comfort": w_comfort, "battery_health": w_battery},
        }
        base_url = effective_base_url(readiness)
        _, err = post_apply({"action": "save_scenario", "zone_id": zid, "zone": zid, "scenario": scenario_payload}, base_url=base_url, headers=prec_headers)
        if err:
            return f"Gagal menyimpan scenario: {err}", {"ts": _now_str()}
        return "Scenario tersimpan.", {"ts": _now_str()}

    @app.callback(
        [
            Output("precooling-earliest-start", "value", allow_duplicate=True),
            Output("precooling-latest-start", "value", allow_duplicate=True),
            Output("precooling-duration-options", "value", allow_duplicate=True),
            Output("precooling-target-t-range", "value", allow_duplicate=True),
            Output("precooling-target-rh-range", "value", allow_duplicate=True),
            Output("precooling-w-cost", "value", allow_duplicate=True),
            Output("precooling-w-co2", "value", allow_duplicate=True),
            Output("precooling-w-comfort", "value", allow_duplicate=True),
            Output("precooling-w-battery", "value", allow_duplicate=True),
            Output("precooling-scenario-feedback", "children", allow_duplicate=True),
        ],
        Input("precooling-reset-scenario-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_scenario(n):
        return "05:00", "10:00", "30,60,90", "22,25", "50,60", 0.35, 0.25, 0.25, 0.15, "Scenario builder direset."

    @app.callback(
        [
            Output("precooling-action-feedback", "children", allow_duplicate=True),
            Output("precooling-refresh-signal", "data", allow_duplicate=True),
        ],
        Input("precooling-apply-btn", "n_clicks"),
        State("precooling-selected-candidate-store", "data"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[
            (Output("precooling-apply-btn", "children"), "Applying...", "Apply Recommendation"),
        ],
    )
    def apply_recommendation(n, candidate, floor_value, floor_zone_map, readiness, token_data):
        if not isinstance(candidate, dict) or not candidate:
            return "Tidak ada recommendation yang dipilih.", {"ts": _now_str()}
        floor = _active_floor(floor_value)
        prec_headers = get_headers(token_data)
        fm = _normalize_floor_zone_map(floor_zone_map)
        active_zones = fm.get(floor) if isinstance(fm.get(floor), list) else []
        if not active_zones:
            return f"Pilih minimal 1 zone untuk Lantai {floor}.", {"ts": _now_str()}
        zone_ids = _target_zone_ids_from_map(fm)
        if not zone_ids:
            return "Zone belum dipilih.", {"ts": _now_str()}
        base_url = effective_base_url(readiness)
        errors = []
        for zid in zone_ids:
            payload = {"action": "apply_recommendation", "zone_id": zid, "zone": zid, "candidate": candidate}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal apply recommendation: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Recommendation berhasil diterapkan.", {"ts": _now_str()}

    @app.callback(
        Output("precooling-download", "data"),
        Input("precooling-export-btn", "n_clicks"),
        [
            State("precooling-selected-zone", "data"),
            State("precooling-status-store", "data"),
            State("precooling-schedule-store", "data"),
            State("precooling-kpi-store", "data"),
            State("precooling-selected-candidate-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def export_report(n, zone, status, schedule, kpi, candidate):
        bundle = {
            "generated_at": datetime.datetime.now().isoformat(),
            "zone": zone,
            "status": status or {},
            "schedule": schedule or {},
            "kpi": kpi or {},
            "selected_candidate": candidate or {},
        }
        content = json.dumps(bundle, indent=2)
        filename = f"precooling_report_{zone or 'all'}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return dcc.send_string(content, filename)

    @app.callback(
        Output("precooling-golden-download", "data"),
        Input("precooling-golden-export-btn", "n_clicks"),
        [
            State("precooling-selected-zone", "data"),
            State("precooling-selected-mode", "data"),
            State("precooling-simulate-request-store", "data"),
            State("precooling-sim-result-store", "data"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def export_golden_sample(n, zone, mode, simulate_req, sim_result, readiness, token_data):
        base_url = effective_base_url(readiness)
        z = str(zone or "").strip() or "all"
        m = str(mode or "").strip() or ""
        diag = simulate_req if isinstance(simulate_req, dict) else {}
        result = sim_result if isinstance(sim_result, dict) else {}

        doctor_payload = None
        doctor_error = None
        if isinstance(base_url, str) and base_url.strip():
            url = f"{base_url.rstrip('/')}/diag/doctor"
            prec_headers = get_headers(token_data)
            try:
                r = requests.get(url, timeout=(1.5, 3.5), headers=prec_headers)
                if int(r.status_code) == 200:
                    doctor_payload = r.json()
                else:
                    doctor_error = f"http_{r.status_code}"
            except Exception as e:
                doctor_error = str(e)[:200]
        else:
            doctor_error = "base_url_missing"

        bundle = _build_precooling_golden_sample_bundle(
            base_url=str(base_url or ""),
            zone=z,
            mode=m,
            simulate_request_diag=diag,
            simulate_result=result,
            doctor=doctor_payload,
            doctor_error=doctor_error,
        )
        content = json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False)
        filename = _golden_sample_filename(zone=z, ts=datetime.datetime.now())
        return dcc.send_string(content, filename)

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-mode-dropdown", "value"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
    )
    def push_mode_to_backend(mode, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": "switch_mode", "zone": zid, "mode": mode}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal mengubah mode: {', '.join(errors[:3])}", {"ts": _now_str()}
        return f"Mode diubah menjadi {mode}.", {"ts": _now_str()}

    def _apply_simple_action(action: str, zone: str, base_url: str, headers: dict | None = None) -> Tuple[str, Dict[str, str]]:
        zone_ids = _expand_zone_scope(zone)
        if not zone_ids:
            return "Zone belum dipilih.", {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": action, "zone": zid}
            _, err = post_apply(payload, base_url=base_url, headers=headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi {action}: {', '.join(errors[:3])}", {"ts": _now_str()}
        return f"Aksi {action} berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-activate-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-activate-btn", "children"), "Activating...", "Activate")],
    )
    def action_activate(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "activate", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi activate: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi activate berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-pause-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-pause-btn", "children"), "Pausing...", "Pause")],
    )
    def action_pause(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "pause", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi pause: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi pause berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-cancel-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-cancel-btn", "children"), "Cancelling...", "Cancel Today")],
    )
    def action_cancel(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "cancel_today", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi cancel_today: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi cancel_today berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-rulebased-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-rulebased-btn", "children"), "Applying...", "Use Rule-Based Strategy")],
    )
    def action_rulebased(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "use_rule_based", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi use_rule_based: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi use_rule_based berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-recompute-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-recompute-btn", "children"), "Recomputing...", "Recompute Schedule")],
    )
    def action_recompute(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "recompute_schedule", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi recompute_schedule: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi recompute_schedule berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-safety-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-stop-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-stop-btn", "children"), "Stopping...", "Stop Precooling")],
    )
    def action_stop(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            _, err = post_apply({"action": "stop_precooling", "zone": zid}, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal menjalankan aksi stop_precooling: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Aksi stop_precooling berhasil.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-safety-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-switch-advisory-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-switch-advisory-btn", "children"), "Switching...", "Switch to Advisory")],
    )
    def action_switch_advisory(n, floor_value, floor_zone_map, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": "switch_mode", "zone": zid, "mode": "advisory"}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal switch advisory: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Mode switched to advisory.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-override-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-request-override-btn", "n_clicks"),
        [
            State("precooling-floor", "value"),
            State("precooling-floor-zone-map", "data"),
            State("precooling-override-temp", "value"),
            State("precooling-override-rh", "value"),
            State("precooling-override-duration", "value"),
            State("precooling-override-hvac-mode", "value"),
            State("precooling-override-energy-source", "value"),
            State("precooling-override-reason", "value"),
            State("backend-readiness-store", "data"),
            State("token-store", "data"),
        ],
        prevent_initial_call=True,
        running=[(Output("precooling-request-override-btn", "children"), "Requesting...", "Request Manual Override")],
    )
    def action_request_override(n, floor_value, floor_zone_map, temp, rh, duration, hvac_mode, energy_source, reason, readiness, token_data):
        prec_headers = get_headers(token_data)
        override = {
            "duration_min": duration,
            "temperature_setpoint_c": temp,
            "rh_setpoint_pct": rh,
            "hvac_mode": hvac_mode,
            "energy_source": energy_source,
        }
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": "request_manual_override", "zone": zid, "override": override, "reason": reason or ""}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal request manual override: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Manual override request terkirim.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-override-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-approve-override-btn", "n_clicks"),
        State("precooling-floor", "value"),
        State("precooling-floor-zone-map", "data"),
        State("precooling-override-reason", "value"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
        running=[(Output("precooling-approve-override-btn", "children"), "Approving...", "Approve Manual Override")],
    )
    def action_approve_override(n, floor_value, floor_zone_map, reason, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": "approve_manual_override", "zone": zid, "reason": reason or ""}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal approve manual override: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Manual override approved.", {"ts": _now_str()}

    @app.callback(
        [Output("precooling-override-action-feedback", "children", allow_duplicate=True), Output("precooling-refresh-signal", "data", allow_duplicate=True)],
        Input("precooling-cancel-override-btn", "n_clicks"),
        [State("precooling-floor", "value"), State("precooling-floor-zone-map", "data"), State("precooling-override-reason", "value"), State("backend-readiness-store", "data"), State("token-store", "data")],
        prevent_initial_call=True,
        running=[(Output("precooling-cancel-override-btn", "children"), "Cancelling...", "Cancel Manual Override")],
    )
    def action_cancel_override(n, floor_value, floor_zone_map, reason, readiness, token_data):
        prec_headers = get_headers(token_data)
        base_url = effective_base_url(readiness)
        zone_ids, err_msg = _resolve_targets_or_error(floor_value, floor_zone_map)
        if err_msg:
            return err_msg, {"ts": _now_str()}
        errors = []
        for zid in zone_ids:
            payload = {"action": "cancel_manual_override", "zone": zid, "reason": reason or ""}
            _, err = post_apply(payload, base_url=base_url, headers=prec_headers)
            if err:
                errors.append(str(err))
        if errors:
            return f"Gagal cancel manual override: {', '.join(errors[:3])}", {"ts": _now_str()}
        return "Manual override canceled.", {"ts": _now_str()}
