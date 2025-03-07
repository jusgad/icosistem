from datetime import datetime
from app.extensions import db
from sqlalchemy.types import JSON

class Config(db.Model):
    """
    Model for storing application-wide configuration settings.
    Implements a key-value store with support for different value types
    and category-based organization.
    """
    __tablename__ = 'configs'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(JSON)
    value_type = db.Column(db.String(20), nullable=False)  # string, int, float, bool, json
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)  # If True, visible to all users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Categorías predefinidas
    CATEGORY_GENERAL = 'general'
    CATEGORY_EMAIL = 'email'
    CATEGORY_SECURITY = 'security'
    CATEGORY_BILLING = 'billing'
    CATEGORY_FEATURES = 'features'
    CATEGORY_LIMITS = 'limits'
    CATEGORY_INTEGRATION = 'integration'

    @classmethod
    def get_value(cls, key, default=None):
        """
        Obtiene el valor de una configuración por su clave.
        """
        config = cls.query.filter_by(key=key).first()
        if config is None:
            return default
        return config.get_typed_value()

    @classmethod
    def set_value(cls, key, value, category=CATEGORY_GENERAL, description=None, 
                  is_public=False, created_by=None):
        """
        Establece o actualiza un valor de configuración.
        """
        config = cls.query.filter_by(key=key).first()
        
        if config is None:
            config = cls(
                key=key,
                category=category,
                description=description,
                is_public=is_public,
                created_by=created_by
            )
            db.session.add(config)

        config.set_value(value)
        db.session.commit()
        return config

    def set_value(self, value):
        """
        Establece el valor y determina automáticamente su tipo.
        """
        if isinstance(value, bool):
            self.value_type = 'bool'
        elif isinstance(value, int):
            self.value_type = 'int'
        elif isinstance(value, float):
            self.value_type = 'float'
        elif isinstance(value, (dict, list)):
            self.value_type = 'json'
        else:
            self.value_type = 'string'
            value = str(value)

        self.value = value

    def get_typed_value(self):
        """
        Retorna el valor convertido al tipo apropiado.
        """
        if self.value is None:
            return None

        try:
            if self.value_type == 'bool':
                return bool(self.value)
            elif self.value_type == 'int':
                return int(self.value)
            elif self.value_type == 'float':
                return float(self.value)
            elif self.value_type == 'json':
                return self.value  # JSON ya está deserializado por SQLAlchemy
            else:  # string
                return str(self.value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def get_all_public(cls):
        """
        Retorna todas las configuraciones públicas.
        """
        return cls.query.filter_by(is_public=True).all()

    @classmethod
    def get_by_category(cls, category):
        """
        Retorna todas las configuraciones de una categoría específica.
        """
        return cls.query.filter_by(category=category).all()

    @classmethod
    def initialize_defaults(cls):
        """
        Inicializa las configuraciones por defecto del sistema.
        """
        defaults = [
            # Configuraciones generales
            {
                'key': 'site_name',
                'value': 'Platform de Emprendimiento',
                'category': cls.CATEGORY_GENERAL,
                'description': 'Nombre del sitio',
                'is_public': True
            },
            # Límites del sistema
            {
                'key': 'max_entrepreneurs_per_ally',
                'value': 5,
                'category': cls.CATEGORY_LIMITS,
                'description': 'Número máximo de emprendedores por aliado',
                'is_public': False
            },
            # Configuraciones de correo
            {
                'key': 'email_sender_name',
                'value': 'Plataforma de Emprendimiento',
                'category': cls.CATEGORY_EMAIL,
                'description': 'Nombre del remitente para correos electrónicos',
                'is_public': False
            },
            # Características del sistema
            {
                'key': 'enable_chat',
                'value': True,
                'category': cls.CATEGORY_FEATURES,
                'description': 'Habilitar sistema de chat',
                'is_public': True
            },
            # Configuraciones de facturación
            {
                'key': 'currency',
                'value': 'USD',
                'category': cls.CATEGORY_BILLING,
                'description': 'Moneda predeterminada del sistema',
                'is_public': True
            }
        ]

        for config in defaults:
            if not cls.query.filter_by(key=config['key']).first():
                cls.set_value(
                    key=config['key'],
                    value=config['value'],
                    category=config['category'],
                    description=config['description'],
                    is_public=config['is_public']
                )

    def __repr__(self):
        return f'<Config {self.key}={self.value} ({self.value_type})>'