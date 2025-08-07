# Referencia de la API

## Descripción General

La API v2 del Ecosistema de Emprendimiento proporciona una API REST integral para gestionar la plataforma del ecosistema de emprendimiento. Este documento proporciona información detallada sobre todos los endpoints disponibles, formatos de solicitud/respuesta y métodos de autenticación.

## Información Base

- **URL Base**: `https://api.ecosistema-emprendimiento.com/api/v2`
- **Tipo de Contenido**: `application/json`
- **Versión de la API**: `2.0`
- **Documentación**: Disponible en `/docs/` (Swagger UI)

## Autenticación

### Token Bearer JWT

La mayoría de los endpoints requieren autenticación usando tokens JWT:

```http
Authorization: Bearer <access_token>
```

### Clave API (Servicio a Servicio)

Para comunicación de servicio a servicio:

```http
X-API-Key: <api_key>
```

## Limitación de Velocidad

Las solicitudes de API tienen limitación de velocidad:

- **Por defecto**: 1000 solicitudes por hora por IP
- **Usuarios autenticados**: 2000 solicitudes por hora
- **Intentos de inicio de sesión**: 5 intentos por minuto
- **Registro**: 3 intentos por minuto

Los headers de limitación de velocidad se incluyen en las respuestas:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642694400
```

## Formatos de Respuesta Comunes

### Respuesta de Éxito

```json
{
    "success": true,
    "data": {
        // datos del objeto
    },
    "metadata": {
        "timestamp": "2024-01-01T12:00:00Z",
        "version": "2.0"
    }
}
```

### Respuesta de Error

```json
{
    "success": false,
    "error": {
        "type": "validation_error",
        "message": "Datos de entrada inválidos",
        "details": {
            "field": "email",
            "issue": "formato de email inválido"
        }
    },
    "metadata": {
        "timestamp": "2024-01-01T12:00:00Z",
        "request_id": "req_123456789"
    }
}
```

### Respuesta Paginada

```json
{
    "success": true,
    "data": [
        // array de objetos
    ],
    "pagination": {
        "current_page": 1,
        "per_page": 20,
        "total_pages": 5,
        "total_count": 100,
        "has_next": true,
        "has_prev": false
    }
}
```

## Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | Éxito |
| 201 | Creado |
| 204 | Sin Contenido |
| 400 | Solicitud Incorrecta |
| 401 | No Autorizado |
| 403 | Prohibido |
| 404 | No Encontrado |
| 409 | Conflicto |
| 422 | Entidad No Procesable |
| 429 | Demasiadas Solicitudes |
| 500 | Error Interno del Servidor |

## Endpoints de Autenticación

### Iniciar Sesión

```http
POST /auth/login
```

**Solicitud:**
```json
{
    "email": "usuario@ejemplo.com",
    "password": "contraseña123",
    "remember_me": false
}
```

**Respuesta:**
```json
{
    "success": true,
    "data": {
        "access_token": "jwt_access_token",
        "refresh_token": "jwt_refresh_token",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": "user_123",
            "email": "usuario@ejemplo.com",
            "user_type": "entrepreneur",
            "name": "Juan Pérez"
        }
    }
}
```

### Actualizar Token

```http
POST /auth/refresh
```

**Headers:**
```http
Authorization: Bearer <refresh_token>
```

**Respuesta:**
```json
{
    "success": true,
    "data": {
        "access_token": "nuevo_jwt_access_token",
        "expires_in": 3600
    }
}
```

### Cerrar Sesión

```http
POST /auth/logout
```

**Headers:**
```http
Authorization: Bearer <access_token>
```

### Registro

```http
POST /auth/register
```

**Solicitud:**
```json
{
    "email": "nuevo@ejemplo.com",
    "password": "contraseña123",
    "confirm_password": "contraseña123",
    "user_type": "entrepreneur",
    "first_name": "Juan",
    "last_name": "Pérez",
    "phone": "+57 300 123 4567",
    "terms_accepted": true
}
```

## Endpoints de Gestión de Usuarios

### Obtener Perfil Actual

```http
GET /users/me
```

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Respuesta:**
```json
{
    "success": true,
    "data": {
        "id": "user_123",
        "email": "usuario@ejemplo.com",
        "user_type": "entrepreneur",
        "first_name": "Juan",
        "last_name": "Pérez",
        "phone": "+57 300 123 4567",
        "profile": {
            "bio": "Emprendedor apasionado por la tecnología",
            "skills": ["Python", "JavaScript", "Gestión"],
            "experience_years": 5,
            "education": "Ingeniería de Sistemas",
            "location": "Bogotá, Colombia"
        },
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-12-01T10:30:00Z",
        "is_verified": true,
        "is_active": true
    }
}
```

### Actualizar Perfil

```http
PUT /users/me
```

**Solicitud:**
```json
{
    "first_name": "Juan Carlos",
    "last_name": "Pérez García",
    "phone": "+57 300 123 4567",
    "profile": {
        "bio": "Emprendedor con experiencia en fintech",
        "skills": ["Python", "React", "Blockchain"],
        "experience_years": 6,
        "location": "Medellín, Colombia"
    }
}
```

### Listar Usuarios (Solo Admins)

```http
GET /users
```

**Parámetros de Consulta:**
- `page` (int): Número de página (por defecto: 1)
- `per_page` (int): Elementos por página (por defecto: 20, máximo: 100)
- `user_type` (string): Filtrar por tipo de usuario
- `is_active` (boolean): Filtrar por estado activo
- `search` (string): Buscar por nombre o email

**Ejemplo:**
```http
GET /users?page=1&per_page=20&user_type=entrepreneur&search=juan
```

## Endpoints de Gestión de Proyectos

### Crear Proyecto

```http
POST /projects
```

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Solicitud:**
```json
{
    "name": "Mi Startup Fintech",
    "description": "Plataforma de pagos para pequeñas empresas",
    "category": "fintech",
    "stage": "idea",
    "industry": "tecnología",
    "business_model": "saas",
    "target_market": "pymes",
    "problem_statement": "Las pymes no tienen acceso a soluciones de pago digitales",
    "solution_description": "Plataforma integral de pagos con API simple",
    "revenue_model": "comisión por transacción",
    "funding_needed": 50000,
    "team_size": 3,
    "technologies": ["Python", "React", "PostgreSQL"],
    "tags": ["fintech", "pagos", "pymes"]
}
```

**Respuesta:**
```json
{
    "success": true,
    "data": {
        "id": "project_456",
        "name": "Mi Startup Fintech",
        "description": "Plataforma de pagos para pequeñas empresas",
        "owner": {
            "id": "user_123",
            "name": "Juan Pérez",
            "email": "juan@ejemplo.com"
        },
        "category": "fintech",
        "stage": "idea",
        "status": "active",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z"
    }
}
```

### Listar Proyectos

```http
GET /projects
```

**Parámetros de Consulta:**
- `page` (int): Número de página
- `per_page` (int): Elementos por página
- `category` (string): Filtrar por categoría
- `stage` (string): Filtrar por etapa
- `status` (string): Filtrar por estado
- `owner_id` (string): Filtrar por propietario
- `search` (string): Buscar en nombre y descripción

### Obtener Detalles del Proyecto

```http
GET /projects/{project_id}
```

### Actualizar Proyecto

```http
PUT /projects/{project_id}
```

### Eliminar Proyecto

```http
DELETE /projects/{project_id}
```

## Endpoints de Mentoría

### Crear Sesión de Mentoría

```http
POST /mentorship/sessions
```

**Solicitud:**
```json
{
    "mentor_id": "user_789",
    "entrepreneur_id": "user_123",
    "project_id": "project_456",
    "session_type": "one_on_one",
    "topic": "estrategia_negocio",
    "description": "Revisión del modelo de negocio y estrategia de go-to-market",
    "scheduled_date": "2024-01-15T14:00:00Z",
    "duration_minutes": 60,
    "location": "virtual",
    "meeting_link": "https://meet.google.com/abc-def-ghi"
}
```

### Listar Sesiones

```http
GET /mentorship/sessions
```

**Parámetros de Consulta:**
- `mentor_id` (string): Filtrar por mentor
- `entrepreneur_id` (string): Filtrar por emprendedor
- `project_id` (string): Filtrar por proyecto
- `status` (string): Filtrar por estado (scheduled, completed, cancelled)
- `from_date` (datetime): Desde fecha
- `to_date` (datetime): Hasta fecha

### Actualizar Sesión

```http
PUT /mentorship/sessions/{session_id}
```

### Completar Sesión con Feedback

```http
POST /mentorship/sessions/{session_id}/complete
```

**Solicitud:**
```json
{
    "mentor_feedback": {
        "rating": 5,
        "notes": "Sesión muy productiva, el emprendedor mostró gran compromiso",
        "recommendations": [
            "Enfocarse en validación de mercado",
            "Desarrollar MVP mínimo viable"
        ],
        "next_steps": [
            "Crear encuestas para validar problema",
            "Definir métricas de éxito"
        ]
    },
    "entrepreneur_feedback": {
        "rating": 5,
        "notes": "Excelentes insights, muy claros los siguientes pasos",
        "helpful_topics": ["validación de mercado", "métricas"],
        "would_recommend": true
    }
}
```

## Endpoints de Analytics

### Dashboard de Métricas Generales

```http
GET /analytics/dashboard
```

**Respuesta:**
```json
{
    "success": true,
    "data": {
        "summary": {
            "total_users": 1250,
            "active_projects": 345,
            "completed_sessions": 892,
            "success_rate": 0.78
        },
        "user_growth": [
            {"date": "2024-01-01", "new_users": 23, "total_users": 1227},
            {"date": "2024-01-02", "new_users": 18, "total_users": 1245}
        ],
        "project_stages": {
            "idea": 125,
            "validation": 89,
            "prototype": 67,
            "launch": 45,
            "growth": 19
        },
        "mentorship_metrics": {
            "avg_session_rating": 4.6,
            "total_hours": 1784,
            "active_mentors": 78
        }
    }
}
```

### Métricas de Usuario

```http
GET /analytics/users/{user_id}/metrics
```

### Métricas de Proyecto

```http
GET /analytics/projects/{project_id}/metrics
```

## Endpoints de Notificaciones

### Listar Notificaciones

```http
GET /notifications
```

**Parámetros de Consulta:**
- `is_read` (boolean): Filtrar por leídas/no leídas
- `notification_type` (string): Tipo de notificación
- `from_date` (datetime): Desde fecha

### Marcar como Leída

```http
PUT /notifications/{notification_id}/read
```

### Marcar Todas como Leídas

```http
PUT /notifications/mark-all-read
```

## Webhooks

### Configurar Webhook

```http
POST /webhooks
```

**Solicitud:**
```json
{
    "url": "https://tu-app.com/webhook",
    "events": [
        "user.created",
        "project.created",
        "session.completed"
    ],
    "secret": "tu_secreto_webhook"
}
```

### Eventos Disponibles

- `user.created` - Usuario registrado
- `user.updated` - Usuario actualizado
- `project.created` - Proyecto creado
- `project.updated` - Proyecto actualizado
- `session.scheduled` - Sesión programada
- `session.completed` - Sesión completada
- `session.cancelled` - Sesión cancelada

### Formato de Payload del Webhook

```json
{
    "event": "project.created",
    "data": {
        "id": "project_456",
        "name": "Mi Startup Fintech",
        "owner_id": "user_123"
    },
    "timestamp": "2024-01-01T10:00:00Z",
    "webhook_id": "webhook_789"
}
```

## Manejo de Errores

### Códigos de Error Comunes

| Código | Tipo | Descripción |
|--------|------|-------------|
| `auth_required` | 401 | Autenticación requerida |
| `invalid_token` | 401 | Token JWT inválido |
| `token_expired` | 401 | Token JWT expirado |
| `insufficient_permissions` | 403 | Permisos insuficientes |
| `resource_not_found` | 404 | Recurso no encontrado |
| `validation_error` | 422 | Error de validación |
| `rate_limit_exceeded` | 429 | Límite de velocidad excedido |
| `internal_error` | 500 | Error interno del servidor |

### Ejemplo de Error de Validación

```json
{
    "success": false,
    "error": {
        "type": "validation_error",
        "message": "Los datos proporcionados no son válidos",
        "details": [
            {
                "field": "email",
                "message": "El formato del email no es válido"
            },
            {
                "field": "password",
                "message": "La contraseña debe tener al menos 8 caracteres"
            }
        ]
    }
}
```

## SDKs y Librerías

### Python SDK

```python
from ecosistema_api import EcosistemaAPI

# Inicializar cliente
client = EcosistemaAPI(
    api_key="tu_api_key",
    base_url="https://api.ecosistema-emprendimiento.com/api/v2"
)

# Autenticarse
auth_result = client.auth.login(
    email="usuario@ejemplo.com",
    password="contraseña123"
)

# Crear proyecto
project = client.projects.create({
    "name": "Mi Startup",
    "description": "Descripción del proyecto",
    "category": "fintech"
})

# Listar proyectos
projects = client.projects.list(
    page=1,
    per_page=20,
    category="fintech"
)
```

### JavaScript SDK

```javascript
import { EcosistemaAPI } from 'ecosistema-api-js';

// Inicializar cliente
const client = new EcosistemaAPI({
    apiKey: 'tu_api_key',
    baseUrl: 'https://api.ecosistema-emprendimiento.com/api/v2'
});

// Autenticarse
const authResult = await client.auth.login({
    email: 'usuario@ejemplo.com',
    password: 'contraseña123'
});

// Crear proyecto
const project = await client.projects.create({
    name: 'Mi Startup',
    description: 'Descripción del proyecto',
    category: 'fintech'
});

// Listar proyectos
const projects = await client.projects.list({
    page: 1,
    perPage: 20,
    category: 'fintech'
});
```

## Ejemplos de cURL

### Autenticación

```bash
curl -X POST https://api.ecosistema-emprendimiento.com/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@ejemplo.com",
    "password": "contraseña123"
  }'
```

### Crear Proyecto

```bash
curl -X POST https://api.ecosistema-emprendimiento.com/api/v2/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tu_access_token" \
  -d '{
    "name": "Mi Startup Fintech",
    "description": "Plataforma de pagos innovadora",
    "category": "fintech",
    "stage": "idea"
  }'
```

### Listar Proyectos

```bash
curl -X GET "https://api.ecosistema-emprendimiento.com/api/v2/projects?page=1&per_page=20&category=fintech" \
  -H "Authorization: Bearer tu_access_token"
```

## Entornos

### Producción
- **URL Base**: `https://api.ecosistema-emprendimiento.com/api/v2`
- **Documentación**: `https://api.ecosistema-emprendimiento.com/docs/`

### Staging
- **URL Base**: `https://staging-api.ecosistema-emprendimiento.com/api/v2`
- **Documentación**: `https://staging-api.ecosistema-emprendimiento.com/docs/`

### Desarrollo
- **URL Base**: `http://localhost:5000/api/v2`
- **Documentación**: `http://localhost:5000/docs/`

## Changelog de la API

### v2.1.0 (Próximamente)
- Nuevos endpoints para gestión de organizaciones
- Mejoras en el sistema de notificaciones
- Soporte para webhooks batch

### v2.0.0 (Actual)
- API completamente rediseñada con arquitectura moderna
- Nuevos endpoints de mentoría
- Sistema de analytics mejorado
- Webhooks para integraciones en tiempo real

### v1.0.0 (Legacy)
- API básica inicial
- Endpoints fundamentales de usuarios y proyectos

## Soporte

Para soporte con la API:

- **Documentación**: Revisa esta documentación y la documentación interactiva en `/docs/`
- **Issues**: Reporta problemas en GitHub Issues
- **Email**: Contacta el equipo de API en api-support@ecosistema-emprendimiento.com
- **Status**: Verifica el estado de la API en status.ecosistema-emprendimiento.com