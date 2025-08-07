# 🚀 Ecosistema de Emprendimiento - Plataforma Moderna

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.0+](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![Licencia: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Estilo de código: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Pruebas](https://img.shields.io/badge/tests-passing-green.svg)](#testing)
[![Documentación API](https://img.shields.io/badge/API-documented-blue.svg)](docs/API_REFERENCE.md)

> **Una plataforma moderna y escalable para gestionar ecosistemas de emprendimiento con mentoría, seguimiento de proyectos y construcción de comunidad.**

## 🚀 Características

### ✨ Arquitectura Moderna
- **Arquitectura Hexagonal**: Separación clara de responsabilidades con puertos y adaptadores
- **Async-First**: Construido con async/await para alto rendimiento
- **Seguridad de Tipos**: Anotaciones de tipo completas con tipado moderno de Python
- **Validación Moderna**: Modelos Pydantic para validación de datos integral
- **Auto-Documentación**: Documentación OpenAPI/Swagger con Flask-RESTX

### 🔐 Autenticación Avanzada
- **Tokens JWT**: Autenticación segura con tokens de acceso/actualización
- **Autenticación de Dos Factores**: Soporte TOTP con códigos de respaldo
- **Integración OAuth**: Inicio de sesión con Google, Microsoft, GitHub
- **Gestión de Sesiones**: Seguimiento y gestión de dispositivos
- **Seguridad de Cuenta**: Limitación de velocidad, protección de bloqueo

### 👥 Gestión de Usuarios
- **Múltiples Tipos de Usuario**: Emprendedores, Aliados/Mentores, Clientes, Administradores
- **Perfiles Enriquecidos**: Perfiles de usuario integrales con habilidades y logros
- **Sistema de Verificación**: Verificación de correo electrónico y teléfono
- **Sistema de Permisos**: Control de acceso basado en roles
- **Seguimiento de Actividad**: Métricas de actividad y compromiso de usuarios

### 📊 Gestión de Proyectos
- **Ciclo de Vida del Proyecto**: Desde la idea hasta la escalabilidad con seguimiento de etapas
- **Gestión de Hitos**: Definir y seguir hitos del proyecto
- **Colaboración en Equipo**: Gestión de miembros del equipo y roles
- **Seguimiento de Progreso**: Indicadores visuales de progreso y métricas
- **Gestión de Documentos**: Carga de archivos y compartición de documentos

### 🎯 Sistema de Mentoría
- **Emparejamiento de Mentores**: Emparejamiento mentor-emprendedor con IA
- **Gestión de Sesiones**: Programar y seguir sesiones de mentoría
- **Establecimiento de Objetivos**: Definir y seguir objetivos de mentoría
- **Sistema de Retroalimentación**: Retroalimentación y calificaciones de sesiones
- **Medición de Impacto**: Seguir la efectividad de la mentoría

### 📈 Analíticas e Informes
- **Panel en Tiempo Real**: Métricas en vivo y KPIs
- **Analíticas de Usuario**: Métricas de compromiso y crecimiento
- **Analíticas de Proyecto**: Tasas de éxito y tendencias
- **Informes Personalizados**: Generar informes detallados
- **Exportación de Datos**: Exportar datos en varios formatos

### 🔧 Stack Tecnológico Moderno
- **Backend**: Python 3.11+, Flask 3.0+, SQLAlchemy 2.0+
- **Base de Datos**: PostgreSQL 15+ con soporte async
- **Caché**: Redis 7+ para sesiones y caché
- **API**: API RESTful con documentación OpenAPI
- **Validación**: Pydantic para validación de datos
- **Pruebas**: pytest con suite de pruebas integral
- **Observabilidad**: OpenTelemetry, Prometheus, Sentry

## 📋 Inicio Rápido

### Prerequisitos

- **Python 3.11+**
- **Node.js 18+** (para el frontend)
- **PostgreSQL 15+**
- **Redis 7+**
- **Docker & Docker Compose** (opcional)

### Instalación

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/your-org/icosistem.git
   cd icosistem
   ```

2. **Configurar el entorno Python**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -e .[dev]
   ```

3. **Configurar el entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tu configuración
   ```

4. **Iniciar servicios (Docker)**
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Inicializar la base de datos**
   ```bash
   flask db upgrade
   flask seed-data  # Opcional: cargar datos de ejemplo
   ```

6. **Iniciar la aplicación**
   ```bash
   python run.py
   ```

7. **Visitar la aplicación**
   - **API**: http://localhost:5000/api/v2/docs/
   - **Verificación de Salud**: http://localhost:5000/api/v2/health/

### Configuración con Docker (Recomendado)

```bash
# Entorno de desarrollo
docker-compose up --build

# Entorno de producción  
docker-compose -f docker-compose.prod.yml up --build
```

## 📚 Documentación

### Arquitectura y Diseño
- [**Guía de Arquitectura Moderna**](docs/MODERN_ARCHITECTURE.md) - Visión completa de la arquitectura
- [**Guía del Desarrollador**](docs/DEVELOPER_GUIDE.md) - Configuración de desarrollo y patrones
- [**Referencia API**](docs/API_REFERENCE.md) - Documentación completa de la API

### Despliegue y Operaciones
- [**Guía de Despliegue**](docs/DEPLOYMENT.md) - Instrucciones de despliegue en producción
- [**Guía de Instalación**](docs/INSTALATION.md) - Pasos de instalación detallados
- [**Registro de Cambios**](docs/CHANGELOG.md) - Historial de versiones y cambios

### Documentación Legacy
- [**Análisis Legacy**](docs/ANALISIS_COMPLETO.md) - Análisis del sistema previo
- [**README Original**](docs/README.md) - Documentación original

## 🏗️ Arquitectura

### Arquitectura Hexagonal

El sistema sigue los principios de arquitectura hexagonal:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Capa de Presentación                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   API REST      │  │   WebSockets    │  │  Herramientas   │  │
│  │  (Flask-RESTX)  │  │  (SocketIO)     │  │     CLI         │  │
│  │                 │  │                 │  │   (Click)       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                      Capa de Aplicación                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Casos de Uso                             │ │
│  │  • UserService  • ProjectService  • MentorshipService      │ │
│  │  • AuthService  • AnalyticsService • NotificationService   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                         Capa de Dominio                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Entidades                              │ │
│  │  • User  • Project  • Mentorship  • Organization           │ │
│  │                                                             │ │
│  │                  Reglas de Negocio                         │ │
│  │  • Validation  • Domain Events  • Specifications           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                   Capa de Infraestructura                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Base de Datos  │  │      Caché      │  │   APIs          │  │
│  │  (PostgreSQL)   │  │    (Redis)      │  │  Externas       │  │
│  │                 │  │                 │  │ (Email, OAuth)  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Componentes Clave

- **Base de Servicio Moderna**: Capa de servicio async-first con observabilidad
- **Validación Pydantic**: Validación de datos y serialización con seguridad de tipos
- **API Flask-RESTX**: API REST auto-documentada con OpenAPI
- **Base de Datos Async**: SQLAlchemy 2.0+ con soporte async
- **Circuit Breakers**: Comunicación resiliente entre servicios
- **Observabilidad**: Logging estructurado, métricas y trazado

## 🧪 Pruebas

El proyecto incluye una suite de pruebas integral con patrones modernos:

```bash
# Ejecutar todas las pruebas
pytest

# Ejecutar tipos específicos de pruebas
pytest -m unit        # Pruebas unitarias
pytest -m integration # Pruebas de integración  
pytest -m api         # Pruebas de API

# Ejecutar con cobertura
pytest --cov=app --cov-report=html

# Ejecutar pruebas de rendimiento
pytest -m slow

# Ejecutar pruebas en paralelo
pytest -n auto
```

### Categorías de Pruebas

- **Pruebas Unitarias**: Capa de servicios y lógica de negocio
- **Pruebas de Integración**: Integración de base de datos y servicios externos
- **Pruebas de API**: Pruebas completas de endpoints de API
- **Pruebas de Rendimiento**: Pruebas de carga y estrés

### Características Modernas de Pruebas

- **Patrón Factory**: Generación limpia de datos de prueba con Factory Boy
- **Soporte Async**: Soporte completo de pruebas asíncronas con pytest-asyncio
- **Fixtures Integrales**: Fixtures de base de datos, autenticación y API
- **Servicios Mock**: Mocking integral para dependencias externas

## 📊 Monitoreo y Observabilidad

### Observabilidad Integrada

- **Verificaciones de Salud**: Sondas de liveness y readiness listas para Kubernetes
- **Métricas**: Recopilación de métricas de Prometheus
- **Rastreo**: Rastreo distribuido con OpenTelemetry
- **Logging**: Logging estructurado con Loguru
- **Seguimiento de Errores**: Integración con Sentry

### Endpoints de Monitoreo

- `GET /api/v2/health/` - Verificación básica de salud
- `GET /api/v2/health/detailed` - Salud integral con dependencias
- `GET /api/v2/health/liveness` - Sonda de liveness de Kubernetes
- `GET /api/v2/health/readiness` - Sonda de readiness de Kubernetes
- `GET /metrics` - Endpoint de métricas de Prometheus

## 🚀 Despliegue

### Ambientes

- **Desarrollo**: Desarrollo local con recarga automática
- **Pruebas**: Ambiente de pruebas automatizadas
- **Staging**: Ambiente de pruebas de preproducción  
- **Producción**: Despliegue de producción de alta disponibilidad

### Opciones de Despliegue

1. **Docker Compose** (Recomendado para desarrollo)
2. **Kubernetes** (Recomendado para producción)
3. **Servidor Tradicional** (Máquinas virtuales)
4. **Plataformas en la Nube** (AWS, GCP, Azure)

Ver [Guía de Despliegue](docs/DEPLOYMENT.md) para instrucciones detalladas.

## 📈 Rendimiento

### Optimizaciones

- **Operaciones Async**: Operaciones de base de datos y HTTP no bloqueantes
- **Connection Pooling**: Gestión optimizada de conexiones de base de datos
- **Estrategia de Caché**: Caché multicapa con Redis
- **Optimización de Consultas**: Consultas de base de datos eficientes con indexación apropiada
- **Rate Limiting**: Protección contra abuso y sobrecarga

### Benchmarks

| Métrica | Valor |
|--------|--------|
| Tiempo de Respuesta API | < 100ms (p95) |
| Consultas de Base de Datos | < 50ms (p95) |
| Usuarios Concurrentes | 1000+ |
| Throughput | 500+ req/sec |
| Uso de Memoria | < 512MB |

## 🛠️ Desarrollo

### Flujo de Trabajo de Desarrollo Moderno

1. **Feature Branch**: Crear rama de funcionalidad desde `main`
2. **Desarrollo**: Usar patrones modernos de Python y async/await
3. **Pruebas**: Escribir pruebas integrales (unitarias, integración, API)
4. **Calidad de Código**: Ejecutar linting, formateo y verificación de tipos
5. **Documentación**: Actualizar documentación relevante
6. **Pull Request**: Crear PR con descripción detallada
7. **Revisión**: Revisión de código y verificaciones automatizadas
8. **Desplegar**: Despliegue automatizado después del merge

### Herramientas de Calidad de Código

```bash
# Formatear código
black .
isort .

# Linting de código  
ruff check .
ruff check . --fix

# Verificación de tipos
mypy .

# Escaneo de seguridad
bandit -r app/

# Hooks de pre-commit
pre-commit run --all-files
```

### Herramientas de Desarrollo

- **Black**: Formateo de código
- **isort**: Ordenamiento de imports  
- **Ruff**: Linting de Python ultra-rápido
- **mypy**: Verificación de tipos estática
- **pre-commit**: Hooks de Git para calidad
- **pytest**: Framework de pruebas moderno

## 🤝 Contribuir

¡Damos la bienvenida a las contribuciones! Por favor consulta nuestras pautas de contribución:

1. **Haz Fork** del repositorio
2. **Crea** una rama de funcionalidad (`git checkout -b feature/amazing-feature`)
3. **Haz Commit** de tus cambios (`git commit -m 'feat: add amazing feature'`)
4. **Push** a la rama (`git push origin feature/amazing-feature`)
5. **Abre** un Pull Request

### Pautas de Contribución

- Sigue [Conventional Commits](https://www.conventionalcommits.org/) para mensajes de commit
- Escribe pruebas para todas las nuevas funcionalidades
- Asegúrate de que todas las pruebas pasen y las verificaciones de calidad de código pasen
- Actualiza la documentación para cualquier cambio en la API
- Sigue el estilo de código y patrones existentes

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 🙏 Agradecimientos

- **Equipo de Flask** por el excelente framework web
- **Equipo de Pydantic** por la validación de datos moderna
- **Equipo de SQLAlchemy** por el ORM poderoso
- **Comunidad de Código Abierto** por el ecosistema increíble

## 📞 Soporte

### Obtener Ayuda

- **Documentación**: Consulta el directorio [docs](docs/)
- **Issues**: Crea un issue en GitHub
- **Discusiones**: Usa GitHub Discussions para preguntas
- **Email**: Contáctanos en support@ecosistema-emprendimiento.com

### Comunidad

- **Discord**: Únete a nuestra comunidad de desarrolladores
- **Twitter**: Síguenos [@EcosistemaAPI](https://twitter.com/EcosistemaAPI)
- **Blog**: Lee actualizaciones en nuestro [blog](https://blog.ecosistema-emprendimiento.com)

### Soporte Profesional

Para soporte empresarial, consultoría o desarrollo personalizado:

- **Email**: enterprise@ecosistema-emprendimiento.com
- **Website**: https://ecosistema-emprendimiento.com/enterprise

---

<div align="center">

**Hecho con ❤️ por el Equipo de Ecosistema**

[Website](https://ecosistema-emprendimiento.com) • 
[Documentation](docs/) • 
[API Reference](docs/API_REFERENCE.md) • 
[Contributing](CONTRIBUTING.md)

</div>