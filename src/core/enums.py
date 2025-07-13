"""Enums do sistema IVO V2."""
from enum import Enum


class CEFRLevel(str, Enum):
    """Níveis do Common European Framework of Reference."""
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class LanguageVariant(str, Enum):
    """Variantes de idiomas suportadas."""
    # English Variants
    AMERICAN_ENGLISH = "american_english"
    BRITISH_ENGLISH = "british_english"
    AUSTRALIAN_ENGLISH = "australian_english"
    INDIAN_ENGLISH = "indian_english"
    CANADIAN_ENGLISH = "canadian_english"
    
    # Spanish Variants
    MEXICAN_SPANISH = "mexican_spanish"
    ARGENTINIAN_SPANISH = "argentinian_spanish"
    COLOMBIAN_SPANISH = "colombian_spanish"
    SPANISH_SPAIN = "spanish_spain"
    
    # Portuguese Variants
    BRAZILIAN_PORTUGUESE = "brazilian_portuguese"
    EUROPEAN_PORTUGUESE = "european_portuguese"
    
    # French Variants
    FRENCH_FRANCE = "french_france"
    CANADIAN_FRENCH = "canadian_french"


class UnitType(str, Enum):
    """Tipo de unidade pedagógica."""
    LEXICAL_UNIT = "lexical_unit"
    GRAMMAR_UNIT = "grammar_unit"


class AimType(str, Enum):
    """Tipo de objetivo (usado internamente)."""
    LEXIS = "lexis"
    GRAMMAR = "grammar"


class TipStrategy(str, Enum):
    """Estratégias TIPS para unidades lexicais."""
    AFIXACAO = "afixacao"  # TIP 1: Prefixes/suffixes
    SUBSTANTIVOS_COMPOSTOS = "substantivos_compostos"  # TIP 2: Compound nouns
    COLOCACOES = "colocacoes"  # TIP 3: Collocations
    EXPRESSOES_FIXAS = "expressoes_fixas"  # TIP 4: Fixed expressions
    IDIOMAS = "idiomas"  # TIP 5: Idioms
    CHUNKS = "chunks"  # TIP 6: Chunks


class GrammarStrategy(str, Enum):
    """Estratégias GRAMMAR para unidades gramaticais."""
    EXPLICACAO_SISTEMATICA = "explicacao_sistematica"  # GRAMMAR 1
    PREVENCAO_ERROS_L1 = "prevencao_erros_l1"  # GRAMMAR 2


class AssessmentType(str, Enum):
    """Tipos de atividades de avaliação."""
    CLOZE_TEST = "cloze_test"  # 1
    GAP_FILL = "gap_fill"  # 2
    REORDENACAO = "reordenacao"  # 3
    TRANSFORMACAO = "transformacao"  # 4
    MULTIPLA_ESCOLHA = "multipla_escolha"  # 5
    VERDADEIRO_FALSO = "verdadeiro_falso"  # 6
    MATCHING = "matching"  # 7


class UnitStatus(str, Enum):
    """Status da unidade."""
    CREATING = "creating"
    VOCAB_PENDING = "vocab_pending"
    SENTENCES_PENDING = "sentences_pending"
    CONTENT_PENDING = "content_pending"
    ASSESSMENTS_PENDING = "assessments_pending"
    COMPLETED = "completed"
    ERROR = "error"


class ContentType(str, Enum):
    """Tipos de conteúdo da unidade."""
    VOCABULARY = "vocabulary"
    SENTENCES = "sentences"
    TIPS = "tips"
    GRAMMAR = "grammar"
    QA = "qa"
    ASSESSMENTS = "assessments"


# Legacy enums (manter compatibilidade)
class EnglishVariant(str, Enum):
    """Variantes do inglês (deprecated - usar LanguageVariant)."""
    AMERICAN = "american"
    BRITISH = "british"


class ApostilaStatus(str, Enum):
    """Status da apostila (deprecated - usar UnitStatus)."""
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    ERROR = "error"