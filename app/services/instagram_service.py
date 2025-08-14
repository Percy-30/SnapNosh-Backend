# ====================================================================
# app/services/instagram_service.py - FIXED VERSION
# ====================================================================
import asyncio
import logging
import os
import re
import sys
import json
import tempfile
import random
import subprocess
from typing import Dict, Any, Optional, List, Tuple

import yt_dlp
import requests
from bs4 import BeautifulSoup

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import USER_AGENTS
from app.config import settings

logger = logging.getLogger(__name__)

# Compatibilidad Windows para to_thread/loop
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


# =========================
# Headers mejorados
# =========================
DESKTOP_HEADERS = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


class InstagramExtractor(BaseExtractor):
    """
    Extractor para Instagram optimizado para Render con estrategia:
      1) yt-dlp (prioritario - más confiable en Render)
      2) Scraping desktop (fallback)
      3) Scraping móvil (último recurso)
    """

    SUPPORTED_DOMAINS = ["instagram.com", "www.instagram.com", "instagr.am", "m.instagram.com"]

    @property
    def platform(self) -> str:
        return "instagram"

    # ---------------------------
    # Helpers comunes
    # ---------------------------
    def get_platform_headers(self, mobile: bool = False) -> Dict[str, str]:
        h = MOBILE_HEADERS.copy() if mobile else DESKTOP_HEADERS.copy()
        # Refrescar User-Agent aleatorio para evitar rate-limit
        if not mobile:
            h["User-Agent"] = random.choice(USER_AGENTS)
        return h

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(round(float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_url(self, url: str) -> str:
        """Normaliza URL para evitar problemas de DNS en Render"""
        # Siempre usar www.instagram.com para mejor compatibilidad
        url = url.replace("m.instagram.com", "www.instagram.com")
        url = url.replace("instagr.am", "www.instagram.com")
        if "instagram.com" in url and not url.startswith("https://www."):
            url = url.replace("https://instagram.com", "https://www.instagram.com")
        # Limpiar parámetros UTM problemáticos
        if "?" in url:
            base_url = url.split("?")[0]
            return base_url
        return url

    # ---------------------------
    # API pública - REORDENADA
    # ---------------------------
    async def extract(
        self,
        url: str,
        mobile: bool = False,
        cookies: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extrae info de un reel/post IG:
        NUEVA ESTRATEGIA para Render:
        1) yt-dlp (más confiable en entornos cloud)
        2) Scraping desktop (fallback)
        3) Scraping móvil (último recurso)
        """
        self.validator.validate_url(url)
        self._cookies = cookies
        
        # Normalizar URL para evitar problemas de DNS
        normalized_url = self._normalize_url(url)
        logger.info(f"🎬 Extracting Instagram content from: {normalized_url}")

        # NUEVA ESTRATEGIA: yt-dlp primero (más estable en Render)
        methods = [
            ("yt-dlp", lambda: self._extract_ytdlp(normalized_url, mobile=False)),
            ("manual_desktop", lambda: self._extract_manual(normalized_url, mobile=False)),
            ("manual_mobile", lambda: self._extract_manual(self._to_mobile_url(normalized_url), mobile=True)),
        ]

        last_error = None
        for method_name, method_func in methods:
            try:
                logger.info(f"🔍 Trying method: {method_name}")
                result = await method_func()
                if result and result.get("video_url"):
                    logger.info(f"✅ Instagram extraction successful with method: {method_name}")
                    return result
                else:
                    logger.warning(f"❌ Method {method_name} returned no video_url")
            except Exception as e:
                last_error = e
                logger.warning(f"❌ Method {method_name} failed: {str(e)}")

        raise SnapTubeError(f"Todos los métodos fallaron en Instagram. Último error: {last_error}")

    # ---------------------------
    # Método 1: yt-dlp (PRIORITARIO)
    # ---------------------------
    def _get_ydl_opts(self, audio_only: bool = False, mobile: bool = False) -> Dict[str, Any]:
        """Opciones optimizadas de yt-dlp para Render"""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best" if audio_only else "best[height<=720]/best",
            "http_headers": self.get_platform_headers(mobile=mobile),
            "socket_timeout": 30,  # Aumentado para Render
            "retries": 5,  # Más reintentos
            "retry_sleep_functions": {"http": lambda n: min(4 ** n, 60)},  # Backoff exponencial
            "extract_flat": False,
            "force_generic_extractor": False,
            "prefer_insecure": False,
            "nocheckcertificate": False,
            # Específico para Instagram
            "extractor_args": {
                "instagram": {
                    "api_version": "v1",
                }
            },
        }
        
        # Cookies si están disponibles
        if getattr(self, "_cookies", None):
            opts["_cookies_inline_text"] = self._cookies
            
        return opts

    async def _extract_ytdlp(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """yt-dlp extraction optimizado para Render"""
        temp_cookie_path = None
        try:
            ydl_opts = self._get_ydl_opts(audio_only=False, mobile=mobile)

            # Manejar cookies
            if ydl_opts.pop("_cookies_inline_text", None):
                fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt", prefix="ig_cookies_")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(self._cookies or "")
                    ydl_opts["cookiefile"] = temp_cookie_path
                except Exception as e:
                    logger.warning(f"Error writing cookies file: {e}")

            def _extract_with_ytdlp():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        logger.info("🔄 Running yt-dlp extraction...")
                        info = ydl.extract_info(url, download=False, process=True)
                        return info
                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ["rate", "limit", "too many", "429"]):
                        logger.warning("⚠️ Rate limit detected, implementing delay...")
                        import time
                        time.sleep(random.uniform(2, 5))
                    raise
                except Exception as e:
                    logger.error(f"yt-dlp extraction error: {e}")
                    raise

            info = await asyncio.to_thread(_extract_with_ytdlp)
            
            if not info:
                logger.warning("yt-dlp returned no info")
                return None

            media_url = self._get_best_media_url(info)
            if not media_url:
                logger.warning("No valid media URL found in yt-dlp result")
                return None

            result = self._build_ydlp_response(info, media_url, method="yt-dlp")
            logger.info("✅ yt-dlp extraction completed successfully")
            return result

        except Exception as e:
            logger.error(f"yt-dlp extraction failed: {str(e)}")
            raise
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.unlink(temp_cookie_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp cookie file: {e}")

    # ---------------------------
    # Método 2 y 3: Scraping (FALLBACK)
    # ---------------------------
    async def _extract_manual(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Scraping mejorado con mejor manejo de errores para Render"""
        headers = self.get_platform_headers(mobile)
        
        # Session con configuración robusta
        session = requests.Session()
        session.headers.update(headers)
        
        # Configurar adapters con retry strategy
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Cookies si están disponibles
        if getattr(self, "_cookies", None):
            session.headers.update({"Cookie": self._cookies})

        try:
            logger.info(f"🌐 Attempting manual extraction from: {url}")
            resp = session.get(
                url, 
                timeout=(10, 30),  # (connect, read) timeout
                allow_redirects=True,
                verify=True
            )
            resp.raise_for_status()
            
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error for {url}: {str(e)}")
            return None
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout error for {url}: {str(e)}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error for {url}: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error for {url}: {str(e)}")
            return None

        try:
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1) LD+JSON primero (más confiable)
            meta = self._extract_from_ld_json(soup)
            if meta.get("video_url"):
                return self._build_manual_response(meta, method="manual_ld_json")

            # 2) OG tags (fallback rápido)
            meta_og = self._extract_from_og(soup)
            if meta_og.get("video_url"):
                return self._build_manual_response(meta_og, method="manual_og")

            # 3) Script parsing (más complejo)
            meta_scripts = self._extract_from_scripts(soup)
            if meta_scripts.get("video_url"):
                self._merge_meta_with_og(meta_scripts, soup)
                return self._build_manual_response(meta_scripts, method="manual_scripts")

            logger.warning("Manual extraction found no video URL")
            return None

        except Exception as e:
            logger.error(f"Error parsing response from {url}: {str(e)}")
            return None

    # ... (resto de métodos helper sin cambios significativos)

    def _extract_from_ld_json(self, soup: BeautifulSoup) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string
                if not raw:
                    continue
                data = json.loads(raw)
                candidates = data if isinstance(data, list) else [data]
                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") == "VideoObject":
                        out["video_url"] = item.get("contentUrl")
                        out["thumbnail"] = (item.get("thumbnailUrl")[0]
                                            if isinstance(item.get("thumbnailUrl"), list)
                                            else item.get("thumbnailUrl"))
                        out["title"] = item.get("name") or item.get("headline")
                        out["description"] = item.get("description")
                        out["upload_date"] = item.get("uploadDate")
                        iso_dur = item.get("duration")
                        if iso_dur:
                            out["duration"] = self._parse_iso8601_duration(iso_dur)
                        break
            except Exception:
                continue
        return out

    def _extract_from_scripts(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Busca patrones en scripts con mejor error handling"""
        out: Dict[str, Any] = {}

        patterns = [
            r'"video_url"\s*:\s*"([^"]+)"',
            r'"play_url"\s*:\s*"([^"]+)"',
            r'"video_versions"\s*:\s*\[\s*\{[^}]*"url"\s*:\s*"([^"]+)"',
        ]

        for script in soup.find_all("script"):
            try:
                txt = script.string or ""
                if not txt or len(txt) < 50:  # Skip very small scripts
                    continue

                # Patrones directos
                for p in patterns:
                    m = re.search(p, txt)
                    if m:
                        url = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
                        if url.startswith("http"):
                            out["video_url"] = url
                            break

                if out.get("video_url"):
                    # Extraer metadatos adicionales
                    self._extract_metadata_from_script(txt, out)
                    break

                # Buscar shortcode_media con mejor parsing
                if "shortcode_media" in txt and not out.get("video_url"):
                    sm = self._extract_json_object(txt, key_name="shortcode_media")
                    if sm and isinstance(sm, dict):
                        self._extract_metadata_from_shortcode(sm, out)
                        if out.get("video_url"):
                            break

            except Exception as e:
                logger.debug(f"Error processing script: {str(e)}")
                continue

        return out

    def _extract_metadata_from_script(self, txt: str, out: Dict[str, Any]) -> None:
        """Helper para extraer metadatos de script"""
        try:
            # Thumbnail
            thumb_match = re.search(r'"display_url"\s*:\s*"([^"]+)"', txt)
            if thumb_match:
                out["thumbnail"] = thumb_match.group(1).replace("\\/", "/")
            
            # Title
            title_match = re.search(r'"title"\s*:\s*"([^"]+)"', txt)
            if title_match:
                out["title"] = title_match.group(1)
        except Exception:
            pass

    def _extract_metadata_from_shortcode(self, sm: Dict[str, Any], out: Dict[str, Any]) -> None:
        """Helper para extraer metadatos de shortcode_media"""
        try:
            if sm.get("is_video") and sm.get("video_url"):
                out["video_url"] = sm.get("video_url")
            
            if not out.get("thumbnail"):
                out["thumbnail"] = sm.get("display_url")
            
            # Dimensiones
            dims = sm.get("dimensions") or {}
            out["width"] = self._safe_int(dims.get("width"))
            out["height"] = self._safe_int(dims.get("height"))
            
            # Uploader
            owner = sm.get("owner") or {}
            out["uploader"] = owner.get("username") or ""
            
            # Caption
            try:
                edges = sm.get("edge_media_to_caption", {}).get("edges", [])
                if edges and edges[0] and edges[0].get("node", {}).get("text"):
                    out["description"] = edges[0]["node"]["text"]
            except Exception:
                pass
            
            # Counts
            out["view_count"] = self._safe_int(sm.get("video_view_count"))
            likes = (sm.get("edge_media_preview_like") or sm.get("edge_liked_by") or {})
            out["like_count"] = self._safe_int(likes.get("count"))
            comments = sm.get("edge_media_to_parent_comment") or sm.get("edge_media_to_comment") or {}
            out["comment_count"] = self._safe_int(comments.get("count"))
            
            # Duración
            out["duration"] = self._safe_int(sm.get("video_duration"))
        except Exception:
            pass

    def _extract_from_og(self, soup: BeautifulSoup) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        def _meta(prop: str) -> Optional[str]:
            tag = soup.find("meta", property=prop)
            return tag["content"] if tag and tag.get("content") else None

        video_url = _meta("og:video") or _meta("og:video:url") or _meta("og:video:secure_url")
        if video_url:
            out["video_url"] = video_url
        out["thumbnail"] = _meta("og:image") or _meta("og:image:secure_url") or ""
        out["title"] = _meta("og:title") or "Instagram Video"
        out["description"] = _meta("og:description") or ""
        out["width"] = self._safe_int(_meta("og:video:width"))
        out["height"] = self._safe_int(_meta("og:video:height"))
        out["duration"] = self._safe_int(_meta("og:video:duration"))
        return out

    def _merge_meta_with_og(self, meta: Dict[str, Any], soup: BeautifulSoup) -> None:
        """Completa campos ausentes con OG tags."""
        og = self._extract_from_og(soup)
        for k in ["title", "thumbnail", "description", "width", "height", "duration"]:
            if not meta.get(k) and og.get(k):
                meta[k] = og[k]

    @staticmethod
    def _parse_iso8601_duration(iso: str) -> int:
        """Convierte duraciones tipo PT40S o PT1M05S -> segundos."""
        try:
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
            if not m:
                return 0
            h = int(m.group(1) or 0)
            mi = int(m.group(2) or 0)
            s = int(m.group(3) or 0)
            return h * 3600 + mi * 60 + s
        except Exception:
            return 0

    @staticmethod
    def _extract_json_object(text: str, key_name: str) -> Optional[Dict[str, Any]]:
        """Extrae un objeto JSON de manera más robusta"""
        try:
            key_idx = text.find(f'"{key_name}"')
            if key_idx == -1:
                return None
            brace_idx = text.find("{", key_idx)
            if brace_idx == -1:
                return None
            
            depth = 0
            for i in range(brace_idx, min(len(text), brace_idx + 50000)):  # Límite de seguridad
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        blob = text[brace_idx:i + 1]
                        blob = blob.replace("\\u0026", "&").replace("\\/", "/")
                        return json.loads(blob)
            return None
        except Exception:
            return None

    def _build_manual_response(self, meta: Dict[str, Any], method: str) -> Dict[str, Any]:
        duration = self._safe_int(meta.get("duration"))
        width = self._safe_int(meta.get("width"))
        height = self._safe_int(meta.get("height"))
        title = str(meta.get("title") or "Instagram Video")
        description = str(meta.get("description") or "")
        thumbnail = str(meta.get("thumbnail") or "")
        uploader = str(meta.get("uploader") or "")
        view_count = self._safe_int(meta.get("view_count"))
        like_count = self._safe_int(meta.get("like_count"))
        comment_count = self._safe_int(meta.get("comment_count"))
        upload_date = str(meta.get("upload_date") or "")

        return {
            "status": "success",
            "platform": self.platform,
            "title": title,
            "description": description,
            "thumbnail": thumbnail,
            "duration": duration,
            "video_url": str(meta.get("video_url") or ""),
            "width": width if width > 0 else None,
            "height": height if height > 0 else None,
            "uploader": uploader,
            "uploader_id": "",
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "upload_date": upload_date,
            "method": method,
            "quality": {
                "resolution": (f"{width}x{height}" if width and height else ""),
                "fps": 0,
                "bitrate": 0,
                "format": "mp4",
            },
        }

    def _to_mobile_url(self, url: str) -> str:
        # Evitar m.m.instagram.com que causa problemas de DNS
        return url.replace("www.instagram.com", "m.instagram.com")

    def _get_best_media_url(self, info: Dict[str, Any], audio_only: bool = False) -> Optional[str]:
        try:
            formats: List[Dict[str, Any]] = info.get("formats", [])
            valid = [
                f for f in formats
                if f.get("url")
                and f.get("protocol") in ("http", "https", "m3u8", "m3u8_native")
                and ((f.get("acodec") != "none" and f.get("vcodec") == "none") if audio_only
                     else (f.get("vcodec") != "none"))
            ]
            if not valid:
                if not audio_only and info.get("url"):
                    return info["url"]
                return None

            def _key(f):
                w = self._safe_int(f.get("width"))
                h = self._safe_int(f.get("height"))
                tbr = self._safe_float(f.get("tbr") or f.get("abr") or 0.0)
                fps = self._safe_float(f.get("fps") or 0.0)
                return (w * h, tbr, fps)

            valid.sort(key=_key, reverse=True)
            return valid[0]["url"]
        except Exception as e:
            logger.warning(f"Error selecting format: {str(e)}")
            return None

    def _build_ydlp_response(self, info: Dict[str, Any], media_url: str, method: str) -> Dict[str, Any]:
        best_format = next((f for f in info.get("formats", []) if f.get("url") == media_url), {})
        width = self._safe_int(best_format.get("width"))
        height = self._safe_int(best_format.get("height"))

        return {
            "status": "success",
            "platform": self.platform,
            "title": str(info.get("title", "Instagram Video")),
            "description": str(info.get("description", "")),
            "thumbnail": str(info.get("thumbnail", "")),
            "duration": self._safe_int(info.get("duration")),
            "video_url": str(media_url),
            "width": width if width > 0 else None,
            "height": height if height > 0 else None,
            "uploader": str(info.get("uploader", "")),
            "uploader_id": str(info.get("uploader_id", "")),
            "view_count": self._safe_int(info.get("view_count")),
            "like_count": self._safe_int(info.get("like_count")),
            "comment_count": self._safe_int(info.get("comment_count")),
            "upload_date": str(info.get("upload_date", "")),
            "method": method,
            "quality": {
                "resolution": f"{width}x{height}" if width and height else "",
                "fps": int(round(self._safe_float(best_format.get("fps")))) if best_format else 0,
                "bitrate": self._safe_int(best_format.get("tbr")),
                "format": str(best_format.get("ext", "mp4")) if best_format else "mp4",
            },
        }

    # ---------------------------
    # Audio extraction
    # ---------------------------
    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """Audio extraction optimizado"""
        temp_cookie_path = None
        try:
            self._cookies = cookies or self._cookies
            normalized_url = self._normalize_url(url)
            ydl_opts = self._get_ydl_opts(audio_only=True, mobile=False)
            
            if ydl_opts.pop("_cookies_inline_text", None):
                fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt", prefix="ig_audio_cookies_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self._cookies or "")
                ydl_opts["cookiefile"] = temp_cookie_path

            def _do():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(normalized_url, download=False, process=True)

            info = await asyncio.to_thread(_do)

            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("url") and f.get("acodec") != "none" and f.get("vcodec") == "none"
            ]
            if not audio_formats:
                raise SnapTubeError("No audio streams found")

            audio_formats.sort(
                key=lambda f: float(f.get("abr") or f.get("tbr") or 0.0),
                reverse=True
            )
            best = audio_formats[0]
            best_url = best["url"]

            return {
                "status": "success",
                "audio_url": best_url,
                "note": "Stream directo. Si es HLS (.m3u8), considera usar ffmpeg para conversión." if best_url.endswith(".m3u8") else "",
                "metadata": {
                    "bitrate": self._safe_int(best.get("abr") or best.get("tbr")),
                    "codec": "aac" if best_url.endswith(".m3u8") else "mp4a",
                    "duration": self._safe_int(info.get("duration")),
                    "quality": "best",
                },
            }
        except yt_dlp.utils.DownloadError as e:
            raise SnapTubeError(f"Instagram audio error: {str(e)}")
        except Exception as e:
            logger.error(f"Error extracting Instagram audio: {str(e)}", exc_info=True)
            raise SnapTubeError("Failed to extract Instagram audio")
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.unlink(temp_cookie_path)
                except Exception:
                    pass