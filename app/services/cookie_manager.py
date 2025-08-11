import os
import json
import sqlite3
import platform
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class CookieManager:
    """Gestor de cookies para yt-dlp desde navegadores o archivos"""
    
    def __init__(self):
        self.system = platform.system()
        
    def get_browser_cookies_path(self, browser: str) -> Optional[Path]:
        """Obtiene la ruta de cookies del navegador según el sistema operativo"""
        paths = {
            "Windows": {
                "chrome": Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Cookies",
                "firefox": Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles",
                "edge": Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
            },
            "Darwin": {  # macOS
                "chrome": Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
                "firefox": Path.home() / "Library/Application Support/Firefox/Profiles",
                "safari": Path.home() / "Library/Cookies/Cookies.binarycookies"
            },
            "Linux": {
                "chrome": Path.home() / ".config/google-chrome/Default/Cookies",
                "firefox": Path.home() / ".mozilla/firefox"
            }
        }
        
        if self.system not in paths or browser.lower() not in paths[self.system]:
            return None
            
        return paths[self.system][browser.lower()]
    
    def extract_chrome_cookies(self, cookies_path: Path) -> List[Dict]:
        """Extrae cookies de Chrome/Edge"""
        cookies = []
        try:
            conn = sqlite3.connect(str(cookies_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
                FROM cookies
                WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google%'
            """)
            
            for row in cursor.fetchall():
                cookies.append({
                    'domain': row[0],
                    'name': row[1],
                    'value': row[2],
                    'path': row[3],
                    'expires': row[4],
                    'secure': bool(row[5]),
                    'httpOnly': bool(row[6])
                })
            
            conn.close()
            logger.info(f"Extraídas {len(cookies)} cookies de Chrome")
            
        except Exception as e:
            logger.error(f"Error extrayendo cookies de Chrome: {e}")
            
        return cookies
    
    def create_netscape_cookies_file(self, cookies: List[Dict], output_path: Path):
        """Crea un archivo de cookies en formato Netscape para yt-dlp"""
        try:
            with open(output_path, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This file contains the http cookies needed for YouTube\n\n")
                
                for cookie in cookies:
                    # Formato Netscape: domain, domain_specified, path, secure, expires, name, value
                    domain_specified = "TRUE" if cookie['domain'].startswith('.') else "FALSE"
                    secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                    expires = str(cookie.get('expires', 0))
                    
                    line = f"{cookie['domain']}\t{domain_specified}\t{cookie['path']}\t{secure}\t{expires}\t{cookie['name']}\t{cookie['value']}\n"
                    f.write(line)
            
            logger.info(f"Archivo de cookies creado: {output_path}")
            
        except Exception as e:
            logger.error(f"Error creando archivo de cookies: {e}")
    
    def export_browser_cookies(self, browser: str, output_path: Path) -> bool:
        """Exporta cookies del navegador especificado"""
        try:
            cookies_path = self.get_browser_cookies_path(browser)
            if not cookies_path or not cookies_path.exists():
                logger.error(f"No se encontraron cookies para {browser}")
                return False
            
            if browser.lower() in ['chrome', 'edge']:
                cookies = self.extract_chrome_cookies(cookies_path)
            else:
                logger.error(f"Navegador {browser} no soportado aún")
                return False
            
            if cookies:
                self.create_netscape_cookies_file(cookies, output_path)
                return True
            
        except Exception as e:
            logger.error(f"Error exportando cookies de {browser}: {e}")
            
        return False
    
    def create_sample_cookies_file(self, output_path: Path):
        """Crea un archivo de cookies de ejemplo"""
        sample_content = """# Netscape HTTP Cookie File
# Coloca aquí tus cookies de YouTube en formato Netscape
# Puedes obtenerlas usando extensiones del navegador como "Get cookies.txt"
#
# Formato: domain	domain_specified	path	secure	expires	name	value
#
# Ejemplo:
# .youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	ejemplo_valor
# .youtube.com	TRUE	/	TRUE	1735689600	LOGIN_INFO	ejemplo_login
"""
        
        try:
            with open(output_path, 'w') as f:
                f.write(sample_content)
            logger.info(f"Archivo de cookies de ejemplo creado: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error creando archivo de ejemplo: {e}")
            return False
    
    def validate_cookies_file(self, cookies_path: Path) -> bool:
        """Valida si el archivo de cookies es válido"""
        try:
            if not cookies_path.exists():
                return False
                
            with open(cookies_path, 'r') as f:
                content = f.read()
                
            # Verificar que tenga al menos una línea de cookie válida
            lines = content.strip().split('\n')
            valid_lines = 0
            
            for line in lines:
                if line.startswith('#') or not line.strip():
                    continue
                    
                parts = line.split('\t')
                if len(parts) >= 7:
                    valid_lines += 1
            
            logger.info(f"Cookies válidas encontradas: {valid_lines}")
            return valid_lines > 0
            
        except Exception as e:
            logger.error(f"Error validando cookies: {e}")
            return False
        
    def auto_export_cookies(self, browser: str = "chrome") -> bool:
        """
        Intenta exportar cookies automáticamente del navegador especificado
        y guarda el archivo en la ruta de cookies configurada.
        """
        from app.config import settings

        output_path = settings.COOKIES_DIR / "cookies.txt"
        success = self.export_browser_cookies(browser, output_path)
        return success