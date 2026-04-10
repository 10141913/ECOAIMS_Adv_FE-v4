import plotly.graph_objects as go
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

def create_gauge_figure(value: float, max_val: float = 100, source: str = 'live') -> go.Figure:
    """
    Creates a Plotly gauge chart figure.
    Source can be 'live' or 'sim' to indicate if data is real or simulated.
    """
    # Validation/clamping
    if value < 0 or max_val < 0:
        value = max(0, value)
        max_val = max(0, max_val)

    try:
        src = str(source or "").strip().lower()
        if src in {"backend", "backend_state", "canonical", "dashboard_state"}:
            src_kind = "backend"
        elif src == "live":
            src_kind = "live"
        else:
            src_kind = "sim"

        bar_color = "#2980b9" if src_kind == "live" else ("#16a085" if src_kind == "backend" else "#9b59b6")
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = value,
            domain = {'x': [0, 1], 'y': [0, 1]},
            number = {'font': {'size': 1}, 'suffix': " kW", 'prefix': ""}, 
            gauge = {
                'axis': {'range': [None, max_val], 'tickwidth': 1, 'tickcolor': "#34495e", 'tickfont': {'size': 8}},
                'bar': {'color': bar_color},
                'bgcolor': "white",
                'steps': [
                    {'range': [0, max_val*0.3], 'color': '#2ecc71'}, 
                    {'range': [max_val*0.3, max_val*0.7], 'color': '#f1c40f'}, 
                    {'range': [max_val*0.7, max_val], 'color': '#e74c3c'}], 
                'threshold': {
                    'line': {'color': "#c0392b", 'width': 3},
                    'thickness': 0.75,
                    'value': value}}))
        
        fig.update_traces(mode="gauge")

        # Add annotations
        percent_val = (value / max_val) * 100 if max_val > 0 else 0
        fig.add_annotation(
            x=0.5, y=0.25,
            text=f"{percent_val:.0f}%",
            showarrow=False,
            font=dict(size=12, color="#2c3e50", family="Arial Black")
        )

        fig.add_annotation(
            x=0.5, y=-0.3,
            text=f"{value:.1f} kW",
            showarrow=False,
            font=dict(size=14, color="#2c3e50", family="Arial", weight="bold")
        )
        
        source_text = "LIVE" if src_kind == "live" else ("BACKEND" if src_kind == "backend" else "SIMULATED")
        source_color = "#27ae60" if src_kind == "live" else ("#16a085" if src_kind == "backend" else "#8e44ad")
        
        fig.add_annotation(
            x=0.5, y=0.55,
            text=source_text,
            showarrow=False,
            font=dict(size=10, color=source_color, family="Arial", weight="bold"),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor=source_color,
            borderwidth=1,
            borderpad=2
        )
        
        fig.update_layout(
            paper_bgcolor="white", 
            font={'color': "#2c3e50", 'family': "Arial"},
            margin=dict(l=5, r=5, t=10, b=40),
            height=160,
            autosize=True
        )
        return fig
    except Exception:
        logger.exception("Failed to create gauge figure")
        return go.Figure()
