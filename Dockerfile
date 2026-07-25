# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12-slim

# ---------- Stage 1: build das dependências ----------
# Isolado num estágio próprio: build-essential/gcc só existem aqui, nunca
# chegam na imagem final. Precisamos deles porque o runner de CI é ARM
# (runner-arm-in8cloud-shared) e nem toda dependência tem wheel manylinux
# pré-compilado pra essa arquitetura — sem isso, pip cairia pra compilar
# do source sem compilador disponível.
FROM python:${PYTHON_VERSION} AS builder

WORKDIR /app

# export (não prefixo antes do primeiro comando): "VAR=x cmd1 && cmd2" só
# aplicaria a env var pro cmd1 - quem dispara o debconf do pacote gcc é o
# apt-get install, o segundo comando da cadeia.
RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia só o requirements.txt primeiro: essa camada (e o pip install) só é
# invalidada quando as dependências mudam, não a cada edit de código-fonte.
COPY backend/requirements.txt .

# Sem --mount=type=cache: o runner de CI builda com o builder clássico do
# Docker, não BuildKit (--mount exige BuildKit e falha nesse runner). O
# cache de layer que importa (essa camada só invalida quando requirements.txt
# muda) já funciona sem isso.
# --no-warn-script-location: os scripts (uvicorn, fastapi etc.) vão pra
# /root/.local/bin, fora do PATH desse estágio - inofensivo, porque quem
# importa é o PATH do estágio runtime (ajustado lá pra /home/appuser/.local/bin).
# --root-user-action=ignore: builder roda como root de propósito (só o
# runtime final troca pra appuser), não precisa do aviso de venv.
RUN pip install \
    --no-cache-dir \
    --user \
    --no-warn-script-location \
    --disable-pip-version-check \
    --root-user-action=ignore \
    -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:${PYTHON_VERSION} AS runtime

# Usuário não-root com UID/GID fixos, sem home real nem shell de login —
# suficiente pra rodar o processo e facilita políticas de segurança no ECS
# (ex. runAsNonRoot / runAsUser na task definition).
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# Pacotes Python instalados no builder (pip install --user -> ~/.local)
COPY --from=builder /root/.local /home/appuser/.local

# backend/ vira a raiz do WORKDIR: main.py, config.py, database.py etc. usam
# imports absolutos entre si (ver comentário em main.py), então main:app só
# resolve se esses arquivos estiverem direto em /app, não em /app/backend.
COPY backend/ .

RUN chown -R appuser:appuser /app /home/appuser/.local

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Não há endpoint /health hoje; /openapi.json é servido pelo FastAPI sem
# depender do Mongo/MQTT estarem no ar, então serve como liveness check
# barato sem precisar instalar curl na imagem.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as r; r.urlopen('http://127.0.0.1:8000/openapi.json', timeout=2)" || exit 1

# Sem --reload: isso é pra produção. As variáveis de ambiente (MONGO_URI,
# MQTT_*) vêm injetadas pela task definition do ECS, não de um .env
# copiado pra imagem (.env está no .dockerignore).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
