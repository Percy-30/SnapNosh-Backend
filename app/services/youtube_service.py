# app/services/youtube_service.py
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlunparse

from app.utils.proxy import ProxyRotator
from app.services.cookie_manager import CookieManager

import yt_dlp

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import YOUTUBE_HEADERS, QUALITY_FORMATS, USER_AGENTS
from app.config import settings

logger = logging.getLogger(__name__)

class YouTubeExtractor(BaseExtractor):
    """Extractor de YouTube con cookies automáticas y fallback multi-cliente"""

    def __init__(self, cookies_file: Optional[str] = None):
        # Si se pasa cookies_file lo usamos; si no, se intenta obtener de CookieManager
        self._cookies_file = cookies_file or CookieManager.get_cookies_path()
        super().__init__()
        self.cookie_manager = CookieManager()
        proxy_list = settings.PROXY_LIST.split(",") if settings.USE_PROXIES else []
        self.proxy_rotator = ProxyRotator(proxy_list)

    @property
    def platform(self) -> str:
        return "youtube"

    def get_platform_headers(self) -> Dict[str, str]:
        return YOUTUBE_HEADERS

    def _ensure_cookies_file(self) -> str:
        """Asegura que haya cookies válidas; si no, intenta exportarlas desde navegador"""
        if self._cookies_file and CookieManager.validate_cookies_file(Path(self._cookies_file)):
            return self._cookies_file

        # Intentar exportar cookies desde navegador
        exported = CookieManager.export_browser_cookies("chrome") or CookieManager.export_browser_cookies("edge")
        if exported:
            self._cookies_file = exported
            return self._cookies_file

        raise SnapTubeError(
            "No se encontró archivo de cookies válido en 'app/cookies/cookies.txt'. "
            "Debes subir cookies.txt generado desde un navegador real."
        )

    def _clean_url(self, url: str) -> str:
        """Elimina parámetros innecesarios de YouTube"""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        clean_query = {}
        if "v" in query:
            clean_query["v"] = query["v"]
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        if clean_query:
            clean_url += f"?v={clean_query['v'][0]}"
        return clean_url

    async def extract(
        self,
        url: str,
        cookies: Optional[str] = None,
        force_ytdlp: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        self.validator.validate_url(url)
        url = self._clean_url(url)
        cookies_file_path = self._ensure_cookies_file()

        ydl_opts = {
            "format": QUALITY_FORMATS.get("1080p", "bestvideo+bestaudio/best"),
            "outtmpl": str(settings.TEMP_DIR / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {"youtube": {"skip": ["hls", "dash"], "player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": self.get_random_user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
            },
            "socket_timeout": settings.REQUEST_TIMEOUT,
        }

        cookies_path = None
        proxy = None

        try:
            if cookies:
                cookies_path = self._save_temp_cookies(cookies)
                ydl_opts["cookiefile"] = cookies_path
            elif cookies_file_path:
                ydl_opts["cookiefile"] = cookies_file_path

            if settings.USE_PROXIES:
                proxy = self.proxy_rotator.get_yt_dlp_proxy_option()
                if proxy:
                    ydl_opts["proxy"] = proxy
                    logger.info(f"Usando proxy: {proxy}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )

            if not info:
                raise SnapTubeError("No se pudo extraer información del video")

            video_url = self._get_best_video_url(info)
            if not video_url:
                if force_ytdlp:
                    return await self._force_extract(url, ydl_opts)
                raise SnapTubeError("No se encontró un URL válido del video")

            return self._build_response(info, bool(cookies_path or cookies_file_path))

        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if settings.USE_PROXIES and proxy and ("could not connect" in msg.lower() or "proxy" in msg.lower()):
                self.proxy_rotator.mark_proxy_failed(proxy)
            if "Sign in to confirm you're not a bot" in msg:
                raise SnapTubeError("YouTube requiere cookies válidas. Usa la extensión 'Get cookies.txt'.")
            raise SnapTubeError(f"Error de YouTube: {msg}")

        except Exception as e:
            logger.error(f"Error general en extracción de YouTube: {e}", exc_info=True)
            raise SnapTubeError(f"Error interno: {e}")

        finally:
            if cookies_path and os.path.exists(cookies_path):
                os.unlink(cookies_path)

    def _save_temp_cookies(self, cookies: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cookies)
        return path

    async def _force_extract(self, url: str, base_opts: dict) -> Dict[str, Any]:
        clients = [
            {"player_client": ["android"], "format": "best[height<=720]"},
            {"player_client": ["tv_embedded"], "format": "best[height<=480]"},
            {"player_client": ["web"], "format": "best[height<=360]"},
        ]

        for client in clients:
            try:
                opts = base_opts.copy()
                opts["extractor_args"] = opts.get("extractor_args", {}).copy()
                opts["extractor_args"]["youtube"] = opts["extractor_args"].get("youtube", {}).copy()
                opts["extractor_args"]["youtube"]["player_client"] = client["player_client"]
                opts["format"] = client["format"]

                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )

                if info and self._get_best_video_url(info):
                    return self._build_response(info, bool(base_opts.get("cookiefile")))

            except Exception:
                continue

        raise SnapTubeError("YouTube bloqueó la extracción. Requiere cookies válidas.")

    def _get_best_video_url(self, info: Dict) -> Optional[str]:
        if info.get("url"):
            return info["url"]

        if "formats" in info:
            formats = sorted(
                info["formats"],
                key=lambda x: (x.get("height", 0) or 0, x.get("tbr", 0) or 0),
                reverse=True,
            )
            for f in formats:
                if f.get("url") and f.get("protocol") in ("http", "https"):
                    return f["url"]

        return None

    def _build_response(self, info: Dict, cookies_used: bool) -> Dict[str, Any]:
        bitrate = info.get("tbr")
        if bitrate is not None:
            bitrate = int(round(bitrate))
        else:
            bitrate = 0
        return {
            "status": "success",
            "platform": "youtube",
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "video_url": self._get_best_video_url(info),
            "uploader": info.get("uploader", ""),
            "view_count": info.get("view_count", 0),
            "like_count": info.get("like_count", 0),
            "method": "ytdlp_with_cookies" if cookies_used else "ytdlp",
            "quality": {
                "resolution": f"{info.get('width', 'unknown')}x{info.get('height', 'unknown')}",
                "fps": info.get("fps"),
                "bitrate": bitrate,
                "format": info.get("ext", "mp4"),
            },
        }

    def extract_audio_url(self, url: str, cookies: str = None) -> str:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": None,
            "http_headers": self.get_platform_headers(),
        }

        if cookies:
            cookies_path = self._save_temp_cookies(cookies)
            ydl_opts["cookiefile"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        audio_formats = [
            f for f in info.get("formats", [])
            if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("url")
        ]
        if audio_formats:
            audio_formats.sort(key=lambda f: f.get("abr") or 0, reverse=True)
            return audio_formats[0]["url"]

        if info.get("url") and info.get("acodec") != "none" and info.get("vcodec") == "none":
            return info["url"]

        raise Exception("No se encontró URL directa de audio")
