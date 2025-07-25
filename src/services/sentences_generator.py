# src/services/sentences_generator.py
"""
Serviço de geração de sentences conectadas ao vocabulário.
Implementação com foco em progressão pedagógica e contexto RAG.
Atualizado para LangChain 0.3 e Pydantic 2.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

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
    """Serviço principal para geração de sentences contextuais."""
    
    def __init__(self):
        """Inicializar serviço com configurações."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM para v0.3
        sentences_config = self.model_configs.get("content_configs", {}).get("sentences_generation", {})
        
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=sentences_config.get("temperature", 0.6),  # Criatividade moderada
            max_tokens=sentences_config.get("max_tokens", 2048),   # Suficiente para múltiplas sentences
            timeout=60,
            max_retries=3,
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache simples em memória
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 30
        
        logger.info("✅ SentencesGeneratorService inicializado com LangChain 0.3")
    
    async def generate_sentences_for_unit(self, generation_params: Dict[str, Any]) -> SentencesSection:
        """
        Gerar sentences conectadas ao vocabulário da unidade.
        
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
            
            # 2. Construir contexto de progressão
            progression_context = await self._build_progression_context(request, vocabulary_analysis)
            
            # 3. Gerar prompt contextual
            sentences_prompt = await self._build_contextual_sentences_prompt(
                request, vocabulary_analysis, progression_context
            )
            
            # 4. Gerar sentences via LLM
            raw_sentences = await self._generate_sentences_llm(sentences_prompt)
            
            # 5. Processar e estruturar sentences
            structured_sentences = await self._process_and_structure_sentences(
                raw_sentences, request, vocabulary_analysis
            )
            
            # 6. Enriquecer com elementos fonéticos
            enriched_sentences = await self._enrich_with_phonetic_elements(
                structured_sentences, request.vocabulary_data
            )
            
            # 7. Construir SentencesSection
            sentences_section = SentencesSection(
                sentences=enriched_sentences["sentences"],
                vocabulary_coverage=enriched_sentences["vocabulary_coverage"],
                contextual_coherence=enriched_sentences["contextual_coherence"],
                progression_appropriateness=enriched_sentences["progression_appropriateness"],
                phonetic_progression=enriched_sentences.get("phonetic_progression", []),
                pronunciation_patterns=enriched_sentences.get("pronunciation_patterns", []),
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
        """Analisar vocabulário para geração de sentences."""
        
        vocabulary_items = request.vocabulary_data.get("items", [])
        
        if not vocabulary_items:
            raise ValueError("Vocabulário vazio - não é possível gerar sentences")
        
        # Análise básica do vocabulário
        word_classes = {}
        frequency_levels = {}
        syllable_counts = []
        vocabulary_words = []
        
        for item in vocabulary_items:
            word = item.get("word", "")
            word_class = item.get("word_class", "unknown")
            frequency = item.get("frequency_level", "medium")
            syllables = item.get("syllable_count", 1)
            
            vocabulary_words.append(word)
            word_classes[word_class] = word_classes.get(word_class, 0) + 1
            frequency_levels[frequency] = frequency_levels.get(frequency, 0) + 1
            syllable_counts.append(syllables)
        
        # Determinar complexidade média
        avg_syllables = sum(syllable_counts) / len(syllable_counts) if syllable_counts else 1
        complexity_level = self._determine_complexity_level(avg_syllables, word_classes)
        
        # Identificar palavras-chave para conectividade
        key_words = self._identify_key_connective_words(vocabulary_words, word_classes)
        
        return {
            "vocabulary_words": vocabulary_words,
            "total_words": len(vocabulary_words),
            "word_classes": word_classes,
            "frequency_levels": frequency_levels,
            "complexity_level": complexity_level,
            "avg_syllables": avg_syllables,
            "key_connective_words": key_words,
            "phonetic_items": [item for item in vocabulary_items if item.get("phoneme")]
        }
    
    async def _build_progression_context(
        self, 
        request: SentencesGenerationRequest, 
        vocabulary_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto de progressão pedagógica."""
        
        # Contexto RAG
        rag_context = request.rag_context
        taught_vocabulary = rag_context.get("taught_vocabulary", [])
        progression_level = rag_context.get("progression_level", "intermediate")
        
        # Vocabulário para reforço (palavras já ensinadas)
        reinforcement_words = rag_context.get("vocabulary_for_reinforcement", [])
        
        # Análise de conectividade
        connectivity_analysis = await self._analyze_vocabulary_connectivity(
            vocabulary_analysis["vocabulary_words"], 
            taught_vocabulary,
            reinforcement_words
        )
        
        # Determinar estratégia de progressão
        progression_strategy = self._determine_progression_strategy(
            request.unit_data.get("cefr_level", "A2"),
            request.hierarchy_context.get("sequence_order", 1),
            progression_level
        )
        
        return {
            "taught_vocabulary": taught_vocabulary[:15],  # Limitar para contexto
            "reinforcement_words": reinforcement_words[:5],
            "progression_level": progression_level,
            "connectivity_analysis": connectivity_analysis,
            "progression_strategy": progression_strategy,
            "sequence_order": request.hierarchy_context.get("sequence_order", 1),
            "target_sentences": request.target_sentences
        }
    
    async def _build_contextual_sentences_prompt(
        self,
        request: SentencesGenerationRequest,
        vocabulary_analysis: Dict[str, Any],
        progression_context: Dict[str, Any]
    ) -> List[Any]:
        """Construir prompt contextual para geração de sentences."""
        
        unit_data = request.unit_data
        vocabulary_words = vocabulary_analysis["vocabulary_words"]
        complexity_level = vocabulary_analysis["complexity_level"]
        
        # Guidelines específicos por nível CEFR
        cefr_guidelines = {
            "A1": "Very simple sentences with basic present tense. Use high-frequency vocabulary and short structures.",
            "A2": "Simple sentences with past and future tenses. Include basic connectors like 'and', 'but', 'because'.",
            "B1": "More complex sentences with conditional and modal verbs. Use varied sentence structures.",
            "B2": "Complex and compound sentences with relative clauses. Include sophisticated connectors.",
            "C1": "Advanced sentence structures with nuanced meanings. Use sophisticated vocabulary and expressions.",
            "C2": "Native-level complexity with idiomatic expressions and advanced grammatical structures."
        }
        
        cefr_level = unit_data.get("cefr_level", "A2")
        cefr_guideline = cefr_guidelines.get(cefr_level, cefr_guidelines["A2"])
        
        system_prompt = f"""You are an expert English teacher creating contextual sentences for {cefr_level} level students.

UNIT CONTEXT:
- Title: {unit_data.get('title', '')}
- Context: {unit_data.get('context', '')}
- Level: {cefr_level}
- Language Variant: {unit_data.get('language_variant', 'american_english')}
- Unit Type: {unit_data.get('unit_type', 'lexical_unit')}

VOCABULARY TO CONNECT:
- New Words ({vocabulary_analysis['total_words']}): {', '.join(vocabulary_words[:15])}
- Word Classes: {dict(list(vocabulary_analysis['word_classes'].items())[:5])}
- Complexity Level: {complexity_level}
- Key Connective Words: {', '.join(vocabulary_analysis['key_connective_words'])}

PROGRESSION CONTEXT:
- Previously Taught: {', '.join(progression_context['taught_vocabulary'])}
- Reinforcement Words: {', '.join(progression_context['reinforcement_words'])}
- Progression Strategy: {progression_context['progression_strategy']}
- Sequence in Book: Unit {progression_context['sequence_order']}

CEFR {cefr_level} GUIDELINES: {cefr_guideline}

SENTENCE GENERATION REQUIREMENTS:
1. Create exactly {request.target_sentences} sentences
2. Use each vocabulary word at least once (some words can appear multiple times)
3. Progress from simple to more complex structures
4. Connect new vocabulary with previously taught words when possible
5. Maintain thematic coherence with unit context: "{unit_data.get('context', '')}"
6. Include natural collocations and word combinations
7. Ensure sentences sound natural to native speakers
8. Vary sentence length and structure appropriately for {cefr_level}

CONNECTIVITY PRINCIPLES:
- New words + known words = natural combinations
- Build sentences that demonstrate real usage
- Show how words work together in context
- Create meaningful, communicative examples

OUTPUT FORMAT: Return valid JSON with this exact structure:
{{
  "sentences": [
    {{
      "text": "Example sentence using vocabulary naturally.",
      "vocabulary_used": ["word1", "word2"],
      "context_situation": "situation_description",
      "complexity_level": "simple|intermediate|complex",
      "reinforces_previous": ["known_word1"],
      "introduces_new": ["new_word1"],
      "phonetic_features": ["stress_pattern", "linking_sounds"],
      "pronunciation_notes": "Optional pronunciation guidance"
    }}
  ],
  "vocabulary_coverage": 0.95,
  "contextual_coherence": 0.90,
  "progression_appropriateness": 0.88
}}"""

        human_prompt = f"""Create {request.target_sentences} contextual sentences for "{unit_data.get('title', '')}"

Context: {unit_data.get('context', '')}
Level: {cefr_level}
Vocabulary: {', '.join(vocabulary_words[:10])}

Requirements:
- Each sentence must use at least 1-2 words from the vocabulary list
- Progress from simple to complex sentence structures
- Maintain thematic coherence with the unit context
- Connect new vocabulary with known words naturally
- Sound natural and communicative

Unit Context: {unit_data.get('context', '')}
Complexity Level: {complexity_level}

Generate the JSON structure now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
    
    async def _generate_sentences_llm(self, prompt_messages: List[Any]) -> Dict[str, Any]:
        """Gerar sentences usando LLM com LangChain 0.3."""
        try:
            logger.info("🤖 Consultando LLM para geração de sentences...")
            
            # Verificar cache
            cache_key = self._generate_cache_key(prompt_messages)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                logger.info("📦 Usando resultado do cache")
                return cached_result
            
            # Gerar usando LangChain 0.3 - método ainvoke
            response = await self.llm.ainvoke(prompt_messages)
            content = response.content
            
            # Tentar parsear JSON
            try:
                # Limpar response se necessário
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].strip()
                
                sentences_data = json.loads(content)
                
                if not isinstance(sentences_data, dict):
                    raise ValueError("Response não é um objeto")
                
                # Salvar no cache
                self._save_to_cache(cache_key, sentences_data)
                
                logger.info(f"✅ LLM retornou {len(sentences_data.get('sentences', []))} sentences")
                return sentences_data
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao parsear JSON, tentando extração manual: {str(e)}")
                return self._extract_sentences_from_text(content)
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            # Retornar sentences de fallback
            return self._generate_fallback_sentences()
    
    async def _process_and_structure_sentences(
        self,
        raw_sentences: Dict[str, Any],
        request: SentencesGenerationRequest,
        vocabulary_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processar e estruturar dados de sentences."""
        
        # Extrair sentences
        sentences_list = raw_sentences.get("sentences", [])
        
        if not sentences_list:
            sentences_list = self._generate_fallback_sentences()["sentences"]
        
        # Processar cada sentence
        processed_sentences = []
        vocabulary_used = set()
        
        for i, sentence_data in enumerate(sentences_list):
            if isinstance(sentence_data, str):
                # Converter string simples para estrutura completa
                sentence_obj = self._convert_string_to_sentence_object(
                    sentence_data, vocabulary_analysis["vocabulary_words"], i
                )
            else:
                sentence_obj = sentence_data
            
            # Validar e enriquecer sentence
            enriched_sentence = await self._validate_and_enrich_sentence(
                sentence_obj, vocabulary_analysis["vocabulary_words"]
            )
            
            processed_sentences.append(enriched_sentence)
            vocabulary_used.update(enriched_sentence.get("vocabulary_used", []))
        
        # Calcular métricas
        vocabulary_coverage = len(vocabulary_used) / max(len(vocabulary_analysis["vocabulary_words"]), 1)
        contextual_coherence = raw_sentences.get("contextual_coherence", 0.8)
        progression_appropriateness = raw_sentences.get("progression_appropriateness", 0.8)
        
        return {
            "sentences": processed_sentences,
            "vocabulary_coverage": vocabulary_coverage,
            "contextual_coherence": contextual_coherence,
            "progression_appropriateness": progression_appropriateness,
            "vocabulary_used": list(vocabulary_used),
            "total_sentences": len(processed_sentences)
        }
    
    async def _enrich_with_phonetic_elements(
        self,
        structured_sentences: Dict[str, Any],
        vocabulary_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enriquecer sentences com elementos fonéticos."""
        
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
                    "ipa_variant": item.get("ipa_variant", "general_american")
                }
        
        # Analisar padrões fonéticos nas sentences
        phonetic_progression = []
        pronunciation_patterns = []
        
        for sentence in sentences:
            vocabulary_used = sentence.get("vocabulary_used", [])
            sentence_phonetics = []
            
            for word in vocabulary_used:
                if word.lower() in phonetic_map:
                    phonetic_data = phonetic_map[word.lower()]
                    sentence_phonetics.append({
                        "word": word,
                        "phoneme": phonetic_data["phoneme"],
                        "syllables": phonetic_data["syllables"]
                    })
            
            if sentence_phonetics:
                # Adicionar elementos fonéticos à sentence
                if "phonetic_features" not in sentence:
                    sentence["phonetic_features"] = []
                
                # Identificar padrões fonéticos
                avg_syllables = sum(p["syllables"] for p in sentence_phonetics) / len(sentence_phonetics)
                if avg_syllables > 2:
                    sentence["phonetic_features"].append("multisyllabic_words")
                
                # Identificar sons específicos
                all_phonemes = " ".join([p["phoneme"] for p in sentence_phonetics])
                if any(sound in all_phonemes for sound in ["θ", "ð", "ŋ", "ʃ", "ʒ"]):
                    sentence["phonetic_features"].append("challenging_sounds")
                
                phonetic_progression.append(f"Sentence {len(phonetic_progression)+1}: {len(sentence_phonetics)} phonetic elements")
        
        # Identificar padrões de pronúncia gerais
        common_patterns = self._identify_pronunciation_patterns(phonetic_map, sentences)
        pronunciation_patterns.extend(common_patterns)
        
        # Enriquecer estrutura
        structured_sentences["phonetic_progression"] = phonetic_progression
        structured_sentences["pronunciation_patterns"] = pronunciation_patterns
        
        return structured_sentences
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _determine_complexity_level(self, avg_syllables: float, word_classes: Dict[str, int]) -> str:
        """Determinar nível de complexidade baseado no vocabulário."""
        
        # Análise de complexidade
        noun_ratio = word_classes.get("noun", 0) / max(sum(word_classes.values()), 1)
        verb_ratio = word_classes.get("verb", 0) / max(sum(word_classes.values()), 1)
        
        if avg_syllables <= 1.5 and noun_ratio > 0.6:
            return "simple"
        elif avg_syllables <= 2.5 and verb_ratio > 0.2:
            return "intermediate"
        else:
            return "complex"
    
    def _identify_key_connective_words(self, vocabulary_words: List[str], word_classes: Dict[str, int]) -> List[str]:
        """Identificar palavras-chave para conectividade."""
        
        # Palavras que facilitam conexões
        connective_types = {
            "verb": ["be", "have", "make", "take", "get", "go", "come"],
            "preposition": ["in", "on", "at", "with", "for", "to", "from"],
            "adjective": ["good", "big", "new", "important", "available"],
            "adverb": ["very", "really", "quite", "often", "usually"]
        }
        
        key_words = []
        for word in vocabulary_words:
            word_lower = word.lower()
            for word_type, connectors in connective_types.items():
                if any(connector in word_lower for connector in connectors):
                    key_words.append(word)
                    break
        
        return key_words[:5]  # Top 5 palavras conectivas
    
    async def _analyze_vocabulary_connectivity(
        self, 
        vocabulary_words: List[str], 
        taught_vocabulary: List[str],
        reinforcement_words: List[str]
    ) -> Dict[str, Any]:
        """Analisar conectividade entre vocabulários."""
        
        # Palavras novas vs. conhecidas
        vocab_set = set(word.lower() for word in vocabulary_words)
        taught_set = set(word.lower() for word in taught_vocabulary)
        
        # Intersecções
        overlapping_words = vocab_set.intersection(taught_set)
        new_words = vocab_set - taught_set
        
        # Palavras para reforço
        reinforcement_opportunities = [word for word in reinforcement_words if word.lower() not in vocab_set]
        
        return {
            "new_words": list(new_words),
            "overlapping_words": list(overlapping_words),
            "reinforcement_opportunities": reinforcement_opportunities[:3],
            "connectivity_score": len(overlapping_words) / max(len(vocab_set), 1),
            "new_word_ratio": len(new_words) / max(len(vocab_set), 1)
        }
    
    def _determine_progression_strategy(self, cefr_level: str, sequence_order: int, progression_level: str) -> str:
        """Determinar estratégia de progressão."""
        
        if sequence_order <= 3:
            return "foundation_building"
        elif sequence_order <= 7:
            return "skill_development"
        elif cefr_level in ["A1", "A2"]:
            return "consolidation_basic"
        elif cefr_level in ["B1", "B2"]:
            return "expansion_intermediate"
        else:
            return "mastery_advanced"
    
    def _convert_string_to_sentence_object(self, sentence_text: str, vocabulary_words: List[str], index: int) -> Dict[str, Any]:
        """Converter string simples para objeto de sentence estruturado."""
        
        # Identificar vocabulário usado na sentence
        vocabulary_used = []
        for word in vocabulary_words:
            if word.lower() in sentence_text.lower():
                vocabulary_used.append(word)
        
        # Determinar complexidade baseada no comprimento
        word_count = len(sentence_text.split())
        if word_count <= 6:
            complexity = "simple"
        elif word_count <= 12:
            complexity = "intermediate"
        else:
            complexity = "complex"
        
        return {
            "text": sentence_text,
            "vocabulary_used": vocabulary_used,
            "context_situation": f"general_context_{index+1}",
            "complexity_level": complexity,
            "reinforces_previous": [],
            "introduces_new": vocabulary_used,
            "phonetic_features": [],
            "pronunciation_notes": None
        }
    
    async def _validate_and_enrich_sentence(self, sentence_obj: Dict[str, Any], vocabulary_words: List[str]) -> Dict[str, Any]:
        """Validar e enriquecer objeto de sentence."""
        
        # Campos obrigatórios
        required_fields = ["text", "vocabulary_used", "context_situation", "complexity_level"]
        for field in required_fields:
            if field not in sentence_obj:
                sentence_obj[field] = self._get_default_value(field, sentence_obj, vocabulary_words)
        
        # Validar vocabulário usado
        text = sentence_obj.get("text", "")
        declared_vocab = sentence_obj.get("vocabulary_used", [])
        actual_vocab = [word for word in vocabulary_words if word.lower() in text.lower()]
        
        # Corrigir vocabulário se necessário
        if set(actual_vocab) != set(declared_vocab):
            sentence_obj["vocabulary_used"] = actual_vocab
        
        # Enriquecer com campos opcionais
        if "reinforces_previous" not in sentence_obj:
            sentence_obj["reinforces_previous"] = []
        
        if "introduces_new" not in sentence_obj:
            sentence_obj["introduces_new"] = actual_vocab
        
        if "phonetic_features" not in sentence_obj:
            sentence_obj["phonetic_features"] = []
        
        return sentence_obj
    
    def _get_default_value(self, field: str, sentence_obj: Dict[str, Any], vocabulary_words: List[str]) -> Any:
        """Obter valor padrão para campo faltante."""
        
        defaults = {
            "text": "Sample sentence using vocabulary.",
            "vocabulary_used": vocabulary_words[:2],
            "context_situation": "general_context",
            "complexity_level": "intermediate"
        }
        
        return defaults.get(field, "")
    
    def _identify_pronunciation_patterns(self, phonetic_map: Dict[str, Dict], sentences: List[Dict]) -> List[str]:
        """Identificar padrões de pronúncia nas sentences."""
        
        patterns = []
        
        # Analisar padrões de stress
        stress_patterns = []
        for sentence in sentences:
            vocabulary_used = sentence.get("vocabulary_used", [])
            for word in vocabulary_used:
                if word.lower() in phonetic_map:
                    phoneme = phonetic_map[word.lower()]["phoneme"]
                    if "ˈ" in phoneme:  # Primary stress
                        stress_patterns.append("primary_stress")
                    if "ˌ" in phoneme:  # Secondary stress
                        stress_patterns.append("secondary_stress")
        
        if stress_patterns:
            patterns.append(f"Stress patterns: {len(set(stress_patterns))} types identified")
        
        # Analisar sons específicos
        difficult_sounds = ["θ", "ð", "ŋ", "ʃ", "ʒ", "æ", "ʌ", "ɜː"]
        sounds_present = []
        
        for phonetic_data in phonetic_map.values():
            phoneme = phonetic_data["phoneme"]
            for sound in difficult_sounds:
                if sound in phoneme:
                    sounds_present.append(sound)
        
        if sounds_present:
            patterns.append(f"Challenging sounds: {len(set(sounds_present))} types present")
        
        return patterns
    
    def _extract_sentences_from_text(self, text: str) -> Dict[str, Any]:
        """Extrair sentences de texto quando JSON parsing falha."""
        
        # Dividir texto em sentences simples
        sentences = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) > 10 and ('.' in line or '!' in line or '?' in line):
                # Limpar marcadores
                clean_line = line.lstrip('123456789.-•').strip()
                if clean_line:
                    sentences.append(clean_line)
        
        # Se não encontrou sentences estruturadas, dividir por pontos
        if not sentences:
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 10]
        
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
            "vocabulary_coverage": 0.7,
            "contextual_coherence": 0.6,
            "progression_appropriateness": 0.7
        }
    
    def _generate_fallback_sentences(self) -> Dict[str, Any]:
        """Gerar sentences de fallback em caso de erro."""
        
        fallback_sentences = [
            {
                "text": "This is an example sentence using vocabulary words.",
                "vocabulary_used": ["example