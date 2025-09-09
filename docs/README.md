# 🚀 Ecosistema de Emprendimiento

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Flask Version](https://img.shields.io/badge/flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![Dependencies](https://img.shields.io/badge/dependencies-79%20optimized-brightgreen.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Performance](https://img.shields.io/badge/optimized-52.4%25%20smaller-orange.svg)](docs/instalacion.md)

> Plataforma integral para la gestión, seguimiento y desarrollo de ecosistemas de emprendimiento que conecta emprendedores, mentores, aliados estratégicos y stakeholders en un entorno colaborativo y productivo.

## 📋 Tabla de Contenidos

- [🎯 Descripción General](#-descripción-general)
- [✨ Características Principales](#-características-principales)
- [🛠️ Tecnologías Utilizadas](#️-tecnologías-utilizadas)
- [📋 Requisitos Previos](#-requisitos-previos)
- [🚀 Instalación y Configuración](#-instalación-y-configuración)
- [💻 Uso Básico](#-uso-básico)
- [📁 Estructura del Proyecto](#-estructura-del-proyecto)
- [🔌 API Documentation](#-api-documentation)
- [🧪 Testing](#-testing)
- [🚢 Deployment](#-deployment)
- [🤝 Contribución](#-contribución)
- [📝 Licencia](#-licencia)
- [📞 Soporte y Contacto](#-soporte-y-contacto)

## 🎯 Descripción General

El **Ecosistema de Emprendimiento** es una plataforma web moderna y escalable diseñada para facilitar la gestión integral de programas de emprendimiento. La aplicación conecta diferentes actores del ecosistema emprendedor en una sola plataforma, proporcionando herramientas avanzadas para el seguimiento, mentoría, desarrollo de proyectos y análisis de impacto.

### 🎭 Tipos de Usuario

- **🔧 Administradores**: Gestión completa del ecosistema, usuarios, programas y analytics
- **💡 Emprendedores**: Desarrollo de proyectos, acceso a mentoría y recursos
- **🤝 Aliados/Mentores**: Mentoría, seguimiento de emprendedores y reportes
- **👥 Clientes/Stakeholders**: Visualización de impacto, directorio de emprendimientos y analytics

## ✨ Características Principales

### 🎯 Gestión de Usuarios y Perfiles
- Sistema de autenticación robusto con OAuth2
- Perfiles personalizables por tipo de usuario
- Sistema de permisos granular
- Verificación de email y recuperación de contraseñas

### 📊 Dashboard Interactivos
- Dashboards específicos por rol de usuario
- Métricas en tiempo real
- Gráficos interactivos con Chart.js
- Widgets personalizables

### 👨‍🏫 Sistema de Mentoría
- Matching inteligente mentor-emprendedor
- Calendario integrado para sesiones
- Seguimiento de progreso y objetivos
- Sistema de evaluación y feedback

### 📈 Gestión de Proyectos
- Metodologías ágiles integradas
- Timeline y milestones
- Gestión de tareas y deadlines
- Seguimiento de KPIs y métricas

### 💬 Comunicación Integrada
- Sistema de mensajería en tiempo real (WebSockets)
- Notificaciones push inteligentes
- Integración con Google Meet
- Foros de discusión por programa

### 📅 Gestión de Eventos y Reuniones
- Integración completa con Google Calendar
- Programación automática de reuniones
- Recordatorios automáticos
- Gestión de salas virtuales

### 📊 Analytics e Informes
- Reportes personalizables en PDF/Excel
- Métricas de impacto en tiempo real
- Análisis predictivo con ML
- Dashboards ejecutivos

### 🔌 Integraciones Externas
- Google Workspace (Calendar, Meet, Drive)
- Sistemas de pago (Stripe, PayPal)
- APIs de terceros mediante webhooks
- Sincronización con CRMs externos

### 🌐 API REST Completa
- API RESTful versionada (v1)
- Autenticación JWT
- Rate limiting y throttling
- Documentación Swagger/OpenAPI

## 🛠️ Tecnologías Utilizadas

### Backend (Optimizado)
- **Python 3.11+**: Lenguaje principal
- **Flask 3.0+**: Framework web moderno
- **SQLAlchemy 2.0+**: ORM avanzado
- **Celery**: Tareas asíncronas
- **Redis**: Cache y message broker
- **JWT**: Autenticación stateless
- **79 dependencias optimizadas** (52.4% menos que antes)

### Frontend
- **Jinja2**: Motor de templates
- **Bootstrap 5**: Framework CSS
- **Chart.js**: Gráficos interactivos
- **Socket.IO**: Comunicación en tiempo real
- **HTMX**: Interactividad sin JavaScript complejo

### Base de Datos
- **PostgreSQL**: Base de datos principal
- **Redis**: Cache y sesiones
- **SQLite**: Desarrollo y testing

### DevOps y Infraestructura
- **Docker & Docker Compose**: Containerización
- **Nginx**: Servidor web/proxy reverso
- **Gunicorn**: WSGI server
- **GitHub Actions**: CI/CD
- **Prometheus & Grafana**: Monitoreo

### Testing y Calidad
- **pytest**: Framework de testing
- **Coverage.py**: Cobertura de código
- **Black**: Formateo de código
- **Flake8**: Linting
- **Pre-commit**: Git hooks

## 📋 Requisitos Previos

### Software Requerido
- **Python 3.11+**
- **PostgreSQL 13+**
- **Redis 6+**
- **Node.js 16+** (para assets frontend)
- **Git**

### ✨ Beneficios de la Optimización
- **Instalación 52.4% más rápida** gracias a menos dependencias
- **Menor consumo de espacio** en disco y memoria
- **Superficie de ataque reducida** en seguridad
- **Menos conflictos** entre dependencias
- **Solo paquetes realmente utilizados** en el código

### Servicios Externos (Opcionales)
- Cuenta de Google Cloud (para integración Calendar/Meet)
- Cuenta de SendGrid/Mailgun (para emails)
- Cuenta de Stripe (para pagos)

## 🚀 Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-org/ecosistema-emprendimiento.git
cd ecosistema-emprendimiento
```

### 2. Configurar Entorno Virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Linux/Mac:
source venv/bin/activate
# En Windows:
venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
# ✅ Dependencias optimizadas (79 paquetes en lugar de 166)
pip install -r requirements.txt

# Verificar la optimización
pip list | wc -l  # Debe mostrar ~85 paquetes instalados

# Dependencias de desarrollo y testing se incluyen automáticamente
# cuando son necesarias para el desarrollo
```

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar variables según tu entorno
nano .env
```

#### Variables de Entorno Principales

```env
# Configuración Flask
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta-muy-segura

# Base de Datos
DATABASE_URL=postgresql://usuario:password@localhost:5432/ecosistema_db
REDIS_URL=redis://localhost:6379/0

# Configuración Email
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=tu-email@gmail.com
MAIL_PASSWORD=tu-app-password

# Integración Google
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret

# APIs Externas
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
```

### 5. Configurar Base de Datos

```bash
# Crear base de datos PostgreSQL
createdb ecosistema_db

# Ejecutar migraciones
flask db upgrade

# Cargar datos de ejemplo (opcional)
python scripts/seed_data.py
```

### 6. Compilar Assets Frontend

```bash
# Instalar dependencias Node.js
npm install

# Compilar assets para desarrollo
npm run dev

# O para producción
npm run build
```

### 7. Iniciar Servicios

```bash
# Terminal 1: Aplicación principal
flask run

# Terminal 2: Worker Celery (tareas asíncronas)
celery -A app.tasks.celery_app worker --loglevel=info

# Terminal 3: Scheduler Celery (tareas periódicas)
celery -A app.tasks.celery_app beat --loglevel=info

# Terminal 4: Monitor Celery (opcional)
celery -A app.tasks.celery_app flower
```

### 8. Verificar Instalación

Visita `http://localhost:5000` en tu navegador. Deberías ver la página de inicio del ecosistema.

## 💻 Uso Básico

### Primer Usuario Administrador

```bash
# Crear usuario administrador
flask create-admin --email admin@example.com --password admin123
```

### Acceso a la Plataforma

1. **Administrador**: `http://localhost:5000/admin`
2. **Emprendedor**: `http://localhost:5000/entrepreneur`
3. **Aliado/Mentor**: `http://localhost:5000/ally`
4. **Cliente**: `http://localhost:5000/client`

### Comandos CLI Útiles

```bash
# Crear usuario
flask create-user --email usuario@example.com --role entrepreneur

# Backup de base de datos
flask backup-db

# Limpiar cache
flask clear-cache

# Generar reporte
flask generate-report --type monthly

# Ejecutar health check
flask health-check
```

## 📁 Estructura del Proyecto

```
ecosistema-emprendimiento/
├── 📁 app/                     # Aplicación principal
│   ├── 📁 core/               # Lógica de negocio central
│   ├── 📁 models/             # Modelos de datos (SQLAlchemy)
│   ├── 📁 api/                # API REST endpoints
│   ├── 📁 views/              # Vistas web (Flask Blueprint)
│   ├── 📁 services/           # Servicios de negocio
│   ├── 📁 forms/              # Formularios (WTForms)
│   ├── 📁 templates/          # Templates Jinja2
│   ├── 📁 static/             # Assets estáticos
│   ├── 📁 utils/              # Utilidades compartidas
│   ├── 📁 sockets/            # WebSockets (Socket.IO)
│   └── 📁 tasks/              # Tareas asíncronas (Celery)
├── 📁 tests/                  # Suite de tests completa
├── 📁 docs/                   # Documentación
├── 📁 scripts/                # Scripts de automatización
├── 📁 docker/                 # Configuración Docker
└── 📁 monitoring/             # Configuración monitoreo
```

### Arquitectura de la Aplicación

```mermaid
graph TB
    A[Cliente Web] --> B[Nginx]
    B --> C[Flask App]
    C --> D[PostgreSQL]
    C --> E[Redis]
    C --> F[Celery Workers]
    F --> G[External APIs]
    H[Admin Panel] --> C
    I[Socket.IO] --> C
```

## 🔌 API Documentation

### Autenticación

Todas las llamadas a la API requieren autenticación JWT:

```bash
# Obtener token
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@example.com", "password": "password123"}'

# Usar token en requests
curl -X GET http://localhost:5000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Endpoints Principales

#### Usuarios
- `GET /api/v1/users` - Listar usuarios
- `POST /api/v1/users` - Crear usuario
- `GET /api/v1/users/{id}` - Obtener usuario
- `PUT /api/v1/users/{id}` - Actualizar usuario
- `DELETE /api/v1/users/{id}` - Eliminar usuario

#### Proyectos
- `GET /api/v1/projects` - Listar proyectos
- `POST /api/v1/projects` - Crear proyecto
- `GET /api/v1/projects/{id}` - Obtener proyecto
- `PUT /api/v1/projects/{id}` - Actualizar proyecto

#### Mentoría
- `GET /api/v1/mentorship/sessions` - Listar sesiones
- `POST /api/v1/mentorship/sessions` - Crear sesión
- `PUT /api/v1/mentorship/sessions/{id}` - Actualizar sesión

### Documentación Interactiva

La documentación completa de la API está disponible en:
- **Swagger UI**: `http://localhost:5000/api/docs`
- **ReDoc**: `http://localhost:5000/api/redoc`

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests con cobertura
pytest --cov=app

# Tests específicos
pytest tests/unit/test_models.py
pytest tests/integration/test_api.py

# Tests de rendimiento
pytest tests/performance/test_load.py
```

### Estructura de Testing

- **Unit Tests**: Tests unitarios para modelos, servicios y utilidades
- **Integration Tests**: Tests de integración para API y vistas
- **Functional Tests**: Tests funcionales end-to-end
- **Performance Tests**: Tests de carga y rendimiento

### Coverage Reports

```bash
# Generar reporte HTML
pytest --cov=app --cov-report=html

# Ver reporte
open htmlcov/index.html
```

## 🚢 Deployment

### Usando Docker (Recomendado)

```bash
# Construcción
docker-compose -f docker-compose.prod.yml build

# Despliegue
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Deployment Manual

```bash
# Configurar variables para producción
export FLASK_ENV=production

# Instalar dependencias
pip install -r requirements.txt

# Compilar assets
npm run build

# Ejecutar migraciones
flask db upgrade

# Iniciar con Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### Usando el Script de Deployment

```bash
# Deployment automático
python scripts/deploy.py --environment production
```

### Configuración Nginx

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /path/to/app/static;
        expires 1y;
    }
}
```

### Variables de Entorno de Producción

```env
FLASK_ENV=production
SECRET_KEY=clave-super-secreta-para-produccion
DATABASE_URL=postgresql://user:pass@prod-db:5432/ecosistema_prod
REDIS_URL=redis://prod-redis:6379/0
```

## 🤝 Contribución

### Flujo de Contribución

1. **Fork** el repositorio
2. **Crear** rama feature: `git checkout -b feature/nueva-funcionalidad`
3. **Commit** cambios: `git commit -m 'Agregar nueva funcionalidad'`
4. **Push** a la rama: `git push origin feature/nueva-funcionalidad`
5. **Crear** Pull Request

### Estándares de Código

```bash
# Formateo automático
black app/ tests/

# Linting
flake8 app/ tests/

# Type checking
mypy app/

# Ordenar imports
isort app/ tests/
```

### Pre-commit Hooks

```bash
# Instalar pre-commit
pip install pre-commit

# Configurar hooks
pre-commit install

# Ejecutar en todos los archivos
pre-commit run --all-files
```

### Convenciones de Commit

Utilizamos [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Cambios en documentación
- `style:` Cambios de formato
- `refactor:` Refactorización de código
- `test:` Agregar o modificar tests
- `chore:` Tareas de mantenimiento

## 📝 Licencia

Este proyecto está licenciado bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 📞 Soporte y Contacto

### 🐛 Reportar Bugs

Si encuentras un bug, por favor:

1. Verifica que no esté ya reportado en [Issues](https://github.com/tu-org/ecosistema-emprendimiento/issues)
2. Crea un nuevo issue con:
   - Descripción clara del problema
   - Pasos para reproducir
   - Comportamiento esperado vs actual
   - Screenshots si aplica
   - Información del entorno

### 💡 Solicitar Funcionalidades

Para solicitar nuevas funcionalidades:

1. Abre un [Feature Request](https://github.com/tu-org/ecosistema-emprendimiento/issues/new?template=feature_request.md)
2. Describe claramente la funcionalidad
3. Explica el caso de uso
4. Proporciona mockups si es posible

### 📧 Contacto

- **Email**: desarrollo@ecosistema-emprendimiento.com
- **Slack**: [#ecosistema-dev](https://workspace.slack.com/channels/ecosistema-dev)
- **Documentación**: [Wiki del Proyecto](https://github.com/tu-org/ecosistema-emprendimiento/wiki)

### 🤝 Comunidad

- [Discussions](https://github.com/tu-org/ecosistema-emprendimiento/discussions) - Preguntas y discusiones
- [Discord](https://discord.gg/ecosistema-emprendimiento) - Chat de la comunidad
- [Newsletter](https://newsletter.ecosistema-emprendimiento.com) - Actualizaciones del proyecto

---

<div align="center">

**🌟 Si este proyecto te ha sido útil, considera darle una estrella en GitHub 🌟**

[![GitHub stars](https://img.shields.io/github/stars/tu-org/ecosistema-emprendimiento.svg?style=social&label=Star)](https://github.com/tu-org/ecosistema-emprendimiento)

*Construido con ❤️ por el equipo de desarrollo del Ecosistema de Emprendimiento*

</div>