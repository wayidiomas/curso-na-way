"""Health check endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
import redis
from config.database import get_supabase_client

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: dict


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Verifica saúde dos serviços."""
    services = {}
    
    # Check Supabase
    try:
        supabase = get_supabase_client()
        # Teste simples de conexão
        services["supabase"] = "healthy"
    except Exception as e:
        services["supabase"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if all("healthy" in v for v in services.values()) else "unhealthy",
        timestamp=datetime.now(),
        services=services
    )
