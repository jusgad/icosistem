# 📡 Documentación de la API

> **Referencia completa de la API REST del Ecosistema de Emprendimiento**

## 📋 Tabla de Contenidos

- [🚀 Introducción](#-introducción)
- [🔐 Autenticación](#-autenticación)
- [📊 Esquemas de Respuesta](#-esquemas-de-respuesta)
- [👥 Usuarios](#-usuarios)
- [🚀 Proyectos](#-proyectos)
- [🏢 Organizaciones](#-organizaciones)
- [🎯 Mentorías](#-mentorías)
- [📈 Analytics](#-analytics)
- [⚙️ Sistema](#️-sistema)
- [📝 Códigos de Error](#-códigos-de-error)

## 🚀 Introducción

La API del Ecosistema de Emprendimiento es una API REST completamente documentada que permite interactuar con todos los componentes del sistema de manera programática.

### 📍 Base URL

```
Production:  https://api.icosistem.com/api/v2
Staging:     https://staging-api.icosistem.com/api/v2
Development: http://localhost:5000/api/v2
```

### 📚 Documentación Interactiva

- **Swagger UI**: `/api/v2/docs/` - Interfaz interactiva
- **ReDoc**: `/api/v2/redoc/` - Documentación limpia
- **OpenAPI Spec**: `/api/v2/openapi.json` - Especificación JSON

### 🔧 Características

- **RESTful**: Sigue principios REST
- **JSON**: Formato de datos JSON exclusivamente
- **CORS**: Soporte completo para CORS
- **Rate Limiting**: Limitación de velocidad inteligente
- **Paginación**: Paginación consistente en todos los endpoints
- **Filtrado**: Filtros avanzados y búsqueda
- **Versionado**: Versionado semántico de la API

## 🔐 Autenticación

### 🎫 JWT Token Authentication

La API usa autenticación JWT (JSON Web Tokens) con tokens de acceso y actualización.

#### 🔑 Registro de Usuario

```http
POST /api/v2/auth/register
Content-Type: application/json

{
  "name": "Juan Pérez",
  "email": "juan@example.com",
  "password": "SecurePass123!",
  "role": "emprendedor"
}
```

**Respuesta exitosa (201)**:
```json
{
  "success": true,
  "message": "Usuario registrado exitosamente",
  "data": {
    "user": {
      "id": 123,
      "name": "Juan Pérez",
      "email": "juan@example.com",
      "role": "emprendedor",
      "is_verified": false,
      "created_at": "2024-01-15T10:30:00Z"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  }
}
```

#### 🔑 Inicio de Sesión

```http
POST /api/v2/auth/login
Content-Type: application/json

{
  "email": "juan@example.com",
  "password": "SecurePass123!"
}
```

**Respuesta exitosa (200)**:
```json
{
  "success": true,
  "message": "Login exitoso",
  "data": {
    "user": {
      "id": 123,
      "name": "Juan Pérez",
      "email": "juan@example.com",
      "role": "emprendedor"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  }
}
```

#### 🔄 Renovar Token

```http
POST /api/v2/auth/refresh
Content-Type: application/json
Authorization: Bearer <refresh_token>

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 🚪 Cerrar Sesión

```http
POST /api/v2/auth/logout
Authorization: Bearer <access_token>
```

### 🛡️ Usar el Token

Incluye el token de acceso en el header `Authorization` de todas las peticiones autenticadas:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 🔐 Roles y Permisos

- **admin**: Acceso completo al sistema
- **mentor**: Gestión de mentorías y acceso a emprendedores
- **emprendedor**: Gestión de proyectos propios
- **cliente**: Visualización y conexión con proyectos

## 📊 Esquemas de Respuesta

### ✅ Respuesta Exitosa Estándar

```json
{
  "success": true,
  "message": "Operación realizada exitosamente",
  "data": {
    // Datos específicos del endpoint
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_abc123",
    "version": "2.1.0"
  }
}
```

### ❌ Respuesta de Error Estándar

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos enviados no son válidos",
    "details": {
      "email": ["El email ya está en uso"],
      "password": ["La contraseña debe tener al menos 8 caracteres"]
    }
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

### 📄 Paginación

```json
{
  "success": true,
  "data": {
    "items": [
      // Array de items
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 150,
      "pages": 8,
      "has_next": true,
      "has_prev": false,
      "next_page": 2,
      "prev_page": null
    }
  }
}
```

## 👥 Usuarios

### 👤 Obtener Perfil Actual

```http
GET /api/v2/users/me
Authorization: Bearer <token>
```

**Respuesta (200)**:
```json
{
  "success": true,
  "data": {
    "id": 123,
    "name": "Juan Pérez",
    "email": "juan@example.com",
    "role": "emprendedor",
    "bio": "Emprendedor apasionado por la tecnología",
    "avatar_url": "https://cdn.icosistem.com/avatars/123.jpg",
    "skills": ["Python", "JavaScript", "Marketing"],
    "location": "Madrid, España",
    "phone": "+34600123456",
    "linkedin": "https://linkedin.com/in/juanperez",
    "website": "https://juanperez.dev",
    "is_verified": true,
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### ✏️ Actualizar Perfil

```http
PUT /api/v2/users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Juan Carlos Pérez",
  "bio": "Emprendedor con 5 años de experiencia en startups tech",
  "skills": ["Python", "JavaScript", "Marketing Digital", "Lean Startup"],
  "location": "Barcelona, España"
}
```

### 🔍 Buscar Usuarios

```http
GET /api/v2/users?role=mentor&skills=python&location=madrid&page=1&per_page=20
Authorization: Bearer <token>
```

**Parámetros de consulta**:
- `role`: Filtrar por rol (`emprendedor`, `mentor`, `cliente`)
- `skills`: Filtrar por habilidades (separadas por coma)
- `location`: Filtrar por ubicación
- `search`: Búsqueda en nombre, bio y habilidades
- `verified`: Filtrar usuarios verificados (`true`/`false`)
- `page`: Página actual (default: 1)
- `per_page`: Items por página (default: 20, max: 100)

### 👤 Obtener Usuario por ID

```http
GET /api/v2/users/123
Authorization: Bearer <token>
```

### 🔄 Cambiar Contraseña

```http
POST /api/v2/users/me/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "current_password": "OldPassword123!",
  "new_password": "NewSecurePassword456!",
  "confirm_password": "NewSecurePassword456!"
}
```

### 📧 Verificar Email

```http
POST /api/v2/users/me/verify-email
Authorization: Bearer <token>
Content-Type: application/json

{
  "verification_code": "123456"
}
```

### 🖼️ Subir Avatar

```http
POST /api/v2/users/me/avatar
Authorization: Bearer <token>
Content-Type: multipart/form-data

avatar: <file>
```

## 🚀 Proyectos

### 📋 Listar Proyectos

```http
GET /api/v2/projects?status=active&stage=mvp&industry=tech&page=1&per_page=20
Authorization: Bearer <token>
```

**Parámetros de consulta**:
- `status`: Filtrar por estado (`active`, `paused`, `completed`, `cancelled`)
- `stage`: Filtrar por etapa (`idea`, `validation`, `mvp`, `growth`, `scale`)
- `industry`: Filtrar por industria
- `owner_id`: Filtrar por propietario
- `search`: Búsqueda en título y descripción
- `featured`: Proyectos destacados (`true`/`false`)
- `sort`: Ordenamiento (`created_at`, `updated_at`, `title`, `stage`)
- `order`: Dirección (`asc`, `desc`)

**Respuesta (200)**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 456,
        "title": "EcoDelivery",
        "description": "Plataforma de delivery ecológico usando vehículos eléctricos",
        "status": "active",
        "stage": "mvp",
        "industry": "logistics",
        "owner": {
          "id": 123,
          "name": "Juan Pérez",
          "avatar_url": "https://cdn.icosistem.com/avatars/123.jpg"
        },
        "team_size": 4,
        "funding_goal": 100000,
        "funding_raised": 25000,
        "tags": ["sostenibilidad", "delivery", "startup"],
        "logo_url": "https://cdn.icosistem.com/projects/456/logo.jpg",
        "website": "https://ecodelivery.com",
        "is_featured": false,
        "created_at": "2024-01-10T00:00:00Z",
        "updated_at": "2024-01-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 150,
      "pages": 8
    }
  }
}
```

### 📝 Crear Proyecto

```http
POST /api/v2/projects
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "EcoDelivery",
  "description": "Plataforma de delivery ecológico usando vehículos eléctricos para reducir la huella de carbono en las ciudades",
  "industry": "logistics",
  "stage": "idea",
  "business_model": "marketplace",
  "target_market": "Consumidores conscientes del medio ambiente en ciudades",
  "problem_statement": "Los servicios de delivery tradicionales contribuyen significativamente a la contaminación urbana",
  "solution": "Red de delivery con vehículos 100% eléctricos y packaging biodegradable",
  "funding_goal": 100000,
  "tags": ["sostenibilidad", "delivery", "startup", "ecommerce"],
  "website": "https://ecodelivery.com",
  "pitch_deck_url": "https://docs.google.com/presentation/d/abc123"
}
```

### 🔍 Obtener Proyecto por ID

```http
GET /api/v2/projects/456
Authorization: Bearer <token>
```

**Respuesta (200)**:
```json
{
  "success": true,
  "data": {
    "id": 456,
    "title": "EcoDelivery",
    "description": "Plataforma de delivery ecológico usando vehículos eléctricos",
    "status": "active",
    "stage": "mvp",
    "industry": "logistics",
    "business_model": "marketplace",
    "target_market": "Consumidores conscientes del medio ambiente en ciudades",
    "problem_statement": "Los servicios de delivery tradicionales contribuyen significativamente a la contaminación urbana",
    "solution": "Red de delivery con vehículos 100% eléctricos y packaging biodegradable",
    "competitive_advantage": "Primera plataforma 100% verde con certificación de carbono neutro",
    "owner": {
      "id": 123,
      "name": "Juan Pérez",
      "email": "juan@example.com",
      "avatar_url": "https://cdn.icosistem.com/avatars/123.jpg"
    },
    "team": [
      {
        "id": 124,
        "name": "María García",
        "role": "CTO",
        "avatar_url": "https://cdn.icosistem.com/avatars/124.jpg"
      }
    ],
    "metrics": {
      "revenue": 15000,
      "users": 250,
      "orders": 1200,
      "growth_rate": 15.5
    },
    "funding": {
      "goal": 100000,
      "raised": 25000,
      "investors_count": 3,
      "equity_offered": 15
    },
    "milestones": [
      {
        "id": 1,
        "title": "MVP Lanzado",
        "description": "Versión beta de la aplicación disponible",
        "status": "completed",
        "due_date": "2024-02-01T00:00:00Z",
        "completed_at": "2024-01-28T10:00:00Z"
      }
    ],
    "tags": ["sostenibilidad", "delivery", "startup"],
    "logo_url": "https://cdn.icosistem.com/projects/456/logo.jpg",
    "images": [
      "https://cdn.icosistem.com/projects/456/screenshot1.jpg",
      "https://cdn.icosistem.com/projects/456/screenshot2.jpg"
    ],
    "documents": [
      {
        "id": 1,
        "name": "Pitch Deck",
        "url": "https://docs.google.com/presentation/d/abc123",
        "type": "presentation"
      }
    ],
    "website": "https://ecodelivery.com",
    "social_links": {
      "linkedin": "https://linkedin.com/company/ecodelivery",
      "twitter": "https://twitter.com/ecodelivery"
    },
    "is_featured": false,
    "is_verified": true,
    "created_at": "2024-01-10T00:00:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### ✏️ Actualizar Proyecto

```http
PUT /api/v2/projects/456
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "EcoDelivery Pro",
  "stage": "growth",
  "metrics": {
    "revenue": 25000,
    "users": 400,
    "orders": 2000
  }
}
```

### 🗑️ Eliminar Proyecto

```http
DELETE /api/v2/projects/456
Authorization: Bearer <token>
```

### 👥 Gestionar Equipo del Proyecto

#### Agregar Miembro

```http
POST /api/v2/projects/456/team
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": 125,
  "role": "Marketing Manager",
  "equity": 5,
  "permissions": ["edit_project", "manage_tasks"]
}
```

#### Actualizar Miembro

```http
PUT /api/v2/projects/456/team/125
Authorization: Bearer <token>
Content-Type: application/json

{
  "role": "Head of Marketing",
  "equity": 7
}
```

#### Remover Miembro

```http
DELETE /api/v2/projects/456/team/125
Authorization: Bearer <token>
```

### 🎯 Hitos del Proyecto

#### Listar Hitos

```http
GET /api/v2/projects/456/milestones
Authorization: Bearer <token>
```

#### Crear Hito

```http
POST /api/v2/projects/456/milestones
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Lanzamiento Beta",
  "description": "Versión beta disponible para 100 usuarios de prueba",
  "due_date": "2024-03-01T00:00:00Z",
  "priority": "high"
}
```

#### Completar Hito

```http
PATCH /api/v2/projects/456/milestones/1/complete
Authorization: Bearer <token>
```

## 🏢 Organizaciones

### 🏢 Listar Organizaciones

```http
GET /api/v2/organizations?type=accelerator&location=spain&page=1&per_page=20
Authorization: Bearer <token>
```

**Parámetros**:
- `type`: Tipo de organización (`accelerator`, `incubator`, `investor`, `government`, `university`)
- `industry`: Filtrar por industria de enfoque
- `location`: Filtrar por ubicación
- `size`: Tamaño (`startup`, `small`, `medium`, `large`)

### 🏢 Crear Organización

```http
POST /api/v2/organizations
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Tech Accelerator Madrid",
  "description": "Aceleradora especializada en startups tecnológicas",
  "type": "accelerator",
  "industry_focus": ["technology", "fintech", "healthtech"],
  "size": "medium",
  "location": "Madrid, España",
  "website": "https://techaccelerator.es",
  "email": "contact@techaccelerator.es",
  "phone": "+34911234567",
  "services": [
    "acceleration_program",
    "mentorship",
    "funding",
    "networking"
  ],
  "program_duration": 12,
  "investment_range": {
    "min": 50000,
    "max": 500000
  }
}
```

### 🔍 Obtener Organización

```http
GET /api/v2/organizations/789
Authorization: Bearer <token>
```

### 📋 Programas de Organización

```http
GET /api/v2/organizations/789/programs
Authorization: Bearer <token>
```

## 🎯 Mentorías

### 🎯 Listar Mentorías

```http
GET /api/v2/mentorships?status=active&mentor_id=124&page=1
Authorization: Bearer <token>
```

**Parámetros**:
- `status`: Estado (`pending`, `active`, `completed`, `cancelled`)
- `mentor_id`: Filtrar por mentor
- `mentee_id`: Filtrar por mentee (emprendedor)
- `project_id`: Filtrar por proyecto

### 🎯 Solicitar Mentoría

```http
POST /api/v2/mentorships/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "mentor_id": 124,
  "project_id": 456,
  "message": "Hola María, me gustaría recibir mentoría en marketing digital para mi startup de delivery ecológico",
  "areas_of_focus": ["marketing", "user_acquisition", "growth_hacking"],
  "goals": [
    "Incrementar base de usuarios en 50%",
    "Optimizar campañas de marketing digital",
    "Desarrollar estrategia de retención"
  ],
  "duration_weeks": 12,
  "frequency": "weekly"
}
```

### ✅ Aceptar Mentoría (Solo Mentores)

```http
POST /api/v2/mentorships/890/accept
Authorization: Bearer <mentor_token>
Content-Type: application/json

{
  "message": "Me parece un proyecto muy interesante. Estaré encantada de ayudarte.",
  "schedule_preference": "tuesdays_10am",
  "communication_method": "video_call"
}
```

### 📅 Sesiones de Mentoría

#### Programar Sesión

```http
POST /api/v2/mentorships/890/sessions
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Revisión de estrategia de marketing",
  "description": "Análisis de métricas actuales y planificación de próximos pasos",
  "scheduled_at": "2024-01-20T10:00:00Z",
  "duration_minutes": 60,
  "meeting_link": "https://meet.google.com/abc-def-ghi",
  "agenda": [
    "Revisión de KPIs del último mes",
    "Análisis de campañas actuales",
    "Estrategia para febrero"
  ]
}
```

#### Completar Sesión

```http
POST /api/v2/mentorships/890/sessions/45/complete
Authorization: Bearer <token>
Content-Type: application/json

{
  "notes": "Gran sesión. Juan ha mostrado excelente progreso en la adquisición de usuarios...",
  "action_items": [
    "Implementar A/B test en landing page",
    "Configurar seguimiento de eventos en GA4",
    "Contactar con influencers locales"
  ],
  "rating": 5,
  "next_session_goals": "Revisar resultados de A/B tests y nuevas campañas"
}
```

### 📊 Feedback de Mentoría

```http
POST /api/v2/mentorships/890/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "rating": 5,
  "feedback": "María ha sido una mentora excepcional. Sus consejos han sido clave para el crecimiento de mi startup.",
  "areas_improved": ["marketing", "strategy", "leadership"],
  "would_recommend": true,
  "testimonial": "Gracias a María, hemos aumentado nuestros usuarios en un 150% en 3 meses."
}
```

## 📈 Analytics

### 📊 Métricas del Usuario

```http
GET /api/v2/analytics/user/dashboard
Authorization: Bearer <token>
```

**Respuesta (200)**:
```json
{
  "success": true,
  "data": {
    "overview": {
      "projects_count": 3,
      "mentorships_active": 2,
      "mentorships_completed": 5,
      "connections_made": 15,
      "profile_views": 234
    },
    "projects_performance": [
      {
        "project_id": 456,
        "title": "EcoDelivery",
        "metrics": {
          "views": 1250,
          "interested_users": 45,
          "applications": 12,
          "completion_rate": 75
        }
      }
    ],
    "mentorship_stats": {
      "total_hours": 48,
      "average_rating": 4.8,
      "goals_completed": 85,
      "improvement_areas": ["marketing", "finance", "strategy"]
    },
    "growth_metrics": {
      "monthly_activity": [
        {"month": "2024-01", "projects": 1, "mentorships": 2, "connections": 5},
        {"month": "2024-02", "projects": 2, "mentorships": 3, "connections": 8}
      ]
    }
  }
}
```

### 📈 Métricas del Proyecto

```http
GET /api/v2/analytics/projects/456/metrics
Authorization: Bearer <token>
```

### 🎯 Métricas de Mentoría

```http
GET /api/v2/analytics/mentorships/890/progress
Authorization: Bearer <token>
```

### 📊 Reportes Personalizados

```http
POST /api/v2/analytics/reports/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "type": "project_performance",
  "project_ids": [456, 789],
  "date_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "metrics": ["views", "applications", "funding_progress", "team_growth"],
  "format": "pdf"
}
```

## ⚙️ Sistema

### 🏥 Health Check

```http
GET /api/v2/health
```

**Respuesta (200)**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "2.1.0",
  "uptime": "5d 12h 30m",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "email": "healthy",
    "storage": "healthy"
  }
}
```

### 🔍 Health Check Detallado

```http
GET /api/v2/health/detailed
Authorization: Bearer <admin_token>
```

### 📊 Métricas del Sistema

```http
GET /api/v2/system/metrics
Authorization: Bearer <admin_token>
```

### ⚙️ Configuración

```http
GET /api/v2/system/config
Authorization: Bearer <admin_token>
```

## 📝 Códigos de Error

### 🔢 Códigos de Estado HTTP

- **200** - OK: Petición exitosa
- **201** - Created: Recurso creado exitosamente
- **204** - No Content: Petición exitosa sin contenido
- **400** - Bad Request: Datos de petición inválidos
- **401** - Unauthorized: No autenticado
- **403** - Forbidden: Sin permisos suficientes
- **404** - Not Found: Recurso no encontrado
- **409** - Conflict: Conflicto con el estado actual
- **422** - Unprocessable Entity: Error de validación
- **429** - Too Many Requests: Límite de velocidad excedido
- **500** - Internal Server Error: Error interno del servidor

### 🏷️ Códigos de Error Personalizados

#### Autenticación y Autorización

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email o contraseña incorrectos"
  }
}
```

- `INVALID_CREDENTIALS` - Credenciales incorrectas
- `TOKEN_EXPIRED` - Token de acceso expirado
- `TOKEN_INVALID` - Token inválido o malformado
- `REFRESH_TOKEN_EXPIRED` - Token de actualización expirado
- `INSUFFICIENT_PERMISSIONS` - Permisos insuficientes
- `ACCOUNT_INACTIVE` - Cuenta desactivada
- `EMAIL_NOT_VERIFIED` - Email no verificado

#### Validación de Datos

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos enviados no son válidos",
    "details": {
      "email": ["El email ya está en uso"],
      "password": ["La contraseña debe tener al menos 8 caracteres"]
    }
  }
}
```

- `VALIDATION_ERROR` - Error de validación general
- `REQUIRED_FIELD` - Campo obligatorio faltante
- `INVALID_FORMAT` - Formato de datos inválido
- `DUPLICATE_RESOURCE` - Recurso duplicado

#### Recursos

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "El proyecto solicitado no existe"
  }
}
```

- `RESOURCE_NOT_FOUND` - Recurso no encontrado
- `RESOURCE_ALREADY_EXISTS` - Recurso ya existe
- `RESOURCE_ACCESS_DENIED` - Acceso denegado al recurso
- `RESOURCE_LIMIT_EXCEEDED` - Límite de recursos excedido

#### Sistema

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Has excedido el límite de peticiones por minuto",
    "details": {
      "limit": 100,
      "reset_time": "2024-01-15T10:35:00Z"
    }
  }
}
```

- `RATE_LIMIT_EXCEEDED` - Límite de velocidad excedido
- `SERVICE_UNAVAILABLE` - Servicio temporalmente no disponible
- `MAINTENANCE_MODE` - Sistema en mantenimiento
- `INTERNAL_ERROR` - Error interno del servidor

### 💡 Manejo de Errores

#### En JavaScript/Frontend

```javascript
async function callAPI(endpoint, options = {}) {
  try {
    const response = await fetch(`/api/v2${endpoint}`, {
      headers: {
        'Authorization': `Bearer ${getToken()}`,
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });

    const data = await response.json();

    if (!response.ok) {
      throw new APIError(data.error.code, data.error.message, data.error.details);
    }

    return data;
  } catch (error) {
    if (error instanceof APIError) {
      // Manejar errores de API específicos
      switch (error.code) {
        case 'TOKEN_EXPIRED':
          await refreshToken();
          return callAPI(endpoint, options); // Reintentar
        case 'VALIDATION_ERROR':
          displayValidationErrors(error.details);
          break;
        default:
          showErrorMessage(error.message);
      }
    } else {
      // Error de red u otro
      showErrorMessage('Error de conexión');
    }
    throw error;
  }
}

class APIError extends Error {
  constructor(code, message, details = null) {
    super(message);
    this.code = code;
    this.details = details;
    this.name = 'APIError';
  }
}
```

#### En Python/Backend

```python
import requests
from typing import Optional, Dict, Any

class APIClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        headers = kwargs.get('headers', {})
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
            
        kwargs['headers'] = headers
        
        response = requests.request(
            method, 
            f"{self.base_url}{endpoint}", 
            **kwargs
        )
        
        if response.status_code == 401:
            raise UnauthorizedError("Token inválido o expirado")
        elif response.status_code == 422:
            error_data = response.json()
            raise ValidationError(error_data['error']['details'])
        elif not response.ok:
            error_data = response.json()
            raise APIError(
                error_data['error']['code'], 
                error_data['error']['message']
            )
            
        return response.json()
        
    def get_projects(self, **params) -> Dict[Any, Any]:
        return self._make_request('GET', '/projects', params=params)

class APIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class ValidationError(APIError):
    def __init__(self, details: Dict[str, List[str]]):
        self.details = details
        super().__init__('VALIDATION_ERROR', 'Datos inválidos')
```

## 🔧 Utilidades para Desarrolladores

### 📚 SDK/Wrappers Oficiales

#### JavaScript/TypeScript

```bash
npm install @icosistem/api-client
```

```javascript
import { IcosistemAPI } from '@icosistem/api-client';

const api = new IcosistemAPI({
  baseURL: 'https://api.icosistem.com/api/v2',
  token: 'your-jwt-token'
});

// Uso
const projects = await api.projects.list({ status: 'active' });
const user = await api.users.me();
```

#### Python

```bash
pip install icosistem-python
```

```python
from icosistem import IcosistemAPI

api = IcosistemAPI(
    base_url='https://api.icosistem.com/api/v2',
    token='your-jwt-token'
)

# Uso
projects = api.projects.list(status='active')
user = api.users.me()
```

### 🧪 Entorno de Testing

```bash
# Base URL para testing
https://staging-api.icosistem.com/api/v2

# Usuarios de prueba disponibles
test-admin@icosistem.com / TestPass123!
test-mentor@icosistem.com / TestPass123!
test-emprendedor@icosistem.com / TestPass123!
```

### 📝 Postman Collection

Importa nuestra colección de Postman para probar la API fácilmente:

```
https://api.icosistem.com/api/v2/postman-collection.json
```

---

## 🆘 Soporte y Recursos

- **Documentación Interactiva**: `/api/v2/docs/`
- **GitHub Issues**: [Reportar Problemas](https://github.com/icosistem/api/issues)
- **Discord**: [Comunidad de Desarrolladores](https://discord.gg/icosistem-dev)
- **Email**: dev-support@icosistem.com

---

**💡 Tip**: Siempre revisa la documentación interactiva en `/api/v2/docs/` para obtener los ejemplos más actualizados y probar los endpoints directamente desde el navegador.