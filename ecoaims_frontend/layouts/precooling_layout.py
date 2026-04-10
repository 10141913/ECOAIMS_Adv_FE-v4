from dash import dcc, html

from ecoaims_frontend.components.precooling.alerts_panel import create_alerts_safety_audit_panel
from ecoaims_frontend.components.precooling.header import create_precooling_header
from ecoaims_frontend.components.precooling.kpi_panel import create_kpi_evaluation_panel
from ecoaims_frontend.components.precooling.optimization_panel import create_optimization_insight_panel
from ecoaims_frontend.components.precooling.overview_cards import create_precooling_overview
from ecoaims_frontend.components.precooling.schedule_panel import create_schedule_and_control
from ecoaims_frontend.components.precooling.scenario_lab import create_scenario_lab
from ecoaims_frontend.components.precooling.thermal_panel import create_thermal_latent_panel
from ecoaims_frontend.config import PRECOOLING_REFRESH_INTERVAL_MS


def create_precooling_layout() -> html.Div:
    return html.Div(
        [
            create_precooling_header(),
            dcc.Loading(create_precooling_overview(), type="circle"),
            dcc.Loading(create_schedule_and_control(), type="circle"),
            dcc.Loading(create_scenario_lab(), type="circle"),
            dcc.Loading(create_thermal_latent_panel(), type="circle"),
            dcc.Loading(create_optimization_insight_panel(), type="circle"),
            dcc.Loading(create_kpi_evaluation_panel(), type="circle"),
            dcc.Loading(create_alerts_safety_audit_panel(), type="circle"),
            dcc.Store(id="precooling-selected-zone", data="floor1_a"),
            dcc.Store(id="precooling-selected-mode"),
            dcc.Store(id="precooling-status-store"),
            dcc.Store(id="precooling-schedule-store"),
            dcc.Store(id="precooling-scenarios-store"),
            dcc.Store(id="precooling-kpi-store"),
            dcc.Store(id="precooling-alerts-store"),
            dcc.Store(id="precooling-audit-store"),
            dcc.Store(id="precooling-sim-result-store"),
            dcc.Store(id="precooling-simulate-request-store"),
            dcc.Store(id="precooling-zones-store"),
            dcc.Store(id="precooling-selected-candidate-store"),
            dcc.Store(id="precooling-settings-snapshot-store"),
            dcc.Store(id="precooling-refresh-signal"),
            dcc.Store(id="precooling-floor-zone-map", data={"1": ["a"], "2": [], "3": []}, storage_type="session"),
            dcc.Interval(id="precooling-interval", interval=PRECOOLING_REFRESH_INTERVAL_MS, n_intervals=0),
        ],
        style={"padding": "12px 20px 20px 20px"},
    )
