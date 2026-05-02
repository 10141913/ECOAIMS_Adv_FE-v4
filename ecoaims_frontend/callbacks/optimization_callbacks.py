import dash
from dash import Input, Output, State
import plotly.graph_objects as go
import requests
from ecoaims_frontend.services.optimization_service import run_energy_optimization
from ecoaims_frontend.services import optimization_service
from ecoaims_frontend.services.operational_policy import effective_feature_decision
from ecoaims_frontend.config import COLORS, LIVE_DATA_SOURCE
from ecoaims_frontend.services.live_data_service import get_live_sensor_data
from ecoaims_frontend.ui.error_ui import error_figure, error_text, status_banner
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.ui.runtime_contract_banner import render_runtime_endpoint_contract_mismatch_banner
from ecoaims_frontend.utils import get_headers

def register_optimization_callbacks(app):
    """
    Registers callbacks for the Optimization Tab.
    """
    
    @app.callback(
        [Output('opt-pie-chart', 'figure'),
         Output('opt-bar-chart', 'figure'),
         Output('opt-recommendation-text', 'children')],
        [Input('opt-run-btn', 'n_clicks'),
         Input('opt-priority-dropdown', 'value'),
         Input('opt-battery-slider', 'value'),
         Input('opt-grid-slider', 'value')],
        [State("backend-readiness-store", "data"), State("opt-optimizer-backend", "value"), State("token-store", "data")],
    )
    def update_optimization_result(n_clicks, priority, battery_capacity, grid_limit, readiness, optimizer_backend, token_data):
        """
        Runs the simulation (or backend call) when parameters change.
        """
        # Trigger simulation even on initial load if desired, or show empty state
        # But n_clicks starts at 0, not None usually
        
        # If simulation hasn't run yet (n_clicks=0), we can either:
        # 1. Return empty figures
        # 2. Run simulation with defaults
        
        # Let's run with defaults so user sees something immediately

        try:
            r = readiness if isinstance(readiness, dict) else {}
            reachable = bool(r.get("backend_reachable"))
            caps = r.get("capabilities") if isinstance(r.get("capabilities"), dict) else {}
            opt_ready = True
            if isinstance(caps.get("optimization"), dict) and caps.get("optimization", {}).get("ready") is False:
                opt_ready = False
            eff = effective_feature_decision("optimization", r)
            if eff.get("final_mode") != "live":
                fig = error_figure("Optimization", "Blocked")
                return fig, fig, status_banner("Optimization", "Optimization blocked", "\n".join([str(x) for x in (eff.get("reason_chain") or [])]))
            if reachable and not opt_ready:
                fig = error_figure("Optimization", "Feature not ready (optimization)")
                return fig, fig, status_banner("Optimization", "Feature not ready (Optimization)", "feature=optimization")

            # Prevent potential callback failure if inputs are None on init
            if priority is None: priority = 'renewable'
            if battery_capacity is None: battery_capacity = 50.0
            if grid_limit is None: grid_limit = 100.0

            # Avoid re-running heavy optimization until user explicitly clicks "run"
            if not n_clicks:
                fig = {"data": [], "layout": {"template": "plotly_white"}}
                ob = str(optimizer_backend or "").strip() or "grid"
                detail = "Pilih parameter lalu klik 'Jalankan Simulasi Optimasi'."
                detail += f"\n\nOptimizer Backend (shared)={ob} (digunakan untuk Precooling/LAEOPF; tidak mengubah hasil /optimize)."
                return fig, fig, status_banner("Optimization", "Ready", detail)
            
            base = effective_base_url(r)

            solar_available = 60.0
            wind_available = 40.0
            total_demand = 120.0
            biofuel_live = None
            state_biofuel = None
            state_soc = None
            state_battery_status = None
            state_battery_energy_kwh = None

            if base:
                try:
                    opt_headers = get_headers(token_data)
                    state = requests.get(f"{base}/dashboard/state?stream_id=default", timeout=3, headers=opt_headers).json()
                    if isinstance(state, dict):
                        pv = float(state.get("pv_power") or 0.0)
                        wt = float(state.get("wind_power") or 0.0)
                        load = float(state.get("load_power") or 0.0)
                        bf = state.get("biofuel_power")
                        if isinstance(bf, (int, float)):
                            state_biofuel = float(bf)
                        soc = state.get("soc")
                        if isinstance(soc, (int, float)):
                            state_soc = float(soc)
                        bs = state.get("battery_status")
                        if isinstance(bs, str) and bs.strip():
                            state_battery_status = str(bs).strip()
                        bek = state.get("battery_energy_kwh")
                        if isinstance(bek, (int, float)):
                            state_battery_energy_kwh = float(bek)
                        if pv >= 0:
                            solar_available = pv
                        if wt >= 0:
                            wind_available = wt
                        if load > 0:
                            total_demand = load
                except Exception:
                    pass

            if LIVE_DATA_SOURCE in {"hybrid", "csv"}:
                try:
                    live = get_live_sensor_data()
                    supply = live.get("supply") if isinstance(live, dict) else {}
                    demand = live.get("demand") if isinstance(live, dict) else {}
                    if isinstance(supply, dict):
                        pv = supply.get("Solar PV")
                        wt = supply.get("Wind Turbine")
                        bf = supply.get("Biofuel")
                        if isinstance(pv, (int, float)):
                            solar_available = float(pv)
                        if isinstance(wt, (int, float)):
                            wind_available = float(wt)
                        if isinstance(bf, (int, float)):
                            biofuel_live = float(bf)
                    if isinstance(demand, dict):
                        s = 0.0
                        for v in demand.values():
                            if isinstance(v, (int, float)):
                                s += float(v)
                        if s > 0:
                            total_demand = s
                except Exception:
                    pass
            
            usage_result, recommendation = run_energy_optimization(
                priority=priority,
                battery_capacity_usage=float(battery_capacity),
                grid_limit=float(grid_limit),
                solar_available=solar_available,
                wind_available=wind_available,
                biofuel_available=float(state_biofuel) if isinstance(state_biofuel, (int, float)) else float(biofuel_live or 0.0),
                total_demand=total_demand,
                skip_backend=not reachable,
                base_url=base,
            )
            
            # Prepare Data for Graphs
            order = ["Solar PV", "Wind Turbine", "Biofuel", "Battery", "PLN/Grid"]
            labels = [k for k in order if k in usage_result]
            values = [float(usage_result.get(k) or 0.0) for k in labels]
            
            # Map colors
            color_map = {
                'Solar PV': COLORS['solar'],
                'Wind Turbine': COLORS['wind'],
                'Biofuel': COLORS['biofuel'],
                'Battery': COLORS['battery'],
                'PLN/Grid': COLORS['grid']
            }
            marker_colors = [color_map.get(label, '#95a5a6') for label in labels]

            # 1. Pie Chart
            pie_fig = go.Figure(data=[go.Pie(
                labels=labels, 
                values=values, 
                hole=.4,
                marker=dict(colors=marker_colors),
                textinfo='label+percent',
                hoverinfo='label+value+percent'
            )])
            pie_fig.update_layout(
                title_text="Proporsi Distribusi Energi",
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20)
            )

            # 2. Bar Chart
            bar_fig = go.Figure(data=[go.Bar(
                x=labels,
                y=values,
                marker_color=marker_colors,
                text=values,
                textposition='auto',
            )])
            bar_fig.update_layout(
                title_text=f"Energi Terpakai (kW) - Total Beban: {total_demand} kW",
                yaxis_title="Daya (kW)",
                xaxis_title="Sumber Energi",
                template='plotly_white',
                margin=dict(l=40, r=40, t=40, b=40)
            )

            rec = str(recommendation or "")
            prefix = "Input simulasi diambil dari dashboard/state (pv/wind/load/biofuel)."
            rec = (prefix + "\n\n" + rec) if rec else prefix
            ob = str(optimizer_backend or "").strip() or "grid"
            rec = (rec + "\n\n" if rec else "") + f"Optimizer Backend (shared)={ob} (digunakan untuk Precooling/LAEOPF; tidak mengubah hasil /optimize)."
            if isinstance(state_soc, (int, float)) or isinstance(state_battery_energy_kwh, (int, float)) or isinstance(state_battery_status, str):
                bits = []
                if isinstance(state_soc, (int, float)):
                    bits.append(f"SOC={float(state_soc)*100.0:.1f}%")
                if isinstance(state_battery_energy_kwh, (int, float)):
                    bits.append(f"BatteryEnergy={float(state_battery_energy_kwh):.1f} kWh")
                if isinstance(state_battery_status, str) and state_battery_status:
                    bits.append(f"BatteryStatus={state_battery_status}")
                if bits:
                    rec = (rec + "\n\n" if rec else "") + "Snapshot backend: " + " | ".join(bits)
            return pie_fig, bar_fig, rec
        except Exception as e:
            fig = error_figure("Optimization", "Simulasi Gagal")
            msg = f"Simulasi Gagal, silakan coba lagi. Detail error: {str(e)}"
            if "runtime_endpoint_contract_mismatch" in msg:
                last = optimization_service.get_last_optimization_endpoint_contract()
                details = last.get("normalized") if isinstance(last, dict) else None
                banner = render_runtime_endpoint_contract_mismatch_banner(details)
                return fig, fig, banner
            return fig, fig, status_banner("Optimization Error", "Simulasi Gagal", msg)

    @app.callback(
        [
            Output("optimizer-backend-store", "data"),
            Output("opt-optimizer-backend", "value"),
            Output("precooling-optimizer-backend", "value"),
        ],
        [Input("opt-optimizer-backend", "value"), Input("precooling-optimizer-backend", "value")],
        State("optimizer-backend-store", "data"),
    )
    def sync_optimizer_backend_store(opt_value, prec_value, current):
        cur = current if isinstance(current, dict) else {}
        cur_val = cur.get("value")
        triggered = ""
        if dash.callback_context and getattr(dash.callback_context, "triggered", None):
            triggered = str(dash.callback_context.triggered[0].get("prop_id") or "")
        if triggered.startswith("opt-optimizer-backend."):
            next_val = opt_value
        elif triggered.startswith("precooling-optimizer-backend."):
            next_val = prec_value
        else:
            next_val = opt_value or prec_value or cur_val or "grid"
        if not isinstance(next_val, str) or not next_val.strip():
            next_val = "grid"
        next_val = next_val.strip()
        store_out = dash.no_update if next_val == cur_val else {"value": next_val}
        opt_out = dash.no_update if triggered.startswith("opt-optimizer-backend.") else next_val
        prec_out = dash.no_update if triggered.startswith("precooling-optimizer-backend.") else next_val
        return store_out, opt_out, prec_out
