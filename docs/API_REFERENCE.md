# API Reference

## Overview

The Ecosistema de Emprendimiento API v2 provides a comprehensive REST API for managing the entrepreneurship ecosystem platform. This document provides detailed information about all available endpoints, request/response formats, and authentication methods.

## Base Information

- **Base URL**: `https://api.ecosistema-emprendimiento.com/api/v2`
- **Content Type**: `application/json`
- **API Version**: `2.0`
- **Documentation**: Available at `/docs/` (Swagger UI)

## Authentication

### JWT Bearer Token

Most endpoints require authentication using JWT tokens:

```http
Authorization: Bearer <access_token>
```

### API Key (Service-to-Service)

For service-to-service communication:

```http
X-API-Key: <api_key>
```

## Rate Limiting

API requests are rate limited:

- **Default**: 1000 requests per hour per IP
- **Authenticated users**: 2000 requests per hour
- **Login attempts**: 5 attempts per minute
- **Registration**: 3 attempts per minute

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642694400
```

## Common Response Formats

### Success Response

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

### Error Response

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
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "uuid"
}
```

### Paginated Response

```json
{
  "success": true,
  "items": [ ... ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_items": 100,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false,
    "next_page": 2,
    "prev_page": null
  }
}
```

## Health Endpoints

### GET /health

Basic health check endpoint.

**Response:**
```json
{
  "healthy": true,
  "service": "ecosistema-emprendimiento-api",
  "version": "2.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime_seconds": 3600,
  "environment": "production"
}
```

### GET /health/detailed

Comprehensive health check with dependencies.

**Response:**
```json
{
  "overall_status": "healthy",
  "services": [
    {
      "name": "database",
      "status": "healthy",
      "response_time_ms": 50,
      "details": {
        "pool_size": 20,
        "checked_out": 5
      }
    },
    {
      "name": "cache",
      "status": "healthy",
      "response_time_ms": 10,
      "details": {
        "connection": "ok"
      }
    }
  ],
  "system_info": {
    "cpu_percent": 25.5,
    "memory": {
      "total_mb": 8192,
      "available_mb": 4096,
      "percent_used": 50
    }
  }
}
```

## Authentication Endpoints

### POST /auth/login

Authenticate user and receive JWT tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "remember_me": false,
  "device_name": "iPhone 15",
  "two_factor_code": "123456"
}
```

**Response:**
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "user_type": "entrepreneur"
  },
  "permissions": ["create_project", "manage_profile"],
  "session_id": "session_uuid"
}
```

**Error Responses:**
- `400` Validation Error
- `401` Authentication Failed
- `423` Account Locked

### POST /auth/register

Register a new user account.

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!",
  "first_name": "Jane",
  "last_name": "Smith",
  "user_type": "entrepreneur",
  "phone": "+1234567890",
  "terms_accepted": true,
  "privacy_accepted": true,
  "marketing_consent": false,
  "organization_name": "My Startup"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Registration successful. Please check your email for verification.",
  "user": {
    "id": "uuid",
    "email": "newuser@example.com",
    "first_name": "Jane",
    "last_name": "Smith"
  },
  "email_verification_required": true,
  "verification_email_sent": true
}
```

### POST /auth/logout

Logout and invalidate current token.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### POST /auth/refresh

Refresh access token using refresh token.

**Headers:** `Authorization: Bearer <refresh_token>`

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST /auth/password-reset

Request password reset email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "If an account with that email exists, a password reset email has been sent",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### POST /auth/two-factor/setup

Setup two-factor authentication.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "secret": "JBSWY3DPEHPK3PXP",
  "backup_codes": [
    "123456",
    "789012",
    "345678",
    "901234",
    "567890"
  ]
}
```

### POST /auth/two-factor/verify

Verify and enable two-factor authentication.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "code": "123456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Two-factor authentication enabled successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## User Management Endpoints

### GET /users/me

Get current user profile.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "user_type": "entrepreneur",
    "status": "active",
    "email_verified": true,
    "phone_verified": false,
    "two_factor_enabled": true,
    "profile_completion": 85,
    "avatar_url": "https://example.com/avatar.jpg",
    "contact_info": {
      "phone": "+1234567890",
      "website": "https://johndoe.com",
      "linkedin": "https://linkedin.com/in/johndoe"
    },
    "notification_preferences": {
      "email_notifications": true,
      "sms_notifications": false,
      "push_notifications": true
    },
    "audit_info": {
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

### PUT /users/me

Update current user profile.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "bio": "Experienced entrepreneur passionate about technology.",
  "contact_info": {
    "website": "https://johndoe.com",
    "linkedin": "https://linkedin.com/in/johndoe"
  },
  "notification_preferences": {
    "email_notifications": true,
    "push_notifications": false
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    // Updated user object
  },
  "message": "Profile updated successfully"
}
```

### GET /users

List users (admin/ally only).

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `search`: Search term
- `user_type`: Filter by user type
- `status`: Filter by status
- `verified_only`: Show only verified users

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "user_type": "entrepreneur",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_items": 100,
    "total_pages": 5
  }
}
```

### GET /users/{user_id}

Get user by ID (admin/ally only).

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "data": {
    // Full user object
  }
}
```

### PUT /users/{user_id}/status

Update user status (admin only).

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "status": "suspended",
  "reason": "Policy violation",
  "notes": "Temporary suspension for review",
  "notify_user": true
}
```

## Entrepreneur Endpoints

### GET /entrepreneurs

List entrepreneurs.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `page`, `per_page`: Pagination
- `industry`: Filter by industry
- `business_stage`: Filter by business stage
- `location`: Filter by location

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": "uuid",
      "user": {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com"
      },
      "business_stage": "growth",
      "company_name": "Tech Innovations Inc",
      "industry": "Technology",
      "description": "Revolutionary AI solutions...",
      "founded_year": 2020,
      "employees_count": 15,
      "location": {
        "city": "San Francisco",
        "country": "USA"
      }
    }
  ],
  "pagination": { ... }
}
```

### GET /entrepreneurs/{entrepreneur_id}

Get entrepreneur details.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "user": { ... },
    "business_stage": "growth",
    "company_name": "Tech Innovations Inc",
    "industry": "Technology",
    "description": "Revolutionary AI solutions for small businesses",
    "founded_year": 2020,
    "employees_count": 15,
    "annual_revenue": 500000,
    "funding_raised": 1000000,
    "projects": [
      {
        "id": "uuid",
        "name": "AI Assistant",
        "status": "active"
      }
    ],
    "metrics": {
      "total_projects": 3,
      "active_projects": 2,
      "completed_projects": 1
    }
  }
}
```

### PUT /entrepreneurs/me

Update entrepreneur profile.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "business_stage": "scale",
  "company_name": "Tech Innovations Corp",
  "industry": "AI/ML",
  "description": "Leading AI solutions provider",
  "employees_count": 25,
  "annual_revenue": 750000,
  "website": "https://techinnovations.com",
  "skills": ["AI", "Machine Learning", "Product Management"],
  "achievements": [
    {
      "title": "Best Startup 2023",
      "organization": "TechCrunch",
      "date": "2023-12-01"
    }
  ]
}
```

## Project Endpoints

### GET /projects

List projects.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `page`, `per_page`: Pagination
- `owner_id`: Filter by owner
- `status`: Filter by status
- `industry`: Filter by industry

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": "uuid",
      "name": "AI-Powered CRM",
      "description": "Customer relationship management with AI insights",
      "owner": {
        "id": "uuid",
        "first_name": "John",
        "last_name": "Doe"
      },
      "status": "active",
      "industry": "SaaS",
      "budget": 50000,
      "timeline_months": 12,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": { ... }
}
```

### POST /projects

Create new project.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "AI-Powered Analytics",
  "description": "Advanced analytics platform using machine learning",
  "industry": "Analytics",
  "stage": "idea",
  "budget": 75000,
  "timeline_months": 18,
  "team_size": 5,
  "technologies": ["Python", "React", "PostgreSQL"],
  "goals": [
    "Build MVP within 6 months",
    "Acquire 100 beta users",
    "Raise Series A funding"
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "AI-Powered Analytics",
    // ... full project object
  },
  "message": "Project created successfully"
}
```

### GET /projects/{project_id}

Get project details.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "AI-Powered Analytics",
    "description": "Advanced analytics platform...",
    "owner": { ... },
    "status": "active",
    "progress": 35,
    "milestones": [
      {
        "id": "uuid",
        "title": "MVP Development",
        "description": "Build minimum viable product",
        "due_date": "2024-06-01",
        "status": "in_progress",
        "completion_percentage": 60
      }
    ],
    "team_members": [
      {
        "user_id": "uuid",
        "role": "Developer",
        "joined_at": "2024-01-01T00:00:00Z"
      }
    ],
    "metrics": {
      "hours_logged": 240,
      "budget_used": 15000,
      "budget_remaining": 35000
    }
  }
}
```

### PUT /projects/{project_id}

Update project.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "AI Analytics Pro",
  "description": "Updated description",
  "status": "in_progress",
  "budget": 80000,
  "progress": 45
}
```

### DELETE /projects/{project_id}

Delete project.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "Project deleted successfully"
}
```

## Analytics Endpoints

### GET /analytics/dashboard

Get dashboard analytics data.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `period`: Time period (7d, 30d, 90d, 1y)
- `user_type`: Filter by user type

**Response:**
```json
{
  "success": true,
  "data": {
    "overview": {
      "total_users": 1250,
      "active_users": 890,
      "total_projects": 340,
      "active_projects": 180
    },
    "growth_metrics": {
      "user_growth_rate": 15.5,
      "project_creation_rate": 8.2,
      "engagement_rate": 72.3
    },
    "charts": {
      "user_registration": [
        {"date": "2024-01-01", "count": 45},
        {"date": "2024-01-02", "count": 52}
      ],
      "project_creation": [
        {"date": "2024-01-01", "count": 12},
        {"date": "2024-01-02", "count": 18}
      ]
    }
  }
}
```

### GET /analytics/users

User analytics data.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "data": {
    "user_distribution": {
      "by_type": {
        "entrepreneur": 45,
        "ally": 25,
        "client": 20,
        "admin": 10
      },
      "by_location": {
        "Colombia": 40,
        "Mexico": 25,
        "Argentina": 20,
        "Other": 15
      }
    },
    "engagement_metrics": {
      "daily_active_users": 420,
      "weekly_active_users": 680,
      "monthly_active_users": 890
    }
  }
}
```

## Error Codes

### Authentication Errors
- `authentication_error`: Invalid credentials
- `token_expired`: JWT token has expired
- `token_invalid`: Invalid JWT token format
- `account_locked`: Account temporarily locked
- `account_inactive`: Account is inactive
- `email_not_verified`: Email verification required

### Validation Errors
- `validation_error`: Input validation failed
- `business_rule_violation`: Business rule validation failed
- `duplicate_resource`: Resource already exists
- `resource_not_found`: Requested resource not found

### Authorization Errors
- `permission_denied`: Insufficient permissions
- `forbidden_action`: Action not allowed
- `resource_access_denied`: Cannot access resource

### System Errors
- `internal_error`: Internal server error
- `service_unavailable`: Service temporarily unavailable
- `rate_limit_exceeded`: Too many requests
- `database_error`: Database operation failed

## Pagination

All list endpoints support pagination:

**Query Parameters:**
- `page`: Page number (starts from 1)
- `per_page`: Items per page (1-100, default: 20)
- `sort`: Sort field (default varies by endpoint)
- `order`: Sort order (`asc` or `desc`, default: `desc`)

**Response includes:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_items": 100,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false,
    "next_page": 2,
    "prev_page": null
  }
}
```

## Filtering and Search

### Query Parameters
- `search`: Search across relevant fields
- `filter[field]`: Filter by specific field
- `date_from`, `date_to`: Date range filtering

### Examples
```
GET /users?search=john&filter[user_type]=entrepreneur&filter[status]=active
GET /projects?date_from=2024-01-01&date_to=2024-01-31
```

## Webhooks

### Supported Events
- `user.created`
- `user.updated`
- `user.deleted`
- `project.created`
- `project.updated`
- `project.completed`

### Webhook Payload
```json
{
  "event": "user.created",
  "data": {
    "user_id": "uuid",
    "user": { ... }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "signature": "sha256=..."
}
```

## SDK Examples

### Python SDK
```python
from ecosistema_client import EcosistemaAPI

client = EcosistemaAPI(api_key="your-api-key")

# Authenticate
auth = client.auth.login("user@example.com", "password")
client.set_access_token(auth.access_token)

# Get current user
user = client.users.me()
print(f"Hello, {user.first_name}!")

# List projects
projects = client.projects.list(page=1, per_page=10)
for project in projects.items:
    print(f"Project: {project.name}")
```

### JavaScript SDK
```javascript
import { EcosistemaAPI } from '@ecosistema/api-client';

const client = new EcosistemaAPI({
  apiKey: 'your-api-key',
  baseURL: 'https://api.ecosistema-emprendimiento.com/api/v2'
});

// Authenticate
const auth = await client.auth.login({
  email: 'user@example.com',
  password: 'password'
});

client.setAccessToken(auth.access_token);

// Get current user
const user = await client.users.me();
console.log(`Hello, ${user.first_name}!`);

// Create project
const project = await client.projects.create({
  name: 'My New Project',
  description: 'A revolutionary idea'
});
```

## Testing

### API Testing
Use tools like Postman, Insomnia, or curl to test endpoints:

```bash
# Login
curl -X POST https://api.example.com/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Get user profile
curl -X GET https://api.example.com/api/v2/users/me \
  -H "Authorization: Bearer <token>"
```

### Automated Testing
```bash
# Run API tests
pytest tests/api/

# Load testing
locust -f load_tests.py --host=https://api.example.com
```

## Support

- **Documentation**: [https://docs.ecosistema-emprendimiento.com](https://docs.ecosistema-emprendimiento.com)
- **API Status**: [https://status.ecosistema-emprendimiento.com](https://status.ecosistema-emprendimiento.com)
- **Support**: [support@ecosistema-emprendimiento.com](mailto:support@ecosistema-emprendimiento.com)
- **Issues**: [GitHub Issues](https://github.com/ecosistema/api/issues)

## Changelog

### v2.0.0 (2024-01-15)
- **NEW**: Modern API architecture with Flask-RESTX
- **NEW**: Comprehensive authentication with 2FA support
- **NEW**: Advanced user management and profiles
- **NEW**: Project management with milestones
- **NEW**: Real-time analytics dashboard
- **IMPROVED**: Better error handling and validation
- **IMPROVED**: Enhanced security with rate limiting
- **IMPROVED**: Comprehensive API documentation

### v1.0.0 (2023-12-01)
- Initial API release
- Basic authentication and user management
- Simple project management