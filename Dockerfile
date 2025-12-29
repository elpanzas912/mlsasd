# Usamos una imagen oficial de Python ligera
FROM python:3.10-slim

# Evita que Python escriba archivos .pyc y salte el buffer de salida
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependencias del sistema necesarias para Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiamos y instalamos dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalamos los navegadores de Playwright (incluyendo dependencias de SO)
RUN playwright install --with-deps chromium

# Copiamos el resto del código
COPY . .

# Comando para iniciar el bot
CMD ["python", "index.py"]
