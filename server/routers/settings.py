"""
Settings Router - 设置路由模块

该模块提供设置相关的 API 路由端点，包括：
- 设置文件存在性检查
- 设置的获取和更新
- 代理配置管理
- 代理连接测试

主要端点：
- GET /api/settings/exists - 检查设置文件是否存在
- GET /api/settings - 获取所有设置（敏感信息已掩码）
- POST /api/settings - 更新设置
- GET /api/settings/proxy/status - 获取代理状态
- GET /api/settings/proxy/test - 测试代理连接
- GET /api/settings/proxy - 获取代理设置
- POST /api/settings/proxy - 更新代理设置
依赖模块：
- services.settings_service - 设置服务
"""

import json
import os
import shutil
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from services.db_service import db_service
from services.settings_service import settings_service
from services.config_service import USER_DATA_DIR
from pydantic import BaseModel

# 创建设置相关的路由器，所有端点都以 /api/settings 为前缀
router = APIRouter(prefix="/api/settings")


@router.get("/exists")
async def settings_exists():
    """
    检查设置文件是否存在

    Returns:
        dict: 包含 exists 字段的字典，指示设置文件是否存在

    Description:
        用于前端检查是否需要显示初始设置向导。
        如果设置文件不存在，通常需要引导用户进行初始配置。
    """
    return {"exists": await settings_service.exists_settings()}


@router.get("")
async def get_settings():
    """
    获取所有设置配置

    Returns:
        dict: 完整的设置配置字典，敏感信息已被掩码处理

    Description:
        返回所有应用设置，包括代理配置、系统提示词等。
        敏感信息（如密码）会被替换为 '*' 字符以保护隐私。
        设置会与默认配置合并，确保所有必需的键都存在。
    """
    return settings_service.get_settings()


@router.post("")
async def update_settings(request: Request):
    """
    更新设置配置

    Args:
        request (Request): HTTP 请求对象，包含要更新的设置数据

    Returns:
        dict: 操作结果，包含 status 和 message 字段

    Description:
        接收 JSON 格式的设置数据并更新到配置文件。
        支持部分更新，新数据会与现有设置合并而不是完全替换。

    Example:
        POST /api/settings
        {
            "proxy": "http://proxy.com:8080"  // 或 "" 或 "system"
        }
    """
    data = await request.json()
    result = await settings_service.update_settings(data)
    return result


@router.get("/proxy/status")
async def get_proxy_status():
    """
    获取代理配置状态

    Returns:
        dict: 代理状态信息，包含以下字段：
            - enable (bool): 代理是否启用
            - configured (bool): 代理是否正确配置
            - message (str): 状态描述信息

    Description:
        检查当前代理配置的状态，包括是否启用和是否正确配置。
        该端点不会暴露完整的代理 URL 以保护安全性。

    Status Logic:
        - enable=True, configured=True: 代理已启用且配置正确
        - enable=True, configured=False: 代理已启用但配置有误
        - enable=False, configured=False: 代理未启用
    """
    # 获取设置中的代理配置
    settings = settings_service.get_raw_settings()
    proxy_setting = settings.get('proxy', '')

    if proxy_setting == '':
        # 不使用代理
        return {
            "enable": False,
            "configured": True,
            "message": "Proxy is disabled"
        }
    elif proxy_setting == 'system':
        # 使用系统代理
        return {
            "enable": True,
            "configured": True,
            "message": "Using system proxy"
        }
    elif proxy_setting.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        # 使用指定的代理URL
        return {
            "enable": True,
            "configured": True,
            "message": "Using custom proxy"
        }
    else:
        # 代理设置格式不正确
        return {
            "enable": True,
            "configured": False,
            "message": "Proxy configuration is invalid"
        }


@router.get("/proxy")
async def get_proxy_settings():
    """
    获取代理设置

    Returns:
        dict: 代理配置字典，包含 proxy 字段

    Description:
        仅返回代理相关的设置，不包含其他配置项。
        用于前端代理设置页面的数据加载。

    Response Format:
        {
            "proxy": ""  // '' | 'system' | 'http://proxy.example.com:8080'
        }
    """
    proxy_config = settings_service.get_proxy_config()
    return {"proxy": proxy_config}


@router.post("/proxy")
async def update_proxy_settings(request: Request):
    """
    更新代理设置

    Args:
        request (Request): HTTP 请求对象，包含代理配置数据

    Returns:
        dict: 操作结果，包含 status 和 message 字段

    Raises:
        HTTPException: 当代理配置数据格式不正确时抛出 400 错误

    Description:
        仅更新代理相关的设置，不影响其他配置项。
        代理配置应该是一个包含 "proxy" 键的对象。

    Example:
        POST /api/settings/proxy
        {
            "proxy": ""  // 不使用代理
        }
        或
        {
            "proxy": "system"  // 使用系统代理
        }
        或
        {
            "proxy": "http://proxy.example.com:8080"  // 使用指定代理
        }
    """
    proxy_data = await request.json()

    # 验证代理数据格式
    if not isinstance(proxy_data, dict) or "proxy" not in proxy_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid proxy configuration. Expected format: {'proxy': 'value'}")

    proxy_value = proxy_data["proxy"]

    # 验证代理值的格式
    if not isinstance(proxy_value, str):
        raise HTTPException(
            status_code=400,
            detail="Proxy value must be a string")

    # 验证代理值的有效性
    if proxy_value not in ['', 'system'] and not proxy_value.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
        raise HTTPException(
            status_code=400,
            detail="Invalid proxy value. Must be '', 'system', or a valid proxy URL")

    # 更新代理设置
    result = await settings_service.update_settings({"proxy": proxy_value})
    return result


class CreateWorkflowRequest(BaseModel):
    name: str
    api_json: dict  # or str if you want it as string
    description: str
    inputs: list   # or str if you want it as string
    outputs: str = None

@router.post("/comfyui/create_workflow")
async def create_workflow(request: CreateWorkflowRequest):
    if not request.name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not request.api_json:
        raise HTTPException(status_code=400, detail="API JSON is required")
    if not request.description:
        raise HTTPException(status_code=400, detail="Description is required")
    if not request.inputs:
        raise HTTPException(status_code=400, detail="Inputs are required")
    try:
        api_json = json.dumps(request.api_json)
        inputs = json.dumps(request.inputs)
        outputs = json.dumps(request.outputs)
        db_service.create_comfy_workflow(request.name, api_json, request.description, inputs, outputs)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create workflow: {str(e)}")

@router.get("/comfyui/list_workflows")
async def list_workflows():
    return db_service.list_comfy_workflows()

@router.delete("/comfyui/delete_workflow")
async def delete_workflow(id: int):
    return db_service.delete_comfy_workflow(id)