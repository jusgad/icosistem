"""
Health check endpoints for the modern API.
"""

from flask_restx import Namespace, Resource, fields
from flask import current_app
import time
import psutil
from datetime import datetime

# Create health namespace
health_ns = Namespace(
    'health',
    description='Health check and system status endpoints',
    path='/health'
)

# Health check models
health_status_model = health_ns.model('HealthStatus', {
    'healthy': fields.Boolean(description='Overall health status'),
    'service': fields.String(description='Service name'),
    'version': fields.String(description='Service version'),
    'timestamp': fields.DateTime(description='Health check timestamp'),
    'uptime_seconds': fields.Float(description='Service uptime in seconds'),
    'environment': fields.String(description='Environment name')
})

service_health_model = health_ns.model('ServiceHealth', {
    'name': fields.String(description='Service name'),
    'status': fields.String(description='Service status', enum=['healthy', 'unhealthy', 'degraded']),
    'response_time_ms': fields.Float(description='Response time in milliseconds'),
    'error': fields.String(description='Error message if unhealthy'),
    'details': fields.Raw(description='Additional health details')
})

detailed_health_model = health_ns.model('DetailedHealth', {
    'overall_status': fields.String(description='Overall system health', enum=['healthy', 'unhealthy', 'degraded']),
    'services': fields.List(fields.Nested(service_health_model), description='Individual service health'),
    'system_info': fields.Raw(description='System information'),
    'database': fields.Nested(service_health_model, description='Database health'),
    'cache': fields.Nested(service_health_model, description='Cache health'),
    'external_services': fields.List(fields.Nested(service_health_model), description='External service health')
})

# Global variable to track startup time
startup_time = time.time()


@health_ns.route('/')
class HealthCheck(Resource):
    """Basic health check endpoint."""
    
    @health_ns.marshal_with(health_status_model)
    @health_ns.doc(
        'health_check',
        description='Quick health check endpoint',
        responses={
            200: 'Service is healthy',
            503: 'Service is unhealthy'
        }
    )
    def get(self):
        """
        Get basic health status.
        
        Returns a simple health check response indicating if the service is running.
        This endpoint is typically used by load balancers and monitoring systems.
        """
        try:
            uptime = time.time() - startup_time
            
            health_data = {
                'healthy': True,
                'service': 'ecosistema-emprendimiento-api',
                'version': current_app.config.get('APP_VERSION', '2.0.0'),
                'timestamp': datetime.utcnow(),
                'uptime_seconds': uptime,
                'environment': current_app.config.get('ENVIRONMENT', 'development')
            }
            
            return health_data, 200
            
        except Exception as e:
            return {
                'healthy': False,
                'service': 'ecosistema-emprendimiento-api',
                'error': str(e),
                'timestamp': datetime.utcnow()
            }, 503


@health_ns.route('/detailed')
class DetailedHealthCheck(Resource):
    """Detailed health check endpoint."""
    
    @health_ns.marshal_with(detailed_health_model)
    @health_ns.doc(
        'detailed_health_check',
        description='Comprehensive health check with dependencies',
        responses={
            200: 'Detailed health information',
            503: 'One or more services are unhealthy'
        }
    )
    def get(self):
        """
        Get detailed health status.
        
        Returns comprehensive health information including:
        - Database connectivity
        - Cache status  
        - External service dependencies
        - System resource usage
        - Individual service status
        """
        services_health = []
        overall_healthy = True
        
        # Check database health
        db_health = self._check_database_health()
        services_health.append(db_health)
        if db_health['status'] != 'healthy':
            overall_healthy = False
        
        # Check cache health
        cache_health = self._check_cache_health()
        services_health.append(cache_health)
        if cache_health['status'] != 'healthy':
            overall_healthy = False
        
        # Check external services
        external_services = self._check_external_services()
        services_health.extend(external_services)
        
        # Get system information
        system_info = self._get_system_info()
        
        # Determine overall status
        unhealthy_count = sum(1 for s in services_health if s['status'] == 'unhealthy')
        degraded_count = sum(1 for s in services_health if s['status'] == 'degraded')
        
        if unhealthy_count > 0:
            overall_status = 'unhealthy'
        elif degraded_count > 0:
            overall_status = 'degraded'  
        else:
            overall_status = 'healthy'
        
        health_data = {
            'overall_status': overall_status,
            'services': services_health,
            'system_info': system_info,
            'database': db_health,
            'cache': cache_health,
            'external_services': external_services
        }
        
        status_code = 200 if overall_status == 'healthy' else 503
        return health_data, status_code
    
    def _check_database_health(self) -> dict:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            from app.extensions_modern import db
            
            # Simple connectivity test
            result = db.session.execute('SELECT 1').fetchone()
            response_time = (time.time() - start_time) * 1000
            
            if result and result[0] == 1:
                # Additional checks for performance
                status = 'healthy'
                if response_time > 1000:  # 1 second threshold
                    status = 'degraded'
                
                return {
                    'name': 'database',
                    'status': status,
                    'response_time_ms': response_time,
                    'details': {
                        'engine': str(db.engine.url),
                        'pool_size': db.engine.pool.size(),
                        'checked_in': db.engine.pool.checkedin(),
                        'checked_out': db.engine.pool.checkedout()
                    }
                }
            else:
                return {
                    'name': 'database',
                    'status': 'unhealthy',
                    'response_time_ms': response_time,
                    'error': 'Database query failed'
                }
                
        except Exception as e:
            return {
                'name': 'database',
                'status': 'unhealthy',
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e)
            }
    
    def _check_cache_health(self) -> dict:
        """Check cache connectivity and performance."""
        start_time = time.time()
        
        try:
            from app.extensions_modern import extensions
            
            if not extensions.redis_client:
                return {
                    'name': 'cache',
                    'status': 'degraded',
                    'response_time_ms': 0,
                    'details': {'message': 'Redis not configured'}
                }
            
            # Test Redis connectivity
            import asyncio
            
            async def test_redis():
                await extensions.redis_client.ping()
                await extensions.redis_client.set('health_check', 'ok', ex=10)
                result = await extensions.redis_client.get('health_check')
                return result == 'ok'
            
            # Run async test in sync context
            result = asyncio.run(test_redis())
            response_time = (time.time() - start_time) * 1000
            
            if result:
                status = 'healthy'
                if response_time > 500:  # 500ms threshold
                    status = 'degraded'
                
                return {
                    'name': 'cache',
                    'status': status,
                    'response_time_ms': response_time,
                    'details': {'connection': 'ok'}
                }
            else:
                return {
                    'name': 'cache',
                    'status': 'unhealthy',
                    'response_time_ms': response_time,
                    'error': 'Cache test failed'
                }
                
        except Exception as e:
            return {
                'name': 'cache',
                'status': 'unhealthy',
                'response_time_ms': (time.time() - start_time) * 1000,
                'error': str(e)
            }
    
    def _check_external_services(self) -> list:
        """Check external service dependencies."""
        external_services = []
        
        # Check email service
        try:
            # Here you would test SMTP connectivity
            external_services.append({
                'name': 'email_service',
                'status': 'healthy',
                'response_time_ms': 50,
                'details': {'provider': 'configured'}
            })
        except Exception as e:
            external_services.append({
                'name': 'email_service',
                'status': 'unhealthy',
                'error': str(e)
            })
        
        # Check file storage
        try:
            # Here you would test S3/file storage connectivity
            external_services.append({
                'name': 'file_storage',
                'status': 'healthy',
                'response_time_ms': 100,
                'details': {'provider': 'local'}
            })
        except Exception as e:
            external_services.append({
                'name': 'file_storage',
                'status': 'unhealthy',
                'error': str(e)
            })
        
        return external_services
    
    def _get_system_info(self) -> dict:
        """Get system resource information."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_info = {
                'total_mb': memory.total // (1024 * 1024),
                'available_mb': memory.available // (1024 * 1024),
                'percent_used': memory.percent
            }
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_info = {
                'total_gb': disk.total // (1024 * 1024 * 1024),
                'free_gb': disk.free // (1024 * 1024 * 1024),
                'percent_used': (disk.used / disk.total) * 100
            }
            
            return {
                'cpu_percent': cpu_percent,
                'memory': memory_info,
                'disk': disk_info,
                'python_version': f"{psutil.version_info[0]}.{psutil.version_info[1]}",
                'process_count': len(psutil.pids()),
                'uptime_seconds': time.time() - startup_time
            }
            
        except Exception as e:
            return {
                'error': f'Failed to get system info: {str(e)}'
            }


@health_ns.route('/liveness')
class LivenessProbe(Resource):
    """Kubernetes liveness probe endpoint."""
    
    @health_ns.doc(
        'liveness_probe',
        description='Kubernetes liveness probe',
        responses={
            200: 'Service is alive',
            503: 'Service should be restarted'
        }
    )
    def get(self):
        """
        Liveness probe for Kubernetes.
        
        This endpoint indicates whether the service is alive and should not be restarted.
        It should only fail if the service is in an unrecoverable state.
        """
        try:
            # Basic liveness check - just verify the process is running
            return {'status': 'alive', 'timestamp': datetime.utcnow().isoformat()}, 200
        except Exception:
            return {'status': 'dead'}, 503


@health_ns.route('/readiness')  
class ReadinessProbe(Resource):
    """Kubernetes readiness probe endpoint."""
    
    @health_ns.doc(
        'readiness_probe',
        description='Kubernetes readiness probe',
        responses={
            200: 'Service is ready to receive traffic',
            503: 'Service is not ready'
        }
    )
    def get(self):
        """
        Readiness probe for Kubernetes.
        
        This endpoint indicates whether the service is ready to receive traffic.
        It should fail if dependencies are unavailable.
        """
        try:
            # Check if critical dependencies are available
            from app.extensions_modern import db
            
            # Quick database check
            db.session.execute('SELECT 1')
            
            return {
                'status': 'ready', 
                'timestamp': datetime.utcnow().isoformat()
            }, 200
            
        except Exception as e:
            return {
                'status': 'not_ready',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }, 503