FROM python:3.9-slim

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_APP=run.py

# Crear un usuario no privilegiado para ejecutar la aplicación
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/instance && chown -R appuser:appuser /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar los archivos de requisitos primero para aprovechar la caché de capas de Docker
COPY requirements.txt /app/
COPY requirements-dev.txt /app/

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . /app/

# Crear el directorio de uploads y establecer permisos
RUN mkdir -p /app/app/static/uploads \
    && chown -R appuser:appuser /app/app/static/uploads

# Script de espera para servicios dependientes
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Cambiar al usuario no privilegiado
USER appuser

# Exponer el puerto
EXPOSE 5000

# Comando de entrada
ENTRYPOINT ["docker-entrypoint.sh"]

# Comando por defecto
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "eventlet", "--workers", "4", "run:app"]