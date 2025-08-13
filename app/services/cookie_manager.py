# app/services/cookie_manager.py
import os
from pathlib import Path
import logging
from typing import Optional

try:
    from browser_cookie3 import chrome, edge
except ImportError:
    chrome = None
    edge = None

logger = logging.getLogger(__name__)

class CookieManager:
    """Gestiona carga y acceso a cookies de YouTube"""

    COOKIES_FILE_PATH = Path(os.getenv("YOUTUBE_COOKIES_PATH", "app/cookies/cookies.txt"))

    @classmethod
    def get_cookies_path(cls) -> Optional[str]:
        """Retorna la ruta de cookies si existe"""
        if cls.validate_cookies_file(cls.COOKIES_FILE_PATH):
            return str(cls.COOKIES_FILE_PATH)
        return None

    @classmethod
    def read_cookies(cls) -> Optional[str]:
        """Lee el contenido del archivo de cookies"""
        path = cls.get_cookies_path()
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    @staticmethod
    def validate_cookies_file(path: Path) -> bool:
        """Verifica que el archivo de cookies existe y no está vacío"""
        return path.exists() and path.stat().st_size > 0

    @classmethod
    def export_browser_cookies(cls, browser: str = "chrome") -> Optional[str]:
        """
        Exporta cookies desde Chrome o Edge a app/cookies/cookies.txt
        Requiere instalar browser-cookie3
        """
        if browser.lower() == "chrome" and chrome:
            cj = chrome(domain_name='youtube.com')
        elif browser.lower() == "edge" and edge:
            cj = edge(domain_name='youtube.com')
        else:
            logger.warning(f"No se pudo exportar cookies: navegador {browser} no soportado o librería no instalada")
            return None

        output_path = cls.COOKIES_FILE_PATH
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for cookie in cj:
                f.write(f"{cookie.domain}\t{cookie.path}\t{cookie.secure}\t{cookie.expires}\t{cookie.name}\t{cookie.value}\n")

        if cls.validate_cookies_file(output_path):
            logger.info(f"Cookies exportadas correctamente desde {browser} a {output_path}")
            return str(output_path)
        return None
