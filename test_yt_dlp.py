"""
Threads Best Video URL Extractor - Playwright
Devuelve la URL del video de mayor calidad automáticamente.
"""

import asyncio
import re
import time
import logging
from typing import List, Optional
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright no está instalado. Instala con: pip install playwright")
    print("⚠️ Después ejecuta: playwright install chromium")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VideoInfo:
    url: str
    quality_tag: Optional[int] = None  # Extraído de mXX, por ejemplo m86 -> 86

class ThreadsBestVideoExtractor:
    def __init__(self, url: str, headless: bool = True):
        self.url = self._normalize_url(url)
        self.headless = headless
        self.browser: Browser = None
        self.playwright: Playwright = None
        self.video_urls: List[VideoInfo] = []

        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright es requerido. Instala con: pip install playwright && playwright install chromium")

    def _normalize_url(self, url: str) -> str:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url = url.replace('threads.net', 'threads.com')
        return url

    async def __aenter__(self):
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def _setup_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        logger.info("🌐 Navegador configurado")

    async def _cleanup(self):
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.warning(f"Warning during cleanup: {e}")

    async def _intercept_requests(self, page: Page):
        async def handle_request(request):
            url = request.url
            if any(domain in url for domain in ['fbcdn.net', 'cdninstagram.com', 'instagram.com']):
                if '.mp4' in url:
                    quality_tag = self._extract_quality_tag(url)
                    self.video_urls.append(VideoInfo(url=url, quality_tag=quality_tag))
                    logger.info(f"🎯 Video URL interceptada: {url[:100]}... | m{quality_tag}")
        page.on("request", handle_request)

    def _extract_quality_tag(self, url: str) -> Optional[int]:
        match = re.search(r'/m(\d+)', url)
        if match:
            return int(match.group(1))
        return None

    async def get_best_video_url(self) -> Optional[str]:
        if not self.browser:
            raise RuntimeError("Browser no está configurado")

        context = await self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        await self._intercept_requests(page)
        logger.info(f"🔗 Navegando a: {self.url}")
        response = await page.goto(self.url, wait_until='networkidle', timeout=30000)
        if not response or response.status >= 400:
            raise Exception(f"Error HTTP {response.status if response else 'unknown'}")

        # Esperar a que cargue y scrolleamos un poco
        await page.wait_for_timeout(3000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        # Seleccionar la mejor URL por quality_tag
        if not self.video_urls:
            raise Exception("No se encontró URL de video")

        best_video = max(
            self.video_urls,
            key=lambda v: v.quality_tag if v.quality_tag is not None else 0
        )
        logger.info(f"🏆 Mejor video seleccionado: m{best_video.quality_tag}")
        await context.close()
        return best_video.url

# Función helper
async def get_threads_best_video_url(url: str, headless: bool = True) -> str:
    async with ThreadsBestVideoExtractor(url, headless=headless) as extractor:
        return await extractor.get_best_video_url()


# CLI
async def main():
    import sys
    if len(sys.argv) < 2:
        print("Uso: python threads_best_video.py <URL> [--visible]")
        sys.exit(1)

    url = sys.argv[1]
    headless = '--visible' not in sys.argv
    print(f"🔗 URL: {url}")
    print(f"🎭 Modo: {'Headless' if headless else 'Visible'}")

    try:
        best_url = await get_threads_best_video_url(url, headless)
        print(f"\n🎯 Mejor video encontrado:\n{best_url}")
    except Exception as e:
        logger.error(f"💥 Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
