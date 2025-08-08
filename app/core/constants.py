"""
Constants for the entrepreneurship ecosystem.
"""

# User roles
ADMIN_ROLE = 'admin'
ENTREPRENEUR_ROLE = 'entrepreneur' 
ALLY_ROLE = 'ally'
CLIENT_ROLE = 'client'

VALID_ROLES = [ADMIN_ROLE, ENTREPRENEUR_ROLE, ALLY_ROLE, CLIENT_ROLE]
ADMIN_ROLES = [ADMIN_ROLE]  # Only admin for now
MENTOR_ROLES = [ALLY_ROLE]  # Allies are mentors
MENTEE_ROLES = [ENTREPRENEUR_ROLE]  # Entrepreneurs are mentees

USER_ROLES = {
    ADMIN_ROLE: {'name': 'Administrador', 'permissions': ['all']},
    ENTREPRENEUR_ROLE: {'name': 'Emprendedor', 'permissions': ['create_project', 'manage_own_projects']},
    ALLY_ROLE: {'name': 'Aliado/Mentor', 'permissions': ['mentor', 'view_entrepreneurs']},
    CLIENT_ROLE: {'name': 'Cliente', 'permissions': ['view_directory', 'generate_reports']}
}

# Timezone
TIMEZONE_BOGOTA = 'America/Bogota'

# Project statuses
PROJECT_STATUSES = [
    'idea', 'validation', 'development', 'launch', 
    'growth', 'scale', 'exit', 'paused', 'cancelled'
]
PROJECT_STATUS = PROJECT_STATUSES  # Alias for compatibility

# Project types
PROJECT_TYPES = [
    'startup', 'social_enterprise', 'cooperative', 'ngo', 'corporate_innovation'
]

# Business models
BUSINESS_MODELS = [
    'b2b', 'b2c', 'b2g', 'marketplace', 'saas', 'freemium', 'subscription'
]

# Industry sectors
INDUSTRY_SECTORS = [
    'technology', 'finance', 'health', 'education', 'agriculture', 'retail', 'services'
]

# Target markets
TARGET_MARKETS = [
    'local', 'national', 'regional', 'global'
]

# Funding stages
FUNDING_STAGES = [
    'bootstrap', 'pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'ipo'
]

# Currencies
CURRENCIES = [
    'COP', 'USD', 'EUR'
]

# Priority levels
PRIORITY_LEVELS = [
    'low', 'medium', 'high', 'critical'
]

# Risk levels
RISK_LEVELS = [
    'low', 'medium', 'high'
]

# Organization types
ORGANIZATION_TYPES = [
    'startup', 'corporation', 'ngo', 'government', 'university', 'accelerator'
]

# Organization status
ORGANIZATION_STATUS = [
    'active', 'inactive', 'pending', 'suspended'
]

# Organization sizes
ORGANIZATION_SIZES = [
    'startup', 'small', 'medium', 'large', 'enterprise'
]

# Program types
PROGRAM_TYPES = [
    'accelerator', 'incubator', 'mentorship', 'training', 'funding'
]

# Program status
PROGRAM_STATUS = [
    'active', 'inactive', 'draft', 'completed', 'cancelled'
]

# Entrepreneur stages
ENTREPRENEUR_STAGES = [
    'ideation', 'validation', 'prototype', 'launch', 'growth', 'scale'
]

# Event types
EVENT_TYPES = [
    'workshop', 'seminar', 'networking', 'pitch', 'conference', 'training'
]

# Event status
EVENT_STATUS = [
    'scheduled', 'in_progress', 'completed', 'cancelled', 'postponed'
]

# Program formats
PROGRAM_FORMATS = [
    'in_person', 'online', 'hybrid'
]

# Assessment status
ASSESSMENT_STATUS = [
    'pending', 'in_progress', 'completed', 'approved', 'rejected'
]

# Selection criteria
SELECTION_CRITERIA = [
    'innovation', 'market_potential', 'team_experience', 'financial_viability', 'scalability'
]

# Notification channels
NOTIFICATION_CHANNELS = [
    'email', 'sms', 'push', 'in_app'
]

# File storage types
FILE_STORAGE_TYPES = [
    'local', 'aws_s3', 'google_cloud', 'azure_blob'
]

# API versions
API_VERSIONS = [
    'v1', 'v2', 'beta'
]

# Error codes
ERROR_CODES = {
    'VALIDATION_ERROR': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'CONFLICT': 409,
    'INTERNAL_ERROR': 500
}

# Success codes
SUCCESS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'ACCEPTED': 202,
    'NO_CONTENT': 204
}

# User permissions
USER_PERMISSIONS = [
    'read', 'write', 'delete', 'admin', 'create_project', 'manage_users'
]

# Timezone mappings
TIMEZONE_MAPPINGS = {
    'bogota': 'America/Bogota',
    'utc': 'UTC',
    'ny': 'America/New_York',
    'madrid': 'Europe/Madrid'
}

# Meeting priorities
MEETING_PRIORITIES = [
    'low', 'medium', 'high', 'urgent'
]

# Notification types
NOTIFICATION_TYPES = [
    'info', 'warning', 'error', 'success'
]

# Email types
EMAIL_TYPES = [
    'welcome', 'verification', 'reset_password', 'notification', 'marketing'
]

# File types
FILE_TYPES = [
    'document', 'image', 'video', 'audio', 'archive', 'other'
]

# Recurrence patterns
RECURRENCE_PATTERNS = [
    'none', 'daily', 'weekly', 'monthly', 'yearly'
]

# Availability status
AVAILABILITY_STATUS = [
    'available', 'busy', 'away', 'offline'
]

# Contact methods
CONTACT_METHODS = [
    'email', 'phone', 'whatsapp', 'telegram', 'video_call'
]

# Document types
DOCUMENT_TYPES = [
    'pdf', 'word', 'excel', 'powerpoint', 'text', 'image'
]

# Application status
APPLICATION_STATUS = [
    'draft', 'submitted', 'under_review', 'approved', 'rejected'
]

# Meeting types
MEETING_TYPES = [
    'consultation', 'mentorship', 'presentation', 'workshop', 'networking'
]

# Meeting status
MEETING_STATUS = [
    'scheduled', 'in_progress', 'completed', 'cancelled', 'rescheduled'
]

# Message types
MESSAGE_TYPES = [
    'inquiry', 'support', 'complaint', 'suggestion', 'other'
]

# Notification types
NOTIFICATION_TYPES = [
    'info', 'warning', 'success', 'error'
]

# Task status
TASK_STATUS = [
    'pending', 'in_progress', 'completed', 'cancelled'
]

# Document types
DOCUMENT_TYPES = [
    'business_plan', 'pitch_deck', 'financial_report', 'legal_document', 'other'
]

# Certification types
CERTIFICATION_TYPES = [
    'iso_9001', 'iso_14001', 'benefit_corp', 'b_corp', 'organic', 'fair_trade'
]

# Countries
COUNTRIES = [
    'CO', 'US', 'MX', 'AR', 'BR', 'CL', 'PE', 'EC', 'VE', 'UY', 'PY', 'BO'
]

# Business limits and constraints
MAX_ENTREPRENEURS_PER_ALLY = 50
MAX_PROJECTS_PER_ENTREPRENEUR = 10
MAX_MENTORSHIP_SESSIONS_PER_MONTH = 20
MAX_FILE_SIZE_MB = 10
MAX_UPLOAD_FILES = 5

# Time constants
SESSION_TIMEOUT_HOURS = 24
PASSWORD_RESET_TIMEOUT_HOURS = 2
EMAIL_VERIFICATION_TIMEOUT_HOURS = 48

# Cache timeouts (in seconds)
CACHE_TIMEOUT_SHORT = 300   # 5 minutes
CACHE_TIMEOUT_MEDIUM = 3600  # 1 hour
CACHE_TIMEOUT_LONG = 86400   # 24 hours

# Economic sectors
ECONOMIC_SECTORS = [
    'technology', 'finance', 'health', 'education', 'agriculture', 
    'manufacturing', 'retail', 'services', 'energy', 'transport'
]

# Mentorship configuration
MENTORSHIP_CONFIG = {
    'max_sessions_per_month': 20,
    'session_duration_minutes': 60,
    'advance_booking_days': 7,
    'cancellation_hours': 24
}

# Client types
CLIENT_TYPES = [
    'individual', 'corporate', 'government', 'nonprofit', 'startup'
]

# Client status
CLIENT_STATUS = [
    'active', 'inactive', 'pending', 'suspended', 'prospect'
]

# Company sizes
COMPANY_SIZES = [
    'startup', 'small', 'medium', 'large', 'enterprise'
]

# Interest areas
INTEREST_AREAS = [
    'technology', 'innovation', 'sustainability', 'social_impact', 
    'market_expansion', 'investment', 'partnership', 'mentorship'
]

# Report types
REPORT_TYPES = [
    'financial', 'progress', 'market_analysis', 'impact', 'custom'
]

# Partnership types
PARTNERSHIP_TYPES = [
    'strategic', 'technology', 'marketing', 'distribution', 'investment'
]

# Activity types
ACTIVITY_TYPES = [
    'login', 'logout', 'registration', 'profile_update', 'project_created', 
    'meeting_scheduled', 'message_sent', 'document_uploaded', 'report_generated'
]

# Auto-generated stubs
REMINDER_INTERVALS = []  # Auto-generated stub


# Auto-generated comprehensive stubs - 1 items
EMAIL_PRIORITIES = ['low', 'medium', 'high']

# Final emergency patch
PARTICIPANT_ROLES = ['host', 'participant', 'observer']
