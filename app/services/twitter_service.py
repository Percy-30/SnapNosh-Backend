import asyncio
import logging
from typing import Dict, Any, Optional, List
import yt_dlp
from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import USER_AGENTS
import random

logger = logging.getLogger(__name__)

class TwitterExtractor(BaseExtractor):
    """Extractor for Twitter (including x.com) videos"""
    
    SUPPORTED_DOMAINS = ["twitter.com", "x.com"]

    @property
    def platform(self) -> str:
        return "twitter"

    def get_platform_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://twitter.com/",
            "Origin": "https://twitter.com",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    def _get_ydl_opts(self, audio_only: bool = False, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Get yt-dlp options with proper headers and configuration"""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
            "http_headers": self.get_platform_headers(),
            "socket_timeout": 30,
            "extract_flat": False,
            "force_generic_extractor": False,
            "retries": 3,
            "extractor_args": {
                "twitter": {
                    "skip_auth_warning": True,
                    "referer": "https://twitter.com/"
                }
            }
        }
        
        if cookies:
            opts["cookiefile"] = cookies
            
        return opts

    async def _safe_extract_info(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Thread-safe info extraction with error handling"""
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
                raise SnapTubeError("Empty response from Twitter")
            return info
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"YT-DLP Error: {str(e)}")
            raise SnapTubeError(f"Twitter API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise SnapTubeError("Failed to process Twitter video")

    def _get_best_media_url(self, info: Dict[str, Any], audio_only: bool = False) -> Optional[str]:
        """Get highest quality media URL with proper validation"""
        try:
            formats: List[Dict] = info.get("formats", [])
            
            # Filter valid formats
            valid_formats = [
                f for f in formats
                if f.get('url') 
                and f.get('protocol') in ('http', 'https', 'm3u8', 'm3u8_native')
                and (f.get('acodec') != 'none' if audio_only else f.get('vcodec') != 'none')
            ]
            
            if not valid_formats:
                return info.get('url') if not audio_only or info.get('acodec') != 'none' else None
            
            # Sort by quality
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

    async def extract(self, url: str, **kwargs) -> Dict[str, Any]:
        """Main extraction method with enhanced error handling"""
        try:
            # Normalize URL (x.com → twitter.com)
            normalized_url = url.replace('x.com', 'twitter.com')
            
            ydl_opts = self._get_ydl_opts()
            info = await self._safe_extract_info(normalized_url, ydl_opts)
            
            video_url = self._get_best_media_url(info)
            if not video_url:
                raise SnapTubeError("No playable video found")
                
            return self._build_response(info, video_url)
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}", exc_info=True)
            raise

    def _build_response(self, info: Dict[str, Any], media_url: str) -> Dict[str, Any]:
        """Build standardized API response with safe type conversion"""
        best_format = next(
            (f for f in info.get("formats", []) if f.get("url") == media_url),
            {}
        )
        
        # Safe type conversion helper
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
            "title": str(info.get("title", "Twitter Video")),
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
                "fps": safe_float(best_format.get("fps")),
                "bitrate": safe_float(best_format.get("tbr")),
                "format": str(best_format.get("ext", "mp4"))
            }
        }

    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> str:
        try:
            ydl_opts = self._get_ydl_opts(audio_only=True, cookies=cookies)
            info = await self._safe_extract_info(url, ydl_opts)
    
            # Filtra formatos solo audio
            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none"
                and f.get("vcodec") == "none"
                and f.get("url")
            ]
            if audio_formats:
                audio_formats.sort(
                    key=lambda f: float(f.get("abr", 0) or f.get("tbr", 0)),
                    reverse=True
                )
                return audio_formats[0]["url"]
    
            # Si no hay audio puro, intenta con formatos combinados
            combined_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none" and f.get("url")
            ]
            if combined_formats:
                combined_formats.sort(
                    key=lambda f: float(f.get("tbr", 0)),
                    reverse=True
                )
                return combined_formats[0]["url"]
    
            # Fallback a url directa si es audio
            if info.get("url") and info.get("acodec") != "none" and info.get("vcodec") == "none":
                return info["url"]
    
            raise SnapTubeError("No se encontró stream de audio válido")
    
        except Exception as e:
            logger.error(f"Error en extract_audio_url(): {str(e)}", exc_info=True)
            raise SnapTubeError(f"Error extrayendo audio: {str(e)}")
