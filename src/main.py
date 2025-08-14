# src/main.py - IVO V2 Sistema Hierárquico Course → Book → Unit
"""
🚀 IVO V2 - Intelligent Vocabulary Organizer
Sistema avançado de geração hierárquica de unidades pedagógicas com IA generativa,
RAG contextual e metodologias comprovadas para ensino de idiomas.

Arquitetura: Course → Book → Unit → Content (Vocabulary, Sentences, Strategies, Assessments)
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import time
import logging
from typing import Dict, Any

# Core imports - Database e configuração
from src.core.database import init_database
from config.logging import setup_logging

# Middleware e sistema de qualidade
from src.core.rate_limiter import RateLimitMiddleware, rate_limiter
from src.core.audit_logger import audit_logger_instance, AuditEventType

# API V2 imports - Estrutura hierárquica
try:
    from src.api.v2.courses import router as courses_router
    from src.api.v2.books import router as books_router
    from src.api.v2.units import router as units_router
    from src.api.v2.vocabulary import router as vocabulary_router
    from src.api.v2.sentences import router as sentences_router
    from src.api.v2.tips import router as tips_router
    from src.api.v2.grammar import router as grammar_router
    from src.api.v2.assessments import router as assessments_router
    from src.api.v2.qa import router as qa_router
    from src.api.health import router as health_router
    
    v2_endpoints_available = True
    v2_missing_modules = []
    
except ImportError as e:
    v2_endpoints_available = False
    v2_missing_modules = str(e).split("'")[1] if "'" in str(e) else str(e)
    logging.warning(f"⚠️ Módulos V2 faltando: {v2_missing_modules}")

# Imports legados V1 (compatibilidade)
try:
    from src.api import auth, apostilas, vocabs, content, images, pdf
    legacy_endpoints_available = True
except ImportError:
    legacy_endpoints_available = False

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÕES DA API V2
# =============================================================================

API_INFO = {
    "name": "IVO V2 - Intelligent Vocabulary Organizer",
    "version": "2.0.0",
    "description": """
    🚀 Sistema avançado de geração hierárquica de materiais didáticos para ensino de idiomas.
    
    **Arquitetura Hierárquica:**
    📚 COURSE → 📖 BOOK → 📑 UNIT → 🔤 CONTENT
    
    **Principais Recursos:**
    • 🧠 RAG Hierárquico para prevenção de repetições
    • 🗣️ Validação IPA com 35+ símbolos fonéticos
    • 📊 6 Estratégias TIPS + 2 Estratégias GRAMMAR
    • 🎯 7 Tipos de Assessment com balanceamento automático
    • 🎓 Q&A baseado na Taxonomia de Bloom
    • 🇧🇷 Prevenção de interferência L1→L2 (português→inglês)
    """,
    "architecture": "Course → Book → Unit → Content",
    "features": [
        "Hierarquia pedagógica obrigatória",
        "RAG contextual para progressão",
        "Rate limiting inteligente",
        "Auditoria empresarial completa",
        "Paginação avançada com filtros",
        "Validação IPA automática",
        "MCP Image Analysis",
        "Metodologias científicas integradas"
    ]
}

MIDDLEWARE_CONFIG = {
    "cors": {
        "allow_origins": ["*"],
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"]
    },
    "rate_limiting": {
        "enabled": True,
        "fallback_to_memory": True
    }
}

API_TAGS = {
    "health": {"description": "🏥 Health checks e monitoramento do sistema"},
    "system": {"description": "⚙️ Informações e estatísticas do sistema"},
    "v2-courses": {"description": "📚 Gestão de cursos completos com níveis CEFR"},
    "v2-books": {"description": "📖 Gestão de books organizados por nível"},
    "v2-units": {"description": "📑 Gestão de unidades pedagógicas com imagens"},
    "v2-vocabulary": {"description": "🔤 Geração de vocabulário com RAG + MCP"},
    "v2-sentences": {"description": "📝 Geração de sentences conectadas"},
    "v2-tips": {"description": "💡 Estratégias TIPS para unidades lexicais"},
    "v2-grammar": {"description": "📐 Estratégias GRAMMAR para unidades gramaticais"},
    "v2-assessments": {"description": "🎯 Geração de atividades balanceadas"},
    "v2-qa": {"description": "❓ Q&A pedagógico com Taxonomia de Bloom"},
    "v1-legacy": {"description": "🔄 Endpoints legados para compatibilidade"}
}

def get_api_health() -> Dict[str, Any]:
    """Verifica saúde da configuração da API."""
    expected_modules = 9  # courses, books, units, vocabulary, sentences, tips, grammar, assessments, qa
    loaded_modules = 0
    missing_modules = []
    
    # Verificar módulos V2
    if v2_endpoints_available:
        try:
            # Tentar importar cada módulo individualmente
            modules_to_check = [
                ("courses", "src.api.v2.courses"),
                ("books", "src.api.v2.books"), 
                ("units", "src.api.v2.units"),
                ("vocabulary", "src.api.v2.vocabulary"),
                ("sentences", "src.api.v2.sentences"),
                ("tips", "src.api.v2.tips"),
                ("grammar", "src.api.v2.grammar"),
                ("assessments", "src.api.v2.assessments"),
                ("qa", "src.api.v2.qa")
            ]
            
            for module_name, module_path in modules_to_check:
                try:
                    __import__(module_path)
                    loaded_modules += 1
                except ImportError:
                    missing_modules.append(module_name)
                    
        except Exception as e:
            missing_modules.extend(["configuration_error"])
    else:
        missing_modules = v2_missing_modules if isinstance(v2_missing_modules, list) else [v2_missing_modules]
    
    completion_percentage = (loaded_modules / expected_modules) * 100
    
    return {
        "configuration_valid": len(missing_modules) == 0,
        "completion_status": {
            "percentage": completion_percentage,
            "loaded": loaded_modules,
            "expected": expected_modules
        },
        "missing_modules": missing_modules,
        "v2_available": v2_endpoints_available,
        "v1_legacy_available": legacy_endpoints_available
    }

def get_hierarchical_flow() -> Dict[str, Any]:
    """Retorna informações sobre o fluxo hierárquico."""
    return {
        "structure": "Course → Book → Unit → Content",
        "creation_order": [
            "1. POST /api/v2/courses (definir níveis CEFR e metodologia)",
            "2. POST /api/v2/courses/{course_id}/books (criar books por nível)",
            "3. POST /api/v2/books/{book_id}/units (criar units com imagens obrigatórias)",
            "4. Geração sequencial de conteúdo por unit"
        ],
        "content_generation_sequence": [
            "vocabulary → sentences → strategy (tips|grammar) → assessments → qa"
        ],
        "rag_context": "Cada geração usa contexto de unidades anteriores para evitar repetições",
        "validation": "Hierarquia obrigatória em todas as operações"
    }

# =============================================================================
# LIFECYCLE MANAGEMENT
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação com validação completa."""
    # Startup
    setup_logging()
    await init_database()
    
    # Validar configuração da API
    api_health = get_api_health()
    
    if api_health["configuration_valid"]:
        logger.info(f"✅ IVO V2 configurado corretamente ({api_health['completion_status']['percentage']:.1f}% completo)")
        logger.info(f"📊 Módulos V2: {api_health['completion_status']['loaded']}/{api_health['completion_status']['expected']}")
    else:
        logger.warning(f"⚠️ Configuração incompleta - Módulos faltando: {api_health['missing_modules']}")
    
    # Log de inicialização
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usando como evento de sistema
        additional_data={
            "event": "application_startup",
            "version": API_INFO["version"],
            "api_health": api_health,
            "features": API_INFO["features"],
            "hierarchical_architecture": True
        }
    )
    
    # Console startup info
    print("=" * 80)
    print("🚀 IVO V2 - Intelligent Vocabulary Organizer INICIADO!")
    print("=" * 80)
    print(f"📋 Versão: {API_INFO['version']}")
    print(f"🏗️ Arquitetura: {API_INFO['architecture']}")
    print(f"✅ API V2: {api_health['completion_status']['percentage']:.1f}% implementada")
    print(f"📊 Módulos V2: {api_health['completion_status']['loaded']}/{api_health['completion_status']['expected']}")
    
    if api_health["missing_modules"]:
        print(f"⚠️  Módulos faltando: {', '.join(api_health['missing_modules'])}")
    
    print("🔧 Recursos ativos:")
    print("   ✅ Rate Limiting inteligente (in-memory)")
    print("   ✅ Auditoria empresarial") 
    print("   ✅ Paginação avançada")
    print("   ✅ Hierarquia Course → Book → Unit")
    print("   ✅ RAG contextual")
    print("   ✅ Validação IPA")
    print("   ✅ MCP Image Analysis")
    
    if legacy_endpoints_available:
        print("   ✅ Endpoints V1 legados (compatibilidade)")
    
    print("📚 Endpoints principais:")
    print("   📍 /docs - Documentação Swagger")
    print("   📍 /api/v2/courses - Gestão de cursos")
    print("   📍 /health - Status do sistema")
    print("   📍 /system/stats - Analytics")
    print("=" * 80)
    
    yield
    
    # Shutdown
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,  # Usando como evento de sistema
        additional_data={
            "event": "application_shutdown",
            "uptime_info": "graceful_shutdown"
        }
    )
    print("👋 IVO V2 finalizado graciosamente!")

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

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
# MIDDLEWARE CONFIGURATION
# =============================================================================

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=MIDDLEWARE_CONFIG["cors"]["allow_origins"],
    allow_credentials=True,
    allow_methods=MIDDLEWARE_CONFIG["cors"]["allow_methods"],
    allow_headers=MIDDLEWARE_CONFIG["cors"]["allow_headers"],
)

# 2. Rate Limiting Middleware
if MIDDLEWARE_CONFIG["rate_limiting"]["enabled"]:
    app.add_middleware(RateLimitMiddleware)

# 3. Request ID Middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Adiciona Request ID único para rastreamento."""
    import uuid
    
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    
    return response

# 4. Audit Middleware
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """Middleware para auditoria completa de requests."""
    start_time = time.time()
    request_id = audit_logger_instance.start_request_tracking(request)
    request.state.audit_request_id = request_id
    
    response = None
    status_code = 500
    error_occurred = False
    
    try:
        response = await call_next(request)
        status_code = response.status_code
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
                "error_message": str(e),
                "request_id": request_id
            },
            success=False,
            error_details=str(e)
        )
        raise
        
    finally:
        # Finalizar tracking
        performance_metrics = audit_logger_instance.end_request_tracking(
            request, status_code
        )
        
        # Log para endpoints V2
        if request.url.path.startswith('/api/v2/'):
            await audit_logger_instance.log_event(
                event_type=AuditEventType.COURSE_VIEWED,  # Evento genérico para acesso
                request=request,
                additional_data={
                    "access_type": "v2_api_endpoint",
                    "endpoint": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "error_occurred": error_occurred,
                    "processing_time": performance_metrics.get("processing_time", 0)
                },
                success=not error_occurred,
                performance_metrics=performance_metrics
            )

# =============================================================================
# ROUTERS V2 - HIERÁRQUICOS
# =============================================================================

# Health check (sempre primeiro)
if v2_endpoints_available:
    try:
        app.include_router(
            health_router,
            prefix="/health", 
            tags=["health"]
        )
    except NameError:
        logger.warning("⚠️ Health router não disponível")

# Registrar routers V2 com tratamento de erro individual
v2_routers = [
    (courses_router, "/api/v2", ["v2-courses"], "courses"),
    (books_router, "/api/v2", ["v2-books"], "books"),
    (units_router, "/api/v2", ["v2-units"], "units"),
    (vocabulary_router, "/api/v2", ["v2-vocabulary"], "vocabulary"),
    (sentences_router, "/api/v2", ["v2-sentences"], "sentences"),
    (tips_router, "/api/v2", ["v2-tips"], "tips"),
    (grammar_router, "/api/v2", ["v2-grammar"], "grammar"),
    (assessments_router, "/api/v2", ["v2-assessments"], "assessments"),
    (qa_router, "/api/v2", ["v2-qa"], "qa")
]

for router, prefix, tags, name in v2_routers:
    try:
        app.include_router(
            router,
            prefix=prefix,
            tags=tags,
            responses={
                404: {"description": "Recurso não encontrado"},
                400: {"description": "Dados inválidos ou hierarquia incorreta"},
                429: {"description": "Rate limit excedido"},
                500: {"description": f"Erro interno no módulo {name}"}
            }
        )
        logger.info(f"✅ Router {name} carregado com sucesso")
    except NameError:
        logger.warning(f"⚠️ Router {name} não disponível - módulo não importado")
    except Exception as e:
        logger.error(f"❌ Erro ao carregar router {name}: {str(e)}")

# =============================================================================
# ROUTERS LEGADOS V1 - COMPATIBILIDADE
# =============================================================================

if legacy_endpoints_available:
    try:
        app.include_router(auth.router, prefix="/auth", tags=["v1-legacy"])
        app.include_router(apostilas.router, prefix="/apostilas", tags=["v1-legacy"])
        app.include_router(vocabs.router, prefix="/vocabs", tags=["v1-legacy"])
        app.include_router(content.router, prefix="/content", tags=["v1-legacy"])
        app.include_router(images.router, prefix="/images", tags=["v1-legacy"])
        app.include_router(pdf.router, prefix="/pdf", tags=["v1-legacy"])
        logger.info("✅ Endpoints legados V1 carregados para compatibilidade")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar endpoints V1: {str(e)}")
else:
    logger.info("ℹ️ Endpoints legados V1 não disponíveis - apenas V2 ativo")

# =============================================================================
# ENDPOINTS INFORMATIVOS
# =============================================================================

@app.get("/", tags=["root"])
async def root(request: Request):
    """Informações gerais da API IVO V2."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "root_info_access"}
    )
    
    api_health = get_api_health()
    hierarchical_flow = get_hierarchical_flow()
    
    return {
        **API_INFO,
        "status": "operational",
        "api_health": api_health,
        "endpoints": {
            "v2_primary": {
                "courses": "/api/v2/courses",
                "books": "/api/v2/courses/{course_id}/books", 
                "units": "/api/v2/books/{book_id}/units",
                "content_generation": {
                    "vocabulary": "/api/v2/units/{unit_id}/vocabulary",
                    "sentences": "/api/v2/units/{unit_id}/sentences",
                    "tips": "/api/v2/units/{unit_id}/tips",
                    "grammar": "/api/v2/units/{unit_id}/grammar",
                    "assessments": "/api/v2/units/{unit_id}/assessments",
                    "qa": "/api/v2/units/{unit_id}/qa"
                }
            },
            "system": {
                "health": "/health",
                "stats": "/system/stats",
                "detailed_health": "/system/health",
                "rate_limits": "/system/rate-limits"
            },
            "documentation": {
                "swagger": "/docs",
                "redoc": "/redoc",
                "api_overview": "/api/overview"
            },
            "v1_legacy": "/auth, /apostilas, /vocabs, /content, /images, /pdf" if legacy_endpoints_available else "Not available"
        },
        "hierarchical_flow": hierarchical_flow,
        "content_generation_workflow": [
            "1. 📚 CREATE Course (with CEFR levels)",
            "2. 📖 CREATE Books (one per CEFR level)",
            "3. 📑 CREATE Units (with mandatory images)",
            "4. 🔤 GENERATE Vocabulary (RAG + MCP analysis)",
            "5. 📝 GENERATE Sentences (connected to vocabulary)",
            "6. 💡 GENERATE Strategy (TIPS for lexical | GRAMMAR for grammatical)",
            "7. 🎯 GENERATE Assessments (2 of 7 types, balanced)",
            "8. ❓ GENERATE Q&A (optional - Bloom's taxonomy)"
        ],
        "key_features": {
            "rag_intelligence": "Context-aware generation prevents repetition",
            "assessment_balancing": "Automatic selection of complementary activities",
            "ipa_validation": "35+ phonetic symbols validated",
            "l1_interference": "Portuguese→English error prevention",
            "methodologies": ["Direct Method", "TIPS Strategies", "Bloom's Taxonomy"]
        }
    }

@app.get("/api/overview", tags=["system"])
async def api_overview(request: Request):
    """Visão geral completa da API IVO V2."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "api_overview_access"}
    )
    
    api_health = get_api_health()
    
    return {
        "system_info": {
            "name": API_INFO["name"],
            "version": API_INFO["version"],
            "architecture": API_INFO["architecture"],
            "status": "operational" if api_health["configuration_valid"] else "degraded"
        },
        "implementation_status": {
            "completion_percentage": api_health["completion_status"]["percentage"],
            "loaded_modules": api_health["completion_status"]["loaded"],
            "expected_modules": api_health["completion_status"]["expected"],
            "missing_modules": api_health.get("missing_modules", []),
            "health_status": "healthy" if api_health["configuration_valid"] else "degraded"
        },
        "hierarchical_architecture": {
            "levels": ["Course", "Book", "Unit", "Content"],
            "mandatory_hierarchy": True,
            "rag_context": "Each level provides context for content generation",
            "progression": "CEFR-based pedagogical progression"
        },
        "content_generation_pipeline": {
            "steps": ["aims", "vocabulary", "sentences", "strategy", "assessments", "qa"],
            "rag_features": [
                "Vocabulary deduplication",
                "Strategy balancing", 
                "Assessment variety",
                "Progression analysis"
            ],
            "ai_integration": "100% contextual analysis with technical fallbacks"
        },
        "quality_assurance": {
            "automatic_validations": 22,
            "ipa_validation": "35+ phonetic symbols",
            "cefr_compliance": "Automatic level adaptation",
            "l1_interference": "Portuguese→English error prevention"
        },
        "advanced_features": API_INFO["features"],
        "legacy_support": {
            "v1_endpoints": legacy_endpoints_available,
            "backward_compatibility": True
        }
    }

@app.get("/system/stats", tags=["system"])
async def system_stats(request: Request):
    """Estatísticas detalhadas do sistema IVO V2."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "system_stats_access"}
    )
    
    try:
        # Tentar obter estatísticas do banco
        try:
            from src.services.hierarchical_database import hierarchical_db
            analytics = await hierarchical_db.get_system_analytics()
        except ImportError:
            analytics = {
                "courses_count": "N/A - Service not available",
                "books_count": "N/A - Service not available", 
                "units_count": "N/A - Service not available",
                "generated_at": time.time()
            }
        
        api_health = get_api_health()
        
        return {
            "success": True,
            "system_analytics": analytics,
            "api_status": {
                "version": API_INFO["version"],
                "health": api_health,
                "features_enabled": API_INFO["features"],
                "modules_status": {
                    "v2_loaded": api_health["completion_status"]["loaded"],
                    "v2_expected": api_health["completion_status"]["expected"],
                    "v1_legacy": legacy_endpoints_available
                }
            },
            "performance_metrics": {
                "rate_limiting": "Active with in-memory storage",
                "audit_logging": "Full request tracking",
                "pagination": "Advanced with filters",
                "cache_status": "Contextual TTL-based"
            },
            "timestamp": analytics.get("generated_at", time.time())
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        return {
            "success": False,
            "error": "Statistics unavailable",
            "message": str(e),
            "api_health": get_api_health(),
            "timestamp": time.time()
        }

@app.get("/system/health", tags=["system"])
async def detailed_health_check(request: Request):
    """Health check detalhado com verificação de dependências."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "detailed_health_check"}
    )
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": API_INFO["version"],
        "services": {},
        "features": {},
        "api_configuration": get_api_health()
    }
    
    # Check Database
    try:
        from config.database import get_supabase_client
        supabase = get_supabase_client()
        result = supabase.table("ivo_courses").select("id").limit(1).execute()
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check OpenAI API
    try:
        import openai
        from config.settings import get_settings
        settings = get_settings()
        if settings.openai_api_key:
            health_status["services"]["openai_api"] = "configured"
        else:
            health_status["services"]["openai_api"] = "not_configured"
    except Exception as e:
        health_status["services"]["openai_api"] = f"unavailable: {str(e)}"
    
    # Rate Limiting Storage (Memory-based)
    health_status["services"]["rate_limiting"] = "memory-based (no Redis required)"
    
    # Check Features
    health_status["features"] = {
        "rate_limiting": "active",
        "audit_logging": "active", 
        "pagination": "active",
        "hierarchical_structure": "active",
        "rag_integration": "active" if v2_endpoints_available else "limited",
        "ipa_validation": "active",
        "mcp_image_analysis": "configured"
    }
    
    # Overall status
    if not health_status["api_configuration"]["configuration_valid"]:
        health_status["status"] = "degraded"
        health_status["degradation_reason"] = "Missing V2 modules"
    
    return health_status

@app.get("/system/rate-limits", tags=["system"])
async def rate_limits_info(request: Request):
    """Informações detalhadas sobre configuração de rate limits."""
    try:
        from src.core.rate_limiter import RATE_LIMIT_CONFIG
        rate_config = RATE_LIMIT_CONFIG
    except ImportError:
        rate_config = "Rate limiter configuration not available"
    
    await audit_logger_instance.log_event(
        event_type=AuditEventType.COURSE_VIEWED,
        request=request,
        additional_data={"endpoint": "rate_limits_info"}
    )
    
    return {
        "rate_limits": rate_config,
        "middleware_config": MIDDLEWARE_CONFIG["rate_limiting"],
        "description": "Rate limits específicos por endpoint com fallback inteligente",
        "identification_strategy": {
            "priority_order": ["user_id (authenticated)", "IP address", "fallback"],
            "headers_checked": ["X-Forwarded-For", "X-Real-IP", "X-User-ID"],
            "window_formats": ["Xs (seconds)", "Xm (minutes)", "Xh (hours)"],
            "storage_type": "In-memory with TTL cleanup"
        },
        "response_headers": [
            "X-RateLimit-Limit (requests allowed)",
            "X-RateLimit-Remaining (requests left)", 
            "X-RateLimit-Reset (reset timestamp)",
            "Retry-After (seconds to wait on 429)"
        ],
        "storage": {
            "type": "In-memory dictionary",
            "persistence": "Session-based (non-persistent)",
            "cleanup": "Automatic TTL-based expiration",
            "scalability": "Single-instance only"
        }
    }

# =============================================================================
# ERROR HANDLERS GLOBAIS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handler para recursos não encontrados."""
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
            "Confirme que o recurso existe na hierarquia Course→Book→Unit",
            "Consulte /docs para endpoints disponíveis",
            "Verificar /api/overview para estrutura da API"
        ],
        "hierarchical_help": {
            "course_operations": "GET /api/v2/courses para listar cursos",
            "book_operations": "GET /api/v2/courses/{course_id}/books para books do curso",
            "unit_operations": "GET /api/v2/books/{book_id}/units para units do book"
        }
    }


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    """Handler para rate limiting excedido."""
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
            "retry_after": rate_limit_info.get("retry_after", 60),
            "request_id": getattr(request.state, 'request_id', 'unknown')
        },
        "suggestions": [
            f"Aguarde {rate_limit_info.get('retry_after', 60)} segundos antes de tentar novamente",
            "Considere implementar cache local para reduzir requests",
            "Verifique se não há requests desnecessários em loop",
            "Para operações em lote, use paginação adequada"
        ],
        "rate_limit_info": {
            "check_limits": "GET /system/rate-limits para ver limites específicos",
            "identification": "Limits aplicados por user_id ou IP address",
            "windows": "Janelas deslizantes de tempo (60s, 10m, 1h)"
        }
    }


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Handler para erros de validação Pydantic."""
    validation_errors = []
    
    # Extrair erros de validação do Pydantic
    if hasattr(exc, 'errors'):
        for error in exc.errors():
            validation_errors.append({
                "field": " → ".join(str(loc) for loc in error.get('loc', [])),
                "message": error.get('msg', 'Validation error'),
                "type": error.get('type', 'unknown'),
                "input": error.get('input')
            })
    
    await audit_logger_instance.log_event(
        event_type=AuditEventType.VALIDATION_FAILED,
        request=request,
        additional_data={
            "error_type": "validation_error",
            "path": str(request.url),
            "method": request.method,
            "validation_errors": validation_errors
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
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "validation_errors": validation_errors
        },
        "suggestions": [
            "Verifique os tipos de dados enviados",
            "Confirme que campos obrigatórios estão presentes",
            "Para hierarquia: course_id e book_id devem existir",
            "Consulte /docs para estrutura exata dos dados"
        ],
        "common_validation_issues": {
            "cefr_level": "Deve ser um dos: A1, A2, B1, B2, C1, C2",
            "unit_type": "Deve ser: lexical_unit ou grammar_unit",
            "language_variant": "Deve ser: american_english, british_english, etc.",
            "hierarchy": "IDs de course_id e book_id devem existir no sistema"
        }
    }


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handler para erros internos do servidor."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,
        request=request,
        additional_data={
            "error_type": "internal_server_error",
            "path": str(request.url),
            "method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
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
            "timestamp": time.time(),
            "exception_type": type(exc).__name__
        },
        "suggestions": [
            "Tente novamente em alguns instantes",
            "Verifique se todas as dependências estão funcionando",
            "Para erros persistentes, consulte /system/health",
            "Contate o suporte técnico se necessário"
        ],
        "system_checks": {
            "health_endpoint": "/system/health para diagnóstico completo",
            "stats_endpoint": "/system/stats para métricas do sistema",
            "database_status": "Verificar conectividade com Supabase",
            "openai_status": "Verificar configuração da API OpenAI"
        }
    }


@app.exception_handler(400)
async def bad_request_handler(request: Request, exc):
    """Handler para bad requests."""
    await audit_logger_instance.log_event(
        event_type=AuditEventType.API_ERROR,
        request=request,
        additional_data={
            "error_type": "bad_request",
            "path": str(request.url),
            "method": request.method,
            "exception_message": str(exc)
        },
        success=False,
        error_details=str(exc)
    )
    
    return {
        "success": False,
        "error_code": "BAD_REQUEST",
        "message": "Requisição inválida",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "error_description": str(exc)
        },
        "suggestions": [
            "Verifique a estrutura da requisição",
            "Confirme que a hierarquia está correta",
            "Para uploads: máximo 10MB por imagem",
            "Consulte a documentação em /docs"
        ],
        "hierarchical_requirements": {
            "course_creation": "Requer name, target_levels, language_variant",
            "book_creation": "Requer course_id válido e target_level",
            "unit_creation": "Requer book_id válido e pelo menos 1 imagem",
            "content_generation": "Requer unit_id válido e status adequado"
        }
    }


# =============================================================================
# STARTUP E EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    """
    Execução direta do servidor FastAPI.
    Para desenvolvimento: python src/main.py
    Para produção: uvicorn src.main:app --host 0.0.0.0 --port 8000
    """
    import os
    
    # Configurações de desenvolvimento
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    print("🔧 Configuração de execução:")
    print(f"   📍 Host: {host}")
    print(f"   🔌 Port: {port}")
    print(f"   🔄 Reload: {reload}")
    print(f"   📝 Log Level: {log_level}")
    print(f"   🏗️ Architecture: {API_INFO['architecture']}")
    print("   📚 Documentação: http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )


# =============================================================================
# ENDPOINTS DE DESENVOLVIMENTO E DEBUG
# =============================================================================

@app.get("/debug/api-status", tags=["debug"], include_in_schema=False)
async def debug_api_status():
    """Endpoint de debug para verificar status da API (não incluído na documentação)."""
    return {
        "debug_info": {
            "v2_endpoints_available": v2_endpoints_available,
            "v2_missing_modules": v2_missing_modules,
            "legacy_endpoints_available": legacy_endpoints_available,
            "api_health": get_api_health(),
            "middleware_config": MIDDLEWARE_CONFIG,
            "api_info": API_INFO
        },
        "environment_checks": {
            "python_version": "3.11+",
            "fastapi_version": "Latest",
            "langchain_version": "0.3.x",
            "pydantic_version": "2.x"
        },
        "expected_modules": [
            "src.api.v2.courses",
            "src.api.v2.books", 
            "src.api.v2.units",
            "src.api.v2.vocabulary",
            "src.api.v2.sentences",
            "src.api.v2.tips",
            "src.api.v2.grammar",
            "src.api.v2.assessments",
            "src.api.v2.qa",
            "src.api.health"
        ]
    }


@app.get("/debug/routes", tags=["debug"], include_in_schema=False)
async def debug_routes():
    """Lista todas as rotas registradas (debug only)."""
    routes_info = []
    
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": getattr(route, 'name', 'unnamed'),
                "tags": getattr(route, 'tags', [])
            })
    
    return {
        "total_routes": len(routes_info),
        "routes": sorted(routes_info, key=lambda x: x['path']),
        "routes_by_prefix": {
            "api_v2": [r for r in routes_info if r['path'].startswith('/api/v2')],
            "system": [r for r in routes_info if r['path'].startswith('/system')],
            "health": [r for r in routes_info if r['path'].startswith('/health')],
            "legacy": [r for r in routes_info if not any(r['path'].startswith(p) for p in ['/api/v2', '/system', '/health', '/docs', '/redoc', '/openapi.json'])]
        }
    }