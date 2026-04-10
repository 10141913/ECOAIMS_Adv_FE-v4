from dash import html
from ecoaims_frontend.config import CARD_STYLE

def create_about_layout() -> html.Div:
    """
    Creates the layout for the About Tab.
    Provides information about the application, developers, and license.
    """
    
    return html.Div([
        # Header
        html.H2("Tentang ECO-AIMS Dashboard", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

        # --- Application Info ---
        html.Div([
            html.H3("🌱 Aplikasi ECO-AIMS", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.P([
                    "ECOAIMS (Emission & Consumption Optimization using AI-based Monitoring System) ",
                    "adalah platform monitoring energi terbarukan yang dirancang untuk membantu pengguna ",
                    "mengelola dan mengoptimalkan konsumsi energi secara efisien."
                ], style={'lineHeight': '1.6', 'marginBottom': '15px'}),
                
                html.H4("Fitur Utama:", style={'color': '#2c3e50', 'marginTop': '20px'}),
                html.Ul([
                    html.Li("Monitoring real-time sistem energi terbarukan (Solar PV, Wind Turbine, Battery)"),
                    html.Li("Prediksi konsumsi dan produksi energi menggunakan model forecasting"),
                    html.Li("Optimasi distribusi energi berdasarkan prioritas yang dapat dikonfigurasi"),
                    html.Li("Pengelolaan Battery Management System (BMS) dengan kontrol real-time"),
                    html.Li("Pelaporan energi dan emisi CO2 dengan format yang dapat diunduh"),
                    html.Li("Sistem notifikasi dan peringatan untuk kondisi darurat"),
                    html.Li("Mode hybrid: integrasi data sensor live dan simulasi")
                ], style={'lineHeight': '1.8'}),
                
                html.H4("Teknologi yang Digunakan:", style={'color': '#2c3e50', 'marginTop': '20px'}),
                html.Ul([
                    html.Li("Backend: Python dengan framework Dash"),
                    html.Li("Visualisasi: Plotly untuk grafik interaktif"),
                    html.Li("Frontend: HTML/CSS dengan desain responsif"),
                    html.Li("Data Processing: Pandas untuk analisis time-series"),
                    html.Li("Konfigurasi: File JSON untuk pengaturan user")
                ], style={'lineHeight': '1.8'})
            ], style={'marginBottom': '30px'})
        ], style={**CARD_STYLE}),

        # --- Development Team ---
        html.Div([
            html.H3("👥 Tim Pengembang", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.Div([
                    html.H4("Lead Developer", style={'color': '#2c3e50', 'marginBottom': '5px'}),
                    html.P("Juliansyah", style={'fontWeight': 'bold', 'margin': '0'}),
                    html.P("Specialist in Renewable Energy Systems", style={'color': '#7f8c8d', 'fontSize': '14px', 'margin': '2px 0'}),
                    html.P("📧 juliansyah001@student.undip.ac.id; juli001@brin.go.id", style={'color': '#3498db', 'fontSize': '14px', 'margin': '2px 0'})
                ], style={'marginBottom': '20px'}),
                
                html.Div([
                    html.H4("Contributors", style={'color': '#2c3e50', 'marginBottom': '5px'}),
                    html.Div([
                        html.Div([
                            html.Ul([
                                html.Li("Research Team - UNDIP Faculty of Engineering"),
                                html.Li("Mechanical Engineering Department"),
                                html.Li("Semarang, Indonesia")
                            ], style={'lineHeight': '1.6', 'margin': '0', 'paddingLeft': '18px'})
                        ], style={'flex': '1', 'minWidth': '260px'}),
                        html.Div([
                            html.Ul([
                                html.Li("Research Center for Energy Conversion Technology, BRIN"),
                                html.Li("Research Center for Electrical Technology, BRIN"),
                                html.Li("Research Center for Production Machine Technology, BRIN"),
                                html.Li("Research Center for Equipment Manufacturing Technology, BRIN"),
                                html.Li("Research Center for Data Science and Information Technology, BRIN")
                            ], style={'lineHeight': '1.6', 'margin': '0', 'paddingLeft': '18px'})
                        ], style={'flex': '1', 'minWidth': '260px'})
                    ], style={'display': 'flex', 'gap': '30px', 'flexWrap': 'wrap'})
                ], style={'marginBottom': '20px'}),
                
                html.Div([
                    html.H4("Institusi", style={'color': '#2c3e50', 'marginBottom': '5px'}),
                    html.Div([
                        html.Div([
                            html.P("Universitas Diponegoro (UNDIP)", style={'fontWeight': 'bold', 'margin': '0'}),
                            html.P("Fakultas Teknik - Departemen Teknik Mesin", style={'color': '#7f8c8d', 'fontSize': '14px', 'margin': '2px 0'}),
                            html.P("Semarang, Indonesia", style={'color': '#7f8c8d', 'fontSize': '14px', 'margin': '2px 0'})
                        ], style={'flex': '1', 'minWidth': '260px'}),
                        html.Div([
                            html.P("National Research & Innovation Agency Republic of Indonesia (BRIN)", style={'fontWeight': 'bold', 'margin': '0'}),
                            html.P("Research Organization for Energy & Manufacturing", style={'color': '#7f8c8d', 'fontSize': '14px', 'margin': '2px 0'}),
                            html.P("South Tangerang, Indonesia", style={'color': '#7f8c8d', 'fontSize': '14px', 'margin': '2px 0'})
                        ], style={'flex': '1', 'minWidth': '260px'})
                    ], style={'display': 'flex', 'gap': '30px', 'flexWrap': 'wrap'})
                ])
            ])
        ], style={**CARD_STYLE}),

        # --- License & Legal ---
        html.Div([
            html.H3("📄 Lisensi & Legal", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.P([
                    "Aplikasi ini dikembangkan sebagai bagian dari penelitian disertasi ",
                    "di Universitas Diponegoro. Hak cipta dilindungi undang-undang."
                ], style={'lineHeight': '1.6', 'marginBottom': '15px'}),
                
                html.H4("Lisensi Penggunaan:", style={'color': '#2c3e50', 'marginTop': '15px'}),
                html.P("✅ Academic & Research Use: Free", style={'color': '#27ae60', 'margin': '5px 0'}),
                html.P("✅ Personal & Educational Use: Free", style={'color': '#27ae60', 'margin': '5px 0'}),
                html.P("⚠️ Commercial Use: Requires License", style={'color': '#f39c12', 'margin': '5px 0'}),
                html.P("⚠️ Redistribution: Requires Permission", style={'color': '#f39c12', 'margin': '5px 0'}),
                
                html.H4("Disclaimer:", style={'color': '#2c3e50', 'marginTop': '15px'}),
                html.P([
                    "Aplikasi ini disediakan 'sebagaimana adanya' tanpa jaminan apapun. ",
                    "Pengguna bertanggung jawab atas penggunaan dan interpretasi data. ",
                    "Selalu lakukan validasi dengan sistem monitoring profesional untuk aplikasi kritis."
                ], style={'color': '#7f8c8d', 'fontSize': '13px', 'lineHeight': '1.5', 'marginTop': '10px'})
            ])
        ], style={**CARD_STYLE}),

        # --- Version Info ---
        html.Div([
            html.H3("🔢 Informasi Versi & Runtime", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.Div([
                    html.H4("🔧 System Runtime Info:", style={'color': '#2c3e50', 'marginBottom': '10px'}),
                    html.Div(id="about-runtime-info", style={'marginBottom': '15px', 'padding': '10px', 'backgroundColor': '#f4f6f7', 'borderRadius': '5px', 'color': '#2c3e50', 'fontFamily': 'monospace'}),
                    html.Button("Refresh Registry", id="btn-refresh-registry", style={'backgroundColor': '#f39c12', 'color': 'white', 'border': 'none', 'padding': '8px 15px', 'borderRadius': '5px', 'cursor': 'pointer', 'fontWeight': 'bold', 'marginBottom': '15px'}),
                    html.Div(id="refresh-registry-status", style={'color': '#27ae60', 'fontSize': '14px', 'marginBottom': '15px'}),
                ]),

                html.Div([
                    html.P("📝 Version: 2.0.0", style={'fontWeight': 'bold', 'margin': '2px 0'}),
                    html.P("📅 Release Date: March 2026", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                    html.P("🔄 Last Update: March 9, 2026", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                    html.P("🔧 Python Version: 3.8+", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                    html.P("📊 Framework: Dash 2.0+", style={'color': '#7f8c8d', 'margin': '2px 0'})
                ], style={'marginBottom': '15px'}),
                
                html.Div([
                    html.H4("🔄 Update History:", style={'color': '#2c3e50', 'marginBottom': '10px'}),
                    html.Ul([
                        html.Li("v2.0.0 - Added BMS, Reports, Help, About tabs with full integration"),
                        html.Li("v1.5.0 - Implemented hybrid sensor mode with auto-fallback"),
                        html.Li("v1.4.0 - Added Settings tab with persistent configuration"),
                        html.Li("v1.3.0 - Enhanced BMS with real-time monitoring and control"),
                        html.Li("v1.2.0 - Added Optimization tab with energy distribution simulation"),
                        html.Li("v1.1.0 - Implemented Forecasting with hourly and daily predictions"),
                        html.Li("v1.0.0 - Initial release with basic monitoring dashboard")
                    ], style={'lineHeight': '1.6'})
                ])
            ])
        ], style={**CARD_STYLE}),

        # --- Contact & Support ---
        html.Div([
            html.H3("📞 Kontak & Dukungan", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.P("Untuk bantuan teknis, pelaporan bug, atau saran pengembangan:", 
                      style={'marginBottom': '15px'}),
                
                html.Div([
                    html.A("📖 Manual Operator (lihat/cetak PDF)", 
                           href="/manual/operator", 
                           target="_blank",
                           style={'backgroundColor': '#9b59b6', 'color': 'white', 'padding': '10px 20px', 
                                  'textDecoration': 'none', 'borderRadius': '5px', 'marginRight': '10px',
                                  'display': 'inline-block', 'fontWeight': 'bold'}),
                    html.A("📖 Manual Peneliti (lihat/cetak PDF)", 
                           href="/manual/research", 
                           target="_blank",
                           style={'backgroundColor': '#8e44ad', 'color': 'white', 'padding': '10px 20px', 
                                  'textDecoration': 'none', 'borderRadius': '5px',
                                  'display': 'inline-block', 'fontWeight': 'bold'})
                ], style={'textAlign': 'center', 'marginTop': '10px', 'marginBottom': '10px'}),
                
                html.Div([
                    html.A("📧 Email: support@ecoaims.undip.ac.id", 
                          href="mailto:support@ecoaims.undip.ac.id", 
                          style={'backgroundColor': '#3498db', 'color': 'white', 'padding': '10px 20px', 
                                 'textDecoration': 'none', 'borderRadius': '5px', 'marginRight': '10px',
                                 'display': 'inline-block', 'fontWeight': 'bold'}),
                    
                    html.A("🌐 Website: www.ecoaims.undip.ac.id", 
                          href="https://www.ecoaims.undip.ac.id", 
                          target="_blank",
                          style={'backgroundColor': '#2ecc71', 'color': 'white', 'padding': '10px 20px', 
                                 'textDecoration': 'none', 'borderRadius': '5px',
                                 'display': 'inline-block', 'fontWeight': 'bold'})
                ], style={'textAlign': 'center', 'marginTop': '15px'})
            ])
        ], style={**CARD_STYLE})

    ], style={'padding': '20px'})
