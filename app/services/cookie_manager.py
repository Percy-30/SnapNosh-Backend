import os
from pathlib import Path
import logging
import tempfile

import browser_cookie3

logger = logging.getLogger(__name__)
COOKIES_FILE = Path("app/cookies/cookies.txt")

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
    
    @staticmethod
    def export_browser_cookies(browser: str = "chrome") -> str | None:
        """Intenta exportar cookies del navegador a un archivo temporal."""
        try:
            if browser.lower() == "chrome":
                cj = browser_cookie3.chrome()
            elif browser.lower() == "edge":
                cj = browser_cookie3.edge()
            else:
                return None

            fd, path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for cookie in cj:
                    f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\tFALSE\t0\t{cookie.name}\t{cookie.value}\n")
            return path
        except Exception as e:
            logger.warning(f"No se pudieron exportar cookies de {browser}: {e}")
            return None
