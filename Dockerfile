FROM python:3.11-slim

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

# Crear un usuario no privilegiado para ejecutar la aplicación
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/instance && chown -R appuser:appuser /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    postgresql-client \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar los archivos de requisitos primero para aprovechar la caché de capas de Docker
COPY requirements.txt requirements-dev.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt
# Instalar dependencias de desarrollo solo en entorno de desarrollo
RUN if [ "$FLASK_ENV" = "development" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Copiar el script de entrada primero para que no se invalide la caché en cada cambio de código
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copiar el código de la aplicación
COPY --chown=appuser:appuser . /app/

# Crear directorios para archivos subidos y asegurar permisos
RUN mkdir -p /app/app/static/uploads \
    && chmod 755 /app/app/static/uploads \
    && chown -R appuser:appuser /app/app/static/uploads

# Exponer el puerto para la aplicación Flask
EXPOSE 5000

# Cambiar al usuario no privilegiado
USER appuser

# Comando de entrada para esperar a que los servicios dependientes estén disponibles
ENTRYPOINT ["docker-entrypoint.sh"]

# Comando por defecto - usar gunicorn con eventlet para soporte de WebSockets
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "eventlet", "--workers", "4", "run:app"]