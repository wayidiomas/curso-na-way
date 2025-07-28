# src/main.py - ATUALIZADO COM NOVA ESTRUTURA DA API
"""Aplicação principal FastAPI com rate limiting, auditoria e estrutura hierárquica completa."""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import time
import logging

# Importações da nova estrutura da API
from src.api import (
    AVAILABLE_ROUTERS, API_INFO, API_TAGS, 
    MIDDLEWARE_CONFIG, get_api_overview, validate_api_health,
    get_hierarchical_flow
)

# Importações existentes
from src.core.database import init_database
from config.logging import setup_logging

# NOVOS IMPORTS - Middleware e melhorias
from src.core.rate_limiter import RateLimitMiddleware, rate_limiter
from src.core.audit_logger import audit_logger_instance, AuditEventType

# Imports legados (se houver)
try:
    from src.api import auth, apostilas, vocabs, content, images, pdf
    legacy_endpoints_available = True
except ImportError:
    legacy_endpoints_available = False

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação com validação da API."""
    # Startup
    setup_logging()
    await init_database()
    
    # Validar configuração da API
    api_health = validate_api_health()
    if api_health["configuration_valid"]:
        logger.info(f"✅ API V2 configurada corretamente ({api_health['completion_status']['percentage']:.1f}% completa)")
        logger.info(f"📊 Módulos carregados: {api_health['completion_status']['loaded']}/{api_health['completion_status']['expected']}")
    else:
        logger.warning(f"⚠️ Problemas na configuração da API: {api_health['missing_modules']}")
    
    # Log de inicialização da aplicação
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usando como evento de sistema
        additional_data={
            "event": "application_startup",
            "version": API_INFO["version"],
            "api_health": api_health,
            "features": API_INFO["features"]
        }
    )
    
    print("🚀 Curso Na Way V2 iniciado com estrutura hierárquica completa!")
    print(f"✅ API V2: {api_health['completion_status']['percentage']:.1f}% implementada")
    print("✅ Rate Limiting ativo")
    print("✅ Auditoria configurada") 
    print("✅ Paginação implementada")
    print("✅ Hierarquia Course → Book → Unit")
    print(f"📚 Módulos V2: {', '.join(AVAILABLE_ROUTERS['v2'].keys())}")
    
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
    title=API_INFO["name"],
    description=API_INFO["description"],
    version=API_INFO["version"],
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": tag_name, "description": tag_info.get("description", "")} 
        for tag_name, tag_info in API_TAGS.items()
    ]
)

# =============================================================================
# MIDDLEWARE CONFIGURATION - USANDO CONFIGURAÇÕES CENTRALIZADAS
# =============================================================================

# 1. CORS Middleware - Usando configuração centralizada
app.add_middleware(
    CORSMiddleware,
    allow_origins=MIDDLEWARE_CONFIG["cors"]["allow_origins"],
    allow_credentials=True,
    allow_methods=MIDDLEWARE_CONFIG["cors"]["allow_methods"],
    allow_headers=MIDDLEWARE_CONFIG["cors"]["allow_headers"],
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
# ROUTERS V2 - USANDO ESTRUTURA CENTRALIZADA
# =============================================================================

# Health check (sempre primeiro)
app.include_router(
    AVAILABLE_ROUTERS["health"], 
    prefix="/health", 
    tags=["health"]
)

# Registrar todos os routers V2 automaticamente
v2_routers = AVAILABLE_ROUTERS["v2"]

# Courses
app.include_router(
    v2_routers["courses"], 
    prefix="/api/v2", 
    tags=["v2-courses"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Dados inválidos"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

# Books
app.include_router(
    v2_routers["books"], 
    prefix="/api/v2", 
    tags=["v2-books"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Hierarquia inválida"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

# Units
app.include_router(
    v2_routers["units"], 
    prefix="/api/v2", 
    tags=["v2-units"],
    responses={
        404: {"description": "Recurso não encontrado"},
        400: {"description": "Dados inválidos ou hierarquia incorreta"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro interno"}
    }
)

# Vocabulary
app.include_router(
    v2_routers["vocabulary"], 
    prefix="/api/v2", 
    tags=["v2-vocabulary"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Unidade não pronta para geração de vocabulário"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de vocabulário"}
    }
)

# Sentences
app.include_router(
    v2_routers["sentences"], 
    prefix="/api/v2", 
    tags=["v2-sentences"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Vocabulário necessário antes de gerar sentences"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de sentences"}
    }
)

# Tips (Estratégias lexicais)
app.include_router(
    v2_routers["tips"], 
    prefix="/api/v2", 
    tags=["v2-tips"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Apenas para unidades lexicais"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de estratégias TIPS"}
    }
)

# Grammar (Estratégias gramaticais)
app.include_router(
    v2_routers["grammar"], 
    prefix="/api/v2", 
    tags=["v2-grammar"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Apenas para unidades gramaticais"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de estratégias GRAMMAR"}
    }
)

# Assessments
app.include_router(
    v2_routers["assessments"], 
    prefix="/api/v2", 
    tags=["v2-assessments"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Conteúdo da unidade incompleto"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de assessments"}
    }
)

# Q&A
app.include_router(
    v2_routers["qa"], 
    prefix="/api/v2", 
    tags=["v2-qa"],
    responses={
        404: {"description": "Unidade não encontrada"},
        400: {"description": "Conteúdo da unidade necessário"},
        429: {"description": "Rate limit excedido"},
        500: {"description": "Erro na geração de Q&A"}
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
# ENDPOINTS INFORMATIVOS E DE SISTEMA - USANDO ESTRUTURA CENTRALIZADA
# =============================================================================

@app.get("/", tags=["root"])
async def root(request: Request):
    """Informações gerais da API usando estrutura centralizada."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "root_info_access"}
    )
    
    hierarchical_flow = get_hierarchical_flow()
    
    return {
        "name": API_INFO["name"],
        "version": API_INFO["version"],
        "description": API_INFO["description"],
        "architecture": API_INFO["architecture"],
        "features": API_INFO["features"],
        "author": API_INFO.get("author", "Curso Na Way"),
        "endpoints": {
            "v2": {
                "courses": "/api/v2/courses",
                "books": "/api/v2/courses/{course_id}/books", 
                "units": "/api/v2/books/{book_id}/units",
                "vocabulary": "/api/v2/units/{unit_id}/vocabulary",
                "sentences": "/api/v2/units/{unit_id}/sentences",
                "tips": "/api/v2/units/{unit_id}/tips",
                "grammar": "/api/v2/units/{unit_id}/grammar",
                "assessments": "/api/v2/units/{unit_id}/assessments",
                "qa": "/api/v2/units/{unit_id}/qa",
                "health": "/health",
                "system": "/system"
            },
            "v1_legacy": "/auth, /apostilas, /vocabs, /content, /images, /pdf" if legacy_endpoints_available else "Not available"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "api_overview": "/api/overview"
        },
        "hierarchical_flow": hierarchical_flow,
        "content_generation_flow": [
            "1. POST /api/v2/units/{id}/vocabulary (RAG + MCP images)",
            "2. POST /api/v2/units/{id}/sentences (conectadas ao vocabulário)",
            "3. POST /api/v2/units/{id}/tips (unidades lexicais)",
            "3. POST /api/v2/units/{id}/grammar (unidades gramaticais)",
            "4. POST /api/v2/units/{id}/assessments (2 atividades balanceadas)",
            "5. POST /api/v2/units/{id}/qa (opcional - Q&A pedagógico)"
        ],
        "rag_features": {
            "vocabulary_deduplication": "Prevenção de repetições com contexto histórico",
            "strategy_balancing": "Distribuição inteligente de estratégias TIPS/GRAMMAR",
            "assessment_variety": "Seleção automática de 2/7 tipos de atividades",
            "progression_analysis": "Análise contínua de progressão pedagógica"
        }
    }


@app.get("/api/overview", tags=["root"])
async def api_overview_endpoint(request: Request):
    """Visão geral completa da API usando função centralizada."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "api_overview_access"}
    )
    
    return get_api_overview()


@app.get("/api/v2", tags=["v2-info"])
async def api_v2_info(request: Request):
    """Informações específicas da API V2 com dados centralizados."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "v2_info_access"}
    )
    
    # Obter status de validação atualizado
    api_health = validate_api_health()
    hierarchical_flow = get_hierarchical_flow()
    
    return {
        "version": "2.0",
        "api_health": api_health,
        "hierarchy": API_INFO["architecture"],
        "implementation_status": {
            "completion_percentage": api_health["completion_status"]["percentage"],
            "modules_loaded": api_health["completion_status"]["loaded"],
            "modules_expected": api_health["completion_status"]["expected"],
            "missing_modules": api_health.get("missing_modules", [])
        },
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
            },
            "rag_integration": {
                "description": "RAG contextual para progressão pedagógica",
                "features": ["Prevenção de repetições", "Balanceamento de estratégias", "Análise de qualidade"],
                "intelligence": "Contexto hierárquico completo Course→Book→Unit"
            }
        },
        "hierarchical_flow": hierarchical_flow,
        "content_generation": {
            "vocabulary": {
                "endpoint": "POST /api/v2/units/{id}/vocabulary",
                "features": ["RAG deduplication", "MCP image analysis", "IPA phonemes", "CEFR adaptation"],
                "dependencies": ["unit_created", "images_uploaded"]
            },
            "sentences": {
                "endpoint": "POST /api/v2/units/{id}/sentences",
                "features": ["Vocabulary integration", "Contextual coherence", "Progression awareness"],
                "dependencies": ["vocabulary_generated"]
            },
            "strategies": {
                "tips": {
                    "endpoint": "POST /api/v2/units/{id}/tips",
                    "description": "6 estratégias lexicais com seleção inteligente",
                    "strategies": ["afixacao", "substantivos_compostos", "colocacoes", "expressoes_fixas", "idiomas", "chunks"],
                    "for": "lexical_units"
                },
                "grammar": {
                    "endpoint": "POST /api/v2/units/{id}/grammar",
                    "description": "2 estratégias gramaticais com foco brasileiro",
                    "strategies": ["explicacao_sistematica", "prevencao_erros_l1"],
                    "for": "grammar_units",
                    "specialization": "Prevenção de interferência português→inglês"
                }
            },
            "assessments": {
                "endpoint": "POST /api/v2/units/{id}/assessments",
                "features": ["7 tipos disponíveis", "Seleção automática de 2", "Balanceamento inteligente"],
                "types": ["cloze_test", "gap_fill", "reordenacao", "transformacao", "multipla_escolha", "verdadeiro_falso", "matching"]
            },
            "qa": {
                "endpoint": "POST /api/v2/units/{id}/qa",
                "features": ["Taxonomia de Bloom", "Perguntas de pronúncia", "Progressão pedagógica"],
                "cognitive_levels": ["remember", "understand", "apply", "analyze", "evaluate", "create"]
            }
        },
        "workflow_example": {
            "step_1": "POST /api/v2/courses (criar curso com níveis CEFR)",
            "step_2": "POST /api/v2/courses/{course_id}/books (criar books por nível)",
            "step_3": "POST /api/v2/books/{book_id}/units (criar units com imagens)",
            "step_4": "GET /api/v2/units/{unit_id}/context (verificar contexto RAG)",
            "step_5": "POST /api/v2/units/{unit_id}/vocabulary (gerar vocabulário)",
            "step_6": "POST /api/v2/units/{unit_id}/sentences (gerar sentences)",
            "step_7": "POST /api/v2/units/{unit_id}/tips OU /grammar (estratégias)",
            "step_8": "POST /api/v2/units/{unit_id}/assessments (finalizar unidade)",
            "step_9": "POST /api/v2/units/{unit_id}/qa (opcional - Q&A pedagógico)"
        }
    }


@app.get("/system/stats", tags=["system"])
async def system_stats(request: Request):
    """Estatísticas do sistema com informações da API."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "system_stats_access"}
    )
    
    try:
        from src.services.hierarchical_database import hierarchical_db
        analytics = await hierarchical_db.get_system_analytics()
        
        # Adicionar informações da API
        api_health = validate_api_health()
        
        return {
            "success": True,
            "data": {
                **analytics,
                "api_status": {
                    "version": API_INFO["version"],
                    "health": api_health,
                    "features_enabled": API_INFO["features"],
                    "modules_loaded": list(AVAILABLE_ROUTERS["v2"].keys())
                }
            },
            "message": "Estatísticas do sistema com status da API",
            "timestamp": analytics.get("generated_at")
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        return {
            "success": False,
            "error": "Erro ao obter estatísticas",
            "message": str(e),
            "api_health": validate_api_health()
        }


@app.get("/system/health", tags=["system"])
async def detailed_health_check(request: Request):
    """Health check detalhado do sistema com validação da API."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "detailed_health_check"}
    )
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {},
        "features": {},
        "api_configuration": validate_api_health()
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
    health_status["features"]["rag_integration"] = "active"
    
    # Verificar se API está degradada
    if not health_status["api_configuration"]["configuration_valid"]:
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/system/rate-limits", tags=["system"])
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
        "global_config": MIDDLEWARE_CONFIG["rate_limiting"],
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
            "Consulte /docs para endpoints disponíveis",
            "Verificar /api/overview para estrutura da API"
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
            "Verifique se não há requests desnecessários em loop",
            "Consulte /system/rate-limits para limites específicos"
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
            "Contate o suporte se o problema persistir",
            "Consulte /system/health para status dos serviços"
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
            "validation_errors": getattr(exc, 'errors', []),
            "request_id": getattr(request.state, 'request_id', 'unknown')   