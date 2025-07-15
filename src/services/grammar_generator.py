# src/services/grammar_generator.py
"""
Serviço de geração de estratégias GRAMMAR com análise de interferência L1→L2.
Implementação das 2 estratégias GRAMMAR do IVO V2 Guide.
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

from src.core.unit_models import GrammarContent
from src.core.enums import CEFRLevel, LanguageVariant, UnitType, GrammarStrategy
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


class GrammarGeneratorService:
    """Serviço principal para geração de estratégias GRAMMAR."""
    
    def __init__(self):
        """Inicializar serviço com configurações."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.6,  # Criatividade moderada para estratégias
            max_tokens=2048,
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache simples em memória
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 50
        
        # Base de conhecimento de interferências L1→L2
        self.l1_interference_patterns = self._load_l1_interference_patterns()
        
        logger.info("✅ GrammarGeneratorService inicializado")
    
    def _load_l1_interference_patterns(self) -> Dict[str, Any]:
        """Carregar padrões de interferência português→inglês."""
        return {
            "article_interference": {
                "errors": [
                    {"pt": "A pasta é boa", "en_wrong": "The pasta is good", "en_correct": "Pasta is good"},
                    {"pt": "O leite está caro", "en_wrong": "The milk is expensive", "en_correct": "Milk is expensive"}
                ],
                "explanation": "Português requires articles with generic nouns, English often doesn't"
            },
            "age_structure": {
                "errors": [
                    {"pt": "Eu tenho 25 anos", "en_wrong": "I have 25 years", "en_correct": "I am 25 years old"},
                    {"pt": "Ela tem 30", "en_wrong": "She has 30", "en_correct": "She is 30 years old"}
                ],
                "explanation": "Portuguese uses 'ter' (have) for age, English uses 'be'"
            },
            "countable_uncountable": {
                "errors": [
                    {"pt": "Leites, pães", "en_wrong": "Milks, breads", "en_correct": "Milk, bread"},
                    {"pt": "Informações", "en_wrong": "Informations", "en_correct": "Information"}
                ],
                "explanation": "Portuguese pluralizes more nouns than English"
            },
            "question_formation": {
                "errors": [
                    {"pt": "O que você está fazendo?", "en_wrong": "What you are doing?", "en_correct": "What are you doing?"},
                    {"pt": "Onde você mora?", "en_wrong": "Where you live?", "en_correct": "Where do you live?"}
                ],
                "explanation": "Portuguese doesn't use auxiliary 'do/does' or invert word order in questions"
            },
            "auxiliary_verbs": {
                "errors": [
                    {"pt": "Você gosta?", "en_wrong": "You like?", "en_correct": "Do you like?"},
                    {"pt": "Ele não fala inglês", "en_wrong": "He no speak English", "en_correct": "He doesn't speak English"}
                ],
                "explanation": "Portuguese doesn't require auxiliary verbs for questions and negatives"
            },
            "false_friends": {
                "errors": [
                    {"pt": "biblioteca", "en_wrong": "library = livraria", "en_correct": "library ≠ livraria (bookstore)"},
                    {"pt": "realizar", "en_wrong": "realize = perceber", "en_correct": "realize ≠ realizar (accomplish)"}
                ],
                "explanation": "Words that look similar but have different meanings"
            }
        }
    
    async def generate_grammar_for_unit(
        self, 
        grammar_params: Dict[str, Any]
    ) -> GrammarContent:
        """
        Gerar estratégias GRAMMAR para uma unidade usando RAG e análise L1.
        
        Args:
            grammar_params: Parâmetros com contexto da unidade, RAG e hierarquia
            
        Returns:
            GrammarContent completo com estratégia selecionada
        """
        try:
            start_time = time.time()
            
            # Extrair parâmetros
            unit_data = grammar_params.get("unit_data", {})
            content_data = grammar_params.get("content_data", {})
            hierarchy_context = grammar_params.get("hierarchy_context", {})
            rag_context = grammar_params.get("rag_context", {})
            
            logger.info(f"📚 Gerando estratégias GRAMMAR para unidade gramatical")
            
            # 1. Analisar conteúdo para detectar necessidade de estratégia
            grammar_analysis = await self._analyze_grammar_needs(
                unit_data, content_data, rag_context
            )
            
            # 2. Selecionar estratégia GRAMMAR adequada
            selected_strategy = await self._select_grammar_strategy(
                grammar_analysis, rag_context
            )
            
            # 3. Construir contexto enriquecido
            enriched_context = await self._build_grammar_context(
                unit_data, content_data, hierarchy_context, rag_context, selected_strategy
            )
            
            # 4. Gerar prompt contextualizado
            grammar_prompt = await self._build_grammar_prompt(
                enriched_context, selected_strategy
            )
            
            # 5. Gerar estratégia via LLM
            raw_grammar = await self._generate_grammar_llm(grammar_prompt)
            
            # 6. Processar e enriquecer conteúdo
            processed_grammar = await self._process_grammar_content(
                raw_grammar, selected_strategy, enriched_context
            )
            
            # 7. Aplicar análise L1→L2 específica
            enriched_grammar = await self._apply_l1_interference_analysis(
                processed_grammar, unit_data, content_data
            )
            
            # 8. Construir resposta final
            grammar_content = GrammarContent(
                strategy=GrammarStrategy(selected_strategy),
                grammar_point=enriched_grammar.get("grammar_point", ""),
                systematic_explanation=enriched_grammar.get("systematic_explanation", ""),
                usage_rules=enriched_grammar.get("usage_rules", []),
                examples=enriched_grammar.get("examples", []),
                l1_interference_notes=enriched_grammar.get("l1_interference_notes", []),
                common_mistakes=enriched_grammar.get("common_mistakes", []),
                vocabulary_integration=enriched_grammar.get("vocabulary_integration", []),
                previous_grammar_connections=enriched_grammar.get("previous_grammar_connections", []),
                selection_rationale=enriched_grammar.get("selection_rationale", "")
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Estratégia GRAMMAR '{selected_strategy}' gerada em {generation_time:.2f}s"
            )
            
            return grammar_content
            
        except Exception as e:
            logger.error(f"❌ Erro na geração de estratégias GRAMMAR: {str(e)}")
            raise
    
    async def _analyze_grammar_needs(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analisar necessidades gramaticais da unidade."""
        
        # Extrair informações do conteúdo
        vocabulary_items = content_data.get("vocabulary", {}).get("items", [])
        sentences = content_data.get("sentences", {}).get("sentences", [])
        
        # Analisar vocabulário em busca de padrões gramaticais
        grammar_patterns = []
        l1_interference_risk = []
        
        for item in vocabulary_items:
            word = item.get("word", "").lower()
            word_class = item.get("word_class", "")
            
            # Detectar palavras que podem causar interferência
            if word in ["have", "be", "do", "can", "will", "must"]:
                l1_interference_risk.append("auxiliary_verbs")
            if word in ["library", "parents", "realize", "attend"]:
                l1_interference_risk.append("false_friends")
            if word_class == "verb":
                grammar_patterns.append("verb_patterns")
            if word_class == "noun":
                grammar_patterns.append("noun_usage")
        
        # Analisar sentences em busca de estruturas gramaticais
        for sentence in sentences:
            text = sentence.get("text", "").lower()
            
            if any(word in text for word in ["do", "does", "did"]):
                grammar_patterns.append("auxiliary_verbs")
            if any(word in text for word in ["the", "a", "