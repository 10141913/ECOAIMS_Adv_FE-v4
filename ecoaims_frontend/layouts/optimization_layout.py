from dash import html, dcc
from ecoaims_frontend.config import CARD_STYLE

def create_optimization_layout() -> html.Div:
    """
    Creates the layout for the Optimization Tab.
    Includes controls for simulation parameters and visualization of results.
    """
    return html.Div([
        # Header
        html.H2("Optimasi Distribusi Energi", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

        html.Div([
            # --- Left Column: Controls ---
            html.Div([
                html.H3("Konfigurasi Parameter", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
                
                # Priority Dropdown
                html.Div([
                    html.Label("Prioritas Penggunaan Energi:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='opt-priority-dropdown',
                        options=[
                            {'label': 'Prioritas Energi Terbarukan (Solar & Wind)', 'value': 'renewable'},
                            {'label': 'Prioritas Baterai (Peak Shaving)', 'value': 'battery'},
                            {'label': 'Prioritas PLN / Grid (Kestabilan)', 'value': 'grid'}
                        ],
                        value='renewable',
                        clearable=False,
                        style={'marginTop': '5px'}
                    ),
                    html.P("Pilih sumber energi utama yang akan digunakan terlebih dahulu untuk memenuhi beban.", 
                           style={'fontSize': '12px', 'color': '#7f8c8d', 'marginTop': '5px'})
                ], style={'marginBottom': '20px'}),

                html.Div(
                    [
                        html.Label("Optimizer Backend (shared untuk Precooling/LAEOPF):", style={"fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="opt-optimizer-backend",
                            options=[
                                {"label": "Grid (default)", "value": "grid"},
                                {"label": "MPC", "value": "mpc"},
                                {"label": "CEM", "value": "cem"},
                            ],
                            value="grid",
                            clearable=False,
                            style={"marginTop": "5px"},
                        ),
                        html.P(
                            "Pilihan ini dipakai oleh Precooling/LAEOPF (Simulate/Candidates). Tidak mengubah hasil simulasi Optimization di tab ini.",
                            style={"fontSize": "12px", "color": "#7f8c8d", "marginTop": "5px"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),

                # Battery Usage Slider
                html.Div([
                    html.Label("Batas Penggunaan Kapasitas Baterai (%):", style={'fontWeight': 'bold'}),
                    dcc.Slider(
                        id='opt-battery-slider',
                        min=0,
                        max=100,
                        step=10,
                        value=50,
                        persistence=True,
                        persistence_type='session',
                        marks={i: f'{i}%' for i in range(0, 101, 20)},
                    ),
                    html.P("Mengatur persentase maksimum kapasitas baterai yang diizinkan untuk dikuras.", 
                           style={'fontSize': '12px', 'color': '#7f8c8d', 'marginTop': '5px'})
                ], style={'marginBottom': '20px'}),
                
                # Grid Limit Slider (Optional extra)
                html.Div([
                    html.Label("Batas Daya Grid (kW):", style={'fontWeight': 'bold'}),
                    dcc.Slider(
                        id='opt-grid-slider',
                        min=0,
                        max=200,
                        step=10,
                        value=100,
                        persistence=True,
                        persistence_type='session',
                        marks={i: f'{i}' for i in range(0, 201, 50)},
                    ),
                ], style={'marginBottom': '30px'}),

                # Run Button
                html.Button('Jalankan Simulasi Optimasi', id='opt-run-btn', n_clicks=0, 
                            style={
                                'backgroundColor': '#3498db', 'color': 'white', 'border': 'none', 
                                'padding': '15px 30px', 'borderRadius': '5px', 'cursor': 'pointer',
                                'fontSize': '16px', 'width': '100%', 'fontWeight': 'bold'
                            })

            ], style={**CARD_STYLE, 'width': '30%', 'marginRight': '2%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # --- Right Column: Results ---
            html.Div([
                html.H3("Hasil Simulasi & Distribusi", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
                
                # Graphs Container
                html.Div([
                    # Pie Chart
                    html.Div([
                        dcc.Graph(id='opt-pie-chart', style={'height': '350px'})
                    ], style={'width': '50%', 'display': 'inline-block'}),
                    
                    # Bar Chart
                    html.Div([
                        dcc.Graph(id='opt-bar-chart', style={'height': '350px'})
                    ], style={'width': '50%', 'display': 'inline-block'}),
                ], style={'display': 'flex'}),

                # Recommendation Box
                html.Div([
                    html.H4("Rekomendasi Sistem:", style={'color': '#27ae60'}),
                    html.P(id='opt-recommendation-text', style={'fontSize': '16px', 'lineHeight': '1.6'})
                ], style={'backgroundColor': '#e8f8f5', 'padding': '15px', 'borderRadius': '5px', 'borderLeft': '5px solid #2ecc71', 'marginTop': '20px'})

            ], style={**CARD_STYLE, 'width': '64%', 'display': 'inline-block', 'verticalAlign': 'top'})

        ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'})

    ], style={'padding': '20px'})
