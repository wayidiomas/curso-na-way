# src/services/aim_detector.py
"""
Serviço de detecção e geração de objetivos pedagógicos (aims) para unidades.
Implementação completa com análise IA contextual para objetivos principais e subsidiários.
Integrado com hierarquia Course → Book → Unit e metodologias TIPS/GRAMMAR do IVO V2.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError, Field, ConfigDict

from src.core.enums import CEFRLevel, LanguageVariant, UnitType, AimType
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


# =============================================================================
# MODELOS PYDANTIC 2 PARA OBJETIVOS
# =============================================================================

class LearningObjective(BaseModel):
    """Modelo para um objetivo de aprendizagem específico."""
    objective: str = Field(..., description="Descrição do objetivo")
    type: str = Field(..., description="Tipo do objetivo (main/subsidiary)")
    category: str = Field(..., description="Categoria (lexical/grammatical/functional/phonetic)")
    measurable: bool = Field(True, description="Se o objetivo é mensurável")
    achievable_level: str = Field(..., description="Nível em que é alcançável")
    bloom_level: str = Field(..., description="Nível da Taxonomia de Bloom")
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class UnitAims(BaseModel):
    """Modelo completo para objetivos de uma unidade."""
    main_aim: str = Field(..., description="Objetivo principal da unidade")
    subsidiary_aims: List[str] = Field(..., description="Objetivos subsidiários")
    aim_type: AimType = Field(..., description="Tipo principal (lexis/grammar)")
    learning_objectives: List[LearningObjective] = Field(..., description="Objetivos estruturados")
    communicative_goals: List[str] = Field(..., description="Objetivos comunicativos")
    assessment_criteria: List[str] = Field(..., description="Critérios de avaliação")
    
    # Campos de contexto
    cefr_appropriateness: float = Field(..., ge=0.0, le=1.0, description="Adequação ao nível CEFR")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="Relevância contextual")
    progression_alignment: float = Field(..., ge=0.0, le=1.0, description="Alinhamento com progressão")
    
    # Metadados
    generated_at: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confiança na análise")
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )


class AimDetectionRequest(BaseModel):
    """Request para detecção de objetivos."""
    unit_data: Dict[str, Any] = Field(..., description="Dados da unidade")
    content_data: Dict[str, Any] = Field(..., description="Conteúdo da unidade")
    hierarchy_context: Dict[str, Any] = Field(default={}, description="Contexto hierárquico")
    rag_context: Dict[str, Any] = Field(default={}, description="Contexto RAG")
    images_analysis: Dict[str, Any] = Field(default={}, description="Análise de imagens")
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='allow'
    )


# =============================================================================
# CONSTANTES PEDAGÓGICAS (METODOLOGIA ESTABELECIDA)
# =============================================================================

# Taxonomia de Bloom por nível CEFR
BLOOM_CEFR_MAPPING = {
    "A1": ["remember", "understand"],
    "A2": ["remember", "understand", "apply"],
    "B1": ["understand", "apply", "analyze"],
    "B2": ["apply", "analyze", "evaluate"],
    "C1": ["analyze", "evaluate", "create"],
    "C2": ["evaluate", "create"]
}

# Tipos de objetivos por categoria
OBJECTIVE_CATEGORIES = {
    "lexical": "vocabulary acquisition and usage",
    "grammatical": "grammar structures and patterns", 
    "functional": "communicative functions and language use",
    "phonetic": "pronunciation and phonemic awareness",
    "cultural": "cultural awareness and appropriateness",
    "strategic": "learning strategies and autonomy"
}

# Templates de objetivos por nível CEFR
CEFR_OBJECTIVE_TEMPLATES = {
    "A1": {
        "lexical": "Students will be able to recognize and use {count} basic words related to {context}",
        "grammatical": "Students will understand and use simple {grammar_point} structures",
        "functional": "Students will be able to {function} in basic {context} situations"
    },
    "A2": {
        "lexical": "Students will be able to use {count} vocabulary items to {purpose} in {context}",
        "grammatical": "Students will correctly apply {grammar_point} in {context} situations", 
        "functional": "Students will communicate effectively about {context} using appropriate language"
    },
    "B1": {
        "lexical": "Students will demonstrate mastery of {count} vocabulary items through varied {context} applications",
        "grammatical": "Students will analyze and apply {grammar_point} structures in complex {context}",
        "functional": "Students will negotiate meaning and express opinions about {context}"
    },
    "B2": {
        "lexical": "Students will evaluate and select appropriate vocabulary for {context} communication",
        "grammatical": "Students will manipulate {grammar_point} structures for nuanced expression in {context}",
        "functional": "Students will argue, persuade, and explain complex ideas related to {context}"
    },
    "C1": {
        "lexical": "Students will synthesize sophisticated vocabulary to express subtle meanings in {context}",
        "grammatical": "Students will employ {grammar_point} structures creatively for stylistic effect",
        "functional": "Students will demonstrate near-native proficiency in {context} discourse"
    },
    "C2": {
        "lexical": "Students will exhibit native-like precision in vocabulary choice for {context}",
        "grammatical": "Students will master all nuances of {grammar_point} in varied {context} registers",
        "functional": "Students will communicate with full native-like competence in {context}"
    }
}


class AimDetectorService:
    """Serviço principal para detecção e geração de objetivos pedagógicos via IA."""
    
    def __init__(self):
        """Inicializar serviço com IA contextual."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM para análise de objetivos
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.3,  # Baixa para consistência na análise pedagógica
            max_tokens=2048,
            api_key=self.openai_config.openai_api_key
        )
        
        logger.info("✅ AimDetectorService inicializado com análise IA contextual")
    
    async def detect_and_generate_aims(self, detection_params: Dict[str, Any]) -> UnitAims:
        """
        Detectar e gerar objetivos pedagógicos para uma unidade usando análise IA contextual.
        
        Args:
            detection_params: Parâmetros com contexto da unidade e conteúdo
            
        Returns:
            UnitAims completo com objetivos estruturados
        """
        try:
            start_time = time.time()
            
            # Validar entrada com Pydantic 2
            request = AimDetectionRequest(**detection_params)
            
            logger.info(f"🎯 Detectando objetivos para unidade {request.unit_data.get('title', 'Unknown')}")
            
            # 1. Construir contexto pedagógico enriquecido
            enriched_context = await self._build_pedagogical_context(request)
            
            # 2. ANÁLISE VIA IA: Detectar tipo principal da unidade (lexis vs grammar)
            main_aim_type = await self._detect_main_aim_type_ai(enriched_context)
            
            # 3. ANÁLISE VIA IA: Gerar objetivo principal contextual
            main_aim = await self._generate_main_aim_ai(enriched_context, main_aim_type)
            
            # 4. ANÁLISE VIA IA: Gerar objetivos subsidiários
            subsidiary_aims = await self._generate_subsidiary_aims_ai(
                enriched_context, main_aim, main_aim_type
            )
            
            # 5. ANÁLISE VIA IA: Estruturar objetivos de aprendizagem
            learning_objectives = await self._structure_learning_objectives_ai(
                enriched_context, main_aim, subsidiary_aims
            )
            
            # 6. ANÁLISE VIA IA: Gerar objetivos comunicativos
            communicative_goals = await self._generate_communicative_goals_ai(
                enriched_context, main_aim_type
            )
            
            # 7. ANÁLISE VIA IA: Definir critérios de avaliação
            assessment_criteria = await self._define_assessment_criteria_ai(
                enriched_context, main_aim, subsidiary_aims
            )
            
            # 8. ANÁLISE VIA IA: Calcular métricas de qualidade
            quality_metrics = await self._calculate_aim_quality_metrics_ai(
                enriched_context, main_aim, subsidiary_aims
            )
            
            # 9. ANÁLISE VIA IA: Avaliar confiança da análise
            confidence_score = await self._assess_analysis_confidence_ai(
                enriched_context, quality_metrics
            )
            
            # 10. Construir UnitAims
            unit_aims = UnitAims(
                main_aim=main_aim,
                subsidiary_aims=subsidiary_aims,
                aim_type=AimType(main_aim_type),
                learning_objectives=learning_objectives,
                communicative_goals=communicative_goals,
                assessment_criteria=assessment_criteria,
                cefr_appropriateness=quality_metrics.get("cefr_appropriateness", 0.8),
                context_relevance=quality_metrics.get("context_relevance", 0.8),
                progression_alignment=quality_metrics.get("progression_alignment", 0.8),
                confidence_score=confidence_score,
                generated_at=datetime.now()
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Objetivos detectados: 1 principal + {len(subsidiary_aims)} subsidiários em {generation_time:.2f}s"
            )
            
            return unit_aims
            
        except ValidationError as e:
            logger.error(f"❌ Erro de validação Pydantic 2: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro na detecção de objetivos: {str(e)}")
            raise
    
    async def _build_pedagogical_context(self, request: AimDetectionRequest) -> Dict[str, Any]:
        """Construir contexto pedagógico enriquecido para análise de objetivos."""
        
        unit_data = request.unit_data
        content_data = request.content_data
        hierarchy_context = request.hierarchy_context
        rag_context = request.rag_context
        images_analysis = request.images_analysis
        
        # Extrair vocabulário da unidade
        vocabulary_items = []
        vocabulary_count = 0
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"]
            vocabulary_count = len(vocabulary_items)
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_items[:15]]
        
        # Extrair estratégias aplicadas
        applied_strategies = []
        strategy_info = ""
        
        if content_data.get("tips"):
            strategy_info = f"TIPS: {content_data['tips'].get('strategy', '')}"
            applied_strategies.append("tips")
        elif content_data.get("grammar"):
            strategy_info = f"GRAMMAR: {content_data['grammar'].get('strategy', '')}"
            applied_strategies.append("grammar")
        
        # Extrair sentences
        sentences_count = 0
        if content_data.get("sentences") and content_data["sentences"].get("sentences"):
            sentences_count = len(content_data["sentences"]["sentences"])
        
        # Análise de imagens
        image_context = ""
        if images_analysis.get("success"):
            themes = []
            for analysis in images_analysis.get("individual_analyses", []):
                if "structured_data" in analysis.get("analysis", {}):
                    analysis_themes = analysis["analysis"]["structured_data"].get("contextual_themes", [])
                    themes.extend(analysis_themes)
            
            if themes:
                image_context = f"Image themes: {', '.join(list(set(themes))[:5])}"
        
        enriched_context = {
            "unit_info": {
                "title": unit_data.get("title", ""),
                "context": unit_data.get("context", ""),
                "cefr_level": unit_data.get("cefr_level", "A2"),
                "unit_type": unit_data.get("unit_type", "lexical_unit"),
                "language_variant": unit_data.get("language_variant", "american_english"),
                "existing_main_aim": unit_data.get("main_aim", ""),
                "existing_subsidiary_aims": unit_data.get("subsidiary_aims", [])
            },
            "content_analysis": {
                "vocabulary_count": vocabulary_count,
                "vocabulary_words": vocabulary_words,
                "vocabulary_items": vocabulary_items,
                "sentences_count": sentences_count,
                "applied_strategies": applied_strategies,
                "strategy_info": strategy_info,
                "has_assessments": bool(content_data.get("assessments")),
                "image_context": image_context
            },
            "hierarchy_info": {
                "course_name": hierarchy_context.get("course_name", ""),
                "book_name": hierarchy_context.get("book_name", ""),
                "sequence_order": hierarchy_context.get("sequence_order", 1),
                "target_level": hierarchy_context.get("target_level", unit_data.get("cefr_level"))
            },
            "progression_context": {
                "taught_vocabulary": rag_context.get("taught_vocabulary", [])[:10],
                "used_strategies": rag_context.get("used_strategies", []),
                "progression_level": rag_context.get("progression_level", "intermediate"),
                "total_units_in_sequence": hierarchy_context.get("sequence_order", 1)
            }
        }
        
        return enriched_context
    
    # =============================================================================
    # ANÁLISES VIA IA (SUBSTITUEM LÓGICA HARD-CODED)
    # =============================================================================
    
    async def _detect_main_aim_type_ai(self, enriched_context: Dict[str, Any]) -> str:
        """Detectar tipo principal do objetivo via análise IA (lexis vs grammar)."""
        
        system_prompt = """Você é um especialista em análise pedagógica de unidades de inglês.
        
        Analise o conteúdo da unidade e determine se o foco principal é LEXICAL (vocabulário) ou GRAMATICAL (gramática).
        
        Considere: vocabulário, estratégias aplicadas, contexto, tipo declarado da unidade."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Analise esta unidade e determine o tipo principal do objetivo:
        
        UNIDADE:
        - Título: {unit_info['title']}
        - Contexto: {unit_info['context']}
        - Tipo declarado: {unit_info['unit_type']}
        - Nível: {unit_info['cefr_level']}
        
        CONTEÚDO:
        - Vocabulário: {content_analysis['vocabulary_count']} palavras
        - Palavras: {', '.join(content_analysis['vocabulary_words'][:8])}
        - Estratégias: {content_analysis['strategy_info']}
        - Sentences: {content_analysis['sentences_count']}
        
        ANÁLISE REQUERIDA:
        1. O foco principal é vocabulário (lexis) ou estruturas gramaticais (grammar)?
        2. Considere o tipo declarado, mas analise o conteúdo real
        3. Se há estratégias TIPS = lexical, GRAMMAR = grammatical
        4. Volume de vocabulário vs. estruturas gramaticais
        
        Retorne APENAS: "lexis" ou "grammar" """
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            detected_type = response.content.strip().lower()
            
            # Validar resposta
            if "lexis" in detected_type:
                return "lexis"
            elif "grammar" in detected_type:
                return "grammar"
            else:
                # Fallback baseado no tipo declarado
                unit_type = unit_info.get("unit_type", "lexical_unit")
                return "lexis" if "lexical" in unit_type else "grammar"
                
        except Exception as e:
            logger.warning(f"Erro na detecção de tipo via IA: {str(e)}")
            # Fallback técnico
            return self._fallback_aim_type_detection(enriched_context)
    
    async def _generate_main_aim_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim_type: str
    ) -> str:
        """Gerar objetivo principal via análise IA contextual."""
        
        system_prompt = f"""Você é um especialista em redação de objetivos pedagógicos para ensino de inglês.
        
        Crie um objetivo principal claro, específico e mensurável para uma unidade do tipo {main_aim_type}.
        
        Use a fórmula: "Students will be able to [action] [content] [context/condition]"."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        hierarchy_info = enriched_context["hierarchy_info"]
        
        human_prompt = f"""Crie o objetivo principal para esta unidade:
        
        UNIDADE:
        - Título: {unit_info['title']}
        - Contexto: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Tipo: {main_aim_type}
        
        CONTEÚDO:
        - Vocabulário: {content_analysis['vocabulary_count']} palavras relacionadas a {unit_info['context']}
        - Estratégia: {content_analysis['strategy_info']}
        - Sequência: Unidade {hierarchy_info['sequence_order']} do {hierarchy_info['book_name']}
        
        DIRETRIZES:
        1. Para tipo LEXIS: foque no vocabulário e seu uso comunicativo
        2. Para tipo GRAMMAR: foque nas estruturas gramaticais e aplicação
        3. Seja específico ao contexto "{unit_info['context']}"
        4. Adeque ao nível {unit_info['cefr_level']}
        5. Torne mensurável e alcançável
        
        Exemplo formato: "Students will be able to use hotel reservation vocabulary to make bookings and inquire about services in formal hospitality contexts."
        
        Crie o objetivo principal agora:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            main_aim = response.content.strip()
            
            # Validar e melhorar se necessário
            if len(main_aim) < 30:
                main_aim = await self._enhance_main_aim_ai(main_aim, enriched_context)
            
            return main_aim
            
        except Exception as e:
            logger.warning(f"Erro na geração do objetivo principal via IA: {str(e)}")
            return self._fallback_main_aim_generation(enriched_context, main_aim_type)
    
    async def _generate_subsidiary_aims_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim: str,
        main_aim_type: str
    ) -> List[str]:
        """Gerar objetivos subsidiários via análise IA."""
        
        system_prompt = f"""Você é um especialista em design curricular para ensino de inglês.
        
        Crie 3-5 objetivos subsidiários que complementem o objetivo principal, cobrindo aspectos como:
        - Gramática/estruturas (se principal for lexical)
        - Vocabulário específico (se principal for gramatical)  
        - Funções comunicativas
        - Consciência fonética
        - Competência cultural
        
        Cada objetivo deve ser específico e mensurável."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Crie objetivos subsidiários para complementar este objetivo principal:
        
        OBJETIVO PRINCIPAL: {main_aim}
        TIPO: {main_aim_type}
        
        CONTEXTO:
        - Unidade: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Vocabulário: {', '.join(content_analysis['vocabulary_words'][:8])}
        - Estratégia: {content_analysis['strategy_info']}
        
        CRIE 3-5 OBJETIVOS SUBSIDIÁRIOS que:
        1. Complementem o objetivo principal
        2. Cubram diferentes aspectos (gramática, funções, pronúncia, cultura)
        3. Sejam específicos ao contexto "{unit_info['context']}"
        4. Sejam apropriados para {unit_info['cefr_level']}
        
        Formato: Lista simples, um objetivo por linha
        Exemplo:
        - Apply polite language structures in hospitality interactions
        - Demonstrate correct pronunciation of key hotel vocabulary
        - Recognize cultural norms in customer service situations
        
        Liste os objetivos subsidiários:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair objetivos da resposta
            subsidiary_aims = self._parse_subsidiary_aims_from_response(response.content)
            
            # Garantir 3-5 objetivos
            if len(subsidiary_aims) < 3:
                additional_aims = await self._generate_additional_aims_ai(
                    enriched_context, main_aim, 3 - len(subsidiary_aims)
                )
                subsidiary_aims.extend(additional_aims)
            
            return subsidiary_aims[:5]  # Máximo 5
            
        except Exception as e:
            logger.warning(f"Erro na geração de objetivos subsidiários via IA: {str(e)}")
            return self._fallback_subsidiary_aims_generation(enriched_context, main_aim_type)
    
    async def _structure_learning_objectives_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim: str,
        subsidiary_aims: List[str]
    ) -> List[LearningObjective]:
        """Estruturar objetivos de aprendizagem usando análise IA."""
        
        system_prompt = """Você é um especialista em Taxonomia de Bloom e objetivos de aprendizagem.
        
        Analise os objetivos e classifique cada um segundo:
        - Categoria (lexical/grammatical/functional/phonetic/cultural/strategic)
        - Nível de Bloom (remember/understand/apply/analyze/evaluate/create)
        - Mensurabilidade (true/false)
        - Adequação ao nível CEFR"""
        
        unit_info = enriched_context["unit_info"]
        all_aims = [main_aim] + subsidiary_aims
        
        human_prompt = f"""Analise e classifique estes objetivos:
        
        OBJETIVOS:
        1. {main_aim} (PRINCIPAL)
        {chr(10).join([f"{i+2}. {aim}" for i, aim in enumerate(subsidiary_aims)])}
        
        CONTEXTO:
        - Nível CEFR: {unit_info['cefr_level']}
        - Contexto: {unit_info['context']}
        
        Para cada objetivo, retorne em formato JSON:
        {{
          "objectives": [
            {{
              "objective": "texto do objetivo",
              "type": "main" ou "subsidiary", 
              "category": "lexical|grammatical|functional|phonetic|cultural|strategic",
              "measurable": true/false,
              "achievable_level": "nível CEFR apropriado",
              "bloom_level": "remember|understand|apply|analyze|evaluate|create"
            }}
          ]
        }}
        
        Analise todos os objetivos agora:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                if "```json" in response.content:
                    json_content = response.content.split("```json")[1].split("```")[0].strip()
                else:
                    json_content = response.content
                
                objectives_data = json.loads(json_content)
                
                learning_objectives = []
                for obj_data in objectives_data.get("objectives", []):
                    try:
                        learning_obj = LearningObjective(**obj_data)
                        learning_objectives.append(learning_obj)
                    except ValidationError as e:
                        logger.warning(f"Objetivo inválido ignorado: {str(e)}")
                
                return learning_objectives
                
            except json.JSONDecodeError:
                logger.warning("Erro no parsing JSON dos objetivos estruturados")
                return self._fallback_structure_objectives(main_aim, subsidiary_aims, unit_info)
                
        except Exception as e:
            logger.warning(f"Erro na estruturação de objetivos via IA: {str(e)}")
            return self._fallback_structure_objectives(main_aim, subsidiary_aims, unit_info)
    
    async def _generate_communicative_goals_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim_type: str
    ) -> List[str]:
        """Gerar objetivos comunicativos via análise IA."""
        
        system_prompt = """Você é um especialista em competência comunicativa para ensino de inglês.
        
        Crie objetivos comunicativos específicos que descrevam o que os estudantes poderão FAZER comunicativamente."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Crie objetivos comunicativos para:
        
        CONTEXTO: {unit_info['context']}
        NÍVEL: {unit_info['cefr_level']}
        TIPO: {main_aim_type}
        VOCABULÁRIO: {', '.join(content_analysis['vocabulary_words'][:8])}
        
        Crie 3-4 objetivos comunicativos específicos no formato:
        "Students will communicate [what] in [context] situations"
        
        Foque no que estudantes FARÃO comunicativamente:
        - Interações específicas do contexto
        - Funções comunicativas relevantes
        - Situações reais de uso
        
        Exemplo para hotel:
        - Students will make hotel reservations by phone and email
        - Students will handle check-in procedures at hotel reception
        - Students will inquire about hotel services and facilities
        
        Crie objetivos comunicativos para "{unit_info['context']}":"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair objetivos comunicativos
            communicative_goals = []
            lines = response.content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or 
                           'students will' in line.lower()):
                    cleaned_line = line.lstrip('-•').strip()
                    if len(cleaned_line) > 20:  # Filtrar linhas muito curtas
                        communicative_goals.append(cleaned_line)
            
            return communicative_goals[:4]  # Máximo 4
            
        except Exception as e:
            logger.warning(f"Erro na geração de objetivos comunicativos via IA: {str(e)}")
            return self._fallback_communicative_goals(enriched_context, main_aim_type)
    
    async def _define_assessment_criteria_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim: str,
        subsidiary_aims: List[str]
    ) -> List[str]:
        """Definir critérios de avaliação via análise IA."""
        
        system_prompt = """Você é um especialista em avaliação pedagógica para ensino de inglês.
        
        Crie critérios específicos e mensuráveis para avaliar o alcance dos objetivos."""
        
        unit_info = enriched_context["unit_info"]
        
        human_prompt = f"""Defina critérios de avaliação para estes objetivos:
        
        OBJETIVO PRINCIPAL: {main_aim}
        
        OBJETIVOS SUBSIDIÁRIOS:
        {chr(10).join([f"- {aim}" for aim in subsidiary_aims])}
        
        CONTEXTO:
        - Nível: {unit_info['cefr_level']}
        - Contexto: {unit_info['context']}
        
        Crie 4-6 critérios específicos que permitam avaliar se os objetivos foram alcançados:
        
        Formato desejado:
        - Critério mensurável e observável
        - Relacionado aos objetivos específicos
        - Apropriado para {unit_info['cefr_level']}
        
        Exemplo:
        - Students correctly use 80% of hotel vocabulary in role-play scenarios
        - Students demonstrate accurate pronunciation of key terms
        - Students complete reservation dialogues with appropriate politeness markers
        
        Defina critérios de avaliação:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair critérios
            assessment_criteria = []
            lines = response.content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or 
                           'students' in line.lower()):
                    cleaned_line = line.lstrip('-•').strip()
                    if len(cleaned_line) > 25:  # Filtrar critérios muito curtos
                        assessment_criteria.append(cleaned_line)
            
            return assessment_criteria[:6]  # Máximo 6
            
        except Exception as e:
            logger.warning(f"Erro na definição de critérios via IA: {str(e)}")
            return self._fallback_assessment_criteria(enriched_context)
    
    async def _calculate_aim_quality_metrics_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim: str,
        subsidiary_aims: List[str]
    ) -> Dict[str, float]:
        """Calcular métricas de qualidade dos objetivos via análise IA."""
        
        system_prompt = """Você é um especialista em avaliação de qualidade de objetivos pedagógicos.
        
        Avalie os objetivos numa escala de 0.0 a 1.0 em três dimensões:
        - Adequação ao nível CEFR
        - Relevância ao contexto específico
        - Alinhamento com progressão pedagógica"""
        
        unit_info = enriched_context["unit_info"]
        hierarchy_info = enriched_context["hierarchy_info"]
        
        human_prompt = f"""Avalie a qualidade destes objetivos:
        
        OBJETIVO PRINCIPAL: {main_aim}
        OBJETIVOS SUBSIDIÁRIOS: {'; '.join(subsidiary_aims)}
        
        CONTEXTO:
        - Nível: {unit_info['cefr_level']}
        - Contexto: {unit_info['context']}
        - Sequência: Unidade {hierarchy_info['sequence_order']}
        
        Avalie (escala 0.0 a 1.0):
        1. CEFR Appropriateness: Quão adequados são para {unit_info['cefr_level']}?
        2. Context Relevance: Quão relevantes para "{unit_info['context']}"?
        3. Progression Alignment: Quão bem se alinham com progressão pedagógica?
        
        Retorne em formato JSON:
        {{
          "cefr_appropriateness": 0.8,
          "context_relevance": 0.9,
          "progression_alignment": 0.7
        }}
        
        Avalie agora:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON
            try:
                if "```json" in response.content:
                    json_content = response.content.split("```json")[1].split("```")[0].strip()
                else:
                    json_content = response.content
                
                metrics = json.loads(json_content)
                
                # Validar scores
                for key in ["cefr_appropriateness", "context_relevance", "progression_alignment"]:
                    if key in metrics:
                        metrics[key] = max(0.0, min(1.0, float(metrics[key])))
                    else:
                        metrics[key] = 0.8  # Default
                
                return metrics
                
            except (json.JSONDecodeError, ValueError):
                logger.warning("Erro no parsing das métricas de qualidade")
                return {"cefr_appropriateness": 0.8, "context_relevance": 0.8, "progression_alignment": 0.8}
                
        except Exception as e:
            logger.warning(f"Erro no cálculo de métricas via IA: {str(e)}")
            return {"cefr_appropriateness": 0.8, "context_relevance": 0.8, "progression_alignment": 0.8}
    
    async def _assess_analysis_confidence_ai(
        self, 
        enriched_context: Dict[str, Any], 
        quality_metrics: Dict[str, float]
    ) -> float:
        """Avaliar confiança da análise via IA."""
        
        system_prompt = """Você é um especialista em autoavaliação de análises pedagógicas.
        
        Avalie sua própria confiança na análise de objetivos considerando a qualidade dos dados de entrada."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Avalie sua confiança na análise de objetivos para:
        
        DADOS DISPONÍVEIS:
        - Título: {"✓" if unit_info['title'] else "✗"} {unit_info['title']}
        - Contexto: {"✓" if unit_info['context'] else "✗"} {unit_info['context']}
        - Vocabulário: {content_analysis['vocabulary_count']} palavras
        - Estratégias: {"✓" if content_analysis['strategy_info'] else "✗"}
        - Imagens: {"✓" if content_analysis['image_context'] else "✗"}
        
        MÉTRICAS CALCULADAS:
        - CEFR: {quality_metrics.get('cefr_appropriateness', 0.8):.2f}
        - Contexto: {quality_metrics.get('context_relevance', 0.8):.2f}
        - Progressão: {quality_metrics.get('progression_alignment', 0.8):.2f}
        
        Numa escala de 0.0 a 1.0, qual sua confiança na análise de objetivos?
        
        Considere:
        - Qualidade dos dados de entrada
        - Completude das informações
        - Coerência dos resultados
        
        Retorne APENAS um número decimal (ex: 0.85):"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair score numérico
            import re
            score_match = re.search(r'0\.\d+|1\.0', response.content)
            if score_match:
                confidence = float(score_match.group())
                return max(0.0, min(1.0, confidence))
            else:
                return 0.8  # Default
                
        except Exception as e:
            logger.warning(f"Erro na avaliação de confiança via IA: {str(e)}")
            return 0.8
    
    # =============================================================================
    # HELPER METHODS DE IA (MELHORIAS E COMPLEMENTOS)
    # =============================================================================
    
    async def _enhance_main_aim_ai(self, basic_aim: str, enriched_context: Dict[str, Any]) -> str:
        """Melhorar objetivo principal muito básico via IA."""
        
        system_prompt = """Você é um especialista em melhoria de objetivos pedagógicos.
        
        Expanda e melhore este objetivo básico para torná-lo mais específico e mensurável."""
        
        unit_info = enriched_context["unit_info"]
        
        human_prompt = f"""Melhore este objetivo muito básico:
        
        OBJETIVO BÁSICO: {basic_aim}
        
        CONTEXTO:
        - Unidade: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        
        Torne-o mais:
        - Específico ao contexto
        - Mensurável
        - Adequado ao nível
        - Profissionalmente redigido
        
        Retorne o objetivo melhorado:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            enhanced_aim = response.content.strip()
            
            return enhanced_aim if len(enhanced_aim) > len(basic_aim) else basic_aim
            
        except Exception as e:
            logger.warning(f"Erro na melhoria do objetivo via IA: {str(e)}")
            return basic_aim
    
    async def _generate_additional_aims_ai(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim: str,
        needed_count: int
    ) -> List[str]:
        """Gerar objetivos subsidiários adicionais via IA."""
        
        system_prompt = """Você é um especialista em completar currículos pedagógicos.
        
        Crie objetivos subsidiários adicionais para complementar o conjunto existente."""
        
        unit_info = enriched_context["unit_info"]
        
        human_prompt = f"""Crie {needed_count} objetivos subsidiários adicionais:
        
        OBJETIVO PRINCIPAL: {main_aim}
        CONTEXTO: {unit_info['context']}
        NÍVEL: {unit_info['cefr_level']}
        
        Crie {needed_count} objetivos que cubram aspectos ainda não abordados:
        - Pronúncia/fonética
        - Aspectos culturais
        - Estratégias de aprendizagem
        - Funções comunicativas específicas
        
        Liste um objetivo por linha:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            additional_aims = []
            lines = response.content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 20:
                    cleaned_line = line.lstrip('-•123456789.').strip()
                    if cleaned_line:
                        additional_aims.append(cleaned_line)
            
            return additional_aims[:needed_count]
            
        except Exception as e:
            logger.warning(f"Erro na geração de objetivos adicionais via IA: {str(e)}")
            return [f"Additional learning objective {i+1}" for i in range(needed_count)]
    
    # =============================================================================
    # FALLBACKS TÉCNICOS (APENAS PARA ERROS DE IA)
    # =============================================================================
    
    def _fallback_aim_type_detection(self, enriched_context: Dict[str, Any]) -> str:
        """Fallback técnico para detecção de tipo quando IA falha."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        # Análise técnica simples
        unit_type = unit_info.get("unit_type", "lexical_unit")
        strategy_info = content_analysis.get("strategy_info", "")
        vocabulary_count = content_analysis.get("vocabulary_count", 0)
        
        # Regras técnicas
        if "lexical" in unit_type or "tips" in strategy_info.lower():
            return "lexis"
        elif "grammar" in strategy_info.lower():
            return "grammar"
        elif vocabulary_count > 15:
            return "lexis"
        else:
            return "lexis"  # Default
    
    def _fallback_main_aim_generation(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim_type: str
    ) -> str:
        """Gerar objetivo principal fallback usando templates técnicos."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        cefr_level = unit_info["cefr_level"]
        context = unit_info["context"]
        vocab_count = content_analysis["vocabulary_count"]
        
        # Templates técnicos por nível e tipo
        templates = CEFR_OBJECTIVE_TEMPLATES.get(cefr_level, CEFR_OBJECTIVE_TEMPLATES["A2"])
        template = templates.get(main_aim_type, templates["lexical"])
        
        # Substituir placeholders
        main_aim = template.format(
            count=vocab_count,
            context=context,
            purpose="communicate effectively",
            grammar_point="relevant structures",
            function="express ideas"
        )
        
        return main_aim
    
    def _fallback_subsidiary_aims_generation(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim_type: str
    ) -> List[str]:
        """Gerar objetivos subsidiários fallback."""
        
        unit_info = enriched_context["unit_info"]
        context = unit_info["context"]
        cefr_level = unit_info["cefr_level"]
        
        # Templates técnicos básicos
        subsidiary_templates = [
            f"Apply appropriate language structures in {context} situations",
            f"Demonstrate correct pronunciation of key {context} vocabulary",
            f"Use polite and culturally appropriate language in {context}",
            f"Recognize and respond to common {context} interactions"
        ]
        
        # Adaptar ao nível CEFR
        if cefr_level in ["A1", "A2"]:
            subsidiary_templates = [aim.replace("Apply", "Use simple").replace("Demonstrate", "Practice") for aim in subsidiary_templates]
        elif cefr_level in ["C1", "C2"]:
            subsidiary_templates = [aim.replace("Apply", "Master").replace("Demonstrate", "Exhibit sophisticated") for aim in subsidiary_templates]
        
        return subsidiary_templates[:4]
    
    def _fallback_structure_objectives(
        self, 
        main_aim: str, 
        subsidiary_aims: List[str], 
        unit_info: Dict[str, Any]
    ) -> List[LearningObjective]:
        """Estruturar objetivos fallback usando classificação técnica."""
        
        learning_objectives = []
        cefr_level = unit_info["cefr_level"]
        
        # Classificar objetivo principal
        main_obj = LearningObjective(
            objective=main_aim,
            type="main",
            category="lexical" if "vocabulary" in main_aim.lower() else "functional",
            measurable=True,
            achievable_level=cefr_level,
            bloom_level=BLOOM_CEFR_MAPPING.get(cefr_level, ["apply"])[0]
        )
        learning_objectives.append(main_obj)
        
        # Classificar objetivos subsidiários
        categories = ["grammatical", "phonetic", "cultural", "strategic"]
        bloom_levels = BLOOM_CEFR_MAPPING.get(cefr_level, ["apply"])
        
        for i, aim in enumerate(subsidiary_aims):
            sub_obj = LearningObjective(
                objective=aim,
                type="subsidiary",
                category=categories[i % len(categories)],
                measurable=True,
                achievable_level=cefr_level,
                bloom_level=bloom_levels[i % len(bloom_levels)]
            )
            learning_objectives.append(sub_obj)
        
        return learning_objectives
    
    def _fallback_communicative_goals(
        self, 
        enriched_context: Dict[str, Any], 
        main_aim_type: str
    ) -> List[str]:
        """Gerar objetivos comunicativos fallback."""
        
        unit_info = enriched_context["unit_info"]
        context = unit_info["context"]
        
        # Templates comunicativos básicos
        communicative_templates = [
            f"Students will communicate effectively in {context} situations",
            f"Students will initiate and maintain conversations about {context}",
            f"Students will understand and respond appropriately in {context} interactions",
            f"Students will express opinions and preferences related to {context}"
        ]
        
        return communicative_templates
    
    def _fallback_assessment_criteria(self, enriched_context: Dict[str, Any]) -> List[str]:
        """Gerar critérios de avaliação fallback."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        context = unit_info["context"]
        vocab_count = content_analysis["vocabulary_count"]
        
        # Critérios técnicos básicos
        criteria = [
            f"Students correctly use 80% of {context} vocabulary in activities",
            f"Students demonstrate appropriate pronunciation of key terms",
            f"Students complete {context} role-plays with cultural appropriateness",
            f"Students respond accurately to {context} comprehension questions"
        ]
        
        if vocab_count > 20:
            criteria.append(f"Students recognize and define {vocab_count} vocabulary items")
        
        return criteria
    
    # =============================================================================
    # PARSER HELPERS
    # =============================================================================
    
    def _parse_subsidiary_aims_from_response(self, response_content: str) -> List[str]:
        """Parser técnico para extrair objetivos subsidiários da resposta IA."""
        
        subsidiary_aims = []
        lines = response_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Filtrar linhas com objetivos
            if line and (line.startswith('-') or line.startswith('•') or 
                        line.startswith(tuple('123456789')) or
                        'students will' in line.lower()):
                
                # Limpar marcadores
                cleaned_line = line.lstrip('-•123456789. ').strip()
                
                # Validar tamanho mínimo
                if len(cleaned_line) > 25 and 'students' in cleaned_line.lower():
                    subsidiary_aims.append(cleaned_line)
        
        return subsidiary_aims
    
    # =============================================================================
    # MÉTODOS PÚBLICOS UTILITÁRIOS
    # =============================================================================
    
    async def validate_existing_aims(
        self, 
        existing_aims: Dict[str, Any], 
        unit_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validar objetivos existentes e sugerir melhorias."""
        
        system_prompt = """Você é um especialista em revisão de objetivos pedagógicos.
        
        Analise os objetivos existentes e sugira melhorias específicas."""
        
        human_prompt = f"""Analise estes objetivos existentes:
        
        OBJETIVO PRINCIPAL: {existing_aims.get('main_aim', 'Não definido')}
        OBJETIVOS SUBSIDIÁRIOS: {existing_aims.get('subsidiary_aims', [])}
        
        CONTEXTO DA UNIDADE: {unit_context.get('context', '')}
        NÍVEL: {unit_context.get('cefr_level', 'A2')}
        
        Avalie e sugira melhorias:
        1. Clareza e especificidade
        2. Mensurabilidade
        3. Adequação ao nível CEFR
        4. Relevância ao contexto
        
        Retorne análise e sugestões de melhoria."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            return {
                "validation_result": response.content,
                "needs_improvement": "melhoria" in response.content.lower() or "sugiro" in response.content.lower(),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f"Erro na validação de objetivos existentes: {str(e)}")
            return {
                "validation_result": "Validação não disponível no momento",
                "needs_improvement": False,
                "analysis_timestamp": datetime.now().isoformat()
            }
    
    async def suggest_progression_aims(
        self, 
        current_aims: UnitAims, 
        next_unit_context: Dict[str, Any]
    ) -> List[str]:
        """Sugerir objetivos para próxima unidade baseado na progressão."""
        
        system_prompt = """Você é um especialista em progressão curricular.
        
        Sugira objetivos para a próxima unidade que construam sobre os objetivos atuais."""
        
        human_prompt = f"""Baseado nestes objetivos atuais:
        
        UNIDADE ATUAL:
        - Principal: {current_aims.main_aim}
        - Subsidiários: {current_aims.subsidiary_aims}
        
        PRÓXIMA UNIDADE:
        - Contexto: {next_unit_context.get('context', '')}
        - Nível: {next_unit_context.get('cefr_level', 'A2')}
        
        Sugira objetivos para a próxima unidade que:
        1. Construam sobre o aprendizado atual
        2. Avancem a complexidade appropriadamente
        3. Sejam relevantes ao novo contexto
        
        Sugira 3-4 objetivos para progressão:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair sugestões
            suggestions = []
            lines = response.content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or 
                           'students will' in line.lower()):
                    cleaned_line = line.lstrip('-•123456789. ').strip()
                    if len(cleaned_line) > 20:
                        suggestions.append(cleaned_line)
            
            return suggestions[:4]
            
        except Exception as e:
            logger.warning(f"Erro na sugestão de progressão: {str(e)}")
            return [
                "Continue developing vocabulary in new contexts",
                "Apply learned structures in more complex situations", 
                "Integrate cultural awareness with language use",
                "Demonstrate increased fluency and accuracy"
            ]
    
    async def analyze_aims_effectiveness(
        self, 
        unit_aims: UnitAims, 
        assessment_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analisar eficácia dos objetivos baseado em resultados de avaliação."""
        
        system_prompt = """Você é um especialista em análise de eficácia pedagógica.
        
        Analise se os objetivos foram eficazes baseado nos resultados de avaliação."""
        
        human_prompt = f"""Analise a eficácia destes objetivos:
        
        OBJETIVOS:
        - Principal: {unit_aims.main_aim}
        - Subsidiários: {unit_aims.subsidiary_aims}
        
        RESULTADOS DE AVALIAÇÃO:
        {json.dumps(assessment_results, indent=2)}
        
        CRITÉRIOS DEFINIDOS:
        {unit_aims.assessment_criteria}
        
        Analise:
        1. Foram os objetivos alcançados?
        2. Que evidências suportam isso?
        3. Que melhorias são necessárias?
        4. Recomendações para próximas unidades?
        
        Forneça análise detalhada da eficácia:"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            return {
                "effectiveness_analysis": response.content,
                "objectives_achieved": "alcançados" in response.content.lower(),
                "improvement_suggestions": "melhorias" in response.content.lower(),
                "analysis_timestamp": datetime.now().isoformat(),
                "confidence_score": unit_aims.confidence_score
            }
            
        except Exception as e:
            logger.warning(f"Erro na análise de eficácia: {str(e)}")
            return {
                "effectiveness_analysis": "Análise não disponível",
                "objectives_achieved": None,
                "improvement_suggestions": True,
                "analysis_timestamp": datetime.now().isoformat(),
                "confidence_score": 0.5
            }
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Obter status do serviço."""
        return {
            "service": "AimDetectorService",
            "status": "active",
            "ai_integration": "100% contextual analysis",
            "supported_aim_types": ["lexis", "grammar"],
            "bloom_taxonomy": "integrated",
            "cefr_levels": list(BLOOM_CEFR_MAPPING.keys()),
            "objective_categories": list(OBJECTIVE_CATEGORIES.keys()),
            "ai_analysis_methods": [
                "_detect_main_aim_type_ai",
                "_generate_main_aim_ai",
                "_generate_subsidiary_aims_ai", 
                "_structure_learning_objectives_ai",
                "_generate_communicative_goals_ai",
                "_define_assessment_criteria_ai",
                "_calculate_aim_quality_metrics_ai",
                "_assess_analysis_confidence_ai"
            ],
            "llm_model": self.openai_config.openai_model,
            "template_support": "CEFR-based templates with AI enhancement"
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def detect_unit_aims(detection_params: Dict[str, Any]) -> UnitAims:
    """
    Função utilitária para detectar objetivos de uma unidade.
    
    Args:
        detection_params: Parâmetros com contexto da unidade
        
    Returns:
        UnitAims completo
    """
    detector = AimDetectorService()
    return await detector.detect_and_generate_aims(detection_params)


async def validate_aims_quality(unit_aims: UnitAims, unit_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validar qualidade dos objetivos detectados.
    
    Args:
        unit_aims: Objetivos a validar
        unit_context: Contexto da unidade
        
    Returns:
        Relatório de validação
    """
    detector = AimDetectorService()
    
    existing_aims = {
        "main_aim": unit_aims.main_aim,
        "subsidiary_aims": unit_aims.subsidiary_aims
    }
    
    return await detector.validate_existing_aims(existing_aims, unit_context)


def analyze_aims_bloom_distribution(learning_objectives: List[LearningObjective]) -> Dict[str, Any]:
    """
    Analisar distribuição dos objetivos na Taxonomia de Bloom.
    
    Args:
        learning_objectives: Lista de objetivos estruturados
        
    Returns:
        Análise da distribuição
    """
    bloom_distribution = {}
    category_distribution = {}
    
    for obj in learning_objectives:
        # Distribuição por nível de Bloom
        bloom_level = obj.bloom_level
        bloom_distribution[bloom_level] = bloom_distribution.get(bloom_level, 0) + 1
        
        # Distribuição por categoria
        category = obj.category
        category_distribution[category] = category_distribution.get(category, 0) + 1
    
    total_objectives = len(learning_objectives)
    
    return {
        "bloom_distribution": bloom_distribution,
        "bloom_percentages": {
            level: (count / total_objectives) * 100 
            for level, count in bloom_distribution.items()
        },
        "category_distribution": category_distribution,
        "category_percentages": {
            category: (count / total_objectives) * 100 
            for category, count in category_distribution.items()
        },
        "total_objectives": total_objectives,
        "bloom_complexity_score": sum(
            ["remember", "understand", "apply", "analyze", "evaluate", "create"].index(obj.bloom_level) + 1
            for obj in learning_objectives if obj.bloom_level in ["remember", "understand", "apply", "analyze", "evaluate", "create"]
        ) / total_objectives if total_objectives > 0 else 0
    }


def create_aims_summary_report(unit_aims: UnitAims) -> str:
    """
    Criar relatório resumido dos objetivos.
    
    Args:
        unit_aims: Objetivos da unidade
        
    Returns:
        Relatório formatado
    """
    report_lines = [
        "UNIT LEARNING OBJECTIVES SUMMARY",
        "=" * 40,
        "",
        f"Main Aim Type: {unit_aims.aim_type.value.upper()}",
        f"Confidence Score: {unit_aims.confidence_score:.2f}",
        f"Generated: {unit_aims.generated_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "MAIN OBJECTIVE:",
        f"• {unit_aims.main_aim}",
        "",
        "SUBSIDIARY OBJECTIVES:",
    ]
    
    for i, aim in enumerate(unit_aims.subsidiary_aims, 1):
        report_lines.append(f"{i}. {aim}")
    
    report_lines.extend([
        "",
        "COMMUNICATIVE GOALS:",
    ])
    
    for goal in unit_aims.communicative_goals:
        report_lines.append(f"• {goal}")
    
    report_lines.extend([
        "",
        "ASSESSMENT CRITERIA:",
    ])
    
    for criterion in unit_aims.assessment_criteria:
        report_lines.append(f"• {criterion}")
    
    # Métricas de qualidade
    report_lines.extend([
        "",
        "QUALITY METRICS:",
        f"• CEFR Appropriateness: {unit_aims.cefr_appropriateness:.1%}",
        f"• Context Relevance: {unit_aims.context_relevance:.1%}",
        f"• Progression Alignment: {unit_aims.progression_alignment:.1%}",
        ""
    ])
    
    # Análise de distribuição se houver objetivos estruturados
    if unit_aims.learning_objectives:
        bloom_analysis = analyze_aims_bloom_distribution(unit_aims.learning_objectives)
        report_lines.extend([
            "BLOOM'S TAXONOMY DISTRIBUTION:",
            f"• Complexity Score: {bloom_analysis['bloom_complexity_score']:.1f}/6.0"
        ])
        
        for level, percentage in bloom_analysis['bloom_percentages'].items():
            report_lines.append(f"• {level.title()}: {percentage:.0f}%")
    
    return "\n".join(report_lines)


def extract_measurable_outcomes(unit_aims: UnitAims) -> List[str]:
    """
    Extrair resultados mensuráveis dos objetivos.
    
    Args:
        unit_aims: Objetivos da unidade
        
    Returns:
        Lista de resultados mensuráveis
    """
    measurable_outcomes = []
    
    # Extrair do objetivo principal
    main_aim = unit_aims.main_aim
    if "will be able to" in main_aim:
        outcome = main_aim.split("will be able to")[-1].strip()
        measurable_outcomes.append(f"Main: {outcome}")
    
    # Extrair dos objetivos subsidiários
    for i, aim in enumerate(unit_aims.subsidiary_aims, 1):
        if "will" in aim.lower():
            # Extrair ação mensurável
            if "will be able to" in aim:
                outcome = aim.split("will be able to")[-1].strip()
            elif "will" in aim:
                outcome = aim.split("will")[-1].strip()
            else:
                outcome = aim
            
            measurable_outcomes.append(f"Sub {i}: {outcome}")
    
    # Adicionar critérios de avaliação como outcomes
    for criterion in unit_aims.assessment_criteria:
        if any(word in criterion.lower() for word in ["correctly", "accurately", "demonstrate", "complete"]):
            measurable_outcomes.append(f"Assessment: {criterion}")
    
    return measurable_outcomes


async def suggest_aims_improvement(
    current_aims: UnitAims, 
    improvement_areas: List[str]
) -> Dict[str, List[str]]:
    """
    Sugerir melhorias específicas para os objetivos.
    
    Args:
        current_aims: Objetivos atuais
        improvement_areas: Áreas que precisam melhoria
        
    Returns:
        Sugestões de melhoria por área
    """
    detector = AimDetectorService()
    
    system_prompt = """Você é um especialista em melhoria de objetivos pedagógicos.
    
    Forneça sugestões específicas e práticas para melhorar os objetivos nas áreas identificadas."""
    
    human_prompt = f"""Sugira melhorias para estes objetivos:
    
    OBJETIVOS ATUAIS:
    - Principal: {current_aims.main_aim}
    - Subsidiários: {'; '.join(current_aims.subsidiary_aims)}
    
    ÁREAS PARA MELHORIA: {', '.join(improvement_areas)}
    
    Para cada área, forneça 2-3 sugestões específicas de melhoria.
    
    Formato:
    ÁREA 1: [nome da área]
    - Sugestão específica 1
    - Sugestão específica 2
    
    Forneça sugestões práticas e implementáveis:"""
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await detector.llm.ainvoke(messages)
        
        # Parse das sugestões por área
        suggestions = {}
        current_area = None
        
        lines = response.content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if any(area.lower() in line.lower() for area in improvement_areas):
                current_area = line.split(':')[0].strip()
                suggestions[current_area] = []
            elif line.startswith('-') and current_area:
                suggestion = line.lstrip('- ').strip()
                if suggestion:
                    suggestions[current_area].append(suggestion)
        
        return suggestions
        
    except Exception as e:
        logger.warning(f"Erro na geração de sugestões de melhoria: {str(e)}")
        
        # Sugestões genéricas de fallback
        fallback_suggestions = {}
        for area in improvement_areas:
            fallback_suggestions[area] = [
                f"Review {area} alignment with CEFR standards",
                f"Increase specificity in {area} descriptions",
                f"Add measurable criteria for {area} assessment"
            ]
        
        return fallback_suggestions


def validate_aims_cefr_alignment(unit_aims: UnitAims, target_cefr: str) -> Dict[str, Any]:
    """
    Validar alinhamento dos objetivos com nível CEFR específico.
    
    Args:
        unit_aims: Objetivos a validar
        target_cefr: Nível CEFR alvo (A1, A2, B1, etc.)
        
    Returns:
        Análise de alinhamento CEFR
    """
    # Palavras-chave por nível CEFR
    cefr_keywords = {
        "A1": ["basic", "simple", "recognize", "understand", "use familiar"],
        "A2": ["everyday", "routine", "describe", "communicate about", "handle"],
        "B1": ["cope with", "express", "explain", "deal with", "produce"],
        "B2": ["interact", "present", "argue", "elaborate", "demonstrate fluency"],
        "C1": ["express fluently", "adapt", "sophisticated", "nuanced", "master"],
        "C2": ["near-native", "subtle", "precise", "effortless", "discriminate"]
    }
    
    expected_keywords = cefr_keywords.get(target_cefr, [])
    
    # Analisar alinhamento do objetivo principal
    main_aim_alignment = any(
        keyword in unit_aims.main_aim.lower() 
        for keyword in expected_keywords
    )
    
    # Analisar objetivos subsidiários
    subsidiary_alignment = []
    for aim in unit_aims.subsidiary_aims:
        alignment = any(
            keyword in aim.lower() 
            for keyword in expected_keywords
        )
        subsidiary_alignment.append(alignment)
    
    # Analisar complexidade via Bloom
    bloom_appropriate = True
    expected_bloom = BLOOM_CEFR_MAPPING.get(target_cefr, ["apply"])
    
    for obj in unit_aims.learning_objectives:
        if obj.bloom_level not in expected_bloom:
            bloom_appropriate = False
            break
    
    # Calcular score geral
    alignment_score = 0
    if main_aim_alignment:
        alignment_score += 0.4
    
    aligned_subsidiary = sum(subsidiary_alignment)
    if len(subsidiary_alignment) > 0:
        alignment_score += 0.4 * (aligned_subsidiary / len(subsidiary_alignment))
    
    if bloom_appropriate:
        alignment_score += 0.2
    
    return {
        "overall_alignment_score": alignment_score,
        "target_cefr": target_cefr,
        "main_aim_aligned": main_aim_alignment,
        "subsidiary_aims_aligned": aligned_subsidiary,
        "total_subsidiary_aims": len(subsidiary_alignment),
        "bloom_taxonomy_appropriate": bloom_appropriate,
        "expected_keywords": expected_keywords,
        "expected_bloom_levels": expected_bloom,
        "recommendations": [
            f"Include more {target_cefr}-appropriate keywords" if alignment_score < 0.7 else "Good CEFR alignment",
            f"Adjust Bloom taxonomy levels to {expected_bloom}" if not bloom_appropriate else "Appropriate cognitive complexity",
            f"Strengthen subsidiary aims alignment" if aligned_subsidiary < len(subsidiary_alignment) * 0.7 else "Well-aligned subsidiary objectives"
        ]
    }


# =============================================================================
# EXEMPLO DE USO E TESTE
# =============================================================================

async def test_aim_detector():
    """Função de teste para o AimDetector."""
    
    # Dados de exemplo
    detection_params = {
        "unit_data": {
            "title": "Hotel Reservations and Check-in",
            "context": "Making hotel reservations and handling check-in procedures",
            "cefr_level": "A2",
            "unit_type": "lexical_unit",
            "language_variant": "american_english"
        },
        "content_data": {
            "vocabulary": {
                "items": [
                    {"word": "reservation", "definition": "reserva"},
                    {"word": "reception", "definition": "recepção"},
                    {"word": "available", "definition": "disponível"},
                    {"word": "check-in", "definition": "fazer check-in"},
                    {"word": "guest", "definition": "hóspede"}
                ]
            },
            "sentences": {
                "sentences": [
                    {"text": "I'd like to make a reservation for tonight."},
                    {"text": "Is there a room available?"}
                ]
            },
            "tips": {
                "strategy": "chunks",
                "title": "Useful Chunks for Hotel Communication"
            }
        },
        "hierarchy_context": {
            "course_name": "English for Travel",
            "book_name": "Basic Travel English", 
            "sequence_order": 3,
            "target_level": "A2"
        },
        "rag_context": {
            "taught_vocabulary": ["hotel", "room", "night", "good", "help"],
            "used_strategies": ["substantivos_compostos"],
            "progression_level": "intermediate"
        },
        "images_analysis": {
            "success": True,
            "individual_analyses": [
                {
                    "analysis": {
                        "structured_data": {
                            "contextual_themes": ["hospitality", "customer_service", "travel"]
                        }
                    }
                }
            ]
        }
    }
    
    try:
        # Detectar objetivos
        detector = AimDetectorService()
        unit_aims = await detector.detect_and_generate_aims(detection_params)
        
        print("✅ Objetivos detectados com sucesso!")
        print(f"Tipo principal: {unit_aims.aim_type.value}")
        print(f"Objetivo principal: {unit_aims.main_aim}")
        print(f"Objetivos subsidiários: {len(unit_aims.subsidiary_aims)}")
        print(f"Score de confiança: {unit_aims.confidence_score:.2f}")
        
        # Criar relatório
        report = create_aims_summary_report(unit_aims)
        print("\n" + "="*50)
        print("RELATÓRIO DE OBJETIVOS:")
        print("="*50)
        print(report)
        
        # Validar alinhamento CEFR
        cefr_validation = validate_aims_cefr_alignment(unit_aims, "A2")
        print(f"\nAlinhamento CEFR A2: {cefr_validation['overall_alignment_score']:.1%}")
        
        return unit_aims
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return None


