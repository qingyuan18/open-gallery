#!/usr/bin/env python3
"""
Test script for different database versions
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_version_5():
    """Test DynamoDB legacy schema (version 5)"""
    print("🧪 Testing DynamoDB Legacy Schema (Version 5)...")
    
    try:
        from services.dynamodb_service import DynamoDBService
        
        # Test basic operations
        db_service = DynamoDBService()
        
        # Test canvas operations
        test_canvas_id = "test_v5_canvas"
        db_service.create_canvas(test_canvas_id, "Test Canvas V5", "test_user")
        print("✅ Canvas creation works")
        
        canvas = db_service.get_canvas(test_canvas_id)
        if canvas:
            print("✅ Canvas retrieval works")
        else:
            print("❌ Canvas retrieval failed")
            return False
        
        # Test session operations
        test_session_id = "test_v5_session"
        db_service.create_chat_session(test_session_id, "gpt-4", "openai", test_canvas_id, "test_user")
        print("✅ Chat session creation works")
        
        # Test message operations
        db_service.create_message(test_session_id, "user", "Test message", "test_user")
        print("✅ Message creation works")
        
        messages = db_service.list_messages(test_session_id)
        if messages:
            print("✅ Message retrieval works")
        else:
            print("❌ Message retrieval failed")
            return False
        
        # Cleanup
        db_service.delete_canvas(test_canvas_id, "test_user")
        print("✅ Canvas deletion works")
        
        print("🎉 Version 5 test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Version 5 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_version_6():
    """Test DynamoDB multi-tenant schema (version 6)"""
    print("🧪 Testing DynamoDB Multi-tenant Schema (Version 6)...")
    
    try:
        from services.user_service import UserService
        from services.dynamodb_service import DynamoDBService
        from services.user_context import UserContextManager
        
        # Test user operations
        user_service = UserService()
        
        # Test authentication
        demo_user = user_service.authenticate_user("demo", "demo123")
        if demo_user:
            print("✅ User authentication works")
        else:
            print("❌ User authentication failed")
            return False
        
        # Test token operations
        token = user_service.create_access_token(demo_user)
        if token:
            print("✅ Token creation works")
        else:
            print("❌ Token creation failed")
            return False
        
        user_from_token = user_service.get_user_by_token(token)
        if user_from_token:
            print("✅ Token verification works")
        else:
            print("❌ Token verification failed")
            return False
        
        # Test database operations with user context
        db_service = DynamoDBService()
        user_id = demo_user["user_id"]
        
        with UserContextManager(user_id, demo_user):
            # Test canvas operations
            test_canvas_id = "test_v6_canvas"
            db_service.create_canvas(test_canvas_id, "Test Canvas V6", user_id)
            print("✅ User-isolated canvas creation works")
            
            canvas = db_service.get_canvas(test_canvas_id, user_id)
            if canvas:
                print("✅ User-isolated canvas retrieval works")
            else:
                print("❌ User-isolated canvas retrieval failed")
                return False
            
            # Test session operations
            test_session_id = "test_v6_session"
            db_service.create_chat_session(test_session_id, "gpt-4", "openai", test_canvas_id, user_id)
            print("✅ User-isolated chat session creation works")
            
            # Test message operations
            db_service.create_message(test_session_id, "user", "Test message", user_id)
            print("✅ User-isolated message creation works")
            
            messages = db_service.list_messages(test_session_id, user_id)
            if messages:
                print("✅ User-isolated message retrieval works")
            else:
                print("❌ User-isolated message retrieval failed")
                return False
            
            # Cleanup
            db_service.delete_canvas(test_canvas_id, user_id)
            print("✅ User-isolated canvas deletion works")
        
        print("🎉 Version 6 test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Version 6 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_user_isolation():
    """Test that user isolation works correctly in version 6"""
    print("🔒 Testing User Isolation...")
    
    try:
        from services.user_service import UserService
        from services.dynamodb_service import DynamoDBService
        from services.user_context import UserContextManager
        
        user_service = UserService()
        db_service = DynamoDBService()
        
        # Get two different users
        admin_user = user_service.authenticate_user("admin", "admin123")
        demo_user = user_service.authenticate_user("demo", "demo123")
        
        if not admin_user or not demo_user:
            print("❌ Could not authenticate test users")
            return False
        
        admin_user_id = admin_user["user_id"]
        demo_user_id = demo_user["user_id"]
        
        # Create canvas as admin user
        admin_canvas_id = "admin_test_canvas"
        with UserContextManager(admin_user_id, admin_user):
            db_service.create_canvas(admin_canvas_id, "Admin Canvas", admin_user_id)
            print("✅ Admin user created canvas")
        
        # Try to access admin's canvas as demo user (should fail)
        with UserContextManager(demo_user_id, demo_user):
            admin_canvas = db_service.get_canvas(admin_canvas_id, demo_user_id)
            if admin_canvas is None:
                print("✅ User isolation works - demo user cannot access admin's canvas")
            else:
                print("❌ User isolation failed - demo user can access admin's canvas")
                return False
        
        # Create canvas as demo user
        demo_canvas_id = "demo_test_canvas"
        with UserContextManager(demo_user_id, demo_user):
            db_service.create_canvas(demo_canvas_id, "Demo Canvas", demo_user_id)
            print("✅ Demo user created canvas")
        
        # Verify admin can access their own canvas but not demo's
        with UserContextManager(admin_user_id, admin_user):
            admin_canvas = db_service.get_canvas(admin_canvas_id, admin_user_id)
            demo_canvas = db_service.get_canvas(demo_canvas_id, admin_user_id)
            
            if admin_canvas and demo_canvas is None:
                print("✅ User isolation works - admin can access own canvas but not demo's")
            else:
                print("❌ User isolation failed")
                return False
        
        # Cleanup
        with UserContextManager(admin_user_id, admin_user):
            db_service.delete_canvas(admin_canvas_id, admin_user_id)
        
        with UserContextManager(demo_user_id, demo_user):
            db_service.delete_canvas(demo_canvas_id, demo_user_id)
        
        print("🎉 User isolation test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ User isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    if len(sys.argv) < 2:
        print("""
🧪 Database Version Test Script

Usage:
  python server/test_database_versions.py <version>

Available tests:
  v5          - Test DynamoDB legacy schema (version 5)
  v6          - Test DynamoDB multi-tenant schema (version 6)
  isolation   - Test user isolation in version 6
  all         - Run all tests

Examples:
  python server/test_database_versions.py v6
  python server/test_database_versions.py isolation
  python server/test_database_versions.py all
""")
        return
    
    test_type = sys.argv[1].lower()
    
    if test_type == "v5":
        success = test_version_5()
    elif test_type == "v6":
        success = test_version_6()
    elif test_type == "isolation":
        success = test_user_isolation()
    elif test_type == "all":
        print("🧪 Running all database version tests...\n")
        
        print("=" * 50)
        v5_success = test_version_5()
        print()
        
        print("=" * 50)
        v6_success = test_version_6()
        print()
        
        print("=" * 50)
        isolation_success = test_user_isolation()
        print()
        
        success = v5_success and v6_success and isolation_success
        
        print("=" * 50)
        print("📊 Test Summary:")
        print(f"  Version 5 (Legacy): {'✅ PASS' if v5_success else '❌ FAIL'}")
        print(f"  Version 6 (Multi-tenant): {'✅ PASS' if v6_success else '❌ FAIL'}")
        print(f"  User Isolation: {'✅ PASS' if isolation_success else '❌ FAIL'}")
        print(f"  Overall: {'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    else:
        print(f"❌ Unknown test type: {test_type}")
        return
    
    if success:
        print(f"\n🎉 Test '{test_type}' completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Test '{test_type}' failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
