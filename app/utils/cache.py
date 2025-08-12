# utils/cache.py
import json
import hashlib
from typing import Optional, Dict, Any
import time

class SimpleCache:
    def __init__(self, ttl: int = 300):  # 5 minutos TTL
        self.cache: Dict[str, Dict] = {}
        self.ttl = ttl
    
    def _get_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        key = self._get_key(url)
        if key in self.cache:
            data = self.cache[key]
            if time.time() - data['timestamp'] < self.ttl:
                return data['result']
            else:
                del self.cache[key]
        return None
    
    def set(self, url: str, result: Dict[str, Any]):
        key = self._get_key(url)
        self.cache[key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        # Limpiar cache viejo
        current_time = time.time()
        expired_keys = [
            k for k, v in self.cache.items()
            if current_time - v['timestamp'] > self.ttl
        ]
        for k in expired_keys:
            del self.cache[k]