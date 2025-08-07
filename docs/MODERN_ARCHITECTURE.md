# Modern Architecture Guide

## Overview

The **Ecosistema de Emprendimiento** platform has been modernized to use the latest Python patterns, libraries, and architectural approaches while maintaining the hexagonal architecture principles. This document outlines the new modern architecture and design patterns implemented.

## Table of Contents

- [Architecture Principles](#architecture-principles)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Modern Patterns](#modern-patterns)
- [API Design](#api-design)
- [Data Validation](#data-validation)
- [Testing Strategy](#testing-strategy)
- [Observability](#observability)
- [Deployment](#deployment)

## Architecture Principles

### Hexagonal Architecture (Ports & Adapters)

The system continues to follow hexagonal architecture principles with clear separation between:

- **Domain Layer**: Pure business logic (entities, value objects, domain services)
- **Application Layer**: Use cases and application services
- **Infrastructure Layer**: Adapters for databases, external services, web frameworks
- **Presentation Layer**: REST API, WebSocket handlers, CLI commands

### Modern Enhancements

1. **Async-First Design**: Built with async/await support from the ground up
2. **Type Safety**: Full type hints using modern Python typing
3. **Validation**: Pydantic models for comprehensive data validation
4. **Observability**: Built-in tracing, metrics, and structured logging
5. **Resilience**: Circuit breakers, retries, and graceful degradation

## Technology Stack

### Core Framework
- **Flask 3.0+**: Modern web framework
- **Flask-RESTX 1.3+**: Auto-generating OpenAPI documentation
- **Pydantic 2.5+**: Data validation and settings management
- **SQLAlchemy 2.0+**: Modern ORM with async support

### Database & Caching
- **PostgreSQL 15+**: Primary database with async support
- **Redis 7+**: Caching and session storage
- **Alembic**: Database migrations

### Observability & Monitoring
- **OpenTelemetry**: Distributed tracing
- **Prometheus**: Metrics collection
- **Loguru**: Structured logging
- **Sentry**: Error tracking

### Testing & Quality
- **pytest 8+**: Testing framework
- **Factory Boy**: Test data generation
- **Ruff**: Fast Python linter
- **Black**: Code formatting
- **mypy**: Static type checking

### Development Tools
- **Ruff**: Ultra-fast linting
- **pre-commit**: Git hooks
- **Docker**: Containerization
- **Docker Compose**: Local development

## Project Structure

```
app/
├── api/                    # API layer
│   ├── modern/            # Modern API v2
│   │   ├── v2.py         # Main API setup
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── users.py      # User management
│   │   └── health.py     # Health checks
│   └── v1/               # Legacy API (deprecated)
├── schemas/               # Pydantic schemas
│   ├── common.py         # Common schemas
│   ├── auth.py           # Authentication schemas
│   ├── user.py           # User schemas
│   └── project.py        # Project schemas
├── services/              # Business logic layer
│   ├── modern_base.py    # Modern service base class
│   ├── auth_service.py   # Authentication service
│   ├── user_service.py   # User management service
│   └── project_service.py # Project management
├── models/               # Database models (SQLAlchemy)
├── extensions_modern.py  # Modern Flask extensions
├── config.py            # Configuration management
└── __init__.py          # Application factory

tests/
├── modern/              # Modern test suite
│   ├── conftest.py     # Test configuration
│   ├── test_auth_api.py # Auth API tests
│   └── test_services.py # Service layer tests
├── fixtures/           # Test fixtures
└── integration/        # Integration tests

docs/
├── MODERN_ARCHITECTURE.md
├── API_REFERENCE.md
├── DEPLOYMENT_GUIDE.md
└── DEVELOPER_GUIDE.md
```

## Modern Patterns

### 1. Modern Service Base Class

```python
from app.services.modern_base import ModernBaseService, service_operation
from app.schemas.user import UserCreate, UserResponse

class UserService(ModernBaseService):
    def __init__(self):
        super().__init__(ServiceConfig(
            name="user_service",
            cache_enabled=True,
            circuit_breaker_enabled=True
        ))
    
    @service_operation("create_user", validation_schema=UserCreate)
    async def create_user(self, data: UserCreate) -> OperationResult[UserResponse]:
        async with self.operation_context("create_user"):
            async with self.database_transaction():
                # Business logic here
                user = User(**data.dict())
                # ... save user
                return self.create_operation_result(UserResponse.from_orm(user))
```

### 2. Pydantic Validation

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr = Field(description="User email address")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    user_type: UserType = Field(description="Type of user")
    phone: Optional[str] = Field(None, regex=r'^\+?[1-9]\d{1,14}$')
    
    class Config:
        str_strip_whitespace = True
        validate_assignment = True
```

### 3. Modern API with Flask-RESTX

```python
from flask_restx import Namespace, Resource
from app.schemas.auth import LoginRequest, LoginResponse

auth_ns = Namespace('auth', description='Authentication endpoints')

@auth_ns.route('/login')
class LoginResource(Resource):
    @auth_ns.expect(LoginRequest)
    @auth_ns.marshal_with(LoginResponse)
    def post(self):
        """User login with JWT tokens"""
        # Implementation
```

### 4. Async Database Operations

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def create_user_async(self, user_data: UserCreate) -> User:
    async with AsyncSession(self.db_engine) as session:
        user = User(**user_data.dict())
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
```

### 5. Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        # Circuit breaker logic
        pass
```

## API Design

### RESTful Endpoints

The API follows REST principles with consistent patterns:

```
GET    /api/v2/users              # List users
POST   /api/v2/users              # Create user
GET    /api/v2/users/{id}         # Get user
PUT    /api/v2/users/{id}         # Update user
DELETE /api/v2/users/{id}         # Delete user
```

### Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "request_id": "uuid",
    "timestamp": "2024-01-15T10:30:00Z",
    "execution_time": 0.123
  }
}
```

### Error Handling

Standardized error responses:

```json
{
  "success": false,
  "error_type": "validation_error",
  "message": "Invalid input data",
  "details": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Authentication

JWT-based authentication with refresh tokens:

```http
Authorization: Bearer <access_token>
X-Refresh-Token: <refresh_token>
```

## Data Validation

### Input Validation with Pydantic

```python
from pydantic import BaseModel, validator

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(max_length=2000)
    budget: Optional[int] = Field(None, ge=0)
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Project name cannot be empty')
        return v.strip()
```

### Business Rule Validation

```python
async def validate_business_rules(self, data: ProjectCreate) -> List[str]:
    errors = []
    
    # Check if user has permission to create project
    if not self.can_create_project():
        errors.append("User does not have permission to create projects")
    
    # Check budget limits
    if data.budget and data.budget > self.max_project_budget():
        errors.append("Budget exceeds maximum allowed amount")
    
    return errors
```

## Testing Strategy

### Modern Test Structure

```python
@pytest.mark.api
@pytest.mark.auth
class TestAuthAPI:
    def test_login_success(self, api_client, test_user):
        response = api_client.post('/api/v2/auth/login', json={
            'email': test_user.email,
            'password': 'password123'
        })
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
```

### Factory Pattern for Test Data

```python
class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
```

### Async Test Support

```python
@pytest.mark.asyncio
async def test_async_user_creation(async_user_service):
    user_data = UserCreate(
        email='test@example.com',
        first_name='Test',
        last_name='User'
    )
    result = await async_user_service.create_user(user_data)
    assert result.success
```

## Observability

### Structured Logging

```python
from loguru import logger
import structlog

logger = structlog.get_logger()

async def create_user(self, data: UserCreate):
    logger.info("Creating user", 
                email=data.email, 
                user_type=data.user_type,
                correlation_id=self.context.correlation_id)
```

### Distributed Tracing

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def create_user(self, data: UserCreate):
    with tracer.start_as_current_span("user.create") as span:
        span.set_attribute("user.email", data.email)
        span.set_attribute("user.type", data.user_type)
        # ... business logic
```

### Metrics Collection

```python
from prometheus_client import Counter, Histogram

request_count = Counter('user_requests_total', 'Total user requests')
request_duration = Histogram('user_request_duration_seconds', 'Request duration')

@request_duration.time()
def create_user(self, data: UserCreate):
    request_count.inc()
    # ... business logic
```

### Health Checks

```python
@api.route('/health')
class HealthCheck(Resource):
    def get(self):
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow(),
            'version': '2.0.0',
            'services': {
                'database': self._check_database(),
                'redis': self._check_redis(),
                'external_api': self._check_external_services()
            }
        }
```

## Deployment

### Docker Configuration

```dockerfile
# Modern Python base image
FROM python:3.12-slim

# Install dependencies
COPY pyproject.toml requirements.txt ./
RUN pip install -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/

# Run application
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "4", "--bind", "0.0.0.0:5000", "app:create_app()"]
```

### Docker Compose for Development

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - DATABASE_URL=postgresql://user:pass@db:5432/ecosistema
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=ecosistema
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecosistema-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ecosistema-api
  template:
    metadata:
      labels:
        app: ecosistema-api
    spec:
      containers:
      - name: api
        image: ecosistema:latest
        ports:
        - containerPort: 5000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: redis-config
              key: url
        livenessProbe:
          httpGet:
            path: /api/v2/health/liveness
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v2/health/readiness
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Migration from Legacy

### Gradual Migration Strategy

1. **Phase 1**: New APIs use modern patterns (v2)
2. **Phase 2**: Migrate existing services to modern base class
3. **Phase 3**: Update frontend to use new APIs
4. **Phase 4**: Deprecate legacy APIs (v1)

### Compatibility Layer

```python
# Legacy API compatibility
@api_v1.route('/users')
class LegacyUserResource(Resource):
    def get(self):
        # Delegate to modern service
        modern_service = UserService()
        result = modern_service.list_users()
        
        # Transform to legacy format
        return self._transform_to_legacy_format(result)
```

## Performance Optimizations

### Caching Strategy

```python
@cached_operation(key_pattern="user_list", ttl=300)
async def list_users(self, filters: UserFilters) -> List[User]:
    # Heavy database query
    return await self.user_repository.find_all(filters)
```

### Database Optimization

```python
# Use async queries with proper indexing
async def get_user_projects(self, user_id: str) -> List[Project]:
    async with AsyncSession(self.engine) as session:
        result = await session.execute(
            select(Project)
            .where(Project.owner_id == user_id)
            .options(joinedload(Project.tags))
        )
        return result.scalars().all()
```

### Connection Pooling

```python
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600
)
```

## Security Considerations

### Input Sanitization

All inputs are validated using Pydantic schemas before processing.

### Authentication & Authorization

- JWT tokens with short expiration times
- Refresh token rotation
- Role-based access control
- Two-factor authentication support

### Security Headers

```python
from flask_talisman import Talisman

Talisman(app, 
    force_https=True,
    strict_transport_security=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline'"
    }
)
```

### Rate Limiting

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

@limiter.limit("5 per minute")
def login():
    # Login logic
```

## Best Practices

### Code Organization

1. **Single Responsibility**: Each service has a single, well-defined purpose
2. **Dependency Injection**: Services receive their dependencies rather than creating them
3. **Interface Segregation**: Small, focused interfaces rather than large ones
4. **Error Handling**: Comprehensive error handling with proper logging

### Development Workflow

1. **Feature Branches**: All development in feature branches
2. **Code Review**: All changes reviewed before merging
3. **Automated Testing**: Full test suite runs on every commit
4. **Continuous Integration**: Automated builds and deployments

### Documentation

1. **API Documentation**: Auto-generated OpenAPI documentation
2. **Code Documentation**: Comprehensive docstrings and type hints
3. **Architecture Documentation**: Keep this document updated
4. **Deployment Documentation**: Step-by-step deployment guides

## Conclusion

The modernized architecture provides:

- **Better Performance**: Async operations and optimized queries
- **Improved Reliability**: Circuit breakers and comprehensive error handling  
- **Enhanced Observability**: Structured logging, metrics, and tracing
- **Developer Experience**: Better tooling, testing, and documentation
- **Maintainability**: Clear separation of concerns and modern patterns

The system is now ready for scale and can handle the growing needs of the entrepreneurship ecosystem platform while maintaining high code quality and developer productivity.