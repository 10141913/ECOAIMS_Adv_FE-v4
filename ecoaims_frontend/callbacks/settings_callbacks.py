import dash
from dash import Input, Output, State, no_update
from ecoaims_frontend.services.settings_service import save_settings, load_settings
from ecoaims_frontend.services.system_runtime_api import get_runtime_config, post_live_energy_file, post_live_energy_enabled
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.utils import get_headers

def register_settings_callbacks(app):
    """
    Registers callbacks for the Settings Tab.
    """
    
    @app.callback(
        Output('settings-save-status', 'children'),
        Input('settings-save-btn', 'n_clicks'),
        [State('settings-unit-energy', 'value'),
         State('settings-cap-solar', 'value'),
         State('settings-cap-wind', 'value'),
         State('settings-cap-battery', 'value'),
         State('settings-cost-tariff', 'value'),
         State('settings-cost-biofuel', 'value'),
         State('settings-cost-carbon', 'value'),
         State('settings-notifications', 'value'),
         State('settings-live-pusher-interval', 'value')]
    )
    def save_settings_callback(n_clicks, unit, cap_solar, cap_wind, cap_batt,
                               cost_tariff, cost_bio, cost_carbon, notifications,
                               live_pusher_interval):
        """
        Saves user settings when the button is clicked.
        """
        if n_clicks is None or n_clicks == 0:
            return ""

        try:
            notifications = notifications or []
            # Construct new settings dictionary
            new_settings = {
                "units": {
                    "energy": unit,
                    "power": "kW", # Hardcoded for now, could be dynamic
                    "emission": "ton CO2"
                },
                "capacities": {
                    "solar_pv": float(cap_solar or 0),
                    "wind_turbine": float(cap_wind or 0),
                    "battery": float(cap_batt or 0)
                },
                "costs": {
                    "electricity_tariff": float(cost_tariff or 0),
                    "biofuel_price": float(cost_bio or 0),
                    "carbon_price": float(cost_carbon or 0)
                },
                "notifications": {
                    "low_battery": 'low_battery' in notifications,
                    "grid_outage": 'grid_outage' in notifications,
                    "high_consumption": 'high_consumption' in notifications
                },
                "live_pusher": {
                    "interval_s": int(live_pusher_interval or 15)
                }
            }
            
            success = save_settings(new_settings)
            
            if success:
                return "✅ Pengaturan berhasil disimpan!"
            else:
                return "❌ Gagal menyimpan pengaturan."
                
        except (ValueError, TypeError):
            return "❌ Input tidak valid. Harap masukkan angka yang benar."
        except Exception as e:
            return f"❌ Terjadi kesalahan: {str(e)}"

    @app.callback(
        Output("settings-runtime-config-summary", "children"),
        Output("settings-live-energy-enabled", "disabled"),
        Input("backend-readiness-interval", "n_intervals"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=False,
    )
    def update_runtime_config_panel(n_intervals, readiness, token_data):
        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        auth_headers = get_headers(token_data)
        data, err = get_runtime_config(base_url=base_url, headers=auth_headers)
        summary = ""
        if err:
            msg = err
            if "status=404" in msg or "Not Found" in msg:
                msg = "endpoint_not_supported:/api/system/runtime-config (404)"
            summary = f"runtime-config unavailable: {msg}"
        else:
            mode = (data or {}).get("mode") or (data or {}).get("lane") or "demo"
            info_lines = []
            for k in ("mode", "lane", "source", "version", "applied", "updated"):
                v = (data or {}).get(k)
                if v is not None:
                    info_lines.append(f"{k}: {v}")
            summary = " • ".join(info_lines) if info_lines else ""
        return summary, False

    @app.callback(
        Output("settings-lane-mode-radio", "value", allow_duplicate=True),
        Output("settings-live-energy-enabled", "value", allow_duplicate=True),
        Input("settings-lane-mode-radio", "value"),
        Input("settings-live-energy-enabled", "value"),
        Input("settings-live-energy-enabled-apply", "n_clicks"),
        prevent_initial_call=True,
    )
    def sync_lane_mode_and_live_energy(lane_mode, live_energy_enabled, apply_clicks):
        triggered = getattr(getattr(dash, "ctx", None), "triggered_id", None)

        if triggered == "settings-lane-mode-radio":
            desired = "enabled" if lane_mode == "live" else "disabled"
            if desired == live_energy_enabled:
                return no_update, no_update
            return no_update, desired

        if triggered == "settings-live-energy-enabled":
            if str(live_energy_enabled).lower() != "enabled":
                return no_update, no_update
            if lane_mode == "live":
                return no_update, no_update
            return "live", no_update

        if triggered == "settings-live-energy-enabled-apply":
            lane_out = "live" if lane_mode != "live" else no_update
            live_out = "enabled" if live_energy_enabled != "enabled" else no_update
            return lane_out, live_out

        return no_update, no_update

    @app.callback(
        Output("settings-live-energy-enabled-status", "children"),
        Output("settings-lane-mode-override", "data"),
        Input("settings-live-energy-enabled-apply", "n_clicks"),
        State("settings-live-energy-enabled", "value"),
        State("backend-readiness-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
    )
    def apply_live_energy_enabled(n_clicks, value, readiness, token_data):
        if not n_clicks:
            return "", no_update
        enabled = True if str(value).lower() == "enabled" else False
        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        auth_headers = get_headers(token_data)
        data, err = post_live_energy_enabled(enabled, base_url=base_url, headers=auth_headers)
        if err:
            msg = err
            if "status=404" in msg or "Not Found" in msg:
                msg = "endpoint_not_supported:/api/system/runtime-config/live-energy-file (404)"
            return f"❌ Gagal set live-energy enabled={enabled}: {msg}", no_update
        new_lane = "live" if enabled else "demo"
        return f"✅ Live-energy enabled={enabled}. Response: {(data or {}).get('status') or 'ok'}", new_lane
