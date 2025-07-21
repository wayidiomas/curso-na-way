# src/mcp/image_analysis_server.py - VERSÃO SIMPLES COM FASTMCP
"""
MCP Server para análise de imagens com OpenAI Vision API
Implementação simplificada usando FastMCP
"""

import os
import json
from datetime import datetime
from openai import AsyncOpenAI
from mcp.server.fastmcp import FastMCP

# Criar servidor MCP
mcp = FastMCP("IVO-Image-Analysis-Server")

# Cliente OpenAI global
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@mcp.tool()
async def analyze_image(
    image_data: str,
    context: str = "",
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> str:
    """
    Analyze image for educational content creation.
    
    Args:
        image_data: Base64 encoded image data
        context: Educational context for the image
        cefr_level: CEFR level (A1, A2, B1, B2, C1, C2)
        unit_type: Unit type (lexical_unit or grammar_unit)
    
    Returns:
        JSON string with analysis results
    """
    
    educational_prompt = f"""
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

3. OBJECTS AND SCENES:
   - List all visible objects, people, actions
   - Describe the setting and atmosphere

Return as JSON:
{{
  "vocabulary_suggestions": [
    {{
      "word": "example",
      "phoneme": "/ɪɡˈzæmpəl/",
      "definition": "exemplo",
      "example": "This is an example sentence.",
      "word_class": "noun",
      "relevance_score": 9
    }}
  ],
  "contextual_themes": ["theme1", "theme2"],
  "objects_and_scenes": ["object1", "object2"],
  "educational_opportunities": ["opportunity1", "opportunity2"]
}}
    """
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": educational_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "high"
                        }
                    }
                ]
            }],
            max_tokens=1500,
            temperature=0.7
        )
        
        analysis_text = response.choices[0].message.content
        
        # Tentar parsear como JSON, senão retornar texto
        try:
            analysis_json = json.loads(analysis_text)
            result = {
                "success": True,
                "analysis": {
                    "structured_data": analysis_json,
                    "raw_analysis": analysis_text,
                    "educational_context": {
                        "cefr_level": cefr_level,
                        "unit_type": unit_type,
                        "provided_context": context
                    }
                },
                "metadata": {
                    "model_used": "gpt-4o-mini",
                    "analysis_timestamp": datetime.now().isoformat(),
                    "tokens_used": response.usage.total_tokens
                }
            }
        except json.JSONDecodeError:
            result = {
                "success": True,
                "analysis": {
                    "raw_analysis": analysis_text,
                    "structured_data": {},
                    "parsing_note": "Could not parse as JSON"
                }
            }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })


@mcp.tool()
async def suggest_vocabulary(
    image_data: str,
    target_count: int = 25,
    cefr_level: str = "A2"
) -> str:
    """
    Suggest vocabulary based on image content.
    
    Args:
        image_data: Base64 encoded image data
        target_count: Target number of vocabulary words
        cefr_level: CEFR level for vocabulary
    
    Returns:
        JSON string with vocabulary suggestions
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

Return as JSON array:
[
  {{
    "word": "example",
    "phoneme": "/ɪɡˈzæmpəl/",
    "definition": "exemplo",
    "example": "This is an example sentence.",
    "word_class": "noun",
    "relevance_score": 9
  }}
]
    """
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "high"
                        }
                    }
                ]
            }],
            max_tokens=2000,
            temperature=0.5
        )
        
        vocabulary_text = response.choices[0].message.content
        
        # Tentar parsear como JSON
        try:
            vocabulary_list = json.loads(vocabulary_text)
            if isinstance(vocabulary_list, list):
                result = {
                    "success": True,
                    "vocabulary": vocabulary_list,
                    "count": len(vocabulary_list),
                    "tool": "suggest_vocabulary",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                result = {
                    "success": False,
                    "error": "Response is not a list",
                    "raw_response": vocabulary_text
                }
        except json.JSONDecodeError:
            result = {
                "success": False,
                "error": "Could not parse JSON",
                "raw_response": vocabulary_text,
                "note": "Manual parsing required"
            }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })


@mcp.tool()
async def detect_objects(image_data: str) -> str:
    """
    Detect objects and analyze scenes in image.
    
    Args:
        image_data: Base64 encoded image data
    
    Returns:
        JSON string with detection results
    """
    
    prompt = """
Analyze this image and provide a detailed breakdown:

1. OBJECTS: List all distinct objects you can see
2. PEOPLE: Describe any people (number, age, actions, clothing)
3. SETTING: Describe the location/environment
4. ACTIONS: What activities/actions are happening
5. ATMOSPHERE: Mood, time of day, weather if visible
6. TEXT: Any visible text or signs
7. EDUCATIONAL_CONTEXT: How this image could be used for English learning

Return as JSON:
{
  "objects": ["object1", "object2"],
  "people": ["description1", "description2"],
  "setting": "location description",
  "actions": ["action1", "action2"],
  "atmosphere": "mood/time description",
  "text_detected": ["text1", "text2"],
  "educational_context": ["use1", "use2"]
}
    """
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "high"
                        }
                    }
                ]
            }],
            max_tokens=1000,
            temperature=0.6
        )
        
        detection_text = response.choices[0].message.content
        
        # Tentar parsear como JSON
        try:
            detection_json = json.loads(detection_text)
            result = {
                "success": True,
                "detection": {
                    "structured_data": detection_json,
                    "raw_text": detection_text
                },
                "tool": "detect_objects",
                "timestamp": datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            result = {
                "success": True,
                "detection": {
                    "raw_text": detection_text,
                    "parsing_note": "Could not parse as JSON"
                },
                "tool": "detect_objects",
                "timestamp": datetime.now().isoformat()
            }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })


# Entry point para o servidor MCP
if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable is required")
        exit(1)
    
    print("🚀 Iniciando IVO Image Analysis MCP Server...")
    print("Available tools: analyze_image, suggest_vocabulary, detect_objects")
    
    # Rodar servidor
    mcp.run()