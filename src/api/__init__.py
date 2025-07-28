# src/api/__init__.py
"""
API Principal do IVO V2 - Intelligent Vocabulary Organizer
Centraliza todos os routers e configurações da API
"""

from .health import router as health_router
from .v2 import (
    courses, books, units, vocabulary, assessments, 
    tips, grammar, sentences, qa
)

# Versão da API geral
__version__ = "2.0.0"

# Informações da API principal
API_INFO = {
    "name": "IVO V2 API",
    "version": __version__,
    "description": "Sistema hierárquico inteligente para geração de apostilas de inglês",
    "architecture": "Course → Book → Unit → Content",
    "author": "Curso Na Way",
    "features": [
        "hierarchical_content_structure",
        "rag_based_generation", 
        "intelligent_vocabulary_management",
        "ipa_phonetic_validation",
        "brazilian_learner_optimization",
        "mcp_image_analysis",
        "rate_limiting_and_audit",
        "advanced_pagination"
    ]
}

# Routers disponíveis por versão
AVAILABLE_ROUTERS = {
    "health": health_router,
    "v2": {
        "courses": courses.router,
        "books": books.router,
        "units": units.router,
        "vocabulary": vocabulary.router,
        "assessments": assessments.router,
        "tips": tips.router,
        "grammar": grammar.router,
        "sentences": sentences.router,
        "qa": qa.router
    }
}

# Tags para documentação automática
API_TAGS = {
    "health": {
        "name": "health",
        "description": "Health checks e monitoramento do sistema"
    },
    "v2-courses": {
        "name": "v2-courses", 
        "description": "Gestão de cursos hierárquicos"
    },
    "v2-books": {
        "name": "v2-books",
        "description": "Gestão de books por nível CEFR"
    },
    "v2-units": {
        "name": "v2-units",
        "description": "Gestão de unidades pedagógicas"
    },
    "v2-vocabulary": {
        "name": "v2-vocabulary",
        "description": "Geração inteligente de vocabulário com IPA"
    },
    "v2-sentences": {
        "name": "v2-sentences",
        "description": "Geração de sentences conectadas"
    },
    "v2-tips": {
        "name": "v2-tips",
        "description": "Estratégias TIPS para unidades lexicais"
    },
    "v2-grammar": {
        "name": "v2-grammar",
        "description": "Estratégias GRAMMAR com prevenção L1→L2"
    },
    "v2-assessments": {
        "name": "v2-assessments",
        "description": "Atividades balanceadas de avaliação"
    },
    "v2-qa": {
        "name": "v2-qa",
        "description": "Perguntas pedagógicas com Taxonomia de Bloom"
    }
}

# Configurações de rate limiting globais
GLOBAL_RATE_LIMITS = {
    "default": "100/minute",
    "generation": "10/minute",
    "upload": "20/minute",
    "heavy_operations": "5/minute"
}

# Status de implementação dos endpoints
IMPLEMENTATION_STATUS = {
    "health": {"status": "complete", "coverage": 100},
    "v2": {
        "courses": {"status": "complete", "coverage": 100},
        "books": {"status": "complete", "coverage": 100},
        "units": {"status": "complete", "coverage": 100},
        "vocabulary": {"status": "complete", "coverage": 100},
        "assessments": {"status": "complete", "coverage": 100},
        "tips": {"status": "complete", "coverage": 95},
        "grammar": {"status": "complete", "coverage": 95},
        "sentences": {"status": "complete", "coverage": 90},
        "qa": {"status": "complete", "coverage": 90}
    },
    "overall_completion": 96.25
}

# Funcionalidades experimentais/beta
EXPERIMENTAL_FEATURES = {
    "voice_generation": False,
    "batch_processing": False,
    "interactive_exercises": False,
    "real_time_collaboration": False,
    "advanced_analytics": True,
    "custom_templates": False
}

def get_api_overview():
    """Retorna visão geral completa da API."""
    return {
        "api_info": API_INFO,
        "implementation_status": IMPLEMENTATION_STATUS,
        "available_routers": list(AVAILABLE_ROUTERS.keys()),
        "v2_modules": list(AVAILABLE_ROUTERS["v2"].keys()),
        "experimental_features": EXPERIMENTAL_FEATURES,
        "rate_limits": GLOBAL_RATE_LIMITS,
        "documentation_tags": list(API_TAGS.keys())
    }

def get_router_by_name(router_name: str, version: str = "v2"):
    """Obter router específico por nome e versão."""
    if version == "health" and router_name == "health":
        return AVAILABLE_ROUTERS["health"]
    elif version == "v2" and router_name in AVAILABLE_ROUTERS["v2"]:
        return AVAILABLE_ROUTERS["v2"][router_name]
    else:
        return None

def validate_api_health():
    """Validar saúde da configuração da API."""
    health_report = {
        "routers_loaded": True,
        "v2_modules_count": len(AVAILABLE_ROUTERS["v2"]),
        "expected_modules": 9,  # courses, books, units, vocab, sentences, tips, grammar, assessments, qa
        "missing_modules": [],
        "configuration_valid": True
    }
    
    expected_v2_modules = [
        "courses", "books", "units", "vocabulary", 
        "sentences", "tips", "grammar", "assessments", "qa"
    ]
    
    for module in expected_v2_modules:
        if module not in AVAILABLE_ROUTERS["v2"]:
            health_report["missing_modules"].append(module)
            health_report["configuration_valid"] = False
    
    health_report["completion_status"] = {
        "loaded": len(AVAILABLE_ROUTERS["v2"]),
        "expected": len(expected_v2_modules),
        "percentage": (len(AVAILABLE_ROUTERS["v2"]) / len(expected_v2_modules)) * 100
    }
    
    return health_report

def get_hierarchical_flow():
    """Retorna fluxo hierárquico recomendado da API."""
    return {
        "hierarchy": "Course → Book → Unit → Content",
        "creation_flow": [
            "1. POST /api/v2/courses (Criar curso)",
            "2. POST /api/v2/courses/{id}/books (Criar books por nível)",
            "3. POST /api/v2/books/{id}/units (Criar unidades sequenciais)",
            "4. POST /api/v2/units/{id}/vocabulary (Gerar vocabulário)",
            "5. POST /api/v2/units/{id}/sentences (Gerar sentences)",
            "6. POST /api/v2/units/{id}/tips OU /grammar (Estratégias)",
            "7. POST /api/v2/units/{id}/assessments (Finalizar unidade)",
            "8. POST /api/v2/units/{id}/qa (Opcional - Q&A pedagógico)"
        ],
        "content_dependencies": {
            "vocabulary": ["unit_created"],
            "sentences": ["vocabulary"],
            "tips": ["vocabulary", "sentences"],
            "grammar": ["vocabulary", "sentences"], 
            "assessments": ["vocabulary", "sentences", "tips_or_grammar"],
            "qa": ["all_previous_content"]
        },
        "rag_integration": [
            "Vocabulário: prevenção de repetições",
            "Estratégias: balanceamento TIPS/GRAMMAR",
            "Assessments: distribuição equilibrada",
            "Progressão: análise pedagógica contínua"
        ]
    }

# Configuração de middleware recomendada
MIDDLEWARE_CONFIG = {
    "cors": {
        "allow_origins": ["*"],  # Permitir todos os domínios
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
        "allow_headers": ["*"]
    },
    "rate_limiting": {
        "enabled": True,
        "storage": "memory",  # ou "redis" se disponível
        "fallback": "allow"
    },
    "audit_logging": {
        "enabled": True,
        "log_level": "INFO",
        "track_performance": True
    },
    "security": {
        "max_request_size": "10MB",
        "timeout_seconds": 30,
        "validate_content_type": True
    }
}

# Exportações públicas
__all__ = [
    "health_router",
    "AVAILABLE_ROUTERS", 
    "API_INFO",
    "API_TAGS",
    "IMPLEMENTATION_STATUS",
    "get_api_overview",
    "get_router_by_name",
    "validate_api_health",
    "get_hierarchical_flow",
    "MIDDLEWARE_CONFIG"
]

# Validação automática na importação
def _validate_on_import():
    """Validação automática quando o módulo é importado."""
    try:
        health = validate_api_health()
        if not health["configuration_valid"]:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"API configuration issues detected: {health['missing_modules']}"
            )
        return health
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to validate API configuration: {str(e)}")
        return {"configuration_valid": False, "error": str(e)}

# Executar validação
_api_health = _validate_on_import()