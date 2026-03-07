"""
Aura — Subscription Auth Helper
Handles OAuth PKCE flow for OpenAI ChatGPT subscription access
and setup-token flow for Anthropic Claude subscription access.
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser
from typing import Optional

from utils.logger import get_logger

logger = get_logger("subscription_auth")

# ─── OpenAI OAuth Constants ──────────────────────────────────────────
OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_AUTH_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
OPENAI_CALLBACK_PORT = 1455
OPENAI_REDIRECT_URI = f"http://127.0.0.1:{OPENAI_CALLBACK_PORT}/auth/callback"


def _generate_pkce() -> tuple:
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    # Per-flow state — reset before each use in start_openai_oauth()
    auth_code = None
    auth_state = None
    error = None
    _lock = threading.Lock()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/auth/callback":
            if "code" in params:
                with _OAuthCallbackHandler._lock:
                    _OAuthCallbackHandler.auth_code = params["code"][0]
                    _OAuthCallbackHandler.auth_state = params.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='font-family:Inter,sans-serif;text-align:center;padding:60px'>"
                    b"<h2>Authentication successful!</h2>"
                    b"<p>You can close this window and return to Aura.</p>"
                    b"</body></html>"
                )
            elif "error" in params:
                with _OAuthCallbackHandler._lock:
                    _OAuthCallbackHandler.error = params["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='font-family:Inter,sans-serif;text-align:center;padding:60px'>"
                    b"<h2>Authentication failed</h2>"
                    b"<p>Please try again in Aura.</p>"
                    b"</body></html>"
                )
            else:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP server logging
        pass


def start_openai_oauth() -> dict:
    """
    Start the OpenAI OAuth PKCE flow.

    Opens a browser for the user to sign in with their ChatGPT account.
    Waits for the callback, exchanges the code for tokens.

    Returns:
        {
            "success": bool,
            "access_token": str | None,
            "refresh_token": str | None,
            "error": str | None,
        }
    """
    # Reset handler state
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.auth_state = None
    _OAuthCallbackHandler.error = None

    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    auth_params = {
        "client_id": OPENAI_CLIENT_ID,
        "redirect_uri": OPENAI_REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "openai.chat",
    }
    auth_url = f"{OPENAI_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    # Start local callback server
    try:
        server = http.server.HTTPServer(
            ("127.0.0.1", OPENAI_CALLBACK_PORT),
            _OAuthCallbackHandler,
        )
    except OSError as e:
        logger.error(f"Failed to start callback server on port {OPENAI_CALLBACK_PORT}: {e}")
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": f"Port {OPENAI_CALLBACK_PORT} is in use. Close other apps using it and retry.",
        }

    server.timeout = 5  # 5-second poll interval

    # Open browser
    logger.info("Opening browser for OpenAI OAuth sign-in...")
    webbrowser.open(auth_url)

    # Wait for callback (blocking, with 120s total timeout)
    import time
    deadline = time.monotonic() + 120
    while _OAuthCallbackHandler.auth_code is None and _OAuthCallbackHandler.error is None:
        server.handle_request()
        if time.monotonic() >= deadline:
            break

    server.server_close()

    if _OAuthCallbackHandler.error:
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": f"OAuth error: {_OAuthCallbackHandler.error}",
        }

    if not _OAuthCallbackHandler.auth_code:
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": "Authentication timed out. Please try again.",
        }

    # Verify state
    if _OAuthCallbackHandler.auth_state != state:
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": "State mismatch — possible CSRF attack.",
        }

    # Exchange code for tokens
    return _exchange_code(
        _OAuthCallbackHandler.auth_code,
        code_verifier,
    )


def _exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange an OAuth authorization code for access/refresh tokens."""
    try:
        import httpx

        response = httpx.post(
            OPENAI_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": OPENAI_CLIENT_ID,
                "code": code,
                "redirect_uri": OPENAI_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(f"Token exchange failed: HTTP {response.status_code}")
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "error": f"Token exchange failed (HTTP {response.status_code})",
            }

        data = response.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "error": "No access token in response",
            }

        logger.info("OpenAI OAuth token exchange successful")
        return {
            "success": True,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": str(e),
        }


def refresh_openai_token(refresh_token: str) -> dict:
    """Refresh an expired OpenAI access token."""
    try:
        import httpx

        response = httpx.post(
            OPENAI_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": OPENAI_CLIENT_ID,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

        if response.status_code != 200:
            return {
                "success": False,
                "access_token": None,
                "refresh_token": None,
                "error": f"Token refresh failed (HTTP {response.status_code})",
            }

        data = response.json()
        return {
            "success": True,
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token", refresh_token),
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "access_token": None,
            "refresh_token": None,
            "error": str(e),
        }
