from dash import dcc, html
from dash import dash_table

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_scenario_lab() -> html.Div:
    cards = html.Div(id="precooling-scenario-cards", style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})

    comparison_table = dash_table.DataTable(
        id="precooling-scenario-compare-table",
        columns=[],
        data=[],
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
        page_size=6,
    )

    builder = html.Div(
        [
            html.H4("Scenario Builder", style={"margin": "0 0 12px 0", "color": PREC_COLORS["text"]}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Earliest Start", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            dcc.Input(id="precooling-earliest-start", value="05:00", type="text", persistence=True, persistence_type='session', style={"width": "100%"}),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Div(
                        [
                            html.Div("Latest Start", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            dcc.Input(id="precooling-latest-start", value="10:00", type="text", persistence=True, persistence_type='session', style={"width": "100%"}),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Div(
                        [
                            html.Div("Duration Options (min)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            dcc.Input(id="precooling-duration-options", value="30,60,90", type="text", style={"width": "100%"}),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Target Temp Range (°C)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            dcc.Input(id="precooling-target-t-range", value="22,25", type="text", persistence=True, persistence_type='session', style={"width": "100%"}),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Div(
                        [
                            html.Div("Target RH Range (%)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            dcc.Input(id="precooling-target-rh-range", value="50,60", type="text", persistence=True, persistence_type='session', style={"width": "100%"}),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Weights", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div("Cost", style={"fontSize": "10px", "color": PREC_COLORS["muted"]}),
                                            dcc.Slider(id="precooling-w-cost", min=0, max=1, step=0.05, value=0.35, persistence=True, persistence_type='session'),
                                        ],
                                        style={"flex": "1"},
                                    ),
                                    html.Div(
                                        [
                                            html.Div("CO2", style={"fontSize": "10px", "color": PREC_COLORS["muted"]}),
                                            dcc.Slider(id="precooling-w-co2", min=0, max=1, step=0.05, value=0.25, persistence=True, persistence_type='session'),
                                        ],
                                        style={"flex": "1"},
                                    ),
                                    html.Div(
                                        [
                                            html.Div("Comfort", style={"fontSize": "10px", "color": PREC_COLORS["muted"]}),
                                            dcc.Slider(id="precooling-w-comfort", min=0, max=1, step=0.05, value=0.25, persistence=True, persistence_type='session'),
                                        ],
                                        style={"flex": "1"},
                                    ),
                                    html.Div(
                                        [
                                            html.Div("Battery Health", style={"fontSize": "10px", "color": PREC_COLORS["muted"]}),
                                            dcc.Slider(id="precooling-w-battery", min=0, max=1, step=0.05, value=0.15, persistence=True, persistence_type='session'),
                                        ],
                                        style={"flex": "1"},
                                    ),
                                ],
                                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                            ),
                        ]
                    ),
                ],
                style={"marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div("Optimizer Backend", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                    dcc.Dropdown(
                            id="precooling-optimizer-backend",
                            options=[
                                {"label": "Grid (default)", "value": "grid"},
                                {"label": "MPC", "value": "mpc"},
                                {"label": "CEM", "value": "cem"},
                            ],
                            value="grid",
                            clearable=False,
                            persistence=True,
                            persistence_type='session',
                            style={"marginTop": "6px"},
                        ),
                ],
                style={"marginTop": "10px"},
            ),
            html.Div(
                [
                    html.Div("Selector (Safe Bandit)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                    html.Div(
                        [
                            dcc.Checklist(
                                id="precooling-selector-enable",
                                options=[{"label": "Enable Selector (Safe Bandit)", "value": "on"}],
                                value=[],
                                inline=True,
                                persistence=True,
                                persistence_type="session",
                                inputStyle={"marginRight": "6px"},
                                labelStyle={"marginRight": "12px"},
                                style={"fontSize": "12px", "color": PREC_COLORS["text"], "marginTop": "6px"},
                            )
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("selector_backend", style={"fontSize": "11px", "color": PREC_COLORS["muted"], "marginBottom": "4px"}),
                                    dcc.Dropdown(
                                        id="precooling-selector-backend",
                                        options=[
                                            {"label": "grid (default)", "value": "grid"},
                                            {"label": "milp", "value": "milp"},
                                            {"label": "bandit", "value": "bandit"},
                                        ],
                                        value="grid",
                                        clearable=False,
                                        persistence=True,
                                        persistence_type="session",
                                    ),
                                ],
                                style={"minWidth": "220px"},
                            ),
                            html.Div(
                                [
                                    html.Div("epsilon (advanced)", style={"fontSize": "11px", "color": PREC_COLORS["muted"], "marginBottom": "4px"}),
                                    dcc.Input(
                                        id="precooling-selector-epsilon",
                                        type="number",
                                        value=0.12,
                                        step=0.01,
                                        style={"width": "160px"},
                                    ),
                                ],
                                style={"minWidth": "180px"},
                            ),
                            html.Div(
                                [
                                    html.Div("min_candidates (advanced)", style={"fontSize": "11px", "color": PREC_COLORS["muted"], "marginBottom": "4px"}),
                                    dcc.Input(
                                        id="precooling-selector-min-candidates",
                                        type="number",
                                        value=3,
                                        step=1,
                                        style={"width": "160px"},
                                    ),
                                ],
                                style={"minWidth": "180px"},
                            ),
                            html.Div(
                                [
                                    html.Div("return_candidates", style={"fontSize": "11px", "color": PREC_COLORS["muted"], "marginBottom": "4px"}),
                                    dcc.Checklist(
                                        id="precooling-selector-return-candidates",
                                        options=[{"label": "True", "value": "on"}],
                                        value=[],
                                        inline=True,
                                        persistence=True,
                                        persistence_type="session",
                                        inputStyle={"marginRight": "6px"},
                                        style={"fontSize": "12px", "color": PREC_COLORS["text"]},
                                    ),
                                ],
                                style={"minWidth": "180px", "marginTop": "0"},
                            ),
                            html.Button(
                                "Preview Selector",
                                id="precooling-selector-preview-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": "#34495e",
                                    "color": "white",
                                    "border": "none",
                                    "padding": "10px 12px",
                                    "borderRadius": "6px",
                                    "cursor": "pointer",
                                    "fontWeight": "bold",
                                    "height": "40px",
                                    "marginTop": "18px",
                                },
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "alignItems": "flex-start", "marginTop": "10px"},
                    ),
                    html.Div(id="precooling-selector-preview-output", style={"marginTop": "10px"}),
                    html.Details(
                        [
                            html.Summary("Raw selector preview (copy)", style={"cursor": "pointer", "marginTop": "8px"}),
                            dcc.Textarea(
                                id="precooling-selector-preview-raw",
                                value="{}",
                                style={"width": "100%", "height": "160px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"},
                            ),
                            dcc.Clipboard(target_id="precooling-selector-preview-raw", title="Copy selector preview"),
                        ],
                        open=False,
                        style={"marginTop": "6px"},
                    ),
                ],
                style={"marginTop": "12px"},
            ),
            html.Div(
                [
                    html.Button(
                        "Generate Candidates",
                        id="precooling-generate-candidates-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["ai"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 12px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginRight": "10px",
                        },
                    ),
                    html.Button(
                        "Run Comparison",
                        id="precooling-run-compare-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["cooling"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 12px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginRight": "10px",
                        },
                    ),
                    html.Button(
                        "Save Scenario",
                        id="precooling-save-scenario-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["renewable"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 12px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginRight": "10px",
                        },
                    ),
                    html.Button(
                        "Reset",
                        id="precooling-reset-scenario-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#bdc3c7",
                            "color": "white",
                            "border": "none",
                            "padding": "10px 12px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Div(id="precooling-scenario-feedback", style={"marginTop": "10px", "color": PREC_COLORS["muted"], "fontSize": "12px"}),
                ],
                style={"marginTop": "14px"},
            ),
        ],
        style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "360px"},
    )

    charts = html.Div(
        [
            html.Div(
                [
                    html.Div("Peak Comparison", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    dcc.Graph(id="precooling-peak-compare-chart", config={"displayModeBar": False}),
                ],
                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "360px"},
            ),
            html.Div(
                [
                    html.Div("Load Profile Comparison", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    dcc.Graph(id="precooling-load-profile-chart", config={"displayModeBar": False}),
                ],
                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "360px"},
            ),
            html.Div(
                [
                    html.Div("Cost vs CO2 Scatter", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    dcc.Graph(id="precooling-cost-co2-scatter", config={"displayModeBar": False}),
                ],
                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "360px"},
            ),
            html.Div(
                [
                    html.Div("Comfort Compliance", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                    dcc.Graph(id="precooling-comfort-chart", config={"displayModeBar": False}),
                ],
                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "360px"},
            ),
        ],
        style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
    )

    return html.Div(
        [
            html.Div(
                [
                    html.H3("Scenario Comparison Lab", style=SECTION_TITLE_STYLE),
                    cards,
                    html.Div(
                        [
                            html.Div("Scenario Comparison Table", style={"color": PREC_COLORS["muted"], "fontSize": "12px", "marginTop": "10px"}),
                            comparison_table,
                        ],
                        style={"marginTop": "10px"},
                    ),
                ],
                style={**CARD_STYLE_TIGHT},
            ),
            html.Div([builder, charts], style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginTop": "10px"}),
        ]
    )
