import json
import os
import time
import requests
from typing import Any
from dash import Input, Output, State, dcc, html

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL
from ecoaims_frontend.services.base_url_service import effective_base_url
from ecoaims_frontend.services.runtime_contract_mismatch import build_runtime_endpoint_contract_mismatch
from ecoaims_frontend.ui.runtime_contract_banner import render_runtime_endpoint_contract_mismatch_banner
from ecoaims_frontend.services import data_service, optimization_service, precooling_api, reports_api


def _extract_runbook_md(payload: dict, *, prefer_home: bool) -> tuple[str | None, str | None]:
    p = payload if isinstance(payload, dict) else {}
    candidates = [
        "home_runbook_md" if prefer_home else "runbook_md",
        "runbook_md" if prefer_home else "home_runbook_md",
        "operator_runbook_md",
        "operator_instructions_md",
        "how_to_run_md",
        "runbook",
        "instructions",
    ]
    for k in candidates:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip(), f"backend:{k}"

    for k in ("operator_steps", "run_steps", "steps"):
        v = p.get(k)
        if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            md = "\n".join([f"{i+1}. {str(x).strip()}" for i, x in enumerate(v) if str(x).strip()])
            if md.strip():
                return md, f"backend:{k}"

    how = p.get("how_to_run")
    if isinstance(how, dict):
        steps = how.get("steps")
        if isinstance(steps, list) and steps and all(isinstance(x, str) for x in steps):
            md = "\n".join([f"{i+1}. {str(x).strip()}" for i, x in enumerate(steps) if str(x).strip()])
            if md.strip():
                return md, "backend:how_to_run.steps"
        md = how.get("md") or how.get("markdown")
        if isinstance(md, str) and md.strip():
            return md.strip(), "backend:how_to_run.md"

    return None, None


def _fallback_md() -> str:
    return "\n".join(
        [
            "### Langkah cepat (operator)",
            "",
            "1. Pastikan backend kanonik berjalan (default: `http://127.0.0.1:8008`).",
            "2. Jalankan `make doctor-stack` untuk memastikan backend sehat, restart FE canonical, dan verifikasi `/__runtime`.",
            "3. Buka Dashboard: `http://127.0.0.1:8050`.",
            "4. Cek tab:",
            "   - Monitoring: data real-time + Sensor Health + Comparison",
            "   - Optimization: simulasi strategi distribusi energi",
            "   - Reports: ringkasan KPI dan export",
            "",
            "### Troubleshooting singkat",
            "",
            "- Jika Monitoring/Comparison menampilkan `Waiting for backend`: jalankan `make doctor-stack`.",
            "- Jika ada `runtime endpoint mismatch`: cek `GET /api/contracts/index` dan `GET /api/startup-info` di backend.",
            "- Jika data sedikit/terpotong: cek `GET /diag/monitoring` dan tingkatkan history/limit di backend.",
        ]
    )

def _build_runbook_from_startup_info(info: dict, *, bootstrap_base_url: str | None) -> str:
    i = info if isinstance(info, dict) else {}
    expected_host = i.get("expected_host")
    expected_port = i.get("expected_port")
    ready = i.get("ready")
    reasons = i.get("reasons_not_ready") if isinstance(i.get("reasons_not_ready"), list) else []
    required_endpoints = i.get("required_endpoints") if isinstance(i.get("required_endpoints"), list) else []
    canonical_ok = i.get("canonical_backend_identity_ok")
    capabilities = i.get("capabilities") if isinstance(i.get("capabilities"), dict) else {}

    canonical_base_url = None
    if isinstance(expected_host, str) and expected_host.strip() and isinstance(expected_port, int):
        canonical_base_url = f"http://{expected_host.strip()}:{int(expected_port)}"

    lines: list[str] = []
    lines.extend(["### Cara menjalankan ECOAIMS (step-by-step)", ""])
    lines.append("1. Jalankan backend kanonik (FastAPI).")
    if canonical_base_url:
        lines.append(f"   - Base URL kanonik (dari `/api/startup-info`): `{canonical_base_url}`")
    if bootstrap_base_url:
        lines.append(f"   - Base URL bootstrap FE: `{bootstrap_base_url}`")
    lines.append("2. Jalankan validasi + restart stack: `make doctor-stack`.")
    lines.append("3. Buka dashboard FE: `http://127.0.0.1:8050`.")
    lines.append("4. Buka tab Monitoring untuk memastikan data tampil, lalu lanjut ke Optimization/Reports sesuai kebutuhan.")
    lines.append("")
    lines.extend(["### Lokasi Backend & Live Pusher", ""])
    if canonical_base_url:
        lines.append(f"- Backend aktif: `{canonical_base_url}`")
    else:
        lines.append("- Backend aktif: gunakan base URL dari `ECOAIMS_API_BASE_URL` atau discovery.")
    lines.append("- Live Pusher (FE → BE): dikendalikan env `ECOAIMS_FE_PUSH_LIVE_STATE` (default: off).")
    lines.append("- Interval push default: 15 detik (dapat diubah di tab Settings).")
    lines.append("")
    lines.extend(["### Stop & Jalankan Ulang", ""])
    lines.append("- Hentikan backend: tutup terminal proses API (Ctrl+C) atau hentikan service terkait.")
    lines.append("- Jalankan ulang backend: `make run-api API_PORT=<port>` (contoh: 8009).")
    lines.append("- Jalankan ulang FE + verifikasi: `make doctor-stack` lalu buka `/__runtime` di FE.")
    lines.append("")
    lines.extend(["### Status backend (discovery)", ""])
    lines.append(f"- Ready: `{bool(ready)}`")
    if reasons:
        lines.append("- Reasons not ready:")
        for r in reasons:
            if isinstance(r, str) and r.strip():
                lines.append(f"  - {r.strip()}")
    lines.append(f"- Canonical identity OK: `{bool(canonical_ok)}`")
    lines.append("")
    lines.extend(["### Endpoint minimum (required_endpoints)", ""])
    if required_endpoints:
        for ep in required_endpoints:
            if isinstance(ep, str) and ep.strip():
                lines.append(f"- `{ep.strip()}`")
    else:
        lines.append("- (tidak tersedia di startup-info)")
    lines.append("")
    lines.extend(["### Kontrak & endpoint map", ""])
    if canonical_base_url:
        lines.append(f"- Registry kontrak: `{canonical_base_url}/api/contracts/index`")
        lines.append(f"- Startup info: `{canonical_base_url}/api/startup-info`")
        lines.append(f"- Diagnostic monitoring: `{canonical_base_url}/diag/monitoring`")
    else:
        lines.append("- Registry kontrak: `/api/contracts/index` (gunakan base URL backend)")
    lines.append("")
    lines.extend(["### Troubleshooting cepat", ""])
    lines.append("- Jika Monitoring/Comparison menunggu backend: jalankan `make doctor-stack` dan pastikan `/health` 200.")
    lines.append("- Jika ada contract mismatch: cek `/api/contracts/index` dan pastikan FE+BE versi sejalan.")
    lines.append("- Jika data sedikit/trimmed: cek `/diag/monitoring` dan tingkatkan history/limit di backend.")
    if capabilities:
        lines.append("")
        lines.extend(["### Capabilities (backend)", ""])
        for k, v in sorted(capabilities.items()):
            if isinstance(v, dict) and "ready" in v:
                lines.append(f"- `{k}`: ready={bool(v.get('ready'))}")
            else:
                lines.append(f"- `{k}`")
    return "\n".join(lines)

def _canonical_base_url_from_startup_info(info: dict) -> str | None:
    i = info if isinstance(info, dict) else {}
    expected_host = i.get("expected_host")
    expected_port = i.get("expected_port")
    if isinstance(expected_host, str) and expected_host.strip() and isinstance(expected_port, int):
        return f"http://{expected_host.strip()}:{int(expected_port)}"
    return None


def compute_home_runbook(readiness: dict | None) -> tuple[str, str]:
    r = readiness if isinstance(readiness, dict) else {}
    base = str(r.get("base_url") or (ECOAIMS_API_BASE_URL or "")).strip().rstrip("/")
    override = str(os.getenv("ECOAIMS_HOME_RUNBOOK_URL") or "").strip()
    if override:
        try:
            resp = requests.get(override, timeout=(1.5, 2.5))
            if resp.status_code == 200:
                if "application/json" in str(resp.headers.get("content-type") or "").lower():
                    js = resp.json()
                    if isinstance(js, dict):
                        md, _src = _extract_runbook_md(js, prefer_home=True)
                        if md:
                            return md, f"Sumber panduan: {override}"
                    if isinstance(js, str) and js.strip():
                        return js.strip(), f"Sumber panduan: {override}"
                txt = (resp.text or "").strip()
                if txt:
                    return txt, f"Sumber panduan: {override}"
        except Exception:
            pass

    if base:
        try:
            info = requests.get(f"{base}/api/startup-info", timeout=(1.5, 2.5)).json()
            if isinstance(info, dict):
                md, src = _extract_runbook_md(info, prefer_home=True)
                if md:
                    return md, f"Sumber panduan: {src}"
                canonical = _canonical_base_url_from_startup_info(info)
                if canonical and canonical.rstrip("/") != base.rstrip("/"):
                    try:
                        info2 = requests.get(f"{canonical}/api/startup-info", timeout=(1.5, 2.5)).json()
                        if isinstance(info2, dict):
                            md2, src2 = _extract_runbook_md(info2, prefer_home=True)
                            if md2:
                                return md2, f"Sumber panduan: {src2}"
                            return _build_runbook_from_startup_info(info2, bootstrap_base_url=base), "Sumber panduan: backend:/api/startup-info (auto)"
                    except Exception:
                        pass
                return _build_runbook_from_startup_info(info, bootstrap_base_url=base), "Sumber panduan: backend:/api/startup-info (auto)"
        except Exception:
            pass
    return _fallback_md(), "Sumber panduan: frontend (fallback)"


def compute_doctor_report(readiness: dict | None) -> tuple[str, str]:
    r = readiness if isinstance(readiness, dict) else {}
    base_url = effective_base_url(r)
    ts = int(time.time())
    url = f"{str(base_url).rstrip('/')}/diag/doctor" if base_url else ""
    report = {"ts": ts, "base_url": base_url, "endpoint": "/diag/doctor", "ok": False}
    msg = ""
    if not url:
        report["error"] = "backend_base_url_missing"
        msg = "base_url tidak tersedia."
        return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), msg
    try:
        resp = requests.get(url, timeout=(1.5, 2.5))
        report["http_status"] = int(resp.status_code)
        if int(resp.status_code) == 200:
            payload = resp.json()
            report["ok"] = True
            report["doctor"] = payload
            msg = f"OK (200) dari {url}"
        else:
            text = (resp.text or "").strip()
            report["error"] = "doctor_http_error"
            report["error_body"] = text[:400] if text else ""
            msg = f"HTTP {resp.status_code} dari {url}"
    except Exception as e:
        report["error"] = "doctor_request_failed"
        report["error_detail"] = str(e)[:400]
        msg = f"Gagal mengambil doctor report dari {url}"
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), msg


def _extract_doctor_contract_hashes(doctor_payload: dict) -> dict:
    d = doctor_payload if isinstance(doctor_payload, dict) else {}
    contracts = d.get("contracts") if isinstance(d.get("contracts"), dict) else {}
    out: dict = {}
    for k, v in contracts.items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, dict):
            continue
        h = v.get("hash") or v.get("contract_manifest_hash")
        if isinstance(h, str) and h.strip():
            out[k.strip()] = h.strip()
    return out


def _contract_change_banner(prev_snapshot: dict | None, next_snapshot: dict | None) -> tuple[Any, dict]:
    prev = prev_snapshot if isinstance(prev_snapshot, dict) else {}
    nxt = next_snapshot if isinstance(next_snapshot, dict) else {}
    prev_hashes = prev.get("contract_hashes") if isinstance(prev.get("contract_hashes"), dict) else {}
    next_hashes = nxt.get("contract_hashes") if isinstance(nxt.get("contract_hashes"), dict) else {}
    if not prev_hashes or not next_hashes:
        return "", {"display": "none"}

    changed = []
    for k in sorted(set(prev_hashes.keys()) | set(next_hashes.keys())):
        pv = prev_hashes.get(k)
        nv = next_hashes.get(k)
        if pv != nv:
            changed.append((k, pv, nv))
    if not changed:
        return "", {"display": "none"}

    rows = []
    for k, pv, nv in changed[:8]:
        rows.append(
            html.Div(
                [
                    html.Div(k, style={"fontWeight": "bold"}),
                    html.Div(f"{pv} → {nv}", style={"fontFamily": "monospace", "fontSize": "11px", "marginTop": "2px"}),
                ],
                style={"marginTop": "6px"},
            )
        )
    if len(changed) > 8:
        rows.append(html.Div(f"+{len(changed) - 8} perubahan lain", style={"marginTop": "6px"}))

    return (
        html.Div(
            [
                html.Div("Backend contract changed — restart FE / hard refresh.", style={"fontWeight": "bold"}),
                html.Div("Perubahan terdeteksi pada endpoint berikut:", style={"marginTop": "4px"}),
                *rows,
            ]
        ),
        {"padding": "10px 12px", "borderRadius": "8px", "border": "1px solid #e74c3c", "backgroundColor": "#fdecea", "color": "#922b21"},
    )


def _doctor_report_filename(*, base_url: str, ts: int) -> str:
    safe_base = str(base_url or "backend").strip()
    safe_base = safe_base.replace("https://", "").replace("http://", "")
    for ch in ["/", "\\", ":", "?", "&", "=", "#", " "]:
        safe_base = safe_base.replace(ch, "_")
    safe_base = safe_base.strip("_") or "backend"
    try:
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(int(ts)))
    except Exception:
        stamp = str(int(ts))
    return f"doctor_report_{safe_base}_{stamp}.json"

def _default_dispatch_payload(*, stream_id: str) -> dict:
    sid = str(stream_id or "").strip() or "proof-rl-1"
    return {
        "stream_id": sid,
        "optimizer_backend": "rl",
        "end_use_cols": ["HVAC", "Lighting", "Pump"],
        "critical_loads": ["Lighting", "Pump"],
        "flexible_loads": ["HVAC"],
        "optimizer_config": {
            "rl_enabled": True,
            "rl_train_episodes": 60,
            "rl_random_seed": 7,
            "rl_use_biofuel_action": False,
        },
        "demand_row": {"timestamp": "2026-03-10T00:00:00", "HVAC": 50.0, "Lighting": 20.0, "Pump": 10.0},
        "supply_row": {"timestamp": "2026-03-10T00:00:00", "PV_potential_kWh": 20.0, "WT_potential_kWh": 5.0},
    }

def _as_float(x: Any) -> float | None:
    try:
        return float(x)
    except Exception:
        return None

def _summarize_dispatch_result(payload: dict) -> tuple[dict, list[dict]]:
    p = payload if isinstance(payload, dict) else {}
    kpi = p.get("kpi") if isinstance(p.get("kpi"), dict) else {}
    schedule = p.get("schedule")
    if not isinstance(schedule, list):
        schedule = p.get("schedule_rows")
    if not isinstance(schedule, list):
        schedule = p.get("rows")
    rows = [r for r in schedule if isinstance(r, dict)] if isinstance(schedule, list) else []
    if not kpi and rows:
        total_grid = 0.0
        total_cost = 0.0
        total_emission = 0.0
        total_unmet = 0.0
        last_soc = None
        for r in rows:
            v = _as_float(r.get("grid_import_kwh"))
            if v is not None:
                total_grid += v
            v = _as_float(r.get("cost"))
            if v is not None:
                total_cost += v
            v = _as_float(r.get("emission"))
            if v is not None:
                total_emission += v
            v = _as_float(r.get("unmet_kwh"))
            if v is not None:
                total_unmet += v
            soc_v = _as_float(r.get("soc"))
            if soc_v is not None:
                last_soc = soc_v
        kpi = {
            "total_grid_import_kwh": total_grid,
            "total_cost": total_cost,
            "total_emission": total_emission,
            "total_unmet_kwh": total_unmet,
        }
        if last_soc is not None:
            kpi["final_soc"] = last_soc
    return kpi, rows


def register_home_callbacks(app):
    @app.callback(
        [Output("home-runbook-md", "children"), Output("home-runbook-source", "children")],
        [Input("backend-readiness-store", "data")],
    )
    def update_home_runbook(readiness):
        return compute_home_runbook(readiness)

    @app.callback(
        [Output("home-contract-mismatch-summary", "children"), Output("settings-contract-mismatch-summary", "children"), Output("contract-mismatch-store", "data")],
        [Input("backend-readiness-store", "data")],
    )
    def update_contract_mismatch_summary(readiness):
        r = readiness if isinstance(readiness, dict) else {}
        base_url = effective_base_url(r)
        items = []

        mon = data_service.get_last_monitoring_endpoint_contract()
        if isinstance(mon, dict) and str(mon.get("status") or "") in {"mismatch", "blocked"}:
            items.append(
                build_runtime_endpoint_contract_mismatch(
                    feature="monitoring",
                    endpoint_key="GET /api/energy-data",
                    path="/api/energy-data",
                    base_url=base_url,
                    errors=mon.get("errors"),
                    source=str(mon.get("source") or ""),
                    payload=None,
                )
            )

        opt = optimization_service.get_last_optimization_endpoint_contract()
        if isinstance(opt, dict) and str(opt.get("status") or "") == "mismatch":
            norm = opt.get("normalized")
            if isinstance(norm, dict):
                items.append(norm)
            else:
                items.append(
                    build_runtime_endpoint_contract_mismatch(
                        feature="optimization",
                        endpoint_key="POST /optimize",
                        path="/optimize",
                        base_url=str(opt.get("base_url") or base_url),
                        errors=opt.get("errors"),
                        source=str(opt.get("source") or ""),
                        payload=None,
                    )
                )

        prec = precooling_api.get_last_precooling_endpoint_contract()
        if isinstance(prec, dict):
            norm = prec.get("normalized")
            if isinstance(norm, dict):
                for v in norm.values():
                    if isinstance(v, dict):
                        items.append(v)

        rep = reports_api.get_last_reports_endpoint_contract()
        if isinstance(rep, dict):
            norm = rep.get("normalized")
            if isinstance(norm, dict):
                for v in norm.values():
                    if isinstance(v, dict):
                        items.append(v)

        if not items:
            out = html.Div("Tidak ada mismatch kontrak runtime terdeteksi.", style={"color": "#1e8449", "fontWeight": "bold"})
            return out, out, {"count": 0}

        children = [
            html.Div(
                f"Total mismatch terdeteksi: {len(items)}",
                style={"color": "#c0392b", "fontWeight": "bold", "marginBottom": "10px"},
            )
        ]
        for i, d in enumerate(items):
            feature = str(d.get("feature") or "")
            endpoint_key = str(d.get("endpoint_key") or "")
            path = str(d.get("path") or "")
            base = str(d.get("base_url") or base_url)
            errs = d.get("errors") if isinstance(d.get("errors"), list) else []
            head = f"{feature} | {endpoint_key} | {path}"
            diag_text = json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False)
            diag_id = f"contract-mismatch-json-{i}"
            children.append(
                html.Details(
                    [
                        html.Summary(head, style={"cursor": "pointer", "fontWeight": "bold", "color": "#2c3e50"}),
                        html.Div(f"base_url={base}", style={"fontFamily": "monospace", "fontSize": "12px", "color": "#566573", "marginTop": "6px"}),
                        html.Div(f"errors={len(errs)}", style={"fontFamily": "monospace", "fontSize": "12px", "color": "#566573"}),
                        render_runtime_endpoint_contract_mismatch_banner(d),
                        html.Details(
                            [
                                html.Summary("Detail teknis / Copy diagnostics", style={"cursor": "pointer"}),
                                dcc.Textarea(id=diag_id, value=diag_text, style={"width": "100%", "height": "180px", "fontFamily": "monospace", "fontSize": "12px", "marginTop": "8px"}),
                                dcc.Clipboard(target_id=diag_id, title="Copy diagnostics"),
                            ],
                            open=False,
                            style={"marginTop": "10px"},
                        ),
                    ],
                    style={"padding": "10px", "border": "1px solid #ecf0f1", "borderRadius": "8px", "backgroundColor": "white", "marginBottom": "10px"},
                )
            )

        panel = html.Div(children)
        return panel, panel, {"count": int(len(items))}

    @app.callback(
        [
            Output("home-doctor-text", "value"),
            Output("home-doctor-msg", "children"),
            Output("home-doctor-snapshot-store", "data"),
            Output("home-doctor-contract-change-banner", "children"),
            Output("home-doctor-contract-change-banner", "style"),
        ],
        [Input("home-doctor-refresh-btn", "n_clicks")],
        [State("backend-readiness-store", "data"), State("home-doctor-snapshot-store", "data")],
        prevent_initial_call=True,
    )
    def update_home_doctor_report(n_clicks, readiness, prev_snapshot):
        content, msg = compute_doctor_report(readiness)
        base = effective_base_url(readiness if isinstance(readiness, dict) else {})
        next_snapshot = {"ts": int(time.time()), "base_url": base, "contract_hashes": {}}
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and isinstance(parsed.get("doctor"), dict):
                next_snapshot["contract_hashes"] = _extract_doctor_contract_hashes(parsed.get("doctor"))
        except Exception:
            next_snapshot["contract_hashes"] = {}
        banner_children, banner_style = _contract_change_banner(prev_snapshot, next_snapshot)
        return content, msg, next_snapshot, banner_children, banner_style

    @app.callback(
        Output("home-doctor-download", "data"),
        [Input("home-doctor-download-btn", "n_clicks")],
        [State("backend-readiness-store", "data")],
        prevent_initial_call=True,
    )
    def download_home_doctor_report(n, readiness):
        content, _ = compute_doctor_report(readiness)
        r = readiness if isinstance(readiness, dict) else {}
        base_url = str(effective_base_url(r) or "")
        filename = _doctor_report_filename(base_url=base_url, ts=int(time.time()))
        return dcc.send_string(content, filename)

    pass
