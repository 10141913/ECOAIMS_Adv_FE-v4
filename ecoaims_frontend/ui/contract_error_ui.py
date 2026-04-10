import json
from typing import Any, Dict, List

from dash import html


def _as_list(v: Any) -> List[str]:
    if isinstance(v, str):
        parts = [p.strip() for p in v.split(",")]
        return [p for p in parts if p]
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for it in v:
        s = str(it).strip()
        if s:
            out.append(s)
    return out


def _normalize_error_details(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    if v is None:
        return {}
    return {"technical": v}


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=lambda o: f"<{type(o).__name__}>")


def _action_cfg(error_details: Dict[str, Any], action_key: str) -> Dict[str, Any]:
    actions = error_details.get("actions")
    if not isinstance(actions, dict):
        return {"enabled": False, "hint": "Fitur ini belum diaktifkan di build ini."}
    cfg = actions.get(action_key)
    if not isinstance(cfg, dict):
        return {"enabled": False, "hint": "Fitur ini belum diaktifkan di build ini."}
    enabled = cfg.get("enabled") is True
    hint = str(cfg.get("hint") or "").strip() if isinstance(cfg.get("hint"), str) else ""
    if not hint:
        hint = "Fitur ini belum diaktifkan di build ini." if not enabled else ""
    return {"enabled": enabled, "hint": hint}


def render_contract_mismatch_error(error_details: Any) -> html.Div:
    error_details = _normalize_error_details(error_details)
    component_label = str(error_details.get("component_label") or "Energy Data Contract")
    expected = str(error_details.get("expected_version", "Unknown"))
    actual = str(error_details.get("actual_version", "Unknown"))
    reason = ""
    compat = error_details.get("compatibility")
    if isinstance(compat, dict):
        reason = str(compat.get("reason") or "").strip()
    missing_fields = _as_list(error_details.get("missing_fields"))
    technical = error_details.get("technical")
    technical_dict = technical if isinstance(technical, dict) else {"detail": technical}

    body = [
        html.Div(
            [
                html.H3("Contract Compatibility Issue"),
                html.P("API contract mismatch detected. System is running in degraded mode."),
            ],
            className="error-header",
        ),
        html.Div(
            [
                html.H4("Contract Version Analysis"),
                html.Div(
                    html.Table(
                        [
                            html.Tr([html.Th("Component"), html.Th("Expected"), html.Th("Actual"), html.Th("Status")]),
                            html.Tr(
                                [
                                    html.Td(component_label),
                                    html.Td(expected),
                                    html.Td(actual),
                                    html.Td(
                                        [
                                            html.Span("MISMATCH", className="badge badge-danger"),
                                            html.Small(f" ({reason})") if reason else html.Span(),
                                        ]
                                    ),
                                ]
                            ),
                        ],
                        className="contract-table",
                    ),
                    className="contract-table-wrap",
                ),
            ]
        ),
    ]

    if missing_fields:
        body.append(html.Div([html.H5("Missing Required Fields"), html.Ul([html.Li(field) for field in missing_fields])]))

    retry_cfg = _action_cfg(error_details, "retry_contract_negotiation")
    sim_cfg = _action_cfg(error_details, "switch_to_simulation")
    view_cfg = _action_cfg(error_details, "view_contract_details")
    ops_hint = str(error_details.get("operator_hint") or "").strip()
    if not ops_hint:
        ops_hint = "Langkah yang bisa dilakukan sekarang: jalankan make doctor-stack, cek /api/startup-info, lalu cocokkan contract_manifest_id/hash dan endpoint /api/energy-data."

    body.extend(
        [
            html.Div(
                [
                    html.H5("Operator Actions"),
                    html.P(ops_hint),
                ]
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Button(
                                "Retry with Negotiation",
                                id="retry-contract-negotiation",
                                className="btn btn-primary",
                                disabled=not bool(retry_cfg.get("enabled")),
                                title=str(retry_cfg.get("hint") or ""),
                            ),
                            html.Div(str(retry_cfg.get("hint") or ""), style={"fontSize": "12px", "opacity": 0.85}),
                        ],
                        style={"display": "inline-block", "marginRight": "10px", "verticalAlign": "top", "maxWidth": "260px"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Switch to Simulation Mode",
                                id="switch-to-simulation",
                                className="btn btn-secondary",
                                disabled=not bool(sim_cfg.get("enabled")),
                                title=str(sim_cfg.get("hint") or ""),
                            ),
                            html.Div(str(sim_cfg.get("hint") or ""), style={"fontSize": "12px", "opacity": 0.85}),
                        ],
                        style={"display": "inline-block", "marginRight": "10px", "verticalAlign": "top", "maxWidth": "260px"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "View Contract Details",
                                id="view-contract-details",
                                className="btn btn-info",
                                disabled=not bool(view_cfg.get("enabled")),
                                title=str(view_cfg.get("hint") or ""),
                            ),
                            html.Div(str(view_cfg.get("hint") or ""), style={"fontSize": "12px", "opacity": 0.85}),
                        ],
                        style={"display": "inline-block", "verticalAlign": "top", "maxWidth": "260px"},
                    ),
                ],
                className="action-buttons",
            ),
            html.Details(
                [
                    html.Summary("Technical Details"),
                    html.Pre(_safe_json(technical_dict), className="technical-details"),
                ]
            ),
        ]
    )

    return html.Div(body, className="contract-error-container")
