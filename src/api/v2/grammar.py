# src/api/v2/grammar.py
"""
Endpoints para geração de estratégias GRAMMAR para unidades gramaticais.
Implementação das 2 estratégias GRAMMAR do IVO V2 Guide com seleção inteligente RAG.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import time

from src.services.hierarchical_database import hierarchical_db
from src.services.grammar_generator import GrammarGeneratorService
from src.core.unit_models import (
    SuccessResponse, ErrorResponse, GrammarContent
)
from src.core.enums import (
    CEFRLevel, LanguageVariant, UnitType, GrammarStrategy
)
from src.core.audit_logger import (
    audit_logger_instance, AuditEventType, audit_endpoint, extract_unit_info
)
from src.core.rate_limiter import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


async def rate_limit_grammar_generation(request):
    """Rate limiting específico para geração de GRAMMAR."""
    await rate_limit_dependency(request, "generate_content")


@router.post("/units/{unit_id}/grammar", response_model=SuccessResponse)
@audit_endpoint(AuditEventType.UNIT_CONTENT_GENERATED, extract_unit_info)
async def generate_grammar_for_unit(
    unit_id: str,
    request: Request,
    _: None = Depends(rate_limit_grammar_generation)
):
    """
    Gerar estratégias GRAMMAR para unidade gramatical com seleção inteligente.
    
    Flow do IVO V2:
    1. Buscar unidade e validar que é grammar_unit
    2. Verificar se possui vocabulário e sentences
    3. Usar RAG para seleção da estratégia GRAMMAR adequada
    4. Aplicar uma das 2 estratégias GRAMMAR baseada no conteúdo
    5. Gerar conteúdo específico da estratégia
    6. Salvar e atualizar status da unidade
    """
    try:
        logger.info(f"Iniciando geração de GRAMMAR para unidade: {unit_id}")
        
        # 1. Buscar e validar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # 2. Verificar se é unidade gramatical
        if unit.unit_type.value != "grammar_unit":
            raise HTTPException(
                status_code=400,
                detail=f"GRAMMAR são apenas para unidades gramaticais. Esta unidade é {unit.unit_type.value}. Use /tips para unidades lexicais."
            )
        
        # 3. Verificar status adequado
        if unit.status.value not in ["content_pending"]:
            if unit.status.value in ["creating", "vocab_pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Unidade deve ter vocabulário e sentences antes de gerar GRAMMAR."
                )
            elif unit.grammar:
                logger.info(f"Unidade {unit_id} já possui GRAMMAR - regenerando")
        
        # 4. Verificar pré-requisitos
        if not unit.vocabulary or not unit.vocabulary.get("items"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter vocabulário antes de gerar GRAMMAR."
            )
        
        if not unit.sentences or not unit.sentences.get("sentences"):
            raise HTTPException(
                status_code=400,
                detail="Unidade deve ter sentences antes de gerar GRAMMAR."
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
        logger.info("Coletando contexto RAG para seleção inteligente de estratégia GRAMMAR...")
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # 7. Preparar dados para seleção e geração
        grammar_params = {
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
                "strategy_density": len(used_strategies) / max(unit.sequence_order, 1),
                "brazilian_learner_context": True  # IVO V2 foca em brasileiros aprendendo inglês
            }
        }
        
        # 8. Gerar GRAMMAR usando service
        start_time = time.time()
        grammar_generator = GrammarGeneratorService()
        
        grammar_content = await grammar_generator.generate_grammar_for_unit(grammar_params)
        
        generation_time = time.time() - start_time
        
        # 9. Salvar GRAMMAR na unidade
        await hierarchical_db.update_unit_content(
            unit_id, 
            "grammar", 
            grammar_content.dict()
        )
        
        # 10. Atualizar lista de estratégias usadas
        strategy_name = grammar_content.strategy.value
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
            generation_type="grammar",
            unit_id=unit_id,
            book_id=unit.book_id,
            course_id=unit.course_id,
            content_stats={
                "strategy_selected": strategy_name,
                "grammar_point": grammar_content.grammar_point,
                "usage_rules_count": len(grammar_content.usage_rules),
                "examples_count": len(grammar_content.examples),
                "l1_interference_notes": len(grammar_content.l1_interference_notes),
                "common_mistakes_count": len(grammar_content.common_mistakes),
                "selection_rationale": grammar_content.selection_rationale,
                "vocabulary_integration": len(grammar_content.vocabulary_integration),
                "portuguese_interference_analysis": True
            },
            ai_usage={
                "model": "gpt-4o-mini",
                "generation_time": generation_time,
                "strategy_selection_algorithm": "rag_based_l1_interference_analysis"
            },
            processing_time=generation_time,
            success=True
        )
        
        return SuccessResponse(
            data={
                "grammar": grammar_content.dict(),
                "generation_stats": {
                    "strategy_selected": strategy_name,
                    "grammar_point": grammar_content.grammar_point,
                    "usage_rules": len(grammar_content.usage_rules),
                    "examples_count": len(grammar_content.examples),
                    "l1_interference_notes": len(grammar_content.l1_interference_notes),
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
                    "selection_rationale": grammar_content.selection_rationale,
                    "used_strategies_context": used_strategies,
                    "l1_interference_focus": grammar_content.l1_interference_notes,
                    "brazilian_learner_adaptations": len(grammar_content.common_mistakes)
                }
            },
            message=f"Estratégia GRAMMAR '{strategy_name}' gerada com sucesso para unidade '{unit.title}'",
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
                f"GET /api/v2/units/{unit_id}/grammar",
                "Analisar qualidade da estratégia",
                f"GET /api/v2/units/{unit_id}/grammar/analysis"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar GRAMMAR para unidade {unit_id}: {str(e)}")
        
        # Log de erro
        await audit_logger_instance.log_content_generation(
            request=request,
            generation_type="grammar",
            unit_id=unit_id,
            book_id=getattr(unit, 'book_id', ''),
            course_id=getattr(unit, 'course_id', ''),
            success=False,
            error_details=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno na geração de GRAMMAR: {str(e)}"
        )


@router.get("/units/{unit_id}/grammar", response_model=SuccessResponse)
async def get_unit_grammar(unit_id: str, request: Request):
    """Obter estratégias GRAMMAR da unidade."""
    try:
        logger.info(f"Buscando GRAMMAR da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade gramatical
        if unit.unit_type.value != "grammar_unit":
            raise HTTPException(
                status_code=400,
                detail=f"Esta unidade é {unit.unit_type.value}. GRAMMAR são apenas para unidades gramaticais."
            )
        
        # Verificar se possui GRAMMAR
        if not unit.grammar:
            return SuccessResponse(
                data={
                    "has_grammar": False,
                    "unit_status": unit.status.value,
                    "unit_type": unit.unit_type.value,
                    "message": "Unidade ainda não possui estratégias GRAMMAR geradas",
                    "prerequisites": {
                        "has_vocabulary": bool(unit.vocabulary),
                        "has_sentences": bool(unit.sentences),
                        "is_grammar_unit": unit.unit_type.value == "grammar_unit"
                    }
                },
                message="GRAMMAR não encontrada",
                hierarchy_info={
                    "course_id": unit.course_id,
                    "book_id": unit.book_id,
                    "unit_id": unit_id,
                    "sequence": unit.sequence_order
                },
                next_suggested_actions=[
                    "Gerar estratégias GRAMMAR",
                    f"POST /api/v2/units/{unit_id}/grammar"
                ]
            )
        
        # Buscar contexto adicional
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        # Análise das GRAMMAR
        grammar_data = unit.grammar
        
        return SuccessResponse(
            data={
                "grammar": grammar_data,
                "analysis": {
                    "strategy_used": grammar_data.get("strategy", "unknown"),
                    "grammar_point": grammar_data.get("grammar_point", ""),
                    "usage_rules_count": len(grammar_data.get("usage_rules", [])),
                    "examples_count": len(grammar_data.get("examples", [])),
                    "l1_interference_notes_count": len(grammar_data.get("l1_interference_notes", [])),
                    "common_mistakes_count": len(grammar_data.get("common_mistakes", [])),
                    "vocabulary_integration": grammar_data.get("vocabulary_integration", []),
                    "previous_grammar_connections": grammar_data.get("previous_grammar_connections", [])
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
                    "selection_rationale": grammar_data.get("selection_rationale", ""),
                    "systematic_explanation": grammar_data.get("systematic_explanation", ""),
                    "brazilian_learner_focus": bool(grammar_data.get("l1_interference_notes"))
                },
                "has_grammar": True
            },
            message=f"Estratégias GRAMMAR da unidade '{unit.title}'",
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
        logger.error(f"Erro ao buscar GRAMMAR da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.put("/units/{unit_id}/grammar", response_model=SuccessResponse)
async def update_unit_grammar(
    unit_id: str,
    grammar_data: Dict[str, Any],
    request: Request,
    _: None = Depends(rate_limit_grammar_generation)
):
    """Atualizar estratégias GRAMMAR da unidade (edição manual)."""
    try:
        logger.info(f"Atualizando GRAMMAR da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade gramatical
        if unit.unit_type.value != "grammar_unit":
            raise HTTPException(
                status_code=400,
                detail="GRAMMAR são apenas para unidades gramaticais"
            )
        
        # Validar estrutura básica dos dados
        if not isinstance(grammar_data, dict):
            raise HTTPException(
                status_code=400,
                detail="Dados de GRAMMAR devem ser um objeto JSON"
            )
        
        required_fields = ["strategy", "grammar_point", "systematic_explanation", "usage_rules", "examples"]
        for field in required_fields:
            if field not in grammar_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo obrigatório ausente: {field}"
                )
        
        # Validar estratégia
        valid_strategies = [strategy.value for strategy in GrammarStrategy]
        if grammar_data["strategy"] not in valid_strategies:
            raise HTTPException(
                status_code=400,
                detail=f"Estratégia inválida. Deve ser uma de: {valid_strategies}"
            )
        
        # Atualizar timestamps
        grammar_data["updated_at"] = time.time()
        
        # Salvar no banco
        await hierarchical_db.update_unit_content(unit_id, "grammar", grammar_data)
        
        # Atualizar estratégias usadas
        strategy_name = grammar_data["strategy"]
        current_strategies = unit.strategies_used or []
        if strategy_name not in current_strategies:
            updated_strategies = current_strategies + [strategy_name]
            await hierarchical_db.update_unit_content(unit_id, "strategies_used", updated_strategies)
        
        # Log da atualização
        await audit_logger_instance.log_event(
            event_type=AuditEventType.UNIT_UPDATED,
            request=request,
            additional_data={
                "update_type": "grammar_manual_edit",
                "strategy": strategy_name,
                "grammar_point": grammar_data["grammar_point"],
                "unit_id": unit_id
            }
        )
        
        return SuccessResponse(
            data={
                "updated": True,
                "grammar": grammar_data,
                "update_stats": {
                    "strategy": strategy_name,
                    "grammar_point": grammar_data["grammar_point"],
                    "examples_count": len(grammar_data.get("examples", [])),
                    "update_timestamp": grammar_data["updated_at"]
                }
            },
            message=f"Estratégias GRAMMAR atualizadas com sucesso",
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
        logger.error(f"Erro ao atualizar GRAMMAR da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.delete("/units/{unit_id}/grammar", response_model=SuccessResponse)
async def delete_unit_grammar(unit_id: str, request: Request):
    """Deletar estratégias GRAMMAR da unidade."""
    try:
        logger.warning(f"Deletando GRAMMAR da unidade: {unit_id}")
        
        # Verificar se unidade existe
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se possui GRAMMAR
        if not unit.grammar:
            return SuccessResponse(
                data={
                    "deleted": False,
                    "message": "Unidade não possui GRAMMAR para deletar"
                },
                message="Nenhuma estratégia GRAMMAR encontrada para deletar"
            )
        
        # Obter estratégia para remover da lista
        strategy_to_remove = unit.grammar.get("strategy")
        
        # Deletar GRAMMAR (setar como None)
        await hierarchical_db.update_unit_content(unit_id, "grammar", None)
        
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
                "update_type": "grammar_deleted",
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
            message="Estratégias GRAMMAR deletadas com sucesso",
            hierarchy_info={
                "course_id": unit.course_id,
                "book_id": unit.book_id,
                "unit_id": unit_id,
                "sequence": unit.sequence_order
            },
            next_suggested_actions=[
                "Regenerar estratégias GRAMMAR",
                f"POST /api/v2/units/{unit_id}/grammar"
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar GRAMMAR da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/units/{unit_id}/grammar/analysis", response_model=SuccessResponse)
async def analyze_unit_grammar(unit_id: str, request: Request):
    """Analisar qualidade e adequação das estratégias GRAMMAR da unidade."""
    try:
        logger.info(f"Analisando GRAMMAR da unidade: {unit_id}")
        
        # Buscar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # Verificar se é unidade gramatical
        if unit.unit_type.value != "grammar_unit":
            raise HTTPException(
                status_code=400,
                detail="Análise de GRAMMAR é apenas para unidades gramaticais"
            )
        
        # Verificar se possui GRAMMAR
        if not unit.grammar:
            raise HTTPException(
                status_code=400,
                detail="Unidade não possui GRAMMAR para analisar"
            )
        
        # Buscar contexto RAG para comparação
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # Analisar GRAMMAR
        grammar_data = unit.grammar
        
        analysis = {
            "strategy_analysis": _analyze_grammar_strategy_selection(grammar_data, used_strategies),
            "content_quality": _analyze_grammar_content_quality(grammar_data),
            "vocabulary_integration": _analyze_grammar_vocabulary_integration(grammar_data, unit.vocabulary),
            "pedagogical_effectiveness": _analyze_grammar_pedagogical_effectiveness(grammar_data, unit.cefr_level.value),
            "l1_interference_analysis": _analyze_l1_interference_quality(grammar_data),
            "contextual_relevance": _analyze_grammar_contextual_relevance(grammar_data, unit),
            "brazilian_learner_adaptation": _analyze_brazilian_learner_adaptation(grammar_data)
        }
        
        # Gerar recomendações
        recommendations = _generate_grammar_recommendations(analysis, unit)
        
        return SuccessResponse(
            data={
                "analysis": analysis,
                "recommendations": recommendations,
                "summary": {
                    "strategy_used": grammar_data.get("strategy"),
                    "grammar_point": grammar_data.get("grammar_point"),
                    "overall_quality": _calculate_grammar_quality(analysis),
                    "l1_interference_score": analysis["l1_interference_analysis"].get("effectiveness_score", 0),
                    "pedagogical_score": analysis["pedagogical_effectiveness"].get("effectiveness_score", 0),
                    "needs_improvement": len(recommendations) > 0
                }
            },
            message=f"Análise das estratégias GRAMMAR da unidade '{unit.title}'",
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
        logger.error(f"Erro ao analisar GRAMMAR da unidade {unit_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


@router.get("/grammar/strategies", response_model=SuccessResponse)
async def get_grammar_strategies_info(request: Request):
    """Obter informações sobre as 2 estratégias GRAMMAR disponíveis."""
    try:
        strategies_info = {
            "explicacao_sistematica": {
                "name": "GRAMMAR 1: Explicação Sistemática",
                "description": "Apresentação clara e organizada da estrutura gramatical",
                "when_to_use": "Para introduzir novos pontos gramaticais de forma estruturada",
                "components": [
                    "Apresentação clara da estrutura",
                    "Exemplos contextualizados progressivos",
                    "Regras de uso específicas",
                    "Progressão lógica de complexidade"
                ],
                "benefit": "Compreensão sistemática e organizada",
                "cefr_levels": ["A1", "A2", "B1", "B2", "C1", "C2"],
                "focus": "Explicação dedutiva e estruturada"
            },
            "prevencao_erros_l1": {
                "name": "GRAMMAR 2: Prevenção de Erros L1→L2",
                "description": "Sistema inteligente de prevenção de interferência português→inglês",
                "when_to_use": "Para antecipar e prevenir erros típicos de brasileiros",
                "components": [
                    "Antecipação de erros comuns",
                    "Exercícios contrastivos",
                    "Substituição sistemática",
                    "Análise de interferência L1"
                ],
                "benefit": "Prevenção proativa de erros recorrentes",
                "cefr_levels": ["A1", "A2", "B1", "B2"],
                "focus": "Análise contrastiva português-inglês",
                "brazilian_specific": True,
                "common_interferences": [
                    "Artigo obrigatório: 'The pasta is good' → 'Pasta is good'",
                    "Estrutura de idade: 'I have 25 years' → 'I am 25 years old'",
                    "Plurais: 'Milks, breads' → 'Milk, bread'",
                    "Ordem de perguntas: 'What you doing?' → 'What are you doing?'"
                ]
            }
        }
        
        return SuccessResponse(
            data={
                "strategies": strategies_info,
                "selection_logic": {
                    "total_available": 2,
                    "selection_criteria": [
                        "Grammar complexity and student level",
                        "Presence of known L1 interference patterns",
                        "Balance with previous strategies used",
                        "Contextual appropriateness",
                        "Brazilian learner specific needs"
                    ]
                },
                "ivo_v2_approach": {
                    "intelligent_selection": "RAG-based strategy selection with L1 interference analysis",
                    "brazilian_focus": "Specialized for Portuguese-speaking learners",
                    "contrastive_analysis": "Built-in Portuguese-English contrastive patterns",
                    "error_prediction": "Proactive error prevention system"
                },
                "l1_interference_examples": {
                    "false_friends": ["exquisite ≠ esquisito", "library ≠ livraria"],
                    "structural_differences": ["word order", "auxiliary verbs", "article usage"],
                    "pronunciation_challenges": ["th sounds", "vowel system", "final consonants"]
                }
            },
            message="Informações sobre as 2 estratégias GRAMMAR do IVO V2"
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter informações das estratégias GRAMMAR: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno: {str(e)}"
        )


# =============================================================================
# HELPER FUNCTIONS PARA GRAMMAR.PY
# =============================================================================

def _determine_progression_level(sequence_order: int) -> str:
    """Determinar nível de progressão baseado na sequência."""
    if sequence_order <= 3:
        return "basic_grammar"
    elif sequence_order <= 7:
        return "intermediate_grammar"
    else:
        return "advanced_grammar"


def _analyze_grammar_strategy_selection(grammar_data: Dict[str, Any], used_strategies: List[str]) -> Dict[str, Any]:
    """Analisar adequação da seleção da estratégia GRAMMAR."""
    current_strategy = grammar_data.get("strategy")
    strategy_count = used_strategies.count(current_strategy) if current_strategy else 0
    
    return {
        "selected_strategy": current_strategy,
        "usage_frequency": strategy_count,
        "is_overused": strategy_count > 3,  # Máximo 3 vezes por book para grammar
        "selection_rationale": grammar_data.get("selection_rationale", ""),
        "previous_connections": grammar_data.get("previous_grammar_connections", []),
        "strategy_diversity_score": len(set(used_strategies)) / 2 if used_strategies else 0  # 2 estratégias disponíveis
    }


def _analyze_grammar_content_quality(grammar_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar qualidade do conteúdo das estratégias GRAMMAR."""
    usage_rules = grammar_data.get("usage_rules", [])
    examples = grammar_data.get("examples", [])
    l1_interference = grammar_data.get("l1_interference_notes", [])
    common_mistakes = grammar_data.get("common_mistakes", [])
    
    return {
        "usage_rules_count": len(usage_rules),
        "examples_count": len(examples),
        "l1_interference_notes_count": len(l1_interference),
        "common_mistakes_count": len(common_mistakes),
        "systematic_explanation_length": len(grammar_data.get("systematic_explanation", "")),
        "content_completeness_score": min((len(usage_rules) + len(examples) + len(l1_interference)) / 10, 1.0),
        "brazilian_adaptation": len(common_mistakes) > 0
    }


def _analyze_grammar_vocabulary_integration(grammar_data: Dict[str, Any], unit_vocabulary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Analisar integração das estratégias GRAMMAR com vocabulário da unidade."""
    vocabulary_integration = grammar_data.get("vocabulary_integration", [])
    
    if not unit_vocabulary or not unit_vocabulary.get("items"):
        return {
            "integration_percentage": 0,
            "words_integrated": 0,
            "total_vocabulary": 0,
            "integration_score": 0
        }
    
    unit_words = [item.get("word", "").lower() for item in unit_vocabulary.get("items", [])]
    integrated_words = [word.lower() for word in vocabulary_integration]
    
    words_integrated = len([word for word in integrated_words if word in unit_words])
    integration_percentage = (words_integrated / len(unit_words)) * 100 if unit_words else 0
    
    return {
        "integration_percentage": integration_percentage,
        "words_integrated": words_integrated,
        "total_vocabulary": len(unit_words),
        "integration_score": integration_percentage / 100,
        "unintegrated_words": [word for word in unit_words if word not in integrated_words][:5]
    }


def _analyze_grammar_pedagogical_effectiveness(grammar_data: Dict[str, Any], cefr_level: str) -> Dict[str, Any]:
    """Analisar eficácia pedagógica da estratégia GRAMMAR."""
    strategy = grammar_data.get("strategy", "")
    
    # Mapear eficácia por estratégia e nível CEFR
    strategy_effectiveness = {
        "explicacao_sistematica": {
            "A1": 0.9, "A2": 0.9, "B1": 0.8, "B2": 0.7, "C1": 0.6, "C2": 0.5
        },
        "prevencao_erros_l1": {
            "A1": 0.95, "A2": 0.9, "B1": 0.85, "B2": 0.7, "C1": 0.5, "C2": 0.3
        }
    }
    
    effectiveness_score = strategy_effectiveness.get(strategy, {}).get(cefr_level, 0.7)
    
    return {
        "strategy": strategy,
        "cefr_level": cefr_level,
        "effectiveness_score": effectiveness_score,
        "is_appropriate": effectiveness_score >= 0.7,
        "recommendations": _get_grammar_effectiveness_recommendations(strategy, cefr_level, effectiveness_score)
    }


def _analyze_l1_interference_quality(grammar_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar qualidade da análise de interferência L1→L2."""
    l1_notes = grammar_data.get("l1_interference_notes", [])
    common_mistakes = grammar_data.get("common_mistakes", [])
    
    # Verificar se aborda interferências específicas do português
    portuguese_patterns = [
        "artigo", "article", "ser", "estar", "ter", "have", "be",
        "ordem", "order", "auxiliar", "auxiliary", "plural", "contável"
    ]
    
    pattern_coverage = 0
    for note in l1_notes:
        note_lower = note.lower()
        if any(pattern in note_lower for pattern in portuguese_patterns):
            pattern_coverage += 1
    
    mistake_quality = 0
    for mistake in common_mistakes:
        if isinstance(mistake, dict):
            if "causa" in str(mistake).lower() and "correção" in str(mistake).lower():
                mistake_quality += 1
    
    return {
        "l1_notes_count": len(l1_notes),
        "common_mistakes_count": len(common_mistakes),
        "portuguese_pattern_coverage": pattern_coverage,
        "mistake_analysis_quality": mistake_quality,
        "effectiveness_score": min((pattern_coverage + mistake_quality) / max(len(l1_notes) + len(common_mistakes), 1), 1.0),
        "has_contrastive_analysis": pattern_coverage > 0,
        "brazilian_specific": True
    }


def _analyze_grammar_contextual_relevance(grammar_data: Dict[str, Any], unit) -> Dict[str, Any]:
    """Analisar relevância contextual da estratégia GRAMMAR."""
    grammar_point = grammar_data.get("grammar_point", "").lower()
    systematic_explanation = grammar_data.get("systematic_explanation", "").lower()
    
    unit_context = (unit.context or "").lower()
    unit_title = (unit.title or "").lower()
    
    # Verificar alinhamento contextual
    context_keywords = unit_context.split() + unit_title.split()
    grammar_content = grammar_point + " " + systematic_explanation
    
    keyword_matches = sum(1 for keyword in context_keywords if keyword in grammar_content)
    context_alignment = keyword_matches / max(len(context_keywords), 1)
    
    return {
        "context_alignment_score": context_alignment,
        "grammar_fits_context": context_alignment > 0.2,
        "unit_context": unit.context,
        "grammar_point": grammar_data.get("grammar_point"),
        "keyword_matches": keyword_matches,
        "explanation_length": len(systematic_explanation)
    }


def _analyze_brazilian_learner_adaptation(grammar_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analisar adaptações específicas para aprendizes brasileiros."""
    l1_notes = grammar_data.get("l1_interference_notes", [])
    common_mistakes = grammar_data.get("common_mistakes", [])
    
    # Padrões específicos de interferência português-inglês
    brazilian_patterns = {
        "false_friends": ["library", "parents", "realize", "attend"],
        "structural": ["auxiliary", "article", "word order", "question formation"],
        "pronunciation": ["th", "final consonants", "vowel reduction"],
        "cultural": ["formal", "informal", "politeness", "directness"]
    }
    
    pattern_matches = {}
    for category, patterns in brazilian_patterns.items():
        matches = 0
        all_content = " ".join(l1_notes + [str(mistake) for mistake in common_mistakes])
        for pattern in patterns:
            if pattern.lower() in all_content.lower():
                matches += 1
        pattern_matches[category] = matches
    
    total_adaptations = sum(pattern_matches.values())
    adaptation_score = min(total_adaptations / 10, 1.0)  # Score de 0 a 1
    
    return {
        "adaptation_score": adaptation_score,
        "pattern_matches": pattern_matches,
        "total_adaptations": total_adaptations,
        "is_well_adapted": adaptation_score > 0.5,
        "brazilian_specific_content": len(l1_notes) > 0,
        "contrastive_examples": len(common_mistakes) > 0
    }


def _generate_grammar_recommendations(analysis: Dict[str, Any], unit) -> List[str]:
    """Gerar recomendações para melhorar estratégias GRAMMAR."""
    recommendations = []
    
    # Análise de seleção de estratégia
    strategy_analysis = analysis["strategy_analysis"]
    if strategy_analysis["is_overused"]:
        recommendations.append(
            f"Estratégia '{strategy_analysis['selected_strategy']}' está sendo usada excessivamente "
            f"({strategy_analysis['usage_frequency']} vezes). Considere alternar para balanceamento."
        )
    
    # Análise de qualidade de conteúdo
    content_quality = analysis["content_quality"]
    if content_quality["usage_rules_count"] < 3:
        recommendations.append(
            f"Poucas regras de uso ({content_quality['usage_rules_count']}). Recomendado: pelo menos 3-5 regras."
        )
    
    if content_quality["examples_count"] < 4:
        recommendations.append(
            "Adicione mais exemplos contextualizados para ilustrar a gramática."
        )
    
    # Análise de integração com vocabulário
    vocab_integration = analysis["vocabulary_integration"]
    if vocab_integration["integration_percentage"] < 30:
        recommendations.append(
            f"Baixa integração com vocabulário da unidade ({vocab_integration['integration_percentage']:.1f}%). "
            f"Inclua mais palavras do vocabulário nos exemplos gramaticais."
        )
    
    # Análise de eficácia pedagógica
    pedagogical = analysis["pedagogical_effectiveness"]
    if not pedagogical["is_appropriate"]:
        recommendations.append(
            f"Estratégia pode não ser a mais adequada para nível {pedagogical['cefr_level']} "
            f"(eficácia: {pedagogical['effectiveness_score']:.1f}). "
            f"Considere: {', '.join(pedagogical['recommendations'])}"
        )
    
    # Análise de interferência L1
    l1_analysis = analysis["l1_interference_analysis"]
    if not l1_analysis["has_contrastive_analysis"]:
        recommendations.append(
            "Adicione análise contrastiva português-inglês para aprendizes brasileiros."
        )
    
    if l1_analysis["effectiveness_score"] < 0.7:
        recommendations.append(
            f"Melhore a análise de interferência L1 (score: {l1_analysis['effectiveness_score']:.1f}). "
            f"Inclua mais exemplos de erros comuns e suas correções."
        )
    
    # Análise contextual
    contextual = analysis["contextual_relevance"]
    if not contextual["grammar_fits_context"]:
        recommendations.append(
            f"Estratégia tem baixo alinhamento com contexto da unidade "
            f"(score: {contextual['context_alignment_score']:.1f}). "
            f"Adapte exemplos gramaticais ao tema da unidade."
        )
    
    # Análise de adaptação brasileira
    brazilian_analysis = analysis["brazilian_learner_adaptation"]
    if not brazilian_analysis["is_well_adapted"]:
        recommendations.append(
            f"Baixa adaptação para aprendizes brasileiros (score: {brazilian_analysis['adaptation_score']:.1f}). "
            f"Inclua mais padrões de interferência português-inglês."
        )
    
    # Recomendações específicas por estratégia
    strategy = strategy_analysis["selected_strategy"]
    if strategy == "explicacao_sistematica":
        recommendations.append("Para explicação sistemática: organize exemplos em progressão de complexidade")
    elif strategy == "prevencao_erros_l1":
        recommendations.append("Para prevenção L1: inclua exercícios contrastivos específicos")
    
    # Recomendações específicas para brasileiros
    if unit.language_variant.value in ["american_english", "british_english"]:
        recommendations.append("Destaque diferenças culturais de uso da gramática entre português e inglês")
    
    return recommendations


def _calculate_grammar_quality(analysis: Dict[str, Any]) -> float:
    """Calcular qualidade geral das estratégias GRAMMAR."""
    try:
        # Componentes da qualidade
        strategy_score = 1.0 if not analysis["strategy_analysis"]["is_overused"] else 0.6
        content_score = analysis["content_quality"]["content_completeness_score"]
        vocab_score = analysis["vocabulary_integration"]["integration_score"]
        pedagogical_score = analysis["pedagogical_effectiveness"]["effectiveness_score"]
        l1_score = analysis["l1_interference_analysis"]["effectiveness_score"]
        context_score = min(analysis["contextual_relevance"]["context_alignment_score"], 1.0)
        brazilian_score = analysis["brazilian_learner_adaptation"]["adaptation_score"]
        
        # Média ponderada com foco em L1 e pedagogia
        weights = {
            "strategy": 0.1,
            "content": 0.15,
            "vocabulary": 0.15,
            "pedagogical": 0.25,
            "l1_interference": 0.25,  # Muito importante para IVO V2
            "context": 0.05,
            "brazilian_adaptation": 0.05
        }
        
        overall_quality = (
            strategy_score * weights["strategy"] +
            content_score * weights["content"] +
            vocab_score * weights["vocabulary"] +
            pedagogical_score * weights["pedagogical"] +
            l1_score * weights["l1_interference"] +
            context_score * weights["context"] +
            brazilian_score * weights["brazilian_adaptation"]
        )
        
        return round(overall_quality, 2)
        
    except Exception as e:
        logger.warning(f"Erro ao calcular qualidade das estratégias GRAMMAR: {str(e)}")
        return 0.7  # Score padrão


def _get_grammar_effectiveness_recommendations(strategy: str, cefr_level: str, effectiveness_score: float) -> List[str]:
    """Obter recomendações de eficácia por estratégia GRAMMAR e nível."""
    recommendations = []
    
    if effectiveness_score < 0.7:
        if strategy == "explicacao_sistematica" and cefr_level in ["C1", "C2"]:
            recommendations.append("Para níveis avançados, considere abordagem mais indutiva")
        elif strategy == "prevencao_erros_l1" and cefr_level in ["C1", "C2"]:
            recommendations.append("Para níveis avançados, foque em nuances sutis ao invés de erros básicos")
        elif strategy == "explicacao_sistematica" and cefr_level in ["A1", "A2"]:
            recommendations.append("Para iniciantes, simplifique explicações e use mais exemplos visuais")
        elif strategy == "prevencao_erros_l1" and cefr_level in ["A1", "A2"]:
            recommendations.append("Para iniciantes, foque nos erros mais básicos e frequentes")
    
    # Recomendações gerais de melhoria
    if effectiveness_score < 0.5:
        recommendations.append("Considere mudar de estratégia para este nível")
    elif effectiveness_score < 0.7:
        recommendations.append("Adapte exemplos e exercícios ao nível específico do aluno")
    
    # Recomendações específicas para brasileiros
    if strategy == "prevencao_erros_l1":
        recommendations.append("Inclua padrões específicos de interferência do português brasileiro")
        recommendations.append("Use exemplos contrastivos diretos (português vs inglês)")
    
    return recommendations


def _get_grammar_strategy_info(strategy: str) -> Dict[str, Any]:
    """Obter informações detalhadas sobre uma estratégia GRAMMAR específica."""
    strategies_info = {
        "explicacao_sistematica": {
            "name": "GRAMMAR 1: Explicação Sistemática",
            "description": "Apresentação organizada e dedutiva da gramática",
            "components": ["clear_presentation", "contextualized_examples", "usage_rules", "logical_progression"],
            "best_for_levels": ["A1", "A2", "B1", "B2"],
            "approach": "Dedutivo - regra → exemplos → prática",
            "cognitive_load": "Médio a alto",
            "memory_technique": "Estruturação e categorização"
        },
        "prevencao_erros_l1": {
            "name": "GRAMMAR 2: Prevenção de Erros L1→L2",
            "description": "Sistema proativo de prevenção de interferência",
            "components": ["error_prediction", "contrastive_analysis", "corrective_exercises", "l1_awareness"],
            "best_for_levels": ["A1", "A2", "B1", "B2"],
            "approach": "Contrastivo - L1 vs L2 → correção → prática",
            "cognitive_load": "Baixo a médio",
            "memory_technique": "Associação contrastiva e substituição",
            "brazilian_specific": True,
            "interference_patterns": [
                "article_usage", "auxiliary_verbs", "word_order", 
                "false_friends", "pronunciation_transfer"
            ]
        }
    }
    
    return strategies_info.get(strategy, {})


def _validate_grammar_strategy_selection(
    vocabulary_items: List[Dict[str, Any]], 
    sentences: List[Dict[str, Any]],
    cefr_level: str,
    used_strategies: List[str],
    unit_context: str
) -> str:
    """Validar e sugerir estratégia GRAMMAR mais adequada."""
    
    # Analisar se há padrões que indicam necessidade de prevenção L1
    l1_indicators = []
    
    # Verificar vocabulário que pode causar interferência
    problematic_words = [
        "library", "parents", "realize", "attend", "college", "fabric",
        "have", "be", "do", "can", "will", "must"
    ]
    
    for item in vocabulary_items:
        word = item.get("word", "").lower()
        if word in problematic_words:
            l1_indicators.append("vocabulary_interference")
            break
    
    # Verificar estruturas gramaticais propensas à interferência
    interferencia_structures = [
        "auxiliary", "article", "question", "negative", "present perfect",
        "past simple", "modal", "preposition", "gerund", "infinitive"
    ]
    
    context_lower = unit_context.lower()
    for structure in interferencia_structures:
        if structure in context_lower:
            l1_indicators.append("structural_interference")
            break
    
    # Contar frequência de estratégias já usadas
    strategy_counts = {}
    for strategy in used_strategies:
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    # Lógica de seleção baseada no IVO V2 Guide
    if cefr_level in ["A1", "A2"]:
        # Para iniciantes, priorizar prevenção L1 se há indicadores
        if (l1_indicators and 
            strategy_counts.get("prevencao_erros_l1", 0) < 3):
            return "prevencao_erros_l1"
        elif strategy_counts.get("explicacao_sistematica", 0) < 2:
            return "explicacao_sistematica"
        else:
            return "prevencao_erros_l1"
    
    elif cefr_level in ["B1", "B2"]:
        # Para intermediários, balancear estratégias
        if (strategy_counts.get("explicacao_sistematica", 0) < 
            strategy_counts.get("prevencao_erros_l1", 0)):
            return "explicacao_sistematica"
        elif l1_indicators:
            return "prevencao_erros_l1"
        else:
            return "explicacao_sistematica"
    
    else:  # C1, C2
        # Para avançados, priorizar explicação sistemática
        return "explicacao_sistematica"