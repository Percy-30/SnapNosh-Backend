import asyncio
import yt_dlp
import logging

logger = logging.getLogger(__name__)

async def get_youtube_audio_url(url: str) -> str:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",  # dejar que yt-dlp elija el mejor audio
        "extract_flat": False,
        "force_generic_extractor": False,
        "noplaylist": True,
    }

    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
        )

        # Filtrar todos los formatos de audio disponibles
        audio_formats = [f for f in info.get("formats", []) if f.get("acodec") != "none"]
        if not audio_formats:
            raise Exception("No se encontró URL de audio")

        # Ordenar por bitrate y devolver la mejor
        audio_formats.sort(key=lambda f: f.get("abr") or 0, reverse=True)
        return audio_formats[0]["url"]

    except Exception as e:
        logger.error(f"Error extrayendo audio: {e}", exc_info=True)
        raise

# ===========================
# Prueba local
# ===========================
if __name__ == "__main__":
    import sys

    async def main():
        url = sys.argv[1] if len(sys.argv) > 1 else None
        if not url:
            print("❌ Proporciona URL de YouTube")
            return

        audio_url = await get_youtube_audio_url(url)
        print(f"🎵 Audio URL: {audio_url}")

    asyncio.run(main())
