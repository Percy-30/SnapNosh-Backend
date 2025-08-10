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