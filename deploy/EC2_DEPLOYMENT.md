# EC2 部署指南 (G6e/G7e 单机部署)

在一台 G6e 或 G7e GPU 实例上同时部署 Open Gallery 和 ComfyUI。

## 1. 启动 EC2 实例

- **实例类型**: `g6e.xlarge` 或 `g7e.xlarge`（根据需求选择更大规格）
- **AMI**: Ubuntu 22.04 LTS (Deep Learning AMI 更佳，自带 CUDA 驱动)
- **存储**: 至少 100GB gp3（模型文件较大）
- **安全组入站规则**:

| 类型 | 端口 | 来源 | 说明 |
|------|------|------|------|
| SSH | 22 | 你的 IP | SSH 登录 |
| Custom TCP | 5174 | 0.0.0.0/0 | Open Gallery 前端 |

> 后端 API (57988) 和 ComfyUI (8188) 仅本机通信，无需对外开放。

## 2. 安装系统依赖

```bash
sudo apt update && sudo apt upgrade -y

# Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Python 3.10+ & Git
sudo apt install -y python3 python3-pip python3-venv git
```

## 3. 部署 ComfyUI

```bash
cd ~
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 下载所需模型到 models/ 对应目录（根据需要的工作流选择）
# 例如 FLUX、WAN 等模型放入 models/checkpoints/

# 启动 ComfyUI（监听本机）
nohup python main.py --listen 127.0.0.1 --port 8188 > ~/comfyui.log 2>&1 &
```

验证 ComfyUI 运行：
```bash
curl http://127.0.0.1:8188/system_stats
```

## 4. 部署 Open Gallery

```bash
cd ~
git clone <your-repo-url> open-gallery
cd open-gallery

# 后端
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 前端
cd ../react
npm install
```

## 5. 配置 ComfyUI 后端地址

编辑 `server/user_data/config.toml`，将 ComfyUI 指向本机：

```toml
[comfyui]
url = "http://127.0.0.1:8188"
```

或者通过环境变量设置（不需要改配置文件）：

```bash
export COMFYUI_URL="http://127.0.0.1:8188"
```

## 6. 启动 Open Gallery

```bash
# 终端 1 - 后端
cd ~/open-gallery/server
source venv/bin/activate
nohup python main.py --port 57988 > ~/gallery-backend.log 2>&1 &

# 终端 2 - 前端
cd ~/open-gallery/react
nohup npm run dev > ~/gallery-frontend.log 2>&1 &
```

## 7. 访问

浏览器打开：`http://<EC2公网IP>:5174`

在 Open Gallery 设置页面中可以配置其他 LLM provider 的 API Key（Anthropic、OpenAI、Bedrock 等）。

## 排查问题

```bash
# 检查各服务是否运行
ps aux | grep -E "comfy|main.py|npm"

# 查看日志
tail -f ~/comfyui.log
tail -f ~/gallery-backend.log
tail -f ~/gallery-frontend.log

# 检查端口监听
ss -tlnp | grep -E "8188|57988|5174"
```
