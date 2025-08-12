FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para Playwright y ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements antes para aprovechar cache de Docker
COPY requirements.txt .

# Instalar dependencias Python (incluido playwright)
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright (chromium)
RUN playwright install --with-deps chromium

# Copiar el código fuente
COPY app/ ./app/

# Crear archivo vacío para cookies persistentes
RUN touch /app/cookies.txt

# Variables de entorno
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000
ENV YOUTUBE_COOKIES_PATH=./cookies.txt

# Exponer puerto
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Ejecutar la aplicación con Gunicorn y Uvicorn worker
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
