# src/mcp/image_analysis_server.py
"""
MCP Server para análise de imagens com OpenAI Vision API
Implementação do PROMPT 3 do IVO V2 Guide
"""

import asyncio
import base64
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from mcp import McpServer, McpSession, create_stdio_session
from mcp.types import (
    Tool, CallToolRequest, CallToolResult, TextContent, ImageContent,
    Resource, ReadResourceRequest, ReadResourceResult
)
from openai import AsyncOpenAI
from PIL import Image
import io

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageAnalysisServer:
    """Servidor MCP para análise de imagens educacionais usando OpenAI Vision."""
    
    def __init__(self):
        self.openai_client = None
        self.cache = {}  # Cache simples para análises
        
        # Configurações do servidor
        self.server_name = "IVO-Image-Analysis-Server"
        self.server_version = "1.0.0"
        
        # Configurar cliente OpenAI
        self._setup_openai_client()
    
    def _setup_openai_client(self):
        """Configurar cliente OpenAI."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.openai_client = AsyncOpenAI(api_key=api_key)
        logger.info("✅ OpenAI client configured successfully")
    
    async def analyze_educational_image(
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
            context: Contexto educacional opcional
            cefr_level: Nível CEFR (A1-C2)
            unit_type: Tipo de unidade (lexical_unit/grammar_unit)
        
        Returns:
            Análise estruturada da imagem
        """
        try:
            # Criar prompt específico para análise educacional
            educational_prompt = self._create_educational_prompt(context, cefr_level, unit_type)
            
            # Fazer análise com OpenAI Vision
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo com visão
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": educational_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            # Processar resposta
            analysis_text = response.choices[0].message.content
            
            # Estruturar resultado
            analysis = {
                "raw_analysis": analysis_text,
                "structured_data": self._parse_analysis_response(analysis_text),
                "educational_context": {
                    "cefr_level": cefr_level,
                    "unit_type": unit_type,
                    "provided_context": context
                },
                "metadata": {
                    "model_used": "gpt-4o-mini",
                    "analysis_timestamp": datetime.now().isoformat(),
                    "tokens_used": response.usage.total_tokens
                }
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro na análise da imagem: {str(e)}")
            raise
    
    def _create_educational_prompt(self, context: str, cefr_level: str, unit_type: str) -> str:
        """Criar prompt específico para análise educacional."""
        
        base_prompt = f"""
You are an expert English teacher analyzing an image for creating educational content.

EDUCATIONAL CONTEXT:
- CEFR Level: {cefr_level}
- Unit Type: {unit_type}
- Additional Context: {context or "Not provided"}

ANALYSIS REQUIREMENTS:

1. VOCABULARY SUGGESTIONS (20-30 words):
   - Focus on {cefr_level} level vocabulary
   - Prioritize nouns, verbs, and adjectives visible in the image
   - Include phonetic transcription (IPA) for each word
   - Provide Portuguese definitions
   - Rate relevance to image context (1-10)

2. CONTEXTUAL THEMES:
   - Identify main themes/situations shown
   - Suggest real-life scenarios this could represent
   - Note cultural aspects if relevant

3. EDUCATIONAL OPPORTUNITIES:
   - Grammar points that could be taught using this image
   - Functional language opportunities (asking, describing, etc.)
   - Potential speaking/writing activities

4. OBJECTS AND SCENES:
   - List all visible objects, people, actions
   - Describe the setting and atmosphere
   - Note any text visible in the image

Please structure your response in clear sections for easy parsing.
        """
        
        if unit_type == "grammar_unit":
            base_prompt += """

GRAMMAR FOCUS:
Since this is a grammar unit, specifically identify:
- Verb tenses that could be practiced
- Sentence structures visible in the scene
- Prepositions of place/time opportunities
- Modal verbs contexts
            """
        else:  # lexical_unit
            base_prompt += """

LEXICAL FOCUS:
Since this is a lexical unit, specifically identify:
- Word families and collocations
- Compound nouns opportunities
- Phrasal verbs contexts
- Idiomatic expressions possibilities
            """
        
        return base_prompt.strip()
    
    def _parse_analysis_response(self, analysis_text: str) -> Dict[str, Any]:
        """Parsear resposta da análise em estrutura JSON."""
        try:
            # Estrutura básica que tentaremos extrair
            structured = {
                "vocabulary_suggestions": [],
                "contextual_themes": [],
                "educational_opportunities": [],
                "objects_and_scenes": [],
                "grammar_focus": [],
                "lexical_focus": []
            }
            
            # Esta é uma versão simplificada do parsing
            # Em uma implementação real, usaríamos NLP mais avançado ou structured output
            lines = analysis_text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detectar seções
                if "VOCABULARY" in line.upper():
                    current_section = "vocabulary_suggestions"
                elif "THEMES" in line.upper() or "CONTEXTUAL" in line.upper():
                    current_section = "contextual_themes"
                elif "EDUCATIONAL" in line.upper() or "OPPORTUNITIES" in line.upper():
                    current_section = "educational_opportunities"
                elif "OBJECTS" in line.upper() or "SCENES" in line.upper():
                    current_section = "objects_and_scenes"
                elif "GRAMMAR" in line.upper():
                    current_section = "grammar_focus"
                elif "LEXICAL" in line.upper():
                    current_section = "lexical_focus"
                elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                    # Item de lista
                    if current_section and current_section in structured:
                        structured[current_section].append(line[1:].strip())
            
            return structured
            
        except Exception as e:
            logger.warning(f"Erro no parsing da análise: {str(e)}")
            # Retornar análise como texto se parsing falhar
            return {
                "raw_text": analysis_text,
                "parsing_error": str(e)
            }
    
    async def suggest_vocabulary_from_image(
        self, 
        image_data: str, 
        target_count: int = 25,
        cefr_level: str = "A2"
    ) -> List[Dict[str, Any]]:
        """
        Sugerir vocabulário específico baseado na imagem.
        
        Args:
            image_data: Imagem em base64
            target_count: Número desejado de palavras
            cefr_level: Nível CEFR
        
        Returns:
            Lista de itens de vocabulário estruturados
        """
        
        prompt = f"""
Analyze this image and suggest exactly {target_count} English vocabulary words appropriate for {cefr_level} level.

For each word, provide:
1. English word
2. IPA phonetic transcription
3. Portuguese definition
4. Example sentence using the word
5. Word class (noun, verb, adjective, etc.)
6. Relevance score to image (1-10)

Focus on words that are:
- Clearly visible or strongly implied in the image
- Appropriate for {cefr_level} level students
- Useful for practical communication
- Representative of the scene/context shown

Format as JSON array with structure:
[
  {{
    "word": "example",
    "phoneme": "/ɪɡˈzæmpəl/",
    "definition": "exemplo",
    "example": "This is a good example.",
    "word_class": "noun",
    "relevance_score": 9,
    "context_relevance": "directly visible in image"
  }}
]
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.5
            )
            
            vocabulary_text = response.choices[0].message.content
            
            # Tentar parsear como JSON
            try:
                vocabulary_list = json.loads(vocabulary_text)
                if isinstance(vocabulary_list, list):
                    return vocabulary_list
            except json.JSONDecodeError:
                # Se não conseguir parsear JSON, extrair palavras manualmente
                return self._extract_vocabulary_from_text(vocabulary_text)
                
        except Exception as e:
            logger.error(f"Erro ao sugerir vocabulário: {str(e)}")
            return []
    
    def _extract_vocabulary_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extrair vocabulário de texto quando JSON parsing falha."""
        # Implementação simplificada - extrair informações básicas
        vocabulary = []
        lines = text.split('\n')
        
        current_word = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Tentar identificar padrões
            if line.startswith('"word"') or line.startswith('word:'):
                if current_word:
                    vocabulary.append(current_word)
                    current_word = {}
                # Extrair palavra
                word = line.split(':')[-1].strip().strip('"').strip(',')
                current_word['word'] = word
            elif 'phoneme' in line.lower() or 'ipa' in line.lower():
                phoneme = line.split(':')[-1].strip().strip('"').strip(',')
                current_word['phoneme'] = phoneme
            elif 'definition' in line.lower():
                definition = line.split(':')[-1].strip().strip('"').strip(',')
                current_word['definition'] = definition
        
        if current_word:
            vocabulary.append(current_word)
            
        return vocabulary
    
    async def detect_objects_and_scenes(self, image_data: str) -> Dict[str, Any]:
        """
        Detectar objetos e cenas na imagem.
        
        Args:
            image_data: Imagem em base64
        
        Returns:
            Informações sobre objetos e cenas detectados
        """
        
        prompt = """
Analyze this image and provide a detailed breakdown:

1. OBJECTS: List all distinct objects you can see
2. PEOPLE: Describe any people (number, age, actions, clothing)
3. SETTING: Describe the location/environment
4. ACTIONS: What activities/actions are happening
5. ATMOSPHERE: Mood, time of day, weather if visible
6. TEXT: Any visible text or signs
7. COLORS: Dominant colors in the image
8. EDUCATIONAL_CONTEXT: How this image could be used for English learning

Format as structured information for easy parsing.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.6
            )
            
            detection_text = response.choices[0].message.content
            
            return {
                "detection_text": detection_text,
                "processed_data": self._parse_detection_response(detection_text),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro na detecção de objetos: {str(e)}")
            return {"error": str(e)}
    
    def _parse_detection_response(self, text: str) -> Dict[str, List[str]]:
        """Parsear resposta de detecção em estrutura."""
        parsed = {
            "objects": [],
            "people": [],
            "setting": [],
            "actions": [],
            "atmosphere": [],
            "text_detected": [],
            "colors": [],
            "educational_context": []
        }
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detectar seções
            if "OBJECTS" in line.upper():
                current_section = "objects"
            elif "PEOPLE" in line.upper():
                current_section = "people"
            elif "SETTING" in line.upper():
                current_section = "setting"
            elif "ACTIONS" in line.upper():
                current_section = "actions"
            elif "ATMOSPHERE" in line.upper():
                current_section = "atmosphere"
            elif "TEXT" in line.upper():
                current_section = "text_detected"
            elif "COLORS" in line.upper():
                current_section = "colors"
            elif "EDUCATIONAL" in line.upper():
                current_section = "educational_context"
            elif line.startswith('-') or line.startswith('•'):
                if current_section and current_section in parsed:
                    parsed[current_section].append(line[1:].strip())
        
        return parsed


# Funções MCP Tools
async def analyze_image_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Tool MCP para análise completa de imagem."""
    try:
        image_data = arguments.get("image_data")
        context = arguments.get("context", "")
        cefr_level = arguments.get("cefr_level", "A2")
        unit_type = arguments.get("unit_type", "lexical_unit")
        
        if not image_data:
            return {"error": "image_data is required"}
        
        # Criar instância do servidor
        server = ImageAnalysisServer()
        
        # Fazer análise
        analysis = await server.analyze_educational_image(
            image_data=image_data,
            context=context,
            cefr_level=cefr_level,
            unit_type=unit_type
        )
        
        return {
            "success": True,
            "analysis": analysis,
            "tool": "analyze_image",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro na tool analyze_image: {str(e)}")
        return {"error": str(e)}


async def suggest_vocabulary_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Tool MCP para sugestão de vocabulário."""
    try:
        image_data = arguments.get("image_data")
        target_count = arguments.get("target_count", 25)
        cefr_level = arguments.get("cefr_level", "A2")
        
        if not image_data:
            return {"error": "image_data is required"}
        
        server = ImageAnalysisServer()
        vocabulary = await server.suggest_vocabulary_from_image(
            image_data=image_data,
            target_count=target_count,
            cefr_level=cefr_level
        )
        
        return {
            "success": True,
            "vocabulary": vocabulary,
            "count": len(vocabulary),
            "tool": "suggest_vocabulary",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro na tool suggest_vocabulary: {str(e)}")
        return {"error": str(e)}


async def detect_objects_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Tool MCP para detecção de objetos."""
    try:
        image_data = arguments.get("image_data")
        
        if not image_data:
            return {"error": "image_data is required"}
        
        server = ImageAnalysisServer()
        detection = await server.detect_objects_and_scenes(image_data)
        
        return {
            "success": True,
            "detection": detection,
            "tool": "detect_objects",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro na tool detect_objects: {str(e)}")
        return {"error": str(e)}


# Configuração do servidor MCP
def create_mcp_server() -> McpServer:
    """Criar e configurar servidor MCP."""
    
    server = McpServer("ivo-image-analysis")
    
    # Registrar tools
    @server.call_tool()
    async def analyze_image(arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze image for educational context."""
        result = await analyze_image_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    @server.call_tool()
    async def suggest_vocabulary(arguments: Dict[str, Any]) -> List[TextContent]:
        """Suggest vocabulary based on image content."""
        result = await suggest_vocabulary_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    @server.call_tool()
    async def detect_objects(arguments: Dict[str, Any]) -> List[TextContent]:
        """Detect objects and scenes in image."""
        result = await detect_objects_tool(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    # Registrar tools no servidor
    server.list_tools = lambda: [
        Tool(
            name="analyze_image",
            description="Analyze image for educational content creation",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_data": {
                        "type": "string",
                        "description": "Base64 encoded image data"
                    },
                    "context": {
                        "type": "string",
                        "description": "Educational context for the image"
                    },
                    "cefr_level": {
                        "type": "string",
                        "description": "CEFR level (A1, A2, B1, B2, C1, C2)",
                        "default": "A2"
                    },
                    "unit_type": {
                        "type": "string",
                        "description": "Unit type (lexical_unit or grammar_unit)",
                        "default": "lexical_unit"
                    }
                },
                "required": ["image_data"]
            }
        ),
        Tool(
            name="suggest_vocabulary",
            description="Suggest vocabulary words based on image content",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_data": {
                        "type": "string",
                        "description": "Base64 encoded image data"
                    },
                    "target_count": {
                        "type": "integer",
                        "description": "Target number of vocabulary words",
                        "default": 25
                    },
                    "cefr_level": {
                        "type": "string",
                        "description": "CEFR level for vocabulary",
                        "default": "A2"
                    }
                },
                "required": ["image_data"]
            }
        ),
        Tool(
            name="detect_objects",
            description="Detect objects and analyze scenes in image",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_data": {
                        "type": "string",
                        "description": "Base64 encoded image data"
                    }
                },
                "required": ["image_data"]
            }
        )
    ]
    
    return server


# Entry point para o servidor MCP
async def main():
    """Main entry point para o servidor MCP."""
    try:
        logger.info("🚀 Iniciando IVO Image Analysis MCP Server...")
        
        # Verificar se OpenAI API key está configurada
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("❌ OPENAI_API_KEY environment variable is required")
            return
        
        # Criar servidor MCP
        server = create_mcp_server()
        
        # Criar sessão stdio
        session = await create_stdio_session(server)
        
        logger.info("✅ IVO Image Analysis MCP Server started successfully")
        logger.info("Available tools: analyze_image, suggest_vocabulary, detect_objects")
        
        # Manter servidor rodando
        await session.run()
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar servidor MCP: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())