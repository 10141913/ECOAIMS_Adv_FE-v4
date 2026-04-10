from dash import html, dcc
from ecoaims_frontend.config import CARD_STYLE

def create_dashboard_layout() -> html.Div:
    """
    Constructs the layout for the 'Dashboard Monitoring' tab.
    
    Returns:
        html.Div: The layout containing speedometers, comparison cards, and trend graphs.
    """
    return html.Div([
        dcc.Store(id="trend-data-store", data=[]),
        # Row 0: Sensor Health Status
        html.Div(id='sensor-health-container', style={'marginBottom': '10px', 'display': 'flex', 'justifyContent': 'center'}),

        # Row 1: Speedometers
        html.Div([
            # Solar PV Gauge
            html.Div([
                html.H4("Solar PV", className='gauge-title'),
                dcc.Graph(id='solar-gauge', config={'displayModeBar': False, 'responsive': True}, style={'height': '180px', 'minHeight': '165px'})
            ], className='gauge-card'),

            # Wind Turbine Gauge
            html.Div([
                html.H4("Wind Turbine", className='gauge-title'),
                dcc.Graph(id='wind-gauge', config={'displayModeBar': False, 'responsive': True}, style={'height': '180px', 'minHeight': '165px'})
            ], className='gauge-card'),

            # Grid Gauge
            html.Div([
                html.H4("PLN / Grid", className='gauge-title'),
                dcc.Graph(id='grid-gauge', config={'displayModeBar': False, 'responsive': True}, style={'height': '180px', 'minHeight': '165px'})
            ], className='gauge-card'),

            # Biofuel Gauge
            html.Div([
                html.H4("Biofuel", className='gauge-title'),
                dcc.Graph(id='biofuel-gauge', config={'displayModeBar': False, 'responsive': True}, style={'height': '180px', 'minHeight': '165px'})
            ], className='gauge-card'),

            # Battery Visual (New)
            html.Div([
                html.H4("Battery", className='gauge-title'),
                html.Div(id='battery-visual-container') # Replaced Graph with generic Div
            ], className='gauge-card'),
            
        ], className='gauge-container'),
        
        # Row 2: Renewable Comparison (Full Width)
        html.Div([
            dcc.Store(id="comparison-update-click-store", data=0),
            html.Div(id="renewable-comparison-status", style={"marginBottom": "8px"}),
            html.Div(id="renewable-comparison-content", style={"width": "100%"}),
            html.Div(
                [
                    html.Button("Update history", id="comparison-update-history-btn", n_clicks=0),
                    html.A(
                        "Instruksi",
                        id="comparison-history-instructions-link",
                        href="/instructions/monitoring-history",
                        target="_blank",
                        style={"marginLeft": "10px", "textDecoration": "underline"},
                    ),
                    html.Div(id="comparison-update-history-result", style={"marginLeft": "10px", "display": "inline-block", "fontSize": "12px", "opacity": 0.9}),
                ],
                style={"marginTop": "10px"},
            ),
            html.Details(
                [
                    html.Summary("Detail teknis / Copy diagnostics", style={"cursor": "pointer"}),
                    dcc.Textarea(id="comparison-diagnostics-text", value="{}", style={"width": "100%", "height": "160px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"}),
                    dcc.Clipboard(target_id="comparison-diagnostics-text", title="Copy diagnostics"),
                ],
                id="comparison-diagnostics-details",
                open=False,
                style={"marginTop": "10px"},
            ),
        ], style={**CARD_STYLE, 'display': 'block', 'width': '95%', 'margin': '20px auto'}),

        html.Div(
            [
                html.H3("KPI Dashboard", style={"color": "#2c3e50", "marginTop": "0"}),
                html.Div(id="kpi-dashboard-panel"),
            ],
            style={**CARD_STYLE, "display": "block", "width": "95%", "margin": "20px auto"},
        ),

        # Row 3: Trend Graph & CO2 Info
        html.Div([
            # Left Column: Trend Graph Only
            html.Div([
                dcc.Graph(id='trend-graph', config={'displayModeBar': False, 'responsive': True}, style={'height': '340px', 'minHeight': '320px'}),
            ], style={**CARD_STYLE, 'width': '60%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            # Right Column: CO2 Info & Status
            html.Div([
                html.H3("Dampak Lingkungan (CO2)", style={'color': '#2c3e50', 'marginTop': '0'}),
                html.Div(id='co2-content'),
                
                html.Hr(),
                
                html.H3("Status Sumber Daya", style={'color': '#2c3e50'}),
                html.Div(id='resource-status-table')
                
            ], style={**CARD_STYLE, 'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top'})
            
        ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'}),
    ])
