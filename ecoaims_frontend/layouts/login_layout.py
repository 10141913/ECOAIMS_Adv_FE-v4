"""
Dash-based login layout for ECOAIMS Frontend.

This layout is shown when the user is not authenticated.
It provides a login form that POSTs to the backend /api/auth/login endpoint
and stores the JWT token in a dcc.Store for use in API callbacks.
Includes a self-contained frontend CAPTCHA (no backend dependency).
"""

from dash import html, dcc


def create_login_layout() -> html.Div:
    """
    Constructs the login page layout as a Dash component.

    Returns:
        html.Div: The root component of the login page.
    """
    return html.Div(
        style={
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
            "minHeight": "100vh",
            "backgroundColor": "#ecf0f1",
            "fontFamily": "Arial, sans-serif",
        },
        children=[
            # Hidden store for JWT token (session-level persistence)
            dcc.Store(id="token-store", storage_type="session"),

            # Hidden store for login feedback messages
            dcc.Store(id="login-feedback-store", storage_type="memory"),

            # Hidden store for frontend CAPTCHA code (memory-only, no backend)
            dcc.Store(id="captcha-store", storage_type="memory"),

            # Hidden store for CSRF tokens from backend
            dcc.Store(id="csrf-token-store", storage_type="memory"),

            # Login card
            html.Div(
                style={
                    "backgroundColor": "white",
                    "borderRadius": "8px",
                    "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
                    "padding": "40px",
                    "maxWidth": "400px",
                    "width": "100%",
                    "textAlign": "center",
                },
                children=[
                    # App logo / title
                    html.H2(
                        "ECO-AIMS",
                        style={
                            "color": "#2c3e50",
                            "marginBottom": "4px",
                            "fontSize": "28px",
                            "fontWeight": "700",
                        },
                    ),
                    html.P(
                        "Energy Dashboard",
                        style={
                            "color": "#7f8c8d",
                            "marginBottom": "24px",
                            "fontSize": "14px",
                        },
                    ),

                    # Username input
                    html.Div(
                        style={"marginBottom": "16px", "textAlign": "left"},
                        children=[
                            html.Label(
                                "Username",
                                style={
                                    "display": "block",
                                    "marginBottom": "6px",
                                    "fontWeight": "600",
                                    "color": "#2c3e50",
                                    "fontSize": "14px",
                                },
                            ),
                            dcc.Input(
                                id="login-username",
                                type="text",
                                placeholder="Enter your username",
                                style={
                                    "width": "100%",
                                    "padding": "10px 12px",
                                    "border": "1px solid #d5d8dc",
                                    "borderRadius": "6px",
                                    "fontSize": "14px",
                                    "boxSizing": "border-box",
                                },
                            ),
                        ],
                    ),

                    # Password input
                    html.Div(
                        style={"marginBottom": "16px", "textAlign": "left"},
                        children=[
                            html.Label(
                                "Password",
                                style={
                                    "display": "block",
                                    "marginBottom": "6px",
                                    "fontWeight": "600",
                                    "color": "#2c3e50",
                                    "fontSize": "14px",
                                },
                            ),
                            dcc.Input(
                                id="login-password",
                                type="password",
                                placeholder="Enter your password",
                                style={
                                    "width": "100%",
                                    "padding": "10px 12px",
                                    "border": "1px solid #d5d8dc",
                                    "borderRadius": "6px",
                                    "fontSize": "14px",
                                    "boxSizing": "border-box",
                                },
                            ),
                        ],
                    ),

                    # ── Frontend CAPTCHA section ──────────────────────────
                    html.Div(
                        style={"marginBottom": "16px", "textAlign": "left"},
                        children=[
                            html.Label(
                                "Verification Code",
                                style={
                                    "display": "block",
                                    "marginBottom": "6px",
                                    "fontWeight": "600",
                                    "color": "#2c3e50",
                                    "fontSize": "14px",
                                },
                            ),
                            # CAPTCHA display area
                            html.Div(
                                id="captcha-display",
                                style={
                                    "fontFamily": "monospace",
                                    "fontSize": "24px",
                                    "fontWeight": "bold",
                                    "letterSpacing": "6px",
                                    "textAlign": "center",
                                    "padding": "10px",
                                    "backgroundColor": "#f4f6f7",
                                    "border": "1px dashed #bdc3c7",
                                    "borderRadius": "6px",
                                    "marginBottom": "8px",
                                    "userSelect": "none",
                                    "cursor": "default",
                                },
                                children="------",
                            ),
                            # CAPTCHA input + refresh button row
                            html.Div(
                                style={
                                    "display": "flex",
                                    "gap": "8px",
                                    "alignItems": "center",
                                },
                                children=[
                                    dcc.Input(
                                        id="captcha-input",
                                        type="text",
                                        placeholder="Enter code above",
                                        style={
                                            "flex": "1",
                                            "padding": "10px 12px",
                                            "border": "1px solid #d5d8dc",
                                            "borderRadius": "6px",
                                            "fontSize": "14px",
                                            "boxSizing": "border-box",
                                            "textTransform": "uppercase",
                                        },
                                        autoComplete="off",
                                    ),
                                    html.Button(
                                        "↻",
                                        id="refresh-captcha-btn",
                                        n_clicks=0,
                                        style={
                                            "padding": "10px 14px",
                                            "backgroundColor": "#ecf0f1",
                                            "color": "#2c3e50",
                                            "border": "1px solid #d5d8dc",
                                            "borderRadius": "6px",
                                            "fontSize": "18px",
                                            "fontWeight": "bold",
                                            "cursor": "pointer",
                                            "lineHeight": "1",
                                        },
                                        title="Refresh CAPTCHA",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # ── End CAPTCHA section ───────────────────────────────

                    # Login button
                    html.Button(
                        "Sign In",
                        id="login-button",
                        n_clicks=0,
                        style={
                            "width": "100%",
                            "padding": "12px",
                            "backgroundColor": "#3498db",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "6px",
                            "fontSize": "16px",
                            "fontWeight": "600",
                            "cursor": "pointer",
                            "marginTop": "8px",
                        },
                    ),

                    # Loading indicator
                    dcc.Loading(
                        id="login-loading",
                        type="circle",
                        children=html.Div(id="login-output", style={"marginTop": "16px"}),
                    ),

                    # Hidden form for fallback POST to Flask login endpoint
                    html.Div(
                        id="login-hidden-form",
                        style={"display": "none"},
                        children=[
                            # This is used by the callback to trigger a page reload
                            # after successful login via the Flask session endpoint
                        ],
                    ),
                ],
            ),
        ],
    )
