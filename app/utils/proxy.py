import random
import requests
import time
from typing import List, Optional, Dict
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ProxyRotator:
    """Gestor de rotación de proxies para yt-dlp"""
    
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = [proxy.strip() for proxy in proxy_list if proxy.strip()]
        self.working_proxies = []
        self.failed_proxies = []
        self.current_index = 0
        self.last_check = 0
        self.check_interval = 300  # 5 minutos
        
        if self.proxy_list:
            self.validate_proxies()
    
    def validate_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """Valida si un proxy funciona"""
        try:
            # Parsear el proxy
            if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                proxy = f"http://{proxy}"
            
            proxies = {
                'http': proxy,
                'https': proxy
            }
            
            # Probar con una URL simple
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            if response.status_code == 200:
                logger.info(f"Proxy válido: {proxy}")
                return True
                
        except Exception as e:
            logger.warning(f"Proxy inválido {proxy}: {e}")
            
        return False
    
    def validate_proxies(self):
        """Valida todos los proxies de la lista"""
        logger.info("Validando proxies...")
        self.working_proxies = []
        self.failed_proxies = []
        
        for proxy in self.proxy_list:
            if self.validate_proxy(proxy):
                self.working_proxies.append(proxy)
            else:
                self.failed_proxies.append(proxy)
        
        logger.info(f"Proxies válidos: {len(self.working_proxies)}/{len(self.proxy_list)}")
        self.last_check = time.time()
    
    def get_next_proxy(self) -> Optional[str]:
        """Obtiene el siguiente proxy en rotación"""
        # Re-validar proxies cada cierto tiempo
        if time.time() - self.last_check > self.check_interval:
            self.validate_proxies()
        
        if not self.working_proxies:
            logger.warning("No hay proxies disponibles")
            return None
        
        proxy = self.working_proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.working_proxies)
        
        return proxy
    
    def get_random_proxy(self) -> Optional[str]:
        """Obtiene un proxy aleatorio"""
        if not self.working_proxies:
            return None
            
        return random.choice(self.working_proxies)
    
    def mark_proxy_failed(self, proxy: str):
        """Marca un proxy como fallido y lo remueve temporalmente"""
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            if proxy not in self.failed_proxies:
                self.failed_proxies.append(proxy)
            logger.warning(f"Proxy marcado como fallido: {proxy}")
    
    def get_proxy_dict(self, proxy: str) -> Dict[str, str]:
        """Convierte proxy string a diccionario para requests/yt-dlp"""
        if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            proxy = f"http://{proxy}"
            
        return {
            'http': proxy,
            'https': proxy
        }
    
    def get_yt_dlp_proxy_option(self) -> Optional[str]:
        """Obtiene proxy en formato para yt-dlp"""
        proxy = self.get_next_proxy()
        if proxy:
            # yt-dlp acepta el proxy directamente como string
            if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                proxy = f"http://{proxy}"
            return proxy
        return None
    
    def test_proxy_with_youtube(self, proxy: str) -> bool:
        """Prueba específicamente si el proxy funciona con YouTube"""
        try:
            proxies = self.get_proxy_dict(proxy)
            
            # Probar acceso a YouTube
            response = requests.get(
                'https://www.youtube.com',
                proxies=proxies,
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            if response.status_code == 200 and 'youtube' in response.text.lower():
                logger.info(f"Proxy funciona con YouTube: {proxy}")
                return True
                
        except Exception as e:
            logger.warning(f"Proxy falló con YouTube {proxy}: {e}")
            
        return False
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de los proxies"""
        return {
            'total_proxies': len(self.proxy_list),
            'working_proxies': len(self.working_proxies),
            'failed_proxies': len(self.failed_proxies),
            'last_check': self.last_check,
            'current_proxy_index': self.current_index
        }

class ProxyTester:
    """Utilidades para probar proxies"""
    
    @staticmethod
    def test_proxy_list(proxy_list: List[str]) -> Dict:
        """Prueba una lista de proxies y devuelve estadísticas"""
        rotator = ProxyRotator(proxy_list)
        
        results = {
            'working': rotator.working_proxies,
            'failed': rotator.failed_proxies,
            'stats': rotator.get_stats()
        }
        
        return results
    
    @staticmethod
    def load_proxies_from_file(file_path: str) -> List[str]:
        """Carga proxies desde un archivo de texto"""
        try:
            with open(file_path, 'r') as f:
                proxies = [line.strip() for line in f.readlines() if line.strip()]
            logger.info(f"Cargados {len(proxies)} proxies desde {file_path}")
            return proxies
        except Exception as e:
            logger.error(f"Error cargando proxies desde archivo: {e}")
            return []