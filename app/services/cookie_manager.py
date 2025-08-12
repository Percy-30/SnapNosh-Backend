import os
from typing import Optional

class CookieManager:
    """Gestiona carga y acceso a cookies YouTube"""

    COOKIES_FILE_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "cookies.txt")

    @classmethod
    def get_cookies_path(cls) -> Optional[str]:
        if os.path.exists(cls.COOKIES_FILE_PATH):
            return cls.COOKIES_FILE_PATH
        return None

    @classmethod
    def read_cookies(cls) -> Optional[str]:
        path = cls.get_cookies_path()
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None
