"""
Threads Video Extractor - Versión mejorada para SnapNosh
"""

import asyncio
import re
import logging
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse
from pathlib import Path

from app.services.base_extractor import BaseExtractor, SnapTubeError
from app.utils.constants import USER_AGENTS
import random

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class ThreadsExtractor(BaseExtractor):
    """
    Extractor mejorado para videos de Threads que:
    - Se integra perfectamente con la arquitectura SnapNosh
    - Obtiene el video real de Threads (no de Instagram CDN)
    - Usa técnicas avanzadas de scraping
    - Maneja múltiples formatos de URL
    """
    
    SUPPORTED_DOMAINS = ["threads.net", "www.threads.net", "threads.com", "www.threads.com"]
    VIDEO_EXTENSIONS = ('.mp4', '.m4v', '.mov', '.webm')
    VIDEO_DOMAINS = ('fbcdn.net', 'cdninstagram.com', 'threads.net')

    def __init__(self, cookies: Optional[str] = None, headless: bool = True, proxy: Optional[str] = None):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.cookies = cookies
        self.headless = headless
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.playwright = None

        if not PLAYWRIGHT_AVAILABLE:
            self.logger.warning(
                "Playwright no está instalado. Para soporte completo de Threads instale con: "
                "pip install playwright && playwright install chromium"
            )

    @property
    def platform(self) -> str:
        return "threads"

    def get_platform_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.threads.net/",
            "Origin": "https://www.threads.net",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _setup_browser(self):
        """Configura el navegador con opciones mejoradas"""
        if not PLAYWRIGHT_AVAILABLE:
            raise SnapTubeError("Playwright es requerido para Threads. Instale con: pip install playwright")

        try:
            self.playwright = await async_playwright().start()
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            }
            
            if self.proxy:
                launch_options['proxy'] = {'server': self.proxy}

            self.browser = await self.playwright.chromium.launch(**launch_options)
        except Exception as e:
            self.logger.error(f"Error al iniciar el navegador: {str(e)}")
            await self._cleanup()
            raise SnapTubeError(f"Error al iniciar el navegador: {str(e)}")

    async def _cleanup(self):
        """Limpia recursos adecuadamente"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.logger.warning(f"Error durante la limpieza: {str(e)}")

    def _normalize_url(self, url: str) -> str:
        """Normaliza URL de Threads"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.replace('threads.net', 'threads.com')

    def _is_threads_video(self, url: str) -> bool:
        """Verifica si la URL es un video real de Threads"""
        return (url and 
                any(ext in url.lower() for ext in self.VIDEO_EXTENSIONS) and
                any(domain in url.lower() for domain in self.VIDEO_DOMAINS))

    async def _extract_video_data(self, url: str) -> Dict[str, Any]:
        """Extrae los datos del video usando técnicas avanzadas"""
        url = self._normalize_url(url)
        context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1920, 'height': 1080},
            storage_state={'cookies': self._parse_cookies()} if self.cookies else None
        )
        
        page = await context.new_page()
        video_urls = []

        try:
            # Interceptar requests de video
            async def handle_response(response):
                content_type = response.headers.get('content-type', '').lower()
                if (self._is_threads_video(response.url) and
                    'video' in content_type):
                    video_urls.append(response.url)

            page.on('response', handle_response)

            # Navegar al post
            await page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Esperar y hacer scroll para cargar contenido dinámico
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            # Extraer video del DOM
            video_element = await page.query_selector('video')
            video_url = await video_element.get_attribute('src') if video_element else None
            thumbnail_url = await video_element.get_attribute('poster') if video_element else None

            # Buscar en el JSON embebido
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                try:
                    content = await script.inner_text()
                    if '"video"' in content:
                        match = re.search(r'"contentUrl":"(https://[^"]+\.mp4[^"]*)"', content)
                        if match and self._is_threads_video(match.group(1)):
                            video_url = match.group(1).replace('\\/', '/')
                except:
                    continue

            # Combinar fuentes de video
            if video_url:
                video_urls.insert(0, video_url)

            if not video_urls:
                raise SnapTubeError("No se encontraron URLs de video válidas")

            # Seleccionar la mejor calidad
            best_url = self._select_best_quality(video_urls)

            return {
                'video_url': best_url,
                'thumbnail_url': thumbnail_url,
                'method': 'playwright'
            }

        except Exception as e:
            self.logger.error(f"Error durante la extracción: {str(e)}")
            raise
        finally:
            await context.close()

    def _parse_cookies(self) -> List[Dict[str, Any]]:
        """Convierte cookies en formato string a lista de diccionarios"""
        if not self.cookies:
            return []
            
        cookies = []
        for line in self.cookies.split(';'):
            parts = line.strip().split('=', 1)
            if len(parts) == 2:
                cookies.append({
                    'name': parts[0],
                    'value': parts[1],
                    'domain': '.threads.net',
                    'path': '/'
                })
        return cookies

    def _select_best_quality(self, video_urls: List[str]) -> str:
        """Selecciona la URL de video con mejor calidad"""
        if not video_urls:
            raise SnapTubeError("No hay URLs de video disponibles")
            
        try:
            return sorted(video_urls, key=lambda x: (
                int(re.search(r'(\d+)p', x, re.I).group(1)) if re.search(r'(\d+)p', x, re.I) else 0
            ), reverse=True)[0]
        except:
            return video_urls[0]

    def _build_response(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Construye la respuesta estándar de SnapNosh"""
        return {
            "status": "success",
            "platform": self.platform,
            "title": "Threads Video",
            "description": "",
            "thumbnail": video_data.get('thumbnail_url', ''),
            "duration": 0,
            "video_url": video_data['video_url'],
            "width": 0,
            "height": 0,
            "uploader": "",
            "uploader_id": "",
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "upload_date": "",
            "method": video_data.get('method', 'playwright'),
            "quality": {
                "resolution": "unknown",
                "fps": 0,
                "bitrate": 0,
                "format": "mp4"
            }
        }

    async def extract(self, url: str, retries: int = 3, **kwargs) -> Dict[str, Any]:
        """Extrae información del video con reintentos"""
        last_error = None
        
        for attempt in range(retries):
            try:
                await self._setup_browser()
                video_data = await self._extract_video_data(url)
                return self._build_response(video_data)
            except Exception as e:
                last_error = e
                self.logger.warning(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Retroceso exponencial
            finally:
                await self._cleanup()
                
        self.logger.error(f"Todos los intentos de extracción fallaron")
        raise SnapTubeError(f"Extracción fallida después de {retries} intentos: {str(last_error)}")

    async def extract_audio_url(self, url: str, **kwargs) -> Dict[str, Any]:
        """Threads no soporta extracción de audio separado"""
        return {
            "status": "error",
            "error": "Threads no permite extracción de audio separado",
            "platform": self.platform
        }