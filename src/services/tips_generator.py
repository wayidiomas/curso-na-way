# src/services/tips_generator.py
"""
Serviço de geração de estratégias TIPS para unidades lexicais.
Implementação das 6 estratégias TIPS do IVO V2 Guide com seleção inteligente RAG.
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


class TipsGeneratorService:
    """Serviço principal para geração de estratégias TIPS com seleção inteligente RAG."""
    
    def __init__(self):
        """Inicializar serviço com configurações."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.7,  # Criatividade para estratégias variadas
            max_tokens=2048,  # Espaço para estratégia completa
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache simples em memória
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 50
        
        # Base de conhecimento das 6 estratégias TIPS
        self.tips_strategies_db = self._load_tips_strategies_database()
        
        logger.info("✅ TipsGeneratorService inicializado com 6 estratégias TIPS")
    
    async def generate_tips_for_unit(self, tips_params: Dict[str, Any]) -> TipsContent:
        """
        Gerar estratégias TIPS para unidade lexical com seleção inteligente RAG.
        
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
            
            # 2. Seleção inteligente da estratégia TIPS usando RAG
            selected_strategy = await self._select_optimal_tips_strategy(enriched_context)
            
            # 3. Gerar prompt específico para a estratégia selecionada
            tips_prompt = await self._build_strategy_specific_prompt(selected_strategy, enriched_context)
            
            # 4. Gerar conteúdo TIPS via LLM
            raw_tips = await self._generate_tips_llm(tips_prompt)
            
            # 5. Processar e estruturar TIPS
            structured_tips = await self._process_and_structure_tips(raw_tips, selected_strategy, enriched_context)
            
            # 6. Enriquecer com componentes fonéticos
            enriched_tips = await self._enrich_with_phonetic_components(structured_tips, content_data)
            
            # 7. Adicionar seleção de estratégias complementares
            final_tips = await self._add_complementary_strategies(enriched_tips, rag_context)
            
            # 8. Construir TipsContent
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
                f"✅ Estratégia TIPS '{selected_strategy}' gerada em {generation_time:.2f}s"
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
        """Construir contexto pedagógico enriquecido para seleção de estratégia."""
        
        # Extrair vocabulário da unidade
        vocabulary_items = []
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"]
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        
        # Extrair sentences
        sentences = []
        if content_data.get("sentences") and content_data["sentences"].get("sentences"):
            sentences = [s.get("text", "") for s in content_data["sentences"]["sentences"]]
        
        # Analisar padrões no vocabulário para seleção de estratégia
        vocabulary_analysis = await self._analyze_vocabulary_patterns(vocabulary_items)
        
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
                "vocabulary_patterns": vocabulary_analysis,
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
    
    async def _analyze_vocabulary_patterns(self, vocabulary_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analisar padrões no vocabulário para informar seleção de estratégia."""
        
        patterns = {
            "has_affixes": False,
            "has_compounds": False,
            "has_collocations": False,
            "has_fixed_expressions": False,
            "has_idiomatic_potential": False,
            "has_functional_chunks": False,
            "morphological_complexity": "low",
            "semantic_coherence": "medium"
        }
        
        words = [item.get("word", "").lower() for item in vocabulary_items]
        
        # Detectar afixos (TIP 1)
        common_prefixes = ["un", "re", "pre", "dis", "mis", "over", "under"]
        common_suffixes = ["er", "ed", "ing", "ly", "tion", "ness", "ful", "less"]
        
        for word in words:
            if any(word.startswith(prefix) for prefix in common_prefixes):
                patterns["has_affixes"] = True
            if any(word.endswith(suffix) for suffix in common_suffixes):
                patterns["has_affixes"] = True
        
        # Detectar compostos (TIP 2)
        compounds_indicators = ["-", "phone", "room", "book", "house", "work", "time"]
        if any(indicator in word for word in words for indicator in compounds_indicators):
            patterns["has_compounds"] = True
        
        # Detectar potencial para colocações (TIP 3)
        collocation_words = ["make", "take", "get", "have", "do", "heavy", "strong", "big"]
        if any(col_word in words for col_word in collocation_words):
            patterns["has_collocations"] = True
        
        # Detectar expressões fixas potenciais (TIP 4)
        if len(words) > 10 and any(len(word) > 6 for word in words):
            patterns["has_fixed_expressions"] = True
        
        # Detectar idiomas potenciais (TIP 5)
        idiomatic_indicators = ["under", "over", "break", "catch", "fall", "get", "come", "go"]
        if any(indicator in words for indicator in idiomatic_indicators):
            patterns["has_idiomatic_potential"] = True
        
        # Detectar chunks funcionais (TIP 6)
        functional_indicators = ["would", "like", "could", "should", "how", "what", "where"]
        if any(indicator in words for indicator in functional_indicators):
            patterns["has_functional_chunks"] = True
        
        # Determinar complexidade morfológica
        avg_word_length = sum(len(word) for word in words) / max(len(words), 1)
        if avg_word_length > 7:
            patterns["morphological_complexity"] = "high"
        elif avg_word_length > 5:
            patterns["morphological_complexity"] = "medium"
        
        return patterns
    
    async def _select_optimal_tips_strategy(self, enriched_context: Dict[str, Any]) -> str:
        """Seleção inteligente da estratégia TIPS baseada em RAG e análise do vocabulário."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        rag_analysis = enriched_context["rag_analysis"]
        
        cefr_level = unit_info["cefr_level"]
        vocabulary_patterns = content_analysis["vocabulary_patterns"]
        used_strategies = rag_analysis["used_strategies"]
        
        # Contador de estratégias já usadas
        strategy_counts = {}
        for strategy in used_strategies:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Sistema de pontuação para cada estratégia
        strategy_scores = {
            "afixacao": 0,
            "substantivos_compostos": 0,
            "colocacoes": 0,
            "expressoes_fixas": 0,
            "idiomas": 0,
            "chunks": 0
        }
        
        # PONTUAÇÃO BASEADA NO VOCABULÁRIO
        if vocabulary_patterns["has_affixes"]:
            strategy_scores["afixacao"] += 30
        
        if vocabulary_patterns["has_compounds"]:
            strategy_scores["substantivos_compostos"] += 35
        
        if vocabulary_patterns["has_collocations"]:
            strategy_scores["colocacoes"] += 25
        
        if vocabulary_patterns["has_fixed_expressions"]:
            strategy_scores["expressoes_fixas"] += 20
        
        if vocabulary_patterns["has_idiomatic_potential"]:
            strategy_scores["idiomas"] += 15
        
        if vocabulary_patterns["has_functional_chunks"]:
            strategy_scores["chunks"] += 25
        
        # PONTUAÇÃO BASEADA NO NÍVEL CEFR
        cefr_preferences = {
            "A1": {"chunks": 25, "substantivos_compostos": 20, "expressoes_fixas": 15, "afixacao": 10},
            "A2": {"substantivos_compostos": 25, "chunks": 20, "expressoes_fixas": 20, "afixacao": 15},
            "B1": {"afixacao": 25, "colocacoes": 20, "expressoes_fixas": 15, "chunks": 10},
            "B2": {"colocacoes": 30, "afixacao": 20, "expressoes_fixas": 15, "idiomas": 10},
            "C1": {"colocacoes": 25, "idiomas": 25, "afixacao": 15, "expressoes_fixas": 10},
            "C2": {"idiomas": 30, "colocacoes": 25, "afixacao": 15, "expressoes_fixas": 5}
        }
        
        level_preferences = cefr_preferences.get(cefr_level, cefr_preferences["A2"])
        for strategy, bonus in level_preferences.items():
            strategy_scores[strategy] += bonus
        
        # PENALIZAÇÃO POR OVERUSE (evitar mais de 2 usos da mesma estratégia)
        for strategy, count in strategy_counts.items():
            if count >= 2:
                strategy_scores[strategy] -= 40  # Penalização forte
            elif count >= 1:
                strategy_scores[strategy] -= 15  # Penalização moderada
        
        # BONIFICAÇÃO PARA VARIEDADE
        unused_strategies = [s for s in strategy_scores.keys() if strategy_counts.get(s, 0) == 0]
        for strategy in unused_strategies:
            strategy_scores[strategy] += 10
        
        # Selecionar estratégia com maior pontuação
        selected_strategy = max(strategy_scores, key=strategy_scores.get)
        max_score = strategy_scores[selected_strategy]
        
        logger.info(f"🎯 Estratégia selecionada: {selected_strategy} (score: {max_score})")
        logger.debug(f"Scores: {strategy_scores}")
        
        return selected_strategy
    
    async def _build_strategy_specific_prompt(
        self, 
        selected_strategy: str, 
        enriched_context: Dict[str, Any]
    ) -> List[Any]:
        """Construir prompt específico para a estratégia TIPS selecionada."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        hierarchy_info = enriched_context["hierarchy_info"]
        rag_analysis = enriched_context["rag_analysis"]
        
        # Obter informações específicas da estratégia
        strategy_info = self.tips_strategies_db[selected_strategy]
        
        system_prompt = f"""You are an expert English teacher implementing the TIPS methodology for lexical units.

SELECTED STRATEGY: {strategy_info['name']}
STRATEGY DESCRIPTION: {strategy_info['description']}

UNIT CONTEXT:
- Title: {unit_info['title']}
- Context: {unit_info['context']}
- Level: {unit_info['cefr_level']}
- Language Variant: {unit_info['language_variant']}
- Main Aim: {unit_info['main_aim']}

VOCABULARY TO INTEGRATE ({content_analysis['vocabulary_count']} words):
{', '.join(content_analysis['vocabulary_words'][:15])}

STRATEGY-SPECIFIC GUIDELINES:
{strategy_info['implementation_guide']}

CEFR {unit_info['cefr_level']} ADAPTATION:
{strategy_info['cefr_adaptations'].get(unit_info['cefr_level'], 'Standard implementation')}

RAG CONTEXT:
- Used strategies: {', '.join(rag_analysis['used_strategies'])}
- Progression level: {rag_analysis['progression_level']}
- Strategy density: {rag_analysis['strategy_density']:.2f}

PHONETIC INTEGRATION:
- Include pronunciation guidance specific to {selected_strategy}
- Focus on {unit_info['language_variant']} pronunciation patterns
- Address stress patterns and connected speech

GENERATION REQUIREMENTS:
1. Apply the {strategy_info['name']} strategy specifically
2. Create practical examples using unit vocabulary
3. Provide memory techniques aligned with the strategy
4. Include practice suggestions that reinforce the strategy
5. Add pronunciation tips specific to this strategy type
6. Ensure {unit_info['cefr_level']} level appropriateness

OUTPUT FORMAT: Return valid JSON with this exact structure:
{{
  "title": "TIP X: Strategy Name",
  "explanation": "Clear explanation of how this strategy works",
  "examples": [
    "Example 1 using unit vocabulary",
    "Example 2 showing the pattern",
    "Example 3 demonstrating application"
  ],
  "practice_suggestions": [
    "Practice activity 1",
    "Practice activity 2"
  ],
  "memory_techniques": [
    "Memory technique 1",
    "Memory technique 2"
  ],
  "vocabulary_coverage": ["word1", "word2", "word3"],
  "phonetic_focus": ["phonetic_aspect1", "phonetic_aspect2"],
  "pronunciation_tips": [
    "Pronunciation tip 1",
    "Pronunciation tip 2"
  ]
}}"""

        human_prompt = f"""Apply the {strategy_info['name']} strategy to the vocabulary: {', '.join(content_analysis['vocabulary_words'][:10])}

Context: {unit_info['context']}
Level: {unit_info['cefr_level']}

{strategy_info['specific_instructions']}

Focus on:
1. How this strategy helps with the specific vocabulary
2. Practical application in the unit context
3. Memory techniques that leverage this strategy
4. Pronunciation patterns relevant to this strategy type

Generate the JSON structure now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
    
    async def _generate_tips_llm(self, prompt_messages: List[Any]) -> Dict[str, Any]:
        """Gerar conteúdo TIPS usando LLM."""
        try:
            logger.info("🤖 Consultando LLM para geração de estratégia TIPS...")
            
            # Verificar cache
            cache_key = self._generate_cache_key(prompt_messages)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                logger.info("📦 Usando resultado do cache")
                return cached_result
            
            # Gerar usando LangChain
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
                
                # Salvar no cache
                self._save_to_cache(cache_key, tips_data)
                
                logger.info(f"✅ LLM retornou estratégia TIPS com {len(tips_data.get('examples', []))} exemplos")
                return tips_data
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao parsear JSON, tentando extração manual: {str(e)}")
                return self._extract_tips_from_text(content)
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            # Retornar TIPS de fallback
            return self._generate_fallback_tips()
    
    async def _process_and_structure_tips(
        self, 
        raw_tips: Dict[str, Any], 
        selected_strategy: str,
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processar e estruturar dados de TIPS."""
        
        # Extrair e validar campos obrigatórios
        title = raw_tips.get("title", f"TIP: {selected_strategy.title()}")
        explanation = raw_tips.get("explanation", "Estratégia de aprendizado de vocabulário.")
        examples = raw_tips.get("examples", [])
        practice_suggestions = raw_tips.get("practice_suggestions", [])
        memory_techniques = raw_tips.get("memory_techniques", [])
        
        # Processar campos opcionais
        vocabulary_coverage = raw_tips.get("vocabulary_coverage", [])
        phonetic_focus = raw_tips.get("phonetic_focus", [])
        pronunciation_tips = raw_tips.get("pronunciation_tips", [])
        
        # Validar e expandir campos se necessário
        if len(examples) < 3:
            # Adicionar exemplos básicos se necessário
            vocabulary_words = enriched_context["content_analysis"]["vocabulary_words"][:3]
            for i, word in enumerate(vocabulary_words):
                if i >= len(examples):
                    examples.append(f"Use '{word}' in context to demonstrate the strategy.")
        
        if len(practice_suggestions) < 2:
            practice_suggestions.extend([
                "Practice identifying patterns in new vocabulary.",
                "Create your own examples using this strategy."
            ])
        
        if len(memory_techniques) < 2:
            memory_techniques.extend([
                "Group words by their common patterns.",
                "Use visual associations to remember connections."
            ])
        
        # Gerar justificativa de seleção
        selection_rationale = self._generate_selection_rationale(
            selected_strategy, enriched_context
        )
        
        return {
            "title": title,
            "explanation": explanation,
            "examples": examples[:5],  # Máximo 5 exemplos
            "practice_suggestions": practice_suggestions[:3],  # Máximo 3 sugestões
            "memory_techniques": memory_techniques[:3],  # Máximo 3 técnicas
            "vocabulary_coverage": vocabulary_coverage,
            "phonetic_focus": phonetic_focus,
            "pronunciation_tips": pronunciation_tips,
            "selection_rationale": selection_rationale
        }
    
    async def _enrich_with_phonetic_components(
        self, 
        structured_tips: Dict[str, Any], 
        content_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enriquecer TIPS com componentes fonéticos específicos."""
        
        phonetic_focus = structured_tips.get("phonetic_focus", [])
        pronunciation_tips = structured_tips.get("pronunciation_tips", [])
        
        # Extrair informações fonéticas do vocabulário
        vocabulary_items = []
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"][:5]
        
        # Adicionar foco fonético se necessário
        if len(phonetic_focus) < 2:
            additional_focus = []
            
            # Analisar padrões de stress no vocabulário
            stress_patterns = []
            for item in vocabulary_items:
                phoneme = item.get("phoneme", "")
                if "ˈ" in phoneme:
                    stress_patterns.append("primary_stress")
                if "ˌ" in phoneme:
                    stress_patterns.append("secondary_stress")
            
            if stress_patterns:
                additional_focus.append("word_stress_patterns")
            
            # Analisar sons difíceis
            difficult_sounds = []
            for item in vocabulary_items:
                phoneme = item.get("phoneme", "")
                if any(sound in phoneme for sound in ["θ", "ð", "ʃ", "ʒ", "ŋ"]):
                    difficult_sounds.append("consonant_challenges")
                if any(sound in phoneme for sound in ["æ", "ʌ", "ɜː"]):
                    difficult_sounds.append("vowel_distinctions")
            
            additional_focus.extend(list(set(difficult_sounds)))
            phonetic_focus.extend(additional_focus[:2])
        
        # Adicionar dicas de pronúncia se necessário
        if len(pronunciation_tips) < 2:
            additional_tips = [
                "Pay attention to word stress when learning new vocabulary.",
                "Practice saying words clearly to improve memory retention."
            ]
            
            # Dicas específicas por estratégia
            strategy = structured_tips.get("title", "").lower()
            if "afixacao" in strategy or "affix" in strategy:
                additional_tips.append("Notice how prefixes and suffixes affect word stress.")
            elif "compound" in strategy or "compostos" in strategy:
                additional_tips.append("Primary stress usually falls on the first part of compounds.")
            elif "collocation" in strategy or "colocacoes" in strategy:
                additional_tips.append("Practice the rhythm of word combinations in natural speech.")
            
            pronunciation_tips.extend(additional_tips[:2])
        
        # Atualizar estrutura
        structured_tips["phonetic_focus"] = phonetic_focus[:3]
        structured_tips["pronunciation_tips"] = pronunciation_tips[:3]
        
        return structured_tips
    
    async def _add_complementary_strategies(
        self, 
        enriched_tips: Dict[str, Any], 
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adicionar estratégias complementares sugeridas."""
        
        current_strategy = None
        title = enriched_tips.get("title", "").lower()
        
        # Identificar estratégia atual
        for strategy_key in self.tips_strategies_db.keys():
            if strategy_key in title or self.tips_strategies_db[strategy_key]["name"].lower() in title:
                current_strategy = strategy_key
                break
        
        complementary_strategies = []
        used_strategies = rag_context.get("used_strategies", [])
        
        if current_strategy:
            # Obter estratégias complementares da base de dados
            strategy_info = self.tips_strategies_db[current_strategy]
            suggested_complementary = strategy_info.get("complementary_strategies", [])
            
            # Filtrar estratégias não usadas recentemente
            for comp_strategy in suggested_complementary:
                if used_strategies.count(comp_strategy) < 2:  # Não usar mais que 2 vezes
                    complementary_strategies.append(comp_strategy)
        
        # Se não há estratégias complementares suficientes, sugerir baseado no que foi menos usado
        if len(complementary_strategies) < 2:
            all_strategies = list(self.tips_strategies_db.keys())
            strategy_counts = {s: used_strategies.count(s) for s in all_strategies}
            least_used = sorted(strategy_counts.items(), key=lambda x: x[1])
            
            for strategy, count in least_used:
                if strategy != current_strategy and strategy not in complementary_strategies:
                    complementary_strategies.append(strategy)
                if len(complementary_strategies) >= 3:
                    break
        
        enriched_tips["complementary_strategies"] = complementary_strategies[:3]
        
        return enriched_tips
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _load_tips_strategies_database(self) -> Dict[str, Dict[str, Any]]:
        """Carregar base de conhecimento das 6 estratégias TIPS."""
        
        return {
            "afixacao": {
                "name": "TIP 1: Afixação",
                "description": "Ensino através de prefixos e sufixos para expansão sistemática",
                "implementation_guide": "Identify common prefixes and suffixes in the vocabulary. Group words by morphological patterns. Teach the meaning of affixes and how they change word meaning.",
                "specific_instructions": "Focus on prefix/suffix patterns. Show how adding affixes creates new words and changes meanings. Use word families.",
                "cefr_adaptations": {
                    "A1": "Simple prefixes like 'un-' and suffixes like '-er'",
                    "A2": "Common affixes including '-ing', '-ed', 're-', 'pre-'",
                    "B1": "Extended range including '-tion', '-ness', 'mis-', 'over-'",
                    "B2": "Complex affixes and multiple affixation patterns",
                    "C1": "Advanced morphological awareness and Latin/Greek roots",
                    "C2": "Sophisticated derivational patterns and etymology"
                },
                "complementary_strategies": ["substantivos_compostos", "colocacoes"],
                "phonetic_aspects": ["stress_shift", "pronunciation_changes"]
            },
            "substantivos_compostos": {
                "name": "TIP 2: Substantivos Compostos",
                "description": "Agrupamento temático de palavras compostas por campo semântico",
                "implementation_guide": "Group compound words by theme or semantic field. Show relationships between simple words and compounds. Focus on meaning construction.",
                "specific_instructions": "Identify compound words and word families. Group by themes like 'workplace', 'technology', 'home'. Show how meaning is built from parts.",
                "cefr_adaptations": {
                    "A1": "Simple, transparent compounds like 'classroom', 'homework'",
                    "A2": "Common compound patterns in daily life contexts",
                    "B1": "Extended compound families and less transparent meanings",
                    "B2": "Complex compounds and metaphorical uses",
                    "C1": "Sophisticated compound structures and technical terms",
                    "C2": "Advanced compound patterns and creative usage"
                },
                "complementary_strategies": ["chunks", "afixacao"],
                "phonetic_aspects": ["compound_stress", "linking_sounds"]
            },
            "colocacoes": {
                "name": "TIP 3: Colocações",
                "description": "Combinações naturais de palavras que soam nativas",
                "implementation_guide": "Teach words that naturally go together. Focus on verb+noun, adjective+noun combinations. Emphasize natural vs unnatural combinations.",
                "specific_instructions": "Identify natural word partnerships. Show strong vs weak collocations. Practice with substitution exercises.",
                "cefr_adaptations": {
                    "A1": "Basic verb+noun collocations like 'have breakfast'",
                    "A2": "Extended common collocations in daily contexts",
                    "B1": "Academic and workplace collocations",
                    "B2": "Sophisticated collocational awareness",
                    "C1": "Advanced collocational patterns and restrictions",
                    "C2": "Native-like collocational competence"
                },
                "complementary_strategies": ["chunks", "expressoes_fixas"],
                "phonetic_aspects": ["collocation_rhythm", "stress_patterns"]
            },
            "expressoes_fixas": {
                "name": "TIP 4: Expressões Fixas",
                "description": "Frases cristalizadas e fórmulas funcionais fixas",
                "implementation_guide": "Teach fixed phrases as complete units. Focus on communicative functions. Show situations where these expressions are used.",
                "specific_instructions": "Present expressions as whole units. Practice in communicative contexts. Focus on functional language.",
                "cefr_adaptations": {
                    "A1": "Basic greetings and polite formulas",
                    "A2": "Common situational expressions",
                    "B1": "Extended functional language for various contexts",
                    "B2": "Sophisticated fixed expressions and discourse markers",
                    "C1": "Advanced formulaic language and register awareness",
                    "C2": "Native-like command of fixed expressions"
                },
                "complementary_strategies": ["chunks", "colocacoes"],
                "phonetic_aspects": ["phrase_stress", "intonation_patterns"]
            },
            "idiomas": {
                "name": "TIP 5: Idiomas",
                "description": "Expressões com significado figurativo e cultural",
                "implementation_guide": "Teach idiomatic meaning alongside literal meaning. Provide cultural context. Use visual aids and stories to aid memory.",
                "specific_instructions": "Explain both literal and figurative meanings. Provide cultural background. Use memorable contexts and stories.",
                "cefr_adaptations": {
                    "A1": "Not typically appropriate for this level",
                    "A2": "Very basic, transparent idioms",
                    "B1": "Common idioms with clear imagery",
                    "B2": "Extended range of common idioms",
                    "C1": "Sophisticated idiomatic awareness",
                    "C2": "Native-like idiomatic competence and cultural awareness"
                },
                "complementary_strategies": ["expressoes_fixas", "colocacoes"],
                "phonetic_aspects": ["idiomatic_stress", "connected_speech"]
            },
            "chunks": {
                "name": "TIP 6: Chunks",
                "description": "Blocos funcionais para fluência automática",
                "implementation_guide": "Teach functional language blocks as complete units. Focus on communicative purposes. Practice for automatic retrieval.",
                "specific_instructions": "Present chunks as ready-made units. Practice until automatic. Focus on communicative functions like agreeing, disagreeing, asking for help.",
                "cefr_adaptations": {
                    "A1": "Basic functional chunks for survival communication",
                    "A2": "Extended chunks for daily communication needs",
                    "B1": "Chunks for more complex communicative functions",
                    "B2": "Sophisticated chunks for nuanced communication",
                    "C1": "Advanced chunks for academic and professional contexts",
                    "C2": "Native-like chunking and processing"
                },
                "complementary_strategies": ["expressoes_fixas", "substantivos_compostos"],
                "phonetic_aspects": ["chunk_rhythm", "fluency_patterns"]
            }
        }
    
    def _generate_selection_rationale(
        self, 
        selected_strategy: str, 
        enriched_context: Dict[str, Any]
    ) -> str:
        """Gerar justificativa para seleção da estratégia."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        rag_analysis = enriched_context["rag_analysis"]
        
        vocabulary_patterns = content_analysis["vocabulary_patterns"]
        used_strategies = rag_analysis["used_strategies"]
        cefr_level = unit_info["cefr_level"]
        
        rationale_parts = []
        
        # Justificativa baseada no vocabulário
        if selected_strategy == "afixacao" and vocabulary_patterns["has_affixes"]:
            rationale_parts.append("O vocabulário apresenta padrões morfológicos claros com prefixos e sufixos")
        elif selected_strategy == "substantivos_compostos" and vocabulary_patterns["has_compounds"]:
            rationale_parts.append("Presença de palavras compostas permite agrupamento temático eficiente")
        elif selected_strategy == "colocacoes" and vocabulary_patterns["has_collocations"]:
            rationale_parts.append("Vocabulário contém palavras que formam colocações naturais importantes")
        elif selected_strategy == "expressoes_fixas" and vocabulary_patterns["has_fixed_expressions"]:
            rationale_parts.append("Contexto favorece o ensino de expressões funcionais fixas")
        elif selected_strategy == "idiomas" and vocabulary_patterns["has_idiomatic_potential"]:
            rationale_parts.append("Vocabulário permite explorar significados idiomáticos relevantes")
        elif selected_strategy == "chunks" and vocabulary_patterns["has_functional_chunks"]:
            rationale_parts.append("Contexto comunicativo favorece o uso de blocos funcionais")
        
        # Justificativa baseada no nível CEFR
        strategy_info = self.tips_strategies_db[selected_strategy]
        cefr_adaptations = strategy_info["cefr_adaptations"]
        if cefr_level in cefr_adaptations and "not typically appropriate" not in cefr_adaptations[cefr_level].lower():
            rationale_parts.append(f"Estratégia apropriada para nível {cefr_level}")
        
        # Justificativa baseada no balanceamento RAG
        strategy_count = used_strategies.count(selected_strategy)
        if strategy_count == 0:
            rationale_parts.append("Estratégia não utilizada ainda no book, promovendo variedade pedagógica")
        elif strategy_count == 1:
            rationale_parts.append("Estratégia usada moderadamente, mantendo balanceamento adequado")
        
        # Justificativa baseada na progressão
        sequence_order = enriched_context["hierarchy_info"]["sequence_order"]
        if sequence_order <= 3 and selected_strategy in ["chunks", "substantivos_compostos"]:
            rationale_parts.append("Estratégia adequada para unidades iniciais do book")
        elif sequence_order > 5 and selected_strategy in ["colocacoes", "idiomas"]:
            rationale_parts.append("Estratégia adequada para unidades mais avançadas do book")
        
        return ". ".join(rationale_parts) if rationale_parts else f"Estratégia {selected_strategy} selecionada para diversificação metodológica"
    
    def _extract_tips_from_text(self, text: str) -> Dict[str, Any]:
        """Extrair TIPS de texto quando JSON parsing falha."""
        
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
            
            # Detectar seções
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
        
        # Preencher campos faltantes
        if not tips_data["title"]:
            tips_data["title"] = "TIP: Estratégia de Vocabulário"
        
        if not tips_data["explanation"]:
            tips_data["explanation"] = "Esta estratégia ajuda na memorização e uso eficaz do vocabulário."
        
        if not tips_data["examples"]:
            tips_data["examples"] = ["Exemplo prático da estratégia com vocabulário da unidade."]
        
        if not tips_data["practice_suggestions"]:
            tips_data["practice_suggestions"] = ["Pratique identificando padrões no vocabulário novo."]
        
        return tips_data
    
    def _generate_fallback_tips(self) -> Dict[str, Any]:
        """Gerar TIPS de fallback em caso de erro."""
        
        fallback_tips = {
            "title": "TIP: Estratégia de Vocabulário Contextual",
            "explanation": "Esta estratégia foca em aprender vocabulário através do contexto e uso prático em situações reais de comunicação.",
            "examples": [
                "Use as palavras novas em frases completas e contextualizadas.",
                "Conecte o vocabulário novo com palavras que você já conhece.",
                "Pratique usar as palavras em diferentes situações comunicativas."
            ],
            "practice_suggestions": [
                "Crie frases próprias usando cada palavra nova pelo menos 3 vezes.",
                "Pratique conversas usando o vocabulário em contextos reais.",
                "Faça associações visuais ou mentais com as palavras novas."
            ],
            "memory_techniques": [
                "Use associação de imagens para conectar palavras ao significado.",
                "Agrupe palavras por temas ou situações de uso.",
                "Repita as palavras em voz alta prestando atenção à pronúncia."
            ],
            "vocabulary_coverage": ["vocabulary", "context", "practice", "memory"],
            "phonetic_focus": ["word_stress", "clear_articulation"],
            "pronunciation_tips": [
                "Preste atenção aos padrões de stress das palavras novas.",
                "Pratique a pronúncia clara para melhorar a memória."
            ]
        }
        
        logger.warning("⚠️ Usando TIPS de fallback")
        return fallback_tips
    
    def _generate_cache_key(self, prompt_messages: List[Any]) -> str:
        """Gerar chave para cache baseada no prompt."""
        content = "".join([msg.content for msg in prompt_messages])
        return f"tips_{hash(content)}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Obter item do cache em memória."""
        current_time = time.time()
        
        # Verificar se existe e não expirou (2 horas = 7200s)
        if (key in self._memory_cache and 
            key in self._cache_expiry and 
            current_time - self._cache_expiry[key] < 7200):
            return self._memory_cache[key]
        
        # Remover se expirado
        if key in self._memory_cache:
            del self._memory_cache[key]
        if key in self._cache_expiry:
            del self._cache_expiry[key]
        
        return None
    
    def _save_to_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Salvar item no cache em memória."""
        # Limpar cache se muito grande
        if len(self._memory_cache) >= self._max_cache_size:
            # Remover item mais antigo
            oldest_key = min(self._cache_expiry.keys(), key=self._cache_expiry.get)
            del self._memory_cache[oldest_key]
            del self._cache_expiry[oldest_key]
        
        self._memory_cache[key] = value
        self._cache_expiry[key] = time.time()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_tips_strategy_selection(
    vocabulary_items: List[Dict[str, Any]], 
    cefr_level: str,
    used_strategies: List[str]
) -> str:
    """Validar e sugerir estratégia TIPS mais adequada."""
    
    # Analisar padrões no vocabulário
    has_affixes = any(
        word.get("word", "").startswith(("un", "re", "pre")) or 
        word.get("word", "").endswith(("er", "ly", "tion", "ing"))
        for word in vocabulary_items
    )
    
    has_compounds = any(
        "-" in word.get("word", "") or 
        any(comp in word.get("word", "") for comp in ["phone", "room", "book", "work"])
        for word in vocabulary_items
    )
    
    has_functional_words = any(
        word.get("word", "").lower() in ["would", "could", "should", "like", "want", "need"]
        for word in vocabulary_items
    )
    
    # Contar frequência de estratégias já usadas
    strategy_counts = {}
    for strategy in used_strategies:
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    # Lógica de seleção baseada no IVO V2 Guide
    if cefr_level in ["A1", "A2"]:
        if has_compounds and strategy_counts.get("substantivos_compostos", 0) < 2:
            return "substantivos_compostos"
        elif has_functional_words and strategy_counts.get("chunks", 0) < 2:
            return "chunks"
        elif strategy_counts.get("expressoes_fixas", 0) < 2:
            return "expressoes_fixas"
        else:
            return "chunks"
    
    elif cefr_level in ["B1", "B2"]:
        if has_affixes and strategy_counts.get("afixacao", 0) < 2:
            return "afixacao"
        elif strategy_counts.get("colocacoes", 0) < 2:
            return "colocacoes"
        elif strategy_counts.get("expressoes_fixas", 0) < 2:
            return "expressoes_fixas"
        else:
            return "afixacao"
    
    else:  # C1, C2
        if strategy_counts.get("idiomas", 0) < 2:
            return "idiomas"
        elif strategy_counts.get("colocacoes", 0) < 2:
            return "colocacoes"
        else:
            return "afixacao"


def analyze_tips_effectiveness(
    tips_content: TipsContent,
    vocabulary_items: List[Dict[str, Any]],
    cefr_level: str
) -> Dict[str, Any]:
    """Analisar eficácia da estratégia TIPS aplicada."""
    
    effectiveness_metrics = {
        "vocabulary_integration": 0.0,
        "cefr_appropriateness": 0.0,
        "strategy_coherence": 0.0,
        "phonetic_awareness": 0.0,
        "overall_score": 0.0
    }
    
    # Analisar integração com vocabulário
    vocabulary_words = {item.get("word", "").lower() for item in vocabulary_items}
    coverage_words = {word.lower() for word in tips_content.vocabulary_coverage}
    
    if vocabulary_words:
        integration_score = len(coverage_words & vocabulary_words) / len(vocabulary_words)
        effectiveness_metrics["vocabulary_integration"] = integration_score
    
    # Analisar adequação ao nível CEFR
    strategy_cefr_map = {
        "chunks": {"A1": 0.9, "A2": 0.8, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "substantivos_compostos": {"A1": 0.8, "A2": 0.9, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "afixacao": {"A1": 0.6, "A2": 0.7, "B1": 0.9, "B2": 0.8, "C1": 0.7, "C2": 0.6},
        "colocacoes": {"A1": 0.3, "A2": 0.5, "B1": 0.7, "B2": 0.9, "C1": 0.8, "C2": 0.7},
        "expressoes_fixas": {"A1": 0.7, "A2": 0.8, "B1": 0.7, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "idiomas": {"A1": 0.2, "A2": 0.3, "B1": 0.5, "B2": 0.7, "C1": 0.9, "C2": 0.9}
    }
    
    strategy_name = tips_content.strategy.value
    if strategy_name in strategy_cefr_map:
        cefr_score = strategy_cefr_map[strategy_name].get(cefr_level, 0.7)
        effectiveness_metrics["cefr_appropriateness"] = cefr_score
    
    # Analisar coerência da estratégia
    has_explanation = len(tips_content.explanation) > 50
    has_examples = len(tips_content.examples) >= 3
    has_practice = len(tips_content.practice_suggestions) >= 2
    has_memory = len(tips_content.memory_techniques) >= 2
    
    coherence_score = sum([has_explanation, has_examples, has_practice, has_memory]) / 4
    effectiveness_metrics["strategy_coherence"] = coherence_score
    
    # Analisar consciência fonética
    phonetic_score = 0.0
    if tips_content.phonetic_focus:
        phonetic_score += 0.5
    if tips_content.pronunciation_tips:
        phonetic_score += 0.5
    
    effectiveness_metrics["phonetic_awareness"] = phonetic_score
    
    # Calcular score geral
    overall_score = sum(effectiveness_metrics.values()) / len(effectiveness_metrics)
    effectiveness_metrics["overall_score"] = overall_score
    
    return effectiveness_metrics


def generate_strategy_recommendations(
    vocabulary_patterns: Dict[str, Any],
    cefr_level: str,
    used_strategies: List[str]
) -> List[str]:
    """Gerar recomendações de estratégias baseadas no contexto."""
    
    recommendations = []
    
    # Recomendações baseadas em padrões de vocabulário
    if vocabulary_patterns.get("has_affixes") and "afixacao" not in used_strategies:
        recommendations.append("Considere usar TIP 1: Afixação devido aos padrões morfológicos no vocabulário")
    
    if vocabulary_patterns.get("has_compounds") and "substantivos_compostos" not in used_strategies:
        recommendations.append("TIP 2: Substantivos Compostos seria eficaz para este vocabulário")
    
    if vocabulary_patterns.get("has_collocations") and "colocacoes" not in used_strategies:
        recommendations.append("TIP 3: Colocações pode melhorar a naturalidade do uso")
    
    # Recomendações baseadas no nível CEFR
    if cefr_level in ["A1", "A2"] and "chunks" not in used_strategies:
        recommendations.append("TIP 6: Chunks é altamente recomendado para níveis básicos")
    
    if cefr_level in ["B2", "C1", "C2"] and "idiomas" not in used_strategies:
        recommendations.append("TIP 5: Idiomas ajudaria a desenvolver fluência avançada")
    
    # Recomendações baseadas no balanceamento
    strategy_counts = {}
    for strategy in used_strategies:
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    overused_strategies = [s for s, count in strategy_counts.items() if count > 2]
    if overused_strategies:
        recommendations.append(f"Diversificar estratégias - {', '.join(overused_strategies)} sendo usadas em excesso")
    
    return recommendations[:3]  # Máximo 3 recomendações