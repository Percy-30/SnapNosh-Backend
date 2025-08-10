# ====================================================================
# app/utils/validators.py
# ====================================================================
import re
from urllib.parse import urlparse
from typing import Optional
from app.config import settings
from app.utils.constants import PLATFORM_PATTERNS, VALID_VIDEO_DOMAINS

class URLValidator:
    """URL validation utilities"""
    
    @staticmethod
    def validate_url(url: str) -> urlparse:
        """Validate and parse URL"""
        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid URL format")
            
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP and HTTPS URLs are supported")
            
            return parsed
        except Exception as e:
            raise ValueError(f"Invalid URL: {str(e)}")
    
    @staticmethod
    def detect_platform(url: str) -> str:
        """Detect platform from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        for platform, patterns in PLATFORM_PATTERNS.items():
            if any(pattern in domain for pattern in patterns):
                return platform
        
        raise ValueError(f"Unsupported platform: {domain}")
    
    @staticmethod
    def validate_video_url(video_url: str, platform: str) -> bool:
        """Validate extracted video URL"""
        if not video_url:
            return False
        
        if platform in VALID_VIDEO_DOMAINS:
            valid_domains = VALID_VIDEO_DOMAINS[platform]
            return any(domain in video_url for domain in valid_domains)
        
        # Generic validation for unknown platforms
        parsed = urlparse(video_url)
        return parsed.scheme in ['http', 'https'] and parsed.netloc

class TikTokValidator:
    """TikTok specific validators"""
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extract TikTok video ID"""
        patterns = [
            r'/video/(\d+)',
            r'tiktok\.com.*?/(\d{19})',
            r'vm\.tiktok\.com/([A-Za-z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None