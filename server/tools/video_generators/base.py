from abc import ABC, abstractmethod
from typing import Optional, Tuple
import base64
import aiofiles
import os
import subprocess
import json
try:
    from nanoid import generate
except ImportError:
    # Fallback ID generation if nanoid is not available
    import random
    import string
    def generate(size=8):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=size))
from utils.http_client import HttpClient


class VideoGenerator(ABC):
    """Abstract base class for video generators"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        input_image: Optional[str] = None,
        duration: int = 5,
        fps: int = 16,
        **kwargs
    ) -> Tuple[str, int, int, int, str]:
        """
        Generate a video and return metadata

        Args:
            prompt: Text prompt for video generation
            model: Model name/identifier
            input_image: Optional input image (base64 or file path) for i2v
            duration: Video duration in seconds
            fps: Frames per second
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (file_id, width, height, duration_seconds, filename)
        """
        pass


async def get_video_info_and_save(url, file_path_without_extension, is_b64=False):
    """Shared utility function to download/decode and save video"""
    if is_b64:
        video_content = base64.b64decode(url)
    else:
        # Fetch the video asynchronously
        async with HttpClient.create() as client:
            response = await client.get(url)
            # Read the video content as bytes
            video_content = response.content
    
    # Save to temporary file first
    temp_path = f"{file_path_without_extension}.mp4"
    async with aiofiles.open(temp_path, 'wb') as out_file:
        await out_file.write(video_content)
    
    print(f'🎬 Video saved to {temp_path}')
    
    # Get video metadata using ffprobe
    try:
        # Use ffprobe to get video information
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', temp_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        # Extract video stream information
        video_stream = None
        for stream in metadata.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if video_stream:
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            # Calculate duration from format or stream
            duration = float(metadata.get('format', {}).get('duration', 0))
            if duration == 0 and video_stream.get('duration'):
                duration = float(video_stream.get('duration', 0))
        else:
            # Fallback values if no video stream found
            width, height, duration = 0, 0, 0
            
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"⚠️ Warning: Could not get video metadata: {e}")
        # Use default values if ffprobe fails
        width, height, duration = 0, 0, 0
    
    # Return metadata
    extension = 'mp4'  # Default to mp4 for videos
    return 'video/mp4', width, height, duration, extension


def generate_video_id():
    """Generate unique video ID"""
    return 'vid_' + generate(size=8)
