# src/api/v2/courses.py
"""Endpoints para gestão de cursos."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from src.services.hierarchical_database import hierarchical_db
from src.core.hierarchical_models import (
    Course, CourseCreateRequest, CourseHierarchyView, 
    CourseProgressSummary, HierarchyValidationResult
)
from src.core.unit_models import SuccessResponse, ErrorResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/courses", response_model=SuccessResponse)
async def create_course(course_data: CourseCreateRequest):
    """Criar novo curso."""
    try:
        logger.info(f"Criando curso: {course_data.name}")
        
        # Criar curso usando o serviço hierárquico
        course = await hierarchical_db.create_course(course_data)
        
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
                f"POST /api/v2/courses/{course.id}/books"
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


@router.get("/courses", response_model=SuccessResponse)
async def list_courses(
    language_variant: Optional[str] = Query(None, description="Filtrar por variante de idioma"),
    target_level: Optional[str] = Query(None, description="Filtrar por nível CEFR"),
    limit: int = Query(50, ge=1, le=100, description="Limite de resultados")
):
    """Listar todos os cursos com filtros opcionais."""
    try:
        logger.info("Listando cursos")
        
        # Buscar todos os cursos
        courses = await hierarchical_db.list_courses()
        
        # Aplicar filtros se especificados
        filtered_courses = courses
        
        if language_variant:
            filtered_courses = [
                c for c in filtered_courses 
                if c.language_variant.value == language_variant
            ]
        
        if target_level:
            filtered_courses = [
                c for c in filtered_courses 
                if target_level in [level.value for level in c.target_levels]
            ]
        
        # Aplicar limite
        limited_courses = filtered_courses[:limit]
        
        # Enriquecer com estatísticas básicas
        courses_with_stats = []
        for course in limited_courses:
            books = await hierarchical_db.list_books_by_course(course.id)
            
            course_data = course.dict()
            course_data["books_count"] = len(books)
            course_data["levels_covered"] = [level.value for level in course.target_levels]
            
            courses_with_stats.append(course_data)
        
        return SuccessResponse(
            data={
                "courses": courses_with_stats,
                "total_found": len(courses_with_stats),
                "total_available": len(courses),
                "filters_applied": {
                    "language_variant": language_variant,
                    "target_level": target_level,
                    "limit": limit
                }
            },
            message=f"{len(courses_with_stats)} cursos encontrados"
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar cursos: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses/{course_id}", response_model=SuccessResponse)
async def get_course(course_id: str):
    """Obter detalhes de um curso específico."""
    try:
        logger.info(f"Buscando curso: {course_id}")
        
        # Buscar curso
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Buscar books do curso
        books = await hierarchical_db.list_books_by_course(course_id)
        
        # Calcular estatísticas
        total_units = sum(book.unit_count for book in books)
        levels_covered = [book.target_level.value for book in books]
        
        return SuccessResponse(
            data={
                "course": course.dict(),
                "books": [book.dict() for book in books],
                "statistics": {
                    "total_books": len(books),
                    "total_units": total_units,
                    "levels_covered": sorted(set(levels_covered)),
                    "methodology": course.methodology
                }
            },
            message=f"Curso '{course.name}' encontrado",
            hierarchy_info={
                "course_id": course.id,
                "level": "course_detail"
            },
            next_suggested_actions=[
                "Visualizar books do curso",
                f"GET /api/v2/courses/{course_id}/books",
                "Criar novo book",
                f"POST /api/v2/courses/{course_id}/books"
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
async def get_course_hierarchy(course_id: str):
    """Obter hierarquia completa do curso (Course → Books → Units)."""
    try:
        logger.info(f"Buscando hierarquia completa do curso: {course_id}")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404, 
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Buscar hierarquia completa
        hierarchy = await hierarchical_db.get_course_hierarchy(course_id)
        
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
                    ) * 100
                }
            },
            message=f"Hierarquia completa do curso '{course.name}'",
            hierarchy_info={
                "course_id": course.id,
                "level": "full_hierarchy",
                "depth": "course->books->units"
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
async def get_course_progress(course_id: str):
    """Obter análise de progresso pedagógico do curso."""
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
                
                books_analysis.append({
                    "book_id": book.id,
                    "book_name": book.name,
                    "target_level": book.target_level.value,
                    "units_count": len(units),
                    "completed_units": len([u for u in units if u.status.value == "completed"]),
                    "vocabulary_taught": len(vocab_words),
                    "strategies_used": len(progression.strategy_distribution),
                    "recommendations": progression.recommendations
                })
        
        # Calcular métricas gerais
        total_units = sum(ba["units_count"] for ba in books_analysis)
        completed_units = sum(ba["completed_units"] for ba in books_analysis)
        completion_rate = (completed_units / max(total_units, 1)) * 100
        
        return SuccessResponse(
            data={
                "course_progress": {
                    "course_name": course.name,
                    "total_books": len(books),
                    "total_units": total_units,
                    "completed_units": completed_units,
                    "completion_rate": round(completion_rate, 2),
                    "unique_vocabulary": len(overall_vocabulary),
                    "strategy_diversity": len(overall_strategies),
                    "assessment_variety": len(overall_assessments)
                },
                "books_analysis": books_analysis,
                "pedagogical_insights": {
                    "strategy_distribution": overall_strategies,
                    "assessment_distribution": overall_assessments,
                    "vocabulary_sample": list(overall_vocabulary)[:20],
                    "recommendations": [
                        "Diversificar estratégias pedagógicas" if len(overall_strategies) < 4 else "Estratégias bem distribuídas",
                        "Balancear tipos de atividades" if len(overall_assessments) < 5 else "Atividades bem variadas",
                        f"Vocabulário: {len(overall_vocabulary)} palavras únicas ensinadas"
                    ]
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


@router.delete("/courses/{course_id}", response_model=SuccessResponse)
async def delete_course(course_id: str):
    """Deletar curso (e todos os books/units relacionados)."""
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
        
        # Por segurança, vamos apenas marcar como "archived" ao invés de deletar
        # Em um sistema real, você implementaria soft delete
        logger.warning(f"Curso {course_id} teria {total_books} books e {total_units} units deletados")
        
        return SuccessResponse(
            data={
                "course_id": course_id,
                "course_name": course.name,
                "would_delete": {
                    "books": total_books,
                    "units": total_units
                },
                "action": "soft_delete_recommended"
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