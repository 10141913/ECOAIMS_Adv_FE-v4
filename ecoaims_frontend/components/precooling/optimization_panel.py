from dash import dcc, html
from dash import dash_table

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, SECTION_TITLE_STYLE, PREC_COLORS


def create_optimization_insight_panel() -> html.Div:
    constraint_table = dash_table.DataTable(
        id="precooling-constraint-matrix",
        columns=[],
        data=[],
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
        page_size=8,
    )

    ranking_table = dash_table.DataTable(
        id="precooling-candidate-ranking",
        columns=[],
        data=[],
        row_selectable="single",
        selected_rows=[],
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
        page_size=8,
    )

    return html.Div(
        [
            html.Div(
                [
                    html.H3("Optimization Insight", style=SECTION_TITLE_STYLE),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Objective Breakdown", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    dcc.Graph(id="precooling-objective-breakdown", config={"displayModeBar": False}, style={"height": "260px"}),
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "320px"},
                            ),
                            html.Div(
                                [
                                    html.Div("Constraint Check Matrix", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    constraint_table,
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "1", "minWidth": "420px"},
                            ),
                        ],
                        style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div("Candidate Ranking", style={"color": PREC_COLORS["muted"], "fontSize": "12px"}),
                                    ranking_table,
                                ],
                                style={**CARD_STYLE_TIGHT, "flex": "2", "minWidth": "520px"},
                            ),
                            html.Div(
                                [
                                    html.H4("Selected Candidate", style={"margin": "0 0 10px 0", "color": PREC_COLORS["text"]}),
                                    html.Div(id="precooling-selected-candidate"),
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
