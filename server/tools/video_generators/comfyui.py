from typing import Optional
import os
import io
import json
import sys
import copy
import math
import base64
import random
import traceback
try:
    from .base import VideoGenerator, get_video_info_and_save, generate_video_id
except ImportError:
    # 使用绝对导入作为备用
    from tools.video_generators.base import VideoGenerator, get_video_info_and_save, generate_video_id
from services.config_service import config_service, FILES_DIR
from routers.comfyui_execution import execute

# MiniMax H3 latent grid: length must be 17k+5 frames at 24 fps
H3_FPS = 24
H3_MIN_LENGTH = 56    # ~2.3s
H3_MAX_LENGTH = 243   # ~10s
H3_DEFAULT_WIDTH = 864
H3_DEFAULT_HEIGHT = 480
H3_TARGET_PIXELS = 0.4 * 1024 * 1024  # 0.4MP resolution tier


def get_asset_path(filename):
    # To get the correct path for pyinstaller bundled application
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the path is relative to the executable
        base_path = sys._MEIPASS
    else:
        # If the application is run in a normal Python environment
        base_path = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))

    return os.path.join(base_path, 'asset', filename)


def h3_length_from_duration(duration: int) -> int:
    """Snap a duration in seconds onto the H3 17k+5 frame grid."""
    frames = int(duration) * H3_FPS
    k = round((frames - 5) / 17)
    length = 17 * k + 5
    return max(H3_MIN_LENGTH, min(H3_MAX_LENGTH, length))


def h3_dims_from_image(image_base64: str) -> tuple[int, int]:
    """Compute H3 width/height (multiples of 32, ~0.4MP) matching the input image aspect ratio."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(image_base64)))
        src_w, src_h = img.size
        scale = math.sqrt(H3_TARGET_PIXELS / (src_w * src_h))
        width = max(32, round(src_w * scale / 32) * 32)
        height = max(32, round(src_h * scale / 32) * 32)
        return width, height
    except Exception as e:
        print(f"⚠️ Could not derive H3 dims from input image, using defaults: {e}")
        return H3_DEFAULT_WIDTH, H3_DEFAULT_HEIGHT


class ComfyUIVideoGenerator(VideoGenerator):
    """ComfyUI video generator implementation (MiniMax H3 workflows)"""

    def __init__(self):
        self.h3_t2v_workflow = None
        self.h3_i2v_workflow = None

        try:
            self.h3_t2v_workflow = json.load(open(get_asset_path('h3_t2v.json'), 'r'))
            print("✅ Loaded MiniMax H3 t2v workflow")
        except Exception as e:
            print(f"❌ Error loading h3_t2v.json: {e}")
            traceback.print_exc()

        try:
            self.h3_i2v_workflow = json.load(open(get_asset_path('h3_i2v.json'), 'r'))
            print("✅ Loaded MiniMax H3 i2v workflow")
        except Exception as e:
            print(f"❌ Error loading h3_i2v.json: {e}")
            traceback.print_exc()

    async def generate(
        self,
        prompt: str,
        model: str,
        input_image: Optional[str] = None,
        duration: int = 5,
        fps: int = H3_FPS,
        **kwargs
    ) -> tuple[str, int, int, int, str]:
        # Get context from kwargs
        ctx = kwargs.get('ctx', {})
        print(f"🎬 ComfyUI generating video: {model}")

        api_url = config_service.app_config.get('comfyui', {}).get('url', '')

        if not api_url:
            raise Exception("ComfyUI URL not configured")

        api_url = api_url.replace('http://', '').replace('https://', '')
        host = api_url.split(':')[0]
        port = api_url.split(':')[1]

        if 'i2v' in model.lower() or input_image:
            if not self.h3_i2v_workflow:
                raise Exception('H3 I2V workflow not available (h3_i2v.json failed to load)')
            return await self._run_h3_i2v_workflow(prompt, input_image, duration, host, port, ctx)
        else:
            if not self.h3_t2v_workflow:
                raise Exception('H3 T2V workflow not available (h3_t2v.json failed to load)')
            return await self._run_h3_t2v_workflow(prompt, duration, host, port, ctx)

    async def _run_h3_t2v_workflow(self, user_prompt: str, duration: int, host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run MiniMax H3 text-to-video workflow
        """
        workflow = copy.deepcopy(self.h3_t2v_workflow)

        # Node 104 - MiniMaxH3ImageToVideo (t2v mode: no first_frame input)
        workflow['104']['inputs']['prompt'] = user_prompt
        workflow['104']['inputs']['length'] = h3_length_from_duration(duration)

        # Node 15 - RandomNoise
        workflow['15']['inputs']['noise_seed'] = random.randint(0, 99999999998)

        print(f"🔧 Workflow params (h3-t2v): length={workflow['104']['inputs']['length']}, "
              f"seed={workflow['15']['inputs']['noise_seed']}, text_preview={user_prompt[:80]!r}")

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from H3 T2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration_s, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration_s), filename

    async def _run_h3_i2v_workflow(self, user_prompt: str, input_image_base64: Optional[str], duration: int, host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run MiniMax H3 image-to-video workflow
        """
        workflow = copy.deepcopy(self.h3_i2v_workflow)

        # Node 114 - ETN_LoadImageBase64
        if input_image_base64:
            workflow['114']['inputs']['image'] = input_image_base64
            width, height = h3_dims_from_image(input_image_base64)
        else:
            placeholder_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII="
            workflow['114']['inputs']['image'] = placeholder_image
            width, height = H3_DEFAULT_WIDTH, H3_DEFAULT_HEIGHT
            print("🔍 DEBUG: Using placeholder image for H3 I2V workflow (no input image provided)")

        # Node 104 - MiniMaxH3ImageToVideo (first_frame wired from ImageScaleToTotalPixels)
        workflow['104']['inputs']['prompt'] = user_prompt
        workflow['104']['inputs']['width'] = width
        workflow['104']['inputs']['height'] = height
        workflow['104']['inputs']['length'] = h3_length_from_duration(duration)

        # Node 15 - RandomNoise
        workflow['15']['inputs']['noise_seed'] = random.randint(0, 99999999998)

        print(f"🔧 Workflow params (h3-i2v): has_input={bool(input_image_base64)}, "
              f"size={width}x{height}, length={workflow['104']['inputs']['length']}, "
              f"seed={workflow['15']['inputs']['noise_seed']}, text_preview={user_prompt[:80]!r}")

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from H3 I2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration_s, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration_s), filename
