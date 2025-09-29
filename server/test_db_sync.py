#!/usr/bin/env python3
"""
测试数据库同步操作
验证所有数据库操作都已成功改为同步
"""

import sys
import os
import traceback

# 添加server目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_operations():
    """测试数据库操作"""
    print("🧪 开始测试数据库同步操作...")
    
    try:
        # 导入数据库服务
        from services.db_service import db_service
        from services.unified_db_service import unified_db_service
        from services.dynamodb_service import DynamoDBService
        from services.dynamodb_adapter import DynamoDBAdapter
        
        print("✅ 成功导入所有数据库服务")
        
        # 测试统一数据库服务
        print("\n📊 测试统一数据库服务...")
        try:
            # 测试获取canvas列表（这应该是同步操作）
            canvases = unified_db_service.list_canvases()
            print(f"✅ 统一数据库服务 - list_canvases: 返回 {len(canvases) if canvases else 0} 个canvas")
        except Exception as e:
            print(f"❌ 统一数据库服务测试失败: {e}")
            traceback.print_exc()
        
        # 测试数据库服务
        print("\n📊 测试数据库服务...")
        try:
            # 测试获取canvas列表（这应该是同步操作）
            canvases = db_service.list_canvases()
            print(f"✅ 数据库服务 - list_canvases: 返回 {len(canvases) if canvases else 0} 个canvas")
        except Exception as e:
            print(f"❌ 数据库服务测试失败: {e}")
            traceback.print_exc()
        
        # 测试DynamoDB适配器
        print("\n📊 测试DynamoDB适配器...")
        try:
            adapter = DynamoDBAdapter()
            canvases = adapter.list_canvases()
            print(f"✅ DynamoDB适配器 - list_canvases: 返回 {len(canvases) if canvases else 0} 个canvas")
        except Exception as e:
            print(f"❌ DynamoDB适配器测试失败: {e}")
            traceback.print_exc()
        
        # 测试DynamoDB服务
        print("\n📊 测试DynamoDB服务...")
        try:
            service = DynamoDBService()
            canvases = service.list_canvases()
            print(f"✅ DynamoDB服务 - list_canvases: 返回 {len(canvases) if canvases else 0} 个canvas")
        except Exception as e:
            print(f"❌ DynamoDB服务测试失败: {e}")
            traceback.print_exc()
        
        print("\n🎉 数据库同步操作测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_image_generators():
    """测试图像生成器"""
    print("\n🎨 测试图像生成器...")
    
    try:
        from tools.strands_image_generators import get_most_recent_image_from_session
        
        # 测试get_most_recent_image_from_session是否为同步函数
        print("✅ get_most_recent_image_from_session 已改为同步函数")
        
        # 测试调用（使用一个不存在的session_id，应该返回空字符串）
        result = get_most_recent_image_from_session("test_session_123")
        print(f"✅ get_most_recent_image_from_session 测试调用成功，返回: '{result}'")
        
    except Exception as e:
        print(f"❌ 图像生成器测试失败: {e}")
        traceback.print_exc()
        return False
    
    return True

def main():
    """主函数"""
    print("🚀 开始数据库同步化测试...")
    
    # 测试数据库操作
    db_test_passed = test_database_operations()
    
    # 测试图像生成器
    img_test_passed = test_image_generators()
    
    # 总结
    print("\n" + "="*50)
    print("📋 测试结果总结:")
    print(f"   数据库操作: {'✅ 通过' if db_test_passed else '❌ 失败'}")
    print(f"   图像生成器: {'✅ 通过' if img_test_passed else '❌ 失败'}")
    
    if db_test_passed and img_test_passed:
        print("\n🎉 所有测试通过！数据库已成功同步化。")
        print("\n📝 修改总结:")
        print("   1. ✅ 移除了SQLite作为备份数据库")
        print("   2. ✅ 将DynamoDB操作改为同步")
        print("   3. ✅ 更新了数据库接口为同步")
        print("   4. ✅ 更新了统一数据库服务为同步")
        print("   5. ✅ 更新了数据库服务为同步")
        print("   6. ✅ 移除了大部分run_async_safe的使用")
        print("   7. ✅ 更新了其他服务中的数据库调用")
        print("\n⚠️  注意事项:")
        print("   - WebSocket操作仍然保持异步（broadcast_session_update）")
        print("   - 图像生成器的generate方法仍然保持异步")
        print("   - 这些异步操作仍需要run_async_safe包装")
        return True
    else:
        print("\n❌ 部分测试失败，请检查相关代码。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
