from dash import html, dcc
from ecoaims_frontend.config import HEADER_STYLE, UPDATE_INTERVAL_MS
from ecoaims_frontend.layouts.home_layout import create_home_layout
from ecoaims_frontend.layouts.dashboard_layout import create_dashboard_layout
from ecoaims_frontend.layouts.forecasting_layout import create_forecasting_layout
from ecoaims_frontend.layouts.optimization_layout import create_optimization_layout
from ecoaims_frontend.layouts.precooling_layout import create_precooling_layout
from ecoaims_frontend.layouts.settings_layout import create_settings_layout
from ecoaims_frontend.layouts.bms_layout import create_bms_layout
from ecoaims_frontend.layouts.reports_layout import create_reports_layout
from ecoaims_frontend.layouts.help_layout import create_help_layout
from ecoaims_frontend.layouts.about_layout import create_about_layout
from ecoaims_frontend.layouts.indoor_layout import create_indoor_layout

def create_layout() -> html.Div:
    """
    Constructs the main layout of the Dash application.
    Includes Tabs for Dashboard, Forecasting, Optimization, BMS, Settings, Reports, Help, and About.
    
    Returns:
        html.Div: The root component of the app layout.
    """
    
    # --- Home Content ---
    home_content = create_home_layout()

    # --- Dashboard Content ---
    dashboard_content = create_dashboard_layout()
    
    # --- Forecasting Content ---
    forecasting_content = create_forecasting_layout()
    
    # --- Optimization Content ---
    optimization_content = create_optimization_layout()

    # --- Precooling Content ---
    precooling_content = create_precooling_layout()

    # --- Settings Content ---
    settings_content = create_settings_layout()
    
    # --- BMS Content ---
    bms_content = create_bms_layout()
    
    # --- Reports Content ---
    reports_content = create_reports_layout()
    
    # --- Help Content ---
    help_content = create_help_layout()
    
    # --- About Content ---
    about_content = create_about_layout()

    # --- Indoor Content ---
    indoor_content = create_indoor_layout()

    # --- Main Layout Structure ---
    return html.Div(style={'backgroundColor': '#ecf0f1', 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'}, children=[
    
        # Alert Container (Fixed position or Top)
        html.Div(id='alert-container'),

        # Header
        html.Div([
            html.H1('ECO-AIMS Energy Dashboard', style={'margin': '0'}),
            html.P('Monitoring Real-time Energi & Emisi Karbon', style={'margin': '5px 0 0 0', 'fontSize': '18px'})
        ], style=HEADER_STYLE),

        html.Div(id="backend-status-banner", style={"maxWidth": "1200px", "margin": "0 auto"}),

        dcc.Store(id="token-store", storage_type="session"),
        dcc.Store(id="backend-readiness-store", storage_type="memory"),
        dcc.Store(id="optimizer-backend-store", storage_type="memory", data={"value": "grid"}),
        dcc.Store(id="contract-mismatch-store", storage_type="memory", data={"count": 0}),

        dcc.Interval(
            id="backend-readiness-interval",
            interval=2000,
            n_intervals=0,
        ),

        # Interval component for real-time updates (Dashboard)
        dcc.Interval(
            id='interval-component',
            interval=UPDATE_INTERVAL_MS,
            n_intervals=0
        ),
        
        # Interval component for 1-hour updates (Renewable Comparison)
        dcc.Interval(
            id='interval-1h',
            interval=60 * 60 * 1000, # 1 hour in milliseconds
            n_intervals=0
        ),

        # Tabs (default Monitoring: grafik & gauge ada di sini, bukan di Home)
        dcc.Tabs(
            id="main-tabs",
            value="monitoring",
            children=[
            dcc.Tab(id="tab-home", value="home", label='Home', children=home_content,
                    selected_style={'borderTop': '3px solid #2c3e50', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),

            dcc.Tab(id="tab-monitoring", value="monitoring", label='Monitoring', children=dashboard_content,
                    selected_style={'borderTop': '3px solid #3498db', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
                    
            dcc.Tab(id="tab-forecasting", value="forecasting", label='Forecasting', children=forecasting_content,
                    selected_style={'borderTop': '3px solid #e74c3c', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
            
            dcc.Tab(id="tab-optimization", value="optimization", label='Optimization', children=optimization_content,
                    selected_style={'borderTop': '3px solid #2ecc71', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),

            dcc.Tab(id="tab-precooling", value="precooling", label='Precooling / LAEOPF', children=precooling_content,
                    selected_style={'borderTop': '3px solid #8e44ad', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
            
            dcc.Tab(id="tab-bms", value="bms", label='BMS', children=bms_content,
                    selected_style={'borderTop': '3px solid #e67e22', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),

            dcc.Tab(id="tab-indoor", value="indoor", label='Indoor Climate', children=indoor_content,
                    selected_style={'borderTop': '3px solid #1abc9c', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
            
            dcc.Tab(id="tab-reports", value="reports", label='Reports', children=reports_content,
                    selected_style={'borderTop': '3px solid #9b59b6', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),

            dcc.Tab(id="tab-settings", value="settings", label='Settings', children=settings_content,
                    selected_style={'borderTop': '3px solid #95a5a6', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
            
            dcc.Tab(id="tab-about", value="about", label='About', children=about_content,
                    selected_style={'borderTop': '3px solid #2c3e50', 'fontWeight': 'bold'},
                    style={'padding': '10px', 'fontWeight': 'bold', 'color': '#7f8c8d'}),
        ], style={'fontFamily': 'Arial, sans-serif', 'marginBottom': '20px'}),

        # Footer
        html.Div([
            html.P("© 2026 ECO-AIMS Dashboard Project. All rights reserved.", style={'color': '#7f8c8d'})
        ], style={'textAlign': 'center', 'padding': '20px', 'marginTop': '20px'})
    ])
