from dash import html, dcc
import plotly.graph_objects as go
import logging

logger = logging.getLogger(__name__)

def create_sparkline(history_data: list, color: str) -> dcc.Graph:
    """Creates a mini sparkline chart."""
    
    # Helper to convert hex to rgba for fill
    fill_color = color
    if color.startswith('#'):
        try:
            h = color.lstrip('#')
            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            fill_color = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.1)"
        except:
            fill_color = color # Fallback

    fig = go.Figure(go.Scatter(
        y=history_data,
        mode='lines',
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=fill_color
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=40,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        hovermode=False
    )
    return dcc.Graph(
        figure=fig, 
        config={'displayModeBar': False, 'staticPlot': True},
        style={'height': '40px', 'width': '100%'}
    )

def create_renewable_comparison_card(data: dict) -> html.Div:
    """
    Creates a full-width horizontal comparison dashboard for renewable energy.
    Includes: Contribution %, MW Capacity, Trend %, Status, and Sparkline.
    """
    try:
        # Extract values
        sources_config = [
            {'key': 'solar', 'name': 'Solar PV', 'icon': '☀️', 'color': '#f1c40f'},
            {'key': 'wind', 'name': 'Wind Turbine', 'icon': '🌬️', 'color': '#3498db'},
            {'key': 'biofuel', 'name': 'Biofuel', 'icon': '🌱', 'color': '#2ecc71'},
            {'key': 'battery', 'name': 'Battery', 'icon': '🔋', 'color': '#9b59b6'}
        ]
        
        total_renewable = sum([data.get(s['key'], {}).get('value', 0) for s in sources_config])
        
        cards = []
        for source in sources_config:
            s_data = data.get(source['key'], {})
            val = s_data.get('value', 0)
            history = s_data.get('history', [])
            status = s_data.get('status', 'Unknown')
            
            # Calculate Percentage
            pct = (val / total_renewable * 100) if total_renewable > 0 else 0
            
            # Calculate Trend (Last point vs Avg of first 3)
            if len(history) >= 2:
                start_avg = sum(history[:3]) / 3 if len(history) >=3 else history[0]
                trend_val = ((val - start_avg) / start_avg * 100) if start_avg > 0 else 0
                trend_symbol = "▲" if trend_val > 0 else "▼"
                trend_color = "#27ae60" if trend_val > 0 else "#c0392b"
            else:
                trend_val = 0
                trend_symbol = "-"
                trend_color = "gray"

            # Create Sparkline
            sparkline = create_sparkline(history, source['color'])
            
            card = html.Div([
                # Icon & Name
                html.Div([
                    html.Div(source['icon'], className='comp-icon', style={'backgroundColor': f"{source['color']}20", 'color': source['color']}),
                    html.Div([
                        html.Div(source['name'], className='comp-name'),
                        html.Div(status, className='comp-status-badge', style={'backgroundColor': '#e8f5e9' if status in ['Normal', 'Optimal', 'Active', 'Connected'] else '#fff3e0', 'color': '#2e7d32' if status in ['Normal', 'Optimal', 'Active', 'Connected'] else '#ef6c00'})
                    ], className='comp-header-text')
                ], className='comp-header'),
                
                # Values
                html.Div([
                    html.Div(f"{val:.1f} kW", className='comp-value'),
                    html.Div(f"{pct:.1f}%", className='comp-pct', style={'color': source['color']}),
                ], className='comp-main-stats'),
                
                # Trend
                html.Div([
                    html.Span(f"{trend_symbol} {abs(trend_val):.1f}%", style={'color': trend_color, 'fontWeight': 'bold'}),
                    html.Span(" vs 1h ago", className='comp-trend-label')
                ], className='comp-trend'),
                
                # Sparkline
                html.Div(sparkline, className='comp-sparkline')
                
            ], className='comp-card-horizontal')
            cards.append(card)
            
        return html.Div([
            html.H4("Real-time Renewable Energy Monitor (Last 60 Minutes)", className='section-title'),
            html.Div(cards, className='comp-container-full')
        ], className='comparison-section')
        
    except Exception as e:
        logger.exception("Failed to create renewable comparison card")
        return html.Div("Error loading comparison data")
