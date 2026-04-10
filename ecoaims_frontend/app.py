import dash
import logging
import os
from datetime import datetime, timezone
import json
import requests

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL, MIN_HISTORY_FOR_COMPARISON
from ecoaims_frontend.layouts.main_layout import create_layout
from ecoaims_frontend.callbacks.main_callbacks import register_callbacks
from ecoaims_frontend.callbacks.forecasting_callbacks import register_forecasting_callbacks
from ecoaims_frontend.callbacks.optimization_callbacks import register_optimization_callbacks
from ecoaims_frontend.callbacks.settings_callbacks import register_settings_callbacks
from ecoaims_frontend.callbacks.bms_callbacks import register_bms_callbacks
from ecoaims_frontend.callbacks.precooling_callbacks import register_precooling_callbacks
from ecoaims_frontend.callbacks.precooling_settings_callbacks import register_precooling_settings_callbacks
from ecoaims_frontend.callbacks.readiness_callbacks import register_readiness_callbacks
from ecoaims_frontend.callbacks.home_callbacks import register_home_callbacks
from ecoaims_frontend.callbacks.about_callbacks import register_about_callbacks
from ecoaims_frontend.layouts.reports_layout import create_reports_callbacks
from ecoaims_frontend.services.optimization_service import prometheus_metrics_text

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
_STARTED_AT = datetime.now(timezone.utc).isoformat()


def _as_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return bool(default)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)

def create_app():
    """
    Factory function to create and configure the Dash application.
    """
    app = dash.Dash(__name__)
    
    # Set Layout
    app.layout = create_layout()
    
    # Register Callbacks
    register_readiness_callbacks(app)
    register_home_callbacks(app)
    register_callbacks(app)
    register_forecasting_callbacks(app)
    register_optimization_callbacks(app)
    register_settings_callbacks(app)
    register_bms_callbacks(app)
    register_precooling_callbacks(app)
    register_precooling_settings_callbacks(app)
    register_about_callbacks(app)
    create_reports_callbacks(app)
    
    return app

# Initialize the Dash app
app = create_app()
server = app.server # Expose server for WSGI deployment (e.g., Gunicorn)

@server.get("/__runtime")
def runtime_info():
    payload = {
        "pid": os.getpid(),
        "started_at": _STARTED_AT,
        "ecoaims_api_base_url": (ECOAIMS_API_BASE_URL or "").rstrip("/"),
        "dash_host": os.getenv("ECOAIMS_DASH_HOST") or os.getenv("ECOAIMS_FRONTEND_HOST") or "127.0.0.1",
        "dash_port": int(os.getenv("ECOAIMS_DASH_PORT") or os.getenv("ECOAIMS_FRONTEND_PORT") or "8050"),
        "dash_debug": _as_bool(os.getenv("ECOAIMS_DASH_DEBUG"), False),
        "dash_use_reloader": _as_bool(os.getenv("ECOAIMS_DASH_USE_RELOADER"), False),
    }
    return server.response_class(
        response=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        status=200,
        mimetype="application/json",
    )

@server.get("/manual/operator")
def manual_operator():
    try:
        here = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(here, "books", "MANUAL_BOOK_ID.md")
        with open(path, "r", encoding="utf-8") as f:
            md = f.read()
    except Exception as e:
        return server.response_class(response=f"<html><body><h3>Manual operator tidak ditemukan</h3><p>{e}</p></body></html>", status=404, mimetype="text/html")
    html_body = []
    html_body.append("<html><head><title>Manual Operator</title><style>body{font-family:Arial, sans-serif;max-width:900px;margin:20px auto;line-height:1.6} pre{white-space:pre-wrap;background:#f7f9fb;border:1px solid #d5d8dc;padding:12px;border-radius:6px} .bar{display:flex;gap:10px;margin-bottom:12px} a.btn{background:#3498db;color:#fff;padding:8px 12px;border-radius:6px;text-decoration:none} .note{color:#7f8c8d;font-size:12px}</style><script>function printPDF(){window.print();}</script></head><body>")
    html_body.append("<div class='bar'>")
    html_body.append("<a class='btn' href='javascript:void(0);' onclick='printPDF()'>Cetak ke PDF (browser)</a>")
    html_body.append("</div>")
    html_body.append("<pre>")
    html_body.append(md)
    html_body.append("</pre></body></html>")
    return server.response_class(response="".join(html_body), status=200, mimetype="text/html")

@server.get("/manual/research")
def manual_research():
    try:
        here = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(here, "books", "MANUAL_BOOK_RESEARCH_ID.md")
        with open(path, "r", encoding="utf-8") as f:
            md = f.read()
    except Exception as e:
        return server.response_class(response=f"<html><body><h3>Manual peneliti tidak ditemukan</h3><p>{e}</p></body></html>", status=404, mimetype="text/html")
    html_body = []
    html_body.append("<html><head><title>Manual Peneliti</title><style>body{font-family:Arial, sans-serif;max-width:900px;margin:20px auto;line-height:1.6} pre{white-space:pre-wrap;background:#f7f9fb;border:1px solid #d5d8dc;padding:12px;border-radius:6px} .bar{display:flex;gap:10px;margin-bottom:12px} a.btn{background:#3498db;color:#fff;padding:8px 12px;border-radius:6px;text-decoration:none} .note{color:#7f8c8d;font-size:12px}</style><script>function printPDF(){window.print();}</script></head><body>")
    html_body.append("<div class='bar'>")
    html_body.append("<a class='btn' href='javascript:void(0);' onclick='printPDF()'>Cetak ke PDF (browser)</a>")
    html_body.append("</div>")
    html_body.append("<pre>")
    html_body.append(md)
    html_body.append("</pre></body></html>")
    return server.response_class(response="".join(html_body), status=200, mimetype="text/html")

@server.get("/metrics")
def metrics():
    return server.response_class(response=prometheus_metrics_text(), status=200, mimetype="text/plain; version=0.0.4")


@server.get("/instructions/monitoring-history")
def instructions_monitoring_history():
    base = (ECOAIMS_API_BASE_URL or "").rstrip("/")
    diag_url = f"{base}/diag/monitoring" if base else ""
    diag = None
    diag_err = None
    required_min = int(MIN_HISTORY_FOR_COMPARISON)
    if diag_url:
        try:
            r = requests.get(diag_url, timeout=2.5)
            if r.status_code == 200:
                js = r.json()
                diag = js if isinstance(js, dict) else {"data": js}
                hist = diag.get("history") if isinstance(diag, dict) else None
                if isinstance(hist, dict) and hist.get("required_min_for_comparison") is not None:
                    try:
                        required_min = int(hist.get("required_min_for_comparison"))
                    except Exception:
                        required_min = int(MIN_HISTORY_FOR_COMPARISON)
            else:
                diag_err = f"http_{r.status_code}"
        except Exception as e:
            diag_err = f"{type(e).__name__}:{e}"

    suggested_records = max(int(required_min) * 2, 24)
    stream_id = "default"
    lines = [
        "<html><head><meta charset='utf-8'><title>ECO-AIMS Monitoring History Instructions</title></head><body style='font-family:Arial,sans-serif;max-width:980px;margin:20px auto;'>",
        "<h2>Monitoring Comparison: Instruksi Perbaikan Data Historis</h2>",
        "<p>Halaman ini membantu operator memperbaiki status <b>Comparison degraded</b> karena histori belum cukup.</p>",
        f"<p><b>Backend base URL:</b> {base or '(unset)'}</p>",
        f"<p><b>Endpoint diag:</b> <a href='{diag_url}' target='_blank'>{diag_url}</a></p>" if diag_url else "<p><b>Endpoint diag:</b> (backend base URL tidak tersedia)</p>",
        "<h3>Langkah cepat</h3>",
        "<ol>",
        "<li>Buka /diag/monitoring dan lihat field <code>history.required_min_for_comparison</code> serta <code>energy_data_records_count</code>.</li>",
        "<li>Jika histori kurang, seed/generate history di backend (development) lalu restart backend.</li>",
        "</ol>",
        "<h3>Contoh perintah (development seed via env)</h3>",
        "<pre style='background:#f4f6f7;border:1px solid #d5d8dc;padding:10px;border-radius:6px;'>"
        + "\n".join(
            [
                "export ECOAIMS_DEV_SEED_HISTORY=true",
                f"export ECOAIMS_DEV_SEED_HISTORY_RECORDS={suggested_records}",
                f"export ECOAIMS_DEV_SEED_STREAM_ID={stream_id}",
                f"export ECOAIMS_REQUIRED_MIN_FOR_COMPARISON={required_min}",
                "",
                "# restart backend setelah set env di atas",
            ]
        )
        + "</pre>",
        "<h3>Contoh cek endpoint</h3>",
        "<pre style='background:#f4f6f7;border:1px solid #d5d8dc;padding:10px;border-radius:6px;'>"
        + "\n".join(
            [
                f"curl -s {diag_url} | python -m json.tool" if diag_url else "curl -s http://127.0.0.1:8008/diag/monitoring | python -m json.tool",
                f"curl -s {base}/api/energy-data?stream_id={stream_id} | python -m json.tool" if base else "curl -s http://127.0.0.1:8008/api/energy-data?stream_id=default | python -m json.tool",
            ]
        )
        + "</pre>",
    ]

    if diag is not None:
        lines.append("<h3>Snapshot /diag/monitoring (ringkas)</h3>")
        lines.append("<pre style='background:#f4f6f7;border:1px solid #d5d8dc;padding:10px;border-radius:6px;white-space:pre-wrap;'>")
        lines.append(json.dumps(diag, indent=2, sort_keys=True)[:20000])
        lines.append("</pre>")
    elif diag_err:
        lines.append(f"<p><b>Catatan:</b> Tidak bisa mengambil /diag/monitoring sekarang: {diag_err}</p>")

    lines.append("</body></html>")
    return server.response_class(response="".join(lines), status=200, mimetype="text/html")

if __name__ == '__main__':
    # Run the application
    host = os.getenv("ECOAIMS_DASH_HOST") or os.getenv("ECOAIMS_FRONTEND_HOST") or "127.0.0.1"
    port = int(os.getenv("ECOAIMS_DASH_PORT") or os.getenv("ECOAIMS_FRONTEND_PORT") or "8050")
    dash_debug = _as_bool(os.getenv("ECOAIMS_DASH_DEBUG"), False)
    dash_use_reloader = _as_bool(os.getenv("ECOAIMS_DASH_USE_RELOADER"), False)
    logger.info(
        "Starting ECO-AIMS Dashboard pid=%s started_at=%s host=%s port=%s ecoaims_api_base_url=%s dash_debug=%s dash_use_reloader=%s",
        os.getpid(),
        _STARTED_AT,
        host,
        port,
        (ECOAIMS_API_BASE_URL or "").rstrip("/"),
        dash_debug,
        dash_use_reloader,
    )
    app.run(debug=dash_debug, host=host, port=port, use_reloader=dash_use_reloader)
