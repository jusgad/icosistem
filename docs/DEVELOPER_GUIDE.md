# Guía del Desarrollador

## Inicio Rápido

### Prerrequisitos

- Python 3.11+
- Node.js 18+ (para frontend)
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (opcional)

### Configuración del Entorno de Desarrollo Local

1. **Clonar el repositorio**
   ```bash
   git clone <repository-url>
   cd icosistem
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -e .[dev]  # Instalar con dependencias de desarrollo
   ```

4. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tu configuración local
   ```

5. **Iniciar servicios con Docker Compose**
   ```bash
   docker-compose up -d postgres redis
   ```

6. **Ejecutar migraciones de base de datos**
   ```bash
   flask db upgrade
   ```

7. **Iniciar la aplicación**
   ```bash
   python run.py
   ```

8. **Ejecutar pruebas**
   ```bash
   pytest
   ```

## Flujo de Trabajo de Desarrollo

### Estilo y Calidad del Código

El proyecto utiliza herramientas modernas de Python para mantener la calidad del código consistente:

```bash
# Formatear código
black .
isort .

# Linter del código
ruff check .
ruff check . --fix  # Auto-corregir problemas

# Verificación de tipos
mypy .

# Escaneo de seguridad
bandit -r app/

# Ejecutar todas las verificaciones de calidad
pre-commit run --all-files
```

### Flujo de Trabajo con Git

1. **Crear rama de funcionalidad**
   ```bash
   git checkout -b feature/nombre-de-tu-funcionalidad
   ```

2. **Realizar cambios y confirmar**
   ```bash
   git add .
   git commit -m "feat: agregar autenticación de usuario"
   ```

3. **Subir y crear PR**
   ```bash
   git push origin feature/nombre-de-tu-funcionalidad
   # Crear pull request en GitHub/GitLab
   ```

### Convención de Mensajes de Commit

Usar [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nueva funcionalidad
- `fix:` Corrección de errores
- `docs:` Cambios en documentación
- `style:` Cambios de formato
- `refactor:` Refactorización del código
- `test:` Agregar pruebas
- `chore:` Tareas de mantenimiento

## Desarrollo de API

### Creación de Nuevos Endpoints

1. **Definir esquemas de Pydantic**
   ```python
   # app/schemas/my_resource.py
   from pydantic import BaseModel, Field
   
   class MyResourceCreate(BaseModel):
       name: str = Field(min_length=1, max_length=100)
       description: str = Field(max_length=1000)
   
   class MyResourceResponse(BaseModel):
       id: str
       name: str
       description: str
       created_at: datetime
   ```

2. **Crear capa de servicios**
   ```python
   # app/services/my_resource_service.py
   from app.services.modern_base import ModernBaseService, service_operation
   
   class MyResourceService(ModernBaseService):
       @service_operation("create_resource")
       async def create_resource(self, data: MyResourceCreate) -> OperationResult[MyResourceResponse]:
           # Lógica de negocio aquí
           pass
   ```

3. **Crear endpoints de API**
   ```python
   # app/api/modern/my_resource.py
   from flask_restx import Namespace, Resource
   
   my_resource_ns = Namespace('my-resource', description='Operaciones de mi recurso')
   
   @my_resource_ns.route('/')
   class MyResourceListResource(Resource):
       @my_resource_ns.expect(MyResourceCreate)
       @my_resource_ns.marshal_with(MyResourceResponse, code=201)
       def post(self):
           """Crear nuevo recurso"""
           pass
   ```

4. **Registrar namespace**
   ```python
   # app/api/modern/v2.py
   from .my_resource import my_resource_ns
   
   api.add_namespace(my_resource_ns, path='/my-resources')
   ```

### Autenticación y Autorización

```python
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import require_permission

@my_resource_ns.route('/')
class MyResourceResource(Resource):
    @jwt_required()
    @require_permission('create_resource')
    def post(self):
        current_user_id = get_jwt_identity()
        # ... implementación
```

## Desarrollo de Base de Datos

### Creación de Modelos

```python
# app/models/my_model.py
from app.models.base import BaseModel
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship

class MyModel(BaseModel):
    __tablename__ = 'my_models'
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    
    # Relaciones
    user = relationship("User", back_populates="my_models")
```

### Creación de Migraciones

```bash
# Generar migración
flask db migrate -m "Agregar tabla my_model"

# Aplicar migración
flask db upgrade

# Revertir migración
flask db downgrade
```

### Consultas de Base de Datos

Usar patrones async para mejor rendimiento:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_user_resources(self, user_id: str) -> List[MyModel]:
    async with AsyncSession(self.engine) as session:
        result = await session.execute(
            select(MyModel)
            .where(MyModel.user_id == user_id)
            .order_by(MyModel.created_at.desc())
        )
        return result.scalars().all()
```

## Pruebas

### Pruebas Unitarias

```python
import pytest
from app.services.my_service import MyService
from app.schemas.my_resource import MyResourceCreate

@pytest.mark.unit
class TestMyService:
    def test_create_resource(self, clean_db):
        service = MyService()
        data = MyResourceCreate(name="Test", description="Recurso de prueba")
        
        result = service.create_resource(data)
        
        assert result.success
        assert result.data.name == "Test"
```

### Pruebas de API

```python
@pytest.mark.api
class TestMyResourceAPI:
    def test_create_resource(self, authenticated_api_client):
        data = {
            'name': 'Recurso de Prueba',
            'description': 'Descripción de prueba'
        }
        
        response = authenticated_api_client.post('/api/v2/my-resources', json=data)
        
        assert response.status_code == 201
        assert response.json()['name'] == 'Recurso de Prueba'
```

### Pruebas de Integración

```python
@pytest.mark.integration
class TestResourceWorkflow:
    def test_complete_resource_lifecycle(self, api_client, test_user):
        # Crear recurso
        # Actualizar recurso  
        # Eliminar recurso
        pass
```

### Ejecutar Pruebas

```bash
# Ejecutar todas las pruebas
pytest

# Ejecutar tipos específicos de pruebas
pytest -m unit
pytest -m integration
pytest -m api

# Ejecutar con cobertura
pytest --cov=app --cov-report=html

# Ejecutar archivo de prueba específico
pytest tests/modern/test_my_service.py

# Ejecutar pruebas en paralelo
pytest -n auto
```

## Desarrollo de Frontend (Futuro)

El proyecto incluirá un frontend moderno construido con:

- **Framework**: Vue.js 3 o React 18
- **Lenguaje**: TypeScript
- **Herramienta de Construcción**: Vite
- **Gestión de Estado**: Pinia (Vue) o Zustand (React)
- **Cliente HTTP**: Axios
- **Librería UI**: Tailwind CSS + Headless UI

## Configuración del Entorno

### Variables de Entorno

Crear archivo `.env` con:

```env
# Aplicación
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta
APP_VERSION=2.0.0

# Base de Datos
DATABASE_URL=postgresql://user:password@localhost:5432/ecosistema_dev
SQLALCHEMY_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=tu-secreto-jwt
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=2592000

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=tu-email@gmail.com
MAIL_PASSWORD=tu-contraseña-app
MAIL_USE_TLS=true

# Servicios Externos
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret

# Monitoreo
SENTRY_DSN=tu-sentry-dsn
```

### Clases de Configuración

```python
# config/development.py
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    CACHE_TYPE = 'SimpleCache'
```

## Depuración

### Modo Debug

```bash
export FLASK_DEBUG=1
python run.py
```

### Configuración de Logging

```python
import structlog

logger = structlog.get_logger(__name__)

def my_function():
    logger.info("Procesando usuario", user_id="123", action="create")
    
    try:
        # ... algún código
        logger.info("Usuario creado exitosamente", user_id="123")
    except Exception as e:
        logger.error("Error al crear usuario", user_id="123", error=str(e))
        raise
```

### Depuración con IDE

Configura tu IDE para ejecutar Flask en modo debug:

- **PyCharm**: Crear configuración de ejecución con `FLASK_APP=app` y `FLASK_ENV=development`
- **VS Code**: Usar configuración launch.json para depuración de Flask

## Optimización de Rendimiento

### Optimización de Base de Datos

```python
# Usar índices
class MyModel(BaseModel):
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )

# Usar select_in_loading para relaciones
from sqlalchemy.orm import selectinload

users = session.execute(
    select(User).options(selectinload(User.projects))
).scalars().all()
```

### Caché

```python
from app.services.modern_base import cached_operation

class MyService(ModernBaseService):
    @cached_operation("user_list", ttl=300)
    async def get_users(self) -> List[User]:
        # Operación costosa
        return await self.user_repository.find_all()
```

### Pool de Conexiones

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    echo=False
)
```

## Monitoreo y Observabilidad

### Verificaciones de Salud

La aplicación incluye verificaciones de salud integrales:

- `/api/v2/health/` - Verificación básica de salud
- `/api/v2/health/detailed` - Salud detallada del sistema
- `/api/v2/health/liveness` - Sonda de vida de Kubernetes
- `/api/v2/health/readiness` - Sonda de preparación de Kubernetes

### Métricas

Las métricas de Prometheus se recopilan automáticamente:

```python
from prometheus_client import Counter, Histogram

request_counter = Counter('app_requests_total', 'Total de solicitudes')
request_duration = Histogram('app_request_duration_seconds', 'Duración de solicitudes')

@request_duration.time()
def my_endpoint():
    request_counter.inc()
    # ... lógica del endpoint
```

### Trazado Distribuido

El trazado OpenTelemetry está integrado:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def my_function():
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("user.id", user_id)
        # ... lógica de la operación
```

## Solución de Problemas

### Problemas Comunes

1. **Errores de Importación**
   ```bash
   # Asegúrate de estar en el entorno virtual
   source venv/bin/activate
   
   # Instalar dependencias
   pip install -e .[dev]
   ```

2. **Problemas de Conexión a Base de Datos**
   ```bash
   # Verificar que PostgreSQL esté ejecutándose
   sudo systemctl status postgresql
   
   # Probar conexión
   psql -h localhost -U username -d database_name
   ```

3. **Problemas de Conexión a Redis**
   ```bash
   # Verificar que Redis esté ejecutándose
   redis-cli ping
   
   # Debería devolver PONG
   ```

4. **Problemas de Migración**
   ```bash
   # Reiniciar migraciones (solo desarrollo)
   flask db downgrade base
   flask db upgrade
   
   # O recrear base de datos
   dropdb ecosistema_dev
   createdb ecosistema_dev
   flask db upgrade
   ```

### Herramientas de Debug

```bash
# Shell de Flask para depuración
flask shell

# Shell de base de datos
flask db-shell

# Mostrar rutas
flask routes

# Mostrar configuración
flask config
```

## Ejemplos de Código

### Implementación Completa de Servicio

```python
from typing import List, Optional
from app.services.modern_base import ModernBaseService, service_operation
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.models.project import Project

class ProjectService(ModernBaseService):
    def __init__(self):
        super().__init__(ServiceConfig(
            name="project_service",
            cache_enabled=True,
            circuit_breaker_enabled=True
        ))
    
    @service_operation("create_project", validation_schema=ProjectCreate)
    async def create_project(self, data: ProjectCreate, user_id: str) -> OperationResult[ProjectResponse]:
        async with self.operation_context("create_project", user_id=user_id):
            # Validar reglas de negocio
            errors = await self.validate_business_rules(data)
            if errors:
                return self.create_operation_result(
                    error="; ".join(errors),
                    error_code="BUSINESS_RULE_VIOLATION"
                )
            
            async with self.database_transaction():
                project = Project(
                    **data.dict(),
                    owner_id=user_id
                )
                
                db.session.add(project)
                await db.session.commit()
                await db.session.refresh(project)
                
                # Emitir evento
                self.emit_event("project.created", {
                    "project_id": project.id,
                    "owner_id": user_id
                })
                
                return self.create_operation_result(
                    ProjectResponse.from_orm(project)
                )
    
    async def validate_business_rules(self, data: ProjectCreate) -> List[str]:
        errors = []
        
        # Verificar si el usuario puede crear más proyectos
        user_project_count = await self.get_user_project_count(data.owner_id)
        if user_project_count >= self.max_projects_per_user():
            errors.append("Se ha alcanzado el número máximo de proyectos")
        
        return errors
```

### Recurso API Completo

```python
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

project_ns = Namespace('projects', description='Gestión de proyectos')

@project_ns.route('/')
class ProjectListResource(Resource):
    @jwt_required()
    @project_ns.expect(ProjectCreate)
    @project_ns.marshal_with(ProjectResponse, code=201)
    @project_ns.marshal_with(ErrorResponse, code=400)
    def post(self):
        """Crear un nuevo proyecto"""
        try:
            user_id = get_jwt_identity()
            data = request.get_json()
            
            project_service = ProjectService()
            result = await project_service.create_project(data, user_id)
            
            if result.success:
                return result.data, 201
            else:
                return {
                    'success': False,
                    'error_type': 'business_error',
                    'message': result.error
                }, 400
                
        except Exception as e:
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'Ocurrió un error'
            }, 500
    
    @jwt_required()
    @project_ns.marshal_list_with(ProjectResponse)
    def get(self):
        """Listar proyectos del usuario"""
        user_id = get_jwt_identity()
        project_service = ProjectService()
        
        projects = await project_service.get_user_projects(user_id)
        return projects
```

## Mejores Prácticas

### Capa de Servicios

1. **Responsabilidad Única**: Cada servicio debe tener un propósito claro
2. **Async Primero**: Usar async/await para operaciones de base de datos
3. **Manejo de Errores**: Siempre manejar excepciones de manera elegante
4. **Validación**: Validar tanto datos de entrada como reglas de negocio
5. **Caché**: Cachear operaciones costosas apropiadamente
6. **Logging**: Registrar operaciones importantes con contexto

### Capa de API

1. **Diseño RESTful**: Seguir principios REST consistentemente
2. **Validación de Entrada**: Usar esquemas Pydantic para validación
3. **Respuestas de Error**: Devolver formatos de error consistentes
4. **Autenticación**: Proteger endpoints apropiadamente
5. **Documentación**: Documentar todos los endpoints con OpenAPI
6. **Versionado**: Usar versionado de API para compatibilidad hacia atrás

### Capa de Base de Datos

1. **Migraciones**: Siempre usar migraciones para cambios de esquema
2. **Índices**: Agregar índices para columnas consultadas frecuentemente
3. **Relaciones**: Usar relaciones SQLAlchemy apropiadas
4. **Operaciones Async**: Usar operaciones de base de datos async
5. **Pool de Conexiones**: Configurar tamaños de pool apropiados
6. **Optimización de Consultas**: Usar joins y eager loading apropiadamente

### Pruebas

1. **Cobertura de Pruebas**: Mantener alta cobertura de pruebas (>80%)
2. **Tipos de Pruebas**: Escribir pruebas unitarias, de integración y de API
3. **Datos de Prueba**: Usar factories para datos de prueba consistentes
4. **Aislamiento de Pruebas**: Cada prueba debe ser independiente
5. **Pruebas Async**: Probar código async apropiadamente
6. **Mock de Servicios Externos**: Hacer mock de dependencias externas

## Contribución

1. **Fork del repositorio**
2. **Crear rama de funcionalidad** desde `main`
3. **Escribir pruebas** para tus cambios
4. **Asegurar que todas las pruebas pasen** y las verificaciones de calidad pasen
5. **Crear pull request** con descripción detallada
6. **Atender retroalimentación de revisión**
7. **Squash commits** antes del merge

## Recursos

- [Documentación de Flask](https://flask.palletsprojects.com/)
- [Documentación de Pydantic](https://docs.pydantic.dev/)
- [Documentación de SQLAlchemy](https://docs.sqlalchemy.org/)
- [Documentación de pytest](https://docs.pytest.org/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/python/)
- [Arquitectura Hexagonal](https://alistair.cockburn.us/hexagonal-architecture/)

## Soporte

Para preguntas y soporte:

1. **Revisar Documentación**: Revisar esta guía y documentación de arquitectura
2. **Buscar Issues**: Buscar issues similares en GitHub
3. **Crear Issue**: Crear issue detallado con pasos de reproducción
4. **Chat del Equipo**: Contactar equipo de desarrollo en Slack/Teams
5. **Revisión de Código**: Solicitar revisión de código para cambios complejos