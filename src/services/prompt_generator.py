# src/services/prompt_generator.py
"""
Serviço centralizado de geração de prompts para o IVO V2.
Implementa prompt engineering otimizado para hierarquia Course → Book → Unit com RAG.
"""

import os
import yaml
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path

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
        """Inicializar serviço com templates pré-carregados."""
        self.templates: Dict[str, PromptTemplate] = {}
        self.prompts_config_dir = Path(__file__).parent.parent / "config" / "prompts" / "ivo"
        
        # Carregar todos os templates
        self._load_all_templates()
        
        # Cache de prompts formatados
        self._prompt_cache: Dict[str, List[Any]] = {}
        
        logger.info(f"✅ PromptGeneratorService inicializado com {len(self.templates)} templates")
    
    # =============================================================================
    # VOCABULÁRIO - PROMPT 6 OTIMIZADO
    # =============================================================================
    
    def generate_vocabulary_prompt(
        self,
        unit_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any],
        images_analysis: Dict[str, Any],
        target_count: int = 25
    ) -> List[Any]:
        """
        Gerar prompt otimizado para vocabulário com RAG e análise de imagens.
        Implementação do PROMPT 6 do IVO V2 Guide.
        """
        
        # Extrair contextos
        unit_ctx = unit_data
        hierarchy_ctx = hierarchy_context
        rag_ctx = rag_context
        images_ctx = images_analysis
        
        # Determinar guidelines por nível CEFR
        cefr_guidelines = self._get_cefr_vocabulary_guidelines(unit_ctx.get("cefr_level", "A2"))
        
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
        
        # Variante de pronúncia
        language_variant = unit_ctx.get("language_variant", "american_english")
        ipa_variant = self._get_ipa_variant(language_variant)
        
        variables = {
            "unit_title": unit_ctx.get("title", ""),
            "unit_context": unit_ctx.get("context", ""),
            "cefr_level": unit_ctx.get("cefr_level", "A2"),
            "language_variant": language_variant,
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
    # SENTENCES - PROMPT CONTEXTUAL
    # =============================================================================
    
    def generate_sentences_prompt(
        self,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para sentences conectadas ao vocabulário."""
        
        # Extrair palavras do vocabulário
        vocabulary_items = vocabulary_data.get("items", [])
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        
        # Análise de complexidade
        avg_syllables = sum(item.get("syllable_count", 1) for item in vocabulary_items) / max(len(vocabulary_items), 1)
        complexity_level = "simple" if avg_syllables <= 1.5 else "intermediate" if avg_syllables <= 2.5 else "complex"
        
        variables = {
            "vocabulary_list": ", ".join(vocabulary_words[:15]),
            "vocabulary_count": len(vocabulary_words),
            "unit_context": unit_data.get("context", ""),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "taught_vocabulary": ", ".join(rag_context.get("taught_vocabulary", [])[:10]),
            "progression_level": rag_context.get("progression_level", "intermediate"),
            "complexity_level": complexity_level,
            "sequence_order": hierarchy_context.get("sequence_order", 1),
            "target_sentences": 12 + min(hierarchy_context.get("sequence_order", 1), 3)  # 12-15 sentences
        }
        
        return self.templates["sentences_generation"].format(**variables)
    
    # =============================================================================
    # TIPS - ESTRATÉGIAS LEXICAIS
    # =============================================================================
    
    def generate_tips_prompt(
        self,
        selected_strategy: str,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para estratégias TIPS com seleção inteligente."""
        
        # Informações da estratégia selecionada
        strategy_info = self._get_tips_strategy_info(selected_strategy)
        
        # Análise do vocabulário para a estratégia
        vocabulary_items = vocabulary_data.get("items", [])
        vocabulary_words = [item.get("word", "") for item in vocabulary_items]
        vocabulary_analysis = self._analyze_vocabulary_for_tips(vocabulary_items, selected_strategy)
        
        variables = {
            "strategy_name": strategy_info["name"],
            "strategy_description": strategy_info["description"],
            "implementation_guide": strategy_info["implementation_guide"],
            "specific_instructions": strategy_info["specific_instructions"],
            "unit_title": unit_data.get("title", ""),
            "unit_context": unit_data.get("context", ""),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "vocabulary_words": ", ".join(vocabulary_words[:15]),
            "vocabulary_count": len(vocabulary_words),
            "used_strategies": ", ".join(rag_context.get("used_strategies", [])),
            "progression_level": rag_context.get("progression_level", "intermediate"),
            "vocabulary_patterns": vocabulary_analysis,
            "cefr_adaptation": strategy_info["cefr_adaptations"].get(
                unit_data.get("cefr_level", "A2"), 
                "Standard implementation"
            ),
            "complementary_strategies": ", ".join(strategy_info.get("complementary_strategies", [])),
            "phonetic_aspects": ", ".join(strategy_info.get("phonetic_aspects", []))
        }
        
        return self.templates["tips_strategies"].format(**variables)
    
    # =============================================================================
    # GRAMMAR - ESTRATÉGIAS GRAMATICAIS
    # =============================================================================
    
    def generate_grammar_prompt(
        self,
        selected_strategy: str,
        unit_data: Dict[str, Any],
        vocabulary_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para estratégias GRAMMAR."""
        
        # Determinar se é explicação sistemática ou prevenção L1
        is_l1_prevention = selected_strategy == "prevencao_erros_l1"
        
        # Identificar ponto gramatical principal
        grammar_point = self._identify_grammar_point(unit_data, vocabulary_data)
        
        # L1 interference patterns (português → inglês)
        l1_patterns = self._get_l1_interference_patterns(grammar_point) if is_l1_prevention else {}
        
        variables = {
            "strategy_type": "Prevenção de Erros L1" if is_l1_prevention else "Explicação Sistemática",
            "grammar_point": grammar_point,
            "unit_context": unit_data.get("context", ""),
            "vocabulary_list": ", ".join([item.get("word", "") for item in vocabulary_data.get("items", [])[:10]]),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "used_strategies": ", ".join(rag_context.get("used_strategies", [])),
            "l1_patterns": l1_patterns,
            "is_l1_prevention": is_l1_prevention,
            "systematic_focus": not is_l1_prevention
        }
        
        template_name = "l1_interference" if is_l1_prevention else "grammar_content"
        return self.templates[template_name].format(**variables)
    
    # =============================================================================
    # ASSESSMENTS - SELEÇÃO BALANCEADA
    # =============================================================================
    
    def generate_assessment_selection_prompt(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        rag_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para seleção inteligente de atividades."""
        
        # Análise de atividades já usadas
        used_assessments = rag_context.get("used_assessments", {})
        assessment_analysis = self._analyze_assessment_balance(used_assessments, unit_data.get("unit_type"))
        
        # Tipos recomendados baseados no tipo de unidade
        recommended_types = self._get_recommended_assessment_types(
            unit_data.get("unit_type", "lexical_unit"),
            unit_data.get("cefr_level", "A2")
        )
        
        variables = {
            "unit_data": str(unit_data),
            "vocabulary_data": str(content_data.get("vocabulary", {})),
            "strategies_used": ", ".join([
                content_data.get("tips", {}).get("strategy", ""),
                content_data.get("grammar", {}).get("strategy", "")
            ]).strip(", "),
            "used_assessments": str(used_assessments),
            "rag_context": str(rag_context),
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "unit_type": unit_data.get("unit_type", "lexical_unit"),
            "balance_analysis": assessment_analysis,
            "recommended_types": ", ".join(recommended_types),
            "underused_types": ", ".join(assessment_analysis.get("underused_types", [])),
            "progression_level": rag_context.get("progression_level", "intermediate")
        }
        
        return self.templates["assessment_selection"].format(**variables)
    
    # =============================================================================
    # Q&A - TAXONOMIA DE BLOOM
    # =============================================================================
    
    def generate_qa_prompt(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        pedagogical_context: Dict[str, Any]
    ) -> List[Any]:
        """Gerar prompt para Q&A baseado na Taxonomia de Bloom."""
        
        # Extrair vocabulário para integração
        vocabulary_items = content_data.get("vocabulary", {}).get("items", [])
        vocabulary_integration = [item.get("word", "") for item in vocabulary_items[:10]]
        
        # Estratégia aplicada
        strategy_applied = ""
        if content_data.get("tips"):
            strategy_applied = f"TIPS: {content_data['tips'].get('strategy', '')}"
        elif content_data.get("grammar"):
            strategy_applied = f"GRAMMAR: {content_data['grammar'].get('strategy', '')}"
        
        # Objetivos de aprendizagem
        learning_objectives = pedagogical_context.get("learning_objectives", [])
        if not learning_objectives:
            learning_objectives = self._generate_learning_objectives(unit_data, content_data)
        
        # Foco fonético
        phonetic_focus = self._determine_phonetic_focus(vocabulary_items)
        
        variables = {
            "unit_title": unit_data.get("title", ""),
            "unit_context": unit_data.get("context", ""),
            "vocabulary_items": ", ".join(vocabulary_integration),
            "strategy_applied": strategy_applied,
            "cefr_level": unit_data.get("cefr_level", "A2"),
            "language_variant": unit_data.get("language_variant", "american_english"),
            "learning_objectives": "; ".join(learning_objectives),
            "phonetic_focus": phonetic_focus,
            "progression_level": pedagogical_context.get("progression_level", "intermediate"),
            "bloom_distribution": self._get_bloom_distribution(unit_data.get("cefr_level", "A2")),
            "pronunciation_focus_count": len([item for item in vocabulary_items if self._has_pronunciation_challenges(item)])
        }
        
        return self.templates["qa_generation"].format(**variables)
    
    # =============================================================================
    # PHONETIC INTEGRATION
    # =============================================================================
    
    def generate_phonetic_integration_prompt(
        self,
        vocabulary_items: List[Dict[str, Any]],
        cefr_level: str,
        language_variant: str
    ) -> List[Any]:
        """Gerar prompt para integração fonética."""
        
        # Análise fonética do vocabulário
        phonetic_analysis = self._analyze_phonetic_complexity(vocabulary_items)
        
        variables = {
            "vocabulary_with_phonemes": str(vocabulary_items),
            "cefr_level": cefr_level,
            "language_variant": language_variant,
            "phonetic_complexity": phonetic_analysis["complexity"],
            "stress_patterns": ", ".join(phonetic_analysis.get("stress_patterns", [])),
            "difficult_sounds": ", ".join(phonetic_analysis.get("difficult_sounds", [])),
            "syllable_distribution": str(phonetic_analysis.get("syllable_distribution", {})),
            "pronunciation_challenges": phonetic_analysis.get("pronunciation_challenges", [])
        }
        
        return self.templates["phonetic_integration"].format(**variables)
    
    # =============================================================================
    # TEMPLATE LOADING E MANAGEMENT
    # =============================================================================
    
    def _load_all_templates(self):
        """Carregar todos os templates de prompts dos arquivos YAML."""
        
        # Templates principais do sistema
        template_files = {
            "vocabulary_generation": "vocabulary_generation.yaml",
            "sentences_generation": "sentences_generation.yaml", 
            "tips_strategies": "tips_strategies.yaml",
            "grammar_content": "grammar_content.yaml",
            "l1_interference": "l1_interference.yaml",
            "assessment_selection": "assessment_selection.yaml",
            "qa_generation": "qa_generation.yaml",
            "phonetic_integration": "phonetic_integration.yaml"
        }
        
        for template_name, filename in template_files.items():
            try:
                template_path = self.prompts_config_dir / filename
                if template_path.exists():
                    template = self._load_template_from_yaml(template_path)
                    self.templates[template_name] = template
                    logger.debug(f"✅ Template carregado: {template_name}")
                else:
                    # Criar template padrão se arquivo não existir
                    self.templates[template_name] = self._create_default_template(template_name)
                    logger.warning(f"⚠️ Arquivo {filename} não encontrado, usando template padrão")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar template {template_name}: {str(e)}")
                self.templates[template_name] = self._create_default_template(template_name)
    
    def _load_template_from_yaml(self, template_path: Path) -> PromptTemplate:
        """Carregar template de arquivo YAML."""
        with open(template_path, 'r', encoding='utf-8') as f:
            template_data = yaml.safe_load(f)
        
        return PromptTemplate(
            name=template_path.stem,
            system_prompt=template_data.get("system_prompt", ""),
            user_prompt=template_data.get("user_prompt", ""),
            variables=self._extract_variables_from_prompts(
                template_data.get("system_prompt", ""),
                template_data.get("user_prompt", "")
            )
        )
    
    def _extract_variables_from_prompts(self, system_prompt: str, user_prompt: str) -> List[str]:
        """Extrair variáveis dos prompts (formato {variavel})."""
        import re
        
        combined_text = system_prompt + " " + user_prompt
        variables = re.findall(r'\{([^}]+)\}', combined_text)
        return list(set(variables))
    
    def _create_default_template(self, template_name: str) -> PromptTemplate:
        """Criar template padrão para fallback."""
        
        default_templates = {
            "vocabulary_generation": PromptTemplate(
                name="vocabulary_generation",
                system_prompt="""You are an expert English teacher creating vocabulary for {cefr_level} level students.

CONTEXT: {unit_context}
LEVEL: {cefr_level}
TARGET: {target_count} words
AVOID: {taught_vocabulary}

Generate vocabulary appropriate for the context and level.""",
                user_prompt="Generate {target_count} vocabulary items for: {unit_title}",
                variables=["cefr_level", "unit_context", "target_count", "taught_vocabulary", "unit_title"]
            ),
            
            "sentences_generation": PromptTemplate(
                name="sentences_generation",
                system_prompt="""Create sentences that demonstrate vocabulary usage.

VOCABULARY: {vocabulary_list}
CONTEXT: {unit_context}
LEVEL: {cefr_level}""",
                user_prompt="Create {target_sentences} sentences using the vocabulary naturally.",
                variables=["vocabulary_list", "unit_context", "cefr_level", "target_sentences"]
            ),
            
            "tips_strategies": PromptTemplate(
                name="tips_strategies",
                system_prompt="""Apply the {strategy_name} strategy to vocabulary learning.

STRATEGY: {strategy_description}
VOCABULARY: {vocabulary_words}
LEVEL: {cefr_level}""",
                user_prompt="Apply this strategy to help students learn the vocabulary effectively.",
                variables=["strategy_name", "strategy_description", "vocabulary_words", "cefr_level"]
            )
        }
        
        return default_templates.get(template_name, PromptTemplate(
            name=template_name,
            system_prompt="You are an expert English teacher.",
            user_prompt="Help the student learn English effectively.",
            variables=[]
        ))
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    def _get_cefr_vocabulary_guidelines(self, cefr_level: str) -> str:
        """Obter guidelines específicas por nível CEFR."""
        guidelines = {
            "A1": "Focus on basic, high-frequency vocabulary. Use simple, everyday words that students encounter daily. Prioritize concrete nouns, basic verbs, and essential adjectives.",
            "A2": "Include practical vocabulary for common situations. Words should be useful for basic communication. Introduce basic academic vocabulary and common phrasal verbs.",
            "B1": "Introduce more varied vocabulary including some academic and professional terms. Include abstract concepts and more sophisticated expressions.",
            "B2": "Include complex vocabulary, collocations, and nuanced meanings. Focus on academic and professional vocabulary with subtle distinctions.",
            "C1": "Advanced vocabulary with sophisticated expressions and academic language. Include specialized terminology and complex semantic relationships.",
            "C2": "Native-level vocabulary including idioms, specialized terms, and subtle distinctions. Advanced register awareness and stylistic variations."
        }
        
        return guidelines.get(cefr_level, guidelines["A2"])
    
    def _get_ipa_variant(self, language_variant: str) -> str:
        """Mapear variante de idioma para variante IPA."""
        mapping = {
            "american_english": "General American",
            "british_english": "Received Pronunciation", 
            "australian_english": "Australian English",
            "canadian_english": "Canadian English",
            "indian_english": "Indian English"
        }
        return mapping.get(language_variant, "General American")
    
    def _get_tips_strategy_info(self, strategy: str) -> Dict[str, Any]:
        """Obter informações detalhadas da estratégia TIPS."""
        
        strategies_db = {
            "afixacao": {
                "name": "TIP 1: Afixação",
                "description": "Ensino através de prefixos e sufixos para expansão sistemática",
                "implementation_guide": "Identify common prefixes and suffixes. Group words by morphological patterns. Teach the meaning of affixes.",
                "specific_instructions": "Focus on prefix/suffix patterns. Show how adding affixes creates new words and changes meanings.",
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
                "implementation_guide": "Group compound words by theme. Show relationships between simple words and compounds.",
                "specific_instructions": "Identify compound words and word families. Group by themes. Show how meaning is built from parts.",
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
                "implementation_guide": "Teach words that naturally go together. Focus on verb+noun, adjective+noun combinations.",
                "specific_instructions": "Identify natural word partnerships. Show strong vs weak collocations.",
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
                "implementation_guide": "Teach fixed phrases as complete units. Focus on communicative functions.",
                "specific_instructions": "Present expressions as whole units. Practice in communicative contexts.",
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
                "implementation_guide": "Teach idiomatic meaning alongside literal meaning. Provide cultural context.",
                "specific_instructions": "Explain both literal and figurative meanings. Provide cultural background.",
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
                "implementation_guide": "Teach functional language blocks as complete units. Focus on communicative purposes.",
                "specific_instructions": "Present chunks as ready-made units. Practice until automatic.",
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
        
        return strategies_db.get(strategy, strategies_db["chunks"])
    
    def _analyze_vocabulary_for_tips(self, vocabulary_items: List[Dict[str, Any]], strategy: str) -> str:
        """Analisar vocabulário para aplicação da estratégia TIPS."""
        
        words = [item.get("word", "").lower() for item in vocabulary_items]
        
        if strategy == "afixacao":
            has_affixes = any(
                word.startswith(("un", "re", "pre", "dis")) or 
                word.endswith(("er", "ly", "tion", "ing", "ness"))
                for word in words
            )
            return f"Has clear affix patterns: {has_affixes}. Words suitable for morphological analysis."
        
        elif strategy == "substantivos_compostos":
            compounds = [word for word in words if "-" in word or any(part in word for part in ["room", "book", "work", "time"])]
            return f"Found {len(compounds)} compound words: {', '.join(compounds[:3])}"
        
        elif strategy == "colocacoes":
            collocation_words = [word for word in words if word in ["make", "take", "get", "have", "do", "heavy", "strong", "big"]]
            return f"Collocation potential with words: {', '.join(collocation_words)}. Focus on natural combinations."
        
        elif strategy == "expressoes_fixas":
            return f"Vocabulary suitable for fixed expressions. Focus on functional language and formulaic phrases."
        
        elif strategy == "idiomas":
            idiomatic_potential = [word for word in words if word in ["break", "catch", "fall", "get", "come", "go", "under", "over"]]
            return f"Idiomatic potential with: {', '.join(idiomatic_potential)}. Explore figurative meanings."
        
        elif strategy == "chunks":
            functional_words = [word for word in words if word in ["would", "like", "could", "should", "how", "what", "where"]]
            return f"Functional chunks possible with: {', '.join(functional_words)}. Build communicative blocks."
        
        return "Standard vocabulary analysis for strategy application."
    
    def _identify_grammar_point(self, unit_data: Dict[str, Any], vocabulary_data: Dict[str, Any]) -> str:
        """Identificar ponto gramatical principal da unidade."""
        
        # Analisar contexto da unidade
        context = unit_data.get("context", "").lower()
        title = unit_data.get("title", "").lower()
        
        # Analisar vocabulário
        vocabulary_items = vocabulary_data.get("items", [])
        word_classes = [item.get("word_class", "") for item in vocabulary_items]
        
        # Identificar padrões gramaticais
        if any(word in context + title for word in ["past", "yesterday", "ago", "last"]):
            return "Past Tenses"
        elif any(word in context + title for word in ["future", "will", "going to", "tomorrow"]):
            return "Future Tenses"
        elif any(word in context + title for word in ["present", "now", "currently", "always"]):
            return "Present Tenses"
        elif "modal" in word_classes or any(word in [item.get("word", "") for item in vocabulary_items] for word in ["can", "could", "should", "would", "must"]):
            return "Modal Verbs"
        elif any(word in context + title for word in ["compare", "more", "most", "better", "best"]):
            return "Comparatives and Superlatives"
        elif "article" in word_classes or any(word in context + title for word in ["a", "an", "the"]):
            return "Articles"
        elif any(word in context + title for word in ["where", "when", "who", "which", "that"]):
            return "Relative Clauses"
        elif any(word in context + title for word in ["if", "condition", "would", "unless"]):
            return "Conditional Sentences"
        else:
            return "General Grammar Structures"
    
    def _get_l1_interference_patterns(self, grammar_point: str) -> Dict[str, Any]:
        """Obter padrões de interferência L1 (português → inglês)."""
        
        interference_patterns = {
            "Articles": {
                "portuguese_pattern": "O café está quente",
                "incorrect_english": "The coffee is hot",
                "correct_english": "Coffee is hot (generic reference)",
                "explanation": "Portuguese uses definite articles with generic nouns, English doesn't"
            },
            
            "Present Tenses": {
                "portuguese_pattern": "Eu estou trabalhando aqui há 5 anos",
                "incorrect_english": "I am working here for 5 years",
                "correct_english": "I have been working here for 5 years",
                "explanation": "Portuguese present continuous for ongoing actions, English uses present perfect continuous"
            },
            
            "Modal Verbs": {
                "portuguese_pattern": "Eu tenho que ir",
                "incorrect_english": "I have to go",
                "correct_english": "I must go / I have to go",
                "explanation": "Portuguese 'ter que' maps to different modals in English depending on context"
            },
            
            "Past Tenses": {
                "portuguese_pattern": "Eu fui para casa ontem",
                "incorrect_english": "I have been to home yesterday",
                "correct_english": "I went home yesterday",
                "explanation": "Portuguese pretérito perfeito vs. English simple past/present perfect distinction"
            },
            
            "Future Tenses": {
                "portuguese_pattern": "Vou fazer amanhã",
                "incorrect_english": "I go to do tomorrow",
                "correct_english": "I will do it tomorrow / I'm going to do it tomorrow",
                "explanation": "Portuguese future construction differs from English will/going to"
            }
        }
        
        return interference_patterns.get(grammar_point, {
            "portuguese_pattern": "Padrão português comum",
            "incorrect_english": "Common interference error",
            "correct_english": "Correct English form",
            "explanation": "Explanation of the difference"
        })
    
    def _analyze_assessment_balance(self, used_assessments: Dict[str, Any], unit_type: str) -> Dict[str, Any]:
        """Analisar balanceamento de atividades."""
        
        # Tipos disponíveis
        all_types = ["cloze_test", "gap_fill", "reordenacao", "transformacao", "multipla_escolha", "verdadeiro_falso", "matching"]
        
        # Contar usos
        type_counts = {}
        total_used = 0
        
        if isinstance(used_assessments, dict):
            for assessment_type, count in used_assessments.items():
                type_counts[assessment_type] = count
                total_used += count
        
        # Identificar tipos subutilizados
        underused_types = []
        for assessment_type in all_types:
            if type_counts.get(assessment_type, 0) <= 1:  # Usado 1 vez ou menos
                underused_types.append(assessment_type)
        
        # Calcular score de balanceamento
        if total_used > 0:
            balance_score = len(set(type_counts.keys())) / len(all_types)
        else:
            balance_score = 1.0  # Primeiro use
        
        return {
            "total_activities_used": total_used,
            "type_distribution": type_counts,
            "underused_types": underused_types,
            "balance_score": balance_score,
            "needs_balancing": balance_score < 0.6
        }
    
    def _get_recommended_assessment_types(self, unit_type: str, cefr_level: str) -> List[str]:
        """Obter tipos de atividades recomendadas."""
        
        if unit_type == "lexical_unit":
            base_recommendations = ["gap_fill", "matching", "verdadeiro_falso"]
            
            if cefr_level in ["A1", "A2"]:
                base_recommendations.extend(["multipla_escolha"])
            else:
                base_recommendations.extend(["cloze_test"])
                
        else:  # grammar_unit
            base_recommendations = ["transformacao", "reordenacao", "cloze_test"]
            
            if cefr_level in ["B1", "B2", "C1", "C2"]:
                base_recommendations.extend(["gap_fill"])
            else:
                base_recommendations.extend(["multipla_escolha"])
        
        return base_recommendations
    
    def _generate_learning_objectives(self, unit_data: Dict[str, Any], content_data: Dict[str, Any]) -> List[str]:
        """Gerar objetivos de aprendizagem se não fornecidos."""
        
        objectives = []
        
        # Objetivo principal baseado no contexto
        if unit_data.get("context"):
            objectives.append(f"Students will be able to communicate effectively in {unit_data['context']} situations")
        
        # Objetivo de vocabulário
        vocab_count = len(content_data.get("vocabulary", {}).get("items", []))
        if vocab_count > 0:
            objectives.append(f"Master and use {vocab_count} new vocabulary items in context")
        
        # Objetivo baseado no tipo de unidade
        if unit_data.get("unit_type") == "lexical_unit":
            objectives.append("Apply vocabulary learning strategies effectively")
            objectives.append("Demonstrate understanding through practical use")
        else:
            objectives.append("Understand and apply grammatical structures accurately")
            objectives.append("Avoid common L1 interference errors")
        
        # Objetivo de pronúncia
        objectives.append("Improve pronunciation accuracy and awareness")
        
        return objectives[:4]  # Máximo 4 objetivos
    
    def _determine_phonetic_focus(self, vocabulary_items: List[Dict[str, Any]]) -> str:
        """Determinar foco fonético baseado no vocabulário."""
        
        if not vocabulary_items:
            return "general_pronunciation"
        
        # Analisar padrões no vocabulário
        phonemes = []
        stress_patterns = []
        
        for item in vocabulary_items:
            phoneme = item.get("phoneme", "")
            if phoneme:
                phonemes.append(phoneme)
                if "ˈ" in phoneme:
                    stress_patterns.append("primary_stress")
                if "ˌ" in phoneme:
                    stress_patterns.append("secondary_stress")
        
        # Determinar foco principal
        difficult_sounds = ["θ", "ð", "ʃ", "ʒ", "ŋ", "æ", "ʌ", "ɜː"]
        has_difficult_sounds = any(sound in "".join(phonemes) for sound in difficult_sounds)
        
        if len(stress_patterns) > len(vocabulary_items) * 0.7:
            return "word_stress_patterns"
        elif has_difficult_sounds:
            return "challenging_phonemes"
        elif any(len(item.get("word", "")) > 6 for item in vocabulary_items):
            return "multisyllabic_pronunciation"
        else:
            return "clear_articulation"
    
    def _get_bloom_distribution(self, cefr_level: str) -> str:
        """Obter distribuição recomendada da Taxonomia de Bloom por nível."""
        
        distributions = {
            "A1": "REMEMBER: 3-4, UNDERSTAND: 2-3, APPLY: 2-3, ANALYZE: 1, EVALUATE: 1, CREATE: 1",
            "A2": "REMEMBER: 2-3, UNDERSTAND: 3-4, APPLY: 2-3, ANALYZE: 1-2, EVALUATE: 1, CREATE: 1",
            "B1": "REMEMBER: 2, UNDERSTAND: 2-3, APPLY: 3-4, ANALYZE: 2, EVALUATE: 1-2, CREATE: 1-2",
            "B2": "REMEMBER: 2, UNDERSTAND: 2, APPLY: 3, ANALYZE: 2-3, EVALUATE: 2, CREATE: 2",
            "C1": "REMEMBER: 1, UNDERSTAND: 2, APPLY: 2, ANALYZE: 3, EVALUATE: 2-3, CREATE: 2-3",
            "C2": "REMEMBER: 1, UNDERSTAND: 1, APPLY: 2, ANALYZE: 3, EVALUATE: 3, CREATE: 3"
        }
        
        return distributions.get(cefr_level, distributions["A2"])
    
    def _has_pronunciation_challenges(self, item: Dict[str, Any]) -> bool:
        """Verificar se item tem desafios de pronúncia."""
        
        phoneme = item.get("phoneme", "")
        word = item.get("word", "")
        
        # Sons difíceis para brasileiros
        difficult_sounds = ["θ", "ð", "ʃ", "ʒ", "ŋ", "æ", "ʌ", "ɜː", "ɪ", "iː"]
        
        return (
            any(sound in phoneme for sound in difficult_sounds) or
            len(word) > 7 or  # Palavras longas
            "ˈ" in phoneme  # Stress patterns
        )
    
    def _analyze_phonetic_complexity(self, vocabulary_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analisar complexidade fonética do vocabulário."""
        
        if not vocabulary_items:
            return {"complexity": "medium", "stress_patterns": [], "difficult_sounds": []}
        
        # Análise de sílabas
        syllable_counts = []
        for item in vocabulary_items:
            syllable_count = item.get("syllable_count")
            if syllable_count:
                syllable_counts.append(syllable_count)
            else:
                # Estimar baseado na palavra
                word = item.get("word", "")
                estimated = max(1, len([c for c in word.lower() if c in "aeiouy"]))
                syllable_counts.append(estimated)
        
        avg_syllables = sum(syllable_counts) / len(syllable_counts) if syllable_counts else 1
        
        # Análise de sons difíceis
        all_phonemes = "".join([item.get("phoneme", "") for item in vocabulary_items])
        difficult_sounds = []
        
        sound_checks = {
            "θ": "voiceless_th",
            "ð": "voiced_th", 
            "ʃ": "sh_sound",
            "ʒ": "zh_sound",
            "ŋ": "ng_sound",
            "æ": "ash_vowel",
            "ʌ": "schwa_stressed",
            "ɜː": "er_vowel"
        }
        
        for sound, name in sound_checks.items():
            if sound in all_phonemes:
                difficult_sounds.append(name)
        
        # Análise de stress
        stress_patterns = []
        for item in vocabulary_items:
            phoneme = item.get("phoneme", "")
            if "ˈ" in phoneme:
                stress_patterns.append("primary_stress")
            if "ˌ" in phoneme:
                stress_patterns.append("secondary_stress")
        
        # Determinar complexidade geral
        if avg_syllables <= 1.5 and len(difficult_sounds) <= 2:
            complexity = "simple"
        elif avg_syllables <= 2.5 and len(difficult_sounds) <= 4:
            complexity = "medium"
        elif avg_syllables <= 3.5 and len(difficult_sounds) <= 6:
            complexity = "complex"
        else:
            complexity = "very_complex"
        
        return {
            "complexity": complexity,
            "average_syllables": avg_syllables,
            "difficult_sounds": list(set(difficult_sounds)),
            "stress_patterns": list(set(stress_patterns)),
            "syllable_distribution": {
                "1": len([s for s in syllable_counts if s == 1]),
                "2": len([s for s in syllable_counts if s == 2]),
                "3": len([s for s in syllable_counts if s == 3]),
                "4+": len([s for s in syllable_counts if s >= 4])
            },
            "pronunciation_challenges": [
                f"Average {avg_syllables:.1f} syllables per word",
                f"{len(difficult_sounds)} challenging sound types",
                f"{len(stress_patterns)} stress pattern types"
            ]
        }
    
    # =============================================================================
    # CACHE E UTILITIES
    # =============================================================================
    
    def clear_cache(self):
        """Limpar cache de prompts."""
        self._prompt_cache.clear()
        logger.info("🗑️ Cache de prompts limpo")
    
    def reload_templates(self):
        """Recarregar todos os templates."""
        self.templates.clear()
        self._load_all_templates()
        self.clear_cache()
        logger.info("🔄 Templates recarregados")
    
    def get_template_info(self, template_name: str) -> Dict[str, Any]:
        """Obter informações sobre um template."""
        if template_name not in self.templates:
            return {"error": f"Template {template_name} não encontrado"}
        
        template = self.templates[template_name]
        return {
            "name": template.name,
            "variables": template.variables,
            "variable_count": len(template.variables),
            "system_prompt_length": len(template.system_prompt),
            "user_prompt_length": len(template.user_prompt)
        }
    
    def list_available_templates(self) -> List[str]:
        """Listar templates disponíveis."""
        return list(self.templates.keys())
    
    def validate_template_variables(self, template_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Validar variáveis para um template."""
        if template_name not in self.templates:
            return {"valid": False, "error": f"Template {template_name} não encontrado"}
        
        template = self.templates[template_name]
        required_vars = set(template.variables)
        provided_vars = set(variables.keys())
        
        missing_vars = required_vars - provided_vars
        extra_vars = provided_vars - required_vars
        
        return {
            "valid": len(missing_vars) == 0,
            "missing_variables": list(missing_vars),
            "extra_variables": list(extra_vars),
            "required_variables": list(required_vars),
            "provided_variables": list(provided_vars)
        }
    
    # =============================================================================
    # CUSTOM PROMPT BUILDERS
    # =============================================================================
    
    def build_custom_prompt(
        self,
        system_message: str,
        user_message: str,
        variables: Dict[str, Any] = None
    ) -> List[Any]:
        """Construir prompt customizado."""
        
        if variables:
            try:
                system_message = system_message.format(**variables)
                user_message = user_message.format(**variables)
            except KeyError as e:
                logger.warning(f"Variável não encontrada no prompt customizado: {e}")
        
        return [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message)
        ]
    
    def build_unit_complete_prompt(
        self,
        unit_data: Dict[str, Any],
        content_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        generation_type: str = "complete_unit"
    ) -> List[Any]:
        """Construir prompt para geração de unidade completa."""
        
        system_prompt = f"""You are an expert English curriculum designer creating a complete pedagogical unit.

UNIT OVERVIEW:
- Title: {unit_data.get('title', '')}
- Context: {unit_data.get('context', '')}
- Level: {unit_data.get('cefr_level', 'A2')}
- Type: {unit_data.get('unit_type', 'lexical_unit')}
- Course: {hierarchy_context.get('course_name', '')}
- Book: {hierarchy_context.get('book_name', '')}
- Sequence: Unit {hierarchy_context.get('sequence_order', 1)}

CONTENT INTEGRATION:
- Vocabulary: {len(content_data.get('vocabulary', {}).get('items', []))} words
- Has Sentences: {bool(content_data.get('sentences'))}
- Has Strategies: {bool(content_data.get('tips') or content_data.get('grammar'))}
- Has Assessments: {bool(content_data.get('assessments'))}

GENERATION FOCUS: {generation_type}

Create a cohesive, pedagogically sound unit that integrates all components effectively."""

        user_prompt = f"""Generate a complete unit that demonstrates best practices in {unit_data.get('unit_type', 'lexical_unit')} instruction for {unit_data.get('cefr_level', 'A2')} level students.

Focus on:
1. Clear learning objectives
2. Logical content progression
3. Integrated skills development
4. Appropriate challenge level
5. Practical communicative value

Context: {unit_data.get('context', '')}"""

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
    
    def get_prompt_statistics(self) -> Dict[str, Any]:
        """Obter estatísticas dos prompts."""
        
        stats = {
            "total_templates": len(self.templates),
            "templates_loaded": list(self.templates.keys()),
            "cache_size": len(self._prompt_cache),
            "template_details": {}
        }
        
        for name, template in self.templates.items():
            stats["template_details"][name] = {
                "variables_count": len(template.variables),
                "system_prompt_words": len(template.system_prompt.split()),
                "user_prompt_words": len(template.user_prompt.split()),
                "variables": template.variables
            }
        
        return stats


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_prompt_for_content_type(
    content_type: str,
    unit_data: Dict[str, Any],
    context_data: Dict[str, Any] = None
) -> List[Any]:
    """Função utilitária para criar prompts por tipo de conteúdo."""
    
    prompt_service = PromptGeneratorService()
    
    context_data = context_data or {}
    
    if content_type == "vocabulary":
        return prompt_service.generate_vocabulary_prompt(
            unit_data=unit_data,
            hierarchy_context=context_data.get("hierarchy", {}),
            rag_context=context_data.get("rag", {}),
            images_analysis=context_data.get("images", {}),
            target_count=context_data.get("target_count", 25)
        )
    
    elif content_type == "sentences":
        return prompt_service.generate_sentences_prompt(
            unit_data=unit_data,
            vocabulary_data=context_data.get("vocabulary", {}),
            hierarchy_context=context_data.get("hierarchy", {}),
            rag_context=context_data.get("rag", {})
        )
    
    elif content_type == "tips":
        return prompt_service.generate_tips_prompt(
            selected_strategy=context_data.get("strategy", "chunks"),
            unit_data=unit_data,
            vocabulary_data=context_data.get("vocabulary", {}),
            rag_context=context_data.get("rag", {})
        )
    
    elif content_type == "grammar":
        return prompt_service.generate_grammar_prompt(
            selected_strategy=context_data.get("strategy", "explicacao_sistematica"),
            unit_data=unit_data,
            vocabulary_data=context_data.get("vocabulary", {}),
            rag_context=context_data.get("rag", {})
        )
    
    elif content_type == "assessments":
        return prompt_service.generate_assessment_selection_prompt(
            unit_data=unit_data,
            content_data=context_data.get("content", {}),
            rag_context=context_data.get("rag", {})
        )
    
    elif content_type == "qa":
        return prompt_service.generate_qa_prompt(
            unit_data=unit_data,
            content_data=context_data.get("content", {}),
            pedagogical_context=context_data.get("pedagogical", {})
        )
    
    else:
        raise ValueError(f"Tipo de conteúdo não suportado: {content_type}")


def validate_prompt_context(
    content_type: str,
    unit_data: Dict[str, Any],
    context_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Validar contexto para geração de prompts."""
    
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "missing_context": []
    }
    
    # Validações básicas
    required_unit_fields = ["title", "context", "cefr_level", "unit_type"]
    for field in required_unit_fields:
        if not unit_data.get(field):
            validation_result["errors"].append(f"Campo obrigatório ausente: {field}")
            validation_result["valid"] = False
    
    # Validações específicas por tipo
    if content_type == "vocabulary":
        if not context_data.get("images") and not unit_data.get("context"):
            validation_result["warnings"].append("Sem análise de imagens nem contexto detalhado")
        
        if not context_data.get("rag", {}).get("taught_vocabulary"):
            validation_result["missing_context"].append("RAG: vocabulário já ensinado")
    
    elif content_type == "sentences":
        if not context_data.get("vocabulary"):
            validation_result["errors"].append("Vocabulário é obrigatório para gerar sentences")
            validation_result["valid"] = False
    
    elif content_type in ["tips", "grammar"]:
        if not context_data.get("vocabulary"):
            validation_result["errors"].append("Vocabulário é obrigatório para estratégias")
            validation_result["valid"] = False
        
        if not context_data.get("strategy"):
            validation_result["warnings"].append("Estratégia não especificada, será selecionada automaticamente")
    
    elif content_type == "assessments":
        required_content = ["vocabulary", "sentences"]
        for content in required_content:
            if not context_data.get("content", {}).get(content):
                validation_result["warnings"].append(f"Conteúdo faltante para assessments: {content}")
    
    return validation_result


# Instância global do serviço
prompt_generator = PromptGeneratorService()