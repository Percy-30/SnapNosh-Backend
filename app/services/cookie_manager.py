import os
from pathlib import Path
import logging

COOKIES_FILE = Path("app/cookies/cookies.txt")
logger = logging.getLogger(__name__)

class CookieManager:
    """Gestión centralizada de cookies de YouTube en formato Netscape"""

    @staticmethod
    def cookies_are_valid() -> bool:
        """Verifica si el archivo de cookies existe y no está vacío"""
        return COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0

    @staticmethod
    def get_cookies_path() -> str:
        """Devuelve la ruta absoluta del archivo de cookies"""
        return str(COOKIES_FILE.resolve())

    @staticmethod
    def read_cookies() -> str:
        """Lee y devuelve el contenido del archivo de cookies"""
        if CookieManager.cookies_are_valid():
            return COOKIES_FILE.read_text(encoding="utf-8")
        return ""
