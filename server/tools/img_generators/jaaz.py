from typing import Optional
import os
import traceback
import base64
try:
    from .base import ImageGenerator, get_image_info_and_save, generate_image_id
except ImportError:
    from tools.img_generators.base import ImageGenerator, get_image_info_and_save, generate_image_id
from services.config_service import config_service, FILES_DIR
from utils.http_client import HttpClient


class JaazGenerator(ImageGenerator):
    """Jaaz Cloud image generator implementation"""

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int, int, str]:
        """
        使用 Jaaz API 服务生成图像
        支持 Replicate 格式和 OpenAI 格式的模型
        """
        # 检查是否是 OpenAI 模型
        if model.startswith('openai/'):
            return await self.generate_openai_image(
                prompt=prompt,
                model=model,
                input_path=input_image,
                **kwargs
            )

        # 原有的 Replicate 兼容逻辑
        try:
            # 从配置中获取 API 设置
            jaaz_config = config_service.app_config.get('jaaz', {})
            api_url = jaaz_config.get('url', '')
            api_token = jaaz_config.get('api_key', '')

            if not api_url or not api_token:
                raise ValueError("Jaaz API URL or token is not configured")

            # 构建请求 URL
            if api_url.rstrip('/').endswith('/api/v1'):
                url = f"{api_url.rstrip('/')}/image/generations"
            else:
                url = f"{api_url.rstrip('/')}/api/v1/image/generations"

            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }

            # 构建请求数据，与 Replicate 格式一致
            data = {
                "prompt": prompt,
                "model": model,
                "aspect_ratio": aspect_ratio,
            }

            # 如果有输入图像，添加到请求中
            if input_image:
                data['input_image'] = input_image

            print(
                f'🦄 Jaaz image generation request: {url} {prompt[:50]}... with model: {model}')

            async with HttpClient.create() as client:
                response = await client.post(url, headers=headers, json=data)
                res = response.json()

            # 从响应中获取图像 URL
            output = res.get('output', '')
            print('🦄 Jaaz image generation response output', output)
            if isinstance(output, list) and len(output) > 0:
                output = output[0]  # 取第一张图片

            if not output:
                error_detail = res.get(
                    'detail', res.get('error', 'Unknown error'))
                raise Exception(
                    f'Jaaz image generation failed: {error_detail}')

            # 生成唯一图像 ID
            image_id = generate_image_id()
            print(f'🦄 Jaaz image generation image_id: {image_id}')

            # 下载并保存图像
            mime_type, width, height, extension = await get_image_info_and_save(
                output,
                os.path.join(FILES_DIR, f'{image_id}')
            )

            filename = f'{image_id}.{extension}'
            return image_id, width, height, filename

        except Exception as e:
            print('Error generating image with Jaaz:', e)
            traceback.print_exc()
            raise e

    async def generate_openai_image(
        self,
        prompt: str,
        model: str,
        input_path: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int, int, str]:
        """
        使用 Jaaz API 服务调用 OpenAI 模型生成图像
        兼容 OpenAI 图像生成 API
        """
        try:
            # 从配置中获取 Jaaz API 设置
            jaaz_config = config_service.app_config.get('jaaz', {})
            api_url = jaaz_config.get('url', '')
            api_token = jaaz_config.get('api_key', '')

            if not api_url or not api_token:
                raise ValueError("Jaaz API URL or token is not configured")

            # 构建请求 URL - 检查是否已经包含 /api/v1
            if api_url.rstrip('/').endswith('/api/v1'):
                url = f"{api_url.rstrip('/')}/image/generations"
            else:
                url = f"{api_url.rstrip('/')}/api/v1/image/generations"

            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }

            # 构建请求数据
            data = {
                "model": model,
                "prompt": prompt,
                "n": kwargs.get("num_images", 1),
                "size": kwargs.get("size", "1024x1024"),
            }

            # 如果有输入图像（编辑模式）
            if input_path:
                if input_path.startswith('data:'):
                    data['input_image'] = input_path
                else:
                    # 如果是文件路径，将图像转换为 base64
                    with open(input_path, 'rb') as image_file:
                        image_data = image_file.read()
                        image_b64 = base64.b64encode(
                            image_data).decode('utf-8')
                        data['input_image'] = image_b64
                data['mask'] = None  # 如果需要遮罩，可以在这里添加

            print(
                f'🦄 Jaaz OpenAI image generation request: {prompt[:50]}... with model: {model}')

            async with HttpClient.create() as client:
                response = await client.post(url, headers=headers, json=data)
                res = response.json()


            # 检查响应格式
            if 'data' in res and len(res['data']) > 0:
                # OpenAI 格式响应
                image_data = res['data'][0]
                if 'b64_json' in image_data:
                    image_b64 = image_data['b64_json']
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_b64,
                        os.path.join(FILES_DIR, f'{image_id}'),
                        is_b64=True
                    )
                    filename = f'{image_id}.{extension}'
                    return image_id, width, height, filename
                elif 'url' in image_data:
                    # URL 格式响应
                    image_url = image_data['url']
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_url,
                        os.path.join(FILES_DIR, f'{image_id}')
                    )
                    filename = f'{image_id}.{extension}'
                    return image_id, width, height, filename

            # 如果没有找到有效的图像数据
            error_detail = res.get('error', res.get('detail', 'Unknown error'))
            raise Exception(
                f'Jaaz OpenAI image generation failed: {error_detail}')

        except Exception as e:
            print('Error generating image with Jaaz OpenAI:', e)
            traceback.print_exc()
            raise e
