from dash import html
import logging

logger = logging.getLogger(__name__)

# Constants for CO2 Calculation (approximate values)
# Grid Emission Factor (kg CO2 per kWh) - average for coal/gas mix
GRID_EMISSION_FACTOR = 0.85 
# Equivalencies
# 1 Passenger Vehicle ~ 4.6 metric tons CO2 / year -> ~12.6 kg / day
CAR_EMISSION_FACTOR_DAILY = 12.6 
# 1 LED Lightbulb (10W) -> 0.01 kWh per hour.
LIGHTBULB_WATTAGE = 10

def create_co2_impact_panel(grid_energy_kwh: float, total_consumption_kwh: float) -> html.Div:
    """
    Generates a Dash HTML component displaying CO2 impact and equivalencies.

    Args:
        grid_energy_kwh (float): Energy consumed from the grid in kWh.
        total_consumption_kwh (float): Total energy consumed from all sources in kWh.

    Returns:
        html.Div: A Dash component containing the CO2 impact visualization.
    """
    try:
        # Calculate CO2 (metric tons)
        co2_tons = (grid_energy_kwh * GRID_EMISSION_FACTOR) / 1000 
        
        # Calculate Equivalencies
        cars_equivalent = (co2_tons * 1000) / CAR_EMISSION_FACTOR_DAILY if CAR_EMISSION_FACTOR_DAILY > 0 else 0
        lightbulbs_equivalent = (total_consumption_kwh * 1000) / LIGHTBULB_WATTAGE if LIGHTBULB_WATTAGE > 0 else 0
        
        return html.Div([
            html.Div([
                html.Span(f"{co2_tons:.4f}", style={'fontSize': '36px', 'fontWeight': 'bold', 'color': '#e74c3c'}),
                html.Span(" Ton CO2", style={'fontSize': '18px', 'color': '#7f8c8d'})
            ], style={'textAlign': 'center', 'marginBottom': '15px'}),
            
            html.Div([
                html.P([
                    html.Span("🚗 ", style={'fontSize': '20px'}),
                    f"Setara dengan emisi harian ",
                    html.B(f"{cars_equivalent:.1f}"),
                    " mobil penumpang."
                ], style={'fontSize': '14px', 'margin': '5px 0'}),
                
                html.P([
                    html.Span("💡 ", style={'fontSize': '20px'}),
                    f"Energi ini bisa menyalakan ",
                    html.B(f"{int(lightbulbs_equivalent)}"),
                    " lampu LED (10W)."
                ], style={'fontSize': '14px', 'margin': '5px 0'})
            ])
        ])
    except Exception as e:
        logger.exception("Failed to create CO2 impact panel")
        return html.Div("Error calculating CO2 impact")
