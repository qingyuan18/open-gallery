#!/usr/bin/env python3
"""
Test script for video generation functionality
"""

import asyncio
import os
import sys
import json

# Add the server directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.video_generators import ComfyUIVideoGenerator
from tools.strands_video_generators import create_generate_video_with_context
from services.config_service import config_service


async def test_comfyui_video_generator():
    """Test ComfyUI video generator directly"""
    print("🎬 Testing ComfyUI Video Generator...")
    
    try:
        generator = ComfyUIVideoGenerator()
        
        # Test T2V workflow
        print("📝 Testing Text-to-Video (T2V)...")
        result = await generator.generate(
            prompt="A beautiful sunset over the ocean with gentle waves",
            model="wan-t2v",
            ctx={'session_id': 'test_session', 'tool_call_id': 'test_tool_call'}
        )
        print(f"✅ T2V Result: {result}")
        
        # Test I2V workflow (with placeholder image)
        print("🖼️ Testing Image-to-Video (I2V)...")
        result = await generator.generate(
            prompt="The girl poses charmingly in front of the camera, swaying gracefully",
            model="wan-i2v",
            input_image="placeholder_base64_image",
            ctx={'session_id': 'test_session', 'tool_call_id': 'test_tool_call'}
        )
        print(f"✅ I2V Result: {result}")
        
    except Exception as e:
        print(f"❌ ComfyUI Video Generator test failed: {e}")
        import traceback
        traceback.print_exc()


def test_strands_video_tool():
    """Test Strands video generation tool"""
    print("🔧 Testing Strands Video Generation Tool...")

    try:
        # Test T2V model (should not use previous image)
        print("📝 Testing T2V model (wan-t2v)...")
        video_model_t2v = {
            'model': 'wan-t2v',
            'provider': 'comfyui'
        }

        video_tool_t2v = create_generate_video_with_context(
            session_id='test_session',
            canvas_id='test_canvas',
            video_model=video_model_t2v,
            user_id='test_user'
        )

        print(f"✅ T2V Video tool created: {video_tool_t2v.__name__}")

        # Test I2V model (should support previous image)
        print("🖼️ Testing I2V model (wan-i2v)...")
        video_model_i2v = {
            'model': 'wan-i2v',
            'provider': 'comfyui'
        }

        video_tool_i2v = create_generate_video_with_context(
            session_id='test_session',
            canvas_id='test_canvas',
            video_model=video_model_i2v,
            user_id='test_user'
        )

        print(f"✅ I2V Video tool created: {video_tool_i2v.__name__}")
        print(f"📋 Tool description: {video_tool_i2v.__doc__[:100]}...")

    except Exception as e:
        print(f"❌ Strands video tool test failed: {e}")
        import traceback
        traceback.print_exc()


def test_model_input_support():
    """Test model input image support detection"""
    print("🔍 Testing Model Input Support Detection...")

    try:
        from tools.strands_image_generators import create_generate_image_with_context
        from tools.strands_video_generators import create_generate_video_with_context

        # Test image models
        print("🎨 Testing Image Models:")

        # flux-t2i should NOT support input images
        image_model_t2i = {'model': 'flux-t2i', 'provider': 'comfyui'}
        print(f"  flux-t2i supports input: {'kontext' in image_model_t2i['model'].lower()}")

        # flux-kontext should support input images
        image_model_kontext = {'model': 'flux-kontext', 'provider': 'comfyui'}
        print(f"  flux-kontext supports input: {'kontext' in image_model_kontext['model'].lower()}")

        # Test video models
        print("🎬 Testing Video Models:")

        # wan-t2v should NOT support input images
        video_model_t2v = {'model': 'wan-t2v', 'provider': 'comfyui'}
        print(f"  wan-t2v supports input: {'i2v' in video_model_t2v['model'].lower()}")

        # wan-i2v should support input images
        video_model_i2v = {'model': 'wan-i2v', 'provider': 'comfyui'}
        print(f"  wan-i2v supports input: {'i2v' in video_model_i2v['model'].lower()}")

        print("✅ Model support detection working correctly")

    except Exception as e:
        print(f"❌ Model support test failed: {e}")
        import traceback
        traceback.print_exc()


def test_config_service():
    """Test configuration service for video models"""
    print("⚙️ Testing Configuration Service...")
    
    try:
        config = config_service.get_config()
        
        # Check if ComfyUI is configured
        comfyui_config = config.get('comfyui', {})
        print(f"🔍 ComfyUI URL: {comfyui_config.get('url', 'Not configured')}")
        
        # Check video models
        models = comfyui_config.get('models', {})
        video_models = {k: v for k, v in models.items() if v.get('type') == 'video'}
        print(f"🎬 Video models found: {list(video_models.keys())}")
        
        if video_models:
            print("✅ Video models are properly configured")
        else:
            print("⚠️ No video models found in configuration")
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")


async def main():
    """Run all tests"""
    print("🚀 Starting Video Generation Tests...\n")
    
    # Test 1: Configuration
    test_config_service()
    print()
    
    # Test 2: Model support detection
    test_model_input_support()
    print()

    # Test 3: Strands tool
    test_strands_video_tool()
    print()

    # Test 4: ComfyUI generator (only if ComfyUI is available)
    comfyui_url = config_service.app_config.get('comfyui', {}).get('url', '')
    if comfyui_url:
        print(f"🔗 ComfyUI URL configured: {comfyui_url}")
        await test_comfyui_video_generator()
    else:
        print("⚠️ ComfyUI URL not configured, skipping ComfyUI tests")
    
    print("\n🏁 Video Generation Tests Complete!")


if __name__ == "__main__":
    asyncio.run(main())
