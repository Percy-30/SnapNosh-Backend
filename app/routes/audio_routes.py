# ====================================================================
# app/routes/audio_routes.py
# ====================================================================
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from app.utils import validators
from app.services.generic_downloader import GenericDownloader
from app.services.tiktok_service import TikTokExtractor
from app.services.facebook_service import FacebookExtractor
from app.services.twitter_service import TwitterExtractor
from app.services.instagram_service import InstagramExtractor
from app.services.threads_service import ThreadsExtractor
from app.services.youtube_service import YouTubeExtractor
from app.services.base_extractor import SnapTubeError
import traceback

# Initialize APIRouter
logger = logging.getLogger(__name__)
router = APIRouter()


# Define the path to the cookies file
COOKIES_FILE = Path("app/cookies/cookies.txt")

# Initialize extractors and downloader
yt_extractor = YouTubeExtractor(cookies_file=str(COOKIES_FILE) if COOKIES_FILE.exists() else None)
fb_extractor = FacebookExtractor()
tw_extractor = TwitterExtractor()
istg_extractor = InstagramExtractor()
trds_extractor = ThreadsExtractor()
downloader = GenericDownloader()
tk_extractor = TikTokExtractor()

# Initialize URL validator and logger
validator = validators.URLValidator()


@router.get("/audio")
async def get_audio_url(
    url: str = Query(..., description="URL del video")
):
    """
    Extrae la URL de audio de diferentes plataformas.
    """
    try:
        # Detect the platform from the URL
        platform = validator.detect_platform(url)
        print(f"🔍 Plataforma detectada: {platform}")

        # Based on the detected platform, call the appropriate extractor
        if platform == "youtube":
            audio_url = await yt_extractor.extract_audio_url(url)
        elif platform == "facebook":
            audio_url = await fb_extractor.extract_audio_url_with_fallback(url)
        elif platform == "twitter":
            audio_url = await tw_extractor.extract_audio_url_with_fallback(url)
        elif platform == "instagram":
            audio_url = await istg_extractor.extract_audio_url_with_fallback(url)
        elif platform == "tiktok":
            audio_url = await tk_extractor.extract_audio_url_with_fallback(url)
        elif platform == "threads":
            audio_url = await trds_extractor.extract_audio_url_with_fallback(url)
        else:
            raise HTTPException(status_code=400, detail="Plataforma no soportada")
        
        # Return the success response
        return {"status": "success", "audio_url": audio_url}

    except SnapTubeError as e:
        # Catch specific SnapTube errors for better handling
        logger.error(f"❌ Error de SnapTube extrayendo audio: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Catch any other unexpected errors and provide a generic message
        print("❌ Error extrayendo audio:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Ocurrió un error inesperado al procesar la solicitud.")
