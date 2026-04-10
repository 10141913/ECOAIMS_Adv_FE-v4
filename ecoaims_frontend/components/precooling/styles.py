from ecoaims_frontend.config import CARD_STYLE

PREC_COLORS = {
    "cooling": "#2980b9",
    "renewable": "#27ae60",
    "battery": "#e67e22",
    "alert": "#c0392b",
    "ai": "#8e44ad",
    "text": "#2c3e50",
    "muted": "#7f8c8d",
    "bg": "#ecf0f1",
    "card": "white",
    "border": "#ecf0f1",
}

SECTION_TITLE_STYLE = {
    "color": PREC_COLORS["text"],
    "borderBottom": f"2px solid {PREC_COLORS['border']}",
    "paddingBottom": "10px",
    "marginBottom": "15px",
}

SMALL_LABEL_STYLE = {"fontSize": "12px", "color": PREC_COLORS["muted"], "margin": "0"}

VALUE_STYLE = {"fontSize": "22px", "fontWeight": "bold", "color": PREC_COLORS["text"], "margin": "0"}

CARD_STYLE_TIGHT = {**CARD_STYLE, "margin": "8px", "padding": "16px"}

