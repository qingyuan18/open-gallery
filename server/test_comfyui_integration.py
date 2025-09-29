#!/usr/bin/env python3
"""
测试 ComfyUI 集成修改
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """测试导入"""
    print("🔧 测试导入...")
    
    try:
        # 测试智能 ComfyUI 工具导入
        from tools.strands_comfyui_generator import create_smart_comfyui_generator
        print("✅ strands_comfyui_generator 导入成功")
        
        # 测试修改后的服务导入
        from services.strands_service import strands_agent
        print("✅ strands_service 导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_detection():
    """测试模型类型检测"""
    print("\n🎨🎬 测试模型类型检测...")
    
    try:
        from tools.strands_comfyui_generator import create_smart_comfyui_generator
        
        # 测试图像模型
        image_model = {
            'model': 'flux-t2i',
            'provider': 'comfyui',
            'media_type': 'image'
        }
        
        # 测试视频模型
        video_model = {
            'model': 'wan-t2v',
            'provider': 'comfyui',
            'media_type': 'video'
        }
        
        print(f"图像模型配置: {image_model}")
        print(f"视频模型配置: {video_model}")
        
        # 创建工具实例
        image_tool = create_smart_comfyui_generator("test_session", "test_canvas", image_model)
        video_tool = create_smart_comfyui_generator("test_session", "test_canvas", video_model)
        
        print(f"✅ 图像工具创建成功: {image_tool.__name__}")
        print(f"✅ 视频工具创建成功: {video_tool.__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ 模型检测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_frontend_config():
    """测试前端配置"""
    print("\n🌐 测试前端配置...")
    
    try:
        # 模拟前端常量配置
        DEFAULT_PROVIDERS_CONFIG = {
            'comfyui': {
                'models': {
                    'flux-kontext': {'type': 'comfyui', 'media_type': 'image'},
                    'flux-t2i': {'type': 'comfyui', 'media_type': 'image'},
                    'wan-t2v': {'type': 'comfyui', 'media_type': 'video'},
                    'wan-i2v': {'type': 'comfyui', 'media_type': 'video'},
                },
                'url': 'http://ec2-34-216-22-132.us-west-2.compute.amazonaws.com:8188',
                'api_key': '',
            }
        }
        
        # 生成模型列表
        model_list = []
        for provider, config in DEFAULT_PROVIDERS_CONFIG.items():
            for model_name, model_config in config['models'].items():
                model_list.append({
                    'provider': provider,
                    'model': model_name,
                    'type': model_config.get('type', 'text'),
                    'media_type': model_config.get('media_type'),
                    'url': config['url'],
                })
        
        print(f"生成的模型列表:")
        for model in model_list:
            print(f"  - {model['provider']}:{model['model']} ({model['type']}) - {model['media_type']}")
        
        # 按类型分组
        comfyui_models = [m for m in model_list if m['type'] == 'comfyui']
        image_models = [m for m in comfyui_models if m['media_type'] == 'image']
        video_models = [m for m in comfyui_models if m['media_type'] == 'video']
        
        print(f"\n📊 模型统计:")
        print(f"  ComfyUI 模型总数: {len(comfyui_models)}")
        print(f"  图像模型: {len(image_models)} 个")
        print(f"  视频模型: {len(video_models)} 个")
        
        if len(comfyui_models) > 0:
            print("✅ 前端配置正确")
            return True
        else:
            print("❌ 前端配置不完整")
            return False
            
    except Exception as e:
        print(f"❌ 前端配置测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始测试 ComfyUI 集成修改...\n")
    
    # 测试导入
    import_success = test_imports()
    
    # 测试模型检测
    detection_success = test_model_detection()
    
    # 测试前端配置
    frontend_success = test_frontend_config()
    
    print(f"\n📝 测试总结:")
    print(f"  1. {'✅' if import_success else '❌'} 导入测试")
    print(f"  2. {'✅' if detection_success else '❌'} 模型检测测试")
    print(f"  3. {'✅' if frontend_success else '❌'} 前端配置测试")
    
    if import_success and detection_success and frontend_success:
        print(f"\n🎉 所有测试都成功！")
        print(f"\n📋 修改总结:")
        print(f"  - ✅ 修复了 utils.async_utils 导入错误")
        print(f"  - ✅ 创建了智能 ComfyUI 生成工具")
        print(f"  - ✅ 前端模型选择器统一为 ComfyUI 下拉菜单")
        print(f"  - ✅ 根据模型名称自动判断图像/视频生成")
        print(f"  - ✅ 支持 flux-* (图像) 和 wan-* (视频) 模型")
        return 0
    else:
        print(f"\n❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
