# config/logging.py
"""Configuração de logging do sistema."""
import logging
import logging.config
import yaml
import os
from pathlib import Path


def setup_logging():
    """Configurar sistema de logging."""
    
    # Criar diretório de logs se não existir
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configuração básica de logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            }
        },
        "loggers": {
            "curso_na_way": {
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "src": {
                "level": "DEBUG", 
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    }
    
    # Aplicar configuração
    logging.config.dictConfig(logging_config)
    
    # Log de inicialização
    logger = logging.getLogger(__name__)
    logger.info("✅ Sistema de logging configurado")


# Função para obter logger com nome consistente
def get_logger(name: str = None):
    """Obter logger configurado."""
    if name:
        return logging.getLogger(f"curso_na_way.{name}")
    return logging.getLogger("curso_na_way")