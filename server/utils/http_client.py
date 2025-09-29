"""
HTTP 客户端工厂和管理器

本模块提供了统一的 HTTP 客户端创建和管理功能，基于 httpx 库封装，支持：
- 自动 SSL 证书验证
- 连接池管理和超时控制
- 同步和异步客户端支持

使用指南：
1. 单次/少量请求：使用 HttpClient.create() 自动管理资源
   async with HttpClient.create() as client:
       response = await client.get("https://api.example.com/data")

2. 长期持有客户端：使用 HttpClient.create_async_client() 手动管理
   client = HttpClient.create_async_client()
   try:
       response = await client.get("https://api.example.com/data")
   finally:
       await client.aclose()

3. 同步请求：使用 HttpClient.create_sync()
   with HttpClient.create_sync() as client:
       response = client.get("https://api.example.com/data")
"""
import ssl
import certifi
import httpx
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager, contextmanager
import logging

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP 客户端工厂和管理器"""

    _ssl_context: Optional[ssl.SSLContext] = None

    @classmethod
    def _get_ssl_context(cls) -> ssl.SSLContext:
        """获取缓存的 SSL 上下文"""
        if cls._ssl_context is None:
            try:
                cls._ssl_context = ssl.create_default_context(
                    cafile=certifi.where())
            except Exception as e:
                logger.warning(
                    f"Failed to create SSL context with certifi: {e}")
                cls._ssl_context = ssl.create_default_context()
        return cls._ssl_context

    @classmethod
    def _get_client_config(cls, **kwargs) -> Dict[str, Any]:
        """获取客户端配置"""
        # 默认超时配置，适合大多数 AI API 调用
        default_timeout = httpx.Timeout(
            connect=20.0,   # 连接超时 20 秒
            read=120.0,     # 读取超时 2 分钟
            write=30.0,     # 写入超时 30 秒
            pool=60.0       # 连接池超时 60 秒
        )

        config = {
            'verify': cls._get_ssl_context(),
            'timeout': default_timeout,
            'follow_redirects': True,
            'limits': httpx.Limits(
                max_keepalive_connections=50,
                max_connections=200,
                keepalive_expiry=60.0
            ),
            **kwargs
        }

        return config

    # ========== 工厂方法 ==========

    @classmethod
    @asynccontextmanager
    async def create(cls, url: Optional[str] = None, **kwargs):
        """创建异步客户端上下文管理器"""
        config = cls._get_client_config(**kwargs)
        client = httpx.AsyncClient(**config)
        try:
            yield client
        finally:
            await client.aclose()

    @classmethod
    @contextmanager
    def create_sync(cls, url: Optional[str] = None, **kwargs):
        """创建同步客户端上下文管理器"""
        config = cls._get_client_config(**kwargs)
        client = httpx.Client(**config)
        try:
            yield client
        finally:
            client.close()

    @classmethod
    def create_async_client(cls, **kwargs) -> httpx.AsyncClient:
        """直接创建异步客户端（需要手动关闭）"""
        config = cls._get_client_config(**kwargs)
        return httpx.AsyncClient(**config)

    @classmethod
    def create_sync_client(cls, **kwargs) -> httpx.Client:
        """直接创建同步客户端（需要手动关闭）"""
        config = cls._get_client_config(**kwargs)
        return httpx.Client(**config)
