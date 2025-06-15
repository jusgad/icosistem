#!/bin/bash
# =============================================================================
# wait-for-it.sh - Service Dependency Manager
# =============================================================================
# 
# Script robusto para esperar la disponibilidad de servicios TCP antes de
# ejecutar comandos. Especialmente útil en entornos Docker y Kubernetes
# para manejar dependencias entre servicios.
# 
# Características:
# - Soporte para múltiples hosts y puertos
# - Timeouts configurables
# - Intervalos de retry personalizables
# - Logging estructurado con niveles
# - Validación de entrada robusta
# - Compatibilidad con diferentes shells
# - Soporte para IPv4 e IPv6
# - Ejecución paralela de checks
# - Health checks personalizados
# - Integración con Docker y Kubernetes
#
# Uso:
#   wait-for-it.sh host:port [host:port...] [options] [-- command args...]
#   wait-for-it.sh -h host -p port [options] [-- command args...]
#
# Ejemplos:
#   wait-for-it.sh db:5432 -- echo "Database is ready"
#   wait-for-it.sh db:5432 redis:6379 -t 60 -- start-app.sh
#   wait-for-it.sh -h localhost -p 8080 -t 30 -s -- curl localhost:8080
#
# Autor: Sistema de Emprendimiento
# Version: 2.0.0
# Basado en wait-for-it de vishnubob
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Script Metadata and Constants
# -----------------------------------------------------------------------------
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_AUTHOR="Sistema de Emprendimiento"

# Default configuration
readonly DEFAULT_TIMEOUT=15
readonly DEFAULT_INTERVAL=1
readonly DEFAULT_RETRIES=0
readonly DEFAULT_QUIET=0
readonly DEFAULT_STRICT=0
readonly DEFAULT_PARALLEL=0

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m' # No Color

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_TIMEOUT=1
readonly EXIT_INVALID_ARGS=2
readonly EXIT_CONNECTION_FAILED=3
readonly EXIT_COMMAND_FAILED=4

# -----------------------------------------------------------------------------
# Global Variables
# -----------------------------------------------------------------------------
CMDNAME=""
HOSTS=()
TIMEOUT=$DEFAULT_TIMEOUT
INTERVAL=$DEFAULT_INTERVAL
RETRIES=$DEFAULT_RETRIES
QUIET=$DEFAULT_QUIET
STRICT=$DEFAULT_STRICT
PARALLEL=$DEFAULT_PARALLEL
COMMAND=()
LOG_LEVEL="INFO"
USE_IPV6=0
CUSTOM_CHECK_COMMAND=""
PROTOCOL="tcp"

# Process tracking for parallel execution
PIDS=()

# -----------------------------------------------------------------------------
# Logging Functions
# -----------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Skip debug messages unless explicitly enabled
    if [[ "$level" == "DEBUG" && "$LOG_LEVEL" != "DEBUG" ]]; then
        return
    fi
    
    # Skip info messages in quiet mode
    if [[ "$QUIET" -eq 1 && "$level" == "INFO" ]]; then
        return
    fi
    
    local color=""
    local prefix=""
    
    case "$level" in
        "ERROR"|"FATAL")
            color="$RED"
            prefix="❌"
            ;;
        "WARN"|"WARNING")
            color="$YELLOW"
            prefix="⚠️"
            ;;
        "INFO")
            color="$GREEN"
            prefix="ℹ️"
            ;;
        "DEBUG")
            color="$BLUE"
            prefix="🔍"
            ;;
        "SUCCESS")
            color="$GREEN"
            prefix="✅"
            ;;
        *)
            color="$NC"
            prefix="📝"
            ;;
    esac
    
    if [[ "$QUIET" -eq 0 || "$level" == "ERROR" || "$level" == "FATAL" ]]; then
        echo -e "${color}${prefix} [$timestamp] [$level] $message${NC}" >&2
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
    log "DEBUG" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

log_fatal() {
    log "FATAL" "$@"
    exit $EXIT_INVALID_ARGS
}

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
usage() {
    cat << EOF
$SCRIPT_NAME v$SCRIPT_VERSION - Service Dependency Manager

Wait for TCP services to become available before executing a command.

USAGE:
    $SCRIPT_NAME [OPTIONS] HOST:PORT [HOST:PORT...] [-- COMMAND ARGS...]
    $SCRIPT_NAME [OPTIONS] -h HOST -p PORT [-- COMMAND ARGS...]

ARGUMENTS:
    HOST:PORT               Service to wait for (can specify multiple)
    COMMAND ARGS           Command to execute after services are available

OPTIONS:
    -h, --host HOST        Host to check (use with -p)
    -p, --port PORT        Port to check (use with -h)
    -t, --timeout TIMEOUT  Timeout in seconds (default: $DEFAULT_TIMEOUT)
    -i, --interval INTERVAL Check interval in seconds (default: $DEFAULT_INTERVAL)
    -r, --retries RETRIES  Number of retries (default: unlimited)
    -s, --strict           Exit with error if command fails
    -q, --quiet            Don't output any status messages
    -P, --parallel         Check multiple hosts in parallel
    -6, --ipv6             Use IPv6
    -v, --verbose          Enable verbose/debug output
    -c, --check COMMAND    Custom health check command
    --protocol PROTOCOL    Protocol to use (tcp, udp) (default: tcp)
    --version              Show version information
    --help                 Show this help message

EXAMPLES:
    # Wait for database
    $SCRIPT_NAME db:5432 -- echo "Database is ready"
    
    # Wait for multiple services
    $SCRIPT_NAME db:5432 redis:6379 -t 60 -- start-app.sh
    
    # Wait with custom timeout and interval
    $SCRIPT_NAME -h localhost -p 8080 -t 30 -i 2 -- curl localhost:8080
    
    # Parallel checking
    $SCRIPT_NAME db:5432 redis:6379 cache:11211 -P -t 30 -- app.sh
    
    # Custom health check
    $SCRIPT_NAME -h api.service.com -p 443 -c "curl -f https://api.service.com/health"
    
    # Strict mode (exit if command fails)
    $SCRIPT_NAME db:5432 -s -- migrations.sh

EXIT CODES:
    0    Success
    1    Timeout
    2    Invalid arguments
    3    Connection failed
    4    Command execution failed (in strict mode)

ENVIRONMENT VARIABLES:
    WAIT_FOR_IT_TIMEOUT     Default timeout (overridden by -t)
    WAIT_FOR_IT_INTERVAL    Default interval (overridden by -i)
    WAIT_FOR_IT_QUIET       Quiet mode (overridden by -q)
    WAIT_FOR_IT_PARALLEL    Parallel mode (overridden by -P)

For more information: https://github.com/your-org/ecosistema-emprendimiento
EOF
}

version() {
    cat << EOF
$SCRIPT_NAME version $SCRIPT_VERSION
Author: $SCRIPT_AUTHOR

This is free software; you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.
EOF
}

is_integer() {
    [[ $1 =~ ^[0-9]+$ ]]
}

is_valid_port() {
    local port="$1"
    is_integer "$port" && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]
}

validate_host_port() {
    local host_port="$1"
    
    if [[ "$host_port" =~ ^(.+):([0-9]+)$ ]]; then
        local host="${BASH_REMATCH[1]}"
        local port="${BASH_REMATCH[2]}"
        
        if [[ -z "$host" ]]; then
            log_error "Empty host in '$host_port'"
            return 1
        fi
        
        if ! is_valid_port "$port"; then
            log_error "Invalid port '$port' in '$host_port'"
            return 1
        fi
        
        return 0
    else
        log_error "Invalid format '$host_port'. Expected format: host:port"
        return 1
    fi
}

parse_host_port() {
    local host_port="$1"
    
    if [[ "$host_port" =~ ^(.+):([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    else
        log_fatal "Invalid host:port format: $host_port"
    fi
}

# -----------------------------------------------------------------------------
# Connection Testing Functions
# -----------------------------------------------------------------------------
test_tcp_connection() {
    local host="$1"
    local port="$2"
    local timeout="${3:-5}"
    
    log_debug "Testing TCP connection to $host:$port (timeout: ${timeout}s)"
    
    # Use different methods based on available tools
    if command -v nc >/dev/null 2>&1; then
        # Use netcat if available
        if [[ "$USE_IPV6" -eq 1 ]]; then
            timeout "$timeout" nc -6 -z "$host" "$port" >/dev/null 2>&1
        else
            timeout "$timeout" nc -4 -z "$host" "$port" >/dev/null 2>&1
        fi
    elif command -v telnet >/dev/null 2>&1; then
        # Use telnet as fallback
        timeout "$timeout" telnet "$host" "$port" >/dev/null 2>&1
    elif [[ -e /dev/tcp ]]; then
        # Use bash built-in TCP support
        timeout "$timeout" bash -c "exec 3<>/dev/tcp/$host/$port && exec 3<&-" >/dev/null 2>&1
    else
        # Try using curl as last resort for HTTP services
        if [[ "$port" -eq 80 || "$port" -eq 443 ]]; then
            local protocol="http"
            [[ "$port" -eq 443 ]] && protocol="https"
            timeout "$timeout" curl -s --connect-timeout "$timeout" "$protocol://$host:$port/" >/dev/null 2>&1
        else
            log_error "No suitable tool found for testing connections (nc, telnet, or /dev/tcp)"
            return 1
        fi
    fi
}

test_udp_connection() {
    local host="$1"
    local port="$2"
    local timeout="${3:-5}"
    
    log_debug "Testing UDP connection to $host:$port (timeout: ${timeout}s)"
    
    if command -v nc >/dev/null 2>&1; then
        if [[ "$USE_IPV6" -eq 1 ]]; then
            timeout "$timeout" nc -6 -u -z "$host" "$port" >/dev/null 2>&1
        else
            timeout "$timeout" nc -4 -u -z "$host" "$port" >/dev/null 2>&1
        fi
    else
        log_error "netcat (nc) required for UDP connection testing"
        return 1
    fi
}

test_connection() {
    local host="$1"
    local port="$2"
    
    case "$PROTOCOL" in
        "tcp")
            test_tcp_connection "$host" "$port" "$INTERVAL"
            ;;
        "udp")
            test_udp_connection "$host" "$port" "$INTERVAL"
            ;;
        *)
            log_error "Unsupported protocol: $PROTOCOL"
            return 1
            ;;
    esac
}

run_custom_check() {
    local host="$1"
    local port="$2"
    
    if [[ -n "$CUSTOM_CHECK_COMMAND" ]]; then
        log_debug "Running custom check: $CUSTOM_CHECK_COMMAND"
        
        # Replace placeholders in custom command
        local cmd="$CUSTOM_CHECK_COMMAND"
        cmd="${cmd//\{HOST\}/$host}"
        cmd="${cmd//\{PORT\}/$port}"
        cmd="${cmd//\{host\}/$host}"
        cmd="${cmd//\{port\}/$port}"
        
        eval "$cmd" >/dev/null 2>&1
    else
        test_connection "$host" "$port"
    fi
}

# -----------------------------------------------------------------------------
# Main Waiting Logic
# -----------------------------------------------------------------------------
wait_for_service() {
    local host="$1"
    local port="$2"
    local service_name="$host:$port"
    
    log_info "Waiting for service $service_name..."
    
    local start_time=$(date +%s)
    local attempts=0
    local max_attempts=$RETRIES
    
    while true; do
        ((attempts++))
        
        # Check if service is available
        if run_custom_check "$host" "$port"; then
            local elapsed=$(($(date +%s) - start_time))
            log_success "Service $service_name is available after ${elapsed}s (${attempts} attempts)"
            return 0
        fi
        
        # Check timeout
        local elapsed=$(($(date +%s) - start_time))
        if [[ $elapsed -ge $TIMEOUT ]]; then
            log_error "Timeout waiting for $service_name after ${elapsed}s"
            return $EXIT_TIMEOUT
        fi
        
        # Check retry limit
        if [[ $max_attempts -gt 0 && $attempts -ge $max_attempts ]]; then
            log_error "Max retries ($max_attempts) reached for $service_name"
            return $EXIT_CONNECTION_FAILED
        fi
        
        log_debug "Service $service_name not available, retrying in ${INTERVAL}s... (attempt $attempts)"
        sleep "$INTERVAL"
    done
}

wait_for_service_parallel() {
    local host="$1"
    local port="$2"
    
    # Run wait_for_service in background and track PID
    wait_for_service "$host" "$port" &
    local pid=$!
    PIDS+=($pid)
    
    return 0
}

wait_for_all_services() {
    local exit_code=0
    
    if [[ "$PARALLEL" -eq 1 ]]; then
        log_info "Checking ${#HOSTS[@]} services in parallel..."
        
        # Start all checks in parallel
        for host_port in "${HOSTS[@]}"; do
            read -r host port <<< "$(parse_host_port "$host_port")"
            wait_for_service_parallel "$host" "$port"
        done
        
        # Wait for all background processes
        log_info "Waiting for parallel checks to complete..."
        for pid in "${PIDS[@]}"; do
            if ! wait "$pid"; then
                exit_code=$EXIT_CONNECTION_FAILED
            fi
        done
        
        if [[ $exit_code -eq 0 ]]; then
            log_success "All services are available!"
        else
            log_error "One or more services failed to become available"
        fi
    else
        log_info "Checking ${#HOSTS[@]} services sequentially..."
        
        # Check services sequentially
        for host_port in "${HOSTS[@]}"; do
            read -r host port <<< "$(parse_host_port "$host_port")"
            
            if ! wait_for_service "$host" "$port"; then
                exit_code=$EXIT_CONNECTION_FAILED
                break
            fi
        done
    fi
    
    return $exit_code
}

# -----------------------------------------------------------------------------
# Command Execution
# -----------------------------------------------------------------------------
execute_command() {
    if [[ ${#COMMAND[@]} -eq 0 ]]; then
        log_info "No command specified, exiting successfully"
        return 0
    fi
    
    log_info "Executing command: ${COMMAND[*]}"
    
    # Execute the command
    "${COMMAND[@]}"
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "Command executed successfully"
    else
        log_error "Command failed with exit code $exit_code"
        
        if [[ "$STRICT" -eq 1 ]]; then
            return $EXIT_COMMAND_FAILED
        fi
    fi
    
    return $exit_code
}

# -----------------------------------------------------------------------------
# Argument Parsing
# -----------------------------------------------------------------------------
parse_arguments() {
    CMDNAME="$1"
    shift
    
    # Load environment variables
    TIMEOUT="${WAIT_FOR_IT_TIMEOUT:-$DEFAULT_TIMEOUT}"
    INTERVAL="${WAIT_FOR_IT_INTERVAL:-$DEFAULT_INTERVAL}"
    QUIET="${WAIT_FOR_IT_QUIET:-$DEFAULT_QUIET}"
    PARALLEL="${WAIT_FOR_IT_PARALLEL:-$DEFAULT_PARALLEL}"
    
    local single_host=""
    local single_port=""
    local parsing_command=0
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--host)
                if [[ -z "$2" ]]; then
                    log_fatal "Option $1 requires an argument"
                fi
                single_host="$2"
                shift 2
                ;;
            -p|--port)
                if [[ -z "$2" ]]; then
                    log_fatal "Option $1 requires an argument"
                fi
                if ! is_valid_port "$2"; then
                    log_fatal "Invalid port: $2"
                fi
                single_port="$2"
                shift 2
                ;;
            -t|--timeout)
                if [[ -z "$2" ]] || ! is_integer "$2"; then
                    log_fatal "Option $1 requires a positive integer argument"
                fi
                TIMEOUT="$2"
                shift 2
                ;;
            -i|--interval)
                if [[ -z "$2" ]] || ! is_integer "$2"; then
                    log_fatal "Option $1 requires a positive integer argument"
                fi
                INTERVAL="$2"
                shift 2
                ;;
            -r|--retries)
                if [[ -z "$2" ]] || ! is_integer "$2"; then
                    log_fatal "Option $1 requires a positive integer argument"
                fi
                RETRIES="$2"
                shift 2
                ;;
            -s|--strict)
                STRICT=1
                shift
                ;;
            -q|--quiet)
                QUIET=1
                shift
                ;;
            -P|--parallel)
                PARALLEL=1
                shift
                ;;
            -6|--ipv6)
                USE_IPV6=1
                shift
                ;;
            -v|--verbose)
                LOG_LEVEL="DEBUG"
                shift
                ;;
            -c|--check)
                if [[ -z "$2" ]]; then
                    log_fatal "Option $1 requires an argument"
                fi
                CUSTOM_CHECK_COMMAND="$2"
                shift 2
                ;;
            --protocol)
                if [[ -z "$2" ]]; then
                    log_fatal "Option $1 requires an argument"
                fi
                if [[ "$2" != "tcp" && "$2" != "udp" ]]; then
                    log_fatal "Protocol must be 'tcp' or 'udp'"
                fi
                PROTOCOL="$2"
                shift 2
                ;;
            --version)
                version
                exit $EXIT_SUCCESS
                ;;
            --help)
                usage
                exit $EXIT_SUCCESS
                ;;
            --)
                parsing_command=1
                shift
                break
                ;;
            -*)
                log_fatal "Unknown option: $1"
                ;;
            *)
                if [[ $parsing_command -eq 1 ]]; then
                    COMMAND+=("$1")
                else
                    # Validate host:port format
                    if validate_host_port "$1"; then
                        HOSTS+=("$1")
                    else
                        exit $EXIT_INVALID_ARGS
                    fi
                fi
                shift
                ;;
        esac
    done
    
    # Add remaining arguments to command if we hit --
    while [[ $# -gt 0 ]]; do
        COMMAND+=("$1")
        shift
    done
    
    # Handle single host/port specification
    if [[ -n "$single_host" || -n "$single_port" ]]; then
        if [[ -z "$single_host" || -z "$single_port" ]]; then
            log_fatal "Both --host and --port must be specified when using single host mode"
        fi
        
        HOSTS=("$single_host:$single_port")
    fi
    
    # Validate we have at least one host
    if [[ ${#HOSTS[@]} -eq 0 ]]; then
        log_fatal "No hosts specified. Use either HOST:PORT format or -h/-p options."
    fi
    
    # Validate timeout and interval
    if [[ $TIMEOUT -le 0 ]]; then
        log_fatal "Timeout must be greater than 0"
    fi
    
    if [[ $INTERVAL -le 0 ]]; then
        log_fatal "Interval must be greater than 0"
    fi
    
    if [[ $INTERVAL -gt $TIMEOUT ]]; then
        log_warn "Interval ($INTERVAL) is greater than timeout ($TIMEOUT)"
    fi
}

# -----------------------------------------------------------------------------
# Signal Handlers
# -----------------------------------------------------------------------------
cleanup() {
    log_debug "Cleaning up background processes..."
    
    # Kill any background processes
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_debug "Terminating process $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    # Wait a moment for graceful shutdown
    sleep 1
    
    # Force kill if still running
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_debug "Force killing process $pid"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
}

# Set up signal handlers
trap cleanup EXIT SIGINT SIGTERM

# -----------------------------------------------------------------------------
# Main Function
# -----------------------------------------------------------------------------
main() {
    # Parse command line arguments
    parse_arguments "$@"
    
    # Show configuration in debug mode
    log_debug "Configuration:"
    log_debug "  Hosts: ${HOSTS[*]}"
    log_debug "  Timeout: ${TIMEOUT}s"
    log_debug "  Interval: ${INTERVAL}s"
    log_debug "  Retries: $RETRIES"
    log_debug "  Protocol: $PROTOCOL"
    log_debug "  Parallel: $PARALLEL"
    log_debug "  Strict: $STRICT"
    log_debug "  IPv6: $USE_IPV6"
    log_debug "  Custom check: ${CUSTOM_CHECK_COMMAND:-none}"
    log_debug "  Command: ${COMMAND[*]:-none}"
    
    # Wait for all services
    if ! wait_for_all_services; then
        exit $EXIT_CONNECTION_FAILED
    fi
    
    # Execute command if provided
    execute_command
    local exit_code=$?
    
    # Exit with appropriate code
    exit $exit_code
}

# -----------------------------------------------------------------------------
# Script Execution
# -----------------------------------------------------------------------------
# Ensure we have at least the script name
if [[ $# -eq 0 ]]; then
    usage
    exit $EXIT_INVALID_ARGS
fi

# Run main function with all arguments
main "$@"