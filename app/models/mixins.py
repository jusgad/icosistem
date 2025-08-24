"""
Mixins especializados para el ecosistema de emprendimiento.
Este módulo proporciona mixins avanzados que añaden funcionalidades específicas a los modelos.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
from flask import current_app, url_for
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, event, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import validates
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from app.extensions import db, cache
from app.core import CACHE_TIMEOUT_SHORT, CACHE_TIMEOUT_MEDIUM
from .base import JSONType

# Configurar logger para mixins
mixins_logger = logging.getLogger('ecosistema.mixins')


# ====================================
# MIXINS BASE
# ====================================

class TimestampMixin:
    """Mixin que añade campos de timestamp automáticos."""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.utcnow, nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    """Mixin que añade funcionalidad de soft delete."""
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True)
    
    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)
    
    def soft_delete(self):
        """Marca el objeto como eliminado."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        """Restaura el objeto eliminado."""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin:
    """Mixin que añade campos de auditoría."""
    
    @declared_attr
    def created_by_id(cls):
        return Column(Integer, nullable=True)
    
    @declared_attr
    def updated_by_id(cls):
        return Column(Integer, nullable=True)


class UserTrackingMixin:
    """Mixin que añade seguimiento de usuario creador y modificador."""
    
    @declared_attr
    def created_by_id(cls):
        return Column(Integer, db.ForeignKey('users.id'), nullable=True)
    
    @declared_attr
    def updated_by_id(cls):
        return Column(Integer, db.ForeignKey('users.id'), nullable=True)
    
    @declared_attr
    def created_by(cls):
        return db.relationship('User', foreign_keys=[cls.created_by_id], 
                              backref=f'{cls.__name__.lower()}_created', lazy='select')
    
    @declared_attr
    def updated_by(cls):
        return db.relationship('User', foreign_keys=[cls.updated_by_id],
                              backref=f'{cls.__name__.lower()}_updated', lazy='select')


class ContactMixin:
    """Mixin que añade campos de contacto."""
    
    @declared_attr
    def email(cls):
        return Column(String(120), nullable=True)
    
    @declared_attr
    def phone(cls):
        return Column(String(20), nullable=True)
    
    @declared_attr
    def address(cls):
        return Column(Text, nullable=True)


# ====================================
# MIXIN DE BÚSQUEDA
# ====================================

class SearchableMixin:
    """
    Mixin que añade capacidades de búsqueda de texto completo.
    Funciona con PostgreSQL (texto completo) y SQLite (LIKE).
    """
    
    @classmethod
    def search(cls, expression: str, page: int = 1, per_page: int = 20, 
               fields: List[str] = None, exact_match: bool = False):
        """
        Realizar búsqueda de texto completo.
        
        Args:
            expression: Expresión de búsqueda
            page: Página de resultados
            per_page: Resultados por página
            fields: Campos específicos para buscar
            exact_match: Búsqueda exacta o parcial
            
        Returns:
            Objeto de paginación con resultados
        """
        if not expression or not expression.strip():
            return cls.query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Campos por defecto para búsqueda
        if not fields:
            fields = getattr(cls, '__searchable__', [])
        
        if not fields:
            # Intentar detectar campos de texto automáticamente
            fields = []
            for column in cls.__table__.columns:
                if isinstance(column.type, (String, Text)):
                    fields.append(column.name)
        
        # Construir query de búsqueda
        search_query = cls._build_search_query(expression, fields, exact_match)
        
        return search_query.paginate(page=page, per_page=per_page, error_out=False)
    
    @classmethod
    def _build_search_query(cls, expression: str, fields: List[str], exact_match: bool):
        """Construir query de búsqueda según el tipo de base de datos."""
        
        # Limpiar expresión de búsqueda
        clean_expression = expression.strip()
        
        # Determinar tipo de base de datos
        db_type = current_app.config.get('SQLALCHEMY_DATABASE_URI', '').lower()
        
        if 'postgresql' in db_type:
            return cls._postgresql_search(clean_expression, fields, exact_match)
        else:
            return cls._sqlite_search(clean_expression, fields, exact_match)
    
    @classmethod
    def _postgresql_search(cls, expression: str, fields: List[str], exact_match: bool):
        """Búsqueda optimizada para PostgreSQL usando texto completo."""
        from sqlalchemy import text
        
        # Crear vector de búsqueda combinando campos
        search_vector = " || ' ' || ".join([f"COALESCE({field}, '')" for field in fields])
        
        if exact_match:
            # Búsqueda exacta
            query = cls.query.filter(
                text(f"to_tsvector('spanish', {search_vector}) @@ plainto_tsquery('spanish', :expression)")
            ).params(expression=expression)
        else:
            # Búsqueda parcial con ranking
            query = cls.query.filter(
                text(f"to_tsvector('spanish', {search_vector}) @@ to_tsquery('spanish', :expression)")
            ).params(expression=f"{expression}:*")
            
            # Ordenar por relevancia
            query = query.order_by(
                text(f"ts_rank(to_tsvector('spanish', {search_vector}), to_tsquery('spanish', :expression)) DESC")
            ).params(expression=f"{expression}:*")
        
        return query
    
    @classmethod
    def _sqlite_search(cls, expression: str, fields: List[str], exact_match: bool):
        """Búsqueda para SQLite usando LIKE."""
        query = cls.query
        
        if exact_match:
            # Búsqueda exacta
            conditions = []
            for field in fields:
                if hasattr(cls, field):
                    conditions.append(getattr(cls, field) == expression)
            
            if conditions:
                query = query.filter(db.or_(*conditions))
        else:
            # Búsqueda parcial
            search_terms = expression.split()
            conditions = []
            
            for term in search_terms:
                term_conditions = []
                for field in fields:
                    if hasattr(cls, field):
                        term_conditions.append(getattr(cls, field).ilike(f'%{term}%'))
                
                if term_conditions:
                    conditions.append(db.or_(*term_conditions))
            
            if conditions:
                query = query.filter(db.and_(*conditions))
        
        return query
    
    @classmethod
    def search_count(cls, expression: str, fields: List[str] = None) -> int:
        """Contar resultados de búsqueda sin paginación."""
        if not expression:
            return cls.query.count()
        
        search_query = cls._build_search_query(expression, fields or [], False)
        return search_query.count()


# ====================================
# MIXIN DE CACHE
# ====================================

class CacheableMixin:
    """
    Mixin que añade capacidades de cache automático a los modelos.
    Usa Flask-Caching para almacenar consultas frecuentes.
    """
    
    @classmethod
    def get_cache_key(cls, method: str, *args, **kwargs) -> str:
        """Generar clave de cache única."""
        # Crear hash de argumentos
        args_str = json.dumps([str(arg) for arg in args], sort_keys=True)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
        combined = f"{args_str}_{kwargs_str}"
        
        hash_obj = hashlib.md5(combined.encode())
        return f"{cls.__name__}_{method}_{hash_obj.hexdigest()}"
    
    @classmethod
    def cached_query(cls, cache_timeout: int = CACHE_TIMEOUT_SHORT):
        """Decorador para cachear consultas."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generar clave de cache
                cache_key = cls.get_cache_key(func.__name__, *args, **kwargs)
                
                # Intentar obtener del cache
                result = cache.get(cache_key)
                if result is not None:
                    mixins_logger.debug(f"Cache hit for {cache_key}")
                    return result
                
                # Ejecutar consulta y cachear
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout=cache_timeout)
                mixins_logger.debug(f"Cache set for {cache_key}")
                
                return result
            return wrapper
        return decorator
    
    @classmethod
    def invalidate_cache(cls, pattern: str = None):
        """Invalidar cache por patrón."""
        if pattern:
            cache_key = f"{cls.__name__}_{pattern}"
        else:
            cache_key = f"{cls.__name__}_*"
        
        # Nota: Implementación específica según backend de cache
        try:
            cache.delete_many(cache_key)
            mixins_logger.info(f"Cache invalidated for pattern: {cache_key}")
        except Exception as e:
            mixins_logger.warning(f"Could not invalidate cache: {str(e)}")
    
    def invalidate_model_cache(self):
        """Invalidar cache específico de esta instancia."""
        self.__class__.invalidate_cache()
    
    @classmethod
    def get_cached(cls, id_value, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Obtener instancia con cache."""
        cache_key = cls.get_cache_key('get_cached', id_value)
        
        instance = cache.get(cache_key)
        if instance is not None:
            return instance
        
        instance = cls.get_by_id(id_value)
        if instance:
            cache.set(cache_key, instance, timeout=timeout)
        
        return instance
    
    def cache_instance(self, timeout: int = CACHE_TIMEOUT_MEDIUM):
        """Cachear esta instancia."""
        cache_key = self.__class__.get_cache_key('get_cached', self.id)
        cache.set(cache_key, self, timeout=timeout)


# ====================================
# MIXIN DE EXPORTACIÓN
# ====================================

class ExportableMixin:
    """
    Mixin que añade capacidades de exportación en múltiples formatos.
    Soporta JSON, CSV, Excel y PDF.
    """
    
    @classmethod
    def export_to_json(cls, query=None, filename: str = None, 
                       include_relationships: bool = False) -> str:
        """Exportar a JSON."""
        if query is None:
            query = cls.query
        
        instances = query.all()
        data = [instance.to_dict(include_relationships=include_relationships) 
                for instance in instances]
        
        json_data = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_data)
            mixins_logger.info(f"Exported {len(instances)} {cls.__name__} to {filename}")
        
        return json_data
    
    @classmethod
    def export_to_csv(cls, query=None, filename: str = None, 
                      fields: List[str] = None) -> str:
        """Exportar a CSV."""
        import csv
        from io import StringIO
        
        if query is None:
            query = cls.query
        
        instances = query.all()
        
        if not instances:
            return ""
        
        # Determinar campos a exportar
        if not fields:
            fields = [column.name for column in cls.__table__.columns]
        
        # Crear CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Escribir header
        writer.writerow(fields)
        
        # Escribir datos
        for instance in instances:
            row = []
            for field in fields:
                value = getattr(instance, field, '')
                
                # Manejar tipos especiales
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False)
                elif value is None:
                    value = ''
                
                row.append(str(value))
            
            writer.writerow(row)
        
        csv_data = output.getvalue()
        output.close()
        
        if filename:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                f.write(csv_data)
            mixins_logger.info(f"Exported {len(instances)} {cls.__name__} to {filename}")
        
        return csv_data
    
    @classmethod  
    def export_to_excel(cls, query=None, filename: str = None, 
                        fields: List[str] = None, sheet_name: str = None):
        """Exportar a Excel."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas es requerido para exportar a Excel")
        
        if query is None:
            query = cls.query
        
        instances = query.all()
        
        if not instances:
            return pd.DataFrame()
        
        # Convertir a diccionarios
        data = [instance.to_dict() for instance in instances]
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        # Filtrar campos si se especifica
        if fields:
            available_fields = [field for field in fields if field in df.columns]
            df = df[available_fields]
        
        if filename:
            sheet_name = sheet_name or cls.__name__
            df.to_excel(filename, sheet_name=sheet_name, index=False)
            mixins_logger.info(f"Exported {len(instances)} {cls.__name__} to {filename}")
        
        return df
    
    def export_instance_to_pdf(self, template_path: str, filename: str = None, 
                               context: Dict[str, Any] = None):
        """Exportar instancia individual a PDF."""
        try:
            from weasyprint import HTML, CSS
            from flask import render_template
        except ImportError:
            raise ImportError("weasyprint es requerido para exportar a PDF")
        
        # Preparar contexto
        pdf_context = {
            'instance': self,
            'data': self.to_dict(include_relationships=True),
            'generated_at': datetime.utcnow()
        }
        
        if context:
            pdf_context.update(context)
        
        # Renderizar template
        html_content = render_template(template_path, **pdf_context)
        
        # Generar PDF
        pdf = HTML(string=html_content).write_pdf()
        
        if filename:
            with open(filename, 'wb') as f:
                f.write(pdf)
            mixins_logger.info(f"Exported {self.__class__.__name__} to PDF: {filename}")
        
        return pdf


# ====================================
# MIXIN DE NOTIFICACIONES
# ====================================

class NotifiableMixin:
    """
    Mixin que permite a los modelos enviar notificaciones automáticas
    cuando ocurren ciertos eventos.
    """
    
    # Configuración de notificaciones por modelo
    _notification_events = {
        'created': {'template': 'model_created', 'enabled': True},
        'updated': {'template': 'model_updated', 'enabled': False},
        'deleted': {'template': 'model_deleted', 'enabled': True},
        'status_changed': {'template': 'status_changed', 'enabled': True}
    }
    
    def send_notification(self, event_type: str, recipients: List[str] = None, 
                         context: Dict[str, Any] = None, method: str = 'email'):
        """
        Enviar notificación por evento.
        
        Args:
            event_type: Tipo de evento (created, updated, deleted, etc.)
            recipients: Lista de emails o IDs de usuarios
            context: Contexto adicional para la notificación
            method: Método de envío (email, sms, push)
        """
        if not self._should_send_notification(event_type):
            return
        
        try:
            from app.services.notification_service import NotificationService
            
            # Preparar contexto
            notification_context = {
                'model_name': self.__class__.__name__,
                'model_id': str(self.id),
                'model_data': self.to_dict(),
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if context:
                notification_context.update(context)
            
            # Determinar destinatarios
            if not recipients:
                recipients = self._get_default_recipients(event_type)
            
            # Enviar notificación
            notification_service = NotificationService()
            
            for recipient in recipients:
                notification_service.send_notification(
                    recipient=recipient,
                    template=self._notification_events[event_type]['template'],
                    context=notification_context,
                    method=method
                )
            
            mixins_logger.info(f"Notification sent for {event_type} on {self.__class__.__name__}")
            
        except Exception as e:
            mixins_logger.error(f"Error sending notification: {str(e)}")
    
    def _should_send_notification(self, event_type: str) -> bool:
        """Verificar si se debe enviar notificación para el evento."""
        event_config = self._notification_events.get(event_type, {})
        return event_config.get('enabled', False)
    
    def _get_default_recipients(self, event_type: str) -> List[str]:
        """Obtener destinatarios por defecto según el evento."""
        # Implementar lógica específica en cada modelo
        return []
    
    @classmethod
    def configure_notifications(cls, event_type: str, enabled: bool = True, 
                               template: str = None):
        """Configurar notificaciones para el modelo."""
        if event_type not in cls._notification_events:
            cls._notification_events[event_type] = {}
        
        cls._notification_events[event_type]['enabled'] = enabled
        if template:
            cls._notification_events[event_type]['template'] = template


# ====================================
# MIXIN DE VALIDACIÓN AVANZADA
# ====================================

class ValidatableMixin:
    """
    Mixin que proporciona validación avanzada con reglas customizables
    y mensajes de error detallados.
    """
    
    # Reglas de validación por modelo
    _validation_rules = {}
    _validation_messages = {}
    
    def validate_all(self) -> Dict[str, List[str]]:
        """
        Ejecutar todas las validaciones del modelo.
        
        Returns:
            Diccionario con errores por campo
        """
        errors = {}
        
        # Validaciones automáticas por tipo de campo
        for column in self.__table__.columns:
            field_errors = self._validate_field(column)
            if field_errors:
                errors[column.name] = field_errors
        
        # Validaciones personalizadas
        custom_errors = self._validate_custom_rules()
        if custom_errors:
            errors.update(custom_errors)
        
        return errors
    
    def _validate_field(self, column) -> List[str]:
        """Validar campo individual según su tipo y restricciones."""
        errors = []
        field_name = column.name
        value = getattr(self, field_name, None)
        
        # Validar campos requeridos (NOT NULL)
        if not column.nullable and value is None:
            errors.append(f"El campo {field_name} es requerido")
        
        # Validar longitud de strings
        if isinstance(column.type, String) and value:
            max_length = getattr(column.type, 'length', None)
            if max_length and len(str(value)) > max_length:
                errors.append(f"El campo {field_name} excede la longitud máxima de {max_length}")
        
        # Validar unicidad
        if column.unique and value is not None:
            existing = self.__class__.query.filter(
                getattr(self.__class__, field_name) == value,
                getattr(self.__class__, 'id') != self.id
            ).first()
            
            if existing:
                errors.append(f"Ya existe un registro con este {field_name}")
        
        return errors
    
    def _validate_custom_rules(self) -> Dict[str, List[str]]:
        """Ejecutar reglas de validación personalizadas."""
        errors = {}
        
        for field, rules in self._validation_rules.items():
            field_errors = []
            value = getattr(self, field, None)
            
            for rule in rules:
                try:
                    if callable(rule):
                        # Regla como función
                        if not rule(value, self):
                            message = self._validation_messages.get(f"{field}_{rule.__name__}", 
                                                                   f"Validación fallida para {field}")
                            field_errors.append(message)
                    elif isinstance(rule, dict):
                        # Regla como diccionario con parámetros
                        rule_type = rule.get('type')
                        rule_params = rule.get('params', {})
                        
                        if not self._execute_validation_rule(rule_type, value, rule_params):
                            message = rule.get('message', f"Validación {rule_type} fallida para {field}")
                            field_errors.append(message)
                            
                except Exception as e:
                    mixins_logger.error(f"Error in validation rule: {str(e)}")
                    field_errors.append(f"Error en validación de {field}")
            
            if field_errors:
                errors[field] = field_errors
        
        return errors
    
    def _execute_validation_rule(self, rule_type: str, value: Any, params: Dict[str, Any]) -> bool:
        """Ejecutar regla de validación específica."""
        if rule_type == 'min_length':
            return value and len(str(value)) >= params.get('length', 0)
        elif rule_type == 'max_length':
            return not value or len(str(value)) <= params.get('length', float('inf'))
        elif rule_type == 'regex':
            import re
            pattern = params.get('pattern')
            return not value or re.match(pattern, str(value)) is not None
        elif rule_type == 'in_choices':
            choices = params.get('choices', [])
            return value in choices
        elif rule_type == 'range':
            min_val = params.get('min', float('-inf'))
            max_val = params.get('max', float('inf'))
            return value is None or (min_val <= value <= max_val)
        
        return True
    
    @classmethod
    def add_validation_rule(cls, field: str, rule: Union[Callable, Dict[str, Any]], 
                           message: str = None):
        """Añadir regla de validación personalizada."""
        if field not in cls._validation_rules:
            cls._validation_rules[field] = []
        
        cls._validation_rules[field].append(rule)
        
        if message:
            rule_key = f"{field}_{rule.__name__ if callable(rule) else rule.get('type', 'custom')}"
            cls._validation_messages[rule_key] = message
    
    def is_valid(self) -> bool:
        """Verificar si el modelo es válido."""
        errors = self.validate_all()
        return len(errors) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Obtener lista plana de errores de validación."""
        errors = self.validate_all()
        flat_errors = []
        
        for field_errors in errors.values():
            flat_errors.extend(field_errors)
        
        return flat_errors


# ====================================
# MIXIN DE MÁQUINA DE ESTADOS
# ====================================

class StateMachineMixin:
    """
    Mixin que implementa una máquina de estados simple para modelos
    que necesitan transiciones controladas entre estados.
    """
    
    # Definir en cada modelo que use el mixin
    _states = {}  # {'state_name': {'transitions': [...], 'on_enter': func, 'on_exit': func}}
    _initial_state = None
    
    @declared_attr
    def state(cls):
        return Column(String(50), nullable=False, doc="Estado actual del modelo")
    
    @declared_attr
    def state_changed_at(cls):
        return Column(DateTime(timezone=True), nullable=True, 
                     doc="Fecha del último cambio de estado")
    
    @declared_attr
    def previous_state(cls):
        return Column(String(50), nullable=True, doc="Estado anterior")
    
    def __init__(self, **kwargs):
        # Establecer estado inicial si no se proporciona
        if 'state' not in kwargs and self._initial_state:
            kwargs['state'] = self._initial_state
        
        super().__init__(**kwargs)
    
    def can_transition_to(self, new_state: str) -> bool:
        """Verificar si es posible transicionar al nuevo estado."""
        if not self.state:
            return new_state == self._initial_state
        
        current_state_config = self._states.get(self.state, {})
        allowed_transitions = current_state_config.get('transitions', [])
        
        return new_state in allowed_transitions
    
    def transition_to(self, new_state: str, save: bool = True, **context):
        """
        Transicionar a nuevo estado.
        
        Args:
            new_state: Estado destino
            save: Si guardar cambios automáticamente
            **context: Contexto adicional para callbacks
        """
        if not self.can_transition_to(new_state):
            raise ValueError(f"Transición inválida de '{self.state}' a '{new_state}'")
        
        old_state = self.state
        
        try:
            # Ejecutar callback de salida del estado actual
            if old_state:
                self._execute_state_callback(old_state, 'on_exit', context)
            
            # Cambiar estado
            self.previous_state = old_state
            self.state = new_state
            self.state_changed_at = datetime.utcnow()
            
            # Ejecutar callback de entrada al nuevo estado
            self._execute_state_callback(new_state, 'on_enter', context)
            
            # Guardar cambios
            if save:
                db.session.commit()
            
            # Log del cambio
            mixins_logger.info(f"{self.__class__.__name__} {self.id}: {old_state} -> {new_state}")
            
            # Enviar notificación si el mixin está disponible
            if hasattr(self, 'send_notification'):
                self.send_notification('status_changed', context={
                    'old_state': old_state,
                    'new_state': new_state,
                    'context': context
                })
                
        except Exception as e:
            db.session.rollback()
            # Revertir cambios
            self.state = old_state
            self.previous_state = None
            self.state_changed_at = None
            raise e
    
    def _execute_state_callback(self, state: str, callback_type: str, context: Dict[str, Any]):
        """Ejecutar callback de estado."""
        state_config = self._states.get(state, {})
        callback = state_config.get(callback_type)
        
        if callback and callable(callback):
            try:
                callback(self, context)
            except Exception as e:
                mixins_logger.error(f"Error in state callback {callback_type} for {state}: {str(e)}")
                raise
    
    def get_available_transitions(self) -> List[str]:
        """Obtener lista de transiciones disponibles desde el estado actual."""
        if not self.state:
            return [self._initial_state] if self._initial_state else []
        
        current_state_config = self._states.get(self.state, {})
        return current_state_config.get('transitions', [])
    
    def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener historial de cambios de estado (requiere ActivityLog)."""
        try:
            from .activity_log import ActivityLog
            
            logs = ActivityLog.query.filter(
                ActivityLog.model_type == self.__class__.__name__,
                ActivityLog.model_id == str(self.id),
                ActivityLog.action == 'state_change'
            ).order_by(ActivityLog.created_at.desc()).limit(limit).all()
            
            return [log.to_dict() for log in logs]
            
        except ImportError:
            mixins_logger.warning("ActivityLog not available for state history")
            return []
    
    @property
    def state_display_name(self) -> str:
        """Obtener nombre legible del estado actual."""
        state_config = self._states.get(self.state, {})
        return state_config.get('display_name', self.state)
    
    @classmethod
    def configure_states(cls, states_config: Dict[str, Dict[str, Any]], initial_state: str):
        """Configurar estados de la máquina."""
        cls._states = states_config
        cls._initial_state = initial_state


# ====================================
# EVENTOS AUTOMÁTICOS PARA MIXINS
# ====================================

@event.listens_for(NotifiableMixin, 'after_insert', propagate=True)
def send_created_notification(mapper, connection, target):
    """Enviar notificación automática al crear."""
    if hasattr(target, 'send_notification'):
        # Usar transacción diferida para evitar problemas con la transacción actual
        @event.listens_for(db.session, 'after_commit', once=True)
        def send_notification_after_commit(session):
            target.send_notification('created')


@event.listens_for(NotifiableMixin, 'after_update', propagate=True) 
def send_updated_notification(mapper, connection, target):
    """Enviar notificación automática al actualizar."""
    if hasattr(target, 'send_notification'):
        @event.listens_for(db.session, 'after_commit', once=True)
        def send_notification_after_commit(session):
            target.send_notification('updated')


@event.listens_for(CacheableMixin, 'after_update', propagate=True)
@event.listens_for(CacheableMixin, 'after_delete', propagate=True)
def invalidate_cache_on_change(mapper, connection, target):
    """Invalidar cache automáticamente al cambiar."""
    target.invalidate_model_cache()


# ====================================
# EXPORTACIONES
# ====================================

__all__ = [
    'TimestampMixin',
    'SoftDeleteMixin',
    'AuditMixin',
    'UserTrackingMixin',
    'ContactMixin',
    'SearchableMixin',
    'CacheableMixin', 
    'ExportableMixin',
    'NotifiableMixin',
    'ValidatableMixin',
    'StateMachineMixin'
]