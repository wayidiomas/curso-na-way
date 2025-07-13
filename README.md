# 📚 Curso Na Way - Gerador de Apostilas de Inglês

Sistema inteligente para geração automatizada de apostilas de inglês personalizadas usando IA generativa.

## 🚀 Tecnologias

- **Backend:** FastAPI + Python 3.11+
- **IA:** LangChain + OpenAI GPT
- **Banco:** Supabase (PostgreSQL + Vector + Auth)
- **Cache:** Redis
- **PDF:** ReportLab + WeasyPrint
- **Imagens:** OpenCV + Pillow
- **Gerenciador:** UV (ultra-rápido!)

## ⚡ Setup Rápido

```bash
# Instalar UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependências
uv sync

# Copiar configurações
cp .env.example .env
# Editar .env com suas chaves

# Rodar aplicação
uv run uvicorn src.main:app --reload
```

## 📖 Uso

1. **Upload de imagens** (obrigatório)
2. **Inserir texto** de contexto
3. **Selecionar nível CEFR** e variante
4. **Gerar vocabulário** (20-30 palavras)
5. **Editar vocabulário** se necessário
6. **Gerar conteúdo** completo
7. **Download PDF** da apostila

## 🏗 Arquitetura

```
Input (Texto + Imagens) → Análise IA → Vocabulário → 
Edição Manual → Geração de Conteúdo → PDF Final
```

## 📄 Tipos de Conteúdo

- **Teoria:** Explicações conceituais
- **Vocabs:** Lista contextual
- **Frases:** Exemplos práticos  
- **Gramática:** Regras e padrões
- **Tips:** Dicas pedagógicas
- **Exercícios:** Texto, preenchimento, interpretativo

## 🔧 Desenvolvimento

```bash
# Testes
uv run pytest

# Linting
uv run ruff check
uv run black .

# Tipo checking
uv run mypy src/
```
