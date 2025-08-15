# ====================================================================
# app/services/facebook_service.py
# ====================================================================
import asyncio
import logging
import os
import re
import json
import tempfile
from typing import Dict, Any, Optional

import yt_dlp
import requests
from bs4 import BeautifulSoup

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.config import settings

logger = logging.getLogger(__name__)

# Headers predefinidos
FACEBOOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

FACEBOOK_MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/89.0.4389.72 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}


class FacebookExtractor(BaseExtractor):
    """Extractor de videos de Facebook actualizado y funcional."""

    @property
    def platform(self) -> str:
        return "facebook"

    def get_platform_headers(self, mobile: bool = False) -> Dict[str, str]:
        return FACEBOOK_MOBILE_HEADERS if mobile else FACEBOOK_HEADERS

    async def extract(
        self, url: str, mobile: bool = False, cookies: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Extrae video completo de Facebook con fallback manual y soporte de cookies."""
        self.validator.validate_url(url)
        self._cookies = cookies

        # Métodos de extracción en orden
        methods = [
            self._extract_ytdlp,
            self._extract_manual,
            self._extract_mobile_redirect
        ]

        last_error = None
        for method in methods:
            try:
                logger.info(f"Intentando {method.__name__} para Facebook")
                result = await method(url, mobile)
                if result and result.get("video_url"):
                    logger.info(f"✅ Extracción exitosa con {method.__name__}")
                    return result
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {method.__name__} falló: {str(e)}")
                continue

        raise SnapTubeError(f"Todos los métodos fallaron. Último error: {last_error}")

    async def _extract_ytdlp(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Extrae usando yt-dlp, admite cookies opcionales."""
        try:
            headers = self.get_platform_headers(mobile)
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "forceurl": True,
                "simulate": True,
                "format": "best",
                "http_headers": headers,
                "extractor_args": {"facebook": {"skip_dash_manifest": True}},
                "socket_timeout": settings.REQUEST_TIMEOUT,
            }

            temp_cookie_path = None
            if getattr(self, "_cookies", None):
                fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self._cookies)
                ydl_opts["cookiefile"] = temp_cookie_path

            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

            if not info:
                return None

            video_url = info.get("url")
            if not video_url and "formats" in info:
                for f in info["formats"]:
                    if f.get("protocol") in ("http", "https") and f.get("url"):
                        video_url = f["url"]
                        break
            if not video_url:
                return None

            return self._build_response(info, method="ytdlp")

        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                os.unlink(temp_cookie_path)

    async def _extract_manual(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Fallback manual usando scraping de Facebook."""
        try:
            headers = self.get_platform_headers(mobile)
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            video_url = (
                self._extract_from_meta_tags(soup)
                or self._extract_from_json_ld(soup)
                or self._extract_from_scripts(soup)
                or self._extract_from_video_tags(soup)
            )
            if not video_url:
                return None

            title = self._get_title(soup)
            thumbnail = self._get_thumbnail(soup)

            return {
                "status": "success",
                "platform": "facebook",
                "title": title,
                "thumbnail": thumbnail,
                "video_url": video_url,
                "duration": 0,
                "width": None,
                "height": None,
                "method": "manual_extraction"
            }

        except Exception as e:
            logger.warning(f"Scraping manual falló para Facebook: {str(e)}")
            return None

    async def _extract_mobile_redirect(self, url: str, mobile: bool = True) -> Optional[Dict[str, Any]]:
        """Intento usando la versión móvil para mejor compatibilidad."""
        mobile_url = url.replace("www.facebook.com", "m.facebook.com")
        return await self._extract_manual(mobile_url, mobile=True)

    # ---------------- Métodos internos ----------------
    def _extract_from_meta_tags(self, soup) -> Optional[str]:
        meta_video = (soup.find("meta", property="og:video")
                      or soup.find("meta", property="og:video:url")
                      or soup.find("meta", property="og:video:secure_url"))
        if meta_video and meta_video.get("content"):
            return meta_video["content"]
        return None

    def _extract_from_json_ld(self, soup) -> Optional[str]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    return data.get("contentUrl")
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("contentUrl"):
                            return item["contentUrl"]
            except json.JSONDecodeError:
                continue
        return None

    def _extract_from_scripts(self, soup) -> Optional[str]:
        patterns = [
            r'"browser_native_hd_url":"([^"]+)"',
            r'"browser_native_sd_url":"([^"]+)"',
            r'src:\\"([^"]+\.mp4[^\\]*)\\"',
            r'video_src":"([^"]+)"',
            r'"playable_url":"([^"]+)"',
            r'"playable_url_quality_hd":"([^"]+)"'
        ]
        for script in soup.find_all("script"):
            if not script.string:
                continue
            for pattern in patterns:
                matches = re.findall(pattern, script.string)
                if matches:
                    return matches[0].replace("\\/", "/")
        return None

    def _extract_from_video_tags(self, soup) -> Optional[str]:
        video_tag = soup.find("video")
        if video_tag:
            if video_tag.get("src"):
                return video_tag["src"]
            for source in video_tag.find_all("source"):
                if source.get("src"):
                    return source["src"]
        return None

    def _get_title(self, soup) -> str:
        title_tag = soup.find("meta", property="og:title") or soup.find("title")
        if title_tag:
            if hasattr(title_tag, "content"):
                return title_tag["content"]
            return title_tag.text.strip()
        return "Facebook Video"

    def _get_thumbnail(self, soup) -> str:
        thumb_tag = soup.find("meta", property="og:image")
        return thumb_tag["content"] if thumb_tag else ""

    def _build_response(self, info: Dict[str, Any], method: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "platform": "facebook",
            "title": info.get("title", "Facebook Video"),
            "description": info.get("description", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": round(info.get("duration", 0)),
            "video_url": info.get("url"),
            "width": info.get("width"),
            "height": info.get("height"),
            "uploader": info.get("uploader", ""),
            "view_count": info.get("view_count", 0),
            "method": method
        }

    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> str:
        """Extrae la URL de audio de un video de Facebook usando yt-dlp."""
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "http_headers": self.get_platform_headers(),
        }

        temp_cookie_path = None
        if cookies:
            fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(cookies)
            ydl_opts["cookiefile"] = temp_cookie_path

        loop = asyncio.get_event_loop()
        try:
            def extract_sync():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await loop.run_in_executor(None, extract_sync)

            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("url")
            ]
            if audio_formats:
                audio_formats.sort(key=lambda f: f.get("abr") or 0, reverse=True)
                return audio_formats[0]["url"]

            if info.get("url") and info.get("acodec") != "none" and info.get("vcodec") == "none":
                return info["url"]

            raise SnapTubeError("No se encontró URL directa de audio en Facebook")
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                os.unlink(temp_cookie_path)
                
    async def extract_audio_url_with_fallback(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """
        Extrae audio de Facebook con fallback seguro.
        Siempre devuelve un dict plano con:
        {
            "audio_url": str,
            "title": str,
            "thumbnail": str,
            "duration": int
        }
        """
        try:
            # Intentar extraer solo audio
            audio_url = await self.extract_audio_url(url, cookies=cookies)
            
            # Extraer info completa para title, thumbnail y duration
            info = await self.extract(url, cookies=cookies)
            
            result = {
                "audio_url": audio_url,
                "title": info.get("title") or "Facebook Video",
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration") or 0
            }

            logger.info(f"🎵 Facebook audio extraction result: {result}")
            return result

        except SnapTubeError as e:
            # Fallback absoluto: usar video como fuente de audio
            info = await self.extract(url, cookies=cookies)
            result = {
                "audio_url": info.get("video_url"),
                "title": info.get("title") or "Facebook Video",
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration") or 0
            }
            logger.warning(f"⚠️ Facebook audio fallback used: {result}")
            return result
