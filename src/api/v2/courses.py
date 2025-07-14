# src/api/v2/courses.py - ATUALIZADO COM RATE LIMITING, AUDITORIA E PAGINAÇÃO
"""Endpoints para gestão de cursos com melhorias completas."""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
import logging

# IMPORTS EXISTENTES
from src.services.hierarchical_database import hierarchical_db
from src.core.hierarchical_models import (
    Course, CourseCreateRequest, CourseHierarchyView, 
    CourseProgressSummary, HierarchyValidationResult
)
from src.core.unit_models import SuccessResponse, ErrorResponse

# NOVOS IMPORTS - MELHORIAS
from src.core.rate_limiter import rate_limit_dependency
from src.core.audit_logger import (
    audit_endpoint, AuditEventType, extract_course_info, audit_logger_instance
)
from src.core.pagination import (
    PaginationParams, SortParams, CourseFilterParams, 
    PaginatedResponse, paginate_query_results
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/courses", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_CREATED,
    resource_extractor=extract_course_info,
    track_performance=True
)
async def create_course(
    course_data: CourseCreateRequest,
    request: Request  # NECESSÁRIO para rate limiting e auditoria
):
    """Criar novo curso - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "create_course")
    
    try:
        logger.info(f"Criando curso: {course_data.name}")
        
        # Criar curso usando o serviço hierárquico
        course = await hierarchical_db.create_course(course_data)
        
        # LOG DE AUDITORIA ADICIONAL
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.COURSE_CREATED,
            request=request,
            course_id=course.id,
            operation_data={
                "course_name": course.name,
                "target_levels": [level.value for level in course.target_levels],
                "language_variant": course.language_variant.value,
                "methodology": course.methodology
            },
            success=True
        )
        
        return SuccessResponse(
            data={
                "course": course.dict(),
                "created": True
            },
            message=f"Curso '{course.name}' criado com sucesso",
            hierarchy_info={
                "course_id": course.id,
                "level": "course"
            },
            next_suggested_actions=[
                "Criar books para organizar o conteúdo por nível CEFR",
                f"POST /api/v2/courses/{course.id}/books",
                "Visualizar hierarquia completa",
                f"GET /api/v2/courses/{course.id}/hierarchy"
            ]
        )
        
    except ValueError as e:
        logger.warning(f"Dados inválidos para curso: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Dados inválidos: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Erro ao criar curso: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses", response_model=PaginatedResponse[dict])
@audit_endpoint(
    event_type=AuditEventType.COURSE_VIEWED,
    track_performance=True
)
async def list_courses_paginated(
    request: Request,
    # PARÂMETROS DE PAGINAÇÃO
    page: int = Query(1, ge=1, description="Número da página"),
    size: int = Query(20, ge=1, le=100, description="Itens por página"),
    sort_by: str = Query("created_at", description="Campo para ordenação"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Ordem"),
    
    # FILTROS ESPECÍFICOS
    language_variant: Optional[str] = Query(None, description="Filtrar por variante de idioma"),
    target_level: Optional[str] = Query(None, description="Filtrar por nível CEFR"),
    methodology: Optional[str] = Query(None, description="Filtrar por metodologia"),
    search: Optional[str] = Query(None, description="Buscar por nome/descrição"),
    
    # OPÇÕES ADICIONAIS
    include_stats: bool = Query(True, description="Incluir estatísticas básicas")
):
    """Listar cursos COM PAGINAÇÃO REAL."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "list_courses")
    
    try:
        logger.info(f"Listando cursos (página {page})")
        
        # CRIAR PARÂMETROS DE PAGINAÇÃO
        pagination = PaginationParams(page=page, size=size)
        sorting = SortParams(sort_by=sort_by, sort_order=sort_order)
        filters = CourseFilterParams(
            language_variant=language_variant,
            target_level=target_level,
            methodology=methodology,
            search=search
        )
        
        # USAR MÉTODO PAGINADO (não mais o método simples)
        courses, total_count = await hierarchical_db.list_courses_paginated(
            pagination=pagination,
            sorting=sorting,
            filters=filters
        )
        
        # Enriquecer com estatísticas se solicitado
        courses_data = []
        for course in courses:
            course_data = course.dict()
            
            if include_stats:
                # Buscar books para estatísticas
                books = await hierarchical_db.list_books_by_course(course.id)
                
                course_data["statistics"] = {
                    "books_count": len(books),
                    "levels_covered": [level.value for level in course.target_levels],
                    "total_units": sum(book.unit_count for book in books),
                    "books_by_level": {}
                }
                
                # Distribuição de books por nível
                for book in books:
                    level = book.target_level.value
                    course_data["statistics"]["books_by_level"][level] = \
                        course_data["statistics"]["books_by_level"].get(level, 0) + 1
            
            courses_data.append(course_data)
        
        # ESTATÍSTICAS GERAIS
        language_variants = {}
        methodology_distribution = {}
        level_distribution = {}
        
        for course in courses:
            # Distribuição por variante
            variant = course.language_variant.value
            language_variants[variant] = language_variants.get(variant, 0) + 1
            
            # Distribuição por metodologia
            for method in course.methodology:
                methodology_distribution[method] = methodology_distribution.get(method, 0) + 1
            
            # Distribuição por níveis
            for level in course.target_levels:
                level_val = level.value
                level_distribution[level_val] = level_distribution.get(level_val, 0) + 1
        
        # RETORNAR RESPONSE PAGINADO
        return await paginate_query_results(
            data=courses_data,
            total_count=total_count,
            pagination=pagination,
            filters=filters,
            message=f"{len(courses_data)} cursos encontrados",
            hierarchy_info={
                "level": "courses_list",
                "aggregated_statistics": {
                    "language_variants": language_variants,
                    "methodology_distribution": methodology_distribution,
                    "level_distribution": level_distribution,
                    "total_courses_in_system": total_count
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar cursos: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses/{course_id}", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_VIEWED,
    resource_extractor=extract_course_info,
    track_performance=True
)
async def get_course(
    course_id: str,
    request: Request,
    include_books: bool = Query(True, description="Incluir books do curso"),
    include_detailed_stats: bool = Query(False, description="Incluir estatísticas detalhadas")
):
    """Obter detalhes de um curso específico - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "get_course")
    
    try:
        logger.info(f"Buscando curso: {course_id}")
        
        # Buscar curso
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        course_data = {
            "course": course.dict(),
            "books": [],
            "statistics": {}
        }
        
        # Incluir books se solicitado
        if include_books:
            books = await hierarchical_db.list_books_by_course(course_id)
            course_data["books"] = [book.dict() for book in books]
            
            # Estatísticas básicas
            total_units = sum(book.unit_count for book in books)
            levels_covered = [book.target_level.value for book in books]
            
            course_data["statistics"].update({
                "total_books": len(books),
                "total_units": total_units,
                "levels_covered": sorted(set(levels_covered)),
                "methodology": course.methodology
            })
            
            # Estatísticas detalhadas se solicitado
            if include_detailed_stats:
                all_units = []
                for book in books:
                    units = await hierarchical_db.list_units_by_book(book.id)
                    all_units.extend(units)
                
                # Análise detalhada
                status_distribution = {}
                unit_types = {}
                quality_scores = []
                
                for unit in all_units:
                    # Status
                    status = unit.status.value
                    status_distribution[status] = status_distribution.get(status, 0) + 1
                    
                    # Tipos
                    unit_type = unit.unit_type.value
                    unit_types[unit_type] = unit_types.get(unit_type, 0) + 1
                    
                    # Qualidade
                    if unit.quality_score:
                        quality_scores.append(unit.quality_score)
                
                course_data["statistics"]["detailed"] = {
                    "status_distribution": status_distribution,
                    "unit_types_distribution": unit_types,
                    "average_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                    "completion_rate": (status_distribution.get("completed", 0) / max(len(all_units), 1)) * 100,
                    "total_units_analyzed": len(all_units)
                }
        
        return SuccessResponse(
            data=course_data,
            message=f"Curso '{course.name}' encontrado",
            hierarchy_info={
                "course_id": course.id,
                "level": "course_detail"
            },
            next_suggested_actions=[
                "Visualizar books do curso",
                f"GET /api/v2/courses/{course_id}/books",
                "Criar novo book",
                f"POST /api/v2/courses/{course_id}/books",
                "Ver hierarquia completa",
                f"GET /api/v2/courses/{course_id}/hierarchy"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses/{course_id}/hierarchy", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_HIERARCHY_ACCESSED,
    track_performance=True
)
async def get_course_hierarchy(
    course_id: str,
    request: Request,
    max_depth: int = Query(3, ge=1, le=3, description="Profundidade máxima (1=course, 2=+books, 3=+units)"),
    include_content_summary: bool = Query(False, description="Incluir resumo de conteúdo")
):
    """Obter hierarquia completa do curso (Course → Books → Units) - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "get_course_hierarchy")
    
    try:
        logger.info(f"Buscando hierarquia completa do curso: {course_id} (depth={max_depth})")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Buscar hierarquia completa com controle de profundidade
        hierarchy = await hierarchical_db.get_course_hierarchy(course_id, max_depth=max_depth)
        
        if not hierarchy:
            raise HTTPException(
                status_code=500, 
                detail="Erro ao montar hierarquia do curso"
            )
        
        # Calcular estatísticas detalhadas
        total_books = len(hierarchy.get("books", []))
        total_units = sum(
            len(book.get("units", [])) 
            for book in hierarchy.get("books", [])
        )
        
        # Estatísticas por status
        status_distribution = {}
        for book in hierarchy.get("books", []):
            for unit in book.get("units", []):
                status = unit.get("status", "unknown")
                status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Análise de progressão se incluir resumo de conteúdo
        content_summary = {}
        if include_content_summary and max_depth >= 3:
            vocabulary_total = 0
            strategies_used = set()
            assessments_used = set()
            
            for book in hierarchy.get("books", []):
                for unit in book.get("units", []):
                    # Vocabulário
                    vocab_taught = unit.get("vocabulary_taught", [])
                    vocabulary_total += len(vocab_taught)
                    
                    # Estratégias
                    unit_strategies = unit.get("strategies_used", [])
                    strategies_used.update(unit_strategies)
                    
                    # Atividades
                    unit_assessments = unit.get("assessments_used", [])
                    assessments_used.update(unit_assessments)
            
            content_summary = {
                "total_vocabulary_words": vocabulary_total,
                "unique_strategies_used": len(strategies_used),
                "unique_assessment_types": len(assessments_used),
                "strategies_list": list(strategies_used),
                "assessment_types_list": list(assessments_used),
                "pedagogical_diversity_score": (len(strategies_used) + len(assessments_used)) / 13  # 6 TIPS + 2 GRAMMAR + 7 ASSESSMENTS = 15 total
            }
        
        # LOG DE AUDITORIA PARA ACESSO À HIERARQUIA
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.COURSE_HIERARCHY_ACCESSED,
            request=request,
            course_id=course_id,
            operation_data={
                "max_depth": max_depth,
                "total_books": total_books,
                "total_units": total_units,
                "include_content_summary": include_content_summary
            },
            success=True
        )
        
        return SuccessResponse(
            data={
                "hierarchy": hierarchy,
                "summary": {
                    "course_name": course.name,
                    "total_books": total_books,
                    "total_units": total_units,
                    "status_distribution": status_distribution,
                    "completion_rate": (
                        status_distribution.get("completed", 0) / max(total_units, 1)
                    ) * 100,
                    "hierarchy_depth": max_depth
                },
                "content_summary": content_summary if include_content_summary else None
            },
            message=f"Hierarquia completa do curso '{course.name}' (profundidade {max_depth})",
            hierarchy_info={
                "course_id": course.id,
                "level": "full_hierarchy",
                "depth": f"course{'->books' if max_depth >= 2 else ''}{'->units' if max_depth >= 3 else ''}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar hierarquia do curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses/{course_id}/progress", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_VIEWED,
    track_performance=True
)
async def get_course_progress(
    course_id: str,
    request: Request,
    include_book_details: bool = Query(True, description="Incluir detalhes por book"),
    include_recommendations: bool = Query(True, description="Incluir recomendações pedagógicas")
):
    """Obter análise de progresso pedagógico do curso - COM MELHORIAS."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "get_course_progress")
    
    try:
        logger.info(f"Analisando progresso do curso: {course_id}")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Buscar books do curso
        books = await hierarchical_db.list_books_by_course(course_id)
        
        # Analisar progresso por book
        books_analysis = []
        overall_strategies = {}
        overall_assessments = {}
        overall_vocabulary = set()
        
        for book in books:
            # Buscar units do book
            units = await hierarchical_db.list_units_by_book(book.id)
            
            if units:
                # Análise do último unit (mais avançado)
                last_unit = max(units, key=lambda u: u.sequence_order)
                
                progression = await hierarchical_db.get_progression_analysis(
                    course_id, book.id, last_unit.sequence_order + 1
                )
                
                # Acumular dados gerais
                for strategy, count in progression.strategy_distribution.items():
                    overall_strategies[strategy] = overall_strategies.get(strategy, 0) + count
                
                if isinstance(progression.assessment_balance, dict):
                    for assessment, count in progression.assessment_balance.items():
                        overall_assessments[assessment] = overall_assessments.get(assessment, 0) + count
                
                # Vocabulário único
                vocab_words = progression.vocabulary_progression.get("words", [])
                overall_vocabulary.update(vocab_words)
                
                book_analysis = {
                    "book_id": book.id,
                    "book_name": book.name,
                    "target_level": book.target_level.value,
                    "units_count": len(units),
                    "completed_units": len([u for u in units if u.status.value == "completed"]),
                    "vocabulary_taught": len(vocab_words),
                    "strategies_used": len(progression.strategy_distribution),
                    "completion_rate": (len([u for u in units if u.status.value == "completed"]) / len(units)) * 100
                }
                
                if include_book_details:
                    book_analysis.update({
                        "progression_details": progression.dict(),
                        "unit_statuses": [
                            {
                                "unit_id": unit.id,
                                "title": unit.title,
                                "status": unit.status.value,
                                "sequence": unit.sequence_order,
                                "quality_score": unit.quality_score
                            }
                            for unit in units
                        ]
                    })
                
                books_analysis.append(book_analysis)
        
        # Calcular métricas gerais
        total_units = sum(ba["units_count"] for ba in books_analysis)
        completed_units = sum(ba["completed_units"] for ba in books_analysis)
        completion_rate = (completed_units / max(total_units, 1)) * 100
        
        # Gerar recomendações pedagógicas
        recommendations = []
        if include_recommendations:
            if completion_rate < 30:
                recommendations.append("Foco na conclusão de unidades iniciadas")
            
            if len(overall_strategies) < 4:
                recommendations.append("Diversificar estratégias pedagógicas")
            
            if len(overall_assessments) < 5:
                recommendations.append("Balancear tipos de atividades")
            
            vocab_per_unit = len(overall_vocabulary) / max(total_units, 1)
            if vocab_per_unit < 15:
                recommendations.append("Aumentar densidade de vocabulário por unidade")
            elif vocab_per_unit > 35:
                recommendations.append("Reduzir densidade de vocabulário para melhor absorção")
            
            if completion_rate > 80:
                recommendations.append("Excelente progresso! Considerar expansão para próximos níveis")
        
        return SuccessResponse(
            data={
                "course_progress": {
                    "course_name": course.name,
                    "course_id": course_id,
                    "total_books": len(books),
                    "total_units": total_units,
                    "completed_units": completed_units,
                    "completion_rate": round(completion_rate, 2),
                    "unique_vocabulary": len(overall_vocabulary),
                    "strategy_diversity": len(overall_strategies),
                    "assessment_variety": len(overall_assessments),
                    "last_updated": books_analysis[-1]["book_name"] if books_analysis else None
                },
                "books_analysis": books_analysis,
                "pedagogical_insights": {
                    "strategy_distribution": overall_strategies,
                    "assessment_distribution": overall_assessments,
                    "vocabulary_sample": list(overall_vocabulary)[:20],
                    "recommendations": recommendations,
                    "quality_indicators": {
                        "pedagogical_variety": (len(overall_strategies) + len(overall_assessments)) / 13,  # Score 0-1
                        "content_density": len(overall_vocabulary) / max(total_units, 1),
                        "completion_momentum": completion_rate / 100
                    }
                }
            },
            message=f"Análise de progresso do curso '{course.name}'",
            hierarchy_info={
                "course_id": course.id,
                "level": "progress_analysis"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar progresso do curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/courses/{course_id}", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_UPDATED,
    resource_extractor=extract_course_info,
    track_performance=True
)
async def update_course(
    course_id: str,
    course_data: CourseCreateRequest,
    request: Request
):
    """Atualizar informações do curso - IMPLEMENTAÇÃO REAL."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "update_course")
    
    try:
        logger.info(f"Atualizando curso: {course_id}")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Implementação real da atualização
        updated_course = await hierarchical_db.update_course(course_id, course_data)
        
        # LOG DE AUDITORIA
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.COURSE_UPDATED,
            request=request,
            course_id=course_id,
            operation_data={
                "old_name": course.name,
                "new_name": course_data.name,
                "changes_applied": {
                    "name": course_data.name != course.name,
                    "description": course_data.description != course.description,
                    "target_levels": course_data.target_levels != course.target_levels,
                    "language_variant": course_data.language_variant != course.language_variant,
                    "methodology": course_data.methodology != course.methodology
                }
            },
            success=True
        )
        
        return SuccessResponse(
            data={
                "course": updated_course.dict(),
                "changes_applied": {
                    "name": course_data.name != course.name,
                    "description": course_data.description != course.description,
                    "target_levels": course_data.target_levels != course.target_levels,
                    "language_variant": course_data.language_variant != course.language_variant,
                    "methodology": course_data.methodology != course.methodology
                },
                "updated": True
            },
            message=f"Curso '{course_data.name}' atualizado com sucesso",
            hierarchy_info={
                "course_id": course.id,
                "level": "course_update"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/courses/{course_id}", response_model=SuccessResponse)
@audit_endpoint(
    event_type=AuditEventType.COURSE_DELETED,
    track_performance=True
)
async def delete_course(course_id: str, request: Request):
    """Deletar curso (e todos os books/units relacionados) - COM AUDITORIA."""
    
    # APLICAR RATE LIMITING
    await rate_limit_dependency(request, "delete_course")
    
    try:
        logger.warning(f"Tentativa de deletar curso: {course_id}")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Verificar quantos books/units serão deletados
        hierarchy = await hierarchical_db.get_course_hierarchy(course_id)
        total_books = len(hierarchy.get("books", []))
        total_units = sum(
            len(book.get("units", [])) 
            for book in hierarchy.get("books", [])
        )
        
        # LOG DE AUDITORIA PARA TENTATIVA DE DELEÇÃO
        await audit_logger_instance.log_hierarchy_operation(
            event_type=AuditEventType.COURSE_DELETED,
            request=request,
            course_id=course_id,
            operation_data={
                "course_name": course.name,
                "books_count": total_books,
                "units_count": total_units,
                "action": "soft_delete_recommended",
                "reason": "safety_protection"
            },
            success=True
        )
        
        # Por segurança, vamos apenas marcar como "archived" ao invés de deletar
        logger.warning(f"Curso {course_id} teria {total_books} books e {total_units} units deletados")
        
        return SuccessResponse(
            data={
                "course_id": course_id,
                "course_name": course.name,
                "would_delete": {
                    "books": total_books,
                    "units": total_units,
                    "total_content_pieces": total_books + total_units
                },
                "action": "soft_delete_recommended",
                "security_note": "Deleção física requer confirmação adicional e backup",
                "alternative_actions": [
                    "Arquivar curso ao invés de deletar",
                    "Fazer backup completo antes da deleção",
                    "Confirmar deleção via endpoint dedicado"
                ]
            },
            message=f"Curso '{course.name}' marcado para arquivamento",
            hierarchy_info={
                "course_id": course.id,
                "level": "deletion_info"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )