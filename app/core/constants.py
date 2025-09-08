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

# Business stages
BUSINESS_STAGES = [
    'idea', 'concept', 'prototype', 'mvp', 'early_stage', 'growth', 'mature', 'scale'
]

# Industries
INDUSTRIES = [
    'technology', 'finance', 'health', 'education', 'agriculture', 'retail', 'services',
    'manufacturing', 'energy', 'transport', 'media', 'tourism', 'food', 'fashion'
]

# Mentorship status
MENTORSHIP_STATUS = [
    'active', 'completed', 'paused', 'cancelled', 'pending'
]

# Evaluation criteria
EVALUATION_CRITERIA = [
    'innovation', 'market_potential', 'team', 'financial_viability', 'scalability', 'impact'
]

# Task status
TASK_STATUS = [
    'pending', 'in_progress', 'completed', 'cancelled', 'overdue'
]

# Activity types
ACTIVITY_TYPES = [
    'user_login', 'user_registration', 'project_created', 'project_updated', 
    'meeting_scheduled', 'task_completed', 'document_uploaded', 'message_sent'
]

# Entrepreneur stages
ENTREPRENEUR_STAGES = [
    'aspirant', 'beginner', 'developing', 'advanced', 'expert'
]

# Project phases
PROJECT_PHASES = [
    'conception', 'planning', 'development', 'testing', 'launch', 'growth', 'maturity'
]

# Project categories
PROJECT_CATEGORIES = [
    'technology', 'social', 'environmental', 'healthcare', 'education', 'finance', 'other'
]

# Mentorship types
MENTORSHIP_TYPES = [
    'individual', 'group', 'peer_to_peer', 'expert', 'reverse'
]

# Mentor specialties
MENTOR_SPECIALTIES = [
    'business_strategy', 'marketing', 'finance', 'technology', 'operations',
    'legal', 'product_development', 'sales', 'leadership', 'fundraising'
]

# Session outcomes
SESSION_OUTCOMES = [
    'successful', 'partially_successful', 'needs_followup', 'cancelled', 'no_show'
]

# Calendar providers
CALENDAR_PROVIDERS = [
    'google', 'outlook', 'apple', 'caldav'
]

# Message status
MESSAGE_STATUS = [
    'sent', 'delivered', 'read', 'failed', 'pending'
]

# Message priorities
MESSAGE_PRIORITIES = [
    'low', 'normal', 'high', 'urgent'
]

# Conversation types
CONVERSATION_TYPES = [
    'direct', 'group', 'announcement', 'support', 'mentorship'
]

# Attachment types
ATTACHMENT_TYPES = [
    'image', 'document', 'video', 'audio', 'archive', 'other'
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

# Se eliminó duplicado - ya se definió arriba en líneas 75-78

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

# OAuth providers
OAUTH_PROVIDERS = [
    'google', 'microsoft', 'linkedin', 'github', 'facebook'
]

# OAuth scopes
OAUTH_SCOPES = {
    'google': ['openid', 'email', 'profile', 'https://www.googleapis.com/auth/calendar'],
    'microsoft': ['openid', 'email', 'profile', 'https://graph.microsoft.com/calendars.readwrite'],
    'linkedin': ['r_liteprofile', 'r_emailaddress'],
    'github': ['user:email', 'read:user'],
    'facebook': ['email', 'public_profile']
}

# Integration types
INTEGRATION_TYPES = [
    'oauth', 'api_key', 'webhook', 'manual'
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

# Meeting priorities
MEETING_PRIORITIES = [
    'low', 'medium', 'high', 'urgent'
]

# Recurrence patterns
RECURRENCE_PATTERNS = [
    'none', 'daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'yearly'
]

# Se eliminó duplicado - ya se definió arriba como REMINDER_INTERVALS corregido

# Participant roles
PARTICIPANT_ROLES = [
    'organizer', 'required', 'optional', 'resource'
]

# Attendance status
ATTENDANCE_STATUS = [
    'pending', 'accepted', 'declined', 'tentative', 'no_response', 'attended', 'absent'
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
    'not_started', 'in_progress', 'blocked', 'waiting_approval', 'under_review',
    'completed', 'cancelled', 'deferred', 'archived', 'failed'
]

# Task types
TASK_TYPES = [
    'general', 'milestone', 'deliverable', 'approval', 'review', 'meeting_prep',
    'follow_up', 'administrative', 'research', 'development', 'marketing',
    'financial', 'legal', 'compliance', 'training', 'documentation',
    'testing', 'deployment', 'maintenance', 'support', 'recurring', 'template'
]

# Task priorities  
TASK_PRIORITIES = [
    'lowest', 'low', 'medium', 'high', 'highest', 'critical', 'urgent'
]

# Task categories
TASK_CATEGORIES = [
    'business_development', 'product_development', 'marketing_sales', 'operations',
    'finance', 'legal_compliance', 'hr_talent', 'technology', 'research',
    'customer_service', 'strategy', 'administration', 'personal', 'other'
]

# Approval requirements
APPROVAL_REQUIREMENTS = [
    'none', 'single_approver', 'multiple_approvers', 'consensus', 'hierarchical'
]

# Document types
DOCUMENT_TYPES = [
    'business_plan', 'pitch_deck', 'financial_report', 'legal_document', 'other'
]

# Document status
DOCUMENT_STATUS = [
    'draft', 'pending_review', 'approved', 'rejected', 'archived'
]

# Document categories
DOCUMENT_CATEGORIES = [
    'financial', 'legal', 'operational', 'strategic', 'administrative'
]

# Access levels
ACCESS_LEVELS = [
    'public', 'private', 'restricted', 'confidential'
]

# File storage providers
FILE_STORAGE_PROVIDERS = [
    'local', 'aws_s3', 'google_cloud', 'azure_blob'
]

# Document formats
DOCUMENT_FORMATS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv'
]

# Approval status
APPROVAL_STATUS = [
    'pending', 'approved', 'rejected', 'requires_changes'
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
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
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

# Mentorship status
MENTORSHIP_STATUS = [
    'requested', 'pending_approval', 'active', 'paused', 'completed', 'cancelled', 'expired'
]

# Session types
SESSION_TYPES = [
    'one_on_one', 'group', 'workshop', 'review', 'goal_setting', 'progress_check', 
    'pitch_practice', 'strategic_planning', 'problem_solving', 'networking', 
    'skills_development', 'feedback_session'
]

# Session status
SESSION_STATUS = [
    'scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show', 'rescheduled'
]

# Feedback ratings
FEEDBACK_RATINGS = [
    'excellent', 'very_good', 'good', 'fair', 'poor'
]

# Expertise areas
EXPERTISE_AREAS = [
    'business_strategy', 'marketing', 'finance', 'technology', 'leadership', 
    'operations', 'legal', 'human_resources', 'product_development', 'sales'
]

# Mentorship goals
MENTORSHIP_GOALS = [
    'skill_development', 'career_guidance', 'business_growth', 'networking', 
    'problem_solving', 'strategic_planning', 'personal_development'
]

# Communication preferences
COMMUNICATION_PREFERENCES = [
    'email', 'video_call', 'phone_call', 'in_person', 'chat', 'hybrid'
]

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

# Reminder intervals (corregido - se eliminó el stub vacío)
REMINDER_INTERVALS = [
    '5_minutes', '15_minutes', '30_minutes', '1_hour', '2_hours', '1_day', '1_week'
]


# Auto-generated comprehensive stubs - 1 items
EMAIL_PRIORITIES = ['low', 'medium', 'high']

# USER_STATUS - nueva constante sin duplicar
USER_STATUS = ["active", "inactive", "pending", "suspended", "banned"]
# Business limits and constraints
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "gif"]

# Additional constants for complete functionality
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp'
LOG_FOLDER = 'logs'

# File type mappings
MIME_TYPES = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'txt': 'text/plain',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif'
}

# Status mappings
STATUS_MAPPINGS = {
    'active': 'Activo',
    'inactive': 'Inactivo',
    'pending': 'Pendiente',
    'suspended': 'Suspendido',
    'banned': 'Prohibido'
}

# Email templates configuration
EMAIL_TEMPLATES = {
    'welcome': 'templates/email/welcome.html',
    'verification': 'templates/email/verification.html',
    'password_reset': 'templates/email/password_reset.html',
    'meeting_reminder': 'templates/email/meeting_reminder.html',
    'project_update': 'templates/email/project_update.html',
    'invitation': 'templates/email/invitation.html',
    'notification': 'templates/email/notification.html'
}

# Email providers configuration
EMAIL_PROVIDERS = {
    'smtp': 'SMTP',
    'sendgrid': 'SendGrid',
    'mailgun': 'Mailgun',
    'ses': 'Amazon SES'
}

# Notification priorities
NOTIFICATION_PRIORITIES = ['low', 'medium', 'high', 'urgent']

# Mentorship status
MENTORSHIP_STATUS = [
    'requested', 'pending_approval', 'active', 'paused', 'completed', 'cancelled', 'expired'
]

# Session types
SESSION_TYPES = [
    'one_on_one', 'group', 'workshop', 'webinar', 'review', 'goal_setting',
    'progress_check', 'pitch_practice', 'strategic_planning', 'problem_solving',
    'networking', 'skills_development', 'feedback_session'
]

# Session status
SESSION_STATUS = [
    'scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show', 'rescheduled'
]

# Feedback ratings for mentorship sessions and evaluations
FEEDBACK_RATINGS = ['excellent', 'very_good', 'good', 'fair', 'poor']

# Areas of expertise for mentors in the entrepreneurship ecosystem
EXPERTISE_AREAS = [
    'business_strategy', 'marketing_sales', 'product_development', 'technology',
    'finance_accounting', 'legal_compliance', 'operations', 'human_resources',
    'leadership_management', 'fundraising_investment', 'market_research',
    'customer_development', 'digital_transformation', 'international_expansion',
    'sustainability', 'social_impact', 'innovation', 'data_analytics',
    'supply_chain', 'partnerships_alliances', 'intellectual_property',
    'risk_management', 'scaling_growth', 'exit_strategies'
]

# Common mentorship goals in entrepreneurship
MENTORSHIP_GOALS = [
    'business_plan_development', 'market_validation', 'product_launch',
    'revenue_growth', 'team_building', 'fundraising_preparation',
    'strategic_planning', 'operational_efficiency', 'leadership_development',
    'networking_expansion', 'digital_marketing', 'customer_acquisition',
    'financial_management', 'competitive_analysis', 'scaling_preparation',
    'exit_strategy', 'innovation_development', 'partnership_building',
    'international_expansion', 'sustainability_integration',
    'technology_adoption', 'regulatory_compliance'
]

# Communication preferences for mentorship relationships
COMMUNICATION_PREFERENCES = [
    'email', 'video_call', 'phone_call', 'in_person', 'chat_messaging',
    'collaborative_platforms', 'project_management_tools', 'social_media',
    'mobile_apps', 'scheduled_meetings', 'ad_hoc_communication',
    'group_sessions', 'one_on_one_sessions'
]

# Mentorship session frequency options
MENTORSHIP_FREQUENCY = [
    'weekly', 'bi_weekly', 'monthly', 'quarterly', 'as_needed'
]

# Mentorship evaluation types
MENTORSHIP_EVALUATION_TYPES = [
    'periodic', 'mid_term', 'final', 'initial', 'quarterly', 'annual'
]

# Mentorship evaluator types
MENTORSHIP_EVALUATOR_TYPES = [
    'mentor', 'mentee', 'coordinator', 'mutual', 'peer', 'supervisor'
]

# File categories and storage constants
FILE_CATEGORIES = {
    'image': ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff'],
    'document': ['pdf', 'doc', 'docx', 'odt', 'rtf', 'txt'],
    'spreadsheet': ['xls', 'xlsx', 'ods', 'csv'],
    'presentation': ['ppt', 'pptx', 'odp'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
    'audio': ['mp3', 'wav', 'ogg', 'aac'],
    'code': ['py', 'js', 'html', 'css', 'java', 'c', 'cpp', 'json', 'xml'],
}

STORAGE_PROVIDERS = ['local', 'aws_s3', 'google_cloud', 'azure_blob', 'ftp', 'sftp']

MAX_FILE_SIZES = {
    'image': 10 * 1024 * 1024,  # 10MB
    'document': 50 * 1024 * 1024,  # 50MB
    'video': 500 * 1024 * 1024,  # 500MB
    'audio': 100 * 1024 * 1024,  # 100MB
    'archive': 200 * 1024 * 1024,  # 200MB
    'default': 25 * 1024 * 1024,  # 25MB
}
