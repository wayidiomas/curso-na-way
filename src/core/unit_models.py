"""Modelos específicos para o sistema IVO V2."""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from fastapi import UploadFile

from .enums import (
    CEFRLevel, LanguageVariant, UnitType, AimType, 
    TipStrategy, GrammarStrategy, AssessmentType, 
    UnitStatus, ContentType
)


# =============================================================================
# INPUT MODELS (Form Data)
# =============================================================================

class UnitCreateRequest(BaseModel):
    """Request para criação de unidade via form data."""
    context: Optional[str] = Field(None, description="Contexto opcional da unidade")
    cefr_level: CEFRLevel = Field(..., description="Nível CEFR")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    unit_type: UnitType = Field(..., description="Tipo de unidade (lexical ou grammar)")
    
    class Config:
        schema_extra = {
            "example": {
                "context": "Hotel reservation and check-in procedures",
                "cefr_level": "B1",
                "language_variant": "american_english",
                "unit_type": "lexical_unit"
            }
        }


# =============================================================================
# VOCABULARY MODELS
# =============================================================================

class VocabularyItem(BaseModel):
    """Item de vocabulário com fonema."""
    word: str = Field(..., description="Palavra no idioma alvo")
    phoneme: str = Field(..., description="Transcrição fonética IPA")
    definition: str = Field(..., description="Definição em português")
    example: str = Field(..., description="Exemplo de uso")
    word_class: str = Field(..., description="Classe gramatical (noun, verb, etc.)")
    frequency_level: str = Field(..., description="Nível de frequência (high, medium, low)")
    
    class Config:
        schema_extra = {
            "example": {
                "word": "reservation",
                "phoneme": "/ˌrez.ɚˈveɪ.ʃən/",
                "definition": "reserva, ato de reservar",
                "example": "I made a reservation for dinner at 7 PM.",
                "word_class": "noun",
                "frequency_level": "high"
            }
        }


class VocabularySection(BaseModel):
    """Seção completa de vocabulário."""
    items: List[VocabularyItem] = Field(..., description="Lista de itens de vocabulário")
    total_count: int = Field(..., description="Total de palavras")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevância contextual")
    generated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# SENTENCES MODELS
# =============================================================================

class Sentence(BaseModel):
    """Sentence conectada ao vocabulário."""
    text: str = Field(..., description="Texto da sentence")
    vocabulary_used: List[str] = Field(..., description="Palavras do vocabulário utilizadas")
    context_situation: str = Field(..., description="Situação contextual")
    complexity_level: str = Field(..., description="Nível de complexidade")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "I need to make a reservation for two people tonight.",
                "vocabulary_used": ["reservation"],
                "context_situation": "restaurant_booking",
                "complexity_level": "intermediate"
            }
        }


class SentencesSection(BaseModel):
    """Seção de sentences."""
    sentences: List[Sentence] = Field(..., description="Lista de sentences")
    vocabulary_coverage: float = Field(..., ge=0.0, le=1.0, description="Cobertura do vocabulário")
    generated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# CONTENT MODELS (Tips & Grammar)
# =============================================================================

class TipsContent(BaseModel):
    """Conteúdo de TIPS para unidades lexicais."""
    strategy: TipStrategy = Field(..., description="Estratégia TIPS aplicada")
    title: str = Field(..., description="Título da estratégia")
    explanation: str = Field(..., description="Explicação da estratégia")
    examples: List[str] = Field(..., description="Exemplos práticos")
    practice_suggestions: List[str] = Field(..., description="Sugestões de prática")
    memory_techniques: List[str] = Field(..., description="Técnicas de memorização")


class GrammarContent(BaseModel):
    """Conteúdo de GRAMMAR para unidades gramaticais."""
    strategy: GrammarStrategy = Field(..., description="Estratégia GRAMMAR aplicada")
    grammar_point: str = Field(..., description="Ponto gramatical principal")
    systematic_explanation: str = Field(..., description="Explicação sistemática")
    usage_rules: List[str] = Field(..., description="Regras de uso")
    examples: List[str] = Field(..., description="Exemplos contextualizados")
    l1_interference_notes: List[str] = Field(..., description="Notas sobre interferência L1")
    common_mistakes: List[Dict[str, str]] = Field(..., description="Erros comuns e correções")


class QASection(BaseModel):
    """Seção de perguntas e respostas."""
    questions: List[str] = Field(..., description="Perguntas para estudantes")
    answers: List[str] = Field(..., description="Respostas completas (para professores)")
    pedagogical_notes: List[str] = Field(..., description="Notas pedagógicas")
    difficulty_progression: str = Field(..., description="Progressão de dificuldade")


# =============================================================================
# ASSESSMENT MODELS
# =============================================================================

class AssessmentActivity(BaseModel):
    """Atividade de avaliação."""
    type: AssessmentType = Field(..., description="Tipo de atividade")
    title: str = Field(..., description="Título da atividade")
    instructions: str = Field(..., description="Instruções da atividade")
    content: Dict[str, Any] = Field(..., description="Conteúdo específico da atividade")
    answer_key: Dict[str, Any] = Field(..., description="Gabarito da atividade")
    estimated_time: int = Field(..., description="Tempo estimado em minutos")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "gap_fill",
                "title": "Complete the sentences",
                "instructions": "Fill in the blanks with the appropriate words from the vocabulary.",
                "content": {
                    "sentences": [
                        "I need to make a _______ for dinner.",
                        "The hotel has excellent _______."
                    ],
                    "word_bank": ["reservation", "service"]
                },
                "answer_key": {
                    "1": "reservation",
                    "2": "service"
                },
                "estimated_time": 10
            }
        }


class AssessmentSection(BaseModel):
    """Seção completa de avaliação."""
    activities: List[AssessmentActivity] = Field(..., description="Lista de atividades (2 selecionadas)")
    selection_rationale: str = Field(..., description="Justificativa da seleção")
    total_estimated_time: int = Field(..., description="Tempo total estimado")
    skills_assessed: List[str] = Field(..., description="Habilidades avaliadas")


# =============================================================================
# UNIT COMPLETE MODEL
# =============================================================================

class ImageInfo(BaseModel):
    """Informações da imagem processada."""
    filename: str = Field(..., description="Nome do arquivo")
    description: str = Field(..., description="Descrição da imagem pela IA")
    objects_detected: List[str] = Field(..., description="Objetos detectados")
    text_detected: Optional[str] = Field(None, description="Texto detectado na imagem")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Score de relevância")


class UnitResponse(BaseModel):
    """Response completa da unidade."""
    id: str = Field(..., description="ID único da unidade")
    title: str = Field(..., description="Título da unidade")
    main_aim: str = Field(..., description="Objetivo principal")
    subsidiary_aims: List[str] = Field(..., description="Objetivos subsidiários")
    
    # Metadata
    unit_type: UnitType = Field(..., description="Tipo de unidade")
    cefr_level: CEFRLevel = Field(..., description="Nível CEFR")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    status: UnitStatus = Field(..., description="Status atual")
    
    # Content Sections
    images: List[ImageInfo] = Field(default=[], description="Informações das imagens")
    vocabulary: Optional[VocabularySection] = Field(None, description="Seção de vocabulário")
    sentences: Optional[SentencesSection] = Field(None, description="Seção de sentences")
    tips: Optional[TipsContent] = Field(None, description="Conteúdo TIPS (se lexical)")
    grammar: Optional[GrammarContent] = Field(None, description="Conteúdo GRAMMAR (se grammar)")
    qa: Optional[QASection] = Field(None, description="Seção Q&A")
    assessments: Optional[AssessmentSection] = Field(None, description="Seção de avaliação")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Quality Control
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Score de qualidade")
    checklist_completed: List[str] = Field(default=[], description="Checklist de qualidade completado")


# =============================================================================
# PROGRESS & STATUS MODELS
# =============================================================================

class GenerationProgress(BaseModel):
    """Progresso da geração de conteúdo."""
    unit_id: str = Field(..., description="ID da unidade")
    current_step: str = Field(..., description="Etapa atual")
    progress_percentage: int = Field(..., ge=0, le=100, description="Porcentagem de progresso")
    message: str = Field(..., description="Mensagem de status")
    estimated_remaining_time: Optional[int] = Field(None, description="Tempo estimado restante (segundos)")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais")


class ErrorResponse(BaseModel):
    """Response de erro padronizado."""
    success: bool = Field(False, description="Sempre False para erros")
    error_code: str = Field(..., description="Código do erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes do erro")
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseModel):
    """Response de sucesso padronizado."""
    success: bool = Field(True, description="Sempre True para sucesso")
    data: Dict[str, Any] = Field(..., description="Dados da resposta")
    message: Optional[str] = Field(None, description="Mensagem opcional")
    timestamp: datetime = Field(default_factory=datetime.now)