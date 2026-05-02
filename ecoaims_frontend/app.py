import dash
import base64
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
import json
import requests

# ── Load .env manually (no python-dotnet dependency) ──────────────────────
def _load_env_file(path: str) -> None:
    """Minimal .env parser: sets os.environ for each KEY=val line."""
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                k = key.strip()
                v = val.strip().strip("\"'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass  # best-effort

_env_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),   # project root
    os.path.join(os.getcwd(), ".env"),                                   # cwd
]
for _p in _env_candidates:
    _load_env_file(_p)
# ──────────────────────────────────────────────────────────────────────────

from flask import Response, redirect, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL, MIN_HISTORY_FOR_COMPARISON
from ecoaims_frontend.layouts.main_layout import create_layout
from ecoaims_frontend.layouts.login_layout import create_login_layout
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
from ecoaims_frontend.callbacks.indoor_callbacks import register_indoor_callbacks
from ecoaims_frontend.callbacks.auth_callbacks import register_auth_callbacks
from ecoaims_frontend.layouts.reports_layout import create_reports_callbacks
from ecoaims_frontend.services.optimization_service import prometheus_metrics_text

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
_STARTED_AT = datetime.now(timezone.utc).isoformat()
_AUTH_ATTEMPTS_LOCK = threading.Lock()
_AUTH_FAILED_ATTEMPTS_BY_IP: dict[str, list[float]] = {}


def _as_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return bool(default)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)

def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[0]
    return request.remote_addr or "-"

def _is_request_secure() -> bool:
    if request.is_secure:
        return True
    xfproto = (request.headers.get("X-Forwarded-Proto") or "").strip().lower()
    return xfproto == "https"

def _require_https_redirect() -> Response | None:
    if not _as_bool(os.getenv("ECOAIMS_FORCE_HTTPS"), False):
        return None
    if _is_request_secure():
        return None
    host = request.headers.get("Host") or ""
    if not host:
        return None
    return redirect("https://" + host + request.full_path.rstrip("?"), code=307)

def _auth_enabled() -> bool:
    return _as_bool(os.getenv("ECOAIMS_AUTH_ENABLED"), True)

def _auth_allowed_paths(path: str) -> bool:
    p = str(path or "")
    if p in {"/login", "/captcha.svg", "/logout", "/api/auth/captcha", "/api/auth/login"}:
        return True
    if p.startswith("/manual/"):
        return True
    if p.startswith("/instructions/"):
        return True
    if p in {"/__runtime", "/metrics", "/favicon.ico"}:
        return True
    # Dash internal routes (layout, dependencies, callbacks, component suites, etc.)
    # must bypass the before_request gateway so the Dash frontend can fetch them.
    # Authentication is enforced inside _resolve_layout() for the layout itself,
    # and callbacks validate tokens/backend auth independently.
    if p.startswith("/_dash-"):
        return True
    if p.startswith("/_reload-hash"):
        return True
    return False

def _is_authenticated() -> bool:
    try:
        return bool(session.get("ecoaims_admin_auth") is True)
    except Exception:
        return False

def _csrf_token() -> str:
    tok = session.get("ecoaims_csrf")
    if isinstance(tok, str) and tok.strip():
        return tok
    tok = secrets.token_urlsafe(24)
    session["ecoaims_csrf"] = tok
    return tok

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(server.secret_key, salt="ecoaims_auth_v1")

def _csrf_from_request(body: dict) -> tuple[str, str]:
    hdr = str(request.headers.get("X-CSRF-Token") or "").strip()
    b = str((body or {}).get("csrf_token") or "").strip()
    return hdr, b

def _csrf_ok(body: dict, *, token_payload: dict | None) -> bool:
    hdr, b = _csrf_from_request(body)
    if not hdr or not b:
        return False
    if not secrets.compare_digest(hdr, b):
        return False
    sess_csrf = session.get("ecoaims_csrf")
    if isinstance(sess_csrf, str) and sess_csrf:
        return secrets.compare_digest(str(sess_csrf), hdr)
    if isinstance(token_payload, dict):
        tok_csrf = str(token_payload.get("csrf_token") or "").strip()
        return bool(tok_csrf) and secrets.compare_digest(tok_csrf, hdr)
    return False

def _captcha_ttl_s() -> int:
    try:
        return max(30, int(os.getenv("ECOAIMS_CAPTCHA_TTL_S", "300") or "300"))
    except Exception:
        return 300

def _auth_mode() -> str:
    return str(os.getenv("ECOAIMS_AUTH_MODE") or "proxy").strip().lower()

def _auth_backend_base_url() -> str:
    v = os.getenv("ECOAIMS_AUTH_BACKEND_BASE_URL") or os.getenv("ECOAIMS_API_BASE_URL") or ""
    return str(v).strip().rstrip("/")

def _backend_cookie_header() -> str:
    return str(request.headers.get("Cookie") or "").strip()

def _backend_request(method: str, path: str, *, json_body: dict | None = None, headers: dict | None = None) -> requests.Response:
    base = _auth_backend_base_url()
    url = base + (path if path.startswith("/") else "/" + path)
    hdrs = dict(headers or {})
    cookie_hdr = _backend_cookie_header()
    if cookie_hdr:
        hdrs["Cookie"] = cookie_hdr
    return requests.request(method.upper(), url, json=json_body, headers=hdrs, timeout=6.5, stream=True)

def _extract_set_cookie_headers(resp: requests.Response) -> list[str]:
    raw = getattr(resp, "raw", None)
    hdrs = getattr(raw, "headers", None)
    if hdrs is not None:
        try:
            vals = hdrs.get_all("Set-Cookie")  # type: ignore[attr-defined]
            if isinstance(vals, list):
                return [str(v) for v in vals if str(v).strip()]
        except Exception:
            pass
    v = resp.headers.get("set-cookie")
    if not v:
        return []
    return [str(v)]

def _json_response(payload: dict, status: int, *, extra_headers: dict | None = None) -> Response:
    resp = server.response_class(
        response=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        status=status,
        mimetype="application/json",
    )
    if isinstance(extra_headers, dict):
        for k, vv in extra_headers.items():
            resp.headers[str(k)] = str(vv)
    return resp

def _rate_limit_window_s() -> int:
    try:
        return max(60, int(os.getenv("ECOAIMS_AUTH_RATE_LIMIT_WINDOW_S", "900") or "900"))
    except Exception:
        return 900

def _rate_limit_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("ECOAIMS_AUTH_RATE_LIMIT_MAX", "5") or "5"))
    except Exception:
        return 5

def _rate_limit_check(ip: str) -> tuple[bool, int]:
    now = time.time()
    win = float(_rate_limit_window_s())
    maxn = _rate_limit_max_attempts()
    with _AUTH_ATTEMPTS_LOCK:
        arr = _AUTH_FAILED_ATTEMPTS_BY_IP.get(ip) or []
        arr = [t for t in arr if (now - t) <= win]
        _AUTH_FAILED_ATTEMPTS_BY_IP[ip] = arr
        if len(arr) >= maxn:
            oldest = min(arr) if arr else now
            retry = int(max(1.0, win - (now - oldest)))
            return False, retry
        return True, 0

def _rate_limit_record_failed(ip: str) -> None:
    now = time.time()
    win = float(_rate_limit_window_s())
    with _AUTH_ATTEMPTS_LOCK:
        arr = _AUTH_FAILED_ATTEMPTS_BY_IP.get(ip) or []
        arr = [t for t in arr if (now - t) <= win]
        arr.append(now)
        _AUTH_FAILED_ATTEMPTS_BY_IP[ip] = arr

def _rate_limit_clear(ip: str) -> None:
    with _AUTH_ATTEMPTS_LOCK:
        _AUTH_FAILED_ATTEMPTS_BY_IP.pop(ip, None)

def _safe_next_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return "/"
    if s.startswith("//"):
        return "/"
    if s.startswith("/") and not s.startswith("/\\"):
        return s
    return "/"

def _new_captcha_text() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))

def _captcha_svg(text: str) -> str:
    w, h = 220, 64
    jitter = [(secrets.randbelow(7) - 3, secrets.randbelow(7) - 3) for _ in text]
    parts = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>")
    parts.append("<defs><linearGradient id='bg' x1='0' x2='1' y1='0' y2='1'><stop offset='0' stop-color='#f7f9fb'/><stop offset='1' stop-color='#eef2f7'/></linearGradient></defs>")
    parts.append("<rect x='0' y='0' width='100%' height='100%' rx='10' fill='url(#bg)' stroke='#cfd6df'/>")
    for _ in range(8):
        x1 = secrets.randbelow(w)
        y1 = secrets.randbelow(h)
        x2 = secrets.randbelow(w)
        y2 = secrets.randbelow(h)
        sw = 1 + secrets.randbelow(2)
        parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#c7d1db' stroke-width='{sw}' opacity='0.8'/>")
    for _ in range(160):
        x = secrets.randbelow(w)
        y = secrets.randbelow(h)
        r = 0.5 + (secrets.randbelow(10) / 10.0)
        parts.append(f"<circle cx='{x}' cy='{y}' r='{r}' fill='#b9c6d3' opacity='0.55'/>")
    x = 18
    for i, ch in enumerate(text):
        dx, dy = jitter[i]
        rot = (secrets.randbelow(23) - 11)
        y = 42 + dy
        parts.append(
            f"<text x='{x + dx}' y='{y}' font-family='Arial, sans-serif' font-size='30' font-weight='700' fill='#2c3e50' transform='rotate({rot} {x + dx} {y})'>{ch}</text>"
        )
        x += 32
    parts.append("</svg>")
    return "".join(parts)

def _render_login_html(*, csrf: str, post_login_redirect: str) -> str:
    esc_redirect = str(post_login_redirect or "/").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    esc_csrf = str(csrf or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    mailto = "mailto:juli001@brin.go.id?subject=Permintaan%20Password%20Baru%20-%20Admin%20ECOAIMS"
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta name="csrf-token" content="{esc_csrf}"/>
  <title>Admin Login - ECOAIMS</title>
  <style>
    :root {{
      --bg: #0b1220;
      --card: rgba(255,255,255,0.92);
      --text: #1f2d3d;
      --muted: #6b7b8c;
      --primary: #2980b9;
      --danger: #c0392b;
      --ok: #1e8449;
      --border: #cfd6df;
    }}
    html,body {{ height:100%; }}
    body {{
      margin:0;
      font-family: Arial, sans-serif;
      background: radial-gradient(1200px 800px at 20% 10%, #123b5a 0%, var(--bg) 55%) fixed;
      display:flex;
      align-items:center;
      justify-content:center;
      padding:18px;
      color: var(--text);
    }}
    .wrap {{ width:100%; max-width: 440px; }}
    .brand {{
      color:#fff;
      text-align:center;
      margin-bottom:12px;
    }}
    .brand .title {{ font-size:22px; font-weight:800; letter-spacing:0.5px; }}
    .brand .sub {{ font-size:13px; opacity:0.85; margin-top:4px; }}
    .card {{
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.25);
      box-shadow: 0 16px 40px rgba(0,0,0,0.35);
      border-radius: 14px;
      padding: 18px 16px;
      backdrop-filter: blur(6px);
    }}
    .row {{ margin-top: 12px; }}
    label {{ display:block; font-size:13px; font-weight:700; margin-bottom:6px; }}
    input {{
      width: 100%;
      box-sizing: border-box;
      padding: 12px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      outline: none;
      font-size: 14px;
      background: #fff;
    }}
    input:focus {{ border-color: #7fb3d5; box-shadow: 0 0 0 3px rgba(41,128,185,0.12); }}
    .err {{ font-size: 12px; color: var(--danger); margin-top: 6px; min-height: 14px; }}
    .toperr {{
      margin-top: 10px;
      background: #fdecea;
      border: 1px solid #f5c6cb;
      color: #7b241c;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 13px;
      display:none;
    }}
    .captcha {{
      display:flex;
      gap:10px;
      align-items:center;
      flex-wrap: wrap;
      background: #d9dde2;
      padding: 10px;
      border-radius: 12px;
      border: 1px solid #b7c0cc;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.55);
    }}
    .captcha img {{
      width: 220px;
      height: 64px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background:#fff;
      flex: none;
      display: block;
      max-width: 100%;
      opacity: 1;
      filter: contrast(1.15) saturate(1.05) brightness(1.05);
      box-shadow: 0 1px 0 rgba(255,255,255,0.75) inset, 0 10px 24px rgba(0,0,0,0.18);
    }}
    .btnrow {{
      display:flex;
      gap:10px;
      align-items:center;
      justify-content: space-between;
      margin-top: 14px;
    }}
    button {{
      border: none;
      border-radius: 10px;
      padding: 12px 14px;
      font-weight: 800;
      cursor: pointer;
      font-size: 14px;
    }}
    .btn-primary {{
      background: var(--primary);
      color: #fff;
      width: 100%;
    }}
    .btn-primary[disabled] {{
      opacity: 0.65;
      cursor: not-allowed;
    }}
    .btn-secondary {{
      background: #ecf0f1;
      color: #2c3e50;
      border: 1px solid var(--border);
      padding: 10px 12px;
      flex: none;
      white-space: nowrap;
    }}
    .hint {{
      margin-top: 10px;
      display:flex;
      justify-content: space-between;
      align-items:center;
      font-size: 13px;
    }}
    .hint a {{
      color: #21618c;
      text-decoration: none;
      font-weight: 700;
    }}
    .hint a:hover {{ text-decoration: underline; }}
    .footer {{
      margin-top: 12px;
      text-align:center;
      color: rgba(255,255,255,0.72);
      font-size: 12px;
    }}
    @media (max-width: 420px) {{
      .captcha {{ flex-direction: column; align-items: stretch; }}
      .captcha img {{ width: 100%; height: 64px; }}
      .btn-secondary {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">
      <div class="title">ECOAIMS Admin</div>
      <div class="sub">Authentication Gateway</div>
    </div>
    <div class="card">
      <div id="toperr" class="toperr"></div>
      <form id="login-form" autocomplete="off">
        <input type="hidden" name="csrf_token" value="{esc_csrf}"/>
        <input type="hidden" name="next" value="{esc_redirect}"/>
        <div class="row">
          <label for="username">Username</label>
          <input id="username" name="username" placeholder="Masukkan username admin" inputmode="text" autocapitalize="none" spellcheck="false" required/>
          <div id="err-username" class="err"></div>
        </div>
        <div class="row">
          <label for="password">Password</label>
          <input id="password" name="password" type="password" placeholder="Masukkan password" required/>
          <div id="err-password" class="err"></div>
        </div>
        <div class="row">
          <label>Captcha</label>
          <div class="captcha">
            <img id="captcha-img" alt="captcha" src=""/>
            <button id="btn-refresh" type="button" class="btn-secondary">Refresh</button>
          </div>
          <div class="row" style="margin-top:10px;">
            <input id="captcha" name="captcha" placeholder="Masukkan captcha" inputmode="text" autocapitalize="none" spellcheck="false" required/>
            <div id="err-captcha" class="err"></div>
          </div>
        </div>
        <div class="btnrow">
          <button id="btn-login" class="btn-primary" type="submit">Login</button>
        </div>
        <div class="hint">
          <a href="{mailto}">Reset Password</a>
          <span id="status" style="color:var(--muted);font-weight:700;"></span>
        </div>
      </form>
    </div>
    <div class="footer">© ECOAIMS</div>
  </div>
  <script>
    const $ = (id) => document.getElementById(id);
    let csrf = document.querySelector('meta[name="csrf-token"]').getAttribute('content') || '';
    let csrfSession = '';
    let captchaToken = '';
    const btnLogin = $('btn-login');
    btnLogin.disabled = true;
    const setCaptchaPlaceholder = (message) => {{
      const msg = String(message || 'Captcha tidak tersedia');
      const svg =
        "<svg xmlns='http://www.w3.org/2000/svg' width='220' height='64' viewBox='0 0 220 64'>" +
        "<rect x='0' y='0' width='220' height='64' rx='10' fill='#f7f9fb' stroke='#cfd6df'/>" +
        "<text x='110' y='30' text-anchor='middle' font-family='Arial, sans-serif' font-size='12' font-weight='700' fill='#7b241c'>Captcha error</text>" +
        "<text x='110' y='48' text-anchor='middle' font-family='Arial, sans-serif' font-size='10' fill='#566573'>" +
        msg.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') +
        "</text></svg>";
      $('captcha-img').src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svg)));
    }};
    const applyCaptcha = (payload) => {{
      if (!payload) return;
      if (payload.csrf_token) {{
        csrf = String(payload.csrf_token);
        document.querySelector('meta[name="csrf-token"]').setAttribute('content', csrf);
        const h = document.querySelector('input[name="csrf_token"]');
        if (h) h.value = csrf;
      }}
      if (payload.csrf_session) {{
        csrfSession = String(payload.csrf_session);
      }}
      if (payload.captcha_token) {{
        captchaToken = String(payload.captcha_token);
      }}
      if (payload.captcha_image) {{
        $('captcha-img').src = String(payload.captcha_image);
        btnLogin.disabled = false;
      }}
    }};
    const refreshCaptcha = async () => {{
      btnLogin.disabled = true;
      try {{
        const resp = await fetch('api/auth/captcha', {{ method: 'GET', credentials: 'include' }});
        if (!resp.ok) {{
          throw new Error('captcha_http_' + resp.status);
        }}
        const data = await resp.json().catch(() => ({{}}));
        applyCaptcha(data);
        if (!($('captcha-img').src || '').trim()) {{
          throw new Error('captcha_missing_image');
        }}
        setTopErr('');
      }} catch (e) {{
        setTopErr('Captcha tidak tersedia. Pastikan FE terbaru dan backend auth aktif, lalu refresh halaman.');
        setCaptchaPlaceholder('Refresh halaman');
      }}
    }};
    $('btn-refresh').addEventListener('click', () => {{
      refreshCaptcha();
      $('captcha').value = '';
      $('captcha').focus();
    }});
    const setErr = (field, msg) => {{
      const el = $('err-' + field);
      if (el) el.textContent = msg || '';
    }};
    const setTopErr = (msg) => {{
      const el = $('toperr');
      if (!msg) {{
        el.style.display = 'none';
        el.textContent = '';
        return;
      }}
      el.textContent = msg;
      el.style.display = 'block';
    }};
    const validate = () => {{
      let ok = true;
      const u = ($('username').value || '').trim();
      const p = ($('password').value || '');
      const c = ($('captcha').value || '').trim();
      setErr('username', '');
      setErr('password', '');
      setErr('captcha', '');
      if (!u) {{ setErr('username', 'Username wajib diisi.'); ok = false; }}
      else if (u.length < 4) {{ setErr('username', 'Username terlalu pendek.'); ok = false; }}
      if (!p) {{ setErr('password', 'Password wajib diisi.'); ok = false; }}
      else if (p.length < 6) {{ setErr('password', 'Password terlalu pendek.'); ok = false; }}
      if (!c) {{ setErr('captcha', 'Captcha wajib diisi.'); ok = false; }}
      else if (c.length < 4) {{ setErr('captcha', 'Captcha tidak valid.'); ok = false; }}
      return ok;
    }};
    ['username','password','captcha'].forEach((k) => {{
      $(k).addEventListener('input', () => {{ validate(); setTopErr(''); }});
    }});
    $('login-form').addEventListener('submit', async (e) => {{
      e.preventDefault();
      setTopErr('');
      $('status').textContent = '';
      if (!validate()) return;
      const btn = $('btn-login');
      btn.disabled = true;
      const oldText = btn.textContent;
      btn.textContent = 'Memproses...';
      $('status').textContent = 'Memvalidasi...';
      try {{
        const username = ($('username').value || '').trim();
        const password = ($('password').value || '');
        const captcha = ($('captcha').value || '').trim();
        const next = (new URLSearchParams(new FormData($('login-form')))).get('next') || '/';
        const payload = {{
          username,
          password,
          captcha,
          csrf_token: csrf,
          csrf_session: csrfSession,
          captcha_token: captchaToken,
          next
        }};
        const resp = await fetch('api/auth/login', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          }},
          body: JSON.stringify(payload),
          credentials: 'include'
        }});
        const data = await resp.json().catch(() => ({{}}));
        if (resp.status === 200 && data && (data.ok || data.access_token)) {{
          $('status').textContent = 'OK. Mengalihkan...';
          window.location.href = data.redirect || '/';
          return;
        }}
        const msg = (data && (data.error || data.detail)) ? String(data.error || data.detail) : 'Login gagal. Periksa input Anda dan coba lagi.';
        setTopErr(msg);
        $('status').textContent = '';
        refreshCaptcha();
        $('captcha').value = '';
      }} catch (err) {{
        setTopErr('Terjadi gangguan jaringan. Silakan coba lagi.');
        refreshCaptcha();
        $('captcha').value = '';
      }} finally {{
        btn.disabled = false;
        btn.textContent = oldText;
      }}
    }});
    refreshCaptcha();
  </script>
</body>
</html>"""

def create_app():
    """
    Factory function to create and configure the Dash application.
    """
    app = dash.Dash(__name__)
    
    # Use a function-based layout so the auth check happens per-request
    # (not at import time when there is no Flask session yet).
    def _resolve_layout():
        try:
            if _auth_enabled() and not _is_authenticated():
                logger.debug("_resolve_layout: not authenticated (auth_enabled=%s), returning login layout", _auth_enabled())
                return create_login_layout()
            logger.debug("_resolve_layout: authenticated (auth_enabled=%s), returning dashboard layout", _auth_enabled())
            return create_layout()
        except Exception as e:
            logger.error("_resolve_layout error: %s", e, exc_info=True)
            # Fallback to login layout on error
            return create_login_layout()
    app.layout = _resolve_layout
    
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
    register_indoor_callbacks(app)
    register_about_callbacks(app)
    register_auth_callbacks(app)
    create_reports_callbacks(app)
    
    return app

# Initialize the Dash app
app = create_app()
server = app.server # Expose server for WSGI deployment (e.g., Gunicorn)

if _as_bool(os.getenv("ECOAIMS_TRUST_PROXY"), True):
    server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1)

server.secret_key = os.getenv("ECOAIMS_SESSION_SECRET") or secrets.token_urlsafe(32)
server.config["SESSION_COOKIE_HTTPONLY"] = True
server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
server.config["SESSION_COOKIE_SECURE"] = _as_bool(os.getenv("ECOAIMS_SESSION_COOKIE_SECURE"), False)
server.permanent_session_lifetime = timedelta(minutes=int(os.getenv("ECOAIMS_SESSION_TTL_MIN", "720") or "720"))

@server.before_request
def _ecoaims_auth_gateway():
    r = _require_https_redirect()
    if r is not None:
        return r
    if not _auth_enabled():
        return None
    if _auth_allowed_paths(request.path):
        return None
    if _is_authenticated():
        return None
    return redirect("/login?next=" + request.full_path.rstrip("?"), code=302)

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

@server.get("/captcha.svg")
def captcha_svg():
    if not _auth_enabled():
        return Response(status=404)
    txt = _new_captcha_text()
    session["ecoaims_captcha"] = txt
    session["ecoaims_captcha_expires_at"] = int(time.time()) + _captcha_ttl_s()
    svg = _captcha_svg(txt)
    resp = Response(svg, status=200, mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp

@server.get("/api/auth/captcha")
def api_auth_captcha():
    """
    Generate a CAPTCHA locally (no backend dependency).
    This endpoint is used by the Flask login page's JavaScript.
    """
    if not _auth_enabled():
        return _json_response({"ok": False, "error": "auth_disabled"}, 404)

    # Always generate CAPTCHA locally — no backend proxy needed.
    # The backend does not provide a /api/auth/captcha endpoint,
    # so proxying would always return 404 / "Captcha tidak tersedia".
    txt = _new_captcha_text()
    ttl_s = _captcha_ttl_s()
    now_i = int(time.time())
    session["ecoaims_captcha"] = txt
    session["ecoaims_captcha_expires_at"] = now_i + ttl_s
    csrf = secrets.token_urlsafe(24)
    session["ecoaims_csrf"] = csrf

    token_payload = {"captcha": txt, "csrf_token": csrf, "issued_at": now_i, "ttl_s": ttl_s}
    captcha_token = _serializer().dumps(token_payload)

    svg = _captcha_svg(txt)
    data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    payload = {
        "csrf_token": csrf,
        "captcha_image": data_url,
        "captcha_text": txt,
        "ttl_s": ttl_s,
        "captcha_token": captcha_token,
        "csrf_session": captcha_token,
    }
    resp = _json_response(payload, 200)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp

@server.get("/login")
def login_page():
    if not _auth_enabled():
        return redirect("/", code=302)
    post_redirect = os.getenv("ECOAIMS_POST_LOGIN_REDIRECT") or "/"
    html = _render_login_html(csrf="", post_login_redirect=post_redirect)
    return Response(html, status=200, mimetype="text/html; charset=utf-8")

def _handle_login_submit():
    if not _auth_enabled():
        return _json_response({"ok": False, "error": "auth_disabled"}, 404)
    body = {}
    if request.is_json:
        try:
            body = request.get_json(silent=True) or {}
        except Exception:
            body = {}
    else:
        body = dict(request.form or {})
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    captcha = str(body.get("captcha") or "").strip()
    next_url = _safe_next_url(str(body.get("next") or "").strip() or (os.getenv("ECOAIMS_POST_LOGIN_REDIRECT") or "/"))
    csrf_session = str(body.get("csrf_session") or "").strip()
    captcha_token = str(body.get("captcha_token") or "").strip()

    if not username or not password or not captcha:
        return _json_response({"detail": "invalid_payload"}, 400)

    hdr_csrf, body_csrf = _csrf_from_request(body)
    if not hdr_csrf or not body_csrf or (not secrets.compare_digest(hdr_csrf, body_csrf)):
        return _json_response({"detail": "csrf_invalid"}, 403)

    if _auth_mode() == "proxy":
        payload = {
            "username": username,
            "password": password,
            "captcha": captcha,
            "csrf_token": body_csrf,
        }
        if csrf_session:
            payload["csrf_session"] = csrf_session
        if captcha_token:
            payload["captcha_token"] = captcha_token

        try:
            be = _backend_request(
                "POST",
                "/api/auth/login",
                json_body=payload,
                headers={"X-CSRF-Token": hdr_csrf, "Content-Type": "application/json"},
            )
        except Exception:
            return _json_response({"detail": "backend_unreachable"}, 503)

        content = be.content or b"{}"
        resp = Response(content, status=int(be.status_code), mimetype=str(be.headers.get("content-type") or "application/json"))
        for sc in _extract_set_cookie_headers(be):
            resp.headers.add("Set-Cookie", sc)
        rid = be.headers.get("x-request-id")
        if rid:
            resp.headers["x-request-id"] = str(rid)
        if int(be.status_code) == 200:
            session["ecoaims_admin_auth"] = True
            session["ecoaims_admin_auth_at"] = int(time.time())
            session.permanent = True
        return resp

    token_payload = None
    if captcha_token:
        try:
            token_payload = _serializer().loads(captcha_token, max_age=_captcha_ttl_s() + 15)
        except (SignatureExpired, BadSignature):
            token_payload = None
        except Exception:
            token_payload = None

    if not _csrf_ok(body, token_payload=token_payload):
        return _json_response({"detail": "csrf_invalid"}, 403)

    ip = _client_ip()
    ok_rate, retry_after = _rate_limit_check(ip)
    if not ok_rate:
        resp = server.response_class(
            response=json.dumps({"ok": False, "error": "too_many_attempts"}, sort_keys=True, separators=(",", ":")),
            status=429,
            mimetype="application/json",
        )
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    expected_captcha = session.get("ecoaims_captcha")
    exp_at = session.get("ecoaims_captcha_expires_at")
    try:
        exp_at_i = int(exp_at)
    except Exception:
        exp_at_i = 0
    now_i = int(time.time())
    captcha_ok = False
    if isinstance(expected_captcha, str) and expected_captcha and exp_at_i > 0 and now_i <= exp_at_i:
        captcha_ok = secrets.compare_digest(str(expected_captcha), captcha)
    elif isinstance(token_payload, dict) and csrf_session and secrets.compare_digest(csrf_session, captcha_token):
        tok_c = str(token_payload.get("captcha") or "")
        captcha_ok = bool(tok_c) and secrets.compare_digest(tok_c, captcha)
    else:
        return server.response_class(
            response=json.dumps({"ok": False, "error": "captcha_missing"}, sort_keys=True, separators=(",", ":")),
            status=400,
            mimetype="application/json",
        )

    admin_user = os.getenv("ECOAIMS_ADMIN_USERNAME") or ""
    admin_hash = os.getenv("ECOAIMS_ADMIN_PASSWORD_HASH") or ""
    admin_plain = os.getenv("ECOAIMS_ADMIN_PASSWORD_PLAINTEXT") or ""
    allow_insecure_default = _as_bool(os.getenv("ECOAIMS_ALLOW_INSECURE_DEFAULT_ADMIN"), False)
    if not admin_user or not admin_hash:
        if not allow_insecure_default:
            logger.error("Auth misconfigured: ECOAIMS_ADMIN_USERNAME/ECOAIMS_ADMIN_PASSWORD_HASH must be set.")
            return server.response_class(
                response=json.dumps({"ok": False, "error": "auth_misconfigured"}, sort_keys=True, separators=(",", ":")),
                status=500,
                mimetype="application/json",
            )
        admin_user = "AdminECOAIMS"
        admin_plain = admin_plain or "Admin3C041M5"

    user_ok = secrets.compare_digest(admin_user, username)
    if allow_insecure_default and (not admin_hash):
        pass_ok = secrets.compare_digest(str(admin_plain), password)
    else:
        pass_ok = False
        try:
            pass_ok = bool(check_password_hash(admin_hash, password))
        except Exception:
            pass_ok = False

    ok = bool(captcha_ok and user_ok and pass_ok)
    logger.info(
        "auth_attempt ok=%s ip=%s ts=%s captcha_ok=%s user_ok=%s pass_ok=%s username=%s captcha_len=%d",
        ok, ip, _now_iso(), captcha_ok, user_ok, pass_ok,
        username, len(captcha),
    )
    if not ok:
        if not captcha_ok:
            logger.warning("login_fail_captcha ip=%s expected=%s submitted=%s", ip, session.get("ecoaims_captcha","?"), captcha)
        if not user_ok:
            logger.warning("login_fail_username ip=%s expected=%s submitted=%s", ip, admin_user, username)
        if not pass_ok:
            logger.warning("login_fail_password ip=%s username=%s", ip, username)
    if not ok:
        _rate_limit_record_failed(ip)
        session["ecoaims_captcha"] = ""
        session["ecoaims_captcha_expires_at"] = 0
        return server.response_class(
            response=json.dumps({"ok": False, "error": "login_failed"}, sort_keys=True, separators=(",", ":")),
            status=401,
            mimetype="application/json",
        )

    _rate_limit_clear(ip)
    session["ecoaims_admin_auth"] = True
    session["ecoaims_admin_auth_at"] = int(time.time())
    session.permanent = True
    return server.response_class(
        response=json.dumps({"ok": True, "redirect": next_url or "/"}, sort_keys=True, separators=(",", ":")),
        status=200,
        mimetype="application/json",
    )

@server.post("/api/auth/login")
def api_auth_login():
    return _handle_login_submit()

@server.post("/login")
def login_submit():
    return _handle_login_submit()

@server.get("/logout")
def logout():
    if not _auth_enabled():
        return redirect("/", code=302)
    session.clear()
    return redirect("/login", code=302)


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

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

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
