from typing import Optional
import os
import traceback
try:
    from .base import ImageGenerator, get_image_info_and_save, generate_image_id
except ImportError:
    from tools.img_generators.base import ImageGenerator, get_image_info_and_save, generate_image_id
from services.config_service import config_service, FILES_DIR
from utils.http_client import HttpClient


class ReplicateGenerator(ImageGenerator):
    """Replicate image generator implementation"""

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int, int, str]:
        try:
            api_key = config_service.app_config.get(
                'replicate', {}).get('api_key', '')
            if not api_key:
                raise ValueError(
                    "Image generation failed: Replicate API key is not set")

            url = f"https://api.replicate.com/v1/models/{model}/predictions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Prefer": "wait"
            }
            data = {
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                }
            }

            if input_image:
                data['input']['input_image'] = input_image
                model = 'black-forest-labs/flux-kontext-pro'

            async with HttpClient.create() as client:
                response = await client.post(url, headers=headers, json=data)
                res = response.json()

            output = res.get('output', '')
            if output == '':
                if res.get('detail', '') != '':
                    raise Exception(
                        f'Replicate image generation failed: {res.get("detail", "")}')
                else:
                    raise Exception(
                        'Replicate image generation failed: no output url found')

            image_id = generate_image_id()
            print('🦄image generation image_id', image_id)

            # get image dimensions
            mime_type, width, height, extension = await get_image_info_and_save(
                output, os.path.join(FILES_DIR, f'{image_id}')
            )
            filename = f'{image_id}.{extension}'
            return image_id, width, height, filename

        except Exception as e:
            print('Error generating image with replicate', e)
            traceback.print_exc()
            raise e
