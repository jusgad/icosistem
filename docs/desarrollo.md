# 🛠️ Guía del Desarrollador

> **Guía completa para configurar el entorno de desarrollo y mejores prácticas**

## 📋 Tabla de Contenidos

- [🚀 Setup Inicial de Desarrollo](#-setup-inicial-de-desarrollo)
- [🏗️ Arquitectura del Proyecto](#️-arquitectura-del-proyecto)
- [📁 Estructura de Directorios](#-estructura-de-directorios)
- [🔄 Flujo de Desarrollo](#-flujo-de-desarrollo)
- [🧪 Testing y Calidad](#-testing-y-calidad)
- [📝 Convenciones de Código](#-convenciones-de-código)
- [🔧 Herramientas de Desarrollo](#-herramientas-de-desarrollo)
- [🐛 Debugging](#-debugging)
- [📊 Monitoreo y Profiling](#-monitoreo-y-profiling)

## 🚀 Setup Inicial de Desarrollo

### ⚙️ Configuración del IDE

#### Visual Studio Code (Recomendado)

1. **Instalar Extensiones Esenciales**:
   ```json
   {
     "recommendations": [
       "ms-python.python",
       "ms-python.flake8",
       "ms-python.black-formatter",
       "ms-python.isort",
       "ms-python.mypy-type-checker",
       "ms-vscode.vscode-json",
       "bradlc.vscode-tailwindcss",
       "esbenp.prettier-vscode",
       "ms-vscode.vscode-yaml",
       "formulahendry.auto-rename-tag",
       "ms-vscode.vscode-eslint"
     ]
   }
   ```

2. **Configurar Settings.json**:
   ```json
   {
     "python.defaultInterpreterPath": "./venv/bin/python",
     "python.formatting.provider": "black",
     "python.linting.enabled": true,
     "python.linting.flake8Enabled": true,
     "python.linting.mypyEnabled": true,
     "python.testing.pytestEnabled": true,
     "python.testing.unittestEnabled": false,
     "editor.formatOnSave": true,
     "editor.codeActionsOnSave": {
       "source.organizeImports": true
     },
     "files.exclude": {
       "**/__pycache__": true,
       "**/*.pyc": true,
       ".pytest_cache": true,
       ".coverage": true,
       "htmlcov": true
     }
   }
   ```

3. **Configurar Launch.json** para debugging:
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "Flask Dev",
         "type": "python",
         "request": "launch",
         "program": "${workspaceFolder}/wsgi.py",
         "env": {
           "FLASK_ENV": "development",
           "FLASK_DEBUG": "1"
         },
         "args": [],
         "console": "integratedTerminal"
       },
       {
         "name": "Flask Tests",
         "type": "python",
         "request": "launch",
         "module": "pytest",
         "args": ["tests/", "-v"],
         "console": "integratedTerminal"
       }
     ]
   }
   ```

#### PyCharm

1. **Configurar Intérprete**:
   - File → Settings → Project → Python Interpreter
   - Agregar intérprete del venv: `./venv/bin/python`

2. **Configurar Code Style**:
   - Settings → Editor → Code Style → Python
   - Importar configuración desde `.editorconfig`

3. **Configurar Run Configurations**:
   - Flask Development Server
   - Pytest Configuration
   - Celery Worker

### 🐍 Entorno Virtual Avanzado

#### Configuración con pyenv (Recomendado)

```bash
# Instalar pyenv
curl https://pyenv.run | bash

# Agregar a ~/.bashrc o ~/.zshrc
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Instalar Python 3.11
pyenv install 3.11.8
pyenv local 3.11.8

# Crear entorno virtual
python -m venv venv
source venv/bin/activate
```

#### Variables de Entorno de Desarrollo

```bash
# .env.development
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_APP=wsgi.py

# Database
DATABASE_URL=postgresql://icosistem_dev:password@localhost:5432/icosistem_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Debug específico
SQLALCHEMY_ECHO=False  # True para ver queries SQL
WERKZEUG_DEBUG_PIN=off
DEBUG_TB_ENABLED=True

# Profiling
PROFILE=False  # True para habilitar profiling

# Email debug
MAIL_SUPPRESS_SEND=True  # No enviar emails reales
MAIL_DEBUG=True
```

### 📦 Dependencias de Desarrollo

```bash
# Instalar todas las dependencias de desarrollo
pip install -r requirements-dev.txt

# Pre-commit hooks
pre-commit install

# Herramientas globales
npm install -g nodemon webpack-dev-server
```

## 🏗️ Arquitectura del Proyecto

### 🎯 Principios de Arquitectura

El proyecto sigue los principios de **Arquitectura Limpia** y **Domain-Driven Design**:

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTACIÓN                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   REST API  │  │  WebSocket  │  │     CLI     │         │
│  │ (Flask-RESTX)│  │ (SocketIO)  │  │  (Click)    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                    APLICACIÓN                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  USE CASES                            │  │
│  │ • UserService     • ProjectService                    │  │
│  │ • AuthService     • MentorshipService                 │  │
│  │ • EmailService    • NotificationService               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                     DOMINIO                                 │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   ENTIDADES     │  │  REGLAS NEGOCIO │                  │
│  │ • User          │  │ • Validations   │                  │
│  │ • Project       │  │ • Policies      │                  │
│  │ • Organization  │  │ • Events        │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                 INFRAESTRUCTURA                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  DATABASE   │  │    CACHE    │  │  EXTERNAL   │         │
│  │(PostgreSQL) │  │   (Redis)   │  │   SERVICES  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 📊 Patrones de Diseño Implementados

1. **Repository Pattern**: Abstracción de la capa de datos
2. **Service Layer Pattern**: Lógica de negocio centralizada
3. **Factory Pattern**: Creación de objetos complejos
4. **Observer Pattern**: Eventos del dominio
5. **Strategy Pattern**: Algoritmos intercambiables
6. **Command Pattern**: Operaciones como objetos

## 📁 Estructura de Directorios

```
icosistem/
├── 📁 app/                          # Código principal de la aplicación
│   ├── 📄 __init__.py              # Factory de la aplicación Flask
│   ├── 📄 config.py                # Configuraciones
│   ├── 📄 extensions.py            # Extensiones de Flask
│   ├── 📄 wsgi.py                  # Punto de entrada WSGI
│   │
│   ├── 📁 core/                    # Núcleo del sistema
│   │   ├── 📄 __init__.py
│   │   ├── 📄 base_service.py      # Clase base para servicios
│   │   ├── 📄 exceptions.py        # Excepciones personalizadas
│   │   ├── 📄 validators.py        # Validadores comunes
│   │   └── 📄 decorators.py        # Decoradores útiles
│   │
│   ├── 📁 models/                  # Modelos de base de datos (SQLAlchemy)
│   │   ├── 📄 __init__.py
│   │   ├── 📄 base.py              # Clase base para modelos
│   │   ├── 📄 user.py              # Modelo de Usuario
│   │   ├── 📄 project.py           # Modelo de Proyecto
│   │   ├── 📄 organization.py      # Modelo de Organización
│   │   ├── 📄 mentorship.py        # Modelo de Mentoría
│   │   └── 📄 mixins.py            # Mixins comunes
│   │
│   ├── 📁 schemas/                 # Schemas Pydantic/Marshmallow
│   │   ├── 📄 __init__.py
│   │   ├── 📄 user.py              # Schemas de Usuario
│   │   ├── 📄 project.py           # Schemas de Proyecto
│   │   ├── 📄 auth.py              # Schemas de autenticación
│   │   └── 📄 common.py            # Schemas comunes
│   │
│   ├── 📁 services/                # Lógica de negocio
│   │   ├── 📄 __init__.py
│   │   ├── 📄 user_service.py      # Servicio de usuarios
│   │   ├── 📄 auth_service.py      # Servicio de autenticación
│   │   ├── 📄 project_service.py   # Servicio de proyectos
│   │   ├── 📄 email_service.py     # Servicio de email
│   │   └── 📄 notification_service.py
│   │
│   ├── 📁 repositories/            # Acceso a datos (Repository Pattern)
│   │   ├── 📄 __init__.py
│   │   ├── 📄 base_repository.py   # Repositorio base
│   │   ├── 📄 user_repository.py   # Repositorio de usuarios
│   │   └── 📄 project_repository.py
│   │
│   ├── 📁 api/                     # Endpoints de la API REST
│   │   ├── 📄 __init__.py
│   │   ├── 📁 v1/                  # API versión 1 (legacy)
│   │   └── 📁 v2/                  # API versión 2 (actual)
│   │       ├── 📄 __init__.py
│   │       ├── 📄 auth.py          # Endpoints de autenticación
│   │       ├── 📄 users.py         # Endpoints de usuarios
│   │       ├── 📄 projects.py      # Endpoints de proyectos
│   │       └── 📄 health.py        # Health checks
│   │
│   ├── 📁 views/                   # Vistas web (si aplica)
│   │   ├── 📄 __init__.py
│   │   ├── 📄 main.py              # Vistas principales
│   │   ├── 📄 auth.py              # Vistas de autenticación
│   │   └── 📄 dashboard.py         # Dashboard
│   │
│   ├── 📁 utils/                   # Utilidades y helpers
│   │   ├── 📄 __init__.py
│   │   ├── 📄 auth.py              # Utilidades de autenticación
│   │   ├── 📄 email.py             # Utilidades de email
│   │   ├── 📄 file_upload.py       # Manejo de archivos
│   │   ├── 📄 pagination.py        # Paginación
│   │   └── 📄 date_utils.py        # Utilidades de fecha
│   │
│   ├── 📁 tasks/                   # Tareas de Celery
│   │   ├── 📄 __init__.py
│   │   ├── 📄 email_tasks.py       # Tareas de email
│   │   ├── 📄 notification_tasks.py
│   │   └── 📄 cleanup_tasks.py     # Tareas de limpieza
│   │
│   ├── 📁 static/                  # Assets estáticos
│   │   ├── 📁 src/                 # Código fuente frontend
│   │   │   ├── 📁 js/              # JavaScript
│   │   │   ├── 📁 scss/            # Estilos SCSS
│   │   │   └── 📁 images/          # Imágenes
│   │   └── 📁 dist/                # Assets compilados
│   │
│   ├── 📁 templates/               # Plantillas Jinja2
│   │   ├── 📁 layouts/             # Layouts base
│   │   ├── 📁 auth/                # Templates de auth
│   │   ├── 📁 dashboard/           # Templates de dashboard
│   │   └── 📁 emails/              # Templates de email
│   │
│   └── 📁 cli/                     # Comandos CLI
│       ├── 📄 __init__.py
│       ├── 📄 user_commands.py     # Comandos de usuario
│       ├── 📄 db_commands.py       # Comandos de BD
│       └── 📄 seed_commands.py     # Comandos de semilla
│
├── 📁 tests/                       # Tests
│   ├── 📄 __init__.py
│   ├── 📄 conftest.py              # Configuración pytest
│   ├── 📁 unit/                    # Tests unitarios
│   ├── 📁 integration/             # Tests de integración
│   ├── 📁 api/                     # Tests de API
│   ├── 📁 fixtures/                # Fixtures de test
│   └── 📁 utils/                   # Utilidades de test
│
├── 📁 migrations/                  # Migraciones Alembic
│   ├── 📄 alembic.ini
│   ├── 📄 env.py
│   └── 📁 versions/                # Archivos de migración
│
├── 📁 docker/                      # Configuraciones Docker
│   ├── 📄 Dockerfile.dev           # Docker desarrollo
│   ├── 📄 Dockerfile.prod          # Docker producción
│   └── 📄 docker-entrypoint.sh     # Script de entrada
│
├── 📁 scripts/                     # Scripts de automatización
│   ├── 📄 setup.sh                 # Script de setup
│   ├── 📄 deploy.sh                # Script de deploy
│   ├── 📄 backup.sh                # Script de backup
│   └── 📄 health_check.py          # Script de health check
│
├── 📁 docs/                        # Documentación
│   ├── 📄 instalacion.md           # Guía de instalación
│   ├── 📄 desarrollo.md            # Guía de desarrollo
│   ├── 📄 api.md                   # Documentación API
│   └── 📄 arquitectura.md          # Documentación arquitectura
│
├── 📁 monitoring/                  # Configuraciones de monitoreo
│   ├── 📄 prometheus.yml           # Config Prometheus
│   └── 📄 grafana-dashboards/      # Dashboards Grafana
│
├── 📄 .env.example                 # Variables de entorno ejemplo
├── 📄 .gitignore                   # Git ignore
├── 📄 .pre-commit-config.yaml      # Pre-commit hooks
├── 📄 requirements.txt             # Dependencias Python
├── 📄 requirements-dev.txt         # Dependencias desarrollo
├── 📄 requirements-prod.txt        # Dependencias producción
├── 📄 package.json                 # Dependencias Node.js
├── 📄 pyproject.toml               # Configuración Python moderna
├── 📄 pytest.ini                  # Configuración pytest
├── 📄 docker-compose.yml           # Docker Compose desarrollo
├── 📄 docker-compose.prod.yml      # Docker Compose producción
└── 📄 README.md                    # Documentación principal
```

## 🔄 Flujo de Desarrollo

### 🌿 Git Workflow

#### Configuración Inicial

```bash
# Configurar Git
git config user.name "Tu Nombre"
git config user.email "tu@email.com"

# Configurar pre-commit
pre-commit install
```

#### Flujo de Feature Branch

```bash
# 1. Actualizar main
git checkout main
git pull origin main

# 2. Crear branch de feature
git checkout -b feature/nombre-descriptivo

# 3. Hacer cambios y commits
git add .
git commit -m "feat: descripción del cambio"

# 4. Push del branch
git push -u origin feature/nombre-descriptivo

# 5. Crear Pull Request en GitHub
```

#### Convenciones de Commit

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Tipos de commit
feat:     # Nueva funcionalidad
fix:      # Corrección de bug
docs:     # Cambios en documentación
style:    # Cambios de formato (no código)
refactor: # Refactorización de código
test:     # Agregar o corregir tests
chore:    # Tareas de mantenimiento

# Ejemplos
git commit -m "feat(auth): agregar autenticación con Google OAuth"
git commit -m "fix(api): corregir validación de email en registro"
git commit -m "docs: actualizar guía de instalación"
```

### 🔧 Scripts de Desarrollo

#### Makefile para Tareas Comunes

```makefile
# Makefile
.PHONY: help install dev test lint clean docker

help:  ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install:  ## Instalar dependencias
	pip install -r requirements-dev.txt
	npm install
	pre-commit install

dev:  ## Iniciar servidor de desarrollo
	flask run --reload --debugger

test:  ## Ejecutar tests
	pytest -v --cov=app

test-watch:  ## Ejecutar tests en modo watch
	ptw -- --cov=app

lint:  ## Ejecutar linters
	black .
	isort .
	flake8 app/
	mypy app/

lint-check:  ## Verificar linting sin cambios
	black --check .
	isort --check .
	flake8 app/
	mypy app/

clean:  ## Limpiar archivos temporales
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/

docker:  ## Construir imagen Docker
	docker build -f docker/Dockerfile.dev -t icosistem:dev .

docker-run:  ## Ejecutar con Docker
	docker-compose up -d

migrate:  ## Ejecutar migraciones
	flask db upgrade

seed:  ## Cargar datos de prueba
	flask seed-data --sample-data
```

#### Scripts de Utilidad

```bash
# scripts/dev-setup.sh
#!/bin/bash
echo "🚀 Configurando entorno de desarrollo..."

# Verificar Python
python --version | grep -q "3.11" || {
    echo "❌ Python 3.11+ requerido"
    exit 1
}

# Instalar dependencias
echo "📦 Instalando dependencias..."
pip install -r requirements-dev.txt
npm install

# Configurar pre-commit
echo "🔧 Configurando pre-commit hooks..."
pre-commit install

# Configurar base de datos
echo "🗄️ Configurando base de datos..."
flask db upgrade
flask seed-data

echo "✅ Setup completado!"
echo "💡 Ejecuta 'flask run' para iniciar el servidor"
```

### 🧑‍💻 Comandos CLI Personalizados

```python
# app/cli/dev_commands.py
import click
from flask.cli import with_appcontext

@click.group()
def dev():
    """Comandos de desarrollo."""
    pass

@dev.command()
@click.option('--count', default=10, help='Número de usuarios a crear')
@with_appcontext
def create_test_users(count):
    """Crear usuarios de prueba."""
    from app.services.user_service import UserService
    from faker import Faker
    
    fake = Faker('es_ES')
    service = UserService()
    
    for _ in range(count):
        user_data = {
            'name': fake.name(),
            'email': fake.email(),
            'password': 'test123',
            'role': fake.random_element(['emprendedor', 'mentor', 'cliente'])
        }
        service.create_user(user_data)
    
    click.echo(f"✅ {count} usuarios de prueba creados")

@dev.command()
@with_appcontext  
def clear_cache():
    """Limpiar caché Redis."""
    from app.extensions import cache
    
    cache.clear()
    click.echo("✅ Cache limpiado")

@dev.command()
@click.option('--email', required=True, help='Email del usuario')
@with_appcontext
def make_admin(email):
    """Hacer admin a un usuario."""
    from app.services.user_service import UserService
    
    service = UserService()
    user = service.get_by_email(email)
    
    if not user:
        click.echo(f"❌ Usuario {email} no encontrado")
        return
    
    user.role = 'admin'
    service.update_user(user.id, {'role': 'admin'})
    click.echo(f"✅ {email} es ahora admin")
```

## 🧪 Testing y Calidad

### 🔬 Configuración de Testing

#### Estructura de Tests

```python
# tests/conftest.py
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Project, Organization

@pytest.fixture
def app():
    """Fixture de la aplicación Flask."""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Fixture del cliente de test."""
    return app.test_client()

@pytest.fixture
def auth_headers(client):
    """Headers de autenticación para tests."""
    # Crear usuario de test y login
    response = client.post('/api/v2/auth/login', json={
        'email': 'test@example.com',
        'password': 'test123'
    })
    token = response.json['access_token']
    
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

@pytest.fixture
def sample_user():
    """Usuario de ejemplo."""
    return User(
        name='Test User',
        email='test@example.com',
        password='hashed_password',
        role='emprendedor'
    )
```

#### Tests Unitarios

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import Mock, patch
from app.services.user_service import UserService
from app.models import User

class TestUserService:
    
    def setup_method(self):
        self.service = UserService()
        
    @patch('app.repositories.user_repository.UserRepository.create')
    def test_create_user_success(self, mock_create):
        # Arrange
        user_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'password': 'test123'
        }
        mock_user = Mock(spec=User)
        mock_create.return_value = mock_user
        
        # Act
        result = self.service.create_user(user_data)
        
        # Assert
        assert result == mock_user
        mock_create.assert_called_once()
    
    def test_validate_email_format(self):
        # Test con email válido
        assert self.service._validate_email('test@example.com') == True
        
        # Test con email inválido
        assert self.service._validate_email('invalid-email') == False
```

#### Tests de Integración

```python
# tests/integration/test_auth_flow.py
import pytest
from app.models import User

class TestAuthFlow:
    
    def test_complete_registration_flow(self, client, app):
        with app.app_context():
            # 1. Registrar usuario
            response = client.post('/api/v2/auth/register', json={
                'name': 'Test User',
                'email': 'test@example.com',
                'password': 'test123',
                'role': 'emprendedor'
            })
            
            assert response.status_code == 201
            data = response.get_json()
            assert 'user' in data
            assert data['user']['email'] == 'test@example.com'
            
            # 2. Verificar que el usuario se guardó en BD
            user = User.query.filter_by(email='test@example.com').first()
            assert user is not None
            assert user.name == 'Test User'
            
            # 3. Login
            login_response = client.post('/api/v2/auth/login', json={
                'email': 'test@example.com',
                'password': 'test123'
            })
            
            assert login_response.status_code == 200
            login_data = login_response.get_json()
            assert 'access_token' in login_data
```

#### Tests de API

```python
# tests/api/test_user_endpoints.py
import pytest

class TestUserEndpoints:
    
    def test_get_user_profile(self, client, auth_headers):
        response = client.get('/api/v2/users/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'id' in data
        assert 'name' in data
        assert 'email' in data
        
    def test_update_user_profile(self, client, auth_headers):
        update_data = {
            'name': 'Updated Name',
            'bio': 'Nueva biografía'
        }
        
        response = client.put('/api/v2/users/me', 
                            json=update_data, 
                            headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['name'] == 'Updated Name'
        assert data['bio'] == 'Nueva biografía'
        
    def test_unauthorized_access(self, client):
        response = client.get('/api/v2/users/me')
        assert response.status_code == 401
```

### 📊 Coverage y Reporting

```bash
# Ejecutar tests con coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Ver reporte en browser
open htmlcov/index.html

# Generar reporte XML para CI
pytest --cov=app --cov-report=xml

# Tests con benchmarking
pytest --benchmark-only

# Tests de performance
pytest -m slow --benchmark-sort=mean
```

### 🔍 Linting y Formateo

#### Configuración Completa

```bash
# Formatear código
black app/ tests/
isort app/ tests/

# Linting
flake8 app/ tests/
pylint app/
mypy app/

# Seguridad
bandit -r app/ -c bandit.yaml
safety check

# Todo en uno
make lint
```

#### Pre-commit Hooks

Los hooks se ejecutan automáticamente antes de cada commit:

```yaml
# .pre-commit-config.yaml (extracto)
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
        
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        
  - repo: https://github.com/pycqa/flake8
    rev: 7.1.0
    hooks:
      - id: flake8
```

## 📝 Convenciones de Código

### 🐍 Python Style Guide

#### Nomenclatura

```python
# Clases: PascalCase
class UserService:
    pass

class ProjectRepository:
    pass

# Funciones y variables: snake_case
def create_user(user_data):
    user_name = user_data.get('name')
    return user_name

# Constantes: SCREAMING_SNAKE_CASE
DATABASE_URL = 'postgresql://...'
MAX_FILE_SIZE = 1024 * 1024  # 1MB

# Privados: prefijo con _
class MyClass:
    def __init__(self):
        self._private_var = 'private'
        self.public_var = 'public'
    
    def _private_method(self):
        pass
    
    def public_method(self):
        pass
```

#### Docstrings

```python
def create_user(user_data: dict) -> User:
    """
    Crear un nuevo usuario en el sistema.
    
    Args:
        user_data (dict): Datos del usuario a crear.
            Debe contener: name, email, password, role.
    
    Returns:
        User: Usuario creado con ID asignado.
    
    Raises:
        ValidationError: Si los datos no son válidos.
        DuplicateEmailError: Si el email ya existe.
    
    Example:
        >>> user_data = {
        ...     'name': 'Juan Pérez',
        ...     'email': 'juan@example.com',
        ...     'password': 'secure123',
        ...     'role': 'emprendedor'
        ... }
        >>> user = create_user(user_data)
        >>> print(user.id)
        1
    """
    pass
```

#### Type Hints

```python
from typing import Optional, List, Dict, Union
from app.models import User, Project

def get_user_projects(
    user_id: int, 
    status: Optional[str] = None,
    limit: int = 10
) -> List[Project]:
    """Obtener proyectos de un usuario."""
    pass

def process_user_data(data: Dict[str, Union[str, int]]) -> User:
    """Procesar datos de usuario."""
    pass

# Para APIs con Pydantic
from pydantic import BaseModel

class UserCreateSchema(BaseModel):
    name: str
    email: str
    password: str
    role: str
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Juan Pérez",
                "email": "juan@example.com", 
                "password": "secure123",
                "role": "emprendedor"
            }
        }
```

### 🌐 Frontend Conventions

#### JavaScript

```javascript
// Usar const/let, no var
const API_BASE_URL = '/api/v2';
let currentUser = null;

// Funciones: camelCase
function getUserProjects(userId) {
    return fetch(`${API_BASE_URL}/users/${userId}/projects`);
}

// Clases: PascalCase
class ProjectManager {
    constructor(apiClient) {
        this.apiClient = apiClient;
    }
    
    async createProject(projectData) {
        return await this.apiClient.post('/projects', projectData);
    }
}

// Constantes: SCREAMING_SNAKE_CASE
const MAX_UPLOAD_SIZE = 5 * 1024 * 1024; // 5MB

// Usar template literals
const message = `Usuario ${user.name} creó el proyecto "${project.title}"`;
```

#### CSS/SCSS

```scss
// Variables con prefijo --
:root {
    --color-primary: #007bff;
    --color-secondary: #6c757d;
    --font-family-base: 'Inter', sans-serif;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 2rem;
}

// Clases BEM
.project-card {
    padding: var(--spacing-md);
    border-radius: 8px;
    
    &__header {
        margin-bottom: var(--spacing-sm);
        font-size: 1.2rem;
        font-weight: 600;
    }
    
    &__content {
        color: var(--color-secondary);
    }
    
    &--featured {
        border: 2px solid var(--color-primary);
    }
}

// Responsive con mobile-first
.container {
    padding: var(--spacing-sm);
    
    @media (min-width: 768px) {
        padding: var(--spacing-md);
    }
    
    @media (min-width: 1024px) {
        padding: var(--spacing-lg);
    }
}
```

## 🔧 Herramientas de Desarrollo

### ⚡ Hot Reload y Live Reload

#### Flask Development Server

```bash
# Con recarga automática
flask run --reload --debugger

# Con host específico
flask run --host=0.0.0.0 --port=5000 --reload
```

#### Frontend Watch Mode

```bash
# Webpack development server
npm run dev

# Watch mode para SCSS
npm run watch:css

# Watch mode completo
npm run watch
```

### 🔍 Debugging

#### Python Debugging

```python
# Con debugger integrado
import pdb; pdb.set_trace()  # Python estándar

# Con ipdb (mejor interfaz)
import ipdb; ipdb.set_trace()

# Con breakpoint() (Python 3.7+)
breakpoint()  # Recomendado

# Debug en servicios
class UserService:
    def create_user(self, user_data):
        breakpoint()  # Parar aquí para debug
        # ... resto del código
```

#### Flask Debug Mode

```python
# app/config.py
class DevelopmentConfig:
    DEBUG = True
    DEBUG_TB_ENABLED = True  # Flask-DebugToolbar
    DEBUG_TB_INTERCEPT_REDIRECTS = False
```

#### Logging Estratégico

```python
# app/utils/logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(app):
    if not app.debug:
        file_handler = RotatingFileHandler(
            'logs/app.log', 
            maxBytes=10240, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Aplicación iniciada')

# En servicios
import logging

logger = logging.getLogger(__name__)

class UserService:
    def create_user(self, user_data):
        logger.info(f"Creando usuario: {user_data.get('email')}")
        try:
            # ... lógica
            logger.info(f"Usuario creado exitosamente: {user.id}")
            return user
        except Exception as e:
            logger.error(f"Error creando usuario: {str(e)}")
            raise
```

### 📊 Profiling y Performance

#### Python Profiling

```python
# Profiling con cProfile
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Tu código aquí
    result = expensive_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('tottime')
    stats.print_stats(20)  # Top 20 funciones
    
    return result

# Con decorador
from functools import wraps
import time

def measure_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} tomó {end - start:.2f} segundos")
        return result
    return wrapper

@measure_time
def slow_function():
    time.sleep(1)
```

#### Database Query Profiling

```python
# Habilitar logging de queries SQL
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# O en configuración
class DevelopmentConfig:
    SQLALCHEMY_ECHO = True  # Mostrar todas las queries
    
# Profiling manual de queries
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 0.1:  # Queries lentas (>100ms)
        app.logger.warning(f"Slow query: {total:.2f}s - {statement[:100]}")
```

### 🔧 Scripts de Automatización

#### Script de Setup Completo

```bash
#!/bin/bash
# scripts/full-setup.sh

set -e  # Salir en cualquier error

echo "🚀 Configuración completa del proyecto..."

# Verificar prerrequisitos
command -v python3.11 >/dev/null 2>&1 || { 
    echo "❌ Python 3.11 requerido"; 
    exit 1; 
}

command -v node >/dev/null 2>&1 || { 
    echo "❌ Node.js requerido"; 
    exit 1; 
}

# Crear entorno virtual
echo "🐍 Creando entorno virtual..."
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
echo "📦 Instalando dependencias Python..."
pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt

# Instalar dependencias Node.js
echo "📦 Instalando dependencias Node.js..."
npm install

# Configurar pre-commit
echo "🔧 Configurando pre-commit..."
pre-commit install

# Configurar base de datos
echo "🗄️ Configurando base de datos..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Configura tu archivo .env antes de continuar"
fi

# Verificar servicios
echo "🔍 Verificando servicios..."
if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -q || echo "⚠️  PostgreSQL no está corriendo"
fi

if command -v redis-cli >/dev/null 2>&1; then
    redis-cli ping >/dev/null 2>&1 || echo "⚠️  Redis no está corriendo"
fi

# Ejecutar migraciones
echo "🗄️ Ejecutando migraciones..."
flask db upgrade || echo "⚠️  Error en migraciones - verifica tu configuración de BD"

# Compilar assets
echo "🎨 Compilando assets..."
npm run build

echo "✅ Setup completado!"
echo "💡 Ejecuta 'flask run' para iniciar el servidor de desarrollo"
```

#### Script de Limpieza

```bash
#!/bin/bash
# scripts/cleanup.sh

echo "🧹 Limpiando archivos temporales..."

# Python
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
rm -rf .pytest_cache/
rm -rf htmlcov/
rm -f .coverage

# Node.js
rm -rf node_modules/.cache/
rm -rf .npm/

# Logs
rm -rf logs/*.log*

# Build artifacts
rm -rf build/
rm -rf dist/
rm -rf app/static/dist/*

echo "✅ Limpieza completada!"
```

---

## 💡 Tips y Mejores Prácticas

### 🚀 Productividad

1. **Usa alias útiles**:
   ```bash
   # En ~/.bashrc o ~/.zshrc
   alias frun="flask run --reload --debugger"
   alias ftest="pytest -v --cov=app"
   alias flint="black . && isort . && flake8 app/"
   ```

2. **Configurar debugging en IDE**:
   - VS Code: Configurar launch.json
   - PyCharm: Run configurations
   - Usar breakpoints en lugar de print()

3. **Shortcuts de desarrollo**:
   ```python
   # En flask shell
   >>> from app.models import *
   >>> from app.extensions import db
   >>> user = User.query.first()
   ```

### 🔒 Seguridad en Desarrollo

1. **Nunca commitear secretos**:
   ```bash
   # Usar detect-secrets
   detect-secrets scan --baseline .secrets.baseline
   ```

2. **Usar variables de entorno**:
   ```python
   import os
   SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-for-dev'
   ```

3. **Configuraciones por ambiente**:
   ```python
   class Config:
       SECRET_KEY = os.environ.get('SECRET_KEY')
       
   class DevelopmentConfig(Config):
       DEBUG = True
       
   class ProductionConfig(Config):
       DEBUG = False
   ```

### 📈 Performance Tips

1. **Lazy loading de relaciones**:
   ```python
   # Malo
   users = User.query.all()
   for user in users:
       print(user.projects)  # N+1 queries
   
   # Bueno
   users = User.query.options(joinedload(User.projects)).all()
   ```

2. **Usar cache inteligentemente**:
   ```python
   from app.extensions import cache
   
   @cache.memoize(timeout=300)
   def expensive_calculation(params):
       # Cálculo costoso
       return result
   ```

3. **Índices en base de datos**:
   ```python
   class User(db.Model):
       email = db.Column(db.String(120), unique=True, index=True)
       created_at = db.Column(db.DateTime, index=True)
   ```

¡Esta guía te ayudará a ser más productivo y escribir código de mejor calidad! 🚀