# src/core/rate_limiter.py
"""Sistema de Rate Limiting para endpoints hierárquicos."""

import time
import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import redis
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import json

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter usando Redis com diferentes políticas por endpoint."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Inicializar rate limiter.
        
        Args:
            redis_url: URL do Redis
        """
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()  # Testar conexão
        except Exception as e:
            logger.warning(f"Redis não disponível, usando cache em memória: {str(e)}")
            self.redis_client = None
            self._memory_cache: Dict[str, Dict] = {}
    
    def _get_client_identifier(self, request: Request) -> str:
        """Obter identificador único do cliente."""
        # Prioridade: user_id (se autenticado) > IP
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fallback para IP (considerando proxies)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _get_rate_limit_key(self, identifier: str, endpoint: str, window: str) -> str:
        """Gerar chave para rate limiting."""
        timestamp = int(time.time() // self._get_window_seconds(window))
        return f"rate_limit:{identifier}:{endpoint}:{timestamp}"
    
    def _get_window_seconds(self, window: str) -> int:
        """Converter window string para segundos."""
        if window.endswith('s'):
            return int(window[:-1])
        elif window.endswith('m'):
            return int(window[:-1]) * 60
        elif window.endswith('h'):
            return int(window[:-1]) * 3600
        return 60  # Default: 1 minuto
    
    async def is_allowed(
        self, 
        request: Request, 
        endpoint: str, 
        limit: int, 
        window: str = "60s"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Verificar se request é permitido.
        
        Args:
            request: FastAPI Request
            endpoint: Nome do endpoint
            limit: Número máximo de requests
            window: Janela de tempo (ex: "60s", "10m", "1h")
            
        Returns:
            Tuple[bool, dict]: (is_allowed, rate_limit_info)
        """
        identifier = self._get_client_identifier(request)
        key = self._get_rate_limit_key(identifier, endpoint, window)
        window_seconds = self._get_window_seconds(window)
        
        try:
            if self.redis_client:
                # Usar Redis
                current_count = await self._redis_check_and_increment(key, window_seconds)
            else:
                # Usar cache em memória
                current_count = self._memory_check_and_increment(key, window_seconds)
            
            is_allowed = current_count <= limit
            
            rate_info = {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": int(time.time()) + window_seconds,
                "window": window,
                "identifier": identifier,
                "endpoint": endpoint
            }
            
            # Log de rate limiting
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded",
                    extra={
                        "identifier": identifier,
                        "endpoint": endpoint,
                        "limit": limit,
                        "current_count": current_count,
                        "window": window,
                        "user_agent": request.headers.get("User-Agent", ""),
                        "path": request.url.path
                    }
                )
            
            return is_allowed, rate_info
            
        except Exception as e:
            logger.error(f"Erro no rate limiting: {str(e)}")
            # Em caso de erro, permitir o request (fail-open)
            return True, {"error": "rate_limiter_unavailable"}
    
    async def _redis_check_and_increment(self, key: str, window_seconds: int) -> int:
        """Verificar e incrementar contador no Redis."""
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = pipe.execute()
        return results[0]
    
    def _memory_check_and_increment(self, key: str, window_seconds: int) -> int:
        """Verificar e incrementar contador em memória."""
        now = time.time()
        
        # Limpar entradas expiradas
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if v.get('expires_at', 0) < now
        ]
        for k in expired_keys:
            del self._memory_cache[k]
        
        # Incrementar contador
        if key not in self._memory_cache:
            self._memory_cache[key] = {
                'count': 1,
                'expires_at': now + window_seconds
            }
        else:
            self._memory_cache[key]['count'] += 1
        
        return self._memory_cache[key]['count']


# Configurações de rate limiting por endpoint
RATE_LIMIT_CONFIG = {
    # Course operations
    "create_course": {"limit": 10, "window": "60s"},
    "list_courses": {"limit": 100, "window": "60s"},
    "get_course": {"limit": 200, "window": "60s"},
    "get_course_hierarchy": {"limit": 50, "window": "60s"},
    "get_course_progress": {"limit": 30, "window": "60s"},
    
    # Book operations  
    "create_book": {"limit": 20, "window": "60s"},
    "list_books": {"limit": 150, "window": "60s"},
    "get_book": {"limit": 200, "window": "60s"},
    "get_book_progression": {"limit": 50, "window": "60s"},
    
    # Unit operations (mais restritivos por serem pesados)
    "create_unit": {"limit": 5, "window": "60s"},
    "list_units": {"limit": 100, "window": "60s"},
    "get_unit": {"limit": 150, "window": "60s"},
    "get_unit_context": {"limit": 30, "window": "60s"},
    "update_unit_status": {"limit": 50, "window": "60s"},
    
    # Operações pesadas (muito restritivos)
    "generate_vocabulary": {"limit": 3, "window": "60s"},
    "generate_content": {"limit": 2, "window": "60s"},
    "analyze_images": {"limit": 5, "window": "60s"},
}


# Instância global
rate_limiter = RateLimiter()


def get_rate_limit_for_endpoint(endpoint: str) -> Dict[str, any]:
    """Obter configuração de rate limit para endpoint."""
    return RATE_LIMIT_CONFIG.get(endpoint, {"limit": 60, "window": "60s"})


async def rate_limit_dependency(
    request: Request,
    endpoint_name: str
) -> None:
    """
    Dependency para rate limiting.
    
    Args:
        request: FastAPI Request
        endpoint_name: Nome do endpoint para buscar configuração
        
    Raises:
        HTTPException: Se rate limit for excedido
    """
    config = get_rate_limit_for_endpoint(endpoint_name)
    
    is_allowed, rate_info = await rate_limiter.is_allowed(
        request=request,
        endpoint=endpoint_name,
        limit=config["limit"],
        window=config["window"]
    )
    
    if not is_allowed:
        # Adicionar headers de rate limiting na resposta
        headers = {
            "X-RateLimit-Limit": str(rate_info["limit"]),
            "X-RateLimit-Remaining": str(rate_info["remaining"]),
            "X-RateLimit-Reset": str(rate_info["reset_time"]),
            "X-RateLimit-Window": rate_info["window"],
            "Retry-After": str(rate_info["reset_time"] - int(time.time()))
        }
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded for {endpoint_name}",
                "limit": rate_info["limit"],
                "window": rate_info["window"],
                "retry_after": rate_info["reset_time"] - int(time.time())
            },
            headers=headers
        )
    
    # Adicionar info de rate limit no estado da request para logs
    request.state.rate_limit_info = rate_info


# Middleware para adicionar headers de rate limiting em respostas
class RateLimitMiddleware:
    """Middleware para adicionar headers de rate limiting."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Adicionar headers de rate limiting se disponíveis
                request = scope.get("fastapi_request")
                if request and hasattr(request.state, 'rate_limit_info'):
                    rate_info = request.state.rate_limit_info
                    if "error" not in rate_info:
                        headers = message.get("headers", [])
                        headers.extend([
                            (b"x-ratelimit-limit", str(rate_info["limit"]).encode()),
                            (b"x-ratelimit-remaining", str(rate_info["remaining"]).encode()),
                            (b"x-ratelimit-reset", str(rate_info["reset_time"]).encode()),
                        ])
                        message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)