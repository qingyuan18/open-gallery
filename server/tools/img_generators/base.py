from abc import ABC, abstractmethod
from typing import Optional, Tuple
import base64
from PIL import Image
from io import BytesIO
import aiofiles
try:
    from nanoid import generate
except ImportError:
    # Fallback ID generation if nanoid is not available
    import random
    import string
    def generate(size=8):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=size))
from utils.http_client import HttpClient


class ImageGenerator(ABC):
    """Abstract base class for image generators"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, int, int, str]:
        """
        Generate an image and return metadata

        Args:
            prompt: Text prompt for image generation
            model: Model name/identifier
            aspect_ratio: Image aspect ratio (e.g., "1:1", "16:9")
            input_image: Optional input image (base64 or file path)
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (file_id, width, height, filename)
        """
        pass


async def get_image_info_and_save(url, file_path_without_extension, is_b64=False):
    """Shared utility function to download/decode and save image"""
    if is_b64:
        image_content = base64.b64decode(url)
    else:
        # Fetch the image asynchronously
        async with HttpClient.create() as client:
            response = await client.get(url)
            # Read the image content as bytes
            image_content = response.content
    # Open the image
    image = Image.open(BytesIO(image_content))

    # Get MIME type
    mime_type = Image.MIME.get(image.format if image.format else 'PNG')

    # Get dimensions
    width, height = image.size

    # Determine the file extension
    extension = image.format.lower() if image.format else 'png'
    file_path = f"{file_path_without_extension}.{extension}"

    # Save the image to a local file with the correct extension asynchronously
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(image_content)
    print('🦄image saved to file_path', file_path)

    return mime_type, width, height, extension


def generate_image_id():
    """Generate unique image ID"""
    return 'im_' + generate(size=8)
