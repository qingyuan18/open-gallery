#!/bin/bash

echo "🚀 Deploying Strands tools fixes..."

# 检查 Python 环境
echo "📋 Checking Python environment..."
python3 --version
which python3

# 安装/更新依赖
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# 特别确保关键依赖已安装
echo "🔧 Installing critical dependencies..."
pip3 install nanoid strands-agents strands-agents-tools

# 运行完整诊断
echo "🔍 Running full Strands diagnosis..."
python3 diagnose_strands.py

# 测试工具导入
echo "🧪 Testing tool imports..."
python3 test_tools.py

# 检查 ComfyUI 连接
echo "🎨 Testing ComfyUI connection..."
python3 -c "
import sys
sys.path.append('.')
from services.config_service import config_service
comfyui_config = config_service.app_config.get('comfyui', {})
url = comfyui_config.get('url', 'http://comfyui-alb-905118004.us-west-2.elb.amazonaws.com:8080')
print(f'ComfyUI URL: {url}')

import httpx
import asyncio

async def test_comfyui():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f'{url}/api/prompt')
            print(f'ComfyUI status: {response.status_code}')
            return response.status_code == 200
    except Exception as e:
        print(f'ComfyUI connection failed: {e}')
        return False

result = asyncio.run(test_comfyui())
print(f'ComfyUI available: {result}')
"

echo "✅ Deployment fixes completed!"
echo ""
echo "📝 Next steps:"
echo "1. Restart your server: python3 main.py"
echo "2. Test image generation with a simple prompt"
echo "3. Check server logs for any remaining issues"
