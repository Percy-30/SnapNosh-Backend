from pathlib import Path
from fastapi import APIRouter, Query, Header, HTTPException
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

COOKIES_FILE = Path("app/cookies/cookies.txt")

yt_extractor = YouTubeExtractor(cookies_file=str(COOKIES_FILE) if COOKIES_FILE.exists() else None)
fb_extractor = FacebookExtractor()
tw_extractor = TwitterExtractor()
istg_extractor = InstagramExtractor()
trds_extractor = ThreadsExtractor()
downloader = GenericDownloader()
tk_extractor = TikTokExtractor()

validator = validators.URLValidator()

router = APIRouter()

@router.get("/audio")
async def get_audio_url(
    url: str = Query(..., description="URL del video"),
    cookies: str = Header(None, description="Cookies YouTube, opcional")
):
    """
    Extrae la URL de audio de diferentes plataformas.
    """
    try:
        platform = validator.detect_platform(url)
        print(f"🔍 Plataforma detectada: {platform}")

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
        else:
            raise HTTPException(status_code=400, detail="Plataforma no soportada")
        
        return {"status": "success", "audio_url": audio_url}

    except Exception as e:
        print("❌ Error extrayendo audio:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
