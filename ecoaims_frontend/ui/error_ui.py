from __future__ import annotations

from dash import html
import plotly.graph_objects as go

from ecoaims_frontend.config import COLORS


def _short_detail(detail: str | None, limit: int = 220) -> str | None:
    if not detail:
        return None
    s = str(detail).strip()
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "…"


def error_text(area: str, detail: str | None = None) -> str:
    d = _short_detail(detail)
    if d:
        return f"Terjadi kesalahan pada {area}: {d}"
    return f"Terjadi kesalahan pada {area}."

def status_banner(area: str, title: str, detail: str | None = None, message: str | None = None) -> html.Div:
    d = _short_detail(detail)
    subtitle = str(message).strip() if isinstance(message, str) and message.strip() else "Menunggu backend siap. UI tetap berjalan dan akan mencoba lagi otomatis."
    children = [
        html.Div(title, style={"fontWeight": "bold", "marginBottom": "4px"}),
        html.Div(subtitle, style={"opacity": 0.9}),
    ]
    if d:
        children.append(html.Div(d, style={"marginTop": "6px", "fontFamily": "monospace", "fontSize": "12px", "opacity": 0.85}))
    return html.Div(
        children,
        style={
            "border": "1px solid #566573",
            "backgroundColor": "#f4f6f7",
            "color": COLORS.get("text_primary", "#2c3e50"),
            "borderRadius": "6px",
            "padding": "10px 12px",
            "margin": "8px 0",
        },
    )


def error_banner(area: str, title: str, detail: str | None = None) -> html.Div:
    d = _short_detail(detail)
    hint = "Coba refresh halaman. Jika berulang, periksa koneksi backend atau konfigurasi base URL."
    if isinstance(detail, str):
        if "class=backend_connection_refused" in detail:
            hint = "Backend belum berjalan atau port salah. Jalankan backend kanonik lalu refresh."
        elif "class=backend_timeout" in detail:
            hint = "Backend timeout. Periksa beban server/jaringan, lalu coba lagi."
        elif "class=backend_endpoint_unavailable" in detail:
            hint = "Backend sehat tetapi endpoint Monitoring tidak tersedia. Pastikan backend versi sesuai."
        elif "class=backend_health_failed" in detail:
            hint = "Health check gagal. Pastikan endpoint /health tersedia dan backend tidak error."
        elif "class=runtime_endpoint_contract_mismatch" in detail:
            hint = "Backend merespons tetapi payload tidak sesuai kontrak minimum. Pastikan backend kanonik versi sesuai."
    children = [
        html.Div(title, style={"fontWeight": "bold", "marginBottom": "4px"}),
        html.Div(hint, style={"opacity": 0.9}),
    ]
    if d:
        children.append(html.Div(d, style={"marginTop": "6px", "fontFamily": "monospace", "fontSize": "12px", "opacity": 0.9}))
    if detail and isinstance(detail, str) and len(detail.strip()) > 240:
        children.append(
            html.Details(
                [
                    html.Summary("Detail teknis", style={"cursor": "pointer", "marginTop": "8px"}),
                    html.Pre(
                        detail.strip()[:4000],
                        style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "fontSize": "12px", "opacity": 0.9, "marginTop": "8px"},
                    ),
                ]
            )
        )
    return html.Div(
        children,
        style={
            "border": "1px solid #e74c3c",
            "backgroundColor": "#fdecea",
            "color": COLORS.get("text_primary", "#2c3e50"),
            "borderRadius": "6px",
            "padding": "10px 12px",
            "margin": "8px 0",
        },
    )


def error_figure(title: str, detail: str | None = None) -> go.Figure:
    d = _short_detail(detail)
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=30, r=30, t=50, b=30),
        title=title,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=260,
    )
    msg = d or "Terjadi kesalahan."
    fig.add_annotation(
        text=msg,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color="#e74c3c"),
    )
    return fig
