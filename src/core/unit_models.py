# src/core/unit_models.py - ATUALIZAÇÃO PARA HIERARQUIA
"""Modelos específicos para o sistema IVO V2 com hierarquia Course → Book → Unit."""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from fastapi import UploadFile

from .enums import (
    CEFRLevel, LanguageVariant, UnitType, AimType, 
    TipStrategy, GrammarStrategy, AssessmentType, 
    UnitStatus, ContentType
)


# =============================================================================
# INPUT MODELS (Form Data) - ATUALIZADOS COM HIERARQUIA
# =============================================================================

class UnitCreateRequest(BaseModel):
    """Request para criação de unidade via form data - REQUER HIERARQUIA."""
    # HIERARQUIA OBRIGATÓRIA (novos campos)
    course_id: str = Field(..., description="ID do curso (obrigatório)")
    book_id: str = Field(..., description="ID do book (obrigatório)")
    
    # Dados da unidade (existentes)
    context: Optional[str] = Field(None, description="Contexto opcional da unidade")
    cefr_level: CEFRLevel = Field(..., description="Nível CEFR")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    unit_type: UnitType = Field(..., description="Tipo de unidade (lexical ou grammar)")
    
    @validator('book_id')
    def validate_book_not_empty(cls, v):
        if not v or v.strip() == "":
            raise ValueError("book_id é obrigatório")
        return v
    
    @validator('course_id')
    def validate_course_not_empty(cls, v):
        if not v or v.strip() == "":
            raise ValueError("course_id é obrigatório")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "course_id": "course_english_beginners",
                "book_id": "book_foundation_a1",
                "context": "Hotel reservation and check-in procedures",
                "cefr_level": "B1",
                "language_variant": "american_english",
                "unit_type": "lexical_unit"
            }
        }


# =============================================================================
# VOCABULARY MODELS - MANTÉM COMPATIBILIDADE
# =============================================================================

class VocabularyItem(BaseModel):
    """Item de vocabulário com fonema."""
    word: str = Field(..., description="Palavra no idioma alvo")
    phoneme: str = Field(..., description="Transcrição fonética IPA")
    definition: str = Field(..., description="Definição em português")
    example: str = Field(..., description="Exemplo de uso")
    word_class: str = Field(..., description="Classe gramatical (noun, verb, etc.)")
    frequency_level: str = Field(..., description="Nível de frequência (high, medium, low)")
    
    # NOVOS CAMPOS PARA PROGRESSÃO
    context_relevance: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevância contextual")
    is_reinforcement: Optional[bool] = Field(False, description="É palavra de reforço?")
    first_introduced_unit: Optional[str] = Field(None, description="Unidade onde foi introduzida")
    
    class Config:
        schema_extra = {
            "example": {
                "word": "reservation",
                "phoneme": "/ˌrez.ɚˈveɪ.ʃən/",
                "definition": "reserva, ato de reservar",
                "example": "I made a reservation for dinner at 7 PM.",
                "word_class": "noun",
                "frequency_level": "high",
                "context_relevance": 0.95,
                "is_reinforcement": False
            }
        }


class VocabularySection(BaseModel):
    """Seção completa de vocabulário - ATUALIZADA COM RAG."""
    items: List[VocabularyItem] = Field(..., description="Lista de itens de vocabulário")
    total_count: int = Field(..., description="Total de palavras")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevância contextual")
    
    # NOVOS CAMPOS PARA RAG
    new_words_count: int = Field(0, description="Palavras totalmente novas")
    reinforcement_words_count: int = Field(0, description="Palavras de reforço")
    rag_context_used: Dict[str, Any] = Field(default={}, description="Contexto RAG utilizado")
    progression_level: str = Field(default="intermediate", description="Nível de progressão")
    
    generated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('total_count')
    def validate_total_count(cls, v, values):
        items = values.get('items', [])
        if v != len(items):
            return len(items)
        return v


# =============================================================================
# CONTENT MODELS (Tips & Grammar) - ATUALIZADOS
# =============================================================================

class TipsContent(BaseModel):
    """Conteúdo de TIPS para unidades lexicais."""
    strategy: TipStrategy = Field(..., description="Estratégia TIPS aplicada")
    title: str = Field(..., description="Título da estratégia")
    explanation: str = Field(..., description="Explicação da estratégia")
    examples: List[str] = Field(..., description="Exemplos práticos")
    practice_suggestions: List[str] = Field(..., description="Sugestões de prática")
    memory_techniques: List[str] = Field(..., description="Técnicas de memorização")
    
    # NOVOS CAMPOS PARA RAG
    vocabulary_coverage: List[str] = Field(default=[], description="Vocabulário coberto pela estratégia")
    complementary_strategies: List[str] = Field(default=[], description="Estratégias complementares sugeridas")
    selection_rationale: str = Field(default="", description="Por que esta estratégia foi selecionada")


class GrammarContent(BaseModel):
    """Conteúdo de GRAMMAR para unidades gramaticais."""
    strategy: GrammarStrategy = Field(..., description="Estratégia GRAMMAR aplicada")
    grammar_point: str = Field(..., description="Ponto gramatical principal")
    systematic_explanation: str = Field(..., description="Explicação sistemática")
    usage_rules: List[str] = Field(..., description="Regras de uso")
    examples: List[str] = Field(..., description="Exemplos contextualizados")
    l1_interference_notes: List[str] = Field(..., description="Notas sobre interferência L1")
    common_mistakes: List[Dict[str, str]] = Field(..., description="Erros comuns e correções")
    
    # NOVOS CAMPOS PARA RAG
    vocabulary_integration: List[str] = Field(default=[], description="Como integra com o vocabulário")
    previous_grammar_connections: List[str] = Field(default=[], description="Conexões com gramática anterior")
    selection_rationale: str = Field(default="", description="Por que esta estratégia foi selecionada")


# =============================================================================
# ASSESSMENT MODELS - ATUALIZADOS COM BALANCEAMENTO
# =============================================================================

class AssessmentActivity(BaseModel):
    """Atividade de avaliação."""
    type: AssessmentType = Field(..., description="Tipo de atividade")
    title: str = Field(..., description="Título da atividade")
    instructions: str = Field(..., description="Instruções da atividade")
    content: Dict[str, Any] = Field(..., description="Conteúdo específico da atividade")
    answer_key: Dict[str, Any] = Field(..., description="Gabarito da atividade")
    estimated_time: int = Field(..., description="Tempo estimado em minutos")
    
    # NOVOS CAMPOS PARA BALANCEAMENTO
    difficulty_level: str = Field(default="intermediate", description="Nível de dificuldade")
    skills_assessed: List[str] = Field(default=[], description="Habilidades avaliadas")
    vocabulary_focus: List[str] = Field(default=[], description="Vocabulário focado")
    
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
                "estimated_time": 10,
                "difficulty_level": "intermediate",
                "skills_assessed": ["vocabulary_recognition", "context_application"],
                "vocabulary_focus": ["reservation", "service"]
            }
        }


class AssessmentSection(BaseModel):
    """Seção completa de avaliação - ATUALIZADA COM BALANCEAMENTO."""
    activities: List[AssessmentActivity] = Field(..., description="Lista de atividades (2 selecionadas)")
    selection_rationale: str = Field(..., description="Justificativa da seleção")
    total_estimated_time: int = Field(..., description="Tempo total estimado")
    skills_assessed: List[str] = Field(..., description="Habilidades avaliadas")
    
    # NOVOS CAMPOS PARA BALANCEAMENTO
    balance_analysis: Dict[str, Any] = Field(default={}, description="Análise de balanceamento")
    underused_activities: List[str] = Field(default=[], description="Atividades subutilizadas")
    complementary_pair: bool = Field(True, description="São atividades complementares?")


# =============================================================================
# UNIT COMPLETE MODEL - ATUALIZADO COM HIERARQUIA
# =============================================================================

class UnitResponse(BaseModel):
    """Response completa da unidade - ATUALIZADA COM HIERARQUIA."""
    # HIERARQUIA (novos campos obrigatórios)
    id: str = Field(..., description="ID único da unidade")
    course_id: str = Field(..., description="ID do curso")
    book_id: str = Field(..., description="ID do book")
    sequence_order: int = Field(..., description="Ordem sequencial no book")
    
    # Informações básicas
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
    
    # PROGRESSÃO PEDAGÓGICA (novos campos)
    strategies_used: List[str] = Field(default=[], description="Estratégias já usadas")
    assessments_used: List[str] = Field(default=[], description="Tipos de atividades já usadas")
    vocabulary_taught: List[str] = Field(default=[], description="Vocabulário ensinado nesta unidade")
    
    # CONTEXTO HIERÁRQUICO (informações derivadas)
    hierarchy_info: Optional[Dict[str, Any]] = Field(None, description="Informações da hierarquia")
    progression_analysis: Optional[Dict[str, Any]] = Field(None, description="Análise de progressão")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Quality Control
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Score de qualidade")
    checklist_completed: List[str] = Field(default=[], description="Checklist de qualidade completado")

    class Config:
        schema_extra = {
            "example": {
                "id": "unit_hotel_reservations_001",
                "course_id": "course_english_beginners",
                "book_id": "book_foundation_a1",
                "sequence_order": 5,
                "title": "Hotel Reservations",
                "main_aim": "Students will be able to make hotel reservations using appropriate vocabulary and phrases",
                "subsidiary_aims": [
                    "Use reservation-related vocabulary accurately",
                    "Apply polite language in formal situations",
                    "Understand hotel policies and procedures"
                ],
                "unit_type": "lexical_unit",
                "cefr_level": "A2",
                "language_variant": "american_english",
                "status": "completed",
                "strategies_used": ["collocations", "chunks"],
                "assessments_used": ["gap_fill", "matching"],
                "vocabulary_taught": ["reservation", "check-in", "availability", "suite"],
                "quality_score": 0.92
            }
        }


# =============================================================================
# ADDITIONAL MODELS FOR SENTENCES AND QA
# =============================================================================

class Sentence(BaseModel):
    """Sentence conectada ao vocabulário."""
    text: str = Field(..., description="Texto da sentence")
    vocabulary_used: List[str] = Field(..., description="Palavras do vocabulário utilizadas")
    context_situation: str = Field(..., description="Situação contextual")
    complexity_level: str = Field(..., description="Nível de complexidade")
    
    # NOVOS CAMPOS PARA PROGRESSÃO
    reinforces_previous: List[str] = Field(default=[], description="Vocabulário anterior reforçado")
    introduces_new: List[str] = Field(default=[], description="Novo vocabulário introduzido")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "I need to make a reservation for two people tonight.",
                "vocabulary_used": ["reservation"],
                "context_situation": "restaurant_booking",
                "complexity_level": "intermediate",
                "reinforces_previous": [],
                "introduces_new": ["reservation"]
            }
        }


class SentencesSection(BaseModel):
    """Seção de sentences."""
    sentences: List[Sentence] = Field(..., description="Lista de sentences")
    vocabulary_coverage: float = Field(..., ge=0.0, le=1.0, description="Cobertura do vocabulário")
    
    # NOVOS CAMPOS PARA RAG
    contextual_coherence: float = Field(default=0.8, description="Coerência contextual")
    progression_appropriateness: float = Field(default=0.8, description="Adequação à progressão")
    
    generated_at: datetime = Field(default_factory=datetime.now)


class QASection(BaseModel):
    """Seção de perguntas e respostas."""
    questions: List[str] = Field(..., description="Perguntas para estudantes")
    answers: List[str] = Field(..., description="Respostas completas (para professores)")
    pedagogical_notes: List[str] = Field(..., description="Notas pedagógicas")
    difficulty_progression: str = Field(..., description="Progressão de dificuldade")
    
    # NOVOS CAMPOS PARA CONTEXTO
    vocabulary_integration: List[str] = Field(default=[], description="Vocabulário integrado")
    cognitive_levels: List[str] = Field(default=[], description="Níveis cognitivos das perguntas")


class ImageInfo(BaseModel):
    """Informações da imagem processada."""
    filename: str = Field(..., description="Nome do arquivo")
    description: str = Field(..., description="Descrição da imagem pela IA")
    objects_detected: List[str] = Field(..., description="Objetos detectados")
    text_detected: Optional[str] = Field(None, description="Texto detectado na imagem")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Score de relevância")
    
    # NOVOS CAMPOS PARA PROGRESSÃO
    vocabulary_suggestions: List[str] = Field(default=[], description="Vocabulário sugerido pela imagem")
    context_themes: List[str] = Field(default=[], description="Temas contextuais identificados")


# =============================================================================
# PROGRESS & STATUS MODELS - ATUALIZADOS
# =============================================================================

class GenerationProgress(BaseModel):
    """Progresso da geração de conteúdo."""
    unit_id: str = Field(..., description="ID da unidade")
    course_id: str = Field(..., description="ID do curso")
    book_id: str = Field(..., description="ID do book")
    sequence_order: int = Field(..., description="Sequência no book")
    
    current_step: str = Field(..., description="Etapa atual")
    progress_percentage: int = Field(..., ge=0, le=100, description="Porcentagem de progresso")
    message: str = Field(..., description="Mensagem de status")
    estimated_remaining_time: Optional[int] = Field(None, description="Tempo estimado restante (segundos)")
    
    # NOVOS CAMPOS PARA CONTEXTO RAG
    rag_context_loaded: bool = Field(False, description="Contexto RAG carregado?")
    precedent_units_found: int = Field(0, description="Unidades precedentes encontradas")
    vocabulary_overlap_analysis: Optional[Dict[str, Any]] = Field(None, description="Análise de sobreposição")
    
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais")


class ErrorResponse(BaseModel):
    """Response de erro padronizado."""
    success: bool = Field(False, description="Sempre False para erros")
    error_code: str = Field(..., description="Código do erro")
    message: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes do erro")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # NOVOS CAMPOS PARA DEPURAÇÃO
    hierarchy_context: Optional[Dict[str, str]] = Field(None, description="Contexto hierárquico do erro")
    suggested_fixes: List[str] = Field(default=[], description="Sugestões de correção")


class SuccessResponse(BaseModel):
    """Response de sucesso padronizado."""
    success: bool = Field(True, description="Sempre True para sucesso")
    data: Dict[str, Any] = Field(..., description="Dados da resposta")
    message: Optional[str] = Field(None, description="Mensagem opcional")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # NOVOS CAMPOS PARA CONTEXTO
    hierarchy_info: Optional[Dict[str, str]] = Field(None, description="Informações hierárquicas")
    next_suggested_actions: List[str] = Field(default=[], description="Próximas ações sugeridas")


# =============================================================================
# BATCH AND BULK OPERATION MODELS
# =============================================================================

class BulkUnitStatus(BaseModel):
    """Status de operação em lote."""
    total_units: int = Field(..., description="Total de unidades processadas")
    successful: int = Field(..., description="Unidades processadas com sucesso")
    failed: int = Field(..., description="Unidades que falharam")
    errors: List[Dict[str, str]] = Field(default=[], description="Detalhes dos erros")
    processing_time: float = Field(..., description="Tempo total de processamento")


class CourseStatistics(BaseModel):
    """Estatísticas do curso."""
    course_id: str
    course_name: str
    total_books: int
    total_units: int
    completed_units: int
    average_quality_score: float
    
    # DISTRIBUIÇÕES
    units_by_level: Dict[str, int] = Field(default={}, description="Unidades por nível CEFR")
    units_by_type: Dict[str, int] = Field(default={}, description="Unidades por tipo")
    strategy_distribution: Dict[str, int] = Field(default={}, description="Distribuição de estratégias")
    assessment_distribution: Dict[str, int] = Field(default={}, description="Distribuição de atividades")
    
    # PROGRESSÃO
    vocabulary_progression: Dict[str, Any] = Field(default={}, description="Progressão de vocabulário")
    quality_progression: List[float] = Field(default=[], description="Progressão da qualidade")
    
    last_updated: datetime = Field(default_factory=datetime.now)


# =============================================================================
# MIGRATION HELPERS (Para compatibilidade)
# =============================================================================

class LegacyUnitAdapter(BaseModel):
    """Adaptador para unidades do sistema antigo."""
    
    @classmethod
    def from_legacy_unit(cls, legacy_data: Dict[str, Any]) -> UnitResponse:
        """Converte unidade do formato antigo para o novo com hierarquia."""
        # Implementar lógica de migração
        # Por enquanto, valores padrão para hierarquia
        return UnitResponse(
            id=legacy_data.get("id", "legacy_unit"),
            course_id=legacy_data.get("course_id", "course_default"),
            book_id=legacy_data.get("book_id", "book_default"),
            sequence_order=legacy_data.get("sequence_order", 1),
            title=legacy_data.get("title", "Legacy Unit"),
            main_aim=legacy_data.get("main_aim", "Legacy main aim"),
            subsidiary_aims=legacy_data.get("subsidiary_aims", []),
            unit_type=UnitType(legacy_data.get("unit_type", "lexical_unit")),
            cefr_level=CEFRLevel(legacy_data.get("cefr_level", "A1")),
            language_variant=LanguageVariant(legacy_data.get("language_variant", "american_english")),
            status=UnitStatus(legacy_data.get("status", "creating")),
            vocabulary=legacy_data.get("vocabulary"),
            sentences=legacy_data.get("sentences"),
            tips=legacy_data.get("tips"),
            grammar=legacy_data.get("grammar"),
            qa=legacy_data.get("qa"),
            assessments=legacy_data.get("assessments"),
            created_at=legacy_data.get("created_at", datetime.now()),
            updated_at=legacy_data.get("updated_at", datetime.now())
        )