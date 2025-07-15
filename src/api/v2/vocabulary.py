# src/api/v2/vocabulary.py - ATUALIZAÇÃO PARA INTEGRAR O SERVIÇO
"""Endpoints para geração de vocabulário com contexto RAG hierárquico."""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Dict, Any
import logging
import time

from src.services.hierarchical_database import hierarchical_db
from src.services.vocabulary_generator import VocabularyGeneratorService
from src.core.unit_models import (
    SuccessResponse, ErrorResponse, VocabularySection, VocabularyItem
)
from src.core.enums import CEFRLevel, LanguageVariant, UnitType
from src.core.audit_logger import (
    audit_logger_instance, AuditEventType, audit_endpoint, extract_unit_info
)
from src.core.rate_limiter import rate_limit_dependency

router = APIRouter()
logger = logging.getLogger(__name__)


async def rate_limit_vocabulary_generation(request):
    """Rate limiting específico para geração de vocabulário."""
    await rate_limit_dependency(request, "generate_vocabulary")


@router.post("/units/{unit_id}/vocabulary", response_model=SuccessResponse)
@audit_endpoint(AuditEventType.UNIT_CONTENT_GENERATED, extract_unit_info)
async def generate_vocabulary_for_unit(
    unit_id: str,
    request: Request,
    _: None = Depends(rate_limit_vocabulary_generation)
):
    """
    Gerar vocabulário contextual para a unidade usando RAG e análise de imagens.
    
    Flow do IVO V2:
    1. Buscar unidade e validar hierarquia
    2. Analisar imagens via MCP (se existirem)
    3. Usar RAG para contexto de progressão
    4. Evitar repetições de vocabulário já ensinado
    5. Gerar vocabulário adequado ao nível CEFR
    6. Salvar e atualizar status da unidade
    """
    try:
        logger.info(f"Iniciando geração de vocabulário para unidade: {unit_id}")
        
        # 1. Buscar e validar unidade
        unit = await hierarchical_db.get_unit(unit_id)
        if not unit:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade {unit_id} não encontrada"
            )
        
        # 2. Verificar status adequado
        if unit.status.value not in ["creating", "vocab_pending"]:
            if unit.vocabulary:
                logger.info(f"Unidade {unit_id} já possui vocabulário - regenerando")
        
        # 3. Buscar contexto da hierarquia
        course = await hierarchical_db.get_course(unit.course_id)
        book = await hierarchical_db.get_book(unit.book_id)
        
        if not course or not book:
            raise HTTPException(
                status_code=400,
                detail="Hierarquia inválida: curso ou book não encontrado"
            )
        
        # 4. Buscar contexto RAG para evitar repetições
        logger.info("Coletando contexto RAG para prevenção de repetições...")
        
        taught_vocabulary = await hierarchical_db.get_taught_vocabulary(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        used_strategies = await hierarchical_db.get_used_strategies(
            unit.course_id, unit.book_id, unit.sequence_order
        )
        
        # 5. Analisar imagens se existirem (usando MCP)
        images_analysis = {}
        if unit.images and len(unit.images) > 0:
            try:
                logger.info("Analisando imagens via MCP para contexto de vocabulário...")
                
                # Usar MCP Image Analysis se disponível
                from src.mcp.mcp_image_client import analyze_images_for_unit_creation
                
                # Extrair dados base64 das imagens
                images_b64 = []
                for img in unit.images:
                    if img.get("base64"):
                        images_b64.append(img["base64"])
                
                if images_b64:
                    images_analysis = await analyze_images_for_unit_creation(
                        image_files_b64=images_b64,
                        context=unit.context or "",
                        cefr_level=unit.cefr_level.value,
                        unit_type=unit.unit_type.value
                    )
                    
                    if images_analysis.get("success"):
                        logger.info(f"Análise de imagens bem-sucedida: {len(images_analysis.get('consolidated_vocabulary', {}).get('vocabulary', []))} palavras sugeridas")
                    else:
                        logger.warning(f"Falha na análise de imagens: {images_analysis.get('error', 'Erro desconhecido')}")
                        
            except Exception as e:
                logger.warning(f"Erro na análise de imagens via MCP: {str(e)}")
                images_analysis = {"error": str(e)}
        
        # 6. Preparar dados para geração
        generation_params = {
            "unit_id": unit_id,
            "unit_data": {
                "title": unit.title,
                "context": unit.context,
                "cefr_level": unit.cefr_level.value,
                "language_variant": unit.language_variant.value,
                "unit_type": unit.unit_type.value
            },
            "hierarchy_context": {
                "course_name": course.name,
                "book_name": book.name,
                "sequence_order": unit.sequence_order,
                "target_level": book.target_level.value
            },
            "rag_context": {
                "taught_vocabulary": taught_vocabulary,
                "used_strategies": used_strategies,
                "progression_level": _determine_progression_level(unit.sequence_order),
                "vocabulary_density": len(taught_vocabulary) / max(unit.sequence_order, 1)
            },
            "images_analysis