# ====================================================================
# app/main.py
# ====================================================================
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routes.video_routes import router as video_router
from app.services import SnapTubeError

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 SnapTube API starting up...")
    
    # Create necessary directories
    settings.TEMP_DIR.mkdir(exist_ok=True)
    settings.COOKIES_DIR.mkdir(exist_ok=True)
    
    # Start background cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    logger.info("✅ SnapTube API ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 SnapTube API shutting down...")
    cleanup_task.cancel()
    await cleanup_temp_files()
    logger.info("👋 Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(video_router)

# Root endpoint
@app.get("/", response_class=JSONResponse)
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "operational",
        "documentation": "/docs" if settings.DEBUG else "Contact administrator",
        "endpoints": {
            "extract": "/api/v1/extract",
            "download": "/api/v1/download", 
            "stream": "/api/v1/stream",
            "platforms": "/api/v1/platforms"
        }
    }

# Exception handlers
@app.exception_handler(SnapTubeError)
async def snaptube_exception_handler(request: Request, exc: SnapTubeError):
    """Handle SnapTube specific errors"""
    return JSONResponse(
        status_code=400,
        content={
            "status": "error", 
            "message": str(exc), 
            "type": "SnapTubeError"
        }
    )

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors"""
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
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "status": "error", 
            "message": "Endpoint not found",
            "available_endpoints": ["/api/v1/extract", "/api/v1/download", "/api/v1/stream"]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error", 
            "message": "Internal server error",
            "type": "InternalError"
        }
    )

# Background tasks
async def periodic_cleanup():
    """Periodic cleanup of temporary files"""
    while True:
        try:
            await cleanup_temp_files()
            await asyncio.sleep(1800)  # Every 30 minutes
        except Exception as e:
            logger.error(f"💥 Periodic cleanup error: {str(e)}")
            await asyncio.sleep(3600)  # Wait longer on error

async def cleanup_temp_files():
    """Clean up old temporary files"""
    try:
        current_time = asyncio.get_event_loop().time()
        cleaned = 0
        
        for filepath in settings.TEMP_DIR.glob("*"):
            if filepath.is_file():
                # Check file age
                file_age = current_time - filepath.stat().st_mtime
                if file_age > settings.CLEANUP_INTERVAL:
                    filepath.unlink()
                    cleaned += 1
        
        if cleaned > 0:
            logger.info(f"🗑️ Cleaned up {cleaned} temporary files")
            
    except Exception as e:
        logger.error(f"⚠️ Cleanup error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        access_log=True,
        log_level=settings.LOG_LEVEL.lower()
    )
