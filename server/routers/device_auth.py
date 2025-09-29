"""
Device authentication router for OAuth2 device flow
"""
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import time
import secrets
import os
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/device", tags=["device_auth"])

# In-memory storage for device codes (in production, use Redis or database)
device_codes: Dict[str, Dict[str, Any]] = {}

class DeviceAuthResponse(BaseModel):
    status: str
    code: str
    expires_at: str
    message: str

class DeviceAuthPollResponse(BaseModel):
    status: str
    message: Optional[str] = None
    token: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None

@router.post("/auth", response_model=DeviceAuthResponse)
async def start_device_auth():
    """Start device authorization flow"""
    try:
        # Generate device code
        device_code = secrets.token_urlsafe(32)
        user_code = secrets.token_hex(4).upper()
        
        # Set expiration (10 minutes from now)
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Store device code info
        device_codes[device_code] = {
            "user_code": user_code,
            "status": "pending",
            "expires_at": expires_at,
            "created_at": datetime.utcnow(),
            "token": None,
            "user_info": None
        }
        
        return DeviceAuthResponse(
            status="success",
            code=device_code,
            expires_at=expires_at.isoformat(),
            message="Please complete authentication in your browser"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start device auth: {str(e)}"
        )

@router.get("/poll", response_model=DeviceAuthPollResponse)
async def poll_device_auth(code: str):
    """Poll for device authorization status"""
    try:
        if code not in device_codes:
            return DeviceAuthPollResponse(
                status="error",
                message="Invalid device code"
            )
        
        device_info = device_codes[code]
        
        # Check if expired
        if datetime.utcnow() > device_info["expires_at"]:
            # Clean up expired code
            del device_codes[code]
            return DeviceAuthPollResponse(
                status="expired",
                message="Device code has expired"
            )
        
        # Check status
        if device_info["status"] == "authorized":
            # Clean up successful code
            token = device_info["token"]
            user_info = device_info["user_info"]
            del device_codes[code]
            
            return DeviceAuthPollResponse(
                status="authorized",
                token=token,
                user_info=user_info,
                message="Authorization successful"
            )
        elif device_info["status"] == "denied":
            # Clean up denied code
            del device_codes[code]
            return DeviceAuthPollResponse(
                status="error",
                message="Authorization was denied"
            )
        else:
            # Still pending
            return DeviceAuthPollResponse(
                status="pending",
                message="Waiting for user authorization"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to poll device auth: {str(e)}"
        )

@router.get("/authorize", response_class=HTMLResponse)
async def device_authorize_page(code: str):
    """Device authorization page (for browser)"""
    try:
        # Read HTML template
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "device_auth.html")
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        else:
            # Fallback simple HTML
            return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>Jaaz Authorization</title></head>
            <body>
                <h1>Jaaz Device Authorization</h1>
                <p>Processing authorization for device code: {code}</p>
                <script>
                    fetch('/api/device/authorize?code={code}')
                        .then(r => r.json())
                        .then(d => {{
                            if (d.status === 'success') {{
                                document.body.innerHTML = '<h1>✅ Authorization Successful!</h1><p>You can close this window.</p>';
                                setTimeout(() => window.close(), 3000);
                            }} else {{
                                document.body.innerHTML = '<h1>❌ Authorization Failed</h1><p>' + (d.error || 'Unknown error') + '</p>';
                            }}
                        }});
                </script>
            </body>
            </html>
            """)

    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Authorization Error</title></head>
        <body>
            <h1>Authorization Error</h1>
            <p>Failed to load authorization page: {str(e)}</p>
        </body>
        </html>
        """)

@router.get("/authorize_api")
async def device_authorize_api(code: str):
    """Device authorization API endpoint"""
    try:
        if code not in device_codes:
            return {"error": "Invalid or expired device code"}

        device_info = device_codes[code]

        # Check if expired
        if datetime.utcnow() > device_info["expires_at"]:
            del device_codes[code]
            return {"error": "Device code has expired"}

        # For development mode, automatically authorize
        # In production, this would show an authorization page

        # Generate access token
        access_token = f"dev_token_{secrets.token_urlsafe(32)}"

        # Create user info (in production, this would come from OAuth provider)
        user_info = {
            "id": f"user_{uuid.uuid4().hex[:8]}",
            "username": f"User_{secrets.token_hex(4)}",
            "email": f"user_{secrets.token_hex(4)}@example.com",
            "provider": "development",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Update device code status
        device_codes[code]["status"] = "authorized"
        device_codes[code]["token"] = access_token
        device_codes[code]["user_info"] = user_info

        return {
            "status": "success",
            "message": "Authorization successful! You can close this window.",
            "user_info": user_info
        }

    except Exception as e:
        return {"error": f"Authorization failed: {str(e)}"}

@router.post("/revoke")
async def revoke_device_auth(code: str):
    """Revoke/deny device authorization"""
    try:
        if code in device_codes:
            device_codes[code]["status"] = "denied"
            return {"status": "success", "message": "Authorization denied"}
        else:
            return {"status": "error", "message": "Invalid device code"}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke device auth: {str(e)}"
        )

# Cleanup expired codes periodically (in production, use a background task)
@router.get("/cleanup")
async def cleanup_expired_codes():
    """Clean up expired device codes"""
    try:
        current_time = datetime.utcnow()
        expired_codes = [
            code for code, info in device_codes.items()
            if current_time > info["expires_at"]
        ]
        
        for code in expired_codes:
            del device_codes[code]
        
        return {
            "status": "success",
            "cleaned_up": len(expired_codes),
            "remaining": len(device_codes)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup codes: {str(e)}"
        )
