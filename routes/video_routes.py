import logging
import asyncio
import os
import random
import uuid
import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, HTTPException, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
import yt_dlp

from app.config import settings
from app.models.video_models import VideoInfo, ErrorResponse, SuccessResponse
from app.services import TikTokExtractor, FacebookExtractor, YouTubeExtractor, SnapTubeError
from app.utils.validators import URLValidator
from utils.constants import QUALITY_FORMATS, USER_AGENTS

# Setup
router = APIRouter(prefix="/api/v1", tags=["videos"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

# Initialize extractors
extractors = {
    "tiktok": TikTokExtractor(),
    "facebook": FacebookExtractor(),
    "youtube": YouTubeExtractor()
}

class SnapTubeService:
    """Main service orchestrator"""
    
    def __init__(self):
        self.validator = URLValidator()
        self.extractors = extractors
    
    async def extract_video(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract video from any supported platform"""
        try:
            platform = self.validator.detect_platform(url)
            extractor = self.extractors[platform]
            
            return await extractor.extract(url, **kwargs)
            
        except Exception as e:
            logger.error(f"Extraction error: {str(e)}")
            raise SnapTubeError(f"Extraction failed: {str(e)}")

service = SnapTubeService()

@router.get("/", response_model=SuccessResponse)
async def api_info():
    """API information endpoint"""
    return SuccessResponse(
        data={
            "name": "SnapTube API",
            "version": settings.API_VERSION,
            "description": settings.API_DESCRIPTION,
            "supported_platforms": ["TikTok", "Facebook", "YouTube"],
            "endpoints": {
                "/extract": "Extract video information",
                "/download": "Download video file",
                "/stream": "Stream video content",
                "/formats": "Get available formats",
                "/health": "Health check"
            }
        }
    )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.API_VERSION,
        "timestamp": asyncio.get_event_loop().time(),
        "temp_files": len(list(settings.TEMP_DIR.glob("*")))
    }

@router.get("/extract", response_model=VideoInfo)
@limiter.limit(settings.RATE_LIMIT_EXTRACT)
async def extract_video_info(
    request: Request,
    url: str = Query(..., description="Video URL from TikTok, Facebook, or YouTube"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies in Netscape format for YouTube"),
    force_ytdlp: bool = Query(False, description="Force yt-dlp usage for YouTube"),
    include_formats: bool = Query(False, description="Include all available formats")
):
    """
    Extract comprehensive video information from social media platforms
    
    **Supported platforms:**
    - **TikTok**: Full metadata extraction with multiple fallback methods
    - **Facebook**: Public videos with metadata  
    - **YouTube**: Requires cookies for some videos
    
    **Parameters:**
    - `url`: Direct video URL
    - `mobile`: Use mobile user agent for better compatibility
    - `cookies`: YouTube cookies for accessing restricted content
    - `force_ytdlp`: Force yt-dlp usage even if initial extraction fails
    - `include_formats`: Include detailed format information in response
    """
    try:
        logger.info(f"🎬 Extracting video info for: {url}")
        
        result = await service.extract_video(
            url=url,
            mobile=mobile,
            cookies=cookies,
            force_ytdlp=force_ytdlp
        )
        
        if not include_formats:
            result.pop('formats', None)
        
        logger.info(f"✅ Successfully extracted using method: {result.get('method')}")
        return result
        
    except SnapTubeError as e:
        logger.error(f"❌ SnapTube error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"💥 Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/download")
@limiter.limit(settings.RATE_LIMIT_DOWNLOAD)
async def download_video(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Video URL"),
    quality: str = Query("720p", description="Video quality: best, 1080p, 720p, 480p, 360p, worst"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    """
    Download video file directly to device
    
    **Quality options:**
    - `best`: Highest available quality
    - `1080p`: 1080p or lower
    - `720p`: 720p or lower (recommended)
    - `480p`: 480p or lower
    - `360p`: 360p or lower  
    - `worst`: Lowest available quality
    """
    try:
        logger.info(f"⬇️ Downloading video: {url}")
        
        # Extract video info first
        video_info = await service.extract_video(
            url=url,
            mobile=mobile,
            cookies=cookies
        )
        
        # Generate unique filename
        download_id = str(uuid.uuid4())
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_info.get('title', 'video'))[:50]
        filename = f"{video_info['platform']}_{safe_title}_{download_id}.mp4"
        filepath = settings.TEMP_DIR / filename
        
        # Download with yt-dlp for quality control
        ydl_opts = {
            'outtmpl': str(filepath),
            'format': QUALITY_FORMATS.get(quality, QUALITY_FORMATS['720p']),
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Referer': f"https://www.{video_info['platform']}.com/"
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: ydl.download([video_info['video_url']])
            )
        
        if not filepath.exists():
            raise HTTPException(status_code=500, detail="Download failed")
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, str(filepath))
        
        # Return file
        return FileResponse(
            path=str(filepath),
            filename=f"{safe_title}.mp4",
            media_type='video/mp4'
        )
        
    except SnapTubeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"💥 Download error: {str(e)}")
        raise HTTPException(status_code=500, detail="Download failed")

@router.get("/stream")
@limiter.limit(settings.RATE_LIMIT_STREAM)
async def stream_video(
    request: Request,
    url: str = Query(..., description="Video URL"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    """
    Stream video content directly without downloading
    """
    try:
        logger.info(f"📺 Streaming video: {url}")
        
        video_info = await service.extract_video(
            url=url,
            mobile=mobile,
            cookies=cookies
        )
        
        video_url = video_info['video_url']
        
        def generate_stream():
            import requests
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Referer': f"https://www.{video_info['platform']}.com/"
            }
            
            with requests.get(video_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
        
        return StreamingResponse(
            generate_stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"inline; filename=\"{video_info.get('title', 'video')}.mp4\""
            }
        )
        
    except SnapTubeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"💥 Streaming error: {str(e)}")
        raise HTTPException(status_code=500, detail="Streaming failed")

@router.get("/formats")
async def get_video_formats(
    request: Request,
    url: str = Query(..., description="Video URL"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    """Get all available formats for a video"""
    try:
        video_info = await service.extract_video(url=url, cookies=cookies)
        
        return {
            "status": "success",
            "platform": video_info['platform'],
            "title": video_info['title'],
            "available_qualities": list(QUALITY_FORMATS.keys()),
            "recommended": "720p",
            "current_quality": video_info.get('quality', {})
        }
        
    except Exception as e:
        logger.error(f"💥 Format extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get formats")

@router.get("/platforms")
async def get_supported_platforms():
    """Get detailed information about supported platforms"""
    return {
        "supported_platforms": [
            {
                "name": "TikTok",
                "domains": ["tiktok.com", "vm.tiktok.com"],
                "features": ["metadata_extraction", "multiple_qualities", "thumbnail", "statistics"],
                "extraction_methods": ["ytdlp", "manual_html", "third_party_api"],
                "notes": "Multiple fallback methods for maximum reliability"
            },
            {
                "name": "Facebook",
                "domains": ["facebook.com", "fb.com", "fb.watch"],
                "features": ["metadata_extraction", "thumbnail"],
                "extraction_methods": ["ytdlp", "manual_html", "mobile_redirect"],
                "notes": "Public videos only, private videos require authentication"
            },
            {
                "name": "YouTube",
                "domains": ["youtube.com", "youtu.be", "m.youtube.com"],
                "features": ["metadata_extraction", "multiple_qualities", "chapters", "subtitles"],
                "extraction_methods": ["ytdlp_multi_client", "forced_extraction"],
                "notes": "May require cookies for age-restricted or private videos"
            }
        ],
        "total_platforms": 3,
        "version": settings.API_VERSION
    }

# Background tasks
async def cleanup_file(filepath: str):
    """Clean up downloaded file after delay"""
    await asyncio.sleep(settings.CLEANUP_INTERVAL)
    try:
        if os.path.exists(filepath):
            os.unlink(filepath)
            logger.info(f"🗑️ Cleaned up file: {filepath}")
    except Exception as e:
        logger.warning(f"⚠️ Cleanup failed for {filepath}: {str(e)}")
