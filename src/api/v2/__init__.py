"""
API V2 - Sistema Hierárquico IVO V2
Course → Book → Unit com geração de conteúdo inteligente

Arquitetura completa com todos os módulos:
- Hierarquia: courses, books, units
- Conteúdo: vocabulary, sentences, tips, grammar, assessments, qa
- Sistema: health
"""

# Imports condicionais com tratamento de erro
try:
    from . import courses
    COURSES_AVAILABLE = True
except ImportError as e:
    courses = None
    COURSES_AVAILABLE = False
    print(f"⚠️ courses module not available: {e}")

try:
    from . import books
    BOOKS_AVAILABLE = True
except ImportError as e:
    books = None
    BOOKS_AVAILABLE = False
    print(f"⚠️ books module not available: {e}")

try:
    from . import units
    UNITS_AVAILABLE = True
except ImportError as e:
    units = None
    UNITS_AVAILABLE = False
    print(f"⚠️ units module not available: {e}")

try:
    from . import vocabulary
    VOCABULARY_AVAILABLE = True
except ImportError as e:
    vocabulary = None
    VOCABULARY_AVAILABLE = False
    print(f"⚠️ vocabulary module not available: {e}")

try:
    from . import sentences
    SENTENCES_AVAILABLE = True
except ImportError as e:
    sentences = None
    SENTENCES_AVAILABLE = False
    print(f"⚠️ sentences module not available: {e}")

try:
    from . import tips
    TIPS_AVAILABLE = True
except ImportError as e:
    tips = None
    TIPS_AVAILABLE = False
    print(f"⚠️ tips module not available: {e}")

try:
    from . import grammar
    GRAMMAR_AVAILABLE = True
except ImportError as e:
    grammar = None
    GRAMMAR_AVAILABLE = False
    print(f"⚠️ grammar module not available: {e}")

try:
    from . import assessments
    ASSESSMENTS_AVAILABLE = True
except ImportError as e:
    assessments = None
    ASSESSMENTS_AVAILABLE = False
    print(f"⚠️ assessments module not available: {e}")

try:
    from . import qa
    QA_AVAILABLE = True
except ImportError as e:
    qa = None
    QA_AVAILABLE = False
    print(f"⚠️ qa module not available: {e}")

try:
    from .. import health  # ← CORRETO: health está em api/, não em api/v2/
    HEALTH_AVAILABLE = True
except ImportError as e:
    health = None
    HEALTH_AVAILABLE = False
    print(f"⚠️ health module not available: {e}")

# Versão da API V2
__version__ = "2.0.0"

# Informações da arquitetura
API_INFO = {
    "version": __version__,
    "name": "IVO V2 API",
    "description": "Sistema hierárquico para geração de apostilas de inglês com IA contextual",
    "architecture": "Course → Book → Unit → Content",
    "features": [
        "hierarchical_structure",
        "rag_integration", 
        "intelligent_content_generation",
        "ipa_validation",
        "l1_interference_prevention",
        "assessment_balancing",
        "bloom_taxonomy_qa",
        "rate_limiting",
        "audit_logging",
        "pagination",
        "mcp_image_analysis"
    ]
}

# Routers disponíveis (apenas os que foram importados com sucesso)
AVAILABLE_ROUTERS = {
    "health": health.router if HEALTH_AVAILABLE else None,
    "v2": {}
}

# Construir dicionário de routers V2 dinamicamente
if COURSES_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["courses"] = courses.router
if BOOKS_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["books"] = books.router
if UNITS_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["units"] = units.router
if VOCABULARY_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["vocabulary"] = vocabulary.router
if SENTENCES_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["sentences"] = sentences.router
if TIPS_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["tips"] = tips.router
if GRAMMAR_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["grammar"] = grammar.router
if ASSESSMENTS_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["assessments"] = assessments.router
if QA_AVAILABLE:
    AVAILABLE_ROUTERS["v2"]["qa"] = qa.router

# Configuração de middleware
MIDDLEWARE_CONFIG = {
    "cors": {
        "allow_origins": ["*"],
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"]
    },
    "rate_limiting": {
        "enabled": True,
        "storage": "in_memory",
        "fallback_ready": True
    }
}

# Tags para documentação
API_TAGS = {
    "health": {
        "description": "🏥 Health checks e monitoramento do sistema",
        "external_docs": None
    },
    "v2-courses": {
        "description": "📚 Gestão de cursos completos com níveis CEFR",
        "external_docs": None
    },
    "v2-books": {
        "description": "📖 Gestão de books organizados por nível CEFR",
        "external_docs": None
    },
    "v2-units": {
        "description": "📑 Gestão de unidades pedagógicas com imagens obrigatórias",
        "external_docs": None
    },
    "v2-vocabulary": {
        "description": "🔤 Geração de vocabulário contextual com RAG + MCP + IPA",
        "external_docs": None
    },
    "v2-sentences": {
        "description": "📝 Geração de sentences conectadas ao vocabulário",
        "external_docs": None
    },
    "v2-tips": {
        "description": "💡 Estratégias TIPS (6 tipos) para unidades lexicais",
        "external_docs": None
    },
    "v2-grammar": {
        "description": "📐 Estratégias GRAMMAR (2 tipos) para unidades gramaticais",
        "external_docs": None
    },
    "v2-assessments": {
        "description": "🎯 Geração de atividades balanceadas (2 de 7 tipos)",
        "external_docs": None
    },
    "v2-qa": {
        "description": "❓ Q&A pedagógico baseado na Taxonomia de Bloom",
        "external_docs": None
    }
}

# Endpoints implementados (atualizados dinamicamente)
IMPLEMENTED_ENDPOINTS = {}

if COURSES_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["courses"] = [
        "POST /api/v2/courses",
        "GET /api/v2/courses",
        "GET /api/v2/courses/{id}",
        "GET /api/v2/courses/{id}/hierarchy",
        "GET /api/v2/courses/{id}/progress",
        "PUT /api/v2/courses/{id}",
        "DELETE /api/v2/courses/{id}"
    ]

if BOOKS_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["books"] = [
        "POST /api/v2/courses/{course_id}/books",
        "GET /api/v2/courses/{course_id}/books",
        "GET /api/v2/books/{id}",
        "GET /api/v2/books/{id}/progression",
        "PUT /api/v2/books/{id}",
        "DELETE /api/v2/books/{id}"
    ]

if UNITS_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["units"] = [
        "POST /api/v2/books/{book_id}/units",
        "GET /api/v2/books/{book_id}/units",
        "GET /api/v2/units/{id}",
        "GET /api/v2/units/{id}/context",
        "PUT /api/v2/units/{id}/status",
        "PUT /api/v2/units/{id}",
        "DELETE /api/v2/units/{id}"
    ]

if VOCABULARY_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["vocabulary"] = [
        "POST /api/v2/units/{unit_id}/vocabulary",
        "GET /api/v2/units/{unit_id}/vocabulary",
        "PUT /api/v2/units/{unit_id}/vocabulary",
        "DELETE /api/v2/units/{unit_id}/vocabulary",
        "GET /api/v2/units/{unit_id}/vocabulary/analysis"
    ]

if SENTENCES_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["sentences"] = [
        "POST /api/v2/units/{unit_id}/sentences",
        "GET /api/v2/units/{unit_id}/sentences",
        "PUT /api/v2/units/{unit_id}/sentences",
        "DELETE /api/v2/units/{unit_id}/sentences",
        "GET /api/v2/units/{unit_id}/sentences/analysis"
    ]

if TIPS_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["tips"] = [
        "POST /api/v2/units/{unit_id}/tips",
        "GET /api/v2/units/{unit_id}/tips",
        "PUT /api/v2/units/{unit_id}/tips",
        "DELETE /api/v2/units/{unit_id}/tips",
        "GET /api/v2/units/{unit_id}/tips/analysis",
        "GET /api/v2/tips/strategies"
    ]

if GRAMMAR_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["grammar"] = [
        "POST /api/v2/units/{unit_id}/grammar",
        "GET /api/v2/units/{unit_id}/grammar",
        "PUT /api/v2/units/{unit_id}/grammar",
        "DELETE /api/v2/units/{unit_id}/grammar",
        "GET /api/v2/units/{unit_id}/grammar/analysis",
        "GET /api/v2/grammar/strategies"
    ]

if ASSESSMENTS_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["assessments"] = [
        "POST /api/v2/units/{unit_id}/assessments",
        "GET /api/v2/units/{unit_id}/assessments",
        "PUT /api/v2/units/{unit_id}/assessments",
        "DELETE /api/v2/units/{unit_id}/assessments",
        "GET /api/v2/units/{unit_id}/assessments/analysis",
        "GET /api/v2/assessments/types"
    ]

if QA_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["qa"] = [
        "POST /api/v2/units/{unit_id}/qa",
        "GET /api/v2/units/{unit_id}/qa",
        "PUT /api/v2/units/{unit_id}/qa",
        "DELETE /api/v2/units/{unit_id}/qa",
        "GET /api/v2/units/{unit_id}/qa/analysis",
        "GET /api/v2/qa/pedagogical-guidelines"
    ]

if HEALTH_AVAILABLE:
    IMPLEMENTED_ENDPOINTS["health"] = [
        "GET /health",
        "GET /health/detailed"
    ]

# Endpoints ainda não implementados (calculados dinamicamente)
ALL_EXPECTED_MODULES = ["courses", "books", "units", "vocabulary", "sentences", "tips", "grammar", "assessments", "qa", "health"]
PENDING_ENDPOINTS = {}

# Marcar como pendente os módulos que não foram importados
module_availability = {
    "courses": COURSES_AVAILABLE,
    "books": BOOKS_AVAILABLE,
    "units": UNITS_AVAILABLE,
    "vocabulary": VOCABULARY_AVAILABLE,
    "sentences": SENTENCES_AVAILABLE,
    "tips": TIPS_AVAILABLE,
    "grammar": GRAMMAR_AVAILABLE,
    "assessments": ASSESSMENTS_AVAILABLE,
    "qa": QA_AVAILABLE,
    "health": HEALTH_AVAILABLE
}

for module_name, is_available in module_availability.items():
    if not is_available:
        PENDING_ENDPOINTS[module_name] = f"Module {module_name} not implemented or not importable"

# Status da implementação (calculado dinamicamente)
implemented_count = sum(1 for available in module_availability.values() if available)
total_expected = len(ALL_EXPECTED_MODULES)
completion_percentage = (implemented_count / total_expected) * 100

IMPLEMENTATION_STATUS = {
    "completed": [name for name, available in module_availability.items() if available],
    "pending": [name for name, available in module_availability.items() if not available],
    "completion_percentage": completion_percentage,
    "modules_loaded": implemented_count,
    "modules_expected": total_expected
}

# Fluxo hierárquico recomendado
HIERARCHICAL_FLOW = {
    "structure": "Course → Book → Unit → Content",
    "creation_sequence": [
        "1. POST /api/v2/courses (definir níveis CEFR e metodologia)",
        "2. POST /api/v2/courses/{course_id}/books (criar books por nível CEFR)",
        "3. POST /api/v2/books/{book_id}/units (criar units com imagens obrigatórias)",
        "4. Sequência de geração de conteúdo por unit"
    ],
    "content_generation_sequence": [
        "4.1. POST /api/v2/units/{unit_id}/vocabulary (RAG + MCP + IPA)",
        "4.2. POST /api/v2/units/{unit_id}/sentences (conectadas ao vocabulário)",
        "4.3. POST /api/v2/units/{unit_id}/tips (para lexical_unit) OU",
        "4.3. POST /api/v2/units/{unit_id}/grammar (para grammar_unit)",
        "4.4. POST /api/v2/units/{unit_id}/assessments (2 atividades balanceadas)",
        "4.5. POST /api/v2/units/{unit_id}/qa (opcional - Q&A pedagógico)"
    ],
    "validation": "Hierarquia obrigatória: course_id → book_id → unit_id"
}

# Configurações de rate limiting específicas
RATE_LIMITS = {
    "courses": {"create": "10/min", "list": "100/min", "get": "200/min"},
    "books": {"create": "20/min", "list": "150/min", "get": "200/min"},
    "units": {"create": "5/min", "list": "100/min", "get": "150/min"},
    "vocabulary": {"generate": "3/min", "get": "150/min"},
    "sentences": {"generate": "3/min", "get": "150/min"},
    "tips": {"generate": "2/min", "get": "100/min"},
    "grammar": {"generate": "2/min", "get": "100/min"},
    "assessments": {"generate": "2/min", "get": "100/min"},
    "qa": {"generate": "2/min", "get": "100/min"},
    "health": {"check": "unlimited"}
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_api_overview() -> dict:
    """Retorna visão geral completa da API V2."""
    return {
        "api_info": API_INFO,
        "implementation_status": IMPLEMENTATION_STATUS,
        "endpoints": {
            "implemented": IMPLEMENTED_ENDPOINTS,
            "pending": PENDING_ENDPOINTS
        },
        "hierarchical_flow": HIERARCHICAL_FLOW,
        "rate_limits": RATE_LIMITS,
        "middleware_config": MIDDLEWARE_CONFIG,
        "module_availability": module_availability
    }

def validate_api_health() -> dict:
    """Valida saúde da configuração da API."""
    return {
        "configuration_valid": len(PENDING_ENDPOINTS) == 0,
        "completion_status": {
            "percentage": completion_percentage,
            "loaded": implemented_count,
            "expected": total_expected
        },
        "missing_modules": list(PENDING_ENDPOINTS.keys()),
        "available_routers": list(AVAILABLE_ROUTERS["v2"].keys()),
        "health_summary": f"{implemented_count}/{total_expected} modules loaded"
    }

def get_hierarchical_flow() -> dict:
    """Retorna informações sobre o fluxo hierárquico."""
    return HIERARCHICAL_FLOW

def is_endpoint_implemented(endpoint_path: str) -> bool:
    """Verifica se um endpoint específico está implementado."""
    for module_endpoints in IMPLEMENTED_ENDPOINTS.values():
        if isinstance(module_endpoints, list) and endpoint_path in module_endpoints:
            return True
    return False

def get_next_endpoints_to_implement() -> dict:
    """Retorna lista de próximos endpoints a implementar."""
    pending_modules = [name for name, available in module_availability.items() if not available]
    
    if not pending_modules:
        return {"message": "All modules implemented!"}
    
    return {
        "priority_modules": pending_modules[:3],  # Top 3
        "all_pending": pending_modules,
        "recommendation": "Focus on content generation modules: sentences, tips, grammar, qa"
    }

def validate_imports() -> dict:
    """Valida se todos os módulos necessários estão disponíveis."""
    validation_results = {}
    
    for module_name, is_available in module_availability.items():
        if is_available:
            try:
                module = globals()[module_name]
                validation_results[module_name] = {
                    "status": "available",
                    "router": hasattr(module, "router"),
                    "endpoints": len(IMPLEMENTED_ENDPOINTS.get(module_name, []))
                }
            except Exception as e:
                validation_results[module_name] = {
                    "status": "import_error",
                    "error": str(e)
                }
        else:
            validation_results[module_name] = {
                "status": "not_available",
                "error": "Module not imported"
            }
    
    validation_results["summary"] = {
        "total_modules": len(module_availability),
        "available_modules": implemented_count,
        "missing_modules": len(PENDING_ENDPOINTS),
        "overall_health": completion_percentage >= 80.0
    }
    
    return validation_results

# =============================================================================
# EXPORTS
# =============================================================================

# Exportações condicionais baseadas na disponibilidade
__all__ = [
    # Utility functions (sempre disponíveis)
    "get_api_overview",
    "validate_api_health", 
    "get_hierarchical_flow",
    "is_endpoint_implemented",
    "get_next_endpoints_to_implement",
    "validate_imports",
    
    # Configuration (sempre disponível)
    "API_INFO",
    "AVAILABLE_ROUTERS",
    "MIDDLEWARE_CONFIG",
    "API_TAGS",
    "IMPLEMENTATION_STATUS",
    "HIERARCHICAL_FLOW",
    "RATE_LIMITS"
]

# Adicionar módulos disponíveis às exportações
if COURSES_AVAILABLE:
    __all__.append("courses")
if BOOKS_AVAILABLE:
    __all__.append("books")
if UNITS_AVAILABLE:
    __all__.append("units")
if VOCABULARY_AVAILABLE:
    __all__.append("vocabulary")
if SENTENCES_AVAILABLE:
    __all__.append("sentences")
if TIPS_AVAILABLE:
    __all__.append("tips")
if GRAMMAR_AVAILABLE:
    __all__.append("grammar")
if ASSESSMENTS_AVAILABLE:
    __all__.append("assessments")
if QA_AVAILABLE:
    __all__.append("qa")
if HEALTH_AVAILABLE:
    __all__.append("health")

# Log de inicialização
print(f"🚀 IVO V2 API initialized: {implemented_count}/{total_expected} modules ({completion_percentage:.1f}%)")
if PENDING_ENDPOINTS:
    print(f"⚠️ Missing modules: {list(PENDING_ENDPOINTS.keys())}")
else:
    print("✅ All modules loaded successfully!")