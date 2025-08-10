import os
from pathlib import Path
from typing import List, Optional

class Settings:
    """Application settings and configuration"""
    
    # API Configuration
    API_TITLE: str = "SnapTube API"
    API_DESCRIPTION: str = "Advanced Social Media Video Downloader API"
    API_VERSION: str = "2.0.0"
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Rate Limiting
    RATE_LIMIT_EXTRACT: str = "30/minute"
    RATE_LIMIT_DOWNLOAD: str = "10/minute"
    RATE_LIMIT_STREAM: str = "20/minute"
    
    # File Management
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "/tmp/snaptube"))
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 500 * 1024 * 1024))  # 500MB
    CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", 3600))  # 1 hour
    
    # Request Configuration
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", 30))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", 3))
    
    # Cookies
    COOKIES_DIR: Path = Path("cookies")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    def __init__(self):
        # Create necessary directories
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.COOKIES_DIR.mkdir(exist_ok=True)

settings = Settings()