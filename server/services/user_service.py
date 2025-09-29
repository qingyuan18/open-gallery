"""
User management service with DynamoDB backend
"""
from typing import Dict, Any, Optional
import uuid
import hashlib
import jwt
from datetime import datetime, timedelta
from .dynamodb_service import DynamoDBService

# JWT settings
JWT_SECRET = "your-secret-key-change-in-production"  # Change this in production!
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class UserService:
    """User management service"""
    
    def __init__(self, region_name='us-west-2'):
        self.db_service = DynamoDBService(region_name=region_name)
    
    def ensure_default_users(self):
        """Create default demo users if they don't exist (called on first login attempt)"""
        try:
            # Check if admin user exists
            admin_user = self.db_service.get_user_by_username("admin")
            if not admin_user:
                self.create_user("admin", "admin@jaaz.com", "admin123")
                print("✅ Created default admin user: admin/admin123")

            # Check if demo user exists
            demo_user = self.db_service.get_user_by_username("demo")
            if not demo_user:
                self.create_user("demo", "demo@jaaz.com", "demo123")
                print("✅ Created default demo user: demo/demo123")

        except Exception as e:
            print(f"⚠️ Warning: Could not create default users: {e}")
            # Don't raise exception, just log the warning
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == password_hash
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        payload = {
            "sub": user_data["user_id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return user data"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def create_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Create a new user"""
        username = username.lower().strip()
        email = email.lower().strip()
        
        # Validate input
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        
        # Check if username already exists
        existing_user = self.db_service.get_user_by_username(username)
        if existing_user:
            raise ValueError("Username already exists")
        
        # Check if email already exists
        existing_email = self.db_service.get_user_by_email(email)
        if existing_email:
            raise ValueError("Email already registered")
        
        # Create new user
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        password_hash = self.hash_password(password)
        
        self.db_service.create_user(username, email, password_hash, user_id)
        
        # Return user info (exclude password hash)
        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "created_at": datetime.utcnow().isoformat(),
            "provider": "jaaz"
        }
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username and password"""
        username = username.lower().strip()
        
        # Get user from database
        user = self.db_service.get_user_by_username(username)
        if not user:
            return None
        
        # Check if user is active
        if not user.get("is_active", True):
            raise ValueError("Account is disabled")
        
        # Verify password
        if not self.verify_password(password, user["password_hash"]):
            return None
        
        # Update last login
        self.db_service.update_user_last_login(username)
        
        # Return user info (exclude password hash)
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "last_login": datetime.utcnow().isoformat(),
            "provider": "jaaz"
        }
    
    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user info from JWT token"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        username = payload.get("username")
        if not username:
            return None
        
        user = self.db_service.get_user_by_username(username)
        if not user:
            return None
        
        # Return user info (exclude password hash)
        return {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "created_at": user["created_at"],
            "last_login": user.get("last_login"),
            "provider": "jaaz"
        }
    
    def change_password(self, username: str, old_password: str, new_password: str):
        """Change user password"""
        username = username.lower().strip()
        
        # Get user from database
        user = self.db_service.get_user_by_username(username)
        if not user:
            raise ValueError("User not found")
        
        # Verify old password
        if not self.verify_password(old_password, user["password_hash"]):
            raise ValueError("Invalid current password")
        
        # Validate new password
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters long")
        
        # Update password
        new_password_hash = self.hash_password(new_password)
        self.db_service.update_user_password(username, new_password_hash)
    
    def deactivate_user(self, username: str):
        """Deactivate user account"""
        username = username.lower().strip()
        self.db_service.deactivate_user(username)
    
    def list_users(self, limit: int = 100) -> list:
        """List all users (for admin purposes)"""
        users = self.db_service.list_users(limit)
        
        # Remove password hashes from response
        for user in users:
            user.pop('password_hash', None)
        
        return users


# Create a global instance
user_service = UserService()
