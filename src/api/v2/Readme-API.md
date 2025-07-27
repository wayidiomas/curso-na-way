# API v2 - Sistema IVO de Geração de Conteúdo Pedagógico

Este diretório contém a implementação completa da API v2 do sistema IVO (Intelligent Vocabulary Organizer), um sistema hierárquico avançado para geração automatizada de apostilas de inglês com foco em aprendizes brasileiros.

## 🏗️ Arquitetura Hierárquica

O sistema segue uma estrutura hierárquica obrigatória:

```
Course → Book → Unit → Content (Vocabulary, Sentences, Strategies, Assessments)
```

### Componentes da Hierarquia

- **Course**: Curso completo com níveis CEFR e metodologia
- **Book**: Livros organizados por nível CEFR dentro do curso  
- **Unit**: Unidades sequenciais dentro do book (lexical_unit ou grammar_unit)
- **Content**: Conteúdo gerado automaticamente com IA

## 📁 Estrutura de Arquivos

### Endpoints Principais

#### 🎯 **courses.py** - Gestão de Cursos
**Funcionalidades:**
- `POST /courses` - Criar curso com níveis CEFR e metodologia
- `GET /courses` - Listar cursos com paginação e filtros avançados
- `GET /courses/{id}` - Obter curso específico com estatísticas
- `GET /courses/{id}/hierarchy` - Visualizar hierarquia completa Course→Book→Unit
- `GET /courses/{id}/progress` - Análise pedagógica de progresso
- `PUT /courses/{id}` - Atualizar informações do curso
- `DELETE /courses/{id}` - Arquivamento seguro (não deleção física)

**Conecta-se com:**
- `hierarchical_database.py` - Operações de banco hierárquico
- `rate_limiter.py` - Controle de taxa de requisições
- `audit_logger.py` - Log de operações e auditoria
- `pagination.py` - Sistema de paginação avançada

#### 📚 **books.py** - Gestão de Books
**Funcionalidades:**
- `POST /courses/{course_id}/books` - Criar book em curso específico
- `GET /courses/{course_id}/books` - Listar books paginados com filtros
- `GET /books/{id}` - Obter book com unidades e estatísticas
- `GET /books/{id}/progression` - Análise de progressão pedagógica
- `PUT /books/{id}` - Atualizar informações do book
- `DELETE /books/{id}` - Arquivamento seguro

**Validações:**
- Nível CEFR do book deve estar nos níveis do curso
- Controle de sequenciamento automático
- Análise de progressão vocabular e estratégias

#### 🎓 **units.py** - Gestão de Unidades
**Funcionalidades:**
- `POST /books/{book_id}/units` - Criar unidade com imagens obrigatórias
- `GET /books/{book_id}/units` - Listar unidades paginadas
- `GET /units/{id}` - Obter unidade completa com contexto RAG
- `GET /units/{id}/context` - Contexto RAG detalhado para geração
- `PUT /units/{id}/status` - Controle de estado da unidade
- `PUT /units/{id}` - Atualizar metadados da unidade
- `DELETE /units/{id}` - Arquivamento com análise de impacto

**Estados da Unidade (Status Flow):**
```
creating → vocab_pending → sentences_pending → content_pending → assessments_pending → completed
```

**Validações:**
- Upload obrigatório de 1-2 imagens (máx 10MB cada)
- Validação hierárquica completa
- Análise de qualidade e progressão

### Geração de Conteúdo com IA

#### 📝 **vocabulary.py** - Geração de Vocabulário
**Sistema RAG Inteligente:**
- Análise de imagens via MCP (Model Context Protocol)
- Prevenção de repetições com contexto histórico
- Geração de fonemas IPA automática
- 20-45 palavras por nível CEFR

**Endpoints:**
- `POST /units/{id}/vocabulary` - Gerar vocabulário com RAG + MCP
- `GET /units/{id}/vocabulary` - Obter vocabulário com análises
- `PUT /units/{id}/vocabulary` - Edição manual validada
- `DELETE /units/{id}/vocabulary` - Remoção com atualização de status
- `GET /units/{id}/vocabulary/analysis` - Análise qualitativa completa

**Conecta-se com:**
- `VocabularyGeneratorService` - Service de geração IA
- `mcp_image_client.py` - Análise de imagens
- Base RAG hierárquica para contexto

#### 📖 **sentences.py** - Geração de Sentences
**Funcionalidades:**
- Sentences conectadas ao vocabulário gerado
- Integração com palavras de reforço de unidades anteriores
- Análise de complexidade e adequação ao nível
- Coerência contextual baseada no tema da unidade

**Endpoints:**
- `POST /units/{id}/sentences` - Gerar sentences conectadas
- `GET /units/{id}/sentences` - Obter sentences com análise
- `PUT /units/{id}/sentences` - Edição manual
- `DELETE /units/{id}/sentences` - Remoção com regressão de status
- `GET /units/{id}/sentences/analysis` - Análise qualitativa

#### 💡 **tips.py** - Estratégias TIPS (Unidades Lexicais)
**6 Estratégias Inteligentes:**
1. **Afixação** - Prefixos e sufixos
2. **Substantivos Compostos** - Agrupamento temático
3. **Colocações** - Combinações naturais
4. **Expressões Fixas** - Fórmulas cristalizadas
5. **Idiomas** - Expressões figurativas
6. **Chunks** - Blocos funcionais

**Seleção RAG:**
- Análise do vocabulário para detectar padrões
- Balanceamento baseado em estratégias já usadas
- Adequação ao nível CEFR
- Foco fonético e pronunciação

**Endpoints:**
- `POST /units/{id}/tips` - Gerar estratégia TIPS inteligente
- `GET /units/{id}/tips` - Obter estratégia aplicada
- `PUT /units/{id}/tips` - Edição manual com validação
- `DELETE /units/{id}/tips` - Remoção com ajuste de status
- `GET /units/{id}/tips/analysis` - Análise pedagógica
- `GET /tips/strategies` - Informações sobre as 6 estratégias

#### 📐 **grammar.py** - Estratégias GRAMMAR (Unidades Gramaticais)
**2 Estratégias Especializadas:**
1. **Explicação Sistemática** - Apresentação organizada e dedutiva
2. **Prevenção de Erros L1→L2** - Análise contrastiva português-inglês

**Foco Brasileiro:**
- Interferência L1 (português) → L2 (inglês)
- Erros comuns de brasileiros
- Exercícios contrastivos específicos
- Análise de false friends e estruturas

**Endpoints:**
- `POST /units/{id}/grammar` - Gerar estratégia GRAMMAR
- `GET /units/{id}/grammar` - Obter estratégia aplicada
- `PUT /units/{id}/grammar` - Edição manual
- `DELETE /units/{id}/grammar` - Remoção
- `GET /units/{id}/grammar/analysis` - Análise L1→L2
- `GET /grammar/strategies` - Info sobre estratégias GRAMMAR

#### 🎯 **assessments.py** - Geração de Atividades
**7 Tipos de Assessment:**
1. **Cloze Test** - Compreensão geral
2. **Gap Fill** - Lacunas específicas  
3. **Reordenação** - Ordem de frases
4. **Transformação** - Estruturas gramaticais
5. **Múltipla Escolha** - Questões objetivas
6. **Verdadeiro/Falso** - Compreensão textual
7. **Matching** - Associação de elementos

**Seleção Inteligente:**
- Algoritmo RAG para balanceamento
- Máximo 2 atividades por unidade
- Evita repetição excessiva (máx 2x por 7 unidades)
- Atividades complementares entre si

**Endpoints:**
- `POST /units/{id}/assessments` - Gerar 2 atividades balanceadas
- `GET /units/{id}/assessments` - Obter atividades com análise
- `PUT /units/{id}/assessments` - Edição manual
- `DELETE /units/{id}/assessments` - Remoção
- `GET /units/{id}/assessments/analysis` - Análise de qualidade
- `GET /assessments/types` - Info sobre os 7 tipos

#### ❓ **qa.py** - Perguntas e Respostas Pedagógicas
**Sistema Q&A Inteligente:**
- Baseado na Taxonomia de Bloom (6 níveis cognitivos)
- Perguntas de pronúncia e consciência fonética
- Integração com vocabulário e estratégias da unidade
- Progressão de dificuldade estruturada

**Níveis Cognitivos:**
1. **Remember** - Recordar fatos básicos
2. **Understand** - Explicar conceitos
3. **Apply** - Usar em situações novas
4. **Analyze** - Quebrar em partes
5. **Evaluate** - Fazer julgamentos
6. **Create** - Produzir conteúdo original

**Endpoints:**
- `POST /units/{id}/qa` - Gerar Q&A pedagógico
- `GET /units/{id}/qa` - Obter perguntas e respostas
- `PUT /units/{id}/qa` - Edição manual
- `DELETE /units/{id}/qa` - Remoção
- `GET /units/{id}/qa/analysis` - Análise pedagógica
- `GET /qa/pedagogical-guidelines` - Diretrizes pedagógicas

### Sistema de Saúde e Monitoramento

#### 🏥 **health.py** - Health Check Avançado
**Monitoramento Completo:**
- Status de conexões (Supabase, OpenAI API)
- Validação de componentes IVO V2
- Verificação de serviços hierárquicos
- Análise de rate limiting e auditoria
- Diagnósticos específicos do sistema

**Endpoints:**
- `GET /health` - Health check básico
- `GET /health/detailed` - Diagnóstico completo com recomendações

**Monitora:**
- Conexão Supabase e tabelas hierárquicas
- OpenAI API para geração de conteúdo
- VocabularyGeneratorService e outros services
- MCP Image Analysis (opcional)
- Rate Limiter em memória
- Audit Logger
- Variáveis de ambiente críticas
- Paths do sistema de arquivos

#### 📋 **__init__.py** - Informações da API
**Metadados Completos:**
- Versão 2.0.0 da API
- Arquitetura hierárquica Course→Book→Unit
- Status de implementação (62.5% completo)
- Endpoints implementados vs pendentes
- Fluxo recomendado de uso
- Rate limits por endpoint
- Sistema de validação de imports

**Informações de Estado:**
- **Implementados**: courses, books, units, vocabulary, assessments, tips, grammar, qa
- **Pendentes**: sentences (implementado mas listado como pendente), exportação, relatórios
- Configurações de rate limiting específicas
- Tags para documentação automática

## 🔧 Integrações e Dependências

### Services Externos
- **OpenAI GPT-4o-mini** - Geração de conteúdo IA
- **Supabase** - Banco de dados PostgreSQL
- **MCP (Model Context Protocol)** - Análise de imagens
- **IPA (International Phonetic Alphabet)** - Transcrições fonéticas

### Components Internos
- **hierarchical_database.py** - ORM hierárquico personalizado
- **rate_limiter.py** - Rate limiting em memória
- **audit_logger.py** - Sistema de auditoria completo
- **pagination.py** - Paginação avançada com filtros
- **enums.py** - Enums do sistema (CEFR, UnitType, etc.)

### Services de Geração
- **VocabularyGeneratorService** - Geração inteligente de vocabulário
- **SentencesGeneratorService** - Criação de sentences conectadas
- **TipsGeneratorService** - Estratégias TIPS para léxico
- **GrammarGeneratorService** - Estratégias GRAMMAR para gramática
- **AssessmentSelectorService** - Seleção inteligente de atividades
- **QAGeneratorService** - Geração de Q&A pedagógico

## 🎯 Sistema RAG (Retrieval-Augmented Generation)

### Contexto Hierárquico Inteligente
O sistema utiliza RAG para:

1. **Prevenção de Repetições**
   - Análise de vocabulário já ensinado
   - Evita duplicação desnecessária
   - Permite reforço estratégico (5-15%)

2. **Balanceamento de Estratégias**
   - Distribui estratégias TIPS/GRAMMAR uniformemente
   - Evita overuse de estratégias específicas
   - Mantém diversidade pedagógica

3. **Seleção de Assessments**
   - Balanceia os 7 tipos de atividades
   - Evita repetição excessiva
   - Garante complementaridade

4. **Progressão Pedagógica**
   - Adapta complexidade à sequência
   - Considera histórico de aprendizagem
   - Mantém coerência curricular

### Análise de Contexto
- **Taught Vocabulary**: Lista de palavras já ensinadas
- **Used Strategies**: Estratégias pedagógicas aplicadas
- **Assessment Balance**: Distribuição de tipos de atividades
- **Progression Level**: Nível de progressão na sequência
- **Quality Metrics**: Métricas de qualidade do conteúdo

## 🚀 Fluxo de Uso Recomendado

1. **Criar Course** com níveis CEFR e metodologia
2. **Criar Books** organizados por nível
3. **Criar Units** sequenciais com imagens
4. **Gerar Vocabulary** usando RAG + MCP
5. **Gerar Sentences** conectadas ao vocabulário
6. **Gerar Strategies** (TIPS para léxico, GRAMMAR para gramática)
7. **Gerar Assessments** (2 atividades balanceadas)
8. **Gerar Q&A** (opcional - complemento pedagógico)
9. **Unit completed!** - Pronta para uso

## 📊 Features Avançadas

### Rate Limiting Inteligente
- Limits específicos por tipo de operação
- Proteção contra abuse de geração IA
- Configuração flexível por endpoint

### Auditoria Completa
- Log de todas operações hierárquicas
- Tracking de geração de conteúdo IA
- Métricas de performance e uso
- Análise de erros e recuperação

### Paginação Avançada
- Filtros dinâmicos por múltiplos campos
- Ordenação flexível
- Metadados estatísticos
- Otimização de performance

### Análise de Qualidade
- Scores automáticos de qualidade
- Recomendações de melhoria
- Análise de adequação CEFR
- Métricas pedagógicas detalhadas

## 🎨 Especificidades para Brasileiros

### Análise L1→L2 (Português→Inglês)
- **False Friends**: library ≠ livraria
- **Estruturas**: auxiliares, artigos, ordem
- **Pronúncia**: sons /th/, vogais, consoantes finais
- **Gramática**: interferência sistemática

### Estratégias Culturais
- Contextos brasileiros em exemplos
- Situações familiares aos aprendizes
- Metodologia adaptada ao perfil brasileiro
- Foco em erros comuns de brasileiros

## 📈 Métricas e Analytics

### Quality Scores
- Vocabulário: relevância, adequação CEFR, fonemas
- Sentences: complexidade, coerência, integração
- Strategies: eficácia pedagógica, adequação ao nível
- Assessments: balanceamento, complementaridade
- Q&A: profundidade cognitiva, progressão

### Progression Analytics
- Densidade vocabular por unidade
- Diversidade de estratégias aplicadas
- Variedade de tipos de assessment
- Taxa de conclusão de unidades
- Qualidade média do conteúdo gerado

---

## 🚨 Limitações Atuais

- **Sentences**: Implementado mas considerado pendente no __init__.py
- **Export/PDF**: Sistema de exportação não implementado
- **Reports**: Relatórios avançados pendentes
- **Real-time**: Sistema de geração em tempo real básico
- **Caching**: Cache em memória apenas (sem Redis)

## 🔮 Próximos Passos

1. Implementar sistema de exportação para PDF
2. Adicionar relatórios pedagógicos avançados
3. Melhorar cache com Redis/persistent storage
4. Sistema de templates customizáveis
5. Dashboard de analytics em tempo real
6. API para integração com LMS
7. Sistema de revisão e correção automática
8. Geração de exercícios adaptativos

---

*Esta API representa um sistema completo de geração automatizada de conteúdo pedagógico para ensino de inglês, com foco especial em aprendizes brasileiros e metodologia baseada em evidências pedagógicas.*