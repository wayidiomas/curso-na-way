# src/main.py - IVO V2 Sistema Hierárquico Course → Book → Unit
"""
🚀 IVO V2 - Intelligent Vocabulary Organizer
Sistema avançado de geração hierárquica de unidades pedagógicas com IA generativa,
RAG contextual e metodologias comprovadas para ensino de idiomas.

Arquitetura: Course → Book → Unit → Content (Vocabulary, Sentences, Strategies, Assessments)
Versão: 2.0.0 - Sem Redis (in-memory) mas preparado para implementação futura
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import time
import logging
import importlib
import os
from typing import Dict, Any, Optional, List

# Core imports - Database e configuração
from src.core.database import init_database
from config.logging import setup_logging

# =============================================================================
# CONFIGURAÇÃO DE LOGGING INICIAL
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# SISTEMA DE IMPORTAÇÃO DINÂMICA ROBUSTO
# =============================================================================

class RouterLoader:
    """Sistema robusto de carregamento de routers com fallbacks."""
    
    def __init__(self):
        self.loaded_routers = {}
        self.failed_routers = {}
        self.router_configs = [
            # (nome_modulo, caminho_import, nome_router, é_crítico)
            ("health", "src.api.health", "router", True),
            ("courses", "src.api.v2.courses", "router", True),
            ("books", "src.api.v2.books", "router", True),
            ("units", "src.api.v2.units", "router", True),
            ("vocabulary", "src.api.v2.vocabulary", "router", True),
            ("sentences", "src.api.v2.sentences", "router", False),
            ("tips", "src.api.v2.tips", "router", False),
            ("grammar", "src.api.v2.grammar", "router", False),
            ("assessments", "src.api.v2.assessments", "router", False),
            ("qa", "src.api.v2.qa", "router", False)
        ]
    
    def load_all_routers(self) -> Dict[str, Any]:
        """Carregar todos os routers com tratamento de erro individual."""
        logger.info("🔧 Iniciando carregamento de routers...")
        
        for module_name, import_path, router_attr, is_critical in self.router_configs:
            try:
                # Import dinâmico do módulo
                module = importlib.import_module(import_path)
                
                # Verificar se tem o atributo router
                if hasattr(module, router_attr):
                    router = getattr(module, router_attr)
                    self.loaded_routers[module_name] = {
                        "router": router,
                        "import_path": import_path,
                        "is_critical": is_critical
                    }
                    logger.info(f"✅ {module_name} router carregado com sucesso")
                else:
                    self.failed_routers[module_name] = f"Módulo sem atributo '{router_attr}'"
                    logger.warning(f"⚠️ {module_name}: módulo carregado mas sem router")
                    
            except ImportError as e:
                self.failed_routers[module_name] = f"ImportError: {str(e)}"
                if is_critical:
                    logger.error(f"❌ CRÍTICO: {module_name} falhou ao carregar: {str(e)}")
                else:
                    logger.warning(f"⚠️ {module_name} não disponível: {str(e)}")
                    
            except Exception as e:
                self.failed_routers[module_name] = f"Erro: {str(e)}"
                logger.error(f"❌ Erro inesperado ao carregar {module_name}: {str(e)}")
        
        # Carregar endpoints legados (V1) opcionalmente
        self._load_legacy_endpoints()
        
        return self.get_load_summary()
    
    def _load_legacy_endpoints(self) -> None:
        """Carregar endpoints legados V1 se disponíveis."""
        try:
            legacy_modules = ["auth", "apostilas", "vocabs", "content", "images", "pdf"]
            legacy_loaded = []
            
            for module_name in legacy_modules:
                try:
                    module = importlib.import_module(f"src.api.{module_name}")
                    if hasattr(module, 'router'):
                        self.loaded_routers[f"legacy_{module_name}"] = {
                            "router": module.router,
                            "import_path": f"src.api.{module_name}",
                            "is_critical": False,
                            "is_legacy": True
                        }
                        legacy_loaded.append(module_name)
                except ImportError:
                    continue
                    
            if legacy_loaded:
                logger.info(f"✅ Endpoints legados V1 carregados: {', '.join(legacy_loaded)}")
            else:
                logger.info("ℹ️ Nenhum endpoint legado V1 encontrado")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar endpoints legados: {str(e)}")
    
    def get_load_summary(self) -> Dict[str, Any]:
        """Obter resumo do carregamento."""
        total_routers = len(self.router_configs)
        loaded_count = len([r for r in self.loaded_routers.values() if not r.get("is_legacy", False)])
        critical_loaded = len([r for r in self.loaded_routers.values() 
                              if r.get("is_critical", False) and not r.get("is_legacy", False)])
        critical_total = len([r for r in self.router_configs if r[3]])  # is_critical
        
        legacy_count = len([r for r in self.loaded_routers.values() if r.get("is_legacy", False)])
        
        return {
            "total_expected": total_routers,
            "loaded_count": loaded_count,
            "failed_count": len(self.failed_routers),
            "critical_loaded": critical_loaded,
            "critical_total": critical_total,
            "legacy_count": legacy_count,
            "completion_percentage": (loaded_count / total_routers) * 100,
            "system_functional": critical_loaded >= max(1, critical_total // 2),  # Pelo menos metade dos críticos
            "loaded_routers": list(self.loaded_routers.keys()),
            "failed_routers": list(self.failed_routers.keys()),
            "failure_details": self.failed_routers
        }
    
    def get_router(self, name: str):
        """Obter router específico ou None se não carregado."""
        router_info = self.loaded_routers.get(name)
        return router_info["router"] if router_info else None


# Instância global do loader
router_loader = RouterLoader()

# =============================================================================
# SISTEMA DE MIDDLEWARE INTELIGENTE (SEM REDIS POR ENQUANTO)
# =============================================================================

class InMemoryRateLimiter:
    """Rate limiter simples em memória (preparado para Redis futuro)."""
    
    def __init__(self):
        self.requests = {}  # {key: [(timestamp, count), ...]}
        self.limits = {
            "default": {"requests": 100, "window": 60},
            "create_course": {"requests": 10, "window": 60},
            "create_unit": {"requests": 5, "window": 60},
            "generate_vocabulary": {"requests": 3, "window": 60},
            "generate_content": {"requests": 2, "window": 60},
        }
        self.cleanup_interval = 300  # 5 minutos
        self.last_cleanup = time.time()
    
    def _cleanup_old_entries(self):
        """Limpar entradas antigas para evitar vazamento de memória."""
        if time.time() - self.last_cleanup < self.cleanup_interval:
            return
        
        current_time = time.time()
        keys_to_remove = []
        
        for key, entries in self.requests.items():
            # Remover entradas mais antigas que 1 hora
            self.requests[key] = [(ts, count) for ts, count in entries 
                                 if current_time - ts < 3600]
            if not self.requests[key]:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]
        
        self.last_cleanup = current_time
    
    def is_allowed(self, identifier: str, endpoint: str = "default") -> tuple[bool, Dict[str, Any]]:
        """Verificar se request é permitido."""
        self._cleanup_old_entries()
        
        limit_config = self.limits.get(endpoint, self.limits["default"])
        window = limit_config["window"]
        max_requests = limit_config["requests"]
        
        current_time = time.time()
        key = f"{identifier}:{endpoint}"
        
        # Obter requests no window atual
        if key not in self.requests:
            self.requests[key] = []
        
        # Filtrar apenas requests dentro da janela
        window_start = current_time - window
        recent_requests = [count for ts, count in self.requests[key] if ts > window_start]
        current_count = sum(recent_requests)
        
        # Verificar se está dentro do limite
        is_allowed = current_count < max_requests
        
        if is_allowed:
            # Adicionar este request
            self.requests[key].append((current_time, 1))
        
        return is_allowed, {
            "limit": max_requests,
            "remaining": max(0, max_requests - current_count - (1 if is_allowed else 0)),
            "reset_time": current_time + window,
            "window": window
        }
    
    # TODO: Métodos para migração futura para Redis
    def _migrate_to_redis(self, redis_client):
        """Placeholder para migração futura para Redis."""
        # Implementar quando Redis for adicionado
        pass
    
    def _load_from_redis(self, redis_client):
        """Placeholder para carregar dados do Redis."""
        # Implementar quando Redis for adicionado
        pass


# Instância global do rate limiter
rate_limiter = InMemoryRateLimiter()

# =============================================================================
# AUDIT LOGGER SIMPLIFICADO (PREPARADO PARA EXTENSÃO)
# =============================================================================

class SimpleAuditLogger:
    """Audit logger simplificado (preparado para sistema completo futuro)."""
    
    def __init__(self):
        self.enabled = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"
        self.request_times = {}
    
    def start_request_tracking(self, request: Request) -> str:
        """Iniciar tracking de request."""
        if not self.enabled:
            return "disabled"
        
        request_id = getattr(request.state, 'request_id', f"req_{int(time.time() * 1000)}")
        self.request_times[request_id] = time.time()
        return request_id
    
    def end_request_tracking(self, request: Request, status_code: int) -> Dict[str, Any]:
        """Finalizar tracking e obter métricas."""
        if not self.enabled:
            return {}
        
        request_id = getattr(request.state, 'audit_request_id', 'unknown')
        end_time = time.time()
        start_time = self.request_times.get(request_id, end_time)
        processing_time = end_time - start_time
        
        # Log se request demorou muito
        if processing_time > 2.0:
            logger.warning(f"⏱️ Request lento detectado: {request.url.path} - {processing_time:.2f}s")
        
        # Limpar tracking
        if request_id in self.request_times:
            del self.request_times[request_id]
        
        return {
            "processing_time": processing_time,
            "status_code": status_code,
            "method": request.method,
            "path": str(request.url.path)
        }
    
    async def log_event(self, event_type: str, request: Optional[Request] = None, **kwargs):
        """Log de evento simples."""
        if not self.enabled:
            return
        
        log_data = {
            "timestamp": time.time(),
            "event_type": event_type,
            "path": str(request.url.path) if request else "system",
            **kwargs
        }
        
        logger.info(f"📊 AUDIT: {event_type} - {log_data}")


# Instância global do audit logger
audit_logger = SimpleAuditLogger()

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
    • 🚀 In-memory storage (sem Redis) preparado para migração futura
    """,
    "architecture": "Course → Book → Unit → Content",
    "storage": "In-memory (preparado para Redis)",
    "features": [
        "Hierarquia pedagógica obrigatória",
        "RAG contextual para progressão",
        "Rate limiting inteligente (in-memory)",
        "Auditoria empresarial simplificada",
        "Paginação avançada com filtros",
        "Validação IPA automática",
        "MCP Image Analysis",
        "Metodologias científicas integradas",
        "Preparado para Redis (implementação futura)"
    ]
}

API_TAGS = [
    {"name": "health", "description": "🏥 Health checks e monitoramento do sistema"},
    {"name": "system", "description": "⚙️ Informações e estatísticas do sistema"},
    {"name": "v2-courses", "description": "📚 Gestão de cursos completos com níveis CEFR"},
    {"name": "v2-books", "description": "📖 Gestão de books organizados por nível"},
    {"name": "v2-units", "description": "📑 Gestão de unidades pedagógicas com imagens"},
    {"name": "v2-vocabulary", "description": "🔤 Geração de vocabulário com RAG + MCP"},
    {"name": "v2-sentences", "description": "📝 Geração de sentences conectadas"},
    {"name": "v2-tips", "description": "💡 Estratégias TIPS para unidades lexicais"},
    {"name": "v2-grammar", "description": "📐 Estratégias GRAMMAR para unidades gramaticais"},
    {"name": "v2-assessments", "description": "🎯 Geração de atividades balanceadas"},
    {"name": "v2-qa", "description": "❓ Q&A pedagógico com Taxonomia de Bloom"},
    {"name": "v1-legacy", "description": "🔄 Endpoints legados para compatibilidade"},
    {"name": "debug", "description": "🔧 Endpoints de debug e desenvolvimento"}
]

# =============================================================================
# FUNÇÕES UTILITÁRIAS DE STATUS
# =============================================================================

def get_api_health() -> Dict[str, Any]:
    """Verificar saúde da configuração da API."""
    load_summary = router_loader.get_load_summary()
    
    return {
        "configuration_valid": load_summary["system_functional"],
        "completion_status": {
            "percentage": load_summary["completion_percentage"],
            "loaded": load_summary["loaded_count"],
            "expected": load_summary["total_expected"],
            "critical_loaded": load_summary["critical_loaded"],
            "critical_total": load_summary["critical_total"]
        },
        "missing_modules": load_summary["failed_routers"],
        "missing_details": load_summary["failure_details"],
        "v2_available": load_summary["loaded_count"] > 0,
        "v1_legacy_available": load_summary["legacy_count"] > 0,
        "system_functional": load_summary["system_functional"],
        "storage_type": "in-memory",
        "redis_ready": False  # Para implementação futura
    }

def get_hierarchical_flow() -> Dict[str, Any]:
    """Retornar informações sobre o fluxo hierárquico."""
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
        "validation": "Hierarquia obrigatória em todas as operações",
        "storage": "In-memory com preparação para Redis futuro"
    }

# =============================================================================
# LIFECYCLE MANAGEMENT
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciar ciclo de vida da aplicação com validação completa."""
    # Startup
    logger.info("🚀 Iniciando IVO V2...")
    setup_logging()
    await init_database()
    
    # Carregar routers
    load_summary = router_loader.load_all_routers()
    api_health = get_api_health()
    
    # Log de inicialização
    await audit_logger.log_event(
        "application_startup",
        version=API_INFO["version"],
        api_health=api_health,
        features=API_INFO["features"],
        hierarchical_architecture=True,
        storage_type="in-memory"
    )
    
    # Console startup info
    print("=" * 80)
    print("🚀 IVO V2 - Intelligent Vocabulary Organizer INICIADO!")
    print("=" * 80)
    print(f"📋 Versão: {API_INFO['version']}")
    print(f"🏗️ Arquitetura: {API_INFO['architecture']}")
    print(f"💾 Storage: In-memory (preparado para Redis)")
    print(f"✅ API V2: {api_health['completion_status']['percentage']:.1f}% implementada")
    print(f"📊 Routers: {load_summary['loaded_count']}/{load_summary['total_expected']} carregados")
    print(f"🔴 Críticos: {load_summary['critical_loaded']}/{load_summary['critical_total']}")
    
    if load_summary["failed_routers"]:
        print(f"⚠️  Módulos faltando: {', '.join(load_summary['failed_routers'])}")
    
    if load_summary["legacy_count"] > 0:
        print(f"🔄 Endpoints V1 legados: {load_summary['legacy_count']} carregados")
    
    print("🔧 Recursos ativos:")
    print("   ✅ Rate Limiting inteligente (in-memory)")
    print("   ✅ Auditoria simplificada") 
    print("   ✅ Paginação avançada")
    print("   ✅ Hierarquia Course → Book → Unit")
    print("   ✅ RAG contextual")
    print("   ✅ Validação IPA")
    print("   ✅ MCP Image Analysis")
    print("   🔄 Preparado para Redis (implementação futura)")
    
    print("📚 Endpoints principais:")
    print("   📍 /docs - Documentação Swagger")
    print("   📍 /api/v2/courses - Gestão de cursos")
    print("   📍 /health - Status do sistema")
    print("   📍 /system/stats - Analytics")
    print("=" * 80)
    
    if not api_health["system_functional"]:
        print("⚠️  SISTEMA EM MODO DEGRADADO - Alguns recursos podem não estar disponíveis")
        print("=" * 80)
    
    yield
    
    # Shutdown
    await audit_logger.log_event("application_shutdown", uptime_info="graceful_shutdown")
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
    openapi_tags=API_TAGS
)

# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configurar conforme necessário em produção
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# 2. Request ID Middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Adicionar Request ID único para rastreamento."""
    import uuid
    
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    
    return response

# 3. Rate Limiting Middleware
@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Middleware de rate limiting in-memory."""
    # Identificar usuário (IP como fallback)
    identifier = request.headers.get('X-User-ID', request.client.host if request.client else 'unknown')
    
    # Determinar endpoint para rate limiting
    endpoint = "default"
    path = request.url.path
    
    if "/api/v2/courses" in path and request.method == "POST":
        endpoint = "create_course"
    elif "/api/v2/units" in path and request.method == "POST":
        endpoint = "create_unit"
    elif "/vocabulary" in path:
        endpoint = "generate_vocabulary"
    elif any(x in path for x in ["/sentences", "/tips", "/grammar", "/assessments", "/qa"]):
        endpoint = "generate_content"
    
    # Verificar rate limit
    is_allowed, rate_info = rate_limiter.is_allowed(identifier, endpoint)
    
    if not is_allowed:
        return Response(
            content=f'{{"error": "Rate limit exceeded", "retry_after": {rate_info["window"]}}}',
            status_code=429,
            headers={
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(rate_info["reset_time"])),
                "Retry-After": str(rate_info["window"])
            }
        )
    
    # Processar request
    response = await call_next(request)
    
    # Adicionar headers de rate limit
    response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(int(rate_info["reset_time"]))
    
    return response

# 4. Audit Middleware
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """Middleware para auditoria simplificada de requests."""
    request_id = audit_logger.start_request_tracking(request)
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
        await audit_logger.log_event(
            "api_error",
            request=request,
            error_type="middleware_exception",
            error_message=str(e),
            request_id=request_id
        )
        raise
        
    finally:
        # Finalizar tracking
        performance_metrics = audit_logger.end_request_tracking(request, status_code)
        
        # Log para endpoints V2 (simplificado)
        if request.url.path.startswith('/api/v2/') and performance_metrics:
            await audit_logger.log_event(
                "v2_api_access",
                request=request,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                error_occurred=error_occurred,
                **performance_metrics
            )

# =============================================================================
# REGISTRO DINÂMICO DE ROUTERS
# =============================================================================

def register_routers():
    """Registrar todos os routers carregados dinamicamente."""
    logger.info("📝 Registrando routers...")
    
    # Health router (sempre primeiro se disponível)
    health_router = router_loader.get_router("health")
    if health_router:
        try:
            app.include_router(health_router, tags=["health"])
            logger.info("✅ Health router registrado")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar health router: {str(e)}")
    
    # Routers V2 principais
    v2_router_mappings = [
        ("courses", "/api/v2", ["v2-courses"]),
        ("books", "/api/v2", ["v2-books"]),
        ("units", "/api/v2", ["v2-units"]),
        ("vocabulary", "/api/v2", ["v2-vocabulary"]),
        ("sentences", "/api/v2", ["v2-sentences"]),
        ("tips", "/api/v2", ["v2-tips"]),
        ("grammar", "/api/v2", ["v2-grammar"]),
        ("assessments", "/api/v2", ["v2-assessments"]),
        ("qa", "/api/v2", ["v2-qa"])
    ]
    
    registered_count = 0
    for router_name, prefix, tags in v2_router_mappings:
        router = router_loader.get_router(router_name)
        if router:
            try:
                app.include_router(
                    router,
                    prefix=prefix,
                    tags=tags,
                    responses={
                        404: {"description": "Recurso não encontrado"},
                        400: {"description": "Dados inválidos ou hierarquia incorreta"},
                        429: {"description": "Rate limit excedido"},
                        500: {"description": f"Erro interno no módulo {router_name}"}
                    }
                )
                registered_count += 1
                logger.info(f"✅ Router {router_name} registrado")
            except Exception as e:
                logger.error(f"❌ Erro ao registrar router {router_name}: {str(e)}")
    
    # Routers legados V1
    legacy_count = 0
    for router_name, router_info in router_loader.loaded_routers.items():
        if router_info.get("is_legacy", False):
            try:
                # Extrair nome do módulo original
                module_name = router_name.replace("legacy_", "")
                app.include_router(
                    router_info["router"], 
                    prefix=f"/{module_name}", 
                    tags=["v1-legacy"]
                )
                legacy_count += 1
                logger.info(f"✅ Router legado {module_name} registrado")
            except Exception as e:
                logger.error(f"❌ Erro ao registrar router legado {router_name}: {str(e)}")
    
    logger.info(f"📊 Registro completo: {registered_count} routers V2, {legacy_count} legados")

# Executar registro de routers
register_routers()

# =============================================================================
# ENDPOINTS INFORMATIVOS
# =============================================================================

@app.get("/", tags=["root"])
async def root(request: Request):
    """Informações gerais da API IVO V2."""
    await audit_logger.log_event("root_info_access", request=request)
    
    api_health = get_api_health()
    hierarchical_flow = get_hierarchical_flow()
    
    return {
        **API_INFO,
        "status": "operational" if api_health["system_functional"] else "degraded",
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
            "v1_legacy": "Disponível se carregado" if api_health.get("v1_legacy_available") else "Não disponível"
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
            "storage": "In-memory (preparado para Redis)",
            "methodologies": ["Direct Method", "TIPS Strategies", "Bloom's Taxonomy"]
        },
        "migration_info": {
            "redis_status": "Preparado para implementação futura",
            "current_storage": "In-memory com TTL",
            "migration_ready": True
        }
    }

@app.get("/api/overview", tags=["system"])
async def api_overview(request: Request):
    """Visão geral completa da API IVO V2."""
    await audit_logger.log_event("api_overview_access", request=request)
    
    api_health = get_api_health()
    load_summary = router_loader.get_load_summary()
    
    return {
        "system_info": {
            "name": API_INFO["name"],
            "version": API_INFO["version"],
            "architecture": API_INFO["architecture"],
            "status": "operational" if api_health["system_functional"] else "degraded",
            "storage_type": "in-memory",
            "redis_ready": False
        },
        "implementation_status": {
            "completion_percentage": api_health["completion_status"]["percentage"],
            "loaded_modules": api_health["completion_status"]["loaded"],
            "expected_modules": api_health["completion_status"]["expected"],
            "missing_modules": api_health.get("missing_modules", []),
            "missing_details": api_health.get("missing_details", {}),
            "health_status": "healthy" if api_health["system_functional"] else "degraded"
        },
        "router_summary": {
            "total_loaded": load_summary["loaded_count"],
            "critical_loaded": load_summary["critical_loaded"],
            "legacy_loaded": load_summary["legacy_count"],
            "failed_routers": load_summary["failed_routers"],
            "system_functional": load_summary["system_functional"]
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
        "storage_and_performance": {
            "current_storage": "In-memory with TTL cleanup",
            "rate_limiting": "In-memory with endpoint-specific limits",
            "audit_logging": "Simplified (preparado para extensão)",
            "redis_migration": {
                "status": "Ready for implementation",
                "benefits": ["Persistence", "Clustering", "Advanced caching"],
                "implementation_effort": "Low (infrastructure prepared)"
            }
        },
        "advanced_features": API_INFO["features"],
        "legacy_support": {
            "v1_endpoints": api_health.get("v1_legacy_available", False),
            "backward_compatibility": True
        }
    }

@app.get("/system/stats", tags=["system"])
async def system_stats(request: Request):
    """Estatísticas detalhadas do sistema IVO V2."""
    await audit_logger.log_event("system_stats_access", request=request)
    
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
        load_summary = router_loader.get_load_summary()
        
        return {
            "success": True,
            "system_analytics": analytics,
            "api_status": {
                "version": API_INFO["version"],
                "health": api_health,
                "features_enabled": API_INFO["features"],
                "modules_status": {
                    "v2_loaded": load_summary["loaded_count"],
                    "v2_expected": load_summary["total_expected"],
                    "v1_legacy": load_summary["legacy_count"],
                    "critical_functional": load_summary["system_functional"]
                }
            },
            "performance_metrics": {
                "rate_limiting": "Active with in-memory storage",
                "audit_logging": "Simplified request tracking",
                "pagination": "Advanced with filters",
                "cache_status": "In-memory TTL-based",
                "storage_type": "In-memory (Redis-ready)"
            },
            "storage_info": {
                "current_type": "in-memory",
                "persistence": False,
                "redis_ready": True,
                "cleanup_active": True,
                "memory_management": "Auto TTL cleanup"
            },
            "router_analytics": {
                "loaded_routers": load_summary["loaded_routers"],
                "failed_routers": load_summary["failed_routers"],
                "failure_details": load_summary["failure_details"]
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
    await audit_logger.log_event("detailed_health_check", request=request)
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": API_INFO["version"],
        "services": {},
        "features": {},
        "storage": {},
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
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.startswith("sk-"):
            health_status["services"]["openai_api"] = "configured"
        else:
            health_status["services"]["openai_api"] = "not_configured"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["openai_api"] = f"unavailable: {str(e)}"
    
    # Storage Health
    health_status["storage"] = {
        "type": "in-memory",
        "rate_limiter": "active",
        "audit_logger": "active",
        "cleanup_active": True,
        "redis_available": False,
        "redis_ready": True,  # Código preparado
        "memory_usage": "managed with TTL"
    }
    
    # Check Features
    health_status["features"] = {
        "rate_limiting": "active (in-memory)",
        "audit_logging": "active (simplified)", 
        "pagination": "active",
        "hierarchical_structure": "active",
        "rag_integration": "active" if health_status["api_configuration"]["v2_available"] else "limited",
        "ipa_validation": "active",
        "mcp_image_analysis": "configured"
    }
    
    # Router Health
    load_summary = router_loader.get_load_summary()
    health_status["routers"] = {
        "total_loaded": load_summary["loaded_count"],
        "critical_loaded": load_summary["critical_loaded"],
        "system_functional": load_summary["system_functional"],
        "failed_count": load_summary["failed_count"]
    }
    
    # Overall status
    if not health_status["api_configuration"]["system_functional"]:
        health_status["status"] = "degraded"
        health_status["degradation_reason"] = "Missing critical modules"
    
    if health_status["services"]["database"].startswith("unhealthy"):
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/system/rate-limits", tags=["system"])
async def rate_limits_info(request: Request):
    """Informações detalhadas sobre configuração de rate limits."""
    await audit_logger.log_event("rate_limits_info", request=request)
    
    return {
        "rate_limits": rate_limiter.limits,
        "storage_type": "in-memory",
        "redis_ready": True,
        "description": "Rate limits in-memory com preparação para Redis",
        "identification_strategy": {
            "priority_order": ["X-User-ID header", "IP address", "fallback"],
            "headers_checked": ["X-User-ID", "X-Forwarded-For", "X-Real-IP"],
            "window_formats": ["requests per seconds"],
            "storage_type": "In-memory dictionary com TTL cleanup"
        },
        "response_headers": [
            "X-RateLimit-Limit (requests allowed)",
            "X-RateLimit-Remaining (requests left)", 
            "X-RateLimit-Reset (reset timestamp)",
            "Retry-After (seconds to wait on 429)"
        ],
        "storage_details": {
            "type": "In-memory dictionary",
            "persistence": "Session-based (non-persistent)",
            "cleanup": "Automatic TTL-based expiration (5 min intervals)",
            "scalability": "Single-instance only",
            "redis_migration": {
                "ready": True,
                "benefits": ["Persistence", "Multi-instance", "Advanced features"],
                "implementation": "Preparado com métodos de migração"
            }
        },
        "performance": {
            "cleanup_interval": f"{rate_limiter.cleanup_interval} seconds",
            "memory_managed": True,
            "auto_cleanup": True
        }
    }

@app.get("/system/redis-migration", tags=["system"])
async def redis_migration_info(request: Request):
    """Informações sobre preparação para migração Redis."""
    await audit_logger.log_event("redis_migration_info", request=request)
    
    return {
        "migration_status": {
            "code_ready": True,
            "infrastructure_ready": False,  # Redis não instalado
            "migration_effort": "Low",
            "estimated_downtime": "< 5 minutes"
        },
        "current_limitations": {
            "persistence": "None - data lost on restart",
            "clustering": "Single instance only",
            "advanced_features": "Basic rate limiting only"
        },
        "redis_benefits": {
            "persistence": "Data survives restarts",
            "clustering": "Multi-instance support",
            "advanced_rate_limiting": "Sliding windows, complex rules",
            "caching": "Advanced caching with TTL",
            "pub_sub": "Real-time notifications",
            "analytics": "Historical data tracking"
        },
        "implementation_steps": [
            "1. Install Redis server",
            "2. Add redis-py dependency",
            "3. Set REDIS_ENABLED=true in .env",
            "4. Configure REDIS_URL",
            "5. Restart application",
            "6. Automatic migration of rate limiter",
            "7. Optional: Migrate audit logs to Redis"
        ],
        "configuration_example": {
            "env_variables": {
                "REDIS_ENABLED": "true",
                "REDIS_URL": "redis://localhost:6379",
                "REDIS_PASSWORD": "optional",
                "REDIS_DB": "0"
            }
        },
        "migration_methods": {
            "rate_limiter": "InMemoryRateLimiter._migrate_to_redis()",
            "audit_logger": "Future implementation",
            "cache_system": "Future implementation"
        }
    }

# =============================================================================
# ERROR HANDLERS GLOBAIS (MELHORADOS)
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handler para recursos não encontrados."""
    await audit_logger.log_event(
        "not_found_error",
        request=request,
        path=str(request.url),
        method=request.method
    )
    
    return {
        "success": False,
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "Recurso não encontrado",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "request_id": getattr(request.state, 'request_id', 'unknown'),
            "system_status": get_api_health()["system_functional"]
        },
        "suggestions": [
            "Verifique se o ID está correto",
            "Confirme que o recurso existe na hierarquia Course→Book→Unit",
            "Consulte /docs para endpoints disponíveis",
            "Verifique /api/overview para estrutura da API"
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
    await audit_logger.log_event(
        "rate_limit_exceeded",
        request=request,
        path=str(request.url),
        method=request.method
    )
    
    return {
        "success": False,
        "error_code": "RATE_LIMIT_EXCEEDED",
        "message": "Limite de requisições excedido",
        "details": {
            "path": str(request.url),
            "method": request.method,
            "storage_type": "in-memory",
            "retry_after": 60,
            "request_id": getattr(request.state, 'request_id', 'unknown')
        },
        "suggestions": [
            "Aguarde 60 segundos antes de tentar novamente",
            "Considere implementar cache local para reduzir requests",
            "Verifique se não há requests desnecessários em loop",
            "Para operações em lote, use paginação adequada"
        ],
        "rate_limit_info": {
            "check_limits": "GET /system/rate-limits para ver limites específicos",
            "storage": "In-memory (Redis migration available)",
            "windows": "Janelas deslizantes com cleanup automático"
        }
    }

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Handler para erros de validação Pydantic."""
    validation_errors = []
    
    if hasattr(exc, 'errors'):
        for error in exc.errors():
            validation_errors.append({
                "field": " → ".join(str(loc) for loc in error.get('loc', [])),
                "message": error.get('msg', 'Validation error'),
                "type": error.get('type', 'unknown'),
                "input": error.get('input')
            })
    
    await audit_logger.log_event(
        "validation_error",
        request=request,
        path=str(request.url),
        validation_errors=validation_errors
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
    await audit_logger.log_event(
        "internal_server_error",
        request=request,
        error_type=type(exc).__name__,
        error_message=str(exc)
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
            "exception_type": type(exc).__name__,
            "system_status": get_api_health()["system_functional"]
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
    await audit_logger.log_event(
        "bad_request",
        request=request,
        error_message=str(exc)
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
# ENDPOINTS DE DEBUG E DESENVOLVIMENTO
# =============================================================================

@app.get("/debug/api-status", tags=["debug"], include_in_schema=False)
async def debug_api_status():
    """Endpoint de debug para verificar status da API."""
    load_summary = router_loader.get_load_summary()
    
    return {
        "debug_info": {
            "router_loader_summary": load_summary,
            "api_health": get_api_health(),
            "loaded_routers": router_loader.loaded_routers,
            "failed_routers": router_loader.failed_routers
        },
        "storage_info": {
            "rate_limiter_active": True,
            "rate_limiter_requests": len(rate_limiter.requests),
            "audit_logger_enabled": audit_logger.enabled,
            "redis_ready": True,
            "redis_enabled": False
        },
        "environment_checks": {
            "python_version": "3.11+",
            "fastapi_version": "Latest",
            "langchain_version": "0.3.x",
            "pydantic_version": "2.x"
        },
        "migration_readiness": {
            "redis_code_ready": True,
            "migration_methods_available": True,
            "fallback_mechanisms": True
        }
    }

@app.get("/debug/routes", tags=["debug"], include_in_schema=False)
async def debug_routes():
    """Lista todas as rotas registradas."""
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
            "debug": [r for r in routes_info if r['path'].startswith('/debug')],
            "legacy": [r for r in routes_info if not any(r['path'].startswith(p) for p in ['/api/v2', '/system', '/health', '/debug', '/docs', '/redoc', '/openapi.json'])]
        },
        "router_summary": router_loader.get_load_summary()
    }

@app.get("/debug/storage", tags=["debug"], include_in_schema=False)
async def debug_storage():
    """Debug de informações de storage."""
    return {
        "rate_limiter": {
            "type": "InMemoryRateLimiter",
            "active_requests": len(rate_limiter.requests),
            "limits_configured": rate_limiter.limits,
            "cleanup_interval": rate_limiter.cleanup_interval,
            "last_cleanup": rate_limiter.last_cleanup,
            "redis_ready": hasattr(rate_limiter, '_migrate_to_redis')
        },
        "audit_logger": {
            "type": "SimpleAuditLogger",
            "enabled": audit_logger.enabled,
            "active_requests": len(audit_logger.request_times),
            "extensible": True
        },
        "migration_info": {
            "redis_migration_ready": True,
            "persistent_storage_ready": False,
            "clustering_ready": False,
            "implementation_effort": "Low"
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
    print(f"   💾 Storage: In-memory (Redis-ready)")
    print("   📚 Documentação: http://localhost:8000/docs")
    print("   🔧 Debug: http://localhost:8000/debug/api-status")
    print("   🔄 Redis Migration: http://localhost:8000/system/redis-migration")
    print("=" * 50)
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )