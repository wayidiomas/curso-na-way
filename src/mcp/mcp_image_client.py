# src/mcp/mcp_image_client.py
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
        # Caminho relativo ao projeto
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "src" / "mcp_servers" / "image_analysis_server.py")
    
    async def connect(self) -> bool:
        """
        Conectar ao servidor MCP.
        
        Returns:
            True se conectado com sucesso
        """
        try:
            logger.info("🔌 Conectando ao MCP Image Analysis Server...")
            
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


class ImageToBase64Converter:
    """Utilitário para conversão de imagens para base64."""
    
    @staticmethod
    def from_file_path(file_path: str) -> str:
        """
        Converter arquivo de imagem para base64.
        
        Args:
            file_path: Caminho para o arquivo de imagem
            
        Returns:
            String base64 da imagem
        """
        try:
            with open(file_path, "rb") as image_file:
                image_data = image_file.read()
                base64_string = base64.b64encode(image_data).decode('utf-8')
                return base64_string
        except Exception as e:
            logger.error(f"Erro ao converter imagem {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def from_pil_image(pil_image: Image.Image, format: str = "JPEG") -> str:
        """
        Converter PIL Image para base64.
        
        Args:
            pil_image: Objeto PIL Image
            format: Formato da imagem (JPEG, PNG, etc.)
            
        Returns:
            String base64 da imagem
        """
        try:
            buffer = io.BytesIO()
            pil_image.save(buffer, format=format)
            image_data = buffer.getvalue()
            base64_string = base64.b64encode(image_data).decode('utf-8')
            return base64_string
        except Exception as e:
            logger.error(f"Erro ao converter PIL image: {str(e)}")
            raise
    
    @staticmethod
    def from_bytes(image_bytes: bytes) -> str:
        """
        Converter bytes de imagem para base64.
        
        Args:
            image_bytes: Bytes da imagem
            
        Returns:
            String base64 da imagem
        """
        try:
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            return base64_string
        except Exception as e:
            logger.error(f"Erro ao converter bytes: {str(e)}")
            raise


# LangChain Tools para integração
class ImageAnalysisInput(BaseModel):
    """Input schema para tool de análise de imagem."""
    image_path: str = Field(..., description="Caminho para o arquivo de imagem")
    context: str = Field("", description="Contexto educacional opcional")
    cefr_level: str = Field("A2", description="Nível CEFR (A1-C2)")
    unit_type: str = Field("lexical_unit", description="Tipo de unidade (lexical_unit/grammar_unit)")


class VocabularySuggestionInput(BaseModel):
    """Input schema para tool de sugestão de vocabulário."""
    image_path: str = Field(..., description="Caminho para o arquivo de imagem")
    target_count: int = Field(25, description="Número desejado de palavras")
    cefr_level: str = Field("A2", description="Nível CEFR (A1-C2)")


class ObjectDetectionInput(BaseModel):
    """Input schema para tool de detecção de objetos."""
    image_path: str = Field(..., description="Caminho para o arquivo de imagem")


class MCPImageAnalysisTool(BaseTool):
    """LangChain tool para análise de imagem via MCP."""
    
    name = "mcp_image_analysis"
    description = "Analyze image for educational content creation using MCP server"
    args_schema = ImageAnalysisInput
    
    def __init__(self):
        super().__init__()
        self.client = MCPImageAnalysisClient()
    
    async def _arun(self, image_path: str, context: str = "", cefr_level: str = "A2", unit_type: str = "lexical_unit") -> str:
        """Async implementation."""
        try:
            # Conectar se necessário
            if not self.client.is_connected:
                await self.client.connect()
            
            # Converter imagem para base64
            image_data = ImageToBase64Converter.from_file_path(image_path)
            
            # Fazer análise
            result = await self.client.analyze_image(
                image_data=image_data,
                context=context,
                cefr_level=cefr_level,
                unit_type=unit_type
            )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Erro na análise de imagem: {str(e)}"
    
    def _run(self, image_path: str, context: str = "", cefr_level: str = "A2", unit_type: str = "lexical_unit") -> str:
        """Sync implementation."""
        import asyncio
        return asyncio.run(self._arun(image_path, context, cefr_level, unit_type))


class MCPVocabularySuggestionTool(BaseTool):
    """LangChain tool para sugestão de vocabulário via MCP."""
    
    name = "mcp_vocabulary_suggestion"
    description = "Suggest vocabulary words based on image content using MCP server"
    args_schema = VocabularySuggestionInput
    
    def __init__(self):
        super().__init__()
        self.client = MCPImageAnalysisClient()
    
    async def _arun(self, image_path: str, target_count: int = 25, cefr_level: str = "A2") -> str:
        """Async implementation."""
        try:
            if not self.client.is_connected:
                await self.client.connect()
            
            image_data = ImageToBase64Converter.from_file_path(image_path)
            
            result = await self.client.suggest_vocabulary(
                image_data=image_data,
                target_count=target_count,
                cefr_level=cefr_level
            )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Erro na sugestão de vocabulário: {str(e)}"
    
    def _run(self, image_path: str, target_count: int = 25, cefr_level: str = "A2") -> str:
        """Sync implementation."""
        import asyncio
        return asyncio.run(self._arun(image_path, target_count, cefr_level))


class MCPObjectDetectionTool(BaseTool):
    """LangChain tool para detecção de objetos via MCP."""
    
    name = "mcp_object_detection"
    description = "Detect objects and analyze scenes in image using MCP server"
    args_schema = ObjectDetectionInput
    
    def __init__(self):
        super().__init__()
        self.client = MCPImageAnalysisClient()
    
    async def _arun(self, image_path: str) -> str:
        """Async implementation."""
        try:
            if not self.client.is_connected:
                await self.client.connect()
            
            image_data = ImageToBase64Converter.from_file_path(image_path)
            
            result = await self.client.detect_objects(image_data=image_data)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Erro na detecção de objetos: {str(e)}"
    
    def _run(self, image_path: str) -> str:
        """Sync implementation."""
        import asyncio
        return asyncio.run(self._arun(image_path))


# Service class para integração fácil
class MCPImageService:
    """Serviço principal para análise de imagens via MCP."""
    
    def __init__(self):
        self.client = MCPImageAnalysisClient()
        self.converter = ImageToBase64Converter()
    
    async def __aenter__(self):
        """Context manager async entry."""
        await self.client.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager async exit."""
        await self.client.disconnect()
    
    async def analyze_uploaded_images(
        self,
        image_files: List[str],
        context: str = "",
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit"
    ) -> List[Dict[str, Any]]:
        """
        Analisar múltiplas imagens carregadas.
        
        Args:
            image_files: Lista de caminhos para arquivos de imagem
            context: Contexto educacional
            cefr_level: Nível CEFR
            unit_type: Tipo de unidade
            
        Returns:
            Lista de análises das imagens
        """
        results = []
        
        for i, image_file in enumerate(image_files):
            try:
                logger.info(f"📸 Analisando imagem {i+1}/{len(image_files)}: {image_file}")
                
                # Converter para base64
                image_data = self.converter.from_file_path(image_file)
                
                # Fazer análise
                analysis = await self.client.analyze_image(
                    image_data=image_data,
                    context=context,
                    cefr_level=cefr_level,
                    unit_type=unit_type
                )
                
                # Adicionar metadados
                analysis["image_info"] = {
                    "filename": os.path.basename(image_file),
                    "filepath": image_file,
                    "sequence": i + 1
                }
                
                results.append(analysis)
                
            except Exception as e:
                logger.error(f"❌ Erro ao analisar {image_file}: {str(e)}")
                results.append({
                    "error": str(e),
                    "image_info": {
                        "filename": os.path.basename(image_file),
                        "filepath": image_file,
                        "sequence": i + 1
                    }
                })
        
        return results
    
    async def generate_vocabulary_from_images(
        self,
        image_files: List[str],
        total_target_words: int = 25,
        cefr_level: str = "A2"
    ) -> Dict[str, Any]:
        """
        Gerar vocabulário consolidado de múltiplas imagens.
        
        Args:
            image_files: Lista de caminhos para imagens
            total_target_words: Total de palavras desejadas
            cefr_level: Nível CEFR
            
        Returns:
            Vocabulário consolidado e deduplicado
        """
        all_vocabulary = []
        words_per_image = max(1, total_target_words // len(image_files))
        
        for image_file in image_files:
            try:
                image_data = self.converter.from_file_path(image_file)
                
                vocabulary = await self.client.suggest_vocabulary(
                    image_data=image_data,
                    target_count=words_per_image,
                    cefr_level=cefr_level
                )
                
                # Adicionar fonte da imagem
                for word_item in vocabulary:
                    word_item["source_image"] = os.path.basename(image_file)
                
                all_vocabulary.extend(vocabulary)
                
            except Exception as e:
                logger.warning(f"Erro ao processar {image_file}: {str(e)}")
        
        # Deduplicar vocabulário
        seen_words = set()
        unique_vocabulary = []
        
        for word_item in all_vocabulary:
            word = word_item.get("word", "").lower()
            if word and word not in seen_words:
                seen_words.add(word)
                unique_vocabulary.append(word_item)
        
        # Ordenar por relevância se disponível
        unique_vocabulary.sort(
            key=lambda x: x.get("relevance_score", 5), 
            reverse=True
        )
        
        # Limitar ao número alvo
        final_vocabulary = unique_vocabulary[:total_target_words]
        
        return {
            "vocabulary": final_vocabulary,
            "total_words": len(final_vocabulary),
            "target_words": total_target_words,
            "source_images": [os.path.basename(f) for f in image_files],
            "deduplication_stats": {
                "original_count": len(all_vocabulary),
                "unique_count": len(unique_vocabulary),
                "final_count": len(final_vocabulary)
            },
            "cefr_level": cefr_level,
            "generated_at": datetime.now().isoformat()
        }


# Função de conveniência para uso direto
async def analyze_images_for_unit(
    image_files: List[str],
    context: str = "",
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> Dict[str, Any]:
    """
    Função de conveniência para analisar imagens para uma unidade.
    
    Args:
        image_files: Lista de arquivos de imagem
        context: Contexto educacional
        cefr_level: Nível CEFR
        unit_type: Tipo de unidade
        
    Returns:
        Análise completa das imagens
    """
    async with MCPImageService() as service:
        # Fazer análises individuais
        analyses = await service.analyze_uploaded_images(
            image_files=image_files,
            context=context,
            cefr_level=cefr_level,
            unit_type=unit_type
        )
        
        # Gerar vocabulário consolidado
        vocabulary_result = await service.generate_vocabulary_from_images(
            image_files=image_files,
            total_target_words=25,
            cefr_level=cefr_level
        )
        
        return {
            "individual_analyses": analyses,
            "consolidated_vocabulary": vocabulary_result,
            "summary": {
                "total_images": len(image_files),
                "successful_analyses": len([a for a in analyses if "error" not in a]),
                "total_vocabulary_suggested": vocabulary_result["total_words"],
                "context": context,
                "cefr_level": cefr_level,
                "unit_type": unit_type
            }
        }


# Export das classes e funções principais
__all__ = [
    "MCPImageAnalysisClient",
    "MCPImageService", 
    "ImageToBase64Converter",
    "MCPImageAnalysisTool",
    "MCPVocabularySuggestionTool", 
    "MCPObjectDetectionTool",
    "analyze_images_for_unit"
]