# ====================================================================
# app/utils/constants.py
# ====================================================================
from typing import Dict, List

# User Agents
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

# Headers for different devices
HEADERS_DESKTOP: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

HEADERS_MOBILE: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Platform specific headers
TIKTOK_HEADERS: Dict[str, str] = {
    **HEADERS_DESKTOP,
    "Referer": "https://www.tiktok.com/",
    "Origin": "https://www.tiktok.com"
}

FACEBOOK_HEADERS: Dict[str, str] = {
    **HEADERS_DESKTOP,
    "Referer": "https://www.facebook.com/",
    "Origin": "https://www.facebook.com"
}

YOUTUBE_HEADERS: Dict[str, str] = {
    **HEADERS_DESKTOP,
    "Referer": "https://www.youtube.com/",
    "Origin": "https://www.youtube.com"
}

# Quality settings
QUALITY_FORMATS: Dict[str, str] = {
    "best": "bestvideo+bestaudio/best",
    "worst": "worstvideo+worstaudio/worst",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]"
}

# Platform detection patterns
PLATFORM_PATTERNS: Dict[str, List[str]] = {
    "tiktok": ["tiktok.com", "vm.tiktok.com"],
    "facebook": ["facebook.com", "fb.com", "fb.watch"],
    "youtube": ["youtube.com", "youtu.be", "m.youtube.com"]
}

# API endpoints for third-party services
THIRD_PARTY_APIS: Dict[str, List[str]] = {
    "tiktok": [
        "https://www.tikwm.com/api/",
        "https://tikdownloader.com/api/"
    ]
}

# Valid video domains for validation
VALID_VIDEO_DOMAINS: Dict[str, List[str]] = {
    "tiktok": ["tiktokcdn.com", "tiktokv.com", "muscdn.com", "byteoversea.com"],
    "facebook": ["video.xx.fbcdn.net", "scontent.xx.fbcdn.net"],
    "youtube": ["googlevideo.com", "youtube.com"]
}