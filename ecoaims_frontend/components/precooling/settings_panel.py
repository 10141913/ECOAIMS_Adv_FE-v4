from dash import dcc, html

from ecoaims_frontend.components.precooling.styles import CARD_STYLE_TIGHT, PREC_COLORS, SECTION_TITLE_STYLE


def _section(title: str, children):
    return html.Div(
        [
            html.H3(title, style=SECTION_TITLE_STYLE),
            html.Div(children),
        ],
        style={**CARD_STYLE_TIGHT},
    )


def _field(label: str, control):
    return html.Div(
        [
            html.Div(label, style={"fontSize": "12px", "color": PREC_COLORS["muted"], "marginBottom": "6px"}),
            control,
        ],
        style={"flex": "1", "minWidth": "260px"},
    )


def _badge(id_: str):
    return html.Div(
        id=id_,
        style={
            "display": "inline-block",
            "padding": "4px 10px",
            "borderRadius": "999px",
            "backgroundColor": "#bdc3c7",
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "12px",
            "minWidth": "140px",
            "textAlign": "center",
        },
        children="Unknown",
    )


def create_precooling_settings_panel() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H2("Settings > Precooling", style={"margin": "0", "color": PREC_COLORS["text"]}),
                            html.Div(
                                "Konfigurasi parameter, constraint, objective weights, fallback rules, dan mode operasi Precooling / LAEOPF.",
                                style={"color": PREC_COLORS["muted"], "marginTop": "4px"},
                            ),
                            html.Div(
                                "Scope di sini adalah scope konfigurasi (load/validate/save/apply/reset) untuk Settings Precooling.",
                                style={"color": PREC_COLORS["muted"], "marginTop": "6px", "fontSize": "12px"},
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div("Scope (Lantai)", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                            dcc.RadioItems(
                                                id="precoolset-floor",
                                                options=[
                                                    {"label": "Lantai 1", "value": "1"},
                                                    {"label": "Lantai 2", "value": "2"},
                                                    {"label": "Lantai 3", "value": "3"},
                                                ],
                                                value="1",
                                                inline=True,
                                                style={"fontSize": "12px", "color": PREC_COLORS["text"]},
                                                inputStyle={"marginRight": "6px"},
                                                labelStyle={"marginRight": "10px"},
                                                persistence=True,
                                                persistence_type="session",
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        [
                                            html.Div("Zone", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}),
                                            dcc.Checklist(
                                                id="precoolset-zone",
                                                options=[
                                                    {"label": "A", "value": "a"},
                                                    {"label": "B", "value": "b"},
                                                    {"label": "C", "value": "c"},
                                                ],
                                                value=["a"],
                                                inline=True,
                                                style={"fontSize": "12px", "color": PREC_COLORS["text"]},
                                                inputStyle={"marginRight": "6px"},
                                                labelStyle={"marginRight": "10px"},
                                                persistence=True,
                                                persistence_type="session",
                                            ),
                                            html.Button(
                                                "Clear Zones",
                                                id="precoolset-clear-zones-btn",
                                                n_clicks=0,
                                                style={
                                                    "backgroundColor": "#bdc3c7",
                                                    "color": "white",
                                                    "border": "none",
                                                    "padding": "6px 10px",
                                                    "borderRadius": "6px",
                                                    "cursor": "pointer",
                                                    "fontWeight": "bold",
                                                    "marginTop": "6px",
                                                },
                                            ),
                                            html.Div(
                                                id="precoolset-zone-selection-error",
                                                style={"marginTop": "6px", "fontSize": "12px", "color": PREC_COLORS["alert"]},
                                            ),
                                        ],
                                        style={"marginTop": "6px"},
                                    ),
                                ]
                            ),
                            html.Div([html.Div("Config Status", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}), _badge("precoolset-config-badge")]),
                            html.Div([html.Div("Dirty", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}), _badge("precoolset-dirty-badge")], style={"marginLeft": "10px"}),
                            html.Div([html.Div("Validation", style={"fontSize": "11px", "color": PREC_COLORS["muted"]}), _badge("precoolset-validation-badge")], style={"marginLeft": "10px"}),
                            html.Div(
                                [
                                    html.Div(
                                        "Scope operasi saat ini: -",
                                        id="precoolset-op-scope-indicator",
                                        style={"fontSize": "12px", "color": PREC_COLORS["muted"], "maxWidth": "360px"},
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Salin scope dari Precooling",
                                                id="precoolset-copy-from-precooling-btn",
                                                n_clicks=0,
                                                style={
                                                    "backgroundColor": "#95a5a6",
                                                    "color": "white",
                                                    "border": "none",
                                                    "padding": "6px 10px",
                                                    "borderRadius": "6px",
                                                    "cursor": "pointer",
                                                    "fontWeight": "bold",
                                                    "fontSize": "12px",
                                                },
                                            ),
                                            html.Button(
                                                "Gunakan scope ini di Precooling",
                                                id="precoolset-use-in-precooling-btn",
                                                n_clicks=0,
                                                style={
                                                    "backgroundColor": "#2980b9",
                                                    "color": "white",
                                                    "border": "none",
                                                    "padding": "6px 10px",
                                                    "borderRadius": "6px",
                                                    "cursor": "pointer",
                                                    "fontWeight": "bold",
                                                    "fontSize": "12px",
                                                },
                                            ),
                                        ],
                                        style={"display": "flex", "gap": "8px", "marginTop": "6px"},
                                    ),
                                    html.Div(
                                        id="precoolset-scope-sync-msg",
                                        style={"marginTop": "6px", "fontSize": "12px", "color": PREC_COLORS["muted"]},
                                    ),
                                ],
                                style={"marginLeft": "14px"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "flex-end"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "16px"},
            ),
            html.Div(
                [
                    html.Button(
                        "Load Current Settings",
                        id="precoolset-load-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["cooling"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                        },
                    ),
                    html.Button(
                        "Validate Settings",
                        id="precoolset-validate-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["ai"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Button(
                        "Save Settings",
                        id="precoolset-save-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["renewable"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Button(
                        "Reset to Default",
                        id="precoolset-reset-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#34495e",
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Button(
                        "Apply to Precooling Engine",
                        id="precoolset-apply-btn",
                        n_clicks=0,
                        style={
                            "backgroundColor": PREC_COLORS["battery"],
                            "color": "white",
                            "border": "none",
                            "padding": "10px 14px",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "fontWeight": "bold",
                            "marginLeft": "10px",
                        },
                    ),
                    html.Div(id="precoolset-action-msg", style={"marginLeft": "14px", "fontSize": "12px", "color": PREC_COLORS["muted"]}),
                ],
                style={"marginTop": "14px", "display": "flex", "alignItems": "center", "flexWrap": "wrap"},
            ),
            dcc.Store(id="precoolset-bundle-store"),
            dcc.Store(id="precoolset-form-store"),
            dcc.Store(id="precoolset-validation-store"),
            dcc.Store(id="precoolset-dirty-store"),
            dcc.Store(id="precoolset-zones-store"),
            html.Div(id="precoolset-warning", style={"marginTop": "10px"}),
            html.Div(
                [
                    _section(
                        "General Settings",
                        html.Div(
                            [
                                _field(
                                    "Enable Precooling",
                                    dcc.Checklist(
                                        id="precoolset-enable-precooling",
                                        options=[{"label": "Enabled", "value": "enabled"}],
                                        value=["enabled"],
                                    ),
                                ),
                                _field(
                                    "Enable LAEOPF Mode",
                                    dcc.Checklist(
                                        id="precoolset-enable-laeopf",
                                        options=[{"label": "Enabled", "value": "enabled"}],
                                        value=["enabled"],
                                    ),
                                ),
                                _field(
                                    "Default Operation Mode",
                                    dcc.Dropdown(
                                        id="precoolset-default-mode",
                                        options=[
                                            {"label": "Monitoring", "value": "monitoring"},
                                            {"label": "Advisory", "value": "advisory"},
                                            {"label": "Auto", "value": "auto"},
                                            {"label": "Fallback", "value": "fallback"},
                                        ],
                                        value="monitoring",
                                        clearable=False,
                                    ),
                                ),
                                _field(
                                    "Default Scenario Type",
                                    dcc.Dropdown(
                                        id="precoolset-default-scenario",
                                        options=[
                                            {"label": "Baseline", "value": "baseline"},
                                            {"label": "Rule-Based", "value": "rule-based"},
                                            {"label": "Optimized", "value": "optimized"},
                                        ],
                                        value="optimized",
                                        clearable=False,
                                    ),
                                ),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Time Window",
                        html.Div(
                            [
                                _field("Earliest Allowed Start Time (HH:MM)", dcc.Input(id="precoolset-earliest", type="text", value="05:00", style={"width": "100%"})),
                                _field("Latest Allowed Start Time (HH:MM)", dcc.Input(id="precoolset-latest", type="text", value="10:00", style={"width": "100%"})),
                                _field("Minimum Precooling Duration (min)", dcc.Input(id="precoolset-min-dur", type="number", value=30, min=1, step=1, style={"width": "100%"})),
                                _field("Maximum Precooling Duration (min)", dcc.Input(id="precoolset-max-dur", type="number", value=120, min=1, step=1, style={"width": "100%"})),
                                _field(
                                    "Weekday Profile Enabled",
                                    dcc.Checklist(id="precoolset-weekday", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"]),
                                ),
                                _field(
                                    "Weekend Profile Enabled",
                                    dcc.Checklist(id="precoolset-weekend", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"]),
                                ),
                                _field(
                                    "Holiday Behavior",
                                    dcc.Dropdown(
                                        id="precoolset-holiday-behavior",
                                        options=[{"label": "Weekday", "value": "weekday"}, {"label": "Weekend", "value": "weekend"}, {"label": "Disable", "value": "disable"}],
                                        value="weekend",
                                        clearable=False,
                                    ),
                                ),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Comfort Limits",
                        html.Div(
                            [
                                _field("Minimum Indoor Temperature (°C)", dcc.Input(id="precoolset-min-temp", type="number", value=22, step=0.1, style={"width": "100%"})),
                                _field("Maximum Indoor Temperature (°C)", dcc.Input(id="precoolset-max-temp", type="number", value=27, step=0.1, style={"width": "100%"})),
                                _field("Pre-Occupancy Target Temperature (°C)", dcc.Input(id="precoolset-target-temp", type="number", value=24, step=0.1, style={"width": "100%"})),
                                _field("Minimum RH (%)", dcc.Input(id="precoolset-min-rh", type="number", value=45, step=0.5, style={"width": "100%"})),
                                _field("Maximum RH (%)", dcc.Input(id="precoolset-max-rh", type="number", value=65, step=0.5, style={"width": "100%"})),
                                _field("Pre-Occupancy Target RH (%)", dcc.Input(id="precoolset-target-rh", type="number", value=55, step=0.5, style={"width": "100%"})),
                                _field(
                                    "Comfort Priority Level",
                                    dcc.Dropdown(
                                        id="precoolset-comfort-priority",
                                        options=[{"label": "Low", "value": "low"}, {"label": "Medium", "value": "medium"}, {"label": "High", "value": "high"}],
                                        value="medium",
                                        clearable=False,
                                    ),
                                ),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "HVAC Constraints",
                        html.Div(
                            [
                                _field("Cooling Capacity Limit (kW)", dcc.Input(id="precoolset-cap-limit", type="number", value=500, min=0, step=1, style={"width": "100%"})),
                                _field("Minimum Runtime (min)", dcc.Input(id="precoolset-min-runtime", type="number", value=15, min=0, step=1, style={"width": "100%"})),
                                _field("Maximum Runtime (min)", dcc.Input(id="precoolset-max-runtime", type="number", value=180, min=0, step=1, style={"width": "100%"})),
                                _field("Setpoint Lower Bound (°C)", dcc.Input(id="precoolset-sp-lo", type="number", value=20, step=0.1, style={"width": "100%"})),
                                _field("Setpoint Upper Bound (°C)", dcc.Input(id="precoolset-sp-hi", type="number", value=26, step=0.1, style={"width": "100%"})),
                                _field("RH Lower Bound (%)", dcc.Input(id="precoolset-rh-lo", type="number", value=40, step=0.5, style={"width": "100%"})),
                                _field("RH Upper Bound (%)", dcc.Input(id="precoolset-rh-hi", type="number", value=70, step=0.5, style={"width": "100%"})),
                                _field(
                                    "Anti Short Cycle Enabled",
                                    dcc.Checklist(id="precoolset-anti-short", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"]),
                                ),
                                _field(
                                    "Ramp Limit Enabled",
                                    dcc.Checklist(id="precoolset-ramp-limit", options=[{"label": "Enabled", "value": "enabled"}], value=[]),
                                ),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Building Parameters",
                        html.Div(
                            [
                                _field(
                                    "Thermal Mass Class",
                                    dcc.Dropdown(
                                        id="precoolset-thermal-mass",
                                        options=[{"label": "Light", "value": "light"}, {"label": "Medium", "value": "medium"}, {"label": "Heavy", "value": "heavy"}],
                                        value="medium",
                                        clearable=False,
                                    ),
                                ),
                                _field("Floor Area (m²)", dcc.Input(id="precoolset-floor-area", type="number", value=1000, min=0, step=1, style={"width": "100%"})),
                                _field("Volume (m³)", dcc.Input(id="precoolset-volume", type="number", value=3000, min=0, step=1, style={"width": "100%"})),
                                _field("U-value Wall", dcc.Input(id="precoolset-u-wall", type="number", value=1.5, min=0, step=0.01, style={"width": "100%"})),
                                _field("U-value Roof", dcc.Input(id="precoolset-u-roof", type="number", value=1.0, min=0, step=0.01, style={"width": "100%"})),
                                _field("SHGC", dcc.Input(id="precoolset-shgc", type="number", value=0.4, min=0, step=0.01, style={"width": "100%"})),
                                _field("ACH / Infiltration Rate", dcc.Input(id="precoolset-ach", type="number", value=0.5, min=0, step=0.01, style={"width": "100%"})),
                                _field("Internal Gain Estimate (W/m²)", dcc.Input(id="precoolset-internal-gain", type="number", value=10, min=0, step=0.1, style={"width": "100%"})),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Energy Coordination",
                        html.Div(
                            [
                                _field("Prioritize PV Surplus", dcc.Checklist(id="precoolset-pv", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Allow Battery Support for Precooling", dcc.Checklist(id="precoolset-batt-support", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Disallow Grid-Only Precooling", dcc.Checklist(id="precoolset-disallow-grid", options=[{"label": "Enabled", "value": "enabled"}], value=[])),
                                _field("Enable Tariff-Aware Strategy", dcc.Checklist(id="precoolset-tariff-aware", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Enable CO2-Aware Strategy", dcc.Checklist(id="precoolset-co2-aware", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Battery SOC Minimum (0..1)", dcc.Input(id="precoolset-soc-min", type="number", value=0.2, min=0, max=1, step=0.01, style={"width": "100%"})),
                                _field("Battery SOC Maximum (0..1)", dcc.Input(id="precoolset-soc-max", type="number", value=0.95, min=0, max=1, step=0.01, style={"width": "100%"})),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Objective Weights",
                        html.Div(
                            [
                                _field("Weight Cost", dcc.Slider(id="precoolset-w-cost", min=0, max=1, step=0.05, value=0.35)),
                                _field("Weight CO2", dcc.Slider(id="precoolset-w-co2", min=0, max=1, step=0.05, value=0.25)),
                                _field("Weight Peak Reduction", dcc.Slider(id="precoolset-w-peak", min=0, max=1, step=0.05, value=0.2)),
                                _field("Weight Comfort", dcc.Slider(id="precoolset-w-comfort", min=0, max=1, step=0.05, value=0.15)),
                                _field("Weight Battery Health", dcc.Slider(id="precoolset-w-battery", min=0, max=1, step=0.05, value=0.05)),
                            ],
                            style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Fallback Rules",
                        html.Div(
                            [
                                _field("Enable Fallback", dcc.Checklist(id="precoolset-enable-fallback", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Fallback Start Time (HH:MM)", dcc.Input(id="precoolset-fb-start", type="text", value="00:00", style={"width": "100%"})),
                                _field("Fallback Duration (min)", dcc.Input(id="precoolset-fb-dur", type="number", value=60, min=1, step=1, style={"width": "100%"})),
                                _field("Fallback Temperature (°C)", dcc.Input(id="precoolset-fb-temp", type="number", value=25, step=0.1, style={"width": "100%"})),
                                _field("Fallback RH (%)", dcc.Input(id="precoolset-fb-rh", type="number", value=60, step=0.5, style={"width": "100%"})),
                                _field("Trigger on Missing Data", dcc.Checklist(id="precoolset-trig-missing", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Trigger on Optimizer Failure", dcc.Checklist(id="precoolset-trig-optim", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Trigger on Battery Constraint", dcc.Checklist(id="precoolset-trig-batt", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                                _field("Trigger on Comfort Risk", dcc.Checklist(id="precoolset-trig-comfort", options=[{"label": "Enabled", "value": "enabled"}], value=["enabled"])),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                    _section(
                        "Advanced / Research Settings",
                        html.Div(
                            [
                                _field("Enable Latent Model", dcc.Checklist(id="precoolset-adv-latent", options=[{"label": "Beta", "value": "enabled"}], value=["enabled"])),
                                _field("Enable Exergy Model", dcc.Checklist(id="precoolset-adv-exergy", options=[{"label": "Beta", "value": "enabled"}], value=["enabled"])),
                                _field("Enable Psychrometric Diagnostics", dcc.Checklist(id="precoolset-adv-psy", options=[{"label": "Experimental", "value": "enabled"}], value=[])),
                                _field("Enable Candidate Ranking Debug", dcc.Checklist(id="precoolset-adv-debug", options=[{"label": "Experimental", "value": "enabled"}], value=[])),
                                _field("Enable Experimental Scenario Runner", dcc.Checklist(id="precoolset-adv-runner", options=[{"label": "Experimental", "value": "enabled"}], value=[])),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                        ),
                    ),
                ],
                style={"marginTop": "12px", "display": "flex", "flexDirection": "column", "gap": "10px"},
            ),
        ],
        style={"padding": "10px"},
    )
