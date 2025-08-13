# ====================================================================
# app/services/threads_service.py
# ====================================================================

import sys
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

# Ajuste para Windows (evita NotImplementedError con subprocess en asyncio)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class ThreadsVideo:
    """Modelo simplificado para URL de video de Threads"""
    url: str
    quality: str = "unknown"

class ThreadsService:
    """Servicio para extraer URL de video de Threads usando Playwright"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None
        self.video_urls: list[str] = []

        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright no está instalado. Ejecuta: pip install playwright && playwright install chromium"
            )

    async def __aenter__(self):
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def _setup_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        logger.info("🌐 Navegador Playwright configurado")

    async def _cleanup(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    def _normalize_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        url = url.replace("threads.net", "threads.com")
        return url

    async def _intercept_requests(self, page: Page):
        async def handle_request(request):
            url = request.url
            if any(pattern in url for pattern in [".mp4", "video"]):
                if any(domain in url for domain in ["fbcdn.net", "cdninstagram.com", "instagram.com"]):
                    logger.info(f"🎯 Video URL interceptada: {url[:100]}...")
                    self.video_urls.append(url)
        page.on("request", handle_request)

    async def get_best_video_url(self, post_url: str) -> str:
        """Devuelve la URL directa del mejor video de un post de Threads"""
        if not self.browser:
            raise RuntimeError("Browser no está configurado")
        self.video_urls.clear()

        normalized_url = self._normalize_url(post_url)
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await self._intercept_requests(page)

        try:
            logger.info(f"🔗 Navegando a: {normalized_url}")
            response = await page.goto(normalized_url, wait_until="networkidle", timeout=30000)
            if not response or response.status >= 400:
                raise Exception(f"Error HTTP {response.status if response else 'unknown'}")

            # Esperar contenido y hacer scroll
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            if not self.video_urls:
                raise Exception("❌ No se encontró URL de video")

            best_url = self.video_urls[0]
            logger.info(f"🎯 Mejor video encontrado: {best_url}")
            return best_url

        finally:
            await context.close()


# Función helper para FastAPI u otros servicios
async def get_threads_video_url(post_url: str, headless: bool = True) -> str:
    async with ThreadsService(headless=headless) as service:
        return await service.get_best_video_url(post_url)


# --------------------------------------------------------------------
# WRAPPER COMPATIBLE CON SnapTubeService
# --------------------------------------------------------------------
class ThreadsExtractor:
    """Wrapper para SnapTubeService, compatible con SnapTubeService.extract_video"""
    async def extract(self, url: str, **kwargs) -> dict:
        video_url = await get_threads_video_url(url, headless=kwargs.get("headless", True))
        return {
            "video_url": video_url,
            "title": "Threads Video",
            "platform": "threads",
            "method": "ThreadsService",
            "formats": [{"format_id": "best", "ext": "mp4", "url": video_url}]
        }


# --------------------------------------------------------------------
# Ejemplo de prueba independiente
# --------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Uso: python threads_service.py <THREADS_POST_URL>")
            return
        url = sys.argv[1]
        video_url = await get_threads_video_url(url)
        print(f"\n🎯 Mejor URL de video:\n{video_url}")

    asyncio.run(main())
