"""
User context management for multi-tenant support
"""
import contextvars
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
import jwt
import json

# Create context variable for user information
_user_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'user_context', 
    default={}
)


def set_user_context(user_id: str, user_info: Optional[Dict[str, Any]] = None):
    """Set user context"""
    context = {
        'user_id': user_id,
        'user_info': user_info or {}
    }
    _user_context.set(context)


def get_user_context() -> Dict[str, Any]:
    """Get current user context"""
    return _user_context.get({})


def get_current_user_id() -> str:
    """Get current user ID"""
    context = get_user_context()
    user_id = context.get('user_id', '')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )
    return user_id


def get_current_user_info() -> Dict[str, Any]:
    """Get current user info"""
    return get_user_context().get('user_info', {})


def extract_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """Extract user information from request"""
    try:
        # Try to get user from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            return decode_jwt_token(token)
        
        # Try to get user from jaaz_user_info in localStorage (for development)
        # This would be passed via custom header in production
        user_info_header = request.headers.get('X-User-Info')
        if user_info_header:
            try:
                user_info = json.loads(user_info_header)
                return user_info
            except json.JSONDecodeError:
                pass
        
        return None
    except Exception as e:
        print(f"Error extracting user from request: {e}")
        return None


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT token to extract user information"""
    try:
        # Handle development mode token
        if token == 'dev_token':
            return {
                'id': 'dev_user',
                'username': 'Development User',
                'email': 'dev_user@example.com',
                'provider': 'development'
            }

        # Use proper JWT verification with the same secret and algorithm as user_service
        from services.user_service import JWT_SECRET, JWT_ALGORITHM

        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            print("JWT token has expired")
            return None
        except jwt.InvalidTokenError:
            print("Invalid JWT token")
            return None

        # Extract user information from token
        user_info = {
            'id': decoded.get('sub') or decoded.get('user_id'),
            'username': decoded.get('username'),
            'email': decoded.get('email'),
            'provider': decoded.get('provider', 'jaaz'),
        }

        # Ensure we have a user ID
        if not user_info['id']:
            return None

        return user_info
    except Exception as e:
        print(f"Error decoding JWT token: {e}")
        return None


def require_authentication():
    """Decorator to require authentication for a function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_id = get_current_user_id()  # This will raise HTTPException if not authenticated
            return func(*args, **kwargs)
        return wrapper
    return decorator


class UserContextManager:
    """Context manager for user context"""
    
    def __init__(self, user_id: str, user_info: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.user_info = user_info or {}
        self.previous_context = None
    
    def __enter__(self):
        self.previous_context = get_user_context()
        set_user_context(self.user_id, self.user_info)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_context:
            _user_context.set(self.previous_context)
        else:
            _user_context.set({})


# Development helper function
def set_development_user(user_id: str = "dev_user", username: str = "Development User"):
    """Set a development user for testing purposes"""
    user_info = {
        'id': user_id,
        'username': username,
        'email': f"{user_id}@example.com",
        'provider': 'development'
    }
    set_user_context(user_id, user_info)
    return user_info
