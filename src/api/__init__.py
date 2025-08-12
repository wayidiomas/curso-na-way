# src/api/__init__.py
"""
API Principal do IVO V2 - Intelligent Vocabulary Organizer
Centraliza todos os routers e configurações da API com imports condicionais robustos.

Arquitetura hierárquica: Course → Book → Unit → Content
"""

import importlib
import logging
from typing import Dict, Any, Optional

# Setup logging
logger = logging.getLogger(__name__)

# Versão da API geral
__version__ = "2.0.0"

# =============================================================================
# IMPORTS CONDICIONAIS COM TRATAMENTO DE ERRO - CORRIGIDO
# =============================================================================

# Health router (prioridade alta)
try:
    from .health import router as health_router
    HEALTH_AVAILABLE = True
    logger.debug("✅ Health router loaded successfully")
except ImportError as e:
    health_router = None
    HEALTH_AVAILABLE = False
    logger.warning(f"⚠️ Health router not available: {e}")

# V2 modules - import individual com fallback
v2_modules = {}
v2_availability = {}

# Módulos V2 esperados
EXPECTED_V2_MODULES = [
    "courses", "books", "units", "vocabulary", 
    "sentences", "tips", "grammar", "assessments", "qa"
]

# Import cada módulo V2 individualmente - VERSÃO CORRIGIDA
for module_name in EXPECTED_V2_MODULES:
    try:
        # CORREÇÃO: Usar importlib.import_module sem parâmetro package inválido
        module = importlib.import_module(f"src.api.v2.{module_name}")
        
        if hasattr(module, 'router'):
            v2_modules[module_name] = module
            v2_availability[module_name] = True
            logger.debug(f"✅ V2 module '{module_name}' loaded successfully")
        else:
            v2_availability[module_name] = False
            logger.warning(f"⚠️ V2 module '{module_name}' exists but has no router")
    except ImportError as e:
        v2_availability[module_name] = False
        logger.warning(f"⚠️ V2 module '{module_name}' not available: {e}")
    except Exception as e:
        v2_availability[module_name] = False
        logger.error(f"❌ Error loading V2 module '{module_name}': {e}")

# Contadores de status
v2_loaded_count = sum(1 for available in v2_availability.values() if available)
v2_expected_count = len(EXPECTED_V2_MODULES)
v2_completion_percentage = (v2_loaded_count / v2_expected_count) * 100

logger.info(f"📊 V2 API Status: {v2_loaded_count}/{v2_expected_count} modules ({v2_completion_percentage:.1f}%)")

# =============================================================================
# CONFIGURAÇÕES DA API
# =============================================================================

# Informações da API principal
API_INFO = {
    "name": "IVO V2 API",
    "version": __version__,
    "description": "Sistema hierárquico inteligente para geração de apostilas de inglês com IA contextual",
    "architecture": "Course → Book → Unit → Content",
    "author": "Curso Na Way",
    "features": [
        "hierarchical_content_structure",
        "rag_based_generation", 
        "intelligent_vocabulary_management",
        "ipa_phonetic_validation",
        "brazilian_learner_optimization",
        "mcp_image_analysis",
        "tips_grammar_strategies",
        "bloom_taxonomy_qa",
        "assessment_balancing",
        "rate_limiting_and_audit",
        "advanced_pagination"
    ],
    "methodology": [
        "Direct Method",
        "6 TIPS Strategies", 
        "2 GRAMMAR Strategies",
        "Bloom's Taxonomy",
        "L1→L2 Interference Prevention"
    ]
}

# Routers disponíveis (construído dinamicamente)
AVAILABLE_ROUTERS = {}

# Adicionar health router se disponível
if HEALTH_AVAILABLE:
    AVAILABLE_ROUTERS["health"] = health_router

# Adicionar módulos V2 disponíveis
AVAILABLE_ROUTERS["v2"] = {}
for module_name, is_available in v2_availability.items():
    if is_available and module_name in v2_modules:
        AVAILABLE_ROUTERS["v2"][module_name] = v2_modules[module_name].router

# Tags para documentação automática (baseadas nos módulos carregados)
API_TAGS = {}

if HEALTH_AVAILABLE:
    API_TAGS["health"] = {
        "name": "health",
        "description": "🏥 Health checks e monitoramento do sistema"
    }

# Tags V2 dinâmicas
v2_tag_descriptions = {
    "courses": "📚 Gestão de cursos hierárquicos com níveis CEFR",
    "books": "📖 Gestão de books organizados por nível CEFR",
    "units": "📑 Gestão de unidades pedagógicas com imagens obrigatórias",
    "vocabulary": "🔤 Geração inteligente de vocabulário com RAG + IPA + MCP",
    "sentences": "📝 Geração de sentences conectadas ao vocabulário",
    "tips": "💡 Estratégias TIPS (6 tipos) para unidades lexicais",
    "grammar": "📐 Estratégias GRAMMAR (2 tipos) com prevenção L1→L2",
    "assessments": "🎯 Atividades balanceadas de avaliação (2 de 7 tipos)",
    "qa": "❓ Perguntas pedagógicas com Taxonomia de Bloom"
}

for module_name, is_available in v2_availability.items():
    if is_available:
        API_TAGS[f"v2-{module_name}"] = {
            "name": f"v2-{module_name}",
            "description": v2_tag_descriptions.get(module_name, f"V2 {module_name} operations")
        }

# Configurações de rate limiting globais
GLOBAL_RATE_LIMITS = {
    "default": "100/minute",
    "content_generation": "10/minute",
    "image_upload": "20/minute", 
    "heavy_operations": "5/minute",
    "vocabulary_generation": "3/minute",
    "assessment_generation": "2/minute"
}

# Status de implementação dos endpoints (calculado dinamicamente)
IMPLEMENTATION_STATUS = {
    "health": {"status": "complete" if HEALTH_AVAILABLE else "missing", "coverage": 100 if HEALTH_AVAILABLE else 0},
    "v2": {}
}

# Status individual dos módulos V2
v2_coverage_estimates = {
    "courses": 100,
    "books": 100, 
    "units": 100,
    "vocabulary": 100,
    "assessments": 100,
    "tips": 95,
    "grammar": 95,
    "sentences": 90,
    "qa": 90
}

for module_name, is_available in v2_availability.items():
    if is_available:
        IMPLEMENTATION_STATUS["v2"][module_name] = {
            "status": "complete",
            "coverage": v2_coverage_estimates.get(module_name, 90)
        }
    else:
        IMPLEMENTATION_STATUS["v2"][module_name] = {
            "status": "missing",
            "coverage": 0
        }

# Cálculo de completion geral
total_coverage = 0
total_modules = 0

if HEALTH_AVAILABLE:
    total_coverage += 100
    total_modules += 1

for module_name, status in IMPLEMENTATION_STATUS["v2"].items():
    total_coverage += status["coverage"]
    total_modules += 1

overall_completion = total_coverage / total_modules if total_modules > 0 else 0
IMPLEMENTATION_STATUS["overall_completion"] = overall_completion

# Funcionalidades experimentais/beta
EXPERIMENTAL_FEATURES = {
    "voice_generation": False,
    "batch_processing": False,
    "interactive_exercises": False,
    "real_time_collaboration": False,
    "advanced_analytics": True,
    "custom_templates": False,
    "multi_language_support": False,
    "ai_tutoring": False
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_api_overview() -> Dict[str, Any]:
    """Retorna visão geral completa da API."""
    return {
        "api_info": API_INFO,
        "implementation_status": IMPLEMENTATION_STATUS,
        "module_availability": {
            "health": HEALTH_AVAILABLE,
            "v2_modules": v2_availability,
            "v2_loaded_count": v2_loaded_count,
            "v2_expected_count": v2_expected_count,
            "v2_completion_percentage": v2_completion_percentage
        },
        "available_routers": {
            "health": HEALTH_AVAILABLE,
            "v2_modules": list(AVAILABLE_ROUTERS["v2"].keys())
        },
        "experimental_features": EXPERIMENTAL_FEATURES,
        "rate_limits": GLOBAL_RATE_LIMITS,
        "documentation_tags": list(API_TAGS.keys()),
        "missing_modules": [name for name, available in v2_availability.items() if not available]
    }

def get_router_by_name(router_name: str, version: str = "v2") -> Optional[Any]:
    """Obter router específico por nome e versão."""
    try:
        if version == "health" and router_name == "health":
            return AVAILABLE_ROUTERS.get("health")
        elif version == "v2" and router_name in AVAILABLE_ROUTERS.get("v2", {}):
            return AVAILABLE_ROUTERS["v2"][router_name]
        else:
            logger.warning(f"Router not found: {router_name} (version: {version})")
            return None
    except Exception as e:
        logger.error(f"Error getting router {router_name}: {e}")
        return None

def validate_api_health() -> Dict[str, Any]:
    """Validar saúde da configuração da API."""
    missing_modules = [name for name, available in v2_availability.items() if not available]
    
    health_report = {
        "routers_loaded": len(AVAILABLE_ROUTERS) > 0,
        "health_available": HEALTH_AVAILABLE,
        "v2_modules_count": v2_loaded_count,
        "expected_modules": v2_expected_count,
        "missing_modules": missing_modules,
        "configuration_valid": len(missing_modules) == 0,
        "completion_status": {
            "loaded": v2_loaded_count,
            "expected": v2_expected_count,
            "percentage": v2_completion_percentage
        },
        "degradation_level": "none" if len(missing_modules) == 0 else "partial" if v2_loaded_count > 0 else "severe"
    }
    
    return health_report

def get_hierarchical_flow() -> Dict[str, Any]:
    """Retorna fluxo hierárquico recomendado da API."""
    return {
        "hierarchy": "Course → Book → Unit → Content",
        "creation_flow": [
            "1. POST /api/v2/courses (Criar curso com níveis CEFR)",
            "2. POST /api/v2/courses/{id}/books (Criar books por nível CEFR)",
            "3. POST /api/v2/books/{id}/units (Criar unidades com imagens obrigatórias)",
            "4. POST /api/v2/units/{id}/vocabulary (Gerar vocabulário RAG + IPA)",
            "5. POST /api/v2/units/{id}/sentences (Gerar sentences conectadas)",
            "6. POST /api/v2/units/{id}/tips OU /grammar (Estratégias pedagógicas)",
            "7. POST /api/v2/units/{id}/assessments (Atividades balanceadas)",
            "8. POST /api/v2/units/{id}/qa (Opcional - Q&A com Bloom's taxonomy)"
        ],
        "content_dependencies": {
            "vocabulary": ["unit_created_with_images"],
            "sentences": ["vocabulary_generated"],
            "tips": ["vocabulary", "sentences", "unit_type=lexical"],
            "grammar": ["vocabulary", "sentences", "unit_type=grammar"], 
            "assessments": ["vocabulary", "sentences", "strategy_applied"],
            "qa": ["all_previous_content_complete"]
        },
        "rag_integration": [
            "Vocabulário: prevenção de repetições com contexto histórico",
            "Estratégias: balanceamento TIPS/GRAMMAR baseado em uso anterior",
            "Assessments: distribuição equilibrada dos 7 tipos disponíveis",
            "Progressão: análise pedagógica contínua Course→Book→Unit"
        ],
        "validation_rules": [
            "Hierarquia obrigatória: course_id → book_id → unit_id",
            "CEFR consistency: book level deve estar nos níveis do course",
            "Image requirement: units precisam de 1-2 imagens para vocabulary",
            "Strategy selection: tips para lexical_unit, grammar para grammar_unit"
        ]
    }

def get_missing_modules_info() -> Dict[str, Any]:
    """Retorna informações sobre módulos faltantes."""
    missing = [name for name, available in v2_availability.items() if not available]
    
    if not missing:
        return {"status": "complete", "message": "All modules loaded successfully!"}
    
    priority_order = ["sentences", "tips", "grammar", "qa", "courses", "books", "units", "vocabulary", "assessments"]
    
    missing_sorted = sorted(missing, key=lambda x: priority_order.index(x) if x in priority_order else 999)
    
    return {
        "status": "incomplete",
        "missing_count": len(missing),
        "missing_modules": missing_sorted,
        "priority_recommendations": {
            "high_priority": [m for m in missing_sorted if m in ["sentences", "tips", "grammar"]],
            "medium_priority": [m for m in missing_sorted if m in ["qa"]],
            "critical": [m for m in missing_sorted if m in ["courses", "books", "units", "vocabulary", "assessments"]]
        },
        "impact_assessment": {
            "content_generation": "limited" if any(m in missing for m in ["sentences", "tips", "grammar"]) else "full",
            "core_hierarchy": "broken" if any(m in missing for m in ["courses", "books", "units"]) else "functional",
            "basic_functionality": "available" if v2_loaded_count >= 3 else "limited"
        }
    }

# Configuração de middleware recomendada
MIDDLEWARE_CONFIG = {
    "cors": {
        "allow_origins": ["*"],  # Configurar conforme necessário em produção
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["*"]
    },
    "rate_limiting": {
        "enabled": True,
        "storage": "memory",  # in-memory para simplicidade
        "fallback": "allow",
        "per_endpoint_limits": True
    },
    "audit_logging": {
        "enabled": True,
        "log_level": "INFO",
        "track_performance": True,
        "include_request_body": False,  # Privacy
        "include_response_body": False   # Performance
    },
    "security": {
        "max_request_size": "10MB",  # Para upload de imagens
        "timeout_seconds": 60,       # Para geração de conteúdo IA
        "validate_content_type": True,
        "require_https": False        # Configurar True em produção
    }
}

# =============================================================================
# AUTO-VALIDATION E EXPORTS
# =============================================================================

def _validate_on_import() -> Dict[str, Any]:
    """Validação automática quando o módulo é importado."""
    try:
        health = validate_api_health()
        missing_info = get_missing_modules_info()
        
        if not health["configuration_valid"]:
            logger.warning(f"⚠️ API configuration incomplete: {health['missing_modules']}")
            logger.info(f"📊 Status: {health['completion_status']['loaded']}/{health['completion_status']['expected']} modules loaded")
        else:
            logger.info("✅ API configuration complete - all modules loaded")
        
        return {
            "health": health,
            "missing_info": missing_info,
            "validation_timestamp": __import__("time").time()
        }
    except Exception as e:
        logger.error(f"❌ Failed to validate API configuration: {str(e)}")
        return {
            "configuration_valid": False, 
            "error": str(e),
            "validation_timestamp": __import__("time").time()
        }

# Executar validação automática
_api_health = _validate_on_import()

# Exportações públicas (dinâmicas baseadas na disponibilidade)
__all__ = [
    "API_INFO",
    "API_TAGS", 
    "AVAILABLE_ROUTERS",
    "IMPLEMENTATION_STATUS",
    "MIDDLEWARE_CONFIG",
    "get_api_overview",
    "get_router_by_name",
    "validate_api_health",
    "get_hierarchical_flow",
    "get_missing_modules_info"
]

# Adicionar health router se disponível
if HEALTH_AVAILABLE:
    __all__.append("health_router")

# Adicionar módulos V2 disponíveis
for module_name, is_available in v2_availability.items():
    if is_available:
        globals()[module_name] = v2_modules[module_name]
        __all__.append(module_name)

# Log final de status
if _api_health.get("health", {}).get("configuration_valid", False):
    logger.info(f"🚀 IVO V2 API initialized successfully ({overall_completion:.1f}% complete)")
else:
    missing_count = len(_api_health.get("health", {}).get("missing_modules", []))
    logger.warning(f"⚠️ IVO V2 API initialized with {missing_count} missing modules ({overall_completion:.1f}% complete)")

# Informação para debugging
__debug_info__ = {
    "v2_availability": v2_availability,
    "health_available": HEALTH_AVAILABLE,
    "loaded_modules": list(AVAILABLE_ROUTERS.get("v2", {}).keys()),
    "api_health": _api_health
}