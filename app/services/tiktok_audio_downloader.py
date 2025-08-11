import asyncio
import aiohttp
import os
import re
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from urllib.parse import urlparse, parse_qs
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TikTokAPIDownloader:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(os.getcwd(), "downloads")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from TikTok URL"""
        patterns = [
            r'/video/(\d+)',
            r'/v/(\d+)',
            r'tiktok\.com/@[\w.-]+/video/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_safe_filename(self, title: str, video_id: str = None) -> str:
        """Generate safe filename"""
        if title:
            safe_title = re.sub(r'[^\w\s-]', '', title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')
            safe_title = safe_title[:50]
        else:
            safe_title = "tiktok_audio"
        
        if video_id:
            safe_title += f"_{video_id}"
        
        return f"{safe_title}.mp3"
    
    async def download_file(self, url: str, output_path: str) -> bool:
        """Download file from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    return True
                else:
                    logger.error(f"Download failed with status: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return False
    
    # ========== API 1: TikMate API ==========
    async def tikmate_api(self, url: str) -> Dict[str, Any]:
        """Use TikMate API for download"""
        try:
            api_url = "https://tikmate.app/api/lookup"
            
            payload = {
                "url": url
            }
            
            async with self.session.post(api_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success'):
                        video_data = data.get('data', {})
                        
                        # Get audio URL
                        audio_url = None
                        if 'music' in video_data:
                            audio_url = video_data['music'].get('play_url')
                        
                        return {
                            'success': True,
                            'audio_url': audio_url,
                            'title': video_data.get('title', ''),
                            'author': video_data.get('author', {}).get('nickname', ''),
                            'duration': video_data.get('duration', 0),
                            'api': 'tikmate'
                        }
            
            return {'success': False, 'error': 'TikMate API failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'TikMate error: {str(e)}'}
    
    # ========== API 2: SSSTik API ==========
    async def ssstik_api(self, url: str) -> Dict[str, Any]:
        """Use SSSTik scraper"""
        try:
            # First get the form data
            ssstik_url = "https://ssstik.io/abc?url=dl"
            
            form_data = aiohttp.FormData()
            form_data.add_field('id', url)
            form_data.add_field('locale', 'en')
            form_data.add_field('tt', 'RFBiZ3Bi')  # This might need updating
            
            headers = {
                'Origin': 'https://ssstik.io',
                'Referer': 'https://ssstik.io/',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            async with self.session.post(ssstik_url, data=form_data, headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Parse HTML to extract download links
                    audio_pattern = r'href="([^"]*)" class="without_watermark"[^>]*>.*?Audio'
                    audio_match = re.search(audio_pattern, html_content, re.IGNORECASE | re.DOTALL)
                    
                    if audio_match:
                        audio_url = audio_match.group(1)
                        
                        # Extract title
                        title_pattern = r'<h2[^>]*>(.*?)</h2>'
                        title_match = re.search(title_pattern, html_content)
                        title = title_match.group(1) if title_match else 'TikTok Audio'
                        
                        return {
                            'success': True,
                            'audio_url': audio_url,
                            'title': title.strip(),
                            'api': 'ssstik'
                        }
            
            return {'success': False, 'error': 'SSSTik parsing failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'SSSTik error: {str(e)}'}
    
    # ========== API 3: TikTok Official API (requires token) ==========
    async def tiktok_official_api(self, url: str, access_token: str = None) -> Dict[str, Any]:
        """Use TikTok Official API (requires developer access)"""
        if not access_token:
            return {'success': False, 'error': 'TikTok Official API requires access token'}
        
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                return {'success': False, 'error': 'Could not extract video ID'}
            
            api_url = f"https://open-api.tiktok.com/video/query/?video_id={video_id}&access_token={access_token}"
            
            async with self.session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('error'):
                        return {'success': False, 'error': data['error']['message']}
                    
                    video_info = data.get('data', {}).get('list', [{}])[0]
                    
                    return {
                        'success': True,
                        'audio_url': video_info.get('music', {}).get('play_url'),
                        'title': video_info.get('title', ''),
                        'author': video_info.get('author', {}).get('display_name', ''),
                        'api': 'official'
                    }
            
            return {'success': False, 'error': 'Official API request failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'Official API error: {str(e)}'}
    
    # ========== API 4: RapidAPI TikTok ==========
    async def rapidapi_tiktok(self, url: str, rapidapi_key: str = None) -> Dict[str, Any]:
        """Use RapidAPI TikTok service"""
        if not rapidapi_key:
            return {'success': False, 'error': 'RapidAPI requires API key'}
        
        try:
            api_url = "https://tiktok-scraper7.p.rapidapi.com/"
            
            headers = {
                "X-RapidAPI-Key": rapidapi_key,
                "X-RapidAPI-Host": "tiktok-scraper7.p.rapidapi.com"
            }
            
            params = {"url": url}
            
            async with self.session.get(api_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success'):
                        video_data = data.get('data', {})
                        
                        return {
                            'success': True,
                            'audio_url': video_data.get('music', {}).get('play_url'),
                            'title': video_data.get('title', ''),
                            'author': video_data.get('author', {}).get('nickname', ''),
                            'api': 'rapidapi'
                        }
            
            return {'success': False, 'error': 'RapidAPI request failed'}
            
        except Exception as e:
            return {'success': False, 'error': f'RapidAPI error: {str(e)}'}
    
    # ========== API 5: Custom TikTok Scraper ==========
    async def custom_scraper(self, url: str) -> Dict[str, Any]:
        """Custom TikTok page scraper"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.tiktok.com/',
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for JSON data in script tags
                    json_pattern = r'<script[^>]*>window\.__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*({.*?})</script>'
                    match = re.search(json_pattern, html)
                    
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            
                            # Navigate the data structure to find audio
                            video_detail = data.get('__DEFAULT_SCOPE__', {}).get('webapp.video-detail', {}).get('itemInfo', {}).get('itemStruct', {})
                            
                            if video_detail:
                                music = video_detail.get('music', {})
                                
                                return {
                                    'success': True,
                                    'audio_url': music.get('playUrl', ''),
                                    'title': video_detail.get('desc', ''),
                                    'author': video_detail.get('author', {}).get('nickname', ''),
                                    'music_title': music.get('title', ''),
                                    'api': 'custom_scraper'
                                }
                        except json.JSONDecodeError:
                            pass
                    
                    # Fallback: look for direct links in HTML
                    audio_patterns = [
                        r'"playAddr":"([^"]*\.mp3[^"]*)"',
                        r'"downloadAddr":"([^"]*\.mp3[^"]*)"',
                        r'playUrl":"([^"]*)"'
                    ]
                    
                    for pattern in audio_patterns:
                        match = re.search(pattern, html)
                        if match:
                            audio_url = match.group(1).replace('\\/', '/')
                            return {
                                'success': True,
                                'audio_url': audio_url,
                                'title': 'TikTok Audio',
                                'api': 'custom_scraper_fallback'
                            }
            
            return {'success': False, 'error': 'Custom scraper failed to find audio'}
            
        except Exception as e:
            return {'success': False, 'error': f'Custom scraper error: {str(e)}'}
    
    async def download_audio(self, url: str, rapidapi_key: str = None, tiktok_token: str = None) -> Dict[str, Any]:
        """
        Try multiple APIs to download TikTok audio
        
        Args:
            url: TikTok video URL
            rapidapi_key: Optional RapidAPI key
            tiktok_token: Optional TikTok official API token
        """
        
        # List of methods to try
        methods = [
            ("Custom Scraper", self.custom_scraper, [url]),
            ("TikMate API", self.tikmate_api, [url]),
            ("SSSTik API", self.ssstik_api, [url]),
        ]
        
        # Add paid APIs if keys provided
        if rapidapi_key:
            methods.append(("RapidAPI", self.rapidapi_tiktok, [url, rapidapi_key]))
        
        if tiktok_token:
            methods.append(("TikTok Official", self.tiktok_official_api, [url, tiktok_token]))
        
        last_error = None
        
        for method_name, method_func, args in methods:
            try:
                logger.info(f"🔄 Trying {method_name}...")
                result = await method_func(*args)
                
                if result['success'] and result.get('audio_url'):
                    logger.info(f"✅ {method_name} found audio URL!")
                    
                    # Download the audio file
                    title = result.get('title', 'tiktok_audio')
                    video_id = self.extract_video_id(url)
                    filename = self.get_safe_filename(title, video_id)
                    output_path = os.path.join(self.output_dir, filename)
                    
                    logger.info(f"📥 Downloading audio: {filename}")
                    download_success = await self.download_file(result['audio_url'], output_path)
                    
                    if download_success and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                        file_size = os.path.getsize(output_path)
                        
                        return {
                            'success': True,
                            'file_path': output_path,
                            'file_size': file_size,
                            'filename': filename,
                            'title': result.get('title', ''),
                            'author': result.get('author', ''),
                            'method': method_name.lower().replace(' ', '_'),
                            'api_used': result.get('api', method_name.lower())
                        }
                    else:
                        logger.warning(f"❌ {method_name} download failed or file too small")
                
                else:
                    logger.warning(f"❌ {method_name} failed: {result.get('error', 'No audio URL found')}")
                    last_error = result.get('error', f'{method_name} failed')
                    
            except Exception as e:
                logger.warning(f"❌ {method_name} crashed: {str(e)}")
                last_error = str(e)
                continue
        
        return {
            'success': False,
            'error': last_error or 'All methods failed',
            'file_path': None,
            'file_size': 0,
            'filename': None,
            'method': None
        }

# Convenience function
async def download_tiktok_audio_api(url: str, output_dir: str = None, rapidapi_key: str = None, tiktok_token: str = None) -> Dict[str, Any]:
    """
    Download TikTok audio using API methods
    
    Args:
        url: TikTok video URL
        output_dir: Output directory
        rapidapi_key: Optional RapidAPI key for premium features
        tiktok_token: Optional TikTok official API token
    """
    async with TikTokAPIDownloader(output_dir) as downloader:
        return await downloader.download_audio(url, rapidapi_key, tiktok_token)

async def main():
    import sys
    
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.tiktok.com/@rodrguezyonder/video/7503962018643217680"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("🎵 TikTok API Audio Downloader")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Output directory: {output_dir or 'downloads/'}")
    print("=" * 50)
    
    try:
        # You can add your API keys here
        # rapidapi_key = "YOUR_RAPIDAPI_KEY"
        # tiktok_token = "YOUR_TIKTOK_TOKEN"
        
        result = await download_tiktok_audio_api(
            url, 
            output_dir,
            # rapidapi_key=rapidapi_key,
            # tiktok_token=tiktok_token
        )
        
        if result['success']:
            print("\n🎉 DOWNLOAD SUCCESSFUL!")
            print(f"📁 File: {result['file_path']}")
            print(f"📊 Size: {result['file_size']:,} bytes ({result['file_size']/1024/1024:.2f} MB)")
            print(f"🔧 Method: {result['method']}")
            print(f"🏷️  Title: {result.get('title', 'N/A')}")
            print(f"👤 Author: {result.get('author', 'N/A')}")
            print(f"🌐 API: {result.get('api_used', 'N/A')}")
            
            print("\n🎧 Audio file is ready!")
            print(f"Full path: {os.path.abspath(result['file_path'])}")
            
        else:
            print("\n❌ DOWNLOAD FAILED!")
            print(f"Error: {result['error']}")
            
            print("\n💡 Suggestions:")
            print("1. Try a different TikTok video URL")
            print("2. Check if the video is public and accessible")
            print("3. Consider getting a RapidAPI key for better reliability")
            print("4. Try again later (some APIs have rate limits)")
            
    except KeyboardInterrupt:
        print("\n⏹️  Download cancelled by user")
    except Exception as e:
        print(f"\n💀 Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())