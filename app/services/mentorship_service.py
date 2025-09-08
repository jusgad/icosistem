"""
Mentorship Service Module

Servicio especializado para gestión del sistema de mentoría en el ecosistema.
Maneja toda la lógica de negocio relacionada con sesiones de mentoría, 
asignaciones mentor-emprendedor, evaluaciones, programación y seguimiento.

Author: Sistema de Emprendimiento
Version: 2.0.0
"""

import logging
from datetime import datetime, timedelta, time
from typing import Optional, Any, Union
from decimal import Decimal
from collections import defaultdict
import statistics
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, asc, case, extract
from flask import current_app
import json

from app.extensions import db
from app.models.mentorship import MentorshipSession
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.user import User
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.document import Document
from app.core.exceptions import (
    ValidationError,
    UserNotFoundError,
    PermissionError,
    ServiceError,
    BusinessLogicError,
    SessionConflictError as ConflictError  # Usar SessionConflictError como ConflictError
)
from app.core.constants import (
    MENTORSHIP_STATUS,
    MENTORSHIP_TYPES,
    MEETING_STATUS,
    NOTIFICATION_TYPES,
    ACTIVITY_TYPES,
    USER_ROLES,
    MENTOR_SPECIALTIES,
    SESSION_OUTCOMES
)
from app.services.base import BaseService
from app.services.notification_service import NotificationService
from app.services.email import EmailService
from app.services.google_calendar import GoogleCalendarService
from app.services.google_meet import GoogleMeetService
from app.utils.validators import validate_session_duration, validate_future_datetime
from app.utils.formatters import format_duration, format_currency
from app.utils.date_utils import (
    get_business_hours, 
    is_business_day, 
    get_timezone_offset,
    convert_to_user_timezone
)

logger = logging.getLogger(__name__)


class MentorshipService(BaseService):
    """
    Servicio especializado para gestión del sistema de mentoría.
    
    Funcionalidades principales:
    - Gestión completa de sesiones de mentoría
    - Asignación inteligente mentor-emprendedor
    - Sistema de evaluaciones y feedback
    - Programación automática con Google Calendar
    - Métricas y analytics de mentoría
    - Gestión de disponibilidad de mentores
    - Sistema de recordatorios y seguimiento
    - Reportes especializados de efectividad
    """

    def __init__(self):
        super().__init__()
        self.notification_service = NotificationService()
        self.email_service = EmailService()
        self.calendar_service = GoogleCalendarService()
        self.meet_service = GoogleMeetService()
        
        # Configuraciones
        self.default_session_duration = current_app.config.get('DEFAULT_SESSION_DURATION_MINUTES', 60)
        self.min_session_duration = current_app.config.get('MIN_SESSION_DURATION_MINUTES', 30)
        self.max_session_duration = current_app.config.get('MAX_SESSION_DURATION_MINUTES', 180)
        self.advance_booking_days = current_app.config.get('ADVANCE_BOOKING_DAYS', 30)
        self.min_advance_hours = current_app.config.get('MIN_ADVANCE_HOURS', 24)

    # ==================== GESTIÓN DE SESIONES ====================

    def create_mentorship_session(self, session_data: dict[str, Any], created_by: int = None) -> MentorshipSession:
        """
        Crea una nueva sesión de mentoría.
        
        Args:
            session_data: Datos de la sesión
            created_by: ID del usuario que crea la sesión
            
        Returns:
            Sesión de mentoría creada
            
        Raises:
            ValidationError: Si los datos no son válidos
            BusinessLogicError: Si viola reglas de negocio
            ConflictError: Si hay conflicto de horarios
        """
        try:
            # Validar datos básicos
            self._validate_session_data(session_data)
            
            # Obtener mentor y emprendedor
            mentor = self._get_mentor_by_id(session_data['mentor_id'])
            entrepreneur = self._get_entrepreneur_by_id(session_data['entrepreneur_id'])
            
            if not mentor:
                raise UserNotFoundError(f"Mentor {session_data['mentor_id']} no encontrado")
            if not entrepreneur:
                raise UserNotFoundError(f"Emprendedor {session_data['entrepreneur_id']} no encontrado")
            
            # Verificar que están relacionados (si es requerido)
            if session_data.get('require_assignment', True):
                if entrepreneur.assigned_mentor_id != mentor.id:
                    raise BusinessLogicError("El emprendedor no está asignado a este mentor")
            
            # Verificar disponibilidad
            scheduled_at = session_data['scheduled_at']
            duration = session_data.get('duration_minutes', self.default_session_duration)
            
            if not self._check_availability(mentor.user_id, entrepreneur.user_id, scheduled_at, duration):
                raise ConflictError("Conflicto de horarios detectado")
            
            # Verificar límites del mentor
            if not self._check_mentor_session_limits(mentor, scheduled_at):
                raise BusinessLogicError("El mentor ha alcanzado su límite de sesiones para este período")
            
            # Crear sesión
            session = MentorshipSession(
                mentor_id=mentor.id,
                entrepreneur_id=entrepreneur.id,
                title=session_data.get('title', f'Sesión de Mentoría - {entrepreneur.user.get_full_name()}'),
                description=session_data.get('description', ''),
                session_type=session_data.get('type', MENTORSHIP_TYPES.GENERAL),
                scheduled_at=scheduled_at,
                duration_minutes=duration,
                status=MENTORSHIP_STATUS.SCHEDULED,
                agenda=session_data.get('agenda'),
                objectives=session_data.get('objectives'),
                preparation_notes=session_data.get('preparation_notes'),
                location_type=session_data.get('location_type', 'virtual'),
                location_details=session_data.get('location_details'),
                is_recurring=session_data.get('is_recurring', False),
                recurrence_pattern=session_data.get('recurrence_pattern'),
                created_by=created_by,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(session)
            db.session.flush()  # Para obtener el ID
            
            # Crear evento en calendario
            calendar_event = self._create_calendar_event(session)
            if calendar_event:
                session.calendar_event_id = calendar_event.get('id')
                session.meet_link = calendar_event.get('meet_link')
            
            # Crear sesiones recurrentes si aplica
            if session.is_recurring and session.recurrence_pattern:
                self._create_recurring_sessions(session)
            
            db.session.commit()
            
            # Enviar notificaciones
            self._send_session_notifications(session, 'created')
            
            # Programar recordatorios
            self._schedule_session_reminders(session)
            
            # Log de actividad
            self._log_activity(
                user_id=entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.SESSION_SCHEDULED,
                details=f"Sesión programada con {mentor.user.get_full_name()} para {scheduled_at.strftime('%d/%m/%Y %H:%M')}",
                performed_by=created_by
            )
            
            logger.info(f"Sesión creada: {session.id} - {mentor.user.email} con {entrepreneur.user.email}")
            return session
            
        except (ValidationError, UserNotFoundError, BusinessLogicError, ConflictError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creando sesión: {str(e)}")
            raise ServiceError(f"Error interno creando sesión: {str(e)}")

    def update_session_status(self, session_id: int, new_status: str, 
                            updated_by: int = None, notes: str = None) -> bool:
        """
        Actualiza el estado de una sesión de mentoría.
        
        Args:
            session_id: ID de la sesión
            new_status: Nuevo estado
            updated_by: ID del usuario que actualiza
            notes: Notas adicionales
            
        Returns:
            True si se actualizó exitosamente
        """
        try:
            session = self.get_session_by_id(session_id)
            if not session:
                raise UserNotFoundError(f"Sesión {session_id} no encontrada")
            
            # Validar transición de estado
            if not self._is_valid_status_transition(session.status, new_status):
                raise BusinessLogicError(f"Transición de estado inválida: {session.status} -> {new_status}")
            
            old_status = session.status
            session.status = new_status
            session.status_updated_at = datetime.now(timezone.utc)
            session.status_updated_by = updated_by
            
            # Acciones específicas por estado
            if new_status == MENTORSHIP_STATUS.IN_PROGRESS:
                session.started_at = datetime.now(timezone.utc)
                
            elif new_status == MENTORSHIP_STATUS.COMPLETED:
                session.completed_at = datetime.now(timezone.utc)
                session.actual_duration_minutes = self._calculate_actual_duration(session)
                
            elif new_status == MENTORSHIP_STATUS.CANCELLED:
                session.cancelled_at = datetime.now(timezone.utc)
                session.cancellation_reason = notes
                # Liberar slot en calendario
                if session.calendar_event_id:
                    self._cancel_calendar_event(session.calendar_event_id)
                    
            elif new_status == MENTORSHIP_STATUS.RESCHEDULED:
                session.rescheduled_at = datetime.now(timezone.utc)
                session.reschedule_reason = notes
            
            # Actualizar historial de estados
            status_history = session.status_history or []
            status_history.append({
                'from_status': old_status,
                'to_status': new_status,
                'changed_at': datetime.now(timezone.utc).isoformat(),
                'changed_by': updated_by,
                'notes': notes
            })
            session.status_history = status_history
            
            db.session.commit()
            
            # Enviar notificaciones
            self._send_session_notifications(session, 'status_updated', old_status)
            
            # Acciones post-completado
            if new_status == MENTORSHIP_STATUS.COMPLETED:
                self._handle_session_completion(session)
            
            # Log de actividad
            self._log_activity(
                user_id=session.entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.SESSION_STATUS_UPDATED,
                details=f"Estado de sesión cambiado: {old_status} -> {new_status}",
                performed_by=updated_by
            )
            
            logger.info(f"Estado de sesión {session_id} actualizado: {old_status} -> {new_status}")
            return True
            
        except (UserNotFoundError, BusinessLogicError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error actualizando estado de sesión: {str(e)}")
            raise ServiceError(f"Error interno actualizando estado: {str(e)}")

    def reschedule_session(self, session_id: int, new_datetime: datetime, 
                          reason: str = None, rescheduled_by: int = None) -> bool:
        """
        Reprograma una sesión de mentoría.
        
        Args:
            session_id: ID de la sesión
            new_datetime: Nueva fecha y hora
            reason: Motivo de la reprogramación
            rescheduled_by: ID del usuario que reprograma
            
        Returns:
            True si se reprogramó exitosamente
        """
        try:
            session = self.get_session_by_id(session_id)
            if not session:
                raise UserNotFoundError(f"Sesión {session_id} no encontrada")
            
            # Validar que la sesión puede ser reprogramada
            if session.status not in [MENTORSHIP_STATUS.SCHEDULED, MENTORSHIP_STATUS.RESCHEDULED]:
                raise BusinessLogicError("Solo se pueden reprogramar sesiones programadas")
            
            # Validar nueva fecha
            if not validate_future_datetime(new_datetime, hours_ahead=self.min_advance_hours):
                raise ValidationError(f"La sesión debe programarse con al menos {self.min_advance_hours} horas de anticipación")
            
            # Verificar disponibilidad en nueva fecha
            if not self._check_availability(
                session.mentor.user_id, 
                session.entrepreneur.user_id, 
                new_datetime, 
                session.duration_minutes,
                exclude_session_id=session_id
            ):
                raise ConflictError("Conflicto de horarios en la nueva fecha")
            
            # Guardar fecha anterior
            previous_datetime = session.scheduled_at
            
            # Actualizar sesión
            session.scheduled_at = new_datetime
            session.status = MENTORSHIP_STATUS.RESCHEDULED
            session.rescheduled_at = datetime.now(timezone.utc)
            session.reschedule_reason = reason
            session.rescheduled_by = rescheduled_by
            
            # Actualizar historial de reprogramaciones
            reschedule_history = session.reschedule_history or []
            reschedule_history.append({
                'previous_datetime': previous_datetime.isoformat(),
                'new_datetime': new_datetime.isoformat(),
                'rescheduled_at': datetime.now(timezone.utc).isoformat(),
                'rescheduled_by': rescheduled_by,
                'reason': reason
            })
            session.reschedule_history = reschedule_history
            
            # Actualizar evento de calendario
            if session.calendar_event_id:
                self._update_calendar_event(session)
            
            db.session.commit()
            
            # Notificaciones
            self._send_session_notifications(session, 'rescheduled', previous_datetime)
            
            # Actualizar recordatorios
            self._update_session_reminders(session)
            
            # Log de actividad
            self._log_activity(
                user_id=session.entrepreneur.user_id,
                activity_type=ACTIVITY_TYPES.SESSION_RESCHEDULED,
                details=f"Sesión reprogramada de {previous_datetime.strftime('%d/%m/%Y %H:%M')} a {new_datetime.strftime('%d/%m/%Y %H:%M')}",
                performed_by=rescheduled_by
            )
            
            logger.info(f"Sesión {session_id} reprogramada: {previous_datetime} -> {new_datetime}")
            return True
            
        except (UserNotFoundError, ValidationError, BusinessLogicError, ConflictError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error reprogramando sesión: {str(e)}")
            raise ServiceError(f"Error interno reprogramando sesión: {str(e)}")

    # ==================== SISTEMA DE EVALUACIONES ====================

    def submit_session_feedback(self, session_id: int, feedback_data: dict[str, Any], 
                              submitted_by: int) -> bool:
        """
        Envía feedback de una sesión completada.
        
        Args:
            session_id: ID de la sesión
            feedback_data: Datos del feedback
            submitted_by: ID del usuario que envía el feedback
            
        Returns:
            True si se guardó exitosamente
        """
        try:
            session = self.get_session_by_id(session_id)
            if not session:
                raise UserNotFoundError(f"Sesión {session_id} no encontrada")
            
            if session.status != MENTORSHIP_STATUS.COMPLETED:
                raise BusinessLogicError("Solo se puede evaluar sesiones completadas")
            
            # Determinar tipo de feedback (mentor o emprendedor)
            is_mentor_feedback = submitted_by == session.mentor.user_id
            is_entrepreneur_feedback = submitted_by == session.entrepreneur.user_id
            
            if not (is_mentor_feedback or is_entrepreneur_feedback):
                raise PermissionError("Solo el mentor o emprendedor pueden evaluar la sesión")
            
            # Validar datos del feedback
            self._validate_feedback_data(feedback_data)
            
            if is_mentor_feedback:
                # Feedback del mentor sobre el emprendedor
                session.mentor_rating = feedback_data.get('rating')
                session.mentor_feedback = feedback_data.get('comments')
                session.entrepreneur_preparation_rating = feedback_data.get('preparation_rating')
                session.entrepreneur_engagement_rating = feedback_data.get('engagement_rating')
                session.mentor_feedback_submitted_at = datetime.now(timezone.utc)
                session.session_outcome = feedback_data.get('outcome')
                session.next_steps = feedback_data.get('next_steps')
                
            else:
                # Feedback del emprendedor sobre el mentor
                session.entrepreneur_rating = feedback_data.get('rating')
                session.entrepreneur_feedback = feedback_data.get('comments')
                session.mentor_helpfulness_rating = feedback_data.get('helpfulness_rating')
                session.mentor_knowledge_rating = feedback_data.get('knowledge_rating')
                session.entrepreneur_feedback_submitted_at = datetime.now(timezone.utc)
                session.would_recommend_mentor = feedback_data.get('would_recommend')
            
            # Marcar feedback como recibido
            if is_mentor_feedback:
                session.mentor_feedback_received = True
            else:
                session.entrepreneur_feedback_received = True
            
            db.session.commit()
            
            # Actualizar estadísticas del mentor/emprendedor
            self._update_user_ratings(session, is_mentor_feedback)
            
            # Notificación de agradecimiento
            self.notification_service.create_notification(
                user_id=submitted_by,
                type=NOTIFICATION_TYPES.FEEDBACK_RECEIVED,
                title="Gracias por tu feedback",
                message="Tu evaluación de la sesión ha sido registrada exitosamente"
            )
            
            # Si ambos han enviado feedback, enviar notificación de completitud
            if session.mentor_feedback_received and session.entrepreneur_feedback_received:
                self._handle_complete_feedback(session)
            
            # Log de actividad
            feedback_type = "mentor" if is_mentor_feedback else "emprendedor"
            self._log_activity(
                user_id=submitted_by,
                activity_type=ACTIVITY_TYPES.FEEDBACK_SUBMITTED,
                details=f"Feedback enviado como {feedback_type} para sesión {session_id}"
            )
            
            logger.info(f"Feedback recibido para sesión {session_id} de {feedback_type}")
            return True
            
        except (UserNotFoundError, BusinessLogicError, PermissionError, ValidationError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando feedback: {str(e)}")
            raise ServiceError(f"Error interno guardando feedback: {str(e)}")

    # ==================== GESTIÓN DE DISPONIBILIDAD ====================

    def set_mentor_availability(self, mentor_id: int, availability_data: dict[str, Any]) -> bool:
        """
        Establece la disponibilidad de un mentor.
        
        Args:
            mentor_id: ID del mentor
            availability_data: Datos de disponibilidad
            
        Returns:
            True si se estableció exitosamente
        """
        try:
            mentor = self._get_mentor_by_id(mentor_id)
            if not mentor:
                raise UserNotFoundError(f"Mentor {mentor_id} no encontrado")
            
            # Validar datos de disponibilidad
            self._validate_availability_data(availability_data)
            
            # Actualizar disponibilidad
            mentor.availability_schedule = availability_data.get('schedule')
            mentor.timezone = availability_data.get('timezone')
            mentor.max_sessions_per_week = availability_data.get('max_sessions_per_week')
            mentor.max_sessions_per_day = availability_data.get('max_sessions_per_day')
            mentor.preferred_session_duration = availability_data.get('preferred_duration')
            mentor.availability_notes = availability_data.get('notes')
            mentor.availability_updated_at = datetime.now(timezone.utc)
            
            # Bloqueos específicos de fechas
            if 'blocked_dates' in availability_data:
                mentor.blocked_dates = availability_data['blocked_dates']
            
            db.session.commit()
            
            # Notificación
            self.notification_service.create_notification(
                user_id=mentor.user_id,
                type=NOTIFICATION_TYPES.AVAILABILITY_UPDATED,
                title="Disponibilidad actualizada",
                message="Tu disponibilidad para mentoría ha sido actualizada exitosamente"
            )
            
            # Log de actividad
            self._log_activity(
                user_id=mentor.user_id,
                activity_type=ACTIVITY_TYPES.AVAILABILITY_UPDATED,
                details="Disponibilidad de mentoría actualizada"
            )
            
            logger.info(f"Disponibilidad actualizada para mentor {mentor.user.email}")
            return True
            
        except (UserNotFoundError, ValidationError):
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error estableciendo disponibilidad: {str(e)}")
            raise ServiceError(f"Error interno estableciendo disponibilidad: {str(e)}")

    def get_mentor_available_slots(self, mentor_id: int, start_date: datetime, 
                                 end_date: datetime, duration_minutes: int = None) -> list[dict[str, Any]]:
        """
        Obtiene slots disponibles de un mentor.
        
        Args:
            mentor_id: ID del mentor
            start_date: Fecha de inicio
            end_date: Fecha de fin
            duration_minutes: Duración deseada de la sesión
            
        Returns:
            Lista de slots disponibles
        """
        try:
            mentor = self._get_mentor_by_id(mentor_id)
            if not mentor:
                raise UserNotFoundError(f"Mentor {mentor_id} no encontrado")
            
            duration = duration_minutes or mentor.preferred_session_duration or self.default_session_duration
            
            # Obtener horario de disponibilidad del mentor
            schedule = mentor.availability_schedule or self._get_default_schedule()
            
            # Obtener sesiones ya programadas
            existing_sessions = self._get_mentor_sessions_in_period(mentor_id, start_date, end_date)
            
            # Obtener fechas bloqueadas
            blocked_dates = mentor.blocked_dates or []
            
            # Generar slots disponibles
            available_slots = []
            current_date = start_date.date()
            
            while current_date <= end_date.date():
                # Saltar si es fecha bloqueada
                if current_date.isoformat() in blocked_dates:
                    current_date += timedelta(days=1)
                    continue
                
                # Saltar si no es día de trabajo según schedule
                weekday = current_date.strftime('%A').lower()
                if weekday not in schedule:
                    current_date += timedelta(days=1)
                    continue
                
                # Obtener horarios del día
                day_schedule = schedule[weekday]
                if not day_schedule.get('available', False):
                    current_date += timedelta(days=1)
                    continue
                
                # Generar slots para el día
                day_slots = self._generate_day_slots(
                    current_date, 
                    day_schedule, 
                    duration, 
                    existing_sessions,
                    mentor.timezone
                )
                available_slots.extend(day_slots)
                
                current_date += timedelta(days=1)
            
            # Filtrar slots que respeten límites diarios/semanales
            filtered_slots = self._filter_slots_by_limits(available_slots, mentor, existing_sessions)
            
            return filtered_slots
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error obteniendo slots disponibles: {str(e)}")
            raise ServiceError(f"Error interno obteniendo disponibilidad: {str(e)}")

    # ==================== MÉTRICAS Y ANALYTICS ====================

    def get_mentor_metrics(self, mentor_id: int, period_days: int = 30) -> dict[str, Any]:
        """
        Obtiene métricas de un mentor.
        
        Args:
            mentor_id: ID del mentor
            period_days: Período en días
            
        Returns:
            Dict con métricas del mentor
        """
        try:
            mentor = self._get_mentor_by_id(mentor_id)
            if not mentor:
                raise UserNotFoundError(f"Mentor {mentor_id} no encontrado")
            
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=period_days)
            
            # Sesiones en el período
            sessions = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.mentor_id == mentor_id,
                    MentorshipSession.created_at >= start_date
                )
            ).all()
            
            # Métricas básicas
            total_sessions = len(sessions)
            completed_sessions = len([s for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED])
            cancelled_sessions = len([s for s in sessions if s.status == MENTORSHIP_STATUS.CANCELLED])
            
            # Métricas de tiempo
            total_hours = sum([s.actual_duration_minutes or s.duration_minutes for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]) / 60
            avg_session_duration = statistics.mean([s.actual_duration_minutes or s.duration_minutes for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]) if completed_sessions > 0 else 0
            
            # Métricas de calidad
            ratings = [s.entrepreneur_rating for s in sessions if s.entrepreneur_rating is not None]
            avg_rating = statistics.mean(ratings) if ratings else 0
            
            helpfulness_ratings = [s.mentor_helpfulness_rating for s in sessions if s.mentor_helpfulness_rating is not None]
            avg_helpfulness = statistics.mean(helpfulness_ratings) if helpfulness_ratings else 0
            
            knowledge_ratings = [s.mentor_knowledge_rating for s in sessions if s.mentor_knowledge_rating is not None]
            avg_knowledge = statistics.mean(knowledge_ratings) if knowledge_ratings else 0
            
            # Métricas de engagement
            feedback_completion_rate = len([s for s in sessions if s.mentor_feedback_received and s.entrepreneur_feedback_received]) / completed_sessions * 100 if completed_sessions > 0 else 0
            
            # Emprendedores únicos atendidos
            unique_entrepreneurs = len(set([s.entrepreneur_id for s in sessions]))
            
            # Distribución por tipo de sesión
            session_types = defaultdict(int)
            for session in sessions:
                session_types[session.session_type] += 1
            
            # Outcomes de sesiones
            outcomes = defaultdict(int)
            for session in sessions:
                if session.session_outcome:
                    outcomes[session.session_outcome] += 1
            
            return {
                'period_days': period_days,
                'start_date': start_date,
                'end_date': end_date,
                'activity': {
                    'total_sessions': total_sessions,
                    'completed_sessions': completed_sessions,
                    'cancelled_sessions': cancelled_sessions,
                    'completion_rate': round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2),
                    'cancellation_rate': round((cancelled_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2)
                },
                'time': {
                    'total_hours': round(total_hours, 2),
                    'avg_session_duration': round(avg_session_duration, 2),
                    'hours_per_week': round(total_hours / (period_days / 7), 2)
                },
                'quality': {
                    'avg_rating': round(avg_rating, 2),
                    'avg_helpfulness': round(avg_helpfulness, 2),
                    'avg_knowledge': round(avg_knowledge, 2),
                    'feedback_completion_rate': round(feedback_completion_rate, 2)
                },
                'reach': {
                    'unique_entrepreneurs': unique_entrepreneurs,
                    'avg_sessions_per_entrepreneur': round(total_sessions / unique_entrepreneurs, 2) if unique_entrepreneurs > 0 else 0
                },
                'distribution': {
                    'by_session_type': dict(session_types),
                    'by_outcome': dict(outcomes)
                }
            }
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error obteniendo métricas de mentor: {str(e)}")
            raise ServiceError(f"Error interno obteniendo métricas: {str(e)}")

    def get_mentorship_analytics(self, date_from: datetime = None, date_to: datetime = None) -> dict[str, Any]:
        """
        Obtiene analytics generales del sistema de mentoría.
        
        Args:
            date_from: Fecha desde
            date_to: Fecha hasta
            
        Returns:
            Dict con analytics del sistema
        """
        try:
            if not date_from:
                date_from = datetime.now(timezone.utc) - timedelta(days=30)
            if not date_to:
                date_to = datetime.now(timezone.utc)
            
            # Sesiones en el período
            sessions_query = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            )
            
            total_sessions = sessions_query.count()
            completed_sessions = sessions_query.filter(MentorshipSession.status == MENTORSHIP_STATUS.COMPLETED).count()
            cancelled_sessions = sessions_query.filter(MentorshipSession.status == MENTORSHIP_STATUS.CANCELLED).count()
            
            # Métricas de mentores activos
            active_mentors = db.session.query(MentorshipSession.mentor_id).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            ).distinct().count()
            
            # Métricas de emprendedores atendidos
            entrepreneurs_served = db.session.query(MentorshipSession.entrepreneur_id).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            ).distinct().count()
            
            # Horas totales de mentoría
            total_hours_result = db.session.query(
                func.sum(
                    func.coalesce(
                        MentorshipSession.actual_duration_minutes,
                        MentorshipSession.duration_minutes
                    )
                )
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to,
                    MentorshipSession.status == MENTORSHIP_STATUS.COMPLETED
                )
            ).scalar()
            
            total_hours = (total_hours_result or 0) / 60
            
            # Rating promedio
            avg_rating_result = db.session.query(
                func.avg(MentorshipSession.entrepreneur_rating)
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to,
                    MentorshipSession.entrepreneur_rating.isnot(None)
                )
            ).scalar()
            
            avg_rating = float(avg_rating_result) if avg_rating_result else 0
            
            # Distribución por tipo de sesión
            session_types = db.session.query(
                MentorshipSession.session_type,
                func.count(MentorshipSession.id).label('count')
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            ).group_by(MentorshipSession.session_type).all()
            
            # Distribución por outcomes
            outcomes = db.session.query(
                MentorshipSession.session_outcome,
                func.count(MentorshipSession.id).label('count')
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to,
                    MentorshipSession.session_outcome.isnot(None)
                )
            ).group_by(MentorshipSession.session_outcome).all()
            
            # Tendencias mensuales
            monthly_stats = db.session.query(
                extract('year', MentorshipSession.created_at).label('year'),
                extract('month', MentorshipSession.created_at).label('month'),
                func.count(MentorshipSession.id).label('sessions_count'),
                func.count(
                    case([(MentorshipSession.status == MENTORSHIP_STATUS.COMPLETED, 1)])
                ).label('completed_count')
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            ).group_by(
                extract('year', MentorshipSession.created_at),
                extract('month', MentorshipSession.created_at)
            ).order_by('year', 'month').all()
            
            # Top mentores por sesiones
            top_mentors = db.session.query(
                MentorshipSession.mentor_id,
                func.count(MentorshipSession.id).label('sessions_count'),
                func.avg(MentorshipSession.entrepreneur_rating).label('avg_rating')
            ).filter(
                and_(
                    MentorshipSession.created_at >= date_from,
                    MentorshipSession.created_at <= date_to
                )
            ).group_by(MentorshipSession.mentor_id).order_by(desc('sessions_count')).limit(10).all()
            
            return {
                'period': {
                    'start_date': date_from,
                    'end_date': date_to,
                    'days': (date_to - date_from).days
                },
                'overview': {
                    'total_sessions': total_sessions,
                    'completed_sessions': completed_sessions,
                    'cancelled_sessions': cancelled_sessions,
                    'completion_rate': round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2),
                    'active_mentors': active_mentors,
                    'entrepreneurs_served': entrepreneurs_served,
                    'total_hours': round(total_hours, 2),
                    'avg_rating': round(avg_rating, 2)
                },
                'distribution': {
                    'by_session_type': {session_type: count for session_type, count in session_types},
                    'by_outcome': {outcome: count for outcome, count in outcomes if outcome}
                },
                'trends': {
                    'monthly': [
                        {
                            'year': int(year),
                            'month': int(month),
                            'sessions': sessions_count,
                            'completed': completed_count,
                            'completion_rate': round((completed_count / sessions_count * 100) if sessions_count > 0 else 0, 2)
                        }
                        for year, month, sessions_count, completed_count in monthly_stats
                    ]
                },
                'top_mentors': [
                    {
                        'mentor_id': mentor_id,
                        'sessions_count': sessions_count,
                        'avg_rating': round(float(avg_rating), 2) if avg_rating else None
                    }
                    for mentor_id, sessions_count, avg_rating in top_mentors
                ]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo analytics de mentoría: {str(e)}")
            raise ServiceError(f"Error interno obteniendo analytics: {str(e)}")

    # ==================== CONSULTAS Y BÚSQUEDAS ====================

    def get_session_by_id(self, session_id: int, include_relationships: bool = False) -> Optional[MentorshipSession]:
        """Obtiene sesión por ID."""
        try:
            query = MentorshipSession.query.filter_by(id=session_id)
            
            if include_relationships:
                query = query.options(
                    joinedload(MentorshipSession.mentor).joinedload(Ally.user),
                    joinedload(MentorshipSession.entrepreneur).joinedload(Entrepreneur.user)
                )
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error obteniendo sesión por ID {session_id}: {str(e)}")
            return None

    def search_sessions(self, 
                       mentor_id: int = None,
                       entrepreneur_id: int = None,
                       status: str = None,
                       session_type: str = None,
                       date_from: datetime = None,
                       date_to: datetime = None,
                       page: int = 1,
                       per_page: int = 20,
                       sort_by: str = 'scheduled_at',
                       sort_order: str = 'desc') -> dict[str, Any]:
        """
        Búsqueda avanzada de sesiones de mentoría.
        
        Args:
            mentor_id: ID del mentor
            entrepreneur_id: ID del emprendedor
            status: Estado de la sesión
            session_type: Tipo de sesión
            date_from: Fecha desde
            date_to: Fecha hasta
            page: Página actual
            per_page: Elementos por página
            sort_by: Campo para ordenar
            sort_order: Orden (asc/desc)
            
        Returns:
            Dict con sesiones y metadatos
        """
        try:
            query = MentorshipSession.query
            
            # Filtros
            if mentor_id:
                query = query.filter(MentorshipSession.mentor_id == mentor_id)
            
            if entrepreneur_id:
                query = query.filter(MentorshipSession.entrepreneur_id == entrepreneur_id)
            
            if status:
                query = query.filter(MentorshipSession.status == status)
            
            if session_type:
                query = query.filter(MentorshipSession.session_type == session_type)
            
            if date_from:
                query = query.filter(MentorshipSession.scheduled_at >= date_from)
            
            if date_to:
                query = query.filter(MentorshipSession.scheduled_at <= date_to)
            
            # Ordenamiento
            sort_column = getattr(MentorshipSession, sort_by, MentorshipSession.scheduled_at)
            if sort_order.lower() == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Incluir relaciones para evitar N+1 queries
            query = query.options(
                joinedload(MentorshipSession.mentor).joinedload(Ally.user),
                joinedload(MentorshipSession.entrepreneur).joinedload(Entrepreneur.user)
            )
            
            # Paginación
            pagination = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'sessions': pagination.items,
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
            logger.error(f"Error en búsqueda de sesiones: {str(e)}")
            raise ServiceError(f"Error interno en búsqueda: {str(e)}")

    # ==================== MÉTODOS PRIVADOS ====================

    def _validate_session_data(self, data: dict[str, Any]) -> None:
        """Valida datos de sesión."""
        required_fields = ['mentor_id', 'entrepreneur_id', 'scheduled_at']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Campo requerido: {field}")
        
        # Validar fecha futura
        if not validate_future_datetime(data['scheduled_at'], hours_ahead=self.min_advance_hours):
            raise ValidationError(f"La sesión debe programarse con al menos {self.min_advance_hours} horas de anticipación")
        
        # Validar duración
        duration = data.get('duration_minutes', self.default_session_duration)
        if not validate_session_duration(duration, self.min_session_duration, self.max_session_duration):
            raise ValidationError(f"Duración debe estar entre {self.min_session_duration} y {self.max_session_duration} minutos")

    def _validate_feedback_data(self, data: dict[str, Any]) -> None:
        """Valida datos de feedback."""
        if 'rating' in data:
            rating = data['rating']
            if rating is not None and (rating < 1 or rating > 5):
                raise ValidationError("Rating debe estar entre 1 y 5")

    def _validate_availability_data(self, data: dict[str, Any]) -> None:
        """Valida datos de disponibilidad."""
        if 'schedule' in data:
            schedule = data['schedule']
            if not isinstance(schedule, dict):
                raise ValidationError("Schedule debe ser un diccionario")
        
        if 'max_sessions_per_week' in data:
            max_sessions = data['max_sessions_per_week']
            if max_sessions is not None and (max_sessions < 1 or max_sessions > 50):
                raise ValidationError("Máximo de sesiones por semana debe estar entre 1 y 50")

    def _get_mentor_by_id(self, mentor_id: int) -> Optional[Ally]:
        """Obtiene mentor por ID."""
        return Ally.query.get(mentor_id)

    def _get_entrepreneur_by_id(self, entrepreneur_id: int) -> Optional[Entrepreneur]:
        """Obtiene emprendedor por ID."""
        return Entrepreneur.query.get(entrepreneur_id)

    def _check_availability(self, mentor_user_id: int, entrepreneur_user_id: int, 
                          scheduled_at: datetime, duration_minutes: int, 
                          exclude_session_id: int = None) -> bool:
        """Verifica disponibilidad de horario."""
        end_time = scheduled_at + timedelta(minutes=duration_minutes)
        
        # Construir query base
        query = MentorshipSession.query.filter(
            and_(
                or_(
                    MentorshipSession.mentor_id == mentor_user_id,
                    MentorshipSession.entrepreneur_id == entrepreneur_user_id
                ),
                MentorshipSession.status.in_([
                    MENTORSHIP_STATUS.SCHEDULED, 
                    MENTORSHIP_STATUS.IN_PROGRESS,
                    MENTORSHIP_STATUS.RESCHEDULED
                ]),
                or_(
                    and_(
                        MentorshipSession.scheduled_at <= scheduled_at,
                        MentorshipSession.scheduled_at + func.interval(MentorshipSession.duration_minutes, 'minute') > scheduled_at
                    ),
                    and_(
                        MentorshipSession.scheduled_at < end_time,
                        MentorshipSession.scheduled_at >= scheduled_at
                    )
                )
            )
        )
        
        # Excluir sesión específica si se proporciona
        if exclude_session_id:
            query = query.filter(MentorshipSession.id != exclude_session_id)
        
        conflicting_sessions = query.count()
        return conflicting_sessions == 0

    def _log_activity(self, user_id: int, activity_type: str, details: str, performed_by: int = None) -> None:
        """Registra actividad en el log."""
        try:
            activity = ActivityLog(
                user_id=user_id,
                activity_type=activity_type,
                details=details,
                performed_by=performed_by or user_id,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(activity)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error registrando actividad: {str(e)}")

    def _send_session_notifications(self, session: MentorshipSession, event_type: str, 
                                  previous_data: Any = None) -> None:
        """Envía notificaciones relacionadas con sesiones."""
        try:
            if event_type == 'created':
                # Notificar al mentor
                self.notification_service.create_notification(
                    user_id=session.mentor.user_id,
                    type=NOTIFICATION_TYPES.SESSION_SCHEDULED,
                    title="Nueva sesión programada",
                    message=f"Sesión programada con {session.entrepreneur.user.get_full_name()} para {session.scheduled_at.strftime('%d/%m/%Y %H:%M')}"
                )
                
                # Notificar al emprendedor
                self.notification_service.create_notification(
                    user_id=session.entrepreneur.user_id,
                    type=NOTIFICATION_TYPES.SESSION_SCHEDULED,
                    title="Sesión de mentoría programada",
                    message=f"Sesión con {session.mentor.user.get_full_name()} programada para {session.scheduled_at.strftime('%d/%m/%Y %H:%M')}"
                )
                
        except Exception as e:
            logger.error(f"Error enviando notificaciones: {str(e)}")

    def _create_calendar_event(self, session: MentorshipSession) -> Optional[dict[str, Any]]:
        """Crea evento en Google Calendar."""
        try:
            event_data = {
                'summary': session.title,
                'description': session.description,
                'start_time': session.scheduled_at,
                'duration_minutes': session.duration_minutes,
                'attendees': [
                    session.mentor.user.email,
                    session.entrepreneur.user.email
                ]
            }
            
            return self.calendar_service.create_event(event_data)
            
        except Exception as e:
            logger.error(f"Error creando evento de calendario: {str(e)}")
            return None

    def _update_calendar_event(self, session: MentorshipSession) -> bool:
        """Actualiza evento en Google Calendar."""
        try:
            if not session.calendar_event_id:
                return False
                
            event_data = {
                'summary': session.title,
                'description': session.description,
                'start_time': session.scheduled_at,
                'duration_minutes': session.duration_minutes
            }
            
            return self.calendar_service.update_event(session.calendar_event_id, event_data)
            
        except Exception as e:
            logger.error(f"Error actualizando evento de calendario: {str(e)}")
            return False

    def _cancel_calendar_event(self, event_id: str) -> bool:
        """Cancela evento en Google Calendar."""
        try:
            return self.calendar_service.cancel_event(event_id)
        except Exception as e:
            logger.error(f"Error cancelando evento de calendario: {str(e)}")
            return False

    def _create_recurring_sessions(self, base_session: MentorshipSession) -> list[MentorshipSession]:
        """Crea sesiones recurrentes basadas en el patrón."""
        try:
            if not base_session.recurrence_pattern:
                return []
            
            pattern = base_session.recurrence_pattern
            recurring_sessions = []
            
            # Determinar fechas de recurrencia
            recurrence_dates = self._calculate_recurrence_dates(
                base_session.scheduled_at,
                pattern
            )
            
            for date in recurrence_dates:
                # Verificar disponibilidad
                if self._check_availability(
                    base_session.mentor.user_id,
                    base_session.entrepreneur.user_id,
                    date,
                    base_session.duration_minutes
                ):
                    # Crear sesión recurrente
                    recurring_session = MentorshipSession(
                        mentor_id=base_session.mentor_id,
                        entrepreneur_id=base_session.entrepreneur_id,
                        title=base_session.title,
                        description=base_session.description,
                        session_type=base_session.session_type,
                        scheduled_at=date,
                        duration_minutes=base_session.duration_minutes,
                        status=MENTORSHIP_STATUS.SCHEDULED,
                        is_recurring=True,
                        parent_session_id=base_session.id,
                        created_at=datetime.now(timezone.utc)
                    )
                    
                    db.session.add(recurring_session)
                    recurring_sessions.append(recurring_session)
            
            return recurring_sessions
            
        except Exception as e:
            logger.error(f"Error creando sesiones recurrentes: {str(e)}")
            return []

    def _calculate_recurrence_dates(self, start_date: datetime, pattern: dict[str, Any]) -> list[datetime]:
        """Calcula fechas de recurrencia."""
        dates = []
        frequency = pattern.get('frequency', 'weekly')  # weekly, biweekly, monthly
        count = pattern.get('count', 4)  # número de recurrencias
        
        current_date = start_date
        
        for i in range(1, count + 1):
            if frequency == 'weekly':
                current_date = start_date + timedelta(weeks=i)
            elif frequency == 'biweekly':
                current_date = start_date + timedelta(weeks=i*2)
            elif frequency == 'monthly':
                # Aproximación para mensual
                current_date = start_date + timedelta(days=30*i)
            
            dates.append(current_date)
        
        return dates

    def _schedule_session_reminders(self, session: MentorshipSession) -> None:
        """Programa recordatorios automáticos para la sesión."""
        try:
            # Recordatorio 24 horas antes
            reminder_24h = session.scheduled_at - timedelta(hours=24)
            if reminder_24h > datetime.now(timezone.utc):
                self._schedule_reminder(session, reminder_24h, '24 horas')
            
            # Recordatorio 1 hora antes
            reminder_1h = session.scheduled_at - timedelta(hours=1)
            if reminder_1h > datetime.now(timezone.utc):
                self._schedule_reminder(session, reminder_1h, '1 hora')
            
        except Exception as e:
            logger.error(f"Error programando recordatorios: {str(e)}")

    def _schedule_reminder(self, session: MentorshipSession, remind_at: datetime, time_before: str) -> None:
        """Programa un recordatorio específico."""
        try:
            # En una implementación real, esto se haría con Celery
            # Por ahora solo creamos notificaciones programadas
            
            reminder_data = {
                'session_id': session.id,
                'remind_at': remind_at,
                'time_before': time_before,
                'mentor_user_id': session.mentor.user_id,
                'entrepreneur_user_id': session.entrepreneur.user_id
            }
            
            # Aquí se programaría la tarea con Celery
            # self.celery_app.send_task('send_session_reminder', args=[reminder_data], eta=remind_at)
            
        except Exception as e:
            logger.error(f"Error programando recordatorio: {str(e)}")

    def _update_session_reminders(self, session: MentorshipSession) -> None:
        """Actualiza recordatorios cuando se reprograma una sesión."""
        try:
            # Cancelar recordatorios existentes
            # self.celery_app.control.revoke(task_id, terminate=True)
            
            # Crear nuevos recordatorios
            self._schedule_session_reminders(session)
            
        except Exception as e:
            logger.error(f"Error actualizando recordatorios: {str(e)}")

    def _is_valid_status_transition(self, current_status: str, new_status: str) -> bool:
        """Valida si la transición de estado es válida."""
        valid_transitions = {
            MENTORSHIP_STATUS.SCHEDULED: [
                MENTORSHIP_STATUS.IN_PROGRESS,
                MENTORSHIP_STATUS.CANCELLED,
                MENTORSHIP_STATUS.RESCHEDULED
            ],
            MENTORSHIP_STATUS.RESCHEDULED: [
                MENTORSHIP_STATUS.IN_PROGRESS,
                MENTORSHIP_STATUS.CANCELLED,
                MENTORSHIP_STATUS.SCHEDULED
            ],
            MENTORSHIP_STATUS.IN_PROGRESS: [
                MENTORSHIP_STATUS.COMPLETED,
                MENTORSHIP_STATUS.CANCELLED
            ],
            MENTORSHIP_STATUS.COMPLETED: [],  # Estado final
            MENTORSHIP_STATUS.CANCELLED: []   # Estado final
        }
        
        return new_status in valid_transitions.get(current_status, [])

    def _calculate_actual_duration(self, session: MentorshipSession) -> Optional[int]:
        """Calcula la duración real de la sesión."""
        if session.started_at and session.completed_at:
            delta = session.completed_at - session.started_at
            return int(delta.total_seconds() / 60)
        return None

    def _handle_session_completion(self, session: MentorshipSession) -> None:
        """Maneja acciones post-completado de sesión."""
        try:
            # Solicitar evaluaciones si no se han enviado
            if not session.mentor_feedback_received:
                self._request_feedback(session, 'mentor')
            
            if not session.entrepreneur_feedback_received:
                self._request_feedback(session, 'entrepreneur')
            
            # Actualizar contadores
            self._update_completion_counters(session)
            
        except Exception as e:
            logger.error(f"Error manejando completado de sesión: {str(e)}")

    def _request_feedback(self, session: MentorshipSession, user_type: str) -> None:
        """Solicita feedback a mentor o emprendedor."""
        try:
            if user_type == 'mentor':
                user_id = session.mentor.user_id
                message = f"Por favor evalúa tu sesión con {session.entrepreneur.user.get_full_name()}"
            else:
                user_id = session.entrepreneur.user_id
                message = f"Por favor evalúa tu sesión con {session.mentor.user.get_full_name()}"
            
            self.notification_service.create_notification(
                user_id=user_id,
                type=NOTIFICATION_TYPES.FEEDBACK_REQUEST,
                title="Evaluación de sesión pendiente",
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error solicitando feedback: {str(e)}")

    def _update_completion_counters(self, session: MentorshipSession) -> None:
        """Actualiza contadores de sesiones completadas."""
        try:
            # Actualizar contador del mentor
            mentor = session.mentor
            mentor.completed_sessions_count = (mentor.completed_sessions_count or 0) + 1
            mentor.total_mentoring_hours = (mentor.total_mentoring_hours or 0) + (session.actual_duration_minutes or session.duration_minutes) / 60
            
            # Actualizar contador del emprendedor
            entrepreneur = session.entrepreneur
            entrepreneur.completed_sessions_count = (entrepreneur.completed_sessions_count or 0) + 1
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error actualizando contadores: {str(e)}")

    def _handle_complete_feedback(self, session: MentorshipSession) -> None:
        """Maneja cuando ambos usuarios han enviado feedback."""
        try:
            # Calcular score promedio
            ratings = [r for r in [session.mentor_rating, session.entrepreneur_rating] if r is not None]
            if ratings:
                session.avg_rating = statistics.mean(ratings)
            
            # Marcar como feedback completo
            session.feedback_complete = True
            session.feedback_completed_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            # Notificar a ambos usuarios
            completion_message = "Ambas evaluaciones han sido completadas. ¡Gracias por el feedback!"
            
            self.notification_service.create_notification(
                user_id=session.mentor.user_id,
                type=NOTIFICATION_TYPES.FEEDBACK_COMPLETE,
                title="Evaluaciones completadas",
                message=completion_message
            )
            
            self.notification_service.create_notification(
                user_id=session.entrepreneur.user_id,
                type=NOTIFICATION_TYPES.FEEDBACK_COMPLETE,
                title="Evaluaciones completadas",
                message=completion_message
            )
            
        except Exception as e:
            logger.error(f"Error manejando feedback completo: {str(e)}")

    def _update_user_ratings(self, session: MentorshipSession, is_mentor_feedback: bool) -> None:
        """Actualiza ratings promedio de usuarios."""
        try:
            if is_mentor_feedback:
                # Actualizar rating del emprendedor
                entrepreneur = session.entrepreneur
                ratings = [s.mentor_rating for s in entrepreneur.mentorship_sessions 
                          if s.mentor_rating is not None and s.status == MENTORSHIP_STATUS.COMPLETED]
                if ratings:
                    entrepreneur.avg_mentor_rating = statistics.mean(ratings)
            else:
                # Actualizar rating del mentor
                mentor = session.mentor
                ratings = [s.entrepreneur_rating for s in mentor.mentorship_sessions 
                          if s.entrepreneur_rating is not None and s.status == MENTORSHIP_STATUS.COMPLETED]
                if ratings:
                    mentor.avg_entrepreneur_rating = statistics.mean(ratings)
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Error actualizando ratings: {str(e)}")

    def _check_mentor_session_limits(self, mentor: Ally, scheduled_at: datetime) -> bool:
        """Verifica si el mentor puede tomar más sesiones."""
        try:
            # Verificar límite diario
            if mentor.max_sessions_per_day:
                day_start = scheduled_at.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                sessions_today = MentorshipSession.query.filter(
                    and_(
                        MentorshipSession.mentor_id == mentor.id,
                        MentorshipSession.scheduled_at >= day_start,
                        MentorshipSession.scheduled_at < day_end,
                        MentorshipSession.status.in_([
                            MENTORSHIP_STATUS.SCHEDULED,
                            MENTORSHIP_STATUS.IN_PROGRESS,
                            MENTORSHIP_STATUS.RESCHEDULED
                        ])
                    )
                ).count()
                
                if sessions_today >= mentor.max_sessions_per_day:
                    return False
            
            # Verificar límite semanal
            if mentor.max_sessions_per_week:
                week_start = scheduled_at - timedelta(days=scheduled_at.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=7)
                
                sessions_this_week = MentorshipSession.query.filter(
                    and_(
                        MentorshipSession.mentor_id == mentor.id,
                        MentorshipSession.scheduled_at >= week_start,
                        MentorshipSession.scheduled_at < week_end,
                        MentorshipSession.status.in_([
                            MENTORSHIP_STATUS.SCHEDULED,
                            MENTORSHIP_STATUS.IN_PROGRESS,
                            MENTORSHIP_STATUS.RESCHEDULED
                        ])
                    )
                ).count()
                
                if sessions_this_week >= mentor.max_sessions_per_week:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verificando límites de mentor: {str(e)}")
            return False

    def _get_default_schedule(self) -> dict[str, Any]:
        """Obtiene horario por defecto."""
        return {
            'monday': {'available': True, 'start': '09:00', 'end': '17:00'},
            'tuesday': {'available': True, 'start': '09:00', 'end': '17:00'},
            'wednesday': {'available': True, 'start': '09:00', 'end': '17:00'},
            'thursday': {'available': True, 'start': '09:00', 'end': '17:00'},
            'friday': {'available': True, 'start': '09:00', 'end': '17:00'},
            'saturday': {'available': False},
            'sunday': {'available': False}
        }

    def _get_mentor_sessions_in_period(self, mentor_id: int, start_date: datetime, end_date: datetime) -> list[MentorshipSession]:
        """Obtiene sesiones del mentor en un período."""
        return MentorshipSession.query.filter(
            and_(
                MentorshipSession.mentor_id == mentor_id,
                MentorshipSession.scheduled_at >= start_date,
                MentorshipSession.scheduled_at <= end_date,
                MentorshipSession.status.in_([
                    MENTORSHIP_STATUS.SCHEDULED,
                    MENTORSHIP_STATUS.IN_PROGRESS,
                    MENTORSHIP_STATUS.RESCHEDULED
                ])
            )
        ).all()

    def _generate_day_slots(self, date: datetime.date, day_schedule: dict[str, Any], 
                          duration: int, existing_sessions: list[MentorshipSession],
                          timezone: str = None) -> list[dict[str, Any]]:
        """Genera slots disponibles para un día específico."""
        try:
            slots = []
            
            if not day_schedule.get('available', False):
                return slots
            
            # Obtener horarios de inicio y fin
            start_time = datetime.strptime(day_schedule['start'], '%H:%M').time()
            end_time = datetime.strptime(day_schedule['end'], '%H:%M').time()
            
            # Crear datetime para el día
            current_slot = datetime.combine(date, start_time)
            day_end = datetime.combine(date, end_time)
            
            # Generar slots cada 30 minutos
            slot_interval = timedelta(minutes=30)
            
            while current_slot + timedelta(minutes=duration) <= day_end:
                # Verificar si el slot está libre
                slot_end = current_slot + timedelta(minutes=duration)
                
                is_free = True
                for session in existing_sessions:
                    session_end = session.scheduled_at + timedelta(minutes=session.duration_minutes)
                    
                    # Verificar solapamiento
                    if (current_slot < session_end and slot_end > session.scheduled_at):
                        is_free = False
                        break
                
                if is_free:
                    slots.append({
                        'datetime': current_slot,
                        'duration_minutes': duration,
                        'available': True
                    })
                
                current_slot += slot_interval
            
            return slots
            
        except Exception as e:
            logger.error(f"Error generando slots del día: {str(e)}")
            return []

    def _filter_slots_by_limits(self, slots: list[dict[str, Any]], mentor: Ally, 
                               existing_sessions: list[MentorshipSession]) -> list[dict[str, Any]]:
        """Filtra slots considerando límites del mentor."""
        try:
            filtered_slots = []
            
            for slot in slots:
                slot_date = slot['datetime']
                
                # Verificar límite diario
                if mentor.max_sessions_per_day:
                    day_start = slot_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)
                    
                    sessions_that_day = len([
                        s for s in existing_sessions
                        if day_start <= s.scheduled_at < day_end
                    ])
                    
                    if sessions_that_day >= mentor.max_sessions_per_day:
                        continue
                
                # Verificar límite semanal
                if mentor.max_sessions_per_week:
                    week_start = slot_date - timedelta(days=slot_date.weekday())
                    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_end = week_start + timedelta(days=7)
                    
                    sessions_that_week = len([
                        s for s in existing_sessions
                        if week_start <= s.scheduled_at < week_end
                    ])
                    
                    if sessions_that_week >= mentor.max_sessions_per_week:
                        continue
                
                filtered_slots.append(slot)
            
            return filtered_slots
            
        except Exception as e:
            logger.error(f"Error filtrando slots: {str(e)}")
            return slots

    def _get_mentorship_summary(self, entrepreneur: Entrepreneur) -> dict[str, Any]:
        """Obtiene resumen de mentoría del emprendedor."""
        try:
            sessions = entrepreneur.mentorship_sessions or []
            
            return {
                'total_sessions': len(sessions),
                'completed_sessions': len([s for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]),
                'upcoming_sessions': len([s for s in sessions if s.status == MENTORSHIP_STATUS.SCHEDULED]),
                'avg_rating_given': statistics.mean([s.entrepreneur_rating for s in sessions if s.entrepreneur_rating]) if sessions else 0,
                'avg_rating_received': statistics.mean([s.mentor_rating for s in sessions if s.mentor_rating]) if sessions else 0,
                'total_hours': sum([s.actual_duration_minutes or s.duration_minutes for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]) / 60,
                'has_active_mentor': entrepreneur.assigned_mentor_id is not None
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen de mentoría: {str(e)}")
            return {}

    def _get_project_phases_distribution(self, projects: List) -> dict[str, int]:
        """Obtiene distribución de fases de proyectos."""
        distribution = defaultdict(int)
        for project in projects:
            if hasattr(project, 'current_phase') and project.current_phase:
                distribution[project.current_phase] += 1
        return dict(distribution)

    def _calculate_task_metrics(self, entrepreneur: Entrepreneur) -> dict[str, Any]:
        """Calcula métricas de tareas del emprendedor."""
        try:
            # Esta función se implementaría en el TaskService
            # Por ahora retornamos métricas básicas
            return {
                'total_tasks': 0,
                'completed_tasks': 0,
                'pending_tasks': 0,
                'completion_rate': 0
            }
        except Exception as e:
            logger.error(f"Error calculando métricas de tareas: {str(e)}")
            return {}

    def _calculate_document_metrics(self, entrepreneur: Entrepreneur) -> dict[str, Any]:
        """Calcula métricas de documentos del emprendedor."""
        try:
            # Esta función se implementaría en el DocumentService
            # Por ahora retornamos métricas básicas
            return {
                'total_documents': 0,
                'recent_uploads': 0,
                'document_types': {}
            }
        except Exception as e:
            logger.error(f"Error calculando métricas de documentos: {str(e)}")
            return {}

    def _calculate_overall_score(self, profile_completion: Dict, project_metrics: Dict,
                               mentorship_metrics: Dict, task_metrics: Dict,
                               document_metrics: Dict) -> float:
        """Calcula score general del emprendedor."""
        try:
            # Pesos para cada métrica
            weights = {
                'profile': 0.2,
                'projects': 0.3,
                'mentorship': 0.25,
                'tasks': 0.15,
                'documents': 0.1
            }
            
            # Scores individuales
            profile_score = profile_completion.get('percentage', 0)
            project_score = project_metrics.get('avg_completion', 0)
            mentorship_score = min(mentorship_metrics.get('completed_sessions', 0) * 20, 100)  # Max 5 sesiones = 100%
            task_score = task_metrics.get('completion_rate', 0)
            document_score = min(document_metrics.get('total_documents', 0) * 10, 100)  # Max 10 docs = 100%
            
            # Score ponderado
            overall_score = (
                profile_score * weights['profile'] +
                project_score * weights['projects'] +
                mentorship_score * weights['mentorship'] +
                task_score * weights['tasks'] +
                document_score * weights['documents']
            )
            
            return round(overall_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculando score general: {str(e)}")
            return 0.0

    def _generate_progress_recommendations(self, entrepreneur: Entrepreneur, overall_score: float) -> list[str]:
        """Genera recomendaciones basadas en el progreso."""
        recommendations = []
        
        try:
            # Recomendaciones basadas en score
            if overall_score < 30:
                recommendations.append("Completa tu perfil para acceder a más recursos")
                recommendations.append("Programa una sesión con tu mentor")
            elif overall_score < 60:
                recommendations.append("Continúa trabajando en tus proyectos")
                recommendations.append("Mantén comunicación regular con tu mentor")
            elif overall_score < 80:
                recommendations.append("Considera aplicar a programas avanzados")
                recommendations.append("Comparte tu progreso con la comunidad")
            else:
                recommendations.append("¡Excelente progreso! Considera mentorear a otros")
                recommendations.append("Explora oportunidades de funding")
            
            # Recomendaciones específicas
            if not entrepreneur.assigned_mentor_id:
                recommendations.append("Solicita asignación de mentor")
            
            if not entrepreneur.projects:
                recommendations.append("Crea tu primer proyecto")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {str(e)}")
            return ["Continúa trabajando en tu emprendimiento"]

    def _count_messages_sent(self, user_id: int, start_date: datetime, end_date: datetime) -> int:
        """Cuenta mensajes enviados por el usuario en un período."""
        try:
            # Esta función se implementaría con el MessageService
            # Por ahora retornamos 0
            return 0
        except Exception as e:
            logger.error(f"Error contando mensajes: {str(e)}")
            return 0

    def _calculate_engagement_score(self, sessions: int, tasks: int, logins: int, 
                                  messages: int, period_days: int) -> float:
        """Calcula score de engagement."""
        try:
            # Normalizar métricas por período
            sessions_per_week = sessions / (period_days / 7)
            tasks_per_week = tasks / (period_days / 7)
            logins_per_week = logins / (period_days / 7)
            messages_per_week = messages / (period_days / 7)
            
            # Calcular score (0-100)
            engagement_score = min(
                sessions_per_week * 25 +      # Max 1 sesión/semana = 25 puntos
                tasks_per_week * 10 +         # Max 2.5 tareas/semana = 25 puntos
                min(logins_per_week * 5, 25) + # Max 5 logins/semana = 25 puntos
                min(messages_per_week * 2.5, 25), # Max 10 mensajes/semana = 25 puntos
                100
            )
            
            return round(engagement_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculando engagement: {str(e)}")
            return 0.0

    # ==================== MÉTODOS DE REPORTES ====================

    def generate_mentorship_report(self, mentor_id: int = None, entrepreneur_id: int = None, 
                                 period_days: int = 30) -> dict[str, Any]:
        """
        Genera reporte especializado de mentoría.
        
        Args:
            mentor_id: ID del mentor (opcional)
            entrepreneur_id: ID del emprendedor (opcional)
            period_days: Período en días
            
        Returns:
            Dict con datos del reporte
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=period_days)
            
            # Base query
            query = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.created_at >= start_date,
                    MentorshipSession.created_at <= end_date
                )
            )
            
            # Filtros específicos
            if mentor_id:
                query = query.filter(MentorshipSession.mentor_id == mentor_id)
            if entrepreneur_id:
                query = query.filter(MentorshipSession.entrepreneur_id == entrepreneur_id)
            
            sessions = query.all()
            
            # Métricas generales
            report_data = {
                'period': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'days': period_days
                },
                'summary': {
                    'total_sessions': len(sessions),
                    'completed_sessions': len([s for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]),
                    'cancelled_sessions': len([s for s in sessions if s.status == MENTORSHIP_STATUS.CANCELLED]),
                    'total_hours': sum([s.actual_duration_minutes or s.duration_minutes for s in sessions if s.status == MENTORSHIP_STATUS.COMPLETED]) / 60
                }
            }
            
            # Métricas específicas por tipo de reporte
            if mentor_id:
                mentor_metrics = self.get_mentor_metrics(mentor_id, period_days)
                report_data['mentor_metrics'] = mentor_metrics
            
            if entrepreneur_id:
                entrepreneur = self._get_entrepreneur_by_id(entrepreneur_id)
                if entrepreneur:
                    mentorship_summary = self._get_mentorship_summary(entrepreneur)
                    report_data['entrepreneur_metrics'] = mentorship_summary
            
            # Distribución de datos
            report_data['distribution'] = {
                'by_type': defaultdict(int),
                'by_outcome': defaultdict(int),
                'by_rating': defaultdict(int)
            }
            
            for session in sessions:
                if session.session_type:
                    report_data['distribution']['by_type'][session.session_type] += 1
                if session.session_outcome:
                    report_data['distribution']['by_outcome'][session.session_outcome] += 1
                if session.entrepreneur_rating:
                    rating_bucket = f"{int(session.entrepreneur_rating)}-stars"
                    report_data['distribution']['by_rating'][rating_bucket] += 1
            
            # Convertir defaultdict a dict regular
            report_data['distribution'] = {
                key: dict(value) for key, value in report_data['distribution'].items()
            }
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generando reporte de mentoría: {str(e)}")
            raise ServiceError(f"Error interno generando reporte: {str(e)}")

    # ==================== MÉTODOS DE LIMPIEZA Y MANTENIMIENTO ====================

    def cleanup_expired_sessions(self) -> int:
        """
        Limpia sesiones vencidas que no fueron completadas.
        
        Returns:
            Número de sesiones limpiadas
        """
        try:
            # Sesiones que debieron haber ocurrido hace más de 24 horas y siguen programadas
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            expired_sessions = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.scheduled_at < cutoff_time,
                    MentorshipSession.status.in_([
                        MENTORSHIP_STATUS.SCHEDULED,
                        MENTORSHIP_STATUS.RESCHEDULED
                    ])
                )
            ).all()
            
            cleaned_count = 0
            for session in expired_sessions:
                # Marcar como no realizada
                session.status = MENTORSHIP_STATUS.NO_SHOW
                session.status_updated_at = datetime.now(timezone.utc)
                
                # Cancelar evento de calendario si existe
                if session.calendar_event_id:
                    self._cancel_calendar_event(session.calendar_event_id)
                
                cleaned_count += 1
            
            if cleaned_count > 0:
                db.session.commit()
                logger.info(f"Sesiones vencidas limpiadas: {cleaned_count}")
            
            return cleaned_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error limpiando sesiones vencidas: {str(e)}")
            return 0

    def send_pending_feedback_reminders(self) -> int:
        """
        Envía recordatorios para feedback pendiente.
        
        Returns:
            Número de recordatorios enviados
        """
        try:
            # Sesiones completadas hace más de 24 horas sin feedback
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            sessions_pending_feedback = MentorshipSession.query.filter(
                and_(
                    MentorshipSession.status == MENTORSHIP_STATUS.COMPLETED,
                    MentorshipSession.completed_at < cutoff_time,
                    or_(
                        MentorshipSession.mentor_feedback_received == False,
                        MentorshipSession.entrepreneur_feedback_received == False
                    )
                )
            ).all()
            
            reminders_sent = 0
            for session in sessions_pending_feedback:
                # Recordatorio al mentor si no ha dado feedback
                if not session.mentor_feedback_received:
                    self._request_feedback(session, 'mentor')
                    reminders_sent += 1
                
                # Recordatorio al emprendedor si no ha dado feedback
                if not session.entrepreneur_feedback_received:
                    self._request_feedback(session, 'entrepreneur')
                    reminders_sent += 1
            
            if reminders_sent > 0:
                logger.info(f"Recordatorios de feedback enviados: {reminders_sent}")
            
            return reminders_sent
            
        except Exception as e:
            logger.error(f"Error enviando recordatorios de feedback: {str(e)}")
            return 0