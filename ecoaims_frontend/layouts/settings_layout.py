from dash import html, dcc
from ecoaims_frontend.config import CARD_STYLE
from ecoaims_frontend.services.settings_service import load_settings
from ecoaims_frontend.components.precooling.settings_panel import create_precooling_settings_panel

def create_settings_layout() -> html.Div:
    """
    Creates the layout for the Settings Tab.
    Allows users to configure units, capacities, costs, and notifications.
    """
    settings = load_settings()

    lane_panel = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Lane / Mode", style={"marginTop": "0", "color": "#34495e"}),
                            dcc.RadioItems(
                                id="settings-lane-mode-radio",
                                options=[
                                    {"label": "Demo (Canonical)", "value": "demo"},
                                    {"label": "Live (External/Realtime)", "value": "live"},
                                ],
                                value="demo",
                                inline=True,
                                style={"marginBottom": "10px"},
                            ),
                            html.Div(
                                id="settings-runtime-config-summary",
                                style={"fontSize": "12px", "color": "#566573", "marginBottom": "0"},
                            ),
                        ],
                        style={"flex": "1", "minWidth": "320px"},
                    ),
                    html.Div(
                        [
                            html.H3("Live Energy Mode (Enable/Disable)", style={"marginTop": "0", "color": "#34495e"}),
                            dcc.RadioItems(
                                id="settings-live-energy-enabled",
                                options=[
                                    {"label": "Enabled", "value": "enabled"},
                                    {"label": "Disabled", "value": "disabled"},
                                ],
                                value="disabled",
                                inline=True,
                                style={"marginBottom": "0"},
                            ),
                        ],
                        style={"flex": "1", "minWidth": "320px"},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-start"},
            ),
            html.Div(
                [
                    html.Button(
                        "Apply Live Energy Mode",
                        id="settings-live-energy-enabled-apply",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#27ae60",
                            "color": "white",
                            "border": "none",
                            "padding": "8px 12px",
                            "borderRadius": "5px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                        },
                    )
                ],
                style={"textAlign": "center", "marginTop": "10px"},
            ),
            html.Div(id="settings-live-energy-enabled-status", style={"marginTop": "6px", "fontSize": "12px"}),
        ],
        style={**CARD_STYLE, "marginBottom": "15px"},
    )

    system_panel = html.Div(
        [
            html.H2("Pengaturan Sistem", style={"textAlign": "center", "color": "#2c3e50", "marginBottom": "30px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Unit & Kapasitas", style={"color": "#34495e", "borderBottom": "2px solid #ecf0f1", "paddingBottom": "10px"}),
                            html.Div(
                                [
                                    html.Label("Unit Energi (kWh/MWh):", style={"fontWeight": "bold"}),
                                    dcc.Dropdown(
                                        id="settings-unit-energy",
                                        options=[
                                            {"label": "Kilowatt-hour (kWh)", "value": "kWh"},
                                            {"label": "Megawatt-hour (MWh)", "value": "MWh"},
                                        ],
                                        value=settings.get("units", {}).get("energy", "kWh"),
                                        clearable=False,
                                    ),
                                ],
                                style={"marginBottom": "20px"},
                            ),
                            html.Label("Kapasitas Pembangkit (kW):", style={"fontWeight": "bold", "marginTop": "10px"}),
                            html.Div(
                                [
                                    html.Label("Solar PV Capacity:", style={"fontSize": "12px"}),
                                    dcc.Input(
                                        id="settings-cap-solar",
                                        type="number",
                                        value=settings.get("capacities", {}).get("solar_pv", 100),
                                        style={"width": "100%", "marginBottom": "10px"},
                                    ),
                                    html.Label("Wind Turbine Capacity:", style={"fontSize": "12px"}),
                                    dcc.Input(
                                        id="settings-cap-wind",
                                        type="number",
                                        value=settings.get("capacities", {}).get("wind_turbine", 150),
                                        style={"width": "100%", "marginBottom": "10px"},
                                    ),
                                    html.Label("Battery Capacity (kWh):", style={"fontSize": "12px"}),
                                    dcc.Input(
                                        id="settings-cap-battery",
                                        type="number",
                                        value=settings.get("capacities", {}).get("battery", 200),
                                        style={"width": "100%", "marginBottom": "10px"},
                                    ),
                                ]
                            ),
                        ],
                        style={**CARD_STYLE, "width": "30%", "display": "inline-block", "verticalAlign": "top"},
                    ),
                    html.Div(
                        [
                            html.H3("Tarif & Biaya", style={"color": "#34495e", "borderBottom": "2px solid #ecf0f1", "paddingBottom": "10px"}),
                            html.Div(
                                [
                                    html.Label("Tarif Listrik (IDR/kWh):", style={"fontWeight": "bold"}),
                                    dcc.Input(
                                        id="settings-cost-tariff",
                                        type="number",
                                        value=settings.get("costs", {}).get("electricity_tariff", 1444.70),
                                        style={"width": "100%", "marginBottom": "15px"},
                                    ),
                                    html.Label("Harga Biofuel (IDR/Liter):", style={"fontWeight": "bold"}),
                                    dcc.Input(
                                        id="settings-cost-biofuel",
                                        type="number",
                                        value=settings.get("costs", {}).get("biofuel_price", 12000),
                                        style={"width": "100%", "marginBottom": "15px"},
                                    ),
                                    html.Label("Harga Emisi Karbon (IDR/ton):", style={"fontWeight": "bold"}),
                                    dcc.Input(
                                        id="settings-cost-carbon",
                                        type="number",
                                        value=settings.get("costs", {}).get("carbon_price", 30000),
                                        style={"width": "100%", "marginBottom": "15px"},
                                    ),
                                ]
                            ),
                        ],
                        style={**CARD_STYLE, "width": "30%", "display": "inline-block", "verticalAlign": "top"},
                    ),
                    html.Div(
                        [
                            html.H3("Notifikasi", style={"color": "#34495e", "borderBottom": "2px solid #ecf0f1", "paddingBottom": "10px"}),
                            dcc.Checklist(
                                id="settings-notifications",
                                options=[
                                    {"label": " Peringatan Baterai Lemah (<20%)", "value": "low_battery"},
                                    {"label": " Peringatan Pemadaman Grid", "value": "grid_outage"},
                                    {"label": " Peringatan Konsumsi Tinggi", "value": "high_consumption"},
                                ],
                                value=[k for k, v in settings.get("notifications", {}).items() if v],
                                style={"lineHeight": "2", "marginBottom": "20px"},
                            ),
                            html.Hr(),
                            html.H3("Live State Pusher", style={"color": "#34495e"}),
                            html.Label("Interval Push (detik):", style={"fontWeight": "bold"}),
                            dcc.Input(
                                id="settings-live-pusher-interval",
                                type="number",
                                min=1,
                                step=1,
                                value=(settings.get("live_pusher", {}).get("interval_s", 15)),
                                style={"width": "100%", "marginBottom": "10px"},
                            ),
                            html.Hr(),
                            html.Button(
                                "Simpan Pengaturan",
                                id="settings-save-btn",
                                n_clicks=0,
                                style={
                                    "backgroundColor": "#27ae60",
                                    "color": "white",
                                    "border": "none",
                                    "padding": "15px 30px",
                                    "borderRadius": "5px",
                                    "cursor": "pointer",
                                    "fontSize": "16px",
                                    "width": "100%",
                                    "fontWeight": "bold",
                                    "marginTop": "20px",
                                },
                            ),
                            html.Div(id="settings-save-status", style={"marginTop": "10px", "textAlign": "center", "fontWeight": "bold"}),
                        ],
                        style={**CARD_STYLE, "width": "30%", "display": "inline-block", "verticalAlign": "top"},
                    ),
                ],
                style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center"},
            ),
            html.Div(
                [
                    html.H3("Contract Mismatch Summary", style={"marginTop": "0", "color": "#34495e"}),
                    html.Div(id="settings-contract-mismatch-summary"),
                ],
                style={**CARD_STYLE, "marginTop": "15px"},
            ),
        ]
    )

    precooling_panel = create_precooling_settings_panel()

    return html.Div(
        [
            dcc.Store(id="settings-lane-mode-override", storage_type="memory"),
            lane_panel,
            dcc.Tabs(
                [
                    dcc.Tab(
                        label="General",
                        children=system_panel,
                        selected_style={"borderTop": "3px solid #2c3e50", "fontWeight": "bold"},
                        style={"padding": "10px", "fontWeight": "bold", "color": "#7f8c8d"},
                    ),
                    dcc.Tab(
                        label="Precooling",
                        children=precooling_panel,
                        selected_style={"borderTop": "3px solid #8e44ad", "fontWeight": "bold"},
                        style={"padding": "10px", "fontWeight": "bold", "color": "#7f8c8d"},
                    ),
                ]
            )
        ],
        style={"padding": "20px"},
    )
