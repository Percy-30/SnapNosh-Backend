# ====================================================================
# app/services/instagram_service.py
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
# Headers
# =========================
DESKTOP_HEADERS = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
    "Origin": "https://www.instagram.com",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960U) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://m.instagram.com/",
    "Origin": "https://m.instagram.com",
}


class InstagramExtractor(BaseExtractor):
    """
    Extractor para Instagram con estrategia:
      1) Scraping (desktop)
      2) Scraping (móvil)
      3) Fallback yt-dlp (con cookies opcionales)
    Devuelve metadatos completos y URLs directas.
    """

    SUPPORTED_DOMAINS = ["instagram.com", "www.instagram.com", "instagr.am", "m.instagram.com"]

    @property
    def platform(self) -> str:
        return "instagram"

    # ---------------------------
    # Helpers comunes
    # ---------------------------
    def get_platform_headers(self, mobile: bool = False) -> Dict[str, str]:
        h = MOBILE_HEADERS if mobile else DESKTOP_HEADERS
        # Refrescar User-Agent aleatorio en desktop para evitar rate-limit
        if not mobile:
            h = {**h, "User-Agent": random.choice(USER_AGENTS)}
        return h

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            if value is None:
                return default
            # strings como "40" o floats 40.0 -> int
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

    # ---------------------------
    # API pública
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
        1) Scraping desktop
        2) Scraping móvil
        3) yt-dlp (con/ sin cookies)
        """
        self.validator.validate_url(url)
        self._cookies = cookies  # contenido de cookies (no ruta), opcional

        methods = [
            lambda: self._extract_manual(url, mobile=False),
            lambda: self._extract_manual(self._to_mobile_url(url), mobile=True),
            lambda: self._extract_ytdlp(url, mobile=True),
        ]

        last_error = None
        for step, method in enumerate(methods, start=1):
            try:
                if step == 3:
                    logger.info("Intentando yt-dlp para Instagram (fallback)")
                result = await method()
                if result and result.get("video_url"):
                    logger.info("✅ Extracción Instagram OK con método %s",
                                result.get("method", "desconocido"))
                    return result
            except Exception as e:
                last_error = e
                logger.warning("❌ Método %s falló: %s", step, str(e), exc_info=False)

        raise SnapTubeError(f"Todos los métodos fallaron en Instagram. Último error: {last_error}")

    # ---------------------------
    # Método 1 y 2: Scraping
    # ---------------------------
    async def _extract_manual(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """
        Scraping robusto:
          - meta og:*
          - application/ld+json (VideoObject)
          - scripts con "shortcode_media"/"video_url"/"video_versions"
          - intento JSON ?__a=1&__d=dis (si lo permite)
        """
        headers = self.get_platform_headers(mobile)
        session = requests.Session()

        # Si tenemos cookies en texto, úsalas (p.ej. "sessionid=...; ds_user_id=...;")
        if getattr(self, "_cookies", None):
            session.headers.update({"Cookie": self._cookies})

        try:
            resp = session.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("HTTP error en Instagram: %s", str(e))
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Intenta LD+JSON (VideoObject)
        meta = self._extract_from_ld_json(soup)
        if meta.get("video_url"):
            return self._build_manual_response(meta, method="manual_ld_json")

        # 2) Intenta directamente por patrones en <script>
        meta2 = self._extract_from_scripts(soup)
        if meta2.get("video_url"):
            # Completar metadatos básicos con OG tags si faltan
            self._merge_meta_with_og(meta2, soup)
            return self._build_manual_response(meta2, method="manual_scripts")

        # 3) Intenta OG tags directamente
        meta3 = self._extract_from_og(soup)
        if meta3.get("video_url"):
            return self._build_manual_response(meta3, method="manual_og")

        # 4) Último intento: endpoint JSON (?__a=1&__d=dis)
        try:
            json_url = self._normalize_to_canonical_json(url)
            rj = session.get(json_url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
            if rj.ok:
                data = rj.json()
                meta4 = self._extract_from_graphql_like(data)
                if meta4.get("video_url"):
                    # completar con OG si falta algo
                    self._merge_meta_with_og(meta4, soup)
                    return self._build_manual_response(meta4, method="manual_json")
        except Exception:
            pass

        return None

    def _extract_from_ld_json(self, soup: BeautifulSoup) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string
                if not raw:
                    continue
                data = json.loads(raw)
                # Puede venir como lista o dict
                candidates = data if isinstance(data, list) else [data]
                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    # VideoObject estándar
                    if item.get("@type") == "VideoObject":
                        out["video_url"] = item.get("contentUrl")
                        # Metadatos
                        out["thumbnail"] = (item.get("thumbnailUrl")[0]
                                            if isinstance(item.get("thumbnailUrl"), list)
                                            else item.get("thumbnailUrl"))
                        out["title"] = item.get("name") or item.get("headline")
                        out["description"] = item.get("description")
                        out["upload_date"] = item.get("uploadDate")
                        # Duración ISO 8601 (PT40S)
                        iso_dur = item.get("duration")
                        if iso_dur:
                            out["duration"] = self._parse_iso8601_duration(iso_dur)
                        break
            except Exception:
                continue
        return out

    def _extract_from_scripts(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Busca en scripts internos patrones comunes:
         - "video_url": "..."
         - "video_versions": [{"url": "..."}]
         - objetos con "shortcode_media"
        """
        out: Dict[str, Any] = {}

        # patrones simples
        patterns = [
            r'"video_url"\s*:\s*"([^"]+)"',
            r'"play_url"\s*:\s*"([^"]+)"',
            r'"video_versions"\s*:\s*\[\s*\{[^}]*"url"\s*:\s*"([^"]+)"',
        ]

        for script in soup.find_all("script"):
            txt = script.string or ""
            if not txt:
                continue

            # 1) patrones directos
            for p in patterns:
                m = re.search(p, txt)
                if m:
                    out["video_url"] = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
                    break
            if out.get("video_url"):
                # tratar de extraer thumbnail y título por si aparecen en el blob
                thumb = re.search(r'"display_url"\s*:\s*"([^"]+)"', txt)
                if thumb:
                    out["thumbnail"] = thumb.group(1).replace("\\/", "/")
                title = re.search(r'"title"\s*:\s*"([^"]+)"', txt)
                if title:
                    out["title"] = title.group(1)
                break

            # 2) buscar bloque "shortcode_media"
            if "shortcode_media" in txt:
                # intenta localizar un bloque JSON razonable del media
                sm = self._extract_json_object(txt, key_name="shortcode_media")
                if sm and isinstance(sm, dict):
                    if sm.get("is_video") and sm.get("video_url"):
                        out["video_url"] = sm.get("video_url")
                    if not out.get("thumbnail"):
                        out["thumbnail"] = sm.get("display_url")
                    # dimensiones
                    dims = sm.get("dimensions") or {}
                    out["width"] = self._safe_int(dims.get("width"))
                    out["height"] = self._safe_int(dims.get("height"))
                    # uploader
                    owner = sm.get("owner") or {}
                    out["uploader"] = owner.get("username") or ""
                    # caption
                    try:
                        edges = sm.get("edge_media_to_caption", {}).get("edges", [])
                        if edges and edges[0] and edges[0].get("node", {}).get("text"):
                            out["description"] = edges[0]["node"]["text"]
                    except Exception:
                        pass
                    # counts
                    out["view_count"] = self._safe_int(sm.get("video_view_count"))
                    likes = (sm.get("edge_media_preview_like") or sm.get("edge_liked_by") or {})
                    out["like_count"] = self._safe_int(likes.get("count"))
                    comments = sm.get("edge_media_to_parent_comment") or sm.get("edge_media_to_comment") or {}
                    out["comment_count"] = self._safe_int(comments.get("count"))
                    # fecha
                    ts = sm.get("taken_at_timestamp")
                    if ts:
                        # IG suele usar unix ts; lo dejamos como string y que el esquema de salida lo maneje si quiere
                        out["upload_date"] = ""
                    # duración (si disponible)
                    out["duration"] = self._safe_int(sm.get("video_duration"))

                    if out.get("video_url"):
                        break

        return out

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

    def _normalize_to_canonical_json(self, url: str) -> str:
        # Quita UTM y agrega parámetros de JSON "clásico"
        base = url.split("?")[0]
        return f"{base}?__a=1&__d=dis"

    def _merge_meta_with_og(self, meta: Dict[str, Any], soup: BeautifulSoup) -> None:
        """Completa campos ausentes con OG tags."""
        og = self._extract_from_og(soup)
        for k in ["title", "thumbnail", "description", "width", "height", "duration"]:
            if not meta.get(k) and og.get(k):
                meta[k] = og[k]

    @staticmethod
    def _parse_iso8601_duration(iso: str) -> int:
        """
        Convierte duraciones tipo PT40S o PT1M05S -> segundos.
        """
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
        """
        Extrae un objeto JSON cuyo nombre de clave aparezca en el texto.
        Busca algo como: "key_name": { ...obj... }
        Intenta hacer un balance de llaves simple.
        """
        try:
            key_idx = text.find(f'"{key_name}"')
            if key_idx == -1:
                return None
            brace_idx = text.find("{", key_idx)
            if brace_idx == -1:
                return None
            # balanceo sencillo de llaves
            depth = 0
            for i in range(brace_idx, len(text)):
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
        # Normaliza y asegura tipos
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
        return (url
                .replace("www.instagram.com", "m.instagram.com")
                .replace("instagram.com", "m.instagram.com"))

    # ---------------------------
    # Método 3: yt-dlp fallback
    # ---------------------------
    def _get_ydl_opts(self, audio_only: bool = False, mobile: bool = True) -> Dict[str, Any]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best" if audio_only else "best",
            "http_headers": self.get_platform_headers(mobile=mobile),
            "socket_timeout": settings.REQUEST_TIMEOUT,
            "extract_flat": False,
            "force_generic_extractor": False,
            "retries": 3,
        }
        # cookies: si self._cookies trae el contenido, lo volcamos a un archivo temporal
        if getattr(self, "_cookies", None):
            # se escribe en _extract_ytdlp/_extract_audio_url para limpiar después
            opts["_cookies_inline_text"] = self._cookies  # marcador interno
        return opts

    async def _extract_ytdlp(self, url: str, mobile: bool = True) -> Optional[Dict[str, Any]]:
        temp_cookie_path = None
        try:
            ydl_opts = self._get_ydl_opts(audio_only=False, mobile=mobile)

            # manejar cookie inline -> archivo temporal
            if ydl_opts.pop("_cookies_inline_text", None):
                fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self._cookies or "")
                ydl_opts["cookiefile"] = temp_cookie_path

            def _do():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False, process=True)

            info = await asyncio.to_thread(_do)
            if not info:
                return None

            media_url = self._get_best_media_url(info)
            if not media_url:
                return None

            return self._build_ydlp_response(info, media_url, method="yt-dlp")
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.unlink(temp_cookie_path)
                except Exception:
                    pass

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
                # a veces yt-dlp deja el directo en info["url"]
                if not audio_only and info.get("url"):
                    return info["url"]
                return None

            # ordenar por resolución y tasa
            def _key(f):
                w = self._safe_int(f.get("width"))
                h = self._safe_int(f.get("height"))
                tbr = self._safe_float(f.get("tbr") or f.get("abr") or 0.0)
                fps = self._safe_float(f.get("fps") or 0.0)
                return (w * h, tbr, fps)

            valid.sort(key=_key, reverse=True)
            return valid[0]["url"]
        except Exception as e:
            logger.warning("Error seleccionando formato Instagram: %s", str(e))
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
    # Audio
    # ---------------------------
    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> Dict[str, Any]:
        """
        Devuelve audio_url directo cuando existe; si es m3u8, indica que requiere conversión.
        """
        temp_cookie_path = None
        try:
            # admite cookies inline
            self._cookies = cookies or self._cookies
            ydl_opts = self._get_ydl_opts(audio_only=True, mobile=True)
            if ydl_opts.pop("_cookies_inline_text", None):
                fd, temp_cookie_path = tempfile.mkstemp(suffix=".txt")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self._cookies or "")
                ydl_opts["cookiefile"] = temp_cookie_path

            def _do():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False, process=True)

            info = await asyncio.to_thread(_do)

            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("url") and f.get("acodec") != "none" and f.get("vcodec") == "none"
            ]
            if not audio_formats:
                raise SnapTubeError("No audio streams found")

            # mayor abr/tbr
            audio_formats.sort(
                key=lambda f: float(f.get("abr") or f.get("tbr") or 0.0),
                reverse=True
            )
            best = audio_formats[0]
            best_url = best["url"]

            if best_url.endswith(".m3u8"):
                # no convertimos aquí para ahorrar CPU en Render; devolvemos instrucción
                return {
                    "status": "success",
                    "audio_url": best_url,
                    "note": "Stream HLS .m3u8. Si necesitas MP3, usa un job de ffmpeg en background.",
                    "metadata": {
                        "bitrate": self._safe_int(best.get("abr") or best.get("tbr")),
                        "codec": "aac",
                        "duration": self._safe_int(info.get("duration")),
                        "quality": "best",
                    },
                }
            else:
                return {
                    "status": "success",
                    "audio_url": best_url,
                    "metadata": {
                        "bitrate": self._safe_int(best.get("abr") or best.get("tbr")),
                        "codec": "mp4a",
                        "duration": self._safe_int(info.get("duration")),
                        "quality": "best",
                    },
                }
        except yt_dlp.utils.DownloadError as e:
            raise SnapTubeError(f"Instagram audio error: {str(e)}")
        except Exception as e:
            logger.error("Error extracting Instagram audio: %s", str(e), exc_info=True)
            raise SnapTubeError("Failed to extract Instagram audio")
        finally:
            if temp_cookie_path and os.path.exists(temp_cookie_path):
                try:
                    os.unlink(temp_cookie_path)
                except Exception:
                    pass
