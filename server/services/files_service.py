from pathlib import Path
from fastapi.responses import FileResponse

def download_file(path: str):
    """
    Download a file given its path.

    Args:
        path (str): Path to the file to be downloaded.

    Returns:
        FileResponse: If the file exists and is a file, returns a FileResponse to trigger download.
    
    Raises:
        HTTPException: If the file does not exist or is not a file, raises a 404 error.
    """
    file_path = Path(path)
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return {"error": "File not found"}
