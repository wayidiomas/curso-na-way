# src/services/qa_generator.py
"""
Serviço de geração de perguntas e respostas pedagógicas.
Implementação baseada na Taxonomia de Bloom com foco em fonética e vocabulário.
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

from src.core.unit_models import QASection
from src.core.enums import CEFRLevel, LanguageVariant, UnitType
from config.models import get_openai_config, load_model_configs

logger = logging.getLogger(__name__)


class QAGeneratorService:
    """Serviço principal para geração de Q&A pedagógico."""
    
    def __init__(self):
        """Inicializar serviço com configurações."""
        self.openai_config = get_openai_config()
        self.model_configs = load_model_configs()
        
        # Configurar LangChain LLM
        self.llm = ChatOpenAI(
            model=self.openai_config.openai_model,
            temperature=0.7,  # Criatividade moderada para perguntas variadas
            max_tokens=3072,  # Espaço para múltiplas perguntas e respostas
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache simples em memória
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._max_cache_size = 50
        
        logger.info("✅ QAGeneratorService inicializado")
    
    async def generate_qa_for_unit(self, qa_params: Dict[str, Any]) -> QASection:
        """
        Gerar Q&A pedagógico para uma unidade.
        
        Args:
            qa_params: Parâmetros com contexto da unidade e hierarquia
            
        Returns:
            QASection completa com perguntas, respostas e notas pedagógicas
        """
        try:
            start_time = time.time()
            
            # Extrair parâmetros
            unit_data = qa_params.get("unit_data", {})
            content_data = qa_params.get("content_data", {})
            hierarchy_context = qa_params.get("hierarchy_context", {})
            pedagogical_context = qa_params.get("pedagogical_context", {})
            
            logger.info(f"🎓 Gerando Q&A pedagógico para unidade {unit_data.get('title', 'Unknown')}")
            
            # 1. Construir contexto pedagógico enriquecido
            enriched_context = await self._build_pedagogical_context(
                unit_data, content_data, hierarchy_context, pedagogical_context
            )
            
            # 2. Gerar prompt baseado na Taxonomia de Bloom
            qa_prompt = await self._build_bloom_taxonomy_prompt(enriched_context)
            
            # 3. Gerar Q&A via LLM
            raw_qa = await self._generate_qa_llm(qa_prompt)
            
            # 4. Processar e estruturar Q&A
            structured_qa = await self._process_and_structure_qa(raw_qa, enriched_context)
            
            # 5. Enriquecer com componentes fonéticos
            enriched_qa = await self._enrich_with_pronunciation_questions(
                structured_qa, content_data
            )
            
            # 6. Adicionar notas pedagógicas
            final_qa = await self._add_pedagogical_notes(enriched_qa, enriched_context)
            
            # 7. Construir QASection
            qa_section = QASection(
                questions=final_qa["questions"],
                answers=final_qa["answers"],
                pedagogical_notes=final_qa["pedagogical_notes"],
                difficulty_progression=final_qa["difficulty_progression"],
                vocabulary_integration=final_qa["vocabulary_integration"],
                cognitive_levels=final_qa["cognitive_levels"],
                pronunciation_questions=final_qa["pronunciation_questions"],
                phonetic_awareness=final_qa["phonetic_awareness"]
            )
            
            generation_time = time.time() - start_time
            
            logger.info(
                f"✅ Q&A gerado: {len(qa_section.questions)} perguntas em {generation_time:.2f}s"
            )
            
            return qa_section
            
        except Exception as e:
            logger.error(f"❌ Erro na geração de Q&A: {str(e)}")
            raise
    
    async def _build_pedagogical_context(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        pedagogical_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construir contexto pedagógico enriquecido."""
        
        # Extrair vocabulário da unidade
        vocabulary_items = []
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"]
        
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        
        # Extrair sentences
        sentences = []
        if content_data.get("sentences") and content_data["sentences"].get("sentences"):
            sentences = [s.get("text", "") for s in content_data["sentences"]["sentences"]]
        
        # Extrair estratégias aplicadas
        strategy_info = ""
        if content_data.get("tips"):
            strategy_info = f"TIPS Strategy: {content_data['tips'].get('strategy', 'unknown')} - {content_data['tips'].get('title', '')}"
        elif content_data.get("grammar"):
            strategy_info = f"GRAMMAR Strategy: {content_data['grammar'].get('strategy', 'unknown')} - {content_data['grammar'].get('grammar_point', '')}"
        
        # Objetivos de aprendizagem
        learning_objectives = pedagogical_context.get("learning_objectives", [])
        
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
                "vocabulary_words": vocabulary_words[:15],  # Top 15 para contexto
                "sentences_count": len(sentences),
                "sample_sentences": sentences[:3],  # Primeiras 3 para referência
                "strategy_applied": strategy_info,
                "has_assessments": bool(content_data.get("assessments"))
            },
            "hierarchy_info": {
                "course_name": hierarchy_context.get("course_name", ""),
                "book_name": hierarchy_context.get("book_name", ""),
                "sequence_order": hierarchy_context.get("sequence_order", 1),
                "target_level": hierarchy_context.get("target_level", unit_data.get("cefr_level"))
            },
            "pedagogical_goals": {
                "learning_objectives": learning_objectives,
                "progression_level": pedagogical_context.get("progression_level", "intermediate"),
                "phonetic_focus": pedagogical_context.get("phonetic_focus", "general_pronunciation"),
                "taught_vocabulary": pedagogical_context.get("taught_vocabulary", [])[:10
            },
            "bloom_taxonomy_targets": self._determine_bloom_targets(
                unit_data.get("cefr_level", "A2"),
                hierarchy_context.get("sequence_order", 1)
            )
        }
        
        return enriched_context
    
    async def _build_bloom_taxonomy_prompt(self, enriched_context: Dict[str, Any]) -> List[Any]:
        """Construir prompt baseado na Taxonomia de Bloom."""
        
        unit_info = enriched_context["unit_info"]
        content_analysis = enriched_context["content_analysis"]
        pedagogical_goals = enriched_context["pedagogical_goals"]
        bloom_targets = enriched_context["bloom_taxonomy_targets"]
        
        # Guidelines específicos por nível CEFR
        cefr_guidelines = {
            "A1": "Focus on basic recall and simple understanding. Use present tense and familiar vocabulary.",
            "A2": "Include recall, understanding, and simple application. Use past and future tenses appropriately.",
            "B1": "Balance understanding and application with some analysis. Include conditional structures.",
            "B2": "Emphasize application and analysis with evaluation. Use complex grammatical structures.",
            "C1": "Focus on analysis, evaluation, and creation. Use sophisticated language and abstract concepts.",
            "C2": "Emphasize evaluation and creation with nuanced analysis. Use native-level expressions."
        }
        
        cefr_level = unit_info["cefr_level"]
        cefr_guideline = cefr_guidelines.get(cefr_level, cefr_guidelines["A2"])
        
        system_prompt = f"""You are an expert English teacher creating pedagogical Q&A based on Bloom's Taxonomy for {cefr_level} level students.

UNIT CONTEXT:
- Title: {unit_info['title']}
- Context: {unit_info['context']}
- Level: {cefr_level}
- Type: {unit_info['unit_type']}
- Language Variant: {unit_info['language_variant']}
- Main Aim: {unit_info['main_aim']}

CONTENT TO INTEGRATE:
- Vocabulary ({content_analysis['vocabulary_count']} words): {', '.join(content_analysis['vocabulary_words'])}
- Sample Sentences: {' | '.join(content_analysis['sample_sentences'])}
- Strategy Applied: {content_analysis['strategy_applied']}

PEDAGOGICAL OBJECTIVES:
- Learning Goals: {'; '.join(pedagogical_goals['learning_objectives'])}
- Progression Level: {pedagogical_goals['progression_level']}
- Phonetic Focus: {pedagogical_goals['phonetic_focus']}

CEFR {cefr_level} GUIDELINES: {cefr_guideline}

BLOOM'S TAXONOMY DISTRIBUTION TARGET:
{json.dumps(bloom_targets, indent=2)}

GENERATION REQUIREMENTS:
1. Create exactly 8-12 questions following Bloom's Taxonomy
2. Include 2-3 pronunciation/phonetic awareness questions
3. Distribute questions across cognitive levels: {', '.join(bloom_targets.keys())}
4. Progress from simple to complex (Remember → Create)
5. Integrate unit vocabulary naturally in questions
6. Include cultural context when appropriate
7. Provide complete, pedagogically sound answers
8. Add teaching notes for instructor guidance

PRONUNCIATION FOCUS AREAS:
- Phoneme awareness (individual sounds)
- Word stress patterns
- Connected speech and rhythm
- {unit_info['language_variant']} specific features

OUTPUT FORMAT: Return valid JSON with this exact structure:
{{
  "questions": [
    "Question 1 (Remember level)",
    "Question 2 (Understand level)",
    "..."
  ],
  "answers": [
    "Complete answer to question 1 with explanations",
    "Complete answer to question 2 with context",
    "..."
  ],
  "cognitive_levels": [
    "remember",
    "understand",
    "..."
  ],
  "pedagogical_notes": [
    "Teaching note 1: How to use this question effectively",
    "Teaching note 2: What to emphasize with students",
    "..."
  ],
  "pronunciation_questions": [
    "Pronunciation-focused question 1",
    "Pronunciation-focused question 2"
  ],
  "phonetic_awareness": [
    "Phonetic awareness development note 1",
    "Phonetic awareness development note 2"
  ],
  "vocabulary_integration": [
    "word1", "word2", "word3"
  ]
}}"""

        human_prompt = f"""Create comprehensive Q&A for the unit "{unit_info['title']}" about "{unit_info['context']}"

Level: {cefr_level}
Vocabulary to integrate: {', '.join(content_analysis['vocabulary_words'][:10])}

Requirements:
- 8-12 questions total
- Follow Bloom's Taxonomy progression
- Include pronunciation questions
- Use unit vocabulary naturally
- Provide complete answers with explanations
- Add pedagogical notes for teachers

Context: {unit_info['context']}
Strategy: {content_analysis['strategy_applied']}

Generate the JSON structure now:"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
    
    async def _generate_qa_llm(self, prompt_messages: List[Any]) -> Dict[str, Any]:
        """Gerar Q&A usando LLM."""
        try:
            logger.info("🤖 Consultando LLM para geração de Q&A...")
            
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
                
                qa_data = json.loads(content)
                
                if not isinstance(qa_data, dict):
                    raise ValueError("Response não é um objeto")
                
                # Salvar no cache
                self._save_to_cache(cache_key, qa_data)
                
                logger.info(f"✅ LLM retornou Q&A com {len(qa_data.get('questions', []))} perguntas")
                return qa_data
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao parsear JSON, tentando extração manual: {str(e)}")
                return self._extract_qa_from_text(content)
                
        except Exception as e:
            logger.error(f"❌ Erro na consulta ao LLM: {str(e)}")
            # Retornar Q&A de fallback
            return self._generate_fallback_qa()
    
    async def _process_and_structure_qa(
        self, 
        raw_qa: Dict[str, Any], 
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processar e estruturar dados de Q&A."""
        
        # Extrair e validar campos obrigatórios
        questions = raw_qa.get("questions", [])
        answers = raw_qa.get("answers", [])
        cognitive_levels = raw_qa.get("cognitive_levels", [])
        
        # Garantir que há o mesmo número de perguntas, respostas e níveis cognitivos
        min_length = min(len(questions), len(answers), len(cognitive_levels))
        if min_length == 0:
            return self._generate_fallback_qa()
        
        # Truncar para o menor comprimento para manter consistência
        questions = questions[:min_length]
        answers = answers[:min_length]
        cognitive_levels = cognitive_levels[:min_length]
        
        # Processar campos opcionais
        pedagogical_notes = raw_qa.get("pedagogical_notes", [])
        pronunciation_questions = raw_qa.get("pronunciation_questions", [])
        phonetic_awareness = raw_qa.get("phonetic_awareness", [])
        vocabulary_integration = raw_qa.get("vocabulary_integration", [])
        
        # Validar e expandir notas pedagógicas se necessário
        if len(pedagogical_notes) < len(questions) // 2:
            # Adicionar notas pedagógicas básicas
            unit_info = enriched_context["unit_info"]
            for i in range(len(questions) - len(pedagogical_notes)):
                pedagogical_notes.append(
                    f"Teaching note: Use this question to reinforce {unit_info['unit_type']} concepts and encourage student participation."
                )
        
        # Determinar progressão de dificuldade
        difficulty_progression = self._analyze_difficulty_progression(cognitive_levels)
        
        return {
            "questions": questions,
            "answers": answers,
            "cognitive_levels": cognitive_levels,
            "pedagogical_notes": pedagogical_notes,
            "pronunciation_questions": pronunciation_questions,
            "phonetic_awareness": phonetic_awareness,
            "vocabulary_integration": vocabulary_integration,
            "difficulty_progression": difficulty_progression
        }
    
    async def _enrich_with_pronunciation_questions(
        self, 
        structured_qa: Dict[str, Any], 
        content_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enriquecer Q&A com perguntas específicas de pronúncia."""
        
        pronunciation_questions = structured_qa.get("pronunciation_questions", [])
        phonetic_awareness = structured_qa.get("phonetic_awareness", [])
        
        # Se já tem perguntas de pronúncia suficientes, manter
        if len(pronunciation_questions) >= 2:
            return structured_qa
        
        # Extrair vocabulário para criar perguntas de pronúncia
        vocabulary_items = []
        if content_data.get("vocabulary") and content_data["vocabulary"].get("items"):
            vocabulary_items = content_data["vocabulary"]["items"][:5]  # Top 5 palavras
        
        # Gerar perguntas de pronúncia adicionais
        additional_pronunciation = []
        additional_awareness = []
        
        for item in vocabulary_items:
            word = item.get("word", "")
            phoneme = item.get("phoneme", "")
            
            if word and phoneme:
                # Pergunta sobre fonema
                additional_pronunciation.append(
                    f"How do you pronounce '{word}'? What sounds do you hear?"
                )
                
                # Consciência fonética
                additional_awareness.append(
                    f"Students should identify the individual sounds in '{word}' {phoneme} and practice stress patterns."
                )
        
        # Adicionar perguntas de pronúncia gerais se necessário
        if len(additional_pronunciation) < 2:
            additional_pronunciation.extend([
                "Which words from this unit have similar stress patterns?",
                "How does connected speech change the pronunciation of these words?"
            ])
            
            additional_awareness.extend([
                "Focus on word stress patterns and rhythm in connected speech.",
                "Encourage students to notice pronunciation differences in different contexts."
            ])
        
        # Combinar com existentes
        structured_qa["pronunciation_questions"] = pronunciation_questions + additional_pronunciation[:2]
        structured_qa["phonetic_awareness"] = phonetic_awareness + additional_awareness[:2]
        
        return structured_qa
    
    async def _add_pedagogical_notes(
        self, 
        enriched_qa: Dict[str, Any], 
        enriched_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adicionar notas pedagógicas detalhadas."""
        
        pedagogical_notes = enriched_qa.get("pedagogical_notes", [])
        questions = enriched_qa.get("questions", [])
        cognitive_levels = enriched_qa.get("cognitive_levels", [])
        
        unit_info = enriched_context["unit_info"]
        cefr_level = unit_info["cefr_level"]
        
        # Expandir notas pedagógicas
        enhanced_notes = []
        
        for i, (question, level) in enumerate(zip(questions, cognitive_levels)):
            if i < len(pedagogical_notes):
                base_note = pedagogical_notes[i]
            else:
                base_note = f"Teaching guidance for question {i+1}"
            
            # Adicionar orientações específicas por nível cognitivo
            level_guidance = self._get_level_specific_guidance(level, cefr_level)
            
            enhanced_note = f"{base_note} | {level_guidance}"
            enhanced_notes.append(enhanced_note)
        
        # Adicionar notas gerais sobre o uso do Q&A
        general_notes = [
            f"Use these questions progressively to build {cefr_level} level comprehension.",
            f"Encourage students to use unit vocabulary: {', '.join(enriched_qa.get('vocabulary_integration', [])[:5])}.",
            "Monitor pronunciation during oral responses and provide feedback.",
            f"Adapt questions to {unit_info['unit_type']} learning objectives."
        ]
        
        enhanced_notes.extend(general_notes)
        
        enriched_qa["pedagogical_notes"] = enhanced_notes
        return enriched_qa
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _determine_bloom_targets(self, cefr_level: str, sequence_order: int) -> Dict[str, int]:
        """Determinar distribuição alvo de níveis de Bloom."""
        
        # Base distribution adaptada por nível CEFR
        base_distributions = {
            "A1": {"remember": 4, "understand": 3, "apply": 2, "analyze": 1, "evaluate": 0, "create": 0},
            "A2": {"remember": 3, "understand": 3, "apply": 3, "analyze": 1, "evaluate": 0, "create": 0},
            "B1": {"remember": 2, "understand": 3, "apply": 3, "analyze": 2, "evaluate": 1, "create": 0},
            "B2": {"remember": 2, "understand": 2, "apply": 3, "analyze": 2, "evaluate": 2, "create": 1},
            "C1": {"remember": 1, "understand": 2, "apply": 2, "analyze": 3, "evaluate": 2, "create": 2},
            "C2": {"remember": 1, "understand": 2, "apply": 2, "analyze": 2, "evaluate": 3, "create": 2}
        }
        
        distribution = base_distributions.get(cefr_level, base_distributions["A2"]).copy()
        
        # Ajustar baseado na sequência (unidades mais avançadas = mais análise)
        if sequence_order > 5:
            if distribution.get("analyze", 0) > 0:
                distribution["analyze"] += 1
            if distribution.get("remember", 0) > 1:
                distribution["remember"] -= 1
        
        return distribution
    
    def _analyze_difficulty_progression(self, cognitive_levels: List[str]) -> str:
        """Analisar progressão de dificuldade."""
        
        level_order = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
        level_scores = {level: i for i, level in enumerate(level_order)}
        
        if not cognitive_levels:
            return "unknown"
        
        scores = [level_scores.get(level, 2) for level in cognitive_levels]
        
        # Verificar se há progressão geral
        if len(scores) > 1:
            avg_first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            avg_second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            
            if avg_second_half > avg_first_half + 0.5:
                return "progressive"
            elif abs(avg_second_half - avg_first_half) <= 0.5:
                return "balanced"
            else:
                return "needs_reordering"
        
        return "single_level"
    
    def _get_level_specific_guidance(self, cognitive_level: str, cefr_level: str) -> str:
        """Obter orientações específicas por nível cognitivo."""
        
        guidance_map = {
            "remember": f"Help students recall vocabulary and basic concepts. For {cefr_level}: focus on recognition and simple recall.",
            "understand": f"Encourage explanation and description. For {cefr_level}: students should demonstrate comprehension through paraphrasing.",
            "apply": f"Guide students to use knowledge in new situations. For {cefr_level}: practical application in different contexts.",
            "analyze": f"Help students break down information and see relationships. For {cefr_level}: compare and contrast elements.",
            "evaluate": f"Encourage critical thinking and judgment. For {cefr_level}: assess and give reasoned opinions.",
            "create": f"Support students in producing original work. For {cefr_level}: combine elements to form something new."
        }
        
        return guidance_map.get(cognitive_level, "Guide students appropriately for their level.")
    
    def _extract_qa_from_text(self, text: str) -> Dict[str, Any]:
        """Extrair Q&A de texto quando JSON parsing falha."""
        
        qa_data = {
            "questions": [],
            "answers": [],
            "cognitive_levels": [],
            "pedagogical_notes": [],
            "pronunciation_questions": [],
            "phonetic_awareness": [],
            "vocabulary_integration": []
        }
        
        lines = text.split('\n')
        current_section = None
        current_list = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detectar seções
            if 'question' in line.lower():
                if current_section and current_list:
                    qa_data[current_section].extend(current_list)
                current_section = 'questions'
                current_list = []
                if ':' in line:
                    current_list.append(line.split(':', 1)[-1].strip())
            elif 'answer' in line.lower():
                if current_section and current_list:
                    qa_data[current_section].extend(current_list)
                current_section = 'answers'
                current_list = []
                if ':' in line:
                    current_list.append(line.split(':', 1)[-1].strip())
            elif 'pronunciation' in line.lower():
                if current_section and current_list:
                    qa_data[current_section].extend(current_list)
                current_section = 'pronunciation_questions'
                current_list = []
            elif any(marker in line for marker in ['1.', '2.', '3.', '-', '•']):
                if current_section:
                    cleaned_line = line.lstrip('123456789.-•').strip()
                    if cleaned_line:
                        current_list.append(cleaned_line)
        
        # Adicionar última seção
        if current_section and current_list:
            qa_data[current_section].extend(current_list)
        
        # Preencher campos faltantes
        num_questions = len(qa_data['questions'])
        
        if len(qa_data['answers']) < num_questions:
            for i in range(len(qa_data['answers']), num_questions):
                qa_data['answers'].append(f"Answer to question {i+1} - comprehensive response needed.")
        
        if len(qa_data['cognitive_levels']) < num_questions:
            default_levels = ['remember', 'understand', 'apply', 'analyze'] * (num_questions // 4 + 1)
            qa_data['cognitive_levels'] = default_levels[:num_questions]
        
        return qa_data
    
    def _generate_fallback_qa(self) -> Dict[str, Any]:
        """Gerar Q&A de fallback em caso de erro."""
        
        fallback_qa = {
            "questions": [
                "What new vocabulary did you learn in this unit?",
                "How would you use these words in a real conversation?",
                "Can you explain the main topic of this unit?",
                "What pronunciation patterns did you notice?",
                "How can you practice these words at home?"
            ],
            "answers": [
                "Students should list and define the key vocabulary from the unit, explaining meanings in their own words.",
                "Students should create example sentences or dialogues using the new vocabulary in realistic contexts.",
                "Students should summarize the unit's main theme and connect it to their personal experiences.",
                "Students should identify stress patterns, difficult sounds, and pronunciation rules from the unit.",
                "Students should suggest practical ways to review and use the vocabulary outside of class."
            ],
            "cognitive_levels": ["remember", "apply", "understand", "analyze", "create"],
            "pedagogical_notes": [
                "Use this question to assess vocabulary retention and understanding.",
                "Encourage creative use of vocabulary in meaningful contexts.",
                "Help students connect new learning to prior knowledge.",
                "Develop phonetic awareness and pronunciation skills.",
                "Promote autonomous learning and self-study strategies."
            ],
            "pronunciation_questions": [
                "Which words in this unit have stress on the first syllable?",
                "How do you pronounce the most difficult word from this unit?"
            ],
            "phonetic_awareness": [
                "Students should develop awareness of English stress patterns.",
                "Focus on clear articulation of challenging sounds."
            ],
            "vocabulary_integration": ["vocabulary", "pronunciation", "conversation", "practice"]
        }
        
        logger.warning("⚠️ Usando Q&A de fallback")
        return fallback_qa
    
    def _generate_cache_key(self, prompt_messages: List[Any]) -> str:
        """Gerar chave para cache baseada no prompt."""
        content = "".join([msg.content for msg in prompt_messages])
        return f"qa_{hash(content)}"
    
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

def validate_qa_structure(qa_data: Dict[str, Any]) -> bool:
    """Validar estrutura básica de Q&A."""
    required_fields = ["questions", "answers"]
    
    for field in required_fields:
        if field not in qa_data:
            return False
        if not isinstance(qa_data[field], list):
            return False
    
    # Verificar se há pelo menos uma pergunta e resposta
    if len(qa_data["questions"]) == 0 or len(qa_data["answers"]) == 0:
        return False
    
    # Verificar se o número de perguntas e respostas é compatível
    if len(qa_data["questions"]) != len(qa_data["answers"]):
        return False
    
    return True


def analyze_cognitive_complexity(cognitive_levels: List[str]) -> Dict[str, Any]:
    """Analisar complexidade cognitiva das perguntas."""
    
    level_weights = {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 5,
        "create": 6
    }
    
    if not cognitive_levels:
        return {"complexity_score": 0, "distribution": {}}
    
    # Calcular score médio de complexidade
    total_weight = sum(level_weights.get(level, 3) for level in cognitive_levels)
    complexity_score = total_weight / len(cognitive_levels)
    
    # Distribuição por níveis
    distribution = {}
    for level in cognitive_levels:
        distribution[level] = distribution.get(level, 0) + 1
    
    return {
        "complexity_score": complexity_score,
        "distribution": distribution,
        "highest_level": max(cognitive_levels, key=lambda x: level_weights.get(x, 0)) if cognitive_levels else None,
        "variety_score": len(set(cognitive_levels)) / 6  # 6 níveis possíveis
    }


def generate_pronunciation_questions(vocabulary_items: List[Dict[str, Any]]) -> List[str]:
    """Gerar perguntas de pronúncia baseadas no vocabulário."""
    
    pronunciation_questions = []
    
    for item in vocabulary_items[:3]:  # Top 3 palavras
        word = item.get("word", "")
        phoneme = item.get("phoneme", "")
        syllable_count = item.get("syllable_count", 1)
        
        if word:
            # Pergunta sobre stress
            if syllable_count > 1:
                pronunciation_questions.append(
                    f"Where is the main stress in the word '{word}'?"
                )
            
            # Pergunta sobre sons específicos
            if phoneme:
                pronunciation_questions.append(
                    f"What sounds do you hear in '{word}'? Practice saying it clearly."
                )
    
    # Perguntas gerais se não há vocabulário suficiente
    if len(pronunciation_questions) < 2:
        pronunciation_questions.extend([
            "Which words from this unit rhyme with each other?",
            "How does the pronunciation change in connected speech?"
        ])
    
    return pronunciation_questions[:3]  # Máximo 3 perguntas


