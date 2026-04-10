import datetime
from dash import html
from ecoaims_frontend.config import CARD_STYLE

def create_sensor_health_card(health_data, *, state_meta=None):
    """
    Creates a visual card for Sensor Health Status.
    """
    status = health_data.get('status', 'normal')
    active = health_data.get('active_sensors', 0)
    stale = health_data.get('stale_sensors', 0)
    missing = health_data.get('missing_sensors', 0)
    last_update = health_data.get('last_update', 'N/A')
    
    # Status Color
    if status == 'normal':
        status_color = '#27ae60' # Green
        status_text = "NORMAL"
    elif status == 'warning':
        status_color = '#f39c12' # Orange
        status_text = "WARNING"
    else:
        status_color = '#c0392b' # Red
        status_text = "CRITICAL"
        
    meta = state_meta if isinstance(state_meta, dict) else {}
    meta_source = meta.get("source")
    meta_ts = meta.get("timestamp")
    meta_age_s = meta.get("age_s")
    meta_stale = meta.get("stale")
    meta_line_children = []
    if meta_source or meta_ts or isinstance(meta_age_s, (int, float)) or meta_stale is True:
        meta_line_children.append(html.Span("Dashboard State: ", style={"color": "#95a5a6"}))
        if meta_source:
            meta_line_children.append(html.Span(f"source={meta_source}", style={"color": "#95a5a6"}))
        if meta_ts:
            if meta_source:
                meta_line_children.append(html.Span(" | ", style={"color": "#95a5a6"}))
            meta_line_children.append(html.Span("ts=", style={"color": "#95a5a6"}))
            meta_line_children.append(html.Span(str(meta_ts), style={"color": "#000000", "fontSize": "12px", "fontWeight": "bold"}))
        if isinstance(meta_age_s, (int, float)):
            if meta_source or meta_ts:
                meta_line_children.append(html.Span(" | ", style={"color": "#95a5a6"}))
            meta_line_children.append(html.Span(f"age={float(meta_age_s):.0f}s", style={"color": "#95a5a6"}))
        if meta_stale is True:
            if meta_source or meta_ts or isinstance(meta_age_s, (int, float)):
                meta_line_children.append(html.Span(" | ", style={"color": "#95a5a6"}))
            meta_line_children.append(html.Span("stale=true", style={"color": "#95a5a6"}))

    if (last_update in (None, "", "N/A") or int(active or 0) == 0) and meta_ts:
        try:
            s = str(meta_ts).strip()
            if s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(s).astimezone()
            last_update = dt.strftime("%H:%M:%S")
        except Exception:
            pass

    return html.Div([
        html.Div([
            html.H4("Sensor Health", style={'margin': '0', 'color': '#34495e'}),
            html.Span(status_text, style={
                'backgroundColor': status_color, 'color': 'white', 
                'padding': '2px 8px', 'borderRadius': '4px', 'fontSize': '12px', 'fontWeight': 'bold'
            })
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '15px'}),
        
        html.Div([
            html.Div([
                html.Span(str(active), style={'fontSize': '24px', 'fontWeight': 'bold', 'color': '#27ae60'}),
                html.P("Active", style={'margin': '0', 'fontSize': '12px', 'color': '#7f8c8d'})
            ], style={'textAlign': 'center', 'flex': '1'}),
            
            html.Div([
                html.Span(str(stale), style={'fontSize': '24px', 'fontWeight': 'bold', 'color': '#f39c12'}),
                html.P("Stale", style={'margin': '0', 'fontSize': '12px', 'color': '#7f8c8d'})
            ], style={'textAlign': 'center', 'flex': '1'}),
            
            html.Div([
                html.Span(str(missing), style={'fontSize': '24px', 'fontWeight': 'bold', 'color': '#c0392b'}),
                html.P("Missing", style={'margin': '0', 'fontSize': '12px', 'color': '#7f8c8d'})
            ], style={'textAlign': 'center', 'flex': '1'}),
        ], style={'display': 'flex', 'marginBottom': '10px'}),
        
        html.Hr(style={'border': '0', 'borderTop': '1px solid #ecf0f1'}),
        
        html.Div([
            html.P(f"Last Update: {last_update}", style={'fontSize': '11px', 'color': '#bdc3c7', 'margin': '0'}),
            html.P(meta_line_children, style={'fontSize': '10px', 'margin': '2px 0 0 0'}) if meta_line_children else html.Div(),
            html.P("Mode: Hybrid (Auto-Switching)", style={'fontSize': '10px', 'color': '#3498db', 'margin': '2px 0 0 0', 'fontStyle': 'italic'})
        ], style={'textAlign': 'center'})
        
    ], style={**CARD_STYLE, 'minWidth': '250px'})
