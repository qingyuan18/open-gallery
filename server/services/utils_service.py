def detect_image_type_from_base64(b64_data: str) -> str:
    # Only take the base64 part, not the "data:image/...," prefix
    if b64_data.startswith("data:"):
        b64_data = b64_data.split(",", 1)[1]

    # Decode just the first few bytes
    prefix_bytes = base64.b64decode(b64_data[:24])  # ~18 bytes is enough

    if prefix_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif prefix_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif prefix_bytes.startswith(b"GIF87a") or prefix_bytes.startswith(b"GIF89a"):
        return "image/gif"
    elif prefix_bytes.startswith(b"RIFF") and b"WEBP" in prefix_bytes:
        return "image/webp"
    else:
        return "application/octet-stream"
