"""
Threads Video Extractor - Versión mejorada para obtener el video real
"""

import asyncio
import re
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

class ThreadsVideoExtractor:
    """
    Extractor mejorado para videos de Threads que:
    - Obtiene el video real de Threads (no de Instagram CDN)
    - Usa técnicas avanzadas de scraping
    - Maneja múltiples formatos de URL
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def __aenter__(self):
        await self._setup_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()
    
    async def _setup_browser(self):
        """Configura el navegador con opciones mejoradas"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright no está instalado")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
    
    async def _cleanup(self):
        """Limpia recursos adecuadamente"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def _normalize_url(self, url: str) -> str:
        """Normaliza URL de Threads"""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.replace('threads.net', 'threads.com')
    
    async def get_video_url(self, post_url: str) -> Dict[str, Any]:
        """
        Obtiene la URL real del video de Threads
        
        Args:
            post_url: URL del post de Threads
            
        Returns:
            Dict con estructura:
            {
                'success': bool,
                'video_url': Optional[str],  # URL directa del video
                'thumbnail_url': Optional[str],
                'error': Optional[str]
            }
        """
        try:
            post_url = self._normalize_url(post_url)
            context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # Interceptar requests de video
            video_urls = []
            async def handle_response(response):
                if 'video' in response.url or '.mp4' in response.url:
                    if 'threads' in response.url or 'fbcdn' in response.url:
                        video_urls.append(response.url)
            
            page.on('response', handle_response)
            
            # Navegar al post
            await page.goto(post_url, wait_until='networkidle', timeout=60000)
            
            # Esperar y hacer scroll para cargar contenido dinámico
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            # Extraer video principal
            video_element = await page.query_selector('video')
            if video_element:
                video_src = await video_element.get_attribute('src')
                if video_src and self._is_threads_video(video_src):
                    return {
                        'success': True,
                        'video_url': video_src,
                        'thumbnail_url': await video_element.get_attribute('poster'),
                        'error': None
                    }
            
            # Buscar en el JSON embebido
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                try:
                    content = await script.inner_text()
                    if '"video"' in content:
                        match = re.search(r'"contentUrl":"(https://[^"]+\.mp4[^"]*)"', content)
                        if match and self._is_threads_video(match.group(1)):
                            return {
                                'success': True,
                                'video_url': match.group(1).replace('\\/', '/'),
                                'thumbnail_url': None,
                                'error': None
                            }
                except:
                    continue
            
            # Si no se encontró, usar las URLs interceptadas
            if video_urls:
                return {
                    'success': True,
                    'video_url': video_urls[0],
                    'thumbnail_url': None,
                    'error': None
                }
            
            raise Exception("No se pudo encontrar el video en el post")
            
        except Exception as e:
            logger.error(f"Error obteniendo video: {str(e)}")
            return {
                'success': False,
                'video_url': None,
                'thumbnail_url': None,
                'error': str(e)
            }
        finally:
            await context.close()
    
    def _is_threads_video(self, url: str) -> bool:
        """Verifica si la URL es un video real de Threads"""
        return (url and 
                any(ext in url.lower() for ext in ['.mp4', '.m4v']) and
                any(domain in url.lower() for domain in ['threads.com', 'threads.net', 'fbcdn.net']))


# Función de conveniencia mejorada
async def get_real_threads_video(post_url: str) -> Dict[str, Any]:
    """
    Obtiene el video real de un post de Threads
    
    Args:
        post_url: URL del post (puede ser threads.com o threads.net)
        
    Returns:
        {
            'success': bool,
            'video_url': str,  # URL directa del video MP4
            'thumbnail_url': str,  # URL de la miniatura (si está disponible)
            'error': str  # Mensaje de error si success=False
        }
    """
    async with ThreadsVideoExtractor(headless=True) as extractor:
        return await extractor.get_video_url(post_url)


# Ejemplo de uso
async def main():
    url = "https://www.threads.com/@n.mas/post/DNLck5IgKNG"
    result = await get_real_threads_video(url)
    
    if result['success']:
        print("✅ Video encontrado:")
        print(f"URL directa: {result['video_url']}")
        if result['thumbnail_url']:
            print(f"Miniatura: {result['thumbnail_url']}")
    else:
        print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())