import os
import platform
from pathlib import Path
from typing import List

class Settings:
    """Application settings and configuration"""

    # API Configuration
    API_TITLE: str = "SnapTube API"
    API_DESCRIPTION: str = "Advanced Social Media Video Downloader API"
    API_VERSION: str = "2.0.0"

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = True

    # Security
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")

    # Rate Limiting
    RATE_LIMIT_EXTRACT: str = "30/minute"
    RATE_LIMIT_DOWNLOAD: str = "10/minute"
    RATE_LIMIT_STREAM: str = "20/minute"

    # File Management
    if platform.system() == "Windows":
        TEMP_DIR: Path = Path.home() / "AppData" / "Local" / "Temp" / "snaptube"
        COOKIES_DIR: Path = TEMP_DIR / "cookies"
    else:
        TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "/tmp/snaptube"))
        COOKIES_DIR: Path = Path(os.getenv("COOKIES_DIR", "/tmp/snaptube/cookies"))
    
    # Aquí definimos la ruta completa al archivo de cookies de YouTube
    YOUTUBE_COOKIES_PATH: Path = Path(os.getenv("YOUTUBE_COOKIES_PATH", "app/cookies/cookies.txt"))

    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 500 * 1024 * 1024))  # 500MB
    CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", 3600))  # 1 hour

    # Request Configuration
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", 30))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", 3))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Proxies
    USE_PROXIES: bool = os.getenv("USE_PROXIES", "false").lower() == "true"
    PROXY_LIST: str = os.getenv("PROXY_LIST", "")  # ej: "http://proxy1:port,http://proxy2:port"

    def __init__(self):
        # Create necessary directories with parents=True
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.COOKIES_DIR.mkdir(parents=True, exist_ok=True)
        self.YOUTUBE_COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)

settings = Settings()
