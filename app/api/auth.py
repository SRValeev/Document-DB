"""
Authentication API routes
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import (
    user_manager,
    rate_limiter,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    get_admin_user,
    generate_api_key,
    User,
    UserCreate,
    UserLogin
)
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)
auth_router = APIRouter()
security = HTTPBearer()


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class ApiKeyResponse(BaseModel):
    """API key response"""
    api_key: str
    expires_in_days: int = 30


@auth_router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request):
    """Register a new user"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limiting
    if not rate_limiter.check_rate_limit(client_ip, "register"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )
    
    try:
        # Validate password strength
        if len(user_data.password) < settings.security.password_min_length:
            raise ValidationError(
                f"Password must be at least {settings.security.password_min_length} characters long"
            )
        
        # Create user
        user = user_manager.create_user(user_data)
        
        # Generate tokens
        token_data = {
            "sub": user.id,
            "username": user.username,
            "is_admin": user.is_admin
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Record successful registration
        rate_limiter.record_attempt(client_ip, success=True, action="register")
        
        logger.info_ctx(
            "User registered successfully",
            user_id=user.id,
            username=user.username,
            client_ip=client_ip
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.security.access_token_expire_minutes * 60,
            user=user
        )
        
    except Exception as e:
        rate_limiter.record_attempt(client_ip, success=False, action="register")
        
        if isinstance(e, (AuthenticationError, ValidationError)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        else:
            logger.error_ctx(f"Registration failed: {e}", client_ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )


@auth_router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin, request: Request):
    """Login user"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limiting
    if not rate_limiter.check_rate_limit(client_ip, "login"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Account temporarily locked."
        )
    
    try:
        # Authenticate user
        user = user_manager.authenticate_user(user_data.username, user_data.password)
        
        if not user:
            rate_limiter.record_attempt(client_ip, success=False, action="login")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        # Generate tokens
        token_data = {
            "sub": user.id,
            "username": user.username,
            "is_admin": user.is_admin
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Record successful login
        rate_limiter.record_attempt(client_ip, success=True, action="login")
        
        logger.info_ctx(
            "User logged in successfully",
            user_id=user.id,
            username=user.username,
            client_ip=client_ip
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.security.access_token_expire_minutes * 60,
            user=user
        )
        
    except HTTPException:
        raise
    except Exception as e:
        rate_limiter.record_attempt(client_ip, success=False, action="login")
        logger.error_ctx(f"Login failed: {e}", client_ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request_data: RefreshTokenRequest):
    """Refresh access token"""
    try:
        # Verify refresh token
        token_data = verify_token(request_data.refresh_token, token_type="refresh")
        
        # Get user
        user = user_manager.get_user(token_data.username)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Generate new tokens
        new_token_data = {
            "sub": user.id,
            "username": user.username,
            "is_admin": user.is_admin
        }
        
        access_token = create_access_token(new_token_data)
        refresh_token = create_refresh_token(new_token_data)
        
        logger.info_ctx(
            "Token refreshed successfully",
            user_id=user.id,
            username=user.username
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.security.access_token_expire_minutes * 60,
            user=user
        )
        
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error_ctx(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@auth_router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@auth_router.post("/api-key", response_model=ApiKeyResponse)
async def create_api_key(current_user: User = Depends(get_current_user)):
    """Generate API key for current user"""
    try:
        api_key = generate_api_key(current_user.id)
        
        logger.info_ctx(
            "API key generated",
            user_id=current_user.id,
            username=current_user.username
        )
        
        return ApiKeyResponse(api_key=api_key)
        
    except Exception as e:
        logger.error_ctx(f"API key generation failed: {e}", user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        )


@auth_router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user (invalidate token)"""
    # Note: In a real implementation, you would add the token to a blacklist
    # For now, we'll just log the logout event
    
    logger.info_ctx(
        "User logged out",
        user_id=current_user.id,
        username=current_user.username
    )
    
    return {"message": "Successfully logged out"}


@auth_router.get("/users", response_model=list[User])
async def list_users(admin_user: User = Depends(get_admin_user)):
    """List all users (admin only)"""
    users = []
    for user_data in user_manager.users_db.values():
        users.append(user_data["user"])
    
    return users


@auth_router.delete("/users/{username}")
async def delete_user(username: str, admin_user: User = Depends(get_admin_user)):
    """Delete a user (admin only)"""
    if username == admin_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    if username not in user_manager.users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    del user_manager.users_db[username]
    
    logger.info_ctx(
        "User deleted",
        deleted_username=username,
        admin_username=admin_user.username
    )
    
    return {"message": f"User {username} deleted successfully"}