from dash import dcc, html

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_thermal_latent_panel() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H3("Thermal & Latent State", style=SECTION_TITLE_STYLE),
                    html.Div(
                        [
                            html.Div(id="precooling-thermal-state", style={"flex": "1", "minWidth": "320px"}),
                            html.Div(id="precooling-latent-state", style={"flex": "1", "minWidth": "320px"}),
                            html.Div(
                                [
                                    html.Div("Psychrometric Mini View", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    dcc.Graph(id="precooling-psychrometric-mini", config={"displayModeBar": False}, style={"height": "220px"}),
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "320px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                    ),
                ],
                style={**CARD_STYLE_TIGHT},
            ),
            html.Div(
                [
                    html.H4("Exergy Analysis", style={"margin": "0 0 10px 0", "color": PREC_COLORS["text"]}),
                    html.Div(id="precooling-exergy-panel"),
                ],
                style={**CARD_STYLE_TIGHT, "marginTop": "10px"},
            ),
        ]
    )

