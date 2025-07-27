# src/services/tips_generator.py
"""
Serviço de geração de estratégias TIPS para unidades lexicais.
Implementação das 6 estratégias TIPS do IVO V2 Guide com seleção inteligente RAG.
CORRIGIDO: Seleção via IA, zero cache, análise contextual completa.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from src.core.unit_models import TipsContent
from src.core.enums import CEFRLevel, LanguageVariant, UnitType, TipStrategy
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES TÉCNICAS (MANTIDAS - METODOLOGIA ESTABELECIDA)
# =============================================================================

TIPS_STRATEGIES = [
    "afixacao",
    "substantivos_compostos", 
    "colocacoes",
    "expressoes_fixas",
    "idiomas",
    "chunks"
]

TIPS_STRATEGY_NAMES = {
    "afixacao": "TIP 1: Afixação",
    "substantivos_compostos": "TIP 2: Substantivos Compostos",
    "colocacoes": "TIP 3: Colocações", 
    "expressoes_fixas": "TIP 4: Expressões Fixas",
    "idiomas": "TIP 5: Idiomas",
    "chunks": "TIP 6: Chunks"
}

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


class TipsGeneratorService:
    """Serviço principal para geração de estratégias TIPS com seleção inteligente IA."""
    
    def __init__(self):
        """Inicializar serviço com IA contextual."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.4,  # Mais baixa para consistência na seleção
            max_tokens=2048,
            api_key=self.openai_config.openai_api_key
        )
        
        logger.info("✅ TipsGeneratorService inicializado com IA contextual e 6 estratégias TIPS")
    
    async def generate_tips_for_unit(self, tips_params: Dict[str, Any]) -> TipsContent:
        """
        Gerar estratégias TIPS para unidade lexical com seleção inteligente IA + RAG.
        
        Args:
            tips_params: Parâmetros com contexto da unidade, hierarquia e RAG
            
        Returns:
            TipsContent completo com estratégia selecionada e aplicada
        """
        try:
            start_time = time.time()
            
            # Extrair parâmetros
            unit_data = tips_params.get("unit_data", {})
            content_data = tips_params.get("content_data", {})
            hierarchy_context = tips_params.get("hierarchy_context", {})
            rag_context = tips_params.get("rag_context", {})
            
            logger.info(f"🎯 Gerando estratégia TIPS para unidade {unit_data.get('title', 'Unknown')}")
            
            # 1. Construir contexto pedagógico enriquecido
            enriched_context = await self._build_pedagogical_context(
                unit_data, content_data, hierarchy_context, rag_context
            )
            
            # 2. ANÁLISE VIA IA: Seleção inteligente da estratégia TIPS
            selected_strategy = await self._select_optimal_tips_strategy_ai(enriched_context)
            
            # 3. ANÁLISE VIA IA: Gerar informações contextuais da estratégia
            strategy_info = await self._analyze_strategy_context_ai(
                selected_strategy, enriched_context
            )
            
            # 4. ANÁLISE VIA IA: Prompt específico para a estratégia
            tips_prompt = await self._build_strategy_specific_prompt_ai(
                selected_strategy, strategy_info, enriched_context
            )
            
            # 5. Gerar conteúdo TIPS via LLM
            raw_tips = await self._generate_tips_llm(tips_prompt)
            
            # 6. ANÁLISE VIA IA: Processar e estruturar TIPS
            structured_tips = await self._process_and_structure_tips_ai(
                raw_tips, selected_strategy, enriched_context
            )
            
            # 7. ANÁLISE VIA IA: Enriquecer com componentes fonéticos
            enriched_tips = await self._enrich_with_phonetic_components_ai(
                structured_tips, content_data, selected_strategy
            )
            
            # 8. ANÁLISE VIA IA: Estratégias complementares
            final_tips = await self._add_complementary_strategies_ai(
                enriched_tips, rag_context, selected_strategy
            )
            
            # 9. Construir TipsContent
            tips_content = TipsContent(
                strategy=TipStrategy(selected_strategy),
                title=final_tips["title"],
                explanation=final_tips["explanation"],
                examples=final_tips["examples"],
                practice_suggestions=final_tips["practice_suggestions"],
                memory_techniques=final_tips["memory_techniques"],
                vocabulary_coverage=final_tips["vocabulary_coverage"],
                complementary_strategies=final_tips["complementary_strategies"],
                selection_rationale=final_tips["selection_rationale"],
                phonetic_focus=final_tips["phonetic_focus"],
                pronunciation_tips=final_tips["pronunciation_tips"]
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Estratégia TIPS '{selected_strategy}' gerada via IA em {generation_time:.2f}s"
            )
            
            return tips_content
            
        except Exception as e:
            logger.error(f"❌ Erro na geração de TIPS: {str(e)}")
            raise
    
    async def _build_pedagogical_context(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto pedagógico enriquecido (mantido - é estruturação técnica)."""
        
        # Extrair vocabulário da unidade
        vocabulary_items = []
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"]
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        
        # Extrair sentences
        sentences = []
        if content_data.get("sentences") and content_data["sentences"].get("sentences"):
            sentences = [s.get("text", "") for s in content_data["sentences"]["sentences"]]
        
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
                "vocabulary_count": len(vocabulary_words),
                "vocabulary_words": vocabulary_words,
                "vocabulary_items": vocabulary_items,
                "sentences_count": len(sentences),
                "sample_sentences": sentences[:3],
                "has_assessments": bool(content_data.get("assessments"))
            },
            "hierarchy_info": {
                "course_name": hierarchy_context.get("course_name", ""),
                "book_name": hierarchy_context.get("book_name", ""),
                "sequence_order": hierarchy_context.get("sequence_order", 1),
                "target_level": hierarchy_context.get("target_level", unit_data.get("cefr_level"))
            },
            "rag_analysis": {
                "used_strategies": rag_context.get("used_strategies", []),
                "taught_vocabulary": rag_context.get("taught_vocabulary", []),
                "progression_level": rag_context.get("progression_level", "intermediate"),
                "strategy_density": rag_context.get("strategy_density", 0)
            }
        }
        
        return enriched_context
    
    # =============================================================================
    # ANÁLISES VIA IA (SUBSTITUEM LÓGICA HARD-CODED)
    # =============================================================================

    async def _select_optimal_tips_strategy_ai(self, enriched_context: Dict[str, Any]) -> str:
        """Seleção inteligente da estratégia TIPS via análise IA."""
        
        system_prompt = """Você é um especialista em metodologia TIPS para ensino de vocabulário.
        
        Analise o contexto fornecido e selecione a estratégia TIPS mais apropriada das 6 disponíveis:
        
        1. afixacao - Prefixos e sufixos para expansão sistemática
        2. substantivos_compostos - Agrupamento temático por campo semântico  
        3. colocacoes - Combinações naturais de palavras
        4. expressoes_fixas - Frases cristalizadas e fórmulas funcionais
        5. idiomas - Expressões com significado figurativo
        6. chunks - Blocos funcionais para fluência automática
        
        Considere: vocabulário específico, nível CEFR, contexto da unidade, estratégias já usadas (RAG)."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        rag_analysis = enriched_context["rag_analysis"]
        
        human_prompt = f"""Selecione a estratégia TIPS ideal para:
        
        UNIDADE:
        - Título: {unit_info['title']}
        - Contexto: {unit_info['context']}
        - Nível: {unit_info['cefr_level']}
        - Tipo: {unit_info['unit_type']}
        
        VOCABULÁRIO ({content_analysis['vocabulary_count']} palavras):
        {', '.join(content_analysis['vocabulary_words'][:15])}
        
        HIERARQUIA:
        - Curso: {enriched_context['hierarchy_info']['course_name']}
        - Livro: {enriched_context['hierarchy_info']['book_name']}  
        - Sequência: Unidade {enriched_context['hierarchy_info']['sequence_order']}
        
        RAG (Balanceamento):
        - Estratégias já usadas: {', '.join(rag_analysis['used_strategies'])}
        - Nível de progressão: {rag_analysis['progression_level']}
        - Densidade de estratégias: {rag_analysis['strategy_density']}
        
        ANÁLISE REQUERIDA:
        1. Examine padrões no vocabulário (afixos, compostos, colocações, etc.)
        2. Considere adequação ao nível {unit_info['cefr_level']}
        3. Analise balanceamento com estratégias já usadas
        4. Avalie potencial pedagógico para este contexto específico
        
        Retorne APENAS o nome da estratégia escolhida (ex: "afixacao", "chunks", etc.)."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            selected = response.content.strip().lower()
            
            # Validar se é estratégia válida
            if selected in TIPS_STRATEGIES:
                return selected
            else:
                # Tentar encontrar na resposta
                for strategy in TIPS_STRATEGIES:
                    if strategy in selected:
                        return strategy
                
                logger.warning(f"IA retornou estratégia inválida: {selected}")
                return "chunks"  # Fallback seguro
                
        except Exception as e:
            logger.warning(f"Erro na seleção IA: {str(e)}")
            return await self._fallback_strategy_selection(enriched_context)

    async def _analyze_strategy_context_ai(
        self, 
        selected_strategy: str, 
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Análise contextual via IA das informações específicas da estratégia."""
        
        system_prompt = f"""Você é um especialista na estratégia TIPS "{TIPS_STRATEGY_NAMES[selected_strategy]}".
        
        Analise como aplicar esta estratégia específica ao contexto fornecido, considerando o vocabulário e situação pedagógica."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Analise a aplicação da estratégia "{selected_strategy}" para:
        
        CONTEXTO: {unit_info['context']}
        VOCABULÁRIO: {', '.join(content_analysis['vocabulary_words'][:12])}
        NÍVEL: {unit_info['cefr_level']}
        
        Forneça análise específica em formato JSON:
        {{
            "description": "Como esta estratégia funciona neste contexto específico",
            "implementation_guide": "Como aplicar especificamente a este vocabulário",
            "cefr_adaptation": "Adaptação específica para {unit_info['cefr_level']} neste contexto",
            "vocabulary_analysis": "Como o vocabulário se adequa a esta estratégia",
            "phonetic_aspects": ["aspecto fonético 1", "aspecto fonético 2"],
            "complementary_strategies": ["estratégia complementar 1", "estratégia complementar 2"]
        }}"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Tentar parsear JSON
            try:
                if "```json" in response.content:
                    json_content = response.content.split("```json")[1].split("```")[0].strip()
                else:
                    json_content = response.content
                
                strategy_info = json.loads(json_content)
                return strategy_info
                
            except json.JSONDecodeError:
                logger.warning("Erro no parsing JSON da análise de estratégia")
                return self._minimal_strategy_info_fallback(selected_strategy)
                
        except Exception as e:
            logger.warning(f"Erro na análise de estratégia via IA: {str(e)}")
            return self._minimal_strategy_info_fallback(selected_strategy)

    async def _build_strategy_specific_prompt_ai(
        self,
        selected_strategy: str,
        strategy_info: Dict[str, Any], 
        enriched_context: Dict[str, Any]
    ) -> List[Any]:
        """Construir prompt específico via IA para a estratégia TIPS."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        hierarchy_info = enriched_context["hierarchy_info"]
        rag_analysis = enriched_context["rag_analysis"]
        
        # ANÁLISE VIA IA: Personalizar prompt baseado no contexto
        prompt_customization = await self._customize_prompt_for_context_ai(
            selected_strategy, strategy_info, enriched_context
        )
        
        system_prompt = f"""You are an expert English teacher implementing the TIPS methodology for lexical units.

SELECTED STRATEGY: {TIPS_STRATEGY_NAMES[selected_strategy]}
STRATEGY CONTEXT: {strategy_info.get('description', 'Estratégia de vocabulário')}

UNIT CONTEXT:
- Title: {unit_info['title']}
- Context: {unit_info['context']}
- Level: {unit_info['cefr_level']}
- Language Variant: {unit_info['language_variant']}
- Main Aim: {unit_info['main_aim']}

VOCABULARY TO INTEGRATE ({content_analysis['vocabulary_count']} words):
{', '.join(content_analysis['vocabulary_words'][:15])}

CONTEXTUAL STRATEGY GUIDELINES:
{strategy_info.get('implementation_guide', 'Apply strategy contextually')}

CEFR {unit_info['cefr_level']} CONTEXTUAL ADAPTATION:
{strategy_info.get('cefr_adaptation', f'Standard {selected_strategy} for {unit_info["cefr_level"]}')}

VOCABULARY ANALYSIS FOR THIS STRATEGY:
{strategy_info.get('vocabulary_analysis', 'Vocabulary suitable for strategy application')}

RAG CONTEXT:
- Used strategies: {', '.join(rag_analysis['used_strategies'])}
- Progression level: {rag_analysis['progression_level']}
- Strategy density: {rag_analysis['strategy_density']:.2f}

PHONETIC INTEGRATION:
- Focus areas: {', '.join(strategy_info.get('phonetic_aspects', ['general pronunciation']))}
- Include pronunciation guidance specific to {selected_strategy}
- Address {unit_info['language_variant']} pronunciation patterns

CUSTOMIZATION INSTRUCTIONS:
{prompt_customization}

GENERATION REQUIREMENTS:
1. Apply the {TIPS_STRATEGY_NAMES[selected_strategy]} specifically to this context
2. Create practical examples using unit vocabulary
3. Provide memory techniques aligned with the strategy
4. Include practice suggestions that reinforce the strategy
5. Add pronunciation tips specific to this strategy type
6. Ensure {unit_info['cefr_level']} level appropriateness for context "{unit_info['context']}"

OUTPUT FORMAT: Return valid JSON with this exact structure:
{{
  "title": "{TIPS_STRATEGY_NAMES[selected_strategy]}",
  "explanation": "Clear explanation of how this strategy works in this specific context",
  "examples": [
    "Example 1 using unit vocabulary",
    "Example 2 showing the pattern", 
    "Example 3 demonstrating application"
  ],
  "practice_suggestions": [
    "Practice activity 1 for this context",
    "Practice activity 2 specific to vocabulary"
  ],
  "memory_techniques": [
    "Memory technique 1 for this strategy",
    "Memory technique 2 adapted to context"
  ],
  "vocabulary_coverage": ["word1", "word2", "word3"],
  "phonetic_focus": ["phonetic_aspect1", "phonetic_aspect2"],
  "pronunciation_tips": [
    "Pronunciation tip 1 for this strategy",
    "Pronunciation tip 2 for this context"
  ]
}}"""

        human_prompt = f"""Apply the {TIPS_STRATEGY_NAMES[selected_strategy]} strategy to the vocabulary: {', '.join(content_analysis['vocabulary_words'][:10])}

Context: {unit_info['context']}
Level: {unit_info['cefr_level']}

Specific focus for this strategy:
{strategy_info.get('implementation_guide', 'Standard application')}

Generate contextual TIPS content that:
1. Demonstrates how this strategy helps with the specific vocabulary
2. Provides practical application in the unit context "{unit_info['context']}"
3. Includes memory techniques that leverage this strategy
4. Addresses pronunciation patterns relevant to this strategy type

Generate the JSON structure now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]

    async def _customize_prompt_for_context_ai(
        self,
        selected_strategy: str,
        strategy_info: Dict[str, Any],
        enriched_context: Dict[str, Any]
    ) -> str:
        """Personalizar prompt via IA baseado no contexto específico."""
        
        system_prompt = """Você é um especialista em personalização de prompts educacionais.
        
        Gere instruções específicas para customizar o prompt da estratégia TIPS baseado no contexto único."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        
        human_prompt = f"""Gere customizações específicas para:
        
        ESTRATÉGIA: {selected_strategy}
        CONTEXTO DA UNIDADE: {unit_info['context']}
        VOCABULÁRIO: {', '.join(content_analysis['vocabulary_words'][:8])}
        NÍVEL: {unit_info['cefr_level']}
        
        Retorne instruções específicas para customizar a aplicação desta estratégia:
        - Como adaptar especificamente para este contexto
        - Que aspectos enfatizar no vocabulário
        - Como conectar com a situação comunicativa
        - Adaptações pedagógicas específicas
        
        Seja específico para esta combinação única de estratégia + contexto + vocabulário."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na customização do prompt via IA: {str(e)}")
            return f"Apply {selected_strategy} specifically to {unit_info['context']} context with provided vocabulary"

    async def _process_and_structure_tips_ai(
        self, 
        raw_tips: Dict[str, Any], 
        selected_strategy: str,
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processar e estruturar dados de TIPS usando análise IA."""
        
        system_prompt = """Você é um especialista em estruturação de conteúdo educacional TIPS.
        
        Processe e melhore o conteúdo TIPS fornecido, garantindo qualidade pedagógica e adequação contextual."""
        
        human_prompt = f"""Processe e melhore este conteúdo TIPS:
        
        CONTEÚDO BRUTO: {str(raw_tips)}
        ESTRATÉGIA: {selected_strategy}
        CONTEXTO: {enriched_context['unit_info']['context']}
        VOCABULÁRIO: {', '.join(enriched_context['content_analysis']['vocabulary_words'][:10])}
        
        Garanta:
        1. Explicação clara e contextual
        2. Mínimo 3 exemplos usando vocabulário da unidade
        3. Mínimo 2 sugestões de prática específicas
        4. Mínimo 2 técnicas de memória adequadas
        5. Cobertura apropriada do vocabulário
        6. Dicas fonéticas relevantes
        
        Retorne em formato JSON estruturado e complete campos faltantes se necessário."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Tentar parsear resposta estruturada
            try:
                if "```json" in response.content:
                    json_content = response.content.split("```json")[1].split("```")[0].strip()
                else:
                    json_content = response.content
                
                processed_tips = json.loads(json_content)
                
                # Adicionar selection_rationale via IA
                rationale = await self._generate_selection_rationale_ai(
                    selected_strategy, enriched_context
                )
                processed_tips["selection_rationale"] = rationale
                
                return processed_tips
                
            except json.JSONDecodeError:
                logger.warning("Erro no parsing do processamento IA, usando fallback técnico")
                return self._technical_process_fallback(raw_tips, selected_strategy, enriched_context)
                
        except Exception as e:
            logger.warning(f"Erro no processamento IA: {str(e)}")
            return self._technical_process_fallback(raw_tips, selected_strategy, enriched_context)

    async def _enrich_with_phonetic_components_ai(
        self, 
        structured_tips: Dict[str, Any], 
        content_data: Dict[str, Any],
        selected_strategy: str
    ) -> Dict[str, Any]:
        """Enriquecer TIPS com componentes fonéticos via análise IA."""
        
        system_prompt = f"""Você é um especialista em fonética aplicada à estratégia TIPS "{selected_strategy}".
        
        Analise o vocabulário e adicione componentes fonéticos específicos para esta estratégia."""
        
        vocabulary_items = content_data.get("vocabulary", {}).get("items", [])[:5]
        vocab_phonetic = [f"{item.get('word', '')}: {item.get('phoneme', '')}" for item in vocabulary_items]
        
        human_prompt = f"""Adicione componentes fonéticos para:
        
        ESTRATÉGIA: {selected_strategy}
        VOCABULÁRIO COM FONEMAS: {'; '.join(vocab_phonetic)}
        TIPS ATUAL: {str(structured_tips)}
        
        Analise e adicione:
        1. Focos fonéticos específicos para esta estratégia
        2. Dicas de pronúncia relevantes ao tipo de estratégia
        3. Padrões fonéticos que apoiam a memorização
        
        Para estratégia "{selected_strategy}":
        - Que aspectos fonéticos são mais relevantes?
        - Como a pronúncia pode reforçar a estratégia?
        - Que dicas ajudam na aplicação prática?
        
        Retorne campos:
        - phonetic_focus: [lista de aspectos fonéticos]
        - pronunciation_tips: [lista de dicas específicas]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair informações fonéticas da resposta
            phonetic_focus = []
            pronunciation_tips = []
            
            lines = response.content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if 'phonetic_focus' in line.lower() or 'foco fonético' in line.lower():
                    current_section = 'phonetic'
                elif 'pronunciation_tips' in line.lower() or 'dicas' in line.lower():
                    current_section = 'pronunciation'
                elif line.startswith(('-', '•', '1.', '2.', '3.')):
                    content = line.lstrip('-•123456789. ')
                    if current_section == 'phonetic' and content:
                        phonetic_focus.append(content)
                    elif current_section == 'pronunciation' and content:
                        pronunciation_tips.append(content)
            
            # Adicionar aos tips estruturados
            if phonetic_focus:
                structured_tips["phonetic_focus"] = phonetic_focus[:3]
            if pronunciation_tips:
                structured_tips["pronunciation_tips"] = pronunciation_tips[:3]
            
            # Garantir campos mínimos
            if not structured_tips.get("phonetic_focus"):
                structured_tips["phonetic_focus"] = [f"Pronunciation patterns for {selected_strategy}"]
            if not structured_tips.get("pronunciation_tips"):
                structured_tips["pronunciation_tips"] = [f"Practice clear articulation for {selected_strategy}"]
            
            return structured_tips
            
        except Exception as e:
            logger.warning(f"Erro no enriquecimento fonético via IA: {str(e)}")
            
            # Fallback técnico
            fallback_complementary = [s for s in TIPS_STRATEGIES if s != selected_strategy and used_strategies.count(s) < 2]
            enriched_tips["complementary_strategies"] = fallback_complementary[:3]
            
            return enriched_tips

    async def _generate_selection_rationale_ai(
        self, 
        selected_strategy: str, 
        enriched_context: Dict[str, Any]
    ) -> str:
        """Gerar justificativa de seleção via IA."""
        
        system_prompt = """Você é um especialista em justificação pedagógica de estratégias TIPS.
        
        Explique de forma clara e concisa por que esta estratégia foi selecionada para este contexto específico."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        rag_analysis = enriched_context["rag_analysis"]
        
        human_prompt = f"""Justifique a seleção da estratégia "{selected_strategy}" para:
        
        CONTEXTO: {unit_info['context']}
        VOCABULÁRIO: {', '.join(content_analysis['vocabulary_words'][:8])}
        NÍVEL: {unit_info['cefr_level']}
        ESTRATÉGIAS USADAS: {', '.join(rag_analysis['used_strategies'])}
        
        Explique:
        1. Por que esta estratégia é ideal para este vocabulário
        2. Como se adequa ao nível {unit_info['cefr_level']}
        3. Como contribui para o balanceamento pedagógico
        
        Seja específico e pedagógico. Máximo 2-3 frases."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"Erro na geração de justificativa via IA: {str(e)}")
            return f"Estratégia {selected_strategy} selecionada para adequação ao contexto {unit_info['context']} e balanceamento pedagógico"

    # =============================================================================
    # FALLBACKS TÉCNICOS (APENAS PARA ERROS DE IA)
    # =============================================================================

    async def _fallback_strategy_selection(self, enriched_context: Dict[str, Any]) -> str:
        """Seleção de fallback quando IA falha (algoritmo técnico simples)."""
        
        unit_info = enriched_context["unit_info"]
        rag_analysis = enriched_context["rag_analysis"]
        
        cefr_level = unit_info["cefr_level"]
        used_strategies = rag_analysis["used_strategies"]
        
        # Estratégias por nível (constante técnica)
        level_preferences = {
            "A1": ["chunks", "substantivos_compostos", "expressoes_fixas"],
            "A2": ["substantivos_compostos", "chunks", "expressoes_fixas"],
            "B1": ["afixacao", "colocacoes", "expressoes_fixas"],
            "B2": ["colocacoes", "afixacao", "expressoes_fixas"],
            "C1": ["colocacoes", "idiomas", "afixacao"],
            "C2": ["idiomas", "colocacoes", "afixacao"]
        }
        
        preferences = level_preferences.get(cefr_level, level_preferences["A2"])
        
        # Selecionar menos usada
        for strategy in preferences:
            if used_strategies.count(strategy) < 2:
                return strategy
        
        return "chunks"  # Fallback final

    def _minimal_strategy_info_fallback(self, selected_strategy: str) -> Dict[str, Any]:
        """Info mínima da estratégia em caso de erro de IA."""
        
        return {
            "description": f"Aplicação da estratégia {TIPS_STRATEGY_NAMES[selected_strategy]}",
            "implementation_guide": f"Aplicar {selected_strategy} ao vocabulário específico da unidade",
            "cefr_adaptation": "Adaptação contextual apropriada ao nível",
            "vocabulary_analysis": "Vocabulário adequado para aplicação da estratégia",
            "phonetic_aspects": ["pronunciation_focus"],
            "complementary_strategies": [s for s in TIPS_STRATEGIES if s != selected_strategy][:2]
        }

    def _technical_process_fallback(
        self, 
        raw_tips: Dict[str, Any], 
        selected_strategy: str,
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processamento técnico fallback quando IA falha."""
        
        # Extrair e validar campos obrigatórios (processamento técnico)
        title = raw_tips.get("title", TIPS_STRATEGY_NAMES[selected_strategy])
        explanation = raw_tips.get("explanation", f"Aplicação da estratégia {selected_strategy}")
        examples = raw_tips.get("examples", [])
        practice_suggestions = raw_tips.get("practice_suggestions", [])
        memory_techniques = raw_tips.get("memory_techniques", [])
        
        vocabulary_words = enriched_context["content_analysis"]["vocabulary_words"]
        
        # Completar campos faltantes com dados mínimos
        if len(examples) < 3:
            for i, word in enumerate(vocabulary_words[:3]):
                if i >= len(examples):
                    examples.append(f"Use '{word}' to demonstrate {selected_strategy} strategy")
        
        if len(practice_suggestions) < 2:
            practice_suggestions.extend([
                f"Practice identifying {selected_strategy} patterns",
                f"Create examples using {selected_strategy} approach"
            ])
        
        if len(memory_techniques) < 2:
            memory_techniques.extend([
                f"Group words by {selected_strategy} patterns",
                f"Use visual associations for {selected_strategy}"
            ])
        
        return {
            "title": title,
            "explanation": explanation,
            "examples": examples[:5],
            "practice_suggestions": practice_suggestions[:3],
            "memory_techniques": memory_techniques[:3],
            "vocabulary_coverage": vocabulary_words[:8],
            "phonetic_focus": ["pronunciation_awareness"],
            "pronunciation_tips": ["Practice clear articulation"],
            "selection_rationale": f"Estratégia {selected_strategy} apropriada para o contexto"
        }

    async def _generate_tips_llm(self, prompt_messages: List[Any]) -> Dict[str, Any]:
        """Gerar conteúdo TIPS usando LLM (sem cache)."""
        try:
            logger.info("🤖 Consultando LLM para geração de estratégia TIPS...")
            
            # Gerar usando LangChain (sem cache)
            response = await self.llm.ainvoke(prompt_messages)
            content = response.content
            
            # Tentar parsear JSON
            try:
                # Limpar response se necessário
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].strip()
                
                tips_data = json.loads(content)
                
                if not isinstance(tips_data, dict):
                    raise ValueError("Response não é um objeto")
                
                logger.info(f"✅ LLM retornou estratégia TIPS com {len(tips_data.get('examples', []))} exemplos")
                return tips_data
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao parsear JSON, tentando extração manual: {str(e)}")
                return self._extract_tips_from_text(content)
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            return await self._generate_fallback_tips_ai()

    async def _generate_fallback_tips_ai(self) -> Dict[str, Any]:
        """Gerar TIPS de fallback via IA quando LLM principal falha."""
        
        system_prompt = """Você é um professor de inglês gerando estratégia TIPS básica de emergência.
        
        Crie conteúdo TIPS simples e útil."""
        
        human_prompt = """Gere estratégia TIPS básica em formato JSON:
        
        {
          "title": "TIP: Estratégia de Vocabulário",
          "explanation": "Explicação clara da estratégia",
          "examples": ["Exemplo 1", "Exemplo 2", "Exemplo 3"],
          "practice_suggestions": ["Prática 1", "Prática 2"],
          "memory_techniques": ["Técnica 1", "Técnica 2"],
          "vocabulary_coverage": ["word1", "word2"],
          "phonetic_focus": ["pronunciation"],
          "pronunciation_tips": ["Dica 1", "Dica 2"]
        }"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            tips_data = json.loads(content)
            
            if isinstance(tips_data, dict):
                logger.info("✅ Fallback IA gerou TIPS de emergência")
                return tips_data
            else:
                raise ValueError("Fallback IA não retornou dict válido")
                
        except Exception as e:
            logger.warning(f"⚠️ Fallback IA também falhou: {str(e)}")
            return self._minimal_hardcoded_fallback()

    def _minimal_hardcoded_fallback(self) -> Dict[str, Any]:
        """Fallback hard-coded mínimo apenas para emergências críticas."""
        logger.warning("⚠️ Usando fallback hard-coded mínimo - apenas para emergências")
        
        return {
            "title": "TIP: Estratégia Contextual",
            "explanation": "Esta estratégia foca em aprender vocabulário através do contexto específico da unidade.",
            "examples": [
                "Use as palavras novas em frases contextualizadas",
                "Conecte vocabulário novo com palavras conhecidas", 
                "Pratique em situações comunicativas reais"
            ],
            "practice_suggestions": [
                "Crie frases próprias com cada palavra nova",
                "Pratique conversações usando o vocabulário"
            ],
            "memory_techniques": [
                "Use associações visuais com as palavras",
                "Agrupe palavras por temas ou situações"
            ],
            "vocabulary_coverage": ["vocabulary", "context", "practice"],
            "phonetic_focus": ["clear_articulation"],
            "pronunciation_tips": [
                "Preste atenção à pronúncia clara",
                "Pratique repetição para melhorar memória"
            ]
        }

    def _extract_tips_from_text(self, text: str) -> Dict[str, Any]:
        """Extrair TIPS de texto quando JSON parsing falha (parser técnico)."""
        
        tips_data = {
            "title": "",
            "explanation": "",
            "examples": [],
            "practice_suggestions": [],
            "memory_techniques": [],
            "vocabulary_coverage": [],
            "phonetic_focus": [],
            "pronunciation_tips": []
        }
        
        lines = text.split('\n')
        current_section = None
        current_list = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detectar seções (parser técnico)
            if any(keyword in line.lower() for keyword in ['title', 'tip']):
                tips_data["title"] = line.split(':', 1)[-1].strip() if ':' in line else line
            elif 'explanation' in line.lower():
                if current_section and current_list:
                    tips_data[current_section].extend(current_list)
                current_section = 'explanation'
                current_list = []
                if ':' in line:
                    explanation_text = line.split(':', 1)[-1].strip()
                    if explanation_text:
                        tips_data["explanation"] = explanation_text
            elif 'example' in line.lower():
                if current_section and current_list:
                    tips_data[current_section].extend(current_list)
                current_section = 'examples'
                current_list = []
            elif 'practice' in line.lower():
                if current_section and current_list:
                    tips_data[current_section].extend(current_list)
                current_section = 'practice_suggestions'
                current_list = []
            elif 'memory' in line.lower():
                if current_section and current_list:
                    tips_data[current_section].extend(current_list)
                current_section = 'memory_techniques'
                current_list = []
            elif 'pronunciation' in line.lower():
                if current_section and current_list:
                    tips_data[current_section].extend(current_list)
                current_section = 'pronunciation_tips'
                current_list = []
            elif any(marker in line for marker in ['1.', '2.', '3.', '-', '•']):
                if current_section and current_section != 'explanation':
                    cleaned_line = line.lstrip('123456789.-•').strip()
                    if cleaned_line:
                        current_list.append(cleaned_line)
            elif current_section == 'explanation':
                tips_data["explanation"] += " " + line
        
        # Adicionar última seção
        if current_section and current_list:
            tips_data[current_section].extend(current_list)
        
        # Preencher campos faltantes (dados técnicos mínimos)
        if not tips_data["title"]:
            tips_data["title"] = "TIP: Estratégia de Vocabulário"
        
        if not tips_data["explanation"]:
            tips_data["explanation"] = "Esta estratégia ajuda na memorização e uso eficaz do vocabulário."
        
        if not tips_data["examples"]:
            tips_data["examples"] = ["Exemplo prático da estratégia"]
        
        if not tips_data["practice_suggestions"]:
            tips_data["practice_suggestions"] = ["Pratique identificando padrões"]
        
        return tips_data

    # =============================================================================
    # UTILITY METHODS (MANTIDOS - INTERFACES TÉCNICAS)
    # =============================================================================

    async def get_service_status(self) -> Dict[str, Any]:
        """Status do serviço (utilitário técnico)."""
        return {
            "service": "TipsGeneratorService",
            "status": "active",
            "strategies": TIPS_STRATEGIES,
            "strategy_names": TIPS_STRATEGY_NAMES,
            "ai_integration": "100% contextual analysis",
            "cache_system": "disabled_as_requested",
            "storage": "supabase_integration",
            "ai_methods": [
                "_select_optimal_tips_strategy_ai",
                "_analyze_strategy_context_ai",
                "_build_strategy_specific_prompt_ai",
                "_customize_prompt_for_context_ai",
                "_process_and_structure_tips_ai",
                "_enrich_with_phonetic_components_ai",
                "_add_complementary_strategies_ai",
                "_generate_selection_rationale_ai"
            ]
        }

    async def validate_tips_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validar parâmetros de geração de TIPS."""
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
        if not unit_data.get("context"):
            validation_result["warnings"].append("Contexto da unidade vazio - pode afetar seleção")
        
        content_data = params.get("content_data", {})
        if not content_data.get("vocabulary", {}).get("items"):
            validation_result["warnings"].append("Vocabulário não disponível")
        
        return validation_result


# =============================================================================
# UTILITY FUNCTIONS REFINADAS (IA + CONSTANTES TÉCNICAS)
# =============================================================================

async def validate_tips_strategy_selection_ai(
    vocabulary_items: List[Dict[str, Any]], 
    cefr_level: str,
    used_strategies: List[str],
    unit_context: str
) -> str:
    """Validar e sugerir estratégia TIPS via IA."""
    
    # Usar serviço principal para análise IA
    tips_service = TipsGeneratorService()
    
    enriched_context = {
        "unit_info": {"cefr_level": cefr_level, "context": unit_context},
        "content_analysis": {"vocabulary_words": [item.get("word", "") for item in vocabulary_items]},
        "rag_analysis": {"used_strategies": used_strategies}
    }
    
    try:
        selected_strategy = await tips_service._select_optimal_tips_strategy_ai(enriched_context)
        return selected_strategy
    except Exception as e:
        logger.warning(f"Erro na validação IA: {str(e)}")
        return await tips_service._fallback_strategy_selection(enriched_context)


async def analyze_tips_effectiveness_ai(
    tips_content: TipsContent,
    vocabulary_items: List[Dict[str, Any]],
    cefr_level: str,
    unit_context: str
) -> Dict[str, Any]:
    """Analisar eficácia da estratégia TIPS via IA."""
    
    tips_service = TipsGeneratorService()
    
    system_prompt = """Você é um especialista em avaliação de eficácia pedagógica de estratégias TIPS.
    
    Analise a qualidade e eficácia da estratégia aplicada considerando o contexto específico."""
    
    human_prompt = f"""Avalie a eficácia desta estratégia TIPS:
    
    ESTRATÉGIA: {tips_content.strategy.value}
    EXPLICAÇÃO: {tips_content.explanation[:200]}...
    EXEMPLOS: {len(tips_content.examples)} exemplos
    VOCABULÁRIO: {', '.join([item.get('word', '') for item in vocabulary_items[:8]])}
    NÍVEL: {cefr_level}
    CONTEXTO: {unit_context}
    
    Avalie (0.0 a 1.0):
    1. Integração com vocabulário
    2. Adequação ao nível CEFR
    3. Coerência da estratégia
    4. Consciência fonética
    
    Retorne scores em formato JSON:
    {{
        "vocabulary_integration": 0.8,
        "cefr_appropriateness": 0.9,
        "strategy_coherence": 0.7,
        "phonetic_awareness": 0.6,
        "overall_score": 0.75
    }}"""
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await tips_service.llm.ainvoke(messages)
        
        # Tentar parsear JSON
        try:
            if "```json" in response.content:
                json_content = response.content.split("```json")[1].split("```")[0].strip()
            else:
                json_content = response.content
                
            effectiveness_metrics = json.loads(json_content)
            return effectiveness_metrics
            
        except json.JSONDecodeError:
            logger.warning("Erro no parsing da análise de eficácia")
            return _technical_effectiveness_fallback(tips_content, vocabulary_items, cefr_level)
            
    except Exception as e:
        logger.warning(f"Erro na análise de eficácia via IA: {str(e)}")
        return _technical_effectiveness_fallback(tips_content, vocabulary_items, cefr_level)


def _technical_effectiveness_fallback(
    tips_content: TipsContent,
    vocabulary_items: List[Dict[str, Any]], 
    cefr_level: str
) -> Dict[str, Any]:
    """Análise técnica de eficácia quando IA falha."""
    
    # Análise técnica básica
    vocabulary_words = {item.get("word", "").lower() for item in vocabulary_items}
    coverage_words = {word.lower() for word in tips_content.vocabulary_coverage}
    
    # Integração com vocabulário (cálculo técnico)
    if vocabulary_words:
        integration_score = len(coverage_words & vocabulary_words) / len(vocabulary_words)
    else:
        integration_score = 0.5
    
    # Adequação CEFR (mapeamento técnico)
    cefr_mapping = {
        "chunks": {"A1": 0.9, "A2": 0.8, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "substantivos_compostos": {"A1": 0.8, "A2": 0.9, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "afixacao": {"A1": 0.6, "A2": 0.7, "B1": 0.9, "B2": 0.8, "C1": 0.7, "C2": 0.6},
        "colocacoes": {"A1": 0.3, "A2": 0.5, "B1": 0.7, "B2": 0.9, "C1": 0.8, "C2": 0.7},
        "expressoes_fixas": {"A1": 0.7, "A2": 0.8, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "idiomas": {"A1": 0.2, "A2": 0.3, "B1": 0.5, "B2": 0.7, "C1": 0.9, "C2": 0.9}
    }
    
    strategy_name = tips_content.strategy.value
    cefr_score = cefr_mapping.get(strategy_name, {}).get(cefr_level, 0.7)
    
    # Coerência da estratégia (análise técnica)
    has_explanation = len(tips_content.explanation) > 50
    has_examples = len(tips_content.examples) >= 3
    has_practice = len(tips_content.practice_suggestions) >= 2
    has_memory = len(tips_content.memory_techniques) >= 2
    
    coherence_score = sum([has_explanation, has_examples, has_practice, has_memory]) / 4
    
    # Consciência fonética (análise técnica)
    phonetic_score = 0.0
    if tips_content.phonetic_focus:
        phonetic_score += 0.5
    if tips_content.pronunciation_tips:
        phonetic_score += 0.5
    
    # Score geral
    overall_score = (integration_score + cefr_score + coherence_score + phonetic_score) / 4
    
    return {
        "vocabulary_integration": integration_score,
        "cefr_appropriateness": cefr_score,
        "strategy_coherence": coherence_score,
        "phonetic_awareness": phonetic_score,
        "overall_score": overall_score
    }


async def generate_strategy_recommendations_ai(
    vocabulary_items: List[Dict[str, Any]],
    cefr_level: str,
    used_strategies: List[str],
    unit_context: str
) -> List[str]:
    """Gerar recomendações de estratégias via IA."""
    
    tips_service = TipsGeneratorService()
    
    system_prompt = """Você é um especialista em recomendação de estratégias pedagógicas TIPS.
    
    Analise o contexto e gere recomendações específicas para otimizar o aprendizado."""
    
    vocabulary_words = [item.get("word", "") for item in vocabulary_items[:10]]
    
    human_prompt = f"""Gere recomendações de estratégias TIPS para:
    
    VOCABULÁRIO: {', '.join(vocabulary_words)}
    NÍVEL: {cefr_level}
    CONTEXTO: {unit_context}
    ESTRATÉGIAS JÁ USADAS: {', '.join(used_strategies)}
    
    Estratégias disponíveis: {', '.join(TIPS_STRATEGIES)}
    
    Analise e recomende:
    1. Estratégias que funcionariam bem com este vocabulário
    2. Adequação ao nível {cefr_level}
    3. Balanceamento com estratégias já usadas
    4. Sequência pedagógica ideal
    
    Retorne máximo 3 recomendações específicas com justificativas breves."""
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await tips_service.llm.ainvoke(messages)
        
        # Extrair recomendações da resposta
        recommendations = []
        lines = response.content.split('\n')
        
        for line in lines:
            line = line.strip()
            if any(strategy in line.lower() for strategy in TIPS_STRATEGIES):
                # Encontrar qual estratégia está mencionada
                for strategy in TIPS_STRATEGIES:
                    if strategy in line.lower():
                        if line not in recommendations:  # Evitar duplicatas
                            recommendations.append(line[:200])  # Limitar tamanho
                        break
        
        return recommendations[:3]
        
    except Exception as e:
        logger.warning(f"Erro na geração de recomendações via IA: {str(e)}")
        
        # Fallback técnico
        fallback_recommendations = []
        
        # Recomendar estratégias menos usadas
        strategy_counts = {s: used_strategies.count(s) for s in TIPS_STRATEGIES}
        least_used = sorted(strategy_counts.items(), key=lambda x: x[1])
        
        for strategy, count in least_used[:3]:
            if count < 2:
                fallback_recommendations.append(f"Considere {TIPS_STRATEGY_NAMES[strategy]} - adequada para {cefr_level}")
        
        return fallback_recommendations[:3]

async def _add_complementary_strategies_ai(
        self, 
        enriched_tips: Dict[str, Any], 
        rag_context: Dict[str, Any],
        selected_strategy: str
    ) -> Dict[str, Any]:
        """Adicionar estratégias complementares via análise IA."""
        
        system_prompt = """Você é um especialista em sequenciação pedagógica de estratégias TIPS.
        
        Analise e recomende estratégias complementares considerando a estratégia atual e histórico de uso."""
        
        used_strategies = rag_context.get("used_strategies", [])
        
        human_prompt = f"""Recomende estratégias complementares para:
        
        ESTRATÉGIA ATUAL: {selected_strategy}
        ESTRATÉGIAS JÁ USADAS: {', '.join(used_strategies)}
        
        Estratégias TIPS disponíveis:
        - afixacao
        - substantivos_compostos
        - colocacoes
        - expressoes_fixas
        - idiomas
        - chunks
        
        Analise:
        1. Que estratégias complementam pedagogicamente {selected_strategy}?
        2. Quais não foram overutilizadas (aparecem < 2 vezes em {used_strategies})?
        3. Qual sequência pedagógica faz sentido?
        
        Retorne máximo 3 estratégias complementares em ordem de prioridade.
        Formato: ["estrategia1", "estrategia2", "estrategia3"]"""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Extrair estratégias da resposta
            complementary = []
            response_lower = response.content.lower()
            
            for strategy in TIPS_STRATEGIES:
                if strategy != selected_strategy and strategy in response_lower:
                    strategy_count = used_strategies.count(strategy)
                    if strategy_count < 2:  # Não overutilizada
                        complementary.append(strategy)
            
            enriched_tips["complementary_strategies"] = complementary[:3]
            
            return enriched_tips
            
        except Exception as e:
            logger.warning(f"Erro na análise de estratégias complementares via IA: {str(e)}")
            
            # Fallback técnico
                        # Fallback técnico
            fallback_complementary = [
                s for s in TIPS_STRATEGIES 
                if s != selected_strategy and used_strategies.count(s) < 2
            ]
            enriched_tips["complementary_strategies"] = fallback_complementary[:3]
            
            return enriched_tips
