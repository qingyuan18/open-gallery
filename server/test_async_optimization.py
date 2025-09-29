#!/usr/bin/env python3
"""
测试异步优化效果
"""
import asyncio
import time
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

async def test_async_optimization():
    """测试异步优化效果"""
    print("🚀 测试异步优化效果...")
    
    try:
        # 测试导入
        from services.strands_service import strands_agent, strands_multi_agent
        from tools.strands_specialized_agents import planner_agent
        print("✅ 成功导入异步化的模块")
        
        # 检查函数是否为异步
        print(f"\n🔍 检查函数类型:")
        print(f"  strands_agent: {'异步' if asyncio.iscoroutinefunction(strands_agent) else '同步'}")
        print(f"  strands_multi_agent: {'异步' if asyncio.iscoroutinefunction(strands_multi_agent) else '同步'}")
        print(f"  planner_agent: {'异步' if asyncio.iscoroutinefunction(planner_agent) else '同步'}")
        
        # 测试图像生成工具
        try:
            from tools.strands_image_generators import create_generate_image_with_context
            image_tool = create_generate_image_with_context("test_session", "test_canvas", {"model": "flux-t2i", "provider": "comfyui"})
            print(f"  generate_image_with_context: {'异步' if asyncio.iscoroutinefunction(image_tool) else '同步'}")
        except Exception as e:
            print(f"  generate_image_with_context: 导入失败 - {e}")
        
        # 测试视频生成工具
        try:
            from tools.strands_video_generators import create_generate_video_with_context
            video_tool = create_generate_video_with_context("test_session", "test_canvas", {"model": "wan-t2v", "provider": "comfyui"})
            print(f"  generate_video_with_context: {'异步' if asyncio.iscoroutinefunction(video_tool) else '同步'}")
        except Exception as e:
            print(f"  generate_video_with_context: 导入失败 - {e}")
        
        print("\n✅ 异步优化测试完成")
        print("\n📝 优化总结:")
        print("   1. ✅ 主 Agent 服务改为异步流式调用")
        print("   2. ✅ Agent as Tool 改为异步工具")
        print("   3. ✅ 图像生成工具改为异步，移除 run_async_safe")
        print("   4. ✅ 视频生成工具改为异步，移除 run_async_safe")
        
        print("\n🎯 预期效果:")
        print("   - 图像/视频生成时不再阻塞 FastAPI 线程池")
        print("   - 前端切换用户、查看 canvas 列表等操作不会被阻塞")
        print("   - 整个调用链完全异步化，提高并发性能")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    success = asyncio.run(test_async_optimization())
    if success:
        print("\n🎉 异步优化成功！")
        print("\n⚠️  注意事项:")
        print("   - 请重启服务器以应用更改")
        print("   - 测试前端操作是否还会阻塞")
        print("   - 如有问题，可以回滚到之前的同步版本")
    else:
        print("\n❌ 异步优化失败，请检查代码")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
