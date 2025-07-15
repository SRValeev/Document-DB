"""
Security and authentication system
"""
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from passlib.hash import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token scheme
security_scheme = HTTPBearer()

# Redis client for rate limiting and session management
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis not available: {e}. Using in-memory store.")
    redis_client = None

# In-memory store as fallback
_memory_store: Dict[str, Any] = {}


class TokenData(BaseModel):
    """Token data model"""
    user_id: str
    username: str
    permissions: list = []
    is_admin: bool = False


class UserCreate(BaseModel):
    """User creation model"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class User(BaseModel):
    """User model"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_salt() -> str:
    """Generate a random salt"""
    return secrets.token_hex(32)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.security.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    
    try:
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.security.secret_key, 
            algorithm=settings.security.algorithm
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise AuthenticationError("Failed to create access token")


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.security.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.security.secret_key,
            algorithm=settings.security.algorithm
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating refresh token: {e}")
        raise AuthenticationError("Failed to create refresh token")


def verify_token(token: str, token_type: str = "access") -> TokenData:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.security.secret_key,
            algorithms=[settings.security.algorithm]
        )
        
        if payload.get("type") != token_type:
            raise AuthenticationError("Invalid token type")
        
        user_id = payload.get("sub")
        username = payload.get("username")
        
        if not user_id or not username:
            raise AuthenticationError("Invalid token payload")
        
        return TokenData(
            user_id=user_id,
            username=username,
            permissions=payload.get("permissions", []),
            is_admin=payload.get("is_admin", False)
        )
    
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise AuthenticationError("Token verification failed")


class RateLimiter:
    """Rate limiting for login attempts"""
    
    def __init__(self):
        self.attempts = {}
        self.lockouts = {}
    
    def _get_key(self, identifier: str, action: str) -> str:
        """Get cache key for rate limiting"""
        return f"rate_limit:{action}:{identifier}"
    
    def _get_lockout_key(self, identifier: str) -> str:
        """Get cache key for lockouts"""
        return f"lockout:{identifier}"
    
    def check_rate_limit(self, identifier: str, action: str = "login") -> bool:
        """Check if action is rate limited"""
        lockout_key = self._get_lockout_key(identifier)
        
        # Check if currently locked out
        if redis_client:
            lockout_time = redis_client.get(lockout_key)
            if lockout_time and float(lockout_time) > time.time():
                return False
        else:
            lockout_time = self.lockouts.get(identifier)
            if lockout_time and lockout_time > time.time():
                return False
        
        return True
    
    def record_attempt(self, identifier: str, success: bool, action: str = "login"):
        """Record a login attempt"""
        attempts_key = self._get_key(identifier, action)
        lockout_key = self._get_lockout_key(identifier)
        
        if success:
            # Clear attempts on successful login
            if redis_client:
                redis_client.delete(attempts_key)
                redis_client.delete(lockout_key)
            else:
                self.attempts.pop(identifier, None)
                self.lockouts.pop(identifier, None)
            return
        
        # Increment failed attempts
        if redis_client:
            attempts = redis_client.incr(attempts_key)
            redis_client.expire(attempts_key, 3600)  # 1 hour expiry
        else:
            attempts = self.attempts.get(identifier, 0) + 1
            self.attempts[identifier] = attempts
        
        # Lock out if too many attempts
        if attempts >= settings.security.max_login_attempts:
            lockout_until = time.time() + (settings.security.lockout_duration_minutes * 60)
            
            if redis_client:
                redis_client.set(lockout_key, str(lockout_until), ex=settings.security.lockout_duration_minutes * 60)
            else:
                self.lockouts[identifier] = lockout_until
            
            logger.warning_ctx(
                f"User locked out due to too many failed attempts",
                identifier=identifier,
                attempts=attempts,
                lockout_duration=settings.security.lockout_duration_minutes
            )


# Global rate limiter instance
rate_limiter = RateLimiter()


class UserManager:
    """User management system"""
    
    def __init__(self):
        # In a real application, this would be a database
        self.users_db = {}
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user"""
        admin_user = User(
            id="admin",
            username="admin",
            email="admin@example.com",
            full_name="Administrator",
            is_admin=True,
            created_at=datetime.utcnow()
        )
        
        hashed_password = hash_password("admin123")
        
        self.users_db["admin"] = {
            "user": admin_user,
            "password_hash": hashed_password
        }
        
        logger.info("Default admin user created")
    
    def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        user_data = self.users_db.get(username)
        return user_data["user"] if user_data else None
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        user_data = self.users_db.get(username)
        if not user_data:
            return None
        
        if not verify_password(password, user_data["password_hash"]):
            return None
        
        # Update last login
        user_data["user"].last_login = datetime.utcnow()
        return user_data["user"]
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        if user_data.username in self.users_db:
            raise AuthenticationError("Username already exists")
        
        user = User(
            id=secrets.token_hex(16),
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            created_at=datetime.utcnow()
        )
        
        hashed_password = hash_password(user_data.password)
        
        self.users_db[user_data.username] = {
            "user": user,
            "password_hash": hashed_password
        }
        
        logger.info_ctx("User created", username=user_data.username, user_id=user.id)
        return user


# Global user manager instance
user_manager = UserManager()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> User:
    """Get current authenticated user"""
    try:
        token_data = verify_token(credentials.credentials)
        user = user_manager.get_user(token_data.username)
        
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        
        return user
    
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user if they are an admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required"
        )
    return current_user


def generate_api_key(user_id: str) -> str:
    """Generate an API key for a user"""
    timestamp = str(int(time.time()))
    data = f"{user_id}:{timestamp}:{secrets.token_hex(16)}"
    
    # Create signature
    signature = hashlib.sha256(
        f"{data}:{settings.security.secret_key}".encode()
    ).hexdigest()
    
    api_key = f"{data}:{signature}"
    
    # Store API key (in production, store in database)
    if redis_client:
        redis_client.setex(f"api_key:{api_key}", 86400 * 30, user_id)  # 30 days
    
    return api_key


def verify_api_key(api_key: str) -> Optional[str]:
    """Verify an API key and return user ID"""
    try:
        parts = api_key.split(":")
        if len(parts) != 4:
            return None
        
        user_id, timestamp, random_part, signature = parts
        data = f"{user_id}:{timestamp}:{random_part}"
        
        # Verify signature
        expected_signature = hashlib.sha256(
            f"{data}:{settings.security.secret_key}".encode()
        ).hexdigest()
        
        if signature != expected_signature:
            return None
        
        # Check expiration (30 days)
        if time.time() - int(timestamp) > 86400 * 30:
            return None
        
        # Check if API key exists in store
        if redis_client:
            stored_user_id = redis_client.get(f"api_key:{api_key}")
            if stored_user_id != user_id:
                return None
        
        return user_id
    
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
        return None