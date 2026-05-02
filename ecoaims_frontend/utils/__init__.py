"""
Utility functions for ECOAIMS Frontend.
"""

from typing import Any


def get_headers(token_data: dict[str, Any] | None = None) -> dict[str, str]:
    """
    Build HTTP headers with Bearer token for backend API requests.

    Args:
        token_data: The token data from dcc.Store (e.g., token-store data).
                    Expected to contain 'access_token' and 'token_type' keys.

    Returns:
        A dictionary of HTTP headers including Authorization if token is present.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }

    if isinstance(token_data, dict):
        access_token = token_data.get("access_token") or ""
        token_type = token_data.get("token_type") or "bearer"
        if access_token:
            headers["Authorization"] = f"{token_type.capitalize()} {access_token}"

    return headers
