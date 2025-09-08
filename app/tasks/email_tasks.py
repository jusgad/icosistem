"""
Sistema de Tareas de Email - Ecosistema de Emprendimiento
========================================================

Este módulo maneja todas las tareas asíncronas relacionadas con el envío de emails
para el ecosistema de emprendimiento. Incluye emails transaccionales, notificaciones,
reportes, digest y campañas específicas para cada tipo de usuario.

Funcionalidades principales:
- Emails de bienvenida y onboarding
- Notificaciones de reuniones y mentorías
- Reportes automáticos personalizados
- Digest de actividades
- Emails de seguimiento y recordatorios
- Campañas de engagement
- Processing de colas de email
- Tracking y analytics de emails
- Manejo de bounces y unsubscribes
"""

import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from celery import group, chain, chord
from jinja2 import Template, Environment, FileSystemLoader
from premailer import transform
import requests

from app.tasks.celery_app import celery_app
from app.core.exceptions import EmailError, TemplateError, EmailDeliveryError
from app.core.constants import EMAIL_TYPES, EMAIL_PRIORITIES, USER_ROLES
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.meeting import Meeting
from app.models.mentorship import MentorshipSession
from app.models.project import Project
from app.models.email_log import EmailLog, EmailStatus, EmailType
from app.models.email_campaign import EmailCampaign
from app.models.notification import Notification
from app.services.email import EmailService
from app.services.analytics_service import AnalyticsService
from app.services.user_service import UserService
from app.utils.formatters import format_datetime, format_currency, format_user_name
from app.utils.string_utils import truncate_text, sanitize_html
from app.utils.cache_utils import cache_get, cache_set
from app.utils.file_utils import ensure_directory_exists

logger = logging.getLogger(__name__)

# Configuración de templates
TEMPLATE_DIR = 'app/templates/emails'
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True
)

# Configuración de email por defecto
DEFAULT_FROM_EMAIL = 'noreply@ecosistema-emprendimiento.com'
DEFAULT_FROM_NAME = 'Ecosistema de Emprendimiento'


class EmailPriority(Enum):
    """Prioridades de email"""
    LOW = 1
    NORMAL = 3
    HIGH = 5
    URGENT = 7
    CRITICAL = 10


class EmailCategory(Enum):
    """Categorías de email"""
    TRANSACTIONAL = "transactional"
    NOTIFICATION = "notification"
    MARKETING = "marketing"
    REPORT = "report"
    DIGEST = "digest"
    REMINDER = "reminder"
    WELCOME = "welcome"
    FOLLOW_UP = "follow_up"


@dataclass
class EmailContext:
    """Contexto para templates de email"""
    user: dict[str, Any]
    app_name: str = "Ecosistema de Emprendimiento"
    app_url: str = "https://ecosistema-emprendimiento.com"
    support_email: str = "soporte@ecosistema-emprendimiento.com"
    unsubscribe_url: str = ""
    tracking_pixel_url: str = ""
    current_year: int = datetime.now().year
    
    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para usar en templates"""
        return asdict(self)


@dataclass
class EmailMetrics:
    """Métricas de email"""
    sent_count: int = 0
    delivered_count: int = 0
    opened_count: int = 0
    clicked_count: int = 0
    bounced_count: int = 0
    unsubscribed_count: int = 0
    failed_count: int = 0


# === TAREAS DE EMAIL TRANSACCIONALES ===

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='emails',
    priority=EmailPriority.HIGH.value
)
def send_welcome_email(self, user_id: int, user_type: str):
    """
    Envía email de bienvenida personalizado según el tipo de usuario
    
    Args:
        user_id: ID del usuario
        user_type: Tipo de usuario (entrepreneur, ally, client, admin)
    """
    try:
        logger.info(f"Enviando email de bienvenida a usuario {user_id} tipo {user_type}")
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            logger.error(f"Usuario {user_id} no encontrado")
            return {'success': False, 'error': 'User not found'}
        
        # Preparar contexto específico por tipo de usuario
        context = _prepare_welcome_context(user, user_type)
        
        # Seleccionar template según tipo de usuario
        template_map = {
            'entrepreneur': 'welcome_entrepreneur.html',
            'ally': 'welcome_ally.html',
            'client': 'welcome_client.html',
            'admin': 'welcome_admin.html'
        }
        
        template_name = template_map.get(user_type, 'welcome_default.html')
        
        # Enviar email
        result = _send_templated_email(
            template_name=template_name,
            context=context,
            to_email=user.email,
            to_name=user.get_full_name(),
            subject=f"¡Bienvenido al Ecosistema de Emprendimiento, {user.first_name}!",
            category=EmailCategory.WELCOME,
            user_id=user_id
        )
        
        # Programar email de seguimiento si es exitoso
        if result.get('success'):
            send_onboarding_sequence.apply_async(
                args=[user_id, user_type, 1],
                countdown=86400  # 24 horas después
            )
        
        return result
        
    except Exception as exc:
        logger.error(f"Error enviando email de bienvenida: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='emails',
    priority=EmailPriority.HIGH.value
)
def send_meeting_notification(self, meeting_id: int, notification_type: str):
    """
    Envía notificaciones de reuniones (confirmación, recordatorio, etc.)
    
    Args:
        meeting_id: ID de la reunión
        notification_type: Tipo de notificación (confirmed, reminder_24h, reminder_1h, cancelled)
    """
    try:
        logger.info(f"Enviando notificación de reunión {meeting_id} tipo {notification_type}")
        
        # Obtener reunión
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            logger.error(f"Reunión {meeting_id} no encontrada")
            return {'success': False, 'error': 'Meeting not found'}
        
        # Preparar contexto
        context = _prepare_meeting_context(meeting, notification_type)
        
        # Seleccionar template y subject según tipo
        template_subject_map = {
            'confirmed': ('meeting_confirmed.html', 'Reunión confirmada'),
            'reminder_24h': ('meeting_reminder.html', 'Recordatorio: Reunión mañana'),
            'reminder_1h': ('meeting_reminder.html', 'Recordatorio: Reunión en 1 hora'),
            'cancelled': ('meeting_cancelled.html', 'Reunión cancelada'),
            'rescheduled': ('meeting_rescheduled.html', 'Reunión reprogramada')
        }
        
        template_name, base_subject = template_subject_map.get(
            notification_type, 
            ('meeting_notification.html', 'Notificación de reunión')
        )
        
        # Enviar a todos los participantes
        results = []
        for participant in meeting.participants:
            result = _send_templated_email(
                template_name=template_name,
                context=context,
                to_email=participant.email,
                to_name=participant.get_full_name(),
                subject=f"{base_subject} - {meeting.title}",
                category=EmailCategory.NOTIFICATION,
                user_id=participant.id,
                metadata={'meeting_id': meeting_id, 'notification_type': notification_type}
            )
            results.append(result)
        
        # Resumir resultados
        success_count = sum(1 for r in results if r.get('success'))
        total_count = len(results)
        
        logger.info(f"Notificación de reunión enviada: {success_count}/{total_count} exitosos")
        
        return {
            'success': success_count > 0,
            'total_sent': total_count,
            'successful_sends': success_count,
            'meeting_id': meeting_id,
            'notification_type': notification_type
        }
        
    except Exception as exc:
        logger.error(f"Error enviando notificación de reunión: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    queue='emails',
    priority=EmailPriority.NORMAL.value
)
def send_mentorship_summary(self, session_id: int, recipient_type: str):
    """
    Envía resumen de sesión de mentoría
    
    Args:
        session_id: ID de la sesión de mentoría
        recipient_type: Tipo de destinatario (entrepreneur, mentor, both)
    """
    try:
        logger.info(f"Enviando resumen de mentoría {session_id} a {recipient_type}")
        
        # Obtener sesión
        session = MentorshipSession.query.get(session_id)
        if not session:
            logger.error(f"Sesión de mentoría {session_id} no encontrada")
            return {'success': False, 'error': 'Session not found'}
        
        # Preparar contexto
        context = _prepare_mentorship_context(session)
        
        results = []
        
        # Enviar a emprendedor
        if recipient_type in ['entrepreneur', 'both']:
            entrepreneur_result = _send_templated_email(
                template_name='mentorship_summary_entrepreneur.html',
                context=context,
                to_email=session.entrepreneur.email,
                to_name=session.entrepreneur.get_full_name(),
                subject=f"Resumen de tu sesión con {session.mentor.get_full_name()}",
                category=EmailCategory.REPORT,
                user_id=session.entrepreneur_id,
                metadata={'session_id': session_id, 'recipient': 'entrepreneur'}
            )
            results.append(entrepreneur_result)
        
        # Enviar a mentor
        if recipient_type in ['mentor', 'both']:
            mentor_result = _send_templated_email(
                template_name='mentorship_summary_mentor.html',
                context=context,
                to_email=session.mentor.email,
                to_name=session.mentor.get_full_name(),
                subject=f"Resumen de tu sesión con {session.entrepreneur.get_full_name()}",
                category=EmailCategory.REPORT,
                user_id=session.mentor_id,
                metadata={'session_id': session_id, 'recipient': 'mentor'}
            )
            results.append(mentor_result)
        
        # Resumir resultados
        success_count = sum(1 for r in results if r.get('success'))
        
        return {
            'success': success_count > 0,
            'total_sent': len(results),
            'successful_sends': success_count,
            'session_id': session_id,
            'recipient_type': recipient_type
        }
        
    except Exception as exc:
        logger.error(f"Error enviando resumen de mentoría: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE REPORTES Y DIGEST ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='emails',
    priority=EmailPriority.NORMAL.value
)
def send_daily_digest(self, user_id: int = None):
    """
    Envía digest diario de actividades
    
    Args:
        user_id: ID de usuario específico, si None envía a todos los usuarios activos
    """
    try:
        logger.info(f"Generando digest diario para usuario {user_id or 'todos'}")
        
        if user_id:
            users = [User.query.get(user_id)]
        else:
            # Obtener usuarios activos que tienen digest habilitado
            users = User.query.filter(
                User.is_active == True,
                User.email_preferences.contains('"daily_digest": true')
            ).all()
        
        results = []
        
        for user in users:
            if not user:
                continue
            
            # Preparar contexto del digest
            context = _prepare_daily_digest_context(user)
            
            # Solo enviar si hay contenido relevante
            if not _has_digest_content(context):
                logger.debug(f"Sin contenido relevante para digest de {user.email}")
                continue
            
            # Seleccionar template según tipo de usuario
            template_name = f'daily_digest_{user.role.value}.html'
            
            result = _send_templated_email(
                template_name=template_name,
                context=context,
                to_email=user.email,
                to_name=user.get_full_name(),
                subject=f"Tu resumen diario del ecosistema - {datetime.now().strftime('%d/%m/%Y')}",
                category=EmailCategory.DIGEST,
                user_id=user.id,
                metadata={'digest_date': datetime.now().date().isoformat()}
            )
            results.append(result)
        
        # Resumir resultados
        success_count = sum(1 for r in results if r.get('success'))
        total_count = len(results)
        
        logger.info(f"Digest diario enviado: {success_count}/{total_count} exitosos")
        
        return {
            'success': success_count > 0,
            'total_sent': total_count,
            'successful_sends': success_count,
            'date': datetime.now().date().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Error enviando digest diario: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='emails',
    priority=EmailPriority.LOW.value
)
def send_weekly_entrepreneur_report(self, entrepreneur_id: int = None):
    """
    Envía reporte semanal a emprendedores
    
    Args:
        entrepreneur_id: ID específico, si None envía a todos los emprendedores
    """
    try:
        logger.info(f"Generando reporte semanal para emprendedor {entrepreneur_id or 'todos'}")
        
        if entrepreneur_id:
            entrepreneurs = [Entrepreneur.query.get(entrepreneur_id)]
        else:
            entrepreneurs = Entrepreneur.query.filter(
                Entrepreneur.is_active == True
            ).all()
        
        results = []
        
        for entrepreneur in entrepreneurs:
            if not entrepreneur:
                continue
            
            # Preparar contexto del reporte
            context = _prepare_weekly_entrepreneur_context(entrepreneur)
            
            result = _send_templated_email(
                template_name='weekly_entrepreneur_report.html',
                context=context,
                to_email=entrepreneur.email,
                to_name=entrepreneur.get_full_name(),
                subject=f"Tu reporte semanal de progreso - Semana {datetime.now().isocalendar()[1]}",
                category=EmailCategory.REPORT,
                user_id=entrepreneur.id,
                metadata={
                    'report_type': 'weekly_entrepreneur',
                    'week': datetime.now().isocalendar()[1],
                    'year': datetime.now().year
                }
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        
        logger.info(f"Reporte semanal de emprendedores enviado: {success_count}/{len(results)} exitosos")
        
        return {
            'success': success_count > 0,
            'total_sent': len(results),
            'successful_sends': success_count,
            'report_type': 'weekly_entrepreneur',
            'week': datetime.now().isocalendar()[1]
        }
        
    except Exception as exc:
        logger.error(f"Error enviando reporte semanal de emprendedores: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='emails',
    priority=EmailPriority.LOW.value
)
def send_monthly_ecosystem_report(self, admin_emails: list[str] = None):
    """
    Envía reporte mensual del ecosistema a administradores
    
    Args:
        admin_emails: Lista de emails específicos, si None envía a todos los admins
    """
    try:
        logger.info("Generando reporte mensual del ecosistema")
        
        if admin_emails:
            recipients = [(email, "Administrador") for email in admin_emails]
        else:
            # Obtener todos los administradores
            admins = User.query.filter(
                User.role == 'admin',
                User.is_active == True
            ).all()
            recipients = [(admin.email, admin.get_full_name()) for admin in admins]
        
        # Preparar contexto del reporte
        context = _prepare_monthly_ecosystem_context()
        
        results = []
        
        for email, name in recipients:
            result = _send_templated_email(
                template_name='monthly_ecosystem_report.html',
                context=context,
                to_email=email,
                to_name=name,
                subject=f"Reporte Mensual del Ecosistema - {datetime.now().strftime('%B %Y')}",
                category=EmailCategory.REPORT,
                metadata={
                    'report_type': 'monthly_ecosystem',
                    'month': datetime.now().month,
                    'year': datetime.now().year
                }
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        
        logger.info(f"Reporte mensual del ecosistema enviado: {success_count}/{len(results)} exitosos")
        
        return {
            'success': success_count > 0,
            'total_sent': len(results),
            'successful_sends': success_count,
            'report_type': 'monthly_ecosystem',
            'month': datetime.now().strftime('%B %Y')
        }
        
    except Exception as exc:
        logger.error(f"Error enviando reporte mensual del ecosistema: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE SECUENCIAS Y SEGUIMIENTO ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=180,
    queue='emails',
    priority=EmailPriority.NORMAL.value
)
def send_onboarding_sequence(self, user_id: int, user_type: str, step: int):
    """
    Envía secuencia de onboarding por pasos
    
    Args:
        user_id: ID del usuario
        user_type: Tipo de usuario
        step: Paso actual de la secuencia (1-5)
    """
    try:
        logger.info(f"Enviando paso {step} de onboarding a usuario {user_id}")
        
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Verificar si el usuario sigue activo
        if not user.is_active:
            logger.info(f"Usuario {user_id} inactivo, cancelando secuencia de onboarding")
            return {'success': False, 'error': 'User inactive'}
        
        # Configuración de pasos por tipo de usuario
        onboarding_steps = {
            'entrepreneur': {
                1: ('Completa tu perfil de emprendedor', 'onboarding_entrepreneur_step1.html'),
                2: ('Crea tu primer proyecto', 'onboarding_entrepreneur_step2.html'),
                3: ('Encuentra tu mentor ideal', 'onboarding_entrepreneur_step3.html'),
                4: ('Programa tu primera mentoría', 'onboarding_entrepreneur_step4.html'),
                5: ('Recursos para emprendedores', 'onboarding_entrepreneur_step5.html')
            },
            'ally': {
                1: ('Configura tu perfil de mentor', 'onboarding_ally_step1.html'),
                2: ('Define tu área de expertise', 'onboarding_ally_step2.html'),
                3: ('Establece tu disponibilidad', 'onboarding_ally_step3.html'),
                4: ('Conoce a los emprendedores', 'onboarding_ally_step4.html'),
                5: ('Herramientas de mentoría', 'onboarding_ally_step5.html')
            },
            'client': {
                1: ('Explora el ecosistema', 'onboarding_client_step1.html'),
                2: ('Configurar notificaciones', 'onboarding_client_step2.html'),
                3: ('Dashboard personalizado', 'onboarding_client_step3.html')
            }
        }
        
        steps_config = onboarding_steps.get(user_type, {})
        if step not in steps_config:
            logger.info(f"Secuencia de onboarding completada para usuario {user_id}")
            return {'success': True, 'message': 'Onboarding sequence completed'}
        
        subject, template_name = steps_config[step]
        
        # Preparar contexto
        context = _prepare_onboarding_context(user, user_type, step)
        
        # Enviar email
        result = _send_templated_email(
            template_name=template_name,
            context=context,
            to_email=user.email,
            to_name=user.get_full_name(),
            subject=f"Paso {step}: {subject}",
            category=EmailCategory.FOLLOW_UP,
            user_id=user_id,
            metadata={'onboarding_step': step, 'user_type': user_type}
        )
        
        # Programar siguiente paso si es exitoso
        if result.get('success') and step < len(steps_config):
            next_step_delay = _get_onboarding_delay(step)
            send_onboarding_sequence.apply_async(
                args=[user_id, user_type, step + 1],
                countdown=next_step_delay
            )
        
        return result
        
    except Exception as exc:
        logger.error(f"Error en secuencia de onboarding: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=180 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='emails',
    priority=EmailPriority.HIGH.value
)
def send_reminder_email(self, reminder_type: str, user_id: int, context_data: dict[str, Any]):
    """
    Envía emails de recordatorio
    
    Args:
        reminder_type: Tipo de recordatorio (meeting, task, deadline, etc.)
        user_id: ID del usuario
        context_data: Datos específicos del recordatorio
    """
    try:
        logger.info(f"Enviando recordatorio {reminder_type} a usuario {user_id}")
        
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Configuración de recordatorios
        reminder_configs = {
            'meeting': {
                'template': 'reminder_meeting.html',
                'subject': 'Recordatorio: Reunión en {time_until}',
                'priority': EmailPriority.HIGH
            },
            'task_deadline': {
                'template': 'reminder_task_deadline.html',
                'subject': 'Recordatorio: Tarea vence {time_until}',
                'priority': EmailPriority.NORMAL
            },
            'mentorship_feedback': {
                'template': 'reminder_mentorship_feedback.html',
                'subject': 'Recordatorio: Feedback pendiente de mentoría',
                'priority': EmailPriority.NORMAL
            },
            'profile_completion': {
                'template': 'reminder_profile_completion.html',
                'subject': 'Completa tu perfil para mejores conexiones',
                'priority': EmailPriority.LOW
            },
            'inactive_user': {
                'template': 'reminder_inactive_user.html',
                'subject': 'Te extrañamos en el ecosistema',
                'priority': EmailPriority.LOW
            }
        }
        
        config = reminder_configs.get(reminder_type)
        if not config:
            return {'success': False, 'error': f'Unknown reminder type: {reminder_type}'}
        
        # Preparar contexto
        context = _prepare_reminder_context(user, reminder_type, context_data)
        
        # Formatear subject con datos del contexto
        subject = config['subject'].format(**context_data)
        
        # Enviar email
        result = _send_templated_email(
            template_name=config['template'],
            context=context,
            to_email=user.email,
            to_name=user.get_full_name(),
            subject=subject,
            category=EmailCategory.REMINDER,
            user_id=user_id,
            metadata={'reminder_type': reminder_type, **context_data}
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"Error enviando recordatorio: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE PROCESAMIENTO MASIVO ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='emails',
    priority=EmailPriority.LOW.value
)
def process_email_queue(self):
    """
    Procesa la cola de emails pendientes
    
    Esta tarea se ejecuta periódicamente para procesar emails
    que están en cola por límites de rate o fallos temporales.
    """
    try:
        logger.info("Procesando cola de emails pendientes")
        
        # Obtener emails pendientes de los últimos 7 días
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        pending_emails = EmailLog.query.filter(
            EmailLog.status == EmailStatus.PENDING,
            EmailLog.created_at >= cutoff_date
        ).order_by(EmailLog.priority.desc(), EmailLog.created_at.asc()).limit(100).all()
        
        if not pending_emails:
            logger.info("No hay emails pendientes para procesar")
            return {'success': True, 'processed': 0}
        
        logger.info(f"Procesando {len(pending_emails)} emails pendientes")
        
        processed = 0
        failed = 0
        
        for email_log in pending_emails:
            try:
                # Intentar enviar email
                result = _send_email_from_log(email_log)
                
                if result.get('success'):
                    email_log.status = EmailStatus.SENT
                    email_log.sent_at = datetime.now(timezone.utc)
                    processed += 1
                else:
                    email_log.retry_count += 1
                    if email_log.retry_count >= 3:
                        email_log.status = EmailStatus.FAILED
                        email_log.error_message = result.get('error', 'Max retries exceeded')
                    failed += 1
                
                # Guardar cambios
                from app import db
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Error procesando email {email_log.id}: {str(e)}")
                email_log.retry_count += 1
                email_log.error_message = str(e)
                
                if email_log.retry_count >= 3:
                    email_log.status = EmailStatus.FAILED
                
                failed += 1
                
                from app import db
                db.session.commit()
        
        logger.info(f"Procesamiento completado: {processed} exitosos, {failed} fallidos")
        
        return {
            'success': True,
            'total_processed': len(pending_emails),
            'successful': processed,
            'failed': failed
        }
        
    except Exception as exc:
        logger.error(f"Error procesando cola de emails: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    queue='emails',
    priority=EmailPriority.LOW.value
)
def send_bulk_campaign(self, campaign_id: int):
    """
    Envía campaña de email masiva
    
    Args:
        campaign_id: ID de la campaña de email
    """
    try:
        logger.info(f"Iniciando envío de campaña {campaign_id}")
        
        # Obtener campaña
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}
        
        # Verificar estado de la campaña
        if campaign.status != 'scheduled':
            return {'success': False, 'error': f'Campaign status is {campaign.status}'}
        
        # Actualizar estado a enviando
        campaign.status = 'sending'
        campaign.started_at = datetime.now(timezone.utc)
        
        from app import db
        db.session.commit()
        
        # Obtener destinatarios según segmentación
        recipients = _get_campaign_recipients(campaign)
        
        logger.info(f"Enviando campaña a {len(recipients)} destinatarios")
        
        # Crear trabajos de envío en lotes
        batch_size = 50
        batches = [recipients[i:i + batch_size] for i in range(0, len(recipients), batch_size)]
        
        # Crear grupo de tareas para envío paralelo
        job_group = group(
            send_campaign_batch.s(campaign_id, batch, batch_idx)
            for batch_idx, batch in enumerate(batches)
        )
        
        # Ejecutar grupo de tareas
        result = job_group.apply_async()
        
        # Guardar job_id para tracking
        campaign.job_id = result.id
        db.session.commit()
        
        return {
            'success': True,
            'campaign_id': campaign_id,
            'total_recipients': len(recipients),
            'total_batches': len(batches),
            'job_id': result.id
        }
        
    except Exception as exc:
        logger.error(f"Error enviando campaña: {str(exc)}")
        
        # Actualizar estado de la campaña a fallida
        try:
            campaign = EmailCampaign.query.get(campaign_id)
            if campaign:
                campaign.status = 'failed'
                campaign.error_message = str(exc)
                from app import db
                db.session.commit()
        except:
            pass
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=600)
        return {'success': False, 'error': str(exc)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue='emails',
    priority=EmailPriority.NORMAL.value
)
def send_campaign_batch(self, campaign_id: int, recipients: list[Dict], batch_idx: int):
    """
    Envía un lote de una campaña de email
    
    Args:
        campaign_id: ID de la campaña
        recipients: Lista de destinatarios del lote
        batch_idx: Índice del lote
    """
    try:
        logger.info(f"Enviando lote {batch_idx} de campaña {campaign_id} con {len(recipients)} destinatarios")
        
        # Obtener campaña
        campaign = EmailCampaign.query.get(campaign_id)
        if not campaign:
            return {'success': False, 'error': 'Campaign not found'}
        
        results = []
        
        for recipient in recipients:
            try:
                # Preparar contexto personalizado
                context = _prepare_campaign_context(campaign, recipient)
                
                # Enviar email
                result = _send_templated_email(
                    template_name=campaign.template_name,
                    context=context,
                    to_email=recipient['email'],
                    to_name=recipient['name'],
                    subject=campaign.subject,
                    category=EmailCategory.MARKETING,
                    user_id=recipient.get('user_id'),
                    metadata={
                        'campaign_id': campaign_id,
                        'batch_idx': batch_idx,
                        'recipient_id': recipient.get('id')
                    }
                )
                
                results.append(result)
                
                # Rate limiting entre envíos
                import time
                time.sleep(0.1)  # 100ms entre emails
                
            except Exception as e:
                logger.error(f"Error enviando a {recipient['email']}: {str(e)}")
                results.append({'success': False, 'error': str(e)})
        
        # Resumir resultados del lote
        success_count = sum(1 for r in results if r.get('success'))
        
        logger.info(f"Lote {batch_idx} completado: {success_count}/{len(recipients)} exitosos")
        
        return {
            'success': True,
            'campaign_id': campaign_id,
            'batch_idx': batch_idx,
            'total_recipients': len(recipients),
            'successful_sends': success_count,
            'failed_sends': len(recipients) - success_count
        }
        
    except Exception as exc:
        logger.error(f"Error enviando lote de campaña: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === TAREAS DE MÉTRICAS Y TRACKING ===

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue='emails',
    priority=EmailPriority.LOW.value
)
def update_email_metrics(self):
    """
    Actualiza métricas de email desde el proveedor de email
    """
    try:
        logger.info("Actualizando métricas de email")
        
        # Obtener emails enviados en los últimos 7 días sin métricas actualizadas
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        emails_to_update = EmailLog.query.filter(
            EmailLog.status == EmailStatus.SENT,
            EmailLog.sent_at >= cutoff_date,
            EmailLog.last_metrics_update.is_(None) | 
            (EmailLog.last_metrics_update < datetime.now(timezone.utc) - timedelta(hours=6))
        ).limit(1000).all()
        
        if not emails_to_update:
            logger.info("No hay emails para actualizar métricas")
            return {'success': True, 'updated': 0}
        
        logger.info(f"Actualizando métricas para {len(emails_to_update)} emails")
        
        email_service = EmailService()
        updated_count = 0
        
        for email_log in emails_to_update:
            try:
                # Obtener métricas del proveedor
                metrics = email_service.get_email_metrics(email_log.external_id)
                
                if metrics:
                    # Actualizar métricas en la base de datos
                    email_log.delivered = metrics.get('delivered', False)
                    email_log.opened = metrics.get('opened', False)
                    email_log.clicked = metrics.get('clicked', False)
                    email_log.bounced = metrics.get('bounced', False)
                    email_log.unsubscribed = metrics.get('unsubscribed', False)
                    email_log.last_metrics_update = datetime.now(timezone.utc)
                    
                    if metrics.get('delivered_at'):
                        email_log.delivered_at = metrics['delivered_at']
                    if metrics.get('opened_at'):
                        email_log.opened_at = metrics['opened_at']
                    if metrics.get('clicked_at'):
                        email_log.clicked_at = metrics['clicked_at']
                    
                    updated_count += 1
                
            except Exception as e:
                logger.error(f"Error actualizando métricas para email {email_log.id}: {str(e)}")
        
        # Guardar cambios
        from app import db
        db.session.commit()
        
        logger.info(f"Métricas actualizadas para {updated_count} emails")
        
        return {
            'success': True,
            'total_checked': len(emails_to_update),
            'updated': updated_count
        }
        
    except Exception as exc:
        logger.error(f"Error actualizando métricas de email: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))
        return {'success': False, 'error': str(exc)}


# === FUNCIONES AUXILIARES PRIVADAS ===

def _send_templated_email(
    template_name: str,
    context: dict[str, Any],
    to_email: str,
    to_name: str,
    subject: str,
    category: EmailCategory,
    user_id: int = None,
    metadata: dict[str, Any] = None,
    priority: EmailPriority = EmailPriority.NORMAL
) -> dict[str, Any]:
    """
    Función auxiliar para enviar emails con template
    """
    try:
        # Cargar template
        template = TEMPLATE_ENV.get_template(template_name)
        
        # Añadir contexto base
        base_context = EmailContext(
            user=context.get('user', {}),
            unsubscribe_url=f"https://ecosistema-emprendimiento.com/unsubscribe?token={_generate_unsubscribe_token(to_email)}",
            tracking_pixel_url=f"https://ecosistema-emprendimiento.com/email/track/{uuid.uuid4()}"
        )
        
        # Combinar contextos
        full_context = {**base_context.to_dict(), **context}
        
        # Renderizar template
        html_content = template.render(**full_context)
        
        # Optimizar HTML para email (inline CSS)
        html_content = transform(html_content)
        
        # Crear log de email
        email_log = EmailLog(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            template_name=template_name,
            category=category.value,
            user_id=user_id,
            metadata=metadata or {},
            priority=priority.value,
            status=EmailStatus.PENDING
        )
        
        from app import db
        db.session.add(email_log)
        db.session.flush()  # Para obtener el ID
        
        # Enviar email
        email_service = EmailService()
        result = email_service.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=html_content,
            category=category.value,
            metadata={'email_log_id': email_log.id, **(metadata or {})}
        )
        
        # Actualizar log según resultado
        if result.get('success'):
            email_log.status = EmailStatus.SENT
            email_log.sent_at = datetime.now(timezone.utc)
            email_log.external_id = result.get('message_id')
        else:
            email_log.status = EmailStatus.FAILED
            email_log.error_message = result.get('error')
        
        db.session.commit()
        
        return result
        
    except Exception as e:
        logger.error(f"Error enviando email con template {template_name}: {str(e)}")
        return {'success': False, 'error': str(e)}


def _prepare_welcome_context(user: User, user_type: str) -> dict[str, Any]:
    """Prepara contexto para email de bienvenida"""
    context = {
        'user': {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'full_name': user.get_full_name(),
            'type': user_type
        },
        'welcome_message': _get_welcome_message(user_type),
        'next_steps': _get_next_steps(user_type),
        'dashboard_url': f"https://ecosistema-emprendimiento.com/{user_type}/dashboard"
    }
    return context


def _prepare_meeting_context(meeting: Meeting, notification_type: str) -> dict[str, Any]:
    """Prepara contexto para notificaciones de reunión"""
    context = {
        'meeting': {
            'id': meeting.id,
            'title': meeting.title,
            'description': meeting.description,
            'start_time': format_datetime(meeting.start_time),
            'end_time': format_datetime(meeting.end_time),
            'location': meeting.location,
            'meeting_url': meeting.meeting_url,
            'duration_minutes': meeting.duration_minutes
        },
        'notification_type': notification_type,
        'participants': [
            {
                'name': p.get_full_name(),
                'email': p.email,
                'role': p.role.value
            }
            for p in meeting.participants
        ]
    }
    
    # Añadir información específica del tipo de notificación
    if notification_type.startswith('reminder'):
        time_until = meeting.start_time - datetime.now(timezone.utc)
        context['time_until'] = _format_time_until(time_until)
    
    return context


def _prepare_mentorship_context(session: MentorshipSession) -> dict[str, Any]:
    """Prepara contexto para resumen de mentoría"""
    context = {
        'session': {
            'id': session.id,
            'date': format_datetime(session.date),
            'duration_minutes': session.duration_minutes,
            'topics_discussed': session.topics_discussed,
            'goals_set': session.goals_set,
            'next_steps': session.next_steps,
            'feedback_entrepreneur': session.feedback_entrepreneur,
            'feedback_mentor': session.feedback_mentor
        },
        'entrepreneur': {
            'name': session.entrepreneur.get_full_name(),
            'email': session.entrepreneur.email,
            'project_name': session.entrepreneur.current_project.name if session.entrepreneur.current_project else None
        },
        'mentor': {
            'name': session.mentor.get_full_name(),
            'email': session.mentor.email,
            'expertise_areas': session.mentor.expertise_areas
        }
    }
    return context


def _prepare_daily_digest_context(user: User) -> dict[str, Any]:
    """Prepara contexto para digest diario"""
    from app.services.analytics_service import AnalyticsService
    
    analytics_service = AnalyticsService()
    
    # Obtener actividades recientes
    activities = analytics_service.get_user_recent_activities(user.id, days=1)
    
    context = {
        'user': {
            'name': user.get_full_name(),
            'type': user.role.value
        },
        'digest_date': format_datetime(datetime.now()),
        'activities': activities,
        'stats': analytics_service.get_user_daily_stats(user.id),
        'upcoming_events': _get_upcoming_events(user),
        'recommendations': _get_personalized_recommendations(user)
    }
    
    return context


def _prepare_weekly_entrepreneur_context(entrepreneur: Entrepreneur) -> dict[str, Any]:
    """Prepara contexto para reporte semanal de emprendedor"""
    from app.services.analytics_service import AnalyticsService
    
    analytics_service = AnalyticsService()
    
    context = {
        'entrepreneur': {
            'name': entrepreneur.get_full_name(),
            'project_name': entrepreneur.current_project.name if entrepreneur.current_project else None
        },
        'week_stats': analytics_service.get_entrepreneur_weekly_stats(entrepreneur.id),
        'mentorship_sessions': _get_recent_mentorship_sessions(entrepreneur.id),
        'project_progress': _get_project_progress(entrepreneur.id),
        'goals_achievements': _get_goals_achievements(entrepreneur.id),
        'recommendations': _get_entrepreneur_recommendations(entrepreneur.id)
    }
    
    return context


def _prepare_monthly_ecosystem_context() -> dict[str, Any]:
    """Prepara contexto para reporte mensual del ecosistema"""
    from app.services.analytics_service import AnalyticsService
    
    analytics_service = AnalyticsService()
    
    context = {
        'month_year': datetime.now().strftime('%B %Y'),
        'ecosystem_stats': analytics_service.get_monthly_ecosystem_stats(),
        'top_entrepreneurs': analytics_service.get_top_entrepreneurs_of_month(),
        'top_mentors': analytics_service.get_top_mentors_of_month(),
        'success_stories': _get_month_success_stories(),
        'growth_metrics': analytics_service.get_growth_metrics(),
        'engagement_metrics': analytics_service.get_engagement_metrics()
    }
    
    return context


def _has_digest_content(context: dict[str, Any]) -> bool:
    """Verifica si el digest tiene contenido relevante"""
    activities = context.get('activities', [])
    upcoming_events = context.get('upcoming_events', [])
    recommendations = context.get('recommendations', [])
    
    return len(activities) > 0 or len(upcoming_events) > 0 or len(recommendations) > 0


def _get_welcome_message(user_type: str) -> str:
    """Obtiene mensaje de bienvenida personalizado"""
    messages = {
        'entrepreneur': "¡Bienvenido a tu journey emprendedor! Estamos aquí para apoyarte en cada paso.",
        'ally': "¡Gracias por unirte como mentor! Tu experiencia será invaluable para los emprendedores.",
        'client': "¡Bienvenido al ecosistema! Explora y descubre oportunidades increíbles.",
        'admin': "Bienvenido al panel de administración del ecosistema."
    }
    return messages.get(user_type, "¡Bienvenido al Ecosistema de Emprendimiento!")


def _get_next_steps(user_type: str) -> list[str]:
    """Obtiene próximos pasos recomendados"""
    steps = {
        'entrepreneur': [
            "Completa tu perfil de emprendedor",
            "Crea tu primer proyecto",
            "Busca un mentor adecuado",
            "Programa tu primera sesión de mentoría"
        ],
        'ally': [
            "Configura tu perfil de mentor",
            "Define tus áreas de expertise",
            "Establece tu disponibilidad",
            "Conecta con emprendedores"
        ],
        'client': [
            "Explora el directorio de emprendimientos",
            "Configura tus preferencias",
            "Suscríbete a actualizaciones"
        ]
    }
    return steps.get(user_type, [])


def _get_onboarding_delay(step: int) -> int:
    """Obtiene delay en segundos para próximo paso de onboarding"""
    delays = {
        1: 86400,   # 24 horas
        2: 172800,  # 48 horas
        3: 259200,  # 72 horas
        4: 432000,  # 5 días
        5: 604800   # 7 días
    }
    return delays.get(step, 86400)


def _generate_unsubscribe_token(email: str) -> str:
    """Genera token seguro para unsubscribe"""
    import hashlib
    import secrets
    
    salt = secrets.token_hex(16)
    token = hashlib.sha256(f"{email}{salt}".encode()).hexdigest()
    
    # Guardar token en cache para validación
    cache_set(f"unsubscribe_token_{token}", email, timeout=2592000)  # 30 días
    
    return token


def _format_time_until(time_delta: timedelta) -> str:
    """Formatea tiempo restante de forma legible"""
    total_seconds = int(time_delta.total_seconds())
    
    if total_seconds < 3600:  # Menos de 1 hora
        minutes = total_seconds // 60
        return f"{minutes} minutos"
    elif total_seconds < 86400:  # Menos de 1 día
        hours = total_seconds // 3600
        return f"{hours} horas"
    else:  # 1 día o más
        days = total_seconds // 86400
        return f"{days} días"


def _get_upcoming_events(user: User) -> list[dict[str, Any]]:
    """Obtiene eventos próximos para el usuario"""
    # Implementar lógica para obtener reuniones, mentorías, etc.
    return []


def _get_personalized_recommendations(user: User) -> list[dict[str, Any]]:
    """Obtiene recomendaciones personalizadas"""
    # Implementar lógica de recomendaciones basada en ML/reglas
    return []


def _get_recent_mentorship_sessions(entrepreneur_id: int) -> list[dict[str, Any]]:
    """Obtiene sesiones de mentoría recientes"""
    sessions = MentorshipSession.query.filter(
        MentorshipSession.entrepreneur_id == entrepreneur_id,
        MentorshipSession.date >= datetime.now(timezone.utc) - timedelta(days=7)
    ).all()
    
    return [
        {
            'mentor_name': session.mentor.get_full_name(),
            'date': format_datetime(session.date),
            'topics': session.topics_discussed,
            'goals': session.goals_set
        }
        for session in sessions
    ]


def _send_email_from_log(email_log: EmailLog) -> dict[str, Any]:
    """Envía email desde log existente"""
    try:
        email_service = EmailService()
        
        # Reconstuir contexto si es necesario
        template = TEMPLATE_ENV.get_template(email_log.template_name)
        html_content = template.render(email_log.metadata.get('context', {}))
        html_content = transform(html_content)
        
        result = email_service.send_email(
            to_email=email_log.to_email,
            to_name=email_log.to_name,
            subject=email_log.subject,
            html_content=html_content,
            category=email_log.category,
            metadata=email_log.metadata
        )
        
        if result.get('success'):
            email_log.external_id = result.get('message_id')
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


# Funciones adicionales que se pueden implementar según necesidades específicas
def _get_campaign_recipients(campaign: EmailCampaign) -> list[dict[str, Any]]:
    """Obtiene destinatarios de campaña según segmentación"""
    # Implementar lógica de segmentación
    return []


def _prepare_campaign_context(campaign: EmailCampaign, recipient: dict[str, Any]) -> dict[str, Any]:
    """Prepara contexto personalizado para campaña"""
    return {
        'recipient': recipient,
        'campaign': {
            'name': campaign.name,
            'id': campaign.id
        }
    }


def _get_project_progress(entrepreneur_id: int) -> dict[str, Any]:
    """Obtiene progreso de proyectos"""
    return {}


def _get_goals_achievements(entrepreneur_id: int) -> list[dict[str, Any]]:
    """Obtiene logros de objetivos"""
    return []


def _get_entrepreneur_recommendations(entrepreneur_id: int) -> list[dict[str, Any]]:
    """Obtiene recomendaciones específicas para emprendedor"""
    return []


def _get_month_success_stories() -> list[dict[str, Any]]:
    """Obtiene historias de éxito del mes"""
    return []


def _prepare_onboarding_context(user: User, user_type: str, step: int) -> dict[str, Any]:
    """Prepara contexto para paso de onboarding"""
    return {
        'user': {
            'name': user.get_full_name(),
            'type': user_type
        },
        'step': step,
        'dashboard_url': f"https://ecosistema-emprendimiento.com/{user_type}/dashboard"
    }


def _prepare_reminder_context(user: User, reminder_type: str, context_data: dict[str, Any]) -> dict[str, Any]:
    """Prepara contexto para recordatorios"""
    return {
        'user': {
            'name': user.get_full_name(),
            'type': user.role.value
        },
        'reminder_type': reminder_type,
        **context_data
    }


# Exportar tareas principales
__all__ = [
    'send_welcome_email',
    'send_meeting_notification',
    'send_mentorship_summary',
    'send_daily_digest',
    'send_weekly_entrepreneur_report',
    'send_monthly_ecosystem_report',
    'send_onboarding_sequence',
    'send_reminder_email',
    'process_email_queue',
    'send_bulk_campaign',
    'send_campaign_batch',
    'update_email_metrics',
    'EmailPriority',
    'EmailCategory',
    'EmailContext',
    'EmailMetrics'
]