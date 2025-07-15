# src/api/v2/tips.py
"""
Endpoints para geração de estratégias TIPS para unidades lexicais.
Implementação das 6 estratégias TIPS do IVO V2 Guide com seleção inteligente RAG.
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
        
        # 12. Log de auditoria - CORRIGIDO: tips_content ao invés de tips_data
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
                "selection_rationale": tips_content.selection_rationale,
                "complementary_strategies": tips_content.complementary_strategies,
                "strategy_diversity_score": len(set(used_strategies)) / 6 if used_strategies else 0
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


# CORRIGIDO: Removidas funções duplicadas _analyze_tips_content_quality, 
# _analyze_vocabulary_integration, _analyze_pedagogical_effectiveness,
# _analyze_phonetic_components, _analyze_contextual_relevance,
# _generate_tips_recommendations, _calculate_tips_quality, 
# _get_effectiveness_recommendations que estavam definidas duas vezes


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
# HELPER FUNCTIONS PARA TIPS.PY
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


def _analyze_vocabulary_integration(tips_data: Dict[str, Any], unit_vocabulary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analisar integração com vocabulário da unidade."""
    vocabulary_coverage = tips_data.get("vocabulary_coverage", [])
    
    if not unit_vocabulary or not unit_vocabulary.get("items"):
        return {
            "coverage_percentage": 0,
            "words_covered": 0,
            "total_vocabulary": 0,
            "integration_score": 0
        }
    
    unit_words = [item.get("word", "").lower() for item in unit_vocabulary.get("items", [])]
    covered_words = [word.lower() for word in vocabulary_coverage]
    
    words_covered = len([word for word in covered_words if word in unit_words])
    coverage_percentage = (words_covered / len(unit_words)) * 100 if unit_words else 0
    
    return {
        "coverage_percentage": coverage_percentage,
        "words_covered": words_covered,
        "total_vocabulary": len(unit_words),
        "integration_score": coverage_percentage / 100,
        "uncovered_words": [word for word in unit_words if word not in covered_words][:5]
    }


def _analyze_pedagogical_effectiveness(tips_data: Dict[str, Any], cefr_level: str) -> Dict[str, Any]:
    """Analisar eficácia pedagógica da estratégia."""
    strategy = tips_data.get("strategy", "")
    
    # Mapear eficácia por estratégia e nível
    strategy_effectiveness = {
        "afixacao": {"A1": 0.6, "A2": 0.8, "B1": 0.9, "B2": 0.8, "C1": 0.7, "C2": 0.6},
        "substantivos_compostos": {"A1": 0.9, "A2": 0.9, "B1": 0.8, "B2": 0.6, "C1": 0.5, "C2": 0.4},
        "colocacoes": {"A1": 0.3, "A2": 0.5, "B1": 0.8, "B2": 0.9, "C1": 0.9, "C2": 0.8},
        "expressoes_fixas": {"A1": 0.5, "A2": 0.8, "B1": 0.8, "B2": 0.7, "C1": 0.6, "C2": 0.5},
        "idiomas": {"A1": 0.2, "A2": 0.3, "B1": 0.5, "B2": 0.8, "C1": 0.9, "C2": 0.9},
        "chunks": {"A1": 0.9, "A2": 0.9, "B1": 0.8, "B2": 0.7, "C1": 0.6, "C2": 0.5}
    }
    
    effectiveness_score = strategy_effectiveness.get(strategy, {}).get(cefr_level, 0.7)
    
    return {
        "strategy": strategy,
        "cefr_level": cefr_level,
        "effectiveness_score": effectiveness_score,
        "is_appropriate": effectiveness_score >= 0.7,
        "recommendations": _get_effectiveness_recommendations(strategy, cefr_level, effectiveness_score)
    }


def _analyze_phonetic_components(tips_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar componentes fonéticos das TIPS."""
    phonetic_focus = tips_data.get("phonetic_focus", [])
    pronunciation_tips = tips_data.get("pronunciation_tips", [])
    
    return {
        "has_phonetic_focus": len(phonetic_focus) > 0,
        "phonetic_elements": phonetic_focus,
        "pronunciation_guidance": len(pronunciation_tips) > 0,
        "pronunciation_tips_count": len(pronunciation_tips),
        "phonetic_integration_score": (len(phonetic_focus) + len(pronunciation_tips)) / 10
    }


def _analyze_contextual_relevance(tips_data: Dict[str, Any], unit) -> Dict[str, Any]:
    """Analisar relevância contextual da estratégia."""
    strategy = tips_data.get("strategy", "")
    unit_context = unit.context or ""
    unit_title = unit.title or ""
    
    # Análise de palavras-chave do contexto
    context_keywords = unit_context.lower().split() + unit_title.lower().split()
    strategy_explanation = tips_data.get("explanation", "").lower()
    
    # Verificar alinhamento com contexto
    keyword_matches = sum(1 for keyword in context_keywords if keyword in strategy_explanation)
    context_alignment = keyword_matches / max(len(context_keywords), 1)
    
    return {
        "context_alignment_score": context_alignment,
        "strategy_fits_context": context_alignment > 0.3,
        "unit_context": unit_context,
        "strategy_explanation_length": len(strategy_explanation),
        "keyword_matches": keyword_matches
    }


def _generate_tips_recommendations(analysis: Dict[str, Any], unit) -> List[str]:
    """Gerar recomendações para melhorar TIPS."""
    recommendations = []
    
    # Análise de seleção de estratégia
    strategy_analysis = analysis["strategy_analysis"]
    if strategy_analysis["is_overused"]:
        recommendations.append(
            f"Estratégia '{strategy_analysis['selected_strategy']}' está sendo usada excessivamente "
            f"({strategy_analysis['usage_frequency']} vezes). Considere diversificar."
        )
    
    # Análise de qualidade de conteúdo
    content_quality = analysis["content_quality"]
    if content_quality["examples_count"] < 3:
        recommendations.append(
            f"Poucos exemplos ({content_quality['examples_count']}). Recomendado: pelo menos 3-5 exemplos."
        )
    
    if content_quality["practice_suggestions_count"] < 2:
        recommendations.append(
            "Adicione mais sugestões de prática para reforçar a estratégia."
        )
    
    # Análise de integração com vocabulário
    vocab_integration = analysis["vocabulary_integration"]
    if vocab_integration["coverage_percentage"] < 50:
        recommendations.append(
            f"Baixa integração com vocabulário da unidade ({vocab_integration['coverage_percentage']:.1f}%). "
            f"Considere incluir mais palavras do vocabulário da unidade."
        )
    
    # Análise de eficácia pedagógica
    pedagogical = analysis["pedagogical_effectiveness"]
    if not pedagogical["is_appropriate"]:
        recommendations.append(
            f"Estratégia pode não ser a mais adequada para nível {pedagogical['cefr_level']} "
            f"(eficácia: {pedagogical['effectiveness_score']:.1f}). "
            f"Considere: {', '.join(pedagogical['recommendations'])}"
        )
    
    # Análise fonética
    phonetic = analysis["phonetic_analysis"]
    if not phonetic["has_phonetic_focus"]:
        recommendations.append(
            "Adicione elementos fonéticos para melhorar a pronúncia."
        )
    
    # Análise contextual
    contextual = analysis["contextual_relevance"]
    if not contextual["strategy_fits_context"]:
        recommendations.append(
            f"Estratégia tem baixo alinhamento com contexto da unidade "
            f"(score: {contextual['context_alignment_score']:.1f}). "
            f"Adapte explicações ao tema da unidade."
        )
    
    # Recomendações específicas por estratégia
    strategy = analysis["strategy_analysis"]["selected_strategy"]
    if strategy == "afixacao":
        recommendations.append("Para afixação: foque em padrões morfológicos recorrentes")
    elif strategy == "colocacoes":
        recommendations.append("Para colocações: inclua exercícios de combinação natural")
    elif strategy == "chunks":
        recommendations.append("Para chunks: enfatize uso em situações comunicativas")
    elif strategy == "substantivos_compostos":
        recommendations.append("Para compostos: agrupe por campos semânticos")
    elif strategy == "expressoes_fixas":
        recommendations.append("Para expressões fixas: pratique em contextos funcionais")
    elif strategy == "idiomas":
        recommendations.append("Para idiomas: explique o significado cultural")
    
    return recommendations


def _calculate_tips_quality(analysis: Dict[str, Any]) -> float:
    """Calcular qualidade geral das TIPS."""
    try:
        # Componentes da qualidade
        strategy_score = 1.0 if not analysis["strategy_analysis"]["is_overused"] else 0.6
        content_score = min(analysis["content_quality"]["content_quality_score"], 1.0)
        vocab_score = analysis["vocabulary_integration"]["integration_score"]
        pedagogical_score = analysis["pedagogical_effectiveness"]["effectiveness_score"]
        phonetic_score = min(analysis["phonetic_analysis"]["phonetic_integration_score"], 1.0)
        context_score = analysis["contextual_relevance"]["context_alignment_score"]
        
        # Média ponderada
        weights = {
            "strategy": 0.2,
            "content": 0.25,
            "vocabulary": 0.25,
            "pedagogical": 0.15,
            "phonetic": 0.1,
            "context": 0.05
        }
        
        overall_quality = (
            strategy_score * weights["strategy"] +
            content_score * weights["content"] +
            vocab_score * weights["vocabulary"] +
            pedagogical_score * weights["pedagogical"] +
            phonetic_score * weights["phonetic"] +
            context_score * weights["context"]
        )
        
        return round(overall_quality, 2)
        
    except Exception as e:
        logger.warning(f"Erro ao calcular qualidade das TIPS: {str(e)}")
        return 0.7  # Score padrão


def _get_effectiveness_recommendations(strategy: str, cefr_level: str, effectiveness_score: float) -> List[str]:
    """Obter recomendações de eficácia por estratégia e nível."""
    recommendations = []
    
    if effectiveness_score < 0.7:
        if strategy == "afixacao" and cefr_level in ["A1", "A2"]:
            recommendations.append("Use prefixos/sufixos mais básicos para iniciantes")
        elif strategy == "colocacoes" and cefr_level in ["A1", "A2"]:
            recommendations.append("Considere chunks ou expressões fixas para níveis básicos")
        elif strategy == "idiomas" and cefr_level in ["A1", "A2", "B1"]:
            recommendations.append("Idiomas são mais adequados para níveis B2+")
        elif strategy == "substantivos_compostos" and cefr_level in ["B2", "C1", "C2"]:
            recommendations.append("Para níveis avançados, foque em colocações ou idiomas")
        elif strategy == "expressoes_fixas" and cefr_level in ["C1", "C2"]:
            recommendations.append("Para níveis avançados, prefira idiomas ou colocações sofisticadas")
        elif strategy == "chunks" and cefr_level in ["C1", "C2"]:
            recommendations.append("Para níveis avançados, foque em chunks acadêmicos e profissionais")
    
    # Recomendações gerais de melhoria
    if effectiveness_score < 0.5:
        recommendations.append("Considere mudar de estratégia para este nível")
    elif effectiveness_score < 0.7:
        recommendations.append("Adapte exemplos e exercícios ao nível do aluno")
    
    return recommendations


def _get_tips_strategy_info(strategy: str) -> Dict[str, Any]:
    """Obter informações detalhadas sobre uma estratégia TIPS específica."""
    strategies_info = {
        "afixacao": {
            "name": "TIP 1: Afixação",
            "description": "Ensino através de prefixos e sufixos",
            "morphological_patterns": ["un- (unhappy)", "re- (remake)", "-er (teacher)", "-ly (quickly)"],
            "best_for_levels": ["A2", "B1", "B2"],
            "phonetic_focus": "Stress shift in derived words",
            "memory_technique": "Pattern recognition and word families"
        },
        "substantivos_compostos": {
            "name": "TIP 2: Substantivos Compostos", 
            "description": "Agrupamento temático de palavras compostas",
            "semantic_fields": ["transport", "technology", "workplace", "home"],
            "best_for_levels": ["A1", "A2", "B1"],
            "phonetic_focus": "Primary stress on first element",
            "memory_technique": "Visual association and semantic grouping"
        },
        "colocacoes": {
            "name": "TIP 3: Colocações",
            "description": "Combinações naturais e frequentes de palavras",
            "collocation_types": ["verb+noun", "adjective+noun", "adverb+adjective"],
            "best_for_levels": ["B1", "B2", "C1"],
            "phonetic_focus": "Natural rhythm in multi-word units",
            "memory_technique": "Frequency awareness and natural combinations"
        },
        "expressoes_fixas": {
            "name": "TIP 4: Expressões Fixas",
            "description": "Fórmulas fixas e frases cristalizadas",
            "functions": ["politeness", "discourse_markers", "social_formulas"],
            "best_for_levels": ["A2", "B1", "B2"],
            "phonetic_focus": "Sentence stress and intonation patterns",
            "memory_technique": "Situational memorization and drilling"
        },
        "idiomas": {
            "name": "TIP 5: Idiomas",
            "description": "Expressões com significado figurativo",
            "categories": ["body_parts", "colors", "animals", "weather"],
            "best_for_levels": ["B2", "C1", "C2"],
            "phonetic_focus": "Connected speech and reduced forms",
            "memory_technique": "Cultural context and image association"
        },
        "chunks": {
            "name": "TIP 6: Chunks",
            "description": "Blocos funcionais para fluência automática",
            "chunk_types": ["sentence_starters", "transitions", "functional_phrases"],
            "best_for_levels": ["A1", "A2", "B1"],
            "phonetic_focus": "Rhythm and stress in formulaic sequences",
            "memory_technique": "Repetition and procedural memory"
        }
    }
    
    return strategies_info.get(strategy, {})


def _validate_tips_strategy_selection(
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
        len(word.get("word", "").split()) > 1
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
        elif strategy_counts.get("chunks", 0) < 2:
            return "chunks"
        else:
            return "expressoes_fixas"
    
    elif cefr_level in ["B1", "B2"]:
        if has_affixes and strategy_counts.get("afixacao", 0) < 2:
            return "afixacao"
        elif strategy_counts.get("colocacoes", 0) < 2:
            return "colocacoes"
        else:
            return "expressoes_fixas"
    
    else:  # C1, C2
        if strategy_counts.get("idiomas", 0) < 2:
            return "idiomas"
        else:
            return "colocacoes"


def _generate_strategy_rationale(
    selected_strategy: str,
    vocabulary_analysis: Dict[str, Any],
    unit_context: Dict[str, Any],
    rag_context: Dict[str, Any]
) -> str:
    """Gerar justificativa para seleção da estratégia."""
    
    strategy_info = _get_tips_strategy_info(selected_strategy)
    cefr_level = unit_context.get("cefr_level", "B1")
    
    rationale_parts = []
    
    # Justificativa baseada no nível CEFR
    if cefr_level in strategy_info.get("best_for_levels", []):
        rationale_parts.append(f"Estratégia adequada para nível {cefr_level}")
    
    # Justificativa baseada no vocabulário
    vocab_patterns = vocabulary_analysis.get("patterns", [])
    if selected_strategy == "afixacao" and "morphological_patterns" in vocab_patterns:
        rationale_parts.append("Vocabulário apresenta padrões morfológicos claros")
    elif selected_strategy == "substantivos_compostos" and "compound_words" in vocab_patterns:
        rationale_parts.append("Presença de palavras compostas permite agrupamento temático")
    elif selected_strategy == "colocacoes" and "natural_combinations" in vocab_patterns:
        rationale_parts.append("Vocabulário permite explorar combinações naturais")
    
    # Justificativa baseada no balanceamento RAG
    used_strategies = rag_context.get("used_strategies", [])
    if used_strategies.count(selected_strategy) <= 1:
        rationale_parts.append("Estratégia pouco utilizada no book, promove variedade")
    
    # Justificativa baseada no contexto
    unit_context_text = unit_context.get("context", "")
    if selected_strategy == "chunks" and any(word in unit_context_text.lower() for word in ["communication", "conversation", "speaking"]):
        rationale_parts.append("Contexto comunicativo favorece uso de chunks funcionais")
    
    return ". ".join(rationale_parts) if rationale_parts else f"Estratégia {selected_strategy} selecionada para diversificação pedagógica"


def _extract_phonetic_patterns(vocabulary_items: List[Dict[str, Any]]) -> List[str]:
    """Extrair padrões fonéticos do vocabulário para foco das TIPS."""
    patterns = []
    
    # Analisar stress patterns
    stress_patterns = []
    for item in vocabulary_items:
        phoneme = item.get("phoneme", "")
        if "ˈ" in phoneme:
            stress_patterns.append("primary_stress")
        if "ˌ" in phoneme:
            stress_patterns.append("secondary_stress")
    
    if stress_patterns:
        patterns.append("word_stress_patterns")
    
    # Analisar difficult sounds
    difficult_sounds = []
    for item in vocabulary_items:
        phoneme = item.get("phoneme", "")
        if any(sound in phoneme for sound in ["θ", "ð", "ʃ", "ʒ", "ŋ"]):
            difficult_sounds.append("consonant_clusters")
        if any(sound in phoneme for sound in ["æ", "ʌ", "ɜː", "ɪə", "eə"]):
            difficult_sounds.append("vowel_distinctions")
    
    patterns.extend(list(set(difficult_sounds)))
    
    return list(set(patterns))