# config/models.py - ATUALIZADO PARA HIERARQUIA
"""Configuração dos modelos de IA com suporte a hierarquia."""
import os
import yaml
from typing import Dict, Any
from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    """Configurações do OpenAI."""
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.7
    
    class Config:
        env_file = ".env"


class LangChainSettings(BaseSettings):
    """Configurações do LangChain."""
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "curso-na-way"
    
    class Config:
        env_file = ".env"


def get_openai_config() -> OpenAISettings:
    """Retorna configurações do OpenAI."""
    return OpenAISettings()


def get_langchain_config() -> LangChainSettings:
    """Retorna configurações do LangChain."""
    return LangChainSettings()


def load_model_configs() -> Dict[str, Any]:
    """Carrega configurações dos modelos do YAML."""
    config_path = os.path.join(os.path.dirname(__file__), "models.yaml")
    
    if not os.path.exists(config_path):
        # Configuração padrão se arquivo não existir
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
                "ivo_vocab_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.5
                },
                "ivo_sentences_generation": {
                    "max_tokens": 1536,
                    "temperature": 0.6
                },
                "ivo_tips_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                "ivo_grammar_generation": {
                    "max_tokens": 2048,
                    "temperature": 0.6
                },
                "ivo_assessments_generation": {
                    "max_tokens": 3072,
                    "temperature": 0.6
                }
            }
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# Instâncias globais
openai_config = get_openai_config()
langchain_config = get_langchain_config()
model_configs = load_model_configs()