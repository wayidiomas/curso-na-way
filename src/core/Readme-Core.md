# 🧠 IVO V2 - Core Module

> **Núcleo central do sistema** que define modelos, validações, paginação, rate limiting e auditoria para a arquitetura hierárquica Course → Book → Unit.

## 📁 Estrutura da Pasta

```
src/core/
├── __init__.py                   # Inicializador vazio
├── audit_logger.py              # Sistema de auditoria completo
├── database.py                  # Inicializador do banco de dados
├── enums.py                     # Enumerações do sistema
├── hierarchical_models.py       # Modelos hierárquicos Course→Book→Unit
├── models.py                    # Configurações de modelos de IA
├── pagination.py                # Sistema de paginação avançado
├── rate_limiter.py              # Rate limiting com Redis/memória
└── unit_models.py               # Modelos específicos de unidades com IPA
```

## 🎯 Responsabilidades Principais

### 1. **Definição da Arquitetura Hierárquica**
- Modelos Pydantic para **Course → Book → Unit**
- Validação automática de estruturas hierárquicas
- Integração com RAG (Retrieval-Augmented Generation)
- Suporte a progressão pedagógica sequencial

### 2. **Validação IPA e Fonética**
- **35+ símbolos IPA validados** automaticamente
- Validação de transcrições fonéticas `/fonema/` e `[fonema]`
- Suporte a múltiplas variantes de pronúncia
- Análise de complexidade fonética

### 3. **Sistema de Auditoria Empresarial**
- **22 tipos de eventos** rastreados
- Logs estruturados em JSON
- Métricas de performance automáticas
- Rastreamento de operações hierárquicas

### 4. **Rate Limiting Inteligente**
- **Diferentes limites por endpoint**
- Fallback Redis → Memória
- Identificação por usuário/IP
- Headers HTTP automáticos

### 5. **Paginação Avançada**
- Filtros específicos por entidade
- Ordenação personalizada
- Metadados completos de navegação
- Queries SQL otimizadas

---

## 📋 Arquivos Detalhados

### 🔧 `enums.py` - Enumerações do Sistema

Define todos os tipos estruturais do IVO V2:

```python
# Níveis pedagógicos
class CEFRLevel(str, Enum):
    A1, A2, B1, B2, C1, C2

# Variantes linguísticas
class LanguageVariant(str, Enum):
    AMERICAN_ENGLISH, BRITISH_ENGLISH, BRAZILIAN_PORTUGUESE...

# Estratégias pedagógicas
class TipStrategy(str, Enum):
    AFIXACAO, COLOCACOES, CHUNKS...  # 6 estratégias

class GrammarStrategy(str, Enum):
    EXPLICACAO_SISTEMATICA, PREVENCAO_ERROS_L1  # 2 estratégias

# Tipos de avaliação
class AssessmentType(str, Enum):
    CLOZE_TEST, GAP_FILL, MATCHING...  # 7 tipos

# Status de unidade
class UnitStatus(str, Enum):
    CREATING, VOCAB_PENDING, COMPLETED, ERROR...
```

**Conecta com:**
- Todos os modelos Pydantic
- APIs de validação
- Sistema de progressão pedagógica

---

### 🏗️ `hierarchical_models.py` - Arquitetura Course→Book→Unit

Modelos principais da hierarquia pedagógica:

#### **Course Models**
```python
class CourseCreateRequest(BaseModel):
    name: str
    target_levels: List[CEFRLevel]  # A1→B2 progression
    language_variant: LanguageVariant
    methodology: List[str] = ["direct_method", "tips_strategies"]

class Course(BaseModel):
    id: str
    total_books: int
    total_units: int
    created_at: datetime
```

#### **Book Models** 
```python
class BookCreateRequest(BaseModel):
    name: str
    target_level: CEFRLevel  # Nível específico do book
    
class Book(BaseModel):
    course_id: str  # Hierarquia obrigatória
    sequence_order: int
    vocabulary_coverage: List[str]  # RAG tracking
    strategies_used: List[str]      # Balanceamento
```

#### **Unit Models com RAG**
```python
class HierarchicalUnitRequest(BaseModel):
    course_id: str  # OBRIGATÓRIO
    book_id: str    # OBRIGATÓRIO
    cefr_level: CEFRLevel
    unit_type: UnitType  # lexical_unit | grammar_unit

class UnitWithHierarchy(BaseModel):
    # Hierarquia
    course_id: str
    book_id: str
    sequence_order: int
    
    # Conteúdo estruturado
    vocabulary: Optional[Dict[str, Any]]
    sentences: Optional[Dict[str, Any]]
    tips: Optional[Dict[str, Any]]
    grammar: Optional[Dict[str, Any]]
    qa: Optional[Dict[str, Any]]
    assessments: Optional[Dict[str, Any]]
    
    # RAG tracking
    strategies_used: List[str]
    vocabulary_taught: List[str]
    status: UnitStatus
    quality_score: Optional[float]
```

#### **RAG Context Models**
```python
class RAGVocabularyContext(BaseModel):
    precedent_vocabulary: List[str]     # Palavras já ensinadas
    vocabulary_gaps: List[str]          # Oportunidades novas
    reinforcement_candidates: List[str] # Candidatas a reforço
    progression_level: str              # Nível pedagógico

class RAGStrategyContext(BaseModel):
    used_strategies: List[str]          # Estratégias já usadas
    recommended_strategy: str           # Próxima recomendada
    strategy_rationale: str             # Justificativa

class RAGAssessmentContext(BaseModel):
    used_assessments: List[Dict[str, Any]]
    recommended_assessments: List[AssessmentType]
    balance_rationale: Dict[str, Any]   # Análise de balanceamento
```

**Conecta com:**
- `services/hierarchical_database.py` (RAG queries)
- `api/v2/*.py` (endpoints hierárquicos)
- Sistema de paginação e filtros

---

### 📚 `unit_models.py` - Modelos com Validação IPA

Sistema completo de modelagem de unidades com **validação fonética avançada**:

#### **Vocabulary Models com IPA**
```python
class VocabularyItem(BaseModel):
    word: str                           # Palavra no idioma alvo
    phoneme: str                        # IPA validado: /ˈrɛstərɑnt/
    definition: str                     # Definição em português
    example: str                        # Contexto de uso
    word_class: str                     # noun, verb, adjective...
    
    # IPA e Fonética
    ipa_variant: str = "general_american"
    stress_pattern: Optional[str]
    syllable_count: Optional[int]
    alternative_pronunciations: List[str]
    
    # RAG e Progressão
    context_relevance: Optional[float]
    is_reinforcement: Optional[bool]
    first_introduced_unit: Optional[str]
    
    @validator('phoneme')
    def validate_ipa_phoneme(cls, v):
        # Validação completa de símbolos IPA
        valid_ipa_chars = set('aæəɑɒɔɪɛɜɝθðʃʒʧʤŋɹɻˈˌː...')
        # Verifica delimitadores / / ou [ ]
        # Valida símbolos individuais
        # Detecta erros comuns
```

#### **Content Models**
```python
class TipsContent(BaseModel):
    strategy: TipStrategy              # AFIXACAO, COLOCACOES...
    explanation: str
    examples: List[str]
    memory_techniques: List[str]
    
    # RAG integration
    vocabulary_coverage: List[str]
    selection_rationale: str
    phonetic_focus: List[str]          # Fonemas focalizados

class GrammarContent(BaseModel):
    strategy: GrammarStrategy          # EXPLICACAO_SISTEMATICA...
    grammar_point: str
    l1_interference_notes: List[str]   # Erros PT→EN
    common_mistakes: List[Dict[str, str]]
```

#### **Assessment Models com Balanceamento**
```python
class AssessmentActivity(BaseModel):
    type: AssessmentType               # CLOZE_TEST, GAP_FILL...
    title: str
    content: Dict[str, Any]
    answer_key: Dict[str, Any]
    
    # Balanceamento
    difficulty_level: str
    skills_assessed: List[str]
    pronunciation_focus: bool
    phonetic_elements: List[str]

class AssessmentSection(BaseModel):
    activities: List[AssessmentActivity]  # Sempre 2 atividades
    selection_rationale: str
    balance_analysis: Dict[str, Any]
    underused_activities: List[str]      # RAG balancing
```

#### **Complete Unit Response**
```python
class UnitResponse(BaseModel):
    # Hierarquia obrigatória
    id: str
    course_id: str
    book_id: str
    sequence_order: int
    
    # Conteúdo estruturado
    vocabulary: Optional[VocabularySection]
    sentences: Optional[SentencesSection]
    tips: Optional[TipsContent]           # Se lexical_unit
    grammar: Optional[GrammarContent]     # Se grammar_unit
    qa: Optional[QASection]
    assessments: Optional[AssessmentSection]
    
    # Tracking pedagógico
    strategies_used: List[str]
    vocabulary_taught: List[str]
    phonemes_introduced: List[str]        # Novos fonemas
    
    # Qualidade
    quality_score: Optional[float]
    checklist_completed: List[str]        # 22 validações
```

#### **Validation & Analysis Models**
```python
class PhoneticValidationResult(BaseModel):
    word: str
    phoneme: str
    is_valid: bool
    validation_details: Dict[str, Any]
    confidence_score: float

class BulkPhoneticValidation(BaseModel):
    total_items: int
    valid_items: int
    validation_results: List[PhoneticValidationResult]
    common_errors: List[str]
```

**Conecta com:**
- Sistema de validação IPA
- Geradores de conteúdo (`services/`)
- APIs de criação (`api/v2/`)

---

### 📄 `pagination.py` - Sistema de Paginação Avançado

Sistema completo de paginação com filtros específicos por entidade:

#### **Core Pagination Models**
```python
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)         # Página (inicia em 1)
    size: int = Field(20, ge=1, le=100) # Itens por página
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

class PaginationMeta(BaseModel):
    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int]
    prev_page: Optional[int]

class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: PaginationMeta
    hierarchy_info: Optional[Dict[str, str]]  # Contexto hierárquico
    filters_applied: Optional[Dict[str, Any]]
```

#### **Sorting & Filtering**
```python
class SortParams(BaseModel):
    sort_by: str = "created_at"
    sort_order: str = Field("desc", regex="^(asc|desc)$")

# Filtros específicos por entidade
class CourseFilterParams(FilterParams):
    language_variant: Optional[str]
    target_level: Optional[str]
    methodology: Optional[str]

class BookFilterParams(FilterParams):
    target_level: Optional[str]
    course_id: Optional[str]

class UnitFilterParams(FilterParams):
    status: Optional[str]
    unit_type: Optional[str]
    cefr_level: Optional[str]
    book_id: Optional[str]
    course_id: Optional[str]
    quality_score_min: Optional[float]
```

#### **Query Builders**
```python
class QueryBuilder:
    @staticmethod
    def build_courses_query(pagination, sorting, filters) -> str:
        # Gera SQL otimizado para cursos
        
    @staticmethod
    def build_books_query(course_id, pagination, sorting, filters) -> str:
        # Gera SQL para books de um curso específico
        
    @staticmethod  
    def build_units_query(book_id, pagination, sorting, filters) -> str:
        # Gera SQL para units de um book específico
```

**Métodos Principais:**
- `create_pagination_params()` - Criar parâmetros
- `build_sql_query_parts()` - Construir WHERE/ORDER/LIMIT
- `paginate_query_results()` - Criar response paginado

**Conecta com:**
- Todos os endpoints de listagem
- `services/hierarchical_database.py`
- Sistema de filtros por entidade

---

### 🛡️ `rate_limiter.py` - Rate Limiting Inteligente

Sistema de rate limiting com **diferentes políticas por endpoint**:

#### **Core Rate Limiter**
```python
class RateLimiter:
    def __init__(self, redis_url: str):
        # Tenta conectar Redis, fallback para memória
        
    async def is_allowed(
        self, 
        request: Request, 
        endpoint: str, 
        limit: int, 
        window: str = "60s"
    ) -> Tuple[bool, Dict[str, any]]:
        # Verifica se request é permitido
        # Retorna: (is_allowed, rate_info)
```

#### **Configurações por Endpoint**
```python
RATE_LIMIT_CONFIG = {
    # Course operations
    "create_course": {"limit": 10, "window": "60s"},
    "list_courses": {"limit": 100, "window": "60s"},
    "get_course": {"limit": 200, "window": "60s"},
    
    # Book operations  
    "create_book": {"limit": 20, "window": "60s"},
    "list_books": {"limit": 150, "window": "60s"},
    
    # Unit operations (mais restritivos)
    "create_unit": {"limit": 5, "window": "60s"},
    "generate_vocabulary": {"limit": 3, "window": "60s"},
    "generate_content": {"limit": 2, "window": "60s"},
}
```

#### **Dependencies & Middleware**
```python
async def rate_limit_dependency(request: Request, endpoint_name: str):
    # Dependency para FastAPI
    # Levanta HTTPException 429 se limite excedido

class RateLimitMiddleware:
    # Adiciona headers X-RateLimit-* automaticamente
```

**Funcionalidades:**
- **Identificação inteligente**: user_id > IP > fallback
- **Múltiplas janelas**: 60s, 10m, 1h
- **Fallback robusto**: Redis → Memória → Fail-open
- **Headers automáticos**: X-RateLimit-Limit, Remaining, Reset

**Conecta com:**
- Todos os endpoints da API
- Sistema de auditoria (logs de rate limit)
- Middleware global

---

### 📊 `audit_logger.py` - Sistema de Auditoria Empresarial

Sistema completo de auditoria com **22 tipos de eventos**:

#### **Event Types**
```python
class AuditEventType(str, Enum):
    # Course operations
    COURSE_CREATED, COURSE_VIEWED, COURSE_UPDATED...
    
    # Book operations
    BOOK_CREATED, BOOK_VIEWED, BOOK_UPDATED...
    
    # Unit operations
    UNIT_CREATED, UNIT_CONTENT_GENERATED...
    
    # Special operations
    RAG_QUERY_EXECUTED, IMAGE_ANALYZED, VOCABULARY_GENERATED...
    
    # Security events
    RATE_LIMIT_EXCEEDED, UNAUTHORIZED_ACCESS...
    
    # System events
    API_ERROR, PERFORMANCE_ALERT
```

#### **Core Audit Logger**
```python
class AuditLogger:
    async def log_event(
        self,
        event_type: AuditEventType,
        request: Optional[Request],
        resource_info: Optional[Dict[str, Any]],
        performance_metrics: Optional[Dict[str, Any]]
    ):
        # Log estruturado em JSON
        
    async def log_hierarchy_operation(
        self,
        event_type: AuditEventType,
        course_id: Optional[str],
        book_id: Optional[str], 
        unit_id: Optional[str]
    ):
        # Log específico para operações hierárquicas
        
    async def log_rag_operation(
        self,
        query_type: str,
        results_count: int,
        processing_time: float
    ):
        # Log específico para RAG
        
    async def log_content_generation(
        self,
        generation_type: str,
        content_stats: Dict[str, Any],
        ai_usage: Dict[str, Any]
    ):
        # Log para geração de conteúdo
```

#### **Performance Tracking**
```python
def start_request_tracking(self, request: Request) -> str:
    # Inicia tracking de performance
    
def end_request_tracking(self, request: Request, status_code: int):
    # Finaliza e calcula métricas
    # Auto-log se > 2 segundos
```

#### **Decorators & Context Managers**
```python
@audit_endpoint(
    event_type=AuditEventType.COURSE_CREATED,
    resource_extractor=extract_course_info,
    track_performance=True
)
async def create_course():
    # Auditoria automática

class AuditContext:
    # Context manager para operações complexas
    async def __aenter__(self):
        # Setup
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Log automático com métricas
```

**Dados Capturados:**
- **Request info**: IP, User-Agent, headers filtrados
- **User info**: user_id, session_id, role
- **Resource info**: course_id, book_id, unit_id, hierarchy
- **Performance**: tempo de execução, status codes
- **Content stats**: tokens, AI usage, RAG effectiveness

**Conecta com:**
- Todos os endpoints (via decorators)
- Sistema de rate limiting
- Métricas de performance
- Logs centralizados (`logs/audit.log`)

---

### 🗄️ `database.py` - Inicializador do Banco

Inicialização e verificação da estrutura hierárquica:

```python
async def init_database():
    # Verificar tabelas hierárquicas
    await _check_hierarchical_tables(supabase)
    # Verificar funções RAG
    await _check_rag_functions(supabase)

async def _check_hierarchical_tables(supabase):
    required_tables = [
        "ivo_courses", 
        "ivo_books", 
        "ivo_units", 
        "ivo_unit_embeddings"
    ]
    # Testa existência de cada tabela

async def _check_rag_functions(supabase):
    # Testa função get_taught_vocabulary
    # Verifica se funções RAG estão disponíveis
```

**Conecta com:**
- `config/database.py` (Supabase client)
- Startup da aplicação
- Sistema de logs

---

### ⚙️ `models.py` - Configurações de IA

Configuração centralizada dos modelos de IA:

```python
class OpenAISettings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.7

class LangChainSettings(BaseSettings):
    langchain_tracing_v2: bool = True
    langchain_project: str = "curso-na-way"

def load_model_configs() -> Dict[str, Any]:
    # Carrega de models.yaml ou defaults
    return {
        "content_configs": {
            "vocab_generation": {"max_tokens": 2048, "temperature": 0.5},
            "ivo_sentences_generation": {"max_tokens": 1536, "temperature": 0.6},
            "ivo_tips_generation": {"max_tokens": 2048, "temperature": 0.7},
            "ivo_grammar_generation": {"max_tokens": 2048, "temperature": 0.6},
            "ivo_assessments_generation": {"max_tokens": 3072, "temperature": 0.6}
        }
    }
```

**Conecta com:**
- Todos os serviços de geração
- LangChain chains
- Configurações por tipo de conteúdo

---

## 🔄 Fluxo de Integração

### 1. **Startup da Aplicação**
```
main.py → core/database.py → Verificação de estrutura
                           → Inicialização de tabelas/funções
```

### 2. **Request Flow**
```
API Request → rate_limiter.py → Verificação de limites
           → audit_logger.py → Início do tracking
           → hierarchical_models.py → Validação
           → unit_models.py → Validação IPA
           → audit_logger.py → Log final
```

### 3. **Content Generation Flow**
```
Unit Request → models.py → Configuração OpenAI
            → hierarchical_models.py → Contexto RAG
            → unit_models.py → Validação IPA
            → audit_logger.py → Log de geração
```

### 4. **Pagination Flow**
```
List Request → pagination.py → Parâmetros + Filtros
            → QueryBuilder → SQL otimizado
            → PaginatedResponse → Metadados completos
```

---

## 🎯 Principais Integrações Externas

### **Com Services Layer**
- `services/hierarchical_database.py` - RAG queries e contexto
- `services/vocabulary_generator.py` - Validação IPA
- `services/qa_generator.py` - Modelos de assessment

### **Com API Layer**
- `api/v2/*.py` - Todos os endpoints usam modelos core
- Rate limiting e auditoria automática
- Paginação em listagens

### **Com Infrastructure**
- `config/database.py` - Supabase client
- Redis para rate limiting
- Sistema de logs estruturados

### **Com External Services**
- OpenAI API - Configurações centralizadas
- LangChain - Tracking e configuração
- MCP (Model Context Protocol) - Análise de imagens

---

## 📈 Métricas de Qualidade

### **Validações Automáticas (22 pontos)**
- ✅ Hierarquia Course→Book→Unit válida
- ✅ Vocabulário adequado ao nível CEFR
- ✅ 100% fonemas IPA válidos
- ✅ RAG context applied corretamente
- ✅ Balanceamento de atividades
- ✅ Prevenção de interferência L1→L2

### **Performance Targets**
- **IPA Validation**: 97%+ accuracy
- **RAG Deduplication**: 90%+ new vocabulary  
- **Assessment Balance**: 88%+ variety distribution
- **API Response**: <2s automated alerts

### **Audit Coverage**
- **100% endpoint coverage** via decorators
- **Real-time performance tracking**
- **Structured JSON logs** para análise
- **Security event detection** automático

---

## 🚀 Uso Típico

### **1. Criar Course**
```python
course_request = CourseCreateRequest(
    name="Business English A2-B1",
    target_levels=[CEFRLevel.A2, CEFRLevel.B1],
    language_variant=LanguageVariant.AMERICAN_ENGLISH
)
# Auditoria automática: COURSE_CREATED
```

### **2. Paginar Books**
```python
pagination = PaginationParams(page=1, size=20)
filters = BookFilterParams(target_level="A2")
# Query builder SQL automático
```

### **3. Validar IPA**
```python
vocab_item = VocabularyItem(
    word="restaurant",
    phoneme="/ˈrɛstərɑnt/",  # Validação automática
    definition="estabelecimento comercial"
)
# 35+ símbolos IPA verificados
```

### **4. Rate Limiting**
```python
@rate_limit_dependency("create_unit")  # 5 req/min
async def create_unit():
    # Automático: Redis check → Headers → Exception 429
```

---

## 🔧 Configuração e Setup

### **Environment Variables**
```bash
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
REDIS_URL=redis://localhost:6379  # Opcional
LANGCHAIN_API_KEY=...             # Opcional
```

### **Dependencies**
```bash
pip install pydantic fastapi redis supabase langchain openai
```

### **Initialization**
```python
from src.core.database import init_database
from src.core.audit_logger import audit_logger_instance
from src.core.rate_limiter import rate_limiter

await init_database()  # Verificar estrutura
# Rate limiter e audit logger são singletons globais
```

---

## 🎓 Resumo Executivo

O módulo **`src/core/`** é o **núcleo inteligente** do IVO V2, fornecendo:

1. **🏗️ Arquitetura Hierárquica** - Course→Book→Unit com RAG
2. **🔤 Validação IPA Avançada** - 35+ símbolos fonéticos validados
3. **📊 Auditoria Empresarial** - 22 tipos de eventos estruturados  
4. **🛡️ Rate Limiting Inteligente** - Diferentes políticas por endpoint
5. **📄 Paginação Avançada** - Filtros específicos por entidade
6. **⚙️ Configuração Centralizada** - OpenAI, LangChain, banco de dados

**Resultado**: Base sólida que garante **qualidade pedagógica**, **performance otimizada** e **monitoramento completo** para todo o sistema IVO V2.