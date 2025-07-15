# src/api/v2/assessments.py
"""
Endpoints para geração de atividades de avaliação com seleção inteligente.
Implementação do sistema de Assessment do IVO V2 Guide.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import time

from src.services.hierarchical_database import hierarchical_db
from src.services.assessment_selector import AssessmentSelectorService
from src.core.unit_models import (
    SuccessResponse, ErrorResponse, AssessmentSection, AssessmentActivity
)
from src.core.enums import (
    CEFRLevel, LanguageVariant, UnitType, AssessmentType
)
from src.core.audit_logger import (
    audit_logger_instance, AuditEventType, audit_endpoint, extract_unit_info
)
from src.core.rate_limiter import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


async def rate_limit_assessments_generation(request):
    """Rate limiting específico para geração de assessments."""
    await rate_limit_dependency(request, "generate_assessments")


@router.post("/units/{unit_id}/assessments", response_model=SuccessResponse)
@audit_endpoint(AuditEventType.UNIT_CONTENT_GENERATED, extract_unit_info)
async def generate_assessments_for_unit(
    unit_id: str,
    request: Request,
    _: None = Depends(rate_limit_assessments_generation)
):
    """
    Gerar atividades de avaliação para a unidade com seleção inteligente.
    
    Flow do IVO V2:
    1. Buscar unidade e validar hierarquia
    2. Verificar se possui vocabulário, sentences e strategies
    3. Usar RAG para balanceamento de atividades
    4. Selecionar 2 atividades ótimas de 7 disponíveis
    5. Gerar conteúdo específico para cada atividade
    6. Salvar e atualizar status da unidade
    """
    try:
        logger.info(f"Iniciando geração de assessments para unidade: {unit_id}")
        
        # 1. Buscar e validar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # 2. Verificar se está pronta para assessments
        if unit.status.value not in ["assessments_pending"]:
            if unit.status.value == "creating":
                raise HTTPException(
                    status_code=400,
                    detail="Unidade ainda não está pronta para assessments. Complete vocabulário, sentences e strategies primeiro."
                )
            elif unit.assessments:
                logger.info(f"Unidade {unit_id} já possui assessments - regenerando")
        
        # 3. Verificar pré-requisitos
        if not unit.vocabulary or not unit.vocabulary.get("items"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter vocabulário antes de gerar assessments."
            )
        
        if not unit.sentences or not unit.sentences.get("sentences"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter sentences antes de gerar assessments."
            )
        
        # Verificar se tem estratégias (TIPS ou GRAMMAR)
        has_strategies = bool(unit.tips or unit.grammar)
        if not has_strategies:
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter estratégias (TIPS ou GRAMMAR) antes de gerar assessments."
            )
        
        # 4. Buscar contexto da hierarquia
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        if not course or not book:
            raise HTTPException(
                status_code=400,
                detail="Hierarquia inválida: curso ou book não encontrado"
            )
        
        # 5. Buscar contexto RAG para balanceamento
        logger.info("Coletando contexto RAG para balanceamento de atividades...")
        
        used_assessments = await hierarchical_db.get_used_assessments(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # 6. Preparar dados para seleção e geração
        assessment_params = {
            "unit_id": unit_id,
            "unit_data": {
                "title": unit.title,
                "context": unit.context,
                "cefr_level": unit.cefr_level.value,
                "language_variant": unit.language_variant.value,
                "unit_type": unit.unit_type.value,
                "status": unit.status.value
            },
            "content_data": {
                "vocabulary": unit.vocabulary,
                "sentences": unit.sentences,
                "tips": unit.tips,
                "grammar": unit.grammar,
                "main_aim": unit.main_aim,
                "subsidiary_aims": unit.subsidiary_aims
            },
            "hierarchy_context": {
                "course_name": course.name,
                "book_name": book.name,
                "sequence_order": unit.sequence_order,
                "target_level": book.target_level.value
            },
            "rag_context": {
                "used_assessments": used_assessments,
                "taught_vocabulary": taught_vocabulary,
                "used_strategies": used_strategies,
                "progression_level": _determine_progression_level(unit.sequence_order),
                "assessment_density": _calculate_assessment_density(used_assessments)
            }
        }
        
        # 7. Gerar assessments usando service
        start_time = time.time()
        assessment_selector = AssessmentSelectorService()
        
        assessment_section = await assessment_selector.generate_assessments_for_unit(
            assessment_params
        )
        
        generation_time = time.time() - start_time
        
        # 8. Salvar assessments na unidade
        await hierarchical_db.update_unit_content(
            unit_id, 
            "assessments", 
            assessment_section.dict()
        )
        
        # 9. Atualizar lista de assessments usados na unidade
        assessment_types = [activity.type.value for activity in assessment_section.activities]
        await hierarchical_db.update_unit_content(
            unit_id,
            "assessments_used",
            assessment_types
        )
        
        # 10. Atualizar status da unidade para completed
        await hierarchical_db.update_unit_status(unit_id, "completed")
        
        # 11. Calcular quality score final
        quality_score = await _calculate_unit_quality_score(unit_id)
        await hierarchical_db.update_unit_content(unit_id, "quality_score", quality_score)
        
        # 12. Log de auditoria
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="assessments",
            unit_id=unit_id,
            book_id=unit.book_id,
            course_id=unit.course_id,
            content_stats={
                "activities_count": len(assessment_section.activities),
                "assessment_types": assessment_types,
                "total_estimated_time": assessment_section.total_estimated_time,
                "skills_assessed": assessment_section.skills_assessed,
                "balance_score": assessment_section.balance_analysis.get("balance_score", 0),
                "quality_score": quality_score
            },
            ai_usage={
                "model": "gpt-4o-mini",
                "generation_time": generation_time,
                "selection_algorithm": "rag_based_intelligent_selection"
            },
            processing_time=generation_time,
            success=True
        )
        
        return SuccessResponse(
            data={
                "assessments": assessment_section.dict(),
                "generation_stats": {
                    "activities_generated": len(assessment_section.activities),
                    "assessment_types": assessment_types,
                    "total_estimated_time": f"{assessment_section.total_estimated_time} min",
                    "skills_assessed": assessment_section.skills_assessed,
                    "processing_time": f"{generation_time:.2f}s"
                },
                "unit_progression": {
                    "unit_id": unit_id,
                    "previous_status": unit.status.value,
                    "new_status": "completed",
                    "final_quality_score": quality_score,
                    "completion_message": "Unidade finalizada com sucesso!"
                },
                "rag_balancing": {
                    "used_assessments_analysis": used_assessments,
                    "selected_activities": assessment_types,
                    "balance_rationale": assessment_section.selection_rationale,
                    "underused_activities": assessment_section.underused_activities
                }
            },
            message=f"Assessments gerados com sucesso para unidade '{unit.title}' - Unidade COMPLETA!",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Visualizar unidade completa",
                f"GET /api/v2/units/{unit_id}",
                "Exportar para PDF",
                f"POST /api/v2/units/{unit_id}/export",
                "Criar próxima unidade no book",
                f"POST /api/v2/books/{unit.book_id}/units"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar assessments para unidade {unit_id}: {str(e)}")
        
        # Log de erro
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="assessments",
            unit_id=unit_id,
            book_id=getattr(unit, 'book_id', ''),
            course_id=getattr(unit, 'course_id', ''),
            success=False,
            error_details=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno na geração de assessments: {str(e)}"
        )


@router.get("/units/{unit_id}/assessments", response_model=SuccessResponse)
async def get_unit_assessments(unit_id: str, request: Request):
    """Obter assessments da unidade."""
    try:
        logger.info(f"Buscando assessments da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui assessments
        if not unit.assessments:
            return SuccessResponse(
                data={
                    "has_assessments": False,
                    "unit_status": unit.status.value,
                    "message": "Unidade ainda não possui assessments gerados",
                    "prerequisites": {
                        "has_vocabulary": bool(unit.vocabulary),
                        "has_sentences": bool(unit.sentences),
                        "has_strategies": bool(unit.tips or unit.grammar)
                    }
                },
                message="Assessments não encontrados",
                hierarchy_info={
                    "course_id": unit.course_id,
                    "book_id": unit.book_id,
                    "unit_id": unit_id,
                    "sequence": unit.sequence_order
                },
                next_suggested_actions=[
                    "Gerar assessments",
                    f"POST /api/v2/units/{unit_id}/assessments"
                ]
            )
        
        # Buscar contexto adicional
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        # Análise dos assessments
        assessments_data = unit.assessments
        activities = assessments_data.get("activities", [])
        
        # Estatísticas dos assessments
        activity_types = {}
        difficulty_distribution = {}
        total_time = 0
        
        for activity in activities:
            activity_type = activity.get("type", "unknown")
            difficulty = activity.get("difficulty_level", "unknown")
            estimated_time = activity.get("estimated_time", 0)
            
            activity_types[activity_type] = activity_types.get(activity_type, 0) + 1
            difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
            total_time += estimated_time
        
        return SuccessResponse(
            data={
                "assessments": assessments_data,
                "analysis": {
                    "total_activities": len(activities),
                    "activity_types": activity_types,
                    "difficulty_distribution": difficulty_distribution,
                    "total_estimated_time": total_time,
                    "skills_assessed": assessments_data.get("skills_assessed", []),
                    "balance_analysis": assessments_data.get("balance_analysis", {}),
                    "selection_rationale": assessments_data.get("selection_rationale", "")
                },
                "unit_context": {
                    "unit_title": unit.title,
                    "unit_type": unit.unit_type.value,
                    "cefr_level": unit.cefr_level.value,
                    "unit_status": unit.status.value,
                    "quality_score": unit.quality_score,
                    "course_name": course.name if course else None,
                    "book_name": book.name if book else None,
                    "sequence_order": unit.sequence_order
                },
                "has_assessments": True
            },
            message=f"Assessments da unidade '{unit.title}'",
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
        logger.error(f"Erro ao buscar assessments da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}/assessments", response_model=SuccessResponse)
async def update_unit_assessments(
    unit_id: str,
    assessments_data: Dict[str, Any],
    request: Request,
    _: None = Depends(rate_limit_assessments_generation)
):
    """Atualizar assessments da unidade (edição manual)."""
    try:
        logger.info(f"Atualizando assessments da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Validar estrutura básica dos dados
        if not isinstance(assessments_data, dict):
            raise HTTPException(
                status_code=400,
                detail="Dados de assessments devem ser um objeto JSON"
            )
        
        required_fields = ["activities"]
        for field in required_fields:
            if field not in assessments_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo obrigatório ausente: {field}"
                )
        
        # Validar estrutura das atividades
        activities = assessments_data["activities"]
        if not isinstance(activities, list):
            raise HTTPException(
                status_code=400,
                detail="Campo 'activities' deve ser uma lista"
            )
        
        if len(activities) != 2:
            raise HTTPException(
                status_code=400,
                detail="Deve haver exatamente 2 atividades de assessment"
            )
        
        # Validar cada atividade
        for i, activity in enumerate(activities):
            if not isinstance(activity, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Atividade {i+1} deve ser um objeto"
                )
            
            required_activity_fields = ["type", "title", "instructions", "content", "answer_key"]
            for field in required_activity_fields:
                if field not in activity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Campo obrigatório ausente na atividade {i+1}: {field}"
                    )
        
        # Atualizar timestamps
        assessments_data["updated_at"] = time.time()
        
        # Extrair tipos de atividades
        activity_types = [activity["type"] for activity in activities]
        
        # Salvar no banco
        await hierarchical_db.update_unit_content(unit_id, "assessments", assessments_data)
        await hierarchical_db.update_unit_content(unit_id, "assessments_used", activity_types)
        
        # Log da atualização
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "assessments_manual_edit",
                "activities_count": len(activities),
                "activity_types": activity_types,
                "unit_id": unit_id
            }
        )
        
        return SuccessResponse(
            data={
                "updated": True,
                "assessments": assessments_data,
                "update_stats": {
                    "total_activities": len(activities),
                    "activity_types": activity_types,
                    "update_timestamp": assessments_data["updated_at"]
                }
            },
            message=f"Assessments atualizados com sucesso",
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
        logger.error(f"Erro ao atualizar assessments da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/units/{unit_id}/assessments", response_model=SuccessResponse)
async def delete_unit_assessments(unit_id: str, request: Request):
    """Deletar assessments da unidade."""
    try:
        logger.warning(f"Deletando assessments da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui assessments
        if not unit.assessments:
            return SuccessResponse(
                data={
                    "deleted": False,
                    "message": "Unidade não possui assessments para deletar"
                },
                message="Nenhum assessment encontrado para deletar"
            )
        
        # Deletar assessments (setar como None)
        await hierarchical_db.update_unit_content(unit_id, "assessments", None)
        await hierarchical_db.update_unit_content(unit_id, "assessments_used", [])
        
        # Ajustar status se necessário
        if unit.status.value == "completed":
            await hierarchical_db.update_unit_status(unit_id, "assessments_pending")
        
        # Log da deleção
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "assessments_deleted",
                "unit_id": unit_id,
                "previous_activities_count": len(unit.assessments.get("activities", []))
            }
        )
        
        return SuccessResponse(
            data={
                "deleted": True,
                "previous_activities_count": len(unit.assessments.get("activities", [])),
                "new_status": "assessments_pending"
            },
            message="Assessments deletados com sucesso",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Regenerar assessments",
                f"POST /api/v2/units/{unit_id}/assessments"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar assessments da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}/assessments/analysis", response_model=SuccessResponse)
async def analyze_unit_assessments(unit_id: str, request: Request):
    """Analisar qualidade e balanceamento dos assessments da unidade."""
    try:
        logger.info(f"Analisando assessments da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui assessments
        if not unit.assessments:
            raise HTTPException(
                status_code=400,
                detail="Unidade não possui assessments para analisar"
            )
        
        # Buscar contexto RAG para comparação
        used_assessments = await hierarchical_db.get_used_assessments(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # Analisar assessments
        assessments_data = unit.assessments
        activities = assessments_data.get("activities", [])
        
        analysis = {
            "balance_analysis": _analyze_assessment_balance(activities, used_assessments),
            "difficulty_analysis": _analyze_difficulty_distribution(activities),
            "skills_coverage": _analyze_skills_coverage(activities),
            "time_analysis": _analyze_time_distribution(activities),
            "content_alignment": _analyze_content_alignment(activities, unit),
            "quality_metrics": {
                "total_activities": len(activities),
                "estimated_time": assessments_data.get("total_estimated_time", 0),
                "skills_assessed": assessments_data.get("skills_assessed", []),
                "balance_score": assessments_data.get("balance_analysis", {}).get("balance_score", 0)
            }
        }
        
        # Gerar recomendações
        recommendations = _generate_assessment_recommendations(analysis, unit)
        
        return SuccessResponse(
            data={
                "analysis": analysis,
                "recommendations": recommendations,
                "summary": {
                    "total_activities": len(activities),
                    "overall_quality": _calculate_assessment_quality(analysis),
                    "balance_score": analysis["balance_analysis"].get("balance_score", 0),
                    "needs_improvement": len(recommendations) > 0
                }
            },
            message=f"Análise dos assessments da unidade '{unit.title}'",
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
        logger.error(f"Erro ao analisar assessments da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/assessments/types", response_model=SuccessResponse)
async def get_assessment_types(request: Request):
    """Obter informações sobre os 7 tipos de assessment disponíveis."""
    try:
        assessment_types_info = {
            "cloze_test": {
                "name": "Cloze Test",
                "description": "Teste de compreensão geral com lacunas",
                "skills": ["reading", "grammar", "vocabulary"],
                "difficulty": "intermediate",
                "estimated_time": "10-15 min",
                "best_for": ["grammar_units", "lexical_units"],
                "when_to_use": "Avaliar compreensão geral e gramática"
            },
            "gap_fill": {
                "name": "Gap Fill",
                "description": "Preenchimento de lacunas específicas",
                "skills": ["grammar", "vocabulary"],
                "difficulty": "beginner_to_intermediate",
                "estimated_time": "8-12 min",
                "best_for": ["grammar_units", "lexical_units"],
                "when_to_use": "Focar em pontos gramaticais ou vocabulário específico"
            },
            "reordenacao": {
                "name": "Sentence Reordering",
                "description": "Reordenação de frases ou palavras",
                "skills": ["grammar", "sentence_structure"],
                "difficulty": "intermediate",
                "estimated_time": "10-15 min",
                "best_for": ["grammar_units"],
                "when_to_use": "Avaliar estrutura e coesão textual"
            },
            "transformacao": {
                "name": "Sentence Transformation",
                "description": "Transformação de estruturas gramaticais",
                "skills": ["grammar", "syntax"],
                "difficulty": "advanced",
                "estimated_time": "15-20 min",
                "best_for": ["grammar_units"],
                "when_to_use": "Avaliar equivalência gramatical"
            },
            "multipla_escolha": {
                "name": "Multiple Choice",
                "description": "Questões de múltipla escolha",
                "skills": ["grammar", "vocabulary", "reading"],
                "difficulty": "beginner_to_advanced",
                "estimated_time": "10-15 min",
                "best_for": ["grammar_units", "lexical_units"],
                "when_to_use": "Avaliar conhecimento objetivo"
            },
            "verdadeiro_falso": {
                "name": "True/False",
                "description": "Questões verdadeiro ou falso",
                "skills": ["reading", "comprehension"],
                "difficulty": "beginner_to_intermediate",
                "estimated_time": "8-12 min",
                "best_for": ["lexical_units"],
                "when_to_use": "Avaliar compreensão textual"
            },
            "matching": {
                "name": "Matching",
                "description": "Associação de elementos",
                "skills": ["vocabulary", "comprehension"],
                "difficulty": "beginner_to_intermediate",
                "estimated_time": "8-12 min",
                "best_for": ["lexical_units"],
                "when_to_use": "Avaliar associações e vocabulário"
            }
        }
        
        return SuccessResponse(
            data={
                "assessment_types": assessment_types_info,
                "selection_logic": {
                    "total_available": 7,
                    "selected_per_unit": 2,
                    "selection_criteria": [
                        "Unit type (lexical vs grammar)",
                        "CEFR level appropriateness",
                        "Balance with previous units",
                        "Complementary skills coverage"
                    ]
                },
                "ivo_v2_strategy": {
                    "balancing": "RAG-based intelligent selection",
                    "variety": "Maximum 2 repetitions per 7 units",
                    "complementarity": "Selected activities complement each other"
                }
            },
            message="Informações sobre tipos de assessment do IVO V2"
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter tipos de assessment: {str(e)}")
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
        return "basic_assessment"
    elif sequence_order <= 7:
        return "intermediate_assessment"
    else:
        return "advanced_assessment"


def _calculate_assessment_density(used_assessments: Dict[str, Any]) -> float:
    """Calcular densidade de uso de assessments."""
    if not used_assessments:
        return 0.0
    
    total_used = sum(used_assessments.values()) if isinstance(used_assessments, dict) else 0
    return total_used / 7  # 7 tipos disponíveis


async def _calculate_unit_quality_score(unit_id: str) -> float:
    """Calcular score de qualidade final da unidade."""
    try:
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            return 0.0
        
        # Componentes da qualidade
        components = {
            "vocabulary": 0.3,
            "sentences": 0.2,
            "strategies": 0.2,
            "assessments": 0.2,
            "hierarchy": 0.1
        }
        
        score = 0.0
        
        # Vocabulário
        if unit.vocabulary:
            vocab_quality = unit.vocabulary.get("context_relevance", 0.7)
            score += vocab_quality * components["vocabulary"]
        
        # Sentences
        if unit.sentences:
            sentences_quality = unit.sentences.get("contextual_coherence", 0.8)
            score += sentences_quality * components["sentences"]
        
        # Estratégias (TIPS ou GRAMMAR)
        if unit.tips or unit.grammar:
            strategies_quality = 0.85  # Boa qualidade padrão para estratégias
            score += strategies_quality * components["strategies"]
        
        # Assessments
        if unit.assessments:
            assessment_balance = unit.assessments.get("balance_analysis", {}).get("balance_score", 0.8)
            score += assessment_balance * components["assessments"]
        
        # Hierarquia
        hierarchy_quality = 0.9  # Boa qualidade para hierarquia válida
        score += hierarchy_quality * components["hierarchy"]
        
        return round(score, 2)
        
    except Exception as e:
        logger.warning(f"Erro ao calcular quality score: {str(e)}")
        return 0.7  # Score padrão


def _analyze_assessment_balance(activities: List[Dict], used_assessments: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar balanceamento dos assessments."""
    current_types = [activity.get("type") for activity in activities]
    
    # Calcular distribuição
    if isinstance(used_assessments, dict):
        all_types = list(used_assessments.keys()) + current_types
    else:
        all_types = current_types
    
    type_counts = {}
    for t in all_types:
        type_counts[t] = type_counts.get(t, 0) + 1
    
    # Calcular score de balanceamento (0-1)
    ideal_distribution = len(all_types) / 7  # 7 tipos disponíveis
    variance = sum((count - ideal_distribution) ** 2 for count in type_counts.values())
    balance_score = max(0, 1 - (variance / (ideal_distribution ** 2)))
    
    return {
        "current_activities": current_types,
        "type_distribution": type_counts,
        "balance_score": round(balance_score, 2),
        "is_well_balanced": balance_score > 0.7,
        "most_used_type": max(type_counts, key=type_counts.get) if type_counts else None,
        "least_used_types": [t for t, count in type_counts.items() if count == min(type_counts.values())] if type_counts else []
    }


def _analyze_difficulty_distribution(activities: List[Dict]) -> Dict[str, Any]:
    """Analisar distribuição de dificuldade."""
    difficulties = [activity.get("difficulty_level", "intermediate") for activity in activities]
    
    difficulty_counts = {}
    for d in difficulties:
        difficulty_counts[d] = difficulty_counts.get(d, 0) + 1
    
    return {
        "distribution": difficulty_counts,
        "most_common": max(difficulty_counts, key=difficulty_counts.get) if difficulty_counts else None,
        "has_variety": len(set(difficulties)) > 1,
        "average_difficulty": _calculate_average_difficulty(difficulties)
    }


def _analyze_skills_coverage(activities: List[Dict]) -> Dict[str, Any]:
    """Analisar cobertura de habilidades."""
    all_skills = []
    for activity in activities:
        skills = activity.get("skills_assessed", [])
        all_skills.extend(skills)
    
    skill_counts = {}
    for skill in all_skills:
        skill_counts[skill] = skill_counts.get(skill, 0) + 1
    
    return {
        "skills_covered": list(set(all_skills)),
        "skill_distribution": skill_counts,
        "coverage_breadth": len(set(all_skills)),
        "most_assessed_skill": max(skill_counts, key=skill_counts.get) if skill_counts else None
    }


def _analyze_time_distribution(activities: List[Dict]) -> Dict[str, Any]:
    """Analisar distribuição de tempo."""
    times = [activity.get("estimated_time", 10) for activity in activities]
    total_time = sum(times)
    
    return {
        "individual_times": times,
        "total_time": total_time,
        "average_time": total_time / len(times) if times else 0,
        "time_balance": "balanced" if max(times) - min(times) <= 5 else "unbalanced" if times else "unknown"
    }


def _analyze_content_alignment(activities: List[Dict], unit) -> Dict[str, Any]:
    """Analisar alinhamento com conteúdo da unidade."""
    vocab_words = []
    if unit.vocabulary:
        vocab_words = [item.get("word", "") for item in unit.vocabulary.get("items", [])]
    
    vocab_usage = 0
    content_references = 0
    
    for activity in activities:
        # Verificar uso de vocabulário
        activity_content = str(activity.get("content", "")).lower()
        for word in vocab_words:
            if word.lower() in activity_content:
                vocab_usage += 1
                break
        
        # Verificar referências ao contexto
        unit_context = unit.context or ""
        if unit_context.lower() in activity_content:
            content_references += 1
    
    alignment_score = (vocab_usage + content_references) / (len(activities) * 2) if activities else 0
    
    return {
        "vocabulary_usage": vocab_usage,
        "content_references": content_references,
        "alignment_score": round(alignment_score, 2),
        "is_well_aligned": alignment_score > 0.5
    }


def _generate_assessment_recommendations(analysis: Dict[str, Any], unit) -> List[str]:
    """Gerar recomendações para melhorar assessments."""
    recommendations = []
    
    # Análise de balanceamento
    balance_analysis = analysis["balance_analysis"]
    if not balance_analysis["is_well_balanced"]:
        recommendations.append(
            f"Balanceamento de atividades pode ser melhorado (score: {balance_analysis['balance_score']:.1f}). "
            f"Considere usar tipos menos utilizados: {', '.join(balance_analysis['least_used_types'][:2])}"
        )
    
    # Análise de dificuldade
    difficulty_analysis = analysis["difficulty_analysis"]
    if not difficulty_analysis["has_variety"]:
        recommendations.append("Considere variar níveis de dificuldade entre as atividades")
    
    # Análise de habilidades
    skills_analysis = analysis["skills_coverage"]
    if skills_analysis["coverage_breadth"] < 3:
        recommendations.append(
            f"Cobertura de habilidades limitada ({skills_analysis['coverage_breadth']} habilidades). "
            f"Considere atividades que avaliem mais habilidades diferentes."
        )
    
    # Análise de tempo
    time_analysis = analysis["time_analysis"]
    if time_analysis["time_balance"] == "unbalanced":
        recommendations.append("Tempos estimados muito diferentes entre atividades. Considere balancear melhor.")
    
    if time_analysis["total_time"] > 30:
        recommendations.append(f"Tempo total muito longo ({time_analysis['total_time']} min). Considere atividades mais concisas.")
    
    # Análise de alinhamento
    content_analysis = analysis["content_alignment"]
    if not content_analysis["is_well_aligned"]:
        recommendations.append(
            f"Baixo alinhamento com conteúdo da unidade (score: {content_analysis['alignment_score']:.1f}). "
            f"Certifique-se de usar o vocabulário e contexto da unidade."
        )
    
    # Recomendações específicas por tipo de unidade
    if unit.unit_type.value == "lexical_unit":
        recommendations.append("Para unidades lexicais, priorize atividades de matching e gap-fill")
    else:
        recommendations.append("Para unidades gramaticais, considere transformation e reordering")
    
    return recommendations


def _calculate_assessment_quality(analysis: Dict[str, Any]) -> float:
    """Calcular qualidade geral dos assessments."""
    try:
        balance_score = analysis["balance_analysis"]["balance_score"]
        skills_breadth = min(analysis["skills_coverage"]["coverage_breadth"] / 5, 1.0)  # Máximo 5 habilidades
        alignment_score = analysis["content_alignment"]["alignment_score"]
        
        # Verificar variedade de dificuldade
        variety_score = 1.0 if analysis["difficulty_analysis"]["has_variety"] else 0.7
        
        # Verificar tempo balanceado
        time_score = 1.0 if analysis["time_analysis"]["time_balance"] == "balanced" else 0.8
        
        # Média ponderada
        overall = (
            balance_score * 0.3 +
            skills_breadth * 0.25 +
            alignment_score * 0.25 +
            variety_score * 0.1 +
            time_score * 0.1
        )
        
        return round(overall, 2)
        
    except Exception as e:
        logger.warning(f"Erro ao calcular qualidade dos assessments: {str(e)}")
        return 0.7


def _calculate_average_difficulty(difficulties: List[str]) -> str:
    """Calcular dificuldade média."""
    if not difficulties:
        return "unknown"
    
    difficulty_values = {
        "beginner": 1,
        "elementary": 2,
        "intermediate": 3,
        "upper_intermediate": 4,
        "advanced": 5
    }
    
    total_value = sum(difficulty_values.get(d, 3) for d in difficulties)
    avg_value = total_value / len(difficulties)
    
    # Mapear de volta para categoria
    if avg_value <= 1.5:
        return "beginner"
    elif avg_value <= 2.5:
        return "elementary"
    elif avg_value <= 3.5:
        return "intermediate"
    elif avg_value <= 4.5:
        return "upper_intermediate"
    else:
        return "advanced"