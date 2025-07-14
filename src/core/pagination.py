# src/core/pagination.py
"""Sistema de paginação para endpoints hierárquicos."""

from typing import List, Optional, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field, validator
from math import ceil
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Parâmetros de paginação."""
    page: int = Field(1, ge=1, description="Número da página (inicia em 1)")
    size: int = Field(20, ge=1, le=100, description="Itens por página (máx 100)")
    
    @validator('page')
    def validate_page(cls, v):
        if v < 1:
            raise ValueError("Página deve ser >= 1")
        return v
    
    @validator('size')
    def validate_size(cls, v):
        if v < 1:
            raise ValueError("Size deve ser >= 1")
        if v > 100:
            raise ValueError("Size máximo é 100")
        return v
    
    @property
    def offset(self) -> int:
        """Calcular offset para SQL."""
        return (self.page - 1) * self.size
    
    @property
    def limit(self) -> int:
        """Alias para size."""
        return self.size


class PaginationMeta(BaseModel):
    """Metadados da paginação."""
    page: int = Field(..., description="Página atual")
    size: int = Field(..., description="Itens por página")
    total: int = Field(..., description="Total de itens")
    pages: int = Field(..., description="Total de páginas")
    has_next: bool = Field(..., description="Tem próxima página")
    has_prev: bool = Field(..., description="Tem página anterior")
    next_page: Optional[int] = Field(None, description="Número da próxima página")
    prev_page: Optional[int] = Field(None, description="Número da página anterior")
    
    @classmethod
    def create(cls, page: int, size: int, total: int) -> "PaginationMeta":
        """Criar metadados de paginação."""
        pages = ceil(total / size) if total > 0 else 1
        has_next = page < pages
        has_prev = page > 1
        
        return cls(
            page=page,
            size=size,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=page + 1 if has_next else None,
            prev_page=page - 1 if has_prev else None
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Response paginado genérico."""
    success: bool = Field(True, description="Status da operação")
    data: List[T] = Field(..., description="Dados da página atual")
    pagination: PaginationMeta = Field(..., description="Metadados de paginação")
    message: Optional[str] = Field(None, description="Mensagem opcional")
    
    # Campos específicos da hierarquia
    hierarchy_info: Optional[Dict[str, str]] = Field(None, description="Informações hierárquicas")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filtros aplicados")
    sort_info: Optional[Dict[str, str]] = Field(None, description="Informações de ordenação")
    
    class Config:
        arbitrary_types_allowed = True


class SortParams(BaseModel):
    """Parâmetros de ordenação."""
    sort_by: str = Field("created_at", description="Campo para ordenação")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="Ordem (asc/desc)")
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v.lower() not in ['asc', 'desc']:
            raise ValueError("sort_order deve ser 'asc' ou 'desc'")
        return v.lower()
    
    @property
    def is_descending(self) -> bool:
        """Verificar se é ordenação decrescente."""
        return self.sort_order == "desc"


class FilterParams(BaseModel):
    """Parâmetros de filtro base."""
    search: Optional[str] = Field(None, description="Busca por texto")
    created_after: Optional[str] = Field(None, description="Filtrar por data de criação (ISO)")
    created_before: Optional[str] = Field(None, description="Filtrar por data de criação (ISO)")
    
    def to_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Converter para dicionário."""
        data = self.dict(exclude_none=exclude_none)
        return {k: v for k, v in data.items() if v is not None} if exclude_none else data


# Filtros específicos por entidade
class CourseFilterParams(FilterParams):
    """Filtros específicos para cursos."""
    language_variant: Optional[str] = Field(None, description="Variante do idioma")
    target_level: Optional[str] = Field(None, description="Nível CEFR")
    methodology: Optional[str] = Field(None, description="Metodologia aplicada")


class BookFilterParams(FilterParams):
    """Filtros específicos para books."""
    target_level: Optional[str] = Field(None, description="Nível CEFR do book")
    course_id: Optional[str] = Field(None, description="ID do curso")


class UnitFilterParams(FilterParams):
    """Filtros específicos para units."""
    status: Optional[str] = Field(None, description="Status da unidade")
    unit_type: Optional[str] = Field(None, description="Tipo da unidade")
    cefr_level: Optional[str] = Field(None, description="Nível CEFR")
    book_id: Optional[str] = Field(None, description="ID do book")
    course_id: Optional[str] = Field(None, description="ID do curso")
    quality_score_min: Optional[float] = Field(None, ge=0.0, le=1.0, description="Score mínimo de qualidade")


# Helper functions
def create_pagination_params(
    page: int = 1,
    size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> tuple[PaginationParams, SortParams]:
    """Criar parâmetros de paginação e ordenação."""
    pagination = PaginationParams(page=page, size=size)
    sorting = SortParams(sort_by=sort_by, sort_order=sort_order)
    return pagination, sorting


def build_sql_query_parts(
    base_table: str,
    pagination: PaginationParams,
    sorting: SortParams,
    filters: Optional[FilterParams] = None,
    allowed_sort_fields: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Construir partes da query SQL para paginação e filtros.
    
    Args:
        base_table: Nome da tabela base
        pagination: Parâmetros de paginação
        sorting: Parâmetros de ordenação
        filters: Filtros opcionais
        allowed_sort_fields: Campos permitidos para ordenação
        
    Returns:
        Dict com partes da query SQL
    """
    # Validar campo de ordenação
    if allowed_sort_fields and sorting.sort_by not in allowed_sort_fields:
        logger.warning(f"Campo de ordenação inválido: {sorting.sort_by}. Usando 'created_at'")
        sorting.sort_by = "created_at"
    
    # WHERE clause
    where_conditions = []
    if filters:
        filter_dict = filters.to_dict()
        
        # Busca por texto
        if filter_dict.get('search'):
            where_conditions.append(f"(name ILIKE '%{filter_dict['search']}%' OR description ILIKE '%{filter_dict['search']}%')")
        
        # Filtros de data
        if filter_dict.get('created_after'):
            where_conditions.append(f"created_at >= '{filter_dict['created_after']}'")
        
        if filter_dict.get('created_before'):
            where_conditions.append(f"created_at <= '{filter_dict['created_before']}'")
        
        # Filtros específicos (adicionados dinamicamente)
        for key, value in filter_dict.items():
            if key not in ['search', 'created_after', 'created_before'] and value:
                where_conditions.append(f"{key} = '{value}'")
    
    where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
    
    # ORDER BY clause
    order_clause = f"ORDER BY {sorting.sort_by} {sorting.sort_order.upper()}"
    
    # LIMIT and OFFSET
    limit_clause = f"LIMIT {pagination.limit} OFFSET {pagination.offset}"
    
    return {
        "where": where_clause,
        "order": order_clause,
        "limit": limit_clause,
        "offset": str(pagination.offset),
        "page_size": str(pagination.size)
    }


async def paginate_query_results(
    data: List[T],
    total_count: int,
    pagination: PaginationParams,
    filters: Optional[FilterParams] = None,
    message: Optional[str] = None,
    hierarchy_info: Optional[Dict[str, str]] = None
) -> PaginatedResponse[T]:
    """
    Criar response paginado a partir dos resultados.
    
    Args:
        data: Lista de dados da página atual
        total_count: Total de registros (sem paginação)
        pagination: Parâmetros de paginação usados
        filters: Filtros aplicados
        message: Mensagem opcional
        hierarchy_info: Informações hierárquicas
        
    Returns:
        Response paginado
    """
    pagination_meta = PaginationMeta.create(
        page=pagination.page,
        size=pagination.size,
        total=total_count
    )
    
    # Log da paginação
    logger.info(
        f"Paginação executada",
        extra={
            "page": pagination.page,
            "size": pagination.size,
            "total": total_count,
            "pages": pagination_meta.pages,
            "filters": filters.to_dict() if filters else None
        }
    )
    
    return PaginatedResponse[T](
        data=data,
        pagination=pagination_meta,
        message=message or f"Página {pagination.page} de {pagination_meta.pages}",
        hierarchy_info=hierarchy_info,
        filters_applied=filters.to_dict() if filters else None
    )


# Query builders específicos para cada entidade
class QueryBuilder:
    """Builder para queries paginadas específicas do domínio."""
    
    @staticmethod
    def build_courses_query(
        pagination: PaginationParams,
        sorting: SortParams,
        filters: Optional[CourseFilterParams] = None
    ) -> str:
        """Construir query para listar cursos."""
        allowed_fields = ["name", "created_at", "updated_at", "target_levels"]
        parts = build_sql_query_parts(
            "ivo_courses",
            pagination,
            sorting,
            filters,
            allowed_fields
        )
        
        base_query = "SELECT * FROM ivo_courses"
        count_query = "SELECT COUNT(*) FROM ivo_courses"
        
        query = f"{base_query} {parts['where']} {parts['order']} {parts['limit']}"
        count = f"{count_query} {parts['where']}"
        
        return {"data_query": query, "count_query": count}
    
    @staticmethod
    def build_books_query(
        course_id: str,
        pagination: PaginationParams,
        sorting: SortParams,
        filters: Optional[BookFilterParams] = None
    ) -> str:
        """Construir query para listar books de um curso."""
        allowed_fields = ["name", "target_level", "sequence_order", "created_at"]
        
        # Adicionar filtro de curso
        if filters:
            filters.course_id = course_id
        else:
            filters = BookFilterParams(course_id=course_id)
        
        parts = build_sql_query_parts(
            "ivo_books",
            pagination,
            sorting,
            filters,
            allowed_fields
        )
        
        base_query = "SELECT * FROM ivo_books"
        count_query = "SELECT COUNT(*) FROM ivo_books"
        
        query = f"{base_query} {parts['where']} {parts['order']} {parts['limit']}"
        count = f"{count_query} {parts['where']}"
        
        return {"data_query": query, "count_query": count}
    
    @staticmethod
    def build_units_query(
        book_id: str,
        pagination: PaginationParams,
        sorting: SortParams,
        filters: Optional[UnitFilterParams] = None
    ) -> str:
        """Construir query para listar units de um book."""
        allowed_fields = ["title", "sequence_order", "status", "cefr_level", "created_at", "quality_score"]
        
        # Adicionar filtro de book
        if filters:
            filters.book_id = book_id
        else:
            filters = UnitFilterParams(book_id=book_id)
        
        parts = build_sql_query_parts(
            "ivo_units",
            pagination,
            sorting,
            filters,
            allowed_fields
        )
        
        base_query = "SELECT * FROM ivo_units"
        count_query = "SELECT COUNT(*) FROM ivo_units"
        
        query = f"{base_query} {parts['where']} {parts['order']} {parts['limit']}"
        count = f"{count_query} {parts['where']}"
        
        return {"data_query": query, "count_query": count}