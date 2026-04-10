from dash import dcc, html

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, PREC_COLORS


def create_precooling_header() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H2(
                                "Precooling / LAEOPF",
                                style={"margin": "0", "color": PREC_COLORS["text"]},
                            ),
                            html.Div(
                                "Latent-Aware Exergy-Optimized Precooling Engine",
                                style={"color": PREC_COLORS["muted"], "marginTop": "4px"},
                            ),
                            html.Div(
                                "Scope di sini adalah scope operasi (monitor/simulate/apply) untuk tab Precooling.",
                                style={"color": PREC_COLORS["muted"], "marginTop": "6px", "fontSize": "12px"},
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Div("Scope (Lantai)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                                    dcc.RadioItems(
                                                        id="precooling-floor",
                                                        options=[
                                                            {"label": "Lantai 1", "value": "1"},
                                                            {"label": "Lantai 2", "value": "2"},
                                                            {"label": "Lantai 3", "value": "3"},
                                                        ],
                                                        value="1",
                                                        inline=True,
                                                        style={"fontSize": "12px", "color": PREC_COLORS["text"]},
                                                        inputStyle={"marginRight": "6px"},
                                                        labelStyle={"marginRight": "10px"},
                                                    ),
                                                ]
                                            ),
                                            html.Div(
                                                [
                                                    html.Div("Zone", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                                    dcc.Checklist(
                                                        id="precooling-zone",
                                                        options=[
                                                            {"label": "A", "value": "a"},
                                                            {"label": "B", "value": "b"},
                                                            {"label": "C", "value": "c"},
                                                        ],
                                                        value=["a"],
                                                        inline=True,
                                                        style={"fontSize": "12px", "color": PREC_COLORS["text"]},
                                                        inputStyle={"marginRight": "6px"},
                                                        labelStyle={"marginRight": "10px"},
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                "Clear Zones",
                                                                id="precooling-clear-zones-btn",
                                                                n_clicks=0,
                                                                style={
                                                                    "backgroundColor": "#bdc3c7",
                                                                    "color": "white",
                                                                    "border": "none",
                                                                    "padding": "6px 10px",
                                                                    "borderRadius": "6px",
                                                                    "cursor": "pointer",
                                                                    "fontWeight": "bold",
                                                                    "marginTop": "6px",
                                                                },
                                                            ),
                                                            html.Div(id="precooling-zone-selection-error", style={"marginTop": "6px", "fontSize": "12px", "color": PREC_COLORS["alert"]}),
                                                        ]
                                                    ),
                                                ]
                                            ),
                                        ],
                                        style={"display": "flex", "gap": "10px", "alignItems": "flex-end"},
                                    ),
                                    html.Div(id="precooling-zone-discovery-banner", style={"marginTop": "6px"}),
                                ],
                                style={"marginRight": "12px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Mode", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    dcc.Dropdown(
                                        id="precooling-mode-dropdown",
                                        options=[
                                            {"label": "Monitoring", "value": "monitoring"},
                                            {"label": "Advisory", "value": "advisory"},
                                            {"label": "Auto", "value": "auto"},
                                            {"label": "Fallback", "value": "fallback"},
                                        ],
                                        value="monitoring",
                                        clearable=False,
                                        persistence=True,
                                        persistence_type='session',
                                        style={"width": "160px"},
                                    ),
                                ],
                                style={"marginRight": "12px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Data Health", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    html.Div(
                                        id="precooling-data-health-badge",
                                        style={
                                            "display": "inline-block",
                                            "padding": "4px 10px",
                                            "borderRadius": "999px",
                                            "backgroundColor": "#bdc3c7",
                                            "color": "white",
                                            "fontWeight": "bold",
                                            "fontSize": "12px",
                                            "minWidth": "100px",
                                            "textAlign": "center",
                                        },
                                        children="Unknown",
                                    ),
                                ],
                                style={"marginRight": "12px", "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div("Last Update", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                    html.Div(
                                        id="precooling-last-update",
                                        style={"fontSize": "12px", "color": PREC_COLORS["text"], "fontWeight": "bold"},
                                        children="-",
                                    ),
                                ],
                                style={"marginRight": "16px"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "flex-end"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "16px"},
            ),
            html.Div(
                [
                    html.Button(
                        "Run Simulation",
                        id="precooling-run-sim-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["ai"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Button(
                        "Apply Recommendation",
                        id="precooling-apply-btn",
                        n_clicks=0,
                        disabled=True,
                        title="Pilih 1 recommendation pada tabel Candidate Ranking terlebih dahulu.",
                        style={
                            "backgroundColor": PREC_COLORS["renewable"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                            "opacity": "0.6",
                        },
                    ),
                    html.Button(
                        "Force Fallback",
                        id="precooling-force-fallback-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["alert"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Button(
                        "Export Report",
                        id="precooling-export-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#34495e",
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Div(
                        id="precooling-action-feedback",
                        style={"marginLeft": "14px", "fontSize": "12px", "color": PREC_COLORS["muted"]},
                    ),
                ],
                style={"marginTop": "14px", "display": "flex", "alignItems": "center", "flexWrap": "wrap"},
            ),
            html.Details(
                [
                    html.Summary("Debug: Copy simulate request", style={"cursor": "pointer"}),
                    dcc.Textarea(
                        id="precooling-simulate-request-text",
                        value="{}",
                        style={"width": "100%", "height": "160px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"},
                    ),
                    dcc.Clipboard(target_id="precooling-simulate-request-text", title="Copy simulate request"),
                    html.Button(
                        "Export Golden Sample (JSON)",
                        id="precooling-golden-export-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#1f618d",
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginTop": "10px",
                        },
                    ),
                ],
                id="precooling-simulate-request-details",
                open=False,
                style={"marginTop": "10px"},
            ),
            dcc.ConfirmDialog(
                id="precooling-fallback-confirm",
                message="Anda yakin ingin Force Fallback? Sistem akan berpindah ke mode aman.",
            ),
            dcc.Download(id="precooling-download"),
            dcc.Download(id="precooling-golden-download"),
        ],
        style={**CARD_STYLE_TIGHT, "position": "sticky", "top": "0", "zIndex": "10"},
    )
