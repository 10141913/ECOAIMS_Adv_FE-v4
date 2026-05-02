import base64
import io
import json
import logging
import math
from datetime import datetime, timedelta

import pandas as pd
import requests
from dash import Input, Output, State, html
import plotly.graph_objects as go

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL
from ecoaims_frontend.services.data_service import get_forecast_data, get_accuracy_data
from ecoaims_frontend.ui.error_ui import error_figure
from ecoaims_frontend.utils import get_headers

logger = logging.getLogger(__name__)

# ── Security / optimisation limits ─────────────────────────────────────────
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
_MAX_CSV_ROWS = 10_000

# ── Required CSV columns ──────────────────────────────────────────────────
_REQUIRED_CSV_COLS = {"timestamp", "HVAC", "Lighting", "Pump", "temperature", "humidity"}

# ── Sample bootstrap data (50 synthetic rows) ──────────────────────────────
_SAMPLE_BOOTSTRAP = [
    {
        "timestamp": (datetime(2026, 4, 1) + timedelta(hours=i)).isoformat(),
        "HVAC": round(18.0 + 10.0 * (i % 24) / 23.0 + 2.0 * (i % 7), 2),
        "Lighting": round(5.0 + 4.0 * (i % 12) / 11.0, 2),
        "Pump": round(3.0 + 2.0 * (i % 8) / 7.0, 2),
        "temperature": round(26.0 + 6.0 * ((i % 24) / 23.0) - 3.0 * ((i % 24) / 23.0) ** 2, 1),
        "humidity": round(60.0 + 15.0 * ((i % 24) / 23.0) - 10.0 * ((i % 24) / 23.0) ** 2, 1),
    }
    for i in range(50)
]


def _parse_csv_contents(contents: str, filename: str) -> tuple[list[dict] | None, str | None, dict | None]:
    """
    Parse a base64-encoded CSV file with security & optimisation checks.

    Returns (records, error_message, audit_info).
    - records: list of dicts on success, None on failure.
    - error_message: str describing the issue on failure, None on success.
    - audit_info: dict with keys {filename, row_count, columns} on success, None on failure.
    """
    # ── 1. Decode base64 & check file size ────────────────────────────────
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
    except Exception as exc:
        return None, f"❌ Gagal mendekode file: {exc}", None

    file_size = len(decoded)
    if file_size > _MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        return None, (
            f"❌ File too large ({size_mb:.1f} MB). Maximum allowed is "
            f"{_MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB."
        ), None

    # ── 2. Parse CSV ──────────────────────────────────────────────────────
    try:
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
    except Exception as exc:
        return None, f"❌ Gagal membaca file CSV: {exc}", None

    # ── 3. Validate required columns ──────────────────────────────────────
    missing_cols = _REQUIRED_CSV_COLS - set(df.columns)
    if missing_cols:
        return None, (
            f"❌ Kolom wajib tidak lengkap. Missing: {', '.join(sorted(missing_cols))}. "
            f"Required: {', '.join(sorted(_REQUIRED_CSV_COLS))}"
        ), None

    # ── 4. Row count limit ────────────────────────────────────────────────
    original_row_count = len(df)
    row_truncated = False
    if original_row_count > _MAX_CSV_ROWS:
        df = df.head(_MAX_CSV_ROWS)
        row_truncated = True
        logger.warning(
            "CSV row limit exceeded: original=%d truncated=%d filename=%s",
            original_row_count, _MAX_CSV_ROWS, filename,
        )

    # ── 5. Numeric validation with pd.to_numeric ──────────────────────────
    numeric_cols = ["HVAC", "Lighting", "Pump", "temperature", "humidity"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_drop = len(df)
    df = df.dropna(subset=["timestamp"] + numeric_cols)
    after_drop = len(df)
    dropped_nan = before_drop - after_drop

    if df.empty:
        return None, "❌ File CSV tidak mengandung data valid setelah validasi numerik.", None

    # ── 6. Build status messages ──────────────────────────────────────────
    warnings: list[str] = []
    if row_truncated:
        warnings.append(
            f"⚠️ Data truncated to {_MAX_CSV_ROWS:,} rows (original: {original_row_count:,} rows)."
        )
    if dropped_nan > 0:
        warnings.append(
            f"⚠️ {dropped_nan} rows had invalid numeric values and were skipped."
        )

    # ── 7. Convert to records ─────────────────────────────────────────────
    records = df.to_dict(orient="records")

    # ── 8. Build audit info ───────────────────────────────────────────────
    audit_info = {
        "filename": filename,
        "row_count": len(records),
        "columns": list(df.columns),
    }

    logger.info(
        "CSV parsed successfully filename=%s rows=%d dropped_nan=%d truncated=%s",
        filename, len(records), dropped_nan, row_truncated,
    )

    return records, None, audit_info, warnings


def register_forecasting_callbacks(app):
    """
    Registers callbacks for the Forecasting Tab.
    """

    # ── Initialise bootstrap data store on first load ──────────────────────
    @app.callback(
        Output('bootstrap-data-store', 'data'),
        Input('bootstrap-data-store', 'id'),
        prevent_initial_call=False,
    )
    def _init_bootstrap_store(_):
        return _SAMPLE_BOOTSTRAP

    # ── CSV Upload callback: parse, validate, audit ────────────────────────
    @app.callback(
        [Output('csv-data-store', 'data'),
         Output('csv-upload-status', 'children')],
        Input('upload-csv', 'contents'),
        State('upload-csv', 'filename'),
        State('token-store', 'data'),
        prevent_initial_call=True,
    )
    def _handle_csv_upload(contents, filename, token_data):
        """
        Parse uploaded CSV with security checks (file size, row limit,
        numeric validation), store in csv-data-store, show status with
        warnings, and POST audit trail to backend.
        """
        if contents is None:
            return None, html.Span(
                "Belum ada file CSV. Data sintetis akan digunakan.",
                style={'color': '#7f8c8d', 'fontSize': '14px'},
            )

        # _parse_csv_contents now returns (records, error, audit_info, warnings)
        result = _parse_csv_contents(contents, filename)
        records, error, audit_info, warnings = result

        if error is not None:
            return None, html.Span(error, style={'color': '#D32F2F', 'fontSize': '14px'})

        # ── Audit trail: POST to backend ──────────────────────────────────
        try:
            audit_url = f"{ECOAIMS_API_BASE_URL.rstrip('/')}/api/v1/ingest/csv/upload"
            audit_headers = get_headers(token_data)
            audit_headers["Content-Type"] = "application/json"
            requests.post(
                audit_url,
                json=audit_info,
                timeout=10,
                headers=audit_headers,
            )
            logger.info("Audit trail sent to %s for %s", audit_url, filename)
        except requests.RequestException as exc:
            # Non-blocking: log warning but do not fail the upload
            logger.warning("Audit trail POST failed for %s: %s", filename, exc)

        # ── Build status display ──────────────────────────────────────────
        n = len(records)
        preview_rows = records[:5]
        preview_text = "; ".join(
            f"{r['timestamp']} HVAC={r['HVAC']}" for r in preview_rows
        )
        preview_ellipsis = "..." if n > 5 else ""

        status_children: list = [
            html.Span(
                f"📁 Using uploaded data ({n} rows from {filename})",
                style={'color': '#2E7D32', 'fontSize': '14px', 'fontWeight': 'bold'},
            ),
            html.Div(
                f"Preview: {preview_text}{preview_ellipsis}",
                style={'color': '#566573', 'fontSize': '12px', 'marginTop': '4px'},
            ),
        ]

        # Append any security / validation warnings
        for w in warnings:
            status_children.append(
                html.Div(w, style={'color': '#FF9800', 'fontSize': '13px', 'marginTop': '4px'})
            )

        status = html.Div(status_children)
        return records, status

    # ── Existing period-based graph update ─────────────────────────────────
    @app.callback(
        [Output('forecast-consumption-graph', 'figure'),
         Output('forecast-renewable-graph', 'figure'),
         Output('forecast-accuracy-graph', 'figure')],
        [Input('forecast-period-dropdown', 'value')]
    )
    def update_forecast_graphs(period):
        """
        Updates all forecasting graphs based on the selected period.
        """
        try:
            data = get_forecast_data(period)
            accuracy_data = get_accuracy_data()
        
            cons_fig = go.Figure()
            if period == 'hourly':
                cons_fig.add_trace(go.Scatter(
                    x=data['time'],
                    y=data['consumption'],
                    mode='lines+markers',
                    name='Konsumsi Energi',
                    line=dict(color='#e74c3c', width=3),
                    hovertemplate='%{y:.2f} kWh<br>%{x}'
                ))
                title = 'Prediksi Konsumsi Energi (24 Jam ke Depan)'
                xaxis_title = 'Waktu'
            else:
                cons_fig.add_trace(go.Bar(
                    x=data['time'],
                    y=data['consumption'],
                    name='Konsumsi Energi',
                    marker_color='#e74c3c',
                    hovertemplate='%{y:.2f} kWh<br>%{x}'
                ))
                title = 'Prediksi Konsumsi Energi (7 Hari ke Depan)'
                xaxis_title = 'Tanggal'
                
            cons_fig.update_layout(
                title=title,
                xaxis_title=xaxis_title,
                yaxis_title='Konsumsi (kWh)',
                template='plotly_white',
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            renew_fig = go.Figure()
            if period == 'hourly':
                renew_fig.add_trace(go.Scatter(
                    x=data['time'],
                    y=data['solar'],
                    mode='lines',
                    name='Solar PV',
                    line=dict(color='#f1c40f', width=2),
                    stackgroup='one'
                ))
                renew_fig.add_trace(go.Scatter(
                    x=data['time'],
                    y=data['wind'],
                    mode='lines',
                    name='Wind Turbine',
                    line=dict(color='#3498db', width=2),
                    stackgroup='one'
                ))
                title = 'Prediksi Produksi Energi Terbarukan (24 Jam)'
            else:
                renew_fig.add_trace(go.Bar(
                    x=data['time'],
                    y=data['solar'],
                    name='Solar PV',
                    marker_color='#f1c40f'
                ))
                renew_fig.add_trace(go.Bar(
                    x=data['time'],
                    y=data['wind'],
                    name='Wind Turbine',
                    marker_color='#3498db'
                ))
                title = 'Prediksi Produksi Energi Terbarukan (7 Hari)'
                
            renew_fig.update_layout(
                title=title,
                xaxis_title=xaxis_title,
                yaxis_title='Produksi (kWh)',
                template='plotly_white',
                barmode='stack' if period == 'daily' else None,
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            acc_fig = go.Figure()
            acc_fig.add_trace(go.Scatter(
                x=accuracy_data['time'],
                y=accuracy_data['actual'],
                mode='lines',
                name='Aktual',
                line=dict(color='#2ecc71', width=3)
            ))
            acc_fig.add_trace(go.Scatter(
                x=accuracy_data['time'],
                y=accuracy_data['forecast'],
                mode='lines',
                name='Prediksi (Model)',
                line=dict(color='#95a5a6', width=2, dash='dash')
            ))
            
            acc_fig.update_layout(
                title='Evaluasi Model: Data Aktual vs Prediksi (24 Jam Terakhir)',
                xaxis_title='Waktu',
                yaxis_title='Energi (kWh)',
                template='plotly_white',
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="x unified"
            )

            return cons_fig, renew_fig, acc_fig
        except Exception as e:
            fig = error_figure("Forecasting", str(e))
            return fig, fig, fig

    # ── LSTM / ML Forecast callback (with CSV data support) ────────────────
    @app.callback(
        Output('forecast-result', 'children'),
        Input('run-forecast-btn', 'n_clicks'),
        State('model-selector', 'value'),
        State('bootstrap-data-store', 'data'),
        State('csv-data-store', 'data'),
        State('token-store', 'data'),
        prevent_initial_call=True,
    )
    def _run_ai_forecast(n_clicks, model_type, bootstrap_data, csv_data, token_data):
        """
        Sends a POST request to the backend LSTM / ML endpoint and displays
        the result status.

        Uses CSV-uploaded data if available; falls back to synthetic data.
        Ensures all 5 end-use columns (HVAC, Lighting, Pump, temperature, humidity)
        are present, timestamps are ISO strings, and minimum 48 bootstrap rows.
        """
        if not n_clicks or n_clicks < 1:
            return html.Div("Klik 'Run Forecast' untuk memulai.", style={'color': '#566573'})

        # ── Required columns ────────────────────────────────────────────────
        _FORECAST_COLS = ["HVAC", "Lighting", "Pump", "temperature", "humidity"]
        _MIN_BOOTSTRAP_ROWS = 48  # 2 × sequence_length (24)

        # ── Helper: normalise a single row ──────────────────────────────────
        def _normalize_forecast_row(row: dict) -> dict:
            """Ensure all 5 columns exist; convert timestamp to ISO string."""
            out = {}
            ts = row.get("timestamp")
            if isinstance(ts, datetime):
                out["timestamp"] = ts.isoformat()
            elif ts is None:
                out["timestamp"] = datetime.now().isoformat()
            else:
                out["timestamp"] = str(ts)
            for col in _FORECAST_COLS:
                v = row.get(col)
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    v = 0.0
                out[col] = float(v)
            return out

        # ── Determine data source ──────────────────────────────────────────
        using_csv = csv_data is not None and len(csv_data) > 0
        source_data = csv_data if using_csv else bootstrap_data

        if source_data is None or len(source_data) == 0:
            return html.Div(
                "❌ Tidak ada data historis. Upload file CSV atau gunakan data sintetis.",
                style={'color': '#D32F2F'},
            )

        # ── Normalise all rows ─────────────────────────────────────────────
        normalized = [_normalize_forecast_row(r) for r in source_data]

        # ── Ensure minimum bootstrap rows (48 = 2 × sequence_length) ───────
        if len(normalized) < _MIN_BOOTSTRAP_ROWS:
            print(f"[AI Forecast] Only {len(normalized)} rows, repeating cyclically to reach {_MIN_BOOTSTRAP_ROWS}")
            repeats = (_MIN_BOOTSTRAP_ROWS // len(normalized)) + 1
            normalized = (normalized * repeats)[:_MIN_BOOTSTRAP_ROWS]

        # ── Split into bootstrap_rows (all except last) and sensor_row ─────
        bootstrap_rows = normalized[:-1]
        sensor_row = normalized[-1]

        # ── Build data source indicator ────────────────────────────────────
        if using_csv:
            source_indicator = f"📁 Using uploaded data ({len(source_data)} rows → {len(normalized)} after norm)"
        else:
            source_indicator = f"🔧 Using synthetic data ({len(normalized)} rows)"

        # ── Build payload ──────────────────────────────────────────────────
        payload = {
            "stream_id": "ui_forecast",
            "model_type": model_type,
            "end_use_cols": _FORECAST_COLS,
            "sequence_length": 24,
            "forecast_horizon": 1,
            "epochs": 5,
            "batch_size": 32,
            "bootstrap_rows": bootstrap_rows,
            "sensor_row": sensor_row,
        }

        print("[AI Forecast] Payload:", json.dumps(payload, indent=2))

        url = f"{ECOAIMS_API_BASE_URL.rstrip('/')}/ai/forecast/multi-end-use"
        forecast_headers = get_headers(token_data)

        try:
            logger.info(
                "Sending AI forecast request model_type=%s url=%s rows=%d source=%s",
                model_type, url, len(bootstrap_rows),
                "csv" if using_csv else "synthetic",
            )
            resp = requests.post(url, json=payload, timeout=300, headers=forecast_headers)
            resp.raise_for_status()
            result = resp.json()
            backend = result.get('backend', '')

            if backend == 'lstm':
                return html.Div([
                    html.Div(source_indicator, style={'fontSize': '13px', 'color': '#566573', 'marginBottom': '4px'}),
                    html.Span("✅ LSTM Active", style={'color': '#2E7D32', 'fontSize': '16px'}),
                ])
            elif backend == 'linear_sequence':
                return html.Div([
                    html.Div(source_indicator, style={'fontSize': '13px', 'color': '#566573', 'marginBottom': '4px'}),
                    html.Span("⚠️ Linear Active (fallback)", style={'color': '#FF9800', 'fontSize': '16px'}),
                ])
            elif backend == 'ensemble':
                return html.Div([
                    html.Div(source_indicator, style={'fontSize': '13px', 'color': '#566573', 'marginBottom': '4px'}),
                    html.Span("✅ Ensemble Active (DLinear+LightGBM+TCN)", style={'color': '#2E7D32', 'fontSize': '16px'}),
                ])
            else:
                return html.Div([
                    html.Div(source_indicator, style={'fontSize': '13px', 'color': '#566573', 'marginBottom': '4px'}),
                    html.Span(f"⚠️ Unknown backend: {backend}", style={'color': '#FF9800', 'fontSize': '16px'}),
                ])

        except requests.exceptions.Timeout:
            msg = "❌ Error: Request timeout (backend LSTM terlalu lama)."
            logger.error(msg)
            return html.Div(msg, style={'color': '#D32F2F', 'fontSize': '16px'})

        except requests.exceptions.ConnectionError:
            msg = f"❌ Error: Tidak dapat terhubung ke backend ({url})."
            logger.error(msg)
            return html.Div(msg, style={'color': '#D32F2F', 'fontSize': '16px'})

        except requests.exceptions.RequestException as exc:
            msg = f"❌ Error: {exc}"
            if hasattr(exc, 'response') and exc.response is not None:
                try:
                    detail = exc.response.json()
                    msg += f" | Detail: {json.dumps(detail, indent=2)}"
                except Exception:
                    msg += f" | Body: {exc.response.text[:500]}"
            logger.error(msg)
            return html.Div(msg, style={'color': '#D32F2F', 'fontSize': '16px'})

        except Exception as exc:
            msg = f"❌ Error: {exc}"
            logger.error(msg, exc_info=True)
            return html.Div(msg, style={'color': '#D32F2F', 'fontSize': '16px'})
