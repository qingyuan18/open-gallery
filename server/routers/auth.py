"""
Traditional username/password authentication router
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional
from services.user_service import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Security
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginResponse(BaseModel):
    status: str
    token: str
    user_info: Dict[str, Any]
    message: str

class RegisterResponse(BaseModel):
    status: str
    message: str
    user_info: Dict[str, Any]

# Helper functions are now in user_service

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User login with username and password"""
    try:
        # Ensure default users exist on first login attempt
        user_service.ensure_default_users()

        username = request.username
        password = request.password

        # Authenticate user
        user_info = user_service.authenticate_user(username, password)

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Create access token
        token = user_service.create_access_token(user_info)

        return LoginResponse(
            status="success",
            token=token,
            user_info=user_info,
            message="Login successful"
        )

    except ValueError as e:
        # Handle specific user service errors (like disabled account)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """User registration"""
    try:
        username = request.username
        email = request.email
        password = request.password

        # Create new user
        user_info = user_service.create_user(username, email, password)

        return RegisterResponse(
            status="success",
            message="Registration successful",
            user_info=user_info
        )

    except ValueError as e:
        # Handle specific user service errors (validation, duplicates, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user info from token"""
    try:
        token = credentials.credentials
        user_info = user_service.get_user_by_token(token)

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        return user_info

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.post("/logout")
async def logout():
    """User logout (client should remove token)"""
    return {
        "status": "success",
        "message": "Logout successful"
    }

@router.get("/users")
async def list_users():
    """List all users (for development/admin purposes)"""
    try:
        users = user_service.list_users()
        return {"users": users}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )
