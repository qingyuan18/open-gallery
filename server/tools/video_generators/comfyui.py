from typing import Optional, Dict, Any
import os
import json
import sys
import copy
import random
import traceback
try:
    from .base import VideoGenerator, get_video_info_and_save, generate_video_id
except ImportError:
    # 使用绝对导入作为备用
    from tools.video_generators.base import VideoGenerator, get_video_info_and_save, generate_video_id
from services.config_service import config_service, FILES_DIR
from routers.comfyui_execution import execute


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


class ComfyUIVideoGenerator(VideoGenerator):
    """ComfyUI video generator implementation"""

    def __init__(self):
        # Load video workflows
        wan_t2v_workflow_path = get_asset_path('wanv_t2v.json')
        wan_i2v_workflow_path = get_asset_path('wan_i2v.json')
        ltx_i2v_workflow_path = get_asset_path('LTX2-3-i2v.json')
        ltx_t2v_workflow_path = get_asset_path('LTX2-t2v.json')

        self.wan_t2v_workflow = None
        self.wan_i2v_workflow = None
        self.ltx_i2v_workflow = None
        self.ltx_t2v_workflow = None

        try:
            self.wan_t2v_workflow = json.load(open(wan_t2v_workflow_path, 'r'))
            self.wan_i2v_workflow = json.load(open(wan_i2v_workflow_path, 'r'))
        except Exception as e:
            print(f"❌ Error loading WAN video workflows: {e}")
            traceback.print_exc()

        try:
            self.ltx_i2v_workflow = json.load(open(ltx_i2v_workflow_path, 'r'))
            print("✅ Loaded LTX2-3-i2v workflow")
        except Exception as e:
            print(f"⚠️ LTX2-3-i2v.json not found, LTX i2v will be unavailable: {e}")
            self.ltx_i2v_workflow = None

        try:
            self.ltx_t2v_workflow = json.load(open(ltx_t2v_workflow_path, 'r'))
            print("✅ Loaded LTX2-t2v workflow")
        except Exception as e:
            print(f"⚠️ LTX2-t2v.json not found, will fallback to WAN t2v: {e}")
            self.ltx_t2v_workflow = None

    async def generate(
        self,
        prompt: str,
        model: str,
        input_image: Optional[str] = None,
        duration: int = 5,
        fps: int = 16,
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

        # Determine workflow based on model and input
        if 'i2v' in model.lower() or input_image:
            # Image-to-video workflow - use LTX-i2v by default, fallback to WAN
            if self.ltx_i2v_workflow:
                return await self._run_ltx_i2v_workflow(prompt, input_image, host, port, ctx)
            else:
                # Fallback to old WAN i2v workflow
                if not self.wan_i2v_workflow:
                    raise Exception('No I2V workflow available (neither LTX nor WAN)')
                return await self._run_wan_i2v_workflow(prompt, input_image, host, port, ctx)
        else:
            # Text-to-video workflow - use LTX2 by default, fallback to WAN
            if self.ltx_t2v_workflow:
                return await self._run_ltx_t2v_workflow(prompt, host, port, ctx)
            elif self.wan_t2v_workflow:
                return await self._run_wan_t2v_workflow(prompt, host, port, ctx)
            else:
                raise Exception('No T2V workflow available (neither LTX2 nor WAN)')

    async def _run_wan_t2v_workflow(self, user_prompt: str, host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run WAN text-to-video workflow
        """
        workflow = copy.deepcopy(self.wan_t2v_workflow)

        # Configure text prompt (node 16 - WanVideoTextEncode)
        # In the new workflow, the prompt is in inputs.positive_prompt
        workflow['16']['inputs']['positive_prompt'] = user_prompt
        
        # Configure seed (node 27 - WanVideoSampler)
        workflow['27']['inputs']['seed'] = random.randint(0, 99999999998)

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from WAN T2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration), filename

    async def _run_ltx_t2v_workflow(self, user_prompt: str, host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run LTX2 text-to-video workflow
        """
        workflow = copy.deepcopy(self.ltx_t2v_workflow)

        # Configure text prompt (node 208 - PrimitiveStringMultiline "Positive prompt")
        workflow['208']['inputs']['value'] = user_prompt

        # Configure seeds
        workflow['209']['inputs']['noise_seed'] = random.randint(0, 99999999998)
        workflow['200']['inputs']['noise_seed'] = random.randint(0, 99999999998)

        print(f"🔧 Workflow params (LTX2-t2v): seed1={workflow['209']['inputs']['noise_seed']}, seed2={workflow['200']['inputs']['noise_seed']}, text_preview={user_prompt[:80]!r}")

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from LTX2 T2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration), filename

    async def _run_wan_i2v_workflow(self, user_prompt: str, input_image_base64: Optional[str], host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run WAN image-to-video workflow
        """
        workflow = copy.deepcopy(self.wan_i2v_workflow)

        if input_image_base64:
            # Configure input image (node 18 - LoadImage)
            # Note: We need to modify this to use base64 input instead of file loading
            # For now, we'll use a placeholder approach similar to flux-kontext
            workflow['122']['inputs']['image'] = input_image_base64
        else:
            # When no input image is provided, create a simple 1x1 pixel transparent PNG as placeholder
            placeholder_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII="
            workflow['122']['inputs']['image'] = placeholder_image
            print("🔍 DEBUG: Using placeholder image for WAN I2V workflow (no input image provided)")

        # Configure text prompt for I2V workflow
        # In I2V workflow, node 16 references node 46 (DeepTranslatorTextNode)
        # So we need to set the text in node 46
        workflow['98']['inputs']['text'] = user_prompt
        
        # Configure seed (node 27 - WanVideoSampler)
        workflow['27']['inputs']['seed'] = random.randint(0, 99999999998)

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from WAN I2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration), filename

    async def _run_ltx_i2v_workflow(self, user_prompt: str, input_image_base64: Optional[str], host: str, port: str, ctx: dict) -> tuple[str, int, int, int, str]:
        """
        Run LTX2-3 image-to-video workflow
        """
        workflow = copy.deepcopy(self.ltx_i2v_workflow)

        # Configure input image (node 98 - ETN_LoadImageBase64)
        if input_image_base64:
            workflow['98']['inputs']['image'] = input_image_base64
        else:
            placeholder_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII="
            workflow['98']['inputs']['image'] = placeholder_image
            print("🔍 DEBUG: Using placeholder image for LTX2-3 I2V workflow (no input image provided)")

        # Configure text prompt (node 233 - Text Multiline)
        workflow['233']['inputs']['text'] = user_prompt

        # Configure seeds (node 201 - RandomNoise, node 214 - KSampler)
        workflow['201']['inputs']['noise_seed'] = random.randint(0, 99999999998)
        workflow['214']['inputs']['seed'] = random.randint(0, 99999999998)

        print(f"🔧 Workflow params (LTX2-3-i2v): has_input={bool(input_image_base64)}, seed1={workflow['201']['inputs']['noise_seed']}, seed2={workflow['214']['inputs']['seed']}, text_preview={user_prompt[:80]!r}")

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from LTX2-3 I2V workflow')

        url = execution.outputs[0]

        # Get video metadata and save
        video_id = generate_video_id()
        mime_type, width, height, duration, extension = await get_video_info_and_save(
            url, os.path.join(FILES_DIR, f'{video_id}')
        )
        filename = f'{video_id}.{extension}'
        return video_id, width, height, int(duration), filename
