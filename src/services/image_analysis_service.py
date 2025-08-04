# src/services/image_analysis_service.py
"""
Service de Análise de Imagens para IVO V2.
Migrado de src/mcp/ para integração direta como service.

MIGRAÇÃO MCP → SERVICE:
- Substituição do MCP Server por LangChain 0.3 direto
- Integração com OpenAI Vision API via ChatOpenAI
- Compatibilidade total com função analyze_images_for_unit_creation()
- Seguindo padrão de outros services (tips_generator.py)

Responsabilidades:
- Analisar imagens via OpenAI Vision API
- Extrair vocabulário contextual para unidades
- Gerar sugestões baseadas em contexto pedagógico
- Integração direta com vocabulary_generator
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

# LangChain 0.3 - Imports diretos (SEM MCP)
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Imports do projeto
from src.core.enums import CEFRLevel, LanguageVariant
from config.models import get_openai_config

logger = logging.getLogger(__name__)


class ImageAnalysisService:
    """
    Service para análise de imagens educacionais.
    
    MIGRADO DE MCP: Funcionalidade transferida do MCP Server para service integrado.
    USA LANGCHAIN 0.3: Comunicação direta com OpenAI via ChatOpenAI.
    """
    
    def __init__(self):
        """Inicializar service seguindo padrão dos outros services."""
        # Configurações (seguindo padrão tips_generator)
        self.openai_config = get_openai_config()
        
        # LangChain ChatOpenAI (substitui cliente MCP)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  # Modelo com vision
            temperature=0.3,      # Análise mais determinística
            max_tokens=1500,      # Espaço para análise detalhada
            timeout=60,
            max_retries=3,
            api_key=self.openai_config.openai_api_key
        )
        
        # Cache em memória (seguindo padrão)
        self._memory_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, float] = {}
        
        logger.info("✅ ImageAnalysisService inicializado (migrado de MCP)")
    
    async def analyze_images_for_vocabulary(
        self, 
        image_files_b64: List[str],
        context: str,
        cefr_level: str = "A2",
        unit_type: str = "lexical_unit",
        target_count: int = 25
    ) -> Dict[str, Any]:
        """
        MÉTODO PRINCIPAL - Analisar imagens e extrair vocabulário.
        
        MIGRADO DE MCP: Funcionalidade equivalente ao antigo MCP Server.
        COMPATIBILIDADE: Mantém mesma assinatura para código existente.
        
        Args:
            image_files_b64: Lista de imagens em base64
            context: Contexto da unidade (ex: "Hotel reservations")
            cefr_level: Nível CEFR
            unit_type: Tipo da unidade
            target_count: Número alvo de palavras
            
        Returns:
            Dict com vocabulário estruturado + metadados
        """
        try:
            start_time = time.time()
            
            # 1. Validação de entrada (seguindo padrão)
            self._validate_analysis_params(image_files_b64, context, cefr_level)
            
            logger.info(f"🖼️ Analisando {len(image_files_b64)} imagens para contexto: {context}")
            
            # 2. Processar cada imagem usando LangChain
            all_vocabulary = []
            for i, image_data in enumerate(image_files_b64):
                vocab_from_image = await self._analyze_single_image_langchain(
                    image_data, context, cefr_level, target_count
                )
                all_vocabulary.extend(vocab_from_image)
                logger.info(f"✅ Imagem {i+1}/{len(image_files_b64)}: {len(vocab_from_image)} palavras")
            
            # 3. Consolidar e deduplicate
            consolidated_vocab = self._consolidate_vocabulary(all_vocabulary, target_count)
            
            # 4. Estruturar resposta (compatível com código existente)
            result = {
                "success": True,
                "consolidated_vocabulary": {
                    "vocabulary": consolidated_vocab
                },
                "statistics": {
                    "images_processed": len(image_files_b64),
                    "total_words_found": len(all_vocabulary),
                    "final_vocabulary_count": len(consolidated_vocab),
                    "processing_time": time.time() - start_time
                },
                "migration_info": {
                    "migrated_from": "MCP Server",
                    "now_using": "LangChain 0.3 + ChatOpenAI",
                    "direct_integration": True
                }
            }
            
            logger.info(f"✅ Análise concluída: {len(consolidated_vocab)} palavras em {result['statistics']['processing_time']:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de imagens: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "consolidated_vocabulary": {"vocabulary": []}
            }
    
    async def _analyze_single_image_langchain(
        self, 
        image_data: str, 
        context: str, 
        cefr_level: str,
        target_count: int
    ) -> List[Dict[str, Any]]:
        """
        Analisar uma única imagem usando LangChain diretamente.
        
        MIGRADO DE MCP: Substitui chamada MCP por LangChain direto.
        """
        try:
            # Construir prompt especializado para educação
            prompt_messages = self._build_analysis_prompt_langchain(
                context, cefr_level, target_count
            )
            
            # Adicionar imagem ao prompt (LangChain 0.3 format)
            human_content = [
                {"type": "text", "text": f"Analyze this image for the context: {context}"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                }
            ]
            
            # Criar mensagem com imagem
            human_message = HumanMessage(content=human_content)
            messages = prompt_messages + [human_message]
            
            # LANGCHAIN 0.3: Usar ainvoke diretamente
            response = await self.llm.ainvoke(messages)
            content = response.content
            
            # Parse da resposta
            vocabulary = self._parse_vocabulary_response(content)
            
            return vocabulary
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar imagem individual: {str(e)}")
            return []
    
    def _build_analysis_prompt_langchain(
        self, 
        context: str, 
        cefr_level: str, 
        target_count: int
    ) -> List[Any]:
        """Construir prompt otimizado para análise educacional com LangChain."""
        
        system_prompt = f"""You are an expert English vocabulary teacher analyzing images for educational content creation.

EDUCATIONAL CONTEXT:
- Teaching Context: {context}
- CEFR Level: {cefr_level}
- Target Vocabulary: {target_count // 2} words per image (will be combined with other images)

ANALYSIS REQUIREMENTS:
1. Identify objects, people, actions, and settings visible in the image
2. Focus on vocabulary appropriate for {cefr_level} level
3. Prioritize practical, communicative vocabulary for "{context}"
4. Include IPA phonetic transcriptions
5. Provide Portuguese definitions for Brazilian learners
6. Rate relevance to context (1-10 scale)

VOCABULARY SELECTION CRITERIA for {cefr_level}:
- Nouns: Concrete objects and people visible
- Verbs: Actions happening or implied
- Adjectives: Descriptive words for visible elements
- Avoid overly complex or technical terms
- Focus on high-frequency, useful words

OUTPUT FORMAT: Return valid JSON array:
[
  {{
    "word": "example",
    "phoneme": "/ɪɡˈzæmpəl/",
    "definition": "exemplo, modelo",
    "example": "This is a good example of {context}.",
    "word_class": "noun",
    "relevance_score": 9
  }}
]

Analyze the image and generate appropriate vocabulary for the educational context."""

        return [SystemMessage(content=system_prompt)]
    
    def _parse_vocabulary_response(self, content: str) -> List[Dict[str, Any]]:
        """Parse da resposta do LLM (migrado de MCP)."""
        try:
            # Limpar resposta se necessário (mesmo processo do MCP)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            vocabulary_list = json.loads(content)
            
            if isinstance(vocabulary_list, list):
                return vocabulary_list
            else:
                logger.warning("⚠️ Resposta não é lista, retornando vazia")
                return []
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Erro ao parsear JSON: {str(e)}")
            return self._extract_vocabulary_from_text(content)
        except Exception as e:
            logger.error(f"❌ Erro no parse: {str(e)}")
            return []
    
    def _extract_vocabulary_from_text(self, content: str) -> List[Dict[str, Any]]:
        """Extract vocabulary quando JSON parsing falha (migrado de MCP)."""
        vocabulary = []
        lines = content.split('\n')
        
        current_item = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Parser simples para extrair informações básicas
            if any(word in line.lower() for word in ['word:', '"word"']):
                if current_item:
                    vocabulary.append(current_item)
                    current_item = {}
                word = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['word'] = word
            elif any(word in line.lower() for word in ['phoneme:', '"phoneme"']):
                phoneme = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['phoneme'] = phoneme
            elif any(word in line.lower() for word in ['definition:', '"definition"']):
                definition = line.split(':')[-1].strip().strip('"').strip(',')
                current_item['definition'] = definition
        
        if current_item:
            vocabulary.append(current_item)
        
        # Preencher campos faltantes
        for item in vocabulary:
            item.setdefault('word_class', 'noun')
            item.setdefault('relevance_score', 7)
            item.setdefault('example', f"This is an example with {item.get('word', 'word')}.")
        
        return vocabulary
    
    def _consolidate_vocabulary(self, all_vocab: List[Dict], target_count: int) -> List[Dict[str, Any]]:
        """Consolidar e deduplicate vocabulário (migrado de MCP)."""
        # Deduplicação por palavra
        seen_words = set()
        unique_vocabulary = []
        
        for word_item in all_vocab:
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
        
        # Limitar ao número alvo
        return unique_vocabulary[:target_count]
    
    def _validate_analysis_params(self, images: List[str], context: str, cefr_level: str) -> None:
        """Validação de parâmetros (seguindo padrão services)."""
        if not images:
            raise ValueError("Lista de imagens não pode estar vazia")
        if not context.strip():
            raise ValueError("Contexto é obrigatório")
        if cefr_level not in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            raise ValueError(f"Nível CEFR inválido: {cefr_level}")
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Status do service (seguindo padrão)."""
        return {
            "service": "ImageAnalysisService",
            "status": "active",
            "migration_status": "completed",
            "migrated_from": "MCP Server",
            "now_using": "LangChain 0.3 + ChatOpenAI",
            "llm_model": "gpt-4o-mini",
            "direct_integration": True,
            "supports_base64_images": True,
            "max_images_per_request": 5
        }


# =============================================================================
# FUNÇÃO DE COMPATIBILIDADE (MANTÉM ASSINATURA ORIGINAL)
# =============================================================================

async def analyze_images_for_unit_creation(
    image_files_b64: List[str],
    context: str = "",
    cefr_level: str = "A2",
    unit_type: str = "lexical_unit"
) -> Dict[str, Any]:
    """
    Função de compatibilidade para manter código existente funcionando.
    
    MANTÉM COMPATIBILIDADE: Mesma assinatura que o antigo MCP.
    MIGRAÇÃO TRANSPARENTE: Código existente continua funcionando sem mudanças.
    """
    try:
        service = ImageAnalysisService()
        result = await service.analyze_images_for_vocabulary(
            image_files_b64, context, cefr_level, unit_type
        )
        
        logger.info("✅ Análise via service integrado (migrado de MCP)")
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro na análise de imagens: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "consolidated_vocabulary": {"vocabulary": []},
            "migration_note": "Error occurred in migrated service (formerly MCP)"
        }


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

async def test_migrated_service():
    """Teste para validar migração MCP → Service."""
    
    # Simular imagens em base64
    fake_images = ["fake_base64_image_1", "fake_base64_image_2"]
    
    # Usar função de compatibilidade (como código existente)
    result = await analyze_images_for_unit_creation(
        image_files_b64=fake_images,
        context="Hotel reservation and check-in procedures",
        cefr_level="A2",
        unit_type="lexical_unit"
    )
    
    if result.get("success"):
        vocabulary = result["consolidated_vocabulary"]["vocabulary"]
        print(f"✅ Migração bem-sucedida: {len(vocabulary)} palavras extraídas")
        print(f"📊 Estatísticas: {result.get('statistics', {})}")
        print(f"🔄 Info migração: {result.get('migration_info', {})}")
    else:
        print(f"❌ Erro na migração: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_migrated_service())