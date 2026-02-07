"""
Security Module
JWT Authentication, Password Hashing, API Key Encryption
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import base64
import hashlib
import secrets

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# =============================================================================
# Password Hashing
# =============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


# =============================================================================
# JWT Token Management
# =============================================================================

class TokenData(BaseModel):
    """Token payload data"""
    sub: str  # user_id
    email: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[datetime] = None
    type: str = "access"  # access, refresh


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token
    
    Args:
        data: Payload data (must include 'sub' for user identification)
        expires_delta: Custom expiration time
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token with longer expiration
    
    Args:
        data: Payload data
    
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        return TokenData(
            sub=user_id,
            email=payload.get("email"),
            role=payload.get("role"),
            exp=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
            type=payload.get("type", "access")
        )
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    Verify token and check type
    
    Args:
        token: JWT token string
        token_type: Expected token type (access or refresh)
    
    Returns:
        TokenData if valid and correct type, None otherwise
    """
    token_data = decode_token(token)
    if token_data is None:
        return None
    
    if token_data.type != token_type:
        return None
    
    # Check expiration
    if token_data.exp and token_data.exp < datetime.now(timezone.utc):
        return None
    
    return token_data


# =============================================================================
# API Key Encryption
# =============================================================================

def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption"""
    # Ensure key is 32 bytes base64 encoded
    key = settings.encryption_key
    if len(key) < 32:
        key = key + "=" * (32 - len(key))
    
    # Create proper Fernet key
    key_bytes = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage
    
    Args:
        api_key: Plain text API key
    
    Returns:
        Encrypted API key string
    """
    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an encrypted API key
    
    Args:
        encrypted_key: Encrypted API key string
    
    Returns:
        Plain text API key
    """
    fernet = _get_fernet()
    encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
    decrypted = fernet.decrypt(encrypted)
    return decrypted.decode()


# =============================================================================
# Utilities
# =============================================================================

def generate_api_key(prefix: str = "jqa") -> str:
    """
    Generate a secure API key
    
    Args:
        prefix: Key prefix for identification
    
    Returns:
        Generated API key string
    """
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage/comparison
    
    Args:
        api_key: Plain text API key
    
    Returns:
        SHA256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()
