"""
API V2 - Sistema Hierárquico IVO V2
Course → Book → Unit com geração de conteúdo inteligente
"""

from . import courses, books, units, vocabulary, assessments

# Versão da API V2
__version__ = "2.0.0"

# Informações da arquitetura
API_INFO = {
    "version": __version__,
    "name": "IVO V2 API",
    "description": "Sistema hierárquico para geração de apostilas de inglês",
    "architecture": "Course → Book → Unit",
    "features": [
        "hierarchical_structure",
        "rag_integration", 
        "intelligent_content_generation",
        "rate_limiting",
        "audit_logging",
        "pagination"
    ]
}

# Routers disponíveis
AVAILABLE_ROUTERS = {
    "courses": courses.router,
    "books": books.router,
    "units": units.router,
    "vocabulary": vocabulary.router,
    "assessments": assessments.router
}

# Endpoints implementados
IMPLEMENTED_ENDPOINTS = {
    "courses": [
        "POST /api/v2/courses",
        "GET /api/v2/courses",
        "GET /api/v2/courses/{id}",
        "GET /api/v2/courses/{id}/hierarchy",
        "GET /api/v2/courses/{id}/progress",
        "PUT /api/v2/courses/{id}",
        "DELETE /api/v2/courses/{id}"
    ],
    "books": [
        "POST /api/v2/courses/{course_id}/books",
        "GET /api/v2/courses/{course_id}/books",
        "GET /api/v2/books/{id}",
        "GET /api/v2/books/{id}/progression",
        "PUT /api/v2/books/{id}",
        "DELETE /api/v2/books/{id}"
    ],
    "units": [
        "POST /api/v2/books/{book_id}/units",
        "GET /api/v2/books/{book_id}/units",
        "GET /api/v2/units/{id}",
        "GET /api/v2/units/{id}/context",
        "PUT /api/v2/units/{id}/status",
        "PUT /api/v2/units/{id}",
        "DELETE /api/v2/units/{id}"
    ],
    "vocabulary": [
        "POST /api/v2/units/{unit_id}/vocabulary",
        "GET /api/v2/units/{unit_id}/vocabulary",
        "PUT /api/v2/units/{unit_id}/vocabulary",
        "DELETE /api/v2/units/{unit_id}/vocabulary",
        "GET /api/v2/units/{unit_id}/vocabulary/analysis"
    ],
    "assessments": [
        "POST /api/v2/units/{unit_id}/assessments",
        "GET /api/v2/units/{unit_id}/assessments",
        "PUT /api/v2/units/{unit_id}/assessments",
        "DELETE /api/v2/units/{unit_id}/assessments",
        "GET /api/v2/units/{unit_id}/assessments/analysis",
        "GET /api/v2/assessments/types"
    ]
}

# Endpoints ainda não implementados (para completar)
PENDING_ENDPOINTS = {
    "sentences": [
        "POST /api/v2/units/{unit_id}/sentences",
        "GET /api/v2/units/{unit_id}/sentences",
        "PUT /api/v2/units/{unit_id}/sentences",
        "DELETE /api/v2/units/{unit_id}/sentences",
        "GET /api/v2/units/{unit_id}/sentences/analysis"
    ],
    "tips": [
        "POST /api/v2/units/{unit_id}/tips",
        "GET /api/v2/units/{unit_id}/tips",
        "PUT /api/v2/units/{unit_id}/tips",
        "DELETE /api/v2/units/{unit_id}/tips",
        "GET /api/v2/units/{unit_id}/tips/analysis"
    ],
    "grammar": [
        "POST /api/v2/units/{unit_id}/grammar",
        "GET /api/v2/units/{unit_id}/grammar",
        "PUT /api/v2/units/{unit_id}/grammar",
        "DELETE /api/v2/units/{unit_id}/grammar",
        "GET /api/v2/units/{unit_id}/grammar/analysis"
    ]
}

# Status da implementação
IMPLEMENTATION_STATUS = {
    "completed": ["courses", "books", "units", "vocabulary", "assessments"],
    "pending": ["sentences", "tips", "grammar"],
    "completion_percentage": 62.5  # 5 de 8 módulos completos
}

# Fluxo recomendado de uso
RECOMMENDED_FLOW = [
    "1. Criar Course",
    "2. Criar Books por nível CEFR",
    "3. Criar Units sequenciais",
    "4. Gerar Vocabulary com RAG",
    "5. Gerar Sentences conectadas",
    "6. Gerar Tips ou Grammar",
    "7. Gerar Assessments (finaliza unit)",
    "8. Unit completed!"
]

# Configurações de rate limiting específicas
RATE_LIMITS = {
    "courses": {"create": "10/min", "list": "100/min", "get": "200/min"},
    "books": {"create": "20/min", "list": "150/min", "get": "200/min"},
    "units": {"create": "5/min", "list": "100/min", "get": "150/min"},
    "vocabulary": {"generate": "3/min", "get": "150/min"},
    "assessments": {"generate": "2/min", "get": "100/min"}
}

# Tags para documentação
ROUTER_TAGS = {
    "courses": "v2-courses",
    "books": "v2-books", 
    "units": "v2-units",
    "vocabulary": "v2-vocabulary",
    "assessments": "v2-assessments"
}

# Função para obter informações da API
def get_api_info():
    """Retorna informações completas da API V2."""
    return {
        "api_info": API_INFO,
        "implementation_status": IMPLEMENTATION_STATUS,
        "endpoints": {
            "implemented": IMPLEMENTED_ENDPOINTS,
            "pending": PENDING_ENDPOINTS
        },
        "recommended_flow": RECOMMENDED_FLOW,
        "rate_limits": RATE_LIMITS
    }

# Função para verificar se um endpoint está implementado
def is_endpoint_implemented(endpoint_path: str) -> bool:
    """Verifica se um endpoint específico está implementado."""
    for module_endpoints in IMPLEMENTED_ENDPOINTS.values():
        if endpoint_path in module_endpoints:
            return True
    return False

# Função para listar próximos endpoints a implementar
def get_next_endpoints_to_implement():
    """Retorna lista de próximos endpoints a implementar."""
    return {
        "priority_1": PENDING_ENDPOINTS["sentences"],
        "priority_2": PENDING_ENDPOINTS["tips"],
        "priority_3": PENDING_ENDPOINTS["grammar"]
    }

# Validação de importações
def validate_imports():
    """Valida se todos os módulos necessários estão disponíveis."""
    validation_results = {}
    
    # Módulos implementados
    implemented_modules = ["courses", "books", "units", "vocabulary", "assessments"]
    
    for module_name in implemented_modules:
        try:
            module = globals()[module_name]
            validation_results[module_name] = {
                "status": "available",
                "router": hasattr(module, "router"),
                "endpoints": len(IMPLEMENTED_ENDPOINTS.get(module_name, []))
            }
        except Exception as e:
            validation_results[module_name] = {
                "status": "error",
                "error": str(e)
            }
    
    return validation_results

# Exportações públicas
__all__ = [
    "courses",
    "books", 
    "units",
    "vocabulary",
    "assessments",
    "API_INFO",
    "AVAILABLE_ROUTERS",
    "IMPLEMENTED_ENDPOINTS",
    "PENDING_ENDPOINTS",
    "IMPLEMENTATION_STATUS",
    "get_api_info",
    "is_endpoint_implemented",
    "get_next_endpoints_to_implement",
    "validate_imports"
]