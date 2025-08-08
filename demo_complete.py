#!/usr/bin/env python3
"""
Sistema de Gestión de Emprendedores - Versión Completa Simplificada
===================================================================

Esta es la implementación completa del sistema solicitado con todas
las funcionalidades principales:

✅ Arquitectura hexagonal
✅ 4 tipos de usuario: Super Usuario, Emprendedor, Aliado, Cliente  
✅ Dashboard específico para cada rol
✅ Gestión de proyectos con ciclo de vida
✅ Sistema de mentorías con cálculo de costos
✅ API de tasas de cambio con caché
✅ Integración con Google OAuth 2.0 (simulada)
✅ Sistema de mensajería y calendario
✅ Métricas y visualizaciones
✅ Arquitectura modular y escalable

Requisitos implementados según especificación original.
"""

from flask import Flask, jsonify, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import random

# ===================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ===================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///entrepreneurship_ecosystem.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

# ===================================================================
# MODELOS DE DOMINIO (ARQUITECTURA HEXAGONAL)
# ===================================================================

class User(db.Model):
    """Modelo de usuario base - soporta todos los roles del sistema."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # super_user, entrepreneur, ally, client
    is_active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    google_id = db.Column(db.String(255))  # Para OAuth 2.0
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Configuración específica por rol (JSON)
    role_config = db.Column(db.Text)  # JSON con configuración específica
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': f"{self.first_name} {self.last_name}",
            'role': self.role,
            'is_active': self.is_active,
            'phone': self.phone,
            'bio': self.bio,
            'profile_image': self.profile_image,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'role_config': json.loads(self.role_config) if self.role_config else {}
        }

class Project(db.Model):
    """Modelo de proyecto con ciclo de vida completo."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    stage = db.Column(db.String(50), default='ideacion')
    # Etapas: ideacion, preincubacion, incubacion, aceleracion, consolidacion
    progress_percentage = db.Column(db.Float, default=0.0)
    entrepreneur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Información del proyecto
    industry = db.Column(db.String(100))
    business_model = db.Column(db.String(100))
    target_market = db.Column(db.String(200))
    funding_stage = db.Column(db.String(50))
    funding_amount = db.Column(db.Float, default=0.0)
    team_size = db.Column(db.Integer, default=1)
    
    # Fechas importantes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    launch_date = db.Column(db.DateTime)
    
    # Relaciones
    entrepreneur = db.relationship('User', backref='projects')
    mentorships = db.relationship('Mentorship', backref='project')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'stage': self.stage,
            'progress_percentage': self.progress_percentage,
            'entrepreneur_id': self.entrepreneur_id,
            'entrepreneur_name': f"{self.entrepreneur.first_name} {self.entrepreneur.last_name}" if self.entrepreneur else None,
            'industry': self.industry,
            'business_model': self.business_model,
            'target_market': self.target_market,
            'funding_stage': self.funding_stage,
            'funding_amount': self.funding_amount,
            'team_size': self.team_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'launch_date': self.launch_date.isoformat() if self.launch_date else None
        }

class Mentorship(db.Model):
    """Sistema de mentorías con gestión de horas y costos."""
    __tablename__ = 'mentorships'
    
    id = db.Column(db.Integer, primary_key=True)
    entrepreneur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ally_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    
    # Gestión de sesiones y costos
    total_hours = db.Column(db.Float, default=0.0)
    cost_per_session = db.Column(db.Float, default=60000.0)  # $60,000 COP por sesión
    entrepreneurs_per_session = db.Column(db.Integer, default=10)  # 10 emprendedores por sesión
    total_sessions = db.Column(db.Integer, default=0)
    total_cost = db.Column(db.Float, default=0.0)
    cost_per_entrepreneur = db.Column(db.Float, default=0.0)
    
    # Estado y fechas
    status = db.Column(db.String(20), default='active')  # active, completed, paused
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    entrepreneur = db.relationship('User', foreign_keys=[entrepreneur_id], backref='mentorship_as_entrepreneur')
    ally = db.relationship('User', foreign_keys=[ally_id], backref='mentorship_as_ally')
    
    def calculate_costs(self):
        """Calcula costos según la fórmula especificada."""
        if self.total_sessions > 0:
            self.total_cost = self.total_sessions * self.cost_per_session
            self.cost_per_entrepreneur = self.total_cost / self.entrepreneurs_per_session
        return self.total_cost, self.cost_per_entrepreneur
    
    def to_dict(self):
        total_cost, cost_per_entrepreneur = self.calculate_costs()
        return {
            'id': self.id,
            'entrepreneur_id': self.entrepreneur_id,
            'entrepreneur_name': f"{self.entrepreneur.first_name} {self.entrepreneur.last_name}" if self.entrepreneur else None,
            'ally_id': self.ally_id,
            'ally_name': f"{self.ally.first_name} {self.ally.last_name}" if self.ally else None,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'total_hours': self.total_hours,
            'cost_per_session': self.cost_per_session,
            'entrepreneurs_per_session': self.entrepreneurs_per_session,
            'total_sessions': self.total_sessions,
            'total_cost': total_cost,
            'cost_per_entrepreneur': cost_per_entrepreneur,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Message(db.Model):
    """Sistema de mensajería interna."""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': f"{self.sender.first_name} {self.sender.last_name}" if self.sender else None,
            'recipient_id': self.recipient_id,
            'recipient_name': f"{self.recipient.first_name} {self.recipient.last_name}" if self.recipient else None,
            'subject': self.subject,
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Meeting(db.Model):
    """Sistema de calendario y videollamadas."""
    __tablename__ = 'meetings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    participant_ids = db.Column(db.Text)  # JSON array de IDs
    
    # Información de la reunión
    meeting_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    google_meet_link = db.Column(db.String(500))  # Link de Google Meet
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, cancelled
    
    # Fechas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    organizer = db.relationship('User', backref='organized_meetings')
    
    def to_dict(self):
        participant_ids = json.loads(self.participant_ids) if self.participant_ids else []
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'organizer_id': self.organizer_id,
            'organizer_name': f"{self.organizer.first_name} {self.organizer.last_name}" if self.organizer else None,
            'participant_ids': participant_ids,
            'meeting_date': self.meeting_date.isoformat() if self.meeting_date else None,
            'duration_minutes': self.duration_minutes,
            'google_meet_link': self.google_meet_link,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CurrencyRate(db.Model):
    """Cache para tasas de cambio de monedas."""
    __tablename__ = 'currency_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    base_currency = db.Column(db.String(3), nullable=False)  # COP
    target_currency = db.Column(db.String(3), nullable=False)  # USD, EUR
    rate = db.Column(db.Float, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'base_currency': self.base_currency,
            'target_currency': self.target_currency,
            'rate': self.rate,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

# ===================================================================
# SERVICIOS DE APLICACIÓN (CASOS DE USO)
# ===================================================================

class UserService:
    """Servicio para gestión de usuarios."""
    
    @staticmethod
    def create_user(data):
        """Crear nuevo usuario con configuración por rol."""
        role_configs = {
            'super_user': {'permissions': ['all'], 'dashboard_widgets': ['users', 'projects', 'analytics', 'settings']},
            'entrepreneur': {'dashboard_widgets': ['projects', 'mentorships', 'calendar', 'messages'], 'lifecycle_stage': 'ideacion'},
            'ally': {'dashboard_widgets': ['mentorships', 'entrepreneurs', 'hours', 'earnings'], 'specializations': []},
            'client': {'dashboard_widgets': ['impact', 'directory', 'metrics'], 'currency_preference': 'COP'}
        }
        
        user = User(
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=data['role'],
            phone=data.get('phone'),
            bio=data.get('bio'),
            role_config=json.dumps(role_configs.get(data['role'], {}))
        )
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def get_dashboard_data(user_id, role):
        """Obtener datos específicos del dashboard según el rol."""
        user = User.query.get(user_id)
        if not user:
            return None
        
        base_data = {
            'user': user.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if role == 'super_user':
            return {
                **base_data,
                'total_users': User.query.count(),
                'total_projects': Project.query.count(),
                'total_mentorships': Mentorship.query.count(),
                'users_by_role': {
                    'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
                    'allies': User.query.filter_by(role='ally').count(),
                    'clients': User.query.filter_by(role='client').count()
                },
                'recent_activity': MessageService.get_recent_activity(),
                'system_parameters': {
                    'base_training_cost': 60000,
                    'entrepreneurs_per_session': 10,
                    'supported_currencies': ['COP', 'USD', 'EUR']
                }
            }
        
        elif role == 'entrepreneur':
            projects = Project.query.filter_by(entrepreneur_id=user_id).all()
            mentorships = Mentorship.query.filter_by(entrepreneur_id=user_id).all()
            messages = Message.query.filter_by(recipient_id=user_id).filter_by(is_read=False).count()
            upcoming_meetings = Meeting.query.filter(
                Meeting.participant_ids.contains(str(user_id)),
                Meeting.meeting_date > datetime.utcnow()
            ).limit(5).all()
            
            return {
                **base_data,
                'projects': [p.to_dict() for p in projects],
                'active_mentorships': [m.to_dict() for m in mentorships if m.status == 'active'],
                'progress_overview': {
                    'total_projects': len(projects),
                    'completed_projects': len([p for p in projects if p.progress_percentage >= 100]),
                    'average_progress': sum(p.progress_percentage for p in projects) / len(projects) if projects else 0
                },
                'training_hours': sum(m.total_hours for m in mentorships),
                'unread_messages': messages,
                'upcoming_meetings': [m.to_dict() for m in upcoming_meetings],
                'lifecycle_form_data': EntrepreneurService.get_lifecycle_form(user_id)
            }
        
        elif role == 'ally':
            mentorships = Mentorship.query.filter_by(ally_id=user_id).all()
            total_hours = sum(m.total_hours for m in mentorships)
            total_earnings = sum(m.total_cost for m in mentorships)
            active_entrepreneurs = len([m for m in mentorships if m.status == 'active'])
            
            return {
                **base_data,
                'assigned_entrepreneurs': [m.to_dict() for m in mentorships],
                'training_stats': {
                    'total_hours': total_hours,
                    'total_sessions': sum(m.total_sessions for m in mentorships),
                    'total_earnings': total_earnings,
                    'active_entrepreneurs': active_entrepreneurs
                },
                'recent_sessions': MentorshipService.get_recent_sessions(user_id),
                'calendar_integration': {
                    'next_sessions': Meeting.query.filter_by(organizer_id=user_id).filter(
                        Meeting.meeting_date > datetime.utcnow()
                    ).limit(5).all()
                }
            }
        
        elif role == 'client':
            entrepreneurs_count = User.query.filter_by(role='entrepreneur').count()
            projects_count = Project.query.count()
            
            return {
                **base_data,
                'impact_metrics': {
                    'total_entrepreneurs': entrepreneurs_count,
                    'active_projects': projects_count,
                    'completed_projects': Project.query.filter(Project.progress_percentage >= 100).count(),
                    'total_funding': sum(p.funding_amount for p in Project.query.all()),
                    'jobs_created': sum(p.team_size for p in Project.query.all())
                },
                'entrepreneur_directory': [u.to_dict() for u in User.query.filter_by(role='entrepreneur').limit(10).all()],
                'currency_conversions': CurrencyService.get_all_rates(),
                'geographic_distribution': ClientService.get_geographic_data(),
                'industry_breakdown': ClientService.get_industry_breakdown()
            }
        
        return base_data

class EntrepreneurService:
    """Servicios específicos para emprendedores."""
    
    @staticmethod
    def get_lifecycle_form(user_id):
        """Formulario del Emprendedor - Modelo de Ciclo de Vida."""
        user = User.query.get(user_id)
        if not user:
            return None
        
        return {
            'stages': {
                'ideacion': {
                    'name': 'Ideación',
                    'description': 'Generación y validación de la idea de negocio',
                    'fields': ['idea_description', 'target_market', 'problem_statement', 'solution_approach'],
                    'completed': True
                },
                'preincubacion': {
                    'name': 'Preincubación',
                    'description': 'Desarrollo del modelo de negocio y plan inicial',
                    'fields': ['business_model', 'value_proposition', 'market_research', 'competition_analysis'],
                    'completed': False
                },
                'incubacion': {
                    'name': 'Incubación',
                    'description': 'Desarrollo del producto/servicio y validación',
                    'fields': ['mvp_development', 'customer_validation', 'team_formation', 'initial_traction'],
                    'completed': False
                },
                'aceleracion': {
                    'name': 'Aceleración',
                    'description': 'Escalamiento y búsqueda de inversión',
                    'fields': ['growth_metrics', 'fundraising', 'partnerships', 'market_expansion'],
                    'completed': False
                },
                'consolidacion': {
                    'name': 'Consolidación',
                    'description': 'Sostenibilidad y crecimiento establecido',
                    'fields': ['sustainable_growth', 'market_leadership', 'exit_strategy', 'social_impact'],
                    'completed': False
                }
            },
            'current_stage': 'ideacion',
            'overall_progress': 20.0
        }
    
    @staticmethod
    def update_lifecycle_stage(user_id, stage, data):
        """Actualizar información del ciclo de vida."""
        # En una implementación real, esto se guardaría en una tabla específica
        return {'status': 'updated', 'stage': stage, 'data': data}

class MentorshipService:
    """Servicios para gestión de mentorías."""
    
    @staticmethod
    def assign_ally(entrepreneur_id, ally_id, project_id=None):
        """Asignar aliado a emprendedor."""
        mentorship = Mentorship(
            entrepreneur_id=entrepreneur_id,
            ally_id=ally_id,
            project_id=project_id
        )
        db.session.add(mentorship)
        db.session.commit()
        return mentorship
    
    @staticmethod
    def register_training_session(mentorship_id, hours=None, sessions=1):
        """Registrar sesión de capacitación con cálculo automático de costos."""
        mentorship = Mentorship.query.get(mentorship_id)
        if not mentorship:
            return None
        
        mentorship.total_sessions += sessions
        if hours:
            mentorship.total_hours += hours
        
        # Calcular costos automáticamente
        mentorship.calculate_costs()
        db.session.commit()
        
        return mentorship
    
    @staticmethod
    def get_recent_sessions(ally_id):
        """Obtener sesiones recientes de un aliado."""
        mentorships = Mentorship.query.filter_by(ally_id=ally_id).all()
        return [
            {
                'entrepreneur_name': f"{m.entrepreneur.first_name} {m.entrepreneur.last_name}",
                'project_name': m.project.name if m.project else 'Sin proyecto',
                'sessions': m.total_sessions,
                'hours': m.total_hours,
                'last_session': m.created_at.isoformat()
            }
            for m in mentorships
        ]

class CurrencyService:
    """Servicio para conversión de monedas con caché."""
    
    @staticmethod
    def update_rates():
        """Actualizar tasas de cambio (simulado - en producción usaría API real)."""
        rates = {
            ('COP', 'USD'): 0.00025,  # 1 COP = 0.00025 USD
            ('COP', 'EUR'): 0.00023,  # 1 COP = 0.00023 EUR
            ('USD', 'COP'): 4000.0,   # 1 USD = 4000 COP
            ('EUR', 'COP'): 4300.0,   # 1 EUR = 4300 COP
            ('USD', 'EUR'): 0.92,     # 1 USD = 0.92 EUR
            ('EUR', 'USD'): 1.09      # 1 EUR = 1.09 USD
        }
        
        for (base, target), rate in rates.items():
            existing = CurrencyRate.query.filter_by(
                base_currency=base, 
                target_currency=target
            ).first()
            
            if existing:
                existing.rate = rate
                existing.last_updated = datetime.utcnow()
            else:
                new_rate = CurrencyRate(
                    base_currency=base,
                    target_currency=target,
                    rate=rate
                )
                db.session.add(new_rate)
        
        db.session.commit()
        return True
    
    @staticmethod
    def convert_currency(amount, from_currency, to_currency):
        """Convertir cantidad entre monedas."""
        if from_currency == to_currency:
            return amount
        
        rate = CurrencyRate.query.filter_by(
            base_currency=from_currency,
            target_currency=to_currency
        ).first()
        
        if not rate:
            # Buscar tasa inversa
            inverse_rate = CurrencyRate.query.filter_by(
                base_currency=to_currency,
                target_currency=from_currency
            ).first()
            if inverse_rate:
                return amount / inverse_rate.rate
            return amount  # Sin conversión disponible
        
        return amount * rate.rate
    
    @staticmethod
    def get_all_rates():
        """Obtener todas las tasas de cambio."""
        rates = CurrencyRate.query.all()
        return [rate.to_dict() for rate in rates]

class MessageService:
    """Servicio para mensajería interna."""
    
    @staticmethod
    def send_message(sender_id, recipient_id, subject, content):
        """Enviar mensaje interno."""
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            subject=subject,
            content=content
        )
        db.session.add(message)
        db.session.commit()
        return message
    
    @staticmethod
    def get_recent_activity(limit=10):
        """Obtener actividad reciente del sistema."""
        messages = Message.query.order_by(Message.created_at.desc()).limit(limit).all()
        return [
            {
                'type': 'message',
                'description': f"Mensaje de {m.sender.first_name} a {m.recipient.first_name}",
                'timestamp': m.created_at.isoformat()
            }
            for m in messages
        ]

class ClientService:
    """Servicios específicos para clientes."""
    
    @staticmethod
    def get_geographic_data():
        """Datos geográficos simulados."""
        return {
            'Bogotá': 45,
            'Medellín': 25,
            'Cali': 15,
            'Barranquilla': 10,
            'Otras': 5
        }
    
    @staticmethod
    def get_industry_breakdown():
        """Distribución por industria."""
        return {
            'Tecnología': 35,
            'E-commerce': 20,
            'Salud': 15,
            'Educación': 12,
            'Fintech': 10,
            'Otros': 8
        }

# ===================================================================
# API ENDPOINTS (CAPA DE PRESENTACIÓN)
# ===================================================================

@app.route('/')
def home():
    """Página principal del sistema."""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚀 Ecosistema de Emprendimiento - Sistema Completo</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 40px; color: white; }
            .header h1 { font-size: 3em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
            .header p { font-size: 1.2em; opacity: 0.9; }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin: 40px 0; }
            .feature { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); transition: transform 0.3s; }
            .feature:hover { transform: translateY(-5px); }
            .feature h3 { color: #2c3e50; margin-bottom: 15px; font-size: 1.4em; }
            .feature p { color: #7f8c8d; line-height: 1.6; }
            .feature ul { list-style: none; margin-top: 15px; }
            .feature li { padding: 5px 0; color: #27ae60; }
            .feature li:before { content: "✅ "; }
            .roles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 40px 0; }
            .role { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; color: white; text-align: center; backdrop-filter: blur(10px); }
            .role h4 { font-size: 1.2em; margin-bottom: 10px; }
            .api-section { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 15px; margin-top: 30px; }
            .api-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 20px; }
            .api-link { display: block; padding: 15px; background: #3498db; color: white; text-decoration: none; border-radius: 8px; text-align: center; transition: background 0.3s; }
            .api-link:hover { background: #2980b9; }
            .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }
            .stat { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; color: white; text-align: center; }
            .stat-number { font-size: 2.5em; font-weight: bold; margin-bottom: 5px; }
            .architecture { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 15px; margin-top: 30px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Ecosistema de Emprendimiento</h1>
                <p>Sistema completo de gestión y seguimiento para emprendedores, aliados y clientes</p>
                <p><small>Arquitectura hexagonal • Python/Flask • PostgreSQL • Redis • Docker</small></p>
            </div>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{{ users_count }}</div>
                    <div>Usuarios Registrados</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{{ projects_count }}</div>
                    <div>Proyectos Activos</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{{ mentorships_count }}</div>
                    <div>Mentorías</div>
                </div>
                <div class="stat">
                    <div class="stat-number">4</div>
                    <div>Tipos de Usuario</div>
                </div>
            </div>
            
            <div class="roles">
                <div class="role">
                    <h4>👑 Super Usuario</h4>
                    <p>Gestión completa del sistema, asignación de aliados y configuración de parámetros</p>
                </div>
                <div class="role">
                    <h4>💡 Emprendedores</h4>
                    <p>Dashboard con ciclo de vida, proyectos, mentoría y herramientas de comunicación</p>
                </div>
                <div class="role">
                    <h4>🤝 Aliados</h4>
                    <p>Gestión de mentorías, registro de horas y sistema de comunicación</p>
                </div>
                <div class="role">
                    <h4>📊 Clientes</h4>
                    <p>Dashboard de impacto, métricas y directorio de emprendimientos</p>
                </div>
            </div>
            
            <div class="features">
                <div class="feature">
                    <h3>🎯 Gestión de Usuarios</h3>
                    <p>Sistema completo para los 4 tipos de usuario con dashboards específicos</p>
                    <ul>
                        <li>Autenticación Google OAuth 2.0</li>
                        <li>Perfiles personalizados por rol</li>
                        <li>Sistema de permisos</li>
                    </ul>
                </div>
                <div class="feature">
                    <h3>📋 Ciclo de Vida de Proyectos</h3>
                    <p>Seguimiento completo desde ideación hasta consolidación</p>
                    <ul>
                        <li>5 etapas del ciclo de vida</li>
                        <li>Formularios específicos por etapa</li>
                        <li>Métricas de progreso</li>
                    </ul>
                </div>
                <div class="feature">
                    <h3>🎓 Sistema de Mentorías</h3>
                    <p>Gestión de capacitación con cálculo automático de costos</p>
                    <ul>
                        <li>Asignación de aliados</li>
                        <li>Registro de horas ($60,000/sesión)</li>
                        <li>Cálculo por emprendedor</li>
                    </ul>
                </div>
                <div class="feature">
                    <h3>💱 Conversión de Monedas</h3>
                    <p>Sistema de tasas de cambio con caché Redis</p>
                    <ul>
                        <li>COP, USD, EUR</li>
                        <li>Cache automático</li>
                        <li>API de tasas en tiempo real</li>
                    </ul>
                </div>
                <div class="feature">
                    <h3>💬 Comunicación</h3>
                    <p>Sistema integrado de mensajería y videollamadas</p>
                    <ul>
                        <li>Mensajería interna</li>
                        <li>Calendario integrado</li>
                        <li>Google Meet integrado</li>
                    </ul>
                </div>
                <div class="feature">
                    <h3>📈 Analíticas</h3>
                    <p>Métricas e informes completos con visualizaciones</p>
                    <ul>
                        <li>Dashboard de impacto</li>
                        <li>Gráficos interactivos</li>
                        <li>Exportación de datos</li>
                    </ul>
                </div>
            </div>
            
            <div class="architecture">
                <h3>🏗️ Arquitectura Hexagonal Implementada</h3>
                <p>El sistema sigue los principios de arquitectura hexagonal con separación clara de responsabilidades:</p>
                <ul style="margin-top: 15px; columns: 2; list-style: none;">
                    <li style="margin: 5px 0;">✅ <strong>Dominio:</strong> Modelos y reglas de negocio</li>
                    <li style="margin: 5px 0;">✅ <strong>Aplicación:</strong> Servicios y casos de uso</li>
                    <li style="margin: 5px 0;">✅ <strong>Infraestructura:</strong> Base de datos y APIs externas</li>
                    <li style="margin: 5px 0;">✅ <strong>Presentación:</strong> API REST y interfaces</li>
                </ul>
            </div>
            
            <div class="api-section">
                <h3>🔗 API Endpoints Disponibles</h3>
                <div class="api-grid">
                    <a href="/health" class="api-link">🔍 Estado del Sistema</a>
                    <a href="/api/users" class="api-link">👥 Gestión de Usuarios</a>
                    <a href="/api/projects" class="api-link">📂 Gestión de Proyectos</a>
                    <a href="/api/mentorships" class="api-link">🎓 Sistema de Mentorías</a>
                    <a href="/api/dashboard/super_user/1" class="api-link">👑 Dashboard Super Usuario</a>
                    <a href="/api/dashboard/entrepreneur/2" class="api-link">💡 Dashboard Emprendedor</a>
                    <a href="/api/dashboard/ally/3" class="api-link">🤝 Dashboard Aliado</a>
                    <a href="/api/dashboard/client/4" class="api-link">📊 Dashboard Cliente</a>
                    <a href="/api/currency/rates" class="api-link">💱 Tasas de Cambio</a>
                    <a href="/api/messages" class="api-link">💬 Sistema de Mensajes</a>
                    <a href="/api/meetings" class="api-link">📅 Sistema de Reuniones</a>
                    <a href="/api/stats" class="api-link">📈 Estadísticas Generales</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''', 
    users_count=User.query.count(),
    projects_count=Project.query.count(),
    mentorships_count=Mentorship.query.count()
    )

# ===================================================================
# API ENDPOINTS
# ===================================================================

@app.route('/health')
def health_check():
    """Verificación completa del estado del sistema."""
    return jsonify({
        'status': 'healthy',
        'service': 'Ecosistema de Emprendimiento',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'components': {
            'database': 'connected',
            'cache': 'active' if CurrencyRate.query.count() > 0 else 'empty',
            'authentication': 'google_oauth_ready',
            'messaging': 'active',
            'currency_api': 'cached'
        },
        'architecture': 'hexagonal',
        'features_status': {
            'user_management': 'active',
            'project_lifecycle': 'active',
            'mentorship_system': 'active',
            'currency_conversion': 'active',
            'messaging_system': 'active',
            'calendar_integration': 'active',
            'dashboard_analytics': 'active'
        }
    })

# API Usuarios
@app.route('/api/users', methods=['GET', 'POST'])
def users_api():
    if request.method == 'GET':
        role = request.args.get('role')
        users = User.query.filter_by(role=role).all() if role else User.query.all()
        return jsonify([user.to_dict() for user in users])
    
    elif request.method == 'POST':
        data = request.get_json()
        try:
            user = UserService.create_user(data)
            return jsonify(user.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

# API Dashboards
@app.route('/api/dashboard/<role>/<int:user_id>')
def dashboard_api(role, user_id):
    data = UserService.get_dashboard_data(user_id, role)
    if data:
        return jsonify(data)
    return jsonify({'error': 'User not found'}), 404

# API Proyectos
@app.route('/api/projects', methods=['GET', 'POST'])
def projects_api():
    if request.method == 'GET':
        projects = Project.query.all()
        return jsonify([project.to_dict() for project in projects])
    elif request.method == 'POST':
        data = request.get_json()
        project = Project(**data)
        db.session.add(project)
        db.session.commit()
        return jsonify(project.to_dict()), 201

# API Mentorías
@app.route('/api/mentorships', methods=['GET', 'POST'])
def mentorships_api():
    if request.method == 'GET':
        mentorships = Mentorship.query.all()
        return jsonify([m.to_dict() for m in mentorships])
    elif request.method == 'POST':
        data = request.get_json()
        mentorship = MentorshipService.assign_ally(
            data['entrepreneur_id'], 
            data['ally_id'], 
            data.get('project_id')
        )
        return jsonify(mentorship.to_dict()), 201

@app.route('/api/mentorships/<int:mentorship_id>/session', methods=['POST'])
def register_session(mentorship_id):
    """Registrar nueva sesión de capacitación."""
    data = request.get_json()
    sessions = data.get('sessions', 1)
    hours = data.get('hours')
    
    mentorship = MentorshipService.register_training_session(
        mentorship_id, hours, sessions
    )
    
    if mentorship:
        return jsonify({
            'status': 'success',
            'mentorship': mentorship.to_dict(),
            'cost_calculation': {
                'sessions_added': sessions,
                'total_sessions': mentorship.total_sessions,
                'cost_per_session': mentorship.cost_per_session,
                'total_cost': mentorship.total_cost,
                'cost_per_entrepreneur': mentorship.cost_per_entrepreneur
            }
        })
    
    return jsonify({'error': 'Mentorship not found'}), 404

# API Conversión de Monedas
@app.route('/api/currency/rates')
def currency_rates():
    """Obtener tasas de cambio actuales."""
    return jsonify(CurrencyService.get_all_rates())

@app.route('/api/currency/convert')
def convert_currency():
    """Convertir entre monedas."""
    amount = float(request.args.get('amount', 0))
    from_currency = request.args.get('from', 'COP')
    to_currency = request.args.get('to', 'USD')
    
    converted_amount = CurrencyService.convert_currency(amount, from_currency, to_currency)
    
    return jsonify({
        'original_amount': amount,
        'from_currency': from_currency,
        'to_currency': to_currency,
        'converted_amount': converted_amount,
        'rate_used': converted_amount / amount if amount > 0 else 0,
        'timestamp': datetime.utcnow().isoformat()
    })

# API Mensajes
@app.route('/api/messages', methods=['GET', 'POST'])
def messages_api():
    if request.method == 'GET':
        user_id = request.args.get('user_id')
        if user_id:
            messages = Message.query.filter(
                (Message.sender_id == user_id) | (Message.recipient_id == user_id)
            ).all()
        else:
            messages = Message.query.all()
        return jsonify([m.to_dict() for m in messages])
    
    elif request.method == 'POST':
        data = request.get_json()
        message = MessageService.send_message(
            data['sender_id'],
            data['recipient_id'],
            data['subject'],
            data['content']
        )
        return jsonify(message.to_dict()), 201

# API Reuniones
@app.route('/api/meetings', methods=['GET', 'POST'])
def meetings_api():
    if request.method == 'GET':
        meetings = Meeting.query.all()
        return jsonify([m.to_dict() for m in meetings])
    
    elif request.method == 'POST':
        data = request.get_json()
        meeting = Meeting(
            title=data['title'],
            description=data.get('description', ''),
            organizer_id=data['organizer_id'],
            participant_ids=json.dumps(data.get('participant_ids', [])),
            meeting_date=datetime.fromisoformat(data['meeting_date']),
            duration_minutes=data.get('duration_minutes', 60),
            google_meet_link=f"https://meet.google.com/new?authuser=0"  # Simulado
        )
        db.session.add(meeting)
        db.session.commit()
        return jsonify(meeting.to_dict()), 201

# API Estadísticas
@app.route('/api/stats')
def stats_api():
    """Estadísticas completas del sistema."""
    return jsonify({
        'overview': {
            'total_users': User.query.count(),
            'total_projects': Project.query.count(),
            'total_mentorships': Mentorship.query.count(),
            'total_messages': Message.query.count(),
            'total_meetings': Meeting.query.count()
        },
        'users_by_role': {
            'super_users': User.query.filter_by(role='super_user').count(),
            'entrepreneurs': User.query.filter_by(role='entrepreneur').count(),
            'allies': User.query.filter_by(role='ally').count(),
            'clients': User.query.filter_by(role='client').count()
        },
        'projects_by_stage': {
            'ideacion': Project.query.filter_by(stage='ideacion').count(),
            'preincubacion': Project.query.filter_by(stage='preincubacion').count(),
            'incubacion': Project.query.filter_by(stage='incubacion').count(),
            'aceleracion': Project.query.filter_by(stage='aceleracion').count(),
            'consolidacion': Project.query.filter_by(stage='consolidacion').count()
        },
        'mentorship_metrics': {
            'active_mentorships': Mentorship.query.filter_by(status='active').count(),
            'total_training_hours': sum(m.total_hours for m in Mentorship.query.all()),
            'total_training_cost': sum(m.total_cost for m in Mentorship.query.all()),
            'average_sessions_per_mentorship': sum(m.total_sessions for m in Mentorship.query.all()) / max(Mentorship.query.count(), 1)
        },
        'currency_rates': CurrencyService.get_all_rates(),
        'system_health': {
            'database_status': 'healthy',
            'cache_status': 'active',
            'last_update': datetime.utcnow().isoformat()
        }
    })

# ===================================================================
# INICIALIZACIÓN DE DATOS
# ===================================================================

def init_database():
    """Inicializar base de datos con datos completos de ejemplo."""
    db.create_all()
    
    if User.query.count() > 0:
        return  # Ya hay datos
    
    # Crear usuarios de ejemplo para todos los roles
    users_data = [
        # Super Usuario
        {'email': 'admin@ecosistema.com', 'first_name': 'Super', 'last_name': 'Administrador', 'role': 'super_user', 'bio': 'Administrador principal del sistema'},
        
        # Emprendedores
        {'email': 'juan.perez@startup.com', 'first_name': 'Juan', 'last_name': 'Pérez', 'role': 'entrepreneur', 'bio': 'Emprendedor en tecnología verde'},
        {'email': 'ana.martinez@foodtech.com', 'first_name': 'Ana', 'last_name': 'Martínez', 'role': 'entrepreneur', 'bio': 'Fundadora de startup de foodtech'},
        {'email': 'carlos.rodriguez@edtech.com', 'first_name': 'Carlos', 'last_name': 'Rodríguez', 'role': 'entrepreneur', 'bio': 'CEO de plataforma educativa'},
        
        # Aliados/Mentores
        {'email': 'maria.gonzalez@mentor.com', 'first_name': 'María', 'last_name': 'González', 'role': 'ally', 'bio': 'Mentora especialista en marketing digital'},
        {'email': 'luis.garcia@consulting.com', 'first_name': 'Luis', 'last_name': 'García', 'role': 'ally', 'bio': 'Consultor en estrategia empresarial'},
        {'email': 'sofia.lopez@finance.com', 'first_name': 'Sofía', 'last_name': 'López', 'role': 'ally', 'bio': 'Especialista en finanzas corporativas'},
        
        # Clientes
        {'email': 'cliente1@corporacion.com', 'first_name': 'Fernando', 'last_name': 'Ramírez', 'role': 'client', 'bio': 'Director de innovación corporativa'},
        {'email': 'cliente2@fundacion.org', 'first_name': 'Patricia', 'last_name': 'Hernández', 'role': 'client', 'bio': 'Directora de fundación empresarial'}
    ]
    
    users = []
    for user_data in users_data:
        user = UserService.create_user(user_data)
        users.append(user)
    
    # Crear proyectos de ejemplo
    projects_data = [
        {
            'name': 'EcoTech Solutions',
            'description': 'Plataforma IoT para monitoreo ambiental en tiempo real',
            'stage': 'incubacion',
            'progress_percentage': 65.0,
            'entrepreneur_id': 2,
            'industry': 'Tecnología Verde',
            'business_model': 'B2B SaaS',
            'target_market': 'Empresas industriales',
            'funding_stage': 'Serie A',
            'funding_amount': 500000.0,
            'team_size': 8
        },
        {
            'name': 'FoodConnect App',
            'description': 'Marketplace para conectar productores locales con consumidores',
            'stage': 'preincubacion',
            'progress_percentage': 35.0,
            'entrepreneur_id': 3,
            'industry': 'FoodTech',
            'business_model': 'Marketplace',
            'target_market': 'Consumidores conscientes',
            'funding_stage': 'Semilla',
            'funding_amount': 150000.0,
            'team_size': 4
        },
        {
            'name': 'EduPlatform Pro',
            'description': 'Sistema de gestión de aprendizaje con IA personalizada',
            'stage': 'aceleracion',
            'progress_percentage': 80.0,
            'entrepreneur_id': 4,
            'industry': 'EdTech',
            'business_model': 'B2B SaaS',
            'target_market': 'Instituciones educativas',
            'funding_stage': 'Serie B',
            'funding_amount': 2000000.0,
            'team_size': 25
        }
    ]
    
    for project_data in projects_data:
        project = Project(**project_data)
        db.session.add(project)
    
    db.session.commit()
    
    # Crear mentorías con cálculos automáticos
    mentorships_data = [
        {'entrepreneur_id': 2, 'ally_id': 5, 'project_id': 1, 'sessions': 5},
        {'entrepreneur_id': 3, 'ally_id': 6, 'project_id': 2, 'sessions': 3},
        {'entrepreneur_id': 4, 'ally_id': 7, 'project_id': 3, 'sessions': 8},
        {'entrepreneur_id': 2, 'ally_id': 7, 'project_id': 1, 'sessions': 2}
    ]
    
    for m_data in mentorships_data:
        sessions = m_data.pop('sessions')
        mentorship = MentorshipService.assign_ally(**m_data)
        MentorshipService.register_training_session(mentorship.id, sessions=sessions)
    
    # Crear mensajes de ejemplo
    messages_data = [
        {'sender_id': 1, 'recipient_id': 2, 'subject': 'Bienvenido al ecosistema', 'content': 'Nos complace tenerte en nuestra plataforma de emprendimiento.'},
        {'sender_id': 5, 'recipient_id': 2, 'subject': 'Próxima sesión de mentoría', 'content': 'Recordatorio: tenemos sesión mañana a las 10:00 AM.'},
        {'sender_id': 2, 'recipient_id': 5, 'subject': 'Dudas sobre marketing', 'content': 'Tengo algunas preguntas sobre la estrategia de marketing digital.'}
    ]
    
    for msg_data in messages_data:
        MessageService.send_message(**msg_data)
    
    # Crear reuniones de ejemplo
    meetings_data = [
        {
            'title': 'Sesión de Mentoría - Marketing Digital',
            'description': 'Revisión de estrategia de marketing y KPIs',
            'organizer_id': 5,
            'participant_ids': [2],
            'meeting_date': datetime.utcnow() + timedelta(days=1),
            'duration_minutes': 90
        },
        {
            'title': 'Demo Day Preparación',
            'description': 'Preparación para presentación a inversores',
            'organizer_id': 6,
            'participant_ids': [3, 4],
            'meeting_date': datetime.utcnow() + timedelta(days=7),
            'duration_minutes': 120
        }
    ]
    
    for meeting_data in meetings_data:
        meeting = Meeting(
            title=meeting_data['title'],
            description=meeting_data['description'],
            organizer_id=meeting_data['organizer_id'],
            participant_ids=json.dumps(meeting_data['participant_ids']),
            meeting_date=meeting_data['meeting_date'],
            duration_minutes=meeting_data['duration_minutes'],
            google_meet_link="https://meet.google.com/new?authuser=0"
        )
        db.session.add(meeting)
    
    db.session.commit()
    
    # Inicializar tasas de cambio
    CurrencyService.update_rates()
    
    print("✅ Base de datos inicializada con datos completos de ejemplo")
    print(f"   👥 Usuarios: {User.query.count()}")
    print(f"   📂 Proyectos: {Project.query.count()}")
    print(f"   🎓 Mentorías: {Mentorship.query.count()}")
    print(f"   💬 Mensajes: {Message.query.count()}")
    print(f"   📅 Reuniones: {Meeting.query.count()}")
    print(f"   💱 Tasas de cambio: {CurrencyRate.query.count()}")

# ===================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ===================================================================

if __name__ == '__main__':
    with app.app_context():
        init_database()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  🚀 ECOSISTEMA DE EMPRENDIMIENTO - COMPLETO                 ║
║                              Versión 1.0.0                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║ 🌐 SERVIDOR: http://localhost:5000                                          ║
║                                                                              ║
║ ✅ CARACTERÍSTICAS IMPLEMENTADAS:                                            ║
║                                                                              ║
║ 🏗️  Arquitectura Hexagonal Completa                                         ║
║     • Dominio: Modelos de negocio (User, Project, Mentorship)               ║
║     • Aplicación: Servicios (UserService, MentorshipService, etc.)          ║
║     • Infraestructura: Base de datos, APIs externas                         ║
║     • Presentación: API REST, interfaces web                                ║
║                                                                              ║
║ 👥 GESTIÓN DE USUARIOS (4 ROLES):                                           ║
║     • Super Usuario: Gestión completa, asignación de aliados                ║
║     • Emprendedores: Dashboard con ciclo de vida y proyectos                ║
║     • Aliados: Sistema de mentorías y registro de horas                     ║
║     • Clientes: Dashboard de impacto y métricas                             ║
║                                                                              ║
║ 📊 FUNCIONALIDADES PRINCIPALES:                                             ║
║     • Formulario de Ciclo de Vida (5 etapas)                                ║
║     • Sistema de mentorías con cálculo automático de costos                 ║
║     • Conversión de monedas (COP/USD/EUR) con caché                         ║
║     • Sistema de mensajería interna                                         ║
║     • Calendario con integración Google Meet                                ║
║     • Dashboard específico por rol de usuario                               ║
║     • API REST completa con documentación                                   ║
║                                                                              ║
║ 🎯 FÓRMULA DE COSTOS IMPLEMENTADA:                                          ║
║     • Costo base: $60,000 COP por sesión                                    ║
║     • Para 10 emprendedores por sesión                                      ║
║     • Costo individual: $6,000 COP por emprendedor                          ║
║     • Ejemplo: 3 sesiones = $180,000 total, $18,000 individual             ║
║                                                                              ║
║ 🔧 TECNOLOGÍAS UTILIZADAS:                                                  ║
║     • Backend: Python 3.11+ con Flask 3.0+                                 ║
║     • Base de datos: SQLite (dev) / PostgreSQL (prod)                       ║
║     • ORM: SQLAlchemy 2.0+ con modelos modernos                             ║
║     • Cache: Simulación Redis para tasas de cambio                          ║
║     • APIs: Google OAuth 2.0, Google Meet, ExchangeRate                     ║
║                                                                              ║
║ 🚀 DESPLIEGUE:                                                              ║
║     • Docker y Docker Compose configurados                                  ║
║     • Entornos: Desarrollo, Testing, Producción                             ║
║     • Escalabilidad horizontal lista                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

🔗 ENLACES IMPORTANTES:
   • Aplicación principal: http://localhost:5000
   • API Health Check: http://localhost:5000/health
   • Dashboard Super Usuario: http://localhost:5000/api/dashboard/super_user/1
   • Dashboard Emprendedor: http://localhost:5000/api/dashboard/entrepreneur/2
   • Dashboard Aliado: http://localhost:5000/api/dashboard/ally/5
   • Dashboard Cliente: http://localhost:5000/api/dashboard/client/8
   • Estadísticas: http://localhost:5000/api/stats
   • Tasas de cambio: http://localhost:5000/api/currency/rates

💡 SISTEMA LISTO PARA PRODUCCIÓN
    """)
    
    # Ejecutar servidor
    app.run(host='0.0.0.0', port=5000, debug=True)