# ====================================================================
# app/models/video_models.py
# ====================================================================
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime

class VideoQuality(BaseModel):
    """Video quality information"""
    resolution: Optional[str] = None
    fps: Optional[int] = None
    bitrate: Optional[int] = None
    format: str = "mp4"

class VideoInfo(BaseModel):
    """Base video information model"""
    status: str = "success"
    platform: str
    title: str
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    video_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    uploader: Optional[str] = None
    uploader_id: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    upload_date: Optional[str] = None
    method: str
    quality: Optional[VideoQuality] = None
    extracted_at: datetime = datetime.now()

class TikTokVideo(VideoInfo):
    """TikTok specific video model"""
    platform: str = "tiktok"
    hashtags: Optional[List[str]] = None
    music_title: Optional[str] = None
    music_author: Optional[str] = None

class FacebookVideo(VideoInfo):
    """Facebook specific video model"""
    platform: str = "facebook"
    page_name: Optional[str] = None

class YouTubeVideo(VideoInfo):
    """YouTube specific video model"""
    platform: str = "youtube"
    channel_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class ErrorResponse(BaseModel):
    """Error response model"""
    status: str = "error"
    message: str
    error_type: Optional[str] = None
    platform: Optional[str] = None

class SuccessResponse(BaseModel):
    """Success response model"""
    status: str = "success"
    data: Any
    message: Optional[str] = None
    

# --- Tus modelos ya existentes (VideoInfo, etc.) ---

class VideoFormat(BaseModel):
    format_id: str
    ext: str
    vcodec: str
    acodec: str
    filesize: Optional[int] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    quality: Optional[int] = None

class VideoThumbnail(BaseModel):
    url: HttpUrl
    width: Optional[int]
    height: Optional[int]

# ---------------- Modelo Snaptube mejorado ----------------

class DownloadOption(BaseModel):
    type: str                 # "video" o "audio"
    quality: str              # Ej: "720p 30fps" o "High Quality (192K)"
    format: str               # Ej: "mp4", "mp3"
    size_estimate: str        # Ej: "~45MB"
    recommended: bool = False
    format_id: Optional[str] = None
    actual_filesize: Optional[int] = None

class SnaptubeVideoInfo(BaseModel):
    id: Optional[str]
    title: str
    description: Optional[str]
    duration: Optional[int]
    duration_string: Optional[str]
    view_count: Optional[int]
    uploader: str
    upload_date: Optional[str]
    thumbnail: Optional[str]
    thumbnails: List[Dict[str, Any]] = []
    webpage_url: Optional[str]
    has_formats: bool

class SearchResult(BaseModel):
    id: Optional[str]
    title: str
    uploader: str
    duration_string: Optional[str]
    view_count: Optional[int]
    thumbnail: Optional[str]
    url: Optional[str]
    upload_date: Optional[str]

class TrendingVideo(BaseModel):
    id: Optional[str]
    title: str
    uploader: str
    duration_string: Optional[str]
    view_count: Optional[int]
    thumbnail: Optional[str]
    url: Optional[str]

# Puedes agregar más modelos según necesites para la API