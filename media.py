"""
VK media handling: inbound attachment download, MIME detection.

Downloads VK attachments (photos, documents, audio, video)
to local cache so the AI agent can analyze them.
"""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Cache paths
_CACHE_ROOT = os.path.join(os.path.expanduser("~"), ".hermes", "cache", "vk_media")

# Image extensions
_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"})

# Audio extensions
_AUDIO_EXTS = frozenset({
    ".mp3", ".ogg", ".opus", ".wav", ".m4a", ".flac", ".aac", ".oga",
})

# Video extensions
_VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"})

# MIME type → extension mapping
_MIME_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/plain": ".txt",
    "application/json": ".json",
}


def _get_cache_dir() -> Path:
    """Get/create the VK media cache directory."""
    path = Path(_CACHE_ROOT)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _guess_extension(media_type: str, url: str) -> str:
    """Guess file extension from URL or MIME type."""
    # Try URL extension first
    url_path = url.split("?")[0]
    _, ext = os.path.splitext(url_path)
    if ext and len(ext) <= 6:
        return ext.lower()

    # Try MIME type
    mime = media_type.lower().split(";")[0].strip()
    return _MIME_MAP.get(mime, ".bin")


def _classify_media(ext: str) -> str:
    """Classify media by extension: 'image', 'audio', 'video', 'document'."""
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    return "document"


async def _download_url(client: httpx.AsyncClient, url: str, limiter=None) -> Optional[bytes]:
    """Download a URL and return bytes, with optional rate limiting."""
    if limiter:
        await limiter.acquire()
    try:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.warning("[VK] Failed to download media from %s: %s", url[:80], e)
        return None


def _save_to_cache(data: bytes, ext: str) -> str:
    """Save data to cache and return the file path."""
    cache_dir = _get_cache_dir()
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    filepath = cache_dir / filename
    filepath.write_bytes(data)
    return str(filepath)


async def download_vk_attachments(
    client: httpx.AsyncClient,
    attachments: List[Dict],
    download_limiter=None,
) -> List[Tuple[str, str, str]]:
    """
    Download VK message attachments to local cache.

    Args:
        client: httpx.AsyncClient for HTTP requests
        attachments: List of VK attachment dicts from the message

    Returns:
        List of (file_path, media_type, original_url) tuples.
        media_type is one of: "image", "audio", "video", "document"
    """
    if not attachments:
        return []

    results: List[Tuple[str, str, str]] = []

    for att in attachments:
        att_type = att.get("type", "")
        url = ""
        ext = ".bin"

        if att_type == "photo":
            photo = att.get("photo", {})
            sizes = photo.get("sizes", [])
            if sizes:
                best = sizes[-1]
                url = best.get("url", "")
                ext = ".jpg"

        elif att_type == "doc":
            doc = att.get("doc", {})
            url = doc.get("url", "")
            title = doc.get("title", "")
            ext_guess = _guess_extension(doc.get("ext", ""), url or title)
            ext = ext_guess if ext_guess != ".bin" else os.path.splitext(title)[1] or ".bin"

        elif att_type == "audio_message":
            audio_msg = att.get("audio_message", {})
            url = audio_msg.get("link_mp3", "")
            if not url:
                url = audio_msg.get("link_ogg", "")
            ext = ".ogg"

        elif att_type == "audio":
            audio = att.get("audio", {})
            url = audio.get("url", "")
            ext = ".mp3"

        elif att_type == "video":
            video = att.get("video", {})
            # VK video might have player URL or files
            url = video.get("player", "") or video.get("files", {}).get("mp4_720", "")
            if not url:
                url = video.get("files", {}).get("mp4_480", "") or video.get("files", {}).get("mp4_360", "")
            ext = ".mp4"

        elif att_type == "sticker":
            sticker = att.get("sticker", {})
            images = sticker.get("images", [])
            if images:
                # Get the largest sticker image
                best = max(images, key=lambda x: x.get("width", 0) * x.get("height", 0))
                url = best.get("url", "")
            ext = ".png"

        elif att_type == "graffiti":
            graffiti = att.get("graffiti", {})
            url = graffiti.get("url", "")
            ext = ".png"

        if not url:
            continue

        data = await _download_url(client, url, limiter=download_limiter)
        if data:
            media_type = _classify_media(ext)
            file_path = _save_to_cache(data, ext)
            results.append((file_path, media_type, url))
            logger.debug("[VK] Downloaded attachment: %s (%s)", file_path, media_type)

    return results


async def download_vk_image_by_url(
    client: httpx.AsyncClient,
    image_url: str,
    download_limiter=None,
) -> Optional[str]:
    """
    Download an image from a URL to local cache.

    Used for send_image when VK rejects direct URL upload.

    Returns the local file path, or None on failure.
    """
    _, ext = os.path.splitext(image_url.split("?")[0])
    if not ext or ext not in _IMAGE_EXTS:
        ext = ".jpg"

    data = await _download_url(client, image_url, limiter=download_limiter)
    if data:
        return _save_to_cache(data, ext)
    return None
