from dash import Input, Output
import plotly.graph_objects as go
from ecoaims_frontend.services.data_service import get_forecast_data, get_accuracy_data
from ecoaims_frontend.ui.error_ui import error_figure

def register_forecasting_callbacks(app):
    """
    Registers callbacks for the Forecasting Tab.
    """
    
    @app.callback(
        [Output('forecast-consumption-graph', 'figure'),
         Output('forecast-renewable-graph', 'figure'),
         Output('forecast-accuracy-graph', 'figure')],
        [Input('forecast-period-dropdown', 'value')]
    )
    def update_forecast_graphs(period):
        """
        Updates all forecasting graphs based on the selected period.
        """
        try:
            data = get_forecast_data(period)
            accuracy_data = get_accuracy_data()
        
            cons_fig = go.Figure()
            if period == 'hourly':
                cons_fig.add_trace(go.Scatter(
                    x=data['time'], 
                    y=data['consumption'], 
                    mode='lines+markers', 
                    name='Konsumsi Energi',
                    line=dict(color='#e74c3c', width=3),
                    hovertemplate='%{y:.2f} kWh<br>%{x}'
                ))
                title = 'Prediksi Konsumsi Energi (24 Jam ke Depan)'
                xaxis_title = 'Waktu'
            else:
                cons_fig.add_trace(go.Bar(
                    x=data['time'], 
                    y=data['consumption'], 
                    name='Konsumsi Energi',
                    marker_color='#e74c3c',
                    hovertemplate='%{y:.2f} kWh<br>%{x}'
                ))
                title = 'Prediksi Konsumsi Energi (7 Hari ke Depan)'
                xaxis_title = 'Tanggal'
                
            cons_fig.update_layout(
                title=title,
                xaxis_title=xaxis_title,
                yaxis_title='Konsumsi (kWh)',
                template='plotly_white',
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            renew_fig = go.Figure()
            if period == 'hourly':
                renew_fig.add_trace(go.Scatter(
                    x=data['time'], 
                    y=data['solar'], 
                    mode='lines', 
                    name='Solar PV',
                    line=dict(color='#f1c40f', width=2),
                    stackgroup='one'
                ))
                renew_fig.add_trace(go.Scatter(
                    x=data['time'], 
                    y=data['wind'], 
                    mode='lines', 
                    name='Wind Turbine',
                    line=dict(color='#3498db', width=2),
                    stackgroup='one'
                ))
                title = 'Prediksi Produksi Energi Terbarukan (24 Jam)'
            else:
                renew_fig.add_trace(go.Bar(
                    x=data['time'], 
                    y=data['solar'], 
                    name='Solar PV',
                    marker_color='#f1c40f'
                ))
                renew_fig.add_trace(go.Bar(
                    x=data['time'], 
                    y=data['wind'], 
                    name='Wind Turbine',
                    marker_color='#3498db'
                ))
                title = 'Prediksi Produksi Energi Terbarukan (7 Hari)'
                
            renew_fig.update_layout(
                title=title,
                xaxis_title=xaxis_title,
                yaxis_title='Produksi (kWh)',
                template='plotly_white',
                barmode='stack' if period == 'daily' else None,
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            acc_fig = go.Figure()
            acc_fig.add_trace(go.Scatter(
                x=accuracy_data['time'],
                y=accuracy_data['actual'],
                mode='lines',
                name='Aktual',
                line=dict(color='#2ecc71', width=3)
            ))
            acc_fig.add_trace(go.Scatter(
                x=accuracy_data['time'],
                y=accuracy_data['forecast'],
                mode='lines',
                name='Prediksi (Model)',
                line=dict(color='#95a5a6', width=2, dash='dash')
            ))
            
            acc_fig.update_layout(
                title='Evaluasi Model: Data Aktual vs Prediksi (24 Jam Terakhir)',
                xaxis_title='Waktu',
                yaxis_title='Energi (kWh)',
                template='plotly_white',
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            return cons_fig, renew_fig, acc_fig
        except Exception as e:
            fig = error_figure("Forecasting", str(e))
            return fig, fig, fig
