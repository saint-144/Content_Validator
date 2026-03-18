"""
Image Processing Service
Handles file operations, pHash computation, pixel-level comparison
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple
import hashlib

from PIL import Image
import imagehash
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def get_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in ALLOWED_IMAGE_TYPES:
        return "image"
    elif suffix in ALLOWED_VIDEO_TYPES:
        return "video"
    raise ValueError(f"Unsupported file type: {suffix}")


def save_upload(file_bytes: bytes, original_name: str, subfolder: str = "templates") -> Tuple[str, str]:
    """Save uploaded file and return (saved_path, saved_filename)."""
    ext = Path(original_name).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_dir = Path(settings.UPLOAD_DIR) / subfolder
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / unique_name
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return str(file_path), unique_name


def compute_phash(file_path: str) -> Optional[str]:
    """Compute perceptual hash of image."""
    try:
        img = Image.open(file_path).convert("RGB")
        return str(imagehash.phash(img))
    except Exception as e:
        logger.error("pHash failed for %s: %s", file_path, e)
        return None


def phash_similarity(hash1: str, hash2: str) -> float:
    """Convert pHash hamming distance to 0-100 similarity score."""
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        distance = h1 - h2
        return max(0.0, (64 - distance) / 64 * 100)
    except Exception:
        return 0.0


def pixel_similarity(path1: str, path2: str, resize_to: Tuple[int, int] = (256, 256)) -> float:
    """
    Compute pixel-level similarity between two images.
    Returns 0-100 where 100 = identical.
    """
    try:
        img1 = Image.open(path1).convert("RGB").resize(resize_to)
        img2 = Image.open(path2).convert("RGB").resize(resize_to)
        arr1 = np.array(img1).astype(float)
        arr2 = np.array(img2).astype(float)
        diff = np.abs(arr1 - arr2)
        mse = np.mean(diff ** 2)
        max_mse = 255 ** 2
        similarity = (1 - mse / max_mse) * 100
        return round(float(similarity), 2)
    except Exception as e:
        logger.error("Pixel similarity failed: %s", e)
        return 0.0


def extract_video_thumbnail(video_path: str) -> Optional[str]:
    """Extract first frame of video as image for LLM analysis."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        success, frame = cap.read()
        cap.release()
        if success:
            thumb_path = video_path + "_thumb.jpg"
            cv2.imwrite(thumb_path, frame)
            return thumb_path
    except ImportError:
        logger.warning("OpenCV not available for video thumbnail extraction")
    except Exception as e:
        logger.error("Video thumbnail extraction failed: %s", e)
    return None


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file for deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def cleanup_temp_file(path: str):
    """Remove a temporary file safely."""
    try:
        if path and os.path.exists(path) and "tmp" in path:
            os.remove(path)
    except Exception:
        pass
