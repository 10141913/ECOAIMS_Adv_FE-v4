from dash import Dash, Input, Output, html, State, ctx
import os
import time
from ecoaims_frontend.services.contract_registry import _MANIFEST_CACHE

def register_about_callbacks(app: Dash):
    @app.callback(
        Output("about-runtime-info", "children"),
        Input("interval-component", "n_intervals"),
        Input("backend-readiness-store", "data")
    )
    def update_about_runtime_info(n_intervals, readiness_data):
        base_url = "Not Available"
        if isinstance(readiness_data, dict):
            base_url = readiness_data.get("base_url", "Not Available")
        
        build_id = os.getenv("ECOAIMS_FE_BUILD_ID", "dev-build")
        
        contract_hash = _MANIFEST_CACHE.get("manifest_hash", "Not Loaded")
        if isinstance(readiness_data, dict) and "contract_manifest_hash" in readiness_data:
            contract_hash = readiness_data.get("contract_manifest_hash", contract_hash)
            
        return html.Div([
            html.P([html.Strong("Active Base URL: "), str(base_url)], style={'margin': '2px 0'}),
            html.P([html.Strong("FE Build ID: "), str(build_id)], style={'margin': '2px 0'}),
            html.P([html.Strong("Latest Contract Hash: "), str(contract_hash)], style={'margin': '2px 0'}),
        ])

    @app.callback(
        Output("refresh-registry-status", "children"),
        Input("btn-refresh-registry", "n_clicks"),
        prevent_initial_call=True
    )
    def refresh_registry_action(n_clicks):
        if n_clicks:
            from ecoaims_frontend.services.contract_registry import clear_registry_cache
            clear_registry_cache()
            return f"Registry cache cleared at {time.strftime('%H:%M:%S')}. System will fetch latest contract on next request."
        return ""

