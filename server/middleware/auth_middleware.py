"""
Authentication middleware for multi-tenant support
"""
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import traceback
from services.user_context import extract_user_from_request, set_user_context, set_development_user


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle user authentication and context setting"""
    
    def __init__(self, app: ASGIApp, development_mode: bool = True):
        super().__init__(app)
        self.development_mode = development_mode
        
        # Paths that don't require authentication
        self.public_paths = {
            '/api/config/exists',
            '/api/config',
            '/api/settings/exists', 
            '/api/settings',
            '/api/test_ssl',
            '/api/test_ssl_full',
            '/api/ssl_status',
            '/socket.io/',
            '/assets/',
            '/',
            '/favicon.ico'
        }
        
        # Paths that start with these prefixes don't require auth
        self.public_prefixes = [
            '/assets/',
            '/socket.io/',
            '/api/auth/',
            '/api/billing'
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request and set user context"""
        try:
            # Skip authentication for public paths
            if self._is_public_path(request.url.path):
                return await call_next(request)
            
            # Extract user information from request
            user_info = extract_user_from_request(request)
            
            if user_info and user_info.get('id'):
                # Set user context for authenticated user
                set_user_context(user_info['id'], user_info)
                print(f"🔐 Authenticated user: {user_info.get('username', user_info['id'])}")
            elif self.development_mode:
                # In development mode, set a default user
                dev_user = set_development_user()
                print(f"🔧 Development mode: Using default user {dev_user['username']}")
            else:
                # No authentication and not in development mode
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"}
                )
            
            # Process the request
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            print(f"❌ Authentication middleware error: {e}")
            traceback.print_exc()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public and doesn't require authentication"""
        # Check exact matches
        if path in self.public_paths:
            return True
        
        # Check prefix matches
        for prefix in self.public_prefixes:
            if path.startswith(prefix):
                return True
        
        # Check if it's a static file request
        if path.startswith('/') and '.' in path.split('/')[-1]:
            return True
            
        return False


class WebSocketAuthenticationMiddleware:
    """Authentication middleware for WebSocket connections"""
    
    @staticmethod
    def authenticate_websocket_connection(auth_data: dict) -> dict:
        """Authenticate WebSocket connection and return user info"""
        try:
            # Extract token from auth data
            token = auth_data.get('token')
            if token:
                from services.user_context import decode_jwt_token
                user_info = decode_jwt_token(token)
                if user_info and user_info.get('id'):
                    return user_info
            
            # Development mode fallback
            return {
                'id': 'dev_user',
                'username': 'Development User',
                'email': 'dev_user@example.com',
                'provider': 'development'
            }
            
        except Exception as e:
            print(f"❌ WebSocket authentication error: {e}")
            return None


# Helper function to get authentication middleware
def get_auth_middleware(development_mode: bool = True):
    """Get authentication middleware instance"""
    return AuthenticationMiddleware(development_mode=development_mode)
