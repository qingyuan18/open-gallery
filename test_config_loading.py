#!/usr/bin/env python3
"""
测试配置加载的脚本
"""

import sys
import os

# 添加服务器路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

def test_config_loading():
    """测试配置加载"""
    
    try:
        from services.config_service import config_service
        
        print("🔧 测试配置服务...")
        
        # 获取配置
        config = config_service.get_config()
        
        print(f"📋 加载的配置提供商: {list(config.keys())}")
        
        # 检查 ComfyUI 配置
        if 'comfyui' in config:
            comfyui_config = config['comfyui']
            print(f"\n🎨 ComfyUI 配置:")
            print(f"  URL: {comfyui_config.get('url', 'NOT SET')}")
            print(f"  API Key: {comfyui_config.get('api_key', 'NOT SET')}")
            print(f"  模型数量: {len(comfyui_config.get('models', {}))}")
            
            models = comfyui_config.get('models', {})
            for model_name, model_config in models.items():
                print(f"    - {model_name}: {model_config}")
        else:
            print("❌ ComfyUI 配置未找到")
        
        return config
        
    except Exception as e:
        print(f"❌ 配置加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_list_models_endpoint():
    """测试 /api/list_models 端点逻辑"""
    
    try:
        from services.config_service import config_service
        
        print("\n🔍 测试模型列表生成...")
        
        config = config_service.get_config()
        res = []
        
        # 模拟 /api/list_models 的逻辑
        for provider in config.keys():
            models = config[provider].get('models', {})
            for model_name in models:
                if provider == 'ollama':
                    continue
                # Skip providers that require API key but don't have one (except bedrock and comfyui)
                if provider not in ['comfyui', 'bedrock'] and config[provider].get('api_key', '') == '':
                    continue
                model = models[model_name]
                model_entry = {
                    'provider': provider,
                    'model': model_name,
                    'url': config[provider].get('url', ''),
                    'type': model.get('type', 'text'),
                    'media_type': model.get('media_type')
                }
                res.append(model_entry)
                
                # 特别关注 ComfyUI 模型
                if provider == 'comfyui':
                    print(f"🎨 ComfyUI 模型: {model_name}")
                    print(f"   URL: {model_entry['url']}")
                    print(f"   Type: {model_entry['type']}")
                    print(f"   Media Type: {model_entry['media_type']}")
        
        print(f"\n📊 总共生成了 {len(res)} 个模型")
        comfyui_models = [m for m in res if m['provider'] == 'comfyui']
        print(f"🎨 ComfyUI 模型数量: {len(comfyui_models)}")
        
        return res
        
    except Exception as e:
        print(f"❌ 模型列表测试失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def test_config_file():
    """测试配置文件内容"""
    
    try:
        from services.config_service import USER_DATA_DIR
        import toml
        
        config_file = os.path.join(USER_DATA_DIR, "config.toml")
        print(f"\n📁 配置文件路径: {config_file}")
        
        if os.path.exists(config_file):
            print("✅ 配置文件存在")
            
            with open(config_file, 'r') as f:
                config_content = toml.load(f)
            
            if 'comfyui' in config_content:
                comfyui_config = config_content['comfyui']
                print(f"🎨 配置文件中的 ComfyUI URL: {comfyui_config.get('url', 'NOT SET')}")
            else:
                print("❌ 配置文件中没有 ComfyUI 配置")
                
        else:
            print("❌ 配置文件不存在")
            
    except Exception as e:
        print(f"❌ 配置文件测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🧪 开始测试配置加载...")
    
    # 测试配置文件
    test_config_file()
    
    # 测试配置加载
    config = test_config_loading()
    
    # 测试模型列表生成
    if config:
        models = test_list_models_endpoint()
        
        # 检查是否有 flux-t2i 模型
        flux_t2i = next((m for m in models if m['provider'] == 'comfyui' and m['model'] == 'flux-t2i'), None)
        if flux_t2i:
            print(f"\n🎯 找到 flux-t2i 模型:")
            print(f"   Provider: {flux_t2i['provider']}")
            print(f"   Model: {flux_t2i['model']}")
            print(f"   URL: {flux_t2i['url']}")
            print(f"   Type: {flux_t2i['type']}")
            print(f"   Media Type: {flux_t2i['media_type']}")
            
            expected_url = "http://ec2-34-216-22-132.us-west-2.compute.amazonaws.com:8188"
            if flux_t2i['url'] == expected_url:
                print("✅ URL 正确")
            else:
                print(f"❌ URL 错误，期望: {expected_url}")
        else:
            print("❌ 未找到 flux-t2i 模型")

if __name__ == "__main__":
    main()
