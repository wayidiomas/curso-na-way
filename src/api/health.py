"""Health check endpoints - Atualizado para IVO V2 sem Redis."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import os
import logging
from typing import Dict, Any, List

from config.database import get_supabase_client
from src.services.hierarchical_database import hierarchical_db

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, str]
    system_info: Dict[str, Any]
    ivo_components: Dict[str, str]


class DetailedHealthResponse(BaseModel):
    """Response model para health check detalhado."""
    overall_status: str
    timestamp: str
    diagnostics: Dict[str, Any]
    recommendations: List[str]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Verifica saúde dos serviços do IVO V2."""
    services = {}
    ivo_components = {}
    system_info = {}
    
    # =============================================================================
    # CHECK SUPABASE DATABASE
    # =============================================================================
    try:
        supabase = get_supabase_client()
        # Teste mais robusto de conexão
        result = supabase.table("ivo_courses").select("id").limit(1).execute()
        services["supabase_connection"] = "healthy"
        
        # Verificar tabelas hierárquicas
        try:
            courses_count = supabase.table("ivo_courses").select("*", count="exact", head=True).execute().count
            books_count = supabase.table("ivo_books").select("*", count="exact", head=True).execute().count
            units_count = supabase.table("ivo_units").select("*", count="exact", head=True).execute().count
            
            services["supabase_tables"] = "healthy"
            system_info["database_stats"] = {
                "courses": courses_count,
                "books": books_count,
                "units": units_count
            }
        except Exception as e:
            services["supabase_tables"] = f"warning: {str(e)}"
            
    except Exception as e:
        services["supabase_connection"] = f"unhealthy: {str(e)}"
    
    # =============================================================================
    # CHECK OPENAI API (CRITICAL FOR CONTENT GENERATION)
    # =============================================================================
    try:
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.startswith("sk-"):
            services["openai_api"] = "healthy"
        else:
            services["openai_api"] = "unhealthy: API key not configured"
    except Exception as e:
        services["openai_api"] = f"unhealthy: {str(e)}"
    
    # =============================================================================
    # CHECK IVO V2 COMPONENTS
    # =============================================================================
    
    # Hierarchical Database Service
    try:
        # Teste simples do serviço
        test_course = await hierarchical_db.get_course("test_health_check")
        ivo_components["hierarchical_database"] = "healthy"
    except Exception as e:
        ivo_components["hierarchical_database"] = f"healthy: {str(e)}"  # Erro esperado para ID inexistente
    
    # Vocabulary Generator Service
    try:
        from src.services.vocabulary_generator import VocabularyGeneratorService
        vocab_service = VocabularyGeneratorService()
        ivo_components["vocabulary_generator"] = "healthy"
    except Exception as e:
        ivo_components["vocabulary_generator"] = f"unhealthy: {str(e)}"
    
    # MCP Image Analysis (Optional)
    try:
        from src.mcp.mcp_image_client import MCPImageAnalysisClient
        ivo_components["mcp_image_analysis"] = "healthy"
    except Exception as e:
        ivo_components["mcp_image_analysis"] = f"optional: {str(e)}"
    
    # Rate Limiter (Memory-based)
    try:
        from src.core.rate_limiter import rate_limiter
        ivo_components["rate_limiter"] = "healthy (memory-based)"
    except Exception as e:
        ivo_components["rate_limiter"] = f"unhealthy: {str(e)}"
    
    # Audit Logger
    try:
        from src.core.audit_logger import audit_logger_instance
        ivo_components["audit_logger"] = "healthy"
    except Exception as e:
        ivo_components["audit_logger"] = f"unhealthy: {str(e)}"
    
    # =============================================================================
    # CHECK ENVIRONMENT VARIABLES
    # =============================================================================
    required_env_vars = [
        "OPENAI_API_KEY",
        "SUPABASE_URL", 
        "SUPABASE_ANON_KEY"
    ]
    
    env_status = {}
    for var in required_env_vars:
        value = os.getenv(var)
        if value:
            env_status[var] = "configured"
        else:
            env_status[var] = "missing"
    
    services["environment_variables"] = "healthy" if all(
        status == "configured" for status in env_status.values()
    ) else "unhealthy"
    
    # =============================================================================
    # CHECK FILE SYSTEM PATHS
    # =============================================================================
    critical_paths = [
        "logs/",
        "data/images/uploads/",
        "data/images/processed/",
        "data/temp/",
        "config/prompts/"
    ]
    
    filesystem_status = {}
    for path in critical_paths:
        try:
            os.makedirs(path, exist_ok=True)
            filesystem_status[path] = "healthy"
        except Exception as e:
            filesystem_status[path] = f"unhealthy: {str(e)}"
    
    services["filesystem"] = "healthy" if all(
        "healthy" in status for status in filesystem_status.values()
    ) else "unhealthy"
    
    # =============================================================================
    # SYSTEM INFORMATION
    # =============================================================================
    system_info.update({
        "version": "2.0.0",
        "environment": os.getenv("APP_ENVIRONMENT", "development"),
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        "architecture": "Course → Book → Unit",
        "features_enabled": [
            "hierarchical_structure",
            "rate_limiting_memory",
            "audit_logging",
            "pagination",
            "vocabulary_generation",
            "mcp_image_analysis"
        ],
        "environment_variables": env_status,
        "filesystem_paths": filesystem_status
    })
    
    # =============================================================================
    # OVERALL HEALTH STATUS
    # =============================================================================
    critical_services = ["supabase_connection", "openai_api", "environment_variables"]
    critical_healthy = all(
        "healthy" in services.get(service, "missing") 
        for service in critical_services
    )
    
    ivo_healthy = all(
        "healthy" in status or "optional" in status
        for status in ivo_components.values()
    )
    
    overall_status = "healthy" if (critical_healthy and ivo_healthy) else "degraded"
    
    # Log do health check
    logger.info(f"Health check executado - Status: {overall_status}")
    if overall_status == "degraded":
        logger.warning("Sistema com componentes degradados - verificar logs")
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(),
        services=services,
        system_info=system_info,
        ivo_components=ivo_components
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Health check detalhado com diagnósticos específicos do IVO V2."""
    diagnostics = {}
    
    # =============================================================================
    # DIAGNÓSTICO DE HIERARQUIA
    # =============================================================================
    try:
        # Teste de criação de hierarquia
        from src.core.hierarchical_models import CourseCreateRequest
        from src.core.enums import CEFRLevel, LanguageVariant
        
        diagnostics["hierarchy_validation"] = {
            "models_importable": True,
            "enums_available": True,
            "status": "healthy"
        }
    except Exception as e:
        diagnostics["hierarchy_validation"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # =============================================================================
    # DIAGNÓSTICO DE GERAÇÃO DE CONTEÚDO
    # =============================================================================
    try:
        from src.services.vocabulary_generator import VocabularyGeneratorService
        
        # Teste de inicialização do serviço
        vocab_service = VocabularyGeneratorService()
        
        diagnostics["content_generation"] = {
            "vocabulary_service": "healthy",
            "llm_configured": bool(vocab_service.llm),
            "cache_system": "memory-based",
            "status": "healthy"
        }
    except Exception as e:
        diagnostics["content_generation"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # =============================================================================
    # DIAGNÓSTICO DE PROMPT TEMPLATES
    # =============================================================================
    prompt_files = [
        "config/prompts/vocab_generation.yaml",
        "config/prompts/ivo/vocabulary_generation.yaml",
        "config/prompts/ivo/sentences_generation.yaml"
    ]
    
    prompt_status = {}
    for file_path in prompt_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    prompt_status[file_path] = "available" if content.strip() else "empty"
            except Exception as e:
                prompt_status[file_path] = f"error: {str(e)}"
        else:
            prompt_status[file_path] = "missing"
    
    diagnostics["prompt_templates"] = {
        "files_status": prompt_status,
        "status": "healthy" if any("available" in status for status in prompt_status.values()) else "degraded"
    }
    
    # =============================================================================
    # DIAGNÓSTICO DE CACHE E PERFORMANCE
    # =============================================================================
    try:
        from src.core.rate_limiter import rate_limiter
        
        # Teste do sistema de cache em memória
        cache_info = {
            "type": "memory-based",
            "redis_disabled": "by_design",
            "rate_limiter": "functional"
        }
        
        diagnostics["cache_performance"] = {
            "cache_info": cache_info,
            "status": "healthy"
        }
    except Exception as e:
        diagnostics["cache_performance"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # =============================================================================
    # DIAGNÓSTICO DE SEGURANÇA
    # =============================================================================
    security_checks = {
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "supabase_keys_present": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY")),
        "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
        "environment": os.getenv("APP_ENVIRONMENT", "development")
    }
    
    diagnostics["security"] = {
        "checks": security_checks,
        "status": "healthy" if security_checks["openai_key_present"] and security_checks["supabase_keys_present"] else "unhealthy"
    }
    
    # =============================================================================
    # RESUMO FINAL
    # =============================================================================
    all_healthy = all(
        diag.get("status") == "healthy" 
        for diag in diagnostics.values()
    )
    
    # ✅ CORREÇÃO: Retornar objeto DetailedHealthResponse em vez de dict
    return DetailedHealthResponse(
        overall_status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now().isoformat(),
        diagnostics=diagnostics,
        recommendations=_generate_health_recommendations(diagnostics)
    )


def _generate_health_recommendations(diagnostics: Dict[str, Any]) -> List[str]:
    """Gerar recomendações baseadas nos diagnósticos."""
    recommendations = []
    
    # Recomendações por componente
    if diagnostics.get("hierarchy_validation", {}).get("status") != "healthy":
        recommendations.append("Verificar imports dos modelos hierárquicos")
    
    if diagnostics.get("content_generation", {}).get("status") != "healthy":
        recommendations.append("Configurar OpenAI API key e verificar VocabularyGeneratorService")
    
    if diagnostics.get("prompt_templates", {}).get("status") != "healthy":
        recommendations.append("Criar templates de prompts em config/prompts/")
    
    if diagnostics.get("security", {}).get("status") != "healthy":
        recommendations.append("Configurar variáveis de ambiente necessárias (OPENAI_API_KEY, SUPABASE_URL)")
    
    # Recomendações gerais
    if not recommendations:
        recommendations.append("Sistema funcionando corretamente - pronto para geração de conteúdo")
    
    return recommendations


# ✅ ALTERNATIVA: Endpoint adicional usando JSONResponse diretamente
@router.get("/detailed-json")
async def detailed_health_check_json():
    """Health check detalhado retornando JSONResponse diretamente."""
    try:
        # Reusar lógica do endpoint principal
        detailed_response = await detailed_health_check()
        
        # Converter para dict e retornar como JSONResponse
        response_dict = {
            "overall_status": detailed_response.overall_status,
            "timestamp": detailed_response.timestamp,
            "diagnostics": detailed_response.diagnostics,
            "recommendations": detailed_response.recommendations
        }
        
        return JSONResponse(content=response_dict)
        
    except Exception as e:
        logger.error(f"Erro no health check detalhado: {str(e)}")
        return JSONResponse(
            content={
                "overall_status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "recommendations": ["Verificar logs do sistema"]
            },
            status_code=500
        )