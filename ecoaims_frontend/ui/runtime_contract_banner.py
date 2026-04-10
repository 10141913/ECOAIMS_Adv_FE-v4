from typing import Any, Dict

from dash import html

from ecoaims_frontend.ui.contract_error_ui import render_contract_mismatch_error


def render_runtime_endpoint_contract_mismatch_banner(details: Any) -> html.Div:
    d = details if isinstance(details, dict) else {}
    return render_contract_mismatch_error(d)

