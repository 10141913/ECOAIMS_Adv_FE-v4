from dash import dcc, html
from dash import dash_table

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_schedule_and_control() -> html.Div:
    left = html.Div(
        [
            html.H3("Schedule & Control", style=SECTION_TITLE_STYLE),
            html.Div(
                [
                    html.Div("Precooling Timeline (24h)", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    dcc.Graph(id="precooling-schedule-timeline", config={"displayModeBar": False}),
                ]
            ),
            html.Div(
                [
                    html.Div("Schedule Table", style={"color": PREC_COLORS["muted"], "fontSize": "12px", "marginTop": "6px"}),
                    dash_table.DataTable(
                        id="precooling-schedule-table",
                        columns=[],
                        data=[],
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "fontFamily": "Arial",
                            "fontSize": "12px",
                            "padding": "8px",
                            "whiteSpace": "nowrap",
                        },
                        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
                        style_data_conditional=[],
                        page_size=8,
                    ),
                ],
                style={"marginTop": "10px"},
            ),
        ],
        style={**CARD_STYLE_TIGHT, "flex": "2", "minWidth": "520px"},
    )

    right = html.Div(
        [
            html.H4("Control Panel", style={"margin": "0 0 10px 0", "color": PREC_COLORS["text"]}),
            html.Div(id="precooling-control-summary"),
            html.Div(
                [
                    html.Div("Manual Override", style={"fontSize": "12px", "color": PREC_COLORS["muted"], "marginTop": "12px"}),
                    html.Div(
                        id="precooling-manual-override",
                        children=[
                            html.Div(
                                [
                                    html.Div(id="precooling-override-state-badge"),
                                    html.Div(id="precooling-override-state-details", style={"marginTop": "8px", "fontSize": "12px", "color": PREC_COLORS["muted"]}),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Div("Temperature Setpoint (°C)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Input(id="precooling-override-temp", type="number", value=25, step=0.1, style={"width": "100%"}),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Div(
                                [
                                    html.Div("RH Setpoint (%)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Input(id="precooling-override-rh", type="number", value=60, step=0.5, style={"width": "100%"}),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Duration (min)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Input(id="precooling-override-duration", type="number", value=60, step=1, min=1, style={"width": "100%"}),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Div(
                                [
                                    html.Div("HVAC Mode", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Dropdown(
                                        id="precooling-override-hvac-mode",
                                        options=[{"label": "Cooling", "value": "cooling"}, {"label": "Auto", "value": "auto"}],
                                        value="cooling",
                                        clearable=False,
                                    ),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Energy Source", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Dropdown(
                                        id="precooling-override-energy-source",
                                        options=[{"label": "Grid", "value": "grid"}, {"label": "PV", "value": "pv"}, {"label": "Mixed", "value": "mixed"}],
                                        value="grid",
                                        clearable=False,
                                    ),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Reason", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Input(id="precooling-override-reason", type="text", value="", placeholder="Optional reason", style={"width": "100%"}),
                                ],
                                style={"marginTop": "10px"},
                            ),
                            html.Button(
                                "Request Manual Override",
                                id="precooling-request-override-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": "#1f618d",
                                    "color": "white",
                                    "border": "none",
                                    "padding": "10px 12px",
                                    "borderRadius": "6px",
                                    "cursor": "pointer",
                                    "fontWeight": "bold",
                                    "width": "100%",
                                    "marginTop": "12px",
                                },
                            ),
                            html.Button(
                                "Approve Manual Override",
                                id="precooling-approve-override-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": PREC_COLORS["renewable"],
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
                                "Cancel Manual Override",
                                id="precooling-cancel-override-btn",
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
                                    "marginTop": "8px",
                                },
                            ),
                            html.Div(id="precooling-override-action-feedback", style={"marginTop": "10px", "fontSize": "12px", "color": PREC_COLORS["muted"]}),
                        ],
                        style={
                            "padding": "10px",
                            "borderRadius": "8px",
                            "border": f"1px solid {PREC_COLORS['border']}",
                            "backgroundColor": "#f8f9fa",
                            "color": PREC_COLORS["text"],
                        },
                    ),
                ]
            ),
            html.Div(
                [
                    html.Button(
                        "Activate",
                        id="precooling-activate-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["renewable"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 12px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "width": "100%",
                            "marginTop": "12px",
                        },
                    ),
                    html.Button(
                        "Pause",
                        id="precooling-pause-btn",
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
                    html.Button(
                        "Cancel Today",
                        id="precooling-cancel-btn",
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
                            "marginTop": "8px",
                        },
                    ),
                    html.Button(
                        "Use Rule-Based Strategy",
                        id="precooling-rulebased-btn",
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
                        "Recompute Schedule",
                        id="precooling-recompute-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["ai"],
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
                ]
            ),
        ],
        style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "320px"},
    )

    return html.Div([left, right], style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})
