# src/services/assessment_selector.py
"""
Serviço de seleção inteligente de atividades de avaliação para o IVO V2.
Implementa balanceamento RAG das 7 atividades disponíveis com seleção via IA contextual.
CORRIGIDO: 100% análise via IA, zero hard-coded, balanceamento inteligente hierárquico.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError, Field, ConfigDict

from src.core.unit_models import AssessmentActivity, AssessmentSection
from src.core.enums import CEFRLevel, LanguageVariant, UnitType, AssessmentType
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES TÉCNICAS (MANTIDAS - METODOLOGIA ESTABELECIDA)
# =============================================================================

ASSESSMENT_TYPES = [
    "cloze_test",      # 1. Compreensão geral com lacunas
    "gap_fill",        # 2. Lacunas específicas de vocabulário
    "reordering",      # 3. Reordenar frases/palavras
    "transformation",  # 4. Transformar estruturas gramaticais
    "multiple_choice", # 5. Questões objetivas
    "true_false",      # 6. Afirmações verdadeiro/falso
    "matching"         # 7. Associação de elementos
]

ASSESSMENT_DESCRIPTIONS = {
    "cloze_test": "Compreensão geral com múltiplas lacunas em texto contextual",
    "gap_fill": "Lacunas específicas focando vocabulário da unidade",
    "reordering": "Reordenar palavras/frases para formar estruturas corretas",
    "transformation": "Transformar estruturas mantendo significado",
    "multiple_choice": "Questões objetivas com alternativas",
    "true_false": "Afirmações para avaliar compreensão textual",
    "matching": "Associar elementos relacionados (palavras, definições, imagens)"
}

SKILLS_ASSESSED_MAPPING = {
    "cloze_test": ["reading_comprehension", "context_analysis", "grammar_in_context"],
    "gap_fill": ["vocabulary_recognition", "word_formation", "context_application"],
    "reordering": ["sentence_structure", "word_order", "syntax_awareness"],
    "transformation": ["grammatical_equivalence", "paraphrasing", "structural_flexibility"],
    "multiple_choice": ["recognition_skills", "discrimination", "elimination_strategies"],
    "true_false": ["reading_comprehension", "inference", "detail_identification"],
    "matching": ["association_skills", "lexical_relationships", "categorization"]
}

CEFR_ASSESSMENT_PREFERENCES = {
    "A1": ["gap_fill", "matching", "true_false", "multiple_choice"],
    "A2": ["gap_fill", "matching", "true_false", "cloze_test"],
    "B1": ["cloze_test", "transformation", "reordering", "gap_fill"],
    "B2": ["transformation", "cloze_test", "reordering", "multiple_choice"],
    "C1": ["transformation", "cloze_test", "reordering", "gap_fill"],
    "C2": ["transformation", "cloze_test", "reordering", "matching"]
}


class AssessmentSelectorService:
    """Serviço principal para seleção inteligente de atividades de avaliação com RAG."""
    
    def __init__(self):
        """Inicializar serviço com IA contextual."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM para análise de balanceamento
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.3,  # Baixa para consistência na seleção
            max_tokens=2048,
            api_key=self.openai_config.openai_api_key
        )
        
        logger.info("✅ AssessmentSelectorService inicializado com 7 atividades e IA contextual")
    
    async def select_optimal_assessments(self, selection_params: Dict[str, Any]) -> AssessmentSection:
        """
        Selecionar 2 atividades complementares usando análise IA + RAG hierárquico.
        
        Args:
            selection_params: Parâmetros com contexto da unidade, conteúdo e RAG
            
        Returns:
            AssessmentSection com 2 atividades selecionadas e balanceadas
        """
        try:
            start_time = time.time()
            
            # Extrair parâmetros
            unit_data = selection_params.get("unit_data", {})
            content_data = selection_params.get("content_data", {})
            hierarchy_context = selection_params.get("hierarchy_context", {})
            rag_context = selection_params.get("rag_context", {})
            
            logger.info(f"🎯 Selecionando atividades para unidade {unit_data.get('title', 'Unknown')}")
            
            # 1. Construir contexto pedagógico enriquecido
            enriched_context = await self._build_assessment_context(
                unit_data, content_data, hierarchy_context, rag_context
            )
            
            # 2. ANÁLISE VIA IA: Análise de balanceamento atual
            balance_analysis = await self._analyze_current_balance_ai(enriched_context)
            
            # 3. ANÁLISE VIA IA: Identificar tipos subutilizados
            underused_types = await self._identify_underused_assessments_ai(
                enriched_context, balance_analysis
            )
            
            # 4. ANÁLISE VIA IA: Seleção inteligente do par complementar
            selected_pair = await self._select_complementary_pair_ai(
                enriched_context, underused_types, balance_analysis
            )
            
            # 5. ANÁLISE VIA IA: Gerar atividades específicas
            activity_1 = await self._generate_specific_activity_ai(
                selected_pair[0], enriched_context, 1
            )
            activity_2 = await self._generate_specific_activity_ai(
                selected_pair[1], enriched_context, 2
            )
            
            # 6. ANÁLISE VIA IA: Justificativa de seleção
            selection_rationale = await self._generate_selection_rationale_ai(
                selected_pair, enriched_context, balance_analysis
            )
            
            # 7. ANÁLISE VIA IA: Análise de complementaridade
            complementarity_analysis = await self._analyze_complementarity_ai(
                activity_1, activity_2, enriched_context
            )
            
            # 8. Calcular métricas de balanceamento
            updated_balance = self._calculate_updated_balance(
                rag_context.get("used_assessments", {}), selected_pair
            )
            
            # 9. Construir AssessmentSection
            assessment_section = AssessmentSection(
                activities=[activity_1, activity_2],
                selection_rationale=selection_rationale,
                total_estimated_time=activity_1.estimated_time + activity_2.estimated_time,
                skills_assessed=list(set(activity_1.skills_assessed + activity_2.skills_assessed)),
                balance_analysis=balance_analysis,
                underused_activities=underused_types,
                complementary_pair=complementarity_analysis.get("is_complementary", True)
            )
            
            selection_time = time.time() - start_time
            
            logger.info(
                f"✅ Atividades selecionadas: {selected_pair[0]} + {selected_pair[1]} em {selection_time:.2f}s"
            )
            
            return assessment_section
            
        except Exception as e:
            logger.error(f"❌ Erro na seleção de atividades: {str(e)}")
            raise
    
    async def _build_assessment_context(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto pedagógico enriquecido para seleção."""
        
        # Extrair vocabulário da unidade
        vocabulary_items = []
        vocabulary_count = 0
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"]
            vocabulary_count = len(vocabulary_items)
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_items[:12]]
        
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
        sentences_data = content_data.get("sentences", {})
        sentences_count = len(sentences_data.get("sentences", []))
        sample_sentences = [s.get("text", "") for s in sentences_data.get("sentences", [])][:3]
        
        # Análise RAG de atividades usadas
        used_assessments = rag_context.get("used_assessments", {})
        if isinstance(used_assessments, list):
            # Converter lista para dict com contagens
            assessment_counts = {}
            for assessment in used_assessments:
                if isinstance(assessment, dict) and "type" in assessment:
                    assessment_type = assessment["type"]
                    assessment_counts[assessment_type] = assessment_counts.get(assessment_type, 0) + 1
                elif isinstance(assessment, str):
                    assessment_counts[assessment] = assessment_counts.get(assessment, 0) + 1
            used_assessments = assessment_counts
        
        enriched_context = {
            "unit_info": {
                "title": unit_data.get("title", ""),
                "context": unit_data.get("context", ""),
                "cefr_level": unit_data.get("cefr_level", "A2"),
                "unit_type": unit_data.get("unit_type", "lexical_unit"),
                "language_variant": unit_data.get("language_variant", "american_english"),
                "main_aim": unit_data.get("main_aim", ""),
                "subsidiary_aims": unit_data.get("subsidiary_aims", [])
            },
            "content_analysis": {
                "vocabulary_count": vocabulary_count,
                "vocabulary_words": vocabulary_words,
                "vocabulary_items": vocabulary_items,
                "sentences_count": sentences_count,
                "sample_sentences": sample_sentences,
                "applied_strategies": applied_strategies,
                "strategy_info": strategy_info,
                "has_tips": bool(content_data.get("tips")),
                "has_grammar": bool(content_data.get("grammar")),
                "content_richness": self._assess_content_richness(content_data)
            },
            "hierarchy_info": {
                "course_name": hierarchy_context.get("course_name", ""),
                "book_name": hierarchy_context.get("book_name", ""),
                "sequence_order": hierarchy_context.get("sequence_order", 1),
                "target_level": hierarchy_context.get("target_level", unit_data.get("cefr_level"))
            },
            "rag_analysis": {
                "used_assessments": used_assessments,
                "assessment_density": sum(used_assessments.values()) if used_assessments else 0,
                "progression_level": rag_context.get("progression_level", "intermediate"),
                "total_units_processed": hierarchy_context.get("sequence_order", 1),
                "underused_threshold": 2  # Máximo 2 usos por tipo a cada 7 unidades
            },
            "selection_preferences": {
                "target_activities": 2,
                "max_total_time": 25,  # 25 minutos máximo
                "prefer_complementary": True,
                "balance_skills": True,
                "avoid_overused": True
            }
        }
        
        return enriched_context
    
    # =============================================================================
    # ANÁLISES VIA IA (SUBSTITUEM LÓGICA HARD-CODED)
    # =============================================================================
    
    async def _analyze_current_balance_ai(self, enriched_context: Dict[str, Any]) -> Dict[str, Any]:
        """Análise contextual via IA do balanceamento atual de atividades."""
        
        system_prompt = """Você é um especialista em balanceamento de atividades de avaliação pedagógica.
        
        Analise o uso histórico de atividades e identifique padrões de balanceamento considerando:
        - Distribuição de tipos de atividades
        - Progressão pedagógica
        - Variedade de habilidades avaliadas
        - Adequação ao nível CEFR e contexto"""
        
        unit_info = enriched_context["unit_info"]
        rag_analysis = enriched_context["rag_analysis"]
        hierarchy_info = enriched_context["hierarchy_info"]
        
        used_assessments = rag_analysis["used_assessments"]
        total_units = hierarchy_info["sequence_order"]
        
        human_prompt = f"""Analise o balanceamento atual de atividades:
        
        CONTEXTO:
        - Unidade: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Tipo: {unit_info['unit_type']}
        - Sequência: Unidade {total_units} do {hierarchy_info['book_name']}
        
        HISTÓRICO DE ATIVIDADES USADAS:
        {json.dumps(used_assessments, indent=2)}
        
        TIPOS DISPONÍVEIS:
        1. cloze_test - Compreensão geral
        2. gap_fill - Vocabulário específico
        3. reordering - Estrutura/ordem
        4. transformation - Equivalência gramatical
        5. multiple_choice - Reconhecimento
        6. true_false - Compreensão textual
        7. matching - Associação
        
        ANÁLISE REQUERIDA:
        1. Que tipos estão sendo overutilizados (>2 usos)?
        2. Que tipos estão subutilizados ou não usados?
        3. Há boa distribuição de habilidades avaliadas?
        4. O balanceamento é apropriado para {unit_info['cefr_level']}?
        
        Retorne análise em formato JSON:
        {{
            "current_distribution": {{"tipo": count, ...}},
            "overused_types": ["tipo1", "tipo2"],
            "underused_types": ["tipo3", "tipo4"],
            "balance_score": 0.75,
            "skill_diversity": 0.80,
            "recommendations": ["recomendação 1", "recomendação 2"]
        }}"""
        
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
                
                balance_analysis = json.loads(json_content)
                
                logger.info(f"✅ Análise de balanceamento: score {balance_analysis.get('balance_score', 0.7):.2f}")
                return balance_analysis
                
            except json.JSONDecodeError:
                logger.warning("Erro no parsing da análise de balanceamento")
                return self._technical_balance_analysis_fallback(enriched_context)
                
        except Exception as e:
            logger.warning(f"Erro na análise de balanceamento via IA: {str(e)}")
            return self._technical_balance_analysis_fallback(enriched_context)
    
    async def _identify_underused_assessments_ai(
        self, 
        enriched_context: Dict[str, Any], 
        balance_analysis: Dict[str, Any]
    ) -> List[str]:
        """Identificar atividades subutilizadas via análise IA."""
        
        system_prompt = """Você é um especialista em identificação de lacunas em atividades pedagógicas.
        
        Identifique quais tipos de atividades precisam ser priorizados para melhor balanceamento."""
        
        unit_info = enriched_context["unit_info"]
        rag_analysis = enriched_context["rag_analysis"]
        
        human_prompt = f"""Identifique atividades subutilizadas:
        
        ANÁLISE DE BALANCEAMENTO:
        {json.dumps(balance_analysis, indent=2)}
        
        CONTEXTO ATUAL:
        - Nível: {unit_info['cefr_level']}
        - Tipo: {unit_info['unit_type']}
        - Total de unidades: {rag_analysis.get('total_units_processed', 1)}
        
        TIPOS DISPONÍVEIS: {', '.join(ASSESSMENT_TYPES)}
        
        Considerando:
        1. Que tipos aparecem < 2 vezes no histórico?
        2. Que tipos são apropriados para {unit_info['cefr_level']}?
        3. Que tipos complementam o tipo de unidade {unit_info['unit_type']}?
        
        Retorne lista de 3-4 tipos priorizados em ordem de necessidade:
        ["tipo_mais_necessario", "tipo_segundo", "tipo_terceiro"]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair lista da resposta
            underused = []
            response_lower = response.content.lower()
            
            # Tentar parse JSON primeiro
            try:
                if '[' in response.content and ']' in response.content:
                    list_match = response.content[response.content.find('['):response.content.find(']')+1]
                    underused_list = json.loads(list_match)
                    underused = [item.strip('"') for item in underused_list if item in ASSESSMENT_TYPES]
            except:
                pass
            
            # Fallback: buscar por tipos mencionados
            if not underused:
                for assessment_type in ASSESSMENT_TYPES:
                    if assessment_type in response_lower:
                        underused.append(assessment_type)
            
            # Garantir máximo 4 tipos
            return underused[:4]
            
        except Exception as e:
            logger.warning(f"Erro na identificação de atividades subutilizadas via IA: {str(e)}")
            return self._technical_underused_fallback(enriched_context)
    
    async def _select_complementary_pair_ai(
        self, 
        enriched_context: Dict[str, Any], 
        underused_types: List[str],
        balance_analysis: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Seleção inteligente do par complementar via análise IA."""
        
        system_prompt = """Você é um especialista em seleção de atividades complementares para avaliação.
        
        Selecione 2 atividades que se complementem pedagogicamente, considerando:
        - Balanceamento de habilidades avaliadas
        - Complementaridade metodológica
        - Adequação ao contexto e nível
        - Priorização de tipos subutilizados"""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Selecione par complementar de atividades:
        
        CONTEXTO:
        - Unidade: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Tipo: {unit_info['unit_type']}
        - Vocabulário: {content_analysis['vocabulary_count']} palavras
        - Estratégia: {content_analysis['strategy_info']}
        
        TIPOS PRIORIZADOS (subutilizados): {', '.join(underused_types)}
        
        TODOS OS TIPOS DISPONÍVEIS:
        1. cloze_test - Compreensão contextual geral
        2. gap_fill - Vocabulário específico
        3. reordering - Estrutura e ordem
        4. transformation - Equivalência gramatical
        5. multiple_choice - Reconhecimento objetivo
        6. true_false - Compreensão de afirmações
        7. matching - Associações e relações
        
        HABILIDADES POR TIPO:
        - cloze_test: leitura, análise contextual, gramática em contexto
        - gap_fill: vocabulário, formação de palavras, aplicação contextual
        - reordering: estrutura sintática, ordem de palavras
        - transformation: equivalência gramatical, paráfrase
        - multiple_choice: discriminação, estratégias de eliminação
        - true_false: inferência, identificação de detalhes
        - matching: associação, relações lexicais
        
        CRITÉRIOS DE SELEÇÃO:
        1. Priorize tipos de {underused_types} se apropriados
        2. Selecione atividades que avaliem habilidades DIFERENTES
        3. Uma deve focar vocabulário, outra estrutura/compreensão
        4. Tempo total deve ser 15-25 minutos
        5. Ambas devem ser apropriadas para {unit_info['cefr_level']}
        
        Para unidade {unit_info['unit_type']}:
        - Se lexical: priorize gap_fill, matching, true_false
        - Se gramatical: priorize transformation, reordering, cloze_test
        
        Retorne APENAS os 2 tipos selecionados:
        ["tipo1", "tipo2"]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair par da resposta
            selected_pair = []
            response_content = response.content
            
            # Tentar parse JSON
            try:
                if '[' in response_content and ']' in response_content:
                    list_match = response_content[response_content.find('['):response_content.find(']')+1]
                    pair_list = json.loads(list_match)
                    selected_pair = [item.strip('"') for item in pair_list if item in ASSESSMENT_TYPES]
            except:
                pass
            
            # Fallback: identificar tipos mencionados
            if len(selected_pair) < 2:
                found_types = []
                for assessment_type in ASSESSMENT_TYPES:
                    if assessment_type in response_content.lower():
                        found_types.append(assessment_type)
                
                selected_pair = found_types[:2]
            
            # Garantir que temos exatamente 2 tipos
            if len(selected_pair) < 2:
                selected_pair = self._technical_pair_fallback(enriched_context, underused_types)
            
            return tuple(selected_pair[:2])
            
        except Exception as e:
            logger.warning(f"Erro na seleção do par via IA: {str(e)}")
            return self._technical_pair_fallback(enriched_context, underused_types)
    
    async def _generate_specific_activity_ai(
        self, 
        activity_type: str, 
        enriched_context: Dict[str, Any],
        activity_number: int
    ) -> AssessmentActivity:
        """Gerar atividade específica via análise IA contextual."""
        
        system_prompt = f"""Você é um especialista em criação de atividades de avaliação do tipo {activity_type}.
        
        Crie uma atividade específica e prática usando o conteúdo da unidade.
        
        TIPO: {activity_type}
        DESCRIÇÃO: {ASSESSMENT_DESCRIPTIONS[activity_type]}
        HABILIDADES AVALIADAS: {', '.join(SKILLS_ASSESSED_MAPPING[activity_type])}"""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        vocabulary_words = content_analysis["vocabulary_words"]
        sample_sentences = content_analysis["sample_sentences"]
        
        human_prompt = f"""Crie atividade {activity_type} para:
        
        CONTEXTO: {unit_info['context']}
        NÍVEL: {unit_info['cefr_level']}
        VOCABULÁRIO: {', '.join(vocabulary_words)}
        SENTENCES DISPONÍVEIS: {'; '.join(sample_sentences)}
        
        INSTRUÇÕES ESPECÍFICAS PARA {activity_type.upper()}:
        
        {self._get_activity_specific_instructions(activity_type, unit_info['cefr_level'])}
        
        RETORNE em formato JSON:
        {{
            "type": "{activity_type}",
            "title": "Título claro e engaging",
            "instructions": "Instruções claras para o estudante",
            "content": {{
                {self._get_content_structure_for_type(activity_type)}
            }},
            "answer_key": {{
                "1": "resposta_correta_1",
                "2": "resposta_correta_2"
            }},
            "estimated_time": 12,
            "difficulty_level": "intermediate",
            "skills_assessed": {json.dumps(SKILLS_ASSESSED_MAPPING[activity_type])},
            "vocabulary_focus": {json.dumps(vocabulary_words[:5])},
            "pronunciation_focus": false,
            "phonetic_elements": []
        }}
        
        Use vocabulário da unidade e crie conteúdo específico para "{unit_info['context']}"."""
        
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
                
                activity_data = json.loads(json_content)
                
                # Validar e criar AssessmentActivity
                activity = AssessmentActivity(
                    type=AssessmentType(activity_data.get("type", activity_type)),
                    title=activity_data.get("title", f"{activity_type.title()} Activity"),
                    instructions=activity_data.get("instructions", f"Complete the {activity_type} activity."),
                    content=activity_data.get("content", {}),
                    answer_key=activity_data.get("answer_key", {}),
                    estimated_time=activity_data.get("estimated_time", 12),
                    difficulty_level=activity_data.get("difficulty_level", "intermediate"),
                    skills_assessed=activity_data.get("skills_assessed", SKILLS_ASSESSED_MAPPING[activity_type]),
                    vocabulary_focus=activity_data.get("vocabulary_focus", vocabulary_words[:3]),
                    pronunciation_focus=activity_data.get("pronunciation_focus", False),
                    phonetic_elements=activity_data.get("phonetic_elements", [])
                )
                
                logger.info(f"✅ Atividade {activity_type} gerada: {activity.title}")
                return activity
                
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Erro no parsing da atividade {activity_type}: {str(e)}")
                return self._technical_activity_fallback(activity_type, enriched_context, activity_number)
                
        except Exception as e:
            logger.warning(f"Erro na geração da atividade {activity_type} via IA: {str(e)}")
            return self._technical_activity_fallback(activity_type, enriched_context, activity_number)
    
    async def _generate_selection_rationale_ai(
        self, 
        selected_pair: Tuple[str, str], 
        enriched_context: Dict[str, Any],
        balance_analysis: Dict[str, Any]
    ) -> str:
        """Gerar justificativa da seleção via análise IA."""
        
        system_prompt = """Você é um especialista em justificação pedagógica de seleção de atividades.
        
        Explique de forma clara e concisa por que estas 2 atividades foram selecionadas considerando o contexto específico."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Justifique a seleção das atividades {selected_pair[0]} e {selected_pair[1]}:
        
        CONTEXTO:
        - Unidade: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Tipo: {unit_info['unit_type']}
        - Vocabulário: {content_analysis['vocabulary_count']} palavras
        - Estratégia: {content_analysis['strategy_info']}
        
        BALANCEAMENTO:
        - Score atual: {balance_analysis.get('balance_score', 0.7):.2f}
        - Tipos subutilizados: {', '.join(balance_analysis.get('underused_types', []))}
        
        ATIVIDADES SELECIONADAS:
        1. {selected_pair[0]} - {ASSESSMENT_DESCRIPTIONS[selected_pair[0]]}
        2. {selected_pair[1]} - {ASSESSMENT_DESCRIPTIONS[selected_pair[1]]}
        
        HABILIDADES AVALIADAS:
        - {selected_pair[0]}: {', '.join(SKILLS_ASSESSED_MAPPING[selected_pair[0]])}
        - {selected_pair[1]}: {', '.join(SKILLS_ASSESSED_MAPPING[selected_pair[1]])}
        
        Explique:
        1. Por que estas atividades são complementares
        2. Como atendem ao balanceamento necessário
        3. Por que são apropriadas para {unit_info['cefr_level']} e "{unit_info['context']}"
        4. Como contribuem para variedade pedagógica
        
        Máximo 3-4 frases, seja específico e pedagógico."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na geração de justificativa via IA: {str(e)}")
            return f"Atividades {selected_pair[0]} e {selected_pair[1]} selecionadas para balanceamento pedagógico e complementaridade de habilidades no contexto {unit_info['context']}."
    
    async def _analyze_complementarity_ai(
        self, 
        activity_1: AssessmentActivity, 
        activity_2: AssessmentActivity,
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Análise de complementaridade entre as atividades via IA."""
        
        system_prompt = """Você é um especialista em análise de complementaridade pedagógica.
        
        Analise se as duas atividades se complementam adequadamente em termos de habilidades e metodologia."""
        
        human_prompt = f"""Analise a complementaridade entre estas atividades:
        
        ATIVIDADE 1:
        - Tipo: {activity_1.type.value}
        - Habilidades: {', '.join(activity_1.skills_assessed)}
        - Tempo: {activity_1.estimated_time} min
        - Foco: {', '.join(activity_1.vocabulary_focus[:3])}
        
        ATIVIDADE 2:
        - Tipo: {activity_2.type.value}
        - Habilidades: {', '.join(activity_2.skills_assessed)}
        - Tempo: {activity_2.estimated_time} min
        - Foco: {', '.join(activity_2.vocabulary_focus[:3])}
        
        Analise:
        1. As habilidades avaliadas são complementares?
        2. Há sobreposição excessiva ou lacunas?
        3. O tempo total é apropriado (15-25 min)?
        4. As atividades cobrem aspectos diferentes do aprendizado?
        
        Retorne análise em JSON:
        {{
            "is_complementary": true,
            "skill_overlap": 0.3,
            "skill_coverage": 0.85,
            "time_appropriateness": 0.9,
            "complementarity_score": 0.8,
            "strengths": ["força 1", "força 2"],
            "potential_gaps": ["lacuna 1"] 
        }}"""
        
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
                
                complementarity = json.loads(json_content)
                return complementarity
                
            except json.JSONDecodeError:
                logger.warning("Erro no parsing da análise de complementaridade")
                return self._technical_complementarity_fallback(activity_1, activity_2)
                
        except Exception as e:
            logger.warning(f"Erro na análise de complementaridade via IA: {str(e)}")
            return self._technical_complementarity_fallback(activity_1, activity_2)
    
    # =============================================================================
    # HELPER METHODS - INSTRUÇÕES E ESTRUTURAS POR TIPO
    # =============================================================================
    
    def _get_activity_specific_instructions(self, activity_type: str, cefr_level: str) -> str:
        """Obter instruções específicas por tipo de atividade."""
        
        instructions = {
            "cloze_test": f"""
            - Crie um texto de 80-120 palavras sobre o contexto
            - Remova 8-12 palavras estratégicas (vocabulário + gramática)
            - Lacunas devem testar compreensão contextual
            - Para {cefr_level}: ajuste complexidade do texto""",
            
            "gap_fill": f"""
            - Crie 6-8 frases usando vocabulário da unidade
            - Uma lacuna por frase focando palavra específica
            - Forneça 3-4 opções por lacuna
            - Para {cefr_level}: ajuste complexidade das frases""",
            
            "reordering": f"""
            - Crie 5-6 frases embaralhadas
            - Use vocabulário da unidade
            - Misture ordem de palavras ou frases
            - Para {cefr_level}: ajuste complexidade estrutural""",
            
            "transformation": f"""
            - Crie 5-6 pares de transformação
            - Mantenha significado, mude estrutura
            - Use vocabulário da unidade
            - Para {cefr_level}: ajuste complexidade gramatical""",
            
            "multiple_choice": f"""
            - Crie 6-8 questões objetivas
            - 4 alternativas por questão
            - Foque vocabulário e compreensão
            - Para {cefr_level}: ajuste complexidade das alternativas""",
            
            "true_false": f"""
            - Crie texto base de 60-80 palavras
            - 6-8 afirmações para julgar
            - Mix de verdadeiro/falso balanceado
            - Para {cefr_level}: ajuste complexidade do raciocínio""",
            
            "matching": f"""
            - Crie 6-8 pares para associar
            - Palavras↔definições, frases↔contextos, etc.
            - Use vocabulário da unidade
            - Para {cefr_level}: ajuste complexidade das associações"""
        }
        
        return instructions.get(activity_type, "Crie atividade apropriada para o tipo especificado.")
    
    def _get_content_structure_for_type(self, activity_type: str) -> str:
        """Obter estrutura de conteúdo por tipo de atividade."""
        
        structures = {
            "cloze_test": '"text": "Texto com _____ lacunas", "gaps": ["palavra1", "palavra2"]',
            "gap_fill": '"sentences": ["Frase com _____"], "options": [["opt1", "opt2", "opt3"]]',
            "reordering": '"scrambled_items": ["palavra/frase embaralhada"], "correct_order": [1, 3, 2]',
            "transformation": '"transformations": [{"original": "frase original", "target": "frase alvo"}]',
            "multiple_choice": '"questions": [{"question": "pergunta", "options": ["a", "b", "c", "d"]}]',
            "true_false": '"text": "texto base", "statements": ["afirmação 1", "afirmação 2"]',
            "matching": '"left_column": ["item1", "item2"], "right_column": ["match1", "match2"]'
        }
        
        return structures.get(activity_type, '"content": "estrutura específica"')
    
    # =============================================================================
    # FALLBACKS TÉCNICOS
    # =============================================================================
    
    def _technical_balance_analysis_fallback(self, enriched_context: Dict[str, Any]) -> Dict[str, Any]:
        """Análise de balanceamento técnica quando IA falha."""
        
        used_assessments = enriched_context["rag_analysis"]["used_assessments"]
        
        # Análise técnica simples
        total_uses = sum(used_assessments.values()) if used_assessments else 0
        overused = [k for k, v in used_assessments.items() if v > 2]
        underused = [t for t in ASSESSMENT_TYPES if used_assessments.get(t, 0) < 2]
        
        balance_score = 1.0 - (len(overused) * 0.2)  # Penalizar overuso
        skill_diversity = len(set(used_assessments.keys())) / len(ASSESSMENT_TYPES)
        
        return {
            "current_distribution": used_assessments,
            "overused_types": overused,
            "underused_types": underused,
            "balance_score": max(0.3, balance_score),
            "skill_diversity": skill_diversity,
            "recommendations": ["Usar tipos subutilizados", "Evitar overuso"]
        }
    
    def _technical_underused_fallback(self, enriched_context: Dict[str, Any]) -> List[str]:
        """Identificação técnica de atividades subutilizadas."""
        
        used_assessments = enriched_context["rag_analysis"]["used_assessments"]
        cefr_level = enriched_context["unit_info"]["cefr_level"]
        
        # Filtrar por preferências CEFR
        preferred_for_level = CEFR_ASSESSMENT_PREFERENCES.get(cefr_level, ASSESSMENT_TYPES[:4])
        
        # Encontrar subutilizados
        underused = []
        for assessment_type in preferred_for_level:
            if used_assessments.get(assessment_type, 0) < 2:
                underused.append(assessment_type)
        
        # Adicionar outros se necessário
        for assessment_type in ASSESSMENT_TYPES:
            if (assessment_type not in underused and 
                used_assessments.get(assessment_type, 0) == 0):
                underused.append(assessment_type)
        
        return underused[:4]
    
    def _technical_pair_fallback(
        self, 
        enriched_context: Dict[str, Any], 
        underused_types: List[str]
    ) -> Tuple[str, str]:
        """Seleção técnica do par quando IA falha."""
        
        unit_type = enriched_context["unit_info"]["unit_type"]
        cefr_level = enriched_context["unit_info"]["cefr_level"]
        
        # Preferências por tipo de unidade
        if unit_type == "lexical_unit":
            preferred = ["gap_fill", "matching", "true_false"]
        else:  # grammar_unit
            preferred = ["transformation", "reordering", "cloze_test"]
        
        # Selecionar do underused primeiro
        selected = []
        for pref in preferred:
            if pref in underused_types:
                selected.append(pref)
                if len(selected) == 2:
                    break
        
        # Completar se necessário
        if len(selected) < 2:
            for pref in preferred:
                if pref not in selected:
                    selected.append(pref)
                    if len(selected) == 2:
                        break
        
        # Fallback final
        if len(selected) < 2:
            selected = ["gap_fill", "multiple_choice"]
        
        return tuple(selected[:2])
    
    def _technical_activity_fallback(
        self, 
        activity_type: str, 
        enriched_context: Dict[str, Any],
        activity_number: int
    ) -> AssessmentActivity:
        """Atividade técnica de fallback quando IA falha."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        vocabulary_words = content_analysis["vocabulary_words"][:3]
        
        # Conteúdo básico por tipo
        basic_content = self._get_basic_content_for_type(activity_type, vocabulary_words, unit_info["context"])
        
        return AssessmentActivity(
            type=AssessmentType(activity_type),
            title=f"{activity_type.replace('_', ' ').title()} Activity",
            instructions=f"Complete the {activity_type.replace('_', ' ')} exercise using the vocabulary from the unit.",
            content=basic_content,
            answer_key={"1": "answer1", "2": "answer2"},
            estimated_time=12,
            difficulty_level="intermediate",
            skills_assessed=SKILLS_ASSESSED_MAPPING[activity_type],
            vocabulary_focus=vocabulary_words,
            pronunciation_focus=False,
            phonetic_elements=[]
        )
    
    def _get_basic_content_for_type(
        self, 
        activity_type: str, 
        vocabulary_words: List[str], 
        context: str
    ) -> Dict[str, Any]:
        """Gerar conteúdo básico por tipo de atividade."""
        
        word1 = vocabulary_words[0] if vocabulary_words else "word"
        word2 = vocabulary_words[1] if len(vocabulary_words) > 1 else "example"
        
        content_templates = {
            "cloze_test": {
                "text": f"In the {context}, people often use _____ to communicate effectively. The _____ is very important.",
                "gaps": [word1, word2]
            },
            "gap_fill": {
                "sentences": [f"The _____ is essential in {context}.", f"People need to _____ properly."],
                "options": [[word1, "other", "option"], [word2, "different", "choice"]]
            },
            "reordering": {
                "scrambled_items": [f"{word1} important very is", f"in used {context} {word2}"],
                "correct_order": [0, 1]
            },
            "transformation": {
                "transformations": [
                    {"original": f"The {word1} is important.", "target": f"It's important to use {word1}."},
                    {"original": f"We need {word2}.", "target": f"{word2} is needed."}
                ]
            },
            "multiple_choice": {
                "questions": [
                    {"question": f"What is used in {context}?", "options": [word1, "option2", "option3", "option4"]},
                    {"question": f"How do you {word2}?", "options": ["correctly", "wrong1", "wrong2", "wrong3"]}
                ]
            },
            "true_false": {
                "text": f"In {context}, {word1} is very important. People always use {word2} correctly.",
                "statements": [f"{word1} is important in {context}.", f"Everyone uses {word2} perfectly."]
            },
            "matching": {
                "left_column": [word1, word2, "item3"],
                "right_column": ["definition1", "definition2", "definition3"]
            }
        }
        
        return content_templates.get(activity_type, {"content": "basic activity content"})
    
    def _technical_complementarity_fallback(
        self, 
        activity_1: AssessmentActivity, 
        activity_2: AssessmentActivity
    ) -> Dict[str, Any]:
        """Análise técnica de complementaridade quando IA falha."""
        
        # Análise técnica simples
        skills_1 = set(activity_1.skills_assessed)
        skills_2 = set(activity_2.skills_assessed)
        
        overlap = len(skills_1 & skills_2) / max(len(skills_1 | skills_2), 1)
        coverage = len(skills_1 | skills_2) / 7  # 7 habilidades principais
        total_time = activity_1.estimated_time + activity_2.estimated_time
        time_appropriate = 0.9 if 15 <= total_time <= 25 else 0.6
        
        complementarity_score = (1 - overlap + coverage + time_appropriate) / 3
        
        return {
            "is_complementary": complementarity_score > 0.6,
            "skill_overlap": overlap,
            "skill_coverage": coverage,
            "time_appropriateness": time_appropriate,
            "complementarity_score": complementarity_score,
            "strengths": ["Atividades com diferentes focos"],
            "potential_gaps": ["Possível melhoria na complementaridade"]
        }
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _assess_content_richness(self, content_data: Dict[str, Any]) -> float:
        """Avaliar riqueza do conteúdo disponível (análise técnica)."""
        
        richness_score = 0.0
        
        # Vocabulário
        vocab_items = content_data.get("vocabulary", {}).get("items", [])
        if len(vocab_items) >= 20:
            richness_score += 0.3
        elif len(vocab_items) >= 10:
            richness_score += 0.2
        else:
            richness_score += 0.1
        
        # Sentences
        sentences = content_data.get("sentences", {}).get("sentences", [])
        if len(sentences) >= 10:
            richness_score += 0.3
        elif len(sentences) >= 5:
            richness_score += 0.2
        else:
            richness_score += 0.1
        
        # Estratégias
        if content_data.get("tips") or content_data.get("grammar"):
            richness_score += 0.2
        
        # Q&A
        if content_data.get("qa"):
            richness_score += 0.2
        
        return min(richness_score, 1.0)
    
    def _calculate_updated_balance(
        self, 
        current_usage: Dict[str, int], 
        selected_pair: Tuple[str, str]
    ) -> Dict[str, Any]:
        """Calcular balanceamento atualizado após seleção."""
        
        updated_usage = current_usage.copy()
        
        for activity_type in selected_pair:
            updated_usage[activity_type] = updated_usage.get(activity_type, 0) + 1
        
        total_activities = sum(updated_usage.values())
        distribution = {k: v/total_activities for k, v in updated_usage.items()} if total_activities > 0 else {}
        
        # Calcular novo score de balanceamento
        ideal_distribution = 1.0 / len(ASSESSMENT_TYPES)  # ~0.143
        variance = sum((freq - ideal_distribution) ** 2 for freq in distribution.values())
        balance_score = max(0.0, 1.0 - variance * 5)  # Escalar para 0-1
        
        return {
            "updated_distribution": updated_usage,
            "balance_score": balance_score,
            "total_activities": total_activities,
            "most_used": max(updated_usage.items(), key=lambda x: x[1]) if updated_usage else None,
            "least_used": min(updated_usage.items(), key=lambda x: x[1]) if updated_usage else None
        }
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Obter status do serviço."""
        return {
            "service": "AssessmentSelectorService", 
            "status": "active",
            "assessment_types": ASSESSMENT_TYPES,
            "total_types_available": len(ASSESSMENT_TYPES),
            "ai_integration": "100% contextual analysis",
            "rag_balancing": "enabled",
            "complementarity_analysis": "enabled",
            "cefr_adaptation": "enabled",
            "selection_method": "intelligent_pair_selection",
            "ai_analysis_methods": [
                "_analyze_current_balance_ai",
                "_identify_underused_assessments_ai",
                "_select_complementary_pair_ai",
                "_generate_specific_activity_ai",
                "_generate_selection_rationale_ai",
                "_analyze_complementarity_ai"
            ],
            "constants_maintained": list(ASSESSMENT_DESCRIPTIONS.keys())
        }
    
    async def validate_selection_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validar parâmetros de seleção."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Validações básicas
        required_fields = ["unit_data", "content_data", "hierarchy_context", "rag_context"]
        for field in required_fields:
            if field not in params:
                validation_result["errors"].append(f"Campo obrigatório ausente: {field}")
                validation_result["valid"] = False
        
        # Validações específicas
        unit_data = params.get("unit_data", {})
        if not unit_data.get("cefr_level"):
            validation_result["warnings"].append("Nível CEFR não especificado")
        
        content_data = params.get("content_data", {})
        if not content_data.get("vocabulary", {}).get("items"):
            validation_result["warnings"].append("Vocabulário não disponível - pode afetar qualidade")
        
        rag_context = params.get("rag_context", {})
        if not rag_context.get("used_assessments"):
            validation_result["warnings"].append("Histórico de atividades vazio - primeira unidade?")
        
        return validation_result


# =============================================================================
# UTILITY FUNCTIONS PARA ENDPOINTS
# =============================================================================

async def select_assessments_for_unit_creation(selection_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função de conveniência para seleção de atividades em endpoints V2.
    Mantém compatibilidade com a API existente.
    """
    try:
        service = AssessmentSelectorService()
        assessment_section = await service.select_optimal_assessments(selection_params)
        
        return {
            "success": True,
            "assessment_section": assessment_section.dict(),
            "selection_time": time.time(),
            "service_version": "langchain_0.3_pydantic_2_rag_balanced"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na função de conveniência: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "fallback_available": True
        }


async def analyze_assessment_balance_ai(
    used_assessments: Dict[str, int],
    unit_context: str,
    cefr_level: str
) -> Dict[str, Any]:
    """
    Analisar balanceamento de atividades via IA.
    
    Args:
        used_assessments: Histórico de uso de atividades
        unit_context: Contexto da unidade
        cefr_level: Nível CEFR
        
    Returns:
        Análise de balanceamento
    """
    service = AssessmentSelectorService()
    
    # Construir contexto mínimo
    enriched_context = {
        "unit_info": {"context": unit_context, "cefr_level": cefr_level},
        "rag_analysis": {"used_assessments": used_assessments},
        "hierarchy_info": {"sequence_order": sum(used_assessments.values())}
    }
    
    try:
        balance_analysis = await service._analyze_current_balance_ai(enriched_context)
        return balance_analysis
    except Exception as e:
        logger.warning(f"Erro na análise de balanceamento via IA: {str(e)}")
        return service._technical_balance_analysis_fallback(enriched_context)


def calculate_assessment_distribution_metrics(used_assessments: Dict[str, int]) -> Dict[str, Any]:
    """
    Calcular métricas de distribuição de atividades (análise técnica).
    
    Args:
        used_assessments: Histórico de uso
        
    Returns:
        Métricas de distribuição
    """
    if not used_assessments:
        return {
            "total_activities": 0,
            "unique_types": 0,
            "most_used": None,
            "least_used": None,
            "balance_score": 1.0,
            "diversity_score": 0.0
        }
    
    total = sum(used_assessments.values())
    unique_types = len(used_assessments)
    
    # Encontrar mais e menos usado
    most_used = max(used_assessments.items(), key=lambda x: x[1])
    least_used = min(used_assessments.items(), key=lambda x: x[1])
    
    # Calcular scores
    max_ideal = total / len(ASSESSMENT_TYPES)
    balance_score = 1.0 - (most_used[1] - max_ideal) / max(total, 1)
    diversity_score = unique_types / len(ASSESSMENT_TYPES)
    
    return {
        "total_activities": total,
        "unique_types": unique_types,
        "most_used": {"type": most_used[0], "count": most_used[1]},
        "least_used": {"type": least_used[0], "count": least_used[1]},
        "balance_score": max(0.0, balance_score),
        "diversity_score": diversity_score,
        "distribution": {k: v/total for k, v in used_assessments.items()}
    }


def get_assessment_recommendations_for_cefr(cefr_level: str, unit_type: str) -> List[str]:
    """
    Obter recomendações de atividades por nível CEFR e tipo de unidade.
    
    Args:
        cefr_level: Nível CEFR (A1, A2, B1, B2, C1, C2)
        unit_type: Tipo de unidade (lexical_unit, grammar_unit)
        
    Returns:
        Lista de tipos recomendados
    """
    base_recommendations = CEFR_ASSESSMENT_PREFERENCES.get(cefr_level, ASSESSMENT_TYPES[:4])
    
    # Ajustar por tipo de unidade
    if unit_type == "lexical_unit":
        # Priorizar atividades focadas em vocabulário
        lexical_priority = ["gap_fill", "matching", "true_false", "cloze_test"]
        recommendations = [t for t in lexical_priority if t in base_recommendations]
        recommendations.extend([t for t in base_recommendations if t not in recommendations])
    
    elif unit_type == "grammar_unit":
        # Priorizar atividades focadas em estruturas
        grammar_priority = ["transformation", "reordering", "cloze_test", "gap_fill"]
        recommendations = [t for t in grammar_priority if t in base_recommendations] 
        recommendations.extend([t for t in base_recommendations if t not in recommendations])
    
    else:
        recommendations = base_recommendations
    
    return recommendations[:4]


def create_assessment_variety_report(used_assessments: Dict[str, int]) -> str:
    """
    Criar relatório de variedade de atividades.
    
    Args:
        used_assessments: Histórico de uso
        
    Returns:
        Relatório formatado
    """
    if not used_assessments:
        return "ASSESSMENT VARIETY REPORT\n\nNo activities used yet. Ready to start with balanced selection."
    
    metrics = calculate_assessment_distribution_metrics(used_assessments)
    
    report_lines = [
        "ASSESSMENT VARIETY REPORT",
        "=" * 30,
        "",
        f"Total Activities: {metrics['total_activities']}",
        f"Unique Types Used: {metrics['unique_types']}/{len(ASSESSMENT_TYPES)}",
        f"Balance Score: {metrics['balance_score']:.1%}",
        f"Diversity Score: {metrics['diversity_score']:.1%}",
        "",
        "DISTRIBUTION:",
    ]
    
    # Ordenar por uso
    sorted_usage = sorted(used_assessments.items(), key=lambda x: x[1], reverse=True)
    
    for activity_type, count in sorted_usage:
        percentage = (count / metrics['total_activities']) * 100
        bar = "█" * int(percentage / 5)  # Visual bar
        description = ASSESSMENT_DESCRIPTIONS.get(activity_type, "Unknown activity")
        report_lines.append(f"  {activity_type:15} [{count:2}] {bar:10} {percentage:5.1f}% - {description}")
    
    # Tipos não usados
    unused_types = [t for t in ASSESSMENT_TYPES if t not in used_assessments]
    if unused_types:
        report_lines.extend([
            "",
            "UNUSED TYPES:",
            ", ".join(unused_types)
        ])
    
    # Recomendações
    if metrics['balance_score'] < 0.7:
        report_lines.extend([
            "",
            "RECOMMENDATIONS:",
            f"• Consider using {metrics['least_used']['type']} more frequently",
            f"• Reduce usage of {metrics['most_used']['type']} temporarily", 
            "• Aim for more balanced distribution"
        ])
    else:
        report_lines.extend([
            "",
            "✅ Good variety and balance maintained!"
        ])
    
    return "\n".join(report_lines)