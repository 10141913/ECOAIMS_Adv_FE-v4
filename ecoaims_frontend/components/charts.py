import plotly.graph_objects as go
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

def create_trend_graph(data_points: List[Dict[str, float]]) -> go.Figure:
    """
    Creates a trend graph for energy consumption vs renewable supply.

    Args:
        data_points (List[Dict[str, float]]): A list of dictionaries containing
            'time' (str), 'consumption' (float), and 'renewable_supply' (float) keys.

    Returns:
        go.Figure: A Plotly Figure object with bar and line charts.
    """
    if not data_points:
        logger.warning("No data points provided for trend graph.")
        return go.Figure()

    try:
        times = [dp.get('time', '') for dp in data_points]
        consumption = [dp.get('consumption', 0.0) for dp in data_points]
        supply = [dp.get('renewable_supply', 0.0) for dp in data_points]
        
        fig = go.Figure()
        
        # Add Bar chart for consumption
        fig.add_trace(go.Bar(
            x=times,
            y=consumption,
            name='Konsumsi Energi',
            marker_color='#3498db',
            opacity=0.7,
            hovertemplate='%{y:.2f} kWh<extra></extra>'
        ))
        
        # Add Line chart for renewable supply
        fig.add_trace(go.Scatter(
            x=times,
            y=supply,
            mode='lines+markers',
            name='Supply Terbarukan (PV + WT)',
            line=dict(color='#2ecc71', width=3), # Green for renewable
            marker=dict(size=8, symbol='diamond'),
            hovertemplate='%{y:.2f} kWh<extra></extra>'
        ))

        fig.update_layout(
            title={
                'text': 'Tren Konsumsi Energi vs Supply Terbarukan',
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            xaxis_title='Waktu',
            yaxis_title='Energi (kWh)',
            template='plotly_white',
            height=320, # Increased height to accommodate bottom legend
            margin=dict(l=40, r=40, t=50, b=80), # Increased bottom margin for legend
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.3,
                xanchor="center",
                x=0.5,
                font=dict(size=12),
                bgcolor='rgba(255, 255, 255, 0.5)'
            ),
            hovermode="x unified",
            showlegend=True
        )
        return fig
    except Exception as e:
        logger.exception("Failed to create trend graph")
        return go.Figure()
