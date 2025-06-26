"""Modelos Pydantic do sistema."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi import UploadFile

from .enums import CEFRLevel, EnglishVariant, ContentType, ApostilaStatus


class VocabularyItem(BaseModel):
    """Item de vocabulário."""
    word: str = Field(..., description="Palavra em inglês")
    definition: str = Field(..., description="Definição em português")
    example: str = Field(..., description="Exemplo de uso em inglês")
    level: CEFRLevel = Field(..., description="Nível CEFR")
    context_image: Optional[str] = Field(None, description="ID da imagem relacionada")


class ContentSection(BaseModel):
    """Seção de conteúdo da apostila."""
    type: ContentType = Field(..., description="Tipo da seção")
    title: str = Field(..., description="Título da seção")
    content: str = Field(..., description="Conteúdo da seção")
    vocabulary_used: List[str] = Field(default=[], description="Vocabulário utilizado")
    created_at: datetime = Field(default_factory=datetime.now)


class ApostilaRequest(BaseModel):
    """Request para criação de apostila."""
    input_text: str = Field(..., description="Texto de entrada com contexto")
    level: CEFRLevel = Field(..., description="Nível CEFR")
    variant: EnglishVariant = Field(..., description="Variante do inglês")
    professor_id: str = Field(..., description="ID do professor")


class ApostilaResponse(BaseModel):
    """Response com dados da apostila."""
    id: str
    title: str
    status: ApostilaStatus
    level: CEFRLevel
    variant: EnglishVariant
    professor_id: str
    vocabulary: List[VocabularyItem] = []
    sections: List[ContentSection] = []
    images: List[str] = []
    pdf_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ImageAnalysisResult(BaseModel):
    """Resultado da análise de imagem."""
    image_id: str
    description: str
    objects_detected: List[str]
    text_detected: Optional[str] = None
    context_relevance: float = Field(..., ge=0.0, le=1.0)


class GenerationProgress(BaseModel):
    """Progresso da geração de conteúdo."""
    step: str
    progress: int = Field(..., ge=0, le=100)
    message: str
    details: Optional[Dict[str, Any]] = None
