# Dockerfile - IVO V2 Seguro (Usuário Não-Root)
FROM python:3.12-slim

LABEL description="IVO V2 - Intelligent Vocabulary Organizer"
LABEL version="2.0.0"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ✅ CORREÇÃO: Criar grupo e usuário com sintaxe correta
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Diretório de trabalho
WORKDIR /app

# Instalar UV como root (necessário)
RUN pip install uv

# Copiar arquivos de dependências e mudar ownership
COPY pyproject.toml README.md ./
RUN chown -R appuser:appgroup /app

# Instalar dependências Python como root (uv precisa)
RUN uv sync --no-dev

# Copiar código da aplicação
COPY src/ ./src/
COPY config/ ./config/

# Criar diretórios necessários e ajustar permissões
RUN mkdir -p logs cache temp uploads && \
    chown -R appuser:appgroup /app && \
    chmod -R 755 /app

# ✅ MUDAR PARA USUÁRIO NÃO-ROOT antes de executar
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expor porta
EXPOSE 8000

# Comando de inicialização como usuário não-root
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]