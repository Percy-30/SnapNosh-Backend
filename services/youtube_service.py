# ====================================================================
# app/services/youtube_service.py
# ====================================================================
import asyncio
import logging
import os
import tempfile
import yt_dlp
from typing import Dict, Any, Optional

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import YOUTUBE_HEADERS, QUALITY_FORMATS, USER_AGENTS
from app.config import settings

logger = logging.getLogger(__name__)

class YouTubeExtractor(BaseExtractor):
    """YouTube video extractor"""
    
    @property
    def platform(self) -> str:
        return "youtube"
    
    def get_platform_headers(self) -> Dict[str, str]:
        return YOUTUBE_HEADERS
    
    async def extract(self, url: str, cookies: Optional[str] = None, force_ytdlp: bool = False, **kwargs) -> Dict[str, Any]:
        """Extract YouTube video"""
        self.validator.validate_url(url)
        
        try:
            ydl_opts = {
                'format': QUALITY_FORMATS['1080p'],
                'outtmpl': str(settings.TEMP_DIR / '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {
                    'youtube': {
                        'skip': ['hls', 'dash'],
                        'player_client': ['android', 'web'],
                    }
                },
                'http_headers': {
                    'User-Agent': self.get_random_user_agent(),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.youtube.com/',
                },
                'socket_timeout': settings.REQUEST_TIMEOUT,
            }

            cookies_path = None
            if cookies:
                cookies_path = self._save_temp_cookies(cookies)
                ydl_opts['cookiefile'] = cookies_path
            elif self._get_cookies_file():
                ydl_opts['cookiefile'] = self._get_cookies_file()

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )
                    
                    if not info:
                        raise SnapTubeError("Could not extract video information")

                    video_url = self._get_best_video_url(info)
                    
                    if not video_url and force_ytdlp:
                        return await self._force_extract(url, ydl_opts)
                    
                    if not video_url:
                        raise SnapTubeError("No valid video URL found")

                    return self._build_response(info, cookies_path)
                    
            finally:
                if cookies_path and os.path.exists(cookies_path):
                    os.unlink(cookies_path)

        except yt_dlp.utils.DownloadError as e:
            msg = str(e)
            if "Sign in to confirm you're not a bot" in msg:
                raise SnapTubeError("YouTube requires valid cookies. Use 'Get cookies.txt' extension.")
            raise SnapTubeError(f"YouTube download error: {msg}")
        except Exception as e:
            logger.error(f"YouTube extraction error: {str(e)}", exc_info=True)
            raise SnapTubeError(f"Internal error: {str(e)}")
    
    def _save_temp_cookies(self, cookies: str) -> str:
        """Save cookies to temporary file"""
        fd, cookies_path = tempfile.mkstemp(suffix='.txt')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(cookies)
        return cookies_path
    
    async def _force_extract(self, url: str, base_opts: dict) -> Dict[str, Any]:
        """Force extraction with different clients"""
        clients = [
            {'player_client': ['android'], 'format': 'best[height<=480]'},
            {'player_client': ['tv_embedded'], 'format': 'best[height<=720]'},
            {'player_client': ['web'], 'format': 'best[height<=360]'},
        ]
        
        for client in clients:
            try:
                opts = base_opts.copy()
                opts['extractor_args']['youtube']['player_client'] = client['player_client']
                opts['format'] = client['format']
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )
                    
                    if info and info.get('url'):
                        return {
                            "status": "success",
                            "platform": "youtube",
                            "title": info.get('title'),
                            "video_url": info['url'],
                            "method": f"forced_{client['player_client'][0]}"
                        }
            except Exception:
                continue
        
        raise SnapTubeError("YouTube blocked extraction. Please provide cookies.")
    
    def _get_best_video_url(self, info: Dict) -> Optional[str]:
        """Get best video URL"""
        video_url = info.get('url')
        if video_url:
            return video_url
        
        if 'formats' in info:
            formats = sorted(
                info['formats'],
                key=lambda x: (x.get('height', 0), x.get('tbr', 0)),
                reverse=True
            )
            
            for f in formats:
                if f.get('url') and f.get('protocol') in ('http', 'https'):
                    return f['url']
        
        return None
    
    def _build_response(self, info: Dict, cookies_used: bool) -> Dict[str, Any]:
        """Build standardized response"""
        return {
            "status": "success",
            "platform": "youtube",
            "title": info.get('title', 'YouTube Video'),
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
            "upload_date": info.get('upload_date', ''),
            "method": "ytdlp_with_cookies" if cookies_used else "ytdlp",
            "quality": self._get_quality_info(info)
        }
    
    def _get_quality_info(self, info: Dict) -> Dict:
        """Get quality information"""
        return {
            'resolution': f"{info.get('width', 'unknown')}x{info.get('height', 'unknown')}",
            'fps': info.get('fps'),
            'bitrate': info.get('tbr'),
            'format': info.get('ext', 'mp4')
        }
