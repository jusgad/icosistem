# Developer Guide

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd icosistem
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .[dev]  # Install with development dependencies
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

5. **Start services with Docker Compose**
   ```bash
   docker-compose up -d postgres redis
   ```

6. **Run database migrations**
   ```bash
   flask db upgrade
   ```

7. **Start the application**
   ```bash
   python run.py
   ```

8. **Run tests**
   ```bash
   pytest
   ```

## Development Workflow

### Code Style and Quality

The project uses modern Python tooling for consistent code quality:

```bash
# Format code
black .
isort .

# Lint code
ruff check .
ruff check . --fix  # Auto-fix issues

# Type checking
mypy .

# Security scanning
bandit -r app/

# Run all quality checks
pre-commit run --all-files
```

### Git Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**
   ```bash
   git add .
   git commit -m "feat: add user authentication"
   ```

3. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub/GitLab
   ```

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Formatting changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

## API Development

### Creating New Endpoints

1. **Define Pydantic schemas**
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

2. **Create service layer**
   ```python
   # app/services/my_resource_service.py
   from app.services.modern_base import ModernBaseService, service_operation
   
   class MyResourceService(ModernBaseService):
       @service_operation("create_resource")
       async def create_resource(self, data: MyResourceCreate) -> OperationResult[MyResourceResponse]:
           # Business logic here
           pass
   ```

3. **Create API endpoints**
   ```python
   # app/api/modern/my_resource.py
   from flask_restx import Namespace, Resource
   
   my_resource_ns = Namespace('my-resource', description='My resource operations')
   
   @my_resource_ns.route('/')
   class MyResourceListResource(Resource):
       @my_resource_ns.expect(MyResourceCreate)
       @my_resource_ns.marshal_with(MyResourceResponse, code=201)
       def post(self):
           """Create new resource"""
           pass
   ```

4. **Register namespace**
   ```python
   # app/api/modern/v2.py
   from .my_resource import my_resource_ns
   
   api.add_namespace(my_resource_ns, path='/my-resources')
   ```

### Authentication & Authorization

```python
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import require_permission

@my_resource_ns.route('/')
class MyResourceResource(Resource):
    @jwt_required()
    @require_permission('create_resource')
    def post(self):
        current_user_id = get_jwt_identity()
        # ... implementation
```

## Database Development

### Creating Models

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
    
    # Relationships
    user = relationship("User", back_populates="my_models")
```

### Creating Migrations

```bash
# Generate migration
flask db migrate -m "Add my_model table"

# Apply migration
flask db upgrade

# Downgrade migration
flask db downgrade
```

### Database Queries

Use async patterns for better performance:

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

## Testing

### Unit Tests

```python
import pytest
from app.services.my_service import MyService
from app.schemas.my_resource import MyResourceCreate

@pytest.mark.unit
class TestMyService:
    def test_create_resource(self, clean_db):
        service = MyService()
        data = MyResourceCreate(name="Test", description="Test resource")
        
        result = service.create_resource(data)
        
        assert result.success
        assert result.data.name == "Test"
```

### API Tests

```python
@pytest.mark.api
class TestMyResourceAPI:
    def test_create_resource(self, authenticated_api_client):
        data = {
            'name': 'Test Resource',
            'description': 'Test description'
        }
        
        response = authenticated_api_client.post('/api/v2/my-resources', json=data)
        
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Resource'
```

### Integration Tests

```python
@pytest.mark.integration
class TestResourceWorkflow:
    def test_complete_resource_lifecycle(self, api_client, test_user):
        # Create resource
        # Update resource  
        # Delete resource
        pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m api

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/modern/test_my_service.py

# Run tests in parallel
pytest -n auto
```

## Frontend Development (Future)

The project will include a modern frontend built with:

- **Framework**: Vue.js 3 or React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **State Management**: Pinia (Vue) or Zustand (React)
- **HTTP Client**: Axios
- **UI Library**: Tailwind CSS + Headless UI

## Environment Configuration

### Environment Variables

Create `.env` file with:

```env
# Application
FLASK_ENV=development
SECRET_KEY=your-secret-key
APP_VERSION=2.0.0

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ecosistema_dev
SQLALCHEMY_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=2592000

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_USE_TLS=true

# External Services
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Monitoring
SENTRY_DSN=your-sentry-dsn
```

### Configuration Classes

```python
# config/development.py
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    CACHE_TYPE = 'SimpleCache'
```

## Debugging

### Debug Mode

```bash
export FLASK_DEBUG=1
python run.py
```

### Logging Configuration

```python
import structlog

logger = structlog.get_logger(__name__)

def my_function():
    logger.info("Processing user", user_id="123", action="create")
    
    try:
        # ... some code
        logger.info("User created successfully", user_id="123")
    except Exception as e:
        logger.error("Failed to create user", user_id="123", error=str(e))
        raise
```

### Debugging with IDE

Configure your IDE to run Flask in debug mode:

- **PyCharm**: Create run configuration with `FLASK_APP=app` and `FLASK_ENV=development`
- **VS Code**: Use launch.json configuration for Flask debugging

## Performance Optimization

### Database Optimization

```python
# Use indexes
class MyModel(BaseModel):
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    )

# Use select_in_loading for relationships
from sqlalchemy.orm import selectinload

users = session.execute(
    select(User).options(selectinload(User.projects))
).scalars().all()
```

### Caching

```python
from app.services.modern_base import cached_operation

class MyService(ModernBaseService):
    @cached_operation("user_list", ttl=300)
    async def get_users(self) -> List[User]:
        # Expensive operation
        return await self.user_repository.find_all()
```

### Connection Pooling

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

## Monitoring and Observability

### Health Checks

The application includes comprehensive health checks:

- `/api/v2/health/` - Basic health check
- `/api/v2/health/detailed` - Detailed system health
- `/api/v2/health/liveness` - Kubernetes liveness probe
- `/api/v2/health/readiness` - Kubernetes readiness probe

### Metrics

Prometheus metrics are automatically collected:

```python
from prometheus_client import Counter, Histogram

request_counter = Counter('app_requests_total', 'Total requests')
request_duration = Histogram('app_request_duration_seconds', 'Request duration')

@request_duration.time()
def my_endpoint():
    request_counter.inc()
    # ... endpoint logic
```

### Distributed Tracing

OpenTelemetry tracing is built-in:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def my_function():
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("user.id", user_id)
        # ... operation logic
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the virtual environment
   source venv/bin/activate
   
   # Install dependencies
   pip install -e .[dev]
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql
   
   # Test connection
   psql -h localhost -U username -d database_name
   ```

3. **Redis Connection Issues**
   ```bash
   # Check Redis is running
   redis-cli ping
   
   # Should return PONG
   ```

4. **Migration Issues**
   ```bash
   # Reset migrations (development only)
   flask db downgrade base
   flask db upgrade
   
   # Or recreate database
   dropdb ecosistema_dev
   createdb ecosistema_dev
   flask db upgrade
   ```

### Debug Tools

```bash
# Flask shell for debugging
flask shell

# Database shell
flask db-shell

# Show routes
flask routes

# Show configuration
flask config
```

## Code Examples

### Complete Service Implementation

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
            # Validate business rules
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
                
                # Emit event
                self.emit_event("project.created", {
                    "project_id": project.id,
                    "owner_id": user_id
                })
                
                return self.create_operation_result(
                    ProjectResponse.from_orm(project)
                )
    
    async def validate_business_rules(self, data: ProjectCreate) -> List[str]:
        errors = []
        
        # Check if user can create more projects
        user_project_count = await self.get_user_project_count(data.owner_id)
        if user_project_count >= self.max_projects_per_user():
            errors.append("Maximum number of projects reached")
        
        return errors
```

### Complete API Resource

```python
from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

project_ns = Namespace('projects', description='Project management')

@project_ns.route('/')
class ProjectListResource(Resource):
    @jwt_required()
    @project_ns.expect(ProjectCreate)
    @project_ns.marshal_with(ProjectResponse, code=201)
    @project_ns.marshal_with(ErrorResponse, code=400)
    def post(self):
        """Create a new project"""
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
                'message': 'An error occurred'
            }, 500
    
    @jwt_required()
    @project_ns.marshal_list_with(ProjectResponse)
    def get(self):
        """List user's projects"""
        user_id = get_jwt_identity()
        project_service = ProjectService()
        
        projects = await project_service.get_user_projects(user_id)
        return projects
```

## Best Practices

### Service Layer

1. **Single Responsibility**: Each service should have one clear purpose
2. **Async First**: Use async/await for database operations
3. **Error Handling**: Always handle exceptions gracefully
4. **Validation**: Validate both input data and business rules
5. **Caching**: Cache expensive operations appropriately
6. **Logging**: Log important operations with context

### API Layer

1. **RESTful Design**: Follow REST principles consistently
2. **Input Validation**: Use Pydantic schemas for validation
3. **Error Responses**: Return consistent error formats
4. **Authentication**: Protect endpoints appropriately
5. **Documentation**: Document all endpoints with OpenAPI
6. **Versioning**: Use API versioning for backward compatibility

### Database Layer

1. **Migrations**: Always use migrations for schema changes
2. **Indexes**: Add indexes for frequently queried columns
3. **Relationships**: Use proper SQLAlchemy relationships
4. **Async Operations**: Use async database operations
5. **Connection Pooling**: Configure appropriate pool sizes
6. **Query Optimization**: Use joins and eager loading appropriately

### Testing

1. **Test Coverage**: Maintain high test coverage (>80%)
2. **Test Types**: Write unit, integration, and API tests
3. **Test Data**: Use factories for consistent test data
4. **Test Isolation**: Each test should be independent
5. **Async Testing**: Test async code properly
6. **Mock External Services**: Mock external dependencies

## Contributing

1. **Fork the repository**
2. **Create feature branch** from `main`
3. **Write tests** for your changes
4. **Ensure all tests pass** and code quality checks pass
5. **Create pull request** with detailed description
6. **Address review feedback**
7. **Squash commits** before merge

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/python/)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)

## Support

For questions and support:

1. **Check Documentation**: Review this guide and architecture docs
2. **Search Issues**: Look for similar issues on GitHub
3. **Create Issue**: Create detailed issue with reproduction steps
4. **Team Chat**: Contact development team on Slack/Teams
5. **Code Review**: Request code review for complex changes