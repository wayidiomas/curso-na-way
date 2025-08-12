# src/core/unit_models.py - ATUALIZADO COM VALIDAÇÃO IPA E MELHORIAS
"""Modelos específicos para o sistema IVO V2 com hierarquia Course → Book → Unit."""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from fastapi import UploadFile
import re

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
# VOCABULARY MODELS - ATUALIZADO COM VALIDAÇÃO IPA COMPLETA
# =============================================================================

class VocabularyItem(BaseModel):
    """Item de vocabulário com fonema IPA validado - VERSÃO COMPLETA."""
    word: str = Field(..., min_length=1, max_length=50, description="Palavra no idioma alvo")
    phoneme: str = Field(..., description="Transcrição fonética IPA válida")
    definition: str = Field(..., min_length=5, max_length=200, description="Definição em português")
    example: str = Field(..., min_length=10, max_length=300, description="Exemplo de uso em contexto")
    word_class: str = Field(..., description="Classe gramatical")
    frequency_level: str = Field("medium", description="Nível de frequência")
    
    # NOVOS CAMPOS PARA PROGRESSÃO
    context_relevance: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevância contextual")
    is_reinforcement: Optional[bool] = Field(False, description="É palavra de reforço?")
    first_introduced_unit: Optional[str] = Field(None, description="Unidade onde foi introduzida")
    
    # NOVOS CAMPOS PARA IPA E FONEMAS
    ipa_variant: str = Field("general_american", description="Variante IPA")
    stress_pattern: Optional[str] = Field(None, description="Padrão de stress")
    syllable_count: Optional[int] = Field(None, ge=1, le=8, description="Número de sílabas")
    alternative_pronunciations: List[str] = Field(default=[], description="Pronúncias alternativas")
    
    @validator('phoneme')
    def validate_ipa_phoneme(cls, v):
        """Validar que o fonema usa símbolos IPA válidos."""
        if not v:
            raise ValueError("Fonema é obrigatório")
        
        # Verificar se está entre delimitadores IPA corretos
        if not ((v.startswith('/') and v.endswith('/')) or 
                (v.startswith('[') and v.endswith(']'))):
            raise ValueError("Fonema deve estar entre / / (fonêmico) ou [ ] (fonético)")
        
        # Símbolos IPA válidos expandidos
        valid_ipa_chars = set(
            # Vogais básicas
            'aæəɑɒɔɪɛɜɝɨɉʊʌʏybcdfɡhijklmnpqrstuɥvwxyz'
            # Consoantes especiais
            'θðʃʒʧʤŋɹɻɾɸβçʝɠʔ'
            # Diacríticos e modificadores
            'ʰʷʲˤ̥̩̯̰̹̜̟̘̙̞̠̃̊'
            # Suprassegmentais
            'ˈˌːˑ'
            # Articulação
            '̪̺̻̼̝̞̘̙̗̖̯̰̱̜̟̚'
            # Caracteres especiais permitidos
            ' .ː'
        )
        
        # Remover delimitadores para validação
        clean_phoneme = v.strip('/[]')
        
        # Verificar se contém apenas símbolos IPA válidos
        invalid_chars = set(clean_phoneme) - valid_ipa_chars
        if invalid_chars:
            raise ValueError(f"Símbolos IPA inválidos encontrados: {invalid_chars}")
        
        # Verificar padrões comuns de erro
        if '//' in clean_phoneme or '[[' in clean_phoneme:
            raise ValueError("Delimitadores duplicados não são permitidos")
        
        # Verificar se tem pelo menos um som válido
        if len(clean_phoneme.strip()) == 0:
            raise ValueError("Fonema não pode estar vazio")
        
        return v
    
    @validator('word')
    def validate_word_format(cls, v):
        """Validar formato da palavra."""
        if not v:
            raise ValueError("Palavra é obrigatória")
        
        # Permitir letras, hífens, apóstrofes e pontos
        if not re.match(r"^[a-zA-Z\-'\.]+$", v):
            raise ValueError("Palavra deve conter apenas letras, hífens, apóstrofes ou pontos")
        
        return v.lower().strip()
    
    @validator('word_class')
    def validate_word_class(cls, v):
        """Validar classe gramatical."""
        valid_classes = {
            "noun", "verb", "adjective", "adverb", "preposition", 
            "conjunction", "article", "pronoun", "interjection",
            "modal", "auxiliary", "determiner", "numeral"
        }
        
        if v.lower() not in valid_classes:
            raise ValueError(f"Classe gramatical deve ser uma de: {', '.join(valid_classes)}")
        
        return v.lower()
    
    @validator('frequency_level')
    def validate_frequency_level(cls, v):
        """Validar nível de frequência."""
        valid_levels = {"high", "medium", "low", "very_high", "very_low"}
        
        if v.lower() not in valid_levels:
            raise ValueError(f"Nível de frequência deve ser um de: {', '.join(valid_levels)}")
        
        return v.lower()
    
    @validator('ipa_variant')
    def validate_ipa_variant(cls, v):
        """Validar variante IPA."""
        valid_variants = {
            "general_american", "received_pronunciation", "australian_english",
            "canadian_english", "irish_english", "scottish_english"
        }
        
        if v.lower() not in valid_variants:
            raise ValueError(f"Variante IPA deve ser uma de: {', '.join(valid_variants)}")
        
        return v.lower()
    
    @validator('alternative_pronunciations', each_item=True)
    def validate_alternative_pronunciations(cls, v):
        """Validar pronúncias alternativas."""
        # Aplicar a mesma validação IPA
        if v and not ((v.startswith('/') and v.endswith('/')) or 
                     (v.startswith('[') and v.endswith(']'))):
            raise ValueError("Pronúncia alternativa deve seguir formato IPA")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "word": "restaurant",
                "phoneme": "/ˈrɛstərɑnt/",
                "definition": "estabelecimento comercial onde se servem refeições",
                "example": "We had dinner at a lovely Italian restaurant last night.",
                "word_class": "noun",
                "frequency_level": "high",
                "context_relevance": 0.95,
                "is_reinforcement": False,
                "ipa_variant": "general_american",
                "stress_pattern": "primary_first",
                "syllable_count": 3,
                "alternative_pronunciations": ["/ˈrestərɑnt/"]
            }
        }


class VocabularySection(BaseModel):
    """Seção completa de vocabulário - ATUALIZADA COM RAG E VALIDAÇÃO."""
    items: List[VocabularyItem] = Field(..., description="Lista de itens de vocabulário")
    total_count: int = Field(..., description="Total de palavras")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevância contextual")
    
    # NOVOS CAMPOS PARA RAG
    new_words_count: int = Field(0, description="Palavras totalmente novas")
    reinforcement_words_count: int = Field(0, description="Palavras de reforço")
    rag_context_used: Dict[str, Any] = Field(default={}, description="Contexto RAG utilizado")
    progression_level: str = Field(default="intermediate", description="Nível de progressão")
    
    # NOVOS CAMPOS PARA IPA
    phoneme_coverage: Dict[str, int] = Field(default={}, description="Cobertura de fonemas IPA")
    pronunciation_variants: List[str] = Field(default=[], description="Variantes de pronúncia utilizadas")
    phonetic_complexity: str = Field(default="medium", description="Complexidade fonética geral")
    
    generated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('total_count')
    def validate_total_count(cls, v, values):
        """Validar contagem total."""
        items = values.get('items', [])
        if v != len(items):
            return len(items)
        return v
    
    @validator('items')
    def validate_items_not_empty(cls, v):
        """Validar que há pelo menos alguns itens."""
        if len(v) == 0:
            raise ValueError("Seção de vocabulário deve ter pelo menos 1 item")
        
        if len(v) > 50:
            raise ValueError("Seção de vocabulário não deve ter mais de 50 itens")
        
        return v
    
    @validator('phonetic_complexity')
    def validate_phonetic_complexity(cls, v):
        """Validar complexidade fonética."""
        valid_complexities = {"simple", "medium", "complex", "very_complex"}
        
        if v.lower() not in valid_complexities:
            raise ValueError(f"Complexidade fonética deve ser uma de: {', '.join(valid_complexities)}")
        
        return v.lower()


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
    
    # NOVOS CAMPOS PARA FONEMAS
    phonetic_focus: List[str] = Field(default=[], description="Fonemas ou padrões fonéticos focalizados")
    pronunciation_tips: List[str] = Field(default=[], description="Dicas específicas de pronúncia")


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
    
    # NOVOS CAMPOS PARA FONEMAS
    pronunciation_focus: bool = Field(False, description="Atividade foca em pronúncia")
    phonetic_elements: List[str] = Field(default=[], description="Elementos fonéticos avaliados")
    
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
                "vocabulary_focus": ["reservation", "service"],
                "pronunciation_focus": False,
                "phonetic_elements": []
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
    images: List["ImageInfo"] = Field(default=[], description="Informações das imagens")
    vocabulary: Optional[VocabularySection] = Field(None, description="Seção de vocabulário")
    sentences: Optional["SentencesSection"] = Field(None, description="Seção de sentences")
    tips: Optional[TipsContent] = Field(None, description="Conteúdo TIPS (se lexical)")
    grammar: Optional[GrammarContent] = Field(None, description="Conteúdo GRAMMAR (se grammar)")
    qa: Optional["QASection"] = Field(None, description="Seção Q&A")
    assessments: Optional[AssessmentSection] = Field(None, description="Seção de avaliação")
    
    # PROGRESSÃO PEDAGÓGICA (novos campos)
    strategies_used: List[str] = Field(default=[], description="Estratégias já usadas")
    assessments_used: List[str] = Field(default=[], description="Tipos de atividades já usadas")
    vocabulary_taught: List[str] = Field(default=[], description="Vocabulário ensinado nesta unidade")
    
    # NOVOS CAMPOS PARA FONEMAS
    phonemes_introduced: List[str] = Field(default=[], description="Fonemas introduzidos nesta unidade")
    pronunciation_focus: Optional[str] = Field(None, description="Foco de pronúncia da unidade")
    
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
                "phonemes_introduced": ["/ˌrezərˈveɪʃən/", "/ˈʧɛk ɪn/"],
                "pronunciation_focus": "stress_patterns",
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
    
    # NOVOS CAMPOS PARA FONEMAS
    phonetic_features: List[str] = Field(default=[], description="Características fonéticas destacadas")
    pronunciation_notes: Optional[str] = Field(None, description="Notas de pronúncia")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "I need to make a reservation for two people tonight.",
                "vocabulary_used": ["reservation"],
                "context_situation": "restaurant_booking",
                "complexity_level": "intermediate",
                "reinforces_previous": [],
                "introduces_new": ["reservation"],
                "phonetic_features": ["word_stress", "schwa_reduction"],
                "pronunciation_notes": "Note the stress on 'reser-VA-tion'"
            }
        }


class SentencesSection(BaseModel):
    """Seção de sentences."""
    sentences: List[Sentence] = Field(..., description="Lista de sentences")
    vocabulary_coverage: float = Field(..., ge=0.0, le=1.0, description="Cobertura do vocabulário")
    
    # NOVOS CAMPOS PARA RAG
    contextual_coherence: float = Field(default=0.8, description="Coerência contextual")
    progression_appropriateness: float = Field(default=0.8, description="Adequação à progressão")
    
    # NOVOS CAMPOS PARA FONEMAS
    phonetic_progression: List[str] = Field(default=[], description="Progressão fonética nas sentences")
    pronunciation_patterns: List[str] = Field(default=[], description="Padrões de pronúncia abordados")
    
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
    
    # NOVOS CAMPOS PARA FONEMAS
    pronunciation_questions: List[str] = Field(default=[], description="Perguntas sobre pronúncia")
    phonetic_awareness: List[str] = Field(default=[], description="Consciência fonética desenvolvida")


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
    
    # NOVOS CAMPOS PARA FONEMAS
    phoneme_analysis_completed: bool = Field(False, description="Análise fonética completada?")
    pronunciation_validation: Optional[Dict[str, Any]] = Field(None, description="Validação de pronúncia")
    
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
    
    # NOVOS CAMPOS PARA FONEMAS
    phoneme_distribution: Dict[str, int] = Field(default={}, description="Distribuição de fonemas IPA")
    pronunciation_variants: List[str] = Field(default=[], description="Variantes de pronúncia usadas")
    phonetic_complexity_trend: List[str] = Field(default=[], description="Tendência de complexidade fonética")
    
    last_updated: datetime = Field(default_factory=datetime.now)


# =============================================================================
# VOCABULARY GENERATION MODELS - NOVOS PARA PROMPT 6
# =============================================================================

class VocabularyGenerationRequest(BaseModel):
    """Request para geração de vocabulário com imagens."""
    images_context: List[Dict[str, Any]] = Field(..., description="Contexto das imagens analisadas")
    target_count: int = Field(25, ge=10, le=50, description="Número desejado de palavras")
    cefr_level: CEFRLevel = Field(..., description="Nível CEFR para o vocabulário")
    language_variant: LanguageVariant = Field(..., description="Variante do idioma")
    unit_type: UnitType = Field(..., description="Tipo de unidade")
    
    # CONFIGURAÇÕES DE IPA
    ipa_variant: str = Field("general_american", description="Variante IPA desejada")
    include_alternative_pronunciations: bool = Field(False, description="Incluir pronúncias alternativas")
    phonetic_complexity: str = Field("medium", description="Complexidade fonética desejada")
    
    # CONTEXTO RAG
    avoid_vocabulary: List[str] = Field(default=[], description="Palavras a evitar (já ensinadas)")
    reinforce_vocabulary: List[str] = Field(default=[], description="Palavras para reforçar")
    
    class Config:
        schema_extra = {
            "example": {
                "images_context": [
                    {
                        "description": "Hotel reception with people checking in",
                        "objects": ["desk", "receptionist", "guests", "luggage"],
                        "themes": ["hospitality", "travel", "accommodation"]
                    }
                ],
                "target_count": 25,
                "cefr_level": "A2",
                "language_variant": "american_english",
                "unit_type": "lexical_unit",
                "ipa_variant": "general_american",
                "include_alternative_pronunciations": False,
                "phonetic_complexity": "medium",
                "avoid_vocabulary": ["hello", "goodbye"],
                "reinforce_vocabulary": ["hotel", "room"]
            }
        }


class VocabularyGenerationResponse(BaseModel):
    """Response da geração de vocabulário."""
    vocabulary_section: VocabularySection = Field(..., description="Seção de vocabulário gerada")
    generation_metadata: Dict[str, Any] = Field(..., description="Metadados da geração")
    rag_analysis: Dict[str, Any] = Field(..., description="Análise RAG aplicada")
    quality_metrics: Dict[str, float] = Field(..., description="Métricas de qualidade")
    
    # MÉTRICAS DE IPA
    phoneme_analysis: Dict[str, Any] = Field(..., description="Análise dos fonemas incluídos")
    pronunciation_coverage: Dict[str, float] = Field(..., description="Cobertura de padrões de pronúncia")
    
    class Config:
        schema_extra = {
            "example": {
                "generation_metadata": {
                    "generation_time_ms": 1500,
                    "ai_model_used": "gpt-4o-mini",
                    "mcp_analysis_included": True,
                    "rag_context_applied": True
                },
                "rag_analysis": {
                    "words_avoided": 3,
                    "words_reinforced": 2,
                    "new_words_generated": 20,
                    "progression_appropriate": True
                },
                "quality_metrics": {
                    "context_relevance": 0.92,
                    "cefr_appropriateness": 0.95,
                    "vocabulary_diversity": 0.88,
                    "phonetic_accuracy": 0.97
                },
                "phoneme_analysis": {
                    "total_unique_phonemes": 35,
                    "most_common_phonemes": ["/ə/", "/ɪ/", "/eɪ/"],
                    "stress_patterns": ["primary_first", "primary_second"],
                    "syllable_distribution": {"1": 5, "2": 12, "3": 6, "4+": 2}
                },
                "pronunciation_coverage": {
                    "vowel_sounds": 0.85,
                    "consonant_clusters": 0.70,
                    "stress_patterns": 0.90
                }
            }
        }


# =============================================================================
# PHONETIC VALIDATION MODELS - NOVOS
# =============================================================================

class PhoneticValidationResult(BaseModel):
    """Resultado da validação fonética de um item de vocabulário."""
    word: str = Field(..., description="Palavra validada")
    phoneme: str = Field(..., description="Fonema validado")
    is_valid: bool = Field(..., description="Se a validação passou")
    
    validation_details: Dict[str, Any] = Field(..., description="Detalhes da validação")
    suggestions: List[str] = Field(default=[], description="Sugestões de correção")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confiança na validação")
    
    class Config:
        schema_extra = {
            "example": {
                "word": "restaurant",
                "phoneme": "/ˈrɛstərɑnt/",
                "is_valid": True,
                "validation_details": {
                    "ipa_symbols_valid": True,
                    "stress_marking_correct": True,
                    "syllable_count_matches": True,
                    "variant_appropriate": True
                },
                "suggestions": [],
                "confidence_score": 0.98
            }
        }


class BulkPhoneticValidation(BaseModel):
    """Validação fonética em lote."""
    total_items: int = Field(..., description="Total de itens validados")
    valid_items: int = Field(..., description="Itens válidos")
    invalid_items: int = Field(..., description="Itens inválidos")
    
    validation_results: List[PhoneticValidationResult] = Field(..., description="Resultados individuais")
    overall_quality: float = Field(..., ge=0.0, le=1.0, description="Qualidade geral")
    
    common_errors: List[str] = Field(default=[], description="Erros comuns encontrados")
    improvement_suggestions: List[str] = Field(default=[], description="Sugestões de melhoria")


# =============================================================================
# MIGRATION HELPERS (Para compatibilidade) - ATUALIZADO
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
            # NOVOS CAMPOS PARA COMPATIBILIDADE
            phonemes_introduced=legacy_data.get("phonemes_introduced", []),
            pronunciation_focus=legacy_data.get("pronunciation_focus"),
            created_at=legacy_data.get("created_at", datetime.now()),
            updated_at=legacy_data.get("updated_at", datetime.now())
        )
    
    @classmethod
    def migrate_vocabulary_to_ipa(cls, legacy_vocabulary: List[Dict[str, Any]]) -> List[VocabularyItem]:
        """Migrar vocabulário antigo para formato com IPA."""
        migrated_items = []
        
        for item in legacy_vocabulary:
            # Gerar fonema básico se não existir
            phoneme = item.get("phoneme")
            if not phoneme:
                # Fonema placeholder - deveria ser gerado por IA
                word = item.get("word", "")
                phoneme = f"/placeholder_{word}/"
            
            try:
                vocabulary_item = VocabularyItem(
                    word=item.get("word", ""),
                    phoneme=phoneme,
                    definition=item.get("definition", ""),
                    example=item.get("example", ""),
                    word_class=item.get("word_class", "noun"),
                    frequency_level=item.get("frequency_level", "medium"),
                    context_relevance=item.get("context_relevance", 0.5),
                    is_reinforcement=item.get("is_reinforcement", False),
                    ipa_variant="general_american",
                    syllable_count=item.get("syllable_count", 1)
                )
                migrated_items.append(vocabulary_item)
            except Exception as e:
                # Log erro e pular item inválido
                print(f"Erro ao migrar item {item.get('word', 'unknown')}: {str(e)}")
                continue
        
        return migrated_items


# =============================================================================
# UTILITY FUNCTIONS PARA IPA - NOVAS
# =============================================================================

def extract_phonemes_from_vocabulary(vocabulary_section: VocabularySection) -> List[str]:
    """Extrair lista única de fonemas de uma seção de vocabulário."""
    phonemes = set()
    
    for item in vocabulary_section.items:
        # Extrair fonemas individuais do campo phoneme
        clean_phoneme = item.phoneme.strip('/[]')
        # Separar por espaços e pontos para obter fonemas individuais
        individual_phonemes = clean_phoneme.replace('.', ' ').split()
        
        for phoneme in individual_phonemes:
            if phoneme and len(phoneme) > 0:
                phonemes.add(phoneme)
    
    return sorted(list(phonemes))


def analyze_phonetic_complexity(vocabulary_items: List[VocabularyItem]) -> Dict[str, Any]:
    """Analisar complexidade fonética de uma lista de itens de vocabulário."""
    if not vocabulary_items:
        return {"complexity": "unknown", "details": {}}
    
    syllable_counts = [item.syllable_count for item in vocabulary_items if item.syllable_count]
    phoneme_lengths = [len(item.phoneme.strip('/[]').replace(' ', '')) for item in vocabulary_items]
    
    avg_syllables = sum(syllable_counts) / len(syllable_counts) if syllable_counts else 1
    avg_phoneme_length = sum(phoneme_lengths) / len(phoneme_lengths) if phoneme_lengths else 5
    
    # Determinar complexidade baseada em métricas
    if avg_syllables <= 1.5 and avg_phoneme_length <= 6:
        complexity = "simple"
    elif avg_syllables <= 2.5 and avg_phoneme_length <= 10:
        complexity = "medium"
    elif avg_syllables <= 3.5 and avg_phoneme_length <= 15:
        complexity = "complex"
    else:
        complexity = "very_complex"
    
    return {
        "complexity": complexity,
        "details": {
            "average_syllables": round(avg_syllables, 2),
            "average_phoneme_length": round(avg_phoneme_length, 2),
            "total_items": len(vocabulary_items),
            "syllable_distribution": {
                "1": len([s for s in syllable_counts if s == 1]),
                "2": len([s for s in syllable_counts if s == 2]),
                "3": len([s for s in syllable_counts if s == 3]),
                "4+": len([s for s in syllable_counts if s >= 4])
            }
        }
    }


def validate_ipa_consistency(vocabulary_items: List[VocabularyItem]) -> Dict[str, Any]:
    """Validar consistência IPA entre itens de vocabulário."""
    variants = set(item.ipa_variant for item in vocabulary_items)
    inconsistencies = []
    
    if len(variants) > 1:
        inconsistencies.append(f"Múltiplas variantes IPA encontradas: {variants}")
    
    # Verificar padrões de stress inconsistentes
    stress_patterns = [item.stress_pattern for item in vocabulary_items if item.stress_pattern]
    unique_patterns = set(stress_patterns)
    
    if len(unique_patterns) > 3:
        inconsistencies.append(f"Muitos padrões de stress diferentes: {unique_patterns}")
    
    return {
        "is_consistent": len(inconsistencies) == 0,
        "inconsistencies": inconsistencies,
        "variants_used": list(variants),
        "stress_patterns_used": list(unique_patterns)
    }

# =============================================================================
# L1 INTERFERENCE PATTERN MODEL - ADICIONAR AO FINAL DE unit_models.py
# =============================================================================

class L1InterferencePattern(BaseModel):
    """Modelo para padrões de interferência L1→L2 (português→inglês)."""
    pattern_type: str = Field(..., description="Tipo de padrão de interferência")
    portuguese_structure: str = Field(..., description="Estrutura em português")
    incorrect_english: str = Field(..., description="Inglês incorreto (interferência)")
    correct_english: str = Field(..., description="Inglês correto")
    explanation: str = Field(..., description="Explicação da interferência")
    prevention_strategy: str = Field(..., description="Estratégia de prevenção")
    examples: List[str] = Field(default=[], description="Exemplos adicionais")
    difficulty_level: str = Field(default="intermediate", description="Nível de dificuldade")
    
    # Validações específicas
    @validator('pattern_type')
    def validate_pattern_type(cls, v):
        """Validar tipo de padrão."""
        valid_types = {
            "grammatical", "lexical", "phonetic", "semantic", 
            "syntactic", "cultural", "pragmatic"
        }
        
        if v.lower() not in valid_types:
            raise ValueError(f"Tipo de padrão deve ser um de: {', '.join(valid_types)}")
        
        return v.lower()
    
    @validator('difficulty_level')
    def validate_difficulty_level(cls, v):
        """Validar nível de dificuldade."""
        valid_levels = {"beginner", "elementary", "intermediate", "upper_intermediate", "advanced"}
        
        if v.lower() not in valid_levels:
            raise ValueError(f"Nível de dificuldade deve ser um de: {', '.join(valid_levels)}")
        
        return v.lower()
    
    @validator('prevention_strategy')
    def validate_prevention_strategy(cls, v):
        """Validar estratégia de prevenção."""
        valid_strategies = {
            "contrastive_exercises", "awareness_raising", "drilling", 
            "error_correction", "explicit_instruction", "input_enhancement",
            "consciousness_raising", "form_focused_instruction"
        }
        
        if v.lower() not in valid_strategies:
            raise ValueError(f"Estratégia deve ser uma de: {', '.join(valid_strategies)}")
        
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "pattern_type": "grammatical",
                "portuguese_structure": "Eu tenho 25 anos",
                "incorrect_english": "I have 25 years",
                "correct_english": "I am 25 years old",
                "explanation": "Portuguese uses 'ter' (have) for age, English uses 'be'",
                "prevention_strategy": "contrastive_exercises",
                "examples": [
                    "I am 30 years old",
                    "She is 25 years old",
                    "How old are you? (not: How many years do you have?)"
                ],
                "difficulty_level": "beginner"
            }
        }


class L1InterferenceAnalysis(BaseModel):
    """Análise completa de interferência L1→L2."""
    grammar_point: str = Field(..., description="Ponto gramatical analisado")
    vocabulary_items: List[str] = Field(..., description="Itens de vocabulário analisados")
    cefr_level: str = Field(..., description="Nível CEFR do conteúdo")
    
    identified_patterns: List[L1InterferencePattern] = Field(..., description="Padrões identificados")
    prevention_strategies: List[str] = Field(..., description="Estratégias de prevenção gerais")
    common_mistakes: List[str] = Field(..., description="Erros comuns identificados")
    preventive_exercises: List[Dict[str, Any]] = Field(..., description="Exercícios preventivos sugeridos")
    
    # Métricas de análise
    interference_risk_score: float = Field(..., ge=0.0, le=1.0, description="Score de risco de interferência")
    patterns_count: int = Field(..., ge=0, description="Número de padrões identificados")
    coverage_areas: List[str] = Field(..., description="Áreas de interferência cobertas")
    
    generated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('interference_risk_score')
    def validate_risk_score(cls, v):
        """Validar score de risco."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Score de risco deve estar entre 0.0 e 1.0")
        return v
    
    @validator('patterns_count')
    def validate_patterns_count(cls, v, values):
        """Validar contagem de padrões."""
        patterns = values.get('identified_patterns', [])
        if v != len(patterns):
            return len(patterns)
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "grammar_point": "Age expressions",
                "vocabulary_items": ["age", "years", "old", "young"],
                "cefr_level": "A1",
                "identified_patterns": [
                    {
                        "pattern_type": "grammatical",
                        "portuguese_structure": "Eu tenho X anos",
                        "incorrect_english": "I have X years",
                        "correct_english": "I am X years old",
                        "explanation": "Age structure difference PT vs EN",
                        "prevention_strategy": "contrastive_exercises"
                    }
                ],
                "prevention_strategies": [
                    "Contrast exercises Portuguese vs English",
                    "Explicit instruction on BE vs HAVE",
                    "Drilling with age expressions"
                ],
                "common_mistakes": [
                    "Using HAVE instead of BE for age",
                    "Literal translation from Portuguese",
                    "Missing 'old' in age expressions"
                ],
                "preventive_exercises": [
                    {
                        "type": "contrast_exercise",
                        "description": "Compare PT and EN age expressions",
                        "examples": ["PT: Tenho 20 anos → EN: I am 20 years old"]
                    }
                ],
                "interference_risk_score": 0.8,
                "patterns_count": 1,
                "coverage_areas": ["grammatical_structure", "verb_usage"]
            }
        }


# =============================================================================
# UTILIDADES PARA L1 INTERFERENCE
# =============================================================================

def create_l1_interference_pattern(
    pattern_type: str,
    portuguese_structure: str,
    incorrect_english: str,
    correct_english: str,
    explanation: str,
    prevention_strategy: str = "contrastive_exercises",
    examples: List[str] = None,
    difficulty_level: str = "intermediate"
) -> L1InterferencePattern:
    """Criar um padrão de interferência L1→L2."""
    return L1InterferencePattern(
        pattern_type=pattern_type,
        portuguese_structure=portuguese_structure,
        incorrect_english=incorrect_english,
        correct_english=correct_english,
        explanation=explanation,
        prevention_strategy=prevention_strategy,
        examples=examples or [],
        difficulty_level=difficulty_level
    )


def get_common_l1_interference_patterns() -> List[L1InterferencePattern]:
    """Retornar padrões comuns de interferência para brasileiros."""
    return [
        L1InterferencePattern(
            pattern_type="grammatical",
            portuguese_structure="Eu tenho 25 anos",
            incorrect_english="I have 25 years",
            correct_english="I am 25 years old",
            explanation="Portuguese uses 'ter' (have) for age, English uses 'be'",
            prevention_strategy="contrastive_exercises",
            examples=["I am 30 years old", "She is 25 years old"],
            difficulty_level="beginner"
        ),
        L1InterferencePattern(
            pattern_type="lexical",
            portuguese_structure="Eu estou com fome",
            incorrect_english="I am with hunger",
            correct_english="I am hungry",
            explanation="Portuguese uses 'estar com + noun', English uses 'be + adjective'",
            prevention_strategy="explicit_instruction",
            examples=["I am thirsty", "I am tired", "I am cold"],
            difficulty_level="beginner"
        ),
        L1InterferencePattern(
            pattern_type="grammatical",
            portuguese_structure="A Maria é mais alta que a Ana",
            incorrect_english="Maria is more tall than Ana",
            correct_english="Maria is taller than Ana",
            explanation="Portuguese always uses 'mais + adjective', English has irregular comparatives",
            prevention_strategy="drilling",
            examples=["bigger (not more big)", "better (not more good)"],
            difficulty_level="elementary"
        ),
        L1InterferencePattern(
            pattern_type="phonetic",
            portuguese_structure="Hospital [hos-pi-TAL]",
            incorrect_english="Hospital [hos-pi-TAL]",
            correct_english="Hospital [HOS-pi-tal]",
            explanation="Portuguese stress on final syllable, English on first",
            prevention_strategy="awareness_raising",
            examples=["Hotel [ho-TEL] vs [ho-TEL]", "Animal [a-ni-MAL] vs [AN-i-mal]"],
            difficulty_level="intermediate"
        ),
        L1InterferencePattern(
            pattern_type="semantic",
            portuguese_structure="Pretender fazer algo",
            incorrect_english="I pretend to do something",
            correct_english="I intend to do something",
            explanation="Portuguese 'pretender' = English 'intend', not 'pretend'",
            prevention_strategy="consciousness_raising",
            examples=["I intend to study", "I plan to travel"],
            difficulty_level="intermediate"
        )
    ]


def analyze_text_for_l1_interference(text: str, cefr_level: str) -> List[str]:
    """Analisar texto para possíveis interferências L1."""
    common_patterns = get_common_l1_interference_patterns()
    potential_issues = []
    
    text_lower = text.lower()
    
    # Verificar padrões conhecidos
    interference_indicators = {
        "have + number + years": "Age expression with HAVE instead of BE",
        "more + adjective": "Comparative with MORE instead of -ER",
        "with + emotion noun": "Emotion expression with WITH instead of adjective",
        "pretend + to": "False friend: pretend vs intend"
    }
    
    for pattern, issue in interference_indicators.items():
        # Verificação simplificada - na prática seria mais sofisticada
        if any(word in text_lower for word in pattern.split(" + ")):
            potential_issues.append(issue)
    
    return potential_issues


# =============================================================================
# FORWARD REFERENCES FIX
# =============================================================================

# Resolver referências circulares
UnitResponse.model_rebuild()
VocabularySection.model_rebuild()
SentencesSection.model_rebuild()
QASection.model_rebuild()