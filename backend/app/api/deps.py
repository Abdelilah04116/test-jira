"""
API Dependencies
Common dependencies for API endpoints
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_token, TokenData
from app.jira.client import JiraClient
from app.services.generator import QAGeneratorService, get_qa_generator_service


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> TokenData:
    """
    Validate JWT token and return current user data
    
    Args:
        credentials: Bearer token from Authorization header
    
    Returns:
        TokenData with user information
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = verify_token(credentials.credentials, token_type="access")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[TokenData]:
    """
    Optional user authentication - returns None if not authenticated
    """
    if not credentials:
        return None
    
    return verify_token(credentials.credentials, token_type="access")


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control
    
    Args:
        allowed_roles: List of roles that can access the endpoint
    
    Returns:
        Dependency function that validates role
    """
    async def check_role(
        current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {allowed_roles}"
            )
        return current_user
    
    return check_role


async def get_jira_client(db: AsyncSession = Depends(get_db)) -> JiraClient:
    """
    Get configured Jira client from DB or environment
    """
    from loguru import logger
    from sqlalchemy import select
    from app.models.database import JiraConfiguration
    from app.core.security import decrypt_api_key
    
    # Try fetching from DB first
    result = await db.execute(select(JiraConfiguration).order_by(JiraConfiguration.updated_at.desc()))
    db_config = result.scalars().first()
    
    url = settings.jira_url
    email = settings.jira_email
    token = settings.jira_api_token
    
    if db_config:
        url = db_config.jira_url
        email = db_config.jira_email
        try:
            token = decrypt_api_key(db_config.jira_api_token_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt Jira token from DB: {e}")
            # Fallback to token if it exists (though unlikely to work if decryption fails)
    
    # Basic validation
    url_ok = url and "your-instance" not in url
    token_ok = token and "your-jira-api-token" not in token
    
    if not (url_ok and token_ok):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Jira integration is not configured. Please visit the Jira Integration settings page."
        )
    
    project_key = settings.jira_project_key
    if db_config:
        project_key = db_config.default_project_key

    return JiraClient(url=url, email=email, api_token=token, project_key=project_key)


async def get_generator_service(
    jira: JiraClient = Depends(get_jira_client)
) -> QAGeneratorService:
    """
    Get QA Generator service with dependencies
    
    Args:
        jira: Jira client dependency
    
    Returns:
        Configured QAGeneratorService
    """
    return get_qa_generator_service(jira_client=jira)


# Rate limiting helper
class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests: int = 100, period: int = 60):
        self.requests = requests
        self.period = period
        self._store: dict = {}
    
    async def check(self, key: str) -> bool:
        """Check if request is allowed"""
        import time
        
        now = time.time()
        
        if key not in self._store:
            self._store[key] = {"count": 0, "reset": now + self.period}
        
        if now > self._store[key]["reset"]:
            self._store[key] = {"count": 0, "reset": now + self.period}
        
        if self._store[key]["count"] >= self.requests:
            return False
        
        self._store[key]["count"] += 1
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(
    requests=settings.rate_limit_requests,
    period=settings.rate_limit_period
)


async def check_rate_limit(request: Request) -> None:
    """
    Rate limiting dependency
    
    Args:
        request: FastAPI request object
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = request.client.host if request.client else "unknown"
    
    if not await rate_limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
