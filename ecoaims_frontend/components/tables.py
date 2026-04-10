from dash import html
from typing import List, Tuple
import logging
import random

logger = logging.getLogger(__name__)

def create_status_table(data: dict) -> html.Table:
    """
    Creates an HTML table displaying the status of energy resources.

    Args:
        data (dict): Dictionary containing resource data.
                     Format: {'solar': {'value': 50, 'max': 100}, ...}

    Returns:
        html.Table: A Dash Table component.
    """
    def get_status(val: float, max_val: float) -> Tuple[str, str]:
        if max_val <= 0: return "Unknown", "gray"
        percentage = (val / max_val) * 100
        if percentage > 80: return "Tinggi", "red"
        if percentage < 20: return "Rendah", "orange"
        return "Normal", "green"

    try:
        # Mapping key to display name
        display_names = {
            'solar': 'Solar PV',
            'wind': 'Wind Turbine',
            'grid': 'PLN/Grid',
            'biofuel': 'Biofuel',
            'battery': 'Battery'
        }

        table_rows = []
        
        # Iterate through known keys to maintain order
        for key in ['solar', 'wind', 'grid', 'biofuel', 'battery']:
            if key in data:
                item = data[key]
                name = display_names.get(key, key.capitalize())
                val = item.get('value', 0)
                max_v = item.get('max', 100)
                source = item.get('source', 'sim') # 'live' or 'sim'
                
                status, color = get_status(val, max_v)
                
                # Random trend arrow for simulation purposes (or calculate if history available)
                trend = random.choice(["⬆️", "⬇️", "➡️"])
                
                # Add source indicator to name
                source_badge = " (Live)" if source == 'live' else ""
                
                row = html.Tr([
                    html.Td(f"{name}{source_badge}", style={'padding': '8px', 'borderBottom': '1px solid #ddd'}),
                    html.Td(f"{val:.1f} kW", style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'right'}),
                    html.Td(status, style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'color': color, 'fontWeight': 'bold'}),
                    html.Td(trend, style={'padding': '8px', 'borderBottom': '1px solid #ddd', 'textAlign': 'center'})
                ])
                table_rows.append(row)

        return html.Table([
            html.Thead(
                html.Tr([
                    html.Th("Sumber", style={'textAlign': 'left', 'padding': '8px'}),
                    html.Th("Output", style={'textAlign': 'right', 'padding': '8px'}),
                    html.Th("Status", style={'textAlign': 'left', 'padding': '8px'}),
                    html.Th("Tren", style={'textAlign': 'center', 'padding': '8px'}),
                ])
            ),
            html.Tbody(table_rows)
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'})
    except Exception as e:
        logger.exception("Failed to create status table")
        return html.Table()
