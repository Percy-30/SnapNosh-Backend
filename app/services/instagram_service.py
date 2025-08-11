import asyncio
import logging
import os
import sys
import tempfile
from typing import Dict, Any, Optional, List
import yt_dlp
from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import USER_AGENTS
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

executor = ThreadPoolExecutor()

class InstagramExtractor(BaseExtractor):
    """Extractor para videos de Instagram (posts, reels, IGTV)"""

    SUPPORTED_DOMAINS = ["instagram.com", "www.instagram.com", "instagr.am"]

    @property
    def platform(self) -> str:
        return "instagram"

    def get_platform_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.instagram.com/",
            "Origin": "https://www.instagram.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_ydl_opts(self, audio_only: bool = False, cookies: Optional[str] = None) -> Dict[str, Any]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
            "http_headers": self.get_platform_headers(),
            "socket_timeout": 30,
            "extract_flat": False,
            "force_generic_extractor": False,
            "retries": 3,
            # Instagram no requiere args extra específicos aquí
        }

        if cookies:
            opts["cookiefile"] = cookies

        return opts

    async def _safe_extract_info(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        try:
            info = await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(
                    url,
                    download=False,
                    process=True,
                    extra_info={}
                )
            )
            if not info:
                raise SnapTubeError("Empty response from Instagram")
            return info
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YT-DLP Error: {str(e)}")
            raise SnapTubeError(f"Instagram API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise SnapTubeError("Failed to process Instagram video")

    def _get_best_media_url(self, info: Dict[str, Any], audio_only: bool = False) -> Optional[str]:
        try:
            formats: List[Dict] = info.get("formats", [])

            valid_formats = [
                f for f in formats
                if f.get('url')
                and f.get('protocol') in ('http', 'https', 'm3u8', 'm3u8_native')
                and (f.get('acodec') != 'none' if audio_only else f.get('vcodec') != 'none')
            ]

            if not valid_formats:
                return info.get('url') if not audio_only or info.get('acodec') != 'none' else None

            valid_formats.sort(
                key=lambda f: (
                    f.get('width', 0) * f.get('height', 0) if not audio_only else 0,
                    float(f.get('tbr', 0) or f.get('abr', 0) or 0),
                    f.get('fps', 0)
                ),
                reverse=True
            )

            return valid_formats[0]['url']
        except Exception as e:
            logger.warning(f"Format selection error: {str(e)}")
            return None

    def _build_response(self, info: Dict[str, Any], media_url: str) -> Dict[str, Any]:
        best_format = next(
            (f for f in info.get("formats", []) if f.get("url") == media_url),
            {}
        )
    
        def safe_int(value, default=0):
            try:
                return int(value) if value is not None else default
            except (TypeError, ValueError):
                return default
    
        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default
    
        return {
            "status": "success",
            "platform": self.platform,
            "title": str(info.get("title", "Instagram Video")),
            "description": str(info.get("description", "")),
            "thumbnail": str(info.get("thumbnail", "")),
            "duration": safe_int(info.get("duration")),
            "video_url": str(media_url),
            "width": safe_int(best_format.get("width")),
            "height": safe_int(best_format.get("height")),
            "uploader": str(info.get("uploader", "")),
            "uploader_id": str(info.get("uploader_id", "")),
            "view_count": safe_int(info.get("view_count")),
            "like_count": safe_int(info.get("like_count")),
            "comment_count": safe_int(info.get("comment_count")),
            "upload_date": str(info.get("upload_date", "")),
            "method": "yt-dlp",
            "quality": {
                "resolution": f"{safe_int(best_format.get('width'))}x{safe_int(best_format.get('height'))}",
                "fps": int(round(safe_float(best_format.get("fps")))),
                "bitrate": safe_int(best_format.get("tbr")),
                "format": str(best_format.get("ext", "mp4"))
            }
        }


    async def extract(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            ydl_opts = self._get_ydl_opts()
            info = await self._safe_extract_info(url, ydl_opts)
            media_url = self._get_best_media_url(info)
            if not media_url:
                raise SnapTubeError("No playable media found")
            return self._build_response(info, media_url)
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}", exc_info=True)
            raise

    async def convert_m3u8_to_mp3(self, m3u8_url: str) -> str:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"audio_{int(asyncio.get_event_loop().time() * 1000)}.mp3")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", m3u8_url,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "128k",
            output_path
        ]

        def run_ffmpeg():
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode().strip()}")
            return output_path

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, run_ffmpeg)

    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        try:
            ydl_opts = self._get_ydl_opts(audio_only=True, cookies=cookies)
            info = await self._safe_extract_info(url, ydl_opts)

            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none"
                and f.get("vcodec") == "none"
                and f.get("url")
            ]

            if not audio_formats:
                raise SnapTubeError("No audio streams found")

            audio_formats.sort(
                key=lambda f: float(f.get("abr", 0) or f.get("tbr", 0)),
                reverse=True
            )
            best_audio_url = audio_formats[0]["url"]

            if best_audio_url.endswith(".m3u8"):
                mp3_path = await self.convert_m3u8_to_mp3(best_audio_url)
                return {
                    "status": "success",
                    "audio_mp3_path": mp3_path,
                    "metadata": {
                        "bitrate": int(audio_formats[0].get("abr", 0) or audio_formats[0].get("tbr", 0)),
                        "codec": "mp3",
                        "duration": int(info.get("duration", 0)),
                        "quality": "128kbps"
                    }
                }
            else:
                return {
                    "status": "success",
                    "audio_url": best_audio_url,
                    "metadata": {
                        "bitrate": int(audio_formats[0].get("abr", 0) or audio_formats[0].get("tbr", 0)),
                        "codec": "mp4a",
                        "duration": int(info.get("duration", 0)),
                        "quality": "128kbps"
                    }
                }
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "solution": "Check URL or audio format"
            }
