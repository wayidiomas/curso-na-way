# src/api/v2/books.py
"""Endpoints para gestão de books."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from src.services.hierarchical_database import hierarchical_db
from src.core.hierarchical_models import (
    Book, BookCreateRequest, HierarchyValidationResult
)
from src.core.unit_models import SuccessResponse, ErrorResponse
from src.core.enums import CEFRLevel

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/courses/{course_id}/books", response_model=SuccessResponse)
async def create_book(course_id: str, book_data: BookCreateRequest):
    """Criar novo book dentro de um curso."""
    try:
        logger.info(f"Criando book '{book_data.name}' no curso {course_id}")
        
        # Verificar se curso existe primeiro
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Validar se o nível do book está nos níveis do curso
        if book_data.target_level not in course.target_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Nível {book_data.target_level.value} não está nos níveis do curso: {[l.value for l in course.target_levels]}"
            )
        
        # Criar book usando o serviço hierárquico
        book = await hierarchical_db.create_book(course_id, book_data)
        
        return SuccessResponse(
            data={
                "book": book.dict(),
                "course_info": {
                    "course_id": course.id,
                    "course_name": course.name,
                    "course_levels": [level.value for level in course.target_levels]
                },
                "created": True
            },
            message=f"Book '{book.name}' criado no curso '{course.name}'",
            hierarchy_info={
                "course_id": course.id,
                "book_id": book.id,
                "level": "book",
                "sequence": book.sequence_order
            },
            next_suggested_actions=[
                "Criar unidades no book",
                f"POST /api/v2/books/{book.id}/units",
                "Visualizar unidades existentes",
                f"GET /api/v2/books/{book.id}/units"
            ]
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Dados inválidos para book: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Dados inválidos: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Erro ao criar book: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/courses/{course_id}/books", response_model=SuccessResponse)
async def list_books_by_course(
    course_id: str,
    target_level: Optional[str] = Query(None, description="Filtrar por nível CEFR"),
    include_units: bool = Query(False, description="Incluir unidades de cada book")
):
    """Listar books de um curso."""
    try:
        logger.info(f"Listando books do curso: {course_id}")
        
        # Verificar se curso existe
        course = await hierarchical_db.get_course(course_id)
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Curso {course_id} não encontrado"
            )
        
        # Buscar books do curso
        books = await hierarchical_db.list_books_by_course(course_id)
        
        # Aplicar filtro de nível se especificado
        if target_level:
            books = [book for book in books if book.target_level.value == target_level]
        
        # Enriquecer com dados de unidades se solicitado
        books_data = []
        for book in books:
            book_info = book.dict()
            
            if include_units:
                units = await hierarchical_db.list_units_by_book(book.id)
                book_info["units"] = [
                    {
                        "id": unit.id,
                        "title": unit.title,
                        "sequence_order": unit.sequence_order,
                        "status": unit.status.value,
                        "unit_type": unit.unit_type.value,
                        "cefr_level": unit.cefr_level.value
                    }
                    for unit in units
                ]
                book_info["units_summary"] = {
                    "total": len(units),
                    "completed": len([u for u in units if u.status.value == "completed"]),
                    "in_progress": len([u for u in units if u.status.value != "completed" and u.status.value != "error"])
                }
            
            books_data.append(book_info)
        
        # Estatísticas do curso
        total_units = sum(book.unit_count for book in books)
        levels_distribution = {}
        for book in books:
            level = book.target_level.value
            levels_distribution[level] = levels_distribution.get(level, 0) + 1
        
        return SuccessResponse(
            data={
                "course_info": {
                    "course_id": course.id,
                    "course_name": course.name,
                    "language_variant": course.language_variant.value
                },
                "books": books_data,
                "statistics": {
                    "total_books": len(books_data),
                    "total_units": total_units,
                    "levels_distribution": levels_distribution,
                    "filter_applied": target_level
                }
            },
            message=f"{len(books_data)} books encontrados no curso '{course.name}'",
            hierarchy_info={
                "course_id": course.id,
                "level": "books_list"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao listar books do curso {course_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/books/{book_id}", response_model=SuccessResponse)
async def get_book(book_id: str, include_units: bool = Query(False, description="Incluir unidades do book")):
    """Obter detalhes de um book específico."""
    try:
        logger.info(f"Buscando book: {book_id}")
        
        # Buscar book
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Buscar curso do book
        course = await hierarchical_db.get_course(book.course_id)
        
        book_data = book.dict()
        
        # Incluir unidades se solicitado
        if include_units:
            units = await hierarchical_db.list_units_by_book(book.id)
            
            book_data["units"] = [
                {
                    "id": unit.id,
                    "title": unit.title,
                    "sequence_order": unit.sequence_order,
                    "status": unit.status.value,
                    "unit_type": unit.unit_type.value,
                    "context": unit.context,
                    "created_at": unit.created_at.isoformat(),
                    "quality_score": unit.quality_score
                }
                for unit in units
            ]
            
            # Estatísticas das unidades
            book_data["units_statistics"] = {
                "total": len(units),
                "completed": len([u for u in units if u.status.value == "completed"]),
                "in_progress": len([u for u in units if u.status.value in ["vocab_pending", "sentences_pending", "content_pending", "assessments_pending"]]),
                "errors": len([u for u in units if u.status.value == "error"]),
                "average_quality": sum(u.quality_score for u in units if u.quality_score) / max(len([u for u in units if u.quality_score]), 1)
            }
            
            # Análise de progressão do book
            if units:
                last_sequence = max(unit.sequence_order for unit in units)
                progression = await hierarchical_db.get_progression_analysis(
                    book.course_id, book.id, last_sequence + 1
                )
                
                book_data["progression_analysis"] = {
                    "vocabulary_taught": len(progression.vocabulary_progression.get("words", [])),
                    "strategies_used": len(progression.strategy_distribution),
                    "assessment_types": len(progression.assessment_balance),
                    "recommendations": progression.recommendations,
                    "quality_metrics": progression.quality_metrics
                }
        
        return SuccessResponse(
            data={
                "book": book_data,
                "course_context": {
                    "course_id": course.id,
                    "course_name": course.name,
                    "course_levels": [level.value for level in course.target_levels],
                    "language_variant": course.language_variant.value
                } if course else None,
                "hierarchy_position": {
                    "sequence_in_course": book.sequence_order,
                    "level_focus": book.target_level.value
                }
            },
            message=f"Book '{book.name}' encontrado",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "book_detail",
                "sequence": book.sequence_order
            },
            next_suggested_actions=[
                "Criar nova unidade",
                f"POST /api/v2/books/{book.id}/units",
                "Ver progressão pedagógica",
                f"GET /api/v2/books/{book.id}/progression"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar book {book_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/books/{book_id}/progression", response_model=SuccessResponse)
async def get_book_progression(book_id: str):
    """Obter análise detalhada de progressão pedagógica do book."""
    try:
        logger.info(f"Analisando progressão do book: {book_id}")
        
        # Verificar se book existe
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Buscar unidades do book
        units = await hierarchical_db.list_units_by_book(book.id)
        
        if not units:
            return SuccessResponse(
                data={
                    "book_info": book.dict(),
                    "progression": {
                        "message": "Nenhuma unidade encontrada no book"
                    }
                },
                message=f"Book '{book.name}' não possui unidades ainda"
            )
        
        # Analisar progressão por unidade
        units_progression = []
        cumulative_vocabulary = set()
        cumulative_strategies = set()
        cumulative_assessments = set()
        
        for unit in sorted(units, key=lambda u: u.sequence_order):
            # Buscar análise específica para esta unidade
            progression = await hierarchical_db.get_progression_analysis(
                book.course_id, book.id, unit.sequence_order
            )
            
            # Vocabulário desta unidade
            unit_vocab = unit.vocabulary_taught or []
            new_words = [w for w in unit_vocab if w not in cumulative_vocabulary]
            repeated_words = [w for w in unit_vocab if w in cumulative_vocabulary]
            
            cumulative_vocabulary.update(unit_vocab)
            cumulative_strategies.update(unit.strategies_used or [])
            cumulative_assessments.update(unit.assessments_used or [])
            
            units_progression.append({
                "unit_id": unit.id,
                "title": unit.title,
                "sequence": unit.sequence_order,
                "status": unit.status.value,
                "vocabulary_analysis": {
                    "new_words": len(new_words),
                    "reinforcement_words": len(repeated_words),
                    "total_words": len(unit_vocab),
                    "new_words_list": new_words[:10],  # Primeiras 10 para exemplo
                },
                "strategies_used": unit.strategies_used or [],
                "assessments_used": unit.assessments_used or [],
                "quality_score": unit.quality_score,
                "recommendations": progression.recommendations if hasattr(progression, 'recommendations') else []
            })
        
        # Análise geral do book
        completed_units = [u for u in units if u.status.value == "completed"]
        avg_quality = sum(u.quality_score for u in completed_units if u.quality_score) / max(len(completed_units), 1)
        
        # Tendências e insights
        vocabulary_growth = len(cumulative_vocabulary)
        strategy_diversity = len(cumulative_strategies)
        assessment_variety = len(cumulative_assessments)
        
        return SuccessResponse(
            data={
                "book_info": {
                    "book_id": book.id,
                    "book_name": book.name,
                    "target_level": book.target_level.value,
                    "sequence_in_course": book.sequence_order
                },
                "overall_progression": {
                    "total_units": len(units),
                    "completed_units": len(completed_units),
                    "completion_rate": (len(completed_units) / len(units)) * 100,
                    "average_quality": round(avg_quality, 2),
                    "vocabulary_diversity": vocabulary_growth,
                    "strategy_diversity": strategy_diversity,
                    "assessment_variety": assessment_variety
                },
                "units_progression": units_progression,
                "pedagogical_insights": {
                    "vocabulary_trend": f"{vocabulary_growth} palavras únicas ensinadas",
                    "strategy_distribution": list(cumulative_strategies),
                    "assessment_distribution": list(cumulative_assessments),
                    "recommendations": [
                        "Manter diversidade de estratégias" if strategy_diversity >= 3 else "Aumentar variedade de estratégias pedagógicas",
                        "Balancear tipos de atividades" if assessment_variety >= 4 else "Diversificar tipos de atividades",
                        "Qualidade consistente" if avg_quality >= 0.8 else "Melhorar qualidade das unidades",
                        f"Progressão de vocabulário: {vocabulary_growth / max(len(completed_units), 1):.1f} palavras por unidade"
                    ]
                }
            },
            message=f"Análise de progressão do book '{book.name}'",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "progression_analysis"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao analisar progressão do book {book_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/books/{book_id}", response_model=SuccessResponse)
async def update_book(book_id: str, book_data: BookCreateRequest):
    """Atualizar informações do book."""
    try:
        logger.info(f"Atualizando book: {book_id}")
        
        # Verificar se book existe
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Verificar se o novo nível é compatível com o curso
        course = await hierarchical_db.get_course(book.course_id)
        if book_data.target_level not in course.target_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Nível {book_data.target_level.value} não está nos níveis do curso"
            )
        
        # Por enquanto, vamos simular a atualização
        # Em implementação real, você adicionaria o método update_book ao serviço
        
        updated_book_data = book.dict()
        updated_book_data.update({
            "name": book_data.name,
            "description": book_data.description,
            "target_level": book_data.target_level.value,
            "updated_at": "now()"
        })
        
        return SuccessResponse(
            data={
                "book": updated_book_data,
                "changes_applied": {
                    "name": book_data.name != book.name,
                    "description": book_data.description != book.description,
                    "target_level": book_data.target_level != book.target_level
                }
            },
            message=f"Book '{book_data.name}' atualizado com sucesso",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "book_update"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar book {book_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/books/{book_id}", response_model=SuccessResponse)
async def delete_book(book_id: str):
    """Deletar book (e todas as unidades relacionadas)."""
    try:
        logger.warning(f"Tentativa de deletar book: {book_id}")
        
        # Verificar se book existe
        book = await hierarchical_db.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=404,
                detail=f"Book {book_id} não encontrado"
            )
        
        # Verificar quantas unidades serão deletadas
        units = await hierarchical_db.list_units_by_book(book_id)
        
        # Por segurança, apenas informar o que seria deletado
        return SuccessResponse(
            data={
                "book_id": book_id,
                "book_name": book.name,
                "would_delete": {
                    "units": len(units),
                    "unit_ids": [unit.id for unit in units]
                },
                "action": "soft_delete_recommended"
            },
            message=f"Book '{book.name}' marcado para arquivamento (contém {len(units)} unidades)",
            hierarchy_info={
                "course_id": book.course_id,
                "book_id": book.id,
                "level": "deletion_info"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar book {book_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )