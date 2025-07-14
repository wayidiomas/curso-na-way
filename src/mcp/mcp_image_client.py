# src/mcp/mcp_image_client.py - CORREÇÃO DO CAMINHO
"""
Cliente MCP para integração com o Image Analysis Server
Implementação do PROMPT 3 do IVO V2 Guide - Lado Cliente
"""

import asyncio
import base64
import json
import logging
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from mcp import ClientSession, StdioServerParameters, create_stdio_client
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MCPImageAnalysisClient:
    """Cliente para comunicação com o MCP Image Analysis Server."""
    
    def __init__(self, server_path: Optional[str] = None):
        """
        Inicializar cliente MCP.
        
        Args:
            server_path: Caminho para o servidor MCP (opcional)
        """
        self.session: Optional[ClientSession] = None
        self.server_path = server_path or self._get_default_server_path()
        self.is_connected = False
        
    def _get_default_server_path(self) -> str:
        """Obter caminho padrão do servidor MCP."""
        # CORREÇÃO: Caminho correto para o servidor
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "src" / "mcp" / "image_analysis_server.py")
    
    async def connect(self) -> bool:
        """
        Conectar ao servidor MCP.
        
        Returns:
            True se conectado com sucesso
        """
        try:
            logger.info("🔌 Conectando ao MCP Image Analysis Server...")
            
            # Verificar se o arquivo do servidor existe
            if not os.path.exists(self.server_path):
                logger.error(f"❌ Servidor MCP não encontrado em: {self.server_path}")
                return False
            
            # Configurar parâmetros do servidor stdio
            server_params = StdioServerParameters(
                command="python",
                args=[self.server_path],
                env={
                    **os.environ,
                    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "")
                }
            )
            
            # Criar cliente e sessão
            client = await create_stdio_client(server_params)
            self.session = client.session
            
            # Verificar conexão listando tools disponíveis
            tools = await self.session.list_tools()
            
            self.is_connected = True
            logger.info(f"✅ Conectado ao MCP Server com {len(tools.tools)} tools disponíveis")
            
            # Log das tools disponíveis
            for tool in tools.tools:
                logger.info(f"   📱 {tool.name}: {tool.description}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com MCP Server: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Desconectar do servidor MCP."""
        if self.session:
            try:
                await self.session.close()
                self.is_connected = False
                logger.info("🔌 Desconectado do MCP Server")
            except Exception as e:
                logger.warning(f"Erro ao desconectar: {str(e)}")
    
    async def analyze_image(
        self,
        image_data: str,
        context: str = "",
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit"
    ) -> Dict[str, Any]:
        """
        Analisar imagem para contexto educacional.
        
        Args:
            image_data: Imagem em base64
            context: Contexto educacional
            cefr_level: Nível CEFR
            unit_type: Tipo de unidade
            
        Returns:
            Resultado da análise
        """
        if not self.is_connected:
            raise RuntimeError("Client not connected to MCP server")
        
        try:
            logger.info("🔍 Analisando imagem com MCP Server...")
            
            # Chamar tool analyze_image
            result = await self.session.call_tool(
                name="analyze_image",
                arguments={
                    "image_data": image_data,
                    "context": context,
                    "cefr_level": cefr_level,
                    "unit_type": unit_type
                }
            )
            
            # Processar resultado
            if result.content and len(result.content) > 0:
                response_text = result.content[0].text
                response_data = json.loads(response_text)
                
                logger.info("✅ Análise de imagem concluída")
                return response_data
            else:
                raise ValueError("Empty response from MCP server")
                
        except Exception as e:
            logger.error(f"❌ Erro na análise de imagem: {str(e)}")
            raise
    
    async def suggest_vocabulary(
        self,
        image_data: str,
        target_count: int = 25,
        cefr_level: str = "A2"
    ) -> List[Dict[str, Any]]:
        """
        Sugerir vocabulário baseado na imagem.
        
        Args:
            image_data: Imagem em base64
            target_count: Número desejado de palavras
            cefr_level: Nível CEFR
            
        Returns:
            Lista de vocabulário sugerido
        """
        if not self.is_connected:
            raise RuntimeError("Client not connected to MCP server")
        
        try:
            logger.info(f"📚 Sugerindo {target_count} palavras de vocabulário...")
            
            result = await self.session.call_tool(
                name="suggest_vocabulary",
                arguments={
                    "image_data": image_data,
                    "target_count": target_count,
                    "cefr_level": cefr_level
                }
            )
            
            if result.content and len(result.content) > 0:
                response_text = result.content[0].text
                response_data = json.loads(response_text)
                
                if response_data.get("success"):
                    vocabulary = response_data.get("vocabulary", [])
                    logger.info(f"✅ {len(vocabulary)} palavras de vocabulário sugeridas")
                    return vocabulary
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    raise ValueError(f"MCP server error: {error_msg}")
            else:
                raise ValueError("Empty response from MCP server")
                
        except Exception as e:
            logger.error(f"❌ Erro na sugestão de vocabulário: {str(e)}")
            raise
    
    async def detect_objects(self, image_data: str) -> Dict[str, Any]:
        """
        Detectar objetos e cenas na imagem.
        
        Args:
            image_data: Imagem em base64
            
        Returns:
            Informações de detecção
        """
        if not self.is_connected:
            raise RuntimeError("Client not connected to MCP server")
        
        try:
            logger.info("👁️ Detectando objetos e cenas...")
            
            result = await self.session.call_tool(
                name="detect_objects",
                arguments={"image_data": image_data}
            )
            
            if result.content and len(result.content) > 0:
                response_text = result.content[0].text
                response_data = json.loads(response_text)
                
                if response_data.get("success"):
                    detection = response_data.get("detection", {})
                    logger.info("✅ Detecção de objetos concluída")
                    return detection
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    raise ValueError(f"MCP server error: {error_msg}")
            else:
                raise ValueError("Empty response from MCP server")
                
        except Exception as e:
            logger.error(f"❌ Erro na detecção de objetos: {str(e)}")
            raise


# Service class para integração fácil com endpoints V2
class MCPImageService:
    """Serviço principal para análise de imagens via MCP."""
    
    def __init__(self):
        self.client = MCPImageAnalysisClient()
    
    async def __aenter__(self):
        """Context manager async entry."""
        await self.client.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager async exit."""
        await self.client.disconnect()
    
    async def analyze_uploaded_images_for_unit(
        self,
        image_files_b64: List[str],
        context: str = "",
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit"
    ) -> Dict[str, Any]:
        """
        Analisar múltiplas imagens já convertidas para base64.
        
        Args:
            image_files_b64: Lista de imagens em base64
            context: Contexto educacional
            cefr_level: Nível CEFR
            unit_type: Tipo de unidade
            
        Returns:
            Análise consolidada das imagens
        """
        analyses = []
        all_vocabulary = []
        
        for i, image_b64 in enumerate(image_files_b64):
            try:
                logger.info(f"📸 Analisando imagem {i+1}/{len(image_files_b64)}")
                
                # Análise individual da imagem
                analysis = await self.client.analyze_image(
                    image_data=image_b64,
                    context=context,
                    cefr_level=cefr_level,
                    unit_type=unit_type
                )
                
                # Sugerir vocabulário específico
                vocabulary = await self.client.suggest_vocabulary(
                    image_data=image_b64,
                    target_count=15,  # Menos por imagem para não sobrecarregar
                    cefr_level=cefr_level
                )
                
                analysis["vocabulary_suggestions"] = vocabulary
                analysis["image_sequence"] = i + 1
                
                analyses.append(analysis)
                all_vocabulary.extend(vocabulary)
                
            except Exception as e:
                logger.error(f"❌ Erro ao analisar imagem {i+1}: {str(e)}")
                analyses.append({
                    "error": str(e),
                    "image_sequence": i + 1
                })
        
        # Consolidar vocabulário único
        seen_words = set()
        unique_vocabulary = []
        
        for word_item in all_vocabulary:
            word = word_item.get("word", "").lower()
            if word and word not in seen_words:
                seen_words.add(word)
                unique_vocabulary.append(word_item)
        
        # Ordenar por relevância
        unique_vocabulary.sort(
            key=lambda x: x.get("relevance_score", 5), 
            reverse=True
        )
        
        # Limitar a 25 palavras finais
        final_vocabulary = unique_vocabulary[:25]
        
        return {
            "success": True,
            "individual_analyses": analyses,
            "consolidated_vocabulary": {
                "vocabulary": final_vocabulary,
                "total_words": len(final_vocabulary),
                "deduplication_stats": {
                    "original_count": len(all_vocabulary),
                    "unique_count": len(unique_vocabulary),
                    "final_count": len(final_vocabulary)
                }
            },
            "summary": {
                "total_images": len(image_files_b64),
                "successful_analyses": len([a for a in analyses if "error" not in a]),
                "context": context,
                "cefr_level": cefr_level,
                "unit_type": unit_type
            },
            "generated_at": datetime.now().isoformat()
        }


# Função de conveniência para uso nos endpoints V2
async def analyze_images_for_unit_creation(
    image_files_b64: List[str],
    context: str = "",
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> Dict[str, Any]:
    """
    Função específica para análise de imagens durante criação de unidades.
    
    Args:
        image_files_b64: Lista de imagens em base64
        context: Contexto educacional
        cefr_level: Nível CEFR
        unit_type: Tipo de unidade
        
    Returns:
        Análise pronta para integração com API V2
    """
    try:
        async with MCPImageService() as service:
            result = await service.analyze_uploaded_images_for_unit(
                image_files_b64=image_files_b64,
                context=context,
                cefr_level=cefr_level,
                unit_type=unit_type
            )
            
            return result
            
    except Exception as e:
        logger.error(f"❌ Erro na análise de imagens para unidade: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Falha na análise de imagens via MCP"
        }