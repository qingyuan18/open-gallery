#!/usr/bin/env python3
"""
Multi-tenant isolation test script
Tests that users can only access their own data
"""
import asyncio
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.user_aware_db_service import UserAwareDatabaseService
from services.user_context import UserContextManager
import uuid


async def test_multi_tenant_isolation():
    """Test that users can only access their own data"""
    print("🧪 Testing Multi-Tenant Isolation...")
    
    # Create database service
    db_service = UserAwareDatabaseService()
    
    # Create test users
    user1_id = "test_user_1"
    user2_id = "test_user_2"
    
    # Create test data for user 1
    print(f"\n👤 Testing User 1: {user1_id}")
    with UserContextManager(user1_id):
        # Create canvas for user 1
        canvas1_id = str(uuid.uuid4())
        db_service.create_canvas(canvas1_id, "User 1 Canvas", user1_id)
        print(f"✅ Created canvas for user 1: {canvas1_id}")
        
        # Create session for user 1
        session1_id = str(uuid.uuid4())
        db_service.create_chat_session(session1_id, "gpt-4", "openai", canvas1_id, user1_id, "User 1 Session")
        print(f"✅ Created session for user 1: {session1_id}")
        
        # Create message for user 1
        db_service.create_message(session1_id, "user", "Hello from user 1", user1_id)
        print(f"✅ Created message for user 1")
        
        # List user 1's data
        user1_canvases = db_service.list_canvases(user1_id)
        user1_sessions = db_service.list_user_chat_sessions(user1_id)
        user1_messages = db_service.list_messages(session1_id, user1_id)
        
        print(f"📊 User 1 has {len(user1_canvases)} canvases, {len(user1_sessions)} sessions, {len(user1_messages)} messages")
    
    # Create test data for user 2
    print(f"\n👤 Testing User 2: {user2_id}")
    with UserContextManager(user2_id):
        # Create canvas for user 2
        canvas2_id = str(uuid.uuid4())
        db_service.create_canvas(canvas2_id, "User 2 Canvas", user2_id)
        print(f"✅ Created canvas for user 2: {canvas2_id}")
        
        # Create session for user 2
        session2_id = str(uuid.uuid4())
        db_service.create_chat_session(session2_id, "gpt-4", "openai", canvas2_id, user2_id, "User 2 Session")
        print(f"✅ Created session for user 2: {session2_id}")
        
        # Create message for user 2
        db_service.create_message(session2_id, "user", "Hello from user 2", user2_id)
        print(f"✅ Created message for user 2")
        
        # List user 2's data
        user2_canvases = db_service.list_canvases(user2_id)
        user2_sessions = db_service.list_user_chat_sessions(user2_id)
        user2_messages = db_service.list_messages(session2_id, user2_id)
        
        print(f"📊 User 2 has {len(user2_canvases)} canvases, {len(user2_sessions)} sessions, {len(user2_messages)} messages")
    
    # Test cross-user access prevention
    print(f"\n🔒 Testing Cross-User Access Prevention...")
    
    # User 1 tries to access User 2's data
    with UserContextManager(user1_id):
        try:
            # Try to access user 2's canvas
            user2_canvas = db_service.get_canvas(canvas2_id, user1_id)
            if user2_canvas is None:
                print("✅ User 1 cannot access User 2's canvas")
            else:
                print("❌ SECURITY ISSUE: User 1 can access User 2's canvas!")
        except Exception as e:
            print(f"✅ User 1 canvas access blocked: {e}")
        
        try:
            # Try to access user 2's session
            user2_session = db_service.get_chat_session(session2_id, user1_id)
            if user2_session is None:
                print("✅ User 1 cannot access User 2's session")
            else:
                print("❌ SECURITY ISSUE: User 1 can access User 2's session!")
        except Exception as e:
            print(f"✅ User 1 session access blocked: {e}")
        
        try:
            # Try to access user 2's messages
            user2_messages = db_service.list_messages(session2_id, user1_id)
            if len(user2_messages) == 0:
                print("✅ User 1 cannot access User 2's messages")
            else:
                print("❌ SECURITY ISSUE: User 1 can access User 2's messages!")
        except Exception as e:
            print(f"✅ User 1 message access blocked: {e}")
    
    # User 2 tries to access User 1's data
    with UserContextManager(user2_id):
        try:
            # Try to access user 1's canvas
            user1_canvas = db_service.get_canvas(canvas1_id, user2_id)
            if user1_canvas is None:
                print("✅ User 2 cannot access User 1's canvas")
            else:
                print("❌ SECURITY ISSUE: User 2 can access User 1's canvas!")
        except Exception as e:
            print(f"✅ User 2 canvas access blocked: {e}")
    
    print(f"\n🎉 Multi-tenant isolation test completed!")


async def test_api_endpoints():
    """Test API endpoints with user authentication"""
    print("\n🌐 Testing API Endpoints with Authentication...")

    # Test with development mode middleware
    import os
    os.environ['DEVELOPMENT_MODE'] = 'true'

    from services.user_context import set_development_user
    from services.db_service import DatabaseService

    # Create database service instance
    db_service = DatabaseService()

    # Test user 1
    user1_info = set_development_user("api_test_user_1", "API Test User 1")
    print(f"👤 Testing API with user: {user1_info['username']}")

    try:
        # Test canvas operations
        canvas_id = str(uuid.uuid4())
        db_service.create_canvas(canvas_id, "API Test Canvas")
        print("✅ Canvas creation successful")

        canvases = db_service.list_canvases()
        print(f"✅ Listed {len(canvases)} canvases")

        canvas_data = db_service.get_canvas_data(canvas_id)
        if canvas_data:
            print("✅ Canvas data retrieval successful")
        else:
            print("❌ Canvas data retrieval failed")

    except Exception as e:
        print(f"❌ API test failed: {e}")

    # Test user 2
    user2_info = set_development_user("api_test_user_2", "API Test User 2")
    print(f"👤 Testing API with user: {user2_info['username']}")

    try:
        # User 2 should not see User 1's canvas
        canvases = db_service.list_canvases()
        if len(canvases) == 0:
            print("✅ User 2 cannot see User 1's canvases")
        else:
            print(f"❌ SECURITY ISSUE: User 2 can see {len(canvases)} canvases from other users!")

        # User 2 should not be able to access User 1's canvas
        try:
            canvas_data = db_service.get_canvas_data(canvas_id)
            if canvas_data is None:
                print("✅ User 2 cannot access User 1's canvas data")
            else:
                print("❌ SECURITY ISSUE: User 2 can access User 1's canvas data!")
        except Exception as e:
            print(f"✅ User 2 canvas access properly blocked: {e}")

    except Exception as e:
        print(f"❌ API test failed: {e}")


async def test_websocket_isolation():
    """Test WebSocket message isolation"""
    print("\n🔌 Testing WebSocket Message Isolation...")

    from services.websocket_state import add_connection, get_user_socket_ids, get_all_socket_ids
    from services.websocket_service import send_to_user_websocket

    # Simulate user connections
    user1_socket = "socket_user1_123"
    user2_socket = "socket_user2_456"

    user1_info = {"id": "ws_test_user_1", "username": "WS Test User 1"}
    user2_info = {"id": "ws_test_user_2", "username": "WS Test User 2"}

    # Add connections
    add_connection(user1_socket, user1_info)
    add_connection(user2_socket, user2_info)

    # Test user-specific socket retrieval
    user1_sockets = get_user_socket_ids("ws_test_user_1")
    user2_sockets = get_user_socket_ids("ws_test_user_2")

    if user1_socket in user1_sockets and user1_socket not in user2_sockets:
        print("✅ User 1 socket properly isolated")
    else:
        print("❌ User 1 socket isolation failed")

    if user2_socket in user2_sockets and user2_socket not in user1_sockets:
        print("✅ User 2 socket properly isolated")
    else:
        print("❌ User 2 socket isolation failed")

    print(f"📊 Total sockets: {len(get_all_socket_ids())}")
    print(f"📊 User 1 sockets: {len(user1_sockets)}")
    print(f"📊 User 2 sockets: {len(user2_sockets)}")


if __name__ == "__main__":
    async def run_all_tests():
        await test_multi_tenant_isolation()
        await test_api_endpoints()
        await test_websocket_isolation()
        print("\n🎉 All multi-tenant tests completed!")

    asyncio.run(run_all_tests())
