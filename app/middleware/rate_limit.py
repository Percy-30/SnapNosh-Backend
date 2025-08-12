# app/middleware/rate_limit.py
import time
import asyncio
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class YouTubeRateLimit:
    """Rate limiter específico para YouTube para evitar bloqueos"""
    
    def __init__(self, min_delay: float = 2.0):
        self.last_requests: Dict[str, float] = {}
        self.min_delay = min_delay
        self.global_last_request = 0.0
    
    async def wait_if_needed(self, client_ip: str):
        """Aplica rate limiting por IP y globalmente"""
        now = time.time()
        
        # Rate limiting por IP
        if client_ip in self.last_requests:
            elapsed = now - self.last_requests[client_ip]
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                logger.info(f"⏳ Rate limiting IP {client_ip}: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # Rate limiting global (para evitar ráfagas)
        global_elapsed = now - self.global_last_request
        if global_elapsed < 1.0:  # Mínimo 1s entre cualquier request
            global_wait = 1.0 - global_elapsed
            await asyncio.sleep(global_wait)
        
        # Actualizar timestamps
        self.last_requests[client_ip] = time.time()
        self.global_last_request = time.time()
        
        # Limpiar entradas viejas (cada 100 requests)
        if len(self.last_requests) > 100:
            cutoff = time.time() - 300  # 5 minutos
            self.last_requests = {
                ip: timestamp for ip, timestamp in self.last_requests.items()
                if timestamp > cutoff
            }