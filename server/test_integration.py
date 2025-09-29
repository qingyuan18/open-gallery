#!/usr/bin/env python3
"""
Integration test for multi-tenant system
Tests the complete flow from frontend to backend
"""
import asyncio
import sys
import os
import json
import uuid
from typing import Dict, Any

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from services.user_context import UserContextManager


def test_canvas_api_isolation():
    """Test canvas API endpoints with user isolation"""
    print("🧪 Testing Canvas API Isolation...")
    
    client = TestClient(app)
    
    # Test data
    user1_canvas_id = str(uuid.uuid4())
    user2_canvas_id = str(uuid.uuid4())
    
    user1_headers = {"X-User-Info": json.dumps({"id": "test_user_1", "username": "Test User 1"})}
    user2_headers = {"X-User-Info": json.dumps({"id": "test_user_2", "username": "Test User 2"})}
    
    # User 1 creates a canvas
    response = client.post("/api/canvas/create", 
        headers=user1_headers,
        json={
            "canvas_id": user1_canvas_id,
            "name": "User 1 Canvas",
            "messages": [],
            "session_id": str(uuid.uuid4()),
            "text_model": {"provider": "openai", "model": "gpt-4", "url": ""},
            "image_model": {"provider": "openai", "model": "dall-e-3", "url": ""},
            "system_prompt": "Test prompt"
        }
    )
    
    if response.status_code == 200:
        print("✅ User 1 canvas creation successful")
    else:
        print(f"❌ User 1 canvas creation failed: {response.status_code}")
        return False
    
    # User 2 creates a canvas
    response = client.post("/api/canvas/create",
        headers=user2_headers,
        json={
            "canvas_id": user2_canvas_id,
            "name": "User 2 Canvas",
            "messages": [],
            "session_id": str(uuid.uuid4()),
            "text_model": {"provider": "openai", "model": "gpt-4", "url": ""},
            "image_model": {"provider": "openai", "model": "dall-e-3", "url": ""},
            "system_prompt": "Test prompt"
        }
    )
    
    if response.status_code == 200:
        print("✅ User 2 canvas creation successful")
    else:
        print(f"❌ User 2 canvas creation failed: {response.status_code}")
        return False
    
    # User 1 lists canvases (should only see their own)
    response = client.get("/api/canvas/list", headers=user1_headers)
    if response.status_code == 200:
        canvases = response.json()
        user1_canvas_count = len(canvases)
        print(f"✅ User 1 sees {user1_canvas_count} canvas(es)")
        
        # Check if user 1 only sees their own canvas
        user1_canvas_found = any(canvas['id'] == user1_canvas_id for canvas in canvases)
        user2_canvas_found = any(canvas['id'] == user2_canvas_id for canvas in canvases)
        
        if user1_canvas_found and not user2_canvas_found:
            print("✅ User 1 isolation working correctly")
        else:
            print("❌ SECURITY ISSUE: User 1 can see other users' canvases!")
            return False
    else:
        print(f"❌ User 1 canvas list failed: {response.status_code}")
        return False
    
    # User 2 lists canvases (should only see their own)
    response = client.get("/api/canvas/list", headers=user2_headers)
    if response.status_code == 200:
        canvases = response.json()
        user2_canvas_count = len(canvases)
        print(f"✅ User 2 sees {user2_canvas_count} canvas(es)")
        
        # Check if user 2 only sees their own canvas
        user1_canvas_found = any(canvas['id'] == user1_canvas_id for canvas in canvases)
        user2_canvas_found = any(canvas['id'] == user2_canvas_id for canvas in canvases)
        
        if user2_canvas_found and not user1_canvas_found:
            print("✅ User 2 isolation working correctly")
        else:
            print("❌ SECURITY ISSUE: User 2 can see other users' canvases!")
            return False
    else:
        print(f"❌ User 2 canvas list failed: {response.status_code}")
        return False
    
    # User 1 tries to access User 2's canvas (should fail)
    response = client.get(f"/api/canvas/{user2_canvas_id}", headers=user1_headers)
    if response.status_code == 404 or response.status_code == 403:
        print("✅ User 1 cannot access User 2's canvas")
    else:
        print(f"❌ SECURITY ISSUE: User 1 can access User 2's canvas! Status: {response.status_code}")
        return False
    
    # User 2 tries to access User 1's canvas (should fail)
    response = client.get(f"/api/canvas/{user1_canvas_id}", headers=user2_headers)
    if response.status_code == 404 or response.status_code == 403:
        print("✅ User 2 cannot access User 1's canvas")
    else:
        print(f"❌ SECURITY ISSUE: User 2 can access User 1's canvas! Status: {response.status_code}")
        return False
    
    return True


def test_authentication_middleware():
    """Test authentication middleware"""
    print("\n🔐 Testing Authentication Middleware...")
    
    client = TestClient(app)
    
    # Test without authentication (should work in development mode)
    response = client.get("/api/canvas/list")
    if response.status_code == 200:
        print("✅ Development mode allows unauthenticated access")
    else:
        print(f"❌ Development mode authentication failed: {response.status_code}")
        return False
    
    # Test with user info header
    headers = {"X-User-Info": json.dumps({"id": "middleware_test_user", "username": "Middleware Test"})}
    response = client.get("/api/canvas/list", headers=headers)
    if response.status_code == 200:
        print("✅ User info header authentication working")
    else:
        print(f"❌ User info header authentication failed: {response.status_code}")
        return False
    
    return True


def run_integration_tests():
    """Run all integration tests"""
    print("🚀 Starting Multi-Tenant Integration Tests...\n")
    
    tests = [
        test_authentication_middleware,
        test_canvas_api_isolation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} PASSED\n")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} ERROR: {e}\n")
    
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All integration tests passed! Multi-tenant isolation is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please review the security issues above.")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
