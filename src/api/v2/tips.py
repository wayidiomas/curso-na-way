# src/api/v2/tips.py
"""
Endpoints para geração de estratégias TIPS para unidades lexicais.
Implementação das 6 estratégias TIPS do IVO V2 Guide.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import time

from src.services.hierarchical_database import hierarchical_db
from src.services.tips_generator import TipsGeneratorService
from src.core.unit_models import (
    SuccessResponse, ErrorResponse, TipsContent
)
from src.core.enums import (
    CEFRLevel, LanguageVariant, UnitType, TipStrategy
)
from src.core.audit_logger import (
    audit_logger_instance, AuditEventType, audit_endpoint, extract_unit_info
)
from src.core.rate_limiter import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


async def rate_limit_tips_generation(request):
    """Rate limiting específico para geração de TIPS."""
    await rate_limit_dependency(request, "generate_content")


@router.post("/units/{unit_id}/tips", response_model=SuccessResponse)
@audit_endpoint(AuditEventType.UNIT_CONTENT_GENERATED, extract_unit_info)
async def generate_tips_for_unit(
    unit_id: str,
    request: Request,
    _: None = Depends(rate_limit_tips_generation)
):
    """
    Gerar estratégias TIPS para unidade lexical com seleção inteligente.
    
    Flow do IVO V2:
    1. Buscar unidade e validar que é lexical_unit
    2. Verificar se possui vocabulário e sentences
    3. Usar RAG para seleção da estratégia TIPS adequada
    4. Aplicar uma das 6 estratégias TIPS baseada no vocabulário
    5. Gerar conteúdo específico da estratégia
    6. Salvar e atualizar status da unidade
    """
    try:
        logger.info(f"Iniciando geração de TIPS para unidade: {unit_id}")
        
        # 1. Buscar e validar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # 2. Verificar se é unidade lexical
        if unit.unit_type.value != "lexical_unit":
            raise HTTPException(
                status_code=400,
                detail=f"TIPS são apenas para unidades lexicais. Esta unidade é {unit.unit_type.value}. Use /grammar para unidades gramaticais."
            )
        
        # 3. Verificar status adequado
        if unit.status.value not in ["content_pending"]:
            if unit.status.value in ["creating", "vocab_pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Unidade deve ter vocabulário e sentences antes de gerar TIPS."
                )
            elif unit.tips:
                logger.info(f"Unidade {unit_id} já possui TIPS - regenerando")
        
        # 4. Verificar pré-requisitos
        if not unit.vocabulary or not unit.vocabulary.get("items"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter vocabulário antes de gerar TIPS."
            )
        
        if not unit.sentences or not unit.sentences.get("sentences"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter sentences antes de gerar TIPS."
            )
        
        # 5. Buscar contexto da hierarquia
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        if not course or not book:
            raise HTTPException(
                status_code=400,
                detail="Hierarquia inválida: curso ou book não encontrado"
            )
        
        # 6. Buscar contexto RAG para seleção da estratégia
        logger.info("Coletando contexto RAG para seleção inteligente de estratégia TIPS...")
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # 7. Preparar dados para seleção e geração
        tips_params = {
            "unit_id": unit_id,
            "unit_data": {
                "title": unit.title,
                "context": unit.context,
                "cefr_level": unit.cefr_level.value,
                "language_variant": unit.language_variant.value,
                "unit_type": unit.unit_type.value,
                "main_aim": unit.main_aim,
                "subsidiary_aims": unit.subsidiary_aims
            },
            "content_data": {
                "vocabulary": unit.vocabulary,
                "sentences": unit.sentences
            },
            "hierarchy_context": {
                "course_name": course.name,
                "book_name": book.name,
                "sequence_order": unit.sequence_order,
                "target_level": book.target_level.value
            },
            "rag_context": {
                "used_strategies": used_strategies,
                "taught_vocabulary": taught_vocabulary,
                "progression_level": _determine_progression_level(unit.sequence_order),
                "strategy_density": len(used_strategies) / max(unit.sequence_order, 1)
            }
        }
        
        # 8. Gerar TIPS usando service
        start_time = time.time()
        tips_generator = TipsGeneratorService()
        
        tips_content = await tips_generator.generate_tips_for_unit(tips_params)
        
        generation_time = time.time() - start_time
        
        # 9. Salvar TIPS na unidade
        await hierarchical_db.update_unit_content(
            unit_id, 
            "tips", 
            tips_content.dict()
        )
        
        # 10. Atualizar lista de estratégias usadas
        strategy_name = tips_content.strategy.value
        current_strategies = unit.strategies_used or []
        updated_strategies = current_strategies + [strategy_name]
        
        await hierarchical_db.update_unit_content(
            unit_id,
            "strategies_used",
            updated_strategies
        )
        
        # 11. Atualizar status da unidade
        await hierarchical_db.update_unit_status(unit_id, "assessments_pending")
        
        # 12. Log de auditoria
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="tips",
            unit_id=unit_id,
            book_id=unit.book_id,
            course_id=unit.course_id,
            content_stats={
                "strategy_selected": strategy_name,
                "vocabulary_coverage": len(tips_content.vocabulary_coverage),
                "examples_count": len(tips_content.examples),
                "practice_suggestions": len(tips_content.practice_suggestions),
                "memory_techniques": len(tips_content.memory_techniques),
                "selection_rationale": tips_content.selection_rationale
            },
            ai_usage={
                "model": "gpt-4o-mini",
                "generation_time": generation_time,
                "strategy_selection_algorithm": "rag_based_intelligent_selection"
            },
            processing_time=generation_time,
            success=True
        )
        
        return SuccessResponse(
            data={
                "tips": tips_content.dict(),
                "generation_stats": {
                    "strategy_selected": strategy_name,
                    "vocabulary_coverage": len(tips_content.vocabulary_coverage),
                    "total_examples": len(tips_content.examples),
                    "practice_suggestions": len(tips_content.practice_suggestions),
                    "processing_time": f"{generation_time:.2f}s"
                },
                "unit_progression": {
                    "unit_id": unit_id,
                    "previous_status": unit.status.value,
                    "new_status": "assessments_pending",
                    "next_step": "Gerar assessments para finalizar a unidade"
                },
                "strategy_analysis": {
                    "selected_strategy": strategy_name,
                    "selection_rationale": tips_content.selection_rationale,
                    "used_strategies_context": used_strategies,
                    "complementary_strategies": tips_content.complementary_strategies,
                    "phonetic_focus": tips_content.phonetic_focus
                }
            },
            message=f"Estratégia TIPS '{strategy_name}' gerada com sucesso para unidade '{unit.title}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Gerar assessments para finalizar",
                f"POST /api/v2/units/{unit_id}/assessments",
                "Verificar estratégia aplicada",
                f"GET /api/v2/units/{unit_id}/tips",
                "Analisar qualidade da estratégia",
                f"GET /api/v2/units/{unit_id}/tips/analysis"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar TIPS para unidade {unit_id}: {str(e)}")
        
        # Log de erro
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="tips",
            unit_id=unit_id,
            book_id=getattr(unit, 'book_id', ''),
            course_id=getattr(unit, 'course_id', ''),
            success=False,
            error_details=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno na geração de TIPS: {str(e)}"
        )


@router.get("/units/{unit_id}/tips", response_model=SuccessResponse)
async def get_unit_tips(unit_id: str, request: Request):
    """Obter estratégias TIPS da unidade."""
    try:
        logger.info(f"Buscando TIPS da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade lexical
        if unit.unit_type.value != "lexical_unit":
            raise HTTPException(
                status_code=400,
                detail=f"Esta unidade é {unit.unit_type.value}. TIPS são apenas para unidades lexicais."
            )
        
        # Verificar se possui TIPS
        if not unit.tips:
            return SuccessResponse(
                data={
                    "has_tips": False,
                    "unit_status": unit.status.value,
                    "unit_type": unit.unit_type.value,
                    "message": "Unidade ainda não possui estratégias TIPS geradas",
                    "prerequisites": {
                        "has_vocabulary": bool(unit.vocabulary),
                        "has_sentences": bool(unit.sentences),
                        "is_lexical_unit": unit.unit_type.value == "lexical_unit"
                    }
                },
                message="TIPS não encontradas",
                hierarchy_info={
                    "course_id": unit.course_id,
                    "book_id": unit.book_id,
                    "unit_id": unit_id,
                    "sequence": unit.sequence_order
                },
                next_suggested_actions=[
                    "Gerar estratégias TIPS",
                    f"POST /api/v2/units/{unit_id}/tips"
                ]
            )
        
        # Buscar contexto adicional
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        # Análise das TIPS
        tips_data = unit.tips
        
        return SuccessResponse(
            data={
                "tips": tips_data,
                "analysis": {
                    "strategy_used": tips_data.get("strategy", "unknown"),
                    "vocabulary_coverage": len(tips_data.get("vocabulary_coverage", [])),
                    "examples_count": len(tips_data.get("examples", [])),
                    "practice_suggestions_count": len(tips_data.get("practice_suggestions", [])),
                    "memory_techniques_count": len(tips_data.get("memory_techniques", [])),
                    "phonetic_focus": tips_data.get("phonetic_focus", []),
                    "pronunciation_tips": tips_data.get("pronunciation_tips", [])
                },
                "unit_context": {
                    "unit_title": unit.title,
                    "unit_type": unit.unit_type.value,
                    "cefr_level": unit.cefr_level.value,
                    "unit_status": unit.status.value,
                    "course_name": course.name if course else None,
                    "book_name": book.name if book else None,
                    "sequence_order": unit.sequence_order
                },
                "strategy_context": {
                    "selection_rationale": tips_data.get("selection_rationale", ""),
                    "complementary_strategies": tips_data.get("complementary_strategies", []),
                    "vocabulary_integration": tips_data.get("vocabulary_coverage", [])
                },
                "has_tips": True
            },
            message=f"Estratégias TIPS da unidade '{unit.title}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar TIPS da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}/tips", response_model=SuccessResponse)
async def update_unit_tips(
    unit_id: str,
    tips_data: Dict[str, Any],
    request: Request,
    _: None = Depends(rate_limit_tips_generation)
):
    """Atualizar estratégias TIPS da unidade (edição manual)."""
    try:
        logger.info(f"Atualizando TIPS da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade lexical
        if unit.unit_type.value != "lexical_unit":
            raise HTTPException(
                status_code=400,
                detail="TIPS são apenas para unidades lexicais"
            )
        
        # Validar estrutura básica dos dados
        if not isinstance(tips_data, dict):
            raise HTTPException(
                status_code=400,
                detail="Dados de TIPS devem ser um objeto JSON"
            )
        
        required_fields = ["strategy", "title", "explanation", "examples"]
        for field in required_fields:
            if field not in tips_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo obrigatório ausente: {field}"
                )
        
        # Validar estratégia
        valid_strategies = [strategy.value for strategy in TipStrategy]
        if tips_data["strategy"] not in valid_strategies:
            raise HTTPException(
                status_code=400,
                detail=f"Estratégia inválida. Deve ser uma de: {valid_strategies}"
            )
        
        # Atualizar timestamps
        tips_data["updated_at"] = time.time()
        
        # Salvar no banco
        await hierarchical_db.update_unit_content(unit_id, "tips", tips_data)
        
        # Atualizar estratégias usadas
        strategy_name = tips_data["strategy"]
        current_strategies = unit.strategies_used or []
        if strategy_name not in current_strategies:
            updated_strategies = current_strategies + [strategy_name]
            await hierarchical_db.update_unit_content(unit_id, "strategies_used", updated_strategies)
        
        # Log da atualização
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "tips_manual_edit",
                "strategy": strategy_name,
                "unit_id": unit_id
            }
        )
        
        return SuccessResponse(
            data={
                "updated": True,
                "tips": tips_data,
                "update_stats": {
                    "strategy": strategy_name,
                    "examples_count": len(tips_data.get("examples", [])),
                    "update_timestamp": tips_data["updated_at"]
                }
            },
            message=f"Estratégias TIPS atualizadas com sucesso",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar TIPS da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/units/{unit_id}/tips", response_model=SuccessResponse)
async def delete_unit_tips(unit_id: str, request: Request):
    """Deletar estratégias TIPS da unidade."""
    try:
        logger.warning(f"Deletando TIPS da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui TIPS
        if not unit.tips:
            return SuccessResponse(
                data={
                    "deleted": False,
                    "message": "Unidade não possui TIPS para deletar"
                },
                message="Nenhuma estratégia TIPS encontrada para deletar"
            )
        
        # Obter estratégia para remover da lista
        strategy_to_remove = unit.tips.get("strategy")
        
        # Deletar TIPS (setar como None)
        await hierarchical_db.update_unit_content(unit_id, "tips", None)
        
        # Remover da lista de estratégias usadas
        if strategy_to_remove and unit.strategies_used:
            updated_strategies = [s for s in unit.strategies_used if s != strategy_to_remove]
            await hierarchical_db.update_unit_content(unit_id, "strategies_used", updated_strategies)
        
        # Ajustar status se necessário
        if unit.status.value in ["assessments_pending", "completed"]:
            await hierarchical_db.update_unit_status(unit_id, "content_pending")
        
        # Log da deleção
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "tips_deleted",
                "unit_id": unit_id,
                "previous_strategy": strategy_to_remove
            }
        )
        
        return SuccessResponse(
            data={
                "deleted": True,
                "previous_strategy": strategy_to_remove,
                "new_status": "content_pending"
            },
            message="Estratégias TIPS deletadas com sucesso",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Regenerar estratégias TIPS",
                f"POST /api/v2/units/{unit_id}/tips"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar TIPS da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}/tips/analysis", response_model=SuccessResponse)
async def analyze_unit_tips(unit_id: str, request: Request):
    """Analisar qualidade e adequação das estratégias TIPS da unidade."""
    try:
        logger.info(f"Analisando TIPS da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade lexical
        if unit.unit_type.value != "lexical_unit":
            raise HTTPException(
                status_code=400,
                detail="Análise de TIPS é apenas para unidades lexicais"
            )
        
        # Verificar se possui TIPS
        if not unit.tips:
            raise HTTPException(
                status_code=400,
                detail="Unidade não possui TIPS para analisar"
            )
        
        # Buscar contexto RAG para comparação
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # Analisar TIPS
        tips_data = unit.tips
        
        analysis = {
            "strategy_analysis": _analyze_strategy_selection(tips_data, used_strategies),
            "content_quality": _analyze_tips_content_quality(tips_data),
            "vocabulary_integration": _analyze_vocabulary_integration(tips_data, unit.vocabulary),
            "pedagogical_effectiveness": _analyze_pedagogical_effectiveness(tips_data, unit.cefr_level.value),
            "phonetic_analysis": _analyze_phonetic_components(tips_data),
            "contextual_relevance": _analyze_contextual_relevance(tips_data, unit)
        }
        
        # Gerar recomendações
        recommendations = _generate_tips_recommendations(analysis, unit)
        
        return SuccessResponse(
            data={
                "analysis": analysis,
                "recommendations": recommendations,
                "summary": {
                    "strategy_used": tips_data.get("strategy"),
                    "overall_quality": _calculate_tips_quality(analysis),
                    "vocabulary_coverage": len(tips_data.get("vocabulary_coverage", [])),
                    "pedagogical_score": analysis["pedagogical_effectiveness"].get("effectiveness_score", 0),
                    "needs_improvement": len(recommendations) > 0
                }
            },
            message=f"Análise das estratégias TIPS da unidade '{unit.title}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar TIPS da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/tips/strategies", response_model=SuccessResponse)
async def get_tips_strategies_info(request: Request):
    """Obter informações sobre as 6 estratégias TIPS disponíveis."""
    try:
        strategies_info = {
            "afixacao": {
                "name": "TIP 1: Afixação",
                "description": "Ensino através de prefixos e sufixos",
                "when_to_use": "Vocabulário com padrões morfológicos claros",
                "examples": ["unsafe, illegal, teacher, quickly"],
                "benefit": "Expansão sistemática de vocabulário",
                "detection_criteria": "Palavras com prefixos/sufixos comuns",
                "cefr_levels": ["A2", "B1", "B2", "C1"],
                "phonetic_focus": "Stress patterns in derived words"
            },
            "substantivos_compostos": {
                "name": "TIP 2: Substantivos Compostos",
                "description": "Agrupamento de palavras compostas por tema",
                "when_to_use": "Palavras compostas do mesmo campo semântico",
                "examples": ["telephone → cellphone, telephone booth, telephone number"],
                "benefit": "Agrupamento temático eficiente",
                "detection_criteria": "Famílias de palavras compostas",
                "cefr_levels": ["A1", "A2", "B1"],
                "phonetic_focus": "Compound stress patterns"
            },
            "colocacoes": {
                "name": "TIP 3: Colocações",
                "description": "Combinações naturais de palavras",
                "when_to_use": "Combinações verbo+substantivo, adjetivo+substantivo",
                "examples": ["take a holiday, heavy rain, arrive at"],
                "benefit": "Naturalidade na comunicação",
                "detection_criteria": "Padrões de coocorrência",
                "cefr_levels": ["B1", "B2", "C1", "C2"],
                "phonetic_focus": "Rhythm in collocations"
            },
            "expressoes_fixas": {
                "name": "TIP 4: Expressões Fixas",
                "description": "Frases cristalizadas e fórmulas fixas",
                "when_to_use": "Frases que não podem ser alteradas",
                "examples": ["to tell you the truth, it's up to you"],
                "benefit": "Comunicação funcional automática",
                "detection_criteria": "Expressões não alteráveis",
                "cefr_levels": ["A2", "B1", "B2"],
                "phonetic_focus": "Intonation patterns in fixed expressions"
            },
            "idiomas": {
                "name": "TIP 5: Idiomas",
                "description": "Expressões com significado figurativo",
                "when_to_use": "Expressões idiomáticas e metafóricas",
                "examples": ["under the weather, green fingers"],
                "benefit": "Compreensão cultural e fluência",
                "detection_criteria": "Significado não-literal",
                "cefr_levels": ["B2", "C1", "C2"],
                "phonetic_focus": "Connected speech in idioms"
            },
            "chunks": {
                "name": "TIP 6: Chunks",
                "description": "Blocos funcionais de linguagem",
                "when_to_use": "Unidades funcionais completas",
                "examples": ["I'd like to..., How about...?, Let me think"],
                "benefit": "Fluência automática e memória de longo prazo",
                "detection_criteria": "Unidades funcionais completas",
                "cefr_levels": ["A1", "A2", "B1", "B2"],
                "phonetic_focus": "Rhythm and stress in chunks"
            }
        }
        
        return SuccessResponse(
            data={
                "strategies": strategies_info,
                "selection_logic": {
                    "total_available": 6,
                    "selection_criteria": [
                        "Vocabulary patterns in the unit",
                        "CEFR level appropriateness",
                        "Balance with previous strategies used",
                        "Phonetic complexity considerations",
                        "Contextual relevance to unit theme"
                    ]
                },
                "ivo_v2_approach": {
                    "intelligent_selection": "RAG-based strategy selection",
                    "variety_maintenance": "Avoid overuse of same strategy",
                    "vocabulary_integration": "Strategy aligns with unit vocabulary",
                    "phonetic_awareness": "Include pronunciation guidance"
                }
            },
            message="Informações sobre as 6 estratégias TIPS do IVO V2"
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter informações das estratégias TIPS: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _determine_progression_level(sequence_order: int) -> str:
    """Determinar nível de progressão baseado na sequência."""
    if sequence_order <= 3:
        return "basic_tips"
    elif sequence_order <= 7:
        return "intermediate_tips"
    else:
        return "advanced_tips"


def _analyze_strategy_selection(tips_data: Dict[str, Any], used_strategies: List[str]) -> Dict[str, Any]:
    """Analisar adequação da seleção da estratégia."""
    current_strategy = tips_data.get("strategy")
    strategy_count = used_strategies.count(current_strategy) if current_strategy else 0
    
    return {
        "selected_strategy": current_strategy,
        "usage_frequency": strategy_count,
        "is_overused": strategy_count > 2,  # Máximo 2 vezes por book
        "selection_rationale": tips_data.get("selection_rationale", ""),
        "complementary_strategies": tips_data.get("complementary_strategies", []),
        "strategy_diversity_score": len(set(used_strategies)) / 6 if used_strategies else 0
    }


def _analyze_tips_content_quality(tips_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar qualidade do conteúdo das TIPS."""
    examples = tips_data.get("examples", [])
    practice_suggestions = tips_data.get("practice_suggestions", [])
    
    return {
        "examples_count": len(examples),
        "practice_suggestions_count": len(practice_suggestions),
        "memory_techniques_count": len(tips_data.get("memory_techniques", [])),
        "phonetic_focus": tips_data.get("phonetic_focus", []),
        "pronunciation_tips": tips_data.get("pronunciation_tips", []),
        "content_quality_score": (len(examples) + len(practice_suggestions)) / 10  # Exemplo de pontuação
    }