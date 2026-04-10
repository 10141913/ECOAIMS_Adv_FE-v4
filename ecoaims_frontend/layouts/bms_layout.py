from dash import html, dcc
from dash import dash_table
import plotly.graph_objects as go
from ecoaims_frontend.config import CARD_STYLE

def _initial_bms_figures():
    # Placeholder figures so the tab doesn't look empty
    soc_fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=0,
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [None, 100]},
                "bar": {"color": "#e74c3c"},
                "steps": [
                    {"range": [0, 20], "color": "#e74c3c"},
                    {"range": [20, 80], "color": "#2ecc71"},
                    {"range": [80, 100], "color": "#e74c3c"},
                ],
            },
        )
    )
    soc_fig.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=20))

    graph_fig = go.Figure()
    graph_fig.add_trace(
        go.Scatter(
            x=["0"],
            y=[0],
            name="SOC (%)",
            mode="lines+markers",
            line=dict(color="#2ecc71", width=3),
        )
    )
    graph_fig.add_trace(
        go.Scatter(
            x=["0"],
            y=[0],
            name="Voltage (V)",
            mode="lines+markers",
            line=dict(color="#3498db", width=2),
            yaxis="y2",
        )
    )
    graph_fig.add_trace(
        go.Scatter(
            x=["0"],
            y=[0],
            name="Temp (°C)",
            mode="lines+markers",
            line=dict(color="#e74c3c", width=2, dash="dot"),
            yaxis="y2",
        )
    )
    graph_fig.update_layout(
        title="Monitoring Real-time (SOC, Voltage, Temp) — initial",
        xaxis_title="Waktu",
        yaxis=dict(title="SOC (%)", range=[0, 100]),
        yaxis2=dict(title="Voltage / Temp", overlaying="y", side="right"),
        legend=dict(x=0, y=1.1, orientation="h"),
        margin=dict(l=50, r=50, t=50, b=50),
        height=350,
        template="plotly_white",
    )
    return soc_fig, graph_fig

def create_bms_layout() -> html.Div:
    """
    Creates the layout for the Battery Management System (BMS) Tab.
    """
    initial_soc_fig, initial_live_fig = _initial_bms_figures()
    return html.Div([
        # Header
        html.H2("Battery Management System (BMS)", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '20px'}),

        # --- Top Row: Key Metrics ---
        html.Div([
            # SOC Gauge
            html.Div([
                html.H4("State of Charge (SOC)", style={'textAlign': 'center', 'margin': '0 0 10px 0'}),
                dcc.Graph(id='bms-soc-gauge', figure=initial_soc_fig, style={'height': '200px'})
            ], style={**CARD_STYLE, 'width': '22%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # Voltage & Current Cards
            html.Div([
                html.H4("Parameter Listrik", style={'textAlign': 'center', 'margin': '0 0 15px 0'}),
                
                html.Div([
                    html.P("Tegangan (Voltage)", style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.H3(id='bms-voltage-text', children="0.0 V", style={'margin': '0', 'color': '#3498db'})
                ], style={'textAlign': 'center', 'marginBottom': '15px'}),
                
                html.Div([
                    html.P("Arus (Current)", style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.H3(id='bms-current-text', children="0.0 A", style={'margin': '0', 'color': '#e67e22'})
                ], style={'textAlign': 'center'})
                
            ], style={**CARD_STYLE, 'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # Temperature & Health
            html.Div([
                html.H4("Status & Kesehatan", style={'textAlign': 'center', 'margin': '0 0 15px 0'}),
                
                html.Div([
                    html.P("Suhu Baterai", style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.H3(id='bms-temp-text', children="0.0 °C", style={'margin': '0', 'color': '#e74c3c'})
                ], style={'textAlign': 'center', 'marginBottom': '15px'}),
                
                html.Div([
                    html.P("Status Kesehatan", style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.H3(id='bms-health-text', children="Normal", style={'margin': '0', 'color': '#27ae60'})
                ], style={'textAlign': 'center'})
                
            ], style={**CARD_STYLE, 'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # Controls
            html.Div([
                html.H4("Kontrol Manual", style={'textAlign': 'center', 'margin': '0 0 15px 0'}),
                
                html.Button("Start Charging", id='btn-start-charge', n_clicks=0, 
                            style={'width': '100%', 'padding': '10px', 'backgroundColor': '#27ae60', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'marginBottom': '10px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
                
                html.Button("Start Discharging", id='btn-start-discharge', n_clicks=0,
                            style={'width': '100%', 'padding': '10px', 'backgroundColor': '#e67e22', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'marginBottom': '10px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
                
                html.Button("Stop System", id='btn-stop-system', n_clicks=0,
                            style={'width': '100%', 'padding': '10px', 'backgroundColor': '#c0392b', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold'}),
                
                html.Div(id='bms-control-feedback', style={'marginTop': '10px', 'fontSize': '12px', 'textAlign': 'center', 'color': '#7f8c8d'})

            ], style={**CARD_STYLE, 'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top'}),

        ], style={'display': 'flex', 'justifyContent': 'center', 'marginBottom': '20px'}),

        # --- Bottom Row: Graphs ---
        html.Div([
            html.Div([
                dcc.Graph(id='bms-live-graph', figure=initial_live_fig, style={'height': '350px'})
            ], style={**CARD_STYLE, 'width': '96%'}),
        ], style={'display': 'flex', 'justifyContent': 'center'}),

        html.Div(
            [
                html.H3("Hasil Optimizer RL (Battery Dispatch)", style={"marginTop": "0", "color": "#34495e"}),
                html.Div(
                    "Panel ini memanggil endpoint dispatch di backend untuk optimizer_backend=\"rl\" dan menampilkan KPI + schedule (kolom utama: grid_import_kwh, soc, cost, emission).",
                    style={"color": "#7f8c8d", "lineHeight": "1.6", "marginBottom": "10px"},
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div("stream_id", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                dcc.Input(id="bms-rl-stream-id", type="text", value="proof-rl-1", style={"width": "260px"}),
                            ]
                        ),
                        html.Div(
                            [
                                html.Div("endpoint path", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                dcc.Input(id="bms-rl-endpoint-path", type="text", value="/ai/optimizer/dispatch", style={"width": "260px"}),
                            ]
                        ),
                        html.Div(
                            [
                                html.Div("Dispatch Mode", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                dcc.RadioItems(
                                    id="bms-rl-dispatch-mode",
                                    options=[
                                        {"label": "Batch (Recommended)", "value": "batch"},
                                        {"label": "Single", "value": "single"},
                                    ],
                                    value="batch",
                                    inline=True,
                                    style={"fontSize": "12px", "color": "#2c3e50"},
                                    inputStyle={"marginRight": "6px"},
                                    labelStyle={"marginRight": "10px"},
                                ),
                            ],
                            style={"minWidth": "320px"},
                        ),
                        html.Div(
                            [
                                html.Div("Export Mode", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                dcc.RadioItems(
                                    id="bms-rl-export-mode",
                                    options=[
                                        {"label": "Export OFF (Curtail)", "value": "curtail"},
                                        {"label": "Export ON", "value": "export"},
                                    ],
                                    value="curtail",
                                    inline=True,
                                    style={"fontSize": "12px", "color": "#2c3e50"},
                                    inputStyle={"marginRight": "6px"},
                                    labelStyle={"marginRight": "10px"},
                                ),
                            ],
                            style={"minWidth": "320px"},
                        ),
                        html.Button(
                            "Run RL Dispatch",
                            id="bms-rl-run-btn",
                            style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold", "height": "40px", "marginTop": "18px"},
                        ),
                        html.Button(
                            "Load Dashboard Dispatch",
                            id="bms-rl-load-btn",
                            style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold", "height": "40px", "marginTop": "18px"},
                        ),
                        html.Div(id="bms-rl-status", style={"fontSize": "12px", "color": "#566573", "marginTop": "22px"}),
                    ],
                    style={"display": "flex", "gap": "12px", "alignItems": "flex-start", "flexWrap": "wrap"},
                ),
                html.Div(
                    [
                        html.Div("DRL Tuner (Safe Meta-Controller)", style={"fontWeight": "bold", "color": "#2c3e50"}),
                        html.Div(
                            [
                                dcc.Checklist(
                                    id="bms-tuner-enable",
                                    options=[{"label": "Enable DRL Tuner", "value": "on"}],
                                    value=[],
                                    inline=True,
                                    persistence=True,
                                    persistence_type="session",
                                    inputStyle={"marginRight": "6px"},
                                    labelStyle={"marginRight": "12px"},
                                    style={"fontSize": "12px", "color": "#2c3e50"},
                                ),
                                html.Div(
                                    [
                                        html.Div("Tuner mode", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                        dcc.Dropdown(
                                            id="bms-tuner-mode",
                                            options=[{"label": "drl_meta", "value": "drl_meta"}],
                                            value="drl_meta",
                                            clearable=False,
                                            persistence=True,
                                            persistence_type="session",
                                            style={"width": "220px"},
                                        ),
                                    ],
                                    style={"minWidth": "240px"},
                                ),
                                html.Button(
                                    "Preview Suggestion",
                                    id="bms-tuner-preview-btn",
                                    style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold", "height": "40px", "marginTop": "18px"},
                                ),
                            ],
                            style={"display": "flex", "gap": "12px", "alignItems": "flex-start", "flexWrap": "wrap", "marginTop": "6px"},
                        ),
                        html.Div(id="bms-tuner-output", style={"marginTop": "10px"}),
                        html.Details(
                            [
                                html.Summary("Raw tuner response (copy)", style={"cursor": "pointer", "marginTop": "8px"}),
                                dcc.Textarea(
                                    id="bms-tuner-raw",
                                    value="{}",
                                    style={"width": "100%", "height": "180px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"},
                                ),
                                dcc.Clipboard(target_id="bms-tuner-raw", title="Copy tuner response"),
                            ],
                            open=False,
                            style={"marginTop": "6px"},
                        ),
                    ],
                    style={"marginTop": "14px", "padding": "12px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
                ),
                html.Div(
                    [
                        html.Div("DRL Policy Proposer (Safe)", style={"fontWeight": "bold", "color": "#2c3e50"}),
                        html.Div(
                            [
                                dcc.Checklist(
                                    id="bms-policy-enable",
                                    options=[{"label": "Enable Policy Proposer", "value": "on"}],
                                    value=[],
                                    inline=True,
                                    persistence=True,
                                    persistence_type="session",
                                    inputStyle={"marginRight": "6px"},
                                    labelStyle={"marginRight": "12px"},
                                    style={"fontSize": "12px", "color": "#2c3e50"},
                                ),
                                html.Div(
                                    [
                                        html.Div("SOC (%)", style={"fontSize": "12px", "color": "#566573"}),
                                        dcc.Slider(
                                            id="bms-policy-soc",
                                            min=0,
                                            max=100,
                                            step=1,
                                            value=50,
                                            marks={0: "0", 50: "50", 100: "100"},
                                            persistence=True,
                                            persistence_type="session",
                                        ),
                                    ],
                                    style={"minWidth": "260px"},
                                ),
                                html.Div(
                                    [
                                        html.Div("demand_total_kwh", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                        dcc.Input(id="bms-policy-demand", type="number", value=80, style={"width": "180px"}),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.Div("renewable_potential_kwh", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                        dcc.Input(id="bms-policy-renewable", type="number", value=25, style={"width": "180px"}),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.Div("tariff (optional)", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                        dcc.Input(id="bms-policy-tariff", type="number", value=None, style={"width": "180px"}),
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.Div("emission_factor (optional)", style={"fontSize": "12px", "color": "#566573", "marginBottom": "4px"}),
                                        dcc.Input(id="bms-policy-emission", type="number", value=None, style={"width": "180px"}),
                                    ]
                                ),
                                html.Button(
                                    "Preview Action",
                                    id="bms-policy-preview-btn",
                                    style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold", "height": "40px", "marginTop": "18px"},
                                ),
                            ],
                            style={"display": "flex", "gap": "12px", "alignItems": "flex-start", "flexWrap": "wrap", "marginTop": "6px"},
                        ),
                        html.Div(id="bms-policy-output", style={"marginTop": "10px"}),
                        html.Details(
                            [
                                html.Summary("Raw policy response (copy)", style={"cursor": "pointer", "marginTop": "8px"}),
                                dcc.Textarea(
                                    id="bms-policy-raw",
                                    value="{}",
                                    style={"width": "100%", "height": "180px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"},
                                ),
                                dcc.Clipboard(target_id="bms-policy-raw", title="Copy policy response"),
                            ],
                            open=False,
                            style={"marginTop": "6px"},
                        ),
                    ],
                    style={"marginTop": "14px", "padding": "12px", "border": "1px solid #ecf0f1", "borderRadius": "10px", "backgroundColor": "#fbfcfc"},
                ),
                html.Div(
                    [
                        html.Div("Request payload (editable)", style={"fontSize": "12px", "color": "#566573", "marginTop": "10px"}),
                        dcc.Textarea(
                            id="bms-rl-payload",
                            value="{}",
                            style={"width": "100%", "height": "180px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "6px"},
                        ),
                        dcc.Clipboard(target_id="bms-rl-payload", title="Copy payload"),
                    ],
                    style={"marginTop": "6px"},
                ),
                html.Div(id="bms-rl-kpi", style={"marginTop": "12px"}),
                html.Div(id="bms-policy-audit", style={"marginTop": "10px"}),
                html.Div(
                    [
                        html.Div("Schedule (preview)", style={"fontSize": "12px", "color": "#566573", "marginTop": "10px"}),
                        dash_table.DataTable(
                            id="bms-rl-table",
                            columns=[],
                            data=[],
                            style_table={"overflowX": "auto"},
                            style_cell={"fontFamily": "Arial", "fontSize": "12px", "padding": "8px", "whiteSpace": "nowrap"},
                            style_header={"fontWeight": "bold", "backgroundColor": "#f4f6f7"},
                            page_size=10,
                        ),
                    ],
                    style={"marginTop": "6px"},
                ),
                html.Details(
                    [
                        html.Summary("Raw response (copy)", style={"cursor": "pointer", "marginTop": "10px"}),
                        dcc.Textarea(
                            id="bms-rl-raw",
                            value="{}",
                            style={"width": "100%", "height": "220px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"},
                        ),
                        dcc.Clipboard(target_id="bms-rl-raw", title="Copy response"),
                    ],
                    open=False,
                    style={"marginTop": "8px"},
                ),
            ],
            style={**CARD_STYLE, "width": "96%", "margin": "20px auto 0 auto"},
        ),
        
        # Interval for BMS
        dcc.Interval(id='bms-interval', interval=2000, n_intervals=0)

    ], style={'padding': '20px'})
