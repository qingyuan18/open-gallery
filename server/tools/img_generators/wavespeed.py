from typing import Optional
import os
import asyncio
import traceback
try:
    from .base import ImageGenerator, get_image_info_and_save, generate_image_id
except ImportError:
    from tools.img_generators.base import ImageGenerator, get_image_info_and_save, generate_image_id
from services.config_service import config_service, FILES_DIR
from utils.http_client import HttpClient


class WavespeedGenerator(ImageGenerator):
    """WaveSpeed image generator implementation"""

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int, int, str]:
        api_key = config_service.app_config.get(
            'wavespeed', {}).get('api_key', '')
        url = config_service.app_config.get('wavespeed', {}).get('url', '')

        async with HttpClient.create() as client:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'channel': os.environ.get('WAVESPEED_CHANNEL', ''),
            }

            if input_image:
                model = 'wavespeed-ai/flux-kontext-pro/multi'
                payload = {
                    "prompt": prompt,
                    "images": [input_image],
                    "guidance_scale": kwargs.get("guidance_scale", 3.5),
                    "num_images": kwargs.get("num_images", 1),
                    "safety_tolerance": str(kwargs.get("safety_tolerance", "2"))
                }
            else:
                payload = {
                    "enable_base64_output": False,
                    "enable_safety_checker": False,
                    "guidance_scale": kwargs.get("guidance_scale", 3.5),
                    "num_images": kwargs.get("num_images", 1),
                    "num_inference_steps": kwargs.get("num_inference_steps", 28),
                    "prompt": prompt,
                    "seed": -1,
                    "size": kwargs.get("size", "1024*1024"),
                    "strength": kwargs.get("strength", 0.8),
                }

            endpoint = f"{url.rstrip('/')}/{model}"
            response = await client.post(endpoint, json=payload, headers=headers)
            response_json = response.json()

            if response.status_code != 200 or response_json.get("code") != 200:
                raise Exception(f"WaveSpeed API error: {response_json}")

            result_url = response_json["data"]["urls"]["get"]

            # 轮询获取图片结果
            for _ in range(60):  # 最多等60秒
                await asyncio.sleep(1)
                result_resp = await client.get(result_url, headers=headers)
                result_data = result_resp.json()
                print("WaveSpeed polling result:", result_data)

                data = result_data.get("data", {})
                outputs = data.get("outputs", [])
                status = data.get("status")

                if status in ("succeeded", "completed") and outputs:
                    image_url = outputs[0]
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_url, os.path.join(FILES_DIR, f'{image_id}')
                    )
                    filename = f'{image_id}.{extension}'
                    return image_id, width, height, filename

                if status == "failed":
                    raise Exception(
                        f"WaveSpeed generation failed: {result_data}")

            raise Exception("WaveSpeed image generation timeout")
