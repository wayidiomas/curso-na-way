# src/main.py - ATUALIZADO PARA HIERARQUIA
"""Aplicação principal FastAPI com endpoints hierárquicos."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Importações existentes
from src.api import health
from src.core.database import init_database
from config.logging import setup_logging

# NOVOS IMPORTS - Endpoints hierárquicos
from src.api.v2 import courses, books, units

# Imports existentes (se houver)
try:
    from src.api import auth, apostilas, vocabs, content, images, pdf
    legacy_endpoints_available = True
except ImportError:
    legacy_endpoints_available = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    # Startup
    setup_logging()
    await init_database()
    print("🚀 Curso Na Way iniciado com hierarquia!")
    
    yield
    
    # Shutdown
    print("👋 Curso Na Way finalizado!")


app = FastAPI(
    title="Curso Na Way API",
    description="Sistema de Geração de Apostilas de Inglês com IA - Hierárquico",
    version="2.0.0",  # Incrementar versão para hierarquia
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure adequadamente em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# ENDPOINT RAIZ COM INFORMAÇÕES DA API
# =============================================================================

@app.get("/")
async def root():
    """Informações gerais da API."""
    return {
        "name": "Curso Na Way API",
        "version": "2.0.0",
        "description": "Sistema hierárquico para geração de apostilas de inglês",
        "architecture": "Course → Book → Unit",
        "features": [
            "Hierarquia obrigatória Course/Book/Unit",
            "RAG contextual para progressão pedagógica",
            "Análise automática de vocabulário precedente",
            "Balanceamento inteligente de estratégias",
            "Tracking de qualidade pedagógica"
        ],
        "endpoints": {
            "v2": {
                "courses": "/api/v2/courses",
                "books": "/api/v2/courses/{course_id}/books", 
                "units": "/api/v2/books/{book_id}/units",
                "health": "/health"
            },
            "v1_legacy": "/auth, /apostilas, /vocabs, /content, /images, /pdf" if legacy_endpoints_available else "Not available"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "hierarchy_flow": {
            "1": "Criar Course com níveis CEFR",
            "2": "Criar Books por nível no Course",
            "3": "Criar Units sequenciais no Book",
            "4": "Gerar conteúdo com RAG contextual"
        }
    }


@app.get("/api/v2")
async def api_v2_info():
    """Informações específicas da API V2."""
    return {
        "version": "2.0",
        "hierarchy": "Course → Book → Unit",
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
                "GET /api/v2/courses": "Listar cursos",
                "GET /api/v2/courses/{id}": "Detalhes do curso",
                "GET /api/v2/courses/{id}/hierarchy": "Hierarquia completa",
                "GET /api/v2/courses/{id}/progress": "Análise de progresso"
            },
            "books": {
                "POST /api/v2/courses/{course_id}/books": "Criar book no curso",
                "GET /api/v2/courses/{course_id}/books": "Listar books do curso",
                "GET /api/v2/books/{id}": "Detalhes do book",
                "GET /api/v2/books/{id}/progression": "Análise de progressão"
            },
            "units": {
                "POST /api/v2/books/{book_id}/units": "Criar unit no book",
                "GET /api/v2/books/{book_id}/units": "Listar units do book",
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
            "step_5": "Próximos prompts: vocabulário, sentences, strategies, assessments"
        }
    }


# =============================================================================
# TRATAMENTO DE ERROS GLOBAL
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handler para 404."""
    return {
        "success": False,
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "Recurso não encontrado",
        "details": {
            "path": str(request.url),
            "method": request.method
        },
        "suggestions": [
            "Verifique se o ID está correto",
            "Confirme que o recurso existe na hierarquia",
            "Consulte /docs para endpoints disponíveis"
        ]
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handler para erros internos."""
    return {
        "success": False,
        "error_code": "INTERNAL_SERVER_ERROR", 
        "message": "Erro interno do servidor",
        "details": {
            "path": str(request.url),
            "method": request.method
        },
        "suggestions": [
            "Tente novamente em alguns instantes",
            "Verifique se todas as dependências estão funcionando",
            "Consulte os logs para mais detalhes"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )