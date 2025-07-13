"""Configuração do banco de dados Supabase."""
import os
from supabase import create_client, Client
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    
    class Config:
        env_file = ".env"


def get_supabase_client() -> Client:
    """Retorna cliente configurado do Supabase."""
    settings = DatabaseSettings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_supabase_admin_client() -> Client:
    """Retorna cliente admin do Supabase."""
    settings = DatabaseSettings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
