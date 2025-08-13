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

# Copiar requirements antes para cache
COPY requirements.txt .

# Instalar dependencias Python (asegúrate que 'playwright' esté en requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores Playwright (chromium)
RUN python -m playwright install --with-deps chromium

# Copiar código fuente
COPY app/ ./app/

# Crear carpeta cookies y archivo cookies.txt vacío para persistencia
RUN mkdir -p /app/cookies && touch /app/cookies/cookies.txt

# Variables de entorno
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000
ENV YOUTUBE_COOKIES_PATH=/app/cookies/cookies.txt

# Exponer puerto
EXPOSE 8000

# Healthcheck para comprobar que la API está arriba
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Comando para iniciar la aplicación con Gunicorn + Uvicorn workers
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
