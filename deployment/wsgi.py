#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
ECOSISTEMA DE EMPRENDIMIENTO - WSGI PRODUCTION ENTRY POINT
============================================================================
Production WSGI entry point for the entrepreneurship ecosystem platform.

This module provides a production-ready WSGI application compatible with
all major WSGI servers including Gunicorn, uWSGI, Apache mod_wsgi, and
cloud deployment platforms.

Author: DevOps Team
Last Updated: 2025-06-14
Python Version: 3.11+

Supported WSGI Servers:
    - Gunicorn
    - uWSGI
    - Apache mod_wsgi
    - Waitress
    - Bjoern
    - CherryPy WSGI Server

Usage:
    Gunicorn: gunicorn --config gunicorn.conf.py wsgi:application
    uWSGI: uwsgi --ini uwsgi.ini
    Apache: Define in VirtualHost with WSGIScriptAlias
    Docker: CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
============================================================================
"""

import logging
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# Ensure the application directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import WSGI utilities
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.middleware.profiler import ProfilerMiddleware

# Import application components
from app import create_app
from app.core.exceptions import ApplicationError
from app.utils.logging import setup_logging
from app.utils.monitoring import setup_monitoring

# ============================================================================
# WSGI CONFIGURATION AND CONSTANTS
# ============================================================================

# Environment detection
WSGI_ENV = os.environ.get('FLASK_ENV', 'production').lower()
DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')
TESTING = os.environ.get('TESTING', 'false').lower() in ('true', '1', 'yes', 'on')

# WSGI server detection
WSGI_SERVER = os.environ.get('WSGI_SERVER', 'gunicorn').lower()

# Performance settings
ENABLE_PROFILING = os.environ.get('ENABLE_PROFILING', 'false').lower() in ('true', '1', 'yes', 'on')
PROFILE_DIR = os.environ.get('PROFILE_DIR', 'profiles')

# Security settings
PROXY_FIX_ENABLED = os.environ.get('PROXY_FIX_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
TRUSTED_PROXIES = int(os.environ.get('TRUSTED_PROXIES', '1'))

# Monitoring settings
METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
REQUEST_LOGGING_ENABLED = os.environ.get('REQUEST_LOGGING_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')

# Application metadata
APP_NAME = "Ecosistema de Emprendimiento"
APP_VERSION = "1.0.0"

# Global variables
_application: Optional[Any] = None
_application_lock = threading.Lock()
_startup_time = time.time()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def configure_wsgi_logging() -> None:
    """Configure logging for WSGI environment."""
    # Determine log level based on environment
    if WSGI_ENV == 'production':
        log_level = logging.WARNING
    elif WSGI_ENV == 'staging':
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    
    # Configure structured logging for production
    setup_logging(
        level=log_level,
        format_json=WSGI_ENV == 'production',
        include_request_id=True,
        log_file=f"logs/wsgi_{WSGI_ENV}.log" if not TESTING else None
    )
    
    # Configure WSGI-specific loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('gunicorn.error').setLevel(logging.INFO)
    logging.getLogger('gunicorn.access').setLevel(logging.INFO)
    
    # Create WSGI logger
    wsgi_logger = logging.getLogger('wsgi')
    wsgi_logger.info(f"WSGI logging configured for {WSGI_ENV} environment")

# ============================================================================
# ENVIRONMENT VALIDATION
# ============================================================================

def validate_wsgi_environment() -> None:
    """Validate WSGI environment configuration."""
    logger = logging.getLogger('wsgi.validation')
    
    # Required environment variables for production
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'REDIS_URL'
    ]
    
    # Check for missing required variables
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars and WSGI_ENV == 'production':
        error_msg = f"Missing required environment variables for production: {missing_vars}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    elif missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
    
    # Validate directory structure
    required_dirs = ['logs', 'app/static/uploads']
    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Validate file permissions in production
    if WSGI_ENV == 'production':
        log_dir = Path('logs')
        if not os.access(log_dir, os.W_OK):
            logger.warning(f"Log directory {log_dir} is not writable")
    
    logger.info("WSGI environment validation completed")

# ============================================================================
# APPLICATION FACTORY
# ============================================================================

def create_wsgi_app() -> Any:
    """
    Create WSGI application with proper configuration.
    
    Returns:
        Flask application configured for WSGI deployment
    """
    logger = logging.getLogger('wsgi.factory')
    
    try:
        logger.info(f"Creating WSGI application for {APP_NAME}")
        
        # Create Flask application
        flask_app = create_app(config_name=WSGI_ENV)
        
        # Configure WSGI-specific settings
        configure_wsgi_app(flask_app)
        
        # Apply middleware
        flask_app = apply_wsgi_middleware(flask_app)
        
        # Setup monitoring if enabled
        if METRICS_ENABLED:
            setup_monitoring(flask_app)
        
        # Log successful creation
        logger.info(f"WSGI application created successfully")
        
        return flask_app
        
    except Exception as e:
        logger.error(f"Failed to create WSGI application: {e}")
        logger.error(traceback.format_exc())
        raise

def configure_wsgi_app(flask_app: Any) -> None:
    """
    Configure Flask application for WSGI deployment.
    
    Args:
        flask_app: Flask application instance
    """
    logger = logging.getLogger('wsgi.config')
    
    # Production-specific configurations
    if WSGI_ENV == 'production':
        # Disable debug mode
        flask_app.config['DEBUG'] = False
        flask_app.config['TESTING'] = False
        
        # Security configurations
        flask_app.config['SESSION_COOKIE_SECURE'] = True
        flask_app.config['SESSION_COOKIE_HTTPONLY'] = True
        flask_app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        
        # Performance configurations
        flask_app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year
        
        logger.info("Production-specific configurations applied")
    
    # Configure request logging
    if REQUEST_LOGGING_ENABLED:
        configure_request_logging(flask_app)
    
    # Configure error handling
    configure_wsgi_error_handling(flask_app)

def configure_request_logging(flask_app: Any) -> None:
    """
    Configure request logging for WSGI.
    
    Args:
        flask_app: Flask application instance
    """
    from flask import request
    
    request_logger = logging.getLogger('wsgi.requests')
    
    @flask_app.before_request
    def log_request_start():
        """Log request start."""
        if not TESTING:
            request_logger.info(
                f"Request started: {request.method} {request.url} "
                f"from {request.remote_addr}"
            )
            request.start_time = time.time()
    
    @flask_app.after_request
    def log_request_end(response):
        """Log request completion."""
        if not TESTING and hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            request_logger.info(
                f"Request completed: {request.method} {request.url} "
                f"Status: {response.status_code} Duration: {duration:.3f}s"
            )
        return response

def configure_wsgi_error_handling(flask_app: Any) -> None:
    """
    Configure error handling for WSGI environment.
    
    Args:
        flask_app: Flask application instance
    """
    from flask import jsonify
    
    error_logger = logging.getLogger('wsgi.errors')
    
    @flask_app.errorhandler(500)
    def internal_server_error(error):
        """Handle internal server errors."""
        error_logger.error(f"Internal server error: {error}")
        error_logger.error(traceback.format_exc())
        
        if WSGI_ENV == 'production':
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            }), 500
        else:
            return jsonify({
                'error': 'Internal Server Error',
                'message': str(error),
                'traceback': traceback.format_exc()
            }), 500
    
    @flask_app.errorhandler(ApplicationError)
    def handle_application_error(error):
        """Handle custom application errors."""
        error_logger.error(f"Application error: {error}")
        return jsonify({
            'error': error.__class__.__name__,
            'message': str(error)
        }), getattr(error, 'status_code', 500)

# ============================================================================
# WSGI MIDDLEWARE
# ============================================================================

def apply_wsgi_middleware(flask_app: Any) -> Any:
    """
    Apply WSGI middleware stack.
    
    Args:
        flask_app: Flask application instance
        
    Returns:
        Flask application with middleware applied
    """
    logger = logging.getLogger('wsgi.middleware')
    
    # Apply ProxyFix middleware for reverse proxy deployments
    if PROXY_FIX_ENABLED:
        flask_app.wsgi_app = ProxyFix(
            flask_app.wsgi_app,
            x_for=TRUSTED_PROXIES,
            x_proto=TRUSTED_PROXIES,
            x_host=TRUSTED_PROXIES,
            x_prefix=TRUSTED_PROXIES
        )
        logger.info(f"ProxyFix middleware applied with {TRUSTED_PROXIES} trusted proxies")
    
    # Apply profiling middleware if enabled
    if ENABLE_PROFILING and WSGI_ENV != 'production':
        Path(PROFILE_DIR).mkdir(exist_ok=True)
        flask_app.wsgi_app = ProfilerMiddleware(
            flask_app.wsgi_app,
            profile_dir=PROFILE_DIR
        )
        logger.info(f"Profiling middleware enabled, profiles saved to {PROFILE_DIR}")
    
    # Apply custom middleware
    flask_app.wsgi_app = WSGIMiddleware(flask_app.wsgi_app)
    
    return flask_app

class WSGIMiddleware:
    """Custom WSGI middleware for additional functionality."""
    
    def __init__(self, app: Callable) -> None:
        """
        Initialize WSGI middleware.
        
        Args:
            app: WSGI application
        """
        self.app = app
        self.logger = logging.getLogger('wsgi.middleware')
        self.request_count = 0
        self.start_time = time.time()
    
    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        """
        WSGI application call.
        
        Args:
            environ: WSGI environment
            start_response: Start response callable
            
        Returns:
            Response iterable
        """
        self.request_count += 1
        
        # Add custom headers
        def new_start_response(status: str, response_headers: List[Tuple[str, str]], 
                             exc_info: Optional[Any] = None) -> Callable:
            # Add server identification
            response_headers.append(('X-Powered-By', f'{APP_NAME}/{APP_VERSION}'))
            response_headers.append(('X-WSGI-Server', WSGI_SERVER))
            
            # Add security headers for production
            if WSGI_ENV == 'production':
                response_headers.extend([
                    ('X-Content-Type-Options', 'nosniff'),
                    ('X-Frame-Options', 'DENY'),
                    ('X-XSS-Protection', '1; mode=block'),
                    ('Referrer-Policy', 'strict-origin-when-cross-origin'),
                    ('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
                ])
            
            return start_response(status, response_headers, exc_info)
        
        # Call the application
        try:
            return self.app(environ, new_start_response)
        except Exception as e:
            self.logger.error(f"WSGI middleware error: {e}")
            self.logger.error(traceback.format_exc())
            
            # Return error response
            error_response = b'{"error": "Internal Server Error"}'
            new_start_response('500 Internal Server Error', [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(error_response)))
            ])
            return [error_response]

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

def add_wsgi_health_checks(flask_app: Any) -> None:
    """
    Add WSGI-specific health check endpoints.
    
    Args:
        flask_app: Flask application instance
    """
    from flask import jsonify
    
    @flask_app.route('/wsgi/health')
    def wsgi_health():
        """WSGI health check endpoint."""
        uptime = time.time() - _startup_time
        
        return jsonify({
            'status': 'healthy',
            'service': APP_NAME,
            'version': APP_VERSION,
            'wsgi_server': WSGI_SERVER,
            'environment': WSGI_ENV,
            'uptime_seconds': uptime,
            'request_count': getattr(_application, '_request_count', 0),
            'timestamp': time.time()
        })
    
    @flask_app.route('/wsgi/info')
    def wsgi_info():
        """WSGI information endpoint."""
        return jsonify({
            'wsgi_server': WSGI_SERVER,
            'python_version': sys.version,
            'environment': WSGI_ENV,
            'debug': DEBUG,
            'proxy_fix_enabled': PROXY_FIX_ENABLED,
            'metrics_enabled': METRICS_ENABLED,
            'profiling_enabled': ENABLE_PROFILING,
            'trusted_proxies': TRUSTED_PROXIES,
            'startup_time': _startup_time
        })

# ============================================================================
# APPLICATION INITIALIZATION
# ============================================================================

def get_wsgi_application() -> Any:
    """
    Get or create WSGI application instance (thread-safe).
    
    Returns:
        WSGI application instance
    """
    global _application
    
    if _application is None:
        with _application_lock:
            if _application is None:
                try:
                    # Configure logging
                    configure_wsgi_logging()
                    
                    # Validate environment
                    validate_wsgi_environment()
                    
                    # Create application
                    _application = create_wsgi_app()
                    
                    # Add health checks
                    add_wsgi_health_checks(_application)
                    
                    # Log successful initialization
                    logger = logging.getLogger('wsgi')
                    logger.info(f"WSGI application initialized successfully")
                    logger.info(f"Environment: {WSGI_ENV}")
                    logger.info(f"WSGI Server: {WSGI_SERVER}")
                    logger.info(f"Debug Mode: {DEBUG}")
                    
                except Exception as e:
                    logger = logging.getLogger('wsgi')
                    logger.error(f"Failed to initialize WSGI application: {e}")
                    logger.error(traceback.format_exc())
                    raise
    
    return _application

# ============================================================================
# SERVER-SPECIFIC CONFIGURATIONS
# ============================================================================

class GunicornConfig:
    """Gunicorn-specific configuration and utilities."""
    
    @staticmethod
    def when_ready(server) -> None:
        """Called just after the server is started."""
        logger = logging.getLogger('gunicorn.wsgi')
        logger.info(f"Gunicorn server ready. Workers: {server.num_workers}")
    
    @staticmethod
    def worker_int(worker) -> None:
        """Called just after a worker exited on SIGINT or SIGQUIT."""
        logger = logging.getLogger('gunicorn.wsgi')
        logger.info(f"Worker {worker.pid} interrupted")
    
    @staticmethod
    def pre_fork(server, worker) -> None:
        """Called just before a worker is forked."""
        logger = logging.getLogger('gunicorn.wsgi')
        logger.info(f"Worker {worker.pid} forked")

class UWSGIConfig:
    """uWSGI-specific configuration and utilities."""
    
    @staticmethod
    def application_startup() -> None:
        """Called when uWSGI starts."""
        logger = logging.getLogger('uwsgi.wsgi')
        logger.info("uWSGI application startup")
    
    @staticmethod
    def application_shutdown() -> None:
        """Called when uWSGI shuts down."""
        logger = logging.getLogger('uwsgi.wsgi')
        logger.info("uWSGI application shutdown")

# ============================================================================
# WSGI APPLICATION INSTANCE
# ============================================================================

# Create the WSGI application instance
try:
    application = get_wsgi_application()
    
    # For compatibility with various WSGI servers
    app = application  # Some servers expect 'app'
    
    # Server-specific hooks
    if WSGI_SERVER == 'gunicorn':
        # Gunicorn hooks are defined in gunicorn.conf.py
        pass
    elif WSGI_SERVER == 'uwsgi':
        try:
            import uwsgi
            # Register uWSGI postfork hook
            @uwsgi.postfork
            def uwsgi_postfork():
                """uWSGI post-fork hook."""
                logger = logging.getLogger('uwsgi.wsgi')
                logger.info("uWSGI worker process started")
        except ImportError:
            pass
    
except Exception as e:
    # Log the error and re-raise
    print(f"CRITICAL: Failed to create WSGI application: {e}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    raise

# ============================================================================
# WSGI COMPLIANCE VERIFICATION
# ============================================================================

def verify_wsgi_compliance() -> bool:
    """
    Verify WSGI application compliance.
    
    Returns:
        True if WSGI compliant, False otherwise
    """
    try:
        # Basic WSGI compliance check
        if not callable(application):
            return False
        
        # Check if application accepts environ and start_response
        import inspect
        sig = inspect.signature(application)
        params = list(sig.parameters.keys())
        
        if len(params) < 2:
            return False
        
        return True
        
    except Exception:
        return False

# Verify WSGI compliance on import
if not verify_wsgi_compliance():
    raise RuntimeError("WSGI application is not compliant")

# ============================================================================
# DEVELOPMENT AND DEBUGGING UTILITIES
# ============================================================================

def wsgi_debug_info() -> Dict[str, Any]:
    """
    Get WSGI debugging information.
    
    Returns:
        Dictionary with debugging information
    """
    return {
        'wsgi_server': WSGI_SERVER,
        'environment': WSGI_ENV,
        'debug': DEBUG,
        'python_version': sys.version,
        'application_type': type(application).__name__,
        'middleware_stack': [
            middleware.__class__.__name__ 
            for middleware in getattr(application, 'wsgi_app', [])
            if hasattr(middleware, '__class__')
        ],
        'startup_time': _startup_time,
        'process_id': os.getpid(),
        'thread_count': threading.active_count()
    }

def print_wsgi_banner() -> None:
    """Print WSGI startup banner."""
    if WSGI_ENV != 'production':
        banner = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         WSGI APPLICATION READY                              ║
║                     {APP_NAME:<45}           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ WSGI Server: {WSGI_SERVER:<15} │ Environment: {WSGI_ENV:<15} │ Debug: {DEBUG:<10} ║
║ Python: {sys.version.split()[0]:<18} │ PID: {os.getpid():<18} │ Threads: {threading.active_count():<8} ║
║ ProxyFix: {PROXY_FIX_ENABLED:<16} │ Metrics: {METRICS_ENABLED:<16} │ Profile: {ENABLE_PROFILING:<7} ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        print(banner)

# Print banner for non-production environments
if not TESTING:
    print_wsgi_banner()

# ============================================================================
# MODULE METADATA
# ============================================================================

__version__ = APP_VERSION
__author__ = "DevOps Team"
__email__ = "devops@ecosistema-emprendimiento.com"
__status__ = "Production"

# ============================================================================
# END OF WSGI MODULE
# ============================================================================
# This WSGI module provides:
# 
# ✅ Production-ready WSGI application
# ✅ Multi-server compatibility (Gunicorn, uWSGI, mod_wsgi)
# ✅ Security middleware and headers
# ✅ Request/response logging
# ✅ Error handling and monitoring
# ✅ Health check endpoints
# ✅ Performance profiling support
# ✅ Environment-specific configurations
# ✅ Thread-safe application initialization
# ✅ WSGI compliance verification
# ✅ Graceful error handling
# ✅ Development debugging utilities
# 
# Deployment examples:
# - Gunicorn: gunicorn --config gunicorn.conf.py wsgi:application
# - uWSGI: uwsgi --module wsgi --callable application
# - Apache: WSGIScriptAlias / /path/to/wsgi.py
# - Docker: CMD ["gunicorn", "wsgi:application"]
# 
# Environment variables:
# - FLASK_ENV: production|staging|development
# - WSGI_SERVER: gunicorn|uwsgi|mod_wsgi
# - PROXY_FIX_ENABLED: true|false
# - TRUSTED_PROXIES: number of trusted proxies
# - ENABLE_PROFILING: true|false (non-production only)
# - METRICS_ENABLED: true|false
# 
# Last updated: 2025-06-14
# Compatible with: WSGI 1.0, Python 3.11+, Flask 3.0+
# ============================================================================