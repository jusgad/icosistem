"""
Inicialización de modelos para el ecosistema de emprendimiento.
"""

import logging

# Configurar logger para modelos
models_logger = logging.getLogger('ecosistema.models')

# ====================================
# IMPORTACIÓN DE MODELOS PRINCIPALES
# ====================================

# Usuario principal
try:
    from .user import User, UserType, UserStatus
    models_logger.info("✅ User model loaded successfully")
except Exception as e:
    models_logger.error(f"❌ Error loading User model: {e}")
    # Importar solo las clases enum básicas si hay error
    from enum import Enum
    
    class UserType(str, Enum):
        ADMIN = 'admin'
        ENTREPRENEUR = 'entrepreneur'
        ALLY = 'ally'
        CLIENT = 'client'
    
    class UserStatus(str, Enum):
        ACTIVE = 'active'
        INACTIVE = 'inactive'
        PENDING = 'pending'
        SUSPENDED = 'suspended'
        BANNED = 'banned'
    
    User = None  # Se cargará más tarde

# Otros modelos principales (importación opcional)
try:
    from .base import BaseModel, CompleteBaseModel
    models_logger.info("✅ Base models loaded successfully")
except Exception as e:
    models_logger.warning(f"⚠️  Base models not available: {e}")
    BaseModel = CompleteBaseModel = None

try:
    from .mixins import SearchableMixin, CacheableMixin
    models_logger.info("✅ Model mixins loaded successfully")
except Exception as e:
    models_logger.warning(f"⚠️  Model mixins not available: {e}")
    SearchableMixin = CacheableMixin = None

# Exportaciones principales
__all__ = ['User', 'UserType', 'UserStatus', 'BaseModel', 'CompleteBaseModel', 
           'SearchableMixin', 'CacheableMixin']
# Importar modelos reales (con manejo de errores)
try:
    from .admin import Admin
    models_logger.info("✅ Admin model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Admin model: {e}")
    Admin = None

try:
    from .organization import Organization
    models_logger.info("✅ Organization model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Organization model: {e}")
    Organization = None

try:
    from .program import Program
    models_logger.info("✅ Program model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Program model: {e}")
    Program = None

try:
    from .activity_log import ActivityLog
    models_logger.info("✅ ActivityLog model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading ActivityLog model: {e}")
    ActivityLog = None

try:
    from .entrepreneur import Entrepreneur
    models_logger.info("✅ Entrepreneur model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Entrepreneur model: {e}")
    Entrepreneur = None

try:
    from .ally import Ally
    models_logger.info("✅ Ally model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Ally model: {e}")
    Ally = None

try:
    from .client import Client
    models_logger.info("✅ Client model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Client model: {e}")
    Client = None

try:
    from .project import Project
    models_logger.info("✅ Project model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Project model: {e}")
    Project = None

try:
    from .meeting import Meeting
    models_logger.info("✅ Meeting model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Meeting model: {e}")
    Meeting = None

try:
    from .task import Task
    models_logger.info("✅ Task model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Task model: {e}")
    Task = None

try:
    from .document import Document
    models_logger.info("✅ Document model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Document model: {e}")
    Document = None

try:
    from .notification import Notification
    models_logger.info("✅ Notification model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Notification model: {e}")
    Notification = None

try:
    from .message import Message
    models_logger.info("✅ Message model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Message model: {e}")
    Message = None

try:
    from .milestone import Milestone
    models_logger.info("✅ Milestone model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Milestone model: {e}")
    Milestone = None

try:
    from .application import Application
    models_logger.info("✅ Application model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Application model: {e}")
    Application = None

try:
    from .availability import Availability
    models_logger.info("✅ Availability model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Availability model: {e}")
    Availability = None

try:
    from .evaluation import Evaluation
    models_logger.info("✅ Evaluation model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading Evaluation model: {e}")
    Evaluation = None

try:
    from .mentorship import MentorshipRelationship
    models_logger.info("✅ MentorshipRelationship model loaded")
except Exception as e:
    models_logger.error(f"❌ Error loading MentorshipRelationship model: {e}")
    MentorshipRelationship = None

# Email models
try:
    from .email_template import EmailTemplate
    from .email_campaign import EmailCampaign
    from .email_log import EmailLog
    from .email_tracking import EmailTracking
    from .email_bounce import EmailBounce
    from .email_suppression import EmailSuppression
    models_logger.info("✅ Email models loaded successfully")
except Exception as e:
    models_logger.error(f"❌ Error loading Email models: {e}")
    EmailTemplate = EmailCampaign = EmailLog = EmailTracking = EmailBounce = EmailSuppression = None

# Export all models
__all__.extend(['Admin', 'Organization', 'Program', 'ActivityLog', 'Entrepreneur', 
               'Ally', 'Client', 'Project', 'Meeting', 'Task', 'Document', 
               'Notification', 'Message', 'Milestone', 'Application', 'Availability', 
               'Evaluation', 'MentorshipRelationship', 'EmailTemplate', 'EmailCampaign',
               'EmailLog', 'EmailTracking', 'EmailBounce', 'EmailSuppression'])
