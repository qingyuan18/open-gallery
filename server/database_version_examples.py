#!/usr/bin/env python3
"""
Database Version Usage Examples
Demonstrates how to use different database versions
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def example_version_5_usage():
    """Example of using DynamoDB legacy schema (version 5)"""
    print("📝 Example: Using DynamoDB Legacy Schema (Version 5)")
    print("=" * 60)
    
    print("""
# Version 5 is single-tenant - no user authentication required
# All operations work directly without user context

from services.dynamodb_service import DynamoDBService

# Initialize service
db_service = DynamoDBService()

# Create canvas (no user_id required)
canvas_id = "my_canvas"
db_service.create_canvas(canvas_id, "My Canvas", "default_user")

# Get canvas (no user verification)
canvas = db_service.get_canvas(canvas_id)

# Create chat session
session_id = "my_session"
db_service.create_chat_session(session_id, "gpt-4", "openai", canvas_id, "default_user")

# Add messages
db_service.create_message(session_id, "user", "Hello!", "default_user")
db_service.create_message(session_id, "assistant", "Hi there!", "default_user")

# Get messages
messages = db_service.list_messages(session_id)
""")
    
    print("✅ Version 5 is simple but lacks user isolation")
    print()


def example_version_6_usage():
    """Example of using DynamoDB multi-tenant schema (version 6)"""
    print("📝 Example: Using DynamoDB Multi-tenant Schema (Version 6)")
    print("=" * 60)
    
    print("""
# Version 6 requires user authentication and provides user isolation

from services.user_service import UserService
from services.dynamodb_service import DynamoDBService
from services.user_context import UserContextManager

# 1. Authenticate user
user_service = UserService()
user = user_service.authenticate_user("demo", "demo123")

if user:
    user_id = user["user_id"]
    
    # 2. Use user context for all operations
    with UserContextManager(user_id, user):
        db_service = DynamoDBService()
        
        # Create canvas (automatically isolated to this user)
        canvas_id = "my_canvas"
        db_service.create_canvas(canvas_id, "My Canvas", user_id)
        
        # Get canvas (only returns user's canvases)
        canvas = db_service.get_canvas(canvas_id, user_id)
        
        # Create chat session
        session_id = "my_session"
        db_service.create_chat_session(session_id, "gpt-4", "openai", canvas_id, user_id)
        
        # Add messages
        db_service.create_message(session_id, "user", "Hello!", user_id)
        db_service.create_message(session_id, "assistant", "Hi there!", user_id)
        
        # Get messages (only user's messages)
        messages = db_service.list_messages(session_id, user_id)
""")
    
    print("✅ Version 6 provides secure user isolation")
    print()


def example_api_authentication():
    """Example of API authentication with version 6"""
    print("📝 Example: API Authentication (Version 6)")
    print("=" * 60)
    
    print("""
# Frontend authentication flow

// 1. Login to get JWT token
const loginResponse = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'demo',
        password: 'demo123'
    })
});

const { token } = await loginResponse.json();

// 2. Store token (localStorage, sessionStorage, or cookie)
localStorage.setItem('authToken', token);

// 3. Use token in subsequent requests
const canvasesResponse = await fetch('/api/canvases', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});

const canvases = await canvasesResponse.json();
""")
    
    print("✅ JWT tokens provide secure API access")
    print()


def example_switching_versions():
    """Example of switching between database versions"""
    print("📝 Example: Switching Database Versions")
    print("=" * 60)
    
    print("""
# Command line examples

# 1. Check available versions
python server/switch_database_version.py list

# 2. Switch to legacy DynamoDB (no authentication)
python server/switch_database_version.py switch --version 5

# 3. Switch to multi-tenant DynamoDB (with authentication)
python server/switch_database_version.py switch --version 6

# 4. Test the current version
python server/test_database_versions.py v6

# 5. Clean up a version (WARNING: deletes all data!)
python server/switch_database_version.py cleanup --version 5 --force
""")
    
    print("✅ Easy switching between database backends")
    print()


def example_development_workflow():
    """Example development workflow"""
    print("📝 Example: Development Workflow")
    print("=" * 60)
    
    print("""
# Recommended development workflow

# 1. Start with multi-tenant version for new projects
python server/switch_database_version.py switch --version 6

# 2. Verify AWS credentials are configured
python server/switch_database_version.py verify

# 3. Test the setup
python server/test_database_versions.py v6

# 4. Start the application
python -m server.main

# 5. Login with default credentials
# Username: demo, Password: demo123
# or
# Username: admin, Password: admin123

# 6. For testing without authentication, switch to version 5
python server/switch_database_version.py switch --version 5

# 7. Run comprehensive tests
python server/test_database_versions.py all
""")
    
    print("✅ Structured development approach")
    print()


def example_production_deployment():
    """Example production deployment"""
    print("📝 Example: Production Deployment")
    print("=" * 60)
    
    print("""
# Production deployment checklist

# 1. Configure AWS credentials (use IAM roles in production)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-west-2

# 2. Deploy with multi-tenant version
python server/switch_database_version.py switch --version 6

# 3. Verify deployment
python server/test_database_versions.py v6

# 4. Test user isolation
python server/test_database_versions.py isolation

# 5. Create additional users via API
curl -X POST http://your-domain/api/auth/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "newuser",
    "email": "user@company.com",
    "password": "secure_password"
  }'

# 6. Monitor DynamoDB usage and costs
aws cloudwatch get-metric-statistics \\
  --namespace AWS/DynamoDB \\
  --metric-name ConsumedReadCapacityUnits \\
  --dimensions Name=TableName,Value=jaaz-canvases
""")
    
    print("✅ Production-ready deployment")
    print()


def main():
    print("🚀 Database Version Usage Examples")
    print("=" * 60)
    print()
    
    example_version_5_usage()
    example_version_6_usage()
    example_api_authentication()
    example_switching_versions()
    example_development_workflow()
    example_production_deployment()
    
    print("📚 Additional Resources:")
    print("  - DATABASE_VERSION_GUIDE.md - Complete version management guide")
    print("  - MULTI_TENANT_IMPLEMENTATION.md - Multi-tenancy details")
    print("  - server/switch_database_version.py - Version switching tool")
    print("  - server/test_database_versions.py - Testing tool")
    print()
    print("🎉 Ready to start using database versions!")


if __name__ == "__main__":
    main()
