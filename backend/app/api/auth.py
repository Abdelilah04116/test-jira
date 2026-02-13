"""
Authentication API Endpoints
User authentication and token management
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.models.schemas import (
    Token,
    TokenRefresh,
    UserLogin,
    UserCreate,
    UserResponse,
)
from app.models.database import User
from app.api.deps import get_current_user, check_rate_limit
from app.core.config import settings
from app.services.audit import audit_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    # _: None = Depends(check_rate_limit)
):
    print(f"\n🚀 DEBUG REGISTER: {user_data.email} | {user_data.name}\n")
    """
    Register a new user
    
    - **email**: User email (must be unique)
    - **password**: User password (min 8 characters)
    - **name**: Display name
    - **role**: User role (admin, qa, po, developer)
    """
    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        name=user_data.name,
        role=user_data.role,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"New user registered: {new_user.email}")
    
    await audit_service.log(
        action="USER_REGISTRATION",
        user_id=new_user.id,
        resource_type="User",
        resource_id=str(new_user.id),
        details={"email": new_user.email, "role": new_user.role.value}
    )
    
    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_rate_limit)
):
    """
    Authenticate user and return JWT tokens
    
    - **email**: User email
    - **password**: User password
    
    Returns access token and refresh token
    """
    # Find user
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    logger.info(f"User logged in: {user.email}")
    
    await audit_service.log(
        action="LOGIN_SUCCESS",
        user_id=user.id,
        resource_type="Auth",
        resource_id=str(user.id),
        details={"email": user.email}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_request: TokenRefresh,
    _: None = Depends(check_rate_limit)
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    
    Returns new access token and refresh token
    """
    token_data = verify_token(token_request.refresh_token, token_type="refresh")
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Create new tokens
    new_token_data = {
        "sub": token_data.sub,
        "email": token_data.email,
        "role": token_data.role
    }
    
    access_token = create_access_token(new_token_data)
    refresh_token = create_refresh_token(new_token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user information
    """
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(current_user.sub))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.post("/logout")
async def logout(current_user = Depends(get_current_user)):
    """
    Logout current user (client should discard tokens)
    """
    # In a production system, you might want to blacklist the token
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Successfully logged out"}
