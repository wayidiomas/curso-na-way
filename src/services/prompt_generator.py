# src/services/prompt_generator.py
"""
Serviço centralizado de geração de prompts para o IVO V2.
Implementa prompt engineering otimizado para hierarquia Course → Book → Unit com RAG.
CORRIGIDO: 100% análise via IA, zero dados hard-coded.
"""

import os
import yaml
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from src.core.enums import CEFRLevel, LanguageVariant, UnitType, TipStrategy, GrammarStrategy, AssessmentType
from src.core.unit_models import VocabularyItem

logger = logging.getLogger(__name__)


class PromptTemplate:
    """Template base para prompts estruturados."""
    
    def __init__(self, name: str, system_prompt: str, user_prompt: str, variables: List[str]):
        self.name = name
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.variables = variables
    
    def format(self, **kwargs) -> List[Union[SystemMessage, HumanMessage]]:
        """Formatar template com variáveis."""
        # Verificar variáveis obrigatórias
        missing_vars = [var for var in self.variables if var not in kwargs]
        if missing_vars:
            logger.warning(f"Variáveis faltantes no template {self.name}: {missing_vars}")
        
        # Formatar prompts
        try:
            formatted_system = self.system_prompt.format(**kwargs)
            formatted_user = self.user_prompt.format(**kwargs)
            
            return [
                SystemMessage(content=formatted_system),
                HumanMessage(content=formatted_user)
            ]
        except KeyError as e:
            logger.error(f"Erro ao formatar template {self.name}: {str(e)}")
            raise


class PromptGeneratorService:
    """Serviço centralizado de geração de prompts otimizados para IVO V2."""
    
    def __init__(self):
        """Inicializar serviço com LLM para análises contextuais."""
        self.templates: Dict[str, PromptTemplate] = {}
        self.prompts_config_dir = Path(__file__).parent.parent / "config" / "prompts" / "ivo"
        
        # Configurar LLM para análises contextuais
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,  # Baixa para consistência
            max_tokens=2000
        )
        
        # Carregar todos os templates
        self._load_all_templates()
        
        logger.info(f"✅ PromptGeneratorService inicializado com {len(self.templates)} templates e IA integrada")
    
    # =============================================================================
    # VOCABULÁRIO - PROMPT 6 OTIMIZADO COM IA
    # =============================================================================
    
    async def generate_vocabulary_prompt(
        self,
        unit_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any],
        images_analysis: Dict[str, Any],
        target_count: int = 25
    ) -> List[Any]:
        """
        Gerar prompt otimizado para vocabulário com RAG e análise de imagens.
        Usa IA para análise contextual de requirements CEFR.
        """
        
        # Extrair contextos
        unit_ctx = unit_data
        hierarchy_ctx = hierarchy_context
        rag_ctx = rag_context
        images_ctx = images_analysis
        
        # ANÁLISE VIA IA: Guidelines CEFR contextuais
        cefr_guidelines = await self._analyze_cefr_requirements_ai(
            cefr_level=unit_ctx.get("cefr_level", "A2"),
            unit_context=unit_ctx.get("context", ""),
            unit_type=unit_ctx.get("unit_type", "lexical_unit")
        )
        
        # ANÁLISE VIA IA: Variante IPA contextual
        ipa_variant = await self._analyze_ipa_variant_ai(
            language_variant=unit_ctx.get("language_variant", "american_english"),
            vocabulary_context=unit_ctx.get("context", "")
        )
        
        # Análise de imagens
        image_vocabulary = []
        image_themes = []
        if images_ctx.get("success"):
            vocab_data = images_ctx.get("consolidated_vocabulary", {}).get("vocabulary", [])
            image_vocabulary = [item.get("word", "") for item in vocab_data if item.get("word")][:15]
            
            for analysis in images_ctx.get("individual_analyses", []):
                if "structured_data" in analysis.get("analysis", {}):
                    themes = analysis["analysis"]["structured_data"].get("contextual_themes", [])
                    image_themes.extend(themes)
        
        # Contexto RAG
        taught_vocabulary = rag_ctx.get("taught_vocabulary", [])
        reinforcement_candidates = taught_vocabulary[-10:] if taught_vocabulary else []
        
        variables = {
            "unit_title": unit_ctx.get("title", ""),
            "unit_context": unit_ctx.get("context", ""),
            "cefr_level": unit_ctx.get("cefr_level", "A2"),
            "language_variant": unit_ctx.get("language_variant", "american_english"),
            "unit_type": unit_ctx.get("unit_type", "lexical_unit"),
            "course_name": hierarchy_ctx.get("course_name", ""),
            "book_name": hierarchy_ctx.get("book_name", ""),
            "sequence_order": hierarchy_ctx.get("sequence_order", 1),
            "target_count": target_count,
            "cefr_guidelines": cefr_guidelines,
            "taught_vocabulary": ", ".join(taught_vocabulary[:20]),
            "reinforcement_candidates": ", ".join(reinforcement_candidates),
            "image_vocabulary": ", ".join(image_vocabulary),
            "image_themes": ", ".join(list(set(image_themes))[:10]),
            "ipa_variant": ipa_variant,
            "has_images": bool(image_vocabulary),
            "progression_level": rag_ctx.get("progression_level", "intermediate"),
            "vocabulary_density": rag_ctx.get("vocabulary_density", 0),
            "images_analyzed": len(images_ctx.get("individual_analyses", []))
        }
        
        return self.templates["vocabulary_generation"].format(**variables)
    
    # =============================================================================
    # SENTENCES - PROMPT CONTEXTUAL COM IA
    # =============================================================================
    
    async def generate_sentences_prompt(
        self,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para sentences conectadas ao vocabulário usando análise IA."""
        
        # Extrair palavras do vocabulário
        vocabulary_items = vocabulary_data.get("items", [])
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        
        # ANÁLISE VIA IA: Complexidade de vocabulário
        complexity_analysis = await self._analyze_vocabulary_complexity_ai(
            vocabulary_items=vocabulary_items,
            unit_context=unit_data.get("context", ""),
            cefr_level=unit_data.get("cefr_level", "A2")
        )
        
        variables = {
            "vocabulary_list": ", ".join(vocabulary_words[:15]),
            "vocabulary_count": len(vocabulary_words),
            "unit_context": unit_data.get("context", ""),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "taught_vocabulary": ", ".join(rag_context.get("taught_vocabulary", [])[:10]),
            "progression_level": rag_context.get("progression_level", "intermediate"),
            "complexity_analysis": complexity_analysis,
            "sequence_order": hierarchy_context.get("sequence_order", 1),
            "target_sentences": 12 + min(hierarchy_context.get("sequence_order", 1), 3)  # 12-15 sentences
        }
        
        return self.templates["sentences_generation"].format(**variables)
    
    # =============================================================================
    # TIPS - ESTRATÉGIAS LEXICAIS COM IA
    # =============================================================================
    
    async def generate_tips_prompt(
        self,
        selected_strategy: str,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para estratégias TIPS com análise IA da estratégia."""
        
        # ANÁLISE VIA IA: Informações da estratégia contextual
        strategy_analysis = await self._analyze_strategy_via_ai(
            strategy_name=selected_strategy,
            vocabulary_items=vocabulary_data.get("items", []),
            unit_context=unit_data.get("context", ""),
            cefr_level=unit_data.get("cefr_level", "A2")
        )
        
        # ANÁLISE VIA IA: Padrões no vocabulário para a estratégia
        vocabulary_patterns = await self._analyze_vocabulary_patterns_ai(
            vocabulary_items=vocabulary_data.get("items", []),
            strategy=selected_strategy,
            unit_context=unit_data.get("context", "")
        )
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_data.get("items", [])]
        
        variables = {
            "strategy_analysis": strategy_analysis,
            "vocabulary_patterns": vocabulary_patterns,
            "unit_title": unit_data.get("title", ""),
            "unit_context": unit_data.get("context", ""),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "vocabulary_words": ", ".join(vocabulary_words[:15]),
            "vocabulary_count": len(vocabulary_words),
            "used_strategies": ", ".join(rag_context.get("used_strategies", [])),
            "progression_level": rag_context.get("progression_level", "intermediate"),
            "selected_strategy": selected_strategy
        }
        
        return self.templates["tips_strategies"].format(**variables)
    
    # =============================================================================
    # GRAMMAR - ESTRATÉGIAS GRAMATICAIS COM IA
    # =============================================================================
    
    async def generate_grammar_prompt(
        self,
        selected_strategy: str,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para estratégias GRAMMAR usando análise IA."""
        
        # Determinar se é explicação sistemática ou prevenção L1
        is_l1_prevention = selected_strategy == "prevencao_erros_l1"
        
        # ANÁLISE VIA IA: Identificar ponto gramatical principal
        grammar_point = await self._identify_grammar_point_ai(
            unit_data=unit_data,
            vocabulary_data=vocabulary_data,
            strategy_focus=selected_strategy
        )
        
        # ANÁLISE VIA IA: Padrões de interferência L1 (se aplicável)
        l1_analysis = ""
        if is_l1_prevention:
            l1_analysis = await self._analyze_l1_interference_ai(
                grammar_point=grammar_point,
                unit_context=unit_data.get("context", ""),
                vocabulary_items=vocabulary_data.get("items", [])
            )
        
        variables = {
            "strategy_type": "Prevenção de Erros L1" if is_l1_prevention else "Explicação Sistemática",
            "grammar_point": grammar_point,
            "unit_context": unit_data.get("context", ""),
            "vocabulary_list": ", ".join([item.get("word", "") for item in vocabulary_data.get("items", [])[:10]]),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "used_strategies": ", ".join(rag_context.get("used_strategies", [])),
            "l1_analysis": l1_analysis,
            "is_l1_prevention": is_l1_prevention,
            "systematic_focus": not is_l1_prevention,
            "selected_strategy": selected_strategy
        }
        
        template_name = "l1_interference" if is_l1_prevention else "grammar_content"
        return self.templates[template_name].format(**variables)
    
    # =============================================================================
    # ASSESSMENTS - SELEÇÃO BALANCEADA COM IA
    # =============================================================================
    
    async def generate_assessment_selection_prompt(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para seleção inteligente de atividades usando IA."""
        
        # ANÁLISE VIA IA: Balanceamento de atividades
        assessment_analysis = await self._analyze_assessment_balance_ai(
            used_assessments=rag_context.get("used_assessments", {}),
            unit_type=unit_data.get("unit_type", "lexical_unit"),
            cefr_level=unit_data.get("cefr_level", "A2"),
            content_data=content_data
        )
        
        # ANÁLISE VIA IA: Tipos recomendados
        recommended_analysis = await self._analyze_recommended_assessments_ai(
            unit_data=unit_data,
            content_data=content_data,
            usage_history=rag_context.get("used_assessments", {})
        )
        
        variables = {
            "unit_data": str(unit_data),
            "vocabulary_data": str(content_data.get("vocabulary", {})),
            "strategies_used": ", ".join([
                content_data.get("tips", {}).get("strategy", ""),
                content_data.get("grammar", {}).get("strategy", "")
            ]).strip(", "),
            "used_assessments": str(rag_context.get("used_assessments", {})),
            "rag_context": str(rag_context),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "unit_type": unit_data.get("unit_type", "lexical_unit"),
            "assessment_analysis": assessment_analysis,
            "recommended_analysis": recommended_analysis,
            "progression_level": rag_context.get("progression_level", "intermediate")
        }
        
        return self.templates["assessment_selection"].format(**variables)
    
    # =============================================================================
    # Q&A - TAXONOMIA DE BLOOM COM IA
    # =============================================================================
    
    async def generate_qa_prompt(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        pedagogical_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para Q&A baseado na Taxonomia de Bloom usando IA."""
        
        # Extrair vocabulário para integração
        vocabulary_items = content_data.get("vocabulary", {}).get("items", [])
        vocabulary_integration = [item.get("word", "") for item in vocabulary_items[:10]]
        
        # Estratégia aplicada
        strategy_applied = ""
        if content_data.get("tips"):
            strategy_applied = f"TIPS: {content_data['tips'].get('strategy', '')}"
        elif content_data.get("grammar"):
            strategy_applied = f"GRAMMAR: {content_data['grammar'].get('strategy', '')}"
        
        # ANÁLISE VIA IA: Objetivos de aprendizagem contextuais
        learning_objectives = await self._generate_learning_objectives_ai(
            unit_data=unit_data,
            content_data=content_data,
            existing_objectives=pedagogical_context.get("learning_objectives", [])
        )
        
        # ANÁLISE VIA IA: Foco fonético contextual
        phonetic_focus = await self._analyze_phonetic_focus_ai(
            vocabulary_items=vocabulary_items,
            unit_context=unit_data.get("context", ""),
            cefr_level=unit_data.get("cefr_level", "A2")
        )
        
        # ANÁLISE VIA IA: Distribuição Bloom adaptativa
        bloom_distribution = await self._analyze_bloom_distribution_ai(
            cefr_level=unit_data.get("cefr_level", "A2"),
            unit_complexity=len(vocabulary_items),
            content_data=content_data
        )
        
        variables = {
            "unit_title": unit_data.get("title", ""),
            "unit_context": unit_data.get("context", ""),
            "vocabulary_items": ", ".join(vocabulary_integration),
            "strategy_applied": strategy_applied,
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "learning_objectives": learning_objectives,
            "phonetic_focus": phonetic_focus,
            "progression_level": pedagogical_context.get("progression_level", "intermediate"),
            "bloom_distribution": bloom_distribution,
            "vocabulary_count": len(vocabulary_items)
        }
        
        return self.templates["qa_generation"].format(**variables)
    
    # =============================================================================
    # PHONETIC INTEGRATION COM IA
    # =============================================================================
    
    async def generate_phonetic_integration_prompt(
        self,
        vocabulary_items: List[Dict[str, Any]],
        cefr_level: str,
        language_variant: str
    ) -> List[Any]:
        """Gerar prompt para integração fonética usando análise IA."""
        
        # ANÁLISE VIA IA: Complexidade fonética
        phonetic_analysis = await self._analyze_phonetic_complexity_ai(
            vocabulary_items=vocabulary_items,
            cefr_level=cefr_level,
            language_variant=language_variant
        )
        
        variables = {
            "vocabulary_with_phonemes": str(vocabulary_items),
            "cefr_level": cefr_level,
            "language_variant": language_variant,
            "phonetic_analysis": phonetic_analysis,
            "vocabulary_count": len(vocabulary_items)
        }
        
        return self.templates["phonetic_integration"].format(**variables)
    
    # =============================================================================
    # MÉTODOS DE ANÁLISE VIA IA (SUBSTITUEM DADOS HARD-CODED)
    # =============================================================================
    
    async def _analyze_cefr_requirements_ai(self, cefr_level: str, unit_context: str, unit_type: str) -> str:
        """Análise contextual via IA para requirements CEFR específicos."""
        
        system_prompt = """Você é um especialista em níveis CEFR e desenvolvimento de vocabulário.
        
        Analise o nível CEFR fornecido considerando o contexto específico da unidade e tipo de ensino.
        
        Forneça guidelines específicas e contextuais para seleção de vocabulário apropriado."""
        
        human_prompt = f"""Analise este contexto educacional:
        
        NÍVEL CEFR: {cefr_level}
        CONTEXTO DA UNIDADE: {unit_context}
        TIPO DE UNIDADE: {unit_type}
        
        Forneça guidelines específicas para seleção de vocabulário considerando:
        - Complexidade apropriada para o nível
        - Relevância contextual
        - Progressão pedagógica
        - Aplicabilidade comunicativa
        
        Responda com guidelines diretas e específicas para este contexto."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise CEFR via IA: {str(e)}")
            return self._minimal_cefr_fallback(cefr_level)
    
    async def _analyze_ipa_variant_ai(self, language_variant: str, vocabulary_context: str) -> str:
        """Análise contextual via IA para variante IPA apropriada."""
        
        system_prompt = """Você é um especialista em fonética e variações do inglês.
        
        Determine a variante IPA mais apropriada considerando a variante linguística e contexto do vocabulário."""
        
        human_prompt = f"""Determine a variante IPA apropriada:
        
        VARIANTE LINGUÍSTICA: {language_variant}
        CONTEXTO DO VOCABULÁRIO: {vocabulary_context}
        
        Retorne a descrição da variante IPA mais apropriada para este contexto específico."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise IPA via IA: {str(e)}")
            return "General American" if "american" in language_variant.lower() else "Received Pronunciation"
    
    async def _analyze_vocabulary_complexity_ai(self, vocabulary_items: List[Dict[str, Any]], unit_context: str, cefr_level: str) -> str:
        """Análise contextual via IA da complexidade do vocabulário."""
        
        system_prompt = """Você é um especialista em análise de vocabulário e complexidade linguística.
        
        Analise a complexidade do vocabulário fornecido considerando o contexto e nível CEFR."""
        
        vocabulary_summary = [f"{item.get('word', '')} ({item.get('word_class', '')})" for item in vocabulary_items[:10]]
        
        human_prompt = f"""Analise a complexidade deste vocabulário:
        
        VOCABULÁRIO: {', '.join(vocabulary_summary)}
        CONTEXTO: {unit_context}
        NÍVEL CEFR: {cefr_level}
        
        Forneça análise da complexidade considerando:
        - Nível de dificuldade das palavras
        - Adequação ao nível CEFR
        - Coerência temática
        - Potencial para sentences conectadas
        
        Retorne análise concisa e específica."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise de complexidade via IA: {str(e)}")
            return "Complexidade média apropriada para o nível"
    
    async def _analyze_strategy_via_ai(self, strategy_name: str, vocabulary_items: List[Dict[str, Any]], unit_context: str, cefr_level: str) -> str:
        """Análise contextual via IA da estratégia TIPS."""
        
        system_prompt = """Você é um especialista em estratégias pedagógicas para ensino de vocabulário.
        
        Analise como aplicar a estratégia TIPS fornecida ao vocabulário e contexto específicos."""
        
        vocabulary_summary = [item.get('word', '') for item in vocabulary_items[:10]]
        
        human_prompt = f"""Analise esta estratégia pedagógica:
        
        ESTRATÉGIA: {strategy_name}
        VOCABULÁRIO: {', '.join(vocabulary_summary)}
        CONTEXTO: {unit_context}
        NÍVEL: {cefr_level}
        
        Forneça análise específica incluindo:
        - Como aplicar esta estratégia ao vocabulário
        - Adaptações necessárias para o nível CEFR
        - Instruções de implementação específicas
        - Benefícios pedagógicos esperados
        
        Retorne análise detalhada e aplicável."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise de estratégia via IA: {str(e)}")
            return f"Aplicação padrão da estratégia {strategy_name} ao contexto fornecido"
    
    async def _analyze_vocabulary_patterns_ai(self, vocabulary_items: List[Dict[str, Any]], strategy: str, unit_context: str) -> str:
        """Análise contextual via IA de padrões no vocabulário para estratégia específica."""
        
        system_prompt = """Você é um especialista em análise de padrões vocabulares para estratégias pedagógicas.
        
        Identifique padrões no vocabulário que sejam relevantes para a estratégia específica."""
        
        vocabulary_details = []
        for item in vocabulary_items[:8]:
            word = item.get('word', '')
            word_class = item.get('word_class', '')
            vocabulary_details.append(f"{word} ({word_class})")
        
        human_prompt = f"""Analise padrões vocabulares para estratégia:
        
        VOCABULÁRIO: {', '.join(vocabulary_details)}
        ESTRATÉGIA: {strategy}
        CONTEXTO: {unit_context}
        
        Identifique padrões específicos que suportem a aplicação da estratégia:
        - Padrões morfológicos (se aplicável)
        - Agrupamentos temáticos
        - Oportunidades de aplicação da estratégia
        - Potencial pedagógico específico
        
        Retorne análise focada na estratégia."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise de padrões via IA: {str(e)}")
            return f"Padrões vocabulares adequados para aplicação da estratégia {strategy}"
    
    async def _identify_grammar_point_ai(self, unit_data: Dict[str, Any], vocabulary_data: Dict[str, Any], strategy_focus: str) -> str:
        """Identificação contextual via IA do ponto gramatical principal."""
        
        system_prompt = """Você é um especialista em análise gramatical e estruturas linguísticas.
        
        Identifique o ponto gramatical principal mais relevante baseado no contexto e vocabulário."""
        
        vocabulary_words = [item.get('word', '') for item in vocabulary_data.get('items', [])[:10]]
        
        human_prompt = f"""Identifique o ponto gramatical principal:
        
        CONTEXTO DA UNIDADE: {unit_data.get('context', '')}
        TÍTULO: {unit_data.get('title', '')}
        VOCABULÁRIO: {', '.join(vocabulary_words)}
        ESTRATÉGIA FOCADA: {strategy_focus}
        NÍVEL CEFR: {unit_data.get('cefr_level', 'A2')}
        
        Determine qual ponto gramatical seria mais relevante e produtivo para esta unidade.
        
        Retorne apenas o nome do ponto gramatical principal (ex: "Present Perfect", "Modal Verbs", etc.)."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na identificação gramatical via IA: {str(e)}")
            return "General Grammar Structures"
    
    async def _analyze_l1_interference_ai(self, grammar_point: str, unit_context: str, vocabulary_items: List[Dict[str, Any]]) -> str:
        """Análise contextual via IA de interferência L1 (português → inglês)."""
        
        system_prompt = """Você é um especialista em interferência linguística português-inglês.
        
        Analise padrões de interferência L1 (português) para L2 (inglês) considerando o ponto gramatical específico."""
        
        vocabulary_summary = [item.get('word', '') for item in vocabulary_items[:8]]
        
        human_prompt = f"""Analise interferência L1→L2:
        
        PONTO GRAMATICAL: {grammar_point}
        CONTEXTO: {unit_context}
        VOCABULÁRIO: {', '.join(vocabulary_summary)}
        
        Identifique:
        - Principais erros de interferência português→inglês neste contexto
        - Padrões específicos que brasileiros cometem
        - Estratégias de prevenção contextuais
        - Exemplos de correção apropriados
        
        Forneça análise específica para prevenção de erros L1."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na análise L1 via IA: {str(e)}")
            return "Análise de interferência L1 não disponível no momento"
    
    async def _analyze_assessment_balance_ai(self, used_assessments: Dict[str, Any], unit_type: str, cefr_level: str, content_data: Dict[str, Any]) -> str:
        """Análise contextual via IA do balanceamento de atividades."""
        
        system_prompt = """Você é um especialista em design de avaliações pedagógicas.
        
        Analise o balanceamento de atividades de avaliação considerando uso histórico e contexto atual."""