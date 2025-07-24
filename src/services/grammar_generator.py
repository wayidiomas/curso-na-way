"""Gerador de conteúdo gramatical usando IA - LangChain 0.3."""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import asyncio
from dataclasses import dataclass

# YAML import
import yaml

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Pydantic 2 nativo - sem necessidade de compatibilidade
from pydantic import BaseModel, ValidationError, Field, ConfigDict

# Imports internos
from config.logging import get_logger
from config.models import get_openai_config, load_model_configs

# Logger configurado
logger = get_logger("grammar_generator")
logger.info("🚀 Usando LangChain 0.3 com Pydantic 2 nativo")


@dataclass
class GrammarContent:
    """Estrutura do conteúdo gramatical gerado."""
    grammar_point: str
    explanation: str
    examples: List[str]
    patterns: List[str]
    variant_notes: Optional[str] = None


class GrammarRequest(BaseModel):
    """Modelo de requisição para geração de gramática - Pydantic 2."""
    input_text: str = Field(..., description="Texto base para análise gramatical")
    vocabulary_list: List[str] = Field(..., description="Lista de vocabulário disponível") 
    level: str = Field(..., description="Nível CEFR (A1, A2, B1, B2, C1, C2)")
    variant: str = Field(default="american", description="Variante do inglês")

    # 🔥 Pydantic 2 - Nova sintaxe de configuração
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )


class GrammarGenerator:
    """Gerador de conteúdo gramatical contextual - LangChain 0.3."""
    
    def __init__(self):
        """Inicializar gerador com LangChain 0.3."""
        self.llm = None
        self.prompts = {}
        self._load_config()
        
    def _load_config(self):
        """Carregar configurações e prompts para LangChain 0.3."""
        try:
            # Configuração do modelo
            openai_config = get_openai_config()
            model_configs = load_model_configs()
            
            # Configurar ChatOpenAI para v0.3
            grammar_config = openai_config.get("content_configs", {}).get("gramatica_generation", {})
            
            # 🔧 Parâmetros para LangChain 0.3
            self.llm = ChatOpenAI(
                model=openai_config.get("model", "gpt-4-turbo-preview"),
                max_tokens=grammar_config.get("max_tokens", 3072), 
                temperature=grammar_config.get("temperature", 0.5),
                timeout=openai_config.get("timeout", 60),
                max_retries=openai_config.get("max_retries", 3),
                api_key=openai_config.get("api_key")  # LangChain 0.3 usa 'api_key' diretamente
            )
            
            logger.info(f"✅ ChatOpenAI v0.3 configurado: {openai_config.get('model')}")
            
            # Carregar prompts
            prompt_file = Path("config/prompts/gramatica_generation.yaml")
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    self.prompts = yaml.safe_load(f)
                logger.info("✅ Prompts carregados")
            else:
                # Prompts padrão otimizados para LangChain 0.3
                self.prompts = {
                    "system_prompt": """Você é um especialista em gramática inglesa usando metodologia moderna.
Sua tarefa é criar conteúdo gramatical estruturado e didático.

DIRETRIZES:
- Use linguagem clara e adaptada ao nível do aluno
- Forneça exemplos práticos e contextuais
- Mantenha foco pedagógico
- Seja preciso mas acessível""",
                    
                    "user_prompt": """CONTEXTO: {input_text}
VOCABULÁRIO DISPONÍVEL: {vocabulary_list}
NÍVEL DO ALUNO: {level}
VARIANTE: {variant}

TAREFA: Criar análise gramatical estruturada

FORMATO DE RESPOSTA:
1. PONTO GRAMATICAL: [identificar estrutura principal]
2. EXPLICAÇÃO: [regra clara e didática]
3. EXEMPLOS: [3-4 exemplos usando o vocabulário]
4. PADRÕES: [padrões de uso comum]
5. NOTAS VARIANTE: [diferenças {variant} se relevante]

Adapte tudo ao nível {level}."""
                }
                logger.warning("⚠️ Usando prompts padrão")
                
        except Exception as e:
            logger.error(f"❌ Erro na configuração: {e}")
            raise

    async def generate_grammar_content(self, request: GrammarRequest) -> GrammarContent:
        """
        Gerar conteúdo gramatical - LangChain 0.3 async nativo.
        
        Args:
            request: Dados da requisição validados pelo Pydantic 2
            
        Returns:
            GrammarContent: Conteúdo estruturado
        """
        try:
            logger.info(f"🎯 Gerando gramática {request.level} - LangChain 0.3")
            
            # Validação automática pelo Pydantic 2
            if not request.input_text.strip():
                raise ValueError("Texto de entrada vazio")
                
            # Preparar mensagens
            system_msg = SystemMessage(content=self.prompts["system_prompt"])
            user_msg = HumanMessage(content=self.prompts["user_prompt"].format(
                input_text=request.input_text,
                vocabulary_list=", ".join(request.vocabulary_list),
                level=request.level,
                variant=request.variant
            ))
            
            # 🚀 LangChain 0.3 - Método ainvoke moderno
            logger.debug("🔄 Invocando LLM com ainvoke (LangChain 0.3)")
            response = await self.llm.ainvoke([system_msg, user_msg])
            
            # Extrair conteúdo da resposta
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Processar resposta estruturada
            grammar_content = self._parse_grammar_response(content, request.level)
            
            logger.info("✅ Gramática gerada com sucesso")
            return grammar_content
            
        except ValidationError as e:
            logger.error(f"❌ Erro Pydantic 2: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro na geração: {e}")
            raise

    def _parse_grammar_response(self, content: str, level: str) -> GrammarContent:
        """
        Parser inteligente para resposta estruturada.
        
        Args:
            content: Resposta da IA
            level: Nível do conteúdo
            
        Returns:
            GrammarContent: Dados estruturados
        """
        try:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Inicializar campos
            grammar_point = ""
            explanation = ""
            examples = []
            patterns = []
            variant_notes = None
            
            current_section = None
            
            # Parsing contextual
            for line in lines:
                line_lower = line.lower()
                
                # Detectar seções por palavras-chave
                if any(kw in line_lower for kw in ["ponto gramatical", "grammar point", "estrutura:"]):
                    current_section = "point"
                    grammar_point = line.split(":", 1)[-1].strip() if ":" in line else line
                    
                elif any(kw in line_lower for kw in ["explicação", "explanation", "regra:"]):
                    current_section = "explanation"
                    if ":" in line:
                        explanation += line.split(":", 1)[-1].strip() + " "
                    
                elif any(kw in line_lower for kw in ["exemplos", "examples"]):
                    current_section = "examples"
                    
                elif any(kw in line_lower for kw in ["padrões", "patterns", "uso"]):
                    current_section = "patterns"
                    
                elif any(kw in line_lower for kw in ["notas", "variante", "diferenças"]):
                    current_section = "variant"
                    
                else:
                    # Adicionar conteúdo à seção atual
                    if current_section == "explanation" and not any(kw in line_lower for kw in ["exemplo", "padrão"]):
                        explanation += line + " "
                    elif current_section == "examples":
                        if line.startswith(("•", "-", "1.", "2.", "3.", "*")):
                            examples.append(line.lstrip("•-123456789.*• "))
                        elif len(line) > 20:  # Linha longa pode ser exemplo
                            examples.append(line)
                    elif current_section == "patterns":
                        if line.startswith(("•", "-", "1.", "2.", "3.", "*")):
                            patterns.append(line.lstrip("•-123456789.*• "))
                    elif current_section == "variant":
                        variant_notes = (variant_notes or "") + line + " "
            
            # Fallbacks inteligentes se parsing falhou
            if not grammar_point:
                # Tentar primeira linha significativa
                significant_lines = [l for l in lines if len(l) > 15]
                grammar_point = significant_lines[0] if significant_lines else "Análise Gramatical"
                
            if not explanation:
                # Usar primeiros parágrafos como explicação
                paragraphs = content.split('\n\n')
                explanation = paragraphs[0] if paragraphs else content[:200]
                
            if not examples:
                # Extrair sentenças como exemplos
                sentences = [s.strip() for s in content.replace('\n', ' ').split('.') 
                           if 15 < len(s.strip()) < 100]
                examples = sentences[:3] if sentences else ["Exemplo contextual aqui."]
                
            if not patterns:
                patterns = ["Padrão gramatical identificado no contexto"]
            
            # Limpar campos
            grammar_point = grammar_point.strip()[:100]  # Limitar tamanho
            explanation = explanation.strip()
            variant_notes = variant_notes.strip() if variant_notes else None
            
            return GrammarContent(
                grammar_point=grammar_point,
                explanation=explanation,
                examples=examples[:5],  # Máximo 5 exemplos
                patterns=patterns[:3],   # Máximo 3 padrões
                variant_notes=variant_notes
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no parsing, usando fallback: {e}")
            
            # Fallback robusto
            return GrammarContent(
                grammar_point="Estrutura Gramatical",
                explanation=content[:500].strip(),
                examples=[content.split('.')[0] + '.' if '.' in content else content[:100]],
                patterns=["Padrão identificado"],
                variant_notes=None
            )

    def format_for_output(self, grammar_content: GrammarContent) -> Dict[str, Any]:
        """Formatar para saída estruturada."""
        return {
            "type": "grammar",
            "grammar_point": grammar_content.grammar_point,
            "explanation": grammar_content.explanation,
            "examples": grammar_content.examples,
            "patterns": grammar_content.patterns,
            "variant_notes": grammar_content.variant_notes,
            "metadata": {
                "generated_at": "timestamp",
                "section": "grammar",
                "langchain_version": "0.3.x",
                "pydantic_version": "2.x"
            }
        }


# 🚀 Função utilitária moderna
async def generate_grammar(
    text: str, 
    vocabulary: List[str], 
    level: str = "B1", 
    variant: str = "american"
) -> Dict[str, Any]:
    """
    Função simplificada para gerar gramática com LangChain 0.3.
    
    Args:
        text: Texto base
        vocabulary: Lista de vocabulário
        level: Nível CEFR
        variant: Variante do inglês
        
    Returns:
        Dict: Conteúdo gramatical formatado
    """
    generator = GrammarGenerator()
    
    # Pydantic 2 - validação automática
    request = GrammarRequest(
        input_text=text,
        vocabulary_list=vocabulary,
        level=level,
        variant=variant
    )
    
    grammar_content = await generator.generate_grammar_content(request)
    return generator.format_for_output(grammar_content)


# Exemplo e teste para LangChain 0.3
if __name__ == "__main__":
    async def test_langchain_v03():
        """Testar LangChain 0.3 com Pydantic 2."""
        try:
            print("🧪 Testando LangChain 0.3 + Pydantic 2...")
            
            # Criar requisição com validação Pydantic 2
            request = GrammarRequest(
                input_text="The students are learning English grammar with modern technology.",
                vocabulary_list=["learn", "grammar", "technology", "student", "modern"],
                level="B2",
                variant="american"
            )
            
            print(f"✅ Requisição validada: {request.level}")
            
            # Testar geração
            generator = GrammarGenerator()
            result = await generator.generate_grammar_content(request)
            
            print("🎯 RESULTADO:")
            print(f"   Ponto: {result.grammar_point}")
            print(f"   Explicação: {result.explanation[:80]}...")
            print(f"   Exemplos: {len(result.examples)}")
            print(f"   Padrões: {len(result.patterns)}")
            
            print("🎉 LangChain 0.3 funcionando perfeitamente!")
            
        except Exception as e:
            print(f"❌ Erro no teste: {e}")
            print("💡 Verifique se OPENAI_API_KEY está configurada no .env")
    
    # Executar teste
    asyncio.run(test_langchain_v03())