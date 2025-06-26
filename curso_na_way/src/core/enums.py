"""Enums do sistema."""
from enum import Enum


class CEFRLevel(str, Enum):
    """Níveis do Common European Framework of Reference."""
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class EnglishVariant(str, Enum):
    """Variantes do inglês."""
    AMERICAN = "american"
    BRITISH = "british"


class ContentType(str, Enum):
    """Tipos de conteúdo da apostila."""
    TEORIA = "teoria"
    VOCABS = "vocabs"
    FRASES = "frases"
    BLOCO_GRAMATICAL = "bloco_gramatical"
    TIPS = "tips"
    EXERCICIO_TEXTO = "exercicio_texto"
    EXERCICIO_PREENCHIMENTO = "exercicio_preenchimento"
    EXERCICIO_INTERPRETATIVO = "exercicio_interpretativo"
    EXERCICIO_GRAMATICAL = "exercicio_gramatical"


class ApostilaStatus(str, Enum):
    """Status da apostila."""
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    ERROR = "error"
