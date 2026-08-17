import base64
import hmac
import hashlib
import time
from typing import Dict, Any, Optional

from app.shared.config.settings import settings


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


def _get_secret_key() -> bytes:
    key = settings.app_secret
    if not key:
        raise ValueError("APP_SECRET is not configured.")
    return key.encode()


def create_token(user_id: str, expires_in_seconds: int = 86400) -> str:
    """Creates an authenticated token for a given user_id."""
    expires_at = int(time.time()) + expires_in_seconds
    payload = f"{user_id}:{expires_at}"
    secret = _get_secret_key()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    token_str = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token_str.encode()).decode()


def verify_token(token: Optional[str], allow_guest: bool = True) -> str:
    """Verifies a token string and returns the user_id. Raises AuthenticationError if invalid/expired."""
    if not token:
        if allow_guest:
            return "user_default_guest"
        raise AuthenticationError("Missing authentication token.")

    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split(":")
        if len(parts) != 3:
            raise AuthenticationError("Malformed authentication token format.")

        user_id, expires_at_str, signature = parts
        expires_at = int(expires_at_str)

        if time.time() > expires_at:
            raise AuthenticationError("Authentication token has expired.")

        payload = f"{user_id}:{expires_at}"
        secret = _get_secret_key()
        expected_sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise AuthenticationError("Invalid token signature.")

        return user_id
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Invalid authentication token: {str(e)}") from e
