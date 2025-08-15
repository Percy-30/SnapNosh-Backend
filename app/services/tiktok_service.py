# ====================================================================
# app/services/tiktok_service.py
# ====================================================================
import asyncio
import logging
import re
import json
import aiohttp
import requests
import yt_dlp
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import TIKTOK_HEADERS, QUALITY_FORMATS
from app.utils.validators import TikTokValidator
from app.config import settings

logger = logging.getLogger(__name__)

class TikTokExtractor(BaseExtractor):
    """TikTok video extractor with multiple fallback methods"""
    
    @property
    def platform(self) -> str:
        return "tiktok"
    
    def get_platform_headers(self) -> Dict[str, str]:
        return TIKTOK_HEADERS
    
    async def extract(self, url: str, mobile: bool = False, **kwargs) -> Dict[str, Any]:
        """Extract TikTok video with multiple methods"""
        self.validator.validate_url(url)
        
        methods = [
            self._extract_ytdlp,
            self._extract_manual,
            self._extract_third_party_api
        ]
        
        last_error = None
        for method in methods:
            try:
                logger.info(f"Trying {method.__name__} for TikTok extraction")
                result = await method(url, mobile)
                
                if result and self.validate_extracted_url(result.get('video_url')):
                    logger.info(f"✅ TikTok extraction successful with {method.__name__}")
                    return result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {method.__name__} failed: {str(e)}")
                continue
        
        raise SnapTubeError(f"All TikTok extraction methods failed. Last error: {str(last_error)}")
    
    async def _extract_ytdlp(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Extract using yt-dlp (primary method)"""
        try:
            headers = self.get_headers(mobile)
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'forceurl': True,
                'simulate': True,
                'skip_download': True,
                'format': QUALITY_FORMATS['best'],
                'noplaylist': True,
                'http_headers': headers,
                'extractor_retries': settings.MAX_RETRIES,
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
                if not self.validate_extracted_url(video_url):
                    return None

                return self._build_response(info, "ytdlp")
                
        except Exception as e:
            logger.warning(f"TikTok yt-dlp extraction failed: {str(e)}")
            return None
    
    async def _extract_manual(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Manual HTML extraction (fallback method)"""
        try:
            headers = self.get_headers(mobile)
            
            response = self.session.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different extraction methods
            video_data = (self._extract_from_sigi_state(soup) or 
                         self._extract_from_universal_data(soup) or
                         self._extract_from_next_data(soup))
            
            if not video_data:
                return None
            
            return self._build_response_from_data(video_data, "manual_extraction")
            
        except Exception as e:
            logger.warning(f"TikTok manual extraction failed: {str(e)}")
            return None
    
    async def _extract_third_party_api(self, url: str, mobile: bool = False) -> Optional[Dict[str, Any]]:
        """Extract using third-party APIs"""
        try:
            # TikWM API
            api_url = f"https://www.tikwm.com/api/?url={url}"
            
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') == 0:
                video_data = data.get('data', {})
                video_url = video_data.get('play', '')
                
                if not self.validate_extracted_url(video_url):
                    return None
                
                return self._build_api_response(video_data, "tikwm_api")
                
        except Exception as e:
            logger.warning(f"TikTok API extraction failed: {str(e)}")
            return None
    
    def _extract_from_sigi_state(self, soup) -> Optional[Dict]:
        """Extract from SIGI_STATE"""
        for script in soup.find_all('script'):
            if script.string and 'SIGI_STATE' in script.string:
                try:
                    match = re.search(r'window\[\'SIGI_STATE\'\]=({.*?});window\[', script.string)
                    if match:
                        data = json.loads(match.group(1))
                        for key, value in data.get('ItemModule', {}).items():
                            if isinstance(value, dict) and 'video' in value:
                                return value
                except (json.JSONDecodeError, AttributeError):
                    continue
        return None
    
    def _extract_from_universal_data(self, soup) -> Optional[Dict]:
        """Extract from __UNIVERSAL_DATA_FOR_REHYDRATION__"""
        for script in soup.find_all('script'):
            if script.string and '__UNIVERSAL_DATA_FOR_REHYDRATION__' in script.string:
                try:
                    match = re.search(r'__UNIVERSAL_DATA_FOR_REHYDRATION__=({.*?});', script.string)
                    if match:
                        data = json.loads(match.group(1))
                        detail_data = data.get('__DEFAULT_SCOPE__', {}).get('webapp.video-detail', {})
                        if 'itemInfo' in detail_data:
                            return detail_data['itemInfo']['itemStruct']
                except (json.JSONDecodeError, AttributeError):
                    continue
        return None
    
    def _extract_from_next_data(self, soup) -> Optional[Dict]:
        """Extract from __NEXT_DATA__"""
        script = soup.find('script', id='__NEXT_DATA__')
        if script and script.string:
            try:
                data = json.loads(script.string)
                props = data.get('props', {}).get('pageProps', {})
                return props.get('itemInfo', {}).get('itemStruct')
            except (json.JSONDecodeError, KeyError):
                pass
        return None
    
    def _get_best_video_url(self, info: Dict) -> Optional[str]:
        """Get the best quality video URL"""
        video_url = info.get('url')
        if video_url:
            return video_url
        
        if 'formats' in info:
            formats = sorted(
                info['formats'], 
                key=lambda x: (
                    x.get('height', 0) or 0,
                    x.get('width', 0) or 0,
                    x.get('tbr', 0) or 0
                ),
                reverse=True
            )
            
            for f in formats:
                if f.get('url') and f.get('protocol') in ('http', 'https'):
                    return f['url']
        
        return None
    
    def _build_response(self, info: Dict, method: str) -> Dict[str, Any]:
        """Build standardized response from yt-dlp info"""
        return {
            "status": "success",
            "platform": "tiktok",
            "title": info.get('title', 'TikTok Video'),
            "description": info.get('description', ''),
            "thumbnail": info.get('thumbnail', ''),
            "duration": info.get('duration', 0),
            "video_url": self._get_best_video_url(info),
            "width": info.get('width'),
            "height": info.get('height'),
            "uploader": info.get('uploader', ''),
            "uploader_id": info.get('uploader_id', ''),
            "view_count": info.get('view_count', 0),
            "like_count": info.get('like_count', 0),
            "comment_count": info.get('comment_count', 0),
            "upload_date": info.get('upload_date', ''),
            "method": method,
            "quality": self._get_quality_info(info)
        }
    
    def _build_response_from_data(self, video_data: Dict, method: str) -> Dict[str, Any]:
        """Build response from manual extraction data"""
        video_info = video_data.get('video', {})
        author = video_data.get('author', {})
        stats = video_data.get('stats', {})
        
        video_url = (video_info.get('downloadAddr') or 
                    video_info.get('playAddr') or 
                    video_info.get('playApi'))
        
        return {
            "status": "success",
            "platform": "tiktok",
            "title": video_data.get('desc', 'TikTok Video'),
            "description": video_data.get('desc', ''),
            "thumbnail": video_info.get('cover', ''),
            "duration": video_info.get('duration', 0),
            "video_url": video_url,
            "width": video_info.get('width'),
            "height": video_info.get('height'),
            "uploader": author.get('uniqueId', ''),
            "uploader_id": author.get('id', ''),
            "view_count": stats.get('playCount', 0),
            "like_count": stats.get('diggCount', 0),
            "comment_count": stats.get('commentCount', 0),
            "method": method
        }
    
    def _build_api_response(self, video_data: Dict, method: str) -> Dict[str, Any]:
        """Build response from API data"""
        author = video_data.get('author', {})
        
        return {
            "status": "success",
            "platform": "tiktok",
            "title": video_data.get('title', 'TikTok Video'),
            "description": video_data.get('title', ''),
            "thumbnail": video_data.get('cover', ''),
            "duration": video_data.get('duration', 0),
            "video_url": video_data.get('play', ''),
            "uploader": author.get('unique_id', ''),
            "view_count": video_data.get('play_count', 0),
            "like_count": video_data.get('digg_count', 0),
            "comment_count": video_data.get('comment_count', 0),
            "method": method
        }
        
    async def extract_audio_url(self, url: str) -> Dict[str, Any]:
        """
        Extrae la URL de audio de TikTok y devuelve metadata completa
        incluyendo miniatura.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                              'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
                              'Mobile/15E148 Safari/604.1'
            }
    
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    html = await response.text()
    
            # Buscar JSON con info de video
            json_pattern = r'<script[^>]*>window\.__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*({.*?})</script>'
            match = re.search(json_pattern, html)
            audio_url = None
            thumbnail = None
            title = None
            duration = 0
    
            if match:
                try:
                    data = json.loads(match.group(1))
                    video_detail = data.get('__DEFAULT_SCOPE__', {}).get(
                        'webapp.video-detail', {}).get('itemInfo', {}).get('itemStruct', {})
                    if video_detail:
                        music = video_detail.get('music', {})
                        audio_url = music.get('playUrl', '')
                        title = video_detail.get('desc', 'TikTok Video')
                        duration = video_detail.get('video', {}).get('duration', 0)
                        thumbnail = video_detail.get('video', {}).get('cover', '')
                except json.JSONDecodeError:
                    pass
                
            # Fallback regex si no hay JSON
            if not audio_url:
                patterns = [
                    r'"playAddr":"([^"]*\.mp3[^"]*)"',
                    r'"downloadAddr":"([^"]*\.mp3[^"]*)"',
                    r'playUrl":"([^"]*)"'
                ]
                for pattern in patterns:
                    match = re.search(pattern, html)
                    if match:
                        audio_url = match.group(1)
                        break
                    
            if not audio_url:
                raise SnapTubeError("Audio URL not found for TikTok video")
    
            # Decodificar Unicode
            audio_url = audio_url.encode('utf-8').decode('unicode_escape')
    
            return {
                "status": "success",
                "audio_url": audio_url,
                "thumbnail": thumbnail,
                "title": title,
                "duration": duration
            }
    
        except Exception as e:
            logger.error(f"Error extracting TikTok audio: {str(e)}", exc_info=True)
            raise SnapTubeError(f"Error extracting TikTok audio: {str(e)}")
    
    async def extract_audio_url_with_fallback(self, url: str) -> Dict[str, Any]:
        try:
            result = await self.extract_audio_url(url)
            
            # Si algo falta, usar extract() para completar
            if not result.get("title") or not result.get("thumbnail") or not result.get("duration"):
                video_info = await self.extract(url)
                result["title"] = result.get("title") or video_info.get("title")
                result["thumbnail"] = result.get("thumbnail") or video_info.get("thumbnail")
                result["duration"] = result.get("duration") or video_info.get("duration")
            
            return {
                "audio_url": result.get("audio_url"),
                "title": result.get("title"),
                "thumbnail": result.get("thumbnail"),
                "duration": result.get("duration")
            }
        except SnapTubeError:
            video_info = await self.extract(url)
            return {
                "audio_url": video_info.get("video_url"),
                "title": video_info.get("title"),
                "thumbnail": video_info.get("thumbnail"),
                "duration": video_info.get("duration")
            }



    
    def _get_quality_info(self, info: Dict) -> Dict:
        """Extract quality information"""
        return {
            'resolution': f"{info.get('width', 'unknown')}x{info.get('height', 'unknown')}",
            'fps': info.get('fps'),
            'bitrate': info.get('tbr'),
            'format': info.get('ext', 'mp4')
        }
    
    def _get_cookies_file(self) -> Optional[str]:
        """Get cookies file path if exists"""
        cookies_path = settings.COOKIES_DIR / f"{self.platform}_cookies.txt"
        return str(cookies_path) if cookies_path.exists() else None
    
    
    
