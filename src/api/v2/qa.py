# src/api/v2/qa.py
"""
Endpoints para geração de perguntas e respostas pedagógicas.
Implementação do sistema de Q&A do IVO V2 Guide com foco pedagógico.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import time

from src.services.hierarchical_database import hierarchical_db
from src.services.qa_generator import QAGeneratorService
from src.core.unit_models import (
    SuccessResponse, ErrorResponse, QASection
)
from src.core.enums import (
    CEFRLevel, LanguageVariant, UnitType
)
from src.core.audit_logger import (
    audit_logger_instance, AuditEventType, audit_endpoint, extract_unit_info
)
from src.core.rate_limiter import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


async def rate_limit_qa_generation(request):
    """Rate limiting específico para geração de Q&A."""
    await rate_limit_dependency(request, "generate_content")


@router.post("/units/{unit_id}/qa", response_model=SuccessResponse)
@audit_endpoint(AuditEventType.UNIT_CONTENT_GENERATED, extract_unit_info)
async def generate_qa_for_unit(
    unit_id: str,
    request: Request,
    _: None = Depends(rate_limit_qa_generation)
):
    """
    Gerar perguntas e respostas pedagógicas para a unidade.
    
    Flow do IVO V2:
    1. Buscar unidade e validar hierarquia
    2. Verificar se possui conteúdo base (vocabulary, sentences, strategies)
    3. Usar RAG para contexto pedagógico
    4. Gerar perguntas em diferentes níveis cognitivos
    5. Incluir perguntas sobre pronúncia e fonética
    6. Salvar e atualizar status da unidade
    """
    try:
        logger.info(f"Iniciando geração de Q&A para unidade: {unit_id}")
        
        # 1. Buscar e validar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # 2. Verificar se está pronta para Q&A
        if unit.status.value not in ["assessments_pending", "completed"]:
            if unit.status.value in ["creating", "vocab_pending", "sentences_pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Unidade deve ter vocabulário, sentences e estratégias antes de gerar Q&A."
                )
            elif unit.qa:
                logger.info(f"Unidade {unit_id} já possui Q&A - regenerando")
        
        # 3. Verificar pré-requisitos
        if not unit.vocabulary or not unit.vocabulary.get("items"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter vocabulário antes de gerar Q&A."
            )
        
        if not unit.sentences or not unit.sentences.get("sentences"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter sentences antes de gerar Q&A."
            )
        
        # Verificar se tem estratégias (TIPS ou GRAMMAR)
        has_strategies = bool(unit.tips or unit.grammar)
        if not has_strategies:
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter estratégias (TIPS ou GRAMMAR) antes de gerar Q&A."
            )
        
        # 4. Buscar contexto da hierarquia
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        if not course or not book:
            raise HTTPException(
                status_code=400,
                detail="Hierarquia inválida: curso ou book não encontrado"
            )
        
        # 5. Buscar contexto pedagógico
        logger.info("Coletando contexto pedagógico para Q&A...")
        
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # 6. Preparar dados para geração
        qa_params = {
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
                "sentences": unit.sentences,
                "tips": unit.tips,
                "grammar": unit.grammar,
                "assessments": unit.assessments
            },
            "hierarchy_context": {
                "course_name": course.name,
                "book_name": book.name,
                "sequence_order": unit.sequence_order,
                "target_level": book.target_level.value
            },
            "pedagogical_context": {
                "taught_vocabulary": taught_vocabulary,
                "used_strategies": used_strategies,
                "progression_level": _determine_progression_level(unit.sequence_order),
                "learning_objectives": _extract_learning_objectives(unit),
                "phonetic_focus": unit.pronunciation_focus or "general_pronunciation"
            }
        }
        
        # 7. Gerar Q&A usando service
        start_time = time.time()
        qa_generator = QAGeneratorService()
        
        qa_section = await qa_generator.generate_qa_for_unit(qa_params)
        
        generation_time = time.time() - start_time
        
        # 8. Salvar Q&A na unidade
        await hierarchical_db.update_unit_content(
            unit_id, 
            "qa", 
            qa_section.dict()
        )
        
        # 9. Manter ou atualizar status (Q&A é complementar, não muda status principal)
        # Se a unidade estava completa, mantém completa
        # Se estava pendente de assessments, mantém assim
        
        # 10. Log de auditoria
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="qa",
            unit_id=unit_id,
            book_id=unit.book_id,
            course_id=unit.course_id,
            content_stats={
                "questions_count": len(qa_section.questions),
                "answers_count": len(qa_section.answers),
                "pedagogical_notes_count": len(qa_section.pedagogical_notes),
                "vocabulary_integration": len(qa_section.vocabulary_integration),
                "cognitive_levels": qa_section.cognitive_levels,
                "pronunciation_questions": len(qa_section.pronunciation_questions),
                "phonetic_awareness": len(qa_section.phonetic_awareness),
                "difficulty_progression": qa_section.difficulty_progression
            },
            ai_usage={
                "model": "gpt-4o-mini",
                "generation_time": generation_time,
                "pedagogical_approach": "bloom_taxonomy_based"
            },
            processing_time=generation_time,
            success=True
        )
        
        return SuccessResponse(
            data={
                "qa": qa_section.dict(),
                "generation_stats": {
                    "total_questions": len(qa_section.questions),
                    "total_answers": len(qa_section.answers),
                    "pedagogical_notes": len(qa_section.pedagogical_notes),
                    "vocabulary_coverage": len(qa_section.vocabulary_integration),
                    "cognitive_levels_covered": len(set(qa_section.cognitive_levels)),
                    "pronunciation_focus": len(qa_section.pronunciation_questions) > 0,
                    "processing_time": f"{generation_time:.2f}s"
                },
                "unit_enhancement": {
                    "unit_id": unit_id,
                    "previous_status": unit.status.value,
                    "qa_added": True,
                    "pedagogical_value": "Q&A section enhances learning comprehension and retention"
                },
                "pedagogical_analysis": {
                    "difficulty_progression": qa_section.difficulty_progression,
                    "cognitive_levels": qa_section.cognitive_levels,
                    "vocabulary_integration": len(qa_section.vocabulary_integration),
                    "pronunciation_awareness": len(qa_section.pronunciation_questions),
                    "learning_objectives_coverage": len(qa_params["pedagogical_context"]["learning_objectives"])
                }
            },
            message=f"Q&A pedagógico gerado com sucesso para unidade '{unit.title}'",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Revisar perguntas geradas",
                f"GET /api/v2/units/{unit_id}/qa",
                "Analisar qualidade pedagógica",
                f"GET /api/v2/units/{unit_id}/qa/analysis",
                "Finalizar unidade se pendente",
                f"POST /api/v2/units/{unit_id}/assessments" if unit.status.value == "assessments_pending" else "Unit ready for use"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar Q&A para unidade {unit_id}: {str(e)}")
        
        # Log de erro
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="qa",
            unit_id=unit_id,
            book_id=getattr(unit, 'book_id', ''),
            course_id=getattr(unit, 'course_id', ''),
            success=False,
            error_details=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno na geração de Q&A: {str(e)}"
        )


@router.get("/units/{unit_id}/qa", response_model=SuccessResponse)
async def get_unit_qa(unit_id: str, request: Request):
    """Obter Q&A da unidade."""
    try:
        logger.info(f"Buscando Q&A da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui Q&A
        if not unit.qa:
            return SuccessResponse(
                data={
                    "has_qa": False,
                    "unit_status": unit.status.value,
                    "message": "Unidade ainda não possui Q&A gerado",
                    "prerequisites": {
                        "has_vocabulary": bool(unit.vocabulary),
                        "has_sentences": bool(unit.sentences),
                        "has_strategies": bool(unit.tips or unit.grammar),
                        "ready_for_qa": all([
                            unit.vocabulary,
                            unit.sentences,
                            (unit.tips or unit.grammar)
                        ])
                    }
                },
                message="Q&A não encontrado",
                hierarchy_info={
                    "course_id": unit.course_id,
                    "book_id": unit.book_id,
                    "unit_id": unit_id,
                    "sequence": unit.sequence_order
                },
                next_suggested_actions=[
                    "Gerar Q&A pedagógico",
                    f"POST /api/v2/units/{unit_id}/qa"
                ]
            )
        
        # Buscar contexto adicional
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        # Análise do Q&A
        qa_data = unit.qa
        
        return SuccessResponse(
            data={
                "qa": qa_data,
                "analysis": {
                    "total_questions": len(qa_data.get("questions", [])),
                    "total_answers": len(qa_data.get("answers", [])),
                    "pedagogical_notes_count": len(qa_data.get("pedagogical_notes", [])),
                    "vocabulary_integration": qa_data.get("vocabulary_integration", []),
                    "cognitive_levels": qa_data.get("cognitive_levels", []),
                    "difficulty_progression": qa_data.get("difficulty_progression", "unknown"),
                    "pronunciation_questions": qa_data.get("pronunciation_questions", []),
                    "phonetic_awareness": qa_data.get("phonetic_awareness", []),
                    "pedagogical_depth": len(set(qa_data.get("cognitive_levels", [])))
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
                "pedagogical_context": {
                    "learning_objectives_covered": len(qa_data.get("vocabulary_integration", [])),
                    "bloom_taxonomy_levels": qa_data.get("cognitive_levels", []),
                    "pronunciation_focus": len(qa_data.get("pronunciation_questions", [])) > 0,
                    "metacognitive_awareness": len(qa_data.get("phonetic_awareness", []))
                },
                "has_qa": True
            },
            message=f"Q&A da unidade '{unit.title}'",
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
        logger.error(f"Erro ao buscar Q&A da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}/qa", response_model=SuccessResponse)
async def update_unit_qa(
    unit_id: str,
    qa_data: Dict[str, Any],
    request: Request,
    _: None = Depends(rate_limit_qa_generation)
):
    """Atualizar Q&A da unidade (edição manual)."""
    try:
        logger.info(f"Atualizando Q&A da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Validar estrutura básica dos dados
        if not isinstance(qa_data, dict):
            raise HTTPException(
                status_code=400,
                detail="Dados de Q&A devem ser um objeto JSON"
            )
        
        required_fields = ["questions", "answers"]
        for field in required_fields:
            if field not in qa_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo obrigatório ausente: {field}"
                )
        
        # Validar estrutura das perguntas e respostas
        questions = qa_data["questions"]
        answers = qa_data["answers"]
        
        if not isinstance(questions, list) or not isinstance(answers, list):
            raise HTTPException(
                status_code=400,
                detail="Questions e answers devem ser listas"
            )
        
        if len(questions) != len(answers):
            raise HTTPException(
                status_code=400,
                detail="Número de perguntas deve ser igual ao número de respostas"
            )
        
        # Validar conteúdo mínimo
        if len(questions) < 3:
            raise HTTPException(
                status_code=400,
                detail="Deve haver pelo menos 3 perguntas"
            )
        
        # Atualizar timestamps
        qa_data["updated_at"] = time.time()
        
        # Salvar no banco
        await hierarchical_db.update_unit_content(unit_id, "qa", qa_data)
        
        # Log da atualização
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "qa_manual_edit",
                "questions_count": len(questions),
                "answers_count": len(answers),
                "unit_id": unit_id
            }
        )
        
        return SuccessResponse(
            data={
                "updated": True,
                "qa": qa_data,
                "update_stats": {
                    "total_questions": len(questions),
                    "total_answers": len(answers),
                    "pedagogical_notes": len(qa_data.get("pedagogical_notes", [])),
                    "update_timestamp": qa_data["updated_at"]
                }
            },
            message=f"Q&A atualizado com sucesso",
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
        logger.error(f"Erro ao atualizar Q&A da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/units/{unit_id}/qa", response_model=SuccessResponse)
async def delete_unit_qa(unit_id: str, request: Request):
    """Deletar Q&A da unidade."""
    try:
        logger.warning(f"Deletando Q&A da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui Q&A
        if not unit.qa:
            return SuccessResponse(
                data={
                    "deleted": False,
                    "message": "Unidade não possui Q&A para deletar"
                },
                message="Nenhum Q&A encontrado para deletar"
            )
        
        # Deletar Q&A (setar como None)
        await hierarchical_db.update_unit_content(unit_id, "qa", None)
        
        # Status não muda pois Q&A é complementar
        
        # Log da deleção
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "qa_deleted",
                "unit_id": unit_id,
                "previous_questions_count": len(unit.qa.get("questions", []))
            }
        )
        
        return SuccessResponse(
            data={
                "deleted": True,
                "previous_questions_count": len(unit.qa.get("questions", [])),
                "status_unchanged": True,
                "note": "Q&A é complementar - status da unidade não alterado"
            },
            message="Q&A deletado com sucesso",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Regenerar Q&A",
                f"POST /api/v2/units/{unit_id}/qa"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar Q&A da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}/qa/analysis", response_model=SuccessResponse)
async def analyze_unit_qa(unit_id: str, request: Request):
    """Analisar qualidade e adequação pedagógica do Q&A da unidade."""
    try:
        logger.info(f"Analisando Q&A da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui Q&A
        if not unit.qa:
            raise HTTPException(
                status_code=400,
                detail="Unidade não possui Q&A para analisar"
            )
        
        # Analisar Q&A
        qa_data = unit.qa
        questions = qa_data.get("questions", [])
        answers = qa_data.get("answers", [])
        
        analysis = {
            "pedagogical_analysis": _analyze_pedagogical_depth(qa_data),
            "cognitive_analysis": _analyze_cognitive_levels(qa_data),
            "vocabulary_analysis": _analyze_vocabulary_integration(qa_data, unit.vocabulary),
            "pronunciation_analysis": _analyze_pronunciation_focus(qa_data),
            "difficulty_analysis": _analyze_difficulty_progression(qa_data),
            "content_alignment": _analyze_content_alignment(qa_data, unit),
            "quality_metrics": {
                "total_questions": len(questions),
                "total_answers": len(answers),
                "pedagogical_notes": len(qa_data.get("pedagogical_notes", [])),
                "vocabulary_integration": len(qa_data.get("vocabulary_integration", [])),
                "pronunciation_questions": len(qa_data.get("pronunciation_questions", []))
            }
        }
        
        # Gerar recomendações
        recommendations = _generate_qa_recommendations(analysis, unit)
        
        return SuccessResponse(
            data={
                "analysis": analysis,
                "recommendations": recommendations,
                "summary": {
                    "total_questions": len(questions),
                    "pedagogical_quality": _calculate_pedagogical_quality(analysis),
                    "cognitive_depth": len(set(qa_data.get("cognitive_levels", []))),
                    "pronunciation_awareness": len(qa_data.get("pronunciation_questions", [])) > 0,
                    "needs_improvement": len(recommendations) > 0
                }
            },
            message=f"Análise do Q&A da unidade '{unit.title}'",
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
        logger.error(f"Erro ao analisar Q&A da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/qa/pedagogical-guidelines", response_model=SuccessResponse)
async def get_qa_pedagogical_guidelines(request: Request):
    """Obter diretrizes pedagógicas para Q&A."""
    try:
        guidelines = {
            "bloom_taxonomy_levels": {
                "remember": {
                    "description": "Recordar informações e fatos básicos",
                    "question_types": ["What is...?", "Define...", "List...", "Name..."],
                    "examples": ["What does 'restaurant' mean?", "List three types of accommodation."]
                },
                "understand": {
                    "description": "Explicar conceitos e ideias",
                    "question_types": ["Explain...", "Describe...", "Compare...", "Why...?"],
                    "examples": ["Explain the difference between 'hotel' and 'motel'.", "Why do we use articles in English?"]
                },
                "apply": {
                    "description": "Usar conhecimento em situações novas",
                    "question_types": ["How would you...?", "What would happen if...?", "Use... in a sentence"],
                    "examples": ["How would you book a hotel room?", "Use 'reservation' in a sentence about restaurants."]
                },
                "analyze": {
                    "description": "Quebrar informações em partes",
                    "question_types": ["Analyze...", "What are the parts of...?", "Why do you think...?"],
                    "examples": ["Analyze the word formation in 'uncomfortable'.", "What are the parts of this hotel advertisement?"]
                },
                "evaluate": {
                    "description": "Fazer julgamentos sobre valor",
                    "question_types": ["Judge...", "What is your opinion...?", "Which is better...?"],
                    "examples": ["Which hotel would you choose and why?", "Evaluate this restaurant review."]
                },
                "create": {
                    "description": "Produzir trabalho novo e original",
                    "question_types": ["Create...", "Design...", "Compose...", "Plan..."],
                    "examples": ["Create a dialogue about checking into a hotel.", "Design a menu for a restaurant."]
                }
            },
            "pronunciation_focus_areas": {
                "phoneme_awareness": {
                    "description": "Consciência de sons individuais",
                    "question_types": ["How many syllables...?", "What sound does... make?", "Which words rhyme with...?"],
                    "importance": "Fundamental for pronunciation development"
                },
                "stress_patterns": {
                    "description": "Padrões de acentuação em palavras",
                    "question_types": ["Where is the stress in...?", "Which syllable is emphasized...?"],
                    "importance": "Critical for natural speech rhythm"
                },
                "connected_speech": {
                    "description": "Como as palavras se conectam na fala",
                    "question_types": ["How do you pronounce... in connected speech?", "What happens when... meets...?"],
                    "importance": "Essential for fluent communication"
                }
            },
            "difficulty_progression": {
                "simple": "Direct, factual questions requiring basic recall",
                "moderate": "Questions requiring understanding and simple application",
                "complex": "Questions requiring analysis, evaluation, or creative thinking",
                "advanced": "Open-ended questions requiring synthesis and critical thinking"
            },
            "content_integration_strategies": {
                "vocabulary_reinforcement": "Questions that review and apply new vocabulary in context",
                "grammar_application": "Questions that require using grammatical structures naturally",
                "pronunciation_practice": "Questions that focus on sound production and awareness",
                "cultural_awareness": "Questions that explore cultural aspects of language use",
                "metacognitive_development": "Questions that help students think about their learning process"
            }
        }
        
        return SuccessResponse(
            data={
                "pedagogical_guidelines": guidelines,
                "ivo_v2_approach": {
                    "question_distribution": "Balanced across cognitive levels with emphasis on application and analysis",
                    "pronunciation_integration": "Every Q&A section includes pronunciation awareness questions",
                    "vocabulary_spiral": "Questions reinforce vocabulary from current and previous units",
                    "cultural_context": "Questions include cultural aspects of language use",
                    "metacognitive_support": "Questions that help students reflect on their learning"
                },
                "best_practices": [
                    "Start with simpler recall questions and progress to more complex analysis",
                    "Include pronunciation questions for phonetic awareness",
                    "Connect questions to real-world situations students will encounter",
                    "Use vocabulary from the unit naturally in question contexts",
                    "Provide clear, complete answers that serve as teaching moments",
                    "Include pedagogical notes to guide teachers in using the Q&A effectively"
                ]
            },
            message="Diretrizes pedagógicas para Q&A do IVO V2"
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter diretrizes pedagógicas: {str(e)}")
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
        return "basic_comprehension"
    elif sequence_order <= 7:
        return "developing_analysis"
    else:
        return "advanced_application"


def _extract_learning_objectives(unit) -> List[str]:
    """Extrair objetivos de aprendizagem da unidade."""
    objectives = []
    
    if unit.main_aim:
        objectives.append(unit.main_aim)
    
    if unit.subsidiary_aims:
        objectives.extend(unit.subsidiary_aims)
    
    # Objetivos implícitos baseados no conteúdo
    if unit.vocabulary:
        objectives.append("Master new vocabulary and use it in context")
    
    if unit.tips:
        objectives.append("Apply vocabulary learning strategies")
    elif unit.grammar:
        objectives.append("Understand and use grammatical structures")
    
    return objectives


def _analyze_pedagogical_depth(qa_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar profundidade pedagógica."""
    pedagogical_notes = qa_data.get("pedagogical_notes", [])
    cognitive_levels = qa_data.get("cognitive_levels", [])
    questions = qa_data.get("questions", [])
    
    # Distribuição por níveis cognitivos
    level_distribution = {}
    for level in cognitive_levels:
        level_distribution[level] = level_distribution.get(level, 0) + 1
    
    # Análise da qualidade das notas pedagógicas
    notes_quality = {
        "total_notes": len(pedagogical_notes),
        "average_length": sum(len(note) for note in pedagogical_notes) / max(len(pedagogical_notes), 1),
        "has_teaching_guidance": any("teach" in note.lower() or "guide" in note.lower() for note in pedagogical_notes),
        "has_learning_tips": any("tip" in note.lower() or "help" in note.lower() for note in pedagogical_notes)
    }
    
    return {
        "cognitive_distribution": level_distribution,
        "cognitive_diversity": len(set(cognitive_levels)),
        "pedagogical_notes_quality": notes_quality,
        "depth_score": (len(set(cognitive_levels)) / 6) * 0.6 + (len(pedagogical_notes) / len(questions)) * 0.4 if questions else 0
    }


def _analyze_cognitive_levels(qa_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar níveis cognitivos das perguntas."""
    cognitive_levels = qa_data.get("cognitive_levels", [])
    questions = qa_data.get("questions", [])
    
    # Mapeamento dos níveis de Bloom
    bloom_levels = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    
    level_counts = {}
    for level in cognitive_levels:
        level_counts[level] = level_counts.get(level, 0) + 1
    
    # Calcular progressão
    progression_score = 0
    if cognitive_levels:
        for i, level in enumerate(cognitive_levels):
            if level in bloom_levels:
                progression_score += bloom_levels.index(level) + 1
        progression_score /= len(cognitive_levels)
    
    return {
        "level_distribution": level_counts,
        "covered_levels": list(set(cognitive_levels)),
        "progression_score": progression_score,
        "has_higher_order": any(level in ["analyze", "evaluate", "create"] for level in cognitive_levels),
        "balance_score": min(len(set(cognitive_levels)) / 6, 1.0)  # Ideal: todos os 6 níveis
    }


def _analyze_vocabulary_integration(qa_data: Dict[str, Any], unit_vocabulary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analisar integração com vocabulário da unidade."""
    vocabulary_integration = qa_data.get("vocabulary_integration", [])
    questions = qa_data.get("questions", [])
    
    if not unit_vocabulary or not unit_vocabulary.get("items"):
        return {
            "integration_percentage": 0,
            "words_integrated": 0,
            "total_vocabulary": 0,
            "integration_score": 0
        }
    
    unit_words = [item.get("word", "").lower() for item in unit_vocabulary.get("items", [])]
    integrated_words = [word.lower() for word in vocabulary_integration]
    
    words_used = len([word for word in integrated_words if word in unit_words])
    integration_percentage = (words_used / len(unit_words)) * 100 if unit_words else 0
    
    # Verificar uso contextual nas perguntas
    contextual_usage = 0
    all_questions_text = " ".join(questions).lower()
    for word in unit_words:
        if word.lower() in all_questions_text:
            contextual_usage += 1
    
    return {
        "integration_percentage": integration_percentage,
        "words_integrated": words_used,
        "total_vocabulary": len(unit_words),
        "contextual_usage": contextual_usage,
        "integration_score": (integration_percentage / 100) * 0.7 + (contextual_usage / len(unit_words)) * 0.3 if unit_words else 0,
        "unused_words": [word for word in unit_words if word not in integrated_words][:5]
    }


def _analyze_pronunciation_focus(qa_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar foco em pronúncia."""
    pronunciation_questions = qa_data.get("pronunciation_questions", [])
    phonetic_awareness = qa_data.get("phonetic_awareness", [])
    total_questions = len(qa_data.get("questions", []))
    
    pronunciation_percentage = (len(pronunciation_questions) / max(total_questions, 1)) * 100
    
    # Categorizar tipos de perguntas de pronúncia
    question_types = {
        "phoneme_focus": 0,
        "stress_patterns": 0,
        "connected_speech": 0,
        "general_pronunciation": 0
    }
    
    for question in pronunciation_questions:
        question_lower = question.lower()
        if any(word in question_lower for word in ["sound", "phoneme", "/", "pronounce"]):
            question_types["phoneme_focus"] += 1
        elif any(word in question_lower for word in ["stress", "accent", "emphasis"]):
            question_types["stress_patterns"] += 1
        elif any(word in question_lower for word in ["connected", "linking", "rhythm"]):
            question_types["connected_speech"] += 1
        else:
            question_types["general_pronunciation"] += 1
    
    return {
        "pronunciation_questions_count": len(pronunciation_questions),
        "pronunciation_percentage": pronunciation_percentage,
        "phonetic_awareness_count": len(phonetic_awareness),
        "question_types": question_types,
        "has_pronunciation_focus": len(pronunciation_questions) > 0,
        "pronunciation_diversity": len([k for k, v in question_types.items() if v > 0])
    }


def _analyze_difficulty_progression(qa_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar progressão de dificuldade."""
    difficulty_progression = qa_data.get("difficulty_progression", "unknown")
    cognitive_levels = qa_data.get("cognitive_levels", [])
    
    # Mapear níveis para scores de dificuldade
    difficulty_scores = {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 5,
        "create": 6
    }
    
    # Calcular progressão
    if cognitive_levels:
        scores = [difficulty_scores.get(level, 3) for level in cognitive_levels]
        avg_difficulty = sum(scores) / len(scores)
        
        # Verificar se há progressão crescente
        is_progressive = all(scores[i] <= scores[i+1] for i in range(len(scores)-1)) if len(scores) > 1 else True
    else:
        avg_difficulty = 3
        is_progressive = False
    
    return {
        "difficulty_progression": difficulty_progression,
        "average_difficulty": avg_difficulty,
        "is_progressive": is_progressive,
        "difficulty_range": max(scores) - min(scores) if cognitive_levels else 0,
        "progression_quality": "excellent" if is_progressive and avg_difficulty > 2.5 else "good" if is_progressive else "needs_improvement"
    }


def _analyze_content_alignment(qa_data: Dict[str, Any], unit) -> Dict[str, Any]:
    """Analisar alinhamento com conteúdo da unidade."""
    questions = qa_data.get("questions", [])
    vocabulary_integration = qa_data.get("vocabulary_integration", [])
    
    # Verificar alinhamento com contexto da unidade
    unit_context = (unit.context or "").lower()
    unit_title = (unit.title or "").lower()
    
    context_alignment = 0
    all_questions_text = " ".join(questions).lower()
    
    # Palavras-chave do contexto
    context_words = unit_context.split() + unit_title.split()
    context_words = [word for word in context_words if len(word) > 3]  # Palavras significativas
    
    for word in context_words:
        if word in all_questions_text:
            context_alignment += 1
    
    alignment_score = context_alignment / max(len(context_words), 1) if context_words else 0
    
    # Verificar alinhamento com estratégias
    strategy_alignment = False
    if unit.tips:
        strategy_name = unit.tips.get("strategy", "")
        if strategy_name in all_questions_text:
            strategy_alignment = True
    elif unit.grammar:
        grammar_point = unit.grammar.get("grammar_point", "")
        if any(word in all_questions_text for word in grammar_point.split()):
            strategy_alignment = True
    
    return {
        "context_alignment_score": alignment_score,
        "strategy_alignment": strategy_alignment,
        "vocabulary_integration_score": len(vocabulary_integration) / max(len(unit.vocabulary.get("items", [])), 1) if unit.vocabulary else 0,
        "content_coherence": (alignment_score + (1 if strategy_alignment else 0)) / 2,
        "is_well_aligned": alignment_score > 0.3 and len(vocabulary_integration) > 0
    }


def _generate_qa_recommendations(analysis: Dict[str, Any], unit) -> List[str]:
    """Gerar recomendações para melhorar Q&A."""
    recommendations = []
    
    # Análise pedagógica
    pedagogical = analysis["pedagogical_analysis"]
    if pedagogical["depth_score"] < 0.6:
        recommendations.append(
            f"Baixa profundidade pedagógica (score: {pedagogical['depth_score']:.1f}). "
            f"Adicione mais notas pedagógicas e diversifique níveis cognitivos."
        )
    
    # Análise cognitiva
    cognitive = analysis["cognitive_analysis"]
    if not cognitive["has_higher_order"]:
        recommendations.append(
            "Faltam perguntas de ordem superior (análise, avaliação, criação). "
            "Adicione perguntas que estimulem pensamento crítico."
        )
    
    if cognitive["balance_score"] < 0.5:
        recommendations.append(
            f"Distribuição desequilibrada de níveis cognitivos (score: {cognitive['balance_score']:.1f}). "
            f"Cubra mais níveis da Taxonomia de Bloom."
        )
    
    # Análise de vocabulário
    vocabulary = analysis["vocabulary_analysis"]
    if vocabulary["integration_score"] < 0.5:
        recommendations.append(
            f"Baixa integração com vocabulário da unidade (score: {vocabulary['integration_score']:.1f}). "
            f"Inclua mais palavras do vocabulário nas perguntas."
        )
    
    if vocabulary["unused_words"]:
        unused_sample = vocabulary["unused_words"][:3]
        recommendations.append(
            f"Palavras não utilizadas nas perguntas: {', '.join(unused_sample)}. "
            f"Considere criar perguntas específicas para essas palavras."
        )
    
    # Análise de pronúncia
    pronunciation = analysis["pronunciation_analysis"]
    if not pronunciation["has_pronunciation_focus"]:
        recommendations.append(
            "Adicione perguntas sobre pronúncia para desenvolver consciência fonética."
        )
    
    if pronunciation["pronunciation_percentage"] < 15:
        recommendations.append(
            f"Poucas perguntas de pronúncia ({pronunciation['pronunciation_percentage']:.1f}%). "
            f"Recomendado: pelo menos 15-20% das perguntas."
        )
    
    # Análise de dificuldade
    difficulty = analysis["difficulty_analysis"]
    if not difficulty["is_progressive"]:
        recommendations.append(
            "Reorganize as perguntas em progressão crescente de dificuldade."
        )
    
    if difficulty["average_difficulty"] < 2.5:
        recommendations.append(
            f"Nível de dificuldade baixo (média: {difficulty['average_difficulty']:.1f}). "
            f"Adicione perguntas mais desafiadoras."
        )
    
    # Análise de alinhamento
    alignment = analysis["content_alignment"]
    if not alignment["is_well_aligned"]:
        recommendations.append(
            f"Baixo alinhamento com conteúdo da unidade (score: {alignment['content_coherence']:.1f}). "
            f"Conecte mais as perguntas ao contexto e tema da unidade."
        )
    
    # Recomendações específicas por tipo de unidade
    if unit.unit_type.value == "lexical_unit":
        recommendations.append("Para unidades lexicais: inclua perguntas sobre colocações e uso contextual")
    else:
        recommendations.append("Para unidades gramaticais: inclua perguntas sobre estruturas e uso prático")
    
    # Recomendações para níveis específicos
    cefr_level = unit.cefr_level.value
    if cefr_level in ["A1", "A2"]:
        recommendations.append("Para níveis básicos: foque em perguntas de compreensão e aplicação simples")
    elif cefr_level in ["B1", "B2"]:
        recommendations.append("Para níveis intermediários: balance compreensão com análise e avaliação")
    else:
        recommendations.append("Para níveis avançados: enfatize análise crítica e criatividade")
    
    return recommendations


def _calculate_pedagogical_quality(analysis: Dict[str, Any]) -> float:
    """Calcular qualidade pedagógica geral."""
    try:
        # Componentes da qualidade
        pedagogical_score = analysis["pedagogical_analysis"]["depth_score"]
        cognitive_score = analysis["cognitive_analysis"]["balance_score"]
        vocabulary_score = analysis["vocabulary_analysis"]["integration_score"]
        pronunciation_score = 1.0 if analysis["pronunciation_analysis"]["has_pronunciation_focus"] else 0.5
        difficulty_score = 1.0 if analysis["difficulty_analysis"]["is_progressive"] else 0.7
        alignment_score = analysis["content_alignment"]["content_coherence"]
        
        # Média ponderada
        weights = {
            "pedagogical": 0.25,
            "cognitive": 0.25,
            "vocabulary": 0.2,
            "pronunciation": 0.1,
            "difficulty": 0.1,
            "alignment": 0.1
        }
        
        overall_quality = (
            pedagogical_score * weights["pedagogical"] +
            cognitive_score * weights["cognitive"] +
            vocabulary_score * weights["vocabulary"] +
            pronunciation_score * weights["pronunciation"] +
            difficulty_score * weights["difficulty"] +
            alignment_score * weights["alignment"]
        )
        
        return round(overall_quality, 2)
        
    except Exception as e:
        logger.warning(f"Erro ao calcular qualidade pedagógica: {str(e)}")
        return 0.7  # Score padrão