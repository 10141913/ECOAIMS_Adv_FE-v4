from dash import html, dcc
from ecoaims_frontend.config import CARD_STYLE

def create_help_layout() -> html.Div:
    """
    Creates the layout for the Help/FAQ Tab.
    Provides user guide, FAQ, and support contact information.
    """
    
    faq_items = [
        {
            "question": "Bagaimana cara membaca dashboard Monitoring?",
            "answer": "Dashboard Monitoring menampilkan status real-time sistem energi. \
                      Speedometer menunjukkan persentase penggunaan dari kapasitas maksimal. \
                      Grafik tren menampilkan pola konsumsi selama 24 jam terakhir. \
                      Kartu Sensor Health menunjukkan status konektivitas sensor."
        },
        {
            "question": "Apa itu mode Hybrid pada sensor?",
            "answer": "Mode Hybrid memungkinkan sistem otomatis beralih antara data sensor \
                      asli (LIVE) dan data simulasi (SIMULATED) jika sensor tidak tersedia. \
                      Ini memastikan dashboard tetap berfungsi meskipun ada sensor yang offline."
        },
        {
            "question": "Bagaimana cara menggunakan fitur Forecasting?",
            "answer": "Pilih periode prediksi (Per Jam atau Per Hari) dari dropdown. \
                      Sistem akan menampilkan prediksi konsumsi energi dan produksi \
                      energi terbarukan. Grafik akurasi menunjukkan performa model prediksi."
        },
        {
            "question": "Apa fungsi tab Optimization?",
            "answer": "Tab Optimization memungkinkan Anda mensimulasasi strategi \
                      distribusi energi. Pilih prioritas energi (Renewable, Battery, \
                      atau Grid) dan atur parameter baterai untuk melihat hasil \
                      optimasi dengan grafik dan rekomendasi sistem."
        },
        {
            "question": "Bagaimana cara mengontrol Baterai (BMS)?",
            "answer": "Gunakan tombol Start Charging untuk mengisi baterai, \
                      Start Discharging untuk mengosongkan, atau Stop System \
                      untuk menghentikan. Sistem akan otomatis berhenti pada \
                      batas SOC 20% (bawah) dan 80% (atas) untuk keamanan."
        },
        {
            "question": "Bagaimana cara mengunduh laporan?",
            "answer": "Pergi ke tab Reports, pilih periode dan format (CSV/PDF), \
                      lalu klik Generate Report. Sistem akan menghasilkan \
                      laporan lengkap tentang konsumsi, efisiensi, dan emisi CO2."
        }
    ]
    
    return html.Div([
        # Header
        html.H2("Pusat Bantuan & FAQ", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),

        # --- Quick Start Guide ---
        html.Div([
            html.H3("📚 Panduan Cepat", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.H4("1. Memulai Aplikasi", style={'color': '#2c3e50'}),
                html.Ol([
                    html.Li("Pastikan Python 3.x terinstal di sistem Anda"),
                    html.Li("Aktifkan virtual environment: source ecoaims_frontend_env/bin/activate"),
                    html.Li("Jalankan aplikasi: python -m ecoaims_frontend.app"),
                    html.Li("Buka browser dan akses: http://127.0.0.1:8050/")
                ], style={'lineHeight': '1.8'}),
                
                html.H4("2. Navigasi Dasar", style={'color': '#2c3e50', 'marginTop': '20px'}),
                html.Ul([
                    html.Li("🏠 Monitoring: Lihat status real-time sistem energi"),
                    html.Li("📊 Forecasting: Prediksi konsumsi dan produksi energi"),
                    html.Li("⚡ Optimization: Simulasi strategi distribusi energi"),
                    html.Li("🔋 BMS: Kontrol dan monitoring baterai"),
                    html.Li("📈 Reports: Unduh laporan performa sistem"),
                    html.Li("⚙️ Settings: Konfigurasi parameter sistem"),
                    html.Li("❓ Help/FAQ: Panduan penggunaan (Anda di sini)")
                ], style={'lineHeight': '1.8'})
            ], style={'marginBottom': '30px'})
        ], style={**CARD_STYLE}),

        # --- FAQ Section ---
        html.Div([
            html.H3("❓ Pertanyaan Umum (FAQ)", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.Div([
                    html.H4(f"Q: {item['question']}", style={'color': '#2c3e50', 'marginBottom': '10px'}),
                    html.P(f"A: {item['answer']}", style={'color': '#7f8c8d', 'lineHeight': '1.6', 'marginBottom': '20px', 'paddingLeft': '20px'})
                ], style={'marginBottom': '15px', 'borderLeft': '3px solid #3498db', 'paddingLeft': '15px'})
                for item in faq_items
            ])
        ], style={**CARD_STYLE}),

        # --- Support Contact ---
        html.Div([
            html.H3("🆘 Dukungan Teknis", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.P("Jika Anda mengalami masalah atau membutuhkan bantuan tambahan:", 
                      style={'marginBottom': '15px'}),
                
                html.Div([
                    html.A("📧 Email Dukungan", 
                          href="mailto:support@ecoaims.com", 
                          style={'backgroundColor': '#3498db', 'color': 'white', 'padding': '10px 20px', 
                                 'textDecoration': 'none', 'borderRadius': '5px', 'marginRight': '10px',
                                 'display': 'inline-block', 'fontWeight': 'bold'}),
                    
                    html.A("💬 Forum Komunitas", 
                          href="https://community.ecoaims.com", 
                          target="_blank",
                          style={'backgroundColor': '#2ecc71', 'color': 'white', 'padding': '10px 20px', 
                                 'textDecoration': 'none', 'borderRadius': '5px', 'marginRight': '10px',
                                 'display': 'inline-block', 'fontWeight': 'bold'}),
                ], style={'marginBottom': '15px'})
            ], style={'textAlign': 'center'})
            
        ], style={**CARD_STYLE}),

        # --- System Info ---
        html.Div([
            html.H3("ℹ️ Informasi Sistem", style={'color': '#34495e', 'borderBottom': '2px solid #ecf0f1', 'paddingBottom': '10px'}),
            
            html.Div([
                html.P("ECO-AIMS Dashboard v2.0", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.P("Framework: Dash (Python) + Plotly", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                html.P("Update Interval: 2 detik (real-time)", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                html.P("Data Source: Hybrid (Live + Simulation)", style={'color': '#7f8c8d', 'margin': '2px 0'}),
                html.P("Terakhir Diperbarui: " + "2026-03-09", style={'color': '#7f8c8d', 'margin': '2px 0'})
            ], style={'textAlign': 'center'})
        ], style={**CARD_STYLE})

    ], style={'padding': '20px'})
