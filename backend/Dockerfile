# Imagem do backend (Railway, Cloud Run ou qualquer host de container).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instalação editável: o código fica em /app e o config.py acha backend/ (samples, YAML, .db).
COPY . .
RUN pip install -e .

# O host define PORT (Railway, Cloud Run); 8000 fora deles.
# --proxy-headers: o IP de cada usuário vem do X-Forwarded-For, senão todo anônimo
# divide o mesmo limite de pré-busca (docs/13).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
