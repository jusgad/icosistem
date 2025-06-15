# Arquitectura de Base de Datos - Ecosistema de Emprendimiento

## Tabla de Contenidos
- [Visión General](#visión-general)
- [Arquitectura General](#arquitectura-general)
- [Modelo de Datos](#modelo-de-datos)
- [Entidades Principales](#entidades-principales)
- [Relaciones y Cardinalidades](#relaciones-y-cardinalidades)
- [Índices y Optimización](#índices-y-optimización)
- [Seguridad y Permisos](#seguridad-y-permisos)
- [Estrategias de Escalabilidad](#estrategias-de-escalabilidad)
- [Respaldos y Recuperación](#respaldos-y-recuperación)
- [Migraciones y Versionado](#migraciones-y-versionado)
- [Monitoreo y Métricas](#monitoreo-y-métricas)

## Visión General

### Tecnologías Utilizadas
- **Motor de Base de Datos**: PostgreSQL 15+ (Producción), SQLite (Desarrollo/Testing)
- **ORM**: SQLAlchemy 2.0+ con modelos declarativos
- **Migraciones**: Alembic para control de versiones de esquema
- **Connection Pool**: pgbouncer para manejo eficiente de conexiones
- **Cache**: Redis para cache de sesiones y datos frecuentemente accedidos

### Principios de Diseño
- **Normalización**: Esquema normalizado hasta 3NF con desnormalización estratégica
- **Integridad Referencial**: Uso extensivo de foreign keys y constraints
- **Auditabilidad**: Tracking completo de cambios con timestamps y user tracking
- **Escalabilidad**: Diseño preparado para sharding horizontal
- **Flexibilidad**: Uso de JSONB para datos semi-estructurados

## Arquitectura General

### Distribución de Datos
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Read Replica  │    │  Primary DB     │    │   Analytics DB  │
│   (Reportes)    │◄───┤  (Operacional)  │────┤   (DataWare)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    ┌─────────┐             ┌─────────┐             ┌─────────┐
    │  Redis  │             │ pgBouncer│             │ S3/MinIO│
    │ (Cache) │             │ (Pool)   │             │ (Files) │
    └─────────┘             └─────────┘             └─────────┘
```

### Patrón de Conexiones
- **Aplicación Web**: Pool de 20 conexiones concurrentes
- **API REST**: Pool de 15 conexiones con rate limiting
- **Workers Celery**: Pool de 10 conexiones para tareas asíncronas
- **Analytics**: Conexión dedicada a read replica

## Modelo de Datos

### Diagrama ER Conceptual
```mermaid
erDiagram
    USERS ||--o{ ENTREPRENEURS : "is_a"
    USERS ||--o{ ALLIES : "is_a"
    USERS ||--o{ CLIENTS : "is_a"
    USERS ||--o{ ADMINS : "is_a"
    
    ORGANIZATIONS ||--o{ USERS : contains
    ORGANIZATIONS ||--o{ PROGRAMS : offers
    
    PROGRAMS ||--o{ PROJECTS : includes
    ENTREPRENEURS ||--o{ PROJECTS : owns
    
    ALLIES ||--o{ MENTORSHIPS : provides
    ENTREPRENEURS ||--o{ MENTORSHIPS : receives
    
    USERS ||--o{ MEETINGS : participates
    PROJECTS ||--o{ MEETINGS : has
    
    USERS ||--o{ MESSAGES : sends
    USERS ||--o{ MESSAGES : receives
    
    USERS ||--o{ DOCUMENTS : uploads
    PROJECTS ||--o{ DOCUMENTS : contains
    
    USERS ||--o{ TASKS : assigned
    PROJECTS ||--o{ TASKS : contains
    
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ ACTIVITY_LOGS : generates
```

## Entidades Principales

### 1. Sistema de Usuarios (users)
```sql
-- Tabla base de usuarios con herencia polimórfica
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    avatar_url TEXT,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('admin', 'entrepreneur', 'ally', 'client')),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP WITH TIME ZONE,
    language_preference VARCHAR(5) DEFAULT 'es',
    timezone VARCHAR(50) DEFAULT 'America/Bogota',
    metadata JSONB DEFAULT '{}',
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- Índices críticos
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_type ON users(user_type);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_metadata_gin ON users USING GIN(metadata);
```

### 2. Organizaciones (organizations)
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    organization_type VARCHAR(50) NOT NULL,
    industry VARCHAR(100),
    website URL,
    logo_url TEXT,
    address JSONB, -- {street, city, state, country, postal_code}
    contact_info JSONB, -- {phone, email, social_media}
    settings JSONB DEFAULT '{}',
    
    -- Métricas
    total_employees INTEGER DEFAULT 0,
    annual_revenue DECIMAL(15,2),
    founded_date DATE,
    
    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    verification_status VARCHAR(20) DEFAULT 'pending',
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_organizations_type ON organizations(organization_type);
CREATE INDEX idx_organizations_industry ON organizations(industry);
CREATE INDEX idx_organizations_verification ON organizations(verification_status);
```

### 3. Programas de Emprendimiento (programs)
```sql
CREATE TABLE programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    program_type VARCHAR(50) NOT NULL, -- 'incubation', 'acceleration', 'mentorship', 'funding'
    duration_weeks INTEGER,
    max_participants INTEGER,
    
    -- Fechas
    application_start DATE,
    application_end DATE,
    program_start DATE,
    program_end DATE,
    
    -- Requisitos
    eligibility_criteria JSONB,
    required_documents JSONB,
    selection_process JSONB,
    
    -- Beneficios
    benefits JSONB, -- funding, mentorship, workspace, etc.
    success_metrics JSONB,
    
    -- Estado
    status VARCHAR(20) DEFAULT 'draft', -- draft, published, active, completed, cancelled
    is_public BOOLEAN DEFAULT TRUE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_programs_organization ON programs(organization_id);
CREATE INDEX idx_programs_type ON programs(program_type);
CREATE INDEX idx_programs_status ON programs(status);
CREATE INDEX idx_programs_dates ON programs(application_start, application_end);
```

### 4. Perfiles Específicos

#### Emprendedores (entrepreneurs)
```sql
CREATE TABLE entrepreneurs (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),
    bio TEXT,
    experience_level VARCHAR(20), -- 'beginner', 'intermediate', 'advanced', 'expert'
    industries_of_interest JSONB, -- Array de industrias
    skills JSONB, -- Array de habilidades
    education JSONB, -- Array de educación
    previous_experience JSONB, -- Array de experiencias
    
    -- Métricas de emprendimiento
    projects_count INTEGER DEFAULT 0,
    mentorship_hours_received DECIMAL(10,2) DEFAULT 0,
    funding_received DECIMAL(15,2) DEFAULT 0,
    
    -- Preferencias
    preferred_meeting_times JSONB,
    communication_preferences JSONB,
    goals JSONB,
    
    -- Estado
    availability_status VARCHAR(20) DEFAULT 'available',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entrepreneurs_organization ON entrepreneurs(organization_id);
CREATE INDEX idx_entrepreneurs_experience ON entrepreneurs(experience_level);
CREATE INDEX idx_entrepreneurs_availability ON entrepreneurs(availability_status);
```

#### Aliados/Mentores (allies)
```sql
CREATE TABLE allies (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),
    bio TEXT,
    title VARCHAR(200),
    company VARCHAR(200),
    expertise_areas JSONB, -- Array de áreas de expertise
    industries JSONB, -- Array de industrias
    certifications JSONB, -- Array de certificaciones
    
    -- Disponibilidad y tarifas
    hourly_rate DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'COP',
    availability_hours JSONB, -- Horarios disponibles por día
    max_entrepreneurs INTEGER DEFAULT 5,
    current_entrepreneurs INTEGER DEFAULT 0,
    
    -- Métricas
    total_mentorship_hours DECIMAL(10,2) DEFAULT 0,
    total_entrepreneurs_mentored INTEGER DEFAULT 0,
    average_rating DECIMAL(3,2) DEFAULT 0,
    total_reviews INTEGER DEFAULT 0,
    
    -- Preferencias
    mentorship_style JSONB,
    communication_preferences JSONB,
    specializations JSONB,
    
    -- Estado
    availability_status VARCHAR(20) DEFAULT 'available',
    verification_status VARCHAR(20) DEFAULT 'pending',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_allies_organization ON allies(organization_id);
CREATE INDEX idx_allies_availability ON allies(availability_status);
CREATE INDEX idx_allies_expertise_gin ON allies USING GIN(expertise_areas);
CREATE INDEX idx_allies_rating ON allies(average_rating);
```

### 5. Proyectos (projects)
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entrepreneur_id UUID NOT NULL REFERENCES entrepreneurs(id) ON DELETE CASCADE,
    program_id UUID REFERENCES programs(id),
    
    -- Información básica
    name VARCHAR(200) NOT NULL,
    description TEXT,
    tagline VARCHAR(500),
    industry VARCHAR(100),
    business_model VARCHAR(50),
    
    -- Detalles del proyecto
    problem_statement TEXT,
    solution_description TEXT,
    target_market JSONB,
    competitive_analysis JSONB,
    revenue_model JSONB,
    
    -- Métricas financieras
    funding_needed DECIMAL(15,2),
    funding_raised DECIMAL(15,2) DEFAULT 0,
    current_revenue DECIMAL(15,2) DEFAULT 0,
    projected_revenue JSONB, -- Proyecciones por año
    
    -- Equipo y recursos
    team_size INTEGER DEFAULT 1,
    team_members JSONB,
    required_skills JSONB,
    
    -- Estado y progreso
    status VARCHAR(20) DEFAULT 'idea', -- idea, development, testing, launch, growth, pivot, paused, completed
    stage VARCHAR(20) DEFAULT 'concept', -- concept, prototype, mvp, beta, production
    progress_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- Fechas importantes
    started_date DATE,
    target_launch_date DATE,
    actual_launch_date DATE,
    
    -- Métricas de tracción
    user_metrics JSONB, -- MAU, conversión, etc.
    market_validation JSONB,
    milestones JSONB,
    
    -- Configuración
    is_public BOOLEAN DEFAULT FALSE,
    seeking_funding BOOLEAN DEFAULT FALSE,
    seeking_mentorship BOOLEAN DEFAULT TRUE,
    seeking_partners BOOLEAN DEFAULT FALSE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_projects_entrepreneur ON projects(entrepreneur_id);
CREATE INDEX idx_projects_program ON projects(program_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_industry ON projects(industry);
CREATE INDEX idx_projects_funding ON projects(seeking_funding) WHERE seeking_funding = TRUE;
CREATE INDEX idx_projects_created_at ON projects(created_at);
```

### 6. Sesiones de Mentoría (mentorships)
```sql
CREATE TABLE mentorships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ally_id UUID NOT NULL REFERENCES allies(id) ON DELETE CASCADE,
    entrepreneur_id UUID NOT NULL REFERENCES entrepreneurs(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id),
    
    -- Configuración de la mentoría
    mentorship_type VARCHAR(20) NOT NULL, -- 'ongoing', 'project_based', 'one_time'
    focus_areas JSONB, -- Areas específicas de enfoque
    goals JSONB, -- Objetivos de la mentoría
    duration_weeks INTEGER,
    
    -- Sesiones
    total_sessions_planned INTEGER DEFAULT 0,
    total_sessions_completed INTEGER DEFAULT 0,
    session_frequency VARCHAR(20), -- 'weekly', 'biweekly', 'monthly'
    session_duration_minutes INTEGER DEFAULT 60,
    
    -- Métricas y progreso
    progress_notes TEXT,
    achievements JSONB,
    challenges JSONB,
    success_metrics JSONB,
    
    -- Fechas
    start_date DATE NOT NULL,
    end_date DATE,
    actual_end_date DATE,
    
    -- Estado y evaluación
    status VARCHAR(20) DEFAULT 'active', -- active, paused, completed, cancelled
    entrepreneur_rating INTEGER CHECK (entrepreneur_rating BETWEEN 1 AND 5),
    ally_rating INTEGER CHECK (ally_rating BETWEEN 1 AND 5),
    entrepreneur_feedback TEXT,
    ally_feedback TEXT,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),
    
    UNIQUE(ally_id, entrepreneur_id, project_id)
);

CREATE INDEX idx_mentorships_ally ON mentorships(ally_id);
CREATE INDEX idx_mentorships_entrepreneur ON mentorships(entrepreneur_id);
CREATE INDEX idx_mentorships_project ON mentorships(project_id);
CREATE INDEX idx_mentorships_status ON mentorships(status);
CREATE INDEX idx_mentorships_dates ON mentorships(start_date, end_date);
```

### 7. Reuniones (meetings)
```sql
CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mentorship_id UUID REFERENCES mentorships(id),
    project_id UUID REFERENCES projects(id),
    
    -- Información básica
    title VARCHAR(200) NOT NULL,
    description TEXT,
    meeting_type VARCHAR(30) NOT NULL, -- 'mentorship', 'project_review', 'team', 'investor_pitch'
    
    -- Programación
    scheduled_start TIMESTAMP WITH TIME ZONE NOT NULL,
    scheduled_end TIMESTAMP WITH TIME ZONE NOT NULL,
    actual_start TIMESTAMP WITH TIME ZONE,
    actual_end TIMESTAMP WITH TIME ZONE,
    timezone VARCHAR(50) DEFAULT 'America/Bogota',
    
    -- Ubicación/Plataforma
    location_type VARCHAR(20) NOT NULL, -- 'online', 'in_person', 'hybrid'
    location_details JSONB, -- {platform, link, address, room}
    
    -- Agenda y contenido
    agenda JSONB,
    objectives JSONB,
    materials JSONB, -- Documentos, enlaces, etc.
    
    -- Estado
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, in_progress, completed, cancelled, rescheduled
    cancellation_reason VARCHAR(200),
    
    -- Seguimiento
    notes TEXT,
    action_items JSONB,
    next_steps JSONB,
    attachments JSONB,
    
    -- Métricas
    attendee_count INTEGER DEFAULT 0,
    duration_minutes INTEGER,
    productivity_rating INTEGER CHECK (productivity_rating BETWEEN 1 AND 5),
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_meetings_mentorship ON meetings(mentorship_id);
CREATE INDEX idx_meetings_project ON meetings(project_id);
CREATE INDEX idx_meetings_scheduled_start ON meetings(scheduled_start);
CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_meetings_type ON meetings(meeting_type);
```

### 8. Participantes de Reuniones (meeting_participants)
```sql
CREATE TABLE meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Rol en la reunión
    role VARCHAR(20) NOT NULL, -- 'organizer', 'required', 'optional', 'observer'
    
    -- Estado de participación
    invitation_status VARCHAR(20) DEFAULT 'pending', -- pending, accepted, declined, tentative
    attendance_status VARCHAR(20) DEFAULT 'unknown', -- unknown, present, absent, late
    
    -- Participación
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE,
    connection_quality VARCHAR(20), -- excellent, good, fair, poor
    
    -- Notas específicas del participante
    private_notes TEXT,
    satisfaction_rating INTEGER CHECK (satisfaction_rating BETWEEN 1 AND 5),
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(meeting_id, user_id)
);

CREATE INDEX idx_meeting_participants_meeting ON meeting_participants(meeting_id);
CREATE INDEX idx_meeting_participants_user ON meeting_participants(user_id);
CREATE INDEX idx_meeting_participants_role ON meeting_participants(role);
CREATE INDEX idx_meeting_participants_status ON meeting_participants(attendance_status);
```

### 9. Sistema de Mensajería (messages)
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type VARCHAR(20) NOT NULL, -- 'direct', 'group', 'project', 'mentorship'
    title VARCHAR(200),
    description TEXT,
    
    -- Configuración
    is_archived BOOLEAN DEFAULT FALSE,
    is_muted BOOLEAN DEFAULT FALSE,
    
    -- Referencia opcional a contexto
    project_id UUID REFERENCES projects(id),
    mentorship_id UUID REFERENCES mentorships(id),
    meeting_id UUID REFERENCES meetings(id),
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id)
);

CREATE TABLE conversation_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Permisos
    role VARCHAR(20) DEFAULT 'member', -- admin, moderator, member
    can_add_participants BOOLEAN DEFAULT FALSE,
    can_remove_participants BOOLEAN DEFAULT FALSE,
    
    -- Estado
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    last_read_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Configuración personal
    notifications_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,
    
    UNIQUE(conversation_id, user_id)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id),
    
    -- Contenido
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'text', -- text, file, image, link, system
    
    -- Referencias
    reply_to_id UUID REFERENCES messages(id),
    thread_root_id UUID REFERENCES messages(id),
    
    -- Archivos adjuntos
    attachments JSONB,
    
    -- Métricas de entrega
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_by JSONB DEFAULT '{}', -- {user_id: timestamp}
    
    -- Estado
    is_edited BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_thread ON messages(thread_root_id);
CREATE INDEX idx_conversations_project ON conversations(project_id);
CREATE INDEX idx_conversations_mentorship ON conversations(mentorship_id);
```

### 10. Sistema de Documentos (documents)
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Propietario y contexto
    owner_id UUID NOT NULL REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    mentorship_id UUID REFERENCES mentorships(id),
    meeting_id UUID REFERENCES meetings(id),
    
    -- Información del archivo
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 para detección de duplicados
    
    -- Almacenamiento
    storage_provider VARCHAR(20) DEFAULT 's3', -- s3, local, gcs
    storage_path TEXT NOT NULL,
    storage_bucket VARCHAR(100),
    
    -- Metadatos
    title VARCHAR(300),
    description TEXT,
    document_type VARCHAR(50), -- business_plan, pitch_deck, financial_model, etc.
    category VARCHAR(50),
    tags JSONB,
    
    -- Versionado
    version INTEGER DEFAULT 1,
    parent_document_id UUID REFERENCES documents(id),
    is_latest_version BOOLEAN DEFAULT TRUE,
    
    -- Permisos y compartir
    visibility VARCHAR(20) DEFAULT 'private', -- private, project, mentorship, organization, public
    download_allowed BOOLEAN DEFAULT TRUE,
    
    -- Procesamiento
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    extracted_text TEXT, -- Para búsqueda full-text
    thumbnail_url TEXT,
    preview_url TEXT,
    
    -- Métricas
    download_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_project ON documents(project_id);
CREATE INDEX idx_documents_mentorship ON documents(mentorship_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_visibility ON documents(visibility);
CREATE INDEX idx_documents_hash ON documents(file_hash);
CREATE INDEX idx_documents_search ON documents USING GIN(to_tsvector('spanish', title || ' ' || COALESCE(description, '') || ' ' || COALESCE(extracted_text, '')));
```

### 11. Sistema de Tareas (tasks)
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Contexto
    project_id UUID REFERENCES projects(id),
    mentorship_id UUID REFERENCES mentorships(id),
    meeting_id UUID REFERENCES meetings(id),
    parent_task_id UUID REFERENCES tasks(id),
    
    -- Información básica
    title VARCHAR(300) NOT NULL,
    description TEXT,
    task_type VARCHAR(30) DEFAULT 'general', -- general, milestone, deliverable, action_item
    
    -- Asignación
    assigned_to UUID REFERENCES users(id),
    assigned_by UUID REFERENCES users(id),
    
    -- Programación
    due_date TIMESTAMP WITH TIME ZONE,
    start_date TIMESTAMP WITH TIME ZONE,
    estimated_hours DECIMAL(10,2),
    actual_hours DECIMAL(10,2) DEFAULT 0,
    
    -- Estado y progreso
    status VARCHAR(20) DEFAULT 'pending', -- pending, in_progress, blocked, completed, cancelled
    priority VARCHAR(10) DEFAULT 'medium', -- low, medium, high, urgent
    progress_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- Dependencias
    depends_on JSONB, -- Array de task IDs
    blocks JSONB, -- Array de task IDs que esta tarea bloquea
    
    -- Seguimiento
    completion_notes TEXT,
    completion_evidence JSONB, -- Links, archivos, etc.
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Métricas
    time_logs JSONB, -- Registro de tiempo trabajado
    comments_count INTEGER DEFAULT 0,
    
    -- Configuración
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern JSONB, -- Para tareas recurrentes
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);
```

### 12. Sistema de Notificaciones (notifications)
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Destinatario
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Contenido
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL, -- meeting_reminder, task_assigned, message_received, etc.
    
    -- Contexto y referencias
    entity_type VARCHAR(50), -- project, meeting, task, message, etc.
    entity_id UUID,
    
    -- Datos adicionales
    data JSONB DEFAULT '{}', -- Datos específicos del tipo de notificación
    
    -- Canales de entrega
    channels JSONB DEFAULT '["web"]', -- web, email, sms, push
    
    -- Estado de entrega
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Programación
    scheduled_for TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Configuración
    priority VARCHAR(10) DEFAULT 'normal', -- low, normal, high, urgent
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Acciones
    action_buttons JSONB, -- Botones de acción rápida
    action_taken VARCHAR(50), -- accept, decline, dismiss, etc.
    action_taken_at TIMESTAMP WITH TIME ZONE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_read ON notifications(is_read);
CREATE INDEX idx_notifications_scheduled ON notifications(scheduled_for);
CREATE INDEX idx_notifications_entity ON notifications(entity_type, entity_id);
```

### 13. Log de Actividades (activity_logs)
```sql
CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Actor
    user_id UUID REFERENCES users(id), -- NULL para acciones del sistema
    
    -- Acción
    action VARCHAR(100) NOT NULL, -- created, updated, deleted, viewed, etc.
    entity_type VARCHAR(50) NOT NULL, -- user, project, meeting, etc.
    entity_id UUID NOT NULL,
    
    -- Contexto adicional
    description TEXT,
    changes JSONB, -- Cambios específicos realizados
    metadata JSONB DEFAULT '{}',
    
    -- Información técnica
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    
    -- Información de contexto
    organization_id UUID REFERENCES organizations(id),
    project_id UUID REFERENCES projects(id),
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Particionado por fecha para mejor rendimiento
CREATE INDEX idx_activity_logs_user ON activity_logs(user_id);
CREATE INDEX idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
CREATE INDEX idx_activity_logs_action ON activity_logs(action);
CREATE INDEX idx_activity_logs_created_at ON activity_logs(created_at);
CREATE INDEX idx_activity_logs_organization ON activity_logs(organization_id);

-- Particionado mensual para logs
SELECT partman.create_parent('public.activity_logs', 'created_at', 'native', 'monthly');
```

### 14. Analytics y Métricas (analytics)
```sql
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identificación del evento
    event_name VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL, -- user, project, mentorship, system
    
    -- Actor y contexto
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255),
    organization_id UUID REFERENCES organizations(id),
    
    -- Propiedades del evento
    properties JSONB DEFAULT '{}',
    
    -- Información técnica
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    
    -- Geolocalización
    country VARCHAR(2),
    region VARCHAR(100),
    city VARCHAR(100),
    
    -- Dispositivo
    device_type VARCHAR(20), -- desktop, mobile, tablet
    os VARCHAR(50),
    browser VARCHAR(50)
);

-- Tabla agregada para métricas rápidas
CREATE TABLE analytics_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Dimensiones
    date DATE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    dimension_type VARCHAR(50), -- organization, user_type, project_stage, etc.
    dimension_value VARCHAR(100),
    
    -- Métricas
    count_value BIGINT DEFAULT 0,
    sum_value DECIMAL(15,2) DEFAULT 0,
    avg_value DECIMAL(15,2) DEFAULT 0,
    min_value DECIMAL(15,2),
    max_value DECIMAL(15,2),
    
    -- Metadatos
    properties JSONB DEFAULT '{}',
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(date, metric_name, dimension_type, dimension_value)
);

CREATE INDEX idx_analytics_events_name ON analytics_events(event_name);
CREATE INDEX idx_analytics_events_user ON analytics_events(user_id);
CREATE INDEX idx_analytics_events_timestamp ON analytics_events(timestamp);
CREATE INDEX idx_analytics_events_organization ON analytics_events(organization_id);

CREATE INDEX idx_analytics_summary_date ON analytics_summary(date);
CREATE INDEX idx_analytics_summary_metric ON analytics_summary(metric_name);
CREATE INDEX idx_analytics_summary_dimension ON analytics_summary(dimension_type, dimension_value);
```

## Relaciones y Cardinalidades

### Relaciones Principales
```
1. users (1) ←→ (0..1) entrepreneurs/allies/clients/admins
2. organizations (1) ←→ (*) users [many-to-many via user_organizations]
3. organizations (1) ←→ (*) programs
4. entrepreneurs (1) ←→ (*) projects
5. allies (*) ←→ (*) entrepreneurs [via mentorships]
6. projects (1) ←→ (*) meetings
7. users (*) ←→ (*) meetings [via meeting_participants]
8. users (1) ←→ (*) messages
9. users (1) ←→ (*) documents
10. users (1) ←→ (*) tasks
```

### Tablas de Unión Adicionales
```sql
-- Relación many-to-many entre usuarios y organizaciones
CREATE TABLE user_organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- member, admin, owner
    permissions JSONB DEFAULT '{}',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_id, organization_id)
);

-- Evaluaciones y ratings
CREATE TABLE user_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rater_id UUID NOT NULL REFERENCES users(id),
    rated_id UUID NOT NULL REFERENCES users(id),
    context_type VARCHAR(20) NOT NULL, -- mentorship, collaboration, project
    context_id UUID NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(rater_id, rated_id, context_type, context_id)
);
```

## Índices y Optimización

### Índices Compuestos Críticos
```sql
-- Consultas frecuentes de dashboard
CREATE INDEX idx_projects_entrepreneur_status ON projects(entrepreneur_id, status);
CREATE INDEX idx_meetings_user_date ON meeting_participants(user_id, meeting_id) 
    INCLUDE (created_at) WHERE attendance_status = 'present';

-- Búsquedas de mentoría
CREATE INDEX idx_mentorships_status_dates ON mentorships(status, start_date, end_date);
CREATE INDEX idx_allies_availability_expertise ON allies(availability_status) 
    INCLUDE (expertise_areas) WHERE availability_status = 'available';

-- Analytics y reportes
CREATE INDEX idx_activity_logs_entity_date ON activity_logs(entity_type, entity_id, created_at);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read, created_at) 
    WHERE is_read = FALSE;
```

### Optimizaciones de Consulta
```sql
-- Estadísticas automáticas
SET default_statistics_target = 100;

-- Configuración de trabajo de memoria
SET work_mem = '256MB';
SET shared_buffers = '2GB';
SET effective_cache_size = '8GB';

-- Optimizaciones específicas
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- Para búsqueda fuzzy
CREATE EXTENSION IF NOT EXISTS unaccent; -- Para búsqueda sin acentos
```

## Seguridad y Permisos

### Row Level Security (RLS)
```sql
-- Habilitar RLS en tablas sensibles
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Políticas de acceso
CREATE POLICY "Users can view their own projects" ON projects
    FOR SELECT USING (entrepreneur_id = current_user_id());

CREATE POLICY "Mentors can view mentee projects" ON projects
    FOR SELECT USING (
        entrepreneur_id IN (
            SELECT entrepreneur_id 
            FROM mentorships 
            WHERE ally_id = current_user_id() 
            AND status = 'active'
        )
    );

-- Función para obtener el usuario actual
CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_user_id')::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Encriptación de Datos Sensibles
```sql
-- Extensión para encriptación
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Función para encriptar datos sensibles
CREATE OR REPLACE FUNCTION encrypt_sensitive_data(data TEXT) RETURNS TEXT AS $$
BEGIN
    RETURN crypt(data, gen_salt('bf', 8));
END;
$$ LANGUAGE plpgsql;
```

## Estrategias de Escalabilidad

### Particionado
```sql
-- Particionado por fecha para logs
CREATE TABLE activity_logs_y2024m01 PARTITION OF activity_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Particionado por organización para datos grandes
CREATE TABLE projects_org_1 PARTITION OF projects
    FOR VALUES IN (1, 2, 3, 4, 5);
```

### Read Replicas
```yaml
# Configuración de lectura/escritura
database_urls:
  master: "postgresql://user:pass@master-db:5432/ecosystem"
  read_replica: "postgresql://user:pass@replica-db:5432/ecosystem"
  analytics: "postgresql://user:pass@analytics-db:5432/ecosystem"
```

### Caching Strategy
```sql
-- Vistas materializadas para reportes
CREATE MATERIALIZED VIEW user_stats AS
SELECT 
    u.user_type,
    COUNT(*) as total_users,
    COUNT(*) FILTER (WHERE u.is_active) as active_users,
    AVG(EXTRACT(EPOCH FROM NOW() - u.created_at)/86400) as avg_days_since_signup
FROM users u
GROUP BY u.user_type;

-- Refresh automático
CREATE INDEX ON user_stats (user_type);
```

## Respaldos y Recuperación

### Estrategia de Backup
```bash
#!/bin/bash
# Script de backup diario
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
    --format=custom \
    --compress=9 \
    --file="/backups/ecosystem_$(date +%Y%m%d_%H%M%S).dump"

# Backup incremental con WAL-E
wal-e backup-push /var/lib/postgresql/data
```

### Point-in-Time Recovery
```sql
-- Configuración para PITR
archive_mode = on
archive_command = 'wal-e wal-push %p'
wal_level = replica
max_wal_senders = 3
```

## Migraciones y Versionado

### Estructura de Migraciones
```python
# migrations/versions/001_initial_schema.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Crear extensiones
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "unaccent"')
    
    # Crear tablas en orden de dependencias
    create_users_table()
    create_organizations_table()
    # ... resto de tablas

def downgrade():
    # Rollback en orden inverso
    op.drop_table('analytics_events')
    # ... resto de rollbacks
```

### Scripts de Migración de Datos
```python
# scripts/migrate_legacy_data.py
def migrate_legacy_users():
    """Migrar usuarios del sistema legacy"""
    legacy_users = fetch_legacy_users()
    
    for user in legacy_users:
        new_user = User(
            email=user['email'],
            password_hash=encrypt_password(user['password']),
            user_type=map_user_type(user['role']),
            # ... mapping de campos
        )
        db.session.add(new_user)
    
    db.session.commit()
```

## Monitoreo y Métricas

### Métricas de Performance
```sql
-- Queries lentas
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Índices no utilizados
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0;

-- Tamaño de tablas
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Alertas Automáticas
```yaml
# prometheus.yml
alerts:
  - name: "Database Connection Pool"
    condition: "pg_stat_database_numbackends > 80"
    severity: "warning"
    
  - name: "Slow Query Detected"
    condition: "pg_stat_statements_mean_time > 1000"
    severity: "critical"
```

### Health Checks
```python
def database_health_check():
    """Verificar salud de la base de datos"""
    checks = {
        'connection': test_connection(),
        'replication_lag': check_replication_lag(),
        'disk_space': check_disk_space(),
        'active_connections': check_connection_count(),
        'query_performance': check_slow_queries()
    }
    
    return {
        'status': 'healthy' if all(checks.values()) else 'unhealthy',
        'checks': checks,
        'timestamp': datetime.utcnow()
    }
```

## Consideraciones Especiales

### Datos Semi-estructurados
```sql
-- Optimización de consultas JSONB
CREATE INDEX idx_projects_target_market_gin ON projects USING GIN(target_market);
CREATE INDEX idx_user_metadata_gin ON users USING GIN(metadata);

-- Consultas optimizadas
SELECT * FROM projects 
WHERE target_market @> '{"age_range": {"min": 18, "max": 35}}';
```

### Internacionalización
```sql
-- Soporte multi-idioma
CREATE TABLE translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    language_code VARCHAR(5) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    translated_value TEXT NOT NULL,
    
    UNIQUE(entity_type, entity_id, language_code, field_name)
);
```

### Compliance y Auditoria
```sql
-- Tabla de consentimientos GDPR
CREATE TABLE user_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type VARCHAR(50) NOT NULL, -- data_processing, marketing, analytics
    consent_given BOOLEAN NOT NULL,
    consent_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    
    -- Para cumplimiento legal
    legal_basis VARCHAR(100),
    purpose_description TEXT,
    data_retention_period INTERVAL
);
```

---

**Documento creado por**: Arquitecto de Datos Senior  
**Fecha**: Junio 2025  
**Versión**: 1.0  
**Estado**: Aprobado para Implementación

> **Nota**: Esta documentación debe mantenerse actualizada con cada cambio en el esquema de la base de datos. Utilizar las migraciones de Alembic para mantener sincronización entre entornos.