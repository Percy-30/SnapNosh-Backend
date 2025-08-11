# ====================================================================
# app/services/base_extractor.py
# ====================================================================
import logging
import random
import requests
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.config import settings
from app.utils.constants import USER_AGENTS, HEADERS_DESKTOP, HEADERS_MOBILE
from app.utils.validators import URLValidator

logger = logging.getLogger(__name__)

class SnapTubeError(Exception):
    """Custom exception for SnapTube operations"""
    pass

class BaseExtractor(ABC):
    """Base class for all video extractors"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS_DESKTOP)
        self.validator = URLValidator()
    
    def get_random_user_agent(self) -> str:
        """Get random user agent"""
        return random.choice(USER_AGENTS)
    
    def get_headers(self, mobile: bool = False, platform_specific: bool = True) -> Dict[str, str]:
        """Get appropriate headers"""
        base_headers = HEADERS_MOBILE if mobile else HEADERS_DESKTOP
        headers = base_headers.copy()
        headers['User-Agent'] = self.get_random_user_agent()
        
        if platform_specific:
            headers.update(self.get_platform_headers())
        
        return headers
    
    @abstractmethod
    def get_platform_headers(self) -> Dict[str, str]:
        """Get platform-specific headers"""
        pass
    
    @abstractmethod
    async def extract(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract video information"""
        pass
    
    def validate_extracted_url(self, video_url: str) -> bool:
        """Validate extracted video URL"""
        return self.validator.validate_video_url(video_url, self.platform)
    
    @property
    @abstractmethod
    def platform(self) -> str:
        """Platform name"""
        pass