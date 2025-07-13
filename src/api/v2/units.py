# src/api/v2/units.py
"""Endpoints para gestão de unidades com hierarquia obrigatória."""
from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
from typing import List, Optional
import logging
import base64
import time

from src.services.hierarchical_database import hierarchical_db
from src.core.hierarchical_models import HierarchicalUnitRequest
from src.core.unit_models import (
    UnitCreateRequest, UnitResponse, SuccessResponse, ErrorResponse,
    GenerationProgress, UnitStatus
)
from src.core.enums import CEFRLevel, LanguageVariant, UnitType

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/books/{book_id}/units", response_model=SuccessResponse)
async def create_unit_with_hierarchy(
    book_id: str,
    image_1: UploadFile = File(..., description="Primeira imagem (obrigatória)"),
    image_2: UploadFile = File(None, description="Segunda imagem (opcional)"),
    context: str = Form(None, description="Contexto da unidade"),
    cefr_level: CEFRLevel = Form(..., description="Nível CEFR"),
    language_variant: LanguageVariant = Form(..., description="Variante do idioma"),
    unit_type: UnitType = Form(..., description="Tipo de unidade")
):
    """Criar unidade com hierarquia Course → Book → Unit obrigatória."""
    
    try:
        logger.info(f"Criando unidade no book: {book_id}")
        
        # 1. Validar book e obter course_id
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404, 
                detail=f"Book {book_id} não encontrado"
            )
        
        course_id = book.course_id
        
        # 2. Validar hierarquia
        validation = await hierarchical_db.validate_hierarchy(course_id, book_id)
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Hierarquia inválida: {validation.errors}"
            )
        
        # 3. Validar nível CEFR compatível com o book
        if cefr_level != book.target_level:
            logger.warning(f"Nível da unidade ({cefr_level.value}) diferente do book ({book.target_level.value})")
        
        # 4. Processar imagens
        images_info = []
        
        # Imagem 1 (obrigatória)
        if image_1:
            img1_content = await image_1.read()
            img1_b64 = base64.b64encode(img1_content).decode()
            images_info.append({
                "filename": image_1.filename,
                "size": len(img1_content),
                "base64": img1_b64,
                "description": "Primeira imagem - análise pendente"
            })
        
        # Imagem 2 (opcional)
        if image_2:
            img2_content = await image_2.read()
            img2_b64 = base64.b64encode(img2_content).decode()
            images_info.append({
                "filename": image_2.filename,
                "size": len(img2_content),
                "base64": img2_b64,
                "description": "Segunda imagem - análise pendente"
            })
        
        # 5. Criar request hierárquico
        unit_request = HierarchicalUnitRequest(
            course_id=course_id,
            book_id=book_id,
            title=f"Unidade {context[:30]}..." if context else "Nova Unidade",
            context=context,
            cefr_level=cefr_level,
            language_variant=language_variant,
            unit_type=unit_type
        )
        
        # 6. Criar unidade no banco
        unit = await hierarchical_db.create_unit(unit_request)
        
        # 7. Atualizar com imagens processadas
        await hierarchical_db.update_unit_content(
            unit.id, 
            "images", 
            images_info
        )
        
        # 8. Buscar contexto do curso e book para response
        course = await hierarchical_db.get_course(course_id)
        
        return SuccessResponse(
            data={
                "unit": {
                    "id": unit.id,
                    "title": unit.title,
                    "sequence_order": unit.sequence_order,
                    "status": unit.status.value,
                    "context": unit.context,
                    "unit_type": unit.unit_type.value,
                    "cefr_level": unit.cefr_level.value,
                    "images_count": len(images_info)
                },
                "hierarchy_context": {
                    "course_id": course.id,
                    "course_name": course.name,
                    "book_id": book.id,
                    "book_name": book.name,
                    "book_level": book.target_level.value,
                    "sequence_in_book": unit.sequence_order
                },
                "images_processed": len(images_info),
                "ready_for_next_step": True
            },
            message=f"Unidade criada na sequência {unit.sequence_order} do book '{book.name}'",
            hierarchy_info={
                "course_id": course_id,
                "book_id": book_id,
                "unit_id": unit.id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Gerar vocabulário com RAG",
                f"POST /api/v2/units/{unit.id}/vocabulary",
                "Ver contexto hierárquico",
                f"GET /api/v2/units/{unit.id}/context"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar unidade: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/books/{book_id}/units", response_model=SuccessResponse)
async def list_units_by_book(
    book_id: str,
    status: Optional[UnitStatus] = Query(None, description="Filtrar por status"),
    include_content: bool = Query(False, description="Incluir conteúdo das unidades")
):
    """Listar unidades de um book em ordem sequencial."""
    
    try:
        logger.info(f"Listando unidades do book: {book_id}")
        
        # Verificar se book existe
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Buscar course para contexto
        course = await hierarchical_db.get_course(book.course_id)
        
        # Buscar unidades do book
        units = await hierarchical_db.list_units_by_book(book_id)
        
        # Aplicar filtro de status se especificado
        if status:
            units = [unit for unit in units if unit.status == status]
        
        # Preparar dados das unidades
        units_data = []
        for unit in units:
            unit_data = {
                "id": unit.id,
                "title": unit.title,
                "sequence_order": unit.sequence_order,
                "status": unit.status.value,
                "unit_type": unit.unit_type.value,
                "cefr_level": unit.cefr_level.value,
                "context": unit.context,
                "quality_score": unit.quality_score,
                "created_at": unit.created_at.isoformat(),
                "updated_at": unit.updated_at.isoformat()
            }
            
            if include_content:
                unit_data.update({
                    "vocabulary": unit.vocabulary,
                    "sentences": unit.sentences,
                    "tips": unit.tips,
                    "grammar": unit.grammar,
                    "assessments": unit.assessments,
                    "strategies_used": unit.strategies_used,
                    "assessments_used": unit.assessments_used,
                    "vocabulary_taught": unit.vocabulary_taught
                })
            
            units_data.append(unit_data)
        
        # Estatísticas das unidades
        status_distribution = {}
        for unit in units:
            status_key = unit.status.value
            status_distribution[status_key] = status_distribution.get(status_key, 0) + 1
        
        return SuccessResponse(
            data={
                "book_context": {
                    "book_id": book.id,
                    "book_name": book.name,
                    "target_level": book.target_level.value,
                    "course_id": course.id if course else None,
                    "course_name": course.name if course else None
                },
                "units": units_data,
                "statistics": {
                    "total_units": len(units_data),
                    "status_distribution": status_distribution,
                    "filter_applied": status.value if status else None,
                    "average_quality": sum(
                        unit.quality_score for unit in units if unit.quality_score
                    ) / max(len([u for u in units if u.quality_score]), 1)
                }
            },
            message=f"{len(units_data)} unidades encontradas no book '{book.name}'",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "units_list"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao listar unidades do book {book_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}", response_model=SuccessResponse)
async def get_unit_complete(unit_id: str):
    """Obter unidade completa com contexto hierárquico."""
    
    try:
        logger.info(f"Buscando unidade completa: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Buscar contexto hierárquico
        book = await hierarchical_db.get_book(unit.book_id)
        course = await hierarchical_db.get_course(unit.course_id)
        
        # Buscar análise de progressão
        progression = await hierarchical_db.get_progression_analysis(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # Montar response completa
        unit_complete = {
            "unit_data": unit.dict(),
            "hierarchy_context": {
                "course": {
                    "id": course.id,
                    "name": course.name,
                    "language_variant": course.language_variant.value,
                    "target_levels": [level.value for level in course.target_levels]
                } if course else None,
                "book": {
                    "id": book.id,
                    "name": book.name,
                    "target_level": book.target_level.value,
                    "sequence_order": book.sequence_order
                } if book else None,
                "position": {
                    "sequence_in_book": unit.sequence_order,
                    "unit_id": unit.id
                }
            },
            "progression_context": {
                "vocabulary_progression": progression.vocabulary_progression,
                "strategy_distribution": progression.strategy_distribution,
                "assessment_balance": progression.assessment_balance,
                "recommendations": progression.recommendations,
                "quality_metrics": progression.quality_metrics
            },
            "content_status": {
                "has_vocabulary": bool(unit.vocabulary),
                "has_sentences": bool(unit.sentences),
                "has_strategies": bool(unit.tips or unit.grammar),
                "has_assessments": bool(unit.assessments),
                "completion_percentage": _calculate_completion_percentage(unit)
            }
        }
        
        return SuccessResponse(
            data=unit_complete,
            message=f"Unidade '{unit.title}' completa",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit.id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=_get_next_actions_for_unit(unit)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}/context", response_model=SuccessResponse)
async def get_unit_rag_context(unit_id: str):
    """Obter contexto RAG para a unidade (vocabulário precedente, estratégias, etc)."""
    
    try:
        logger.info(f"Buscando contexto RAG para unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Buscar contexto RAG
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_assessments = await hierarchical_db.get_used_assessments(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # Análise de precedentes (unidades anteriores no book)
        precedent_units = []
        all_units = await hierarchical_db.list_units_by_book(unit.book_id)
        for prev_unit in all_units:
            if prev_unit.sequence_order < unit.sequence_order:
                precedent_units.append({
                    "unit_id": prev_unit.id,
                    "title": prev_unit.title,
                    "sequence": prev_unit.sequence_order,
                    "status": prev_unit.status.value,
                    "vocabulary_count": len(prev_unit.vocabulary_taught or []),
                    "strategies": prev_unit.strategies_used or [],
                    "assessments": prev_unit.assessments_used or []
                })
        
        # Recomendações baseadas no contexto
        recommendations = []
        
        if len(taught_vocabulary) > 100:
            recommendations.append("Considerar revisão de vocabulário - muitas palavras já ensinadas")
        
        if len(set(used_strategies)) < 3:
            recommendations.append("Diversificar estratégias pedagógicas")
        
        available_strategies = ["afixacao", "substantivos_compostos", "colocacoes", "expressoes_fixas", "idiomas", "chunks"]
        unused_strategies = [s for s in available_strategies if s not in used_strategies]
        if unused_strategies:
            recommendations.append(f"Estratégias disponíveis: {unused_strategies[:3]}")
        
        return SuccessResponse(
            data={
                "unit_info": {
                    "unit_id": unit.id,
                    "title": unit.title,
                    "sequence_order": unit.sequence_order,
                    "unit_type": unit.unit_type.value
                },
                "rag_context": {
                    "taught_vocabulary": {
                        "total_words": len(taught_vocabulary),
                        "words_sample": taught_vocabulary[:20],  # Amostra das primeiras 20
                        "vocabulary_density": len(taught_vocabulary) / max(unit.sequence_order, 1)
                    },
                    "used_strategies": {
                        "strategies": used_strategies,
                        "count": len(used_strategies),
                        "diversity_score": len(set(used_strategies)) / max(len(used_strategies), 1)
                    },
                    "used_assessments": {
                        "assessment_stats": used_assessments,
                        "total_activities": sum(used_assessments.values()) if isinstance(used_assessments, dict) else 0
                    }
                },
                "precedent_units": precedent_units,
                "recommendations": recommendations,
                "progression_insights": {
                    "position_in_book": f"{unit.sequence_order} de {len(all_units)}",
                    "vocabulary_growth_rate": len(taught_vocabulary) / max(unit.sequence_order, 1),
                    "pedagogical_variety": len(set(used_strategies)) + len(set(used_assessments.keys()) if isinstance(used_assessments, dict) else 0)
                }
            },
            message=f"Contexto RAG para unidade '{unit.title}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit.id,
                "sequence": unit.sequence_order
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar contexto RAG da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}/status", response_model=SuccessResponse)
async def update_unit_status(unit_id: str, new_status: UnitStatus):
    """Atualizar status da unidade."""
    
    try:
        logger.info(f"Atualizando status da unidade {unit_id} para {new_status.value}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Atualizar status
        success = await hierarchical_db.update_unit_status(unit_id, new_status)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Falha ao atualizar status"
            )
        
        return SuccessResponse(
            data={
                "unit_id": unit_id,
                "old_status": unit.status.value,
                "new_status": new_status.value,
                "updated": True
            },
            message=f"Status atualizado de '{unit.status.value}' para '{new_status.value}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit.id,
                "sequence": unit.sequence_order
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar status da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


def _calculate_completion_percentage(unit) -> float:
    """Calcular porcentagem de conclusão da unidade."""
    components = [
        bool(unit.vocabulary),
        bool(unit.sentences),
        bool(unit.tips or unit.grammar),
        bool(unit.assessments)
    ]
    return (sum(components) / len(components)) * 100


def _get_next_actions_for_unit(unit) -> List[str]:
    """Determinar próximas ações baseadas no estado da unidade."""
    actions = []
    
    if unit.status.value == "creating":
        actions.append(f"POST /api/v2/units/{unit.id}/vocabulary")
    elif unit.status.value == "vocab_pending":
        actions.append(f"POST /api/v2/units/{unit.id}/vocabulary")
    elif unit.status.value == "sentences_pending":
        actions.append(f"POST /api/v2/units/{unit.id}/sentences")
    elif unit.status.value == "content_pending":
        if unit.unit_type.value == "lexical_unit":
            actions.append(f"POST /api/v2/units/{unit.id}/tips")
        else:
            actions.append(f"POST /api/v2/units/{unit.id}/grammar")
    elif unit.status.value == "assessments_pending":
        actions.append(f"POST /api/v2/units/{unit.id}/assessments")
    
    actions.append(f"GET /api/v2/units/{unit.id}/context")
    
    return actions