# ====================================================================
# app/main.py
# ====================================================================
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.limits import limiter

from app.config import settings
from app.routes.video_routes import router as video_router
#from app.routes import audio_routes
from app.routes.audio_routes import router as audio_router
from app.routes.cookies_routes import router as cookies_router
from app.routes.download_routes import router as download_router
from app.services.base_extractor import SnapTubeError
from app.services.youtube_cookie_updater import login_youtube_and_save_cookies
from app.cookies.check_cookies import cookies_are_valid  # Adaptado al formato Netscape

# ==========================================================
# LOGGING CONFIG
# ==========================================================
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# ==========================================================
# COOKIES MANAGEMENT
# ==========================================================
_last_cookie_update_attempt = None

def ensure_valid_cookies(force: bool = False) -> bool:
    """Verifica y actualiza cookies si es necesario."""
    global _last_cookie_update_attempt

    # Evita intentos demasiado seguidos (1 min de espera mínimo)
    if not force and _last_cookie_update_attempt and (datetime.now() - _last_cookie_update_attempt).seconds < 60:
        logger.warning("⏳ Último intento de actualización de cookies fue hace menos de 1 min. Saltando...")
        return False

    _last_cookie_update_attempt = datetime.now()

    if force or not cookies_are_valid():
        logger.warning("⚠️ Cookies inválidas o ausentes. Intentando regenerar...")
        try:
            login_youtube_and_save_cookies()
            return cookies_are_valid()
        except Exception as e:
            logger.error(f"💥 Error regenerando cookies: {str(e)}", exc_info=True)
            return False
    return True

# ==========================================================
# APP LIFESPAN
# ==========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown"""
    logger.info("🚀 SnapNosh API starting up...")

    # Crear directorios necesarios
    settings.TEMP_DIR.mkdir(exist_ok=True)
    settings.COOKIES_DIR.mkdir(exist_ok=True)
    settings.YOUTUBE_COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Verificar cookies al iniciar
    if not ensure_valid_cookies():
        logger.error("🚨 No se pudieron generar cookies al iniciar. El API puede fallar en peticiones a YouTube.")

    # Tarea en segundo plano para limpieza
    cleanup_task = asyncio.create_task(periodic_cleanup())

    logger.info("✅ SnapNosh API ready!")
    yield

    logger.info("🛑 SnapNosh API shutting down...")
    cleanup_task.cancel()
    await cleanup_temp_files()
    logger.info("👋 Shutdown complete")

# ==========================================================
# FASTAPI APP
# ==========================================================
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Rate Limiter Middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
#app.include_router(video_router, prefix="/api/v1", tags=["video"])
#app.include_router(cookies_router, prefix="/api/v1", tags=["cookies"])
#app.include_router(download_router, prefix="/api/v1", tags=["download"])
#app.include_router(video_router) #cookies_routes
app.include_router(video_router)
app.include_router(cookies_router, prefix="/api") 
app.include_router(download_router, prefix="/api/v1")
app.include_router(audio_router)
app.include_router(audio_router, prefix="/api/v1")
# ==========================================================
# ROOT
# ==========================================================
@app.get("/", response_class=JSONResponse)
async def root():
    """API Status"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "operational",
        "documentation": "/docs" if settings.DEBUG else "Contact administrator",
        "endpoints": {
            "extract": "/api/v1/extract",
            "download": "/api/v1/download",
            "stream": "/api/v1/stream",
            "audio": "/api/v1/audio",
            "platforms": "/api/v1/platforms"
        }
    }

# ==========================================================
# COOKIES CHECK
# ==========================================================
@app.get("/check-cookies")
async def check_cookies():
    path = Path(settings.YOUTUBE_COOKIES_PATH)
    return {"exists": path.exists(), "path": str(path.resolve())}

@app.get("/debug/cookies")
async def debug_cookies():
    path = settings.YOUTUBE_COOKIES_PATH
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(500)
        return {"path": str(path), "content_preview": content}
    return {"error": "Archivo no encontrado", "path": str(path)}

# ==========================================================
# EXCEPTION HANDLERS
# ==========================================================
@app.exception_handler(SnapTubeError)
async def snaptube_exception_handler(request: Request, exc: SnapTubeError):
    """Handle SnapTube errors"""
    error_text = str(exc).lower()
    if any(keyword in error_text for keyword in ["cookies", "signin", "login", "auth"]):
        logger.warning("🔄 Error de cookies detectado. Intentando actualización automática...")
        if ensure_valid_cookies(force=True):
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Cookies actualizadas, intente nuevamente."}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "No se pudo actualizar cookies automáticamente."}
            )
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": str(exc), "type": "SnapTubeError"}
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Rate limit exceeded"""
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "message": f"Rate limit exceeded: {exc.detail}",
            "type": "RateLimitError"
        }
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Not found"""
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "message": "Endpoint not found",
            "available_endpoints": ["/api/v1/extract", "/api/v1/download", "/api/v1/stream", "/api/v1/audio"]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Internal server error"""
    logger.error(f"Internal server error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error", "type": "InternalError"}
    )

# ==========================================================
# BACKGROUND TASKS
# ==========================================================
async def periodic_cleanup():
    """Clean temporary files periodically"""
    while True:
        try:
            await cleanup_temp_files()
            await asyncio.sleep(1800)  # 30 min
        except Exception as e:
            logger.error(f"💥 Periodic cleanup error: {str(e)}")
            await asyncio.sleep(3600)

async def cleanup_temp_files():
    """Remove old temporary files"""
    try:
        current_time = asyncio.get_event_loop().time()
        cleaned = 0
        for filepath in settings.TEMP_DIR.glob("*"):
            if filepath.is_file():
                file_age = current_time - filepath.stat().st_mtime
                if file_age > settings.CLEANUP_INTERVAL:
                    filepath.unlink()
                    cleaned += 1
        if cleaned > 0:
            logger.info(f"🗑️ Cleaned {cleaned} temporary files")
    except Exception as e:
        logger.error(f"⚠️ Cleanup error: {str(e)}")

# ==========================================================
# MAIN ENTRY
# ==========================================================
if __name__ == "__main__":
    logger.info("🚀 Iniciando SnapTube-Like API...")
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        access_log=True,
        log_level=settings.LOG_LEVEL.lower()
    )
