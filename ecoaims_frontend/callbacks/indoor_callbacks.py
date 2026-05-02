"""
Indoor Module Callbacks for ECO-AIMS.

Each callback wraps its logic in try/except and returns safe fallback
values so that a single failure does not brick the entire dashboard.

Callbacks implemented:
  - load_zones: populate zone selector dropdown
  - adaptive_polling: exponential backoff + jitter on error count
  - update_live_data: fetch latest sensor readings + staleness badge
  - update_chart: 24h timeseries chart
  - preview_csv: upload CSV file, store job_id, enable polling
  - poll_csv_status: polling loop via csv-status-interval to display preview
  - commit_csv: commit previewed CSV data
  - check_maintenance_mode: show/hide maintenance banner
"""

import base64
import logging
import os
import random
import time
from datetime import datetime, timezone

import plotly.graph_objs as go
from dash import Input, Output, State, callback_context, dcc, html, no_update

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL, API_BASE_URL as CFG_API_BASE_URL
from ecoaims_frontend.services.indoor_api import (
    commit_csv_upload,
    fetch_latest,
    fetch_timeseries,
    fetch_zones,
    upload_csv_preview,
    get_csv_status,
    fetch_maintenance_status,
)
from ecoaims_frontend.utils import get_headers

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────
_BASE_INTERVAL_MS = 60000  # 60 s
_MAX_INTERVAL_MS = 240000  # 240 s
_FRESH_SECONDS = 180       # < 3 min → green
_STALE_SECONDS = 300       # 3-5 min → yellow, >5 min → red


# ── Helpers ────────────────────────────────────


def _freshness_badge(last_updated_str: str | None) -> html.Span:
    """Return a coloured staleness badge based on last-updated time."""
    if not last_updated_str:
        return html.Span("🔴 No data", className="badge badge-danger")

    try:
        s = last_updated_str.replace("Z", "+00:00")
        last_updated = datetime.fromisoformat(s)
    except Exception:
        return html.Span("🟡 Unknown", className="badge badge-warning")

    now = datetime.now(timezone.utc)
    seconds_ago = (now - last_updated).total_seconds()

    if seconds_ago < _FRESH_SECONDS:
        return html.Span(
            "🟢 Fresh",
            className="badge badge-success",
            title=f"Last updated {int(seconds_ago)} seconds ago",
        )
    if seconds_ago < _STALE_SECONDS:
        return html.Span(
            "🟡 Stale (network lag)",
            className="badge badge-warning",
            title=f"Last updated {int(seconds_ago)} seconds ago",
        )
    return html.Span(
        "🔴 Stale (data not updated)",
        className="badge badge-danger",
        title=f"Last updated {int(seconds_ago)} seconds ago",
    )


def _empty_figure(title: str = "No data") -> go.Figure:
    """Return an empty Plotly figure with a centred title."""
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": title,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 14, "color": "#7f8c8d"},
            }
        ],
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


# ── Callback Registration ──────────────────────


def register_indoor_callbacks(app) -> None:
    """Register all indoor module callbacks on the given Dash app."""

    # ── 1. Zone Selector ────────────────────────
    @app.callback(
        Output("zone-selector", "options"),
        Input("indoor-tabs", "value"),
        State("token-store", "data"),
    )
    def load_zones(tab_value: str, token_data: dict | None = None) -> list[dict]:
        """Load available zones from backend when the live tab is active."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: load_zones — Mencoba koneksi ke {api_url}", flush=True)
        # ────────────────────────────────────────────────────────────────

        if tab_value != "live":
            return []
        try:
            auth_headers = get_headers(token_data)
            zones = fetch_zones(headers=auth_headers)
            if not zones:
                return [{"label": "No zones available", "value": "error"}]
            return [{"label": str(z), "value": str(z)} for z in zones]
        except Exception:
            logger.exception("load_zones failed")
            return [{"label": "Error loading zones", "value": "error"}]

    # ── 2. Adaptive Polling ─────────────────────
    @app.callback(
        Output("polling-interval", "interval"),
        Input("error-count-store", "data"),
        Input("last-poll-time", "data"),
    )
    def adaptive_polling(
        error_count: int, last_poll: float
    ) -> int:
        """Exponential backoff + jitter based on consecutive error count.

        Base: 60s → 120s → 240s (max).
        """
        _ = last_poll  # keep for future use (e.g. rate-limiting)
        if not isinstance(error_count, (int, float)) or error_count <= 0:
            return _BASE_INTERVAL_MS

        capped = min(int(error_count), 2)  # 0, 1, 2 → 60, 120, 240
        backoff = _BASE_INTERVAL_MS * (2**capped)
        jitter = backoff * (0.9 + random.random() * 0.2)  # ±10 %
        return min(int(jitter), _MAX_INTERVAL_MS)

    # ── 3. Live Data ────────────────────────────
    @app.callback(
        Output("live-temp", "children"),
        Output("live-rh", "children"),
        Output("live-co2", "children"),
        Output("live-freshness", "children"),
        Output("snapshot-version", "children"),
        Output("error-count-store", "data"),
        Input("zone-selector", "value"),
        Input("polling-interval", "n_intervals"),
        State("error-count-store", "data"),
        State("token-store", "data"),
    )
    def update_live_data(
        zone_id: str | None,
        _n_intervals: int | None,
        error_count: int,
        token_data: dict | None = None,
    ) -> tuple:
        """Fetch latest indoor sensor data and update live indicators."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: update_live_data — Mencoba koneksi ke {api_url}", flush=True)
        # ────────────────────────────────────────────────────────────────

        if not zone_id or zone_id == "error":
            return "---", "---", "---", "⚠️ No zone selected", "", error_count

        try:
            auth_headers = get_headers(token_data)
            data = fetch_latest(zone_id, headers=auth_headers)
            if data is None:
                new_count = (error_count or 0) + 1
                return (
                    "---",
                    "---",
                    "---",
                    "⚠️ Service unavailable",
                    "",
                    new_count,
                )

            # Success → reset error count
            new_count = 0
            freshness = _freshness_badge(data.get("last_updated_utc"))
            version = f"Snapshot version: {data.get('snapshot_version', 'N/A')}"

            temp = data.get("zone_temp_c")
            rh = data.get("zone_rh_pct")
            co2 = data.get("co2_ppm", "N/A")

            temp_str = f"{float(temp):.1f}" if isinstance(temp, (int, float)) else "---"
            rh_str = f"{float(rh):.0f}" if isinstance(rh, (int, float)) else "---"
            co2_str = str(co2) if co2 is not None else "N/A"

            return temp_str, rh_str, co2_str, freshness, version, new_count

        except Exception:
            logger.exception("update_live_data failed for zone=%s", zone_id)
            new_count = (error_count or 0) + 1
            return "---", "---", "---", "⚠️ Error", "", new_count

    # ── 4. Mini Chart (24h Timeseries) ──────────
    @app.callback(
        Output("indoor-chart", "figure"),
        Input("zone-selector", "value"),
        Input("polling-interval", "n_intervals"),
        State("token-store", "data"),
    )
    def update_chart(
        zone_id: str | None,
        _n_intervals: int | None,
        token_data: dict | None = None,
    ) -> go.Figure:
        """Fetch 24h timeseries and render a dual-axis chart."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: update_chart — Mencoba koneksi ke {api_url}", flush=True)
        # ────────────────────────────────────────────────────────────────

        if not zone_id or zone_id == "error":
            return _empty_figure("Select a zone")

        try:
            auth_headers = get_headers(token_data)
            points = fetch_timeseries(zone_id, hours=24, headers=auth_headers)
            if not points:
                return _empty_figure("No data available")

            timestamps = [p.get("timestamp") for p in points if p.get("timestamp")]
            temps = [
                float(p["temp_c"])
                for p in points
                if isinstance(p.get("temp_c"), (int, float))
            ]
            rh_vals = [
                float(p["rh_pct"])
                for p in points
                if isinstance(p.get("rh_pct"), (int, float))
            ]

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=temps,
                    name="Temperature (°C)",
                    line=dict(color="#e74c3c", width=2),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=rh_vals,
                    name="Humidity (%)",
                    line=dict(color="#3498db", width=2),
                    yaxis="y2",
                )
            )

            fig.update_layout(
                title=f"Last 24 Hours — Zone {zone_id}",
                xaxis_title="Time",
                yaxis_title="Temperature (°C)",
                yaxis2=dict(
                    title="Humidity (%)",
                    overlaying="y",
                    side="right",
                ),
                legend=dict(x=0, y=1, orientation="h"),
                height=300,
                margin=dict(l=40, r=40, t=60, b=40),
                template="plotly_white",
            )
            return fig

        except Exception:
            logger.exception("update_chart failed for zone=%s", zone_id)
            return _empty_figure("Error loading chart")

    # ── 5. CSV Upload + Polling Status ──────────
    @app.callback(
        Output("csv-preview-summary", "children"),
        Output("csv-preview-table", "children"),
        Output("csv-commit-btn", "style"),
        Output("csv-status", "children"),
        Output("job-id-store", "data"),
        Output("csv-upload-id-store", "data"),
        Output("csv-status-interval", "disabled"),
        Input("csv-upload", "contents"),
        Input("manual-upload-btn", "n_clicks"),
        State("csv-upload", "filename"),
        State("token-store", "data"),
        prevent_initial_call=False,
    )
    def preview_csv(
        contents: str | None,
        n_clicks: int | None,
        filename: str | None,
        token_data: dict | None = None,
    ) -> tuple:
        """Upload CSV file (upload step only), store job_id, enable status polling.

        The backend auto-processes the preview in a background task.
        A separate polling callback (poll_csv_status) reads the status
        via csv-status-interval and displays the preview when ready.
        """
        # ── DEBUG: trace callback trigger & connection check ───────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: preview_csv — Dipanggil! n_clicks={n_clicks}, contents={'provided' if contents else 'None'}, filename={filename}", flush=True)
        print(f"DEBUG: preview_csv — Mencoba koneksi ke {api_url}", flush=True)
        logger.info("preview_csv triggered — n_clicks=%s, contents=%s, filename=%s", n_clicks, "provided" if contents else "None", filename)
        logger.info("API_BASE_URL=%s", api_url)
        # ────────────────────────────────────────────────────────────────

        # Jika tidak ada file yang diupload, return default
        if contents is None:
            print("DEBUG: preview_csv — contents is None, returning defaults", flush=True)
            return "", "", {"display": "none"}, "", None, None, True

        try:
            print(f"DEBUG: preview_csv — decoding file: {filename}", flush=True)
            content_type, content_string = contents.split(",", 1)
            decoded = base64.b64decode(content_string)
            print(f"DEBUG: preview_csv — decoded {len(decoded)} bytes from {filename}", flush=True)
            logger.info("preview_csv decoded %d bytes from %s", len(decoded), filename)

            auth_headers = get_headers(token_data)
            # Cetak token untuk verifikasi (hanya 20 karakter pertama)
            auth_hdr = auth_headers.get("Authorization", "TIDAK ADA")
            print(f"DEBUG: preview_csv — Authorization header: {auth_hdr[:40]}...", flush=True)
            # Tujuan pengiriman data
            print(f"DEBUG: preview_csv — Mengirim data ke {api_url}/api/v4/csv/upload (timeout=10s)", flush=True)
            result = upload_csv_preview(decoded, filename or "upload.csv", headers=auth_headers)
            print(f"DEBUG: preview_csv — upload_csv_preview result={result}", flush=True)

            if result is None:
                print(f"DEBUG: preview_csv — upload_csv_preview returned None (backend unreachable)", flush=True)
                return (
                    html.Div(
                        [
                            html.Strong("Upload failed — "),
                            "backend unreachable or returned an error. ",
                            html.Br(),
                            html.Small(
                                "Check the server logs (indoor_api) for the exact error detail.",
                                style={"color": "#888"},
                            ),
                        ],
                        className="error",
                    ),
                    "",
                    {"display": "none"},
                    "",
                    None,
                    None,
                    True,
                )

            # Check if backend returned an error payload
            if "error" in result:
                err_msg = result.get("error", result.get("message", "Unknown server error"))
                print(f"DEBUG: preview_csv — backend returned error: {err_msg}", flush=True)
                return (
                    html.Div(
                        [
                            html.Strong("Server error: "),
                            html.Span(str(err_msg)),
                        ],
                        className="error",
                    ),
                    "",
                    {"display": "none"},
                    "",
                    None,
                    None,
                    True,
                )

            job_id = result.get("job_id")
            upload_id = result.get("upload_id")
            print(f"DEBUG: preview_csv — success, job_id={job_id}, upload_id={upload_id}", flush=True)
            logger.info("preview_csv success — job_id=%s, upload_id=%s", job_id, upload_id)

            # Show initial processing status and enable polling
            return (
                html.Div("⏳ Processing preview...", style={"color": "#888"}),
                "",
                {"display": "none"},
                "",
                job_id,
                upload_id,
                False,  # disabled=False → enable interval
            )

        except Exception as exc:
            logger.exception("preview_csv failed")
            print(f"DEBUG: preview_csv — EXCEPTION: {exc}", flush=True)
            # Cetak response.text jika exception memiliki response (misalnya HTTPError)
            try:
                if hasattr(exc, 'response') and exc.response is not None:
                    resp_text = exc.response.text[:1000]
                    print(f"DEBUG: preview_csv — Response text: {resp_text}", flush=True)
            except Exception:
                pass
            return (
                html.Div(
                    [
                        html.Strong("Upload failed — "),
                        str(exc),
                        html.Br(),
                        html.Small(
                            "Check terminal logs for full error detail (CORS, Timeout, or Wrong Port).",
                            style={"color": "#888"},
                        ),
                    ],
                    className="error",
                ),
                "",
                {"display": "none"},
                "",
                None,
                None,
                True,
            )

    # ── 6. CSV Status Polling ────────────────────
    @app.callback(
        Output("csv-preview-summary", "children", allow_duplicate=True),
        Output("csv-preview-table", "children", allow_duplicate=True),
        Output("csv-commit-btn", "style", allow_duplicate=True),
        Output("csv-status", "children", allow_duplicate=True),
        Output("csv-status-interval", "disabled", allow_duplicate=True),
        Output("job-id-store", "data", allow_duplicate=True),
        Input("csv-status-interval", "n_intervals"),
        State("job-id-store", "data"),
        State("csv-upload-id-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
    )
    def poll_csv_status(
        n_intervals: int | None,
        job_id: str | None,
        upload_id: str | None,
        token_data: dict | None = None,
    ) -> tuple:
        """Poll the backend for CSV job status and display preview when ready."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: poll_csv_status — Mencoba koneksi ke {api_url}", flush=True)
        print(f"DEBUG: poll_csv_status triggered — n_intervals={n_intervals}, job_id={job_id}, upload_id={upload_id}", flush=True)
        # ────────────────────────────────────────────────────────────────

        if not job_id:
            print("DEBUG: poll_csv_status — no job_id, returning no_update", flush=True)
            return no_update, no_update, no_update, no_update, no_update, no_update

        try:
            auth_headers = get_headers(token_data)
            print(f"DEBUG: poll_csv_status — calling get_csv_status(job_id={job_id})", flush=True)
            status_result = get_csv_status(job_id, headers=auth_headers)
            print(f"DEBUG: poll_csv_status — get_csv_status result={status_result}", flush=True)

            if status_result is None:
                print(f"DEBUG: poll_csv_status — status_result is None", flush=True)
                return (
                    no_update,
                    no_update,
                    no_update,
                    html.Div("⚠️ Status check failed — retrying...", style={"color": "#e67e22"}),
                    no_update,
                    no_update,
                )

            # ── Normalize response structure ──────────────────────────────
            # Backend may return flat:  {"status":"preview_ready","stats":{...}}
            # or nested under "job":     {"job":{"status":"preview_ready","stats":{...}}}
            job = status_result.get("job", status_result)
            # ───────────────────────────────────────────────────────────────

            # ── Normalize status to UPPER_CASE (backend may return lowercase) ──
            raw_status = str(job.get("status", "PENDING") or "PENDING")
            job_status = raw_status.upper()
            # ────────────────────────────────────────────────────────────────────

            stats = job.get("stats", {})
            preview_data = job.get("preview_data", [])

            print(f"DEBUG: poll_csv_status — raw_status='{raw_status}', normalized='{job_status}', stats={stats}", flush=True)

            # ── Status: PREVIEW_READY — tampilkan preview, aktifkan commit, hentikan polling ──
            if job_status in ("PREVIEW_READY", "PREVIEWREADY"):
                summary = html.Div(
                    [
                        html.H6("✅ Preview Ready", style={"color": "#27ae60"}),
                        html.P(f"Total rows: {stats.get('total_rows', '?')}"),
                        html.P(
                            f"✅ Valid: {stats.get('valid_rows', '?')}",
                            style={"color": "#27ae60"},
                        ),
                        html.P(
                            f"❌ Invalid: {stats.get('rejected_rows', '?')}",
                            style={"color": "#e74c3c"},
                        ),
                    ]
                )

                # Build a simple preview table from sample rows
                table = ""
                if preview_data and isinstance(preview_data, list):
                    rows = preview_data[:10]  # limit to 10 rows
                    table = html.Table(
                        className="preview-table",
                        children=[
                            html.Thead(
                                html.Tr([html.Th(k) for k in rows[0].keys()])
                            ),
                            html.Tbody([
                                html.Tr([html.Td(str(v)) for v in row.values()])
                                for row in rows
                            ]),
                        ],
                    )

                print(f"DEBUG: poll_csv_status — PREVIEW_READY, returning preview data, stopping polling", flush=True)
                return (
                    summary,
                    table,
                    {"display": "inline-block"},  # show commit button
                    "",
                    True,   # disabled=True → stop polling interval
                    None,   # clear job_id
                )

            # ── Status: PENDING / PROCESSING — lanjut polling ──────────────
            elif job_status in ("PENDING", "PROCESSING"):
                print(f"DEBUG: poll_csv_status — still processing: {raw_status}", flush=True)
                return (
                    no_update,
                    no_update,
                    no_update,
                    html.Div(
                        f"⏳ Processing... ({raw_status})",
                        style={"color": "#888"},
                    ),
                    no_update,
                    no_update,
                )

            # ── Status: COMMITTED ──────────────────────────────────────────
            elif job_status == "COMMITTED":
                print(f"DEBUG: poll_csv_status — COMMITTED", flush=True)
                return (
                    html.Div("This file has already been committed.", style={"color": "#888"}),
                    "",
                    {"display": "none"},
                    "",
                    True,   # stop polling
                    None,   # clear job_id
                )

            # ── Status: ERROR or unknown ───────────────────────────────────
            else:
                error_msg = job.get("error", f"Unexpected status: '{raw_status}'")
                print(f"DEBUG: poll_csv_status — error/unknown: {error_msg}", flush=True)
                return (
                    html.Div(f"❌ {error_msg}", className="error"),
                    "",
                    {"display": "none"},
                    "",
                    True,   # stop polling
                    None,   # clear job_id
                )

        except Exception as exc:
            logger.exception("poll_csv_status failed for job %s", job_id)
            print(f"DEBUG: poll_csv_status — EXCEPTION for job {job_id}: {exc}", flush=True)
            try:
                if hasattr(exc, 'response') and exc.response is not None:
                    resp_text = exc.response.text[:1000]
                    print(f"DEBUG: poll_csv_status — Response text: {resp_text}", flush=True)
            except Exception:
                pass
            return (
                no_update,
                no_update,
                no_update,
                html.Div("⚠️ Status check error — retrying...", style={"color": "#e67e22"}),
                no_update,
                no_update,
            )

    # ── 7. CSV Commit ───────────────────────────
    @app.callback(
        Output("csv-status", "children", allow_duplicate=True),
        Input("csv-commit-btn", "n_clicks"),
        State("csv-upload-id-store", "data"),
        State("token-store", "data"),
        prevent_initial_call=True,
    )
    def commit_csv(
        n_clicks: int | None,
        upload_id: str | None,
        token_data: dict | None = None,
    ) -> html.Div | str:
        """Commit a previously previewed CSV upload."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: commit_csv — Mencoba koneksi ke {api_url}", flush=True)
        # ────────────────────────────────────────────────────────────────

        if not n_clicks or not upload_id:
            return no_update

        try:
            auth_headers = get_headers(token_data)
            result = commit_csv_upload(upload_id, headers=auth_headers)
            if result is None:
                return html.Div(
                    [
                        html.Strong("Commit failed — "),
                        "backend unreachable or returned an error. ",
                        html.Br(),
                        html.Small(
                            "Check the server logs (indoor_api) for the exact error detail.",
                            style={"color": "#888"},
                        ),
                    ],
                    className="error",
                )

            # Check if backend returned an error payload
            if "error" in result:
                err_msg = result.get("error", result.get("message", "Unknown server error"))
                return html.Div(
                    [
                        html.Strong("Server error: "),
                        html.Span(str(err_msg)),
                    ],
                    className="error",
                )

            return html.Div(
                [
                    html.H6("✅ Import Complete!"),
                    html.P(f"Accepted: {result.get('accepted', '?')}"),
                    html.P(f"Rejected: {result.get('rejected', '?')}"),
                    html.P(
                        f"Ignored (duplicate): {result.get('ignored_duplicate', 0)}"
                    ),
                ],
                className="success-message",
            )

        except Exception as exc:
            logger.exception("commit_csv failed")
            print(f"DEBUG: commit_csv — EXCEPTION: {exc}", flush=True)
            try:
                if hasattr(exc, 'response') and exc.response is not None:
                    resp_text = exc.response.text[:1000]
                    print(f"DEBUG: commit_csv — Response text: {resp_text}", flush=True)
            except Exception:
                pass
            return html.Div(
                [
                    html.Strong("Commit failed — "),
                    str(exc),
                    html.Br(),
                    html.Small(
                        "Check terminal logs for full error detail (CORS, Timeout, or Wrong Port).",
                        style={"color": "#888"},
                    ),
                ],
                className="error",
            )

    # ── 8. Maintenance Banner ───────────────────
    @app.callback(
        Output("maintenance-banner", "children"),
        Output("maintenance-banner", "style"),
        Input("polling-interval", "n_intervals"),
        State("token-store", "data"),
    )
    def check_maintenance_mode(
        _n_intervals: int | None,
        token_data: dict | None = None,
    ) -> tuple:
        """Show maintenance banner if backend reports maintenance mode."""
        # ── DEBUG: connection check ────────────────────────────────────
        api_url = os.getenv("ECOAIMS_API_BASE_URL") or os.getenv("API_BASE_URL") or str(ECOAIMS_API_BASE_URL)
        print(f"DEBUG: check_maintenance_mode — Mencoba koneksi ke {api_url}", flush=True)
        # ────────────────────────────────────────────────────────────────

        try:
            auth_headers = get_headers(token_data)
            status = fetch_maintenance_status(headers=auth_headers)
            if isinstance(status, dict) and status.get("maintenance_mode"):
                until = status.get("until", "unknown")
                banner = html.Div(
                    [
                        html.Span("🔧", style={"marginRight": "6px"}),
                        f"Maintenance in progress until {until}",
                    ],
                    className="alert alert-warning",
                )
                return banner, {"display": "block", "margin": "10px 0"}
        except Exception:
            logger.debug("check_maintenance_mode failed (non-critical)")

        return "", {"display": "none"}
