from fastapi import APIRouter, Query, HTTPException, Request, BackgroundTasks, Header
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from typing import Optional
import asyncio
import random
import re
import uuid
import yt_dlp
import logging
from pathlib import Path
import requests
from fastapi import Request

from app.config import settings
from app.services.snapnosh_service import EnhancedSnapNoshConverter
from app.utils.constants import QUALITY_FORMATS, USER_AGENTS
from app.services.base_extractor import SnapTubeError
from app.limits import limiter
from app.tasks import cleanup_file

logger = logging.getLogger(__name__)
router = APIRouter()

def select_format(formats, only_audio, desired_quality):
    """
    Selecciona el formato más adecuado según only_audio y calidad deseada.
    """
    if only_audio:
        # Formatos solo audio
        audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
        if not audio_formats:
            raise ValueError("No audio-only formats found")
        audio_formats.sort(key=lambda f: f.get('abr', 0), reverse=True)
        return audio_formats[0]['format_id']
    else:
        # Formatos video+audio
        video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
        if not video_formats:
            raise ValueError("No video+audio formats found")
        def get_height(fmt):
            h = fmt.get('height')
            if h is not None:
                return h
            # fallback
            fnote = fmt.get('format_note', '')
            m = re.search(r'(\d+)p', fnote)
            if m:
                return int(m.group(1))
            return 0

        desired_height = int(re.findall(r'(\d+)', desired_quality)[0]) if re.findall(r'(\d+)', desired_quality) else 720
        selected_fmt = None
        max_height = 0
        for fmt in video_formats:
            h = get_height(fmt)
            if h <= desired_height and h > max_height:
                max_height = h
                selected_fmt = fmt
        if not selected_fmt:
            selected_fmt = max(video_formats, key=get_height)
        return selected_fmt['format_id']


@router.get("/download")
@limiter.limit(settings.RATE_LIMIT_DOWNLOAD)
async def download_video(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Video URL"),
    quality: str = Query("720p", description="Video quality"),
    only_audio: bool = Query(False, description="Download audio only"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    try:
        logger.info(f"⬇️ Download request: URL={url} only_audio={only_audio} quality={quality}")

        video_info = await EnhancedSnapNoshConverter.extract_video(url=url, mobile=mobile, cookies=cookies)
        if 'formats' not in video_info or not video_info['formats']:
            raise HTTPException(status_code=400, detail="No formats found for video")

        format_id = select_format(video_info['formats'], only_audio, quality)

        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_info.get('title', 'video'))[:50]
        ext = 'mp3' if only_audio else 'mp4'
        filename = f"{video_info['platform']}_{safe_title}_{uuid.uuid4()}.{ext}"
        filepath = Path(settings.TEMP_DIR) / filename

        ydl_opts = {
            'outtmpl': str(filepath),
            'format': format_id,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }] if only_audio else [],
            'http_headers': {
                'User-Agent': random.choice(USER_AGENTS),
                'Referer': f"https://www.{video_info['platform']}.com/"
            },
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'noplaylist': True,
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        if not filepath.exists():
            raise HTTPException(status_code=500, detail="Download failed")

        background_tasks.add_task(cleanup_file, str(filepath))
        media_type = 'audio/mpeg' if only_audio else 'video/mp4'

        return FileResponse(path=str(filepath), filename=filename, media_type=media_type)

    except SnapTubeError as e:
        logger.warning(f"SnapTubeError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error during download:")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.get("/thumbnail")
@limiter.limit("20/minute")
async def get_thumbnail(
    request: Request,  # <-- agregas esto
    url: str = Query(..., description="Video URL"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    """
    Devuelve la miniatura del video (redirige a la URL de la imagen).
    """
    try:
        video_info = await EnhancedSnapNoshConverter.extract_video(url=url, mobile=mobile, cookies=cookies)
        thumbnail_url = video_info.get('thumbnail')
        if not thumbnail_url:
            raise HTTPException(status_code=404, detail="Thumbnail not found")

        # Para evitar descargar la imagen, hacemos redirect a la URL directa
        return RedirectResponse(thumbnail_url)

    except SnapTubeError as e:
        logger.warning(f"SnapTubeError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching thumbnail:")
        raise HTTPException(status_code=500, detail=f"Failed to get thumbnail: {str(e)}")


@router.get("/formats")
@limiter.limit("30/minute")
async def get_formats(
    request: Request,  # <-- agregas esto
    url: str = Query(..., description="Video URL"),
    mobile: bool = Query(False, description="Use mobile user agent"),
    cookies: Optional[str] = Header(None, description="Cookies for YouTube")
):
    """
    Lista formatos y calidades disponibles para un video.
    """
    try:
        video_info = await EnhancedSnapNoshConverter.extract_video(url=url, mobile=mobile, cookies=cookies)
        formats = video_info.get('formats', [])
        qualities = []
        for f in formats:
            # filtrar solo formatos con video o audio válido
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                # audio-only
                desc = f"Audio - {f.get('abr', 'unknown')} kbps"
            elif f.get('vcodec') != 'none':
                # video+audio or video-only
                height = f.get('height') or re.search(r'(\d+)p', f.get('format_note', '') or '') and int(re.search(r'(\d+)p', f.get('format_note')).group(1)) or 'unknown'
                desc = f"Video - {height}p"
            else:
                continue

            qualities.append({
                'format_id': f['format_id'],
                'description': desc,
                'ext': f.get('ext', 'unknown'),
                'filesize': f.get('filesize') or f.get('filesize_approx'),
            })

        return JSONResponse({
            "status": "success",
            "platform": video_info.get('platform'),
            "title": video_info.get('title'),
            "available_formats": qualities,
            "recommended_quality": "720p"
        })

    except SnapTubeError as e:
        logger.warning(f"SnapTubeError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error fetching formats:")
        raise HTTPException(status_code=500, detail=f"Failed to get formats: {str(e)}")