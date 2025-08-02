# Dockerfile - Curso Na Way (Baseado em Melhores Práticas da Comunidade)
# Inspirado nas práticas modernas para FastAPI + LangChain + IA

# Usar Python 3.12 Alpine - Mais seguro e menor
FROM python:3.12-alpine

# Metadados
LABEL description="Curso Na Way - Sistema de Apostilas com IA"
LABEL version="0.2.0"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependências do sistema (Alpine)
RUN apk add --no-cache \
    curl \
    build-base \
    cairo-dev \
    pango-dev \
    gdk-pixbuf-dev \
    libffi-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev

# Criar usuário não-root para segurança
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Diretório de trabalho
WORKDIR /app

# CORREÇÃO: Copiar arquivos de dependências E README.md juntos (cache Docker mantido)
COPY --chown=appuser:appgroup pyproject.toml README.md ./

# Instalar UV e dependências
RUN pip install uv && \
    uv sync --no-dev

# Copiar código da aplicação
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup config/ ./config/

# Criar diretórios necessários
RUN mkdir -p logs cache temp uploads && \
    chown -R appuser:appgroup /app

# Mudar para usuário não-root
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expor porta
EXPOSE 8000

# Comando usando o novo fastapi CLI (prática mais moderna)
CMD ["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]