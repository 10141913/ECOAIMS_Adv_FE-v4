from dash import dcc, html

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_kpi_evaluation_panel() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("KPI, Evaluation & Impact", style=SECTION_TITLE_STYLE),
                    html.Div(id="precooling-kpi-master-cards", style={"display": "flex", "gap": "10px", "flexWrap": "wrap"}),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Before vs After Analytics", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    dcc.Graph(id="precooling-before-after-load", config={"displayModeBar": False}),
                                    dcc.Graph(id="precooling-before-after-temp", config={"displayModeBar": False}),
                                    dcc.Graph(id="precooling-before-after-rh", config={"displayModeBar": False}),
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "2", "minWidth": "560px"},
                            ),
                            html.Div(
                                [
                                    html.H4("Uncertainty & Data Confidence", style={"margin": "0 0 10px 0", "color": PREC_COLORS["text"]}),
                                    html.Div(id="precooling-uncertainty-panel"),
                                    html.Div(
                                        [
                                            html.Div("Model Status", style={"fontSize": "12px", "color": PREC_COLORS["muted"], "marginTop": "12px"}),
                                            html.Div(id="precooling-model-status"),
                                        ]
                                    ),
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "320px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginTop": "10px"},
                    ),
                ],
                style={**CARD_STYLE_TIGHT},
            )
        ]
    )

