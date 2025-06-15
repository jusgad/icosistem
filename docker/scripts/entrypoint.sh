#!/bin/bash
# =============================================================================
# Docker Entrypoint Script - Ecosistema de Emprendimiento
# =============================================================================
# 
# Script de inicialización completo para contenedores Docker que maneja:
# - Verificación de dependencias y configuración
# - Inicialización de base de datos y migraciones
# - Configuración de permisos y seguridad
# - Manejo de secretos y variables de entorno
# - Health checks y monitoring
# - Graceful shutdown y manejo de señales
# - Diferentes modos de ejecución (app, worker, beat, etc.)
# - Logging estructurado y debugging
# - Inicialización de datos y assets
# - Backup y recovery procedures
#
# Uso:
#   docker run image [command] [args...]
#   
# Comandos disponibles:
#   app, webapp, server    - Ejecutar aplicación Flask
#   worker                 - Ejecutar Celery worker
#   beat, scheduler        - Ejecutar Celery beat
#   flower                 - Ejecutar Flower monitoring
#   shell, bash           - Shell interactivo
#   migrate               - Ejecutar migraciones
#   seed                  - Crear datos iniciales
#   test                  - Ejecutar tests
#   health                - Health check
#   backup                - Backup de base de datos
#   restore               - Restaurar backup
#
# Autor: Sistema de Emprendimiento
# Version: 1.0.0
# =============================================================================

set -e  # Exit on any error

# -----------------------------------------------------------------------------
# Global Variables and Configuration
# -----------------------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_VERSION="1.0.0"
readonly APP_USER="appuser"
readonly APP_GROUP="appgroup"
readonly APP_DIR="/app"
readonly LOG_DIR="/app/logs"
readonly BACKUP_DIR="/app/backups"
readonly UPLOAD_DIR="/app/uploads"
readonly TEMP_DIR="/app/temp"

# Environment detection
ENVIRONMENT="${FLASK_ENV:-${ENVIRONMENT:-production}}"
DEBUG="${FLASK_DEBUG:-${DEBUG:-0}}"
IS_DEVELOPMENT=$([[ "$ENVIRONMENT" == "development" ]] && echo 1 || echo 0)

# Process management
MAIN_PID=$$
CHILD_PIDS=()
SHUTDOWN_INITIATED=0

# Health check settings
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-30}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-10}"
HEALTH_CHECK_RETRIES="${HEALTH_CHECK_RETRIES:-3}"

# -----------------------------------------------------------------------------
# Color Codes for Logging
# -----------------------------------------------------------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Logging Functions
# -----------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local color=""
    
    case "$level" in
        "ERROR"|"FATAL")
            color="$RED"
            ;;
        "WARN"|"WARNING")
            color="$YELLOW"
            ;;
        "INFO")
            color="$GREEN"
            ;;
        "DEBUG")
            color="$BLUE"
            ;;
        "SUCCESS")
            color="$GREEN"
            ;;
        *)
            color="$NC"
            ;;
    esac
    
    # Log to stdout with color (for docker logs)
    echo -e "${color}[$timestamp] [$level] [$$] $message${NC}" >&1
    
    # Log to file without color (if directory exists)
    if [[ -d "$LOG_DIR" ]]; then
        echo "[$timestamp] [$level] [$$] $message" >> "$LOG_DIR/entrypoint.log"
    fi
}

log_info() {
    log "INFO" "$@"
}

log_warn() {
    log "WARN" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_debug() {
    [[ "$DEBUG" == "1" ]] && log "DEBUG" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

log_fatal() {
    log "FATAL" "$@"
    exit 1
}

# -----------------------------------------------------------------------------
# Banner and Information Display
# -----------------------------------------------------------------------------
show_banner() {
    echo -e "${BLUE}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                          ECOSISTEMA EMPRENDIMIENTO                          ║
║                              Docker Container                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    log_info "🚀 Container starting..."
    log_info "📦 Script: $SCRIPT_NAME v$SCRIPT_VERSION"
    log_info "🌍 Environment: $ENVIRONMENT"
    log_info "🐛 Debug Mode: $([ "$DEBUG" == "1" ] && echo "Enabled" || echo "Disabled")"
    log_info "👤 User: $(whoami) (UID: $(id -u), GID: $(id -g))"
    log_info "🏠 Working Directory: $(pwd)"
    log_info "🕐 Timestamp: $(date)"
    log_info "🔧 Command: $*"
    echo
}

# -----------------------------------------------------------------------------
# Signal Handlers for Graceful Shutdown
# -----------------------------------------------------------------------------
cleanup() {
    if [[ $SHUTDOWN_INITIATED -eq 1 ]]; then
        return
    fi
    
    SHUTDOWN_INITIATED=1
    log_warn "🛑 Shutdown signal received. Initiating graceful shutdown..."
    
    # Kill child processes
    for pid in "${CHILD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "🔄 Terminating child process $pid..."
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    # Wait for children to exit
    local timeout=30
    local count=0
    while [[ $count -lt $timeout ]]; do
        local running_children=0
        for pid in "${CHILD_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                ((running_children++))
            fi
        done
        
        if [[ $running_children -eq 0 ]]; then
            break
        fi
        
        log_info "⏳ Waiting for $running_children child process(es) to exit... ($count/$timeout)"
        sleep 1
        ((count++))
    done
    
    # Force kill if still running
    for pid in "${CHILD_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_warn "⚡ Force killing process $pid"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    
    log_success "✅ Graceful shutdown completed"
    exit 0
}

# Trap signals
trap cleanup SIGTERM SIGINT SIGQUIT

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

is_number() {
    [[ $1 =~ ^[0-9]+$ ]]
}

wait_for_service() {
    local service_name="$1"
    local host="$2"
    local port="$3"
    local timeout="${4:-60}"
    local interval="${5:-2}"
    
    log_info "⏳ Waiting for $service_name at $host:$port (timeout: ${timeout}s)..."
    
    local count=0
    while [[ $count -lt $timeout ]]; do
        if timeout 1 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
            log_success "✅ $service_name is ready!"
            return 0
        fi
        
        log_debug "🔄 $service_name not ready... retrying in ${interval}s ($count/$timeout)"
        sleep "$interval"
        ((count += interval))
    done
    
    log_error "❌ Timeout waiting for $service_name at $host:$port"
    return 1
}

check_database_connection() {
    local retries="${1:-30}"
    local interval="${2:-2}"
    
    if [[ -z "$DATABASE_URL" ]]; then
        log_warn "⚠️ DATABASE_URL not set, skipping database check"
        return 0
    fi
    
    log_info "🗄️ Checking database connection..."
    
    for ((i=1; i<=retries; i++)); do
        if python << 'EOF'
import os
import sys
from urllib.parse import urlparse
import time

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("No DATABASE_URL provided")
        sys.exit(1)
    
    # Handle postgres:// vs postgresql:// 
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    engine = create_engine(db_url, pool_pre_ping=True)
    
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        row = result.fetchone()
        if row and row[0] == 1:
            print("Database connection successful!")
            sys.exit(0)
        else:
            print("Database query failed")
            sys.exit(1)
            
except ImportError as e:
    print(f"Missing dependencies: {e}")
    sys.exit(1)
except OperationalError as e:
    print(f"Database connection failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
EOF
        then
            log_success "✅ Database connection established!"
            return 0
        fi
        
        log_debug "🔄 Database not ready... retrying ($i/$retries)"
        sleep "$interval"
    done
    
    log_error "❌ Failed to connect to database after $retries attempts"
    return 1
}

check_redis_connection() {
    local retries="${1:-20}"
    local interval="${2:-2}"
    
    if [[ -z "$REDIS_URL" ]]; then
        log_warn "⚠️ REDIS_URL not set, skipping Redis check"
        return 0
    fi
    
    log_info "🔴 Checking Redis connection..."
    
    for ((i=1; i<=retries; i++)); do
        if python << 'EOF'
import os
import sys
from urllib.parse import urlparse

try:
    import redis
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Parse Redis URL
    parsed = urlparse(redis_url)
    
    r = redis.Redis(
        host=parsed.hostname or 'localhost',
        port=parsed.port or 6379,
        db=int(parsed.path.lstrip('/')) if parsed.path else 0,
        password=parsed.password,
        socket_timeout=5,
        socket_connect_timeout=5
    )
    
    # Test connection
    r.ping()
    print("Redis connection successful!")
    sys.exit(0)
    
except ImportError:
    print("Redis module not available")
    sys.exit(1)
except Exception as e:
    print(f"Redis connection failed: {e}")
    sys.exit(1)
EOF
        then
            log_success "✅ Redis connection established!"
            return 0
        fi
        
        log_debug "🔄 Redis not ready... retrying ($i/$retries)"
        sleep "$interval"
    done
    
    log_error "❌ Failed to connect to Redis after $retries attempts"
    return 1
}

# -----------------------------------------------------------------------------
# Environment and Configuration Setup
# -----------------------------------------------------------------------------
setup_environment() {
    log_info "🔧 Setting up environment..."
    
    # Set Python environment
    export PYTHONUNBUFFERED=1
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH="${PYTHONPATH:-}:$APP_DIR"
    
    # Set Flask environment
    export FLASK_APP="${FLASK_APP:-wsgi.py}"
    export FLASK_ENV="$ENVIRONMENT"
    export FLASK_DEBUG="$DEBUG"
    
    # Create required directories
    local directories=(
        "$LOG_DIR"
        "$BACKUP_DIR"
        "$UPLOAD_DIR"
        "$TEMP_DIR"
        "$APP_DIR/instance"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_debug "📁 Creating directory: $dir"
            mkdir -p "$dir"
        fi
    done
    
    # Set permissions if running as root (for setup)
    if [[ $(id -u) -eq 0 ]]; then
        log_info "👑 Running as root, setting up permissions..."
        
        # Ensure app user exists
        if ! id "$APP_USER" &>/dev/null; then
            log_info "👤 Creating app user: $APP_USER"
            groupadd -r "$APP_GROUP" 2>/dev/null || true
            useradd -r -g "$APP_GROUP" -d "$APP_DIR" -s /bin/bash "$APP_USER" 2>/dev/null || true
        fi
        
        # Set ownership
        chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"
        
        # Set directory permissions
        chmod 755 "$APP_DIR"
        chmod 775 "$LOG_DIR" "$UPLOAD_DIR" "$TEMP_DIR" "$BACKUP_DIR"
        chmod 755 "$APP_DIR/instance"
        
        log_success "✅ Permissions configured"
    fi
    
    log_success "✅ Environment setup completed"
}

# -----------------------------------------------------------------------------
# Secrets and Configuration Management
# -----------------------------------------------------------------------------
load_secrets() {
    log_info "🔐 Loading secrets and configuration..."
    
    local secrets_dir="/run/secrets"
    local env_file="$APP_DIR/.env"
    
    # Load Docker secrets if available
    if [[ -d "$secrets_dir" ]]; then
        for secret_file in "$secrets_dir"/*; do
            if [[ -f "$secret_file" ]]; then
                local secret_name=$(basename "$secret_file")
                local env_var_name=$(echo "$secret_name" | tr '[:lower:]' '[:upper:]')
                
                # Read secret value
                local secret_value
                secret_value=$(cat "$secret_file")
                
                # Export as environment variable
                export "$env_var_name=$secret_value"
                
                log_debug "🔑 Loaded secret: $secret_name -> $env_var_name"
            fi
        done
    fi
    
    # Load .env file if it exists
    if [[ -f "$env_file" ]]; then
        log_debug "📄 Loading environment file: $env_file"
        set -o allexport
        source "$env_file"
        set +o allexport
    fi
    
    # Validate critical environment variables
    local required_vars=()
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        required_vars+=(
            "SECRET_KEY"
            "DATABASE_URL"
        )
    fi
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            log_fatal "❌ Required environment variable not set: $var"
        fi
    done
    
    log_success "✅ Secrets and configuration loaded"
}

# -----------------------------------------------------------------------------
# Database Operations
# -----------------------------------------------------------------------------
run_migrations() {
    log_info "🗄️ Running database migrations..."
    
    if ! command_exists flask; then
        log_error "❌ Flask command not found"
        return 1
    fi
    
    # Check if migrations directory exists
    if [[ ! -d "$APP_DIR/migrations" ]]; then
        log_info "📝 Initializing database migrations..."
        if ! flask db init; then
            log_error "❌ Failed to initialize migrations"
            return 1
        fi
    fi
    
    # Check if there are pending migrations
    local migration_status
    migration_status=$(flask db current 2>/dev/null || echo "none")
    
    if [[ "$migration_status" == "none" ]] || [[ "$migration_status" == "" ]]; then
        log_info "🆕 No current migration found, creating initial migration..."
        if ! flask db migrate -m "Initial migration"; then
            log_warn "⚠️ Failed to create migration (this might be normal if tables already exist)"
        fi
    fi
    
    # Run migrations
    log_info "⬆️ Applying database migrations..."
    if flask db upgrade; then
        log_success "✅ Database migrations completed successfully"
        return 0
    else
        log_error "❌ Database migrations failed"
        return 1
    fi
}

create_initial_data() {
    log_info "🌱 Creating initial data..."
    
    local seed_script="$APP_DIR/scripts/seed_data.py"
    
    if [[ -f "$seed_script" ]]; then
        local seed_args=""
        
        if [[ "$IS_DEVELOPMENT" == "1" ]]; then
            seed_args="--development"
        fi
        
        if python "$seed_script" $seed_args; then
            log_success "✅ Initial data created successfully"
        else
            log_warn "⚠️ Failed to create initial data (this might be normal if data already exists)"
        fi
    else
        log_warn "⚠️ Seed script not found at $seed_script"
    fi
}

backup_database() {
    log_info "💾 Creating database backup..."
    
    if [[ -z "$DATABASE_URL" ]]; then
        log_error "❌ DATABASE_URL not set, cannot create backup"
        return 1
    fi
    
    local backup_file="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"
    
    # Run backup
    if python << EOF
import os
import subprocess
from urllib.parse import urlparse

db_url = os.environ.get('DATABASE_URL')
parsed = urlparse(db_url)

if parsed.scheme.startswith('postgresql'):
    # PostgreSQL backup
    env = os.environ.copy()
    env['PGPASSWORD'] = parsed.password or ''
    
    cmd = [
        'pg_dump',
        '-h', parsed.hostname or 'localhost',
        '-p', str(parsed.port or 5432),
        '-U', parsed.username or 'postgres',
        '-d', parsed.path.lstrip('/') or 'postgres',
        '--clean',
        '--no-owner',
        '--no-privileges',
        '-f', '$backup_file'
    ]
    
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        print("PostgreSQL backup completed successfully")
    else:
        print(f"PostgreSQL backup failed: {result.stderr}")
        exit(1)
        
elif parsed.scheme.startswith('sqlite'):
    # SQLite backup
    import shutil
    db_path = parsed.path
    shutil.copy2(db_path, '$backup_file')
    print("SQLite backup completed successfully")
    
else:
    print(f"Unsupported database type: {parsed.scheme}")
    exit(1)
EOF
    then
        log_success "✅ Database backup created: $backup_file"
        
        # Cleanup old backups (keep last 10)
        find "$BACKUP_DIR" -name "db_backup_*.sql" -type f | sort -r | tail -n +11 | xargs rm -f
        
        return 0
    else
        log_error "❌ Database backup failed"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Asset and Static File Management
# -----------------------------------------------------------------------------
compile_assets() {
    log_info "🎨 Compiling frontend assets..."
    
    # Check if Node.js assets need compilation
    if [[ -f "$APP_DIR/package.json" ]]; then
        log_info "📦 Installing/updating npm dependencies..."
        
        cd "$APP_DIR"
        
        # Install dependencies if node_modules doesn't exist or package.json is newer
        if [[ ! -d "node_modules" ]] || [[ "package.json" -nt "node_modules" ]]; then
            if npm ci --only=production; then
                log_success "✅ npm dependencies installed"
            else
                log_warn "⚠️ npm install failed, continuing without assets compilation"
                return 1
            fi
        fi
        
        # Compile assets for production
        if [[ "$ENVIRONMENT" == "production" ]]; then
            if npm run build:prod; then
                log_success "✅ Production assets compiled"
            else
                log_warn "⚠️ Asset compilation failed"
                return 1
            fi
        elif [[ "$IS_DEVELOPMENT" == "1" ]]; then
            if npm run build:dev; then
                log_success "✅ Development assets compiled"
            else
                log_warn "⚠️ Development asset compilation failed"
                return 1
            fi
        fi
    else
        log_debug "📦 No package.json found, skipping asset compilation"
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# Health Check Functions
# -----------------------------------------------------------------------------
run_health_check() {
    local timeout="${1:-$HEALTH_CHECK_TIMEOUT}"
    
    log_info "🏥 Running health check..."
    
    local health_script="$APP_DIR/scripts/health_check.py"
    
    if [[ -f "$health_script" ]]; then
        if timeout "$timeout" python "$health_script" --quiet; then
            log_success "✅ Health check passed"
            return 0
        else
            log_error "❌ Health check failed"
            return 1
        fi
    else
        log_warn "⚠️ Health check script not found, using basic check"
        
        # Basic health check - try to import the app
        if timeout "$timeout" python -c "from app import create_app; app = create_app(); print('App import successful')"; then
            log_success "✅ Basic health check passed"
            return 0
        else
            log_error "❌ Basic health check failed"
            return 1
        fi
    fi
}

continuous_health_check() {
    log_info "🏥 Starting continuous health monitoring..."
    
    while true; do
        sleep "$HEALTH_CHECK_INTERVAL"
        
        if [[ $SHUTDOWN_INITIATED -eq 1 ]]; then
            break
        fi
        
        if ! run_health_check; then
            log_error "❌ Health check failed, but continuing to run..."
            # In production, you might want to exit here
            # exit 1
        fi
    done
}

# -----------------------------------------------------------------------------
# Application Startup Functions
# -----------------------------------------------------------------------------
start_flask_app() {
    log_info "🚀 Starting Flask application..."
    
    local port="${PORT:-8000}"
    local host="${HOST:-0.0.0.0}"
    local workers="${WEB_CONCURRENCY:-4}"
    local worker_class="${WORKER_CLASS:-gevent}"
    local timeout="${WORKER_TIMEOUT:-120}"
    local bind="$host:$port"
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        # Production: Use Gunicorn
        log_info "🏭 Starting production server with Gunicorn..."
        log_info "📍 Binding to: $bind"
        log_info "👷 Workers: $workers ($worker_class)"
        log_info "⏱️ Timeout: ${timeout}s"
        
        exec gunicorn \
            --bind "$bind" \
            --workers "$workers" \
            --worker-class "$worker_class" \
            --timeout "$timeout" \
            --keepalive 2 \
            --max-requests 1000 \
            --max-requests-jitter 100 \
            --preload \
            --access-logfile - \
            --error-logfile - \
            --log-level info \
            --capture-output \
            "wsgi:app"
    else
        # Development: Use Flask dev server
        log_info "🔧 Starting development server..."
        log_info "📍 URL: http://$host:$port"
        log_info "🐛 Debug: $DEBUG"
        
        export FLASK_RUN_HOST="$host"
        export FLASK_RUN_PORT="$port"
        
        exec flask run
    fi
}

start_celery_worker() {
    log_info "👷 Starting Celery worker..."
    
    local concurrency="${CELERY_CONCURRENCY:-4}"
    local loglevel="${CELERY_LOG_LEVEL:-info}"
    local queues="${CELERY_QUEUES:-default}"
    
    log_info "⚙️ Concurrency: $concurrency"
    log_info "📝 Log level: $loglevel"
    log_info "📋 Queues: $queues"
    
    exec celery -A celery_worker.celery worker \
        --loglevel="$loglevel" \
        --concurrency="$concurrency" \
        --queues="$queues" \
        --without-gossip \
        --without-mingle \
        --without-heartbeat
}

start_celery_beat() {
    log_info "⏰ Starting Celery beat scheduler..."
    
    local loglevel="${CELERY_LOG_LEVEL:-info}"
    local schedule_file="${CELERY_SCHEDULE_FILE:-/app/celerybeat-schedule}"
    
    log_info "📝 Log level: $loglevel"
    log_info "📅 Schedule file: $schedule_file"
    
    exec celery -A celery_worker.celery beat \
        --loglevel="$loglevel" \
        --schedule="$schedule_file" \
        --pidfile=/app/celerybeat.pid
}

start_flower() {
    log_info "🌸 Starting Flower monitoring..."
    
    local port="${FLOWER_PORT:-5555}"
    local url_prefix="${FLOWER_URL_PREFIX:-}"
    
    log_info "📍 Port: $port"
    log_info "🔗 URL prefix: $url_prefix"
    
    local cmd="celery -A celery_worker.celery flower --port=$port"
    
    if [[ -n "$url_prefix" ]]; then
        cmd="$cmd --url_prefix=$url_prefix"
    fi
    
    exec $cmd
}

# -----------------------------------------------------------------------------
# Main Initialization Function
# -----------------------------------------------------------------------------
initialize_container() {
    log_info "🔄 Initializing container..."
    
    # Setup environment
    setup_environment
    
    # Load secrets and configuration
    load_secrets
    
    # Wait for dependencies
    if [[ "${SKIP_DB_WAIT:-0}" != "1" ]]; then
        check_database_connection
    fi
    
    if [[ "${SKIP_REDIS_WAIT:-0}" != "1" ]]; then
        check_redis_connection
    fi
    
    # Run migrations if enabled
    if [[ "${AUTO_MIGRATE:-0}" == "1" ]]; then
        run_migrations
    fi
    
    # Create initial data if enabled
    if [[ "${CREATE_INITIAL_DATA:-0}" == "1" ]]; then
        create_initial_data
    fi
    
    # Compile assets if enabled
    if [[ "${COMPILE_ASSETS:-0}" == "1" ]]; then
        compile_assets
    fi
    
    # Run initial health check
    if [[ "${SKIP_HEALTH_CHECK:-0}" != "1" ]]; then
        run_health_check
    fi
    
    log_success "✅ Container initialization completed"
}

# -----------------------------------------------------------------------------
# Command Handlers
# -----------------------------------------------------------------------------
handle_app_command() {
    initialize_container
    
    # Start continuous health monitoring in background if enabled
    if [[ "${CONTINUOUS_HEALTH_CHECK:-0}" == "1" ]]; then
        continuous_health_check &
        CHILD_PIDS+=($!)
    fi
    
    start_flask_app
}

handle_worker_command() {
    initialize_container
    start_celery_worker
}

handle_beat_command() {
    initialize_container
    start_celery_beat
}

handle_flower_command() {
    setup_environment
    load_secrets
    check_redis_connection
    start_flower
}

handle_shell_command() {
    setup_environment
    load_secrets
    
    log_info "🐚 Starting interactive shell..."
    
    if [[ $# -gt 1 ]]; then
        # Execute specific shell command
        shift
        exec "$@"
    else
        # Start interactive shell
        if command_exists flask; then
            log_info "🌶️ Starting Flask shell..."
            exec flask shell
        else
            log_info "🐍 Starting Python shell..."
            exec python
        fi
    fi
}

handle_migrate_command() {
    setup_environment
    load_secrets
    check_database_connection
    run_migrations
}

handle_seed_command() {
    setup_environment
    load_secrets
    check_database_connection
    create_initial_data
}

handle_test_command() {
    setup_environment
    load_secrets
    
    log_info "🧪 Running tests..."
    
    if command_exists pytest; then
        exec pytest tests/ -v "$@"
    elif command_exists python; then
        exec python -m unittest discover tests/ -v
    else
        log_fatal "❌ No test runner found"
    fi
}

handle_health_command() {
    setup_environment
    load_secrets
    run_health_check
}

handle_backup_command() {
    setup_environment
    load_secrets
    check_database_connection
    backup_database
}

handle_restore_command() {
    if [[ $# -lt 2 ]]; then
        log_fatal "❌ Usage: $0 restore <backup_file>"
    fi
    
    local backup_file="$2"
    
    if [[ ! -f "$backup_file" ]]; then
        log_fatal "❌ Backup file not found: $backup_file"
    fi
    
    setup_environment
    load_secrets
    check_database_connection
    
    log_info "🔄 Restoring database from: $backup_file"
    
    # Implementation depends on database type
    log_warn "⚠️ Database restore not implemented yet"
}

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
main() {
    # Show banner
    show_banner
    
    # Handle the case where no command is provided
    local command="${1:-app}"
    
    case "$command" in
        "app"|"webapp"|"server"|"gunicorn"|"flask")
            handle_app_command "$@"
            ;;
        "worker"|"celery-worker")
            handle_worker_command "$@"
            ;;
        "beat"|"scheduler"|"celery-beat")
            handle_beat_command "$@"
            ;;
        "flower"|"monitoring")
            handle_flower_command "$@"
            ;;
        "shell"|"bash"|"sh")
            handle_shell_command "$@"
            ;;
        "migrate"|"migration"|"db-migrate")
            handle_migrate_command "$@"
            ;;
        "seed"|"seed-data"|"initial-data")
            handle_seed_command "$@"
            ;;
        "test"|"tests"|"pytest")
            shift
            handle_test_command "$@"
            ;;
        "health"|"health-check"|"healthcheck")
            handle_health_command "$@"
            ;;
        "backup"|"db-backup")
            handle_backup_command "$@"
            ;;
        "restore"|"db-restore")
            handle_restore_command "$@"
            ;;
        "help"|"--help"|"-h")
            show_help
            exit 0
            ;;
        "version"|"--version"|"-v")
            echo "$SCRIPT_NAME version $SCRIPT_VERSION"
            exit 0
            ;;
        *)
            # Try to execute as a direct command
            if command_exists "$command"; then
                log_info "🔧 Executing command: $*"
                setup_environment
                load_secrets
                exec "$@"
            else
                log_error "❌ Unknown command: $command"
                show_help
                exit 1
            fi
            ;;
    esac
}

# -----------------------------------------------------------------------------
# Help Function
# -----------------------------------------------------------------------------
show_help() {
    cat << EOF
Docker Entrypoint Script for Ecosistema de Emprendimiento

USAGE:
    $SCRIPT_NAME [COMMAND] [ARGS...]

COMMANDS:
    app, webapp, server     Start the Flask web application
    worker                  Start Celery worker for background tasks
    beat, scheduler         Start Celery beat scheduler
    flower                  Start Flower monitoring interface
    shell, bash            Start interactive shell (Flask shell if available)
    migrate                Run database migrations
    seed                   Create initial data
    test [ARGS...]         Run tests
    health                 Run health check
    backup                 Create database backup
    restore <file>         Restore database from backup
    help                   Show this help message
    version                Show version information

ENVIRONMENT VARIABLES:
    FLASK_ENV              Environment (development/production)
    FLASK_DEBUG            Debug mode (0/1)
    DATABASE_URL           Database connection string
    REDIS_URL              Redis connection string
    AUTO_MIGRATE           Run migrations automatically (0/1)
    CREATE_INITIAL_DATA    Create initial data (0/1)
    COMPILE_ASSETS         Compile frontend assets (0/1)
    SKIP_DB_WAIT           Skip waiting for database (0/1)
    SKIP_REDIS_WAIT        Skip waiting for Redis (0/1)
    SKIP_HEALTH_CHECK      Skip initial health check (0/1)
    CONTINUOUS_HEALTH_CHECK Enable continuous health monitoring (0/1)

EXAMPLES:
    $SCRIPT_NAME app                    # Start web application
    $SCRIPT_NAME worker                 # Start Celery worker
    $SCRIPT_NAME shell                  # Start Flask shell
    $SCRIPT_NAME test --verbose         # Run tests with verbose output
    $SCRIPT_NAME migrate                # Run database migrations
    $SCRIPT_NAME backup                 # Create database backup

For more information, visit: https://github.com/your-org/ecosistema-emprendimiento
EOF
}

# -----------------------------------------------------------------------------
# Script Execution
# -----------------------------------------------------------------------------
# Ensure we're in the app directory
cd "$APP_DIR" || log_fatal "❌ Failed to change to app directory: $APP_DIR"

# Start main function with all arguments
main "$@"