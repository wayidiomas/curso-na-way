# src/services/sentences_generator.py
"""
Serviço de geração de sentences conectadas ao vocabulário.
Implementação completa com foco em progressão pedagógica e contexto RAG.
Atualizado para LangChain 0.3 e Pydantic 2 com sistema hierárquico Course → Book → Unit.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import hashlib

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError, Field, ConfigDict

from src.core.unit_models import SentencesSection, Sentence
from src.core.enums import CEFRLevel, LanguageVariant, UnitType
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


class SentencesGenerationRequest(BaseModel):
    """Modelo de requisição para geração de sentences - Pydantic 2."""
    unit_data: Dict[str, Any] = Field(..., description="Dados da unidade")
    vocabulary_data: Dict[str, Any] = Field(..., description="Dados do vocabulário")
    hierarchy_context: Dict[str, Any] = Field(default={}, description="Contexto hierárquico")
    rag_context: Dict[str, Any] = Field(default={}, description="Contexto RAG")
    images_context: List[Dict[str, Any]] = Field(default=[], description="Contexto das imagens")
    target_sentences: int = Field(default=12, ge=8, le=20, description="Número alvo de sentences")
    
    # Pydantic 2 - Nova sintaxe de configuração
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        extra='allow'
    )


class SentencesGeneratorService:
    """Serviço principal para geração de sentences contextuais com RAG hierárquico."""
    
    def __init__(self):
        """Inicializar serviço com configurações LangChain 0.3."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM para v0.3
        sentences_config = self.model_configs.get("content_configs", {}).get("ivo_sentences_generation", {})
        
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=sentences_config.get("temperature", 0.6),  # Criatividade moderada
            max_tokens=sentences_config.get("max_tokens", 2048),   # Suficiente para múltiplas sentences
            timeout=60,
            max_retries=3,
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache inteligente em memória
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 50
        self._cache_ttl = 3600  # 1 hora
        
        logger.info("✅ SentencesGeneratorService inicializado com LangChain 0.3")
    
    async def generate_sentences_for_unit(self, generation_params: Dict[str, Any]) -> SentencesSection:
        """
        Gerar sentences conectadas ao vocabulário da unidade com progressão pedagógica.
        
        Args:
            generation_params: Parâmetros com contexto da unidade e RAG
            
        Returns:
            SentencesSection completa com sentences estruturadas
        """
        try:
            start_time = time.time()
            
            # Validar entrada com Pydantic 2
            request = SentencesGenerationRequest(**generation_params)
            
            logger.info(f"📝 Gerando sentences para unidade {request.unit_data.get('title', 'Unknown')}")
            
            # 1. Analisar vocabulário disponível
            vocabulary_analysis = await self._analyze_vocabulary_for_sentences(request)
            
            # 2. Construir contexto de progressão hierárquica
            progression_context = await self._build_hierarchical_progression_context(request, vocabulary_analysis)
            
            # 3. Gerar prompt contextual com RAG
            sentences_prompt = await self._build_rag_contextual_sentences_prompt(
                request, vocabulary_analysis, progression_context
            )
            
            # 4. Gerar sentences via LLM com cache inteligente
            raw_sentences = await self._generate_sentences_llm_cached(sentences_prompt, request)
            
            # 5. Processar e estruturar sentences
            structured_sentences = await self._process_and_structure_sentences(
                raw_sentences, request, vocabulary_analysis
            )
            
            # 6. Enriquecer com elementos fonéticos e conectividade
            enriched_sentences = await self._enrich_with_phonetic_and_connectivity(
                structured_sentences, request.vocabulary_data, progression_context
            )
            
            # 7. Validar progressão pedagógica
            validated_sentences = await self._validate_pedagogical_progression(
                enriched_sentences, request
            )
            
            # 8. Construir SentencesSection final
            sentences_section = SentencesSection(
                sentences=validated_sentences["sentences"],
                vocabulary_coverage=validated_sentences["vocabulary_coverage"],
                contextual_coherence=validated_sentences["contextual_coherence"],
                progression_appropriateness=validated_sentences["progression_appropriateness"],
                phonetic_progression=validated_sentences.get("phonetic_progression", []),
                pronunciation_patterns=validated_sentences.get("pronunciation_patterns", []),
                generated_at=datetime.now()
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Sentences geradas: {len(sentences_section.sentences)} em {generation_time:.2f}s"
            )
            
            return sentences_section
            
        except ValidationError as e:
            logger.error(f"❌ Erro de validação Pydantic 2: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro na geração de sentences: {str(e)}")
            raise
    
    async def _analyze_vocabulary_for_sentences(self, request: SentencesGenerationRequest) -> Dict[str, Any]:
        """Analisar vocabulário para geração de sentences otimizada."""
        
        vocabulary_items = request.vocabulary_data.get("items", [])
        
        if not vocabulary_items:
            raise ValueError("Vocabulário vazio - não é possível gerar sentences")
        
        # Análise detalhada do vocabulário
        word_classes = {}
        frequency_levels = {}
        syllable_counts = []
        vocabulary_words = []
        phonetic_complexity = {}
        collocations_potential = []
        
        for item in vocabulary_items:
            word = item.get("word", "")
            word_class = item.get("word_class", "unknown")
            frequency = item.get("frequency_level", "medium")
            syllables = item.get("syllable_count", 1)
            phoneme = item.get("phoneme", "")
            context_relevance = item.get("context_relevance", 0.5)
            
            vocabulary_words.append(word)
            word_classes[word_class] = word_classes.get(word_class, 0) + 1
            frequency_levels[frequency] = frequency_levels.get(frequency, 0) + 1
            syllable_counts.append(syllables)
            
            # Análise fonética
            if phoneme:
                complexity = self._calculate_phonetic_complexity(phoneme)
                phonetic_complexity[word] = complexity
            
            # Identificar potencial de colocações
            if word_class in ["verb", "noun", "adjective"] and context_relevance > 0.7:
                collocations_potential.append(word)
        
        # Determinar complexidade média e padrões
        avg_syllables = sum(syllable_counts) / len(syllable_counts) if syllable_counts else 1
        complexity_level = self._determine_sentences_complexity_level(avg_syllables, word_classes, phonetic_complexity)
        
        # Identificar palavras-chave para conectividade
        key_words = self._identify_sentence_connective_words(vocabulary_words, word_classes)
        
        # Analisar potencial temático
        thematic_clusters = self._identify_thematic_clusters(vocabulary_items)
        
        return {
            "vocabulary_words": vocabulary_words,
            "total_words": len(vocabulary_words),
            "word_classes": word_classes,
            "frequency_levels": frequency_levels,
            "complexity_level": complexity_level,
            "avg_syllables": avg_syllables,
            "key_connective_words": key_words,
            "phonetic_items": [item for item in vocabulary_items if item.get("phoneme")],
            "phonetic_complexity": phonetic_complexity,
            "collocations_potential": collocations_potential,
            "thematic_clusters": thematic_clusters,
            "high_relevance_words": [item.get("word") for item in vocabulary_items if item.get("context_relevance", 0) > 0.8]
        }
    
    async def _build_hierarchical_progression_context(
        self, 
        request: SentencesGenerationRequest, 
        vocabulary_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto de progressão pedagógica hierárquica."""
        
        # Contexto RAG hierárquico
        rag_context = request.rag_context
        hierarchy_context = request.hierarchy_context
        
        taught_vocabulary = rag_context.get("taught_vocabulary", [])
        progression_level = rag_context.get("progression_level", "intermediate")
        reinforcement_words = rag_context.get("vocabulary_for_reinforcement", [])
        
        # Contexto hierárquico Course → Book → Unit
        course_name = hierarchy_context.get("course_name", "")
        book_name = hierarchy_context.get("book_name", "")
        sequence_order = hierarchy_context.get("sequence_order", 1)
        target_level = hierarchy_context.get("target_level", "A2")
        
        # Análise de conectividade hierárquica
        connectivity_analysis = await self._analyze_hierarchical_vocabulary_connectivity(
            vocabulary_analysis["vocabulary_words"], 
            taught_vocabulary,
            reinforcement_words,
            sequence_order
        )
        
        # Determinar estratégia de progressão baseada na hierarquia
        progression_strategy = self._determine_hierarchical_progression_strategy(
            request.unit_data.get("cefr_level", "A2"),
            sequence_order,
            progression_level,
            book_name
        )
        
        # Análise de complexidade de sentences
        sentence_complexity_guidance = self._get_sentence_complexity_guidance(
            request.unit_data.get("cefr_level", "A2"),
            sequence_order,
            vocabulary_analysis["complexity_level"]
        )
        
        return {
            "taught_vocabulary": taught_vocabulary[:20],  # Expandido para contexto
            "reinforcement_words": reinforcement_words[:8],
            "progression_level": progression_level,
            "connectivity_analysis": connectivity_analysis,
            "progression_strategy": progression_strategy,
            "hierarchy": {
                "course_name": course_name,
                "book_name": book_name,
                "sequence_order": sequence_order,
                "target_level": target_level
            },
            "sentence_complexity_guidance": sentence_complexity_guidance,
            "target_sentences": request.target_sentences,
            "thematic_coherence": vocabulary_analysis["thematic_clusters"]
        }
    
    async def _build_rag_contextual_sentences_prompt(
        self,
        request: SentencesGenerationRequest,
        vocabulary_analysis: Dict[str, Any],
        progression_context: Dict[str, Any]
    ) -> List[Any]:
        """Construir prompt contextual para geração de sentences com RAG hierárquico."""
        
        unit_data = request.unit_data
        vocabulary_words = vocabulary_analysis["vocabulary_words"]
        complexity_level = vocabulary_analysis["complexity_level"]
        hierarchy = progression_context["hierarchy"]
        
        # Guidelines específicos por nível CEFR (expandidos)
        cefr_guidelines = {
            "A1": {
                "structure": "Very simple sentences with basic present tense. Use high-frequency vocabulary and short structures (4-8 words).",
                "connectors": "Use basic connectors: and, but, or",
                "vocabulary": "Focus on concrete, everyday vocabulary",
                "complexity": "One idea per sentence, simple SVO structure"
            },
            "A2": {
                "structure": "Simple sentences with past and future tenses. Include basic connectors like 'and', 'but', 'because'.",
                "connectors": "Add: because, when, after, before",
                "vocabulary": "Include some abstract concepts, basic adjectives",
                "complexity": "Two clauses maximum, introduce compound sentences"
            },
            "B1": {
                "structure": "More complex sentences with conditional and modal verbs. Use varied sentence structures.",
                "connectors": "Include: however, although, despite, in order to",
                "vocabulary": "Professional and academic vocabulary, precise adjectives",
                "complexity": "Complex sentences with dependent clauses"
            },
            "B2": {
                "structure": "Complex and compound sentences with relative clauses. Include sophisticated connectors.",
                "connectors": "Advanced: nevertheless, furthermore, consequently, whereas",
                "vocabulary": "Nuanced vocabulary, idiomatic expressions",
                "complexity": "Multiple clauses, embedded structures"
            },
            "C1": {
                "structure": "Advanced sentence structures with nuanced meanings. Use sophisticated vocabulary and expressions.",
                "connectors": "Sophisticated: notwithstanding, albeit, inasmuch as",
                "vocabulary": "Precise, sophisticated, academic/professional register",
                "complexity": "Complex syntax, subtle relationships between ideas"
            },
            "C2": {
                "structure": "Native-level complexity with idiomatic expressions and advanced grammatical structures.",
                "connectors": "Native-level discourse markers and transitions",
                "vocabulary": "Near-native lexical sophistication",
                "complexity": "Natural complexity matching native speakers"
            }
        }
        
        cefr_level = unit_data.get("cefr_level", "A2")
        cefr_guidance = cefr_guidelines.get(cefr_level, cefr_guidelines["A2"])
        
        # Contextualização temática
        thematic_context = ""
        if vocabulary_analysis["thematic_clusters"]:
            clusters = list(vocabulary_analysis["thematic_clusters"].keys())[:3]
            thematic_context = f"Main themes to connect: {', '.join(clusters)}"
        
        system_prompt = f"""You are an expert English teacher creating contextual sentences for {cefr_level} level students using the IVO V2 pedagogical method.

HIERARCHICAL CONTEXT:
- Course: {hierarchy['course_name']}
- Book: {hierarchy['book_name']} (Level: {hierarchy['target_level']})
- Unit: {unit_data.get('title', '')} (Sequence: {hierarchy['sequence_order']})
- Context: {unit_data.get('context', '')}
- Language Variant: {unit_data.get('language_variant', 'american_english')}
- Unit Type: {unit_data.get('unit_type', 'lexical_unit')}

VOCABULARY TO CONNECT ({vocabulary_analysis['total_words']} words):
- Target Words: {', '.join(vocabulary_words[:20])}
- Word Classes: {dict(list(vocabulary_analysis['word_classes'].items())[:6])}
- High-Priority Words: {', '.join(vocabulary_analysis['high_relevance_words'][:10])}
- Complexity Level: {complexity_level}
- Key Connectors: {', '.join(vocabulary_analysis['key_connective_words'])}
- {thematic_context}

RAG PROGRESSION CONTEXT:
- Previously Taught ({len(progression_context['taught_vocabulary'])}): {', '.join(progression_context['taught_vocabulary'])}
- For Reinforcement: {', '.join(progression_context['reinforcement_words'])}
- Progression Strategy: {progression_context['progression_strategy']}
- Unit Position: #{hierarchy['sequence_order']} in {hierarchy['book_name']}

CEFR {cefr_level} REQUIREMENTS:
- Structure: {cefr_guidance['structure']}
- Connectors: {cefr_guidance['connectors']}
- Vocabulary Level: {cefr_guidance['vocabulary']}
- Complexity: {cefr_guidance['complexity']}

SENTENCE GENERATION STRATEGY:
{progression_context['sentence_complexity_guidance']}

IVO V2 PEDAGOGICAL PRINCIPLES:
1. VOCABULARY INTEGRATION: Use each target word at least once, some words multiple times
2. PROGRESSIVE COMPLEXITY: Start simple, gradually increase structural complexity
3. CONTEXTUAL COHERENCE: All sentences should relate to "{unit_data.get('context', '')}"
4. CONNECTIVITY: Connect new vocabulary with previously taught words naturally
5. COMMUNICATIVE PURPOSE: Sentences should demonstrate real, meaningful usage
6. HIERARCHICAL REINFORCEMENT: Build on vocabulary from previous units
7. PHONETIC AWARENESS: Consider pronunciation patterns in sentence flow

NATURAL LANGUAGE PRINCIPLES:
- Use authentic collocations and word combinations
- Ensure sentences sound natural to native speakers
- Vary sentence length appropriately for {cefr_level} level
- Create meaningful, contextually relevant examples
- Show how words work together in real communication

OUTPUT FORMAT - Return exactly this JSON structure:
{{
  "sentences": [
    {{
      "text": "Natural sentence using vocabulary contextually and meaningfully.",
      "vocabulary_used": ["word1", "word2"],
      "context_situation": "specific_context_description",
      "complexity_level": "simple|intermediate|complex",
      "reinforces_previous": ["known_word1"],
      "introduces_new": ["new_word1"],
      "phonetic_features": ["stress_pattern", "linking_sounds"],
      "pronunciation_notes": "Optional pronunciation guidance for this sentence",
      "communicative_function": "greeting|information|request|description",
      "sentence_length": 8,
      "grammatical_focus": ["present_simple", "article_usage"]
    }}
  ],
  "vocabulary_coverage": 0.95,
  "contextual_coherence": 0.90,
  "progression_appropriateness": 0.88,
  "thematic_consistency": 0.92
}}

CRITICAL: Every sentence must sound natural and be contextually meaningful within "{unit_data.get('context', '')}"."""

        human_prompt = f"""Create exactly {request.target_sentences} contextual sentences for the unit "{unit_data.get('title', '')}" following IVO V2 methodology.

SPECIFIC REQUIREMENTS:
- Context Theme: {unit_data.get('context', '')}
- CEFR Level: {cefr_level}
- Target Vocabulary: {', '.join(vocabulary_words[:15])}
- Unit Position: #{hierarchy['sequence_order']} in {hierarchy['book_name']}

PROGRESSION REQUIREMENTS:
- Previously Taught Words to Connect: {', '.join(progression_context['taught_vocabulary'][:10])}
- Words for Reinforcement: {', '.join(progression_context['reinforcement_words'])}
- Complexity Progression: {progression_context['sentence_complexity_guidance']['progression_pattern']}

QUALITY STANDARDS:
- Each sentence uses 1-3 target vocabulary words
- Connect new words with previously learned vocabulary naturally
- Progress from {progression_context['sentence_complexity_guidance']['start_complexity']} to {progression_context['sentence_complexity_guidance']['end_complexity']}
- All sentences relate to the theme: "{unit_data.get('context', '')}"
- Sound natural and communicatively meaningful
- Demonstrate authentic usage patterns

Generate the complete JSON structure with all {request.target_sentences} sentences now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
    
    async def _generate_sentences_llm_cached(self, prompt_messages: List[Any], request: SentencesGenerationRequest) -> Dict[str, Any]:
        """Gerar sentences usando LLM com cache inteligente."""
        try:
            logger.info("🤖 Consultando LLM para geração de sentences...")
            
            # Verificar cache inteligente
            cache_key = self._generate_intelligent_cache_key(prompt_messages, request)
            cached_result = self._get_from_cache_with_ttl(cache_key)
            if cached_result:
                logger.info("📦 Usando resultado do cache inteligente")
                return cached_result
            
            # Gerar usando LangChain 0.3 - método ainvoke
            response = await self.llm.ainvoke(prompt_messages)
            content = response.content
            
            # Processar resposta com múltiplas estratégias de parsing
            sentences_data = await self._parse_llm_response_robust(content)
            
            # Salvar no cache com TTL
            self._save_to_cache_with_ttl(cache_key, sentences_data)
            
            logger.info(f"✅ LLM retornou {len(sentences_data.get('sentences', []))} sentences")
            return sentences_data
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            # Retornar sentences de fallback baseadas no vocabulário
            return await self._generate_intelligent_fallback_sentences(request)
    
    async def _parse_llm_response_robust(self, content: str) -> Dict[str, Any]:
        """Parser robusto para resposta do LLM com múltiplas estratégias."""
        
        # Estratégia 1: JSON direto
        try:
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_content = content.split("```")[1].strip()
            else:
                json_content = content.strip()
            
            sentences_data = json.loads(json_content)
            
            if self._validate_sentences_structure(sentences_data):
                return sentences_data
                
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("⚠️ JSON parsing failed, trying structured extraction...")
        
        # Estratégia 2: Extração estruturada
        try:
            extracted_data = await self._extract_sentences_structured(content)
            if self._validate_sentences_structure(extracted_data):
                return extracted_data
        except Exception:
            logger.warning("⚠️ Structured extraction failed, using text parsing...")
        
        # Estratégia 3: Parsing de texto
        return self._extract_sentences_from_text_advanced(content)
    
    async def _process_and_structure_sentences(
        self,
        raw_sentences: Dict[str, Any],
        request: SentencesGenerationRequest,
        vocabulary_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processar e estruturar dados de sentences com validação avançada."""
        
        # Extrair sentences
        sentences_list = raw_sentences.get("sentences", [])
        
        if not sentences_list:
            sentences_list = await self._generate_intelligent_fallback_sentences(request)
            sentences_list = sentences_list["sentences"]
        
        # Processar cada sentence com validação
        processed_sentences = []
        vocabulary_used = set()
        complexity_progression = []
        
        for i, sentence_data in enumerate(sentences_list):
            if isinstance(sentence_data, str):
                # Converter string simples para estrutura completa
                sentence_obj = await self._convert_string_to_structured_sentence(
                    sentence_data, vocabulary_analysis["vocabulary_words"], i, request
                )
            else:
                sentence_obj = sentence_data
            
            # Validar e enriquecer sentence
            enriched_sentence = await self._validate_and_enrich_sentence_advanced(
                sentence_obj, vocabulary_analysis, request
            )
            
            processed_sentences.append(enriched_sentence)
            vocabulary_used.update(enriched_sentence.get("vocabulary_used", []))
            complexity_progression.append(enriched_sentence.get("complexity_level", "intermediate"))
        
        # Calcular métricas avançadas
        vocabulary_coverage = len(vocabulary_used) / max(len(vocabulary_analysis["vocabulary_words"]), 1)
        contextual_coherence = raw_sentences.get("contextual_coherence", self._calculate_contextual_coherence(processed_sentences, request))
        progression_appropriateness = self._calculate_progression_appropriateness(complexity_progression, request)
        thematic_consistency = raw_sentences.get("thematic_consistency", self._calculate_thematic_consistency(processed_sentences, vocabulary_analysis))
        
        return {
            "sentences": processed_sentences,
            "vocabulary_coverage": vocabulary_coverage,
            "contextual_coherence": contextual_coherence,
            "progression_appropriateness": progression_appropriateness,
            "thematic_consistency": thematic_consistency,
            "vocabulary_used": list(vocabulary_used),
            "total_sentences": len(processed_sentences),
            "complexity_progression": complexity_progression
        }
    
    async def _enrich_with_phonetic_and_connectivity(
        self,
        structured_sentences: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        progression_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enriquecer sentences com elementos fonéticos e análise de conectividade."""
        
        sentences = structured_sentences["sentences"]
        vocabulary_items = vocabulary_data.get("items", [])
        
        # Criar mapa palavra → dados fonéticos
        phonetic_map = {}
        for item in vocabulary_items:
            word = item.get("word", "")
            phoneme = item.get("phoneme", "")
            if word and phoneme:
                phonetic_map[word.lower()] = {
                    "phoneme": phoneme,
                    "syllables": item.get("syllable_count", 1),
                    "stress_pattern": item.get("stress_pattern", ""),
                    "ipa_variant": item.get("ipa_variant", "general_american"),
                    "complexity": self._calculate_phonetic_complexity(phoneme)
                }
        
        # Analisar padrões fonéticos e conectividade
        phonetic_progression = []
        pronunciation_patterns = []
        connectivity_analysis = []
        
        for i, sentence in enumerate(sentences):
            vocabulary_used = sentence.get("vocabulary_used", [])
            sentence_phonetics = []
            connectivity_score = 0
            
            # Análise fonética
            for word in vocabulary_used:
                if word.lower() in phonetic_map:
                    phonetic_data = phonetic_map[word.lower()]
                    sentence_phonetics.append({
                        "word": word,
                        "phoneme": phonetic_data["phoneme"],
                        "syllables": phonetic_data["syllables"],
                        "complexity": phonetic_data["complexity"]
                    })
            
            # Enriquecer sentence com dados fonéticos
            if sentence_phonetics:
                sentence = await self._enrich_sentence_with_phonetics(sentence, sentence_phonetics)
                
                avg_syllables = sum(p["syllables"] for p in sentence_phonetics) / len(sentence_phonetics)
                phonetic_progression.append(f"Sentence {i+1}: {len(sentence_phonetics)} phonetic elements, avg {avg_syllables:.1f} syllables")
            
            # Análise de conectividade
            reinforced_words = sentence.get("reinforces_previous", [])
            if reinforced_words:
                connectivity_score = len(reinforced_words) / max(len(vocabulary_used), 1)
                connectivity_analysis.append(f"Sentence {i+1}: {connectivity_score:.1f} connectivity score")
        
        # Identificar padrões de pronúncia globais
        global_patterns = self._identify_global_pronunciation_patterns(phonetic_map, sentences)
        pronunciation_patterns.extend(global_patterns)
        
        # Analisar conectividade hierárquica
        hierarchical_connectivity = self._analyze_hierarchical_connectivity(sentences, progression_context)
        
        # Enriquecer estrutura com análises
        structured_sentences["phonetic_progression"] = phonetic_progression
        structured_sentences["pronunciation_patterns"] = pronunciation_patterns
        structured_sentences["connectivity_analysis"] = connectivity_analysis
        structured_sentences["hierarchical_connectivity"] = hierarchical_connectivity
        
        return structured_sentences
    
    async def _validate_pedagogical_progression(
        self,
        enriched_sentences: Dict[str, Any],
        request: SentencesGenerationRequest
    ) -> Dict[str, Any]:
        """Validar e ajustar progressão pedagógica das sentences."""
        
        sentences = enriched_sentences["sentences"]
        cefr_level = request.unit_data.get("cefr_level", "A2")
        unit_type = request.unit_data.get("unit_type", "lexical_unit")
        
        # Validar progressão de complexidade
        complexity_validation = self._validate_complexity_progression(sentences, cefr_level)
        
        # Validar cobertura de vocabulário
        vocabulary_validation = self._validate_vocabulary_coverage(sentences, request.vocabulary_data)
        
        # Validar coerência contextual
        context_validation = self._validate_contextual_coherence(sentences, request.unit_data.get("context", ""))
        
        # Aplicar correções se necessário
        if not complexity_validation["is_valid"]:
            sentences = await self._adjust_complexity_progression(sentences, complexity_validation["issues"])
        
        if not vocabulary_validation["is_adequate"]:
            sentences = await self._improve_vocabulary_coverage(sentences, vocabulary_validation["missing_words"], request)
        
        # Recalcular métricas após validação
        final_vocabulary_coverage = vocabulary_validation["coverage"] if vocabulary_validation["is_adequate"] else self._recalculate_vocabulary_coverage(sentences, request.vocabulary_data)
        final_contextual_coherence = context_validation["coherence_score"] if context_validation["is_coherent"] else self._recalculate_contextual_coherence(sentences, request)
        final_progression_appropriateness = complexity_validation["appropriateness_score"] if complexity_validation["is_valid"] else self._recalculate_progression_appropriateness(sentences, cefr_level)
        
        # Estrutura final validada
        enriched_sentences.update({
            "sentences": sentences,
            "vocabulary_coverage": final_vocabulary_coverage,
            "contextual_coherence": final_contextual_coherence,
            "progression_appropriateness": final_progression_appropriateness,
            "validation_applied": True,
            "validation_results": {
                "complexity": complexity_validation,
                "vocabulary": vocabulary_validation,
                "context": context_validation
            }
        })
        
        return enriched_sentences
    
    # =============================================================================
    # HELPER METHODS - ANÁLISE DE VOCABULÁRIO
    # =============================================================================
    
    def _calculate_phonetic_complexity(self, phoneme: str) -> str:
        """Calcular complexidade fonética de um fonema."""
        if not phoneme:
            return "simple"
        
        # Remover delimitadores
        clean_phoneme = phoneme.strip('/[]')
        
        # Fatores de complexidade
        complex_sounds = ["θ", "ð", "ʃ", "ʒ", "ŋ", "ɹ", "æ", "ʌ", "ɜː", "ɪə", "eə"]
        stress_markers = clean_phoneme.count("ˈ") + clean_phoneme.count("ˌ")
        sound_count = len([s for s in complex_sounds if s in clean_phoneme])
        
        if sound_count >= 3 or stress_markers >= 2:
            return "complex"
        elif sound_count >= 1 or stress_markers >= 1:
            return "intermediate"
        else:
            return "simple"
    
    def _determine_sentences_complexity_level(self, avg_syllables: float, word_classes: Dict[str, int], phonetic_complexity: Dict[str, str]) -> str:
        """Determinar nível de complexidade para geração de sentences."""
        
        # Análise de distribuição de classes
        total_words = sum(word_classes.values())
        noun_ratio = word_classes.get("noun", 0) / max(total_words, 1)
        verb_ratio = word_classes.get("verb", 0) / max(total_words, 1)
        adjective_ratio = word_classes.get("adjective", 0) / max(total_words, 1)
        
        # Análise fonética
        complex_phonetics = len([word for word, complexity in phonetic_complexity.items() if complexity == "complex"])
        phonetic_ratio = complex_phonetics / max(len(phonetic_complexity), 1)
        
        # Determinar complexidade
        if avg_syllables <= 1.5 and noun_ratio > 0.6 and phonetic_ratio < 0.3:
            return "simple"
        elif avg_syllables <= 2.5 and verb_ratio > 0.2 and phonetic_ratio < 0.6:
            return "intermediate"
        else:
            return "complex"
    
    def _identify_sentence_connective_words(self, vocabulary_words: List[str], word_classes: Dict[str, int]) -> List[str]:
        """Identificar palavras-chave que facilitam conectividade em sentences."""
        
        # Palavras que facilitam conexões naturais em sentences
        connective_patterns = {
            "high_frequency_verbs": ["be", "have", "do", "make", "take", "get", "go", "come", "see", "know"],
            "common_prepositions": ["in", "on", "at", "with", "for", "to", "from", "by", "about"],
            "versatile_adjectives": ["good", "bad", "big", "small", "new", "old", "important", "interesting"],
            "temporal_adverbs": ["now", "today", "yesterday", "tomorrow", "always", "never", "usually"],
            "modal_auxiliaries": ["can", "could", "will", "would", "should", "must", "may", "might"]
        }
        
        key_words = []
        for word in vocabulary_words:
            word_lower = word.lower()
            for category, patterns in connective_patterns.items():
                if any(pattern in word_lower or word_lower == pattern for pattern in patterns):
                    key_words.append(word)
                    break
        
        return key_words[:8]  # Top 8 palavras conectivas
    
    def _identify_thematic_clusters(self, vocabulary_items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Identificar clusters temáticos no vocabulário."""
        
        # Definir campos semânticos comuns
        semantic_fields = {
            "hospitality": ["hotel", "reservation", "room", "service", "guest", "reception", "check-in", "booking"],
            "business": ["meeting", "presentation", "client", "company", "office", "manager", "project", "deadline"],
            "technology": ["computer", "internet", "software", "digital", "online", "app", "device", "system"],
            "education": ["student", "teacher", "school", "university", "study", "learn", "course", "exam"],
            "food": ["restaurant", "meal", "menu", "order", "cook", "eat", "drink", "kitchen"],
            "travel": ["airport", "flight", "ticket", "luggage", "passport", "journey", "destination", "trip"],
            "health": ["doctor", "hospital", "medicine", "treatment", "patient", "healthy", "illness", "exercise"],
            "shopping": ["store", "price", "buy", "sell", "customer", "product", "payment", "discount"]
        }
        
        clusters = {}
        
        for item in vocabulary_items:
            word = item.get("word", "").lower()
            for field, keywords in semantic_fields.items():
                if any(keyword in word or word in keyword for keyword in keywords):
                    if field not in clusters:
                        clusters[field] = []
                    clusters[field].append(item.get("word"))
                    break
        
        # Filtrar clusters com pelo menos 2 palavras
        return {field: words for field, words in clusters.items() if len(words) >= 2}
    
    # =============================================================================
    # HELPER METHODS - PROGRESSÃO HIERÁRQUICA
    # =============================================================================
    
    async def _analyze_hierarchical_vocabulary_connectivity(
        self, 
        vocabulary_words: List[str], 
        taught_vocabulary: List[str],
        reinforcement_words: List[str],
        sequence_order: int
    ) -> Dict[str, Any]:
        """Analisar conectividade entre vocabulários na hierarquia."""
        
        # Converter para sets para análises
        vocab_set = set(word.lower() for word in vocabulary_words)
        taught_set = set(word.lower() for word in taught_vocabulary)
        reinforcement_set = set(word.lower() for word in reinforcement_words)
        
        # Análises de intersecção
        overlapping_words = vocab_set.intersection(taught_set)
        new_words = vocab_set - taught_set
        reinforcement_opportunities = reinforcement_set - vocab_set
        
        # Análise de progressão baseada na sequência
        progression_analysis = self._analyze_sequence_progression(sequence_order, len(vocab_set), len(taught_set))
        
        # Potencial de conectividade (palavras que podem ser combinadas)
        connectivity_potential = self._calculate_connectivity_potential(vocabulary_words, taught_vocabulary)
        
        return {
            "new_words": list(new_words),
            "overlapping_words": list(overlapping_words),
            "reinforcement_opportunities": list(reinforcement_opportunities)[:5],
            "connectivity_score": len(overlapping_words) / max(len(vocab_set), 1),
            "new_word_ratio": len(new_words) / max(len(vocab_set), 1),
            "progression_analysis": progression_analysis,
            "connectivity_potential": connectivity_potential,
            "sequence_order": sequence_order
        }
    
    def _determine_hierarchical_progression_strategy(self, cefr_level: str, sequence_order: int, progression_level: str, book_name: str) -> str:
        """Determinar estratégia de progressão baseada na hierarquia."""
        
        # Análise por posição na sequência
        if sequence_order <= 2:
            base_strategy = "foundation_introduction"
        elif sequence_order <= 5:
            base_strategy = "skill_building"
        elif sequence_order <= 10:
            base_strategy = "consolidation"
        else:
            base_strategy = "mastery_application"
        
        # Modificar baseado no nível CEFR
        if cefr_level in ["A1", "A2"]:
            level_modifier = "basic"
        elif cefr_level in ["B1", "B2"]:
            level_modifier = "intermediate"
        else:
            level_modifier = "advanced"
        
        # Modificar baseado no nome do book (se contém indicadores específicos)
        book_modifier = ""
        if "foundation" in book_name.lower():
            book_modifier = "_foundation"
        elif "business" in book_name.lower():
            book_modifier = "_professional"
        elif "academic" in book_name.lower():
            book_modifier = "_academic"
        
        return f"{base_strategy}_{level_modifier}{book_modifier}"
    
    def _get_sentence_complexity_guidance(self, cefr_level: str, sequence_order: int, vocabulary_complexity: str) -> Dict[str, Any]:
        """Obter orientações de complexidade para sentences."""
        
        # Definir progressão de complexidade
        complexity_progression_maps = {
            "A1": {
                "start_complexity": "very_simple",
                "end_complexity": "simple",
                "progression_pattern": "Linear progression from 3-4 words to 6-8 words",
                "sentence_types": ["simple_statements", "basic_questions"],
                "max_clauses": 1
            },
            "A2": {
                "start_complexity": "simple",
                "end_complexity": "intermediate",
                "progression_pattern": "Build from simple to compound sentences",
                "sentence_types": ["compound_sentences", "basic_complex"],
                "max_clauses": 2
            },
            "B1": {
                "start_complexity": "intermediate",
                "end_complexity": "complex",
                "progression_pattern": "Introduce complex structures gradually",
                "sentence_types": ["complex_sentences", "conditional_structures"],
                "max_clauses": 3
            },
            "B2": {
                "start_complexity": "complex",
                "end_complexity": "sophisticated",
                "progression_pattern": "Use varied complex structures",
                "sentence_types": ["multi_clause", "embedded_structures"],
                "max_clauses": 4
            },
            "C1": {
                "start_complexity": "sophisticated",
                "end_complexity": "advanced",
                "progression_pattern": "Native-like structural variety",
                "sentence_types": ["advanced_structures", "discourse_markers"],
                "max_clauses": 5
            },
            "C2": {
                "start_complexity": "advanced",
                "end_complexity": "native_level",
                "progression_pattern": "Natural complexity with stylistic variation",
                "sentence_types": ["native_structures", "stylistic_variety"],
                "max_clauses": 6
            }
        }
        
        base_guidance = complexity_progression_maps.get(cefr_level, complexity_progression_maps["A2"])
        
        # Ajustar baseado na posição da sequência
        if sequence_order <= 3:
            base_guidance["adjustment"] = "Keep slightly simpler for early units"
        elif sequence_order >= 10:
            base_guidance["adjustment"] = "Allow more complexity for later units"
        else:
            base_guidance["adjustment"] = "Standard progression"
        
        # Ajustar baseado na complexidade do vocabulário
        if vocabulary_complexity == "complex":
            base_guidance["vocabulary_adjustment"] = "Use simpler sentence structures to balance vocabulary complexity"
        elif vocabulary_complexity == "simple":
            base_guidance["vocabulary_adjustment"] = "Can use more complex sentence structures"
        else:
            base_guidance["vocabulary_adjustment"] = "Balanced complexity"
        
        return base_guidance
    
    # =============================================================================
    # HELPER METHODS - CACHE E PERFORMANCE
    # =============================================================================
    
    def _generate_intelligent_cache_key(self, prompt_messages: List[Any], request: SentencesGenerationRequest) -> str:
        """Gerar chave de cache inteligente baseada em contexto."""
        
        # Componentes da chave
        unit_context = request.unit_data.get("context", "")
        vocabulary_words = [item.get("word") for item in request.vocabulary_data.get("items", [])][:10]
        cefr_level = request.unit_data.get("cefr_level", "A2")
        sequence_order = request.hierarchy_context.get("sequence_order", 1)
        
        # Criar hash baseado em componentes críticos
        key_components = [
            unit_context,
            "|".join(sorted(vocabulary_words)),
            cefr_level,
            str(sequence_order),
            str(request.target_sentences)
        ]
        
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache_with_ttl(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obter do cache com verificação de TTL."""
        
        current_time = time.time()
        
        # Verificar se existe e não expirou
        if (cache_key in self._memory_cache and 
            cache_key in self._cache_expiry and
            current_time < self._cache_expiry[cache_key]):
            return self._memory_cache[cache_key]
        
        # Limpar entrada expirada
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        if cache_key in self._cache_expiry:
            del self._cache_expiry[cache_key]
        
        return None
    
    def _save_to_cache_with_ttl(self, cache_key: str, data: Dict[str, Any]) -> None:
        """Salvar no cache com TTL."""
        
        current_time = time.time()
        
        # Limpar cache se muito grande
        if len(self._memory_cache) >= self._max_cache_size:
            self._cleanup_cache()
        
        # Salvar com timestamp de expiração
        self._memory_cache[cache_key] = data
        self._cache_expiry[cache_key] = current_time + self._cache_ttl
    
    def _cleanup_cache(self) -> None:
        """Limpar entradas expiradas do cache."""
        
        current_time = time.time()
        expired_keys = [
            key for key, expiry_time in self._cache_expiry.items()
            if current_time >= expiry_time
        ]
        
        for key in expired_keys:
            if key in self._memory_cache:
                del self._memory_cache[key]
            if key in self._cache_expiry:
                del self._cache_expiry[key]
        
        # Se ainda muito grande, remover os mais antigos
        if len(self._memory_cache) >= self._max_cache_size:
            sorted_keys = sorted(self._cache_expiry.keys(), key=lambda k: self._cache_expiry[k])
            keys_to_remove = sorted_keys[:len(sorted_keys)//2]
            
            for key in keys_to_remove:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                if key in self._cache_expiry:
                    del self._cache_expiry[key]
    
    # =============================================================================
    # HELPER METHODS - PARSING E ESTRUTURAÇÃO
    # =============================================================================
    
    def _validate_sentences_structure(self, data: Dict[str, Any]) -> bool:
        """Validar estrutura básica dos dados de sentences."""
        
        if not isinstance(data, dict):
            return False
        
        # Verificar campos obrigatórios
        if "sentences" not in data:
            return False
        
        sentences = data["sentences"]
        if not isinstance(sentences, list) or len(sentences) == 0:
            return False
        
        # Verificar estrutura de pelo menos uma sentence
        for sentence in sentences[:3]:  # Verificar primeiras 3
            if not isinstance(sentence, dict):
                return False
            if "text" not in sentence or not sentence["text"]:
                return False
        
        return True
    
    async def _extract_sentences_structured(self, content: str) -> Dict[str, Any]:
        """Extrair sentences usando parsing estruturado."""
        
        sentences = []
        lines = content.split('\n')
        
        current_sentence = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detectar início de nova sentence
            if line.startswith('"') and line.endswith('"'):
                if current_sentence:
                    sentences.append(current_sentence)
                current_sentence = {
                    "text": line.strip('"'),
                    "vocabulary_used": [],
                    "context_situation": "general_context",
                    "complexity_level": "intermediate"
                }
            
            # Detectar campos específicos
            elif "vocabulary_used:" in line.lower():
                vocab_part = line.split(":", 1)[1].strip()
                vocab_words = [w.strip() for w in vocab_part.split(",")]
                current_sentence["vocabulary_used"] = vocab_words
            
            elif "context:" in line.lower():
                context = line.split(":", 1)[1].strip()
                current_sentence["context_situation"] = context
        
        # Adicionar última sentence
        if current_sentence:
            sentences.append(current_sentence)
        
        # Se não encontrou sentences estruturadas, usar método básico
        if not sentences:
            return self._extract_sentences_from_text_advanced(content)
        
        return {
            "sentences": sentences,
            "vocabulary_coverage": 0.8,
            "contextual_coherence": 0.7,
            "progression_appropriateness": 0.8
        }
    
    def _extract_sentences_from_text_advanced(self, text: str) -> Dict[str, Any]:
        """Extrair sentences de texto com análise avançada."""
        
        # Estratégias múltiplas de extração
        sentences = []
        import re

        # Estratégia 1: Por numeração
        numbered_pattern = r'^\d+\.\s*(.+)'

        
        for line in text.split('\n'):
            match = re.match(numbered_pattern, line.strip())
            if match:
                sentences.append(match.group(1).strip())
        
        # Estratégia 2: Por pontuação
        if not sentences:
            sentence_candidates = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentence_candidates if len(s.strip()) > 15]
        
        # Estratégia 3: Por linhas significativas
        if not sentences:
            lines = text.split('\n')
            sentences = [line.strip() for line in lines if len(line.strip()) > 15 and any(char.isalpha() for char in line)]
        
        # Converter para estrutura
        structured_sentences = []
        for i, sentence in enumerate(sentences[:15]):  # Máximo 15
            structured_sentences.append({
                "text": sentence,
                "vocabulary_used": [],
                "context_situation": f"extracted_context_{i+1}",
                "complexity_level": "intermediate",
                "reinforces_previous": [],
                "introduces_new": [],
                "phonetic_features": [],
                "pronunciation_notes": None
            })
        
        return {
            "sentences": structured_sentences,
            "vocabulary_coverage": 0.6,
            "contextual_coherence": 0.5,
            "progression_appropriateness": 0.6
        }
    
    async def _convert_string_to_structured_sentence(self, sentence_text: str, vocabulary_words: List[str], index: int, request: SentencesGenerationRequest) -> Dict[str, Any]:
        """Converter string simples para objeto de sentence estruturado com contexto."""
        
        # Identificar vocabulário usado na sentence
        vocabulary_used = []
        for word in vocabulary_words:
            if word.lower() in sentence_text.lower():
                vocabulary_used.append(word)
        
        # Determinar complexidade baseada em múltiplos fatores
        word_count = len(sentence_text.split())
        clause_count = sentence_text.count(',') + 1
        
        if word_count <= 6 and clause_count == 1:
            complexity = "simple"
        elif word_count <= 12 and clause_count <= 2:
            complexity = "intermediate"
        else:
            complexity = "complex"
        
        # Determinar contexto baseado no tema da unidade
        unit_context = request.unit_data.get("context", "")
        context_situation = self._infer_context_situation(sentence_text, unit_context, index)
        
        return {
            "text": sentence_text,
            "vocabulary_used": vocabulary_used,
            "context_situation": context_situation,
            "complexity_level": complexity,
            "reinforces_previous": [],
            "introduces_new": vocabulary_used,
            "phonetic_features": [],
            "pronunciation_notes": None,
            "sentence_length": word_count,
            "grammatical_focus": self._identify_grammatical_focus(sentence_text)
        }
    
    async def _validate_and_enrich_sentence_advanced(self, sentence_obj: Dict[str, Any], vocabulary_analysis: Dict[str, Any], request: SentencesGenerationRequest) -> Dict[str, Any]:
        """Validar e enriquecer objeto de sentence com análise avançada."""
        
        vocabulary_words = vocabulary_analysis["vocabulary_words"]
        
        # Campos obrigatórios com valores padrão inteligentes
        required_fields = {
            "text": "Sample sentence using vocabulary.",
            "vocabulary_used": [],
            "context_situation": "general_context",
            "complexity_level": "intermediate",
            "reinforces_previous": [],
            "introduces_new": [],
            "phonetic_features": [],
            "pronunciation_notes": None
        }
        
        for field, default_value in required_fields.items():
            if field not in sentence_obj:
                sentence_obj[field] = default_value
        
        # Validar e corrigir vocabulário usado
        text = sentence_obj.get("text", "")
        declared_vocab = sentence_obj.get("vocabulary_used", [])
        actual_vocab = [word for word in vocabulary_words if word.lower() in text.lower()]
        
        # Corrigir vocabulário se necessário
        if set(actual_vocab) != set(declared_vocab):
            sentence_obj["vocabulary_used"] = actual_vocab
            sentence_obj["introduces_new"] = actual_vocab
        
        # Analisar palavras de reforço
        taught_vocabulary = request.rag_context.get("taught_vocabulary", [])
        reinforcement_words = [word for word in taught_vocabulary if word.lower() in text.lower()]
        sentence_obj["reinforces_previous"] = reinforcement_words
        
        # Enriquecer com análise gramatical
        sentence_obj["grammatical_focus"] = self._identify_grammatical_focus(text)
        sentence_obj["sentence_length"] = len(text.split())
        
        # Determinar função comunicativa
        sentence_obj["communicative_function"] = self._determine_communicative_function(text)
        
        return sentence_obj
    
    # =============================================================================
    # HELPER METHODS - VALIDAÇÃO E MÉTRICAS
    # =============================================================================
    
    def _calculate_contextual_coherence(self, sentences: List[Dict[str, Any]], request: SentencesGenerationRequest) -> float:
        """Calcular coerência contextual das sentences."""
        
        unit_context = request.unit_data.get("context", "").lower()
        
        if not unit_context:
            return 0.7  # Score padrão se não há contexto
        
        # Palavras-chave do contexto
        context_keywords = set(unit_context.split())
        
        coherent_sentences = 0
        for sentence in sentences:
            sentence_text = sentence.get("text", "").lower()
            sentence_words = set(sentence_text.split())
            
            # Verificar sobreposição de palavras-chave
            overlap = len(context_keywords.intersection(sentence_words))
            if overlap > 0:
                coherent_sentences += 1
        
        return coherent_sentences / max(len(sentences), 1)
    
    def _calculate_progression_appropriateness(self, complexity_progression: List[str], request: SentencesGenerationRequest) -> float:
        """Calcular adequação da progressão de complexidade."""
        
        if not complexity_progression:
            return 0.7
        
        # Mapear complexidades para valores numéricos
        complexity_values = {
            "simple": 1,
            "very_simple": 0.5,
            "intermediate": 2,
            "complex": 3,
            "sophisticated": 4,
            "advanced": 5
        }
        
        # Calcular progressão
        values = [complexity_values.get(comp, 2) for comp in complexity_progression]
        
        # Verificar se há progressão crescente ou estável
        progression_score = 0
        for i in range(1, len(values)):
            if values[i] >= values[i-1]:  # Permite progressão ou estabilidade
                progression_score += 1
        
        return progression_score / max(len(values) - 1, 1)
    
    def _calculate_thematic_consistency(self, sentences: List[Dict[str, Any]], vocabulary_analysis: Dict[str, Any]) -> float:
        """Calcular consistência temática das sentences."""
        
        thematic_clusters = vocabulary_analysis.get("thematic_clusters", {})
        
        if not thematic_clusters:
            return 0.8  # Score padrão se não há clusters identificados
        
        # Verificar quantas sentences usam vocabulário dos clusters principais
        main_themes = list(thematic_clusters.keys())[:3]  # Top 3 temas
        thematic_sentences = 0
        
        for sentence in sentences:
            vocabulary_used = [word.lower() for word in sentence.get("vocabulary_used", [])]
            
            for theme in main_themes:
                theme_words = [word.lower() for word in thematic_clusters[theme]]
                if any(word in vocabulary_used for word in theme_words):
                    thematic_sentences += 1
                    break
        
        return thematic_sentences / max(len(sentences), 1)
    
    def _validate_complexity_progression(self, sentences: List[Dict[str, Any]], cefr_level: str) -> Dict[str, Any]:
        """Validar progressão de complexidade das sentences."""
        
        complexities = [sentence.get("complexity_level", "intermediate") for sentence in sentences]
        
        # Complexidades esperadas por nível CEFR
        expected_complexities = {
            "A1": ["simple", "very_simple"],
            "A2": ["simple", "intermediate"],
            "B1": ["intermediate", "complex"],
            "B2": ["intermediate", "complex", "sophisticated"],
            "C1": ["complex", "sophisticated", "advanced"],
            "C2": ["sophisticated", "advanced"]
        }
        
        expected = expected_complexities.get(cefr_level, ["intermediate"])
        
        # Verificar adequação
        appropriate_count = 0
        issues = []
        
        for i, complexity in enumerate(complexities):
            if complexity in expected:
                appropriate_count += 1
            else:
                issues.append(f"Sentence {i+1}: {complexity} not appropriate for {cefr_level}")
        
        appropriateness_score = appropriate_count / max(len(complexities), 1)
        is_valid = appropriateness_score >= 0.7
        
        return {
            "is_valid": is_valid,
            "appropriateness_score": appropriateness_score,
            "issues": issues,
            "expected_complexities": expected,
            "actual_complexities": complexities
        }
    
    def _validate_vocabulary_coverage(self, sentences: List[Dict[str, Any]], vocabulary_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validar cobertura de vocabulário nas sentences."""
        
        vocabulary_items = vocabulary_data.get("items", [])
        target_words = [item.get("word", "").lower() for item in vocabulary_items]
        
        # Coletar palavras usadas
        used_words = set()
        for sentence in sentences:
            vocabulary_used = sentence.get("vocabulary_used", [])
            used_words.update([word.lower() for word in vocabulary_used])
        
        # Calcular cobertura
        coverage = len(used_words.intersection(set(target_words))) / max(len(target_words), 1)
        is_adequate = coverage >= 0.8  # 80% de cobertura mínima
        
        missing_words = [word for word in target_words if word not in used_words]
        
        return {
            "is_adequate": is_adequate,
            "coverage": coverage,
            "used_words": list(used_words),
            "missing_words": missing_words,
            "target_words_count": len(target_words),
            "used_words_count": len(used_words)
        }
    
    def _validate_contextual_coherence(self, sentences: List[Dict[str, Any]], unit_context: str) -> Dict[str, Any]:
        """Validar coerência contextual das sentences."""
        
        if not unit_context:
            return {"is_coherent": True, "coherence_score": 0.8}
        
        context_keywords = set(unit_context.lower().split())
        coherent_count = 0
        
        for sentence in sentences:
            sentence_text = sentence.get("text", "").lower()
            context_situation = sentence.get("context_situation", "").lower()
            
            # Verificar se a sentence se relaciona com o contexto
            sentence_words = set(sentence_text.split())
            situation_words = set(context_situation.split())
            
            # Calcular sobreposição
            text_overlap = len(context_keywords.intersection(sentence_words))
            situation_overlap = len(context_keywords.intersection(situation_words))
            
            if text_overlap > 0 or situation_overlap > 0:
                coherent_count += 1
        
        coherence_score = coherent_count / max(len(sentences), 1)
        is_coherent = coherence_score >= 0.6
        
        return {
            "is_coherent": is_coherent,
            "coherence_score": coherence_score,
            "coherent_sentences": coherent_count,
            "total_sentences": len(sentences),
            "context_keywords": list(context_keywords)
        }
    
    # =============================================================================
    # HELPER METHODS - AJUSTES E MELHORIAS
    # =============================================================================
    
    async def _adjust_complexity_progression(self, sentences: List[Dict[str, Any]], issues: List[str]) -> List[Dict[str, Any]]:
        """Ajustar progressão de complexidade das sentences."""
        
        for i, sentence in enumerate(sentences):
            # Verificar se esta sentence tem problemas
            sentence_issues = [issue for issue in issues if f"Sentence {i+1}" in issue]
            
            if sentence_issues:
                # Ajustar complexidade baseado na posição
                if i < len(sentences) // 3:  # Primeiro terço
                    sentence["complexity_level"] = "simple"
                elif i < 2 * len(sentences) // 3:  # Segundo terço
                    sentence["complexity_level"] = "intermediate"
                else:  # Último terço
                    sentence["complexity_level"] = "complex"
        
        return sentences
    
    async def _improve_vocabulary_coverage(self, sentences: List[Dict[str, Any]], missing_words: List[str], request: SentencesGenerationRequest) -> List[Dict[str, Any]]:
        """Melhorar cobertura de vocabulário adicionando palavras ausentes."""
        
        if not missing_words:
            return sentences
        
        # Tentar adicionar palavras ausentes às sentences existentes
        for word in missing_words[:5]:  # Limitar a 5 palavras
            # Encontrar sentence mais adequada para adicionar a palavra
            best_sentence_idx = self._find_best_sentence_for_word(sentences, word, request)
            
            if best_sentence_idx is not None:
                sentence = sentences[best_sentence_idx]
                
                # Adicionar palavra ao vocabulário usado
                if "vocabulary_used" not in sentence:
                    sentence["vocabulary_used"] = []
                
                if word not in sentence["vocabulary_used"]:
                    sentence["vocabulary_used"].append(word)
                    sentence["introduces_new"].append(word)
                    
                    # Opcionalmente, modificar o texto da sentence para incluir a palavra
                    # (implementação simplificada)
                    current_text = sentence.get("text", "")
                    if word.lower() not in current_text.lower():
                        sentence["text"] = self._integrate_word_into_sentence(current_text, word)
        
        return sentences
    
    def _find_best_sentence_for_word(self, sentences: List[Dict[str, Any]], word: str, request: SentencesGenerationRequest) -> Optional[int]:
        """Encontrar a sentence mais adequada para adicionar uma palavra."""
        
        # Critérios de adequação:
        # 1. Sentence com menos vocabulário (para equilibrar)
        # 2. Sentence com contexto relacionado
        # 3. Sentence com complexidade adequada
        
        best_score = -1
        best_idx = None
        
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Critério 1: Menos vocabulário usado (score mais alto)
            vocab_used = len(sentence.get("vocabulary_used", []))
            if vocab_used < 3:
                score += 3
            elif vocab_used < 5:
                score += 1
            
            # Critério 2: Contexto relacionado
            context_situation = sentence.get("context_situation", "").lower()
            unit_context = request.unit_data.get("context", "").lower()
            if any(keyword in context_situation for keyword in unit_context.split()):
                score += 2
            
            # Critério 3: Complexidade adequada (não muito complexa)
            complexity = sentence.get("complexity_level", "intermediate")
            if complexity in ["simple", "intermediate"]:
                score += 1
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        return best_idx
    
    def _integrate_word_into_sentence(self, current_text: str, word: str) -> str:
        """Integrar uma palavra em uma sentence existente (implementação básica)."""
        
        # Implementação simplificada - adicionar palavra de forma natural
        # Em uma implementação completa, isso usaria análise sintática
        
        if current_text.endswith('.'):
            # Adicionar palavra antes do ponto final
            return f"{current_text[:-1]} with {word}."
        else:
            # Adicionar palavra no final
            return f"{current_text} {word}."
    
    # =============================================================================
    # HELPER METHODS - ANÁLISE FONÉTICA E CONECTIVIDADE
    # =============================================================================
    
    async def _enrich_sentence_with_phonetics(self, sentence: Dict[str, Any], sentence_phonetics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enriquecer sentence com dados fonéticos."""
        
        if "phonetic_features" not in sentence:
            sentence["phonetic_features"] = []
        
        # Analisar características fonéticas
        avg_syllables = sum(p["syllables"] for p in sentence_phonetics) / len(sentence_phonetics)
        
        # Adicionar características baseadas na análise
        if avg_syllables > 2.5:
            sentence["phonetic_features"].append("multisyllabic_focus")
        
        # Identificar sons específicos
        all_phonemes = " ".join([p["phoneme"] for p in sentence_phonetics])
        
        difficult_sounds = ["θ", "ð", "ŋ", "ʃ", "ʒ", "ɹ"]
        present_sounds = [sound for sound in difficult_sounds if sound in all_phonemes]
        
        if present_sounds:
            sentence["phonetic_features"].append("challenging_sounds")
            sentence["pronunciation_notes"] = f"Focus on sounds: {', '.join(present_sounds)}"
        
        # Analisar padrões de stress
        stress_count = all_phonemes.count("ˈ") + all_phonemes.count("ˌ")
        if stress_count >= 2:
            sentence["phonetic_features"].append("stress_pattern_practice")
        
        return sentence
    
    def _identify_global_pronunciation_patterns(self, phonetic_map: Dict[str, Dict], sentences: List[Dict]) -> List[str]:
        """Identificar padrões de pronúncia globais nas sentences."""
        
        patterns = []
        
        # Coletar todos os dados fonéticos usados
        all_phonetic_data = []
        for sentence in sentences:
            vocabulary_used = sentence.get("vocabulary_used", [])
            for word in vocabulary_used:
                if word.lower() in phonetic_map:
                    all_phonetic_data.append(phonetic_map[word.lower()])
        
        if not all_phonetic_data:
            return patterns
        
        # Analisar padrões de stress
        stress_types = []
        for data in all_phonetic_data:
            phoneme = data["phoneme"]
            if "ˈ" in phoneme:
                stress_types.append("primary_stress")
            if "ˌ" in phoneme:
                stress_types.append("secondary_stress")
        
        if stress_types:
            unique_stress = set(stress_types)
            patterns.append(f"Stress patterns: {len(unique_stress)} types across sentences")
        
        # Analisar distribuição de sílabas
        syllable_counts = [data["syllables"] for data in all_phonetic_data]
        if syllable_counts:
            avg_syllables = sum(syllable_counts) / len(syllable_counts)
            max_syllables = max(syllable_counts)
            patterns.append(f"Syllable complexity: avg {avg_syllables:.1f}, max {max_syllables}")
        
        # Analisar sons específicos
        all_phonemes = " ".join([data["phoneme"] for data in all_phonetic_data])
        
        vowel_sounds = ["æ", "ʌ", "ɜː", "ɪ", "ʊ", "ə"]
        consonant_clusters = ["θ", "ð", "ʃ", "ʒ", "ŋ", "ɹ"]
        
        present_vowels = [v for v in vowel_sounds if v in all_phonemes]
        present_consonants = [c for c in consonant_clusters if c in all_phonemes]
        
        if present_vowels:
            patterns.append(f"Vowel focus: {len(present_vowels)} challenging vowel sounds")
        
        if present_consonants:
            patterns.append(f"Consonant focus: {len(present_consonants)} challenging consonants")
        
        return patterns
    
    def _analyze_hierarchical_connectivity(self, sentences: List[Dict], progression_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analisar conectividade hierárquica das sentences."""
        
        taught_vocabulary = progression_context.get("taught_vocabulary", [])
        reinforcement_words = progression_context.get("reinforcement_words", [])
        
        # Analisar quantas sentences fazem conexões
        connecting_sentences = 0
        total_connections = 0
        
        for sentence in sentences:
            reinforced = sentence.get("reinforces_previous", [])
            if reinforced:
                connecting_sentences += 1
                total_connections += len(reinforced)
        
        connectivity_score = connecting_sentences / max(len(sentences), 1)
        average_connections = total_connections / max(connecting_sentences, 1)
        
        # Analisar distribuição de palavras de reforço
        reinforcement_usage = {}
        for sentence in sentences:
            for word in sentence.get("reinforces_previous", []):
                reinforcement_usage[word] = reinforcement_usage.get(word, 0) + 1
        
        return {
            "connectivity_score": connectivity_score,
            "connecting_sentences": connecting_sentences,
            "total_connections": total_connections,
            "average_connections_per_sentence": average_connections,
            "reinforcement_usage": reinforcement_usage,
            "well_distributed": len(reinforcement_usage) >= len(reinforcement_words) * 0.6
        }
    
    # =============================================================================
    # HELPER METHODS - ANÁLISE SEMÂNTICA E CONTEXTUAL
    # =============================================================================
    
    def _infer_context_situation(self, sentence_text: str, unit_context: str, index: int) -> str:
        """Inferir situação contextual de uma sentence."""
        
        # Mapear contextos comuns
        context_mappings = {
            "hotel": ["check_in", "reservation", "room_service", "reception"],
            "restaurant": ["ordering", "menu_reading", "paying_bill", "reservation"],
            "business": ["meeting", "presentation", "negotiation", "planning"],
            "travel": ["airport", "transportation", "directions", "booking"],
            "education": ["classroom", "studying", "examination", "discussion"],
            "shopping": ["purchasing", "asking_prices", "comparing_products", "payment"]
        }
        
        # Identificar contexto principal
        unit_context_lower = unit_context.lower()
        sentence_lower = sentence_text.lower()
        
        for main_context, situations in context_mappings.items():
            if main_context in unit_context_lower:
                # Escolher situação baseada no conteúdo da sentence
                for situation in situations:
                    if any(word in sentence_lower for word in situation.split('_')):
                        return situation
                # Se não encontrou situação específica, usar a primeira
                return situations[index % len(situations)]
        
        # Contexto padrão baseado no índice
        default_contexts = ["general_conversation", "daily_interaction", "practical_situation", "social_context"]
        return default_contexts[index % len(default_contexts)]
    
    def _identify_grammatical_focus(self, sentence_text: str) -> List[str]:
        """Identificar foco gramatical de uma sentence."""
        
        focus_areas = []
        text_lower = sentence_text.lower()
        
        # Identificar estruturas gramaticais
        if any(word in text_lower for word in ["is", "are", "was", "were", "am"]):
            focus_areas.append("be_verb")
        
        if any(word in text_lower for word in ["have", "has", "had"]):
            focus_areas.append("have_verb")
        
        if any(word in text_lower for word in ["will", "would", "can", "could", "should", "must"]):
            focus_areas.append("modal_verbs")
        
        if any(word in text_lower for word in ["the", "a", "an"]):
            focus_areas.append("articles")
        
        if "?" in sentence_text:
            focus_areas.append("question_formation")
        
        if "not" in text_lower or "n't" in text_lower:
            focus_areas.append("negation")
        
        # Se não identificou nenhum foco específico
        if not focus_areas:
            focus_areas.append("general_structure")
        
        return focus_areas
    
    def _determine_communicative_function(self, sentence_text: str) -> str:
        """Determinar função comunicativa da sentence."""
        
        text_lower = sentence_text.lower()
        
        # Identificar função baseada em padrões
        if "?" in sentence_text:
            if any(word in text_lower for word in ["what", "where", "when", "why", "how", "who"]):
                return "asking_information"
            else:
                return "asking_confirmation"
        
        elif "!" in sentence_text:
            return "expressing_emotion"
        
        elif any(phrase in text_lower for phrase in ["please", "could you", "would you", "can you"]):
            return "making_request"
        
        elif any(phrase in text_lower for phrase in ["hello", "hi", "good morning", "good afternoon"]):
            return "greeting"
        
        elif any(phrase in text_lower for phrase in ["thank you", "thanks", "goodbye", "bye"]):
            return "social_formula"
        
        elif any(word in text_lower for word in ["think", "believe", "feel", "opinion"]):
            return "expressing_opinion"
        
        else:
            return "giving_information"
    
    # =============================================================================
    # HELPER METHODS - ANÁLISE DE PROGRESSÃO
    # =============================================================================
    
    def _analyze_sequence_progression(self, sequence_order: int, vocab_count: int, taught_count: int) -> Dict[str, Any]:
        """Analisar progressão baseada na sequência."""
        
        # Calcular densidade de vocabulário
        if sequence_order == 1:
            expected_density = "high_new_vocabulary"
        elif sequence_order <= 5:
            expected_density = "balanced_new_reinforcement"
        else:
            expected_density = "reinforcement_focused"
        
        # Calcular progressão acumulativa
        total_vocabulary = vocab_count + taught_count
        new_vocabulary_ratio = vocab_count / max(total_vocabulary, 1)
        
        # Determinar adequação da progressão
        progression_adequacy = self._evaluate_progression_adequacy(sequence_order, new_vocabulary_ratio)
        
        return {
            "sequence_order": sequence_order,
            "expected_density": expected_density,
            "new_vocabulary_ratio": new_vocabulary_ratio,
            "progression_adequacy": progression_adequacy,
            "total_vocabulary_in_context": total_vocabulary
        }
    
    def _calculate_connectivity_potential(self, vocabulary_words: List[str], taught_vocabulary: List[str]) -> Dict[str, Any]:
        """Calcular potencial de conectividade entre vocabulários."""
        
        # Identificar palavras que facilitam conexões
        connective_words = []
        for word in vocabulary_words:
            word_lower = word.lower()
            # Palavras que naturalmente se conectam com outras
            if any(pattern in word_lower for pattern in ["with", "for", "and", "or", "but", "because"]):
                connective_words.append(word)
        
        # Calcular potencial de combinações
        combination_potential = len(vocabulary_words) * len(taught_vocabulary)
        practical_combinations = min(combination_potential, 50)  # Limite prático
        
        return {
            "connective_words": connective_words,
            "combination_potential": practical_combinations,
            "connectivity_score": len(connective_words) / max(len(vocabulary_words), 1)
        }
    
    def _evaluate_progression_adequacy(self, sequence_order: int, new_vocabulary_ratio: float) -> str:
        """Avaliar adequação da progressão."""
        
        # Definir intervalos esperados por sequência
        if sequence_order <= 2:
            if new_vocabulary_ratio >= 0.8:
                return "excellent"
            elif new_vocabulary_ratio >= 0.6:
                return "good"
            else:
                return "needs_more_new_vocabulary"
        
        elif sequence_order <= 5:
            if 0.4 <= new_vocabulary_ratio <= 0.7:
                return "excellent"
            elif 0.3 <= new_vocabulary_ratio <= 0.8:
                return "good"
            else:
                return "needs_balance_adjustment"
        
        else:  # sequence_order > 5
            if new_vocabulary_ratio <= 0.4:
                return "excellent"
            elif new_vocabulary_ratio <= 0.6:
                return "good"
            else:
                return "too_much_new_vocabulary"
    
    # =============================================================================
    # HELPER METHODS - FALLBACKS E RECUPERAÇÃO
    # =============================================================================
    
    async def _generate_intelligent_fallback_sentences(self, request: SentencesGenerationRequest) -> Dict[str, Any]:
        """Gerar sentences de fallback inteligentes baseadas no contexto."""
        
        vocabulary_items = request.vocabulary_data.get("items", [])
        unit_context = request.unit_data.get("context", "")
        cefr_level = request.unit_data.get("cefr_level", "A2")
        target_count = request.target_sentences
        
        if not vocabulary_items:
            return self._generate_minimal_fallback()
        
        # Extrair palavras do vocabulário
        vocabulary_words = [item.get("word", "") for item in vocabulary_items[:20]]
        
        # Templates baseados no nível CEFR
        templates = self._get_cefr_sentence_templates(cefr_level, unit_context)
        
        # Gerar sentences usando templates
        fallback_sentences = []
        for i in range(min(target_count, 15)):
            template = templates[i % len(templates)]
            
            # Selecionar palavras para esta sentence
            sentence_words = vocabulary_words[i:i+2] if i < len(vocabulary_words) else vocabulary_words[:2]
            
            # Gerar sentence usando template
            sentence_text = self._apply_template(template, sentence_words, unit_context)
            
            fallback_sentences.append({
                "text": sentence_text,
                "vocabulary_used": sentence_words,
                "context_situation": f"fallback_context_{i+1}",
                "complexity_level": template["complexity"],
                "reinforces_previous": [],
                "introduces_new": sentence_words,
                "phonetic_features": [],
                "pronunciation_notes": None,
                "communicative_function": template["function"]
            })
        
        return {
            "sentences": fallback_sentences,
            "vocabulary_coverage": 0.8,
            "contextual_coherence": 0.7,
            "progression_appropriateness": 0.75,
            "fallback_used": True
        }
    
    def _get_cefr_sentence_templates(self, cefr_level: str, unit_context: str) -> List[Dict[str, Any]]:
        """Obter templates de sentences por nível CEFR."""
        
        templates_by_level = {
            "A1": [
                {"pattern": "This is a {word1}.", "complexity": "simple", "function": "description"},
                {"pattern": "I like {word1}.", "complexity": "simple", "function": "preference"},
                {"pattern": "The {word1} is {word2}.", "complexity": "simple", "function": "description"},
                {"pattern": "I have a {word1}.", "complexity": "simple", "function": "possession"},
                {"pattern": "Where is the {word1}?", "complexity": "simple", "function": "asking_location"}
            ],
            "A2": [
                {"pattern": "I would like to {word1} a {word2}.", "complexity": "intermediate", "function": "making_request"},
                {"pattern": "The {word1} is very {word2}.", "complexity": "intermediate", "function": "description"},
                {"pattern": "Can you help me with the {word1}?", "complexity": "intermediate", "function": "asking_help"},
                {"pattern": "I need to {word1} before {word2}.", "complexity": "intermediate", "function": "expressing_necessity"},
                {"pattern": "This {word1} looks {word2}.", "complexity": "intermediate", "function": "observation"}
            ],
            "B1": [
                {"pattern": "I'm interested in {word1} because it's {word2}.", "complexity": "complex", "function": "expressing_interest"},
                {"pattern": "Although the {word1} is {word2}, I still like it.", "complexity": "complex", "function": "contrasting"},
                {"pattern": "If you {word1} the {word2}, it will be better.", "complexity": "complex", "function": "giving_advice"},
                {"pattern": "The {word1} that we discussed is {word2}.", "complexity": "complex", "function": "referring"},
                {"pattern": "I've been {word1} for this {word2} all week.", "complexity": "complex", "function": "describing_duration"}
            ]
        }
        
        # Adaptar templates ao contexto
        base_templates = templates_by_level.get(cefr_level, templates_by_level["A2"])
        
        # Se há contexto específico, adaptar alguns templates
        if "hotel" in unit_context.lower():
            base_templates.append({"pattern": "I'd like to book a {word1} for {word2}.", "complexity": "intermediate", "function": "booking"})
        
        return base_templates
    
    def _apply_template(self, template: Dict[str, Any], words: List[str], context: str) -> str:
        """Aplicar template para gerar sentence."""
        
        pattern = template["pattern"]
        
        # Substituir placeholders com palavras
        if len(words) >= 2:
            sentence = pattern.replace("{word1}", words[0]).replace("{word2}", words[1])
        elif len(words) == 1:
            sentence = pattern.replace("{word1}", words[0]).replace("{word2}", "good")
        else:
            sentence = pattern.replace("{word1}", "example").replace("{word2}", "good")
        
        return sentence
    
    def _generate_minimal_fallback(self) -> Dict[str, Any]:
        """Gerar fallback mínimo quando não há dados suficientes."""
        
        minimal_sentences = [
            {
                "text": "This is an example sentence for learning English.",
                "vocabulary_used": ["example"],
                "context_situation": "general_learning",
                "complexity_level": "intermediate",
                "reinforces_previous": [],
                "introduces_new": ["example"],
                "phonetic_features": [],
                "pronunciation_notes": None
            },
            {
                "text": "Students practice with vocabulary words every day.",
                "vocabulary_used": ["practice", "vocabulary"],
                "context_situation": "educational_context",
                "complexity_level": "intermediate",
                "reinforces_previous": [],
                "introduces_new": ["practice", "vocabulary"],
                "phonetic_features": [],
                "pronunciation_notes": None
            }
        ]
        
        return {
            "sentences": minimal_sentences,
            "vocabulary_coverage": 0.5,
            "contextual_coherence": 0.6,
            "progression_appropriateness": 0.7,
            "minimal_fallback": True
        }
    
    # =============================================================================
    # HELPER METHODS - RECÁLCULO DE MÉTRICAS
    # =============================================================================
    
    def _recalculate_vocabulary_coverage(self, sentences: List[Dict[str, Any]], vocabulary_data: Dict[str, Any]) -> float:
        """Recalcular cobertura de vocabulário após ajustes."""
        
        vocabulary_items = vocabulary_data.get("items", [])
        target_words = set(item.get("word", "").lower() for item in vocabulary_items)
        
        used_words = set()
        for sentence in sentences:
            vocabulary_used = sentence.get("vocabulary_used", [])
            used_words.update(word.lower() for word in vocabulary_used)
        
        if not target_words:
            return 0.8  # Score padrão
        
        return len(used_words.intersection(target_words)) / len(target_words)
    
    def _recalculate_contextual_coherence(self, sentences: List[Dict[str, Any]], request: SentencesGenerationRequest) -> float:
        """Recalcular coerência contextual após ajustes."""
        
        unit_context = request.unit_data.get("context", "").lower()
        
        if not unit_context:
            return 0.75
        
        context_words = set(unit_context.split())
        coherent_count = 0
        
        for sentence in sentences:
            sentence_text = sentence.get("text", "").lower()
            sentence_words = set(sentence_text.split())
            
            if context_words.intersection(sentence_words):
                coherent_count += 1
        
        return coherent_count / max(len(sentences), 1)
    
    def _recalculate_progression_appropriateness(self, sentences: List[Dict[str, Any]], cefr_level: str) -> float:
        """Recalcular adequação da progressão após ajustes."""
        
        complexities = [sentence.get("complexity_level", "intermediate") for sentence in sentences]
        
        # Complexidades esperadas por nível
        expected_for_level = {
            "A1": ["simple", "very_simple"],
            "A2": ["simple", "intermediate"],
            "B1": ["intermediate", "complex"],
            "B2": ["intermediate", "complex"],
            "C1": ["complex", "sophisticated"],
            "C2": ["sophisticated", "advanced"]
        }
        
        expected = expected_for_level.get(cefr_level, ["intermediate"])
        
        appropriate_count = sum(1 for comp in complexities if comp in expected)
        return appropriate_count / max(len(complexities), 1)


# =============================================================================
# FUNÇÃO DE CONVENIÊNCIA PARA ENDPOINTS
# =============================================================================

async def generate_sentences_for_unit_creation(generation_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função de conveniência para geração de sentences em endpoints V2.
    Mantém compatibilidade com a API existente.
    """
    try:
        service = SentencesGeneratorService()
        sentences_section = await service.generate_sentences_for_unit(generation_params)
        
        return {
            "success": True,
            "sentences_section": sentences_section.dict(),
            "generation_time": time.time(),
            "service_version": "langchain_0.3_pydantic_2"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na função de conveniência: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "fallback_available": True
        }


