# src/mcp/mcp_image_client.py - VERSÃO SIMPLES
"""
Cliente MCP para integração com o Image Analysis Server
Implementação simplificada usando o SDK oficial
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPImageAnalysisClient:
    """Cliente simples para comunicação com o MCP Image Analysis Server."""
    
    def __init__(self, server_path: str = None):
        """
        Args:
            server_path: Caminho para o servidor MCP
        """
        if server_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.server_path = str(project_root / "src" / "mcp" / "image_analysis_server.py")
        else:
            self.server_path = server_path
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chamar uma tool do servidor MCP.
        
        Args:
            tool_name: Nome da tool
            arguments: Argumentos para a tool
            
        Returns:
            Resultado da tool parseado como JSON
        """
        # Configurar parâmetros do servidor
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_path]
        )
        
        try:
            # Conectar ao servidor
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Chamar tool
                    result = await session.call_tool(tool_name, arguments)
                    
                    # Processar resultado
                    if result.content and hasattr(result.content[0], 'text'):
                        response_text = result.content[0].text
                        return json.loads(response_text)
                    else:
                        return {"error": "Empty response from server"}
                        
        except Exception as e:
            logger.error(f"Erro ao chamar tool {tool_name}: {str(e)}")
            return {"error": str(e)}
    
    async def analyze_image(
        self,
        image_data: str,
        context: str = "",
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit"
    ) -> Dict[str, Any]:
        """Analisar imagem para contexto educacional."""
        return await self.call_tool("analyze_image", {
            "image_data": image_data,
            "context": context,
            "cefr_level": cefr_level,
            "unit_type": unit_type
        })
    
    async def suggest_vocabulary(
        self,
        image_data: str,
        target_count: int = 25,
        cefr_level: str = "A2"
    ) -> List[Dict[str, Any]]:
        """Sugerir vocabulário baseado na imagem."""
        result = await self.call_tool("suggest_vocabulary", {
            "image_data": image_data,
            "target_count": target_count,
            "cefr_level": cefr_level
        })
        
        if result.get("success"):
            return result.get("vocabulary", [])
        else:
            logger.warning(f"Erro na sugestão de vocabulário: {result.get('error')}")
            return []
    
    async def detect_objects(self, image_data: str) -> Dict[str, Any]:
        """Detectar objetos e cenas na imagem."""
        result = await self.call_tool("detect_objects", {
            "image_data": image_data
        })
        
        if result.get("success"):
            return result.get("detection", {})
        else:
            logger.warning(f"Erro na detecção de objetos: {result.get('error')}")
            return {}


class MCPImageService:
    """Serviço principal para análise de imagens via MCP."""
    
    def __init__(self):
        self.client = MCPImageAnalysisClient()
    
    async def analyze_uploaded_images_for_unit(
        self,
        image_files_b64: List[str],
        context: str = "",
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit"
    ) -> Dict[str, Any]:
        """
        Analisar múltiplas imagens e consolidar vocabulário.
        
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
                    target_count=15,  # Menos por imagem
                    cefr_level=cefr_level
                )
                
                # Adicionar vocabulário à análise
                if analysis.get("success"):
                    analysis["vocabulary_suggestions"] = vocabulary
                    analysis["image_sequence"] = i + 1
                    analyses.append(analysis)
                    all_vocabulary.extend(vocabulary)
                else:
                    analyses.append({
                        "error": analysis.get("error", "Unknown error"),
                        "image_sequence": i + 1
                    })
                
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
            if isinstance(word_item, dict):
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


# Função de conveniência para uso nos endpoints V2 (compatibilidade total)
async def analyze_images_for_unit_creation(
    image_files_b64: List[str],
    context: str = "",
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> Dict[str, Any]:
    """
    Função específica para análise de imagens durante criação de unidades.
    MANTÉM A MESMA ASSINATURA da versão anterior para compatibilidade.
    
    Args:
        image_files_b64: Lista de imagens em base64
        context: Contexto educacional
        cefr_level: Nível CEFR
        unit_type: Tipo de unidade
        
    Returns:
        Análise pronta para integração com API V2
    """
    try:
        service = MCPImageService()
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


# Exemplo de uso direto
async def example_usage():
    """Exemplo de como usar o cliente."""
    
    # Exemplo com imagens fake (você usaria imagens reais em base64)
    fake_images = ["fake_base64_image_1", "fake_base64_image_2"]
    
    result = await analyze_images_for_unit_creation(
        image_files_b64=fake_images,
        context="Hotel reservation and check-in procedures",
        cefr_level="A2",
        unit_type="lexical_unit"
    )
    
    if result.get("success"):
        vocabulary = result["consolidated_vocabulary"]["vocabulary"]
        print(f"✅ Encontrou {len(vocabulary)} palavras:")
        for word_item in vocabulary[:5]:  # Mostrar apenas 5
            print(f"  - {word_item.get('word')}: {word_item.get('definition')}")
    else:
        print(f"❌ Erro: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(example_usage())