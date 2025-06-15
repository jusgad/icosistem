# Guía de Deployment - Ecosistema de Emprendimiento

## Tabla de Contenidos

1. [Requisitos del Sistema](#requisitos-del-sistema)
2. [Preparación del Servidor](#preparación-del-servidor)
3. [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
4. [Base de Datos](#base-de-datos)
5. [Deployment con Docker](#deployment-con-docker)
6. [Configuración de Servicios](#configuración-de-servicios)
7. [Proxy Reverso y SSL](#proxy-reverso-y-ssl)
8. [Monitoreo y Logging](#monitoreo-y-logging)
9. [Backup y Recuperación](#backup-y-recuperación)
10. [Mantenimiento](#mantenimiento)
11. [Troubleshooting](#troubleshooting)

---

## Requisitos del Sistema

### Recursos Mínimos Recomendados

**Para Entorno de Producción:**
- **CPU:** 4 cores (8 recomendados)
- **RAM:** 8GB (16GB recomendados)
- **Almacenamiento:** 100GB SSD (500GB recomendados)
- **Red:** 1Gbps
- **OS:** Ubuntu 20.04 LTS / Ubuntu 22.04 LTS / CentOS 8+ / RHEL 8+

**Para Entorno de Staging:**
- **CPU:** 2 cores
- **RAM:** 4GB
- **Almacenamiento:** 50GB SSD
- **Network:** 100Mbps

### Software Requerido

```bash
# Dependencias del sistema
- Docker 24.0+
- Docker Compose 2.0+
- Nginx 1.18+
- Let's Encrypt (Certbot)
- PostgreSQL 14+ (si no se usa contenedor)
- Redis 6.0+ (si no se usa contenedor)
```

---

## Preparación del Servidor

### 1. Actualización del Sistema

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git vim htop

# CentOS/RHEL
sudo yum update -y
sudo yum install -y curl wget git vim htop
```

### 2. Instalación de Docker

```bash
# Instalación de Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER

# Instalación de Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar instalación
docker --version
docker-compose --version
```

### 3. Configuración de Firewall

```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 5432  # PostgreSQL (si es externo)
sudo ufw allow 6379  # Redis (si es externo)

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 4. Configuración de Usuarios

```bash
# Crear usuario para la aplicación
sudo adduser --system --group --home /opt/ecosistema ecosistema
sudo usermod -aG docker ecosistema

# Crear directorios de aplicación
sudo mkdir -p /opt/ecosistema/{app,data,logs,backups}
sudo chown -R ecosistema:ecosistema /opt/ecosistema
```

---

## Configuración de Variables de Entorno

### 1. Archivo de Producción (.env.prod)

```bash
# === CONFIGURACIÓN BÁSICA ===
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-super-secret-key-here-min-32-chars
WTF_CSRF_SECRET_KEY=your-csrf-secret-key-here

# === BASE DE DATOS ===
DATABASE_URL=postgresql://ecosistema_user:secure_password@postgres:5432/ecosistema_prod
POSTGRES_DB=ecosistema_prod
POSTGRES_USER=ecosistema_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# === REDIS/CACHE ===
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
CACHE_REDIS_URL=redis://redis:6379/3

# === SEGURIDAD ===
JWT_SECRET_KEY=your-jwt-secret-key-here
PASSWORD_SALT=your-password-salt-here
ENCRYPTION_KEY=your-32-byte-encryption-key-base64

# === EMAIL ===
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=noreply@yourcompany.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@yourcompany.com

# === GOOGLE SERVICES ===
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_CALENDAR_CREDENTIALS=/app/config/google-calendar-credentials.json
GOOGLE_MEET_CREDENTIALS=/app/config/google-meet-credentials.json

# === AWS/S3 (para archivos) ===
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
S3_BUCKET=ecosistema-files-prod
S3_ENDPOINT_URL=https://s3.amazonaws.com

# === SMS ===
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_NUMBER=+1234567890

# === MONITOREO ===
SENTRY_DSN=your-sentry-dsn
NEW_RELIC_LICENSE_KEY=your-newrelic-key
PROMETHEUS_METRICS_PORT=9090

# === APLICACIÓN ===
APP_NAME=Ecosistema de Emprendimiento
APP_URL=https://yourdomain.com
ADMIN_EMAIL=admin@yourcompany.com
SUPPORT_EMAIL=support@yourcompany.com

# === RATE LIMITING ===
RATE_LIMIT_STORAGE_URL=redis://redis:6379/4
DEFAULT_RATE_LIMIT=100 per hour

# === LOGGING ===
LOG_LEVEL=INFO
LOG_FILE=/app/logs/application.log
ERROR_LOG_FILE=/app/logs/error.log

# === BACKUP ===
BACKUP_S3_BUCKET=ecosistema-backups-prod
BACKUP_RETENTION_DAYS=30

# === PERFORMANCE ===
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_MAX_REQUESTS=1000
GUNICORN_TIMEOUT=30

# === FEATURES FLAGS ===
ENABLE_ANALYTICS=True
ENABLE_NOTIFICATIONS=True
ENABLE_WEBHOOKS=True
ENABLE_API_DOCS=False
MAINTENANCE_MODE=False
```

### 2. Generación de Claves Seguras

```bash
# Script para generar claves seguras
cat > generate_keys.py << 'EOF'
import secrets
import base64
import os

def generate_secret_key(length=32):
    return secrets.token_urlsafe(length)

def generate_encryption_key():
    key = os.urandom(32)
    return base64.b64encode(key).decode()

if __name__ == "__main__":
    print("SECRET_KEY=" + generate_secret_key())
    print("WTF_CSRF_SECRET_KEY=" + generate_secret_key())
    print("JWT_SECRET_KEY=" + generate_secret_key())
    print("PASSWORD_SALT=" + generate_secret_key(16))
    print("ENCRYPTION_KEY=" + generate_encryption_key())
EOF

python3 generate_keys.py
```

---

## Base de Datos

### 1. Configuración PostgreSQL Standalone

```bash
# Instalación PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Configuración de usuario y base de datos
sudo -u postgres psql << 'EOF'
CREATE USER ecosistema_user WITH PASSWORD 'secure_password';
CREATE DATABASE ecosistema_prod OWNER ecosistema_user;
GRANT ALL PRIVILEGES ON DATABASE ecosistema_prod TO ecosistema_user;
ALTER USER ecosistema_user CREATEDB;
\q
EOF

# Configuración de PostgreSQL
sudo vim /etc/postgresql/14/main/postgresql.conf
# Agregar/modificar:
# listen_addresses = 'localhost'
# max_connections = 100
# shared_buffers = 256MB
# effective_cache_size = 1GB

sudo vim /etc/postgresql/14/main/pg_hba.conf
# Agregar:
# local   ecosistema_prod   ecosistema_user                     md5
# host    ecosistema_prod   ecosistema_user   127.0.0.1/32      md5

sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

### 2. Backup y Restauración

```bash
# Script de backup diario
cat > /opt/ecosistema/scripts/backup_db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/ecosistema/backups"
DB_NAME="ecosistema_prod"
DB_USER="ecosistema_user"

# Crear backup
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Limpiar backups antiguos (mantener 30 días)
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete

# Subir a S3 (opcional)
if [ ! -z "$AWS_ACCESS_KEY_ID" ]; then
    aws s3 cp $BACKUP_DIR/db_backup_$DATE.sql.gz s3://ecosistema-backups-prod/database/
fi
EOF

chmod +x /opt/ecosistema/scripts/backup_db.sh

# Agregar a crontab
echo "0 2 * * * /opt/ecosistema/scripts/backup_db.sh" | sudo crontab -u ecosistema -
```

---

## Deployment con Docker

### 1. Archivo docker-compose.prod.yml

```yaml
version: '3.8'

services:
  # Aplicación principal
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    restart: unless-stopped
    env_file:
      - .env.prod
    volumes:
      - ./app:/app
      - ./logs:/app/logs
      - uploads_data:/app/static/uploads
      - static_data:/app/static/dist
    depends_on:
      - postgres
      - redis
    networks:
      - ecosistema_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Nginx Proxy
  nginx:
    image: nginx:1.21-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx-sites:/etc/nginx/conf.d:ro
      - static_data:/var/www/static:ro
      - uploads_data:/var/www/uploads:ro
      - certbot_data:/etc/letsencrypt:ro
      - nginx_cache:/var/cache/nginx
    depends_on:
      - web
    networks:
      - ecosistema_network

  # Base de datos
  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    env_file:
      - .env.prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres-init:/docker-entrypoint-initdb.d
    networks:
      - ecosistema_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER -d $POSTGRES_DB"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Redis para cache y sesiones
  redis:
    image: redis:6-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - ecosistema_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Celery Worker
  celery_worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    restart: unless-stopped
    command: celery -A celery_worker.celery worker --loglevel=info --concurrency=4
    env_file:
      - .env.prod
    volumes:
      - ./app:/app
      - ./logs:/app/logs
      - uploads_data:/app/static/uploads
    depends_on:
      - postgres
      - redis
    networks:
      - ecosistema_network

  # Celery Beat (scheduler)
  celery_beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    restart: unless-stopped
    command: celery -A celery_worker.celery beat --loglevel=info --schedule=/tmp/celerybeat-schedule
    env_file:
      - .env.prod
    volumes:
      - ./app:/app
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - ecosistema_network

  # Celery Flower (monitor)
  celery_flower:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    restart: unless-stopped
    command: celery -A celery_worker.celery flower --port=5555
    env_file:
      - .env.prod
    ports:
      - "5555:5555"
    depends_on:
      - redis
    networks:
      - ecosistema_network

  # Certbot para SSL
  certbot:
    image: certbot/certbot
    volumes:
      - certbot_data:/etc/letsencrypt
      - certbot_www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

  # Monitoring - Prometheus
  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
    ports:
      - "9090:9090"
    networks:
      - ecosistema_network

  # Monitoring - Grafana
  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana-dashboard.json:/var/lib/grafana/dashboards/dashboard.json:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin_password_here
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    networks:
      - ecosistema_network

volumes:
  postgres_data:
  redis_data:
  uploads_data:
  static_data:
  certbot_data:
  certbot_www:
  nginx_cache:
  prometheus_data:
  grafana_data:

networks:
  ecosistema_network:
    driver: bridge
```

### 2. Dockerfile de Producción

```dockerfile
FROM python:3.11-slim-bullseye

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_APP=run.py

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN groupadd -r ecosistema && useradd -r -g ecosistema ecosistema

# Crear directorio de aplicación
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/static/uploads /app/instance && \
    chown -R ecosistema:ecosistema /app

# Instalar Gunicorn
RUN pip install gunicorn[gevent]==20.1.0

# Cambiar a usuario no-root
USER ecosistema

# Exponer puerto
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Comando por defecto
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
```

### 3. Configuración Gunicorn

```python
# gunicorn.conf.py
import os
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "gevent"
worker_connections = 1000
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = 50
preload_app = True
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 30))
keepalive = 2

# Logging
accesslog = "/app/logs/gunicorn_access.log"
errorlog = "/app/logs/gunicorn_error.log"
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'ecosistema_gunicorn'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = 'ecosistema'
group = 'ecosistema'
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None
```

### 4. Script de Deployment

```bash
#!/bin/bash
# deploy.sh

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuración
APP_DIR="/opt/ecosistema/app"
BACKUP_DIR="/opt/ecosistema/backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo -e "${GREEN}🚀 Iniciando deployment de Ecosistema de Emprendimiento${NC}"

# Función para logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.prod.yml" ]; then
    error "No se encontró docker-compose.prod.yml. ¿Estás en el directorio correcto?"
fi

# Verificar que existe el archivo .env.prod
if [ ! -f ".env.prod" ]; then
    error "No se encontró .env.prod. Crea el archivo de configuración primero."
fi

# 1. Backup de la aplicación actual
log "📦 Creando backup de la aplicación actual..."
if [ -d "$APP_DIR" ]; then
    sudo tar -czf "$BACKUP_DIR/app_backup_$DATE.tar.gz" -C "$(dirname $APP_DIR)" "$(basename $APP_DIR)"
    log "✅ Backup creado: $BACKUP_DIR/app_backup_$DATE.tar.gz"
fi

# 2. Backup de la base de datos
log "🗄️ Creando backup de la base de datos..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U ecosistema_user ecosistema_prod | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"
    log "✅ Backup de DB creado: $BACKUP_DIR/db_backup_$DATE.sql.gz"
fi

# 3. Detener servicios actuales
log "⏹️ Deteniendo servicios actuales..."
docker-compose -f docker-compose.prod.yml down

# 4. Actualizar código
log "📥 Actualizando código..."
git pull origin main

# 5. Construir nuevas imágenes
log "🔨 Construyendo nuevas imágenes Docker..."
docker-compose -f docker-compose.prod.yml build --no-cache

# 6. Ejecutar migraciones
log "🔄 Ejecutando migraciones de base de datos..."
docker-compose -f docker-compose.prod.yml run --rm web flask db upgrade

# 7. Iniciar servicios
log "🚀 Iniciando servicios..."
docker-compose -f docker-compose.prod.yml up -d

# 8. Verificar que los servicios estén funcionando
log "🔍 Verificando servicios..."
sleep 30

# Verificar aplicación web
if curl -f -s http://localhost/health > /dev/null; then
    log "✅ Aplicación web funcionando correctamente"
else
    error "❌ La aplicación web no responde correctamente"
fi

# Verificar base de datos
if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U ecosistema_user > /dev/null; then
    log "✅ Base de datos funcionando correctamente"
else
    error "❌ La base de datos no responde"
fi

# 9. Limpiar imágenes antiguas
log "🧹 Limpiando imágenes Docker antiguas..."
docker image prune -f

# 10. Verificar logs
log "📋 Últimas líneas de logs:"
docker-compose -f docker-compose.prod.yml logs --tail=20 web

log "🎉 Deployment completado exitosamente!"
log "📊 Monitoreo disponible en:"
log "   - Aplicación: https://yourdomain.com"
log "   - Grafana: http://yourdomain.com:3000"
log "   - Flower: http://yourdomain.com:5555"

# Enviar notificación (opcional)
if [ ! -z "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🚀 Deployment de Ecosistema de Emprendimiento completado exitosamente"}' \
        $SLACK_WEBHOOK_URL
fi
```

---

## Configuración de Servicios

### 1. Configuración Nginx

```nginx
# docker/nginx.conf
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        application/atom+xml
        application/geo+json
        application/javascript
        application/x-javascript
        application/json
        application/ld+json
        application/manifest+json
        application/rdf+xml
        application/rss+xml
        application/xhtml+xml
        application/xml
        font/eot
        font/otf
        font/ttf
        image/svg+xml
        text/css
        text/javascript
        text/plain
        text/xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https:; media-src 'self'; object-src 'none'; child-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;

    # Cache zones
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=static:10m max_size=1g inactive=1h use_temp_path=off;

    include /etc/nginx/conf.d/*.conf;
}
```

```nginx
# docker/nginx-sites/default.conf
upstream app {
    least_conn;
    server web:5000 max_fails=3 fail_timeout=30s;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Static files
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }

    location /uploads/ {
        alias /var/www/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # Auth endpoints (with stricter rate limiting)
    location ~ ^/(login|register|reset-password) {
        limit_req zone=login burst=5 nodelay;
        
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /socket.io/ {
        proxy_pass http://app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Health check
    location /health {
        proxy_pass http://app;
        access_log off;
    }

    # Main application
    location / {
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
        
        # Cache static responses
        proxy_cache static;
        proxy_cache_valid 200 1h;
        proxy_cache_valid 404 1m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_background_update on;
        proxy_cache_lock on;
    }
}
```

### 2. Configuración SSL con Let's Encrypt

```bash
#!/bin/bash
# setup_ssl.sh

DOMAIN="yourdomain.com"
EMAIL="admin@yourdomain.com"

# Verificar que Nginx esté funcionando
if ! docker-compose -f docker-compose.prod.yml ps nginx | grep -q "Up"; then
    echo "Error: Nginx no está funcionando"
    exit 1
fi

# Obtener certificado SSL inicial
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN

# Recargar Nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo "✅ SSL configurado correctamente para $DOMAIN"
```

---

## Monitoreo y Logging

### 1. Configuración Prometheus

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'ecosistema-app'
    static_configs:
      - targets: ['web:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:9113']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### 2. Configuración de Alertas

```yaml
# monitoring/alerts.yml
groups:
  - name: ecosistema_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(flask_http_request_exceptions_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Alta tasa de errores en la aplicación"
          description: "La tasa de errores es {{ $value }} errores por segundo"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(flask_http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Tiempo de respuesta alto"
          description: "El percentil 95 del tiempo de respuesta es {{ $value }} segundos"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Base de datos no disponible"
          description: "La base de datos PostgreSQL no está respondiendo"

      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Redis no disponible"
          description: "El servidor Redis no está respondiendo"

      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Uso alto de memoria"
          description: "El uso de memoria está en {{ $value }}%"

      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Uso alto de disco"
          description: "El uso de disco está en {{ $value }}%"

      - alert: ApplicationDown
        expr: up{job="ecosistema-app"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Aplicación no disponible"
          description: "La aplicación principal no está respondiendo"
```

### 3. Script de Logs Centralizados

```bash
#!/bin/bash
# scripts/setup_logging.sh

# Configurar logrotate para logs de aplicación
cat > /etc/logrotate.d/ecosistema << 'EOF'
/opt/ecosistema/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 ecosistema ecosistema
    postrotate
        docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml restart web > /dev/null 2>&1 || true
    endscript
}
EOF

# Configurar rsyslog para logs centralizados
cat > /etc/rsyslog.d/50-ecosistema.conf << 'EOF'
# Logs de aplicación Ecosistema
:programname, isequal, "ecosistema" /var/log/ecosistema/app.log
& stop

# Logs de Nginx
:programname, isequal, "nginx" /var/log/ecosistema/nginx.log
& stop
EOF

systemctl restart rsyslog

# Crear directorio de logs si no existe
mkdir -p /var/log/ecosistema
chown syslog:adm /var/log/ecosistema
```

---

## Backup y Recuperación

### 1. Script de Backup Completo

```bash
#!/bin/bash
# scripts/backup_complete.sh

set -e

# Configuración
BACKUP_DIR="/opt/ecosistema/backups"
S3_BUCKET="ecosistema-backups-prod"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Crear directorio de backup
mkdir -p "$BACKUP_DIR"

log "🚀 Iniciando backup completo del sistema..."

# 1. Backup de base de datos
log "📊 Backup de base de datos..."
docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml exec -T postgres \
    pg_dump -U ecosistema_user -Fc ecosistema_prod > "$BACKUP_DIR/db_backup_$DATE.dump"

# Verificar backup de DB
if [ ! -f "$BACKUP_DIR/db_backup_$DATE.dump" ]; then
    error "Falló el backup de la base de datos"
fi

log "✅ Backup de base de datos completado"

# 2. Backup de archivos subidos
log "📁 Backup de archivos subidos..."
if docker volume ls | grep -q ecosistema_uploads_data; then
    docker run --rm -v ecosistema_uploads_data:/source -v "$BACKUP_DIR":/backup \
        alpine tar -czf "/backup/uploads_backup_$DATE.tar.gz" -C /source .
    log "✅ Backup de archivos completado"
fi

# 3. Backup de configuración
log "⚙️ Backup de configuración..."
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
    -C /opt/ecosistema/app \
    .env.prod docker-compose.prod.yml docker/ monitoring/ \
    --exclude=docker/postgres-data \
    --exclude=docker/redis-data

log "✅ Backup de configuración completado"

# 4. Backup de logs
log "📋 Backup de logs..."
tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" -C /opt/ecosistema logs/
log "✅ Backup de logs completado"

# 5. Subir a S3 (si está configurado)
if [ ! -z "$AWS_ACCESS_KEY_ID" ] && [ ! -z "$S3_BUCKET" ]; then
    log "☁️ Subiendo backups a S3..."
    
    aws s3 cp "$BACKUP_DIR/db_backup_$DATE.dump" "s3://$S3_BUCKET/database/"
    aws s3 cp "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" "s3://$S3_BUCKET/uploads/"
    aws s3 cp "$BACKUP_DIR/config_backup_$DATE.tar.gz" "s3://$S3_BUCKET/config/"
    aws s3 cp "$BACKUP_DIR/logs_backup_$DATE.tar.gz" "s3://$S3_BUCKET/logs/"
    
    log "✅ Backups subidos a S3"
fi

# 6. Limpiar backups antiguos
log "🧹 Limpiando backups antiguos..."
find "$BACKUP_DIR" -name "*backup_*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 7. Verificar integridad de backups
log "🔍 Verificando integridad de backups..."

# Verificar DB backup
if ! pg_restore --list "$BACKUP_DIR/db_backup_$DATE.dump" > /dev/null 2>&1; then
    error "El backup de la base de datos está corrupto"
fi

# Verificar archivos
if ! tar -tzf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" > /dev/null 2>&1; then
    error "El backup de archivos está corrupto"
fi

log "✅ Verificación de integridad completada"

# 8. Reportar resultados
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "📊 Backup completado exitosamente"
log "   - Tamaño total: $BACKUP_SIZE"
log "   - Ubicación: $BACKUP_DIR"
log "   - Fecha: $(date)"

# Enviar notificación
if [ ! -z "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"✅ Backup de Ecosistema completado - Tamaño: $BACKUP_SIZE\"}" \
        "$SLACK_WEBHOOK_URL"
fi
```

### 2. Script de Restauración

```bash
#!/bin/bash
# scripts/restore.sh

set -e

# Verificar argumentos
if [ $# -ne 1 ]; then
    echo "Uso: $0 <fecha_backup_YYYYMMDD_HHMMSS>"
    echo "Ejemplo: $0 20240115_143000"
    exit 1
fi

BACKUP_DATE="$1"
BACKUP_DIR="/opt/ecosistema/backups"
APP_DIR="/opt/ecosistema/app"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Verificar que existen los backups
DB_BACKUP="$BACKUP_DIR/db_backup_$BACKUP_DATE.dump"
UPLOADS_BACKUP="$BACKUP_DIR/uploads_backup_$BACKUP_DATE.tar.gz"
CONFIG_BACKUP="$BACKUP_DIR/config_backup_$BACKUP_DATE.tar.gz"

if [ ! -f "$DB_BACKUP" ]; then
    error "No se encontró el backup de base de datos: $DB_BACKUP"
fi

log "🔄 Iniciando restauración del backup: $BACKUP_DATE"

# Confirmar con el usuario
warning "⚠️  ATENCIÓN: Esta operación sobrescribirá los datos actuales"
read -p "¿Estás seguro de que quieres continuar? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Operación cancelada"
    exit 0
fi

# 1. Crear backup de seguridad antes de restaurar
log "📦 Creando backup de seguridad de datos actuales..."
SAFETY_DATE=$(date +%Y%m%d_%H%M%S)
./backup_complete.sh
log "✅ Backup de seguridad creado"

# 2. Detener aplicación
log "⏹️ Deteniendo aplicación..."
cd "$APP_DIR"
docker-compose -f docker-compose.prod.yml down

# 3. Restaurar base de datos
log "📊 Restaurando base de datos..."
docker-compose -f docker-compose.prod.yml up -d postgres
sleep 10

# Eliminar base de datos actual y crear nueva
docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U ecosistema_user -c "DROP DATABASE IF EXISTS ecosistema_prod;"
docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U ecosistema_user -c "CREATE DATABASE ecosistema_prod OWNER ecosistema_user;"

# Restaurar datos
docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_restore -U ecosistema_user -d ecosistema_prod < "$DB_BACKUP"

log "✅ Base de datos restaurada"

# 4. Restaurar archivos subidos
if [ -f "$UPLOADS_BACKUP" ]; then
    log "📁 Restaurando archivos subidos..."
    docker-compose -f docker-compose.prod.yml down
    docker volume rm ecosistema_uploads_data 2>/dev/null || true
    docker volume create ecosistema_uploads_data
    docker run --rm -v ecosistema_uploads_data:/target -v "$BACKUP_DIR":/backup \
        alpine tar -xzf "/backup/uploads_backup_$BACKUP_DATE.tar.gz" -C /target
    log "✅ Archivos subidos restaurados"
fi

# 5. Restaurar configuración (opcional)
if [ -f "$CONFIG_BACKUP" ]; then
    read -p "¿Restaurar configuración también? (yes/no): " restore_config
    if [ "$restore_config" = "yes" ]; then
        log "⚙️ Restaurando configuración..."
        tar -xzf "$CONFIG_BACKUP" -C "$APP_DIR"
        log "✅ Configuración restaurada"
    fi
fi

# 6. Iniciar aplicación
log "🚀 Iniciando aplicación..."
docker-compose -f docker-compose.prod.yml up -d

# 7. Verificar que todo funciona
log "🔍 Verificando aplicación..."
sleep 30

if curl -f -s http://localhost/health > /dev/null; then
    log "✅ Aplicación funcionando correctamente"
else
    error "❌ La aplicación no responde después de la restauración"
fi

log "🎉 Restauración completada exitosamente!"
log "📊 Datos restaurados desde: $BACKUP_DATE"
log "🔒 Backup de seguridad disponible en: safety_backup_$SAFETY_DATE"
```

---

## Mantenimiento

### 1. Script de Mantenimiento Regular

```bash
#!/bin/bash
# scripts/maintenance.sh

set -e

GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log "🔧 Iniciando rutinas de mantenimiento..."

# 1. Limpiar logs antiguos
log "📋 Limpiando logs antiguos..."
find /opt/ecosistema/logs -name "*.log" -mtime +30 -delete
docker system prune -f

# 2. Optimizar base de datos
log "🗄️ Optimizando base de datos..."
docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml exec -T postgres \
    psql -U ecosistema_user -d ecosistema_prod -c "VACUUM ANALYZE;"

# 3. Limpiar caché Redis
log "🗃️ Limpiando cache Redis..."
docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml exec -T redis \
    redis-cli FLUSHDB

# 4. Actualizar certificados SSL
log "🔒 Verificando certificados SSL..."
docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml run --rm certbot renew

# 5. Verificar espacio en disco
log "💾 Verificando espacio en disco..."
df -h | grep -E '9[0-9]%|100%' && echo "⚠️ Espacio en disco bajo" || echo "✅ Espacio en disco OK"

# 6. Reiniciar servicios para aplicar updates
log "🔄 Reiniciando servicios..."
docker-compose -f /opt/ecosistema/app/docker-compose.prod.yml restart

log "✅ Mantenimiento completado"
```

### 2. Configurar Cron para Tareas Automáticas

```bash
# Configurar crontab para usuario ecosistema
sudo crontab -u ecosistema -e

# Agregar las siguientes líneas:
# Backup diario a las 2:00 AM
0 2 * * * /opt/ecosistema/scripts/backup_complete.sh >> /opt/ecosistema/logs/backup.log 2>&1

# Mantenimiento semanal los domingos a las 3:00 AM  
0 3 * * 0 /opt/ecosistema/scripts/maintenance.sh >> /opt/ecosistema/logs/maintenance.log 2>&1

# Verificación de salud cada 5 minutos
*/5 * * * * /opt/ecosistema/scripts/health_check.py >> /opt/ecosistema/logs/health.log 2>&1

# Limpiar logs antiguos diariamente
0 1 * * * find /opt/ecosistema/logs -name "*.log" -mtime +7 -delete

# Renovar certificados SSL mensualmente
0 4 1 * * /opt/ecosistema/scripts/renew_ssl.sh >> /opt/ecosistema/logs/ssl.log 2>&1
```

---

## Troubleshooting

### 1. Problemas Comunes y Soluciones

#### Aplicación no responde
```bash
# Verificar logs
docker-compose -f docker-compose.prod.yml logs web

# Reiniciar servicio
docker-compose -f docker-compose.prod.yml restart web

# Verificar recursos
docker stats
```

#### Base de datos no conecta
```bash
# Verificar estado de PostgreSQL
docker-compose -f docker-compose.prod.yml ps postgres

# Verificar logs de DB
docker-compose -f docker-compose.prod.yml logs postgres

# Conectar manualmente
docker-compose -f docker-compose.prod.yml exec postgres psql -U ecosistema_user -d ecosistema_prod
```

#### Problemas de SSL
```bash
# Verificar certificados
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/cert.pem -text -noout

# Renovar certificados
docker-compose -f docker-compose.prod.yml run --rm certbot renew

# Verificar configuración Nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

#### Alto uso de recursos
```bash
# Verificar uso de memoria
free -h

# Verificar uso de CPU
top

# Verificar procesos Docker
docker stats

# Optimizar base de datos
docker-compose -f docker-compose.prod.yml exec postgres psql -U ecosistema_user -d ecosistema_prod -c "VACUUM FULL ANALYZE;"
```

### 2. Scripts de Diagnóstico

```bash
#!/bin/bash
# scripts/health_check.py

import requests
import psycopg2
import redis
import json
import sys
from datetime import datetime

def check_web_app():
    try:
        response = requests.get('http://localhost/health', timeout=10)
        return response.status_code == 200
    except:
        return False

def check_database():
    try:
        conn = psycopg2.connect(
            host='localhost',
            database='ecosistema_prod',
            user='ecosistema_user',
            password='secure_password'
        )
        conn.close()
        return True
    except:
        return False

def check_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True
    except:
        return False

def main():
    timestamp = datetime.now().isoformat()
    
    checks = {
        'timestamp': timestamp,
        'web_app': check_web_app(),
        'database': check_database(),
        'redis': check_redis()
    }
    
    # Log results
    print(json.dumps(checks))
    
    # Exit with error if any check fails
    if not all([checks['web_app'], checks['database'], checks['redis']]):
        sys.exit(1)

if __name__ == '__main__':
    main()
```

### 3. Checklist de Deployment

**Pre-deployment:**
- [ ] Backup completo realizado
- [ ] Variables de entorno configuradas
- [ ] Certificados SSL válidos
- [ ] DNS configurado correctamente
- [ ] Recursos del servidor suficientes

**During deployment:**
- [ ] Servicios detenidos correctamente
- [ ] Imágenes construidas sin errores
- [ ] Migraciones ejecutadas exitosamente
- [ ] Servicios iniciados en orden correcto

**Post-deployment:**
- [ ] Health checks pasando
- [ ] SSL funcionando
- [ ] Logs sin errores críticos
- [ ] Métricas normales
- [ ] Backup post-deployment realizado

---

## Comandos Útiles

### Docker
```bash
# Ver logs en tiempo real
docker-compose -f docker-compose.prod.yml logs -f web

# Acceder a contenedor
docker-compose -f docker-compose.prod.yml exec web bash

# Verificar recursos
docker stats

# Limpiar sistema
docker system prune -a
```

### Base de datos
```bash
# Backup manual
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U ecosistema_user ecosistema_prod > backup.sql

# Restaurar
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U ecosistema_user ecosistema_prod < backup.sql

# Acceder a PostgreSQL
docker-compose -f docker-compose.prod.yml exec postgres psql -U ecosistema_user -d ecosistema_prod
```

### Nginx
```bash
# Recargar configuración
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

# Verificar configuración
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Ver logs de acceso
docker-compose -f docker-compose.prod.yml logs nginx
```

---

## Contacto y Soporte

Para problemas de deployment o consultas técnicas:
- **Email:** devops@yourcompany.com
- **Slack:** #ecosistema-deployment
- **Documentación:** https://docs.yourcompany.com
- **Monitoring:** https://grafana.yourcompany.com

---

*Última actualización: $(date)*