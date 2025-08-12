# src/__init__.py - IVO V2 Package Initialization
"""
🚀 IVO V2 - Intelligent Vocabulary Organizer
Sistema avançado de geração hierárquica de unidades pedagógicas com IA generativa.

Este módulo define o pacote principal do IVO V2 e facilita imports para outros módulos.
Arquitetura: Course → Book → Unit → Content (Vocabulary, Sentences, Strategies, Assessments)
"""

import logging
from typing import Dict, Any, Optional

# Version info
__version__ = "2.0.0"
__author__ = "Curso Na Way"
__description__ = "Sistema hierárquico de geração de conteúdo pedagógico com IA"
__architecture__ = "Course → Book → Unit → Content"

# Setup logging for the package
logger = logging.getLogger(__name__)

# =============================================================================
# PACKAGE METADATA
# =============================================================================

PACKAGE_INFO = {
    "name": "IVO V2 - Intelligent Vocabulary Organizer",
    "version": __version__,
    "author": __author__,
    "description": __description__,
    "architecture": __architecture__,
    "features": [
        "Hierarquia pedagógica obrigatória",
        "RAG contextual para progressão",
        "Validação IPA automática",
        "6 Estratégias TIPS + 2 Estratégias GRAMMAR",
        "7 Tipos de Assessment balanceados",
        "Q&A com Taxonomia de Bloom",
        "Prevenção L1→L2 (português→inglês)",
        "MCP Image Analysis",
        "Rate limiting inteligente",
        "Auditoria empresarial completa"
    ],
    "modules": {
        "core": "Modelos, validações, paginação, rate limiting, auditoria",
        "api": "Endpoints hierárquicos V2 + compatibilidade V1",
        "services": "Geradores de conteúdo com IA contextual",
        "mcp": "Model Context Protocol para análise de imagens",
        "config": "Configurações de banco, logging, settings"
    }
}

# =============================================================================
# IMPORT HELPERS
# =============================================================================

def get_package_info() -> Dict[str, Any]:
    """Retorna informações completas do pacote IVO V2."""
    return PACKAGE_INFO.copy()

def get_version() -> str:
    """Retorna a versão atual do IVO V2."""
    return __version__

def get_architecture_info() -> Dict[str, Any]:
    """Retorna informações sobre a arquitetura hierárquica."""
    return {
        "hierarchy": "Course → Book → Unit → Content",
        "levels": {
            "course": "Curso completo com níveis CEFR e metodologia",
            "book": "Módulo específico por nível CEFR (A1, A2, B1, etc.)",
            "unit": "Unidade pedagógica com imagens obrigatórias",
            "content": "Conteúdo gerado: vocabulary, sentences, strategies, assessments, qa"
        },
        "mandatory_flow": [
            "1. Create Course with CEFR levels",
            "2. Create Books per CEFR level", 
            "3. Create Units with images",
            "4. Generate Content sequentially"
        ],
        "rag_context": "Cada nível fornece contexto para evitar repetições"
    }

# =============================================================================
# CONDITIONAL IMPORTS WITH ERROR HANDLING
# =============================================================================

# Core imports (always available)
try:
    from .core.enums import CEFRLevel, UnitType, LanguageVariant, TipStrategy, GrammarStrategy, AssessmentType, UnitStatus
    from .core.hierarchical_models import Course, Book, UnitWithHierarchy
    from .core.unit_models import VocabularyItem, VocabularySection
    CORE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Core modules não disponíveis: {e}")
    CORE_AVAILABLE = False

# Services imports (may not be fully available)
try:
    from .services import (
        VocabularyGeneratorService,
        SentencesGeneratorService, 
        TipsGeneratorService,
        GrammarGenerator,
        AssessmentSelectorService,
        QAGeneratorService
    )
    SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Services não disponíveis: {e}")
    SERVICES_AVAILABLE = False

# API imports (may be partial)
try:
    from .api.v2 import courses, books, units, vocabulary, sentences, tips, grammar, assessments, qa
    API_V2_AVAILABLE = True
except ImportError as e:
    logger.warning(f"API V2 parcialmente disponível: {e}")
    API_V2_AVAILABLE = False

# MCP imports (optional)
try:
    from .mcp.mcp_image_client import analyze_images_for_unit_creation
    MCP_AVAILABLE = True
except ImportError as e:
    logger.debug(f"MCP não disponível: {e}")
    MCP_AVAILABLE = False

# =============================================================================
# MODULE STATUS CHECKING
# =============================================================================

def get_module_status() -> Dict[str, Any]:
    """Verifica status de disponibilidade dos módulos principais."""
    return {
        "core": {
            "available": CORE_AVAILABLE,
            "description": "Modelos, validações, enums, paginação",
            "critical": True
        },
        "services": {
            "available": SERVICES_AVAILABLE,
            "description": "Geradores de conteúdo com IA",
            "critical": True
        },
        "api_v2": {
            "available": API_V2_AVAILABLE,
            "description": "Endpoints hierárquicos principais",
            "critical": True
        },
        "mcp": {
            "available": MCP_AVAILABLE,
            "description": "Análise de imagens via OpenAI Vision",
            "critical": False
        },
        "overall_health": CORE_AVAILABLE and SERVICES_AVAILABLE and API_V2_AVAILABLE
    }

def validate_package_integrity() -> Dict[str, Any]:
    """Valida integridade completa do pacote."""
    module_status = get_module_status()
    
    critical_modules_ok = all([
        module_status["core"]["available"],
        module_status["services"]["available"], 
        module_status["api_v2"]["available"]
    ])
    
    # CORREÇÃO: Verificar se info é dict antes de acessar como subscriptable
    missing_critical_modules = []
    optional_modules_missing = []
    
    for name, info in module_status.items():
        
        if isinstance(info, dict) and info.get("critical") and not info.get("available"):
            missing_critical_modules.append(name)
        elif isinstance(info, dict) and not info.get("critical") and not info.get("available"):
            optional_modules_missing.append(name)
    
    return {
        "package_valid": critical_modules_ok,
        "version": __version__,
        "architecture": __architecture__,
        "module_status": module_status,
        "missing_critical_modules": missing_critical_modules,
        "optional_modules_missing": optional_modules_missing
    }

# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

# Conditional exports based on availability
__all__ = ["get_package_info", "get_version", "get_architecture_info", "get_module_status", "validate_package_integrity"]

# Add available classes to __all__
if CORE_AVAILABLE:
    __all__.extend([
        "CEFRLevel", "UnitType", "LanguageVariant", "TipStrategy", 
        "GrammarStrategy", "AssessmentType", "UnitStatus",
        "Course", "Book", "UnitWithHierarchy", 
        "VocabularyItem", "VocabularySection"
    ])

if SERVICES_AVAILABLE:
    __all__.extend([
        "VocabularyGeneratorService", "SentencesGeneratorService",
        "TipsGeneratorService", "GrammarGenerator", 
        "AssessmentSelectorService", "QAGeneratorService"
    ])

if MCP_AVAILABLE:
    __all__.extend(["analyze_images_for_unit_creation"])

# =============================================================================
# PACKAGE INITIALIZATION LOG
# =============================================================================

def _log_package_init():
    """Log de inicialização do pacote com status dos módulos."""
    status = validate_package_integrity()
    
    if status["package_valid"]:
        logger.info(f"✅ IVO V2 Package initialized successfully (v{__version__})")
        logger.info(f"🏗️ Architecture: {__architecture__}")
    else:
        logger.warning(f"⚠️ IVO V2 Package initialized with missing modules (v{__version__})")
        if status["missing_critical_modules"]:
            logger.warning(f"❌ Critical modules missing: {status['missing_critical_modules']}")
        if status["optional_modules_missing"]:
            logger.info(f"ℹ️ Optional modules missing: {status['optional_modules_missing']}")

# Initialize logging on import
_log_package_init()

# =============================================================================
# QUICK START HELPER
# =============================================================================

def get_quick_start_guide() -> Dict[str, Any]:
    """Retorna guia rápido para usar o IVO V2."""
    return {
        "installation_check": "import src; print(src.validate_package_integrity())",
        "basic_workflow": [
            "1. from src.services import VocabularyGeneratorService",
            "2. from src.core.hierarchical_models import Course, Book, UnitWithHierarchy", 
            "3. Create Course → Create Book → Create Unit → Generate Content",
            "4. Use API endpoints: /api/v2/courses, /api/v2/books, /api/v2/units"
        ],
        "api_documentation": "/docs (when FastAPI app is running)",
        "health_check": "/health (when FastAPI app is running)",
        "package_info": "src.get_package_info()",
        "architecture_info": "src.get_architecture_info()"
    }

# Add to exports
__all__.append("get_quick_start_guide")

# =============================================================================
# DEVELOPMENT UTILITIES
# =============================================================================

def _development_mode_check() -> bool:
    """Verifica se está em modo de desenvolvimento."""
    import os
    return os.getenv("ENVIRONMENT", "development").lower() == "development"

if _development_mode_check():
    logger.debug("🔧 IVO V2 running in development mode")
    logger.debug(f"📊 Module status: {get_module_status()}")

# =============================================================================
# PACKAGE CONSTANTS
# =============================================================================

# Export useful constants
SUPPORTED_CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
SUPPORTED_LANGUAGES = ["american_english", "british_english", "brazilian_portuguese"]
SUPPORTED_UNIT_TYPES = ["lexical_unit", "grammar_unit"]
DEFAULT_VOCABULARY_COUNT = 25
DEFAULT_SENTENCES_COUNT = 15
MAX_IMAGES_PER_UNIT = 2
MAX_IMAGE_SIZE_MB = 10

# Add constants to exports
__all__.extend([
    "SUPPORTED_CEFR_LEVELS", "SUPPORTED_LANGUAGES", "SUPPORTED_UNIT_TYPES",
    "DEFAULT_VOCABULARY_COUNT", "DEFAULT_SENTENCES_COUNT", 
    "MAX_IMAGES_PER_UNIT", "MAX_IMAGE_SIZE_MB"
])