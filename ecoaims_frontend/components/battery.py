from dash import html

def create_battery_visual(value: float, max_value: float, status: str, soc_pct=None, soc=None) -> html.Div:
    """
    Creates a visual representation of a battery.

    Args:
        value (float): Current battery charge in kWh.
        max_value (float): Maximum battery capacity in kWh.
        status (str): "Charging" or "Discharging".

    Returns:
        html.Div: A Dash component representing the battery.
    """
    percentage = None
    if isinstance(soc_pct, (int, float)):
        percentage = float(soc_pct)
    elif isinstance(soc, (int, float)):
        s = float(soc)
        if 0.0 <= s <= 1.0:
            percentage = s * 100.0
        elif 0.0 <= s <= 100.0:
            percentage = s
    if percentage is None:
        if isinstance(value, (int, float)) and isinstance(max_value, (int, float)) and float(max_value) > 0 and float(value) > 0:
            percentage = (float(value) / float(max_value)) * 100.0
    if percentage is not None:
        percentage = max(20.0, min(80.0, min(max(float(percentage), 0.0), 100.0)))

    # Determine color based on status
    if status == "Charging":
        battery_color = "#2ecc71" # Green
        status_icon = "⚡"
    elif status == "Discharging":
        battery_color = "#e74c3c" # Red
        status_icon = "🔻"
    else:
        battery_color = "#7f8c8d"
        status_icon = "⏸"

    if percentage is None:
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            style={
                                "height": "100%",
                                "width": "0%",
                                "backgroundColor": battery_color,
                                "borderRadius": "2px",
                                "transition": "width 0.5s ease-in-out, background-color 0.3s",
                            }
                        ),
                        html.Div(
                            "---",
                            style={
                                "position": "absolute",
                                "top": "50%",
                                "left": "50%",
                                "transform": "translate(-50%, -50%)",
                                "color": "#2c3e50",
                                "fontWeight": "bold",
                                "fontSize": "16px",
                            },
                        ),
                    ],
                    className="battery-body",
                    style={
                        "position": "relative",
                        "width": "80%",
                        "height": "60px",
                        "border": "4px solid #34495e",
                        "borderRadius": "5px",
                        "padding": "2px",
                        "margin": "10px auto",
                        "backgroundColor": "#ecf0f1",
                    },
                ),
                html.Div(
                    [
                        html.Div("Waiting for data…", style={"fontSize": "14px", "fontWeight": "bold", "color": "#7f8c8d"}),
                        html.Div(f"{status} {status_icon}", style={"fontSize": "14px", "color": battery_color, "fontWeight": "bold", "marginTop": "5px"}),
                    ],
                    style={"textAlign": "center", "marginTop": "10px"},
                ),
            ],
            style={"position": "relative", "padding": "10px", "width": "100%"},
        )

    return html.Div([
        # Battery Body (Outer Shell)
        html.Div([
            # Battery Level (Inner Fill)
            html.Div(style={
                'height': '100%',
                'width': f'{percentage}%',
                'backgroundColor': battery_color,
                'borderRadius': '2px',
                'transition': 'width 0.5s ease-in-out, background-color 0.3s'
            }),
            # Percentage Text (Centered)
            html.Div(f"{percentage:.1f}%", style={
                'position': 'absolute',
                'top': '50%',
                'left': '50%',
                'transform': 'translate(-50%, -50%)',
                'color': 'white' if percentage > 50 else '#2c3e50', # Contrast text
                'fontWeight': 'bold',
                'fontSize': '16px',
                'textShadow': '0px 0px 2px rgba(0,0,0,0.5)' if percentage > 50 else 'none'
            })
        ], className='battery-body', style={
            'position': 'relative',
            'width': '80%',
            'height': '60px',
            'border': '4px solid #34495e',
            'borderRadius': '5px',
            'padding': '2px',
            'margin': '10px auto',
            'backgroundColor': '#ecf0f1'
        }),
        
        # Battery Terminal (Positive Node)
        html.Div(style={
            'width': '10px',
            'height': '20px',
            'backgroundColor': '#34495e',
            'position': 'absolute',
            'right': '5%', # Adjust based on container
            'top': '50%',
            'transform': 'translate(100%, -50%)',
            'borderTopRightRadius': '3px',
            'borderBottomRightRadius': '3px'
        }),

        # Info Text (kW and Status)
        html.Div([
            html.Div(f"{value:.1f} kWh", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2c3e50'}),
            html.Div(f"{status} {status_icon}", style={
                'fontSize': '14px', 
                'color': battery_color, 
                'fontWeight': 'bold',
                'marginTop': '5px'
            })
        ], style={'textAlign': 'center', 'marginTop': '10px'})

    ], style={'position': 'relative', 'padding': '10px', 'width': '100%'})
