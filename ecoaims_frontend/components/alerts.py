from dash import html

def create_alert_notification(data, total_consumption, renewable_supply):
    """
    Generates alert notifications based on energy data.

    Args:
        data (dict): Current energy data.
        total_consumption (float): Total energy consumption.
        renewable_supply (float): Total renewable energy supply.

    Returns:
        html.Div: A Dash component containing visual alerts and audio element.
    """
    alerts = []
    play_sound = False

    meta = data.get("state_meta") if isinstance(data, dict) else None
    if isinstance(meta, dict) and meta.get("stale") is True:
        ts = meta.get("timestamp") or "unknown"
        src = meta.get("source") or "unknown"
        alerts.append(
            {
                "msg": f"Data backend bukan real-time (source={src}, ts={ts}). PV bisa 0 walau kondisi siang.",
                "color": "#f39c12",
                "icon": "🕒",
            }
        )
    
    batt = data.get("battery") if isinstance(data, dict) else None
    batt_pct = None
    if isinstance(batt, dict):
        sp = batt.get("soc_pct")
        if isinstance(sp, (int, float)):
            batt_pct = float(sp)
        elif isinstance(batt.get("soc"), (int, float)):
            s = float(batt.get("soc"))
            if 0.0 <= s <= 1.0:
                batt_pct = s * 100.0
            elif 0.0 <= s <= 100.0:
                batt_pct = s
        else:
            batt_val = batt.get("value")
            batt_max = batt.get("max")
            if isinstance(batt_val, (int, float)) and isinstance(batt_max, (int, float)) and float(batt_max) > 0:
                batt_pct = (float(batt_val) / float(batt_max)) * 100.0
    batt_pct = float(batt_pct or 0.0)
    
    if batt_pct <= 20:
        alerts.append({
            "msg": f"Baterai hampir habis! SOC {batt_pct:.1f}%", 
            "color": "#e74c3c", # Red
            "icon": "⚠️"
        })
        play_sound = True # Serious alert triggers sound
        
    elif batt_pct >= 80:
        alerts.append({
            "msg": f"Baterai penuh, SOC {batt_pct:.1f}%", 
            "color": "#f39c12", # Orange
            "icon": "🔋"
        })
        play_sound = True
        
    # Scenario 3: Grid Low (< 20% of max capacity)
    grid_val = data['grid']['value']
    grid_max = data['grid']['max']
    if grid_val < (grid_max * 0.2):
        alerts.append({
            "msg": "Grid sedang tidak terhubung/dibatasi!", 
            "color": "#e74c3c", # Red
            "icon": "⚡"
        })
        play_sound = True

    # Scenario 4: Renewable Insufficient
    if renewable_supply < total_consumption:
        alerts.append({
            "msg": "Energi terbarukan tidak mencukupi untuk memenuhi permintaan!", 
            "color": "#f1c40f", # Yellow/Gold
            "icon": "📉"
        })
        play_sound = True

    if not alerts:
        return html.Div() # Empty if no alerts

    # Create Alert Elements
    alert_elements = []
    for alert in alerts:
        alert_elements.append(
            html.Div([
                html.Span(alert['icon'], style={'fontSize': '24px', 'marginRight': '10px'}),
                html.Span(alert['msg'], style={'fontWeight': 'bold', 'fontSize': '16px'})
            ], style={
                'backgroundColor': alert['color'],
                'color': 'white',
                'padding': '15px',
                'borderRadius': '5px',
                'marginBottom': '10px',
                'display': 'flex',
                'alignItems': 'center',
                'boxShadow': '0 2px 5px rgba(0,0,0,0.2)'
            })
        )

    # Add Audio Element if needed
    if play_sound:
        # Note: 'autoplay' policy in browsers might block this without user interaction first
        # We can try to mitigate ERR_ABORTED by ensuring the file exists, but browser policy is strict.
        # Adding 'muted' sometimes helps but defeats the purpose of an alarm.
        # Best practice: User must interact with DOM first.
        # For now, we keep it but acknowledge it might fail silently in console.
        alert_elements.append(html.Audio(src='/assets/alert_sound.mp3', autoPlay=True, style={'display': 'none'}))

    return html.Div(
        alert_elements,
        style={
            "position": "fixed",
            "bottom": "20px",
            "right": "20px",
            "left": "auto",
            "top": "auto",
            "zIndex": "1000",
            "width": "350px",
            "maxHeight": "45vh",
            "overflowY": "auto",
        },
    )
