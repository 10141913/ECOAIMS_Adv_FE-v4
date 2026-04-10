from dash import dcc, html
from dash import dash_table

from ecoaims_frontend.config import CARD_STYLE


def create_home_layout() -> html.Div:
    return html.Div(
        [
            html.H2("Home", style={"textAlign": "center", "color": "#2c3e50", "marginBottom": "20px"}),
            html.P(
                "Grafik dan gauge real-time ada di tab Monitoring (dibuka otomatis saat memuat aplikasi). "
                "Tab Home berisi panduan operator, ringkasan kontrak, dan doctor report.",
                style={"textAlign": "center", "color": "#566573", "fontSize": "14px", "maxWidth": "900px", "margin": "0 auto 18px auto", "lineHeight": "1.5"},
            ),
            html.Div(
                [
                    html.H3("Ringkasan Sistem", style={"marginTop": "0", "color": "#34495e"}),
                    html.P(
                        "ECOAIMS adalah dashboard monitoring dan optimasi energi yang mengintegrasikan monitoring real-time, forecasting, optimasi, BMS, pelaporan, dan strategi precooling (LAEOPF).",
                        style={"color": "#7f8c8d", "lineHeight": "1.6"},
                    ),
                    html.H4("Navigasi Cepat", style={"color": "#2c3e50", "marginTop": "20px"}),
                    html.Ul(
                        [
                            html.Li("Monitoring: kondisi energi real-time + Sensor Health"),
                            html.Li("Forecasting: prediksi konsumsi/supply"),
                            html.Li("Optimization: simulasi strategi distribusi energi"),
                            html.Li("Precooling / LAEOPF: simulasi, rekomendasi, KPI, audit, dan kontrol precooling"),
                            html.Li("BMS: monitoring dan kontrol baterai"),
                            html.Li("Reports: ringkasan KPI dan export laporan"),
                            html.Li("Settings: konfigurasi parameter sistem"),
                        ],
                        style={"color": "#7f8c8d", "lineHeight": "1.8"},
                    ),
                ],
                style={**CARD_STYLE},
            ),
            html.Div(
                [
                    html.H3("Panduan Menjalankan Sistem", style={"marginTop": "0", "color": "#34495e"}),
                    html.Div(id="home-runbook-source", style={"color": "#7f8c8d", "fontSize": "12px", "marginBottom": "10px"}),
                    dcc.Markdown(id="home-runbook-md", style={"color": "#2c3e50", "lineHeight": "1.65"}),
                ],
                style={**CARD_STYLE, "marginTop": "15px"},
            ),
            html.Div(
                [
                    html.H3("Contract Mismatch Summary", style={"marginTop": "0", "color": "#34495e"}),
                    html.Div(id="home-contract-mismatch-summary"),
                ],
                style={**CARD_STYLE, "marginTop": "15px"},
            ),
            html.Div(
                [
                    html.H3("Doctor Report", style={"marginTop": "0", "color": "#34495e"}),
                    dcc.Store(id="home-doctor-snapshot-store", storage_type="local"),
                    html.Div(
                        [
                            html.Button(
                                "Refresh Doctor Report",
                                id="home-doctor-refresh-btn",
                                style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold"},
                            ),
                            html.Button(
                                "Download Doctor Report (JSON)",
                                id="home-doctor-download-btn",
                                style={"padding": "10px 14px", "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold"},
                            ),
                            html.Div(id="home-doctor-msg", style={"marginLeft": "12px", "fontSize": "12px", "color": "#566573"}),
                        ],
                        style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "10px"},
                    ),
                    html.Div(id="home-doctor-contract-change-banner", style={"marginTop": "10px"}),
                    dcc.Textarea(id="home-doctor-text", value="{}", style={"width": "100%", "height": "220px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "10px"}),
                    dcc.Clipboard(target_id="home-doctor-text", title="Copy Doctor Report"),
                    dcc.Download(id="home-doctor-download"),
                ],
                style={**CARD_STYLE, "marginTop": "15px"},
            ),
        ],
        style={"padding": "20px"},
    )
