# src/core/database.py
"""Inicializador do banco de dados com suporte a hierarquia."""
import logging
from config.database import get_supabase_client

logger = logging.getLogger(__name__)


async def init_database():
    """Inicializar banco de dados e verificar estrutura hierárquica."""
    try:
        supabase = get_supabase_client()
        
        # Verificar se as tabelas hierárquicas existem
        await _check_hierarchical_tables(supabase)
        
        # Verificar se as funções RAG existem
        await _check_rag_functions(supabase)
        
        logger.info("✅ Banco de dados inicializado com hierarquia")
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {str(e)}")
        raise


async def _check_hierarchical_tables(supabase):
    """Verificar se as tabelas hierárquicas existem."""
    required_tables = ["ivo_courses", "ivo_books", "ivo_units", "ivo_unit_embeddings"]
    
    for table in required_tables:
        try:
            # Teste simples para verificar se a tabela existe
            result = supabase.table(table).select("count", count="exact").limit(1).execute()
            logger.info(f"✅ Tabela {table}: {result.count} registros")
        except Exception as e:
            logger.warning(f"⚠️  Tabela {table} pode não existir: {str(e)}")


async def _check_rag_functions(supabase):
    """Verificar se as funções RAG existem."""
    try:
        # Testar função get_taught_vocabulary
        result = supabase.rpc("get_taught_vocabulary", {
            "target_course_id": "test_course",
            "target_book_id": None,
            "target_sequence": None
        }).execute()
        
        logger.info("✅ Funções RAG estão disponíveis")
        
    except Exception as e:
        logger.warning(f"⚠️  Funções RAG podem não existir: {str(e)}")
        logger.warning("Execute o SQL das funções no Supabase Dashboard")