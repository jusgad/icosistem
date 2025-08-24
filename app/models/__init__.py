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
# Additional model stubs
class Admin:
    """Admin model stub."""
    pass

class Organization:
    """Organization model stub."""
    pass

class Program:
    """Program model stub."""
    pass

class Activity:
    """Activity model stub."""  
    pass

# Additional critical model stubs
class Entrepreneur:
    """Entrepreneur model stub."""
    pass

class Ally:
    """Ally model stub."""
    pass

class Client:
    """Client model stub."""
    pass

class Project:
    """Project model stub."""
    pass

class Meeting:
    """Meeting model stub."""
    pass

class Task:
    """Task model stub."""
    pass

class Document:
    """Document model stub."""
    pass

class Notification:
    """Notification model stub."""
    pass

class Message:
    """Message model stub."""
    pass

class ActivityLog:
    """ActivityLog model stub."""
    pass

class Milestone:
    """Milestone model stub."""
    pass

class ProjectMilestone:
    """ProjectMilestone model stub."""
    pass

class ProgramMilestone:
    """ProgramMilestone model stub."""
    pass

class Application:
    """Application model stub."""
    pass

class Availability:
    """Availability model stub."""
    pass

class Evaluation:
    """Evaluation model stub."""
    pass

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
__all__.extend(['Admin', 'Organization', 'Program', 'Activity', 'Entrepreneur', 
               'Ally', 'Client', 'Project', 'Meeting', 'Task', 'Document', 
               'Notification', 'Message', 'ActivityLog', 'Milestone', 'ProjectMilestone',
               'ProgramMilestone', 'Application', 'Availability', 'Evaluation', 'EmailTemplate', 'EmailCampaign',
               'EmailLog', 'EmailTracking', 'EmailBounce', 'EmailSuppression'])
