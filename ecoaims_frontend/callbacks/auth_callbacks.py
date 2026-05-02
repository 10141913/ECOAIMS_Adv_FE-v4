"""
Authentication callbacks for ECOAIMS Frontend.

Handles login via frontend auth (ECOAIMS_AUTH_MODE=local),
stores session-based authentication state,
and provides a self-contained frontend CAPTCHA (no backend dependency).
"""

import json
import logging
import random
import string
from typing import Any

import requests
from dash import Input, Output, State, callback, no_update, html

from ecoaims_frontend.config import ECOAIMS_API_BASE_URL

logger = logging.getLogger(__name__)

# ── CAPTCHA constants ──────────────────────────────────────────────
_CAPTCHA_CHARS = string.ascii_uppercase + string.digits
_CAPTCHA_LENGTH = 6


def _generate_captcha_text() -> str:
    """Generate a random alphanumeric CAPTCHA string."""
    return "".join(random.choices(_CAPTCHA_CHARS, k=_CAPTCHA_LENGTH))


def register_auth_callbacks(app) -> None:
    """
    Register authentication-related Dash callbacks.

    Args:
        app: The Dash application instance.
    """

    # ── CAPTCHA generation callback ──────────────────────────────────
    @app.callback(
        Output("captcha-store", "data"),
        Output("captcha-display", "children"),
        Output("csrf-token-store", "data"),
        Input("refresh-captcha-btn", "n_clicks"),
        prevent_initial_call=False,
    )
    def _refresh_captcha(n_clicks: int) -> tuple:
        """
        Generate a new random CAPTCHA string and fetch CSRF tokens from backend.

        Also fires on initial page load (prevent_initial_call=False)
        so the CAPTCHA is ready before the user interacts.
        
        The CAPTCHA text is obtained from the Flask /api/auth/captcha endpoint
        so that both the Dash display and the Flask validation use the same
        captcha value. Falls back to self-generated captcha if the backend
        is unreachable.
        
        Returns:
            Tuple of (captcha_code, display_text, csrf_tokens_dict)
        """
        code = _generate_captcha_text()
        
        # Fetch CAPTCHA text + CSRF tokens from the Flask server
        csrf_tokens = {}
        try:
            frontend_base = f"{request.scheme}://{request.host}"
            resp = requests.get(f"{frontend_base}/api/auth/captcha", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                csrf_tokens = {
                    "csrf_token": data.get("csrf_token", ""),
                    "csrf_session": data.get("csrf_session", ""),
                    "captcha_token": data.get("captcha_token", ""),
                }
                # Use the captcha text from the Flask server so that
                # the Flask /api/auth/login handler validates against
                # the SAME captcha that was displayed to the user.
                captcha_text = data.get("captcha_text", "")
                if captcha_text:
                    code = captcha_text
                logger.debug("CSRF tokens fetched from /api/auth/captcha")
        except Exception as e:
            logger.warning("Failed to fetch CSRF tokens: %s", e)
        
        # Display with a space between each character for readability
        display = "  ".join(code)
        return code, display, csrf_tokens

    # ── Login callback ───────────────────────────────────────────────
    @app.callback(
        Output("token-store", "data"),
        Output("login-output", "children"),
        Output("login-feedback-store", "data"),
        Input("login-button", "n_clicks"),
        State("login-username", "value"),
        State("login-password", "value"),
        State("captcha-store", "data"),
        State("captcha-input", "value"),
        State("csrf-token-store", "data"),
        prevent_initial_call=True,
    )
    def _handle_login(
        n_clicks: int,
        username: str | None,
        password: str | None,
        captcha_code: str | None,
        captcha_input: str | None,
        csrf_tokens: dict | None,
    ) -> tuple:
        """
        Handle login button click: validate CAPTCHA first, then
        POST to backend /api/auth/login, store JWT token, and return feedback.

        Args:
            n_clicks: Number of button clicks.
            username: Username from input.
            password: Password from input.
            captcha_code: The expected CAPTCHA code from captcha-store.
            captcha_input: The user-entered CAPTCHA value.

        Returns:
            Tuple of (token_data, feedback_children, feedback_store_data).
        """
        if not n_clicks or n_clicks < 1:
            return no_update, no_update, no_update

        # Validate inputs
        username = (username or "").strip()
        password = password or ""

        if not username or not password:
            feedback = html.Div(
                "Please enter both username and password.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "missing_fields"}

        # ── CAPTCHA validation (frontend-only) ────────────────────────
        user_captcha = (captcha_input or "").strip().upper()
        expected_captcha = (captcha_code or "").strip().upper()

        if not user_captcha:
            feedback = html.Div(
                "Please enter the verification code.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "captcha_empty"}

        if user_captcha != expected_captcha:
            feedback = html.Div(
                "Incorrect verification code. Please try again.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "captcha_mismatch"}

        # ── Frontend login (local auth) ───────────────────────────────
        # NOTE: We POST to the frontend's /api/auth/login endpoint (not backend's)
        # because ECOAIMS_AUTH_MODE=local means frontend handles auth locally.
        # Using a relative URL so it works regardless of host/port configuration.
        login_url = "/api/auth/login"
        
        # Extract CSRF tokens
        csrf_token_dict = csrf_tokens or {}
        csrf_token = csrf_token_dict.get("csrf_token", "")
        csrf_session = csrf_token_dict.get("csrf_session", "")
        captcha_token = csrf_token_dict.get("captcha_token", "")

        try:
            logger.info(
                "Attempting login for user=%s via %s with captcha validation",
                username,
                login_url,
            )
            # Get the frontend base URL from the request context
            frontend_base = f"{request.scheme}://{request.host}"
            full_url = frontend_base + login_url
            
            resp = requests.post(
                full_url,
                json={
                    "username": username,
                    "password": password,
                    "captcha": user_captcha,  # Include CAPTCHA for frontend validation
                    "csrf_token": csrf_token,
                    "csrf_session": csrf_session,
                    "captcha_token": captcha_token,
                },
                headers={
                    "X-CSRF-Token": csrf_token,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
        except requests.exceptions.ConnectionError:
            logger.error("Login failed: backend unreachable at %s", login_url)
            feedback = html.Div(
                "Cannot connect to server. Please try again later.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "backend_unreachable"}
        except requests.exceptions.Timeout:
            logger.error("Login failed: timeout at %s", login_url)
            feedback = html.Div(
                "Server did not respond in time. Please try again.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "timeout"}
        except requests.exceptions.RequestException as e:
            logger.error("Login failed: %s", e)
            feedback = html.Div(
                f"Connection error: {e}",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "request_error"}

        # Parse response
        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code == 200 and data.get("ok"):
            # Successful login via frontend auth
            # The frontend sets Flask session["ecoaims_admin_auth"] = True
            # No JWT token needed since session cookie is set
            token_data: dict[str, Any] = {
                "access_token": "",  # Session-based auth, no JWT needed
                "token_type": "session",
                "username": username,
                "role": "",
                "logged_in": True,
            }

            feedback = html.Div(
                "Login successful! Loading dashboard...",
                style={"color": "#27ae60", "fontSize": "14px", "fontWeight": "600"},
            )
            
            # Redirect to dashboard after a short delay for UI feedback
            # The browser session cookie is already set by the login response
            return token_data, feedback, {"ok": True}

        elif resp.status_code == 401:
            # Invalid credentials
            error_msg = data.get("error", "Invalid username or password.")
            feedback = html.Div(
                f"Login failed: {error_msg}",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "invalid_credentials"}

        elif resp.status_code == 429:
            # Rate limited
            feedback = html.Div(
                "Too many login attempts. Please try again later.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "rate_limited"}

        elif resp.status_code == 403:
            # CSRF or other forbidden
            feedback = html.Div(
                "Access denied or session expired. Please refresh and try again.",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "forbidden"}

        else:
            detail = data.get("detail", data.get("error", f"HTTP {resp.status_code}"))
            feedback = html.Div(
                f"Login failed: {detail}",
                style={"color": "#e74c3c", "fontSize": "14px"},
            )
            return no_update, feedback, {"ok": False, "error": "unknown"}

