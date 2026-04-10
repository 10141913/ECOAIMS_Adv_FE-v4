from dash import html, dcc
from ecoaims_frontend.config import CARD_STYLE

import plotly.graph_objects as go

from ecoaims_frontend.services.data_service import get_accuracy_data, get_forecast_data


def _build_initial_forecasting_figures():
    """
    Provide non-empty figures on first render.
    Some client-side tab switches may delay triggering server callbacks,
    so empty default figures can show blank axes.
    """
    period = "hourly"
    data = get_forecast_data(period)
    accuracy_data = get_accuracy_data()

    cons_fig = go.Figure()
    cons_fig.add_trace(
        go.Scatter(
            x=data["time"],
            y=data["consumption"],
            mode="lines+markers",
            name="Konsumsi Energi",
            line=dict(color="#e74c3c", width=3),
            hovertemplate="%{y:.2f} kWh<br>%{x}",
        )
    )
    cons_fig.update_layout(
        title="Prediksi Konsumsi Energi (24 Jam ke Depan)",
        xaxis_title="Waktu",
        yaxis_title="Konsumsi (kWh)",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
    )

    renew_fig = go.Figure()
    renew_fig.add_trace(
        go.Scatter(
            x=data["time"],
            y=data["solar"],
            mode="lines",
            name="Solar PV",
            line=dict(color="#f1c40f", width=2),
            stackgroup="one",
        )
    )
    renew_fig.add_trace(
        go.Scatter(
            x=data["time"],
            y=data["wind"],
            mode="lines",
            name="Wind Turbine",
            line=dict(color="#3498db", width=2),
            stackgroup="one",
        )
    )
    renew_fig.update_layout(
        title="Prediksi Produksi Energi Terbarukan (24 Jam)",
        xaxis_title="Waktu",
        yaxis_title="Produksi (kWh)",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
    )

    acc_fig = go.Figure()
    acc_fig.add_trace(
        go.Scatter(
            x=accuracy_data["time"],
            y=accuracy_data["actual"],
            mode="lines",
            name="Aktual",
            line=dict(color="#2ecc71", width=3),
        )
    )
    acc_fig.add_trace(
        go.Scatter(
            x=accuracy_data["time"],
            y=accuracy_data["forecast"],
            mode="lines",
            name="Prediksi (Model)",
            line=dict(color="#95a5a6", width=2, dash="dash"),
        )
    )
    acc_fig.update_layout(
        title="Evaluasi Model: Data Aktual vs Prediksi (24 Jam Terakhir)",
        xaxis_title="Waktu",
        yaxis_title="Energi (kWh)",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40),
        hovermode="x unified",
    )

    return cons_fig, renew_fig, acc_fig

def create_forecasting_layout():
    """
    Creates the layout for the Forecasting Tab.
    Includes graphs for energy consumption prediction and renewable energy production.
    """
    initial_cons_fig, initial_renew_fig, initial_acc_fig = _build_initial_forecasting_figures()
    return html.Div([
        # Header for this section
        html.H2("Forecasting Energi", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

        # Controls Section
        html.Div([
            html.Label("Pilih Periode Prediksi:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
            dcc.Dropdown(
                id='forecast-period-dropdown',
                options=[
                    {'label': 'Per Jam (24 Jam ke Depan)', 'value': 'hourly'},
                    {'label': 'Harian (7 Hari ke Depan)', 'value': 'daily'}
                ],
                value='hourly',
                clearable=False,
                persistence=True,
                persistence_type='session',
                style={'width': '300px'}
            )
        ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '5px', 'marginBottom': '20px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),

        # Graphs Section
        html.Div([
            # Consumption Forecast Graph
            html.Div([
                html.H3("Prediksi Konsumsi Energi", style={'textAlign': 'center', 'color': '#34495e'}),
                dcc.Loading(
                    id="loading-consumption",
                    type="default",
                    children=dcc.Graph(
                        id='forecast-consumption-graph',
                        figure=initial_cons_fig,
                        config={'displayModeBar': False},
                    )
                ),
                html.P("Grafik ini menunjukkan estimasi penggunaan energi berdasarkan tren historis dan pola penggunaan.", 
                       style={'fontSize': '14px', 'color': '#7f8c8d', 'textAlign': 'center', 'marginTop': '10px'})
            ], style={**CARD_STYLE, 'marginBottom': '30px'}),

            # Renewable Production Forecast Graph
            html.Div([
                html.H3("Prediksi Produksi Energi Terbarukan (Solar & Wind)", style={'textAlign': 'center', 'color': '#34495e'}),
                dcc.Loading(
                    id="loading-renewable",
                    type="default",
                    children=dcc.Graph(
                        id='forecast-renewable-graph',
                        figure=initial_renew_fig,
                        config={'displayModeBar': False},
                    )
                ),
                html.P("Grafik ini memprediksi output dari panel surya dan turbin angin berdasarkan prakiraan cuaca.", 
                       style={'fontSize': '14px', 'color': '#7f8c8d', 'textAlign': 'center', 'marginTop': '10px'})
            ], style={**CARD_STYLE, 'marginBottom': '30px'}),
            
            # Historical vs Forecast Comparison (Optional but requested)
            html.Div([
                html.H3("Akurasi: Data Historis vs Prediksi", style={'textAlign': 'center', 'color': '#34495e'}),
                dcc.Loading(
                    id="loading-accuracy",
                    type="default",
                    children=dcc.Graph(
                        id='forecast-accuracy-graph',
                        figure=initial_acc_fig,
                        config={'displayModeBar': False},
                    )
                ),
                html.P("Perbandingan antara data aktual yang tercatat dengan prediksi sebelumnya untuk mengevaluasi akurasi model.", 
                       style={'fontSize': '14px', 'color': '#7f8c8d', 'textAlign': 'center', 'marginTop': '10px'})
            ], style=CARD_STYLE),

        ])
    ], style={'padding': '20px'})
