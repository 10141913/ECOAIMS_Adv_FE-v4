import json

import dash
from dash import ALL, html, dcc, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import random
from ecoaims_frontend.config import CARD_STYLE
import io
import base64

from urllib.parse import quote
from plotly.subplots import make_subplots

from ecoaims_frontend.services.operational_policy import effective_feature_decision
from ecoaims_frontend.services.reports_api import (
    get_precooling_impact,
    get_precooling_impact_export_csv,
    get_precooling_impact_filter_options,
    get_precooling_impact_history,
    get_last_reports_endpoint_contract,
    get_precooling_impact_session_detail,
    get_precooling_impact_session_timeseries,
)
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.ui.error_ui import error_banner, error_figure, status_banner
from ecoaims_frontend.ui.runtime_contract_banner import render_runtime_endpoint_contract_mismatch_banner

_REPORTS_BUNDLE_FILES = [
    ("weather_timeseries.csv", "Unduh weather_timeseries.csv"),
    ("demand_simulated.csv", "Unduh demand_simulated.csv"),
    ("forecast_output.csv", "Unduh forecast_output.csv"),
    ("baseline_dispatch.csv", "Unduh baseline_dispatch.csv"),
    ("ecoaims_dispatch.csv", "Unduh ecoaims_dispatch.csv"),
    ("scenario_summary.csv", "Unduh scenario_summary.csv"),
]

def _impact_badge(basis: str) -> html.Span:
    b = (basis or "").lower()
    if b == "applied":
        bg, fg, text = "#e8f8f5", "#1e8449", "Applied"
    elif b == "fallback":
        bg, fg, text = "#fdecea", "#c0392b", "Fallback"
    elif b == "insufficient_data":
        bg, fg, text = "#f4f6f7", "#566573", "Insufficient Data"
    else:
        bg, fg, text = "#ebf5fb", "#21618c", "Modeled"
    return html.Span(
        text,
        style={
            "backgroundColor": bg,
            "color": fg,
            "border": f"1px solid {fg}",
            "borderRadius": "999px",
            "padding": "2px 10px",
            "fontSize": "12px",
            "fontWeight": "bold",
        },
    )


def _impact_notice(basis: str, note: str | None) -> html.Div | None:
    b = (basis or "").lower()
    if b == "fallback":
        title = "Fallback session detected"
        detail = note or "Precooling berjalan dalam mode fallback. Dampak mungkin tidak merepresentasikan strategi optimized."
        border = "#c0392b"
        bg = "#fdecea"
    elif b == "insufficient_data":
        title = "Insufficient Data"
        detail = note or "Precooling impact belum tersedia untuk periode ini."
        border = "#566573"
        bg = "#f4f6f7"
    else:
        return None
    return html.Div(
        [html.Div(title, style={"fontWeight": "bold", "marginBottom": "4px"}), html.Div(detail, style={"opacity": 0.9})],
        style={
            "border": f"1px solid {border}",
            "backgroundColor": bg,
            "borderRadius": "6px",
            "padding": "10px 12px",
            "margin": "8px 0",
            "color": "#2c3e50",
        },
    )

def _fidelity_badge(value: str | None) -> html.Span:
    v = str(value or "").strip().lower()
    if v == "actual":
        bg, fg, text = "#e8f8f5", "#1e8449", "Actual"
    elif v == "approximated":
        bg, fg, text = "#fef5e7", "#b9770e", "Approximated"
    else:
        bg, fg, text = "#ebf5fb", "#21618c", "Modeled"
    return html.Span(
        text,
        style={
            "backgroundColor": bg,
            "color": fg,
            "border": f"1px solid {fg}",
            "borderRadius": "999px",
            "padding": "2px 10px",
            "fontSize": "12px",
            "fontWeight": "bold",
            "marginLeft": "6px",
        },
    )


def _chips(values: list, title: str) -> html.Div:
    vs = [str(x) for x in (values or []) if str(x).strip()]
    if not vs:
        return html.Div()
    return html.Div(
        [
            html.Div(title, style={"fontWeight": "bold", "marginBottom": "6px"}),
            html.Div(
                [
                    html.Span(
                        v,
                        style={
                            "display": "inline-block",
                            "padding": "2px 8px",
                            "borderRadius": "999px",
                            "border": "1px solid #ccd1d1",
                            "backgroundColor": "#f8f9fa",
                            "marginRight": "6px",
                            "marginBottom": "6px",
                            "fontSize": "12px",
                            "fontFamily": "monospace",
                        },
                    )
                    for v in vs
                ],
                style={"display": "flex", "flexWrap": "wrap"},
            ),
        ],
        style={"marginTop": "10px"},
    )


def _evidence_fig(payload: dict | None) -> go.Figure:
    p = payload if isinstance(payload, dict) else {}
    ts = p.get("timestamps") if isinstance(p.get("timestamps"), list) else []
    series = p.get("series") if isinstance(p.get("series"), dict) else {}

    def _arr(k: str) -> list:
        v = series.get(k)
        return v if isinstance(v, list) else []

    if not ts:
        fig = go.Figure()
        fig.update_layout(template="plotly_white", margin=dict(l=30, r=30, t=50, b=30), title="Session Evidence (Timeseries)", xaxis=dict(visible=False), yaxis=dict(visible=False), height=360)
        fig.add_annotation(text="Timeseries evidence belum tersedia untuk session ini.", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(color="#566573"))
        return fig

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=("Energy (kW): Before vs After", "Cost (IDR): Before vs After", "CO2 (kg): Before vs After"))
    fig.add_trace(go.Scatter(x=ts, y=_arr("energy_kw_before"), mode="lines", name="Before", line=dict(color="#95a5a6")), row=1, col=1)
    fig.add_trace(go.Scatter(x=ts, y=_arr("energy_kw_after"), mode="lines", name="After", line=dict(color="#27ae60")), row=1, col=1)
    fig.add_trace(go.Scatter(x=ts, y=_arr("cost_idr_before"), mode="lines", name="Before", line=dict(color="#95a5a6")), row=2, col=1)
    fig.add_trace(go.Scatter(x=ts, y=_arr("cost_idr_after"), mode="lines", name="After", line=dict(color="#2980b9")), row=2, col=1)
    fig.add_trace(go.Scatter(x=ts, y=_arr("co2_kg_before"), mode="lines", name="Before", line=dict(color="#95a5a6")), row=3, col=1)
    fig.add_trace(go.Scatter(x=ts, y=_arr("co2_kg_after"), mode="lines", name="After", line=dict(color="#f39c12")), row=3, col=1)
    fig.update_layout(template="plotly_white", height=520, margin=dict(l=40, r=40, t=60, b=40), title="Session Evidence (Timeseries)", showlegend=False)
    return fig


def _reports_placeholder_fig(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        height=280,
        margin=dict(l=30, r=30, t=50, b=30),
        title=title,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(color="#566573"))
    return fig


def _reports_waiting_outputs(message: str) -> tuple:
    empty = _reports_placeholder_fig("Reports", "Waiting for backend...")
    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    return (
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        empty,
        empty,
        status_banner("Reports", "Waiting for backend (Reports)", message),
        html.Div(),
        _reports_placeholder_fig("Precooling Impact (Energy)", "Backend belum siap."),
        _reports_placeholder_fig("Precooling Impact (Peak)", "Backend belum siap."),
        stream_options,
        zone_options,
        _reports_placeholder_fig("Precooling Impact Trend", "Backend belum siap."),
        html.Div("History belum tersedia (backend belum siap).", style={"color": "#566573"}),
        [],
        None,
        html.Div(),
        html.Div(),
        "{}",
    )


def _reports_backend_not_ready_outputs(message: str) -> tuple:
    empty = _reports_placeholder_fig("Reports", "Backend connected (warming up).")
    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    return (
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        empty,
        empty,
        status_banner("Reports", "Backend connected (not ready yet)", message),
        html.Div(),
        _reports_placeholder_fig("Precooling Impact (Energy)", "Backend belum ready."),
        _reports_placeholder_fig("Precooling Impact (Peak)", "Backend belum ready."),
        stream_options,
        zone_options,
        _reports_placeholder_fig("Precooling Impact Trend", "Backend belum ready."),
        html.Div("History belum tersedia (backend belum ready).", style={"color": "#566573"}),
        [],
        None,
        html.Div(),
        html.Div(),
        "{}",
    )


def _reports_contract_mismatch_outputs(message: str) -> tuple:
    empty = _reports_placeholder_fig("Reports", "Contract mismatch.")
    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    return (
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        empty,
        empty,
        status_banner("Reports", "Backend connected but contract mismatch", message),
        html.Div(),
        _reports_placeholder_fig("Precooling Impact (Energy)", "Contract mismatch."),
        _reports_placeholder_fig("Precooling Impact (Peak)", "Contract mismatch."),
        stream_options,
        zone_options,
        _reports_placeholder_fig("Precooling Impact Trend", "Contract mismatch."),
        html.Div("History belum tersedia (contract mismatch).", style={"color": "#566573"}),
        [],
        None,
        html.Div(),
        html.Div(),
        "{}",
    )


def _reports_feature_not_ready_outputs(message: str) -> tuple:
    empty = _reports_placeholder_fig("Reports", "Feature not ready.")
    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    return (
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        empty,
        empty,
        status_banner("Reports", "Feature not ready (Reports)", message),
        html.Div(),
        _reports_placeholder_fig("Precooling Impact (Energy)", "Feature reports belum siap."),
        _reports_placeholder_fig("Precooling Impact (Peak)", "Feature reports belum siap."),
        stream_options,
        zone_options,
        _reports_placeholder_fig("Precooling Impact Trend", "Feature reports belum siap."),
        html.Div("History belum tersedia (feature reports belum siap).", style={"color": "#566573"}),
        [],
        None,
        html.Div(),
        html.Div(),
        "{}",
    )


def _reports_error_outputs(detail: str) -> tuple:
    empty = _reports_placeholder_fig("Reports", "Error")
    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    return (
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        empty,
        empty,
        error_banner("Reports", "Gagal memuat Reports", detail),
        html.Div(),
        error_figure("Precooling Impact (Energy)", detail),
        error_figure("Precooling Impact (Peak)", detail),
        stream_options,
        zone_options,
        error_figure("Precooling Impact Trend", detail),
        html.Div(error_banner("Reports", "Gagal memuat Reports", detail)),
        [],
        None,
        html.Div(),
        html.Div(),
        "{}",
    )


def compute_reports_outputs(period, impact_stream, impact_zone, impact_granularity, impact_basis_filter, readiness) -> tuple:
    r = readiness if isinstance(readiness, dict) else {}
    eff = effective_feature_decision("reports", r)
    base_url = effective_base_url(r)
    if eff.get("final_mode") != "live":
        msg = "\n".join([str(x) for x in (eff.get("reason_chain") or [])]) or "reports_not_live"
        if eff.get("final_mode") == "blocked":
            return _reports_feature_not_ready_outputs(msg)
        return _reports_waiting_outputs(msg)
    if r.get("backend_reachable") is not True:
        msg = f"base_url={r.get('base_url')}\nerror_class={r.get('error_class')}"
        return _reports_waiting_outputs(msg)
    if r.get("backend_ready") is not True:
        msg = f"base_url={r.get('base_url')}\nreasons_not_ready={r.get('reasons_not_ready')}"
        return _reports_backend_not_ready_outputs(msg)
    if r.get("contract_valid") is not True:
        return _reports_contract_mismatch_outputs(str(r.get("contract_mismatch_reason") or "contract_invalid"))
    caps = r.get("capabilities") if isinstance(r.get("capabilities"), dict) else {}
    reports_cap = caps.get("reports") if isinstance(caps.get("reports"), dict) else None
    if not (isinstance(reports_cap, dict) and reports_cap.get("ready") is True):
        return _reports_feature_not_ready_outputs("capability=reports.ready!=true")

    if period == 'today':
        days = 1
    elif period == 'week':
        days = 7
    elif period == 'month':
        days = 30
    else:
        days = 365

    dates = [datetime.now() - timedelta(days=x) for x in range(days, 0, -1)]
    daily_consumption = [random.uniform(800, 1200) for _ in range(days)]
    renewable_ratio = [random.uniform(0.6, 0.8) for _ in range(days)]

    total_consumption = sum(daily_consumption)
    avg_renewable_efficiency = sum(renewable_ratio) / len(renewable_ratio) * 100

    grid_emission_factor = 0.85
    co2_emission = (total_consumption * (1 - avg_renewable_efficiency/100) * grid_emission_factor) / 1000
    co2_saved = (total_consumption * (avg_renewable_efficiency/100) * grid_emission_factor) / 1000

    grid_tariff = 1444.70
    renewable_cost = 800
    cost_savings = total_consumption * (avg_renewable_efficiency/100) * (grid_tariff - renewable_cost)

    if days > 1:
        prev_consumption = sum(daily_consumption[:-7]) if days >= 14 else total_consumption * 0.95
        trend_pct = ((total_consumption - prev_consumption) / prev_consumption) * 100
        trend_text = f"vs {days*2} hari sebelumnya: {'+' if trend_pct > 0 else ''}{trend_pct:.1f}%"
    else:
        trend_text = "vs kemarin: +2.3%"

    consumption_fig = go.Figure()
    consumption_fig.add_trace(go.Scatter(
        x=dates, y=daily_consumption,
        mode='lines+markers', name='Konsumsi Harian',
        line=dict(color='#3498db', width=2)
    ))
    consumption_fig.update_layout(
        title=f'Konsumsi Energi Harian ({days} hari)',
        xaxis_title='Tanggal',
        yaxis_title='Konsumsi (kWh)',
        template='plotly_white',
        margin=dict(l=40, r=40, t=40, b=40)
    )

    composition_data = {
        'Solar PV': sum([random.uniform(0.3, 0.4) * daily_consumption[i] for i in range(min(30, days))]),
        'Wind Turbine': sum([random.uniform(0.2, 0.3) * daily_consumption[i] for i in range(min(30, days))]),
        'Battery': sum([random.uniform(0.1, 0.2) * daily_consumption[i] for i in range(min(30, days))]),
        'PLN/Grid': sum([random.uniform(0.2, 0.3) * daily_consumption[i] for i in range(min(30, days))])
    }

    composition_fig = go.Figure(data=[go.Pie(
        labels=list(composition_data.keys()),
        values=list(composition_data.values()),
        hole=.4,
        marker=dict(colors=['#f1c40f', '#3498db', '#9b59b6', '#e74c3c'])
    )])
    composition_fig.update_layout(
        title='Komposisi Sumber Energi',
        template='plotly_white'
    )

    stream_options = [{"label": "precooling", "value": "precooling"}]
    zone_options = [{"label": "zone_a", "value": "zone_a"}]
    impact_stream = impact_stream or "precooling"
    impact_zone = impact_zone or "zone_a"
    basis_vals = impact_basis_filter if isinstance(impact_basis_filter, list) else []
    basis_str = ",".join([str(x) for x in basis_vals if str(x).strip()]) if basis_vals else None
    gran = str(impact_granularity or "daily")

    opts, opts_err = get_precooling_impact_filter_options(base_url=base_url)
    if not opts_err and isinstance(opts, dict):
        streams = opts.get("streams") if isinstance(opts.get("streams"), list) else ["precooling"]
        zones = opts.get("zones") if isinstance(opts.get("zones"), list) else ["zone_a"]
        stream_options = [{"label": str(x), "value": str(x)} for x in streams if str(x).strip()]
        zone_options = [{"label": str(x), "value": str(x)} for x in zones if str(x).strip()]

    impact_stream = impact_stream or (stream_options[0]["value"] if stream_options else "precooling")
    impact_zone = impact_zone or (zone_options[0]["value"] if zone_options else "zone_a")

    impact_data, impact_err = get_precooling_impact(period, zone=impact_zone, stream_id=impact_stream, basis_filter=basis_str, granularity=gran, base_url=base_url)
    if impact_err or not isinstance(impact_data, dict):
        if isinstance(impact_err, str) and "runtime_endpoint_contract_mismatch" in impact_err:
            last = get_last_reports_endpoint_contract()
            normalized = last.get("normalized") if isinstance(last, dict) else None
            normalized = normalized if isinstance(normalized, dict) else {}
            details = normalized.get("/api/reports/precooling-impact")
            if not isinstance(details, dict) and normalized:
                details = list(normalized.values())[0]
            impact_status = render_runtime_endpoint_contract_mismatch_banner(details)
        else:
            impact_status = error_banner("Reports", "Gagal memuat Precooling Impact", impact_err or "Respons tidak valid")
        impact_cards = html.Div()
        impact_energy_fig = error_figure("Precooling Impact (Energy)", impact_err or "Gagal memuat")
        impact_peak_fig = error_figure("Precooling Impact (Peak)", impact_err or "Gagal memuat")
        impact_trend_fig = error_figure("Precooling Impact Trend", impact_err or "Gagal memuat")
        impact_history_table = html.Div()
        session_select_options = []
        session_select_value = None
        impact_quality = html.Div()
        impact_table = html.Div()
    else:
        basis = (impact_data or {}).get("basis", "insufficient_data")
        note = (impact_data or {}).get("note")
        basis_reason = (impact_data or {}).get("basis_reason")
        confidence = (impact_data or {}).get("confidence")
        status_line = [_impact_badge(str(basis))]
        status_line.append(html.Span(f"  Filter: period={period}, stream={impact_stream}, zone={impact_zone}, granularity={gran}, basis={basis_str or 'all'}", style={"marginLeft": "10px", "fontSize": "12px", "color": "#566573"}))
        if confidence is not None:
            status_line.append(html.Span(f"  Confidence: {float(confidence):.2f}", style={"marginLeft": "10px", "fontSize": "12px", "color": "#566573"}))
        if note:
            status_line.append(html.Span(f"  {note}", style={"marginLeft": "10px", "fontSize": "12px", "color": "#566573"}))
        if basis_reason:
            status_line.append(html.Span(f"  Reason: {basis_reason}", style={"marginLeft": "10px", "fontSize": "12px", "color": "#566573"}))
        if str(basis).lower() == "applied":
            status_line.append(html.Span("  (auto mode)", style={"marginLeft": "10px", "fontSize": "12px", "color": "#1e8449"}))
        impact_status = html.Div([html.Div(status_line), _impact_notice(str(basis), note)])

        summary = (impact_data or {}).get("summary") if isinstance(impact_data, dict) else {}
        scenarios = (impact_data or {}).get("scenarios") if isinstance(impact_data, dict) else []
        quality = (impact_data or {}).get("quality") if isinstance(impact_data, dict) else {}
        impact_cards = _impact_cards(summary if isinstance(summary, dict) else {})
        impact_energy_fig = _impact_fig_compare(scenarios if isinstance(scenarios, list) else [], "energy_kwh", "Before vs After Energy", "kWh")
        impact_peak_fig = _impact_fig_compare(scenarios if isinstance(scenarios, list) else [], "peak_kw", "Before vs After Peak", "kW")
        impact_quality = _quality_panel(quality if isinstance(quality, dict) else {}, str(basis), note)

        hist_data, hist_err = get_precooling_impact_history(period=period, granularity=gran, basis_filter=basis_str, zone=impact_zone, stream_id=impact_stream, base_url=base_url)
        if hist_err:
            impact_trend_fig = error_figure("Precooling Impact Trend", hist_err)
            impact_history_table = html.Div(error_banner("Reports", "Gagal memuat Precooling Impact History", hist_err))
            session_select_options = []
            session_select_value = None
        else:
            rows = (hist_data or {}).get("rows") if isinstance(hist_data, dict) else []
            rows = rows if isinstance(rows, list) else []
            impact_trend_fig = _trend_fig(rows, granularity=gran)
            impact_history_table = _history_table(rows) if rows else html.Div("History belum tersedia untuk filter ini.", style={"color": "#566573"})
            session_select_options = [{"label": f"{row.get('date','-')} | {str(row.get('row_id') or '')[:24]}", "value": row.get("row_id")} for row in rows if isinstance(row, dict) and row.get("row_id")]
            session_select_value = session_select_options[0]["value"] if session_select_options else None

        if str(basis).lower() == "insufficient_data":
            impact_table = html.Div("Precooling impact belum tersedia untuk periode ini.", style={"color": "#566573"})
        else:
            impact_table = _impact_table(scenarios if isinstance(scenarios, list) else [])

    report_data = {
        'period': period,
        'total_consumption': total_consumption,
        'renewable_efficiency': avg_renewable_efficiency,
        'co2_emission': co2_emission,
        'co2_saved': co2_saved,
        'cost_savings': cost_savings,
        'daily_data': [{'date': d.strftime('%Y-%m-%d'), 'consumption': c} for d, c in zip(dates, daily_consumption)]
    }

    return (
        f"{total_consumption:,.0f} kWh",
        f"{avg_renewable_efficiency:.1f}%",
        f"{co2_emission:.2f} ton",
        f"Rp {cost_savings:,.0f}",
        trend_text,
        f"tersimpan: {co2_saved:.2f} ton",
        consumption_fig,
        composition_fig,
        impact_status,
        impact_cards,
        impact_energy_fig,
        impact_peak_fig,
        stream_options,
        zone_options,
        impact_trend_fig,
        impact_history_table,
        session_select_options,
        session_select_value,
        impact_quality,
        impact_table,
        str(report_data),
    )


def _fmt_idr(x: float | None) -> str:
    try:
        if x is None:
            return "Rp -"
        return f"Rp {float(x):,.0f}"
    except (TypeError, ValueError):
        return "Rp -"


def _fmt_float(x: float | None, suffix: str, digits: int = 2) -> str:
    try:
        if x is None:
            return f"-{suffix}"
        return f"{float(x):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return f"-{suffix}"


def _impact_cards(summary: dict) -> html.Div:
    s = summary or {}
    energy = (s.get("energy") or {}) if isinstance(s.get("energy"), dict) else {}
    peak = (s.get("peak") or {}) if isinstance(s.get("peak"), dict) else {}
    cost = (s.get("cost") or {}) if isinstance(s.get("cost"), dict) else {}
    co2 = (s.get("co2") or {}) if isinstance(s.get("co2"), dict) else {}
    comfort = (s.get("comfort") or {}) if isinstance(s.get("comfort"), dict) else {}

    def _sub_before_after(before_val: str, after_val: str) -> html.Div:
        return html.Div(
            [
                html.Div(f"Before: {before_val}", style={"fontSize": "12px", "color": "#566573"}),
                html.Div(f"After: {after_val}", style={"fontSize": "12px", "color": "#566573"}),
            ]
        )

    return html.Div(
        [
            html.Div(
                [
                    html.H4("Energy Impact", style={"margin": "0 0 6px 0"}),
                    html.H2(_fmt_float(energy.get("delta_kwh"), " kWh", 2), style={"margin": 0, "color": "#2ecc71"}),
                    _sub_before_after(_fmt_float(energy.get("before_kwh"), " kWh", 2), _fmt_float(energy.get("after_kwh"), " kWh", 2)),
                ],
                style={**CARD_STYLE, "width": "19%", "display": "inline-block", "textAlign": "center"},
            ),
            html.Div(
                [
                    html.H4("Peak Impact", style={"margin": "0 0 6px 0"}),
                    html.H2(_fmt_float(peak.get("delta_kw"), " kW", 2), style={"margin": 0, "color": "#3498db"}),
                    _sub_before_after(_fmt_float(peak.get("before_kw"), " kW", 2), _fmt_float(peak.get("after_kw"), " kW", 2)),
                ],
                style={**CARD_STYLE, "width": "19%", "display": "inline-block", "textAlign": "center", "marginLeft": "1%"},
            ),
            html.Div(
                [
                    html.H4("Cost Impact", style={"margin": "0 0 6px 0"}),
                    html.H2(_fmt_idr(cost.get("delta_idr")), style={"margin": 0, "color": "#27ae60"}),
                    _sub_before_after(_fmt_idr(cost.get("before_idr")), _fmt_idr(cost.get("after_idr"))),
                ],
                style={**CARD_STYLE, "width": "19%", "display": "inline-block", "textAlign": "center", "marginLeft": "1%"},
            ),
            html.Div(
                [
                    html.H4("CO2 Impact", style={"margin": "0 0 6px 0"}),
                    html.H2(_fmt_float(co2.get("delta_kg"), " kg", 2), style={"margin": 0, "color": "#f39c12"}),
                    _sub_before_after(_fmt_float(co2.get("before_kg"), " kg", 2), _fmt_float(co2.get("after_kg"), " kg", 2)),
                ],
                style={**CARD_STYLE, "width": "19%", "display": "inline-block", "textAlign": "center", "marginLeft": "1%"},
            ),
            html.Div(
                [
                    html.H4("Comfort Impact", style={"margin": "0 0 6px 0"}),
                    html.H2(
                        _fmt_float((comfort.get("after_ratio") * 100.0) if comfort.get("after_ratio") is not None else None, "%", 1),
                        style={"margin": 0, "color": "#8e44ad"},
                    ),
                    _sub_before_after(
                        _fmt_float((comfort.get("before_ratio") * 100.0) if comfort.get("before_ratio") is not None else None, "%", 1),
                        _fmt_float((comfort.get("after_ratio") * 100.0) if comfort.get("after_ratio") is not None else None, "%", 1),
                    ),
                ],
                style={**CARD_STYLE, "width": "19%", "display": "inline-block", "textAlign": "center", "marginLeft": "1%"},
            ),
        ],
        style={"marginBottom": "10px"},
    )


def _impact_table(scenarios: list) -> html.Table:
    rows = []
    for s in scenarios or []:
        if not isinstance(s, dict):
            continue
        name = s.get("name", "-")
        rows.append(
            html.Tr(
                [
                    html.Td(str(name), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_fmt_float(s.get("energy_kwh", 0.0), "", 2), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_fmt_float(s.get("peak_kw", 0.0), "", 2), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_fmt_idr(s.get("cost_idr", 0.0)), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_fmt_float(s.get("co2_kg", 0.0), "", 2), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_fmt_float(float(s.get("comfort_compliance", 0.0) or 0.0) * 100.0, "%", 1), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                ]
            )
        )

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Scenario", style={"textAlign": "left", "padding": "8px"}),
                        html.Th("Energy (kWh)", style={"textAlign": "right", "padding": "8px"}),
                        html.Th("Peak (kW)", style={"textAlign": "right", "padding": "8px"}),
                        html.Th("Cost (IDR)", style={"textAlign": "right", "padding": "8px"}),
                        html.Th("CO2 (kg)", style={"textAlign": "right", "padding": "8px"}),
                        html.Th("Comfort", style={"textAlign": "right", "padding": "8px"}),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"},
    )


def _impact_fig_compare(scenarios: list, metric_key: str, title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    labels = []
    values = []
    for s in scenarios or []:
        if not isinstance(s, dict):
            continue
        labels.append(str(s.get("name") or "-"))
        try:
            values.append(float(s.get(metric_key, 0.0) or 0.0))
        except (TypeError, ValueError):
            values.append(0.0)
    if not labels:
        fig.update_layout(
            template="plotly_white",
            margin=dict(l=30, r=30, t=50, b=30),
            title=title,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=260,
        )
        fig.add_annotation(
            text="Data belum tersedia untuk periode ini.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(color="#566573"),
        )
        return fig
    fig.add_trace(go.Bar(x=labels, y=values, marker_color=["#95a5a6", "#e67e22", "#27ae60"][: len(labels)]))
    fig.update_layout(template="plotly_white", height=280, margin=dict(l=40, r=40, t=45, b=40), title=title, yaxis_title=y_title)
    return fig


def _quality_panel(quality: dict | None, basis: str, note: str | None) -> html.Div:
    q = quality if isinstance(quality, dict) else {}

    def _bool(v: object) -> str:
        if v is True:
            return "Yes"
        if v is False:
            return "No"
        return "-"

    def _num(v: object, suffix: str = "", digits: int = 1) -> str:
        try:
            if v is None:
                return "-"
            return f"{float(v):.{digits}f}{suffix}"
        except (TypeError, ValueError):
            return "-"

    rows = [
        ("Aggregation Mode", str(q.get("aggregation_mode") or "-")),
        ("Aggregation Reason", str(q.get("aggregation_reason") or "-")),
        ("Basis Resolved", str(q.get("basis_resolved") or "-")),
        ("Reconstructable", _bool(q.get("reconstructable"))),
        ("Coverage", _num(q.get("coverage_pct"), "%", 1)),
        ("Telemetry Completeness", _num(q.get("telemetry_completeness_pct"), "%", 1)),
        ("Source Cost", str(q.get("source_cost") or "-")),
        ("Source CO2", str(q.get("source_co2") or "-")),
        ("Source Comfort", str(q.get("source_comfort") or "-")),
        ("Matched Apply Events", str(q.get("matched_apply_events") if q.get("matched_apply_events") is not None else "-")),
        ("Matched Dispatch Rows", str(q.get("matched_dispatch_rows") if q.get("matched_dispatch_rows") is not None else "-")),
        ("Matched Windows", str(q.get("matched_windows") if q.get("matched_windows") is not None else "-")),
        ("Gaps Detected", _bool(q.get("gaps_detected"))),
        ("Confidence", _num(q.get("confidence"), "", 2)),
    ]

    notes = q.get("notes")
    notes = notes if isinstance(notes, list) else []
    note_line = note or ""
    if note_line:
        notes = [note_line, *[str(x) for x in notes if x]]
    notes = [str(x) for x in notes if isinstance(x, (str, int, float)) and str(x).strip()]

    warn = None
    try:
        conf = float(q.get("confidence")) if q.get("confidence") is not None else None
    except (TypeError, ValueError):
        conf = None
    gaps = bool(q.get("gaps_detected"))
    dispatch_rows = q.get("matched_dispatch_rows")
    telemetry_backed = dispatch_rows is not None and dispatch_rows != 0
    if (not telemetry_backed) or gaps or (conf is not None and conf < 0.6) or str(basis).lower() in {"fallback", "insufficient_data"}:
        explain = "Sebagian data mungkin tidak lengkap; interpretasi dampak perlu kehati-hatian."
        if not telemetry_backed:
            explain = "History belum sepenuhnya telemetry-backed (matched_dispatch_rows kosong/0)."
        warn = html.Div(
            [
                html.Div("Data Quality Notice", style={"fontWeight": "bold", "marginBottom": "4px"}),
                html.Div(explain, style={"opacity": 0.9}),
            ],
            style={"border": "1px solid #566573", "backgroundColor": "#f4f6f7", "borderRadius": "6px", "padding": "10px 12px", "margin": "8px 0", "color": "#2c3e50"},
        )

    return html.Div(
        [
            html.H4("Data Quality", style={"marginBottom": "10px"}),
            warn,
            html.Table(
                [
                    html.Tbody(
                        [
                            html.Tr([html.Td(k, style={"padding": "6px 8px", "borderBottom": "1px solid #eee"}), html.Td(v, style={"padding": "6px 8px", "borderBottom": "1px solid #eee", "textAlign": "right"})])
                            for k, v in rows
                        ]
                    )
                ],
                style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"},
            ),
            html.Div([html.Div(x, style={"fontSize": "12px", "color": "#566573"}) for x in notes], style={"marginTop": "10px"}) if notes else html.Div(),
        ]
    )


def _trend_placeholder(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(template="plotly_white", margin=dict(l=30, r=30, t=50, b=30), title=title, xaxis=dict(visible=False), yaxis=dict(visible=False), height=320)
    fig.add_annotation(text="History belum tersedia untuk filter ini.", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(color="#566573"))
    return fig


def _trend_fig(rows: list, granularity: str) -> go.Figure:
    if not isinstance(rows, list) or not rows:
        return _trend_placeholder("Precooling Impact Trend")
    x = []
    e = []
    c = []
    co2 = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        label = r.get("date") if str(granularity).lower() == "daily" else (r.get("ts") or r.get("date"))
        x.append(label)
        e.append(r.get("energy_delta_kwh"))
        c.append(r.get("cost_delta_idr"))
        co2.append(r.get("co2_delta_kg"))

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=("Energy Delta (kWh)", "Cost Delta (IDR)", "CO2 Delta (kg)"))
    fig.add_trace(go.Scatter(x=x, y=e, mode="lines+markers", name="Energy Δ", line=dict(color="#27ae60")), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=c, mode="lines+markers", name="Cost Δ", line=dict(color="#2980b9")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=co2, mode="lines+markers", name="CO2 Δ", line=dict(color="#f39c12")), row=3, col=1)
    fig.update_layout(template="plotly_white", height=380, margin=dict(l=40, r=40, t=60, b=40), title="Precooling Impact Trend", showlegend=False)
    return fig


def _history_table(rows: list) -> html.Table:
    def _s(x: object) -> str:
        return str(x) if x is not None and str(x).strip() else "-"

    def _trunc(x: object, n: int = 16) -> str:
        s = _s(x)
        if s == "-":
            return s
        return s if len(s) <= n else (s[:n] + "…")

    def _flt(x: object, digits: int = 2) -> str:
        try:
            if x is None:
                return "-"
            return f"{float(x):.{digits}f}"
        except (TypeError, ValueError):
            return "-"

    def _idr(x: object) -> str:
        try:
            if x is None:
                return "-"
            return f"{float(x):,.0f}"
        except (TypeError, ValueError):
            return "-"

    body = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        body.append(
            html.Tr(
                [
                    html.Td(_trunc(r.get("row_id")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "fontFamily": "monospace"}),
                    html.Td(_s(r.get("date")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_s(r.get("session_window")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_s(r.get("basis")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_s(r.get("stream_id")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_s(r.get("zone_id")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_flt(r.get("energy_before_kwh")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("energy_after_kwh")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("energy_delta_kwh")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_idr(r.get("cost_before_idr")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_idr(r.get("cost_after_idr")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_idr(r.get("cost_delta_idr")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("co2_before_kg")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("co2_after_kg")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("co2_delta_kg")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("comfort_before_ratio"), 3), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("comfort_after_ratio"), 3), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_flt(r.get("comfort_delta_ratio"), 3), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_s(r.get("applied_scenario")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_s(r.get("fallback_used")), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                    html.Td(_trunc(r.get("event_id")), style={"padding": "8px", "borderBottom": "1px solid #ddd", "fontFamily": "monospace"}),
                    html.Td(_flt(r.get("confidence"), 2), style={"padding": "8px", "borderBottom": "1px solid #ddd", "textAlign": "right"}),
                    html.Td(_trunc(r.get("notes"), 40), style={"padding": "8px", "borderBottom": "1px solid #ddd"}),
                ]
            )
        )

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Row", style={"padding": "8px"}),
                        html.Th("Date", style={"padding": "8px"}),
                        html.Th("Window", style={"padding": "8px"}),
                        html.Th("Basis", style={"padding": "8px"}),
                        html.Th("Stream", style={"padding": "8px"}),
                        html.Th("Zone", style={"padding": "8px"}),
                        html.Th("E Before", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("E After", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("E Δ", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("C Before", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("C After", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("C Δ", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("CO2 B", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("CO2 A", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("CO2 Δ", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("Comfort B", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("Comfort A", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("Comfort Δ", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("Applied Scenario", style={"padding": "8px"}),
                        html.Th("Fallback", style={"padding": "8px"}),
                        html.Th("Event", style={"padding": "8px"}),
                        html.Th("Conf", style={"padding": "8px", "textAlign": "right"}),
                        html.Th("Notes", style={"padding": "8px"}),
                    ]
                )
            ),
            html.Tbody(body),
        ],
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": "12px"},
    )
def create_reports_layout() -> html.Div:
    """
    Creates the layout for the Reports Tab.
    Provides energy consumption reports, CO2 emissions, and system efficiency.
    """
    return html.Div([
        # Header
        html.H2("Laporan Energi & Performa Sistem", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

        # --- Controls Row ---
        html.Div([
            html.Div([
                html.Label("Periode Laporan:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='reports-period-dropdown',
                    options=[
                        {'label': 'Hari Ini', 'value': 'today'},
                        {'label': '7 Hari Terakhir', 'value': 'week'},
                        {'label': '30 Hari Terakhir', 'value': 'month'},
                        {'label': 'Tahun Ini', 'value': 'year'}
                    ],
                    value='week',
                    clearable=False,
                    style={'width': '200px'}
                )
            ], style={'display': 'inline-block', 'marginRight': '20px'}),

            html.Div([
                html.Label("Format Export:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='reports-format-dropdown',
                    options=[
                        {'label': 'CSV', 'value': 'csv'},
                        {'label': 'PDF', 'value': 'pdf'}
                    ],
                    value='csv',
                    clearable=False,
                    style={'width': '120px'}
                )
            ], style={'display': 'inline-block', 'marginRight': '20px'}),

            html.Button("Generate Report", id='reports-generate-btn', n_clicks=0,
                       style={'backgroundColor': '#27ae60', 'color': 'white', 'border': 'none', 
                              'padding': '10px 20px', 'borderRadius': '5px', 'cursor': 'pointer',
                              'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'marginBottom': '30px'}),

        # --- Summary Cards Row ---
        html.Div([
            html.Div([
                html.H4("Konsumsi Total", style={'margin': '0 0 10px 0'}),
                html.H2(id='reports-total-consumption', children="0 kWh", 
                       style={'color': '#e74c3c', 'margin': '0'}),
                html.P(id='reports-consumption-trend', children="vs periode sebelumnya", 
                      style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '5px 0 0 0'})
            ], style={**CARD_STYLE, 'width': '23%', 'display': 'inline-block', 'textAlign': 'center'}),

            html.Div([
                html.H4("Efisiensi Renewable", style={'margin': '0 0 10px 0'}),
                html.H2(id='reports-renewable-efficiency', children="0%", 
                       style={'color': '#2ecc71', 'margin': '0'}),
                html.P("Pengurangan emisi vs grid", style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '5px 0 0 0'})
            ], style={**CARD_STYLE, 'width': '23%', 'display': 'inline-block', 'textAlign': 'center', 'marginLeft': '1%'}),

            html.Div([
                html.H4("Emisi CO2", style={'margin': '0 0 10px 0'}),
                html.H2(id='reports-co2-emission', children="0 ton", 
                       style={'color': '#f39c12', 'margin': '0'}),
                html.P(id='reports-co2-saved', children="tersimpan vs grid", 
                      style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '5px 0 0 0'})
            ], style={**CARD_STYLE, 'width': '23%', 'display': 'inline-block', 'textAlign': 'center', 'marginLeft': '1%'}),

            html.Div([
                html.H4("Penghematan Biaya", style={'margin': '0 0 10px 0'}),
                html.H2(id='reports-cost-savings', children="Rp 0", 
                       style={'color': '#27ae60', 'margin': '0'}),
                html.P("vs tarif grid PLN", style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '5px 0 0 0'})
            ], style={**CARD_STYLE, 'width': '23%', 'display': 'inline-block', 'textAlign': 'center', 'marginLeft': '1%'})
        ], style={'marginBottom': '30px'}),

        # --- Charts Row ---
        html.Div([
            html.Div([
                html.H4("Tren Konsumsi Harian", style={'marginBottom': '15px'}),
                dcc.Graph(id='reports-daily-consumption-chart', style={'height': '300px'})
            ], style={**CARD_STYLE, 'width': '48%', 'display': 'inline-block'}),

            html.Div([
                html.H4("Komposisi Sumber Energi", style={'marginBottom': '15px'}),
                dcc.Graph(id='reports-energy-composition-chart', style={'height': '300px'})
            ], style={**CARD_STYLE, 'width': '48%', 'display': 'inline-block', 'marginLeft': '2%'})
        ], style={'marginBottom': '30px'}),

        html.Div(
            [
                html.H3("Precooling Impact", style={"marginBottom": "10px"}),
                html.Div(
                    [
                        html.Div("Tujuan & definisi metrik", style={"fontWeight": "bold", "marginBottom": "6px"}),
                        html.Div(
                            "Precooling Impact (Reports) menampilkan dampak precooling dalam format before vs after (delta + nilai before/after) dari endpoint reports precooling.",
                            style={"fontSize": "12px", "color": "#566573", "lineHeight": "1.6"},
                        ),
                        html.Div(
                            "Untuk memastikan penyebab perbedaan angka dengan KPI Dashboard, catat filter yang dipilih di tab Reports (period, stream_id, zone_id, basis) karena filter ini menentukan window dan scope perhitungan.",
                            style={"fontSize": "12px", "color": "#566573", "lineHeight": "1.6", "marginTop": "6px"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                html.Div(id="reports-precooling-impact-status", style={"marginBottom": "10px"}),
                html.Div(id="reports-precooling-impact-cards"),
                html.Div(
                    [
                        html.Div([dcc.Graph(id="reports-precooling-impact-energy-fig", style={"height": "300px"})], style={**CARD_STYLE, "width": "48%", "display": "inline-block"}),
                        html.Div([dcc.Graph(id="reports-precooling-impact-peak-fig", style={"height": "300px"})], style={**CARD_STYLE, "width": "48%", "display": "inline-block", "marginLeft": "2%"}),
                    ],
                    style={"marginBottom": "12px"},
                ),
                html.Div(
                    [
                        html.H4("Impact History", style={"marginBottom": "10px"}),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Stream", style={"fontWeight": "bold", "marginBottom": "6px"}),
                                        dcc.Dropdown(
                                            id="reports-precooling-impact-stream-filter",
                                            options=[{"label": "precooling", "value": "precooling"}],
                                            value="precooling",
                                            clearable=False,
                                            style={"width": "220px"},
                                        ),
                                    ],
                                    style={"display": "inline-block", "marginRight": "20px"},
                                ),
                                html.Div(
                                    [
                                        html.Div("Zone", style={"fontWeight": "bold", "marginBottom": "6px"}),
                                        dcc.Dropdown(
                                            id="reports-precooling-impact-zone-filter",
                                            options=[{"label": "zone_a", "value": "zone_a"}],
                                            value="zone_a",
                                            clearable=False,
                                            style={"width": "180px"},
                                        ),
                                    ],
                                    style={"display": "inline-block", "marginRight": "20px"},
                                ),
                                html.Div(
                                    [
                                        html.Div("Granularity", style={"fontWeight": "bold", "marginBottom": "6px"}),
                                        dcc.RadioItems(
                                            id="reports-precooling-impact-granularity",
                                            options=[{"label": "Daily", "value": "daily"}, {"label": "Session", "value": "session"}],
                                            value="daily",
                                            inline=True,
                                        ),
                                    ],
                                    style={"display": "inline-block", "marginRight": "20px"},
                                ),
                                html.Div(
                                    [
                                        html.Div("Basis Filter", style={"fontWeight": "bold", "marginBottom": "6px"}),
                                        dcc.Dropdown(
                                            id="reports-precooling-impact-basis-filter",
                                            options=[
                                                {"label": "Applied", "value": "applied"},
                                                {"label": "Modeled", "value": "modeled"},
                                                {"label": "Fallback", "value": "fallback"},
                                            ],
                                            value=["modeled", "applied", "fallback"],
                                            multi=True,
                                            clearable=False,
                                            style={"width": "260px"},
                                        ),
                                    ],
                                    style={"display": "inline-block"},
                                ),
                            ],
                            style={"marginBottom": "10px"},
                        ),
                        dcc.Graph(id="reports-precooling-impact-trend-fig", style={"height": "380px"}),
                        html.Div(id="reports-precooling-impact-history-table", style={"overflowX": "auto"}),
                        html.Div(
                            [
                                dcc.Dropdown(id="reports-precooling-impact-session-select", options=[], value=None, placeholder="Select session (row_id)...", style={"width": "420px", "display": "inline-block"}),
                                html.Button(
                                    "Open Session Detail",
                                    id="reports-precooling-impact-session-open-btn",
                                    n_clicks=0,
                                    style={"backgroundColor": "#34495e", "color": "white", "border": "none", "padding": "10px 12px", "borderRadius": "5px", "cursor": "pointer", "fontWeight": "bold", "marginLeft": "10px"},
                                ),
                            ],
                            style={"marginTop": "10px"},
                        ),
                    ],
                    style={**CARD_STYLE, "marginBottom": "12px"},
                ),
                html.Div(id="reports-precooling-impact-quality", style={**CARD_STYLE, "marginBottom": "12px"}),
                html.Div(
                    [
                        html.Button(
                            "Export Precooling Impact CSV",
                            id="reports-precooling-impact-export-btn",
                            n_clicks=0,
                            style={"backgroundColor": "#2c3e50", "color": "white", "border": "none", "padding": "10px 14px", "borderRadius": "5px", "cursor": "pointer", "fontWeight": "bold"},
                        ),
                        html.Div(id="reports-precooling-impact-export-status", style={"marginTop": "10px"}),
                        dcc.Download(id="reports-precooling-impact-export-download"),
                    ],
                    style={**CARD_STYLE, "marginBottom": "12px"},
                ),
                html.Div(
                    [
                        html.H4("Impact Table", style={"marginBottom": "10px"}),
                        html.Div(id="reports-precooling-impact-table"),
                    ],
                    style={**CARD_STYLE},
                ),
            ],
            id="reports-precooling-impact-panel",
            style={**CARD_STYLE, "marginBottom": "30px"},
        ),

        html.Div(id="reports-precooling-impact-session-modal-container"),

        # --- Export Section ---
        html.Div([
            html.H4("Export Laporan", style={'marginBottom': '15px'}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Reports Bundle (Backend)", style={"fontWeight": "bold", "marginBottom": "10px"}),
                            html.Div(id="reports-bundle-downloads"),
                        ],
                        style={"marginBottom": "16px"},
                    ),
                    html.Div(id='reports-export-section', style={'textAlign': 'center'}),
                ]
            )
        ], style={**CARD_STYLE}),

        # Hidden div to store report data
        html.Div(id='reports-data-store', style={'display': 'none'})

    ], style={'padding': '20px'})

def create_reports_callbacks(app):
    """
    Registers callbacks for the Reports Tab.
    """
    
    @app.callback(
        [Output('reports-total-consumption', 'children'),
         Output('reports-renewable-efficiency', 'children'),
         Output('reports-co2-emission', 'children'),
         Output('reports-cost-savings', 'children'),
         Output('reports-consumption-trend', 'children'),
         Output('reports-co2-saved', 'children'),
         Output('reports-daily-consumption-chart', 'figure'),
         Output('reports-energy-composition-chart', 'figure'),
         Output('reports-precooling-impact-status', 'children'),
         Output('reports-precooling-impact-cards', 'children'),
         Output('reports-precooling-impact-energy-fig', 'figure'),
         Output('reports-precooling-impact-peak-fig', 'figure'),
         Output('reports-precooling-impact-stream-filter', 'options'),
         Output('reports-precooling-impact-zone-filter', 'options'),
         Output('reports-precooling-impact-trend-fig', 'figure'),
         Output('reports-precooling-impact-history-table', 'children'),
         Output('reports-precooling-impact-session-select', 'options'),
         Output('reports-precooling-impact-session-select', 'value'),
         Output('reports-precooling-impact-quality', 'children'),
         Output('reports-precooling-impact-table', 'children'),
         Output('reports-data-store', 'children')],
        [Input('reports-generate-btn', 'n_clicks'),
         Input('reports-period-dropdown', 'value'),
         Input('reports-precooling-impact-stream-filter', 'value'),
         Input('reports-precooling-impact-zone-filter', 'value'),
         Input('reports-precooling-impact-granularity', 'value'),
         Input('reports-precooling-impact-basis-filter', 'value')],
        State("backend-readiness-store", "data"),
    )
    def update_reports(n_clicks, period, impact_stream, impact_zone, impact_granularity, impact_basis_filter, readiness):
        """
        Updates all report components based on selected period.
        """
        try:
            return compute_reports_outputs(period, impact_stream, impact_zone, impact_granularity, impact_basis_filter, readiness)
        except Exception as e:
            return _reports_error_outputs(str(e))

    @app.callback(
        [Output("reports-precooling-impact-export-download", "data"), Output("reports-precooling-impact-export-status", "children")],
        [Input("reports-precooling-impact-export-btn", "n_clicks")],
        [
            State("reports-period-dropdown", "value"),
            State("reports-precooling-impact-stream-filter", "value"),
            State("reports-precooling-impact-zone-filter", "value"),
            State("reports-precooling-impact-granularity", "value"),
            State("reports-precooling-impact-basis-filter", "value"),
            State("backend-readiness-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def export_precooling_impact_csv(n_clicks, period, stream_id, zone_id, granularity, basis_filter, readiness):
        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        reachable = bool(r.get("backend_reachable")) if "backend_reachable" in r else True
        contract_valid = bool(r.get("contract_valid")) if "contract_valid" in r else True
        caps = r.get("capabilities") if isinstance(r.get("capabilities"), dict) else {}
        reports_ready = True
        if isinstance(caps.get("reports"), dict) and caps.get("reports", {}).get("ready") is False:
            reports_ready = False
        if not reachable:
            return None, status_banner("Reports", "Waiting for backend (Reports)", f"base_url={r.get('base_url')}\nerror_class={r.get('error_class')}")
        if not contract_valid:
            return None, status_banner("Reports", "Backend connected but contract mismatch", str(r.get("contract_mismatch_reason") or "contract_invalid"))
        if not reports_ready:
            return None, status_banner("Reports", "Feature not ready (Reports)", "feature=reports")
        basis_vals = basis_filter if isinstance(basis_filter, list) else []
        basis_str = ",".join([str(x) for x in basis_vals if str(x).strip()]) if basis_vals else None
        content, err = get_precooling_impact_export_csv(
            period=period,
            granularity=str(granularity or "daily"),
            basis_filter=basis_str,
            zone=zone_id,
            stream_id=stream_id,
            base_url=base_url,
        )
        if err or not content:
            return None, error_banner("Reports", "Gagal export Precooling Impact CSV", err or "Dataset kosong.")
        filename = f"precooling_impact_{period}_{granularity}.csv"
        return dcc.send_bytes(content, filename), html.Div("Export siap diunduh.", style={"color": "#1e8449"})

    @app.callback(
        Output("reports-bundle-downloads", "children"),
        Input("backend-readiness-store", "data"),
        prevent_initial_call=False,
    )
    def render_reports_bundle_downloads(readiness):
        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        reachable = bool(r.get("backend_reachable")) if "backend_reachable" in r else True
        if not reachable:
            return status_banner("Reports", "Waiting for backend (Reports)", f"base_url={r.get('base_url')}\nerror_class={r.get('error_class')}")
        if not isinstance(base_url, str) or not base_url.strip():
            return html.Div("Backend base URL belum tersedia.", style={"color": "#566573"})

        def _btn(filename: str, text: str):
            url = base_url.rstrip("/") + "/api/reports/download/" + quote(filename)
            return html.A(
                text,
                href=url,
                download=filename,
                target="_blank",
                style={
                    "backgroundColor": "#3498db",
                    "color": "white",
                    "padding": "10px 12px",
                    "textDecoration": "none",
                    "borderRadius": "6px",
                    "display": "inline-block",
                    "fontWeight": "bold",
                    "minWidth": "260px",
                    "textAlign": "center",
                },
            )

        return html.Div(
            [_btn(fn, label) for fn, label in _REPORTS_BUNDLE_FILES],
            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
        )

    @app.callback(
        Output("reports-precooling-impact-session-modal-container", "children"),
        [Input("reports-precooling-impact-session-open-btn", "n_clicks"), Input({"type": "reports-precooling-impact-modal-close", "name": ALL}, "n_clicks")],
        [State("reports-precooling-impact-session-select", "value"), State("reports-period-dropdown", "value"), State("reports-precooling-impact-stream-filter", "value"), State("reports-precooling-impact-zone-filter", "value"), State("backend-readiness-store", "data")],
        prevent_initial_call=True,
    )
    def open_session_detail(open_clicks, close_clicks, selected_row_id, period, stream_id, zone_id, readiness):
        ctx = dash.callback_context
        if not ctx.triggered:
            return []
        prop_id = ctx.triggered[0].get("prop_id") or ""
        id_part = prop_id.split(".", 1)[0]
        trig = None
        if id_part.startswith("{"):
            try:
                trig = json.loads(id_part)
            except Exception:
                trig = id_part
        else:
            trig = id_part

        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        reachable = bool(r.get("backend_reachable")) if "backend_reachable" in r else True
        contract_valid = bool(r.get("contract_valid")) if "contract_valid" in r else True
        caps = r.get("capabilities") if isinstance(r.get("capabilities"), dict) else {}
        reports_ready = True
        if isinstance(caps.get("reports"), dict) and caps.get("reports", {}).get("ready") is False:
            reports_ready = False
        if not reachable:
            body = status_banner("Reports", "Waiting for backend (Reports)", f"base_url={r.get('base_url')}\nerror_class={r.get('error_class')}")
            return [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                        html.Button(
                                            "Close",
                                            id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                            n_clicks=0,
                                            style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                        ),
                                    ],
                                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                                ),
                                html.Div(
                                    [
                                        body,
                                        dcc.Graph(
                                            id="reports-precooling-impact-session-evidence-fig",
                                            figure=_reports_placeholder_fig("Session Evidence (Timeseries)", "Backend belum siap."),
                                        ),
                                    ],
                                    id="reports-precooling-impact-session-modal-body",
                                ),
                            ],
                            style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                        ),
                    ],
                    id="reports-precooling-impact-session-modal",
                    style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
                )
            ]
        if not contract_valid:
            body = status_banner("Reports", "Backend connected but contract mismatch", str(r.get("contract_mismatch_reason") or "contract_invalid"))
            return [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                        html.Button(
                                            "Close",
                                            id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                            n_clicks=0,
                                            style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                        ),
                                    ],
                                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                                ),
                                html.Div(
                                    [
                                        body,
                                        dcc.Graph(
                                            id="reports-precooling-impact-session-evidence-fig",
                                            figure=_reports_placeholder_fig("Session Evidence (Timeseries)", "Contract mismatch."),
                                        ),
                                    ],
                                    id="reports-precooling-impact-session-modal-body",
                                ),
                            ],
                            style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                        ),
                    ],
                    id="reports-precooling-impact-session-modal",
                    style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
                )
            ]
        if not reports_ready:
            body = status_banner("Reports", "Feature not ready (Reports)", "feature=reports")
            return [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                        html.Button(
                                            "Close",
                                            id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                            n_clicks=0,
                                            style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                        ),
                                    ],
                                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                                ),
                                html.Div(
                                    [
                                        body,
                                        dcc.Graph(
                                            id="reports-precooling-impact-session-evidence-fig",
                                            figure=_reports_placeholder_fig("Session Evidence (Timeseries)", "Feature reports belum siap."),
                                        ),
                                    ],
                                    id="reports-precooling-impact-session-modal-body",
                                ),
                            ],
                            style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                        ),
                    ],
                    id="reports-precooling-impact-session-modal",
                    style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
                )
            ]
        if isinstance(trig, dict) and trig.get("type") == "reports-precooling-impact-modal-close":
            return []

        if trig != "reports-precooling-impact-session-open-btn":
            return []

        rid = str(selected_row_id or "").strip()
        if not rid:
            body = error_banner("Reports", "Gagal memuat detail session", "row_id kosong")
            return [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                        html.Button(
                                            "Close",
                                            id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                            n_clicks=0,
                                            style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                        ),
                                    ],
                                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                                ),
                                html.Div(
                                    [
                                        body,
                                        dcc.Graph(
                                            id="reports-precooling-impact-session-evidence-fig",
                                            figure=_reports_placeholder_fig("Session Evidence (Timeseries)", "row_id kosong."),
                                        ),
                                    ],
                                    id="reports-precooling-impact-session-modal-body",
                                ),
                            ],
                            style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                        ),
                    ],
                    id="reports-precooling-impact-session-modal",
                    style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
                )
            ]

        detail, err = get_precooling_impact_session_detail(row_id=rid, period=period, zone=zone_id, stream_id=stream_id, base_url=base_url)
        if err or not isinstance(detail, dict):
            body = error_banner("Reports", "Gagal memuat detail session", err or "Respons tidak valid")
            return [
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                        html.Button(
                                            "Close",
                                            id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                            n_clicks=0,
                                            style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                        ),
                                    ],
                                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                                ),
                                html.Div(
                                    [
                                        body,
                                        dcc.Graph(
                                            id="reports-precooling-impact-session-evidence-fig",
                                            figure=_reports_placeholder_fig("Session Evidence (Timeseries)", "Detail session tidak tersedia."),
                                        ),
                                    ],
                                    id="reports-precooling-impact-session-modal-body",
                                ),
                            ],
                            style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                        ),
                    ],
                    id="reports-precooling-impact-session-modal",
                    style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
                )
            ]

        record = detail.get("record") if isinstance(detail.get("record"), dict) else {}
        quality = detail.get("quality") if isinstance(detail.get("quality"), dict) else {}
        telemetry = detail.get("telemetry_preview")
        telemetry = telemetry if isinstance(telemetry, list) else []
        before_fidelity = detail.get("before_fidelity")
        after_fidelity = detail.get("after_fidelity")
        reason_codes = [
            detail.get("basis_reason_code"),
            detail.get("aggregation_reason_code"),
            detail.get("fallback_reason_code"),
        ]
        reason_codes = [x for x in reason_codes if isinstance(x, str) and x.strip()]
        quality_flags = detail.get("quality_flags")
        quality_flags = quality_flags if isinstance(quality_flags, list) else []

        ts_payload, ts_err = get_precooling_impact_session_timeseries(row_id=rid, period=period, zone=zone_id, stream_id=stream_id, base_url=base_url)
        evidence_fig = _evidence_fig(ts_payload if isinstance(ts_payload, dict) else None) if not ts_err else error_figure("Session Evidence (Timeseries)", ts_err)

        body = html.Div(
            [
                html.Div(
                    [
                        html.Div(f"Row ID: {record.get('row_id', rid)}", style={"fontFamily": "monospace", "fontSize": "12px", "color": "#566573"}),
                        html.Div(f"Window: {record.get('session_window', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Stream: {record.get('stream_id', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Zone: {record.get('zone_id', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Basis: {record.get('basis', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Applied Scenario: {record.get('applied_scenario', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Fallback Used: {record.get('fallback_used', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Confidence: {record.get('confidence', '-')}", style={"fontSize": "13px"}),
                        html.Div(f"Notes: {record.get('notes', '-')}", style={"fontSize": "13px", "color": "#566573"}),
                        html.Div(
                            [
                                html.Span("Before Fidelity:", style={"fontSize": "13px"}),
                                _fidelity_badge(before_fidelity),
                                html.Span("  After Fidelity:", style={"fontSize": "13px", "marginLeft": "14px"}),
                                _fidelity_badge(after_fidelity),
                            ],
                            style={"marginTop": "6px"},
                        ),
                    ],
                    style={"marginBottom": "12px"},
                ),
                html.Div(
                    [
                        html.H4("Session Evidence", style={"marginBottom": "8px"}),
                        dcc.Graph(id="reports-precooling-impact-session-evidence-fig", figure=evidence_fig),
                        _chips(reason_codes, "Reason Codes"),
                        _chips(quality_flags, "Quality Flags"),
                    ],
                    style={**CARD_STYLE, "marginTop": "10px"},
                ),
                html.Div(
                    [
                        html.H4("Before / After / Delta", style={"marginBottom": "8px"}),
                        _impact_cards(
                            {
                                "energy": {"before_kwh": record.get("energy_before_kwh"), "after_kwh": record.get("energy_after_kwh"), "delta_kwh": record.get("energy_delta_kwh")},
                                "peak": {"before_kw": record.get("peak_before_kw"), "after_kw": record.get("peak_after_kw"), "delta_kw": record.get("peak_delta_kw")},
                                "cost": {"before_idr": record.get("cost_before_idr"), "after_idr": record.get("cost_after_idr"), "delta_idr": record.get("cost_delta_idr")},
                                "co2": {"before_kg": record.get("co2_before_kg"), "after_kg": record.get("co2_after_kg"), "delta_kg": record.get("co2_delta_kg")},
                                "comfort": {"before_ratio": record.get("comfort_before_ratio"), "after_ratio": record.get("comfort_after_ratio"), "delta_ratio": record.get("comfort_delta_ratio")},
                            }
                        ),
                    ]
                ),
                html.Div(_quality_panel(quality, str(record.get("basis") or ""), str(record.get("notes") or "")), style={**CARD_STYLE, "marginTop": "10px"}),
                html.Div(
                    [
                        html.H4("Telemetry Preview", style={"marginBottom": "8px"}),
                        html.Div("Tidak ada telemetry preview.", style={"color": "#566573"}) if not telemetry else html.Pre(str(telemetry[:8]), style={"fontSize": "12px", "backgroundColor": "#f8f9fa", "padding": "10px", "borderRadius": "6px"}),
                    ],
                    style={**CARD_STYLE, "marginTop": "10px"},
                ),
            ]
        )
        return [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Session Detail", style={"fontWeight": "bold", "fontSize": "16px"}),
                                    html.Button(
                                        "Close",
                                        id={"type": "reports-precooling-impact-modal-close", "name": "close"},
                                        n_clicks=0,
                                        style={"backgroundColor": "#566573", "color": "white", "border": "none", "padding": "6px 10px", "borderRadius": "4px", "cursor": "pointer"},
                                    ),
                                ],
                                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
                            ),
                            html.Div(body, id="reports-precooling-impact-session-modal-body"),
                        ],
                        style={"backgroundColor": "white", "borderRadius": "8px", "padding": "14px", "maxWidth": "900px", "width": "92%", "maxHeight": "85vh", "overflowY": "auto"},
                    )
                ],
                id="reports-precooling-impact-session-modal",
                style={"display": "flex", "position": "fixed", "top": 0, "left": 0, "right": 0, "bottom": 0, "backgroundColor": "rgba(0,0,0,0.35)", "zIndex": 9999, "justifyContent": "center", "alignItems": "center"},
            )
        ]
    
    @app.callback(
        Output('reports-export-section', 'children'),
        [Input('reports-generate-btn', 'n_clicks')],
        [State('reports-format-dropdown', 'value'),
         State('reports-data-store', 'children')]
    )
    def export_report(n_clicks, format_type, data_str):
        """
        Handles report export functionality.
        """
        if n_clicks == 0 or not data_str:
            return ""
            
        try:
            import ast
            data = ast.literal_eval(data_str)
            if not isinstance(data, dict):
                return html.Div(
                    [
                        html.P("Data report tidak valid.", style={"color": "#e74c3c"}),
                        html.P("Silakan klik Generate Report lagi setelah backend siap.", style={"fontSize": "12px", "color": "#7f8c8d"}),
                    ]
                )
            daily_data = data.get("daily_data")
            if not isinstance(daily_data, list) or not daily_data:
                return html.Div(
                    [
                        html.P("Data report belum tersedia untuk diexport.", style={"color": "#e74c3c"}),
                        html.P("Pastikan Reports sudah live/ready, lalu klik Generate Report.", style={"fontSize": "12px", "color": "#7f8c8d"}),
                    ]
                )
            
            if format_type == 'csv':
                # Create CSV content
                csv_content = "Date,Consumption (kWh),Source\n"
                for item in daily_data:
                    if isinstance(item, dict):
                        csv_content += f"{item.get('date','')},{item.get('consumption','')},Mixed\n"
                    
                # Create download link
                csv_string = "data:text/csv;charset=utf-8," + quote(csv_content)
                
                return html.Div([
                    html.P("Report generated successfully!", style={'color': '#27ae60'}),
                    html.A("Download CSV", 
                           href=csv_string, 
                           download=f"energy_report_{data.get('period','period')}.csv",
                           style={'backgroundColor': '#27ae60', 'color': 'white', 'padding': '10px 20px', 
                                  'textDecoration': 'none', 'borderRadius': '5px', 'display': 'inline-block',
                                  'marginTop': '10px'})
                ])
                
            elif format_type == 'pdf':
                # For PDF, we'll create a simple text-based approach
                # In a real app, you'd use a proper PDF library like reportlab
                pdf_content = f"""
ENERGY REPORT - ECO-AIMS Dashboard
Period: {data['period']}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
- Total Consumption: {data['total_consumption']:,.0f} kWh
- Renewable Efficiency: {data['renewable_efficiency']:.1f}%
- CO2 Emission: {data['co2_emission']:.2f} ton
- Cost Savings: Rp {data['cost_savings']:,.0f}

This is a simplified PDF report. For full PDF functionality, 
integrate with a proper PDF generation library.
"""
                
                return html.Div([
                    html.P("PDF report template generated!", style={'color': '#27ae60'}),
                    html.P("Note: Full PDF functionality requires additional libraries like reportlab.", 
                          style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.Pre(pdf_content, style={'backgroundColor': '#f8f9fa', 'padding': '15px', 
                                                 'borderRadius': '5px', 'marginTop': '10px',
                                                 'fontSize': '12px', 'overflow': 'auto'})
                ])
                
        except Exception as e:
            return html.Div([
                html.P(f"Error generating report: {str(e)}", style={'color': '#e74c3c'}),
                html.P("Please try again or contact support.", style={'fontSize': '12px', 'color': '#7f8c8d'})
            ])
