from dash import html

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, PREC_COLORS, SECTION_TITLE_STYLE


def create_precooling_overview() -> html.Div:
    hero = html.Div(
        [
            html.H3("Precooling Status Overview", style=SECTION_TITLE_STYLE),
            html.Div(id="precooling-hero-card"),
            html.Div(id="precooling-quick-kpi-row", style={"display": "flex", "gap": "10px", "flexWrap": "wrap"}),
            html.Div(
                [
                    html.H4("Explainability", style={"margin": "16px 0 10px 0", "color": PREC_COLORS["text"]}),
                    html.Div(
                        id="precooling-explainability-box",
                        style={
                            "padding": "12px",
                            "borderRadius": "8px",
                            "border": f"1px solid {PREC_COLORS['border']}",
                            "backgroundColor": "#f8f9fa",
                            "color": PREC_COLORS["text"],
                        },
                    ),
                ],
                style={"marginTop": "8px"},
            ),
        ],
        style={**CARD_STYLE_TIGHT},
    )

    return hero

