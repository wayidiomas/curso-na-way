"""Aplicação principal FastAPI."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from src.api import auth, apostilas, vocabs, content, images, pdf, health
from src.core.database import init_database
from config.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""
    # Startup
    setup_logging()
    await init_database()
    print("🚀 Curso Na Way iniciado!")
    
    yield
    
    # Shutdown
    print("👋 Curso Na Way finalizado!")


app = FastAPI(
    title="Curso Na Way API",
    description="Sistema de Geração de Apostilas de Inglês com IA",
    version="1.0.0",
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

# Routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(apostilas.router, prefix="/apostilas", tags=["apostilas"])
app.include_router(vocabs.router, prefix="/vocabs", tags=["vocabs"])
app.include_router(content.router, prefix="/content", tags=["content"])
app.include_router(images.router, prefix="/images", tags=["images"])
app.include_router(pdf.router, prefix="/pdf", tags=["pdf"])


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
