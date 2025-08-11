# ====================================================================
# app/services/facebook_service.py
# ====================================================================
import asyncio
import logging
import os
import re
import json
import tempfile
import yt_dlp
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import FACEBOOK_HEADERS, QUALITY_FORMATS
from app.config import settings

logger = logging.getLogger(__name__)

class FacebookExtractor(BaseExtractor):
    """Facebook video extractor"""
    
    @property
    def platform(self) -> str:
        return "facebook"
    
    def get_platform_headers(self) -> Dict[str, str]:
        return FACEBOOK_HEADERS
    
    async def extract(self, url: str, mobile: bool = False, **kwargs) -> Dict[str, Any]:
        """Extract Facebook video"""
        self.validator.validate_url(url)
        
        methods = [
            self._extract_ytdlp,
            self._extract_manual,
            self._extract_mobile_redirect
        ]
        
        last_error = None
        for method in methods:
            try:
                logger.info(f"Trying {method.__name__} for Facebook extraction")
                result = await method(url, mobile)
                
                if result and result.get('video_url'):
                    logger.info(f"✅ Facebook extraction successful with {method.__name__}")
                    return result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {method.__name__} failed: {str(e)}")
                continue
        
        raise SnapTubeError(f"All Facebook extraction methods failed. Last error: {str(last_error)}")
    
    async def _extract_ytdlp(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Extract using yt-dlp"""
        try:
            headers = self.get_headers(mobile)
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'forceurl': True,
                'simulate': True,
                'format': 'best',
                'http_headers': headers,
                'extractor_args': {'facebook': {'skip_dash_manifest': True}},
                'socket_timeout': settings.REQUEST_TIMEOUT,
                'cookiefile': self._get_cookies_file()
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                
                if not info:
                    return None

                video_url = self._get_best_video_url(info)
                if not video_url:
                    return None

                return self._build_response(info, "ytdlp")
                
        except Exception as e:
            logger.warning(f"Facebook yt-dlp extraction failed: {str(e)}")
            return None
    
    async def _extract_manual(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Manual Facebook extraction"""
        try:
            headers = self.get_headers(mobile)
            
            response = self.session.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different extraction methods
            video_url = (self._extract_from_meta_tags(soup) or
                        self._extract_from_json_ld(soup) or
                        self._extract_from_scripts(soup) or
                        self._extract_from_video_tags(soup))
            
            if not video_url:
                return None
            
            # Get metadata
            title = self._get_title(soup)
            thumbnail = self._get_thumbnail(soup)
            
            return {
                "status": "success",
                "platform": "facebook",
                "title": title,
                "thumbnail": thumbnail,
                "video_url": video_url,
                "method": "manual_extraction"
            }
            
        except Exception as e:
            logger.warning(f"Facebook manual extraction failed: {str(e)}")
            return None
    
    async def _extract_mobile_redirect(self, url: str, mobile: bool = True) -> Optional[Dict[str, Any]]:
        """Try mobile version for better access"""
        try:
            # Convert to mobile URL
            mobile_url = url.replace('www.facebook.com', 'm.facebook.com')
            return await self._extract_manual(mobile_url, mobile=True)
        except Exception as e:
            logger.warning(f"Facebook mobile extraction failed: {str(e)}")
            return None
    
    def _extract_from_meta_tags(self, soup) -> Optional[str]:
        """Extract from meta tags"""
        meta_video = (soup.find("meta", property="og:video") or 
                     soup.find("meta", property="og:video:url") or
                     soup.find("meta", property="og:video:secure_url"))
        if meta_video and meta_video.get("content"):
            return meta_video["content"]
        return None
    
    def _extract_from_json_ld(self, soup) -> Optional[str]:
        """Extract from JSON-LD"""
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
        """Extract from JavaScript"""
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
                    return matches[0].replace('\\/', '/')
        return None
    
    def _extract_from_video_tags(self, soup) -> Optional[str]:
        """Extract from video tags"""
        video_tag = soup.find("video")
        if video_tag:
            # Try src attribute first
            if video_tag.get("src"):
                return video_tag["src"]
            
            # Try source tags
            sources = video_tag.find_all("source")
            for source in sources:
                if source.get("src"):
                    return source["src"]
        return None
    
    def _get_title(self, soup) -> str:
        """Get video title"""
        title_tag = (soup.find("meta", property="og:title") or 
                    soup.find("meta", name="title") or
                    soup.find("title"))
        
        if title_tag:
            if hasattr(title_tag, "content"):
                return title_tag["content"]
            else:
                return title_tag.text.strip()
        return "Facebook Video"
    
    def _get_thumbnail(self, soup) -> str:
        """Get video thumbnail"""
        thumbnail_tag = (soup.find("meta", property="og:image") or
                        soup.find("meta", property="og:image:url"))
        return thumbnail_tag["content"] if thumbnail_tag else ""
    
    def _get_best_video_url(self, info: Dict) -> Optional[str]:
        """Get best video URL"""
        video_url = info.get('url')
        if video_url:
            return video_url
        
        if 'formats' in info:
            for f in info['formats']:
                if f.get('protocol') in ('http', 'https') and f.get('url'):
                    return f['url']
        
        return None
    
    def _build_response(self, info: Dict, method: str) -> Dict[str, Any]:
        """Build standardized response"""
        return {
            "status": "success",
            "platform": "facebook",
            "title": info.get('title', 'Facebook Video'),
            "description": info.get('description', ''),
            "thumbnail": info.get('thumbnail', ''),
            "duration": info.get('duration', 0),
            "video_url": self._get_best_video_url(info),
            "width": info.get('width'),
            "height": info.get('height'),
            "uploader": info.get('uploader', ''),
            "view_count": info.get('view_count', 0),
            "method": method
        }
        
    async def extract_audio_url(self, url: str, cookies: Optional[str] = None) -> str:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "http_headers": self.get_platform_headers(),  # si tienes este método para headers
        }
    
        temp_cookie_path = None
        if cookies:
            import tempfile
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
                audio_url = audio_formats[0]["url"]
            elif info.get("url") and info.get("acodec") != "none" and info.get("vcodec") == "none":
                audio_url = info["url"]
            else:
                raise SnapTubeError("No se encontró URL directa de audio en Facebook")
    
            return audio_url
        finally:
            if temp_cookie_path:
                try:
                    os.unlink(temp_cookie_path)
                except Exception:
                    pass
