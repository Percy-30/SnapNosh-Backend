# ====================================================================
# app/utils/constants.py
# ====================================================================
from typing import Dict, List

# User Agents (puedes ampliar esta lista)
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
]

# Headers genéricos para escritorio
HEADERS_DESKTOP: Dict[str, str] = {
    "User-Agent": USER_AGENTS[0],
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

# Headers genéricos para móvil
HEADERS_MOBILE: Dict[str, str] = {
    "User-Agent": USER_AGENTS[2],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Headers específicos por plataforma
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

TWITTER_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENTS[0],
    "Referer": "https://twitter.com/",
    "Origin": "https://twitter.com",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

HEADERS_DEFAULT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


INSTAGRAM_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENTS[0],
    "Referer": "https://www.instagram.com/",
    "Origin": "https://www.instagram.com",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# NUEVO: Headers para Threads.net (Meta Threads)
THREADS_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENTS[0],
    "Referer": "https://www.threads.net/",
    "Origin": "https://www.threads.net",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Quality format strings para yt-dlp
QUALITY_FORMATS: Dict[str, str] = {
    "best": "bestvideo+bestaudio/best",
    "worst": "worstvideo+worstaudio/worst",
    "144p": "bestvideo[height<=144]+bestaudio/best[height<=144]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]"  # 4k
}

# Detectores de plataformas para URLs
PLATFORM_PATTERNS: Dict[str, List[str]] = {
    "tiktok": ["tiktok.com", "vm.tiktok.com"],
    "facebook": ["facebook.com", "fb.com", "fb.watch"],
    "youtube": ["youtube.com", "youtu.be", "m.youtube.com"],
    "twitter": ["twitter.com", "mobile.twitter.com", "x.com"],
    "instagram": ["instagram.com", "www.instagram.com", "instagr.am"],
    "threads": ["threads.net", "www.threads.net", "threads.com", "www.threads.com"], # NUEVO: Threads
    "downloader": [],  # para URLs genéricas sin patrón específico
}

# APIs de terceros usadas (ejemplo para TikTok)
THIRD_PARTY_APIS: Dict[str, List[str]] = {
    "tiktok": [
        "https://www.tikwm.com/api/",
        "https://tikdownloader.com/api/"
    ]
}

# Dominios válidos para validar URLs de videos
VALID_VIDEO_DOMAINS: Dict[str, List[str]] = {
    "tiktok": ["tiktokcdn.com", "tiktokv.com", "muscdn.com", "byteoversea.com"],
    "facebook": ["video.xx.fbcdn.net", "scontent.xx.fbcdn.net"],
    "youtube": ["googlevideo.com", "youtube.com"],
    "twitter": ["twitter.com", "mobile.twitter.com", "x.com", "twimg.com"],
    "instagram": ["instagram.com", "cdninstagram.com", "instagram.fxyz1-1.fna.fbcdn.net"],
    "threads": ["threads.net", "www.threads.net", "threads.com", "www.threads.com"], # NUEVO: Threads dominios válidos
    "downloader": [],
}
