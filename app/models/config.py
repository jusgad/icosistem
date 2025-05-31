"""
Config Model - Sistema de configuración dinámica
===============================================

Este módulo define los modelos para gestionar configuraciones del sistema
de forma dinámica, permitiendo cambios en tiempo real sin redeployment.

Funcionalidades:
- Configuraciones por organización y globales
- Tipos de datos tipados y validados
- Configuraciones sensibles encriptadas
- Versionado y auditoría de cambios
- Cache automático para performance
- Configuraciones por ambiente
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Union, List
import json
import secrets
from decimal import Decimal

from sqlalchemy import Index, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from cryptography.fernet import Fernet

from app.extensions import db
from app.models.base import BaseModel
from app.models.mixins import TimestampMixin, SoftDeleteMixin
from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data


class ConfigScope(Enum):
    """Alcance de las configuraciones"""
    GLOBAL = "global"           # Configuración global del sistema
    ORGANIZATION = "organization"  # Por organización
    PROGRAM = "program"         # Por programa específico
    USER = "user"              # Por usuario específico
    ENVIRONMENT = "environment" # Por ambiente (dev, prod, etc.)


class ConfigType(Enum):
    """Tipos de configuración"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    ARRAY = "array"
    ENCRYPTED = "encrypted"    # Para datos sensibles
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"


class ConfigCategory(Enum):
    """Categorías de configuración"""
    SYSTEM = "system"
    AUTHENTICATION = "authentication"
    NOTIFICATION = "notification"
    INTEGRATION = "integration"
    BUSINESS_RULES = "business_rules"
    UI_SETTINGS = "ui_settings"
    SECURITY = "security"
    ANALYTICS = "analytics"
    EMAIL = "email"
    SMS = "sms"
    PAYMENT = "payment"
    STORAGE = "storage"
    API = "api"
    FEATURE_FLAGS = "feature_flags"


class ConfigPriority(Enum):
    """Prioridad de configuraciones (para resolución de conflictos)"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SystemConfig(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Modelo principal para configuraciones del sistema
    
    Attributes:
        id: ID único de la configuración
        key: Clave única de la configuración
        value: Valor de la configuración
        config_type: Tipo de dato de la configuración
        category: Categoría de la configuración
        scope: Alcance de la configuración
        priority: Prioridad para resolución de conflictos
        description: Descripción de la configuración
        is_sensitive: Si contiene datos sensibles
        is_required: Si es requerida para el funcionamiento
        is_editable: Si puede ser editada por usuarios
        default_value: Valor por defecto
        validation_rules: Reglas de validación (JSON)
        organization_id: ID de organización (si aplica)
        program_id: ID de programa (si aplica)
        user_id: ID de usuario (si aplica)
        environment: Ambiente específico
        version: Versión de la configuración
        last_modified_by: Último usuario que modificó
    """
    
    __tablename__ = 'system_configs'
    
    # Campos principales
    key = db.Column(
        db.String(200),
        nullable=False,
        index=True
    )
    
    value = db.Column(
        db.Text,
        nullable=True
    )
    
    config_type = db.Column(
        db.Enum(ConfigType),
        nullable=False,
        default=ConfigType.STRING
    )
    
    category = db.Column(
        db.Enum(ConfigCategory),
        nullable=False,
        index=True
    )
    
    scope = db.Column(
        db.Enum(ConfigScope),
        nullable=False,
        default=ConfigScope.GLOBAL,
        index=True
    )
    
    priority = db.Column(
        db.Enum(ConfigPriority),
        nullable=False,
        default=ConfigPriority.MEDIUM
    )
    
    description = db.Column(
        db.Text,
        nullable=True
    )
    
    # Propiedades de configuración
    is_sensitive = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    
    is_required = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    
    is_editable = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True
    )
    
    # Valores y validación
    default_value = db.Column(
        db.Text,
        nullable=True
    )
    
    validation_rules = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Referencias de alcance
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    program_id = db.Column(
        db.Integer,
        db.ForeignKey('programs.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    environment = db.Column(
        db.String(50),
        nullable=True,
        index=True
    )
    
    # Versionado y auditoría
    version = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )
    
    last_modified_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Metadatos adicionales
    metadata = db.Column(
        JSONB,
        nullable=True,
        default=dict
    )
    
    # Relaciones
    organization = db.relationship('Organization', foreign_keys=[organization_id])
    program = db.relationship('Program', foreign_keys=[program_id])
    user = db.relationship('User', foreign_keys=[user_id])
    modifier = db.relationship('User', foreign_keys=[last_modified_by])
    
    # Índices compuestos
    __table_args__ = (
        Index('ix_config_key_scope', 'key', 'scope'),
        Index('ix_config_org_key', 'organization_id', 'key'),
        Index('ix_config_scope_active', 'scope', 'is_active'),
        Index('ix_config_category_active', 'category', 'is_active'),
        # Constraint de unicidad por contexto
        db.UniqueConstraint('key', 'scope', 'organization_id', 'program_id', 'user_id', 'environment', 
                           name='uq_config_context'),
        {'extend_existing': True}
    )
    
    def __repr__(self):
        return f"<SystemConfig {self.key}: {self.scope.value}>"
    
    @validates('key')
    def validate_key(self, key, value):
        """Valida formato de la clave"""
        if not value or len(value.strip()) == 0:
            raise ValueError("La clave no puede estar vacía")
        
        # Normalizar clave (minúsculas, guiones bajos)
        normalized = value.lower().replace('-', '_').replace(' ', '_')
        
        # Validar formato
        import re
        if not re.match(r'^[a-z0-9_]+$', normalized):
            raise ValueError("La clave solo puede contener letras, números y guiones bajos")
        
        return normalized
    
    @validates('value')
    def validate_value(self, key, value):
        """Valida el valor según el tipo"""
        if value is None:
            return value
            
        # Aplicar validaciones según el tipo
        if self.config_type == ConfigType.INTEGER:
            try:
                int(value)
            except (ValueError, TypeError):
                raise ValueError("El valor debe ser un entero válido")
                
        elif self.config_type == ConfigType.FLOAT:
            try:
                float(value)
            except (ValueError, TypeError):
                raise ValueError("El valor debe ser un número decimal válido")
                
        elif self.config_type == ConfigType.BOOLEAN:
            if value.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                raise ValueError("El valor debe ser un booleano válido")
                
        elif self.config_type == ConfigType.JSON:
            try:
                json.loads(value) if isinstance(value, str) else value
            except (json.JSONDecodeError, TypeError):
                raise ValueError("El valor debe ser JSON válido")
                
        elif self.config_type == ConfigType.EMAIL:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                raise ValueError("El valor debe ser un email válido")
                
        elif self.config_type == ConfigType.URL:
            import re
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            if not re.match(url_pattern, value, re.IGNORECASE):
                raise ValueError("El valor debe ser una URL válida")
        
        return value
    
    @hybrid_property
    def parsed_value(self):
        """Obtiene el valor parseado según su tipo"""
        if self.value is None:
            return self._get_default_value()
        
        # Desencriptar si es sensible
        raw_value = self.value
        if self.is_sensitive and raw_value:
            try:
                raw_value = decrypt_sensitive_data(raw_value)
            except Exception:
                # Si falla la desencriptación, usar valor por defecto
                return self._get_default_value()
        
        # Parsear según tipo
        if self.config_type == ConfigType.INTEGER:
            return int(raw_value)
        elif self.config_type == ConfigType.FLOAT:
            return float(raw_value)
        elif self.config_type == ConfigType.DECIMAL:
            return Decimal(raw_value)
        elif self.config_type == ConfigType.BOOLEAN:
            return raw_value.lower() in ('true', '1', 'yes', 'on')
        elif self.config_type == ConfigType.JSON:
            return json.loads(raw_value) if isinstance(raw_value, str) else raw_value
        elif self.config_type == ConfigType.ARRAY:
            return json.loads(raw_value) if isinstance(raw_value, str) else raw_value
        elif self.config_type == ConfigType.DATE:
            from datetime import datetime
            return datetime.fromisoformat(raw_value).date()
        elif self.config_type == ConfigType.DATETIME:
            from datetime import datetime
            return datetime.fromisoformat(raw_value)
        else:
            return raw_value
    
    def _get_default_value(self):
        """Obtiene el valor por defecto parseado"""
        if not self.default_value:
            return None
            
        # Crear instancia temporal para parsear el valor por defecto
        temp_config = SystemConfig(
            config_type=self.config_type,
            value=self.default_value,
            is_sensitive=False  # Los valores por defecto no son sensibles
        )
        return temp_config.parsed_value
    
    def set_value(self, value, encrypt_if_sensitive=True):
        """
        Establece el valor, encriptando si es necesario
        
        Args:
            value: Nuevo valor
            encrypt_if_sensitive: Si encriptar valores sensibles
        """
        # Convertir a string si es necesario
        if self.config_type in (ConfigType.JSON, ConfigType.ARRAY):
            if not isinstance(value, str):
                value = json.dumps(value)
        else:
            value = str(value)
        
        # Encriptar si es sensible
        if self.is_sensitive and encrypt_if_sensitive and value:
            value = encrypt_sensitive_data(value)
        
        # Incrementar versión
        self.version += 1
        self.value = value
    
    def to_dict(self, include_sensitive=False):
        """Convierte la configuración a diccionario"""
        data = {
            'id': self.id,
            'key': self.key,
            'config_type': self.config_type.value,
            'category': self.category.value,
            'scope': self.scope.value,
            'priority': self.priority.value,
            'description': self.description,
            'is_required': self.is_required,
            'is_editable': self.is_editable,
            'is_active': self.is_active,
            'organization_id': self.organization_id,
            'program_id': self.program_id,
            'user_id': self.user_id,
            'environment': self.environment,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Incluir valor solo si no es sensible o se permite explícitamente
        if not self.is_sensitive or include_sensitive:
            data['value'] = self.parsed_value
        else:
            data['value'] = '***HIDDEN***'
        
        return data


class ConfigHistory(BaseModel, TimestampMixin):
    """
    Historial de cambios en configuraciones
    
    Attributes:
        id: ID único del registro de historial
        config_id: ID de la configuración
        old_value: Valor anterior
        new_value: Nuevo valor
        changed_by: Usuario que realizó el cambio
        change_reason: Razón del cambio
        change_type: Tipo de cambio (create, update, delete)
    """
    
    __tablename__ = 'config_history'
    
    config_id = db.Column(
        db.Integer,
        db.ForeignKey('system_configs.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    old_value = db.Column(
        db.Text,
        nullable=True
    )
    
    new_value = db.Column(
        db.Text,
        nullable=True
    )
    
    changed_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    
    change_reason = db.Column(
        db.Text,
        nullable=True
    )
    
    change_type = db.Column(
        db.String(20),
        nullable=False,
        default='update'
    )
    
    # Relaciones
    config = db.relationship('SystemConfig', backref='history')
    user = db.relationship('User', backref='config_changes')


class ConfigManager:
    """Gestor de configuraciones del sistema"""
    
    _cache = {}
    _cache_ttl = {}
    
    @classmethod
    def get(
        cls,
        key: str,
        default=None,
        organization_id: Optional[int] = None,
        program_id: Optional[int] = None,
        user_id: Optional[int] = None,
        environment: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Obtiene una configuración con resolución de contexto
        
        Args:
            key: Clave de la configuración
            default: Valor por defecto si no existe
            organization_id: ID de organización
            program_id: ID de programa
            user_id: ID de usuario
            environment: Ambiente específico
            use_cache: Si usar caché
            
        Returns:
            Valor de la configuración parseado
        """
        # Generar clave de caché
        cache_key = f"{key}:{organization_id}:{program_id}:{user_id}:{environment}"
        
        # Verificar caché
        if use_cache and cache_key in cls._cache:
            cache_time = cls._cache_ttl.get(cache_key, 0)
            if datetime.utcnow().timestamp() - cache_time < 300:  # 5 minutos TTL
                return cls._cache[cache_key]
        
        # Buscar configuración con prioridad de contexto
        configs = cls._get_configs_by_priority(
            key, organization_id, program_id, user_id, environment
        )
        
        if not configs:
            return default
        
        # Tomar la configuración de mayor prioridad
        config = configs[0]
        value = config.parsed_value
        
        # Guardar en caché
        if use_cache:
            cls._cache[cache_key] = value
            cls._cache_ttl[cache_key] = datetime.utcnow().timestamp()
        
        return value
    
    @classmethod
    def set(
        cls,
        key: str,
        value: Any,
        config_type: ConfigType = ConfigType.STRING,
        category: ConfigCategory = ConfigCategory.SYSTEM,
        scope: ConfigScope = ConfigScope.GLOBAL,
        organization_id: Optional[int] = None,
        program_id: Optional[int] = None,
        user_id: Optional[int] = None,
        environment: Optional[str] = None,
        description: Optional[str] = None,
        is_sensitive: bool = False,
        changed_by: Optional[int] = None,
        change_reason: Optional[str] = None
    ) -> SystemConfig:
        """
        Establece una configuración
        
        Args:
            key: Clave de la configuración
            value: Valor a establecer
            config_type: Tipo de configuración
            category: Categoría
            scope: Alcance
            organization_id: ID de organización
            program_id: ID de programa
            user_id: ID de usuario
            environment: Ambiente
            description: Descripción
            is_sensitive: Si es sensible
            changed_by: Usuario que hace el cambio
            change_reason: Razón del cambio
            
        Returns:
            Instancia de SystemConfig
        """
        # Buscar configuración existente
        existing = SystemConfig.query.filter_by(
            key=key,
            scope=scope,
            organization_id=organization_id,
            program_id=program_id,
            user_id=user_id,
            environment=environment
        ).first()
        
        if existing:
            # Registrar cambio en historial
            old_value = existing.value
            cls._record_change(existing.id, old_value, str(value), changed_by, change_reason, 'update')
            
            # Actualizar configuración existente
            existing.set_value(value)
            existing.last_modified_by = changed_by
            config = existing
        else:
            # Crear nueva configuración
            config = SystemConfig(
                key=key,
                config_type=config_type,
                category=category,
                scope=scope,
                organization_id=organization_id,
                program_id=program_id,
                user_id=user_id,
                environment=environment,
                description=description,
                is_sensitive=is_sensitive,
                last_modified_by=changed_by
            )
            config.set_value(value)
            db.session.add(config)
            
            # Registrar creación en historial
            db.session.flush()  # Para obtener el ID
            cls._record_change(config.id, None, str(value), changed_by, change_reason, 'create')
        
        db.session.commit()
        
        # Limpiar caché relacionada
        cls._clear_cache_for_key(key)
        
        return config
    
    @classmethod
    def delete(
        cls,
        key: str,
        organization_id: Optional[int] = None,
        program_id: Optional[int] = None,
        user_id: Optional[int] = None,
        environment: Optional[str] = None,
        changed_by: Optional[int] = None,
        change_reason: Optional[str] = None
    ) -> bool:
        """
        Elimina una configuración
        
        Returns:
            True si se eliminó, False si no existía
        """
        config = SystemConfig.query.filter_by(
            key=key,
            organization_id=organization_id,
            program_id=program_id,
            user_id=user_id,
            environment=environment
        ).first()
        
        if not config:
            return False
        
        # Registrar eliminación en historial
        cls._record_change(config.id, config.value, None, changed_by, change_reason, 'delete')
        
        # Eliminación lógica
        config.soft_delete()
        db.session.commit()
        
        # Limpiar caché
        cls._clear_cache_for_key(key)
        
        return True
    
    @classmethod
    def get_by_category(
        cls,
        category: ConfigCategory,
        organization_id: Optional[int] = None,
        include_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """Obtiene todas las configuraciones de una categoría"""
        query = SystemConfig.query.filter(
            SystemConfig.category == category,
            SystemConfig.is_active == True
        )
        
        if organization_id:
            query = query.filter(
                or_(
                    SystemConfig.organization_id == organization_id,
                    SystemConfig.scope == ConfigScope.GLOBAL
                )
            )
        
        configs = query.all()
        return [config.to_dict(include_sensitive=include_sensitive) for config in configs]
    
    @classmethod
    def _get_configs_by_priority(
        cls,
        key: str,
        organization_id: Optional[int] = None,
        program_id: Optional[int] = None,
        user_id: Optional[int] = None,
        environment: Optional[str] = None
    ) -> List[SystemConfig]:
        """Obtiene configuraciones ordenadas por prioridad de contexto"""
        query = SystemConfig.query.filter(
            SystemConfig.key == key,
            SystemConfig.is_active == True
        )
        
        # Construir condiciones de contexto por prioridad
        conditions = []
        
        # 1. Usuario específico (mayor prioridad)
        if user_id:
            conditions.append(
                and_(
                    SystemConfig.scope == ConfigScope.USER,
                    SystemConfig.user_id == user_id
                )
            )
        
        # 2. Programa específico
        if program_id:
            conditions.append(
                and_(
                    SystemConfig.scope == ConfigScope.PROGRAM,
                    SystemConfig.program_id == program_id
                )
            )
        
        # 3. Organización específica
        if organization_id:
            conditions.append(
                and_(
                    SystemConfig.scope == ConfigScope.ORGANIZATION,
                    SystemConfig.organization_id == organization_id
                )
            )
        
        # 4. Ambiente específico
        if environment:
            conditions.append(
                and_(
                    SystemConfig.scope == ConfigScope.ENVIRONMENT,
                    SystemConfig.environment == environment
                )
            )
        
        # 5. Global (menor prioridad)
        conditions.append(SystemConfig.scope == ConfigScope.GLOBAL)
        
        # Aplicar condiciones con OR
        if conditions:
            query = query.filter(or_(*conditions))
        
        # Ordenar por prioridad de configuración y contexto
        return query.order_by(
            SystemConfig.priority.desc(),
            case(
                (SystemConfig.scope == ConfigScope.USER, 1),
                (SystemConfig.scope == ConfigScope.PROGRAM, 2),
                (SystemConfig.scope == ConfigScope.ORGANIZATION, 3),
                (SystemConfig.scope == ConfigScope.ENVIRONMENT, 4),
                (SystemConfig.scope == ConfigScope.GLOBAL, 5),
                else_=6
            )
        ).all()
    
    @classmethod
    def _record_change(
        cls,
        config_id: int,
        old_value: Optional[str],
        new_value: Optional[str],
        changed_by: Optional[int],
        change_reason: Optional[str],
        change_type: str
    ):
        """Registra un cambio en el historial"""
        history = ConfigHistory(
            config_id=config_id,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            change_reason=change_reason,
            change_type=change_type
        )
        db.session.add(history)
    
    @classmethod
    def _clear_cache_for_key(cls, key: str):
        """Limpia el caché para una clave específica"""
        keys_to_remove = [k for k in cls._cache.keys() if k.startswith(f"{key}:")]
        for k in keys_to_remove:
            cls._cache.pop(k, None)
            cls._cache_ttl.pop(k, None)
    
    @classmethod
    def clear_cache(cls):
        """Limpia todo el caché"""
        cls._cache.clear()
        cls._cache_ttl.clear()


# Event listeners para limpiar caché automáticamente
@event.listens_for(SystemConfig, 'after_update')
@event.listens_for(SystemConfig, 'after_insert')
@event.listens_for(SystemConfig, 'after_delete')
def clear_config_cache(mapper, connection, target):
    """Limpia caché cuando se modifica una configuración"""
    ConfigManager._clear_cache_for_key(target.key)


# Configuraciones predeterminadas del sistema
DEFAULT_CONFIGS = {
    # Sistema
    'system_name': {
        'value': 'Ecosistema de Emprendimiento',
        'type': ConfigType.STRING,
        'category': ConfigCategory.SYSTEM,
        'description': 'Nombre del sistema'
    },
    'system_version': {
        'value': '1.0.0',
        'type': ConfigType.STRING,
        'category': ConfigCategory.SYSTEM,
        'description': 'Versión del sistema'
    },
    'maintenance_mode': {
        'value': 'false',
        'type': ConfigType.BOOLEAN,
        'category': ConfigCategory.SYSTEM,
        'description': 'Modo de mantenimiento'
    },
    
    # Autenticación
    'password_min_length': {
        'value': '8',
        'type': ConfigType.INTEGER,
        'category': ConfigCategory.AUTHENTICATION,
        'description': 'Longitud mínima de contraseña'
    },
    'session_timeout': {
        'value': '3600',
        'type': ConfigType.INTEGER,
        'category': ConfigCategory.AUTHENTICATION,
        'description': 'Timeout de sesión en segundos'
    },
    'max_login_attempts': {
        'value': '5',
        'type': ConfigType.INTEGER,
        'category': ConfigCategory.AUTHENTICATION,
        'description': 'Máximo intentos de login'
    },
    
    # Notificaciones
    'email_notifications_enabled': {
        'value': 'true',
        'type': ConfigType.BOOLEAN,
        'category': ConfigCategory.NOTIFICATION,
        'description': 'Notificaciones por email habilitadas'
    },
    'sms_notifications_enabled': {
        'value': 'false',
        'type': ConfigType.BOOLEAN,
        'category': ConfigCategory.NOTIFICATION,
        'description': 'Notificaciones por SMS habilitadas'
    },
    
    # Reglas de negocio
    'max_projects_per_entrepreneur': {
        'value': '3',
        'type': ConfigType.INTEGER,
        'category': ConfigCategory.BUSINESS_RULES,
        'description': 'Máximo proyectos por emprendedor'
    },
    'mentorship_session_duration': {
        'value': '60',
        'type': ConfigType.INTEGER,
        'category': ConfigCategory.BUSINESS_RULES,
        'description': 'Duración sesión mentoría (minutos)'
    }
}


def initialize_default_configs():
    """Inicializa configuraciones predeterminadas"""
    for key, config_data in DEFAULT_CONFIGS.items():
        existing = SystemConfig.query.filter_by(
            key=key,
            scope=ConfigScope.GLOBAL
        ).first()
        
        if not existing:
            config = SystemConfig(
                key=key,
                value=config_data['value'],
                config_type=config_data['type'],
                category=config_data['category'],
                scope=ConfigScope.GLOBAL,
                description=config_data['description'],
                is_required=True,
                is_editable=config_data.get('editable', True)
            )
            db.session.add(config)
    
    db.session.commit()