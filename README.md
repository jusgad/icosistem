# Ecosistema de Emprendimiento - Modern Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0+](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-passing-green.svg)](#testing)
[![API Docs](https://img.shields.io/badge/API-documented-blue.svg)](docs/API_REFERENCE.md)

> **A modern, scalable platform for managing entrepreneurship ecosystems with mentorship, project tracking, and community building.**

## 🚀 Features

### ✨ Modern Architecture
- **Hexagonal Architecture**: Clean separation of concerns with ports & adapters
- **Async-First**: Built with async/await for high performance
- **Type Safety**: Full type hints with modern Python typing
- **Modern Validation**: Pydantic models for comprehensive data validation
- **Auto-Documentation**: OpenAPI/Swagger documentation with Flask-RESTX

### 🔐 Advanced Authentication
- **JWT Tokens**: Secure authentication with access/refresh tokens
- **Two-Factor Auth**: TOTP support with backup codes
- **OAuth Integration**: Google, Microsoft, GitHub login
- **Session Management**: Device tracking and management
- **Account Security**: Rate limiting, lockout protection

### 👥 User Management
- **Multiple User Types**: Entrepreneurs, Allies/Mentors, Clients, Admins
- **Rich Profiles**: Comprehensive user profiles with skills, achievements
- **Verification System**: Email and phone verification
- **Permission System**: Role-based access control
- **Activity Tracking**: User activity and engagement metrics

### 📊 Project Management
- **Project Lifecycle**: From idea to scale with stage tracking
- **Milestone Management**: Define and track project milestones
- **Team Collaboration**: Team member management and roles
- **Progress Tracking**: Visual progress indicators and metrics
- **Document Management**: File uploads and document sharing

### 🎯 Mentorship System
- **Mentor Matching**: AI-powered mentor-entrepreneur matching
- **Session Management**: Schedule and track mentorship sessions
- **Goal Setting**: Define and track mentorship goals
- **Feedback System**: Session feedback and ratings
- **Impact Measurement**: Track mentorship effectiveness

### 📈 Analytics & Reporting
- **Real-time Dashboard**: Live metrics and KPIs
- **User Analytics**: Engagement and growth metrics
- **Project Analytics**: Success rates and trends
- **Custom Reports**: Generate detailed reports
- **Data Export**: Export data in various formats

### 🔧 Modern Tech Stack
- **Backend**: Python 3.11+, Flask 3.0+, SQLAlchemy 2.0+
- **Database**: PostgreSQL 15+ with async support
- **Caching**: Redis 7+ for sessions and caching
- **API**: RESTful API with OpenAPI documentation
- **Validation**: Pydantic for data validation
- **Testing**: pytest with comprehensive test suite
- **Observability**: OpenTelemetry, Prometheus, Sentry

## 📋 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **PostgreSQL 15+**
- **Redis 7+**
- **Docker & Docker Compose** (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/icosistem.git
   cd icosistem
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .[dev]
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start services (Docker)**
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Initialize database**
   ```bash
   flask db upgrade
   flask seed-data  # Optional: load sample data
   ```

6. **Start the application**
   ```bash
   python run.py
   ```

7. **Visit the application**
   - **API**: http://localhost:5000/api/v2/docs/
   - **Health Check**: http://localhost:5000/api/v2/health/

### Docker Setup (Recommended)

```bash
# Development environment
docker-compose up --build

# Production environment  
docker-compose -f docker-compose.prod.yml up --build
```

## 📚 Documentation

### Architecture & Design
- [**Modern Architecture Guide**](docs/MODERN_ARCHITECTURE.md) - Complete architecture overview
- [**Developer Guide**](docs/DEVELOPER_GUIDE.md) - Development setup and patterns
- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation

### Deployment & Operations
- [**Deployment Guide**](docs/DEPLOYMENT.md) - Production deployment instructions
- [**Installation Guide**](docs/INSTALATION.md) - Detailed installation steps
- [**Change Log**](docs/CHANGELOG.md) - Version history and changes

### Legacy Documentation
- [**Legacy Analysis**](docs/ANALISIS_COMPLETO.md) - Previous system analysis
- [**Original README**](docs/README.md) - Original documentation

## 🏗️ Architecture

### Hexagonal Architecture

The system follows hexagonal architecture principles:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   REST API      │  │   WebSockets    │  │   CLI Tools     │  │
│  │  (Flask-RESTX)  │  │  (SocketIO)     │  │   (Click)       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                       Application Layer                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Use Cases                              │ │
│  │  • UserService  • ProjectService  • MentorshipService      │ │
│  │  • AuthService  • AnalyticsService • NotificationService   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                          Domain Layer                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Entities                               │ │
│  │  • User  • Project  • Mentorship  • Organization           │ │
│  │                                                             │ │
│  │                   Business Rules                            │ │
│  │  • Validation  • Domain Events  • Specifications           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   Database      │  │      Cache      │  │  External APIs  │  │
│  │  (PostgreSQL)   │  │    (Redis)      │  │ (Email, OAuth)  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

- **Modern Service Base**: Async-first service layer with observability
- **Pydantic Validation**: Type-safe data validation and serialization  
- **Flask-RESTX API**: Auto-documented REST API with OpenAPI
- **Async Database**: SQLAlchemy 2.0+ with async support
- **Circuit Breakers**: Resilient service communication
- **Observability**: Structured logging, metrics, and tracing

## 🧪 Testing

The project includes a comprehensive test suite with modern patterns:

```bash
# Run all tests
pytest

# Run specific test types
pytest -m unit        # Unit tests
pytest -m integration # Integration tests  
pytest -m api         # API tests

# Run with coverage
pytest --cov=app --cov-report=html

# Run performance tests
pytest -m slow

# Run tests in parallel
pytest -n auto
```

### Test Categories

- **Unit Tests**: Service layer and business logic
- **Integration Tests**: Database and external service integration
- **API Tests**: Complete API endpoint testing
- **Performance Tests**: Load and stress testing

### Modern Testing Features

- **Factory Pattern**: Clean test data generation with Factory Boy
- **Async Support**: Full async test support with pytest-asyncio
- **Comprehensive Fixtures**: Database, authentication, and API fixtures
- **Mock Services**: Comprehensive mocking for external dependencies

## 📊 Monitoring & Observability

### Built-in Observability

- **Health Checks**: Kubernetes-ready liveness and readiness probes
- **Metrics**: Prometheus metrics collection
- **Tracing**: OpenTelemetry distributed tracing
- **Logging**: Structured logging with Loguru
- **Error Tracking**: Sentry integration

### Monitoring Endpoints

- `GET /api/v2/health/` - Basic health check
- `GET /api/v2/health/detailed` - Comprehensive health with dependencies
- `GET /api/v2/health/liveness` - Kubernetes liveness probe
- `GET /api/v2/health/readiness` - Kubernetes readiness probe
- `GET /metrics` - Prometheus metrics endpoint

## 🚀 Deployment

### Environments

- **Development**: Local development with hot reload
- **Testing**: Automated testing environment
- **Staging**: Pre-production testing environment  
- **Production**: High-availability production deployment

### Deployment Options

1. **Docker Compose** (Recommended for development)
2. **Kubernetes** (Recommended for production)
3. **Traditional Server** (Virtual machines)
4. **Cloud Platforms** (AWS, GCP, Azure)

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

## 📈 Performance

### Optimizations

- **Async Operations**: Non-blocking database and HTTP operations
- **Connection Pooling**: Optimized database connection management
- **Caching Strategy**: Multi-layer caching with Redis
- **Query Optimization**: Efficient database queries with proper indexing
- **Rate Limiting**: Protection against abuse and overload

### Benchmarks

| Metric | Value |
|--------|--------|
| API Response Time | < 100ms (p95) |
| Database Queries | < 50ms (p95) |
| Concurrent Users | 1000+ |
| Throughput | 500+ req/sec |
| Memory Usage | < 512MB |

## 🛠️ Development

### Modern Development Workflow

1. **Feature Branch**: Create feature branch from `main`
2. **Development**: Use modern Python patterns and async/await
3. **Testing**: Write comprehensive tests (unit, integration, API)
4. **Code Quality**: Run linting, formatting, and type checking
5. **Documentation**: Update relevant documentation
6. **Pull Request**: Create PR with detailed description
7. **Review**: Code review and automated checks
8. **Deploy**: Automated deployment after merge

### Code Quality Tools

```bash
# Format code
black .
isort .

# Lint code  
ruff check .
ruff check . --fix

# Type checking
mypy .

# Security scan
bandit -r app/

# Pre-commit hooks
pre-commit run --all-files
```

### Development Tools

- **Black**: Code formatting
- **isort**: Import sorting  
- **Ruff**: Ultra-fast Python linting
- **mypy**: Static type checking
- **pre-commit**: Git hooks for quality
- **pytest**: Modern testing framework

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Contribution Guidelines

- Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages
- Write tests for all new features
- Ensure all tests pass and code quality checks pass
- Update documentation for any API changes
- Follow the existing code style and patterns

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Flask Team** for the excellent web framework
- **Pydantic Team** for modern data validation
- **SQLAlchemy Team** for the powerful ORM
- **Open Source Community** for the amazing ecosystem

## 📞 Support

### Getting Help

- **Documentation**: Check the [docs](docs/) directory
- **Issues**: Create an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact us at support@ecosistema-emprendimiento.com

### Community

- **Discord**: Join our developer community
- **Twitter**: Follow [@EcosistemaAPI](https://twitter.com/EcosistemaAPI)
- **Blog**: Read updates on our [blog](https://blog.ecosistema-emprendimiento.com)

### Professional Support

For enterprise support, consulting, or custom development:

- **Email**: enterprise@ecosistema-emprendimiento.com
- **Website**: https://ecosistema-emprendimiento.com/enterprise

---

<div align="center">

**Made with ❤️ by the Ecosistema Team**

[Website](https://ecosistema-emprendimiento.com) • 
[Documentation](docs/) • 
[API Reference](docs/API_REFERENCE.md) • 
[Contributing](CONTRIBUTING.md)

</div>