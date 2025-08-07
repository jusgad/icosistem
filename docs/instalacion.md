# 📦 Guía de Instalación Completa

> **Guía paso a paso para instalar y configurar el Ecosistema de Emprendimiento**

## 📋 Tabla de Contenidos

- [⚡ Instalación Rápida](#-instalación-rápida)
- [🔧 Instalación Detallada](#-instalación-detallada)
- [🐳 Instalación con Docker](#-instalación-con-docker)
- [☁️ Instalación en la Nube](#️-instalación-en-la-nube)
- [🔧 Configuración Avanzada](#-configuración-avanzada)
- [❗ Solución de Problemas](#-solución-de-problemas)

## ⚡ Instalación Rápida

### 🚀 Para Desarrolladores (5 minutos)

```bash
# 1. Clonar repositorio
git clone https://github.com/ecosistema-emprendimiento/icosistem.git
cd icosistem

# 2. Configurar entorno virtual
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
npm install

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 5. Inicializar base de datos (requiere PostgreSQL corriendo)
flask db upgrade
flask seed-data

# 6. Iniciar aplicación
flask run
```

### 🐳 Con Docker (3 minutos)

```bash
# 1. Clonar repositorio
git clone https://github.com/ecosistema-emprendimiento/icosistem.git
cd icosistem

# 2. Copiar configuración
cp .env.example .env

# 3. Iniciar todo con Docker
docker-compose up -d

# 4. Ejecutar migraciones
docker-compose exec web flask db upgrade
docker-compose exec web flask seed-data
```

¡Ya tienes la aplicación corriendo en http://localhost:5000!

## 🔧 Instalación Detallada

### 📋 Prerrequisitos del Sistema

#### 🐧 Linux (Ubuntu/Debian)

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nodejs \
    npm \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libssl-dev \
    supervisor
```

#### 🍎 macOS

```bash
# Instalar Homebrew si no está instalado
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar dependencias
brew install \
    python@3.11 \
    postgresql@15 \
    redis \
    node \
    git

# Iniciar servicios
brew services start postgresql@15
brew services start redis
```

#### 🪟 Windows

```powershell
# Instalar chocolatey si no está instalado
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# Instalar dependencias
choco install -y python311 postgresql redis nodejs git
```

### 🗄️ Configuración de Base de Datos

#### PostgreSQL Setup

```bash
# 1. Conectar a PostgreSQL
sudo -u postgres psql

# 2. Crear usuario y base de datos
CREATE USER icosistem_user WITH PASSWORD 'tu_password_seguro';
CREATE DATABASE icosistem_dev OWNER icosistem_user;
CREATE DATABASE icosistem_test OWNER icosistem_user;
GRANT ALL PRIVILEGES ON DATABASE icosistem_dev TO icosistem_user;
GRANT ALL PRIVILEGES ON DATABASE icosistem_test TO icosistem_user;

# Opcional: crear base de datos de producción
CREATE DATABASE icosistem_prod OWNER icosistem_user;
GRANT ALL PRIVILEGES ON DATABASE icosistem_prod TO icosistem_user;

# Salir de PostgreSQL
\q
```

#### Configurar Redis

```bash
# Linux: editar configuración Redis
sudo nano /etc/redis/redis.conf

# Configuraciones recomendadas:
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# Reiniciar Redis
sudo systemctl restart redis-server

# macOS con Homebrew
brew services restart redis
```

### 🐍 Configuración de Python

#### 1. Crear y Activar Entorno Virtual

```bash
# Verificar versión de Python
python3.11 --version  # Debe ser 3.11.0 o superior

# Crear entorno virtual
python3.11 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows PowerShell
# venv\Scripts\activate.bat   # Windows CMD

# Verificar activación
which python  # Debe mostrar ruta dentro de venv/
python --version  # Debe mostrar Python 3.11.x
```

#### 2. Actualizar pip y setuptools

```bash
# Actualizar herramientas base
pip install --upgrade pip setuptools wheel

# Instalar dependencias de compilación
pip install Cython
```

#### 3. Instalar Dependencias de Python

```bash
# Dependencias base (obligatorias)
pip install -r requirements.txt

# Dependencias de desarrollo (recomendadas)
pip install -r requirements-dev.txt

# Dependencias de producción (opcional)
pip install -r requirements-prod.txt

# Verificar instalación
pip list | grep -i flask
pip list | grep -i sqlalchemy
```

### 🌐 Configuración de Node.js

#### 1. Verificar Instalación

```bash
# Verificar versiones
node --version  # Debe ser v18.0.0 o superior
npm --version   # Debe ser v9.0.0 o superior
```

#### 2. Instalar Dependencias Frontend

```bash
# Instalar dependencias
npm install

# Verificar instalación
npm list --depth=0

# Instalar herramientas globales útiles
npm install -g nodemon webpack-cli @vue/cli
```

#### 3. Compilar Assets

```bash
# Desarrollo (con watch mode)
npm run dev

# Producción (optimizado)
npm run build:prod

# Verificar compilación
ls -la app/static/dist/
```

### ⚙️ Variables de Entorno

#### 1. Crear Archivo .env

```bash
# Copiar template
cp .env.example .env

# Editar con tu editor favorito
nano .env  # o code .env, vim .env, etc.
```

#### 2. Configuración Básica

```env
# ==============================================================================
# CONFIGURACIÓN BÁSICA DE LA APLICACIÓN
# ==============================================================================

# Entorno de la aplicación
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_APP=wsgi.py

# Seguridad - ¡CAMBIAR EN PRODUCCIÓN!
SECRET_KEY=tu-clave-secreta-super-larga-y-segura-cambiar-en-produccion
JWT_SECRET_KEY=otra-clave-secreta-para-jwt-cambiar-en-produccion

# ==============================================================================
# BASE DE DATOS
# ==============================================================================

# PostgreSQL Principal
DATABASE_URL=postgresql://icosistem_user:tu_password_seguro@localhost:5432/icosistem_dev

# PostgreSQL para Testing (opcional)
TEST_DATABASE_URL=postgresql://icosistem_user:tu_password_seguro@localhost:5432/icosistem_test

# ==============================================================================
# CACHÉ Y SESIONES
# ==============================================================================

# Redis
REDIS_URL=redis://localhost:6379/0

# Configuración de cache
CACHE_TYPE=redis
CACHE_DEFAULT_TIMEOUT=300

# ==============================================================================
# EMAIL
# ==============================================================================

# Configuración SMTP (Gmail ejemplo)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=tu-email@gmail.com
MAIL_PASSWORD=tu-contraseña-de-aplicación

# Configuración de emails
MAIL_DEFAULT_SENDER="Ecosistema Emprendimiento <noreply@tudominio.com>"
MAIL_SUPPRESS_SEND=False

# ==============================================================================
# SERVICIOS EXTERNOS
# ==============================================================================

# Google OAuth
GOOGLE_CLIENT_ID=tu-google-client-id.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-google-client-secret

# GitHub OAuth (opcional)
GITHUB_CLIENT_ID=tu-github-client-id
GITHUB_CLIENT_SECRET=tu-github-client-secret

# Stripe (pagos)
STRIPE_PUBLIC_KEY=pk_test_tu_stripe_public_key
STRIPE_SECRET_KEY=sk_test_tu_stripe_secret_key

# Twilio (SMS)
TWILIO_ACCOUNT_SID=tu-twilio-account-sid
TWILIO_AUTH_TOKEN=tu-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# ==============================================================================
# MONITOREO Y LOGGING
# ==============================================================================

# Sentry (opcional pero recomendado)
SENTRY_DSN=https://tu-sentry-dsn@sentry.io/proyecto

# Log Level
LOG_LEVEL=INFO

# ==============================================================================
# CONFIGURACIÓN DE DESARROLLO
# ==============================================================================

# Debug toolbar
DEBUG_TB_ENABLED=True
DEBUG_TB_INTERCEPT_REDIRECTS=False

# Profiling
PROFILE=False
```

#### 3. Configuración de Producción

Para producción, crea un archivo `.env.prod`:

```env
# Configuración de producción
FLASK_ENV=production
FLASK_DEBUG=False

# Base de datos de producción
DATABASE_URL=postgresql://user:pass@prod-db:5432/icosistem_prod

# Redis de producción
REDIS_URL=redis://prod-redis:6379/0

# SSL y seguridad
SSL_REDIRECT=True
SECURE_HEADERS=True

# Configuración de workers
WEB_CONCURRENCY=4
WORKER_TIMEOUT=120
MAX_REQUESTS=1000
```

### 🗄️ Inicialización de Base de Datos

#### 1. Ejecutar Migraciones

```bash
# Verificar estado de migraciones
flask db current

# Ejecutar todas las migraciones pendientes
flask db upgrade

# Ver historial de migraciones
flask db history

# Verificar en PostgreSQL
psql -U icosistem_user -d icosistem_dev -c "\dt"
```

#### 2. Cargar Datos Iniciales

```bash
# Cargar datos básicos (usuarios admin, roles, etc.)
flask seed-data

# Cargar datos de ejemplo para desarrollo
flask seed-data --sample-data

# Cargar datos específicos
flask seed-data --users --organizations --projects

# Verificar datos cargados
flask list-users
```

#### 3. Crear Usuario Administrador

```bash
# Crear admin interactivamente
flask create-admin

# Crear admin con datos específicos
flask create-admin \
    --email admin@tudominio.com \
    --password admin123 \
    --name "Administrador Principal"

# Verificar creación
flask list-users --role admin
```

### 🔧 Configuración de Servicios

#### 1. Configurar Celery (Tareas en Background)

```bash
# Terminal 1: Iniciar worker
celery -A app.celery worker --loglevel=info

# Terminal 2: Iniciar beat (scheduler)
celery -A app.celery beat --loglevel=info

# Terminal 3: Iniciar flower (monitoreo)
celery -A app.celery flower

# Acceder a Flower: http://localhost:5555
```

#### 2. Configurar Supervisor (Producción)

```bash
# Crear archivo de configuración
sudo nano /etc/supervisor/conf.d/icosistem.conf
```

```ini
[program:icosistem-web]
command=/path/to/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
directory=/path/to/icosistem
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/icosistem/web.log

[program:icosistem-celery]
command=/path/to/venv/bin/celery -A app.celery worker --loglevel=info
directory=/path/to/icosistem
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/icosistem/celery.log

[program:icosistem-beat]
command=/path/to/venv/bin/celery -A app.celery beat --loglevel=info
directory=/path/to/icosistem
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/icosistem/beat.log
```

```bash
# Recargar y iniciar servicios
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

## 🐳 Instalación con Docker

### 🚀 Docker Compose (Recomendado)

#### 1. Instalación de Docker

```bash
# Linux (Ubuntu)
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
# Logout y login de nuevo

# macOS
brew install docker docker-compose
# O descargar Docker Desktop

# Windows
# Descargar e instalar Docker Desktop desde docker.com
```

#### 2. Configuración con Docker Compose

```bash
# Copiar configuración
cp .env.example .env
# Editar .env con configuraciones de Docker

# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Ejecutar comandos en contenedores
docker-compose exec web flask db upgrade
docker-compose exec web flask seed-data

# Parar servicios
docker-compose down
```

#### 3. Configuración de Desarrollo con Docker

```yaml
# docker-compose.override.yml para desarrollo
version: '3.8'

services:
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
    volumes:
      - .:/app
      - /app/venv  # Excluir venv del bind mount
    environment:
      - FLASK_DEBUG=True
      - FLASK_ENV=development
    ports:
      - "5000:5000"
    
  postgres:
    environment:
      - POSTGRES_DB=icosistem_dev
      - POSTGRES_USER=icosistem_user
      - POSTGRES_PASSWORD=dev_password
    ports:
      - "5432:5432"
  
  redis:
    ports:
      - "6379:6379"
```

### 🏗️ Construcción de Imágenes Personalizadas

#### 1. Imagen de Desarrollo

```bash
# Construir imagen de desarrollo
docker build -f docker/Dockerfile.dev -t icosistem:dev .

# Ejecutar contenedor de desarrollo
docker run -d \
    --name icosistem-dev \
    -p 5000:5000 \
    -v $(pwd):/app \
    -e FLASK_ENV=development \
    icosistem:dev
```

#### 2. Imagen de Producción

```bash
# Construir imagen de producción
docker build -f docker/Dockerfile.prod -t icosistem:latest .

# Ejecutar contenedor de producción
docker run -d \
    --name icosistem-prod \
    -p 8000:8000 \
    -e DATABASE_URL=postgresql://... \
    -e REDIS_URL=redis://... \
    icosistem:latest
```

## ☁️ Instalación en la Nube

### 🚀 Heroku

#### 1. Preparación

```bash
# Instalar Heroku CLI
# Linux
curl https://cli-assets.heroku.com/install.sh | sh

# macOS
brew install heroku/brew/heroku

# Login
heroku login
```

#### 2. Crear Aplicación

```bash
# Crear app
heroku create tu-app-icosistem

# Configurar variables de entorno
heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=tu-clave-secreta
heroku config:set DATABASE_URL=postgresql://...

# Agregar add-ons
heroku addons:create heroku-postgresql:hobby-dev
heroku addons:create heroku-redis:hobby-dev

# Desplegar
git push heroku main

# Ejecutar migraciones
heroku run flask db upgrade
heroku run flask seed-data
```

### ☁️ AWS EC2

#### 1. Lanzar Instancia EC2

```bash
# Conectar a instancia
ssh -i tu-key.pem ubuntu@tu-ec2-instance.amazonaws.com

# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y python3.11 python3.11-venv nginx supervisor
```

#### 2. Configurar RDS (PostgreSQL)

```bash
# Crear instancia RDS PostgreSQL
aws rds create-db-instance \
    --db-instance-identifier icosistem-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username icosistem_user \
    --master-user-password tu_password_seguro \
    --allocated-storage 20 \
    --db-name icosistem_prod
```

#### 3. Configurar ElastiCache (Redis)

```bash
# Crear cluster Redis
aws elasticache create-cache-cluster \
    --cache-cluster-id icosistem-redis \
    --engine redis \
    --cache-node-type cache.t3.micro \
    --num-cache-nodes 1
```

### 🌐 Google Cloud Platform

#### 1. Cloud Run

```bash
# Construir y subir imagen
docker build -t gcr.io/tu-proyecto/icosistem .
docker push gcr.io/tu-proyecto/icosistem

# Desplegar en Cloud Run
gcloud run deploy icosistem \
    --image gcr.io/tu-proyecto/icosistem \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars FLASK_ENV=production
```

#### 2. Cloud SQL y Memorystore

```bash
# Crear instancia Cloud SQL
gcloud sql instances create icosistem-db \
    --database-version POSTGRES_14 \
    --tier db-f1-micro \
    --region us-central1

# Crear instancia Memorystore Redis
gcloud redis instances create icosistem-redis \
    --size 1 \
    --region us-central1
```

## 🔧 Configuración Avanzada

### 🔒 Configuración de SSL/TLS

#### 1. Con Let's Encrypt (Certbot)

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tudominio.com -d www.tudominio.com

# Auto-renovación
sudo crontab -e
# Agregar: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### 2. Configuración Nginx con SSL

```nginx
# /etc/nginx/sites-available/icosistem
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tudominio.com www.tudominio.com;
    
    ssl_certificate /etc/letsencrypt/live/tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tudominio.com/privkey.pem;
    
    # SSL optimizations
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /path/to/icosistem/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        gzip_static on;
    }
}
```

### 📊 Configuración de Monitoreo

#### 1. Prometheus y Grafana

```bash
# Docker compose para monitoreo
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus_data:
  grafana_data:
```

#### 2. Configuración Prometheus

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules.yml"

scrape_configs:
  - job_name: 'icosistem'
    static_configs:
      - targets: ['host.docker.internal:5000']
    metrics_path: '/metrics'
    scrape_interval: 5s
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres_exporter:9187']
      
  - job_name: 'redis'
    static_configs:
      - targets: ['redis_exporter:9121']
```

### 🔄 Configuración de Backup

#### 1. Backup de PostgreSQL

```bash
# Script de backup
#!/bin/bash
# backup-db.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/icosistem"
DB_NAME="icosistem_prod"
DB_USER="icosistem_user"

# Crear directorio si no existe
mkdir -p $BACKUP_DIR

# Backup de base de datos
pg_dump -U $DB_USER -h localhost $DB_NAME > "$BACKUP_DIR/icosistem_$DATE.sql"

# Comprimir backup
gzip "$BACKUP_DIR/icosistem_$DATE.sql"

# Eliminar backups antiguos (conservar últimos 30 días)
find $BACKUP_DIR -name "icosistem_*.sql.gz" -mtime +30 -delete

echo "Backup completado: icosistem_$DATE.sql.gz"
```

#### 2. Cron para Backups Automáticos

```bash
# Agregar a crontab
crontab -e

# Backup diario a las 2 AM
0 2 * * * /path/to/backup-db.sh

# Backup de archivos semanalmente
0 3 * * 0 tar -czf /var/backups/icosistem/files_$(date +\%Y\%m\%d).tar.gz /path/to/icosistem/app/uploads/
```

## ❗ Solución de Problemas

### 🐍 Problemas de Python

#### Error: "python3.11 not found"

```bash
# Ubuntu/Debian
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Verificar instalación
python3.11 --version
```

#### Error: "Failed building wheel for psycopg2"

```bash
# Instalar dependencias de compilación
sudo apt install postgresql-server-dev-all gcc

# O usar versión binaria
pip install psycopg2-binary
```

#### Error: "No module named '_ctypes'"

```bash
# Ubuntu/Debian
sudo apt install libffi-dev

# Reinstalar Python si es necesario
sudo apt install --reinstall python3.11-dev
```

### 🗄️ Problemas de Base de Datos

#### Error: "Connection refused" PostgreSQL

```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Iniciar si está parado
sudo systemctl start postgresql

# Verificar puerto y conexiones
sudo netstat -tulnp | grep 5432

# Verificar configuración
sudo nano /etc/postgresql/15/main/postgresql.conf
# listen_addresses = 'localhost'

sudo nano /etc/postgresql/15/main/pg_hba.conf
# local   all             all                                     md5
```

#### Error: "FATAL: database does not exist"

```bash
# Conectar como superuser
sudo -u postgres psql

# Crear base de datos
CREATE DATABASE icosistem_dev OWNER icosistem_user;

# Verificar creación
\l

# Salir
\q
```

#### Error: "permission denied for relation"

```bash
# Otorgar permisos completos
sudo -u postgres psql

GRANT ALL PRIVILEGES ON DATABASE icosistem_dev TO icosistem_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO icosistem_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO icosistem_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO icosistem_user;

\q
```

### 🔴 Problemas de Redis

#### Error: "Connection refused" Redis

```bash
# Verificar que Redis esté corriendo
sudo systemctl status redis-server

# Iniciar si está parado
sudo systemctl start redis-server

# Verificar puerto
sudo netstat -tulnp | grep 6379

# Test de conexión
redis-cli ping
# Debe responder: PONG
```

#### Error: "Out of memory"

```bash
# Editar configuración Redis
sudo nano /etc/redis/redis.conf

# Configurar límite de memoria
maxmemory 512mb
maxmemory-policy allkeys-lru

# Reiniciar Redis
sudo systemctl restart redis-server
```

### 🌐 Problemas de Frontend

#### Error: "npm install fails"

```bash
# Limpiar cache de npm
npm cache clean --force

# Eliminar node_modules y reinstalar
rm -rf node_modules package-lock.json
npm install

# Si persiste, usar npm ci
npm ci
```

#### Error: "webpack command not found"

```bash
# Instalar webpack globalmente
npm install -g webpack webpack-cli

# O usar npx
npx webpack --version
```

### 🐳 Problemas de Docker

#### Error: "Permission denied" Docker

```bash
# Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Logout y login de nuevo
# O ejecutar:
newgrp docker

# Verificar
docker run hello-world
```

#### Error: "Port already in use"

```bash
# Encontrar proceso usando el puerto
sudo lsof -i :5000

# Matar proceso si es necesario
sudo kill -9 <PID>

# O cambiar puerto en docker-compose.yml
ports:
  - "5001:5000"  # Usar puerto diferente
```

### 🔧 Problemas de Configuración

#### Error: "Environment variable not set"

```bash
# Verificar que el archivo .env existe
ls -la .env

# Verificar contenido
cat .env

# Verificar que Flask lo carga
flask shell
>>> import os
>>> os.environ.get('DATABASE_URL')
```

#### Error: "Module not found"

```bash
# Verificar que el entorno virtual está activo
which python
# Debe mostrar ruta dentro de venv/

# Verificar instalación del módulo
pip list | grep nombre-modulo

# Reinstalar si es necesario
pip install --upgrade nombre-modulo
```

### 📝 Logs de Debugging

#### Habilitar Logs Detallados

```bash
# En .env
FLASK_DEBUG=True
LOG_LEVEL=DEBUG

# Ver logs en tiempo real
tail -f logs/app.log

# O con Docker
docker-compose logs -f web
```

#### Ubicaciones de Logs Importantes

```bash
# Logs de la aplicación
tail -f logs/app.log

# Logs de PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-15-main.log

# Logs de Redis
sudo tail -f /var/log/redis/redis-server.log

# Logs de Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Logs del sistema
sudo journalctl -u icosistem-web -f
```

### 🆘 Obtener Ayuda

Si necesitas ayuda adicional:

1. **Revisa la documentación**: [docs/](../docs/)
2. **Busca en issues existentes**: [GitHub Issues](https://github.com/ecosistema-emprendimiento/icosistem/issues)
3. **Crea un nuevo issue**: Incluye logs, configuración y pasos para reproducir
4. **Únete a la comunidad**: [Discord](https://discord.gg/icosistem)
5. **Contacta soporte**: support@icosistem.com

---

**💡 Consejo**: Mantén un log detallado de los pasos que sigues durante la instalación. Te ayudará a identificar problemas y a reproducir la instalación en otros entornos.