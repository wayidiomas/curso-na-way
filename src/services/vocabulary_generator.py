# src/services/vocabulary_generator.py
"""
Serviço de geração de vocabulário com RAG e análise de imagens.
Implementação completa do PROMPT 6 do IVO V2 Guide.
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

from src.core.unit_models import (
    VocabularyItem, VocabularySection, VocabularyGenerationRequest,
    VocabularyGenerationResponse
)
from src.core.enums import CEFRLevel, LanguageVariant, UnitType
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


class VocabularyGeneratorService:
    """Serviço principal para geração de vocabulário contextual."""
    
    def __init__(self):
        """Inicializar serviço com configurações."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.6,  # Criatividade moderada para vocabulário
            max_tokens=2048,
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache simples em memória (substituindo Redis)
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 100
        
        logger.info("✅ VocabularyGeneratorService inicializado")
    
    async def generate_vocabulary_for_unit(
        self, 
        generation_params: Dict[str, Any]
    ) -> VocabularySection:
        """
        Gerar vocabulário para uma unidade usando RAG e análise de imagens.
        
        Args:
            generation_params: Parâmetros com contexto da unidade, RAG e imagens
            
        Returns:
            VocabularySection completa com itens validados
        """
        try:
            start_time = time.time()
            
            # Extrair parâmetros
            unit_data = generation_params.get("unit_data", {})
            hierarchy_context = generation_params.get("hierarchy_context", {})
            rag_context = generation_params.get("rag_context", {})
            images_analysis = generation_params.get("images_analysis", {})
            target_count = generation_params.get("target_vocabulary_count", 25)
            
            logger.info(f"🔤 Gerando {target_count} palavras de vocabulário para unidade")
            
            # 1. Construir contexto enriquecido
            enriched_context = await self._build_enriched_context(
                unit_data, hierarchy_context, rag_context, images_analysis
            )
            
            # 2. Gerar prompt contextualizado
            vocabulary_prompt = await self._build_vocabulary_prompt(
                enriched_context, target_count
            )
            
            # 3. Gerar vocabulário via LLM
            raw_vocabulary = await self._generate_vocabulary_llm(vocabulary_prompt)
            
            # 4. Processar e validar vocabulário
            validated_items = await self._process_and_validate_vocabulary(
                raw_vocabulary, enriched_context
            )
            
            # 5. Aplicar RAG para evitar repetições
            filtered_items = await self._apply_rag_filtering(
                validated_items, rag_context
            )
            
            # 6. Enriquecer com fonemas IPA
            enriched_items = await self._enrich_with_phonemes(
                filtered_items, unit_data.get("language_variant", "american_english")
            )
            
            # 7. Calcular métricas de qualidade
            quality_metrics = await self._calculate_quality_metrics(
                enriched_items, enriched_context, rag_context
            )
            
            # 8. Construir resposta final
            vocabulary_section = VocabularySection(
                items=enriched_items[:target_count],  # Limitar ao número desejado
                total_count=len(enriched_items[:target_count]),
                context_relevance=quality_metrics.get("context_relevance", 0.8),
                new_words_count=quality_metrics.get("new_words_count", len(enriched_items)),
                reinforcement_words_count=quality_metrics.get("reinforcement_count", 0),
                rag_context_used=rag_context,
                progression_level=rag_context.get("progression_level", "intermediate"),
                phoneme_coverage=quality_metrics.get("phoneme_coverage", {}),
                pronunciation_variants=[unit_data.get("language_variant", "american_english")],
                phonetic_complexity=self._determine_phonetic_complexity(enriched_items),
                generated_at=datetime.now()
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Vocabulário gerado: {len(enriched_items)} palavras em {generation_time:.2f}s"
            )
            
            return vocabulary_section
            
        except Exception as e:
            logger.error(f"❌ Erro na geração de vocabulário: {str(e)}")
            raise
    
    async def _build_enriched_context(
        self,
        unit_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any],
        images_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto enriquecido para geração."""
        
        # Extrair vocabulário das imagens se disponível
        image_vocabulary = []
        if images_analysis.get("success") and images_analysis.get("consolidated_vocabulary"):
            vocab_data = images_analysis["consolidated_vocabulary"].get("vocabulary", [])
            image_vocabulary = [item.get("word", "") for item in vocab_data if item.get("word")]
        
        # Contexto base da unidade
        base_context = unit_data.get("context", "")
        unit_title = unit_data.get("title", "")
        
        # Contexto da hierarquia
        course_name = hierarchy_context.get("course_name", "")
        book_name = hierarchy_context.get("book_name", "")
        sequence_order = hierarchy_context.get("sequence_order", 1)
        
        # Análise de progressão
        taught_vocabulary = rag_context.get("taught_vocabulary", [])
        progression_level = rag_context.get("progression_level", "intermediate")
        
        # Temas contextuais das imagens
        image_themes = []
        if images_analysis.get("success"):
            for analysis in images_analysis.get("individual_analyses", []):
                if "structured_data" in analysis.get("analysis", {}):
                    themes = analysis["analysis"]["structured_data"].get("contextual_themes", [])
                    image_themes.extend(themes)
        
        enriched_context = {
            "unit_context": {
                "title": unit_title,
                "context": base_context,
                "cefr_level": unit_data.get("cefr_level", "A2"),
                "language_variant": unit_data.get("language_variant", "american_english"),
                "unit_type": unit_data.get("unit_type", "lexical_unit")
            },
            "hierarchy_context": {
                "course_name": course_name,
                "book_name": book_name,
                "sequence_order": sequence_order,
                "target_level": hierarchy_context.get("target_level", unit_data.get("cefr_level"))
            },
            "rag_context": {
                "taught_vocabulary": taught_vocabulary[:20],  # Últimas 20 para contexto
                "progression_level": progression_level,
                "vocabulary_density": rag_context.get("vocabulary_density", 0),
                "words_to_avoid": taught_vocabulary,
                "reinforcement_candidates": self._select_reinforcement_words(taught_vocabulary)
            },
            "images_context": {
                "vocabulary_suggestions": image_vocabulary[:15],  # Top 15 das imagens
                "themes": list(set(image_themes))[:10],  # Top 10 temas únicos
                "has_images": bool(image_vocabulary),
                "images_analyzed": len(images_analysis.get("individual_analyses", []))
            },
            "generation_preferences": {
                "target_count": 25,
                "allow_reinforcement": True,
                "focus_on_images": bool(image_vocabulary),
                "progression_appropriate": True
            }
        }
        
        return enriched_context
    
    async def _build_vocabulary_prompt(
        self, 
        enriched_context: Dict[str, Any], 
        target_count: int
    ) -> List[Any]:
        """Construir prompt contextualizado para geração de vocabulário."""
        
        unit_ctx = enriched_context["unit_context"]
        hierarchy_ctx = enriched_context["hierarchy_context"]
        rag_ctx = enriched_context["rag_context"]
        images_ctx = enriched_context["images_context"]
        
        # Sistema de prompts baseado no nível CEFR
        cefr_guidelines = {
            "A1": "Focus on basic, high-frequency vocabulary. Use simple, everyday words that students encounter daily.",
            "A2": "Include practical vocabulary for common situations. Words should be useful for basic communication.",
            "B1": "Introduce more varied vocabulary including some academic and professional terms.",
            "B2": "Include complex vocabulary, collocations, and nuanced meanings.",
            "C1": "Advanced vocabulary with sophisticated expressions and academic language.",
            "C2": "Native-level vocabulary including idioms, specialized terms, and subtle distinctions."
        }
        
        cefr_level = unit_ctx["cefr_level"]
        cefr_guideline = cefr_guidelines.get(cefr_level, cefr_guidelines["A2"])
        
        system_prompt = f"""You are an expert English vocabulary teacher creating contextualized vocabulary for {cefr_level} level students.

EDUCATIONAL CONTEXT:
- Course: {hierarchy_ctx['course_name']}
- Book: {hierarchy_ctx['book_name']}
- Unit: {unit_ctx['title']}
- Sequence: Unit {hierarchy_ctx['sequence_order']} of the book
- Context: {unit_ctx['context']}
- Level: {cefr_level}
- Language Variant: {unit_ctx['language_variant']}
- Unit Type: {unit_ctx['unit_type']}

CEFR GUIDELINES FOR {cefr_level}: {cefr_guideline}

RAG CONTEXT (Important for coherence):
- Words already taught: {', '.join(rag_ctx['taught_vocabulary'])}
- Progression level: {rag_ctx['progression_level']}
- Reinforcement candidates: {', '.join(rag_ctx['reinforcement_candidates'][:5])}

IMAGES ANALYSIS:
{"- Image vocabulary suggestions: " + ', '.join(images_ctx['vocabulary_suggestions']) if images_ctx['vocabulary_suggestions'] else "- No images analyzed"}
{"- Image themes: " + ', '.join(images_ctx['themes']) if images_ctx['themes'] else ""}

GENERATION REQUIREMENTS:
1. Generate exactly {target_count} vocabulary items
2. Avoid repeating words from "already taught" list unless for reinforcement
3. Focus on words visible/suggested in images when available
4. Ensure vocabulary is appropriate for {cefr_level} level
5. Include 10-20% reinforcement words for review
6. Each word must include: word, IPA phoneme, Portuguese definition, contextual example
7. Prioritize practical, communicative vocabulary
8. Use {unit_ctx['language_variant']} pronunciations

OUTPUT FORMAT: Return valid JSON array with this exact structure:
[
  {{
    "word": "example",
    "phoneme": "/ɪɡˈzæmpəl/",
    "definition": "exemplo, modelo",
    "example": "This is a good example of modern architecture.",
    "word_class": "noun",
    "frequency_level": "high",
    "context_relevance": 0.9,
    "is_reinforcement": false
  }}
]"""

        human_prompt = f"""Generate {target_count} vocabulary items for the unit "{unit_ctx['title']}" in the context: "{unit_ctx['context']}"

Level: {cefr_level}
Type: {unit_ctx['unit_type']}

{"Image suggestions to prioritize: " + ', '.join(images_ctx['vocabulary_suggestions'][:10]) if images_ctx['vocabulary_suggestions'] else "No image context available."}

Remember:
- Avoid: {', '.join(rag_ctx['words_to_avoid'][:10])}
- Consider for reinforcement: {', '.join(rag_ctx['reinforcement_candidates'][:5])}
- Focus on practical, communicative vocabulary
- Ensure {unit_ctx['language_variant']} pronunciation
- Make examples relevant to the context

Generate the JSON array now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
    
    async def _generate_vocabulary_llm(self, prompt_messages: List[Any]) -> List[Dict[str, Any]]:
        """Gerar vocabulário usando LLM."""
        try:
            logger.info("🤖 Consultando LLM para geração de vocabulário...")
            
            # Usar cache se disponível
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
                
                vocabulary_list = json.loads(content)
                
                if not isinstance(vocabulary_list, list):
                    raise ValueError("Response não é uma lista")
                
                # Salvar no cache
                self._save_to_cache(cache_key, vocabulary_list)
                
                logger.info(f"✅ LLM retornou {len(vocabulary_list)} itens de vocabulário")
                return vocabulary_list
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao parsear JSON, tentando extração manual: {str(e)}")
                return self._extract_vocabulary_from_text(content)
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            # Retornar vocabulário de fallback
            return self._generate_fallback_vocabulary()
    
    async def _process_and_validate_vocabulary(
        self, 
        raw_vocabulary: List[Dict[str, Any]], 
        enriched_context: Dict[str, Any]
    ) -> List[VocabularyItem]:
        """Processar e validar itens de vocabulário."""
        validated_items = []
        
        unit_ctx = enriched_context["unit_context"]
        
        for i, raw_item in enumerate(raw_vocabulary):
            try:
                # Aplicar valores padrão se necessário
                processed_item = {
                    "word": raw_item.get("word", f"word_{i}").lower().strip(),
                    "phoneme": raw_item.get("phoneme", f"/word_{i}/"),
                    "definition": raw_item.get("definition", "definição não disponível"),
                    "example": raw_item.get("example", f"Example with {raw_item.get('word', 'word')}."),
                    "word_class": raw_item.get("word_class", "noun"),
                    "frequency_level": raw_item.get("frequency_level", "medium"),
                    "context_relevance": raw_item.get("context_relevance", 0.7),
                    "is_reinforcement": raw_item.get("is_reinforcement", False),
                    "ipa_variant": self._get_ipa_variant(unit_ctx["language_variant"]),
                    "syllable_count": self._estimate_syllable_count(raw_item.get("word", "")),
                }
                
                # Validar usando Pydantic
                vocabulary_item = VocabularyItem(**processed_item)
                validated_items.append(vocabulary_item)
                
            except ValidationError as e:
                logger.warning(f"⚠️ Item {i+1} inválido, pulando: {str(e)}")
                continue
            except Exception as e:
                logger.warning(f"⚠️ Erro ao processar item {i+1}: {str(e)}")
                continue
        
        logger.info(f"✅ {len(validated_items)} itens validados de {len(raw_vocabulary)} originais")
        return validated_items
    
    async def _apply_rag_filtering(
        self, 
        vocabulary_items: List[VocabularyItem], 
        rag_context: Dict[str, Any]
    ) -> List[VocabularyItem]:
        """Aplicar filtros RAG para evitar repetições e melhorar progressão."""
        
        taught_words = set(word.lower() for word in rag_context.get("taught_vocabulary", []))
        reinforcement_candidates = set(word.lower() for word in rag_context.get("reinforcement_candidates", []))
        
        filtered_items = []
        new_words_count = 0
        reinforcement_count = 0
        max_reinforcement = len(vocabulary_items) // 5  # Máximo 20% reforço
        
        # Primeiro, adicionar palavras novas
        for item in vocabulary_items:
            word_lower = item.word.lower()
            
            if word_lower not in taught_words:
                # Palavra nova - adicionar
                item.is_reinforcement = False
                filtered_items.append(item)
                new_words_count += 1
                
            elif (word_lower in reinforcement_candidates and 
                  reinforcement_count < max_reinforcement):
                # Palavra para reforço - adicionar com limite
                item.is_reinforcement = True
                filtered_items.append(item)
                reinforcement_count += 1
            
            # Parar se atingiu o número desejado
            if len(filtered_items) >= 30:  # Gerar um pouco mais para ter opções
                break
        
        logger.info(
            f"🎯 RAG filtering: {new_words_count} novas, {reinforcement_count} reforço"
        )
        
        return filtered_items
    
    async def _enrich_with_phonemes(
        self, 
        vocabulary_items: List[VocabularyItem], 
        language_variant: str
    ) -> List[VocabularyItem]:
        """Enriquecer itens com fonemas IPA mais precisos."""
        
        # Para MVP, vamos manter os fonemas que já vieram do LLM
        # Em implementação futura, podemos usar API de pronúncia ou dicionário
        
        for item in vocabulary_items:
            # Verificar se o fonema precisa de correção
            if not item.phoneme or item.phoneme == f"/placeholder_{item.word}/":
                # Gerar fonema básico baseado na palavra
                item.phoneme = self._generate_basic_phoneme(item.word, language_variant)
            
            # Definir variante IPA
            item.ipa_variant = self._get_ipa_variant(language_variant)
            
            # Estimar padrão de stress
            if not item.stress_pattern:
                item.stress_pattern = self._estimate_stress_pattern(item.phoneme)
        
        return vocabulary_items
    
    async def _calculate_quality_metrics(
        self, 
        vocabulary_items: List[VocabularyItem], 
        enriched_context: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcular métricas de qualidade do vocabulário gerado."""
        
        if not vocabulary_items:
            return {"context_relevance": 0.0, "new_words_count": 0, "reinforcement_count": 0}
        
        # Contagens básicas
        new_words = [item for item in vocabulary_items if not item.is_reinforcement]
        reinforcement_words = [item for item in vocabulary_items if item.is_reinforcement]
        
        # Relevância contextual média
        relevance_scores = [item.context_relevance for item in vocabulary_items if item.context_relevance]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.7
        
        # Cobertura de fonemas
        phonemes_used = set()
        for item in vocabulary_items:
            if item.phoneme:
                # Extrair fonemas individuais (simplificado)
                clean_phoneme = item.phoneme.strip('/[]')
                phonemes_used.update(clean_phoneme.replace(' ', ''))
        
        phoneme_coverage = {
            "total_unique_phonemes": len(phonemes_used),
            "coverage_score": min(len(phonemes_used) / 30, 1.0)  # 30 fonemas = 100%
        }
        
        # Distribuição por classe de palavra
        word_classes = {}
        for item in vocabulary_items:
            word_class = item.word_class
            word_classes[word_class] = word_classes.get(word_class, 0) + 1
        
        return {
            "context_relevance": avg_relevance,
            "new_words_count": len(new_words),
            "reinforcement_count": len(reinforcement_words),
            "phoneme_coverage": phoneme_coverage,
            "word_class_distribution": word_classes,
            "quality_score": (avg_relevance + phoneme_coverage["coverage_score"]) / 2
        }
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _select_reinforcement_words(self, taught_vocabulary: List[str]) -> List[str]:
        """Selecionar palavras candidatas para reforço."""
        # Para MVP, selecionar últimas 10 palavras ensinadas
        return taught_vocabulary[-10:] if taught_vocabulary else []
    
    def _get_ipa_variant(self, language_variant: str) -> str:
        """Mapear variante de idioma para variante IPA."""
        mapping = {
            "american_english": "general_american",
            "british_english": "received_pronunciation",
            "australian_english": "australian_english",
            "canadian_english": "canadian_english"
        }
        return mapping.get(language_variant, "general_american")
    
    def _estimate_syllable_count(self, word: str) -> int:
        """Estimar número de sílabas (algoritmo simples)."""
        if not word:
            return 1
            
        word = word.lower()
        vowels = "aeiouy"
        syllables = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllables += 1
            prev_was_vowel = is_vowel
        
        # Ajustes
        if word.endswith('e'):
            syllables -= 1
        if syllables == 0:
            syllables = 1
            
        return syllables
    
    def _generate_basic_phoneme(self, word: str, language_variant: str) -> str:
        """Gerar fonema básico para palavra (fallback)."""
        # Implementação muito básica - em produção usar API de pronúncia
        return f"/{word.replace('e', 'ə').replace('a', 'æ')}/"
    
    def _estimate_stress_pattern(self, phoneme: str) -> str:
        """Estimar padrão de stress do fonema."""
        if 'ˈ' in phoneme:
            return "primary_first"
        elif 'ˌ' in phoneme:
            return "secondary_first"
        else:
            return "unstressed"
    
    def _determine_phonetic_complexity(self, vocabulary_items: List[VocabularyItem]) -> str:
        """Determinar complexidade fonética geral."""
        if not vocabulary_items:
            return "medium"
            
        avg_syllables = sum(item.syllable_count or 1 for item in vocabulary_items) / len(vocabulary_items)
        
        if avg_syllables <= 1.5:
            return "simple"
        elif avg_syllables <= 2.5:
            return "medium"
        elif avg_syllables <= 3.5:
            return "complex"
        else:
            return "very_complex"
    
    def _extract_vocabulary_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extrair vocabulário de texto quando JSON parsing falha."""
        vocabulary = []
        lines = text.split('\n')
        
        current_item = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Tentar extrair informações básicas
            if 'word:' in line.lower() or '"word"' in line:
                if current_item:
                    vocabulary.append(current_item)
                    current_item = {}
                word = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['word'] = word
            elif 'phoneme:' in line.lower() or '"phoneme"' in line:
                phoneme = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['phoneme'] = phoneme
            elif 'definition:' in line.lower() or '"definition"' in line:
                definition = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['definition'] = definition
            elif 'example:' in line.lower() or '"example"' in line:
                example = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['example'] = example
        
        if current_item:
            vocabulary.append(current_item)
        
        # Preencher campos faltantes
        for item in vocabulary:
            item.setdefault('word_class', 'noun')
            item.setdefault('frequency_level', 'medium')
            item.setdefault('context_relevance', 0.7)
            item.setdefault('is_reinforcement', False)
        
        return vocabulary
    
    def _generate_fallback_vocabulary(self) -> List[Dict[str, Any]]:
        """Gerar vocabulário de fallback em caso de erro."""
        fallback_words = [
            {
                "word": "example",
                "phoneme": "/ɪɡˈzæmpəl/",
                "definition": "exemplo",
                "example": "This is an example sentence.",
                "word_class": "noun",
                "frequency_level": "high",
                "context_relevance": 0.8,
                "is_reinforcement": False
            },
            {
                "word": "important",
                "phoneme": "/ɪmˈpɔrtənt/",
                "definition": "importante",
                "example": "This is very important.",
                "word_class": "adjective",
                "frequency_level": "high",
                "context_relevance": 0.7,
                "is_reinforcement": False
            }
        ]
        
        logger.warning("⚠️ Usando vocabulário de fallback")
        return fallback_words
    
    def _generate_cache_key(self, prompt_messages: List[Any]) -> str:
        """Gerar chave para cache baseada no prompt."""
        content = "".join([msg.content for msg in prompt_messages])
        return f"vocab_{hash(content)}"
    
    def _get_from_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Obter item do cache em memória."""
        current_time = time.time()
        
        # Verificar se existe e não expirou (1 hora = 3600s)
        if (key in self._memory_cache and 
            key in self._cache_expiry and 
            current_time - self._cache_expiry[key] < 3600):
            return self._memory_cache[key]
        
        # Remover se expirado
        if key in self._memory_cache:
            del self._memory_cache[key]
        if key in self._cache_expiry:
            del self._cache_expiry[key]
        
        return None
    
    def _save_to_cache(self, key: str, value: List[Dict[str, Any]]) -> None:
        """Salvar item no cache em memória."""
        # Limpar cache se muito grande
        if len(self._memory_cache) >= self._max_cache_size:
            # Remover item mais antigo
            oldest_key = min(self._cache_expiry.keys(), key=self._cache_expiry.get)
            del self._memory_cache[oldest_key]
            del self._cache_expiry[oldest_key]
        
        self._memory_cache[key] = value
        self._cache_expiry[key] = time.time()