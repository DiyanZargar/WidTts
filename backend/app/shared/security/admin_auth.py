"""
Admin authentication dependency for protecting administrative API routes.
"""

from typing import Optional
from fastapi import Header, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.shared.config.settings import settings

security = HTTPBearer(auto_error=False)


async def require_admin_auth(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Validate that the request provides the configured admin key.

    Accepts either:
      - Header: X-Admin-Key: <ADMIN_API_KEY>
      - Header: Authorization: Bearer <ADMIN_API_KEY>
    """
    configured_key = settings.admin_api_key

    # If no key is configured on server, block admin access for safety
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication is not configured on the server",
        )

    # 1. Check X-Admin-Key header
    if x_admin_key and x_admin_key == configured_key:
        return "admin"

    # 2. Check Bearer token
    if auth_creds and auth_creds.credentials == configured_key:
        return "admin"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required. Provide valid X-Admin-Key or Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
