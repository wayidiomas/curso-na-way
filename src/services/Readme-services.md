# 📦 Services Layer - IVO V2

> **Sistema de serviços hierárquicos com IA contextual para geração pedagógica Course → Book → Unit**

O diretório `services/` contém todos os serviços especializados do IVO V2 (Intelligent Vocabulary Organizer) que implementam a geração hierárquica de conteúdo pedagógico usando IA contextual, metodologias científicas estabelecidas e RAG (Retrieval Augmented Generation).

## 🏗️ Arquitetura Geral

### Padrão Arquitetural
- **LangChain 0.3** com método `ainvoke` para todas as consultas LLM
- **Pydantic 2** com sintaxe nativa (`model_config = ConfigDict`)
- **100% Análise via IA** para decisões contextuais complexas
- **Constantes técnicas mantidas** para padrões estabelecidos (CEFR, IPA, etc.)
- **RAG Hierárquico** com contexto Course → Book → Unit
- **Zero cache** conforme solicitação (todas as análises são contextuais)

### Hierarquia Pedagógica
```
📚 COURSE (Curso Completo)
├── 📖 BOOK (Módulo por Nível CEFR)
│   ├── 📑 UNIT (Unidade Pedagógica)
│   │   ├── 🔤 VOCABULARY (25 palavras + IPA)
│   │   ├── 📝 SENTENCES (12-15 conectadas)
│   │   ├── ⚡ STRATEGIES (TIPS 1-6 ou GRAMMAR 1-2)
│   │   ├── 📊 ASSESSMENTS (2 de 7 tipos)
│   │   ├── 🎯 AIMS (Objetivos pedagógicos)
│   │   └── 🎓 Q&A (Taxonomia de Bloom)
```

## 🔧 Serviços Principais

### 1. **VocabularyGeneratorService** (`vocabulary_generator.py`)
**Responsabilidade**: Geração de vocabulário contextual com RAG e análise de imagens

**Funcionalidades**:
- Geração de 25 palavras por unidade com validação IPA
- Análise de imagens via MCP (Model Context Protocol)
- RAG para evitar repetições entre unidades
- Suporte a 5 variantes linguísticas (American, British, etc.)
- Guidelines CEFR contextuais via IA

**Métodos IA**:
- `_analyze_cefr_guidelines_ai`: Guidelines específicas por contexto
- `_analyze_phonetic_complexity_ai`: Complexidade fonética adaptativa
- `_analyze_context_relevance_ai`: Relevância contextual (score 0.0-1.0)
- `_improve_phonemes_ai`: Melhoria de transcrições IPA

**Constantes Técnicas**:
- `IPA_VARIANT_MAPPING`: Mapeamento de variantes IPA
- `VOWEL_SOUNDS`: Análise silábica
- `STRESS_PATTERNS`: Padrões de acento

### 2. **SentencesGeneratorService** (`sentences_generator.py`)
**Responsabilidade**: Geração de sentences conectadas ao vocabulário com progressão pedagógica

**Funcionalidades**:
- 12-15 sentences por unidade
- Conectividade com vocabulário da unidade
- Progressão de complexidade (simples → complexa)
- Cache inteligente com TTL de 1 hora
- Validação de coerência contextual

**Métodos IA**:
- `_analyze_vocabulary_complexity_ai`: Análise de complexidade lexical
- `_customize_prompt_for_context_ai`: Personalização contextual
- `_validate_and_enrich_sentence_advanced`: Enriquecimento avançado

**Pipeline de Geração**:
1. Análise de vocabulário → 2. Contexto hierárquico → 3. Prompt RAG → 4. Geração LLM → 5. Validação pedagógica

### 3. **TipsGeneratorService** (`tips_generator.py`)
**Responsabilidade**: Seleção e aplicação das 6 estratégias TIPS para unidades lexicais

**Estratégias TIPS**:
1. **Afixação**: Prefixos e sufixos para expansão sistemática
2. **Substantivos Compostos**: Agrupamento temático por campo semântico
3. **Colocações**: Combinações naturais de palavras
4. **Expressões Fixas**: Frases cristalizadas e fórmulas funcionais
5. **Idiomas**: Expressões com significado figurativo
6. **Chunks**: Blocos funcionais para fluência automática

**Métodos IA**:
- `_select_optimal_tips_strategy_ai`: Seleção inteligente baseada em contexto + RAG
- `_analyze_strategy_context_ai`: Análise contextual da estratégia
- `_build_strategy_specific_prompt_ai`: Prompt personalizado por estratégia
- `_enrich_with_phonetic_components_ai`: Componentes fonéticos específicos

**Balanceamento RAG**: Evita overuso de estratégias (máximo 2 usos por estratégia a cada 7 unidades)

### 4. **GrammarGenerator** (`grammar_generator.py`)
**Responsabilidade**: Estratégias GRAMMAR para unidades gramaticais

**Estratégias GRAMMAR**:
1. **GRAMMAR 1**: Explicação Sistemática com progressão lógica
2. **GRAMMAR 2**: Prevenção L1→L2 (português → inglês)

**Métodos IA**:
- `_identify_grammar_point_ai`: Identificação contextual do ponto gramatical
- `_analyze_systematic_approach_ai`: Abordagem sistemática específica
- `_analyze_l1_interference_ai`: Padrões de interferência L1 brasileiros

**L1 Interference Database**: Base de erros comuns português→inglês integrada

### 5. **AssessmentSelectorService** (`assessment_selector.py`)
**Responsabilidade**: Seleção inteligente de 2 atividades complementares dentre 7 tipos

**7 Tipos de Assessment**:
1. **Cloze Test**: Compreensão geral com lacunas
2. **Gap Fill**: Vocabulário específico
3. **Reordering**: Estrutura e ordem
4. **Transformation**: Equivalência gramatical
5. **Multiple Choice**: Reconhecimento objetivo
6. **True/False**: Compreensão textual
7. **Matching**: Associações lexicais

**Métodos IA**:
- `_analyze_current_balance_ai`: Análise de balanceamento atual
- `_select_complementary_pair_ai`: Seleção de par complementar
- `_generate_specific_activity_ai`: Geração de atividade específica
- `_analyze_complementarity_ai`: Análise de complementaridade

**Algoritmo de Balanceamento**: RAG evita overuso, seleciona tipos subutilizados

### 6. **QAGeneratorService** (`qa_generator.py`)
**Responsabilidade**: Geração de Q&A baseado na Taxonomia de Bloom

**Taxonomia de Bloom Implementada**:
- **Remember**: Recall de vocabulário básico
- **Understand**: Explicação e compreensão
- **Apply**: Aplicação em novos contextos
- **Analyze**: Análise e relações
- **Evaluate**: Avaliação crítica
- **Create**: Produção original

**Distribuição por CEFR**:
- **A1/A2**: Foco em Remember + Understand
- **B1/B2**: Balance Apply + Analyze
- **C1/C2**: Emphasis Evaluate + Create

**Componentes Fonéticos**: 2-3 perguntas de pronúncia por unidade

### 7. **AimDetectorService** (`aim_detector.py`)
**Responsabilidade**: Detecção e geração de objetivos pedagógicos

**Estrutura de Objetivos**:
- **Main Aim**: Objetivo principal da unidade
- **Subsidiary Aims**: 3-5 objetivos subsidiários
- **Learning Objectives**: Estruturados com Taxonomia de Bloom
- **Communicative Goals**: Objetivos comunicativos
- **Assessment Criteria**: Critérios de avaliação

**Métodos IA**:
- `_detect_main_aim_type_ai`: Detecção lexis vs grammar
- `_generate_main_aim_ai`: Objetivo principal contextual
- `_generate_subsidiary_aims_ai`: Objetivos subsidiários
- `_calculate_aim_quality_metrics_ai`: Métricas de qualidade

### 8. **L1InterferenceAnalyzer** (`l1_interference.py`)
**Responsabilidade**: Análise especializada de interferência português→inglês

**Áreas de Análise**:
- **Grammatical Structure**: Diferenças estruturais
- **Vocabulary Interference**: False friends, uso semântico
- **Pronunciation Interference**: Sons desafiadores para brasileiros
- **Preventive Exercises**: Exercícios de prevenção específicos

**Cache Contextual**: 2 horas de TTL, máximo 50 análises

### 9. **HierarchicalDatabaseService** (`hierarchical_database.py`)
**Responsabilidade**: Operações de banco com hierarquia e paginação

**Funcionalidades**:
- CRUD completo para Course → Book → Unit
- Paginação avançada com filtros
- RAG Functions SQL para contexto hierárquico
- Validação de hierarquia
- Analytics do sistema

**RAG Functions**:
- `get_taught_vocabulary()`: Vocabulário já ensinado
- `get_used_strategies()`: Estratégias já aplicadas
- `get_used_assessments()`: Atividades já usadas
- `match_precedent_units()`: Unidades precedentes similares

### 10. **PromptGeneratorService** (`prompt_generator.py`)
**Responsabilidade**: Geração centralizada de prompts otimizados

**Templates Contextuais**:
- Prompts específicos por serviço
- Análise CEFR via IA
- Customização contextual
- Variante linguística integrada

## 🧠 Hub Central (`__init__.py`)

### ServiceRegistry
**Gerenciamento centralizado** de todas as instâncias de serviços:

```python
service_registry = ServiceRegistry()
await service_registry.initialize_services()

# Acesso direto
vocab_service = await get_vocabulary_service()
tips_service = await get_tips_service()
```

### ContentGenerationPipeline
**Pipeline sequencial** de geração:

```python
pipeline_steps = [
    "aims",          # 1. Objetivos pedagógicos
    "vocabulary",    # 2. Vocabulário contextual 
    "sentences",     # 3. Sentences conectadas
    "strategy",      # 4. TIPS ou GRAMMAR
    "assessments",   # 5. Atividades balanceadas
    "qa"            # 6. Q&A pedagógico
]
```

## 🎯 Metodologias Pedagógicas

### Método Direto
- Ensino direto na língua alvo
- Contexto comunicativo real
- Evita tradução excessiva

### Estratégias TIPS
- **Neurociência aplicada**: Estratégias baseadas em como o cérebro processa vocabulário
- **Agrupamento semântico**: Organização por campos semânticos
- **Automatização**: Chunks para fluência

### Taxonomia de Bloom
- **Progressão cognitiva**: Remember → Create
- **Adequação CEFR**: Distribuição apropriada por nível
- **Avaliação formativa**: Questões de múltiplos níveis

### Prevenção L1→L2
- **Análise contrastiva**: Português vs Inglês
- **Erros preditos**: Base de interferências comuns
- **Exercícios preventivos**: Atividades específicas

## 🔬 Análises via IA

### Padrão de Implementação
**Todos os serviços seguem o padrão**:
1. **Análise contextual via IA** para decisões complexas
2. **Constantes técnicas mantidas** para padrões estabelecidos
3. **Fallbacks técnicos** para casos de erro de IA
4. **Validação Pydantic 2** para estruturas de dados

### Exemplos de Métodos IA
```python
async def _analyze_context_via_ai(self, context: Dict) -> str:
    """Análise contextual específica via IA."""
    system_prompt = "Expert analysis prompt..."
    human_prompt = f"Analyze: {context}"
    response = await self.llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])
    return response.content.strip()

async def _fallback_technical_analysis(self, context: Dict) -> str:
    """Fallback técnico quando IA falha."""
    # Lógica técnica determinística
    return technical_analysis_result
```

## 📊 Métricas de Qualidade

### 22 Pontos de Controle Automático
- **Estrutura Pedagógica**: 8 pontos (hierarquia, objetivos, progressão)
- **Qualidade Linguística**: 7 pontos (IPA, relevância, conectividade)
- **RAG e Progressão**: 7 pontos (novidade, balanceamento, coerência)

### KPIs de Consistência
- **Vocabulary Overlap**: 10-20% reforço, 80-90% novo
- **Strategy Variety**: Máximo 2 repetições por book
- **Assessment Balance**: Distribuição equilibrada 7 tipos
- **CEFR Progression**: Sem saltos > 1 nível

## 🚀 Performance e Escalabilidade

### Otimizações
- **Cache Inteligente**: TTL contextual (desabilitado conforme solicitação)
- **Rate Limiting**: Proteção por endpoint
- **Paginação**: Sistema completo com filtros
- **Async/Await**: Operações não-bloqueantes
- **Connection Pooling**: Otimização de banco

### Monitoramento
- **Audit Logging**: Sistema completo de auditoria
- **Quality Metrics**: Acompanhamento em tempo real
- **Error Tracking**: Fallbacks e recuperação

## 🔧 Configuração e Uso

### Inicialização
```python
from src.services import (
    service_registry,
    content_pipeline,
    initialize_all_services
)

# Inicializar todos os serviços
await initialize_all_services()

# Usar pipeline completo
result = await content_pipeline.generate_complete_unit_content(
    unit_data, hierarchy_context, rag_context, images_analysis
)

# Usar serviços individuais
vocab_service = await get_vocabulary_service()
vocabulary = await vocab_service.generate_vocabulary_for_unit(params)
```

### Validação de Parâmetros
```python
# Todos os serviços implementam validação
validation = await service.validate_params(params)
if not validation["valid"]:
    handle_errors(validation["errors"])
```

## 🧪 Testes e Qualidade

### Cobertura de Testes
- **Unit Tests**: Cada serviço individual
- **Integration Tests**: Pipeline completo
- **Performance Tests**: Benchmarks de velocidade
- **Quality Tests**: Validação de métricas pedagógicas

### Exemplo de Teste
```python
async def test_vocabulary_generation():
    service = VocabularyGeneratorService()
    params = build_test_params()
    
    vocabulary = await service.generate_vocabulary_for_unit(params)
    
    assert len(vocabulary.items) == 25
    assert vocabulary.context_relevance >= 0.8
    assert all(item.phoneme.startswith('/') for item in vocabulary.items)
```

## 📝 Contribuição

### Adicionando Novos Serviços
1. Herdar padrões estabelecidos (LangChain 0.3 + Pydantic 2)
2. Implementar análises via IA para decisões complexas
3. Manter constantes técnicas para padrões estabelecidos
4. Adicionar fallbacks técnicos para robustez
5. Registrar no `ServiceRegistry`
6. Implementar `get_service_status()` e `validate_params()`

### Exemplo de Novo Serviço
```python
class NewPedagogicalService:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    async def generate_content(self, params: Dict) -> ContentModel:
        # 1. Análise via IA para decisões contextuais
        analysis = await self._analyze_context_ai(params)
        
        # 2. Usar constantes técnicas quando apropriado
        constants = ESTABLISHED_CONSTANTS[params["type"]]
        
        # 3. Implementar fallbacks técnicos
        try:
            result = await self._generate_via_ai(analysis, constants)
        except Exception:
            result = self._technical_fallback(params, constants)
        
        return ContentModel(**result)
    
    async def get_service_status(self) -> Dict[str, Any]:
        return {"service": "NewPedagogicalService", "status": "active"}
```

## 🌟 Principais Inovações

1. **100% Análise Contextual via IA**: Substituição de lógica hard-coded por análise inteligente
2. **RAG Hierárquico**: Contexto Course → Book → Unit para evitar repetições
3. **Metodologias Científicas**: TIPS, GRAMMAR, Taxonomia de Bloom integradas
4. **Balanceamento Inteligente**: Seleção automática baseada em histórico
5. **Validação IPA Completa**: 35+ símbolos fonéticos validados
6. **Prevenção L1→L2**: Análise específica de interferência português→inglês
7. **Pipeline Sequencial**: Geração coordenada de todos os componentes
8. **Cache Contextual**: Performance otimizada (desabilitado conforme solicitação)

---

**Última atualização**: 2025-01-28  
**LangChain Version**: 0.3.x  
**Pydantic Version**: 2.x  
**AI Integration**: 100% contextual analysis  
**Fallback Coverage**: Completa para robustez