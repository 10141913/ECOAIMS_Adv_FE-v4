
"""
Indoor Module Layout for ECO-AIMS.

Provides the UI components for indoor climate monitoring:
- Live Sensor Feed tab (zone selector, live indicators, freshness, 24h chart)
- CSV Import tab (upload, preview, commit workflow)

All components are wrapped in a single isolated container (indoor-module-root)
so that errors in the indoor panel do not affect the rest of the dashboard.
"""

from dash import dcc, html


# ── Client-side script untuk debug upload event ─────────────────────────
_UPLOAD_DEBUG_SCRIPT = """
document.addEventListener('DOMContentLoaded', function() {
    console.log('[ECOAIMS] indoor_layout loaded, looking for csv-upload...');
    var upload = document.getElementById('csv-upload');
    if (upload) {
        console.log('[ECOAIMS] Found csv-upload element:', upload);
        upload.addEventListener('click', function(e) {
            console.log('[ECOAIMS] csv-upload clicked');
        });
        var fileInput = upload.querySelector('input[type="file"]');
        if (fileInput) {
            console.log('[ECOAIMS] Found file input inside csv-upload');
            fileInput.addEventListener('change', function(e) {
                var file = e.target.files ? e.target.files[0] : null;
                console.log('[ECOAIMS] File selected:', file ? file.name : 'no files');
            });
        } else {
            console.warn('[ECOAIMS] No file input found inside csv-upload!');
        }
    } else {
        console.error('[ECOAIMS] csv-upload element NOT FOUND in DOM!');
    }
});
"""
# ─────────────────────────────────────────────────────────────────────────


def create_indoor_layout() -> html.Div:
    """Construct the indoor module layout.

    Returns:
        html.Div: The root indoor module container.
    """
    return html.Div(
        id="indoor-module-root",
        className="indoor-module",
        children=[
            html.H4("🌡️ System Inputs (Indoor Climate)", className="indoor-title"),
            # Maintenance banner (hidden by default)
            html.Div(id="maintenance-banner", style={"display": "none"}),

            # ── Upload component placed OUTSIDE tabs so it is always
            #    mounted when the Indoor Climate tab is active (fixes
            #    dcc.Upload callback not firing inside nested dcc.Tab) ──
            html.Div(
                className="indoor-csv-upload-section",
                style={
                    "border": "1px solid #ddd",
                    "borderRadius": "6px",
                    "padding": "12px",
                    "marginBottom": "12px",
                    "backgroundColor": "#fafafa",
                },
                children=[
                    html.H5("📂 CSV Upload", style={"margin": "0 0 8px 0", "fontSize": "15px"}),
                    html.P(
                        [
                            "Upload CSV file with indoor sensor data. ",
                            html.Small(
                                "Required columns: ",
                                style={"color": "#888"},
                            ),
                            html.Code("timestamp"),
                            ", ",
                            html.Code("zone_id"),
                            ", ",
                            html.Code("temp_c"),
                            ", ",
                            html.Code("rh_pct"),
                            ", ",
                            html.Code("co2_ppm"),
                            html.Br(),
                            html.Small(
                                "Columns are automatically mapped to backend format.",
                                style={"color": "#888"},
                            ),
                        ],
                        style={"fontSize": "small", "margin": "0 0 8px 0"},
                    ),
                    dcc.Upload(
                        id="csv-upload",
                        children=html.Div(
                            [
                                "📁 Drag and Drop or ",
                                html.A("Select CSV File"),
                            ]
                        ),
                        style={
                            "width": "100%",
                            "height": "80px",
                            "lineHeight": "80px",
                            "borderWidth": "2px",
                            "borderStyle": "dashed",
                            "borderRadius": "5px",
                            "textAlign": "center",
                            "margin": "0",
                        },
                        # Accept only CSV files for better UX
                        accept=".csv",
                        multiple=False,
                    ),
                    # Backup manual upload button (step 5 fallback)
                    html.Div(
                        style={"marginTop": "8px", "display": "flex", "gap": "8px", "alignItems": "center"},
                        children=[
                            html.Button(
                                "📤 Upload Manual",
                                id="manual-upload-btn",
                                n_clicks=0,
                                style={
                                    "padding": "8px 16px",
                                    "backgroundColor": "#2980b9",
                                    "color": "white",
                                    "border": "none",
                                    "borderRadius": "4px",
                                    "cursor": "pointer",
                                    "fontSize": "13px",
                                },
                            ),
                            html.Span(
                                "Pilih file CSV di atas, lalu tekan tombol ini.",
                                style={"color": "#888", "fontSize": "12px"},
                            ),
                        ],
                    ),
                ],
            ),

            dcc.Tabs(
                id="indoor-tabs",
                value="live",
                children=[
                    # ── TAB 1: Live Sensor Feed ──
                    dcc.Tab(
                        label="Live Sensor Feed",
                        value="live",
                        children=[
                            html.Div(
                                className="indoor-live-panel",
                                children=[
                                    # Zone Selector
                                    html.Div(
                                        className="indoor-zone-row",
                                        children=[
                                            html.Label(
                                                "Select Zone:",
                                                className="zone-label",
                                            ),
                                            dcc.Dropdown(
                                                id="zone-selector",
                                                placeholder="Loading zones...",
                                                style={"minWidth": "260px"},
                                            ),
                                        ],
                                    ),
                                    # Live Indicators (3 cards)
                                    html.Div(
                                        className="indoor-cards-row",
                                        children=[
                                            html.Div(
                                                className="indoor-card",
                                                children=[
                                                    html.H5(
                                                        "Temperature",
                                                        className="card-title",
                                                    ),
                                                    html.H2(
                                                        id="live-temp",
                                                        children="---",
                                                        className="live-value",
                                                    ),
                                                    html.Small("°C", className="unit"),
                                                ],
                                            ),
                                            html.Div(
                                                className="indoor-card",
                                                children=[
                                                    html.H5(
                                                        "Relative Humidity",
                                                        className="card-title",
                                                    ),
                                                    html.H2(
                                                        id="live-rh",
                                                        children="---",
                                                        className="live-value",
                                                    ),
                                                    html.Small("%", className="unit"),
                                                ],
                                            ),
                                            html.Div(
                                                className="indoor-card",
                                                children=[
                                                    html.H5(
                                                        "CO₂",
                                                        className="card-title",
                                                    ),
                                                    html.H2(
                                                        id="live-co2",
                                                        children="---",
                                                        className="live-value",
                                                    ),
                                                    html.Small("ppm", className="unit"),
                                                ],
                                            ),
                                        ],
                                    ),
                                    # Freshness & Snapshot Version
                                    html.Div(
                                        id="live-freshness",
                                        className="freshness-indicator",
                                    ),
                                    html.Div(
                                        id="snapshot-version",
                                        className="snapshot-version",
                                        style={"fontSize": "small"},
                                    ),
                                    # Mini Chart 24h
                                    html.Div(
                                        className="chart-container",
                                        children=[
                                            html.H6(
                                                "Last 24 Hours Trend",
                                                className="chart-title",
                                            ),
                                            dcc.Graph(
                                                id="indoor-chart",
                                                config={"displayModeBar": False},
                                            ),
                                        ],
                                    ),
                                    # Hidden stores & polling
                                    dcc.Interval(
                                        id="polling-interval",
                                        interval=60000,
                                    ),
                                    dcc.Store(id="error-count-store", data=0),
                                    dcc.Store(id="last-poll-time", data=0),
                                    dcc.Store(id="upload-id-store", data=None),
                                ],
                            )
                        ],
                    ),
                    # ── TAB 2: CSV Import ──
                    dcc.Tab(
                        label="CSV Import",
                        value="csv",
                        children=[
                            html.Div(
                                className="indoor-csv-panel",
                                children=[
                                    # Preview Section
                                    html.Div(
                                        id="csv-preview-container",
                                        children=[
                                            html.H6("Preview Result"),
                                            html.Div(id="csv-preview-summary"),
                                            html.Div(id="csv-preview-table"),
                                            html.Button(
                                                "Confirm Commit",
                                                id="csv-commit-btn",
                                                style={
                                                    "display": "none",
                                                    "backgroundColor": "#28a745",
                                                    "color": "white",
                                                },
                                            ),
                                            html.Div(
                                                id="csv-status",
                                                style={"marginTop": "10px"},
                                            ),
                                        ],
                                    ),
                                    # Hidden polling interval & stores for CSV workflow
                                    dcc.Interval(
                                        id="csv-status-interval",
                                        interval=2000,
                                        disabled=True,
                                    ),
                                    dcc.Store(id="job-id-store", data=None),
                                    dcc.Store(id="csv-upload-id-store", data=None),
                                ],
                            )
                        ],
                    ),
                ],
            ),
            # Client-side debug script untuk upload event
            html.Script(_UPLOAD_DEBUG_SCRIPT),
        ],
    )
