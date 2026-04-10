import json
from typing import Any, Dict

from dash import html


def _normalize(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    if v is None:
        return {}
    return {"technical": v}


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=lambda o: f"<{type(o).__name__}>")


def render_contract_negotiation_error(negotiation_result: Any) -> html.Div:
    r = _normalize(negotiation_result)
    expected = r.get("expected") if isinstance(r.get("expected"), dict) else {}
    backend = r.get("backend") if isinstance(r.get("backend"), dict) else {}
    comp = r.get("compatibility") if isinstance(r.get("compatibility"), dict) else {}
    decision = str(r.get("decision") or "").strip() or "unknown"
    compatible = comp.get("compatible")

    badge_text = "COMPATIBLE" if compatible is True else ("INCOMPATIBLE" if compatible is False else "UNKNOWN")
    badge_cls = "badge badge-ok" if compatible is True else ("badge badge-danger" if compatible is False else "badge badge-warn")

    reason = str(comp.get("reason") or "").strip()
    severity = str(comp.get("severity") or "").strip()

    actions = [
        "Short-term: gunakan simulation data (jika diizinkan oleh policy) untuk menjaga dashboard tetap hidup.",
        "Medium-term: update frontend agar sesuai dengan versi kontrak backend.",
        "Long-term: aktifkan auto-sync kontrak (registry/manifest) agar drift terdeteksi sebelum request data.",
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.H3("Contract Compatibility Check"),
                    html.P("Pre-flight negotiation gagal atau tidak kompatibel. Sistem berjalan dalam degraded mode."),
                ],
                className="error-header",
            ),
            html.Div(
                [
                    html.H4("Version Comparison"),
                    html.Div(
                        html.Table(
                            [
                                html.Tr([html.Th("Side"), html.Th("Contract ID"), html.Th("Version"), html.Th("Status")]),
                                html.Tr(
                                    [
                                        html.Td("Frontend (expected)"),
                                        html.Td(str(expected.get("id") or "Unknown")),
                                        html.Td(str(expected.get("version") or "Unknown")),
                                        html.Td(html.Span(badge_text, className=badge_cls)),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Backend (reported)"),
                                        html.Td(str(backend.get("id") or "Unknown")),
                                        html.Td(str(backend.get("version") or "Unknown")),
                                        html.Td(html.Small(f"{reason} {severity}".strip())),
                                    ]
                                ),
                            ],
                            className="contract-table",
                        ),
                        className="contract-table-wrap",
                    ),
                ]
            ),
            html.Div([html.H5("Recommended Actions"), html.Ul([html.Li(x) for x in actions])]),
            html.Div(
                [
                    html.Div(
                        [
                            html.Button(
                                "Use Simulation Data",
                                id="use-simulation-data",
                                className="btn btn-secondary",
                                disabled=True,
                                title="Belum aktif: fallback simulation dikontrol oleh policy/env, bukan tombol UI.",
                            ),
                            html.Div(
                                "Belum aktif: fallback simulation dikontrol oleh policy/env, bukan tombol UI.",
                                style={"fontSize": "12px", "opacity": 0.85},
                            ),
                        ],
                        style={"display": "inline-block", "marginRight": "10px", "verticalAlign": "top", "maxWidth": "320px"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Check Backend Status",
                                id="check-backend-status",
                                className="btn btn-info",
                                disabled=True,
                                title="Belum aktif: gunakan /health, /api/startup-info, /api/contracts/index, atau make doctor-stack.",
                            ),
                            html.Div(
                                "Belum aktif: gunakan /health, /api/startup-info, /api/contracts/index, atau make doctor-stack.",
                                style={"fontSize": "12px", "opacity": 0.85},
                            ),
                        ],
                        style={"display": "inline-block", "verticalAlign": "top", "maxWidth": "360px"},
                    ),
                ],
                className="action-buttons",
            ),
            html.Details(
                [
                    html.Summary("Technical Details"),
                    html.Pre(_safe_json({"decision": decision, "attempt": r.get("attempt"), "raw": r}), className="technical-details"),
                ]
            ),
        ],
        className="contract-error-container",
    )
