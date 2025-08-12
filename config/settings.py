# config/settings.py
"""Configurações centralizadas do sistema IVO V2."""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Configurações principais do sistema."""
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.7
    
    # Database Configuration
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_key: Optional[str] = None
    
    # Application Configuration
    app_name: str = "IVO V2 - Intelligent Vocabulary Organizer"
    app_version: str = "2.0.0"
    app_environment: str = "development"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    reload: bool = True
    
    # Security
    secret_key: str = "your-super-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/minute"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # File Upload
    max_image_size: int = 10485760  # 10MB
    max_images_per_request: int = 5
    allowed_image_types: str = "jpg,jpeg,png,webp"
    
    # Paths
    upload_dir: str = "./data/images/uploads"
    processed_dir: str = "./data/images/processed"
    pdf_dir: str = "./data/pdfs/generated"
    temp_dir: str = "./data/temp"
    cache_dir: str = "./data/cache"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instância global das configurações
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Obter instância singleton das configurações."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Funções de conveniência para compatibilidade
def get_openai_api_key() -> Optional[str]:
    """Obter chave da API OpenAI."""
    return get_settings().openai_api_key


def get_supabase_config() -> dict:
    """Obter configurações do Supabase."""
    settings = get_settings()
    return {
        "url": settings.supabase_url,
        "anon_key": settings.supabase_anon_key,
        "service_key": settings.supabase_service_key
    }


def get_database_config() -> dict:
    """Obter configurações do banco de dados."""
    return get_supabase_config()


def is_development() -> bool:
    """Verificar se está em modo desenvolvimento."""
    return get_settings().app_environment.lower() == "development"


def is_production() -> bool:
    """Verificar se está em modo produção."""
    return get_settings().app_environment.lower() == "production"


# Validações de configuração
def validate_required_settings() -> dict:
    """Validar configurações obrigatórias."""
    settings = get_settings()
    missing = []
    warnings = []
    
    # Verificar configurações críticas
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    
    if not settings.supabase_anon_key:
        missing.append("SUPABASE_ANON_KEY")
    
    # Verificar configurações recomendadas
    if settings.secret_key == "your-super-secret-key-here-change-in-production":
        warnings.append("SECRET_KEY using default value - change in production")
    
    if is_production() and settings.debug:
        warnings.append("DEBUG=True in production environment")
    
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
        "environment": settings.app_environment
    }


# Para compatibilidade com código existente
def get_config():
    """Alias para get_settings() para compatibilidade."""
    return get_settings()