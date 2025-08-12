# app/services/youtube_service.py
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import random
import time

from app.utils.proxy import ProxyRotator
from app.services.cookie_manager import CookieManager
import yt_dlp

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import YOUTUBE_HEADERS, QUALITY_FORMATS, USER_AGENTS
from app.config import settings

logger = logging.getLogger(__name__)

COOKIES_FILE = Path("cookies.txt")

class YouTubeExtractor(BaseExtractor):
    """Enhanced YouTube extractor with multiple fallback strategies and cookie management"""

    def __init__(self, cookies_file: Optional[str] = None):
        self._cookies_file = cookies_file or (str(COOKIES_FILE) if COOKIES_FILE.exists() else None)
        super().__init__()
        
        self.cookie_manager = CookieManager()
        proxy_list = settings.PROXY_LIST.split(",") if settings.USE_PROXIES else []
        self.proxy_rotator = ProxyRotator(proxy_list)
        
        # User agent rotation
        self.user_agents = USER_AGENTS or [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
        ]

    @property
    def platform(self) -> str:
        return "youtube"

    def get_platform_headers(self) -> Dict[str, str]:
        headers = YOUTUBE_HEADERS.copy()
        headers["User-Agent"] = self.get_random_user_agent()
        return headers

    def get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def _ensure_cookies_file(self) -> Optional[str]:
        """Ensure we have a valid cookies file, exporting from browser if needed"""
        if self._cookies_file and Path(self._cookies_file).exists():
            return self._cookies_file

        # Try exporting from browsers
        for browser in ['chrome', 'edge', 'firefox', 'brave']:
            output_path = Path("cookies.txt")
            success = self.cookie_manager.export_browser_cookies(browser, output_path)
            if success and self.cookie_manager.validate_cookies_file(output_path):
                self._cookies_file = str(output_path)
                logger.info(f"Cookies file generated automatically from {browser}")
                return self._cookies_file
        
        logger.warning("Could not generate cookies file automatically")
        return None

    async def extract(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best",
        **kwargs
    ) -> Dict[str, Any]:
        """Enhanced extraction with multiple fallback strategies"""
        self.validator.validate_url(url)
        
        # Try different strategies in order
        strategies = [
            self._try_with_cookies,
            self._try_with_proxy_rotation,
            self._try_mobile_client,
            self._try_legacy_approach,
            self._try_emergency_extraction
        ]
        
        for strategy in strategies:
            try:
                result = await strategy(url, cookies, quality)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Strategy {strategy.__name__} failed: {str(e)}")
                continue
        
        raise SnapTubeError("All extraction methods failed. YouTube may be blocking requests.")

    async def _try_with_cookies(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best"
    ) -> Dict[str, Any]:
        """Primary strategy using cookies"""
        cookies_path = None
        cookies_file = self._ensure_cookies_file()
        
        try:
            # Use provided cookies or fall back to file
            if cookies:
                cookies_path = self._save_temp_cookies(cookies)
                cookies_file = cookies_path
                
            if not cookies_file:
                raise SnapTubeError("No cookies available")
                
            ydl_opts = self._get_base_options(quality)
            ydl_opts["cookiefile"] = cookies_file
            
            info = await self._execute_extraction(url, ydl_opts)
            return self._build_response(info, True)
            
        finally:
            if cookies_path and os.path.exists(cookies_path):
                os.unlink(cookies_path)

    async def _try_with_proxy_rotation(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best"
    ) -> Dict[str, Any]:
        """Try with proxy rotation if enabled"""
        if not settings.USE_PROXIES:
            raise SnapTubeError("Proxy rotation not enabled")
            
        proxy = self.proxy_rotator.get_yt_dlp_proxy_option()
        if not proxy:
            raise SnapTubeError("No proxies available")
            
        ydl_opts = self._get_base_options(quality)
        ydl_opts["proxy"] = proxy
        
        try:
            info = await self._execute_extraction(url, ydl_opts)
            return self._build_response(info, False)
        except Exception as e:
            if "proxy" in str(e).lower():
                self.proxy_rotator.mark_proxy_failed(proxy)
            raise

    async def _try_mobile_client(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best"
    ) -> Dict[str, Any]:
        """Try with mobile client configuration"""
        ydl_opts = self._get_base_options(quality)
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["android", "ios"],
                "skip": ["hls", "dash"]
            }
        }
        ydl_opts["http_headers"]["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 10; SM-G981B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/80.0.3987.162 Mobile Safari/537.36"
        )
        
        info = await self._execute_extraction(url, ydl_opts)
        return self._build_response(info, False)

    async def _try_legacy_approach(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best"
    ) -> Dict[str, Any]:
        """Legacy approach for older YouTube formats"""
        ydl_opts = self._get_base_options(quality)
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["web"],
                "skip": ["hls", "dash"]
            }
        }
        ydl_opts["format"] = "best[height<=720]"
        
        info = await self._execute_extraction(url, ydl_opts)
        return self._build_response(info, False)

    async def _try_emergency_extraction(
        self,
        url: str,
        cookies: Optional[str] = None,
        quality: str = "best"
    ) -> Dict[str, Any]:
        """Last resort extraction method"""
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "socket_timeout": 120,
            "retries": 15,
            "ignoreerrors": True,
            "force_generic_extractor": True,
            "format": "worst/best",
            "http_headers": {
                "User-Agent": "curl/7.68.0"
            }
        }
        
        info = await self._execute_extraction(url, ydl_opts)
        return self._build_response(info, False)

    def _get_base_options(self, quality: str = "best") -> Dict[str, Any]:
        """Get base yt-dlp options"""
        return {
            "format": QUALITY_FORMATS.get(quality, "bestvideo+bestaudio/best"),
            "outtmpl": str(settings.TEMP_DIR / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {
                "youtube": {
                    "skip": ["hls", "dash"],
                    "player_client": ["android", "web"],
                }
            },
            "http_headers": self.get_platform_headers(),
            "socket_timeout": settings.REQUEST_TIMEOUT,
            "retries": 3,
            "fragment_retries": 3,
        }

    async def _execute_extraction(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual extraction with rate limiting"""
        # Rate limiting
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
            
            if not info:
                raise SnapTubeError("No video information found")
                
            if not self._get_best_video_url(info):
                raise SnapTubeError("No valid video URL found")
                
            return info
            
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Sign in to confirm you're not a bot" in error_msg:
                raise SnapTubeError(
                    "YouTube requires valid cookies. Please use cookies for authentication."
                )
            raise SnapTubeError(f"YouTube error: {error_msg}")
        except Exception as e:
            raise SnapTubeError(f"Extraction error: {str(e)}")

    def _save_temp_cookies(self, cookies: str) -> str:
        """Save cookies to temporary file"""
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cookies)
        return path

    def _get_best_video_url(self, info: Dict) -> Optional[str]:
        """Get the best available video URL"""
        if info.get("url"):
            return info["url"]

        if "formats" in info:
            # Sort formats by quality (height + bitrate)
            formats = sorted(
                info["formats"],
                key=lambda x: (
                    x.get("height", 0) or 0,
                    x.get("tbr", 0) or 0,
                    x.get("vcodec") != "none",
                    x.get("acodec") != "none"
                ),
                reverse=True,
            )
            
            # Find first playable format
            for f in formats:
                if f.get("url") and f.get("protocol") in ("http", "https"):
                    return f["url"]

        return None

    def _build_response(self, info: Dict, cookies_used: bool) -> Dict[str, Any]:
        """Build standardized response"""
        video_url = self._get_best_video_url(info)
        best_format = self._get_best_format(info.get("formats", []))
        
        return {
            "status": "success",
            "platform": "youtube",
            "title": info.get("title", ""),
            "description": info.get("description", "")[:500],
            "thumbnail": self._get_best_thumbnail(info),
            "duration": info.get("duration", 0),
            "video_url": video_url,
            "uploader": info.get("uploader", ""),
            "view_count": info.get("view_count", 0),
            "like_count": info.get("like_count", 0),
            "upload_date": info.get("upload_date", ""),
            "method": "ytdlp_with_cookies" if cookies_used else "ytdlp",
            "quality": {
                "resolution": f"{best_format.get('width', '?')}x{best_format.get('height', '?')}",
                "fps": best_format.get("fps"),
                "bitrate": int(round(best_format.get("tbr", 0))) if best_format.get("tbr") else 0,
                "format": best_format.get("ext", "mp4"),
            },
            "formats": self._get_available_formats(info.get("formats", []))
        }

    def _get_best_format(self, formats: List[Dict]) -> Dict:
        """Get the best quality format"""
        if not formats:
            return {}
            
        return max(
            formats,
            key=lambda x: (
                x.get("height", 0) or 0,
                x.get("tbr", 0) or 0
            )
        )

    def _get_best_thumbnail(self, info: Dict) -> str:
        """Get the highest quality thumbnail available"""
        for quality in ["maxresdefault", "hqdefault", "mqdefault", "sddefault"]:
            thumb_url = info.get("thumbnail", "").replace("default", quality)
            if thumb_url != info.get("thumbnail"):
                return thumb_url
        return info.get("thumbnail", "")

    def _get_available_formats(self, formats: List[Dict]) -> List[Dict]:
        """Get available formats information"""
        simplified_formats = []
        for fmt in formats[:10]:  # Limit to 10 formats
            if fmt.get("url"):
                simplified_formats.append({
                    "format_id": fmt.get("format_id", ""),
                    "url": fmt.get("url", ""),
                    "ext": fmt.get("ext", ""),
                    "resolution": f"{fmt.get('width', '?')}x{fmt.get('height', '?')}",
                    "fps": fmt.get("fps"),
                    "filesize": fmt.get("filesize"),
                    "vcodec": fmt.get("vcodec", ""),
                    "acodec": fmt.get("acodec", "")
                })
        return simplified_formats

    async def extract_audio_url(self, url: str, cookies: str = None) -> str:
        """Extract direct audio URL"""
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "http_headers": self.get_platform_headers(),
        }

        if cookies:
            cookies_path = self._save_temp_cookies(cookies)
            ydl_opts["cookiefile"] = cookies_path
        elif self._cookies_file:
            ydl_opts["cookiefile"] = self._cookies_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )

            # Find best audio format
            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none" and f.get("url")
            ]
            
            if not audio_formats:
                raise SnapTubeError("No audio formats found")

            # Sort by audio bitrate
            audio_formats.sort(
                key=lambda f: (f.get("asr", 0) or 0, f.get("abr", 0) or 0),
                reverse=True
            )
            
            return audio_formats[0]["url"]
            
        except Exception as e:
            raise SnapTubeError(f"Audio extraction failed: {str(e)}")
            
        finally:
            if cookies and "cookies_path" in locals():
                os.unlink(cookies_path)