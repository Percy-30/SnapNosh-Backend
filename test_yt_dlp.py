import sys
import yt_dlp
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, parse_qs
import logging
import random
import time
import re

class GenericDownloader:
    def __init__(self):
        # Configurar logging detallado
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Pool de User-Agents actualizados y realistas
        self.user_agents = [
            # Chrome Windows (más común)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            
            # Firefox Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            
            # Chrome Mac
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            
            # Safari Mac
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            
            # Mobile (para estrategia móvil)
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        ]
        
        # Rate limiting
        self.last_request_time = 0
        self.min_delay = 1.0  # Mínimo 1 segundo entre requests
        
    async def extract(self, url: str, **kwargs) -> Dict[str, Any]:
        """Punto de entrada principal para extracción"""
        loop = asyncio.get_event_loop()
        
        # Detectar y normalizar la plataforma
        platform = self._detect_platform(url)
        normalized_url = self._normalize_url(url, platform)
        
        self.logger.info(f"🎬 Extracting from {platform.upper()}: {normalized_url}")
        
        # Rate limiting respetuoso
        await self._apply_rate_limit()
        
        # Estrategias específicas por plataforma
        if platform == 'youtube':
            return await self._extract_youtube_advanced(normalized_url, loop, **kwargs)
        elif platform == 'vimeo':
            return await self._extract_vimeo_advanced(normalized_url, loop, **kwargs)
        elif platform == 'twitter':
            return await self._extract_twitter_advanced(normalized_url, loop, **kwargs)
        else:
            return await self._extract_generic_advanced(normalized_url, loop, platform, **kwargs)
    
    async def _extract_youtube_advanced(self, url: str, loop, **kwargs) -> Dict[str, Any]:
        """Estrategias avanzadas específicas para YouTube"""
        
        # Estrategias ordenadas por probabilidad de éxito
        strategies = [
            ('optimal', self._get_youtube_optimal_config),
            ('high_quality', self._get_youtube_hq_config),
            ('mobile', self._get_youtube_mobile_config),
            ('api_key', self._get_youtube_api_config),
            ('legacy', self._get_youtube_legacy_config),
            ('aggressive', self._get_youtube_aggressive_config),
            ('fallback', self._get_youtube_fallback_config)
        ]
        
        quality_preference = kwargs.get('quality', 'best')
        include_formats = kwargs.get('include_formats', True)
        
        for strategy_name, config_func in strategies:
            try:
                self.logger.info(f"🎯 YouTube: Trying {strategy_name} strategy")
                
                # Delay progresivo entre estrategias
                if strategy_name != 'optimal':
                    delay = random.uniform(1.5, 3.0)
                    await asyncio.sleep(delay)
                
                config = config_func(quality_preference)
                info = await self._attempt_extraction(url, config, loop, strategy_name)
                
                if info and self._validate_extraction(info):
                    video_url = self._get_best_video_url(info, quality_preference)
                    if video_url:
                        return self._build_response(info, 'youtube', video_url, f'youtube_{strategy_name}', include_formats)
                        
            except Exception as e:
                self.logger.warning(f"❌ YouTube {strategy_name}: {self._sanitize_error(str(e))}")
                continue
        
        # Si todas las estrategias principales fallan, intentar modo de emergencia
        return await self._emergency_extraction(url, 'youtube', loop)
    
    async def _extract_vimeo_advanced(self, url: str, loop, **kwargs) -> Dict[str, Any]:
        """Estrategias para Vimeo"""
        strategies = [
            ('direct', self._get_vimeo_direct_config),
            ('api', self._get_vimeo_api_config),
            ('player', self._get_vimeo_player_config)
        ]
        
        return await self._try_strategies(url, 'vimeo', strategies, loop, **kwargs)
    
    async def _extract_twitter_advanced(self, url: str, loop, **kwargs) -> Dict[str, Any]:
        """Estrategias para Twitter/X"""
        strategies = [
            ('api', self._get_twitter_api_config),
            ('web', self._get_twitter_web_config),
            ('mobile', self._get_twitter_mobile_config)
        ]
        
        return await self._try_strategies(url, 'twitter', strategies, loop, **kwargs)
    
    async def _extract_generic_advanced(self, url: str, loop, platform: str, **kwargs) -> Dict[str, Any]:
        """Extracción genérica robusta"""
        config = self._get_generic_robust_config()
        
        try:
            info = await self._attempt_extraction(url, config, loop, 'generic_robust')
            if info and self._validate_extraction(info):
                video_url = self._get_best_video_url(info, kwargs.get('quality', 'best'))
                return self._build_response(info, platform, video_url, 'generic_success', kwargs.get('include_formats', True))
        except Exception as e:
            self.logger.warning(f"Generic extraction failed: {e}")
        
        return self._build_failed_response(platform, "Generic extraction failed")
    
    # =============================================================================
    # CONFIGURACIONES ESPECÍFICAS DE YOUTUBE
    # =============================================================================
    
    def _get_youtube_optimal_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración óptima para YouTube con balance rendimiento/calidad"""
        return {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'format': self._get_format_selector(quality, 'youtube'),
            'extract_flat': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'http_headers': self._get_realistic_headers('youtube'),
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'] if quality == 'fast' else [],
                    'player_client': ['web'],
                }
            }
        }
    
    def _get_youtube_hq_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración para alta calidad en YouTube"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 45,
            'retries': 5,
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            'extract_flat': False,
            'http_headers': self._get_realistic_headers('youtube'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android'],
                    'player_skip': ['configs'],
                }
            }
        }
    
    def _get_youtube_mobile_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración móvil para YouTube"""
        mobile_headers = self._get_realistic_headers('mobile')
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': 'best[height<=720]/best',
            'http_headers': mobile_headers,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            }
        }
    
    def _get_youtube_api_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración usando API de YouTube"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': self._get_format_selector(quality, 'youtube'),
            'http_headers': self._get_realistic_headers('youtube'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],
                    'player_skip': ['webpage'],
                }
            }
        }
    
    def _get_youtube_legacy_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración legacy para YouTube"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 60,
            'retries': 8,
            'format': 'best',
            'prefer_free_formats': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                }
            }
        }
    
    def _get_youtube_aggressive_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración agresiva para casos difíciles"""
        return {
            'quiet': False,  # Mostrar errores detallados
            'skip_download': True,
            'socket_timeout': 90,
            'retries': 10,
            'fragment_retries': 10,
            'format': 'best',
            'ignore_no_formats_error': True,
            'http_headers': self._get_realistic_headers('youtube'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios', 'tv_embedded'],
                    'player_skip': [],
                }
            }
        }
    
    def _get_youtube_fallback_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración de último recurso"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 120,
            'retries': 15,
            'ignoreerrors': True,
            'force_generic_extractor': True,
            'format': 'worst/best',
            'http_headers': {
                'User-Agent': 'curl/7.68.0'
            }
        }
    
    # =============================================================================
    # CONFIGURACIONES PARA OTRAS PLATAFORMAS
    # =============================================================================
    
    def _get_vimeo_direct_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración directa para Vimeo"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': self._get_format_selector(quality, 'vimeo'),
            'http_headers': self._get_realistic_headers('vimeo')
        }
    
    def _get_vimeo_api_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración API para Vimeo"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 45,
            'format': self._get_format_selector(quality, 'vimeo'),
            'http_headers': {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'application/json',
                'Referer': 'https://vimeo.com/'
            }
        }
    
    def _get_vimeo_player_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración player para Vimeo"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': 'best',
            'http_headers': self._get_realistic_headers('vimeo'),
            'extractor_args': {
                'vimeo': {
                    'player_url': True
                }
            }
        }
    
    def _get_twitter_api_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración API para Twitter"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': self._get_format_selector(quality, 'twitter'),
            'http_headers': self._get_realistic_headers('twitter')
        }
    
    def _get_twitter_web_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración web para Twitter"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 45,
            'format': 'best',
            'http_headers': self._get_realistic_headers('twitter')
        }
    
    def _get_twitter_mobile_config(self, quality: str = 'best') -> Dict[str, Any]:
        """Configuración móvil para Twitter"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 30,
            'format': 'best[height<=720]',
            'http_headers': self._get_realistic_headers('mobile')
        }
    
    def _get_generic_robust_config(self) -> Dict[str, Any]:
        """Configuración robusta genérica"""
        return {
            'quiet': True,
            'skip_download': True,
            'socket_timeout': 45,
            'retries': 5,
            'format': 'best',
            'http_headers': self._get_realistic_headers('generic')
        }
    
    # =============================================================================
    # MÉTODOS DE UTILIDAD
    # =============================================================================
    
    def _detect_platform(self, url: str) -> str:
        """Detecta la plataforma basándose en la URL"""
        try:
            domain = urlparse(url).netloc.lower()
            if 'youtube.com' in domain or 'youtu.be' in domain:
                return 'youtube'
            elif 'vimeo.com' in domain:
                return 'vimeo'
            elif 'twitter.com' in domain or 'x.com' in domain:
                return 'twitter'
            elif 'tiktok.com' in domain:
                return 'tiktok'
            elif 'instagram.com' in domain:
                return 'instagram'
            elif 'facebook.com' in domain or 'fb.watch' in domain:
                return 'facebook'
            else:
                return 'generic'
        except:
            return 'generic'
    
    def _normalize_url(self, url: str, platform: str) -> str:
        """Normaliza la URL según la plataforma"""
        if platform == 'youtube':
            # Extraer video ID de diferentes formatos de URL de YouTube
            patterns = [
                r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
                r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
                r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    return f'https://www.youtube.com/watch?v={video_id}'
        
        return url
    
    def _get_format_selector(self, quality: str, platform: str) -> str:
        """Genera selector de formato optimizado por plataforma y calidad"""
        format_map = {
            'youtube': {
                'best': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'high': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'medium': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                'low': 'worst[height>=360]/worst',
                'fast': 'best[height<=360]',
                'audio': 'bestaudio'
            },
            'vimeo': {
                'best': 'best[height<=1080]',
                'high': 'best[height<=720]',
                'medium': 'best[height<=480]',
                'low': 'worst',
                'fast': 'worst'
            },
            'twitter': {
                'best': 'best',
                'high': 'best[height<=720]',
                'medium': 'best[height<=480]',
                'low': 'worst',
                'fast': 'worst'
            }
        }
        
        return format_map.get(platform, {}).get(quality, 'best')
    
    def _get_realistic_headers(self, context: str = 'generic') -> Dict[str, str]:
        """Genera headers realistas según el contexto"""
        base_ua = random.choice(self.user_agents)
        
        base_headers = {
            'User-Agent': base_ua,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        context_headers = {
            'youtube': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin'
            },
            'vimeo': {
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://vimeo.com/',
                'Origin': 'https://vimeo.com'
            },
            'twitter': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://twitter.com/',
                'Origin': 'https://twitter.com'
            },
            'mobile': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
        }
        
        # Agregar headers específicos del contexto
        if context in context_headers:
            base_headers.update(context_headers[context])
        
        # Agregar headers específicos de Chrome si es Chrome
        if 'Chrome' in base_ua:
            base_headers.update({
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            })
        
        return base_headers
    
    async def _apply_rate_limit(self):
        """Aplica rate limiting respetuoso"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            self.logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def _try_strategies(self, url: str, platform: str, strategies: List, loop, **kwargs) -> Dict[str, Any]:
        """Intenta múltiples estrategias para una plataforma"""
        quality = kwargs.get('quality', 'best')
        include_formats = kwargs.get('include_formats', True)
        
        for strategy_name, config_func in strategies:
            try:
                self.logger.info(f"🎯 {platform.upper()}: Trying {strategy_name}")
                
                if strategy_name != strategies[0][0]:  # No delay en primera estrategia
                    await asyncio.sleep(random.uniform(1, 2))
                
                config = config_func(quality)
                info = await self._attempt_extraction(url, config, loop, strategy_name)
                
                if info and self._validate_extraction(info):
                    video_url = self._get_best_video_url(info, quality)
                    if video_url:
                        return self._build_response(info, platform, video_url, f'{platform}_{strategy_name}', include_formats)
                        
            except Exception as e:
                self.logger.warning(f"❌ {platform.upper()} {strategy_name}: {self._sanitize_error(str(e))}")
                continue
        
        return await self._emergency_extraction(url, platform, loop)
    
    async def _attempt_extraction(self, url: str, ydl_opts: dict, loop, strategy: str) -> Optional[Dict[str, Any]]:
        """Intenta extraer información con manejo robusto de errores"""
        def run_extraction():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Pequeño delay aleatorio para simular comportamiento humano
                    time.sleep(random.uniform(0.1, 0.5))
                    return ydl.extract_info(url, download=False)
            except Exception as e:
                raise e
        
        try:
            info = await loop.run_in_executor(None, run_extraction)
            
            if info and self._validate_extraction(info):
                self.logger.info(f"✅ Strategy '{strategy}' successful!")
                return info
            else:
                raise Exception("No valid video information found")
                
        except Exception as e:
            error_msg = self._sanitize_error(str(e))
            self.logger.warning(f"❌ Strategy '{strategy}': {error_msg}")
            raise Exception(error_msg)
    
    async def _emergency_extraction(self, url: str, platform: str, loop) -> Dict[str, Any]:
        """Extracción de emergencia como último recurso"""
        self.logger.info(f"🚨 Emergency extraction for {platform}")
        
        emergency_config = {
            'quiet': False,
            'skip_download': True,
            'socket_timeout': 120,
            'retries': 20,
            'ignoreerrors': True,
            'format': 'worst/best',
            'http_headers': {'User-Agent': 'curl/7.68.0'}
        }
        
        try:
            info = await self._attempt_extraction(url, emergency_config, loop, 'emergency')
            if info:
                video_url = self._get_best_video_url(info, 'best')
                return self._build_response(info, platform, video_url, 'emergency_success', False)
        except Exception as e:
            self.logger.error(f"Emergency extraction failed: {e}")
        
        return self._build_failed_response(platform, "All extraction methods failed")
    
    def _validate_extraction(self, info: Dict[str, Any]) -> bool:
        """Valida que la extracción sea exitosa"""
        if not info:
            return False
        
        # Verificar que tenemos al menos una URL de video o formatos
        has_url = info.get('url')
        has_formats = info.get('formats') and len(info['formats']) > 0
        has_title = info.get('title')
        
        return bool(has_title and (has_url or has_formats))
    
    def _get_best_video_url(self, info: Dict[str, Any], quality: str = 'best') -> str:
        """Selecciona la mejor URL de video según la calidad solicitada"""
        # 1. Intentar URL directa
        if info.get('url') and info['url'].startswith(('http://', 'https://')):
            return str(info['url'])
        
        # 2. Buscar en formatos
        formats = info.get('formats', [])
        if not formats:
            return ''
        
        # 3. Filtrar formatos válidos
        valid_formats = [f for f in formats if f.get('url') and f['url'].startswith(('http://', 'https://'))]
        if not valid_formats:
            return ''
        
        # 4. Selección basada en calidad
        if quality == 'best':
            # Mejor calidad disponible
            best_format = max(valid_formats, key=lambda f: f.get('height', 0) or 0)
            return str(best_format['url'])
        elif quality == 'high':
            # 720p o mejor
            high_formats = [f for f in valid_formats if (f.get('height') or 0) >= 720]
            if high_formats:
                return str(min(high_formats, key=lambda f: f.get('height', 999))['url'])
        elif quality == 'medium':
            # 480p aproximadamente
            medium_formats = [f for f in valid_formats if 400 <= (f.get('height') or 0) <= 600]
            if medium_formats:
                return str(medium_formats[0]['url'])
        elif quality == 'low':
            # Menor calidad
            low_format = min(valid_formats, key=lambda f: f.get('height', 999))
            return str(low_format['url'])
        
        # Fallback: primer formato válido
        return str(valid_formats[0]['url'])
    
    def _build_response(self, info: Dict[str, Any], platform: str, video_url: str, method: str, include_formats: bool = True) -> Dict[str, Any]:
        """Construye respuesta exitosa estandarizada"""
        response = {
            'platform': platform,
            'title': str(info.get('title', 'unknown')),
            'video_url': video_url or '',
            'method': method,
            'duration': info.get('duration'),
            'thumbnail': str(info.get('thumbnail', '')),
            'uploader': str(info.get('uploader', 'unknown')),
            'view_count': info.get('view_count'),
            'upload_date': info.get('upload_date'),
            'description': str(info.get('description', ''))[:500]
        }
        
        # Incluir formatos solo si se solicita (para reducir payload)
        if include_formats:
            formats = info.get('formats', [])
            response['formats'] = [
                {
                    'format_id': f.get('format_id', 'unknown'),
                    'url': f.get('url', ''),
                    'ext': f.get('ext', 'unknown'),
                    'quality': f.get('height', 'unknown'),
                    'filesize': f.get('filesize'),
                    'fps': f.get('fps'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec')
                }
                for f in formats[:10]  # Limitar a 10 formatos para reducir tamaño
            ]
        else:
            response['formats'] = []
        
        return response
    
    def _build_failed_response(self, platform: str, error_message: str) -> Dict[str, Any]:
        """Construye respuesta de fallo estandarizada"""
        return {
            'platform': platform,
            'title': 'extraction_failed',
            'video_url': '',
            'formats': [],
            'method': 'failed',
            'error': error_message,
            'duration': None,
            'thumbnail': '',
            'uploader': 'unknown'
        }
    
    def _sanitize_error(self, error_message: str) -> str:
        """Limpia mensajes de error para logging"""
        # Remover información sensible o muy técnica
        sanitized = error_message.replace('\n', ' ').strip()
        if len(sanitized) > 200:
            sanitized = sanitized[:200] + '...'
        return sanitized

    # =============================================================================
    # API PÚBLICA ADICIONAL
    # =============================================================================
    
    async def get_video_info(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """API simplificada para obtener solo información básica del video"""
        try:
            result = await self.extract(url, quality=quality, include_formats=False)
            return {
                'success': result['method'] != 'failed',
                'title': result['title'],
                'duration': result['duration'],
                'thumbnail': result['thumbnail'],
                'uploader': result['uploader'],
                'platform': result['platform']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'platform': self._detect_platform(url)
            }
    
    async def get_direct_url(self, url: str, quality: str = 'best') -> Optional[str]:
        """Obtiene solo la URL directa del video"""
        try:
            result = await self.extract(url, quality=quality, include_formats=False)
            return result.get('video_url') if result['method'] != 'failed' else None
        except Exception:
            return None
    
    async def get_available_qualities(self, url: str) -> List[str]:
        """Obtiene las calidades disponibles para un video"""
        try:
            result = await self.extract(url, include_formats=True)
            if result['method'] == 'failed':
                return []
            
            qualities = set()
            for fmt in result.get('formats', []):
                height = fmt.get('quality', 0)
                if isinstance(height, int):
                    if height >= 1080:
                        qualities.add('best')
                    elif height >= 720:
                        qualities.add('high')
                    elif height >= 480:
                        qualities.add('medium')
                    else:
                        qualities.add('low')
            
            return sorted(list(qualities), key=lambda x: ['low', 'medium', 'high', 'best'].index(x))
        except Exception:
            return []
    
    def get_supported_platforms(self) -> List[str]:
        """Devuelve la lista de plataformas soportadas"""
        return [
            'youtube',
            'vimeo', 
            'twitter',
            'tiktok',
            'instagram',
            'facebook',
            'generic'
        ]
    
    def is_supported_url(self, url: str) -> bool:
        """Verifica si la URL es de una plataforma soportada"""
        platform = self._detect_platform(url)
        return platform in self.get_supported_platforms()

# =============================================================================
# UTILIDADES DE TESTING Y DEMOSTRACIÓN
# =============================================================================

class VideoDownloaderTester:
    """Clase para testing sistemático del downloader"""
    
    def __init__(self):
        self.downloader = GenericDownloader()
        self.test_results = []
    
    async def run_comprehensive_test(self, urls: List[str]):
        """Ejecuta tests comprehensivos"""
        print("🚀 GenericDownloader - Test Suite Completo")
        print("=" * 80)
        
        for i, url in enumerate(urls, 1):
            print(f"\n🔍 Test {i}/{len(urls)}: {url}")
            print("-" * 60)
            
            start_time = time.time()
            
            # Test 1: Extracción básica
            await self._test_basic_extraction(url)
            
            # Test 2: Diferentes calidades
            await self._test_quality_options(url)
            
            # Test 3: API simplificada
            await self._test_simplified_api(url)
            
            elapsed = time.time() - start_time
            print(f"⏱️ Test completado en {elapsed:.2f}s")
    
    async def _test_basic_extraction(self, url: str):
        """Test de extracción básica"""
        try:
            result = await self.downloader.extract(url)
            success = result['method'] != 'failed'
            
            print(f"📊 Extracción básica: {'✅ ÉXITO' if success else '❌ FALLÓ'}")
            if success:
                print(f"   📺 Plataforma: {result['platform']}")
                print(f"   📝 Título: {result['title'][:50]}{'...' if len(result['title']) > 50 else ''}")
                print(f"   🎬 Video URL: {'✅' if result['video_url'] else '❌'}")
                print(f"   🔧 Método: {result['method']}")
                print(f"   ⏱️ Duración: {result.get('duration', 'N/A')}s")
                print(f"   👁️ Vistas: {result.get('view_count', 'N/A')}")
            else:
                print(f"   ⚠️ Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"📊 Extracción básica: ❌ EXCEPCIÓN - {str(e)[:100]}")
    
    async def _test_quality_options(self, url: str):
        """Test de opciones de calidad"""
        qualities = ['best', 'high', 'medium', 'low']
        quality_results = {}
        
        for quality in qualities:
            try:
                result = await self.downloader.extract(url, quality=quality, include_formats=False)
                quality_results[quality] = result['method'] != 'failed'
            except:
                quality_results[quality] = False
        
        print("📊 Test de calidades:")
        for quality, success in quality_results.items():
            print(f"   {quality.capitalize()}: {'✅' if success else '❌'}")
    
    async def _test_simplified_api(self, url: str):
        """Test de API simplificada"""
        try:
            # Test info básica
            info = await self.downloader.get_video_info(url)
            info_success = info.get('success', False)
            
            # Test URL directa
            direct_url = await self.downloader.get_direct_url(url)
            url_success = bool(direct_url)
            
            # Test calidades disponibles
            qualities = await self.downloader.get_available_qualities(url)
            qualities_success = len(qualities) > 0
            
            print("📊 API simplificada:")
            print(f"   Info básica: {'✅' if info_success else '❌'}")
            print(f"   URL directa: {'✅' if url_success else '❌'}")
            print(f"   Calidades: {'✅' if qualities_success else '❌'} ({len(qualities)} disponibles)")
            
        except Exception as e:
            print(f"📊 API simplificada: ❌ EXCEPCIÓN - {str(e)[:50]}")

# =============================================================================
# SCRIPT PRINCIPAL DE TESTING
# =============================================================================

async def main():
    """Función principal para testing"""
    if len(sys.argv) < 2:
        print("🚀 GenericDownloader - YouTube Optimizado")
        print("=" * 50)
        print("Uso: python script.py <URL1> [URL2] [...]")
        print("\n🎯 Características principales:")
        print("  ✅ Múltiples estrategias anti-bloqueo")
        print("  ✅ Selección inteligente de calidad")
        print("  ✅ Rate limiting respetuoso")
        print("  ✅ Manejo robusto de errores")
        print("  ✅ Headers realistas y rotación de UA")
        print("  ✅ Configuraciones específicas por plataforma")
        print("\n📋 Plataformas soportadas:")
        downloader = GenericDownloader()
        platforms = downloader.get_supported_platforms()
        for platform in platforms:
            print(f"  • {platform.capitalize()}")
        
        print("\n💡 Ejemplos de uso:")
        print("  python script.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        print("  python script.py https://vimeo.com/123456789")
        print("  python script.py https://twitter.com/user/status/123456789")
        print("\n🧪 Para testing completo, usa:")
        print("  python script.py --test <URL1> [URL2] [...]")
        return
    
    urls = sys.argv[1:]
    
    # Verificar si es modo test
    if urls[0] == '--test':
        urls = urls[1:]
        if not urls:
            print("❌ Modo test requiere al menos una URL")
            return
        
        tester = VideoDownloaderTester()
        await tester.run_comprehensive_test(urls)
        return
    
    # Modo normal
    downloader = GenericDownloader()
    
    for i, url in enumerate(urls, 1):
        print(f"\n🔍 Procesando URL {i}/{len(urls)}: {url}")
        print("=" * 80)
        
        # Verificar si la URL es soportada
        if not downloader.is_supported_url(url):
            print(f"⚠️ Advertencia: URL podría no estar soportada (plataforma: {downloader._detect_platform(url)})")
        
        start_time = time.time()
        
        try:
            # Extracción principal
            result = await downloader.extract(url, quality='best', include_formats=True)
            elapsed = time.time() - start_time
            
            # Mostrar resultados
            success = result['method'] != 'failed'
            print(f"{'✅ ÉXITO' if success else '❌ FALLÓ'} (en {elapsed:.2f}s)")
            
            if success:
                print(f"\n📊 Información del video:")
                print(f"   📺 Plataforma: {result['platform'].upper()}")
                print(f"   📝 Título: {result['title']}")
                print(f"   👤 Autor: {result.get('uploader', 'N/A')}")
                print(f"   ⏱️ Duración: {result.get('duration', 'N/A')}s")
                print(f"   👁️ Vistas: {result.get('view_count', 'N/A')}")
                print(f"   📅 Fecha: {result.get('upload_date', 'N/A')}")
                print(f"   🔧 Método: {result['method']}")
                
                if result['video_url']:
                    print(f"\n🎬 URL del video:")
                    print(f"   {result['video_url'][:100]}{'...' if len(result['video_url']) > 100 else ''}")
                
                if result.get('thumbnail'):
                    print(f"\n🖼️ Miniatura:")
                    print(f"   {result['thumbnail'][:100]}{'...' if len(result['thumbnail']) > 100 else ''}")
                
                # Mostrar formatos disponibles (primeros 5)
                formats = result.get('formats', [])
                if formats:
                    print(f"\n📋 Formatos disponibles ({len(formats)} total):")
                    for fmt in formats[:5]:
                        quality = fmt.get('quality', 'N/A')
                        ext = fmt.get('ext', 'N/A')
                        filesize = fmt.get('filesize')
                        size_str = f" ({filesize//1024//1024}MB)" if filesize else ""
                        print(f"   • {quality}p {ext.upper()}{size_str}")
                    
                    if len(formats) > 5:
                        print(f"   ... y {len(formats) - 5} más")
            
            else:
                print(f"\n❌ Error: {result.get('error', 'Error desconocido')}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ EXCEPCIÓN (en {elapsed:.2f}s): {str(e)}")
        
        print("-" * 80)

if __name__ == "__main__":
    import time
    asyncio.run(main())