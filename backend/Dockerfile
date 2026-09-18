# Backend del Cotizador visual.
# Contexto de build: la RAÍZ del repo (así lo usa Railway con railway.toml en la raíz).
# Local:  docker build -f backend/Dockerfile -t cotizador-backend .
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias de sistema de WeasyPrint (Pango, Cairo, GDK-Pixbuf, HarfBuzz) y fuentes.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        fonts-ibm-plex \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/fixtures ./fixtures
COPY backend/scripts ./scripts
RUN pip install .

EXPOSE 8000

# Railway inyecta PORT; en local se usa 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
