#!/usr/bin/env python3
"""
测试 ComfyUI 工具的脚本
"""

import sys
import os
import asyncio

# 添加服务器路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

async def test_comfyui_tool():
    """测试 ComfyUI 工具创建和调用"""
    
    try:
        # 导入工具创建函数
        from tools.strands_comfyui_generator import create_smart_comfyui_generator
        
        # 模拟参数
        session_id = "test_session"
        canvas_id = "test_canvas"
        comfyui_model = {
            'model': 'flux-dev',
            'provider': 'comfyui',
            'media_type': 'image'
        }
        user_id = "test_user"
        
        print("🔧 创建 ComfyUI 工具...")
        tool_func = create_smart_comfyui_generator(session_id, canvas_id, comfyui_model, user_id)
        
        print(f"✅ 工具创建成功: {tool_func.__name__}")
        print(f"📝 工具类型: {type(tool_func)}")
        print(f"🔍 工具是否为异步: {asyncio.iscoroutinefunction(tool_func)}")
        
        # 测试工具调用（不实际生成图像，只测试到模型检测部分）
        print("\n🧪 测试工具调用...")
        
        # 这里我们不实际调用工具，因为需要真实的生成器
        # 只是验证工具函数的创建是否成功
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_traceback_import():
    """测试 traceback 导入是否正常"""
    
    try:
        import traceback
        print("✅ traceback 模块导入成功")
        
        # 测试 traceback 函数
        try:
            raise ValueError("测试异常")
        except Exception as e:
            print("🔍 测试异常处理...")
            traceback.print_exc()
            print("✅ traceback.print_exc() 工作正常")
        
        return True
        
    except Exception as e:
        print(f"❌ traceback 测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🧪 开始测试 ComfyUI 工具...")
    
    # 测试 traceback 导入
    print("\n1️⃣ 测试 traceback 导入...")
    traceback_test = await test_traceback_import()
    
    # 测试 ComfyUI 工具
    print("\n2️⃣ 测试 ComfyUI 工具创建...")
    tool_test = await test_comfyui_tool()
    
    # 总结
    print("\n📋 测试结果总结:")
    print(f"   traceback 导入: {'✅ 通过' if traceback_test else '❌ 失败'}")
    print(f"   ComfyUI 工具: {'✅ 通过' if tool_test else '❌ 失败'}")
    
    if traceback_test and tool_test:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，需要进一步检查。")

if __name__ == "__main__":
    asyncio.run(main())
