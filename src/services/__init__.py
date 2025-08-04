# src/services/__init__.py
"""
IVO V2 - Intelligent Vocabulary Organizer Services Hub
Centralização de todos os serviços do sistema hierárquico Course → Book → Unit.

ATUALIZAÇÃO DE MIGRAÇÃO:
✅ ADICIONADO: ImageAnalysisService (migrado de MCP)
✅ FUNÇÃO DE COMPATIBILIDADE: analyze_images_for_unit_creation mantida

Este módulo fornece acesso unificado a todos os serviços do IVO V2:
- VocabularyGeneratorService: Geração de vocabulário com RAG e análise de imagens
- SentencesGeneratorService: Geração de sentences conectadas ao vocabulário
- TipsGeneratorService: Estratégias TIPS (6 estratégias lexicais)
- GrammarGenerator: Estratégias GRAMMAR (explicação sistemática + prevenção L1→L2)
- QAGeneratorService: Q&A baseado na Taxonomia de Bloom
- AssessmentSelectorService: Seleção inteligente de atividades (7 tipos)
- AimDetectorService: Detecção e geração de objetivos pedagógicos
- HierarchicalDatabaseService: Operações de banco com hierarquia
- L1InterferenceAnalyzer: Análise de interferência português→inglês
- PromptGeneratorService: Geração centralizada de prompts
- ImageAnalysisService: Análise de imagens (MIGRADO DE MCP) ✅

Arquitetura: LangChain 0.3 + Pydantic 2 + IA contextual + RAG hierárquico
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# =============================================================================
# IMPORTS DOS SERVIÇOS PRINCIPAIS
# =============================================================================

# Serviços de Geração de Conteúdo
from .vocabulary_generator import VocabularyGeneratorService
from .sentences_generator import SentencesGeneratorService  
from .tips_generator import TipsGeneratorService
from .grammar_generator import GrammarGenerator
from .qa_generator import QAGeneratorService

# Serviços de Seleção e Análise
from .assessment_selector import AssessmentSelectorService
from .aim_detector import AimDetectorService
from .l1_interference import L1InterferenceAnalyzer

# ✅ MIGRAÇÃO MCP → SERVICE: Import do novo service
from .image_analysis_service import ImageAnalysisService, analyze_images_for_unit_creation

# Serviços de Infraestrutura
from .hierarchical_database import HierarchicalDatabaseService, hierarchical_db
from .prompt_generator import PromptGeneratorService

# =============================================================================
# IMPORTS DAS FUNÇÕES UTILITÁRIAS
# =============================================================================

# Vocabulary Utils
#from .vocabulary_generator import (
    # Funções utilitári#as mantidas do arquivo original)

# Sentences Utils  
from .sentences_generator import (
    generate_sentences_for_unit_creation
)

# Tips Utils
from .tips_generator import (
    validate_tips_strategy_selection_ai,
    analyze_tips_effectiveness_ai,
    generate_strategy_recommendations_ai
)

# Grammar Utils
from .grammar_generator import (
    generate_grammar
)

# QA Utils
from .qa_generator import (
    generate_qa_for_unit_async,
    enhance_existing_qa,
    create_qa_quality_report,
    validate_qa_structure,
    analyze_cognitive_complexity,
    generate_pronunciation_questions
)

# Assessment Utils
from .assessment_selector import (
    select_assessments_for_unit_creation,
    analyze_assessment_balance_ai,
    calculate_assessment_distribution_metrics,
    get_assessment_recommendations_for_cefr,
    create_assessment_variety_report
)

# Aim Detection Utils
from .aim_detector import (
    detect_unit_aims,
    validate_aims_quality,
    analyze_aims_bloom_distribution,
    create_aims_summary_report,
    extract_measurable_outcomes,
    suggest_aims_improvement,
    validate_aims_cefr_alignment
)

# L1 Interference Utils
from .l1_interference import (
    analyze_text_for_l1_interference,
    create_l1_interference_report,
    l1_interference_analyzer
)

logger = logging.getLogger(__name__)


# =============================================================================
# REGISTRY DE SERVIÇOS (ATUALIZADO)
# =============================================================================

class ServiceRegistry:
    """Registry centralizado de todos os serviços do IVO V2."""
    
    def __init__(self):
        """Inicializar registry com instâncias dos serviços."""
        self._services = {}
        self._initialized = False
        
    async def initialize_services(self) -> None:
        """Inicializar todos os serviços do IVO V2."""
        if self._initialized:
            return
            
        try:
            logger.info("🚀 Inicializando IVO V2 Services Hub (incluindo ImageAnalysisService migrado)...")
            
            # Inicializar serviços principais
            self._services = {
                # Geração de Conteúdo
                "vocabulary": VocabularyGeneratorService(),
                "sentences": SentencesGeneratorService(),
                "tips": TipsGeneratorService(),
                "grammar": GrammarGenerator(),
                "qa": QAGeneratorService(),
                
                # Seleção e Análise
                "assessments": AssessmentSelectorService(),
                "aims": AimDetectorService(),
                "l1_interference": L1InterferenceAnalyzer(),
                
                # ✅ MIGRAÇÃO: Adicionar ImageAnalysisService
                "image_analysis": ImageAnalysisService(),
                
                # Infraestrutura
                "database": hierarchical_db,  # Instância global já inicializada
                "prompts": PromptGeneratorService()
            }
            
            self._initialized = True
            
            # ✅ Log de confirmação da migração
            logger.info(f"✅ IVO V2 Services Hub inicializado com {len(self._services)} serviços")
            logger.info("🔄 MIGRAÇÃO CONCLUÍDA: ImageAnalysisService integrado (anteriormente MCP)")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização dos serviços: {str(e)}")
            raise
    
    def get_service(self, service_name: str):
        """Obter instância de um serviço específico."""
        if not self._initialized:
            raise RuntimeError("Services não inicializados. Chame initialize_services() primeiro.")
        
        service = self._services.get(service_name)
        if not service:
            available_services = list(self._services.keys())
            raise ValueError(f"Serviço '{service_name}' não encontrado. Disponíveis: {available_services}")
        
        return service
    
    def get_all_services(self) -> Dict[str, Any]:
        """Obter todas as instâncias de serviços."""
        if not self._initialized:
            raise RuntimeError("Services não inicializados. Chame initialize_services() primeiro.")
        
        return self._services.copy()
    
    async def get_services_status(self) -> Dict[str, Any]:
        """Obter status de todos os serviços."""
        if not self._initialized:
            return {"status": "not_initialized", "services": []}
        
        services_status = {}
        
        for service_name, service_instance in self._services.items():
            try:
                if hasattr(service_instance, 'get_service_status'):
                    status = await service_instance.get_service_status()
                else:
                    status = {"status": "active", "methods": dir(service_instance)}
                
                services_status[service_name] = status
                
            except Exception as e:
                services_status[service_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "hub_status": "active",
            "total_services": len(self._services),
            "initialized_at": datetime.now().isoformat(),
            "services": services_status,
            "migration_info": {
                "mcp_to_service_migration": "completed",
                "image_analysis_service": "integrated",
                "backward_compatibility": "maintained"
            }
        }


# Instância global do registry
service_registry = ServiceRegistry()


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA PARA ACESSO DIRETO (ATUALIZADO)
# =============================================================================

async def get_vocabulary_service() -> VocabularyGeneratorService:
    """Obter serviço de geração de vocabulário."""
    await service_registry.initialize_services()
    return service_registry.get_service("vocabulary")

async def get_sentences_service() -> SentencesGeneratorService:
    """Obter serviço de geração de sentences."""
    await service_registry.initialize_services()
    return service_registry.get_service("sentences")

async def get_tips_service() -> TipsGeneratorService:
    """Obter serviço de estratégias TIPS."""
    await service_registry.initialize_services()
    return service_registry.get_service("tips")

async def get_grammar_service() -> GrammarGenerator:
    """Obter serviço de geração de gramática."""
    await service_registry.initialize_services()
    return service_registry.get_service("grammar")

async def get_qa_service() -> QAGeneratorService:
    """Obter serviço de geração de Q&A."""
    await service_registry.initialize_services()
    return service_registry.get_service("qa")

async def get_assessments_service() -> AssessmentSelectorService:
    """Obter serviço de seleção de atividades."""
    await service_registry.initialize_services()
    return service_registry.get_service("assessments")

async def get_aims_service() -> AimDetectorService:
    """Obter serviço de detecção de objetivos."""
    await service_registry.initialize_services()
    return service_registry.get_service("aims")

async def get_l1_service() -> L1InterferenceAnalyzer:
    """Obter serviço de análise L1 (português→inglês)."""
    await service_registry.initialize_services()
    return service_registry.get_service("l1_interference")

# ✅ NOVA FUNÇÃO: Acesso ao service de análise de imagens
async def get_image_analysis_service() -> ImageAnalysisService:
    """Obter serviço de análise de imagens (migrado de MCP)."""
    await service_registry.initialize_services()
    return service_registry.get_service("image_analysis")

async def get_database_service() -> HierarchicalDatabaseService:
    """Obter serviço de banco hierárquico."""
    await service_registry.initialize_services()
    return service_registry.get_service("database")

async def get_prompts_service() -> PromptGeneratorService:
    """Obter serviço de geração de prompts."""
    await service_registry.initialize_services()
    return service_registry.get_service("prompts")


# =============================================================================
# PIPELINE DE GERAÇÃO HIERÁRQUICA (SEM MUDANÇAS)
# =============================================================================

class ContentGenerationPipeline:
    """Pipeline para geração sequencial de conteúdo de unidade."""
    
    def __init__(self):
        self.services = service_registry
        
    async def generate_complete_unit_content(
        self,
        unit_data: Dict[str, Any],
        hierarchy_context: Dict[str, Any],
        rag_context: Dict[str, Any],
        images_analysis: Dict[str, Any] = None,
        generate_options: Dict[str, bool] = None
    ) -> Dict[str, Any]:
        """
        Gerar conteúdo completo de uma unidade seguindo o pipeline IVO V2.
        
        Pipeline: Aims → Vocabulary → Sentences → Tips/Grammar → Assessments → QA
        
        ✅ MIGRAÇÃO: images_analysis agora usa ImageAnalysisService integrado
        """
        await self.services.initialize_services()
        
        # Opções padrão de geração
        if generate_options is None:
            generate_options = {
                "generate_aims": True,
                "generate_vocabulary": True,
                "generate_sentences": True,
                "generate_strategy": True,  # TIPS ou GRAMMAR
                "generate_assessments": True,
                "generate_qa": True
            }
        
        result = {
            "unit_data": unit_data,
            "generation_pipeline": "complete",
            "generated_content": {},
            "generation_order": [],
            "generation_time": {},
            "success": True,
            "errors": [],
            "migration_notes": {
                "image_analysis": "Now using integrated ImageAnalysisService (migrated from MCP)"
            }
        }
        
        try:
            # 1. AIMS - Detectar objetivos pedagógicos
            if generate_options.get("generate_aims", True):
                start_time = datetime.now()
                
                aims_service = self.services.get_service("aims")
                aims_params = {
                    "unit_data": unit_data,
                    "content_data": {},  # Vazio na primeira etapa
                    "hierarchy_context": hierarchy_context,
                    "rag_context": rag_context,
                    "images_analysis": images_analysis or {}
                }
                
                aims_content = await aims_service.detect_and_generate_aims(aims_params)
                result["generated_content"]["aims"] = aims_content.dict()
                result["generation_order"].append("aims")
                result["generation_time"]["aims"] = (datetime.now() - start_time).total_seconds()
                
                logger.info("✅ Aims gerados via pipeline")
            
            # 2. VOCABULARY - Gerar vocabulário contextual
            if generate_options.get("generate_vocabulary", True):
                start_time = datetime.now()
                
                vocab_service = self.services.get_service("vocabulary")
                vocab_params = {
                    "unit_data": unit_data,
                    "hierarchy_context": hierarchy_context,
                    "rag_context": rag_context,
                    "images_analysis": images_analysis or {},
                    "target_vocabulary_count": 25
                }
                
                vocabulary_content = await vocab_service.generate_vocabulary_for_unit(vocab_params)
                result["generated_content"]["vocabulary"] = vocabulary_content.dict()
                result["generation_order"].append("vocabulary")
                result["generation_time"]["vocabulary"] = (datetime.now() - start_time).total_seconds()
                
                logger.info("✅ Vocabulary gerado via pipeline")
            
            # 3. SENTENCES - Gerar sentences conectadas
            if generate_options.get("generate_sentences", True):
                start_time = datetime.now()
                
                sentences_service = self.services.get_service("sentences")
                sentences_params = {
                    "unit_data": unit_data,
                    "vocabulary_data": result["generated_content"].get("vocabulary", {}),
                    "hierarchy_context": hierarchy_context,
                    "rag_context": rag_context,
                    "target_sentences": 12
                }
                
                sentences_content = await sentences_service.generate_sentences_for_unit(sentences_params)
                result["generated_content"]["sentences"] = sentences_content.dict()
                result["generation_order"].append("sentences")
                result["generation_time"]["sentences"] = (datetime.now() - start_time).total_seconds()
                
                logger.info("✅ Sentences geradas via pipeline")
            
            # 4. STRATEGY - Gerar TIPS ou GRAMMAR
            if generate_options.get("generate_strategy", True):
                start_time = datetime.now()
                
                unit_type = unit_data.get("unit_type", "lexical_unit")
                
                if unit_type == "lexical_unit":
                    # Gerar TIPS
                    tips_service = self.services.get_service("tips")
                    tips_params = {
                        "unit_data": unit_data,
                        "content_data": result["generated_content"],
                        "hierarchy_context": hierarchy_context,
                        "rag_context": rag_context
                    }
                    
                    tips_content = await tips_service.generate_tips_for_unit(tips_params)
                    result["generated_content"]["tips"] = tips_content.dict()
                    result["generation_order"].append("tips")
                    
                else:
                    # Gerar GRAMMAR
                    grammar_service = self.services.get_service("grammar")
                    grammar_params = {
                        "input_text": " ".join([s.get("text", "") for s in result["generated_content"].get("sentences", {}).get("sentences", [])]),
                        "vocabulary_list": [item.get("word", "") for item in result["generated_content"].get("vocabulary", {}).get("items", [])],
                        "level": unit_data.get("cefr_level", "A2"),
                        "variant": unit_data.get("language_variant", "american"),
                        "unit_context": unit_data.get("context", ""),
                        "strategy": "systematic",  # ou "l1_prevention" baseado em análise
                        "rag_context": rag_context
                    }
                    
                    grammar_content = await grammar_service.generate_grammar_content(grammar_params)
                    result["generated_content"]["grammar"] = grammar_content.__dict__
                    result["generation_order"].append("grammar")
                
                result["generation_time"]["strategy"] = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ Strategy ({unit_type}) gerada via pipeline")
            
            # 5. ASSESSMENTS - Selecionar atividades
            if generate_options.get("generate_assessments", True):
                start_time = datetime.now()
                
                assessments_service = self.services.get_service("assessments")
                assessments_params = {
                    "unit_data": unit_data,
                    "content_data": result["generated_content"],
                    "hierarchy_context": hierarchy_context,
                    "rag_context": rag_context
                }
                
                assessments_content = await assessments_service.select_optimal_assessments(assessments_params)
                result["generated_content"]["assessments"] = assessments_content.dict()
                result["generation_order"].append("assessments")
                result["generation_time"]["assessments"] = (datetime.now() - start_time).total_seconds()
                
                logger.info("✅ Assessments selecionadas via pipeline")
            
            # 6. QA - Gerar perguntas e respostas
            if generate_options.get("generate_qa", True):
                start_time = datetime.now()
                
                qa_service = self.services.get_service("qa")
                qa_params = {
                    "unit_data": unit_data,
                    "content_data": result["generated_content"],
                    "hierarchy_context": hierarchy_context,
                    "pedagogical_context": {
                        "learning_objectives": result["generated_content"].get("aims", {}).get("subsidiary_aims", []),
                        "progression_level": rag_context.get("progression_level", "intermediate")
                    }
                }
                
                qa_content = await qa_service.generate_qa_for_unit(qa_params)
                result["generated_content"]["qa"] = qa_content.dict()
                result["generation_order"].append("qa")
                result["generation_time"]["qa"] = (datetime.now() - start_time).total_seconds()
                
                logger.info("✅ QA gerado via pipeline")
            
            # Calcular tempo total
            total_time = sum(result["generation_time"].values())
            result["total_generation_time"] = total_time
            
            logger.info(f"🎉 Pipeline completo: {len(result['generation_order'])} componentes em {total_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Erro no pipeline de geração: {str(e)}")
            result["success"] = False
            result["errors"].append(str(e))
            
        return result


# Instância global do pipeline
content_pipeline = ContentGenerationPipeline()


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA PARA PIPELINE (ATUALIZADO)
# =============================================================================

async def generate_complete_unit(
    unit_data: Dict[str, Any],
    hierarchy_context: Dict[str, Any],
    rag_context: Dict[str, Any],
    images_analysis: Dict[str, Any] = None,
    generate_options: Dict[str, bool] = None
) -> Dict[str, Any]:
    """Função de conveniência para gerar unidade completa."""
    return await content_pipeline.generate_complete_unit_content(
        unit_data, hierarchy_context, rag_context, images_analysis, generate_options
    )

async def generate_vocabulary_only(
    unit_data: Dict[str, Any],
    hierarchy_context: Dict[str, Any],
    rag_context: Dict[str, Any],
    images_analysis: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Função de conveniência para gerar apenas vocabulário."""
    vocab_service = await get_vocabulary_service()
    
    vocab_params = {
        "unit_data": unit_data,
        "hierarchy_context": hierarchy_context,
        "rag_context": rag_context,
        "images_analysis": images_analysis or {},
        "target_vocabulary_count": 25
    }
    
    vocabulary_content = await vocab_service.generate_vocabulary_for_unit(vocab_params)
    return {"vocabulary": vocabulary_content.dict()}

async def generate_sentences_only(
    unit_data: Dict[str, Any],
    vocabulary_data: Dict[str, Any],
    hierarchy_context: Dict[str, Any],
    rag_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Função de conveniência para gerar apenas sentences."""
    sentences_service = await get_sentences_service()
    
    sentences_params = {
        "unit_data": unit_data,
        "vocabulary_data": vocabulary_data,
        "hierarchy_context": hierarchy_context,
        "rag_context": rag_context,
        "target_sentences": 12
    }
    
    sentences_content = await sentences_service.generate_sentences_for_unit(sentences_params)
    return {"sentences": sentences_content.dict()}

# ✅ NOVA FUNÇÃO: Análise de imagens integrada
async def analyze_images_only(
    image_files_b64: List[str],
    context: str,
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> Dict[str, Any]:
    """Função de conveniência para análise de imagens usando service integrado."""
    image_service = await get_image_analysis_service()
    
    return await image_service.analyze_images_for_vocabulary(
        image_files_b64, context, cefr_level, unit_type
    )


# =============================================================================
# STATUS E INFORMAÇÕES DO HUB (ATUALIZADO)
# =============================================================================

async def get_services_hub_status() -> Dict[str, Any]:
    """Obter status completo do hub de serviços."""
    return await service_registry.get_services_status()

async def initialize_all_services() -> None:
    """Inicializar todos os serviços do IVO V2."""
    await service_registry.initialize_services()

def get_available_services() -> List[str]:
    """Obter lista de serviços disponíveis."""
    return [
        "vocabulary",        # VocabularyGeneratorService
        "sentences",         # SentencesGeneratorService
        "tips",             # TipsGeneratorService
        "grammar",          # GrammarGenerator
        "qa",               # QAGeneratorService
        "assessments",      # AssessmentSelectorService
        "aims",             # AimDetectorService
        "l1_interference",  # L1InterferenceAnalyzer
        "image_analysis",   # ImageAnalysisService ✅ NOVO
        "database",         # HierarchicalDatabaseService
        "prompts"           # PromptGeneratorService
    ]

def get_pipeline_steps() -> List[str]:
    """Obter ordem de steps do pipeline de geração."""
    return [
        "aims",          # 1. Detectar objetivos pedagógicos
        "vocabulary",    # 2. Gerar vocabulário contextual
        "sentences",     # 3. Gerar sentences conectadas
        "strategy",      # 4. Aplicar TIPS ou GRAMMAR
        "assessments",   # 5. Selecionar atividades
        "qa"            # 6. Gerar Q&A pedagógico
    ]


# =============================================================================
# EXPORTS PRINCIPAIS (ATUALIZADO)
# =============================================================================

__all__ = [
    # Classes de Serviços
    "VocabularyGeneratorService",
    "SentencesGeneratorService", 
    "TipsGeneratorService",
    "GrammarGenerator",
    "QAGeneratorService",
    "AssessmentSelectorService",
    "AimDetectorService",
    "L1InterferenceAnalyzer",
    "HierarchicalDatabaseService",
    "PromptGeneratorService",
    "ImageAnalysisService",  # ✅ ADICIONADO
    
    # Registry e Pipeline
    "ServiceRegistry",
    "ContentGenerationPipeline",
    "service_registry",
    "content_pipeline",
    
    # Funções de Acesso Direto
    "get_vocabulary_service",
    "get_sentences_service",
    "get_tips_service", 
    "get_grammar_service",
    "get_qa_service",
    "get_assessments_service",
    "get_aims_service",
    "get_l1_service",
    "get_database_service",
    "get_prompts_service",
    "get_image_analysis_service",  # ✅ ADICIONADO
    
    # Pipeline Functions
    "generate_complete_unit",
    "generate_vocabulary_only",
    "generate_sentences_only",
    "analyze_images_only",  # ✅ ADICIONADO
    
    # Utility Functions
    "get_services_hub_status",
    "initialize_all_services",
    "get_available_services",
    "get_pipeline_steps",
    
    # Instância Global do Database
    "hierarchical_db",
    
    # ✅ FUNÇÃO DE COMPATIBILIDADE MANTIDA
    "analyze_images_for_unit_creation",
    
    # Utils Re-exports
    "generate_sentences_for_unit_creation",
    "validate_tips_strategy_selection_ai",
    "analyze_tips_effectiveness_ai",
    "generate_strategy_recommendations_ai",
    "generate_grammar",
    "generate_qa_for_unit_async",
    "enhance_existing_qa",
    "create_qa_quality_report",
    "validate_qa_structure",
    "analyze_cognitive_complexity",
    "generate_pronunciation_questions",
    "select_assessments_for_unit_creation",
    "analyze_assessment_balance_ai",
    "calculate_assessment_distribution_metrics",
    "get_assessment_recommendations_for_cefr",
    "create_assessment_variety_report",
    "detect_unit_aims",
    "validate_aims_quality",
    "analyze_aims_bloom_distribution",
    "create_aims_summary_report",
    "extract_measurable_outcomes",
    "suggest_aims_improvement",
    "validate_aims_cefr_alignment",
    "analyze_text_for_l1_interference",
    "create_l1_interference_report",
    "l1_interference_analyzer"
]


# =============================================================================
# INICIALIZAÇÃO AUTOMÁTICA (ATUALIZADO)
# =============================================================================

logger.info("📦 IVO V2 Services Hub carregado - todos os serviços disponíveis")
logger.info(f"🔧 Serviços disponíveis: {', '.join(get_available_services())}")
logger.info(f"🚀 Pipeline steps: {' → '.join(get_pipeline_steps())}")
logger.info("🔄 MIGRAÇÃO MCP→SERVICE: ImageAnalysisService integrado com sucesso")
logger.info("✅ COMPATIBILIDADE: analyze_images_for_unit_creation() mantida")
logger.info("💡 Use initialize_all_services() para inicializar ou acesse serviços individuais via get_*_service()")