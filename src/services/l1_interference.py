# src/services/l1_interference.py
"""
Serviço especializado em análise e prevenção de interferência L1→L2 (português→inglês).
Implementação das estratégias GRAMMAR 2 do IVO V2 Guide usando IA para todas as verificações.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from src.core.unit_models import (
    GrammarContent, VocabularyItem, L1InterferencePattern,
    CommonMistake, ContrastiveExample
)
from src.core.enums import CEFRLevel, LanguageVariant
from config.models import get_openai_config

logger = logging.getLogger(__name__)


class L1InterferenceAnalyzer:
    """Analisador de interferência L1 (português) no aprendizado de inglês usando IA."""
    
    def __init__(self):
        """Inicializar com configurações de IA."""
        self.openai_config = get_openai_config()
        
        # LLM para análise de interferência
        self.llm = ChatOpenAI(
            model=self.openai_config.get("model", "gpt-4o-mini"),
            temperature=0.3,  # Baixa criatividade para análise técnica
            max_tokens=3072,
            api_key=self.openai_config["api_key"]
        )
        
        # Cache de análises recentes
        self._analysis_cache: Dict[str, Any] = {}
        self._max_cache_size = 50
        
        logger.info("✅ L1InterferenceAnalyzer inicializado com IA")
    
    async def analyze_content_for_l1_interference(
        self,
        grammar_point: str,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str,
        unit_context: str,
        language_variant: str = "american_english"
    ) -> Dict[str, Any]:
        """
        Analisar conteúdo da unidade para identificar interferências L1 usando IA.
        
        Args:
            grammar_point: Ponto gramatical principal da unidade
            vocabulary_items: Lista de vocabulário da unidade
            cefr_level: Nível CEFR da unidade
            unit_context: Contexto temático da unidade
            language_variant: Variante do inglês (american/british)
            
        Returns:
            Dict com análise completa de interferências L1→L2
        """
        try:
            logger.info(f"🔍 Analisando interferência L1→L2 via IA: {grammar_point}")
            
            # Cache key para evitar reprocessamento
            cache_key = self._generate_cache_key(
                grammar_point, vocabulary_items, cefr_level, unit_context
            )
            
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                logger.info("📦 Usando análise L1 do cache")
                return cached_result
            
            # 1. Análise principal de interferência via IA
            main_analysis = await self._analyze_main_interference_patterns(
                grammar_point, vocabulary_items, cefr_level, unit_context, language_variant
            )
            
            # 2. Análise específica de vocabulário via IA
            vocabulary_analysis = await self._analyze_vocabulary_interference_ai(
                vocabulary_items, cefr_level, unit_context, language_variant
            )
            
            # 3. Análise de pronúncia via IA
            pronunciation_analysis = await self._analyze_pronunciation_interference_ai(
                vocabulary_items, cefr_level, language_variant
            )
            
            # 4. Geração de exercícios preventivos via IA
            preventive_exercises = await self._generate_preventive_exercises_ai(
                main_analysis, vocabulary_analysis, pronunciation_analysis, cefr_level
            )
            
            # 5. Recomendações pedagógicas via IA
            teaching_recommendations = await self._generate_teaching_recommendations_ai(
                grammar_point, main_analysis, cefr_level, unit_context
            )
            
            # 6. Compilar análise final
            l1_analysis = {
                "grammar_point": grammar_point,
                "cefr_level": cefr_level,
                "unit_context": unit_context,
                "language_variant": language_variant,
                "main_interference_patterns": main_analysis,
                "vocabulary_interference": vocabulary_analysis,
                "pronunciation_interference": pronunciation_analysis,
                "preventive_exercises": preventive_exercises,
                "teaching_recommendations": teaching_recommendations,
                "common_mistakes": main_analysis.get("predicted_common_mistakes", []),
                "contrastive_examples": main_analysis.get("contrastive_examples", []),
                "prevention_strategies": main_analysis.get("prevention_strategies", []),
                "difficulty_assessment": await self._assess_difficulty_level_ai(
                    grammar_point, vocabulary_items, cefr_level
                ),
                "brazilian_specific_focus": True,
                "analysis_timestamp": datetime.now().isoformat(),
                "ai_confidence_score": main_analysis.get("confidence_score", 0.85)
            }
            
            # Salvar no cache
            self._save_to_cache(cache_key, l1_analysis)
            
            logger.info(f"✅ Análise L1→L2 concluída via IA com {len(main_analysis.get('interference_patterns', []))} padrões")
            
            return l1_analysis
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de interferência L1 via IA: {str(e)}")
            raise
    
    async def _analyze_main_interference_patterns(
        self,
        grammar_point: str,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str,
        unit_context: str,
        language_variant: str
    ) -> Dict[str, Any]:
        """Análise principal de padrões de interferência via IA."""
        
        vocabulary_words = [item.word for item in vocabulary_items]
        vocabulary_examples = [f"{item.word}: {item.example}" for item in vocabulary_items[:8]]
        
        system_prompt = """You are a world-class expert in Second Language Acquisition, specializing in L1 interference analysis for Brazilian Portuguese speakers learning English.

Your expertise includes:
- Contrastive analysis between Portuguese and English
- Common error patterns of Brazilian learners
- Pedagogical strategies for interference prevention
- CEFR-appropriate difficulty assessment

Analyze content for specific L1 (Portuguese) → L2 (English) interference patterns that Brazilian learners are likely to encounter."""

        human_prompt = f"""Analyze this English lesson content for L1 interference from Brazilian Portuguese:

LESSON DETAILS:
- Grammar Point: {grammar_point}
- CEFR Level: {cefr_level}
- Context Theme: {unit_context}
- English Variant: {language_variant}

VOCABULARY IN LESSON:
{chr(10).join(vocabulary_examples)}

ANALYSIS REQUIRED:
Identify specific Portuguese→English interference patterns that Brazilian students will likely encounter with this content.

For each interference pattern, provide:
1. The Portuguese linguistic structure/habit
2. How it incorrectly transfers to English
3. The correct English form
4. Clear explanation of the difference
5. Practical prevention technique

FOCUS AREAS TO ANALYZE:
- Grammatical structure differences
- Word order patterns
- Article usage patterns
- Verb construction differences
- Preposition usage
- False cognates/friends
- Pronunciation transfer
- Semantic differences

Return detailed analysis in JSON format:
{{
  "interference_patterns": [
    {{
      "category": "grammatical_structure",
      "portuguese_pattern": "specific Portuguese structure",
      "incorrect_english_transfer": "how Brazilians incorrectly say it",
      "correct_english": "proper English form",
      "explanation": "why this happens and how they differ",
      "prevention_technique": "specific teaching strategy",
      "example_context": "example using lesson vocabulary",
      "difficulty_level": "how hard this is for {cefr_level}",
      "frequency": "how often this error occurs"
    }}
  ],
  "predicted_common_mistakes": [
    {{
      "mistake": "specific error students will make",
      "correction": "how to fix it",
      "reason": "why Brazilians make this mistake"
    }}
  ],
  "contrastive_examples": [
    {{
      "portuguese": "Portuguese version",
      "english_wrong": "literal translation (wrong)",
      "english_correct": "proper English",
      "teaching_point": "what to emphasize"
    }}
  ],
  "prevention_strategies": [
    "specific strategy 1 for this content",
    "specific strategy 2 for this content"
  ],
  "confidence_score": 0.95
}}

Be specific to the actual content provided. Avoid generic advice."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            # Parse resposta JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            analysis = json.loads(content)
            
            logger.info(f"✅ Análise principal L1 via IA: {len(analysis.get('interference_patterns', []))} padrões")
            return analysis
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Erro ao parsear JSON da análise principal L1: {str(e)}")
            return await self._fallback_main_analysis(grammar_point, vocabulary_words, cefr_level)
        except Exception as e:
            logger.error(f"❌ Erro na análise principal L1 via IA: {str(e)}")
            return await self._fallback_main_analysis(grammar_point, vocabulary_words, cefr_level)
    
    async def _analyze_vocabulary_interference_ai(
        self,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str,
        unit_context: str,
        language_variant: str
    ) -> Dict[str, Any]:
        """Análise específica de interferência de vocabulário via IA."""
        
        vocabulary_details = []
        for item in vocabulary_items:
            vocab_detail = f"Word: {item.word}"
            if item.definition:
                vocab_detail += f" | Portuguese: {item.definition}"
            if item.example:
                vocab_detail += f" | Example: {item.example}"
            if item.word_class:
                vocab_detail += f" | Class: {item.word_class}"
            vocabulary_details.append(vocab_detail)
        
        system_prompt = """You are an expert in lexical interference analysis for Brazilian Portuguese speakers learning English.

Analyze vocabulary for specific L1 interference issues including:
- False friends/cognates
- Semantic differences
- Usage pattern differences
- Collocation differences
- Register differences
- Cultural concept differences"""

        human_prompt = f"""Analyze this vocabulary list for L1 interference from Brazilian Portuguese:

VOCABULARY TO ANALYZE:
{chr(10).join(vocabulary_details)}

CONTEXT: {unit_context}
LEVEL: {cefr_level}
VARIANT: {language_variant}

For each word that has potential L1 interference, identify:
1. Type of interference (false friend, usage difference, etc.)
2. How Brazilians might misuse it
3. Correct usage in English
4. Prevention/teaching strategy

Return analysis in JSON:
{{
  "vocabulary_interference_items": [
    {{
      "word": "vocabulary word",
      "interference_type": "false_friend|usage_difference|semantic_difference|collocation_issue",
      "portuguese_confusion": "what Portuguese speakers think it means",
      "actual_english_meaning": "correct English meaning/usage",
      "common_mistake": "typical error Brazilians make",
      "correct_usage": "proper way to use it",
      "teaching_strategy": "how to prevent this mistake",
      "examples": {{
        "wrong": "example of wrong usage",
        "correct": "example of correct usage"
      }},
      "severity": "high|medium|low"
    }}
  ],
  "overall_interference_level": "assessment of overall vocabulary interference risk",
  "teaching_priority": ["word1", "word2", "word3"],
  "prevention_focus": "main area to focus prevention efforts"
}}

Focus only on words that actually have interference potential."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            analysis = json.loads(content)
            
            logger.info(f"✅ Análise vocabulário L1 via IA: {len(analysis.get('vocabulary_interference_items', []))} itens")
            return analysis
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na análise de vocabulário L1 via IA: {str(e)}")
            return {
                "vocabulary_interference_items": [],
                "overall_interference_level": "medium",
                "teaching_priority": [item.word for item in vocabulary_items[:3]],
                "prevention_focus": "general_awareness"
            }
    
    async def _analyze_pronunciation_interference_ai(
        self,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str,
        language_variant: str
    ) -> Dict[str, Any]:
        """Análise de interferência de pronúncia via IA."""
        
        pronunciation_data = []
        for item in vocabulary_items:
            pronunciation_info = f"Word: {item.word}"
            if item.phoneme:
                pronunciation_info += f" | IPA: {item.phoneme}"
            if item.syllable_count:
                pronunciation_info += f" | Syllables: {item.syllable_count}"
            pronunciation_data.append(pronunciation_info)
        
        system_prompt = """You are an expert phonetician specializing in pronunciation interference from Brazilian Portuguese to English.

Analyze pronunciation challenges that Brazilian Portuguese speakers will face with this vocabulary, considering:
- Portuguese phonological system vs English
- Common pronunciation errors of Brazilians
- Specific sounds that don't exist in Portuguese
- Stress pattern differences
- Syllable structure differences
- Connected speech challenges"""

        human_prompt = f"""Analyze pronunciation interference for Brazilian Portuguese speakers:

VOCABULARY PRONUNCIATION DATA:
{chr(10).join(pronunciation_data)}

STUDENT LEVEL: {cefr_level}
ENGLISH VARIANT: {language_variant}

Identify specific pronunciation challenges Brazilians will face with these words:

1. Individual sound challenges (sounds not in Portuguese)
2. Stress pattern difficulties
3. Syllable structure issues
4. Connected speech problems
5. Typical Brazilian pronunciation errors for each challenging word

Return detailed analysis in JSON:
{{
  "pronunciation_challenges": [
    {{
      "word": "vocabulary word",
      "ipa": "IPA transcription",
      "challenge_type": "sound_substitution|stress_pattern|syllable_structure|connected_speech",
      "specific_difficulty": "exact pronunciation challenge for Brazilians",
      "typical_brazilian_error": "how Brazilians typically mispronounce it",
      "correct_pronunciation": "correct way to pronounce",
      "teaching_technique": "specific technique to teach correct pronunciation",
      "practice_exercises": ["drill 1", "drill 2"],
      "difficulty_level": "easy|moderate|hard|very_hard"
    }}
  ],
  "overall_pronunciation_assessment": {{
    "difficulty_level": "assessment for {cefr_level} Brazilian learners",
    "main_challenge_areas": ["area1", "area2"],
    "teaching_priorities": ["priority1", "priority2"]
  }},
  "systematic_issues": [
    {{
      "pattern": "systematic pronunciation pattern issue",
      "explanation": "why this is hard for Brazilians",
      "solution": "teaching approach"
    }}
  ]
}}

Focus on realistic, specific challenges Brazilian speakers face."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            analysis = json.loads(content)
            
            logger.info(f"✅ Análise pronúncia L1 via IA: {len(analysis.get('pronunciation_challenges', []))} desafios")
            return analysis
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na análise de pronúncia L1 via IA: {str(e)}")
            return {
                "pronunciation_challenges": [],
                "overall_pronunciation_assessment": {
                    "difficulty_level": "moderate",
                    "main_challenge_areas": ["consonant_clusters", "vowel_sounds"],
                    "teaching_priorities": ["clear_articulation", "stress_awareness"]
                },
                "systematic_issues": []
            }
    
    async def _generate_preventive_exercises_ai(
        self,
        main_analysis: Dict[str, Any],
        vocabulary_analysis: Dict[str, Any],
        pronunciation_analysis: Dict[str, Any],
        cefr_level: str
    ) -> List[Dict[str, Any]]:
        """Gerar exercícios preventivos via IA."""
        
        system_prompt = """You are an expert EFL curriculum designer specializing in L1 interference prevention exercises for Brazilian learners.

Create specific, practical exercises that prevent L1 interference based on the analysis provided. Exercises should be:
- Appropriate for the CEFR level
- Focused on the specific interference patterns identified
- Engaging and effective
- Easy for teachers to implement"""

        # Compilar dados da análise
        interference_summary = {
            "grammar_patterns": main_analysis.get("interference_patterns", []),
            "vocabulary_issues": vocabulary_analysis.get("vocabulary_interference_items", []),
            "pronunciation_challenges": pronunciation_analysis.get("pronunciation_challenges", [])
        }
        
        human_prompt = f"""Create preventive exercises for L1 interference based on this analysis:

INTERFERENCE ANALYSIS:
{json.dumps(interference_summary, indent=2)}

STUDENT LEVEL: {cefr_level}

Create 3-5 different exercise types that specifically target the interference patterns identified. Each exercise should:

1. Target a specific interference pattern
2. Be appropriate for {cefr_level} level
3. Include clear instructions
4. Have specific examples
5. Focus on prevention rather than just correction

Return exercises in JSON format:
{{
  "preventive_exercises": [
    {{
      "exercise_type": "contrastive_awareness|error_prevention|pronunciation_drill|usage_practice",
      "title": "Clear, engaging title",
      "target_interference": "specific L1 issue this addresses",
      "instructions": "clear instructions for students",
      "content": {{
        "items": [
          {{
            "prompt": "exercise item",
            "correct_answer": "correct response",
            "explanation": "why this is correct"
          }}
        ],
        "additional_notes": "any extra guidance"
      }},
      "teaching_tips": ["tip1 for teacher", "tip2 for teacher"],
      "estimated_time": "time in minutes",
      "skill_focus": ["grammar", "vocabulary", "pronunciation"],
      "difficulty": "appropriate for level"
    }}
  ],
  "implementation_sequence": "recommended order to use exercises",
  "assessment_criteria": "how to evaluate student progress"
}}

Make exercises specific to the actual interference patterns found, not generic."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            exercises_data = json.loads(content)
            
            logger.info(f"✅ Exercícios preventivos gerados via IA: {len(exercises_data.get('preventive_exercises', []))}")
            return exercises_data.get('preventive_exercises', [])
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na geração de exercícios preventivos via IA: {str(e)}")
            return self._create_fallback_exercises(cefr_level)
    
    async def _generate_teaching_recommendations_ai(
        self,
        grammar_point: str,
        main_analysis: Dict[str, Any],
        cefr_level: str,
        unit_context: str
    ) -> List[str]:
        """Gerar recomendações pedagógicas via IA."""
        
        system_prompt = """You are an experienced EFL teacher trainer specializing in teaching Brazilian students.

Provide specific, actionable teaching recommendations for preventing L1 interference based on the analysis provided."""

        human_prompt = f"""Based on this L1 interference analysis, provide specific teaching recommendations:

GRAMMAR POINT: {grammar_point}
STUDENT LEVEL: {cefr_level}
CONTEXT: {unit_context}

INTERFERENCE ANALYSIS:
{json.dumps(main_analysis, indent=2)}

Provide 5-8 specific, actionable teaching recommendations that help prevent the L1 interference patterns identified. Each recommendation should:

1. Be specific to the actual interference patterns found
2. Be practical for classroom implementation
3. Be appropriate for {cefr_level} level Brazilian students
4. Include concrete teaching techniques

Format as JSON array:
{{
  "teaching_recommendations": [
    "Specific recommendation 1 with concrete technique",
    "Specific recommendation 2 with concrete technique",
    ...
  ]
}}

Focus on prevention strategies, not just error correction."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            recommendations_data = json.loads(content)
            
            logger.info(f"✅ Recomendações pedagógicas geradas via IA: {len(recommendations_data.get('teaching_recommendations', []))}")
            return recommendations_data.get('teaching_recommendations', [])
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na geração de recomendações via IA: {str(e)}")
            return [
                f"Focus on contrastive explanation of {grammar_point} vs Portuguese equivalents",
                f"Use explicit error prevention techniques for {cefr_level} level",
                "Provide abundant practice with immediate corrective feedback",
                "Emphasize differences in structure between Portuguese and English"
            ]
    
    async def _assess_difficulty_level_ai(
        self,
        grammar_point: str,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str
    ) -> Dict[str, Any]:
        """Avaliar nível de dificuldade da interferência via IA."""
        
        vocabulary_words = [item.word for item in vocabulary_items]
        
        system_prompt = """You are an expert in Second Language Acquisition assessment, specializing in interference difficulty evaluation for Brazilian learners."""

        human_prompt = f"""Assess the L1 interference difficulty level for Brazilian Portuguese speakers:

CONTENT TO ASSESS:
- Grammar Point: {grammar_point}
- Vocabulary: {', '.join(vocabulary_words)}
- Student Level: {cefr_level}

Evaluate:
1. How difficult will L1 interference be for Brazilian students?
2. What makes it particularly challenging?
3. What factors make it easier or harder?
4. Realistic timeline for mastery

Return assessment in JSON:
{{
  "overall_difficulty": "very_easy|easy|moderate|hard|very_hard",
  "difficulty_factors": [
    "factor 1 that makes it hard/easy",
    "factor 2 that makes it hard/easy"
  ],
  "mastery_timeline": "realistic time estimate for {cefr_level} students",
  "success_indicators": [
    "sign 1 that students are overcoming interference",
    "sign 2 that students are overcoming interference"
  ],
  "difficulty_score": 0.75
}}

Be realistic about Brazilian learner challenges."""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            assessment = json.loads(content)
            
            logger.info(f"✅ Avaliação de dificuldade via IA: {assessment.get('overall_difficulty', 'moderate')}")
            return assessment
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na avaliação de dificuldade via IA: {str(e)}")
            return {
                "overall_difficulty": "moderate",
                "difficulty_factors": ["Cross-linguistic differences", "Brazilian learner patterns"],
                "mastery_timeline": f"3-6 weeks for {cefr_level} students with focused practice",
                "success_indicators": ["Reduced L1 transfer errors", "Increased awareness of differences"],
                "difficulty_score": 0.6
            }
    
    # =============================================================================
    # FALLBACK METHODS
    # =============================================================================
    
    async def _fallback_main_analysis(
        self,
        grammar_point: str,
        vocabulary_words: List[str],
        cefr_level: str
    ) -> Dict[str, Any]:
        """Análise de fallback quando IA falha."""
        return {
            "interference_patterns": [
                {
                    "category": "general_interference",
                    "portuguese_pattern": f"Portuguese structure related to {grammar_point}",
                    "incorrect_english_transfer": "Literal translation from Portuguese",
                    "correct_english": f"Proper English {grammar_point} structure",
                    "explanation": f"Portuguese and English differ in {grammar_point} usage",
                    "prevention_technique": "Explicit contrastive instruction",
                    "example_context": f"Context-specific example with {vocabulary_words[0] if vocabulary_words else 'vocabulary'}",
                    "difficulty_level": f"Moderate for {cefr_level}",
                    "frequency": "Common among Brazilian learners"
                }
            ],
            "predicted_common_mistakes": [
                {
                    "mistake": f"Common Brazilian error with {grammar_point}",
                    "correction": f"Correct {grammar_point} usage",
                    "reason": "L1 transfer from Portuguese"
                }
            ],
            "contrastive_examples": [
                {
                    "portuguese": f"Portuguese equivalent of {grammar_point}",
                    "english_wrong": "Literal English translation",
                    "english_correct": f"Correct English {grammar_point}",
                    "teaching_point": "Emphasize structural difference"
                }
            ],
            "prevention_strategies": [
                "Use contrastive analysis techniques",
                "Provide explicit error prevention instruction"
            ],
            "confidence_score": 0.7
        }
    
    def _create_fallback_exercises(self, cefr_level: str) -> List[Dict[str, Any]]:
        """Exercícios de fallback quando IA falha."""
        return [
            {
                "exercise_type": "contrastive_awareness",
                "title": "Portuguese vs English Comparison",
                "target_interference": "General L1 transfer",
                "instructions": "Compare Portuguese and English structures",
                "content": {
                    "items": [
                        {
                            "prompt": "Identify the difference between Portuguese and English",
                            "correct_answer": "English structure differs from Portuguese",
                            "explanation": "Languages have different patterns"
                        }
                    ],
                    "additional_notes": "Focus on preventing direct translation"
                },
                "teaching_tips": ["Use explicit comparison", "Highlight differences"],
                "estimated_time": "10-15 minutes",
                "skill_focus": ["grammar", "awareness"],
                "difficulty": f"Appropriate for {cefr_level}"
            }
        ]
    
    # =============================================================================
    # CACHE MANAGEMENT
    # =============================================================================
    
    def _generate_cache_key(
        self,
        grammar_point: str,
        vocabulary_items: List[VocabularyItem],
        cefr_level: str,
        unit_context: str
    ) -> str:
        """Gerar chave única para cache."""
        vocab_words = [item.word for item in vocabulary_items]
        content = f"{grammar_point}_{cefr_level}_{unit_context}_{'-'.join(vocab_words[:5])}"
        return f"l1_analysis_{hash(content)}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Recuperar análise do cache."""
        if key in self._analysis_cache:
            cached_data = self._analysis_cache[key]
            # Verificar se não expirou (2 horas)
            if time.time() - cached_data.get("cached_at", 0) < 7200:
                return cached_data.get("data")
        return None
    
    def _save_to_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Salvar análise no cache."""
        # Limpar cache se muito grande
        if len(self._analysis_cache) >= self._max_cache_size:
            oldest_key = min(
                self._analysis_cache.keys(),
                key=lambda k: self._analysis_cache[k].get("cached_at", 0)
            )
            del self._analysis_cache[oldest_key]
        
        self._analysis_cache[key] = {
            "data": data,
            "cached_at": time.time()
        }
    
    def clear_cache(self) -> None:
        """Limpar cache de análises."""
        self._analysis_cache.clear()
        logger.info("🗑️ Cache de análises L1 limpo")
    
    # =============================================================================
    # PUBLIC INTERFACE METHODS
    # =============================================================================
    
    async def quick_interference_check(
        self,
        word_or_phrase: str,
        cefr_level: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Verificação rápida de interferência para uma palavra ou frase específica.
        
        Args:
            word_or_phrase: Palavra ou frase para verificar
            cefr_level: Nível CEFR do estudante
            context: Contexto opcional
            
        Returns:
            Dict com análise rápida de interferência
        """
        try:
            system_prompt = """You are an expert in L1 interference for Brazilian Portuguese speakers learning English.

Provide a quick, focused analysis of potential L1 interference for the given word or phrase."""

            human_prompt = f"""Quick L1 interference check for Brazilian learners:

WORD/PHRASE: "{word_or_phrase}"
STUDENT LEVEL: {cefr_level}
CONTEXT: {context if context else "General usage"}

Analyze:
1. Is there potential L1 interference from Portuguese?
2. What specific interference might occur?
3. Quick prevention tip

Return brief analysis in JSON:
{{
  "has_interference": true/false,
  "interference_type": "false_friend|structure|pronunciation|usage|none",
  "quick_explanation": "brief explanation of the issue",
  "prevention_tip": "one quick teaching tip",
  "severity": "low|medium|high"
}}

Be concise but accurate."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            result = json.loads(content)
            
            logger.info(f"✅ Verificação rápida L1 para '{word_or_phrase}': {result.get('interference_type', 'none')}")
            return result
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na verificação rápida L1: {str(e)}")
            return {
                "has_interference": False,
                "interference_type": "unknown",
                "quick_explanation": "Unable to analyze at this time",
                "prevention_tip": "Monitor for common Brazilian learner errors",
                "severity": "medium"
            }
    
    async def generate_contrastive_explanation(
        self,
        english_structure: str,
        portuguese_equivalent: str,
        cefr_level: str
    ) -> str:
        """
        Gerar explicação contrastiva entre estrutura inglesa e portuguesa.
        
        Args:
            english_structure: Estrutura em inglês
            portuguese_equivalent: Equivalente em português
            cefr_level: Nível CEFR
            
        Returns:
            Explicação contrastiva detalhada
        """
        try:
            system_prompt = f"""You are an expert EFL teacher specializing in contrastive analysis for Brazilian students at {cefr_level} level.

Create a clear, pedagogical explanation comparing English and Portuguese structures."""

            human_prompt = f"""Create a contrastive explanation for {cefr_level} Brazilian students:

ENGLISH STRUCTURE: {english_structure}
PORTUGUESE EQUIVALENT: {portuguese_equivalent}
STUDENT LEVEL: {cefr_level}

Explain:
1. How the structures differ
2. Why Brazilians might make mistakes
3. Key teaching points to emphasize
4. Simple rule to remember

Make the explanation appropriate for {cefr_level} students - clear and not too complex."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            explanation = response.content
            
            logger.info(f"✅ Explicação contrastiva gerada para {cefr_level}")
            return explanation
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na geração de explicação contrastiva: {str(e)}")
            return f"Compare {english_structure} in English with {portuguese_equivalent} in Portuguese. Notice the structural differences and practice the English pattern."
    
    async def predict_common_errors(
        self,
        lesson_content: Dict[str, Any],
        cefr_level: str
    ) -> List[Dict[str, Any]]:
        """
        Prever erros comuns que estudantes brasileiros farão com o conteúdo.
        
        Args:
            lesson_content: Conteúdo da lição (grammar_point, vocabulary, etc.)
            cefr_level: Nível CEFR
            
        Returns:
            Lista de erros preditos com correções
        """
        try:
            system_prompt = """You are an experienced EFL teacher who has taught thousands of Brazilian students.

Predict the most likely errors Brazilian students will make with this lesson content."""

            human_prompt = f"""Predict common errors Brazilian students will make:

LESSON CONTENT:
{json.dumps(lesson_content, indent=2)}

STUDENT LEVEL: {cefr_level}

Based on your experience with Brazilian learners, predict:
1. The 5 most likely errors they will make
2. Why they will make each error
3. How to correct each error

Return predictions in JSON:
{{
  "predicted_errors": [
    {{
      "error_category": "grammar|vocabulary|pronunciation|usage",
      "student_will_say": "what student will incorrectly say/write",
      "correct_form": "the correct form",
      "why_this_error": "reason based on Portuguese interference",
      "correction_strategy": "how to help them fix it",
      "likelihood": "very_high|high|medium|low"
    }}
  ]
}}

Focus on realistic, specific errors based on Portuguese L1 patterns."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            predictions = json.loads(content)
            
            logger.info(f"✅ Predições de erro geradas: {len(predictions.get('predicted_errors', []))}")
            return predictions.get('predicted_errors', [])
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na predição de erros comuns: {str(e)}")
            return [
                {
                    "error_category": "general",
                    "student_will_say": "Common Brazilian learner error",
                    "correct_form": "Correct English form",
                    "why_this_error": "L1 Portuguese interference",
                    "correction_strategy": "Explicit instruction and practice",
                    "likelihood": "medium"
                }
            ]
    
    async def create_awareness_exercise(
        self,
        interference_pattern: Dict[str, Any],
        cefr_level: str
    ) -> Dict[str, Any]:
        """
        Criar exercício de conscientização para padrão específico de interferência.
        
        Args:
            interference_pattern: Padrão de interferência identificado
            cefr_level: Nível CEFR
            
        Returns:
            Exercício estruturado de conscientização
        """
        try:
            system_prompt = f"""You are an expert exercise designer for Brazilian EFL learners at {cefr_level} level.

Create a focused awareness exercise for the specific interference pattern provided."""

            human_prompt = f"""Create an awareness exercise for this L1 interference pattern:

INTERFERENCE PATTERN:
{json.dumps(interference_pattern, indent=2)}

STUDENT LEVEL: {cefr_level}

Design an exercise that:
1. Helps students become aware of this interference
2. Is appropriate for {cefr_level} level
3. Is engaging and effective
4. Takes 5-10 minutes to complete

Return exercise in JSON:
{{
  "exercise_title": "clear, engaging title",
  "objective": "what students will learn",
  "instructions": "clear step-by-step instructions",
  "content": {{
    "awareness_items": [
      {{
        "portuguese_version": "Portuguese structure/phrase",
        "english_wrong": "incorrect English (L1 transfer)",
        "english_correct": "correct English form",
        "explanation": "brief explanation of difference"
      }}
    ],
    "practice_items": [
      {{
        "situation": "context for practice",
        "student_task": "what student should do",
        "correct_answer": "expected correct response"
      }}
    ]
  }},
  "teacher_notes": ["tip 1", "tip 2"],
  "extension_activity": "optional follow-up activity"
}}

Make it specific to the interference pattern provided."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            exercise = json.loads(content)
            
            logger.info(f"✅ Exercício de conscientização criado: {exercise.get('exercise_title', 'Exercise')}")
            return exercise
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na criação de exercício de conscientização: {str(e)}")
            return {
                "exercise_title": "L1 Interference Awareness",
                "objective": "Recognize differences between Portuguese and English",
                "instructions": "Compare the Portuguese and English versions",
                "content": {
                    "awareness_items": [],
                    "practice_items": []
                },
                "teacher_notes": ["Focus on contrastive explanation"],
                "extension_activity": "Additional practice with similar patterns"
            }
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas das análises realizadas."""
        return {
            "cache_size": len(self._analysis_cache),
            "max_cache_size": self._max_cache_size,
            "cache_hit_ratio": "Not tracked in current implementation",
            "total_analyses": "Not tracked in current implementation",
            "ai_model": self.openai_config.get("model", "gpt-4o-mini"),
            "service_status": "active"
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def analyze_text_for_l1_interference(
    text: str,
    cefr_level: str,
    analyzer: Optional[L1InterferenceAnalyzer] = None
) -> Dict[str, Any]:
    """
    Função utilitária para analisar um texto livre para interferências L1.
    
    Args:
        text: Texto para analisar
        cefr_level: Nível CEFR do estudante
        analyzer: Instância do analisador (opcional)
        
    Returns:
        Análise de interferências no texto
    """
    if analyzer is None:
        analyzer = L1InterferenceAnalyzer()
    
    try:
        system_prompt = """You are an expert in analyzing L1 interference in student writing/speaking for Brazilian Portuguese speakers learning English."""

        human_prompt = f"""Analyze this text for L1 interference from Brazilian Portuguese:

TEXT TO ANALYZE: "{text}"
STUDENT LEVEL: {cefr_level}

Identify:
1. Actual L1 interference errors present
2. Likely causes (Portuguese influence)
3. Corrections needed
4. Teaching priorities

Return analysis in JSON:
{{
  "interference_errors_found": [
    {{
      "error_text": "specific error in the text",
      "error_type": "grammar|vocabulary|word_order|preposition|article",
      "correct_form": "how it should be written",
      "portuguese_influence": "why Brazilian made this error",
      "teaching_point": "what to focus on"
    }}
  ],
  "overall_assessment": "general assessment of L1 interference level",
  "teaching_priorities": ["priority 1", "priority 2"],
  "positive_aspects": ["what student did correctly"]
}}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        response = await analyzer.llm.ainvoke(messages)
        content = response.content
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
        
        analysis = json.loads(content)
        return analysis
        
    except Exception as e:
        logger.warning(f"⚠️ Erro na análise de texto para L1: {str(e)}")
        return {
            "interference_errors_found": [],
            "overall_assessment": "Unable to analyze at this time",
            "teaching_priorities": ["General error correction"],
            "positive_aspects": ["Student attempted communication"]
        }


def create_l1_interference_report(
    analysis_data: Dict[str, Any],
    unit_title: str,
    cefr_level: str
) -> str:
    """
    Criar relatório resumido de interferência L1.
    
    Args:
        analysis_data: Dados da análise de interferência
        unit_title: Título da unidade
        cefr_level: Nível CEFR
        
    Returns:
        Relatório formatado em texto
    """
    try:
        report_lines = [
            f"L1 INTERFERENCE ANALYSIS REPORT",
            f"Unit: {unit_title}",
            f"Level: {cefr_level}",
            f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "MAIN INTERFERENCE PATTERNS:"
        ]
        
        patterns = analysis_data.get("main_interference_patterns", {}).get("interference_patterns", [])
        for i, pattern in enumerate(patterns[:5], 1):
            report_lines.extend([
                f"{i}. {pattern.get('category', 'Unknown').title()}",
                f"   Portuguese: {pattern.get('portuguese_pattern', 'N/A')}",
                f"   Common Error: {pattern.get('incorrect_english_transfer', 'N/A')}",
                f"   Correct Form: {pattern.get('correct_english', 'N/A')}",
                f"   Prevention: {pattern.get('prevention_technique', 'N/A')}",
                ""
            ])
        
        # Vocabulário
        vocab_issues = analysis_data.get("vocabulary_interference", {}).get("vocabulary_interference_items", [])
        if vocab_issues:
            report_lines.extend([
                "VOCABULARY INTERFERENCE:",
                ""
            ])
            for item in vocab_issues[:3]:
                report_lines.extend([
                    f"• {item.get('word', 'Unknown')} - {item.get('interference_type', 'Unknown')}",
                    f"  Issue: {item.get('common_mistake', 'N/A')}",
                    f"  Correct: {item.get('correct_usage', 'N/A')}",
                    ""
                ])
        
        # Recomendações
        recommendations = analysis_data.get("teaching_recommendations", [])
        if recommendations:
            report_lines.extend([
                "TEACHING RECOMMENDATIONS:",
                ""
            ])
            for i, rec in enumerate(recommendations[:5], 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")
        
        # Dificuldade
        difficulty = analysis_data.get("difficulty_assessment", {})
        if difficulty:
            report_lines.extend([
                "DIFFICULTY ASSESSMENT:",
                f"Overall Level: {difficulty.get('overall_difficulty', 'Unknown').title()}",
                f"Mastery Timeline: {difficulty.get('mastery_timeline', 'Unknown')}",
                f"Confidence Score: {analysis_data.get('ai_confidence_score', 'N/A')}",
                ""
            ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        logger.warning(f"⚠️ Erro na criação do relatório L1: {str(e)}")
        return f"L1 Interference Analysis Report for {unit_title} ({cefr_level}) - Report generation error"


# Instância global do serviço
l1_interference_analyzer = L1InterferenceAnalyzer()