import asyncio
from typing import List, Dict, Any, Optional
import re

import yt_dlp
from app.models.video_models import VideoInfo, VideoFormat, SnaptubeVideoInfo, DownloadOption, SearchResult, TrendingVideo
from app.services.threads_service import get_threads_video_url

class EnhancedSnapNoshConverter:
    @staticmethod
    def format_filesize(bytes_size: Optional[int]) -> str:
        if not bytes_size:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"~{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"~{bytes_size:.1f}TB"

    @staticmethod
    def get_quality_label(resolution: str, fps: Optional[float] = None) -> str:
        if not resolution:
            return "Unknown"
        height_match = re.search(r'(\d+)p?$', resolution)
        if height_match:
            height = int(height_match.group(1))
            label = f"{height}p"
            if fps and fps > 30:
                label += f" {int(fps)}fps"
            return label
        return resolution

    @staticmethod
    def generate_smart_download_options(video_info: VideoInfo) -> List[DownloadOption]:
        options = []
        seen_qualities = set()

        video_formats = [f for f in video_info.formats if f.vcodec and f.vcodec != 'none']
        video_formats.sort(key=lambda x: x.quality or 0, reverse=True)

        for fmt in video_formats:
            if not fmt.resolution:
                continue
            quality_label = EnhancedSnapNoshConverter.get_quality_label(fmt.resolution, fmt.fps)
            if quality_label in seen_qualities:
                continue
            seen_qualities.add(quality_label)

            size_estimate = "Unknown"
            if fmt.filesize:
                size_estimate = EnhancedSnapNoshConverter.format_filesize(fmt.filesize)
            elif video_info.duration:
                size_estimate = EnhancedSnapNoshConverter.estimate_filesize(video_info.duration, quality_label, "video")

            recommended = "720p" in quality_label

            options.append(DownloadOption(
                type="video",
                quality=quality_label,
                format=fmt.ext,
                size_estimate=size_estimate,
                recommended=recommended,
                format_id=fmt.format_id,
                actual_filesize=fmt.filesize
            ))

        # Opciones de audio
        audio_qualities = [
            ("High Quality", "192K"),
            ("Standard", "128K"),
            ("Low Quality", "96K")
        ]

        for i, (quality_name, bitrate) in enumerate(audio_qualities):
            size_estimate = "Unknown"
            if video_info.duration:
                size_estimate = EnhancedSnapNoshConverter.estimate_filesize(video_info.duration, quality_name.lower(), "audio")

            options.append(DownloadOption(
                type="audio",
                quality=f"{quality_name} ({bitrate})",
                format="mp3",
                size_estimate=size_estimate,
                recommended=(i == 1)
            ))

        return options

    @staticmethod
    def estimate_filesize(duration: int, quality: str, format_type: str) -> str:
        if not duration:
            return "Unknown"
        rates = {
            "video": {
                "2160p": 15.0,
                "1440p": 10.0,
                "1080p": 8.0,
                "720p": 5.0,
                "480p": 3.0,
                "360p": 2.0,
                "240p": 1.0,
                "144p": 0.5
            },
            "audio": {
                "high": 1.5,
                "standard": 1.0,
                "low": 0.6
            }
        }
        minutes = duration / 60
        if format_type == "video":
            height_match = re.search(r'(\d+)p', quality.lower())
            if height_match:
                height = height_match.group(1) + "p"
                rate = rates["video"].get(height, 3.0)
            else:
                rate = 3.0
        else:
            quality_key = quality.lower().split()[0]
            rate = rates["audio"].get(quality_key, 1.0)
        estimated_mb = minutes * rate
        if estimated_mb < 1:
            return f"~{int(estimated_mb * 1024)}KB"
        elif estimated_mb < 1024:
            return f"~{int(estimated_mb)}MB"
        else:
            return f"~{estimated_mb/1024:.1f}GB"

    @staticmethod
    def enhance_video_info(video_info: VideoInfo) -> SnaptubeVideoInfo:
        best_thumbnail = None
        if video_info.thumbnails:
            sorted_thumbs = sorted(
                video_info.thumbnails,
                key=lambda x: abs((x.width or 480) - 480) if x.width else 999
            )
            best_thumbnail = sorted_thumbs[0].url

        description = None
        if video_info.description:
            description = (video_info.description[:150] + "...") if len(video_info.description) > 150 else video_info.description

        thumbnails_data = []
        for thumb in video_info.thumbnails[:8]:
            thumbnails_data.append({
                "url": thumb.url,
                "width": thumb.width,
                "height": thumb.height,
                "resolution": f"{thumb.width}x{thumb.height}" if thumb.width and thumb.height else None
            })

        return SnaptubeVideoInfo(
            id=None,
            title=video_info.title,
            description=description,
            duration=video_info.duration,
            duration_string=video_info.duration_string,
            view_count=video_info.view_count,
            uploader=video_info.uploader or "Unknown Uploader",
            upload_date=video_info.upload_date,
            thumbnail=best_thumbnail,
            thumbnails=thumbnails_data,
            webpage_url=video_info.video_url,
            has_formats=bool(video_info.formats)
        )

    @staticmethod
    async def extract_video(url: str, mobile: bool = False, cookies: Optional[str] = None) -> dict:
        # Detectar si es Threads
        if "threads.com" in url or "threads.net" in url:
            video_url = await get_threads_video_url(url, headless=True)
            return {
                "video_url": video_url,
                "title": "Threads Video",  # Opcional, puedes intentar scrapear título si quieres
                "platform": "threads",
                "method": "ThreadsService",
                "formats": [{"format_id": "best", "ext": "mp4", "url": video_url}]
            }
    
        # Para otras plataformas seguimos con yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'format': 'best',
            'noplaylist': True,
        }
    
        if mobile:
            ydl_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 9; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
            }
    
        if cookies:
            ydl_opts['cookiefile'] = cookies
    
        loop = asyncio.get_event_loop()
    
        def run_extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
    
        info = await loop.run_in_executor(None, run_extract)
        return info
