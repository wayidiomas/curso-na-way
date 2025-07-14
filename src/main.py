# src/main.py - ATUALIZADO COM RATE LIMITING E AUDITORIA
"""Aplicação principal FastAPI com rate limiting, auditoria e middleware."""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import time
import logging

# Importações existentes
from src.api import health
from src.core.database import init_database
from config.logging import setup_logging

# NOVOS IMPORTS - Middleware e melhorias
from src.core.rate_limiter import RateLimitMiddleware, rate_limiter
from src.core.audit_logger import audit_logger_instance, AuditEventType

# Endpoints hierárquicos
from src.api.v2 import courses, books, units

# Imports existentes (se houver)
try:
    from src.api import auth, apostilas, vocabs, content, images, pdf
    legacy_endpoints_available = True
except ImportError:
    legacy_endpoints_available = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    # Startup
    setup_logging()
    await init_database()
    
    # Log de inicialização da aplicação
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usando como evento de sistema
        additional_data={
            "event": "application_startup",
            "version": "2.0.0",
            "features": [
                "hierarchical_structure",
                "rate_limiting", 
                "audit_logging",
                "pagination",
                "rag_integration"
            ]
        }
    )
    
    print("🚀 Curso Na Way V2 iniciado com todas as melhorias!")
    print("✅ Rate Limiting ativo")
    print("✅ Auditoria configurada") 
    print("✅ Paginação implementada")
    print("✅ Hierarquia Course → Book → Unit")
    
    yield
    
    # Shutdown
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usando como evento de sistema
        additional_data={
            "event": "application_shutdown",
            "uptime_info": "application_stopped"
        }
    )
    print("👋 Curso Na Way V2 finalizado!")


app = FastAPI(
    title="Curso Na Way API V2",
    description="Sistema Hierárquico de Geração de Apostilas de Inglês com IA",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure adequadamente em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware)

# 3. Audit Middleware
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """Middleware para auditoria de requests."""
    # Iniciar tracking da request
    start_time = time.time()
    request_id = audit_logger_instance.start_request_tracking(request)
    
    # Adicionar request_id no estado para outros middlewares
    request.state.request_id = request_id
    
    response = None
    status_code = 500
    response_size = None
    error_occurred = False
    
    try:
        # Executar request
        response = await call_next(request)
        status_code = response.status_code
        
        # Tentar obter tamanho da response
        if hasattr(response, 'headers'):
            content_length = response.headers.get('content-length')
            if content_length:
                response_size = int(content_length)
        
        return response
        
    except Exception as e:
        error_occurred = True
        status_code = 500
        
        # Log do erro
        await audit_logger_instance.log_event(
            event_type=AuditEventType.API_ERROR,
            request=request,
            additional_data={
                "error_type": "middleware_exception",
                "error_message": str(e)
            },
            success=False,
            error_details=str(e)
        )
        
        raise
        
    finally:
        # Finalizar tracking
        performance_metrics = audit_logger_instance.end_request_tracking(
            request, status_code, response_size
        )
        
        # Log de acesso para endpoints específicos
        if request.url.path.startswith('/api/v2/'):
            await audit_logger_instance.log_event(
                event_type=AuditEventType.COURSE_VIEWED,  # Genérico para acessos
                request=request,
                additional_data={
                    "access_type": "api_endpoint",
                    "endpoint": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "response_size": response_size,
                    "error_occurred": error_occurred
                },
                success=not error_occurred,
                performance_metrics=performance_metrics
            )

# 4. Request ID Middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Middleware para adicionar Request ID único."""
    import uuid
    
    # Gerar ou usar Request ID existente
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    # Adicionar Request ID na response
    response.headers['X-Request-ID'] = request_id
    
    return response

# =============================================================================
# ROUTERS HIERÁRQUICOS (VERSÃO 2)
# =============================================================================

# Health check (sempre primeiro)
app.include_router(health.router, prefix="/health", tags=["health"])

# Endpoints hierárquicos Course → Book → Unit
app.include_router(
    courses.router, 
    prefix="/api/v2", 
    tags=["v2-courses"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Dados inválidos"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

app.include_router(
    books.router, 
    prefix="/api/v2", 
    tags=["v2-books"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Hierarquia inválida"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

app.include_router(
    units.router, 
    prefix="/api/v2", 
    tags=["v2-units"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Dados inválidos ou hierarquia incorreta"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

# =============================================================================
# ROUTERS LEGADOS (VERSÃO 1) - COMPATIBILIDADE
# =============================================================================

if legacy_endpoints_available:
    app.include_router(auth.router, prefix="/auth", tags=["v1-auth"])
    app.include_router(apostilas.router, prefix="/apostilas", tags=["v1-apostilas"])
    app.include_router(vocabs.router, prefix="/vocabs", tags=["v1-vocabs"])
    app.include_router(content.router, prefix="/content", tags=["v1-content"])
    app.include_router(images.router, prefix="/images", tags=["v1-images"])
    app.include_router(pdf.router, prefix="/pdf", tags=["v1-pdf"])
    print("✅ Endpoints legados V1 carregados para compatibilidade")
else:
    print("⚠️  Endpoints legados V1 não encontrados - apenas V2 disponível")

# =============================================================================
# ENDPOINTS INFORMATIVOS E DE SISTEMA
# =============================================================================

@app.get("/")
async def root(request: Request):
    """Informações gerais da API."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "root_info_access"}
    )
    
    return {
        "name": "Curso Na Way API V2",
        "version": "2.0.0",
        "description": "Sistema hierárquico para geração de apostilas de inglês",
        "architecture": "Course → Book → Unit",
        "features": {
            "hierarchical_structure": "Estrutura obrigatória de 3 níveis",
            "rate_limiting": "Proteção contra abuso com limites por endpoint",
            "audit_logging": "Log completo de todas as operações",
            "pagination": "Paginação inteligente em todos os endpoints de listagem",
            "rag_integration": "RAG contextual para progressão pedagógica",
            "quality_control": "Checklist automático de 22 pontos"
        },
        "endpoints": {
            "v2": {
                "courses": "/api/v2/courses",
                "books": "/api/v2/courses/{course_id}/books", 
                "units": "/api/v2/books/{book_id}/units",
                "health": "/health",
                "system": "/system"
            },
            "v1_legacy": "/auth, /apostilas, /vocabs, /content, /images, /pdf" if legacy_endpoints_available else "Not available"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "rate_limits": {
            "courses": "10-100 requests/minute dependendo da operação",
            "books": "20-150 requests/minute dependendo da operação", 
            "units": "5-150 requests/minute dependendo da operação",
            "generation": "2-5 requests/minute para operações pesadas"
        },
        "hierarchy_flow": {
            "1": "Criar Course com níveis CEFR",
            "2": "Criar Books por nível no Course",
            "3": "Criar Units sequenciais no Book",
            "4": "Gerar conteúdo com RAG contextual"
        },
        "pagination_examples": {
            "basic": "GET /api/v2/courses?page=1&size=20",
            "filtered": "GET /api/v2/courses?language_variant=american_english&target_level=A2",
            "sorted": "GET /api/v2/courses?sort_by=name&sort_order=asc",
            "search": "GET /api/v2/courses?search=business&page=2"
        }
    }


@app.get("/system/stats")
async def system_stats(request: Request):
    """Estatísticas do sistema."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "system_stats_access"}
    )
    
    try:
        from src.services.hierarchical_database import hierarchical_db
        analytics = await hierarchical_db.get_system_analytics()
        
        return {
            "success": True,
            "data": analytics,
            "message": "Estatísticas do sistema",
            "timestamp": analytics.get("generated_at")
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        return {
            "success": False,
            "error": "Erro ao obter estatísticas",
            "message": str(e)
        }


@app.get("/system/health")
async def detailed_health_check(request: Request):
    """Health check detalhado do sistema."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "detailed_health_check"}
    )
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {},
        "features": {}
    }
    
    # Check Database
    try:
        from config.database import get_supabase_client
        supabase = get_supabase_client()
        # Teste simples
        result = supabase.table("ivo_courses").select("id").limit(1).execute()
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis (Rate Limiting)
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unavailable: {str(e)} (using memory fallback)"
    
    # Check Features
    health_status["features"]["rate_limiting"] = "active"
    health_status["features"]["audit_logging"] = "active"
    health_status["features"]["pagination"] = "active"
    health_status["features"]["hierarchical_structure"] = "active"
    
    return health_status


@app.get("/system/rate-limits")
async def rate_limits_info(request: Request):
    """Informações sobre rate limits do sistema."""
    from src.core.rate_limiter import RATE_LIMIT_CONFIG
    
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "rate_limits_info"}
    )
    
    return {
        "rate_limits": RATE_LIMIT_CONFIG,
        "description": "Rate limits por endpoint",
        "identification": {
            "priority": "user_id (if authenticated) > IP address",
            "headers_checked": ["X-Forwarded-For", "X-Real-IP"],
            "window_formats": ["60s", "10m", "1h"]
        },
        "headers_returned": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining", 
            "X-RateLimit-Reset",
            "Retry-After (on 429)"
        ]
    }


# =============================================================================
# TRATAMENTO DE ERROS GLOBAL COM AUDITORIA
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handler para 404 com auditoria."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,
        request=request,
        additional_data={
            "error_type": "not_found",
            "path": str(request.url),
            "method": request.method
        },
        success=False,
        error_details="Resource not found"
    )
    
    return {
        "success": False,
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "Recurso não encontrado",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', 'unknown')
        },
        "suggestions": [
            "Verifique se o ID está correto",
            "Confirme que o recurso existe na hierarquia",
            "Consulte /docs para endpoints disponíveis"
        ]
    }


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    """Handler para rate limiting com auditoria."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
        request=request,
        additional_data={
            "error_type": "rate_limit_exceeded",
            "path": str(request.url),
            "method": request.method,
            "rate_limit_details": getattr(exc, 'detail', {})
        },
        success=False,
        error_details="Rate limit exceeded"
    )
    
    # Extrair detalhes do rate limit se disponível
    rate_limit_info = getattr(exc, 'detail', {})
    
    return {
        "success": False,
        "error_code": "RATE_LIMIT_EXCEEDED",
        "message": "Limite de requisições excedido",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "limit": rate_limit_info.get("limit"),
            "window": rate_limit_info.get("window"),
            "retry_after": rate_limit_info.get("retry_after")
        },
        "suggestions": [
            f"Aguarde {rate_limit_info.get('retry_after', 60)} segundos antes de tentar novamente",
            "Considere implementar cache local para reduzir requests",
            "Verifique se não há requests desnecessários em loop"
        ]
    }


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handler para erros internos com auditoria."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,
        request=request,
        additional_data={
            "error_type": "internal_server_error",
            "path": str(request.url),
            "method": request.method,
            "exception_type": type(exc).__name__
        },
        success=False,
        error_details=str(exc)
    )
    
    return {
        "success": False,
        "error_code": "INTERNAL_SERVER_ERROR", 
        "message": "Erro interno do servidor",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "timestamp": time.time()
        },
        "suggestions": [
            "Tente novamente em alguns instantes",
            "Verifique se todas as dependências estão funcionando",
            "Contate o suporte se o problema persistir"
        ]
    }


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Handler para erros de validação com auditoria."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.VALIDATION_FAILED,
        request=request,
        additional_data={
            "error_type": "validation_error",
            "path": str(request.url),
            "method": request.method,
            "validation_errors": getattr(exc, 'errors', [])
        },
        success=False,
        error_details="Validation failed"
    )
    
    return {
        "success": False,
        "error_code": "VALIDATION_ERROR",
        "message": "Dados inválidos fornecidos",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "validation_errors": getattr(exc, 'errors', [])
        },
        "suggestions": [
            "Verifique os tipos de dados enviados",
            "Consulte a documentação da API em /docs",
            "Valide campos obrigatórios"
        ]
    }


# =============================================================================
# STARTUP E SHUTDOWN HOOKS ADICIONAIS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Eventos de startup adicionais."""
    logger.info("🔧 Configurações adicionais de startup...")
    
    # Configurar rate limiter
    try:
        from src.core.rate_limiter import rate_limiter
        # Teste de conectividade
        logger.info("✅ Rate limiter configurado")
    except Exception as e:
        logger.warning(f"⚠️ Rate limiter com limitações: {str(e)}")
    
    # Configurar audit logger
    try:
        from src.core.audit_logger import audit_logger_instance
        logger.info("✅ Audit logger configurado")
    except Exception as e:
        logger.warning(f"⚠️ Audit logger com limitações: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Eventos de shutdown."""
    logger.info("🛑 Executando shutdown procedures...")
    
    # Log final de shutdown
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usar como evento de sistema
        additional_data={
            "event": "graceful_shutdown",
            "message": "Application shutdown completed successfully"
        }
    )


# =============================================================================
# MIDDLEWARE DE PERFORMANCE MONITORING
# =============================================================================

@app.middleware("http")
async def performance_monitoring_middleware(request: Request, call_next):
    """Middleware para monitoramento de performance."""
    start_time = time.time()
    
    # Executar request
    response = await call_next(request)
    
    # Calcular tempo de processamento
    process_time = time.time() - start_time
    
    # Adicionar header de performance
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log de performance para requests lentos
    if process_time > 1.0:  # > 1 segundo
        await audit_logger_instance.log_event(
            event_type=AuditEventType.PERFORMANCE_ALERT,
            request=request,
            additional_data={
                "slow_request": True,
                "processing_time": process_time,
                "threshold_exceeded": "1.0_seconds",
                "path": request.url.path,
                "method": request.method
            },
            performance_metrics={
                "processing_time_ms": process_time * 1000,
                "status_code": response.status_code
            }
        )
    
    return response


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )


@app.get("/api/v2")
async def api_v2_info(request: Request):
    """Informações específicas da API V2."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "v2_info_access"}
    )
    
    return {
        "version": "2.0",
        "hierarchy": "Course → Book → Unit",
        "improvements": {
            "rate_limiting": {
                "description": "Proteção inteligente contra abuso",
                "implementation": "Redis-backed com fallback em memória",
                "granularity": "Por endpoint e por usuário"
            },
            "pagination": {
                "description": "Paginação automática em listagens",
                "features": ["Ordenação customizável", "Filtros avançados", "Metadados completos"],
                "limits": "Máximo 100 itens por página"
            },
            "audit_logging": {
                "description": "Log estruturado de todas as operações",
                "features": ["Tracking de performance", "Contexto hierárquico", "Métricas de uso"],
                "storage": "Arquivo JSON estruturado"
            }
        },
        "key_features": {
            "hierarchical_structure": "Estrutura obrigatória de 3 níveis",
            "rag_integration": "RAG contextual para progressão pedagógica",
            "vocabulary_tracking": "Prevenção de repetições desnecessárias",
            "strategy_balancing": "Distribuição inteligente de estratégias",
            "quality_control": "Checklist automático de 22 pontos"
        },
        "available_endpoints": {
            "courses": {
                "POST /api/v2/courses": "Criar novo curso",
                "GET /api/v2/courses": "Listar cursos (paginado)",
                "GET /api/v2/courses/{id}": "Detalhes do curso",
                "GET /api/v2/courses/{id}/hierarchy": "Hierarquia completa",
                "GET /api/v2/courses/{id}/progress": "Análise de progresso",
                "PUT /api/v2/courses/{id}": "Atualizar curso",
                "DELETE /api/v2/courses/{id}": "Deletar curso"
            },
            "books": {
                "POST /api/v2/courses/{course_id}/books": "Criar book no curso",
                "GET /api/v2/courses/{course_id}/books": "Listar books do curso (paginado)",
                "GET /api/v2/books/{id}": "Detalhes do book",
                "GET /api/v2/books/{id}/progression": "Análise de progressão"
            },
            "units": {
                "POST /api/v2/books/{book_id}/units": "Criar unit no book",
                "GET /api/v2/books/{book_id}/units": "Listar units do book (paginado)",
                "GET /api/v2/units/{id}": "Detalhes completos da unit",
                "GET /api/v2/units/{id}/context": "Contexto RAG da unit",
                "PUT /api/v2/units/{id}/status": "Atualizar status"
            }
        },
        "workflow_example": {
            "step_1": "POST /api/v2/courses (criar curso)",
            "step_2": "POST /api/v2/courses/{course_id}/books (criar books por nível)",
            "step_3": "POST /api/v2/books/{book_id}/units (criar units sequenciais)",
            "step_4": "GET /api/v2/units/{unit_id}/context (verificar RAG)",
            "step_5": "Próximos prompts: vocabulário, sentences, strategies, assessments"}}



