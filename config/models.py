"""Configuração dos modelos de IA."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from config.logging import get_logger

logger = get_logger("models_config")


class OpenAISettings(BaseSettings):
    """Configurações do OpenAI."""
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.7
    
    class Config:
        env_file = ".env"


class ModelConfigs:
    """Gerenciador de configurações dos modelos."""
    
    def __init__(self):
        self.configs = {}
        self._load_configs()
    
    def _load_configs(self):
        """Carregar configurações do arquivo YAML."""
        try:
            config_path = Path("config/models.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.configs = yaml.safe_load(f)
                logger.info("✅ Configurações dos modelos carregadas")
            else:
                # Configurações padrão se arquivo não existir
                self.configs = self._get_default_configs()
                logger.warning("⚠️ Arquivo models.yaml não encontrado, usando configurações padrão")
                
        except Exception as e:
            logger.error(f"❌ Erro ao carregar configurações: {e}")
            self.configs = self._get_default_configs()
    
    def _get_default_configs(self) -> Dict[str, Any]:
        """Configurações padrão dos modelos."""
        return {
            "openai": {
                "model": "gpt-4-turbo-preview",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_retries": 3
            },
            "content_configs": {
                "vocab_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.5
                },
                "teoria_generation": {
                    "max_tokens": 3072,
                    "temperature": 0.6
                },
                "frases_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                "gramatica_generation": {
                    "max_tokens": 3072,
                    "temperature": 0.5
                },
                "tips_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.8
                },
                "exercicios_generation": {
                    "max_tokens": 4096,
                    "temperature": 0.6
                }
            }
        }
    
    def get_openai_config(self) -> Dict[str, Any]:
        """Obter configurações do OpenAI."""
        openai_config = self.configs.get("openai", {})
        
        # Mesclar com variáveis de ambiente
        env_settings = OpenAISettings()
        
        return {
            "model": getattr(env_settings, 'openai_model', openai_config.get("model")),
            "max_tokens": getattr(env_settings, 'openai_max_tokens', openai_config.get("max_tokens")),
            "temperature": getattr(env_settings, 'openai_temperature', openai_config.get("temperature")),
            "timeout": openai_config.get("timeout", 60),
            "max_retries": openai_config.get("max_retries", 3),
            "api_key": env_settings.openai_api_key,
            "content_configs": self.configs.get("content_configs", {})
        }
    
    def get_content_config(self, content_type: str) -> Dict[str, Any]:
        """Obter configuração específica para tipo de conteúdo."""
        content_configs = self.configs.get("content_configs", {})
        return content_configs.get(content_type, {})


# Instância global
_model_configs = ModelConfigs()


def get_openai_config() -> Dict[str, Any]:
    """
    Função para obter configurações do OpenAI.
    
    Returns:
        Dict: Configurações do OpenAI
    """
    return _model_configs.get_openai_config()


def load_model_configs() -> Dict[str, Any]:
    """
    Função para carregar todas as configurações dos modelos.
    
    Returns:
        Dict: Todas as configurações
    """
    return _model_configs.configs


def get_content_config(content_type: str) -> Dict[str, Any]:
    """
    Obter configuração para um tipo específico de conteúdo.
    
    Args:
        content_type: Tipo de conteúdo (vocab_generation, teoria_generation, etc.)
        
    Returns:
        Dict: Configurações específicas do tipo
    """
    return _model_configs.get_content_config(content_type)


def reload_configs():
    """Recarregar configurações dos modelos."""
    global _model_configs
    _model_configs = ModelConfigs()
    logger.info("🔄 Configurações dos modelos recarregadas")


# Função para validar se as configurações estão corretas
def validate_openai_config() -> bool:
    """
    Validar se as configurações do OpenAI estão corretas.
    
    Returns:
        bool: True se válidas, False caso contrário
    """
    try:
        config = get_openai_config()
        
        # Verificar se API key está presente
        if not config.get("api_key"):
            logger.error("❌ OPENAI_API_KEY não configurada")
            return False
            
        # Verificar configurações básicas
        required_fields = ["model", "max_tokens", "temperature"]
        for field in required_fields:
            if field not in config:
                logger.error(f"❌ Campo obrigatório '{field}' não encontrado")
                return False
        
        logger.info("✅ Configurações do OpenAI válidas")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao validar configurações: {e}")
        return False


# Exemplo de uso para debug
if __name__ == "__main__":
    print("🔧 Testando configurações dos modelos...")
    
    # Testar carregamento
    config = get_openai_config()
    print(f"Modelo: {config['model']}")
    print(f"Max Tokens: {config['max_tokens']}")
    print(f"Temperature: {config['temperature']}")
    
    # Testar configuração de conteúdo específico
    grammar_config = get_content_config("gramatica_generation")
    print(f"Grammar Config: {grammar_config}")
    
    # Validar configurações
    is_valid = validate_openai_config()
    print(f"Configurações válidas: {is_valid}")