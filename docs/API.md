# API Documentation - Ecosistema de Emprendimiento

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Autenticación](#autenticación)
3. [Estructura de Respuestas](#estructura-de-respuestas)
4. [Paginación](#paginación)
5. [Rate Limiting](#rate-limiting)
6. [Endpoints](#endpoints)
7. [Webhooks](#webhooks)
8. [Esquemas de Datos](#esquemas-de-datos)
9. [Códigos de Error](#códigos-de-error)
10. [SDKs y Ejemplos](#sdks-y-ejemplos)

---

## Introducción

### Información General

**Base URL:** `https://api.ecosistema.com/v1`
**Versión:** `1.0.0`
**Protocolo:** `HTTPS Only`
**Formato:** `JSON`
**Charset:** `UTF-8`

### Características de la API

- **RESTful**: Sigue principios REST estándares
- **Versionado**: Versionado en URL y headers
- **Autenticación**: JWT + OAuth 2.0
- **Rate Limiting**: 1000 requests/hora por defecto
- **Paginación**: Cursor-based y offset-based
- **Filtrado**: Query parameters avanzados
- **Webhooks**: Notificaciones en tiempo real
- **OpenAPI 3.0**: Especificación completa disponible

### Headers Requeridos

```http
Content-Type: application/json
Authorization: Bearer {token}
Accept: application/json
User-Agent: YourApp/1.0.0
X-API-Version: v1
```

---

## Autenticación

### Tipos de Autenticación

#### 1. JWT Bearer Token (Recomendado)

```http
POST /auth/login
Content-Type: application/json

{
  "email": "usuario@ejemplo.com",
  "password": "contraseña_segura",
  "remember_me": true
}
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "expires_at": "2024-12-31T23:59:59Z",
    "user": {
      "id": "usr_123456",
      "email": "usuario@ejemplo.com",
      "role": "entrepreneur",
      "permissions": ["read:profile", "write:projects"]
    }
  }
}
```

#### 2. OAuth 2.0 (Para aplicaciones terceras)

```http
GET /auth/oauth/authorize?
  client_id=your_client_id&
  response_type=code&
  redirect_uri=https://yourapp.com/callback&
  scope=read:profile+write:projects&
  state=random_string
```

#### 3. API Keys (Para servicios)

```http
GET /users/me
Authorization: ApiKey your_api_key_here
```

### Refresh Token

```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4..."
}
```

### Permissions y Scopes

| Scope | Descripción |
|-------|-------------|
| `read:profile` | Leer perfil del usuario |
| `write:profile` | Modificar perfil del usuario |
| `read:projects` | Leer proyectos |
| `write:projects` | Crear/editar proyectos |
| `admin:users` | Administrar usuarios |
| `admin:system` | Administración del sistema |

---

## Estructura de Respuestas

### Respuesta Exitosa

```json
{
  "success": true,
  "data": {
    "id": "usr_123456",
    "name": "Juan Pérez",
    "email": "juan@ejemplo.com"
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_789012",
    "version": "v1"
  }
}
```

### Respuesta de Error

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos proporcionados no son válidos",
    "details": [
      {
        "field": "email",
        "message": "El email no tiene un formato válido"
      }
    ]
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_789012",
    "version": "v1"
  }
}
```

### Respuesta con Paginación

```json
{
  "success": true,
  "data": [
    {"id": 1, "name": "Proyecto 1"},
    {"id": 2, "name": "Proyecto 2"}
  ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 100,
    "has_next": true,
    "has_prev": false,
    "next_cursor": "eyJpZCI6MjB9",
    "prev_cursor": null
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_789012"
  }
}
```

---

## Paginación

### Offset-based (Tradicional)

```http
GET /projects?page=2&per_page=20&sort=created_at&order=desc
```

### Cursor-based (Recomendado para grandes datasets)

```http
GET /projects?cursor=eyJpZCI6MjB9&limit=20
```

### Parámetros de Paginación

| Parámetro | Tipo | Descripción | Defecto |
|-----------|------|-------------|---------|
| `page` | integer | Número de página | 1 |
| `per_page` | integer | Items por página (máx: 100) | 20 |
| `cursor` | string | Cursor para paginación | - |
| `limit` | integer | Límite de items (cursor-based) | 20 |
| `sort` | string | Campo para ordenar | created_at |
| `order` | string | Dirección (asc/desc) | desc |

---

## Rate Limiting

### Límites por Endpoint

| Endpoint Type | Límite | Ventana |
|---------------|--------|---------|
| Auth | 10 req/min | 1 minuto |
| Read Operations | 1000 req/hora | 1 hora |
| Write Operations | 500 req/hora | 1 hora |
| Upload Files | 100 req/hora | 1 hora |
| Analytics | 200 req/hora | 1 hora |

### Headers de Rate Limiting

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
X-RateLimit-Window: 3600
```

### Respuesta de Rate Limit Excedido

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Has excedido el límite de peticiones",
    "retry_after": 3600
  }
}
```

---

## Endpoints

### 📁 Authentication

#### POST /auth/login
Autenticar usuario y obtener tokens de acceso.

**Request:**
```json
{
  "email": "usuario@ejemplo.com",
  "password": "contraseña_segura",
  "remember_me": false,
  "device_info": {
    "name": "iPhone 15",
    "type": "mobile",
    "os": "iOS 17.1"
  }
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "dGhpcyBpcyBhIHJl...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "usr_123456",
      "email": "usuario@ejemplo.com",
      "role": "entrepreneur",
      "first_login": false,
      "last_login_at": "2024-01-15T09:30:00Z"
    }
  }
}
```

#### POST /auth/register
Registrar nuevo usuario.

**Request:**
```json
{
  "email": "nuevo@ejemplo.com",
  "password": "contraseña_segura123",
  "first_name": "Juan",
  "last_name": "Pérez",
  "role": "entrepreneur",
  "phone": "+57300123456",
  "organization": "Mi Startup SAS",
  "terms_accepted": true,
  "privacy_accepted": true
}
```

#### POST /auth/forgot-password
Solicitar reset de contraseña.

#### POST /auth/reset-password
Resetear contraseña con token.

#### POST /auth/refresh
Renovar token de acceso.

#### POST /auth/logout
Cerrar sesión e invalidar tokens.

#### GET /auth/me
Obtener información del usuario autenticado.

---

### 👥 Users

#### GET /users
Listar usuarios (Admin/Allies).

**Query Parameters:**
```http
GET /users?role=entrepreneur&status=active&search=juan&page=1&per_page=20
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `role` | string | Filtrar por rol (entrepreneur, ally, admin, client) |
| `status` | string | Filtrar por estado (active, inactive, pending) |
| `search` | string | Buscar por nombre o email |
| `organization_id` | string | Filtrar por organización |
| `created_after` | datetime | Usuarios creados después de fecha |
| `created_before` | datetime | Usuarios creados antes de fecha |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "usr_123456",
      "email": "juan@ejemplo.com",
      "first_name": "Juan",
      "last_name": "Pérez",
      "role": "entrepreneur",
      "status": "active",
      "avatar_url": "https://cdn.ecosistema.com/avatars/usr_123456.jpg",
      "organization": {
        "id": "org_789",
        "name": "Mi Startup SAS"
      },
      "profile": {
        "phone": "+57300123456",
        "bio": "Emprendedor apasionado por la tecnología",
        "linkedin": "https://linkedin.com/in/juan-perez",
        "website": "https://mistartup.com"
      },
      "created_at": "2024-01-10T14:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "last_activity_at": "2024-01-15T10:25:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 89
  }
}
```

#### GET /users/{user_id}
Obtener detalles de usuario específico.

#### PUT /users/{user_id}
Actualizar usuario.

#### DELETE /users/{user_id}
Eliminar usuario (soft delete).

#### POST /users/{user_id}/activate
Activar usuario.

#### POST /users/{user_id}/deactivate
Desactivar usuario.

#### GET /users/{user_id}/activity
Obtener log de actividades del usuario.

---

### 🚀 Projects

#### GET /projects
Listar proyectos.

**Query Parameters:**
```http
GET /projects?entrepreneur_id=usr_123&status=active&industry=technology&stage=seed
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `entrepreneur_id` | string | Filtrar por emprendedor |
| `status` | string | Estado del proyecto |
| `industry` | string | Industria del proyecto |
| `stage` | string | Etapa del proyecto |
| `funding_needed` | boolean | Si necesita financiamiento |
| `min_funding` | number | Financiamiento mínimo |
| `max_funding` | number | Financiamiento máximo |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "prj_456789",
      "name": "EcoApp - Sostenibilidad Digital",
      "description": "Aplicación móvil para promover prácticas sostenibles",
      "status": "active",
      "stage": "seed",
      "industry": "technology",
      "entrepreneur": {
        "id": "usr_123456",
        "name": "Juan Pérez",
        "email": "juan@ejemplo.com"
      },
      "business_model": "freemium",
      "target_market": "Millennials y Gen Z conscientes del medio ambiente",
      "funding": {
        "needed": true,
        "amount_requested": 50000,
        "amount_raised": 15000,
        "currency": "USD",
        "use_of_funds": "Desarrollo de MVP y marketing inicial"
      },
      "team": [
        {
          "id": "usr_123456",
          "name": "Juan Pérez",
          "role": "CEO & Founder",
          "equity": 60
        },
        {
          "id": "usr_789012",
          "name": "María González",
          "role": "CTO",
          "equity": 25
        }
      ],
      "metrics": {
        "users": 1250,
        "revenue": 2500,
        "growth_rate": 15.5
      },
      "documents": [
        {
          "id": "doc_123",
          "name": "Business Plan 2024",
          "type": "business_plan",
          "url": "https://docs.ecosistema.com/doc_123.pdf"
        }
      ],
      "created_at": "2024-01-10T14:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### POST /projects
Crear nuevo proyecto.

**Request:**
```json
{
  "name": "EcoApp - Sostenibilidad Digital",
  "description": "Aplicación móvil para promover prácticas sostenibles en el día a día",
  "industry": "technology",
  "stage": "idea",
  "business_model": "freemium",
  "target_market": "Millennials y Gen Z conscientes del medio ambiente",
  "problem_statement": "Falta de herramientas accesibles para adoptar hábitos sostenibles",
  "solution": "App que gamifica acciones sostenibles con recompensas",
  "competitive_advantage": "Primera app en Colombia con sistema de recompensas locales",
  "funding": {
    "needed": true,
    "amount_requested": 50000,
    "currency": "USD",
    "use_of_funds": "Desarrollo de MVP, marketing inicial y contratación de equipo"
  },
  "team": [
    {
      "user_id": "usr_123456",
      "role": "CEO & Founder",
      "equity": 60,
      "commitment": "full-time"
    }
  ],
  "tags": ["sostenibilidad", "mobile", "gamificación", "medio ambiente"]
}
```

#### GET /projects/{project_id}
Obtener detalles del proyecto.

#### PUT /projects/{project_id}
Actualizar proyecto.

#### DELETE /projects/{project_id}
Eliminar proyecto.

#### POST /projects/{project_id}/team
Agregar miembro al equipo.

#### GET /projects/{project_id}/metrics
Obtener métricas del proyecto.

#### POST /projects/{project_id}/metrics
Actualizar métricas del proyecto.

---

### 📅 Meetings

#### GET /meetings
Listar reuniones.

**Query Parameters:**
```http
GET /meetings?date_from=2024-01-15&date_to=2024-01-31&type=mentorship&status=scheduled
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "mtg_789012",
      "title": "Sesión de Mentoría - Estrategia de Marketing",
      "description": "Revisar estrategias de marketing digital y posicionamiento",
      "type": "mentorship",
      "status": "scheduled",
      "start_time": "2024-01-20T15:00:00Z",
      "end_time": "2024-01-20T16:00:00Z",
      "timezone": "America/Bogota",
      "location": {
        "type": "virtual",
        "url": "https://meet.google.com/abc-defg-hij",
        "meeting_id": "abc-defg-hij"
      },
      "participants": [
        {
          "id": "usr_123456",
          "name": "Juan Pérez",
          "role": "entrepreneur",
          "status": "accepted"
        },
        {
          "id": "usr_789012",
          "name": "Ana Martínez",
          "role": "mentor",
          "status": "accepted"
        }
      ],
      "project": {
        "id": "prj_456789",
        "name": "EcoApp - Sostenibilidad Digital"
      },
      "agenda": [
        "Revisión de métricas actuales",
        "Análisis de competencia",
        "Estrategias de adquisición de usuarios",
        "Próximos pasos y acciones"
      ],
      "documents": [
        {
          "id": "doc_456",
          "name": "Marketing Strategy Presentation",
          "url": "https://docs.ecosistema.com/doc_456.pdf"
        }
      ],
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

#### POST /meetings
Crear nueva reunión.

#### GET /meetings/{meeting_id}
Obtener detalles de reunión.

#### PUT /meetings/{meeting_id}
Actualizar reunión.

#### DELETE /meetings/{meeting_id}
Cancelar reunión.

#### POST /meetings/{meeting_id}/join
Unirse a reunión.

#### POST /meetings/{meeting_id}/notes
Agregar notas de reunión.

---

### 💬 Messages

#### GET /messages
Listar mensajes/conversaciones.

#### POST /messages
Enviar nuevo mensaje.

#### GET /messages/{conversation_id}
Obtener mensajes de conversación.

#### PUT /messages/{message_id}
Editar mensaje.

#### DELETE /messages/{message_id}
Eliminar mensaje.

#### POST /messages/{message_id}/read
Marcar mensaje como leído.

---

### 📄 Documents

#### GET /documents
Listar documentos.

**Query Parameters:**
```http
GET /documents?project_id=prj_456&type=business_plan&shared_with_me=true
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "doc_123456",
      "name": "Business Plan 2024 - EcoApp",
      "description": "Plan de negocio detallado con proyecciones financieras",
      "type": "business_plan",
      "file_type": "pdf",
      "size": 2048576,
      "url": "https://docs.ecosistema.com/doc_123456.pdf",
      "thumbnail_url": "https://docs.ecosistema.com/thumbs/doc_123456.jpg",
      "project": {
        "id": "prj_456789",
        "name": "EcoApp - Sostenibilidad Digital"
      },
      "owner": {
        "id": "usr_123456",
        "name": "Juan Pérez"
      },
      "permissions": {
        "can_read": true,
        "can_write": false,
        "can_delete": false,
        "can_share": true
      },
      "shared_with": [
        {
          "user_id": "usr_789012",
          "permission": "read",
          "shared_at": "2024-01-15T10:30:00Z"
        }
      ],
      "version": "1.2",
      "status": "final",
      "tags": ["business-plan", "financials", "2024"],
      "created_at": "2024-01-10T14:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### POST /documents
Subir nuevo documento.

**Request (multipart/form-data):**
```http
POST /documents
Content-Type: multipart/form-data

file: [archivo binario]
name: "Business Plan 2024"
description: "Plan de negocio actualizado"
type: "business_plan"
project_id: "prj_456789"
tags: ["business-plan", "2024"]
```

#### GET /documents/{document_id}
Obtener detalles del documento.

#### PUT /documents/{document_id}
Actualizar metadatos del documento.

#### DELETE /documents/{document_id}
Eliminar documento.

#### POST /documents/{document_id}/share
Compartir documento.

#### GET /documents/{document_id}/download
Descargar archivo.

---

### 📊 Analytics

#### GET /analytics/overview
Dashboard general de métricas.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-31T23:59:59Z"
    },
    "users": {
      "total": 1250,
      "new": 89,
      "active": 1100,
      "by_role": {
        "entrepreneurs": 800,
        "allies": 150,
        "clients": 250,
        "admins": 50
      }
    },
    "projects": {
      "total": 450,
      "active": 380,
      "new": 25,
      "by_stage": {
        "idea": 120,
        "mvp": 80,
        "seed": 60,
        "growth": 40,
        "scale": 20
      },
      "funding_raised": {
        "total": 2500000,
        "currency": "USD",
        "average_per_project": 6578
      }
    },
    "meetings": {
      "total": 890,
      "completed": 756,
      "upcoming": 134,
      "average_duration": 52.5
    },
    "engagement": {
      "messages_sent": 5670,
      "documents_shared": 1230,
      "logins_per_user": 8.5,
      "session_duration": 25.2
    }
  }
}
```

#### GET /analytics/users
Métricas de usuarios.

#### GET /analytics/projects
Métricas de proyectos.

#### GET /analytics/meetings
Métricas de reuniones.

#### GET /analytics/export
Exportar datos analíticos.

---

### 🔗 Organizations

#### GET /organizations
Listar organizaciones.

#### POST /organizations
Crear organización.

#### GET /organizations/{org_id}
Obtener detalles de organización.

#### PUT /organizations/{org_id}
Actualizar organización.

#### GET /organizations/{org_id}/members
Listar miembros de organización.

#### POST /organizations/{org_id}/invite
Invitar miembro a organización.

---

### 🎯 Programs

#### GET /programs
Listar programas de emprendimiento.

#### POST /programs
Crear programa.

#### GET /programs/{program_id}
Obtener detalles del programa.

#### POST /programs/{program_id}/apply
Aplicar a programa.

#### GET /programs/{program_id}/applicants
Listar aplicantes.

---

### 🔔 Notifications

#### GET /notifications
Listar notificaciones.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "not_123456",
      "type": "meeting_reminder",
      "title": "Recordatorio de Reunión",
      "message": "Tu reunión con Ana Martínez comienza en 15 minutos",
      "status": "unread",
      "priority": "high",
      "data": {
        "meeting_id": "mtg_789012",
        "start_time": "2024-01-20T15:00:00Z"
      },
      "actions": [
        {
          "type": "join_meeting",
          "label": "Unirse",
          "url": "https://meet.google.com/abc-defg-hij"
        }
      ],
      "created_at": "2024-01-20T14:45:00Z"
    }
  ]
}
```

#### PUT /notifications/{notification_id}/read
Marcar notificación como leída.

#### POST /notifications/read-all
Marcar todas como leídas.

#### GET /notifications/settings
Obtener configuración de notificaciones.

#### PUT /notifications/settings
Actualizar configuración de notificaciones.

---

## Webhooks

### Configuración de Webhooks

#### POST /webhooks
Crear webhook.

**Request:**
```json
{
  "url": "https://yourapp.com/webhooks/ecosistema",
  "events": [
    "user.created",
    "project.updated",
    "meeting.scheduled",
    "document.shared"
  ],
  "secret": "your_webhook_secret",
  "active": true
}
```

#### GET /webhooks
Listar webhooks configurados.

#### PUT /webhooks/{webhook_id}
Actualizar webhook.

#### DELETE /webhooks/{webhook_id}
Eliminar webhook.

#### POST /webhooks/{webhook_id}/test
Probar webhook.

### Eventos Disponibles

| Evento | Descripción |
|--------|-------------|
| `user.created` | Usuario creado |
| `user.updated` | Usuario actualizado |
| `user.deleted` | Usuario eliminado |
| `project.created` | Proyecto creado |
| `project.updated` | Proyecto actualizado |
| `project.deleted` | Proyecto eliminado |
| `meeting.scheduled` | Reunión programada |
| `meeting.completed` | Reunión completada |
| `meeting.cancelled` | Reunión cancelada |
| `document.uploaded` | Documento subido |
| `document.shared` | Documento compartido |
| `message.sent` | Mensaje enviado |
| `notification.created` | Notificación creada |

### Ejemplo de Payload

```json
{
  "event": "project.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "project": {
      "id": "prj_456789",
      "name": "EcoApp - Sostenibilidad Digital",
      "entrepreneur_id": "usr_123456"
    }
  },
  "webhook_id": "wh_789012"
}
```

---

## Esquemas de Datos

### User Schema

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^usr_[a-zA-Z0-9]+$",
      "description": "Identificador único del usuario"
    },
    "email": {
      "type": "string",
      "format": "email",
      "description": "Email del usuario (único)"
    },
    "first_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 50
    },
    "last_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 50
    },
    "role": {
      "type": "string",
      "enum": ["admin", "entrepreneur", "ally", "client"]
    },
    "status": {
      "type": "string",
      "enum": ["active", "inactive", "pending", "banned"]
    },
    "profile": {
      "type": "object",
      "properties": {
        "phone": {"type": "string"},
        "bio": {"type": "string", "maxLength": 500},
        "avatar_url": {"type": "string", "format": "uri"},
        "linkedin": {"type": "string", "format": "uri"},
        "website": {"type": "string", "format": "uri"},
        "skills": {
          "type": "array",
          "items": {"type": "string"}
        },
        "interests": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    }
  },
  "required": ["id", "email", "first_name", "last_name", "role"]
}
```

### Project Schema

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^prj_[a-zA-Z0-9]+$"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100
    },
    "description": {
      "type": "string",
      "maxLength": 1000
    },
    "status": {
      "type": "string",
      "enum": ["draft", "active", "paused", "completed", "cancelled"]
    },
    "stage": {
      "type": "string",
      "enum": ["idea", "mvp", "seed", "growth", "scale"]
    },
    "industry": {
      "type": "string",
      "enum": ["technology", "healthcare", "education", "finance", "retail", "agriculture", "energy", "other"]
    },
    "business_model": {
      "type": "string",
      "enum": ["b2b", "b2c", "b2b2c", "marketplace", "saas", "freemium", "subscription", "other"]
    },
    "entrepreneur_id": {
      "type": "string",
      "pattern": "^usr_[a-zA-Z0-9]+$"
    },
    "funding": {
      "type": "object",
      "properties": {
        "needed": {"type": "boolean"},
        "amount_requested": {"type": "number", "minimum": 0},
        "amount_raised": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["USD", "COP", "EUR"]},
        "use_of_funds": {"type": "string"}
      }
    },
    "team": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "user_id": {"type": "string"},
          "role": {"type": "string"},
          "equity": {"type": "number", "minimum": 0, "maximum": 100},
          "commitment": {"type": "string", "enum": ["full-time", "part-time", "advisor"]}
        }
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "users": {"type": "integer", "minimum": 0},
        "revenue": {"type": "number", "minimum": 0},
        "growth_rate": {"type": "number"},
        "burn_rate": {"type": "number"}
      }
    }
  },
  "required": ["id", "name", "entrepreneur_id", "status", "stage"]
}
```

### Meeting Schema

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^mtg_[a-zA-Z0-9]+$"
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "maxLength": 200
    },
    "description": {
      "type": "string",
      "maxLength": 1000
    },
    "type": {
      "type": "string",
      "enum": ["mentorship", "pitch", "review", "workshop", "networking", "other"]
    },
    "status": {
      "type": "string",
      "enum": ["scheduled", "in_progress", "completed", "cancelled", "no_show"]
    },
    "start_time": {
      "type": "string",
      "format": "date-time"
    },
    "end_time": {
      "type": "string",
      "format": "date-time"
    },
    "timezone": {
      "type": "string",
      "default": "America/Bogota"
    },
    "location": {
      "type": "object",
      "properties": {
        "type": {"type": "string", "enum": ["virtual", "physical"]},
        "url": {"type": "string", "format": "uri"},
        "address": {"type": "string"},
        "meeting_id": {"type": "string"}
      }
    },
    "participants": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "user_id": {"type": "string"},
          "status": {"type": "string", "enum": ["invited", "accepted", "declined", "tentative"]}
        }
      }
    }
  },
  "required": ["id", "title", "type", "start_time", "end_time"]
}
```

---

## Códigos de Error

### HTTP Status Codes

| Código | Nombre | Descripción |
|--------|--------|-------------|
| 200 | OK | Petición exitosa |
| 201 | Created | Recurso creado exitosamente |
| 204 | No Content | Petición exitosa sin contenido |
| 400 | Bad Request | Petición inválida |
| 401 | Unauthorized | No autenticado |
| 403 | Forbidden | Sin permisos |
| 404 | Not Found | Recurso no encontrado |
| 409 | Conflict | Conflicto con recurso existente |
| 422 | Unprocessable Entity | Error de validación |
| 429 | Too Many Requests | Rate limit excedido |
| 500 | Internal Server Error | Error interno del servidor |
| 503 | Service Unavailable | Servicio no disponible |

### Error Codes Específicos

| Código | Descripción | HTTP Status |
|--------|-------------|-------------|
| `VALIDATION_ERROR` | Error de validación de datos | 422 |
| `AUTHENTICATION_FAILED` | Credenciales inválidas | 401 |
| `TOKEN_EXPIRED` | Token JWT expirado | 401 |
| `INSUFFICIENT_PERMISSIONS` | Permisos insuficientes | 403 |
| `RESOURCE_NOT_FOUND` | Recurso no encontrado | 404 |
| `DUPLICATE_RESOURCE` | Recurso duplicado | 409 |
| `RATE_LIMIT_EXCEEDED` | Límite de peticiones excedido | 429 |
| `FILE_TOO_LARGE` | Archivo demasiado grande | 400 |
| `INVALID_FILE_TYPE` | Tipo de archivo no válido | 400 |
| `QUOTA_EXCEEDED` | Cuota excedida | 403 |
| `MAINTENANCE_MODE` | Modo mantenimiento activo | 503 |

### Ejemplo de Respuesta de Error Detallada

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Los datos proporcionados contienen errores",
    "details": [
      {
        "field": "email",
        "code": "INVALID_FORMAT",
        "message": "El formato del email no es válido"
      },
      {
        "field": "password",
        "code": "TOO_WEAK",
        "message": "La contraseña debe tener al menos 8 caracteres"
      }
    ],
    "documentation_url": "https://docs.ecosistema.com/errors/validation"
  },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "req_789012",
    "version": "v1"
  }
}
```

---

## SDKs y Ejemplos

### JavaScript/Node.js SDK

#### Instalación
```bash
npm install @ecosistema/sdk
```

#### Uso Básico
```javascript
const EcosistemaSDK = require('@ecosistema/sdk');

const client = new EcosistemaSDK({
  apiKey: 'your_api_key',
  baseURL: 'https://api.ecosistema.com/v1',
  timeout: 30000
});

// Autenticación
const auth = await client.auth.login({
  email: 'usuario@ejemplo.com',
  password: 'contraseña'
});

// Listar proyectos
const projects = await client.projects.list({
  status: 'active',
  page: 1,
  per_page: 20
});

// Crear proyecto
const newProject = await client.projects.create({
  name: 'Mi Nuevo Proyecto',
  description: 'Descripción del proyecto',
  industry: 'technology',
  stage: 'idea'
});

// Subir documento
const document = await client.documents.upload({
  file: fileBuffer,
  name: 'Business Plan',
  type: 'business_plan',
  project_id: 'prj_123456'
});
```

### Python SDK

#### Instalación
```bash
pip install ecosistema-sdk
```

#### Uso Básico
```python
from ecosistema_sdk import EcosistemaClient

client = EcosistemaClient(
    api_key='your_api_key',
    base_url='https://api.ecosistema.com/v1'
)

# Autenticación
auth_response = client.auth.login(
    email='usuario@ejemplo.com',
    password='contraseña'
)

# Listar usuarios
users = client.users.list(
    role='entrepreneur',
    status='active',
    page=1,
    per_page=20
)

# Crear reunión
meeting = client.meetings.create(
    title='Sesión de Mentoría',
    type='mentorship',
    start_time='2024-01-20T15:00:00Z',
    end_time='2024-01-20T16:00:00Z',
    participants=['usr_123456', 'usr_789012']
)
```

### cURL Examples

#### Autenticación
```bash
curl -X POST https://api.ecosistema.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@ejemplo.com",
    "password": "contraseña_segura"
  }'
```

#### Listar Proyectos
```bash
curl -X GET "https://api.ecosistema.com/v1/projects?status=active&page=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/json"
```

#### Crear Usuario
```bash
curl -X POST https://api.ecosistema.com/v1/users \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "nuevo@ejemplo.com",
    "first_name": "Juan",
    "last_name": "Pérez",
    "role": "entrepreneur"
  }'
```

#### Subir Documento
```bash
curl -X POST https://api.ecosistema.com/v1/documents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@business_plan.pdf" \
  -F "name=Business Plan 2024" \
  -F "type=business_plan" \
  -F "project_id=prj_456789"
```

### Webhook Verification

#### Node.js
```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
  const computedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload, 'utf8')
    .digest('hex');
    
  return signature === `sha256=${computedSignature}`;
}

// Express.js middleware
app.post('/webhooks/ecosistema', (req, res) => {
  const signature = req.headers['x-ecosistema-signature'];
  const payload = JSON.stringify(req.body);
  
  if (!verifyWebhookSignature(payload, signature, process.env.WEBHOOK_SECRET)) {
    return res.status(401).send('Unauthorized');
  }
  
  // Procesar webhook
  const { event, data } = req.body;
  console.log(`Received ${event} event:`, data);
  
  res.status(200).send('OK');
});
```

#### Python
```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    computed_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature == f"sha256={computed_signature}"

# Flask example
from flask import Flask, request, jsonify

@app.route('/webhooks/ecosistema', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Ecosistema-Signature')
    payload = request.get_data(as_text=True)
    
    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Procesar webhook
    data = request.get_json()
    event = data.get('event')
    webhook_data = data.get('data')
    
    print(f"Received {event} event:", webhook_data)
    
    return jsonify({'status': 'success'})
```

---

## Migración y Versionado

### Versionado de API

La API utiliza versionado semántico y soporta múltiples versiones simultáneamente:

- **v1**: Versión actual estable
- **v2**: Próxima versión (beta)

### Headers de Versión

```http
X-API-Version: v1
Accept: application/vnd.ecosistema.v1+json
```

### Cambios Breaking vs Non-Breaking

**Non-Breaking Changes (no requieren nueva versión):**
- Agregar nuevos campos opcionales
- Agregar nuevos endpoints
- Agregar nuevos valores a enums existentes
- Mejorar mensajes de error

**Breaking Changes (requieren nueva versión):**
- Remover o renombrar campos
- Cambiar tipos de datos
- Cambiar comportamiento de endpoints existentes
- Remover endpoints

### Plan de Deprecación

```json
{
  "deprecated": true,
  "deprecation_date": "2024-06-01T00:00:00Z",
  "sunset_date": "2024-12-01T00:00:00Z",
  "migration_guide": "https://docs.ecosistema.com/migration/v1-to-v2",
  "replacement": {
    "version": "v2",
    "endpoint": "/v2/users"
  }
}
```

---

## Herramientas y Recursos

### Postman Collection
```bash
# Importar colección de Postman
curl -O https://api.ecosistema.com/postman/collection.json
```

### OpenAPI Specification
```bash
# Descargar especificación OpenAPI 3.0
curl -O https://api.ecosistema.com/openapi.json
```

### Swagger UI
**URL:** https://api.ecosistema.com/docs

### Playground Interactivo
**URL:** https://api.ecosistema.com/playground

### Status Page
**URL:** https://status.ecosistema.com

---

## Soporte y Contacto

### Documentación Adicional
- **Guías de Inicio:** https://docs.ecosistema.com/getting-started
- **Tutoriales:** https://docs.ecosistema.com/tutorials
- **FAQ:** https://docs.ecosistema.com/faq
- **Changelog:** https://docs.ecosistema.com/changelog

### Soporte Técnico
- **Email:** api-support@ecosistema.com
- **Slack:** #api-support
- **Horarios:** Lunes a Viernes, 9:00 - 18:00 COT

### Contribuciones
- **GitHub:** https://github.com/ecosistema/api-docs
- **Issues:** https://github.com/ecosistema/api-docs/issues
- **Mejoras:** Pull requests bienvenidos

---

*Documentación actualizada: 2024-01-15*
*Versión de API: v1.0.0*