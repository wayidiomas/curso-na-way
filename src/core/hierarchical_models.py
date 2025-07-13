# src/core/hierarchical_models.py
"""Modelos para a estrutura hierárquica Course → Book → Unit do IVO V2."""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

from .enums import (
    CEFRLevel, LanguageVariant, UnitType, 
    TipStrategy, GrammarStrategy, AssessmentType, UnitStatus
)


# =============================================================================
# COURSE MODELS
# =============================================================================

class CourseCreateRequest(BaseModel):
    """Request para criação de curso."""
    name: str = Field(..., min_length=3, max_length=200, description="Nome do curso")
    description: Optional[str] = Field(None, max_length=1000, description="Descrição do curso")
    target_levels: List[CEFRLevel] = Field(..., min_items=1, description="Níveis CEFR cobertos")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    methodology: List[str] = Field(
        default=["direct_method", "tips_strategies"], 
        description="Metodologias aplicadas"
    )
    
    @validator('target_levels')
    def validate_target_levels(cls, v):
        if not v:
            raise ValueError("Pelo menos um nível CEFR deve ser especificado")
        # Verificar ordem lógica dos níveis
        level_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        sorted_levels = sorted(v, key=lambda x: level_order.index(x.value))
        return sorted_levels
    
    class Config:
        schema_extra = {
            "example": {
                "name": "English for Business Professionals",
                "description": "Complete course for business English from A2 to B2",
                "target_levels": ["A2", "B1", "B2"],
                "language_variant": "american_english",
                "methodology": ["direct_method", "tips_strategies", "business_focus"]
            }
        }


class Course(BaseModel):
    """Modelo completo de curso."""
    id: str
    name: str
    description: Optional[str] = None
    target_levels: List[CEFRLevel]
    language_variant: LanguageVariant
    methodology: List[str] = []
    total_books: int = 0
    total_units: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# BOOK MODELS
# =============================================================================

class BookCreateRequest(BaseModel):
    """Request para criação de book."""
    name: str = Field(..., min_length=3, max_length=200, description="Nome do book")
    description: Optional[str] = Field(None, max_length=1000, description="Descrição do book")
    target_level: CEFRLevel = Field(..., description="Nível CEFR específico do book")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Business Fundamentals - A2",
                "description": "Basic business vocabulary and expressions",
                "target_level": "A2"
            }
        }


class Book(BaseModel):
    """Modelo completo de book."""
    id: str
    course_id: str
    name: str
    description: Optional[str] = None
    target_level: CEFRLevel
    sequence_order: int
    unit_count: int = 0
    vocabulary_coverage: List[str] = []  # palavras já ensinadas
    strategies_used: List[str] = []      # estratégias já usadas
    assessments_used: List[str] = []     # tipos de atividades já usadas
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# UNIT MODELS COM HIERARQUIA
# =============================================================================

class HierarchicalUnitRequest(BaseModel):
    """Request para criação de unidade com hierarquia obrigatória."""
    # Hierarquia obrigatória
    course_id: str = Field(..., description="ID do curso")
    book_id: str = Field(..., description="ID do book")
    
    # Dados da unidade
    title: Optional[str] = Field(None, description="Título da unidade")
    context: Optional[str] = Field(None, description="Contexto da unidade")
    cefr_level: CEFRLevel = Field(..., description="Nível CEFR")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    unit_type: UnitType = Field(..., description="Tipo de unidade")
    
    @validator('book_id')
    def validate_book_belongs_to_course(cls, v, values):
        # Esta validação seria feita no service layer com acesso ao banco
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "course_id": "course_english_beginners",
                "book_id": "book_foundation_a1",
                "title": "Hotel Reservations",
                "context": "Making hotel reservations and check-in procedures",
                "cefr_level": "A2",
                "language_variant": "american_english",
                "unit_type": "lexical_unit"
            }
        }


class UnitWithHierarchy(BaseModel):
    """Modelo de unidade com informações hierárquicas."""
    # Identificação e hierarquia
    id: str
    course_id: str
    book_id: str
    sequence_order: int
    
    # Dados básicos
    title: Optional[str] = None
    main_aim: Optional[str] = None
    subsidiary_aims: List[str] = []
    context: Optional[str] = None
    cefr_level: CEFRLevel
    language_variant: LanguageVariant
    unit_type: UnitType
    
    # Conteúdo (estruturas complexas como JSONB)
    images: List[Dict[str, Any]] = []
    vocabulary: Optional[Dict[str, Any]] = None
    sentences: Optional[Dict[str, Any]] = None
    tips: Optional[Dict[str, Any]] = None
    grammar: Optional[Dict[str, Any]] = None
    qa: Optional[Dict[str, Any]] = None
    assessments: Optional[Dict[str, Any]] = None
    
    # Tracking de progressão
    strategies_used: List[str] = []
    assessments_used: List[str] = []
    vocabulary_taught: List[str] = []
    
    # Status e qualidade
    status: UnitStatus = UnitStatus.CREATING
    quality_score: Optional[float] = None
    checklist_completed: List[str] = []
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# RAG CONTEXT MODELS
# =============================================================================

class RAGVocabularyContext(BaseModel):
    """Contexto RAG para geração de vocabulário."""
    precedent_vocabulary: List[str] = Field(
        default=[], 
        description="Palavras já ensinadas em unidades anteriores"
    )
    vocabulary_gaps: List[str] = Field(
        default=[], 
        description="Oportunidades de vocabulário novo identificadas"
    )
    reinforcement_candidates: List[str] = Field(
        default=[], 
        description="Palavras candidatas para reforço"
    )
    context_suggestions: List[str] = Field(
        default=[], 
        description="Temas contextuais de unidades anteriores"
    )
    progression_level: str = Field(
        default="high_frequency_basic", 
        description="Nível de progressão pedagógica"
    )


class RAGStrategyContext(BaseModel):
    """Contexto RAG para seleção de estratégias."""
    used_strategies: List[str] = Field(
        default=[], 
        description="Estratégias já usadas no book"
    )
    recommended_strategy: str = Field(
        ..., 
        description="Estratégia recomendada para complementar"
    )
    strategy_rationale: str = Field(
        ..., 
        description="Justificativa da seleção"
    )


class RAGAssessmentContext(BaseModel):
    """Contexto RAG para balanceamento de atividades."""
    used_assessments: List[Dict[str, Any]] = Field(
        default=[], 
        description="Atividades já usadas anteriormente"
    )
    recommended_assessments: List[AssessmentType] = Field(
        default=[], 
        description="Atividades recomendadas"
    )
    balance_rationale: Dict[str, Any] = Field(
        default={}, 
        description="Análise de balanceamento"
    )


# =============================================================================
# HIERARCHY NAVIGATION MODELS
# =============================================================================

class CourseHierarchyView(BaseModel):
    """Visão hierárquica completa de um curso."""
    course: Course
    books: List[Dict[str, Any]] = []  # Book + suas units
    
    @validator('books', pre=True, always=True)
    def build_books_with_units(cls, v, values):
        # Esta lógica seria implementada no service layer
        return v or []


class UnitHierarchyInfo(BaseModel):
    """Informações hierárquicas de uma unidade."""
    unit_id: str
    unit_title: Optional[str]
    unit_sequence: int
    unit_status: UnitStatus
    
    book_id: str
    book_name: str
    book_sequence: int
    book_target_level: CEFRLevel
    
    course_id: str
    course_name: str
    course_language_variant: LanguageVariant
    
    created_at: datetime


class ProgressionAnalysis(BaseModel):
    """Análise de progressão pedagógica."""
    course_id: str
    book_id: str
    current_sequence: int
    
    vocabulary_progression: Dict[str, Any] = {}
    strategy_distribution: Dict[str, int] = {}
    assessment_balance: Dict[str, int] = {}
    
    recommendations: List[str] = []
    quality_metrics: Dict[str, float] = {}


# =============================================================================
# UTILITY MODELS
# =============================================================================

class HierarchyValidationResult(BaseModel):
    """Resultado da validação hierárquica."""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []


class BulkUnitCreateRequest(BaseModel):
    """Request para criação em lote de unidades."""
    book_id: str
    units: List[HierarchicalUnitRequest]
    
    @validator('units')
    def validate_units_consistency(cls, v, values):
        book_id = values.get('book_id')
        if not book_id:
            return v
            
        # Verificar que todas as units pertencem ao mesmo book
        for unit in v:
            if unit.book_id != book_id:
                raise ValueError(f"Unit book_id {unit.book_id} doesn't match request book_id {book_id}")
        
        return v


class CourseProgressSummary(BaseModel):
    """Resumo de progresso do curso."""
    course_id: str
    course_name: str
    total_books: int
    total_units: int
    completed_units: int
    average_quality_score: Optional[float] = None
    
    books_progress: List[Dict[str, Any]] = []
    latest_activity: Optional[datetime] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calcula porcentagem de conclusão."""
        if self.total_units == 0:
            return 0.0
        return (self.completed_units / self.total_units) * 100