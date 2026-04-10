from dash import html
from dash import dash_table

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_alerts_safety_audit_panel() -> html.Div:
    alerts_table = dash_table.DataTable(
        id="precooling-alerts-table",
        columns=[],
        data=[],
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
        page_size=8,
    )

    audit_table = dash_table.DataTable(
        id="precooling-audit-table",
        columns=[],
        data=[],
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
        page_size=8,
    )

    return html.Div(
        [
            html.Div(
                [
                    html.H3("Alerts, Safety & Audit Trail", style=SECTION_TITLE_STYLE),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Alerts Center", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    alerts_table,
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "2", "minWidth": "560px"},
                            ),
                            html.Div(
                                [
                                    html.H4("Safety & Override", style={"margin": "0 0 10px 0", "color": PREC_COLORS["text"]}),
                                    html.Button(
                                        "Force Fallback",
                                        id="precooling-safety-fallback-btn",
                                        n_clicks=0,
                                        style={
                                            "backgroundColor": PREC_COLORS["alert"],
                                            "color": "white",
                                            "border": "none",
                                            "padding": "10px 12px",
                                            "borderRadius": "6px",
                                            "cursor": "pointer",
                                            "fontWeight": "bold",
                                            "width": "100%",
                                        },
                                    ),
                                    html.Button(
                                        "Stop Precooling",
                                        id="precooling-stop-btn",
                                        n_clicks=0,
                                        style={
                                            "backgroundColor": "#34495e",
                                            "color": "white",
                                            "border": "none",
                                            "padding": "10px 12px",
                                            "borderRadius": "6px",
                                            "cursor": "pointer",
                                            "fontWeight": "bold",
                                            "width": "100%",
                                            "marginTop": "8px",
                                        },
                                    ),
                                    html.Button(
                                        "Switch to Advisory",
                                        id="precooling-switch-advisory-btn",
                                        n_clicks=0,
                                        style={
                                            "backgroundColor": PREC_COLORS["battery"],
                                            "color": "white",
                                            "border": "none",
                                            "padding": "10px 12px",
                                            "borderRadius": "6px",
                                            "cursor": "pointer",
                                            "fontWeight": "bold",
                                            "width": "100%",
                                            "marginTop": "8px",
                                        },
                                    ),
                                    html.Div(id="precooling-safety-feedback", style={"marginTop": "10px", "fontSize": "12px", "color": PREC_COLORS["muted"]}),
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "320px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                    ),
                    html.Div(
                        [
                            html.Div("Audit Trail", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                            html.Div(id="precooling-selector-audit", style={"marginTop": "10px"}),
                            audit_table,
                        ],
                        style={**CARD_STYLE_TIGHT, "marginTop": "10px"},
                    ),
                ],
                style={**CARD_STYLE_TIGHT},
            )
        ]
    )
