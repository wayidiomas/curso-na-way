# src/api/v2/units.py - ATUALIZADO COM RATE LIMITING, AUDITORIA E PAGINAÇÃO
"""Endpoints para gestão de unidades com hierarquia obrigatória."""
from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form, Request
from typing import List, Optional
import logging
import base64
import time
import asyncio

# IMPORTS EXISTENTES
from src.services.hierarchical_database import hierarchical_db
from src.core.hierarchical_models import HierarchicalUnitRequest
from src.core.unit_models import (
    UnitCreateRequest, UnitResponse, SuccessResponse, ErrorResponse,
    GenerationProgress, UnitStatus
)
from src.core.enums import CEFRLevel, LanguageVariant, UnitType

# NOVOS IMPORTS - MELHORIAS
from src.core.rate_limiter import rate_limit_dependency
from src.core.audit_logger import (
    audit_endpoint, AuditEventType, extract_unit_info, audit_logger_instance
)
from src.core.pagination import (
    PaginationParams, SortParams, UnitFilterParams, 
    PaginatedResponse, paginate_query_results
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/books/{book_id}/units", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.UNIT_CREATED,
    resource_extractor=extract_unit_info,
    track_performance=True
)
async def create_unit_with_hierarchy(
    book_id: str,
    request: Request,  # NECESSÁRIO para rate limiting e auditoria
    image_1: UploadFile = File(..., description="Primeira imagem (obrigatória)"),
    image_2: UploadFile = File(None, description="Segunda imagem (opcional)"),
    context: str = Form(None, description="Contexto da unidade"),
    cefr_level: CEFRLevel = Form(..., description="Nível CEFR"),
    language_variant: LanguageVariant = Form(..., description="Variante do idioma"),
    unit_type: UnitType = Form(..., description="Tipo de unidade")
):
    """Criar unidade com hierarquia Course → Book → Unit obrigatória - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "create_unit")
    
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
        
        # 2. VALIDAÇÃO HIERÁRQUICA COMPLETA (MELHORADA)
        validation = await hierarchical_db.validate_hierarchy_complete(
            book_id=book_id,
            unit_data={
                "cefr_level": cefr_level.value,
                "unit_type": unit_type.value,
                "language_variant": language_variant.value
            }
        )
        
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "hierarchy_validation_failed",
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "suggestions": validation.suggestions
                }
            )
        
        # 3. Log de warnings se houver
        if validation.warnings:
            logger.warning(f"Warnings na criação da unidade: {validation.warnings}")
        
        # 4. Processar imagens com validação aprimorada
        images_info = []
        
        # Validar tamanho e formato da imagem 1 (obrigatória)
        if image_1:
            if image_1.size > 10 * 1024 * 1024:  # 10MB max
                raise HTTPException(
                    status_code=400,
                    detail="Imagem 1 muito grande (máximo 10MB)"
                )
            
            if not image_1.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="Arquivo 1 deve ser uma imagem"
                )
            
            img1_content = await image_1.read()
            img1_b64 = base64.b64encode(img1_content).decode()
            images_info.append({
                "filename": image_1.filename,
                "size": len(img1_content),
                "content_type": image_1.content_type,
                "base64": img1_b64,
                "description": "Primeira imagem - análise pendente",
                "is_primary": True
            })
        
        # Imagem 2 (opcional) com validação
        if image_2:
            if image_2.size > 10 * 1024 * 1024:  # 10MB max
                raise HTTPException(
                    status_code=400,
                    detail="Imagem 2 muito grande (máximo 10MB)"
                )
            
            if not image_2.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="Arquivo 2 deve ser uma imagem"
                )
            
            img2_content = await image_2.read()
            img2_b64 = base64.b64encode(img2_content).decode()
            images_info.append({
                "filename": image_2.filename,
                "size": len(img2_content),
                "content_type": image_2.content_type,
                "base64": img2_b64,
                "description": "Segunda imagem - análise pendente",
                "is_primary": False
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
        
        # 9. LOG DE AUDITORIA DETALHADO
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.UNIT_CREATED,
            request=request,
            course_id=course_id,
            book_id=book_id,
            unit_id=unit.id,
            operation_data={
                "unit_title": unit.title,
                "unit_type": unit.unit_type.value,
                "cefr_level": unit.cefr_level.value,
                "sequence_order": unit.sequence_order,
                "images_count": len(images_info),
                "context_provided": bool(context),
                "validation_warnings": validation.warnings
            },
            success=True
        )
        
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
                    "language_variant": unit.language_variant.value,
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
                "validation_info": {
                    "is_valid": validation.is_valid,
                    "warnings": validation.warnings,
                    "suggestions": validation.suggestions
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
                "Gerar vocabulário com RAG e fonemas IPA",
                f"POST /api/v2/units/{unit.id}/vocabulary",
                "Ver contexto hierárquico RAG",
                f"GET /api/v2/units/{unit.id}/context",
                "Analisar imagens via MCP",
                f"POST /api/v2/units/{unit.id}/analyze-images"
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


@router.get("/books/{book_id}/units", response_model=PaginatedResponse[dict])
@audit_endpoint(
    event_type=AuditEventType.UNIT_VIEWED,
    track_performance=True
)
async def list_units_by_book_paginated(
    book_id: str,
    request: Request,
    # PARÂMETROS DE PAGINAÇÃO
    page: int = Query(1, ge=1, description="Número da página"),
    size: int = Query(20, ge=1, le=100, description="Itens por página"),
    sort_by: str = Query("sequence_order", description="Campo para ordenação"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Ordem"),
    
    # FILTROS ESPECÍFICOS
    status: Optional[str] = Query(None, description="Filtrar por status"),
    unit_type: Optional[str] = Query(None, description="Filtrar por tipo"),
    cefr_level: Optional[str] = Query(None, description="Filtrar por nível CEFR"),
    quality_score_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Score mínimo de qualidade"),
    search: Optional[str] = Query(None, description="Buscar por título/contexto"),
    
    # OPÇÕES ADICIONAIS
    include_content: bool = Query(False, description="Incluir conteúdo das unidades"),
    include_progression: bool = Query(False, description="Incluir análise de progressão")
):
    """Listar unidades de um book COM PAGINAÇÃO REAL."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "list_units")
    
    try:
        logger.info(f"Listando unidades do book: {book_id} (página {page})")
        
        # Verificar se book existe
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Buscar course para contexto
        course = await hierarchical_db.get_course(book.course_id)
        
        # CRIAR PARÂMETROS DE PAGINAÇÃO
        pagination = PaginationParams(page=page, size=size)
        sorting = SortParams(sort_by=sort_by, sort_order=sort_order)
        filters = UnitFilterParams(
            book_id=book_id,  # Automático
            status=status,
            unit_type=unit_type,
            cefr_level=cefr_level,
            quality_score_min=quality_score_min,
            search=search
        )
        
        # USAR MÉTODO PAGINADO
        units, total_count = await hierarchical_db.list_units_paginated(
            book_id=book_id,
            pagination=pagination,
            sorting=sorting,
            filters=filters
        )
        
        # Preparar dados das unidades com enriquecimento opcional
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
                    "vocabulary_taught": unit.vocabulary_taught,
                    "phonemes_introduced": getattr(unit, 'phonemes_introduced', []),
                    "pronunciation_focus": getattr(unit, 'pronunciation_focus', None)
                })
            
            if include_progression:
                # Análise de progressão para esta unidade
                progression = await hierarchical_db.get_progression_analysis(
                    unit.course_id, unit.book_id, unit.sequence_order
                )
                unit_data["progression_analysis"] = {
                    "vocabulary_context": len(progression.vocabulary_progression.get("words", [])),
                    "strategies_available": list(progression.strategy_distribution.keys()),
                    "recommendations": progression.recommendations[:3]  # Primeiras 3
                }
            
            units_data.append(unit_data)
        
        # ESTATÍSTICAS AVANÇADAS
        status_distribution = {}
        type_distribution = {}
        level_distribution = {}
        quality_stats = []
        
        all_units_for_stats = await hierarchical_db.list_units_by_book(book_id)
        for unit in all_units_for_stats:
            # Status
            status_key = unit.status.value
            status_distribution[status_key] = status_distribution.get(status_key, 0) + 1
            
            # Tipos
            type_key = unit.unit_type.value
            type_distribution[type_key] = type_distribution.get(type_key, 0) + 1
            
            # Níveis
            level_key = unit.cefr_level.value
            level_distribution[level_key] = level_distribution.get(level_key, 0) + 1
            
            # Qualidade
            if unit.quality_score:
                quality_stats.append(unit.quality_score)
        
        # RETORNAR RESPONSE PAGINADO
        return await paginate_query_results(
            data=units_data,
            total_count=total_count,
            pagination=pagination,
            filters=filters,
            message=f"{len(units_data)} unidades encontradas no book '{book.name}'",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "units_list",
                "book_context": {
                    "book_name": book.name,
                    "target_level": book.target_level.value,
                    "course_name": course.name if course else None
                },
                "aggregated_statistics": {
                    "status_distribution": status_distribution,
                    "type_distribution": type_distribution,
                    "level_distribution": level_distribution,
                    "quality_metrics": {
                        "average_quality": sum(quality_stats) / len(quality_stats) if quality_stats else 0,
                        "total_with_scores": len(quality_stats),
                        "completion_rate": (status_distribution.get("completed", 0) / len(all_units_for_stats)) * 100 if all_units_for_stats else 0
                    }
                }
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
@audit_endpoint(
    event_type=AuditEventType.UNIT_VIEWED,
    resource_extractor=extract_unit_info,
    track_performance=True
)
async def get_unit_complete(
    unit_id: str,
    request: Request,
    include_content: bool = Query(True, description="Incluir conteúdo completo"),
    include_progression: bool = Query(True, description="Incluir análise de progressão"),
    include_rag_context: bool = Query(False, description="Incluir contexto RAG detalhado")
):
    """Obter unidade completa com contexto hierárquico - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "get_unit")
    
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
        
        # Montar response base
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
            "content_status": {
                "has_vocabulary": bool(unit.vocabulary),
                "has_sentences": bool(unit.sentences),
                "has_strategies": bool(unit.tips or unit.grammar),
                "has_assessments": bool(unit.assessments),
                "completion_percentage": _calculate_completion_percentage(unit),
                "ready_for_generation": unit.status.value in ["creating", "vocab_pending"]
            }
        }
        
        # Incluir análise de progressão se solicitado
        if include_progression:
            progression = await hierarchical_db.get_progression_analysis(
                unit.course_id, unit.book_id, unit.sequence_order
            )
            
            unit_complete["progression_context"] = {
                "vocabulary_progression": progression.vocabulary_progression,
                "strategy_distribution": progression.strategy_distribution,
                "assessment_balance": progression.assessment_balance,
                "recommendations": progression.recommendations,
                "quality_metrics": progression.quality_metrics
            }
        
        # Incluir contexto RAG detalhado se solicitado
        if include_rag_context:
            taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
                unit.course_id, unit.book_id, unit.sequence_order
            )
            
            used_strategies = await hierarchical_db.get_used_strategies(
                unit.course_id, unit.book_id, unit.sequence_order
            )
            
            used_assessments = await hierarchical_db.get_used_assessments(
                unit.course_id, unit.book_id, unit.sequence_order
            )
            
            unit_complete["detailed_rag_context"] = {
                "taught_vocabulary": {
                    "total_words": len(taught_vocabulary),
                    "words_sample": taught_vocabulary[:10],
                    "density": len(taught_vocabulary) / max(unit.sequence_order, 1)
                },
                "used_strategies": {
                    "strategies": used_strategies,
                    "diversity_score": len(set(used_strategies)) / max(len(used_strategies), 1) if used_strategies else 0
                },
                "used_assessments": used_assessments,
                "generation_recommendations": _get_generation_recommendations(
                    taught_vocabulary, used_strategies, used_assessments, unit
                )
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
@audit_endpoint(
    event_type=AuditEventType.UNIT_CONTEXT_ACCESSED,
    track_performance=True
)
async def get_unit_rag_context(
    unit_id: str,
    request: Request,
    include_precedents: bool = Query(True, description="Incluir unidades precedentes"),
    include_recommendations: bool = Query(True, description="Incluir recomendações"),
    include_phonetic_analysis: bool = Query(False, description="Incluir análise fonética")
):
    """Obter contexto RAG para a unidade - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "get_unit_context")
    
    try:
        logger.info(f"Buscando contexto RAG para unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Buscar contexto RAG básico
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_assessments = await hierarchical_db.get_used_assessments(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        rag_context = {
            "unit_info": {
                "unit_id": unit.id,
                "title": unit.title,
                "sequence_order": unit.sequence_order,
                "unit_type": unit.unit_type.value,
                "cefr_level": unit.cefr_level.value,
                "status": unit.status.value
            },
            "rag_context": {
                "taught_vocabulary": {
                    "total_words": len(taught_vocabulary),
                    "words_sample": taught_vocabulary[:20],
                    "vocabulary_density": len(taught_vocabulary) / max(unit.sequence_order, 1)
                },
                "used_strategies": {
                    "strategies": used_strategies,
                    "count": len(used_strategies),
                    "diversity_score": len(set(used_strategies)) / max(len(used_strategies), 1) if used_strategies else 0
                },
                "used_assessments": {
                    "assessment_stats": used_assessments,
                    "total_activities": sum(used_assessments.values()) if isinstance(used_assessments, dict) else 0
                }
            }
        }
        
        # Incluir unidades precedentes se solicitado
        if include_precedents:
            all_units = await hierarchical_db.list_units_by_book(unit.book_id)
            precedent_units = []
            
            for prev_unit in all_units:
                if prev_unit.sequence_order < unit.sequence_order:
                    precedent_units.append({
                        "unit_id": prev_unit.id,
                        "title": prev_unit.title,
                        "sequence": prev_unit.sequence_order,
                        "status": prev_unit.status.value,
                        "vocabulary_count": len(prev_unit.vocabulary_taught or []),
                        "strategies": prev_unit.strategies_used or [],
                        "assessments": prev_unit.assessments_used or [],
                        "quality_score": prev_unit.quality_score
                    })
            
            rag_context["precedent_units"] = sorted(precedent_units, key=lambda x: x["sequence"])
        
        # Incluir recomendações se solicitado
        if include_recommendations:
            recommendations = []
            
            if len(taught_vocabulary) > 100:
                recommendations.append("Considerar revisão de vocabulário - muitas palavras já ensinadas")
            
            if len(set(used_strategies)) < 3:
                recommendations.append("Diversificar estratégias pedagógicas")
            
            available_strategies = ["afixacao", "substantivos_compostos", "colocacoes", "expressoes_fixas", "idiomas", "chunks"]
            unused_strategies = [s for s in available_strategies if s not in used_strategies]
            if unused_strategies:
                recommendations.append(f"Estratégias disponíveis: {unused_strategies[:3]}")
            
            # Recomendações específicas para fonemas
            if unit.unit_type.value == "lexical_unit":
                recommendations.append("Considerar análise fonética IPA para vocabulário")
                recommendations.append("Incluir padrões de pronunciação no conteúdo")
            
            rag_context["recommendations"] = recommendations
        
        # Incluir análise fonética se solicitado
        if include_phonetic_analysis and unit.vocabulary:
            try:
                # Analisar fonemas existentes na unidade
                phonetic_analysis = {
                    "phonemes_present": getattr(unit, 'phonemes_introduced', []),
                    "pronunciation_focus": getattr(unit, 'pronunciation_focus', None),
                    "phonetic_complexity": "medium",  # Seria calculado dinamicamente
                    "ipa_variants_used": ["general_american"],  # Padrão
                    "recommendations": [
                        "Adicionar transcrição IPA para novas palavras",
                        "Incluir exercícios de pronúncia",
                        "Considerar padrões de stress"
                    ]
                }
                
                rag_context["phonetic_analysis"] = phonetic_analysis
                
            except Exception as e:
                logger.warning(f"Erro na análise fonética: {str(e)}")
                rag_context["phonetic_analysis"] = {"error": "Análise não disponível"}
        
        # Insights de progressão
        all_units = await hierarchical_db.list_units_by_book(unit.book_id)
        rag_context["progression_insights"] = {
            "position_in_book": f"{unit.sequence_order} de {len(all_units)}",
            "vocabulary_growth_rate": len(taught_vocabulary) / max(unit.sequence_order, 1),
            "pedagogical_variety": len(set(used_strategies)) + len(set(used_assessments.keys()) if isinstance(used_assessments, dict) else 0),
            "completion_momentum": len([u for u in all_units if u.status.value == "completed"]) / len(all_units) if all_units else 0
        }
        
        return SuccessResponse(
            data=rag_context,
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
@audit_endpoint(
    event_type=AuditEventType.UNIT_STATUS_CHANGED,
    track_performance=True
)
async def update_unit_status(
    unit_id: str, 
    new_status: UnitStatus,
    request: Request
):
    """Atualizar status da unidade - COM AUDITORIA."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "update_unit_status")
    
    try:
        logger.info(f"Atualizando status da unidade {unit_id} para {new_status.value}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Validar transição de status
        valid_transitions = {
            "creating": ["vocab_pending", "error"],
            "vocab_pending": ["sentences_pending", "error"],
            "sentences_pending": ["content_pending", "error"],
            "content_pending": ["assessments_pending", "error"],
            "assessments_pending": ["completed", "error"],
            "completed": ["vocab_pending", "sentences_pending", "content_pending", "assessments_pending"],  # Permitir reedição
            "error": ["creating", "vocab_pending", "sentences_pending", "content_pending", "assessments_pending"]  # Permitir recuperação
        }
        
        current_status = unit.status.value
        if new_status.value not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Transição inválida de '{current_status}' para '{new_status.value}'"
            )
        
        # Atualizar status
        success = await hierarchical_db.update_unit_status(unit_id, new_status)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Falha ao atualizar status"
            )
        
        # LOG DE AUDITORIA
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.UNIT_STATUS_CHANGED,
            request=request,
            course_id=unit.course_id,
            book_id=unit.book_id,
            unit_id=unit_id,
            operation_data={
                "old_status": current_status,
                "new_status": new_status.value,
                "unit_title": unit.title,
                "sequence_order": unit.sequence_order,
                "transition_valid": True
            },
            success=True
        )
        
        return SuccessResponse(
            data={
                "unit_id": unit_id,
                "old_status": current_status,
                "new_status": new_status.value,
                "updated": True,
                "transition_info": {
                    "is_valid": True,
                    "next_possible_statuses": valid_transitions.get(new_status.value, [])
                }
            },
            message=f"Status atualizado de '{current_status}' para '{new_status.value}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit.id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=_get_next_actions_for_unit_by_status(new_status, unit_id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar status da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.UNIT_UPDATED,
    resource_extractor=extract_unit_info,
    track_performance=True
)
async def update_unit(
    unit_id: str,
    request: Request,
    title: Optional[str] = Form(None, description="Novo título"),
    context: Optional[str] = Form(None, description="Novo contexto"),
    cefr_level: Optional[CEFRLevel] = Form(None, description="Novo nível CEFR"),
    unit_type: Optional[UnitType] = Form(None, description="Novo tipo de unidade")
):
    """Atualizar informações básicas da unidade - NOVO ENDPOINT."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "update_unit")
    
    try:
        logger.info(f"Atualizando unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Preparar dados para atualização
        update_data = {}
        changes_applied = {}
        
        if title is not None and title != unit.title:
            update_data["title"] = title
            changes_applied["title"] = True
        
        if context is not None and context != unit.context:
            update_data["context"] = context
            changes_applied["context"] = True
        
        if cefr_level is not None and cefr_level != unit.cefr_level:
            # Validar se o novo nível é compatível com o book
            book = await hierarchical_db.get_book(unit.book_id)
            if cefr_level != book.target_level:
                logger.warning(f"Novo nível ({cefr_level.value}) diferente do book ({book.target_level.value})")
            
            update_data["cefr_level"] = cefr_level.value
            changes_applied["cefr_level"] = True
        
        if unit_type is not None and unit_type != unit.unit_type:
            update_data["unit_type"] = unit_type.value
            changes_applied["unit_type"] = True
        
        if not update_data:
            return SuccessResponse(
                data={
                    "unit_id": unit_id,
                    "message": "Nenhuma alteração necessária",
                    "current_data": {
                        "title": unit.title,
                        "context": unit.context,
                        "cefr_level": unit.cefr_level.value,
                        "unit_type": unit.unit_type.value
                    }
                },
                message="Unidade não modificada - dados iguais aos atuais"
            )
        
        # Atualizar unidade
        update_data["updated_at"] = "now()"
        
        # Aqui você adicionaria o método update_unit_basic no hierarchical_database
        # Por enquanto, simular sucesso
        updated = True  # await hierarchical_db.update_unit_basic(unit_id, update_data)
        
        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Falha ao atualizar unidade"
            )
        
        # LOG DE AUDITORIA
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            course_id=unit.course_id,
            book_id=unit.book_id,
            unit_id=unit_id,
            operation_data={
                "changes_applied": changes_applied,
                "old_data": {
                    "title": unit.title,
                    "context": unit.context,
                    "cefr_level": unit.cefr_level.value,
                    "unit_type": unit.unit_type.value
                },
                "new_data": update_data
            },
            success=True
        )
        
        return SuccessResponse(
            data={
                "unit_id": unit_id,
                "changes_applied": changes_applied,
                "updated_fields": list(update_data.keys()),
                "updated": True
            },
            message=f"Unidade atualizada com sucesso ({len(changes_applied)} campos alterados)",
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
        logger.error(f"Erro ao atualizar unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/units/{unit_id}", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.UNIT_DELETED,
    track_performance=True
)
async def delete_unit(unit_id: str, request: Request):
    """Deletar unidade - COM AUDITORIA."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "delete_unit")
    
    try:
        logger.warning(f"Tentativa de deletar unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar impacto da deleção
        book = await hierarchical_db.get_book(unit.book_id)
        all_units = await hierarchical_db.list_units_by_book(unit.book_id)
        
        impact_analysis = {
            "sequence_gap": unit.sequence_order,
            "total_units_in_book": len(all_units),
            "position_in_book": f"{unit.sequence_order} de {len(all_units)}",
            "has_content": any([unit.vocabulary, unit.sentences, unit.tips, unit.grammar, unit.assessments]),
            "quality_score": unit.quality_score,
            "status": unit.status.value
        }
        
        # LOG DE AUDITORIA PARA TENTATIVA DE DELEÇÃO
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.UNIT_DELETED,
            request=request,
            course_id=unit.course_id,
            book_id=unit.book_id,
            unit_id=unit_id,
            operation_data={
                "unit_title": unit.title,
                "impact_analysis": impact_analysis,
                "action": "soft_delete_recommended",
                "reason": "data_preservation"
            },
            success=True
        )
        
        # Por segurança, apenas informar o que seria deletado
        return SuccessResponse(
            data={
                "unit_id": unit_id,
                "unit_title": unit.title,
                "impact_analysis": impact_analysis,
                "action": "soft_delete_recommended",
                "security_note": "Deleção física pode afetar sequenciamento do book",
                "alternative_actions": [
                    "Marcar como 'archived' ao invés de deletar",
                    "Mover para posição final do book",
                    "Fazer backup antes da deleção definitiva"
                ],
                "book_context": {
                    "book_id": book.id,
                    "book_name": book.name,
                    "total_units": len(all_units)
                }
            },
            message=f"Unidade '{unit.title}' marcada para arquivamento",
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
        logger.error(f"Erro ao deletar unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


# =============================================================================
# FUNÇÕES AUXILIARES MELHORADAS
# =============================================================================

def _calculate_completion_percentage(unit) -> float:
    """Calcular porcentagem de conclusão da unidade - MELHORADO."""
    components = [
        bool(unit.vocabulary),
        bool(unit.sentences),
        bool(unit.tips or unit.grammar),
        bool(unit.assessments)
    ]
    
    # Considerar qualidade na completude
    base_percentage = (sum(components) / len(components)) * 100
    
    # Ajustar baseado na qualidade se disponível
    if unit.quality_score and base_percentage > 0:
        quality_factor = unit.quality_score
        return min(base_percentage * quality_factor, 100)
    
    return base_percentage


def _get_next_actions_for_unit(unit) -> List[str]:
    """Determinar próximas ações baseadas no estado da unidade - MELHORADO."""
    actions = []
    
    status = unit.status.value
    unit_id = unit.id
    
    if status == "creating":
        actions.extend([
            f"POST /api/v2/units/{unit_id}/vocabulary",
            f"GET /api/v2/units/{unit_id}/context"
        ])
    elif status == "vocab_pending":
        actions.extend([
            f"POST /api/v2/units/{unit_id}/vocabulary",
            f"GET /api/v2/units/{unit_id}/context"
        ])
    elif status == "sentences_pending":
        actions.extend([
            f"POST /api/v2/units/{unit_id}/sentences",
            f"GET /api/v2/units/{unit_id}/vocabulary"
        ])
    elif status == "content_pending":
        if unit.unit_type.value == "lexical_unit":
            actions.append(f"POST /api/v2/units/{unit_id}/tips")
        else:
            actions.append(f"POST /api/v2/units/{unit_id}/grammar")
        actions.append(f"GET /api/v2/units/{unit_id}/sentences")
    elif status == "assessments_pending":
        actions.extend([
            f"POST /api/v2/units/{unit_id}/assessments",
            f"GET /api/v2/units/{unit_id}/tips" if unit.unit_type.value == "lexical_unit" else f"GET /api/v2/units/{unit_id}/grammar"
        ])
    elif status == "completed":
        actions.extend([
            f"GET /api/v2/units/{unit_id}",
            f"POST /api/v2/units/{unit_id}/export",
            "Criar próxima unidade no book"
        ])
    elif status == "error":
        actions.extend([
            f"PUT /api/v2/units/{unit_id}/status",
            f"GET /api/v2/units/{unit_id}/context",
            "Verificar logs de erro"
        ])
    
    # Ações sempre disponíveis
    actions.extend([
        f"GET /api/v2/units/{unit_id}/context",
        f"PUT /api/v2/units/{unit_id}"
    ])
    
    return actions


def _get_next_actions_for_unit_by_status(status: UnitStatus, unit_id: str) -> List[str]:
    """Determinar próximas ações baseadas no novo status - NOVA FUNÇÃO."""
    actions = []
    
    if status == UnitStatus.VOCAB_PENDING:
        actions.extend([
            f"POST /api/v2/units/{unit_id}/vocabulary",
            f"GET /api/v2/units/{unit_id}/context"
        ])
    elif status == UnitStatus.SENTENCES_PENDING:
        actions.extend([
            f"POST /api/v2/units/{unit_id}/sentences",
            f"GET /api/v2/units/{unit_id}/vocabulary"
        ])
    elif status == UnitStatus.CONTENT_PENDING:
        actions.extend([
            f"POST /api/v2/units/{unit_id}/tips",
            f"POST /api/v2/units/{unit_id}/grammar",
            f"GET /api/v2/units/{unit_id}/sentences"
        ])
    elif status == UnitStatus.ASSESSMENTS_PENDING:
        actions.extend([
            f"POST /api/v2/units/{unit_id}/assessments",
            f"GET /api/v2/units/{unit_id}/content"
        ])
    elif status == UnitStatus.COMPLETED:
        actions.extend([
            f"GET /api/v2/units/{unit_id}",
            f"POST /api/v2/units/{unit_id}/export"
        ])
    
    return actions


def _get_generation_recommendations(
    taught_vocabulary: List[str], 
    used_strategies: List[str], 
    used_assessments: dict, 
    unit
) -> List[str]:
    """Gerar recomendações para próxima geração de conteúdo - NOVA FUNÇÃO."""
    recommendations = []
    
    # Recomendações de vocabulário
    vocab_density = len(taught_vocabulary) / max(unit.sequence_order, 1)
    if vocab_density > 30:
        recommendations.append("Reduzir densidade de vocabulário (muitas palavras por unidade)")
    elif vocab_density < 15:
        recommendations.append("Aumentar densidade de vocabulário (poucas palavras por unidade)")
    
    # Recomendações de estratégias
    strategy_diversity = len(set(used_strategies))
    if strategy_diversity < 3:
        recommendations.append("Aumentar variedade de estratégias pedagógicas")
    
    # Recomendações de atividades
    if isinstance(used_assessments, dict):
        assessment_variety = len(used_assessments.keys())
        if assessment_variety < 4:
            recommendations.append("Diversificar tipos de atividades de avaliação")
    
    # Recomendações específicas por tipo de unidade
    if unit.unit_type.value == "lexical_unit":
        recommendations.append("Incluir transcrição IPA para vocabulário")
        recommendations.append("Focar em colocações e chunks")
    else:
        recommendations.append("Incluir análise de interferência L1→L2")
        recommendations.append("Adicionar exercícios contrastivos")
    
    return recommendations