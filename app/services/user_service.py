"""
User Service Module

Servicio central para gestión de usuarios en el ecosistema de emprendimiento.
Maneja la lógica de negocio para todos los tipos de usuarios: Admin, Entrepreneur, Ally, Client.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Any, Union
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func, desc, asc
from flask import current_app, url_for
import secrets
import uuid

from app.extensions import db
from app.models.user import User
from app.models.admin import Admin
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.organization import Organization
from app.models.activity_log import ActivityLog
from app.core.exceptions import (
    ValidationError, 
    UserNotFoundError, 
    DuplicateUserError,
    AuthenticationError,
    PermissionError,
    ServiceError
)
from app.core.constants import (
    USER_STATUS, 
    USER_ROLES, 
    NOTIFICATION_TYPES,
    ACTIVITY_TYPES
)
from app.services.base import BaseService
from app.services.email import EmailService
from app.services.notification_service import NotificationService
from app.utils.validators import validate_email, validate_phone, validate_password
from app.utils.formatters import format_phone_number, sanitize_string
from app.utils.date_utils import get_local_timezone
from app.utils.crypto_utils import generate_secure_token, encrypt_sensitive_data

logger = logging.getLogger(__name__)


class UserService(BaseService):
    """
    Servicio principal para gestión de usuarios del ecosistema.
    
    Funcionalidades principales:
    - CRUD completo de usuarios
    - Autenticación y autorización
    - Gestión de roles y permisos
    - Activación/desactivación de cuentas
    - Recuperación de contraseñas
    - Búsquedas avanzadas y filtros
    - Integración con servicios externos
    - Logging y auditoría
    """

    def __init__(self):
        super().__init__()
        self.email_service = EmailService()
        self.notification_service = NotificationService()
        self.max_login_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
        self.lockout_duration = current_app.config.get('LOCKOUT_DURATION_MINUTES', 30)

    # ==================== MÉTODOS DE CREACIÓN ====================

    def create_user(self, user_data: dict[str, Any], user_type: str) -> Union[User, Admin, Entrepreneur, Ally, Client]:
        """
        Crea un nuevo usuario en el sistema.
        
        Args:
            user_data: Datos del usuario a crear
            user_type: Tipo de usuario (admin, entrepreneur, ally, client)
            
        Returns:
            Usuario creado
            
        Raises:
            ValidationError: Si los datos no son válidos
            DuplicateUserError: Si el usuario ya existe
        """
        try:
            # Validar datos básicos
            self._validate_user_data(user_data, is_creation=True)
            
            # Verificar si el usuario ya existe
            if self.get_user_by_email(user_data['email']):
                raise DuplicateUserError(f"Usuario con email {user_data['email']} ya existe")
            
            # Preparar datos del usuario
            prepared_data = self._prepare_user_data(user_data)
            
            # Crear usuario según el tipo
            user = self._create_user_by_type(prepared_data, user_type)
            
            # Guardar en base de datos
            db.session.add(user)
            db.session.commit()
            
            # Log de actividad
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.USER_CREATED,
                details=f"Usuario {user_type} creado: {user.email}"
            )
            
            # Enviar email de bienvenida
            self._send_welcome_email(user)
            
            # Notificación
            self.notification_service.create_notification(
                user_id=user.id,
                type=NOTIFICATION_TYPES.WELCOME,
                title="¡Bienvenido al ecosistema!",
                message=f"Tu cuenta como {user_type} ha sido creada exitosamente."
            )
            
            logger.info(f"Usuario creado exitosamente: {user.email} (Tipo: {user_type})")
            return user
            
        except ValidationError:
            db.session.rollback()
            raise
        except DuplicateUserError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando usuario: {str(e)}")
            raise ServiceError(f"Error interno creando usuario: {str(e)}")

    def _create_user_by_type(self, data: dict[str, Any], user_type: str) -> Union[Admin, Entrepreneur, Ally, Client]:
        """Crea usuario específico según el tipo."""
        user_classes = {
            'admin': Admin,
            'entrepreneur': Entrepreneur,
            'ally': Ally,
            'client': Client
        }
        
        if user_type not in user_classes:
            raise ValidationError(f"Tipo de usuario inválido: {user_type}")
        
        UserClass = user_classes[user_type]
        return UserClass(**data)

    # ==================== MÉTODOS DE AUTENTICACIÓN ====================

    def authenticate_user(self, email: str, password: str, remember_me: bool = False) -> tuple[User, str]:
        """
        Autentica un usuario con email y contraseña.
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
            remember_me: Si mantener la sesión activa
            
        Returns:
            Tupla con (usuario, token_sesion)
            
        Raises:
            AuthenticationError: Si las credenciales son inválidas
        """
        try:
            # Normalizar email
            email = email.lower().strip()
            
            # Buscar usuario
            user = self.get_user_by_email(email, include_inactive=True)
            if not user:
                logger.warning(f"Intento de login con email inexistente: {email}")
                raise AuthenticationError("Credenciales inválidas")
            
            # Verificar si la cuenta está bloqueada
            if user.is_locked:
                if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
                    remaining = user.locked_until - datetime.now(timezone.utc)
                    raise AuthenticationError(f"Cuenta bloqueada. Intenta en {remaining.seconds // 60} minutos")
                else:
                    # Desbloquear cuenta si el tiempo expiró
                    user.is_locked = False
                    user.locked_until = None
                    user.failed_login_attempts = 0
            
            # Verificar contraseña
            if not user.check_password(password):
                self._handle_failed_login(user)
                raise AuthenticationError("Credenciales inválidas")
            
            # Verificar si la cuenta está activa
            if not user.is_active:
                raise AuthenticationError("Cuenta inactiva. Contacta al administrador")
            
            # Login exitoso
            self._handle_successful_login(user, remember_me)
            
            # Generar token de sesión
            session_token = self._generate_session_token(user)
            
            logger.info(f"Login exitoso: {user.email}")
            return user, session_token
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Error en autenticación: {str(e)}")
            raise ServiceError(f"Error interno en autenticación: {str(e)}")

    def _handle_failed_login(self, user: User) -> None:
        """Maneja intentos fallidos de login."""
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.now(timezone.utc)
        
        if user.failed_login_attempts >= self.max_login_attempts:
            user.is_locked = True
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.lockout_duration)
            
            # Notificar al usuario
            self.notification_service.create_notification(
                user_id=user.id,
                type=NOTIFICATION_TYPES.SECURITY_ALERT,
                title="Cuenta bloqueada",
                message=f"Tu cuenta ha sido bloqueada por {self.lockout_duration} minutos debido a múltiples intentos fallidos"
            )
        
        db.session.commit()

    def _handle_successful_login(self, user: User, remember_me: bool) -> None:
        """Maneja login exitoso."""
        user.last_login = datetime.now(timezone.utc)
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.login_count += 1
        
        if remember_me:
            user.remember_token = generate_secure_token()
            user.remember_token_expires = datetime.now(timezone.utc) + timedelta(days=30)
        
        db.session.commit()
        
        # Log de actividad
        self._log_activity(
            user_id=user.id,
            activity_type=ACTIVITY_TYPES.USER_LOGIN,
            details=f"Login desde IP: {self._get_client_ip()}"
        )

    # ==================== MÉTODOS DE RECUPERACIÓN DE CONTRASEÑA ====================

    def request_password_reset(self, email: str) -> bool:
        """
        Solicita reseteo de contraseña.
        
        Args:
            email: Email del usuario
            
        Returns:
            True si se envió el email
        """
        try:
            user = self.get_user_by_email(email)
            if not user:
                # Por seguridad, no revelamos si el email existe
                logger.warning(f"Solicitud de reset para email inexistente: {email}")
                return True
            
            # Generar token de reset
            reset_token = generate_secure_token()
            user.reset_token = reset_token
            user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
            
            db.session.commit()
            
            # Enviar email
            reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
            self.email_service.send_password_reset_email(user, reset_url)
            
            # Log de actividad
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.PASSWORD_RESET_REQUESTED,
                details="Solicitud de reseteo de contraseña"
            )
            
            logger.info(f"Solicitud de reset de contraseña enviada: {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error en solicitud de reset: {str(e)}")
            return True  # Por seguridad, siempre retornamos True

    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Resetea la contraseña usando el token.
        
        Args:
            token: Token de reset
            new_password: Nueva contraseña
            
        Returns:
            True si se resetó exitosamente
            
        Raises:
            ValidationError: Si el token es inválido o la contraseña no cumple requisitos
        """
        try:
            # Validar nueva contraseña
            if not validate_password(new_password):
                raise ValidationError("La contraseña no cumple los requisitos de seguridad")
            
            # Buscar usuario por token
            user = User.query.filter_by(reset_token=token).first()
            if not user or not user.reset_token_expires or datetime.now(timezone.utc) > user.reset_token_expires:
                raise ValidationError("Token de reset inválido o expirado")
            
            # Actualizar contraseña
            user.password_hash = generate_password_hash(new_password)
            user.reset_token = None
            user.reset_token_expires = None
            user.password_changed_at = datetime.now(timezone.utc)
            
            # Reset de intentos fallidos
            user.failed_login_attempts = 0
            user.is_locked = False
            user.locked_until = None
            
            db.session.commit()
            
            # Notificación
            self.notification_service.create_notification(
                user_id=user.id,
                type=NOTIFICATION_TYPES.SECURITY_ALERT,
                title="Contraseña actualizada",
                message="Tu contraseña ha sido actualizada exitosamente"
            )
            
            # Log de actividad
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.PASSWORD_CHANGED,
                details="Contraseña cambiada via reset token"
            )
            
            logger.info(f"Contraseña reseteada exitosamente: {user.email}")
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error reseteando contraseña: {str(e)}")
            raise ServiceError(f"Error interno reseteando contraseña: {str(e)}")

    # ==================== MÉTODOS DE CONSULTA ====================

    def get_user_by_id(self, user_id: int, include_inactive: bool = False) -> Optional[User]:
        """
        Obtiene usuario por ID.
        
        Args:
            user_id: ID del usuario
            include_inactive: Si incluir usuarios inactivos
            
        Returns:
            Usuario encontrado o None
        """
        try:
            query = User.query.filter_by(id=user_id)
            
            if not include_inactive:
                query = query.filter_by(is_active=True)
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo usuario por ID {user_id}: {str(e)}")
            return None

    def get_user_by_email(self, email: str, include_inactive: bool = False) -> Optional[User]:
        """
        Obtiene usuario por email.
        
        Args:
            email: Email del usuario
            include_inactive: Si incluir usuarios inactivos
            
        Returns:
            Usuario encontrado o None
        """
        try:
            email = email.lower().strip()
            query = User.query.filter_by(email=email)
            
            if not include_inactive:
                query = query.filter_by(is_active=True)
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo usuario por email {email}: {str(e)}")
            return None

    def search_users(self, 
                    search_term: str = None,
                    user_type: str = None,
                    status: str = None,
                    organization_id: int = None,
                    created_from: datetime = None,
                    created_to: datetime = None,
                    page: int = 1,
                    per_page: int = 20,
                    sort_by: str = 'created_at',
                    sort_order: str = 'desc') -> dict[str, Any]:
        """
        Búsqueda avanzada de usuarios.
        
        Args:
            search_term: Término de búsqueda (nombre, email)
            user_type: Tipo de usuario a filtrar
            status: Estado del usuario
            organization_id: ID de organización
            created_from: Fecha de creación desde
            created_to: Fecha de creación hasta
            page: Página actual
            per_page: Usuarios por página
            sort_by: Campo para ordenar
            sort_order: Orden (asc/desc)
            
        Returns:
            Dict con usuarios y metadatos de paginación
        """
        try:
            query = User.query
            
            # Filtros de búsqueda
            if search_term:
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        User.first_name.ilike(search_pattern),
                        User.last_name.ilike(search_pattern),
                        User.email.ilike(search_pattern)
                    )
                )
            
            if user_type:
                query = query.filter_by(user_type=user_type)
            
            if status:
                if status == 'active':
                    query = query.filter_by(is_active=True)
                elif status == 'inactive':
                    query = query.filter_by(is_active=False)
                elif status == 'locked':
                    query = query.filter_by(is_locked=True)
            
            if organization_id:
                query = query.filter_by(organization_id=organization_id)
            
            if created_from:
                query = query.filter(User.created_at >= created_from)
            
            if created_to:
                query = query.filter(User.created_at <= created_to)
            
            # Ordenamiento
            sort_column = getattr(User, sort_by, User.created_at)
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Paginación
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'users': pagination.items,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'per_page': per_page,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev,
                'next_page': pagination.next_num if pagination.has_next else None,
                'prev_page': pagination.prev_num if pagination.has_prev else None
            }
            
        except Exception as e:
            logger.error(f"Error en búsqueda de usuarios: {str(e)}")
            raise ServiceError(f"Error interno en búsqueda: {str(e)}")

    # ==================== MÉTODOS DE ACTUALIZACIÓN ====================

    def update_user(self, user_id: int, update_data: dict[str, Any], updated_by: int = None) -> User:
        """
        Actualiza un usuario.
        
        Args:
            user_id: ID del usuario a actualizar
            update_data: Datos a actualizar
            updated_by: ID del usuario que hace la actualización
            
        Returns:
            Usuario actualizado
            
        Raises:
            UserNotFoundError: Si el usuario no existe
            ValidationError: Si los datos no son válidos
        """
        try:
            user = self.get_user_by_id(user_id, include_inactive=True)
            if not user:
                raise UserNotFoundError(f"Usuario con ID {user_id} no encontrado")
            
            # Validar datos de actualización
            self._validate_user_data(update_data, is_creation=False)
            
            # Verificar email duplicado si se está cambiando
            if 'email' in update_data and update_data['email'] != user.email:
                existing_user = self.get_user_by_email(update_data['email'])
                if existing_user and existing_user.id != user_id:
                    raise DuplicateUserError(f"Email {update_data['email']} ya está en uso")
            
            # Preparar datos
            prepared_data = self._prepare_user_data(update_data, is_update=True)
            
            # Actualizar campos
            changes = []
            for field, value in prepared_data.items():
                if hasattr(user, field) and getattr(user, field) != value:
                    old_value = getattr(user, field)
                    setattr(user, field, value)
                    changes.append(f"{field}: {old_value} -> {value}")
            
            user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Log de actividad
            if changes:
                self._log_activity(
                    user_id=user.id,
                    activity_type=ACTIVITY_TYPES.USER_UPDATED,
                    details=f"Campos actualizados: {', '.join(changes)}",
                    performed_by=updated_by
                )
                
                logger.info(f"Usuario actualizado: {user.email} - Cambios: {changes}")
            
            return user
            
        except (UserNotFoundError, ValidationError, DuplicateUserError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando usuario {user_id}: {str(e)}")
            raise ServiceError(f"Error interno actualizando usuario: {str(e)}")

    def change_user_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """
        Cambia la contraseña de un usuario.
        
        Args:
            user_id: ID del usuario
            current_password: Contraseña actual
            new_password: Nueva contraseña
            
        Returns:
            True si se cambió exitosamente
            
        Raises:
            UserNotFoundError: Si el usuario no existe
            AuthenticationError: Si la contraseña actual es incorrecta
            ValidationError: Si la nueva contraseña no es válida
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"Usuario con ID {user_id} no encontrado")
            
            # Verificar contraseña actual
            if not user.check_password(current_password):
                raise AuthenticationError("Contraseña actual incorrecta")
            
            # Validar nueva contraseña
            if not validate_password(new_password):
                raise ValidationError("La nueva contraseña no cumple los requisitos de seguridad")
            
            # Actualizar contraseña
            user.password_hash = generate_password_hash(new_password)
            user.password_changed_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Notificación
            self.notification_service.create_notification(
                user_id=user.id,
                type=NOTIFICATION_TYPES.SECURITY_ALERT,
                title="Contraseña actualizada",
                message="Tu contraseña ha sido cambiada exitosamente"
            )
            
            # Log de actividad
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.PASSWORD_CHANGED,
                details="Contraseña cambiada por el usuario"
            )
            
            logger.info(f"Contraseña cambiada exitosamente: {user.email}")
            return True
            
        except (UserNotFoundError, AuthenticationError, ValidationError):
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cambiando contraseña: {str(e)}")
            raise ServiceError(f"Error interno cambiando contraseña: {str(e)}")

    # ==================== MÉTODOS DE ESTADO ====================

    def activate_user(self, user_id: int, activated_by: int = None) -> bool:
        """Activa un usuario."""
        return self._change_user_status(user_id, True, activated_by, "activado")

    def deactivate_user(self, user_id: int, deactivated_by: int = None, reason: str = None) -> bool:
        """Desactiva un usuario."""
        return self._change_user_status(user_id, False, deactivated_by, "desactivado", reason)

    def _change_user_status(self, user_id: int, is_active: bool, changed_by: int = None, 
                           action: str = None, reason: str = None) -> bool:
        """Cambia el estado de activación de un usuario."""
        try:
            user = self.get_user_by_id(user_id, include_inactive=True)
            if not user:
                raise UserNotFoundError(f"Usuario con ID {user_id} no encontrado")
            
            if user.is_active == is_active:
                return True  # Ya está en el estado deseado
            
            user.is_active = is_active
            user.updated_at = datetime.now(timezone.utc)
            
            if not is_active:
                # Si se desactiva, también deslogear
                user.remember_token = None
                user.remember_token_expires = None
            
            db.session.commit()
            
            # Notificación
            status_text = "activada" if is_active else "desactivada"
            self.notification_service.create_notification(
                user_id=user.id,
                type=NOTIFICATION_TYPES.ACCOUNT_STATUS,
                title=f"Cuenta {status_text}",
                message=f"Tu cuenta ha sido {status_text}.{f' Motivo: {reason}' if reason else ''}"
            )
            
            # Log de actividad
            details = f"Usuario {action}"
            if reason:
                details += f" - Motivo: {reason}"
            
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.USER_STATUS_CHANGED,
                details=details,
                performed_by=changed_by
            )
            
            logger.info(f"Usuario {action}: {user.email}")
            return True
            
        except UserNotFoundError:
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cambiando estado de usuario {user_id}: {str(e)}")
            raise ServiceError(f"Error interno cambiando estado: {str(e)}")

    # ==================== MÉTODOS DE ESTADÍSTICAS ====================

    def get_user_statistics(self, date_from: datetime = None, date_to: datetime = None) -> dict[str, Any]:
        """
        Obtiene estadísticas de usuarios.
        
        Args:
            date_from: Fecha desde
            date_to: Fecha hasta
            
        Returns:
            Dict con estadísticas
        """
        try:
            base_query = User.query
            
            if date_from:
                base_query = base_query.filter(User.created_at >= date_from)
            if date_to:
                base_query = base_query.filter(User.created_at <= date_to)
            
            # Estadísticas básicas
            total_users = base_query.count()
            active_users = base_query.filter_by(is_active=True).count()
            inactive_users = base_query.filter_by(is_active=False).count()
            locked_users = base_query.filter_by(is_locked=True).count()
            
            # Por tipo de usuario
            entrepreneurs = base_query.filter_by(user_type='entrepreneur').count()
            allies = base_query.filter_by(user_type='ally').count()
            clients = base_query.filter_by(user_type='client').count()
            admins = base_query.filter_by(user_type='admin').count()
            
            # Usuarios por mes (últimos 12 meses)
            monthly_stats = []
            for i in range(12):
                month_start = datetime.now(timezone.utc).replace(day=1) - timedelta(days=30*i)
                month_end = month_start + timedelta(days=30)
                
                count = User.query.filter(
                    and_(
                        User.created_at >= month_start,
                        User.created_at < month_end
                    )
                ).count()
                
                monthly_stats.append({
                    'month': month_start.strftime('%Y-%m'),
                    'count': count
                })
            
            monthly_stats.reverse()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'locked_users': locked_users,
                'by_type': {
                    'entrepreneurs': entrepreneurs,
                    'allies': allies,
                    'clients': clients,
                    'admins': admins
                },
                'monthly_registrations': monthly_stats,
                'activity_rate': round((active_users / total_users * 100) if total_users > 0 else 0, 2)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            raise ServiceError(f"Error interno obteniendo estadísticas: {str(e)}")

    # ==================== MÉTODOS PRIVADOS ====================

    def _validate_user_data(self, data: dict[str, Any], is_creation: bool = False) -> None:
        """Valida los datos del usuario."""
        required_fields = ['email', 'first_name', 'last_name'] if is_creation else []
        
        # Verificar campos requeridos
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Campo requerido: {field}")
        
        # Validar email
        if 'email' in data:
            if not validate_email(data['email']):
                raise ValidationError("Email inválido")
        
        # Validar contraseña (solo en creación)
        if is_creation and 'password' in data:
            if not validate_password(data['password']):
                raise ValidationError("Contraseña no cumple los requisitos de seguridad")
        
        # Validar teléfono
        if 'phone' in data and data['phone']:
            if not validate_phone(data['phone']):
                raise ValidationError("Número de teléfono inválido")
        
        # Validar nombres
        if 'first_name' in data:
            if len(data['first_name'].strip()) < 2:
                raise ValidationError("Nombre debe tener al menos 2 caracteres")
        
        if 'last_name' in data:
            if len(data['last_name'].strip()) < 2:
                raise ValidationError("Apellido debe tener al menos 2 caracteres")

    def _prepare_user_data(self, data: dict[str, Any], is_update: bool = False) -> dict[str, Any]:
        """Prepara y sanitiza los datos del usuario."""
        prepared = {}
        
        # Email
        if 'email' in data:
            prepared['email'] = data['email'].lower().strip()
        
        # Nombres
        if 'first_name' in data:
            prepared['first_name'] = sanitize_string(data['first_name']).title()
        
        if 'last_name' in data:
            prepared['last_name'] = sanitize_string(data['last_name']).title()
        
        # Teléfono
        if 'phone' in data and data['phone']:
            prepared['phone'] = format_phone_number(data['phone'])
        
        # Contraseña (solo si se proporciona)
        if 'password' in data and not is_update:
            prepared['password_hash'] = generate_password_hash(data['password'])
        
        # Otros campos simples
        simple_fields = ['bio', 'location', 'timezone', 'language', 'organization_id']
        for field in simple_fields:
            if field in data:
                prepared[field] = data[field]
        
        # Campos de fecha
        if not is_update:
            prepared['created_at'] = datetime.now(timezone.utc)
            prepared['is_active'] = True
            prepared['email_verification_token'] = generate_secure_token()
        
        return prepared

    def _send_welcome_email(self, user: User) -> None:
        """Envía email de bienvenida."""
        try:
            verification_url = url_for(
                'auth.verify_email', 
                token=user.email_verification_token, 
                _external=True
            )
            self.email_service.send_welcome_email(user, verification_url)
        except Exception as e:
            logger.error(f"Error enviando email de bienvenida: {str(e)}")

    def _generate_session_token(self, user: User) -> str:
        """Genera token de sesión seguro."""
        token_data = f"{user.id}:{datetime.now(timezone.utc).isoformat()}:{secrets.token_hex(16)}"
        return encrypt_sensitive_data(token_data)

    def _log_activity(self, user_id: int, activity_type: str, details: str, performed_by: int = None) -> None:
        """Registra actividad en el log."""
        try:
            activity = ActivityLog(
                user_id=user_id,
                activity_type=activity_type,
                details=details,
                performed_by=performed_by or user_id,
                ip_address=self._get_client_ip(),
                user_agent=self._get_user_agent(),
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error registrando actividad: {str(e)}")

    def _get_client_ip(self) -> str:
        """Obtiene IP del cliente."""
        from flask import request
        return request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    def _get_user_agent(self) -> str:
        """Obtiene User-Agent del cliente."""
        from flask import request
        return request.headers.get('User-Agent', 'Unknown')

    # ==================== MÉTODOS DE LIMPIEZA ====================

    def cleanup_expired_tokens(self) -> int:
        """
        Limpia tokens expirados.
        
        Returns:
            Número de tokens limpiados
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Reset tokens expirados
            reset_count = User.query.filter(
                and_(
                    User.reset_token.isnot(None),
                    User.reset_token_expires < now
                )
            ).update({
                'reset_token': None,
                'reset_token_expires': None
            })
            
            # Remember tokens expirados
            remember_count = User.query.filter(
                and_(
                    User.remember_token.isnot(None),
                    User.remember_token_expires < now
                )
            ).update({
                'remember_token': None,
                'remember_token_expires': None
            })
            
            db.session.commit()
            
            total_cleaned = reset_count + remember_count
            if total_cleaned > 0:
                logger.info(f"Tokens limpiados: {total_cleaned} (Reset: {reset_count}, Remember: {remember_count})")
            
            return total_cleaned
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error limpiando tokens: {str(e)}")
            return 0

    def delete_user(self, user_id: int, deleted_by: int = None, reason: str = None) -> bool:
        """
        Elimina un usuario (soft delete).
        
        Args:
            user_id: ID del usuario a eliminar
            deleted_by: ID del usuario que elimina
            reason: Motivo de eliminación
            
        Returns:
            True si se eliminó exitosamente
        """
        try:
            user = self.get_user_by_id(user_id, include_inactive=True)
            if not user:
                raise UserNotFoundError(f"Usuario con ID {user_id} no encontrado")
            
            # Soft delete - marcar como eliminado
            user.is_active = False
            user.deleted_at = datetime.now(timezone.utc)
            user.deleted_by = deleted_by
            user.deletion_reason = reason
            
            # Limpiar tokens de sesión
            user.remember_token = None
            user.remember_token_expires = None
            user.reset_token = None
            user.reset_token_expires = None
            
            db.session.commit()
            
            # Log de actividad
            details = f"Usuario eliminado"
            if reason:
                details += f" - Motivo: {reason}"
            
            self._log_activity(
                user_id=user.id,
                activity_type=ACTIVITY_TYPES.USER_DELETED,
                details=details,
                performed_by=deleted_by
            )
            
            logger.info(f"Usuario eliminado: {user.email}")
            return True
            
        except UserNotFoundError:
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error eliminando usuario {user_id}: {str(e)}")
            raise ServiceError(f"Error interno eliminando usuario: {str(e)}")