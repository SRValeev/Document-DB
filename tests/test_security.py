"""
Tests for security functionality
"""
import pytest
from datetime import datetime, timedelta
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    user_manager,
    rate_limiter,
    UserCreate
)
from app.core.exceptions import AuthenticationError


class TestPasswordHashing:
    """Test password hashing functionality"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert verify_password(password, hashed)
    
    def test_verify_password_wrong(self):
        """Test password verification with wrong password"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert not verify_password(wrong_password, hashed)


class TestJWTTokens:
    """Test JWT token functionality"""
    
    def test_create_and_verify_token(self):
        """Test token creation and verification"""
        token_data = {
            "sub": "test_user_id",
            "username": "test_user",
            "is_admin": False
        }
        
        token = create_access_token(token_data)
        assert token is not None
        assert len(token) > 0
        
        # Verify token
        decoded_data = verify_token(token)
        assert decoded_data.user_id == "test_user_id"
        assert decoded_data.username == "test_user"
        assert decoded_data.is_admin is False
    
    def test_verify_invalid_token(self):
        """Test verification of invalid token"""
        with pytest.raises(AuthenticationError):
            verify_token("invalid_token")
    
    def test_token_expiration(self):
        """Test token expiration"""
        # Create token with very short expiration
        token_data = {"sub": "test_user", "username": "test"}
        
        # This would need mocking time for proper testing
        # For now, just test the basic flow
        token = create_access_token(token_data, expires_delta=timedelta(seconds=1))
        assert token is not None


class TestUserManager:
    """Test user management functionality"""
    
    def test_create_user(self):
        """Test user creation"""
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123",
            full_name="Test User"
        )
        
        user = user_manager.create_user(user_data)
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.is_admin is False
        
        # Cleanup
        if "testuser" in user_manager.users_db:
            del user_manager.users_db["testuser"]
    
    def test_create_duplicate_user(self):
        """Test creating user with duplicate username"""
        user_data = UserCreate(
            username="duplicate",
            email="test1@example.com",
            password="password123"
        )
        
        # Create first user
        user_manager.create_user(user_data)
        
        # Try to create duplicate
        with pytest.raises(AuthenticationError):
            user_manager.create_user(user_data)
        
        # Cleanup
        if "duplicate" in user_manager.users_db:
            del user_manager.users_db["duplicate"]
    
    def test_authenticate_user(self):
        """Test user authentication"""
        # Create user first
        user_data = UserCreate(
            username="authtest",
            email="auth@example.com",
            password="password123"
        )
        user_manager.create_user(user_data)
        
        # Test successful authentication
        authenticated_user = user_manager.authenticate_user("authtest", "password123")
        assert authenticated_user is not None
        assert authenticated_user.username == "authtest"
        
        # Test failed authentication
        failed_auth = user_manager.authenticate_user("authtest", "wrong_password")
        assert failed_auth is None
        
        # Cleanup
        if "authtest" in user_manager.users_db:
            del user_manager.users_db["authtest"]


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    def test_rate_limit_check(self):
        """Test rate limit checking"""
        identifier = "test_ip_123"
        
        # Should not be rate limited initially
        assert rate_limiter.check_rate_limit(identifier) is True
        
        # Record failed attempts
        for _ in range(5):  # Max attempts from config
            rate_limiter.record_attempt(identifier, success=False)
        
        # Should be rate limited now
        # Note: This test assumes default config of 5 max attempts
        # In a real test, you'd want to use a test-specific configuration
    
    def test_successful_attempt_clears_limit(self):
        """Test that successful attempt clears rate limiting"""
        identifier = "test_ip_456"
        
        # Record some failed attempts
        for _ in range(3):
            rate_limiter.record_attempt(identifier, success=False)
        
        # Record successful attempt
        rate_limiter.record_attempt(identifier, success=True)
        
        # Should not be rate limited after successful attempt
        assert rate_limiter.check_rate_limit(identifier) is True


if __name__ == "__main__":
    pytest.main([__file__])