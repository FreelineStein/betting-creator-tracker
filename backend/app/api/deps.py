from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

security = HTTPBearer()


def require_admin(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Dependency that validates the admin API key on write endpoints."""
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="Admin API key not configured on the server",
        )
    if credentials.credentials != settings.admin_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key",
        )
    return credentials.credentials
