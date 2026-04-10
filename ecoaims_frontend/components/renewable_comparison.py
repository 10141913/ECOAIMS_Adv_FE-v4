from dash import html
import logging

logger = logging.getLogger(__name__)

from ecoaims_frontend.ui.error_ui import error_banner

def create_renewable_comparison_card(data: dict) -> html.Div:
    """
    Creates a component displaying the comparison of renewable energy sources.
    
    Args:
        data (dict): Dictionary containing energy data for 'solar', 'wind', 'biofuel', 'battery'.
        
    Returns:
        html.Div: A Dash component with the comparison layout.
    """
    try:
        # Extract values (using 1-hour aggregated data if available, fallback to current * 3)
        pv_val = data.get('solar', {}).get('value_3h', data.get('solar', {}).get('value', 0) * 3)
        wt_val = data.get('wind', {}).get('value_3h', data.get('wind', {}).get('value', 0) * 3)
        bio_val = data.get('biofuel', {}).get('value_3h', data.get('biofuel', {}).get('value', 0) * 3)
        batt_val = data.get('battery', {}).get('value_3h', data.get('battery', {}).get('value', 0) * 3)
        grid_val = data.get('grid', {}).get('value_3h', data.get('grid', {}).get('value', 0) * 3)
        
        total_energy = pv_val + wt_val + bio_val + batt_val + grid_val
        
        # Calculate percentages
        pv_pct = (pv_val / total_energy * 100) if total_energy > 0 else 0
        wt_pct = (wt_val / total_energy * 100) if total_energy > 0 else 0
        bio_pct = (bio_val / total_energy * 100) if total_energy > 0 else 0
        batt_pct = (batt_val / total_energy * 100) if total_energy > 0 else 0
        grid_pct = (grid_val / total_energy * 100) if total_energy > 0 else 0
        
        sources = [
            {'name': 'Solar PV', 'val': pv_val, 'pct': pv_pct, 'color': '#f1c40f', 'icon': '☀️'},
            {'name': 'Wind Turbine', 'val': wt_val, 'pct': wt_pct, 'color': '#3498db', 'icon': '🌬️'},
            {'name': 'Biofuel', 'val': bio_val, 'pct': bio_pct, 'color': '#2ecc71', 'icon': '🌱'},
            {'name': 'PLN / Grid', 'val': grid_val, 'pct': grid_pct, 'color': '#e74c3c', 'icon': '🔌'},
            {'name': 'Battery', 'val': batt_val, 'pct': batt_pct, 'color': '#9b59b6', 'icon': '🔋'}
        ]
        
        # Create card items
        cards = []
        for source in sources:
            card = html.Div([
                html.Div(source['icon'], className='comparison-icon'),
                html.Div([
                    html.Div(source['name'], className='comparison-label'),
                    html.Div(f"{source['val']:.1f} kWh", className='comparison-value'),
                    html.Div(f"{source['pct']:.1f}%", className='comparison-percentage', style={'color': source['color']})
                ], className='comparison-info')
            ], className='comparison-card')
            cards.append(card)
            
        return html.Div([
            html.H4("Komparasi Bauran Energi", className='section-title'),
            html.Div(cards, className='comparison-container')
        ], className='comparison-section')
        
    except Exception as e:
        logger.exception("Failed to create renewable comparison card")
        return error_banner("Monitoring", "Gagal membangun komponen komparasi energi", str(e))
