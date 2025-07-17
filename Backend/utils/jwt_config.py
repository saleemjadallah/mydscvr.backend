"""
JWT Configuration Utility
Centralized JWT settings and utilities for consistent token handling
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
import logging

from config import settings

logger = logging.getLogger(__name__)


class JWTConfig:
    """Centralized JWT configuration and utilities"""
    
    # Centralized JWT settings
    SECRET_KEY = settings.JWT_SECRET
    ALGORITHM = getattr(settings, 'algorithm', 'HS256')
    
    # Token expiration settings from config
    ACCESS_TOKEN_EXPIRE_MINUTES = getattr(settings, 'access_token_expire_minutes', 15)
    REFRESH_TOKEN_EXPIRE_DAYS = getattr(settings, 'refresh_token_expire_days', 7)
    
    # Extended access token for auth service (backward compatibility)
    ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days for auth service
    
    @classmethod
    def create_access_token(
        cls, 
        data: dict, 
        expires_delta: Optional[timedelta] = None,
        use_extended_expiry: bool = False
    ) -> str:
        """
        Create JWT access token with consistent settings
        
        Args:
            data: Token payload data
            expires_delta: Custom expiration time
            use_extended_expiry: Use 7-day expiry for auth service compatibility
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        elif use_extended_expiry:
            # Use extended expiry for auth service (7 days)
            expire = datetime.utcnow() + timedelta(hours=cls.ACCESS_TOKEN_EXPIRE_HOURS)
        else:
            # Use standard expiry from config (15 minutes)
            expire = datetime.utcnow() + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        
        try:
            encoded_jwt = jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating JWT token: {e}")
            raise
    
    @classmethod
    def create_refresh_token(cls, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire})
        
        try:
            encoded_jwt = jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise
    
    @classmethod
    def verify_token(cls, token: str) -> Optional[dict]:
        """
        Verify and decode JWT token
        
        Returns:
            Token payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}")
            return None
    
    @classmethod
    def get_user_id_from_token(cls, token: str) -> Optional[str]:
        """
        Extract user ID from JWT token
        
        Returns:
            User ID if token is valid, None otherwise
        """
        payload = cls.verify_token(token)
        if payload:
            user_id = payload.get("sub")  # 'sub' is standard for user ID
            logger.info(f"🔓 Extracted user_id from token: {user_id}")
            return user_id
        logger.warning("🔓 Failed to extract user_id from token - payload is None")
        return None
    
    @classmethod
    def is_token_expired(cls, token: str) -> bool:
        """Check if token is expired without raising exception"""
        try:
            jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return False
        except jwt.ExpiredSignatureError:
            return True
        except jwt.JWTError:
            return True
    
    @classmethod
    def get_token_expiry(cls, token: str) -> Optional[datetime]:
        """Get token expiration datetime"""
        payload = cls.verify_token(token)
        if payload and 'exp' in payload:
            return datetime.fromtimestamp(payload['exp'])
        return None


# Convenience functions for backward compatibility
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create access token - backward compatibility function"""
    return JWTConfig.create_access_token(data, expires_delta)

def create_refresh_token(data: dict) -> str:
    """Create refresh token - backward compatibility function"""
    return JWTConfig.create_refresh_token(data)

def verify_token(token: str) -> Optional[dict]:
    """Verify token - backward compatibility function"""
    return JWTConfig.verify_token(token)