# src/services/hierarchical_database.py
"""Serviço para operações de banco com hierarquia Course → Book → Unit."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging

from config.database import get_supabase_client
from src.core.hierarchical_models import (
    Course, CourseCreateRequest, Book, BookCreateRequest,
    UnitWithHierarchy, HierarchicalUnitRequest, RAGVocabularyContext,
    RAGStrategyContext, RAGAssessmentContext, ProgressionAnalysis,
    HierarchyValidationResult
)
from src.core.enums import UnitStatus, CEFRLevel


logger = logging.getLogger(__name__)


class HierarchicalDatabaseService:
    """Serviço para operações hierárquicas no banco de dados."""
    
    def __init__(self):
        self.supabase = get_supabase_client()
    
    # =============================================================================
    # COURSE OPERATIONS
    # =============================================================================
    
    async def create_course(self, course_data: CourseCreateRequest) -> Course:
        """Criar novo curso."""
        try:
            # Preparar dados para inserção
            insert_data = {
                "name": course_data.name,
                "description": course_data.description,
                "target_levels": [level.value for level in course_data.target_levels],
                "language_variant": course_data.language_variant.value,
                "methodology": course_data.methodology
            }
            
            # Inserir no banco
            result = self.supabase.table("ivo_courses").insert(insert_data).execute()
            
            if not result.data:
                raise Exception("Falha ao criar curso")
            
            # Retornar modelo Course
            course_record = result.data[0]
            return Course(**course_record)
            
        except Exception as e:
            logger.error(f"Erro ao criar curso: {str(e)}")
            raise
    
    async def get_course(self, course_id: str) -> Optional[Course]:
        """Buscar curso por ID."""
        try:
            result = self.supabase.table("ivo_courses").select("*").eq("id", course_id).execute()
            
            if not result.data:
                return None
                
            return Course(**result.data[0])
            
        except Exception as e:
            logger.error(f"Erro ao buscar curso {course_id}: {str(e)}")
            raise
    
    async def list_courses(self) -> List[Course]:
        """Listar todos os cursos."""
        try:
            result = self.supabase.table("ivo_courses").select("*").order("created_at", desc=True).execute()
            
            return [Course(**record) for record in result.data]
            
        except Exception as e:
            logger.error(f"Erro ao listar cursos: {str(e)}")
            raise
    
    # =============================================================================
    # BOOK OPERATIONS
    # =============================================================================
    
    async def create_book(self, course_id: str, book_data: BookCreateRequest) -> Book:
        """Criar novo book dentro de um curso."""
        try:
            # Verificar se o curso existe
            course = await self.get_course(course_id)
            if not course:
                raise ValueError(f"Curso {course_id} não encontrado")
            
            # Determinar próximo sequence_order
            next_sequence = await self._get_next_book_sequence(course_id)
            
            # Preparar dados para inserção
            insert_data = {
                "course_id": course_id,
                "name": book_data.name,
                "description": book_data.description,
                "target_level": book_data.target_level.value,
                "sequence_order": next_sequence
            }
            
            # Inserir no banco
            result = self.supabase.table("ivo_books").insert(insert_data).execute()
            
            if not result.data:
                raise Exception("Falha ao criar book")
            
            return Book(**result.data[0])
            
        except Exception as e:
            logger.error(f"Erro ao criar book: {str(e)}")
            raise
    
    async def get_book(self, book_id: str) -> Optional[Book]:
        """Buscar book por ID."""
        try:
            result = self.supabase.table("ivo_books").select("*").eq("id", book_id).execute()
            
            if not result.data:
                return None
                
            return Book(**result.data[0])
            
        except Exception as e:
            logger.error(f"Erro ao buscar book {book_id}: {str(e)}")
            raise
    
    async def list_books_by_course(self, course_id: str) -> List[Book]:
        """Listar books de um curso."""
        try:
            result = (
                self.supabase.table("ivo_books")
                .select("*")
                .eq("course_id", course_id)
                .order("sequence_order")
                .execute()
            )
            
            return [Book(**record) for record in result.data]
            
        except Exception as e:
            logger.error(f"Erro ao listar books do curso {course_id}: {str(e)}")
            raise
    
    # =============================================================================
    # UNIT OPERATIONS
    # =============================================================================
    
    async def create_unit(self, unit_data: HierarchicalUnitRequest) -> UnitWithHierarchy:
        """Criar unidade com validação hierárquica."""
        try:
            # Validar hierarquia
            validation = await self.validate_hierarchy(unit_data.course_id, unit_data.book_id)
            if not validation.is_valid:
                raise ValueError(f"Hierarquia inválida: {validation.errors}")
            
            # Determinar próximo sequence_order
            next_sequence = await self._get_next_unit_sequence(unit_data.book_id)
            
            # Preparar dados para inserção
            insert_data = {
                "course_id": unit_data.course_id,
                "book_id": unit_data.book_id,
                "sequence_order": next_sequence,
                "title": unit_data.title,
                "context": unit_data.context,
                "cefr_level": unit_data.cefr_level.value,
                "language_variant": unit_data.language_variant.value,
                "unit_type": unit_data.unit_type.value,
                "status": UnitStatus.CREATING.value
            }
            
            # Inserir no banco
            result = self.supabase.table("ivo_units").insert(insert_data).execute()
            
            if not result.data:
                raise Exception("Falha ao criar unidade")
            
            return UnitWithHierarchy(**result.data[0])
            
        except Exception as e:
            logger.error(f"Erro ao criar unidade: {str(e)}")
            raise
    
    async def get_unit(self, unit_id: str) -> Optional[UnitWithHierarchy]:
        """Buscar unidade por ID."""
        try:
            result = self.supabase.table("ivo_units").select("*").eq("id", unit_id).execute()
            
            if not result.data:
                return None
                
            return UnitWithHierarchy(**result.data[0])
            
        except Exception as e:
            logger.error(f"Erro ao buscar unidade {unit_id}: {str(e)}")
            raise
    
    async def list_units_by_book(self, book_id: str) -> List[UnitWithHierarchy]:
        """Listar unidades de um book."""
        try:
            result = (
                self.supabase.table("ivo_units")
                .select("*")
                .eq("book_id", book_id)
                .order("sequence_order")
                .execute()
            )
            
            return [UnitWithHierarchy(**record) for record in result.data]
            
        except Exception as e:
            logger.error(f"Erro ao listar unidades do book {book_id}: {str(e)}")
            raise
    
    async def update_unit_status(self, unit_id: str, status: UnitStatus) -> bool:
        """Atualizar status da unidade."""
        try:
            result = (
                self.supabase.table("ivo_units")
                .update({"status": status.value, "updated_at": "now()"})
                .eq("id", unit_id)
                .execute()
            )
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar status da unidade {unit_id}: {str(e)}")
            raise
    
    async def update_unit_content(self, unit_id: str, content_type: str, content: Dict[str, Any]) -> bool:
        """Atualizar conteúdo específico da unidade."""
        try:
            update_data = {
                content_type: content,
                "updated_at": "now()"
            }
            
            result = (
                self.supabase.table("ivo_units")
                .update(update_data)
                .eq("id", unit_id)
                .execute()
            )
            
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar conteúdo {content_type} da unidade {unit_id}: {str(e)}")
            raise
    
    # =============================================================================
    # RAG FUNCTIONS
    # =============================================================================
    
    async def get_taught_vocabulary(
        self, 
        course_id: str, 
        book_id: Optional[str] = None, 
        sequence_order: Optional[int] = None
    ) -> List[str]:
        """Buscar vocabulário já ensinado usando função SQL."""
        try:
            result = self.supabase.rpc(
                "get_taught_vocabulary",
                {
                    "target_course_id": course_id,
                    "target_book_id": book_id,
                    "target_sequence": sequence_order
                }
            ).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Erro ao buscar vocabulário ensinado: {str(e)}")
            return []
    
    async def get_used_strategies(
        self, 
        course_id: str, 
        book_id: str, 
        sequence_order: int
    ) -> List[str]:
        """Buscar estratégias já usadas usando função SQL."""
        try:
            result = self.supabase.rpc(
                "get_used_strategies",
                {
                    "target_course_id": course_id,
                    "target_book_id": book_id,
                    "target_sequence": sequence_order
                }
            ).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Erro ao buscar estratégias usadas: {str(e)}")
            return []
    
    async def get_used_assessments(
        self, 
        course_id: str, 
        book_id: str, 
        sequence_order: int
    ) -> Dict[str, Any]:
        """Buscar atividades já usadas usando função SQL."""
        try:
            result = self.supabase.rpc(
                "get_used_assessments",
                {
                    "target_course_id": course_id,
                    "target_book_id": book_id,
                    "target_sequence": sequence_order
                }
            ).execute()
            
            return result.data or {}
            
        except Exception as e:
            logger.error(f"Erro ao buscar atividades usadas: {str(e)}")
            return {}
    
    async def match_precedent_units(
        self,
        query_embedding: List[float],
        course_id: str,
        book_id: str,
        sequence_order: int,
        match_threshold: float = 0.7,
        match_count: int = 5
    ) -> List[Dict[str, Any]]:
        """Buscar unidades precedentes para RAG."""
        try:
            result = self.supabase.rpc(
                "match_precedent_units",
                {
                    "query_embedding": query_embedding,
                    "target_course_id": course_id,
                    "target_book_id": book_id,
                    "target_sequence": sequence_order,
                    "match_threshold": match_threshold,
                    "match_count": match_count
                }
            ).execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Erro ao buscar unidades precedentes: {str(e)}")
            return []
    
    # =============================================================================
    # VALIDATION & HELPER METHODS
    # =============================================================================
    
    async def validate_hierarchy(self, course_id: str, book_id: str) -> HierarchyValidationResult:
        """Validar se book pertence ao curso."""
        try:
            # Verificar se course existe
            course = await self.get_course(course_id)
            if not course:
                return HierarchyValidationResult(
                    is_valid=False,
                    errors=[f"Curso {course_id} não encontrado"]
                )
            
            # Verificar se book existe e pertence ao curso
            result = (
                self.supabase.table("ivo_books")
                .select("id, course_id")
                .eq("id", book_id)
                .eq("course_id", course_id)
                .execute()
            )
            
            if not result.data:
                return HierarchyValidationResult(
                    is_valid=False,
                    errors=[f"Book {book_id} não pertence ao curso {course_id}"]
                )
            
            return HierarchyValidationResult(is_valid=True)
            
        except Exception as e:
            logger.error(f"Erro na validação hierárquica: {str(e)}")
            return HierarchyValidationResult(
                is_valid=False,
                errors=[f"Erro de validação: {str(e)}"]
            )
    
    async def get_progression_analysis(
        self, 
        course_id: str, 
        book_id: str, 
        current_sequence: int
    ) -> ProgressionAnalysis:
        """Analisar progressão pedagógica."""
        try:
            # Buscar vocabulário ensinado
            taught_vocab = await self.get_taught_vocabulary(course_id, book_id, current_sequence)
            
            # Buscar estratégias usadas
            used_strategies = await self.get_used_strategies(course_id, book_id, current_sequence)
            
            # Buscar atividades usadas
            used_assessments = await self.get_used_assessments(course_id, book_id, current_sequence)
            
            # Contar estratégias
            strategy_distribution = {}
            for strategy in used_strategies:
                strategy_distribution[strategy] = strategy_distribution.get(strategy, 0) + 1
            
            # Análise de balanceamento
            assessment_balance = {}
            if isinstance(used_assessments, dict):
                assessment_balance = used_assessments
            
            # Gerar recomendações
            recommendations = []
            if len(taught_vocab) > 100:
                recommendations.append("Considerar revisão de vocabulário aprendido")
            
            if len(set(used_strategies)) < 3:
                recommendations.append("Diversificar estratégias pedagógicas")
            
            return ProgressionAnalysis(
                course_id=course_id,
                book_id=book_id,
                current_sequence=current_sequence,
                vocabulary_progression={"total_words": len(taught_vocab), "words": taught_vocab[:10]},
                strategy_distribution=strategy_distribution,
                assessment_balance=assessment_balance,
                recommendations=recommendations,
                quality_metrics={
                    "vocabulary_diversity": len(set(taught_vocab)) / max(len(taught_vocab), 1),
                    "strategy_diversity": len(set(used_strategies)) / max(len(used_strategies), 1)
                }
            )
            
        except Exception as e:
            logger.error(f"Erro na análise de progressão: {str(e)}")
            return ProgressionAnalysis(
                course_id=course_id,
                book_id=book_id,
                current_sequence=current_sequence
            )
    
    async def _get_next_book_sequence(self, course_id: str) -> int:
        """Determinar próximo sequence_order para book."""
        try:
            result = (
                self.supabase.table("ivo_books")
                .select("sequence_order")
                .eq("course_id", course_id)
                .order("sequence_order", desc=True)
                .limit(1)
                .execute()
            )
            
            if result.data:
                return result.data[0]["sequence_order"] + 1
            return 1
            
        except Exception as e:
            logger.error(f"Erro ao determinar próximo sequence para course {course_id}: {str(e)}")
            return 1
    
    async def _get_next_unit_sequence(self, book_id: str) -> int:
        """Determinar próximo sequence_order para unit."""
        try:
            result = (
                self.supabase.table("ivo_units")
                .select("sequence_order")
                .eq("book_id", book_id)
                .order("sequence_order", desc=True)
                .limit(1)
                .execute()
            )
            
            if result.data:
                return result.data[0]["sequence_order"] + 1
            return 1
            
        except Exception as e:
            logger.error(f"Erro ao determinar próximo sequence para book {book_id}: {str(e)}")
            return 1
    
    # =============================================================================
    # BULK OPERATIONS
    # =============================================================================
    
    async def get_course_hierarchy(self, course_id: str) -> Dict[str, Any]:
        """Buscar hierarquia completa do curso."""
        try:
            # Buscar curso
            course = await self.get_course(course_id)
            if not course:
                return {}
            
            # Buscar books do curso
            books = await self.list_books_by_course(course_id)
            
            # Para cada book, buscar suas units
            hierarchy = {
                "course": course.dict(),
                "books": []
            }
            
            for book in books:
                units = await self.list_units_by_book(book.id)
                book_data = book.dict()
                book_data["units"] = [unit.dict() for unit in units]
                hierarchy["books"].append(book_data)
            
            return hierarchy
            
        except Exception as e:
            logger.error(f"Erro ao buscar hierarquia do curso {course_id}: {str(e)}")
            return {}


# Instância global do serviço
hierarchical_db = HierarchicalDatabaseService()