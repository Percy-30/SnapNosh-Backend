import yt_dlp
from typing import Optional

class GenericDownloader:
    def __init__(self, output_dir: str = './downloads'):
        self.output_dir = output_dir

    def download(self, url: str) -> dict:
        ydl_opts = {
            'outtmpl': f'{self.output_dir}/%(title)s.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return {
                "title": info.get("title"),
                "filename": filename,
                "duration": info.get("duration"),
                "url": url
            }
    
