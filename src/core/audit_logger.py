# src/core/audit_logger.py
"""Sistema de logs de auditoria para operações hierárquicas."""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import Request
from enum import Enum
import asyncio
import uuid

# Configurar logger específico para auditoria
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Handler específico para auditoria (pode ser arquivo separado)
audit_handler = logging.FileHandler("logs/audit.log")
audit_formatter = logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "audit_data": %(message)s}'
)
audit_handler.setFormatter(audit_formatter)
audit_logger.addHandler(audit_handler)
audit_logger.propagate = False  # Não propagar para outros loggers


class AuditEventType(str, Enum):
    """Tipos de eventos de auditoria."""
    # Course operations
    COURSE_CREATED = "course_created"
    COURSE_VIEWED = "course_viewed"
    COURSE_UPDATED = "course_updated"
    COURSE_DELETED = "course_deleted"
    COURSE_HIERARCHY_ACCESSED = "course_hierarchy_accessed"
    
    # Book operations
    BOOK_CREATED = "book_created"
    BOOK_VIEWED = "book_viewed"
    BOOK_UPDATED = "book_updated"
    BOOK_DELETED = "book_deleted"
    BOOK_PROGRESSION_ANALYZED = "book_progression_analyzed"
    
    # Unit operations
    UNIT_CREATED = "unit_created"
    UNIT_VIEWED = "unit_viewed"
    UNIT_UPDATED = "unit_updated"
    UNIT_DELETED = "unit_deleted"  # ← ADICIONADO: valor que estava faltando
    UNIT_STATUS_CHANGED = "unit_status_changed"
    UNIT_CONTEXT_ACCESSED = "unit_context_accessed"
    UNIT_CONTENT_GENERATED = "unit_content_generated"
    
    # Special operations
    RAG_QUERY_EXECUTED = "rag_query_executed"
    IMAGE_ANALYZED = "image_analyzed"
    VOCABULARY_GENERATED = "vocabulary_generated"
    ASSESSMENT_GENERATED = "assessment_generated"
    
    # Security events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    VALIDATION_FAILED = "validation_failed"
    
    # System events
    API_ERROR = "api_error"
    PERFORMANCE_ALERT = "performance_alert"


class AuditLogger:
    """Sistema de auditoria para operações do IVO V2."""
    
    def __init__(self):
        self.logger = audit_logger
        self._request_tracking: Dict[str, Dict] = {}
    
    def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extrair informações da request para auditoria."""
        # IP real (considerando proxies)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return {
            "ip_address": client_ip,
            "user_agent": request.headers.get("User-Agent", ""),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": {
                key: value for key, value in request.headers.items()
                if key.lower() not in ['authorization', 'cookie', 'x-api-key']  # Filtrar headers sensíveis
            },
            "request_id": getattr(request.state, 'request_id', str(uuid.uuid4())),
        }
    
    def _extract_user_info(self, request: Request) -> Dict[str, Any]:
        """Extrair informações do usuário (se autenticado)."""
        # Placeholder para quando implementar autenticação
        user_info = {
            "user_id": getattr(request.state, 'user_id', None),
            "username": getattr(request.state, 'username', None),
            "user_role": getattr(request.state, 'user_role', None),
            "session_id": getattr(request.state, 'session_id', None),
        }
        
        return {k: v for k, v in user_info.items() if v is not None}
    
    async def log_event(
        self,
        event_type: AuditEventType,
        request: Optional[Request] = None,
        resource_info: Optional[Dict[str, Any]] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_details: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Registrar evento de auditoria.
        
        Args:
            event_type: Tipo do evento
            request: Request FastAPI (opcional)
            resource_info: Informações do recurso afetado
            additional_data: Dados adicionais específicos do evento
            success: Se a operação foi bem-sucedida
            error_details: Detalhes do erro (se houver)
            performance_metrics: Métricas de performance
        """
        try:
            audit_entry = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
            }
            
            # Informações da request
            if request:
                audit_entry["request"] = self._extract_request_info(request)
                audit_entry["user"] = self._extract_user_info(request)
            
            # Informações do recurso
            if resource_info:
                audit_entry["resource"] = resource_info
            
            # Dados adicionais
            if additional_data:
                audit_entry["additional_data"] = additional_data
            
            # Informações de erro
            if error_details:
                audit_entry["error"] = {
                    "message": error_details,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Métricas de performance
            if performance_metrics:
                audit_entry["performance"] = performance_metrics
            
            # Contexto específico do IVO V2
            audit_entry["system"] = {
                "service": "ivo-v2",
                "version": "2.0.0",
                "environment": "production"  # Poderia vir de variável de ambiente
            }
            
            # Log estruturado
            self.logger.info(json.dumps(audit_entry, ensure_ascii=False))
            
        except Exception as e:
            # Log de erro no sistema de auditoria não deve quebrar a aplicação
            logging.getLogger(__name__).error(f"Erro no sistema de auditoria: {str(e)}")
    
    async def log_hierarchy_operation(
        self,
        event_type: AuditEventType,
        request: Request,
        course_id: Optional[str] = None,
        book_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        operation_data: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_details: Optional[str] = None
    ) -> None:
        """Log específico para operações hierárquicas."""
        resource_info = {}
        
        if course_id:
            resource_info["course_id"] = course_id
        if book_id:
            resource_info["book_id"] = book_id
        if unit_id:
            resource_info["unit_id"] = unit_id
        
        # Determinar nível hierárquico
        if unit_id:
            resource_info["hierarchy_level"] = "unit"
        elif book_id:
            resource_info["hierarchy_level"] = "book"
        elif course_id:
            resource_info["hierarchy_level"] = "course"
        
        await self.log_event(
            event_type=event_type,
            request=request,
            resource_info=resource_info,
            additional_data=operation_data,
            success=success,
            error_details=error_details
        )
    
    async def log_rag_operation(
        self,
        request: Request,
        query_type: str,
        course_id: str,
        book_id: Optional[str] = None,
        sequence_order: Optional[int] = None,
        results_count: int = 0,
        processing_time: float = 0.0,
        success: bool = True
    ) -> None:
        """Log específico para operações RAG."""
        rag_data = {
            "query_type": query_type,
            "results_count": results_count,
            "processing_time_ms": processing_time * 1000,
            "sequence_context": sequence_order
        }
        
        performance_metrics = {
            "execution_time_ms": processing_time * 1000,
            "results_returned": results_count
        }
        
        await self.log_hierarchy_operation(
            event_type=AuditEventType.RAG_QUERY_EXECUTED,
            request=request,
            course_id=course_id,
            book_id=book_id,
            operation_data=rag_data,
            success=success
        )
    
    async def log_content_generation(
        self,
        request: Request,
        generation_type: str,
        unit_id: str,
        book_id: str,
        course_id: str,
        content_stats: Optional[Dict[str, Any]] = None,
        ai_usage: Optional[Dict[str, Any]] = None,
        processing_time: float = 0.0,
        success: bool = True,
        error_details: Optional[str] = None
    ) -> None:
        """Log específico para geração de conteúdo."""
        generation_data = {
            "generation_type": generation_type,
            "processing_time_ms": processing_time * 1000,
            "content_stats": content_stats or {},
            "ai_usage": ai_usage or {}
        }
        
        await self.log_hierarchy_operation(
            event_type=AuditEventType.UNIT_CONTENT_GENERATED,
            request=request,
            course_id=course_id,
            book_id=book_id,
            unit_id=unit_id,
            operation_data=generation_data,
            success=success,
            error_details=error_details
        )
    
    def start_request_tracking(self, request: Request) -> str:
        """Iniciar tracking de uma request para métricas de performance."""
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        request.state.request_id = request_id
        
        self._request_tracking[request_id] = {
            "start_time": time.time(),
            "path": request.url.path,
            "method": request.method
        }
        
        return request_id
    
    def end_request_tracking(
        self, 
        request: Request, 
        status_code: int,
        response_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Finalizar tracking e retornar métricas."""
        request_id = getattr(request.state, 'request_id', None)
        if not request_id or request_id not in self._request_tracking:
            return {}
        
        tracking_data = self._request_tracking.pop(request_id)
        end_time = time.time()
        duration = end_time - tracking_data["start_time"]
        
        metrics = {
            "request_id": request_id,
            "duration_ms": duration * 1000,
            "status_code": status_code,
            "response_size_bytes": response_size,
            "path": tracking_data["path"],
            "method": tracking_data["method"]
        }
        
        # Log de performance se for lento
        if duration > 2.0:  # > 2 segundos
            asyncio.create_task(self.log_event(
                event_type=AuditEventType.PERFORMANCE_ALERT,
                request=request,
                additional_data={"slow_request": True},
                performance_metrics=metrics
            ))
        
        return metrics


# Instância global
audit_logger_instance = AuditLogger()


# Decorador para auditoria automática
def audit_endpoint(
    event_type: AuditEventType,
    resource_extractor: Optional[callable] = None,
    track_performance: bool = True
):
    """
    Decorador para auditoria automática de endpoints.
    
    Args:
        event_type: Tipo do evento de auditoria
        resource_extractor: Função para extrair informações do recurso
        track_performance: Se deve trackear performance
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extrair request dos argumentos
            request = None
            for arg in args:
                if hasattr(arg, 'method') and hasattr(arg, 'url'):
                    request = arg
                    break
            
            if not request:
                # Buscar request nos kwargs
                request = kwargs.get('request')
            
            # Iniciar tracking
            if request and track_performance:
                audit_logger_instance.start_request_tracking(request)
            
            start_time = time.time()
            success = True
            error_details = None
            result = None
            
            try:
                # Executar função original
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                success = False
                error_details = str(e)
                raise
                
            finally:
                if request:
                    # Extrair informações do recurso
                    resource_info = {}
                    if resource_extractor and result:
                        try:
                            resource_info = resource_extractor(result, *args, **kwargs)
                        except Exception:
                            pass  # Não quebrar por erro no extractor
                    
                    # Log do evento
                    processing_time = time.time() - start_time
                    await audit_logger_instance.log_event(
                        event_type=event_type,
                        request=request,
                        resource_info=resource_info,
                        success=success,
                        error_details=error_details,
                        performance_metrics={"processing_time_ms": processing_time * 1000}
                    )
        
        return wrapper
    return decorator


# Extractors específicos para recursos
def extract_course_info(result, *args, **kwargs) -> Dict[str, Any]:
    """Extrator de informações de curso."""
    try:
        if hasattr(result, 'data') and isinstance(result.data, dict):
            course_data = result.data.get('course', {})
            return {
                "course_id": course_data.get('id'),
                "course_name": course_data.get('name'),
                "target_levels": course_data.get('target_levels', []),
                "language_variant": course_data.get('language_variant')
            }
    except Exception:
        pass
    return {}


def extract_book_info(result, *args, **kwargs) -> Dict[str, Any]:
    """Extrator de informações de book."""
    try:
        if hasattr(result, 'data') and isinstance(result.data, dict):
            book_data = result.data.get('book', {})
            return {
                "book_id": book_data.get('id'),
                "book_name": book_data.get('name'),
                "course_id": book_data.get('course_id'),
                "target_level": book_data.get('target_level'),
                "sequence_order": book_data.get('sequence_order')
            }
    except Exception:
        pass
    return {}


def extract_unit_info(result, *args, **kwargs) -> Dict[str, Any]:
    """Extrator de informações de unit."""
    try:
        if hasattr(result, 'data') and isinstance(result.data, dict):
            unit_data = result.data.get('unit', {})
            hierarchy_context = result.data.get('hierarchy_context', {})
            return {
                "unit_id": unit_data.get('id'),
                "unit_title": unit_data.get('title'),
                "book_id": hierarchy_context.get('book_id'),
                "course_id": hierarchy_context.get('course_id'),
                "sequence_order": unit_data.get('sequence_order'),
                "unit_type": unit_data.get('unit_type'),
                "status": unit_data.get('status')
            }
    except Exception:
        pass
    return {}


# Context manager para operações complexas
class AuditContext:
    """Context manager para auditoria de operações complexas."""
    
    def __init__(
        self,
        event_type: AuditEventType,
        request: Request,
        operation_name: str
    ):
        self.event_type = event_type
        self.request = request
        self.operation_name = operation_name
        self.start_time = None
        self.additional_data = {}
        self.success = True
        self.error_details = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        self.additional_data["operation_name"] = self.operation_name
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
            self.error_details = str(exc_val)
        
        processing_time = time.time() - self.start_time
        self.additional_data["processing_time_ms"] = processing_time * 1000
        
        await audit_logger_instance.log_event(
            event_type=self.event_type,
            request=self.request,
            additional_data=self.additional_data,
            success=self.success,
            error_details=self.error_details,
            performance_metrics={"processing_time_ms": processing_time * 1000}
        )
    
    def add_data(self, key: str, value: Any):
        """Adicionar dados contextuais durante a operação."""
        self.additional_data[key] = value