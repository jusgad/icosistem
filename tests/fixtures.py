"""
Ecosistema de Emprendimiento - Fixtures Especializadas
======================================================

Este módulo contiene fixtures especializadas para el testing del ecosistema de emprendimiento,
incluyendo scenarios complejos de negocio, datos de analytics, workflows completos y 
configuraciones específicas del dominio.

Características especializadas:
- Fixtures de programas y convocatorias
- Scenarios de mentorías completas
- Datos de analytics y métricas realistas
- Workflows de evaluación y selección
- Configuraciones de notificaciones
- Datos de integraciones externas
- Fixtures de reportes y dashboards
- Scenarios de escalamiento y growth
- Configuraciones multi-tenant
- Datos de performance empresarial

Tipos de fixtures incluidas:
- Domain-specific: Específicas del ecosistema
- Workflow: Para procesos de negocio completos
- Analytics: Para testing de métricas y reportes
- Integration: Para testing de servicios externos
- Performance: Para testing de carga específica
- Business Rules: Para reglas de negocio complejas

Uso:
    from tests.fixtures import (
        startup_accelerator_program, mentorship_complete_session,
        analytics_dashboard_data, investor_matching_scenario
    )
    
    def test_accelerator_application(startup_accelerator_program):
        program = startup_accelerator_program
        assert program['applications_open'] is True
        assert len(program['mentors']) >= 5

Author: Sistema de Testing Empresarial  
Created: 2025-06-13
Version: 2.1.0
"""

import os
import json
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple, Generator
from dataclasses import dataclass, field
from enum import Enum
import random

import pytest
import factory
from faker import Faker

# Imports del framework base
from tests import (
    logger, fake, db_session, 
    UserFactory, EntrepreneurFactory, AllyFactory, ClientFactory,
    ProjectFactory, MeetingFactory, MessageFactory
)

# Imports del proyecto
try:
    from app.models.user import User
    from app.models.entrepreneur import Entrepreneur  
    from app.models.ally import Ally
    from app.models.client import Client
    from app.models.project import Project
    from app.models.meeting import Meeting
    from app.models.organization import Organization
    from app.models.program import Program
    from app.models.mentorship import MentorshipSession
    from app.models.notification import Notification
    from app.models.analytics import AnalyticsEvent
    from app.services.analytics_service import AnalyticsService
except ImportError as e:
    logger.warning(f"Algunos modelos no disponibles: {e}")


# ============================================================================
# ENUMS Y CLASES DE SOPORTE
# ============================================================================

class ProgramType(Enum):
    ACCELERATOR = "accelerator"
    INCUBATOR = "incubator"
    BOOTCAMP = "bootcamp"
    COMPETITION = "competition"
    FELLOWSHIP = "fellowship"


class ProjectStage(Enum):
    IDEA = "idea"
    VALIDATION = "validation"
    PROTOTYPE = "prototype"
    MVP = "mvp"
    GROWTH = "growth"
    SCALE = "scale"


class IndustryVertical(Enum):
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    AGTECH = "agtech"
    CLEANTECH = "cleantech"
    RETAIL = "retail"
    LOGISTICS = "logistics"
    ENTERTAINMENT = "entertainment"


@dataclass
class ProgramConfiguration:
    """Configuración de programa de emprendimiento."""
    name: str
    type: ProgramType
    duration_weeks: int
    investment_amount: int
    equity_percentage: float
    batch_size: int
    focus_industries: List[IndustryVertical]
    application_deadline: datetime
    program_start_date: datetime
    requirements: Dict[str, Any] = field(default_factory=dict)
    benefits: List[str] = field(default_factory=list)
    mentor_count: int = 10
    success_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EcosystemMetrics:
    """Métricas del ecosistema para analytics."""
    total_entrepreneurs: int
    active_projects: int
    completed_mentorships: int
    total_funding_raised: Decimal
    average_project_valuation: Decimal
    success_rate_percentage: float
    geographic_distribution: Dict[str, int]
    industry_distribution: Dict[str, int]
    monthly_growth_rate: float
    retention_rate: float


# ============================================================================
# FIXTURES DE CONFIGURACIÓN DEL ECOSISTEMA
# ============================================================================

@pytest.fixture(scope='session')
def ecosystem_configuration():
    """Configuración global del ecosistema."""
    config = {
        'name': 'Ecosistema Emprendimiento Colombia',
        'version': '2.1.0',
        'supported_countries': ['CO', 'MX', 'PE', 'CL', 'AR'],
        'default_currency': 'COP',
        'supported_languages': ['es', 'en'],
        'timezone': 'America/Bogota',
        'max_projects_per_entrepreneur': 5,
        'max_mentors_per_project': 3,
        'default_mentorship_duration_hours': 1,
        'application_review_days': 14,
        'funding_rounds': ['pre_seed', 'seed', 'series_a', 'series_b'],
        'evaluation_criteria': {
            'team': 0.3,
            'market': 0.25,
            'product': 0.25,
            'traction': 0.2
        },
        'notification_channels': ['email', 'sms', 'in_app', 'slack'],
        'file_storage_providers': ['aws_s3', 'google_cloud', 'azure'],
        'analytics_providers': ['google_analytics', 'mixpanel', 'amplitude'],
    }
    
    logger.info(f"🌍 Configuración del ecosistema cargada: {config['name']} v{config['version']}")
    return config


@pytest.fixture(scope='function')
def multi_language_content():
    """Contenido en múltiples idiomas para testing i18n."""
    content = {
        'es': {
            'welcome_message': 'Bienvenido al ecosistema de emprendimiento',
            'application_submitted': 'Tu aplicación ha sido enviada exitosamente',
            'mentorship_scheduled': 'Tu sesión de mentoría ha sido programada',
            'project_approved': 'Tu proyecto ha sido aprobado',
            'funding_received': 'Has recibido financiación',
            'program_completed': 'Felicitaciones, has completado el programa'
        },
        'en': {
            'welcome_message': 'Welcome to the entrepreneurship ecosystem',
            'application_submitted': 'Your application has been submitted successfully',
            'mentorship_scheduled': 'Your mentorship session has been scheduled',
            'project_approved': 'Your project has been approved',
            'funding_received': 'You have received funding',
            'program_completed': 'Congratulations, you have completed the program'
        }
    }
    
    return content


# ============================================================================
# FIXTURES DE PROGRAMAS DE EMPRENDIMIENTO
# ============================================================================

@pytest.fixture(scope='function')
def startup_accelerator_program(db_session):
    """Programa acelerador completo con mentores y recursos."""
    program_config = ProgramConfiguration(
        name="TechStart Accelerator 2025",
        type=ProgramType.ACCELERATOR,
        duration_weeks=12,
        investment_amount=50000,
        equity_percentage=7.0,
        batch_size=20,
        focus_industries=[IndustryVertical.FINTECH, IndustryVertical.HEALTHTECH],
        application_deadline=datetime.utcnow() + timedelta(days=30),
        program_start_date=datetime.utcnow() + timedelta(days=60),
        requirements={
            'min_team_size': 2,
            'max_team_size': 4,
            'min_traction': 'mvp_launched',
            'geographic_restriction': 'latam',
            'previous_funding': 'optional'
        },
        benefits=[
            'Inversión inicial de $50,000 USD',
            'Mentoría intensiva con expertos',
            'Acceso a red de inversionistas',
            'Oficinas en hub tecnológico',
            'Demo Day con 200+ inversionistas'
        ],
        mentor_count=15,
        success_metrics={
            'target_next_funding': 500000,
            'expected_graduation_rate': 0.85,
            'job_creation_target': 50,
            'revenue_growth_target': 300
        }
    )
    
    # Crear organización que maneja el programa
    organization = {
        'id': 1,
        'name': 'TechStart Ventures',
        'type': 'accelerator',
        'country': 'CO',
        'city': 'Bogotá',
        'founded_year': 2018,
        'total_investments': 5000000,
        'portfolio_companies': 75,
        'successful_exits': 8
    }
    
    # Crear mentores especializados
    mentors = []
    mentor_specialties = [
        ('business_strategy', 'Estrategia de Negocio'),
        ('finance', 'Finanzas y Fundraising'), 
        ('marketing', 'Marketing Digital'),
        ('product', 'Desarrollo de Producto'),
        ('sales', 'Ventas y Business Development'),
        ('legal', 'Legal y Compliance'),
        ('hr', 'Recursos Humanos'),
        ('technology', 'Tecnología y Arquitectura'),
        ('operations', 'Operaciones'),
        ('international', 'Expansión Internacional')
    ]
    
    for i, (specialty, description) in enumerate(mentor_specialties):
        mentor_user = UserFactory(
            email=f'mentor_{specialty}@techstart.com',
            role_type='ally'
        )
        
        mentor = AllyFactory(
            user=mentor_user,
            expertise_areas=[specialty],
            experience_years=10 + i,
            hourly_rate=150 + (i * 25),
            bio=f'Experto en {description} con más de {10 + i} años de experiencia'
        )
        
        mentors.append({
            'user': mentor_user,
            'profile': mentor,
            'specialty': specialty,
            'description': description,
            'availability_hours': 10 + (i * 2),
            'success_stories': random.randint(5, 25),
            'average_rating': round(4.2 + (random.random() * 0.8), 1)
        })
    
    # Crear aplicaciones de ejemplo
    applications = []
    for i in range(25):  # 25 aplicaciones para 20 cupos
        entrepreneur_user = UserFactory(
            email=f'applicant_{i}@startup{i}.com',
            role_type='entrepreneur'
        )
        
        entrepreneur = EntrepreneurFactory(
            user=entrepreneur_user,
            business_name=f'Startup Innovadora {i}',
            stage=random.choice(list(ProjectStage)).value,
            industry=random.choice(list(IndustryVertical)).value
        )
        
        application = {
            'id': i + 1,
            'entrepreneur': entrepreneur,
            'status': random.choice(['pending', 'under_review', 'approved', 'rejected']),
            'submitted_at': datetime.utcnow() - timedelta(days=random.randint(1, 20)),
            'pitch_deck_url': f'https://storage.example.com/pitches/startup_{i}.pdf',
            'team_size': random.randint(2, 4),
            'funding_raised': random.randint(0, 100000),
            'monthly_revenue': random.randint(0, 50000),
            'evaluation_score': round(random.uniform(6.0, 9.5), 1),
            'reviewer_notes': f'Startup con potencial en {entrepreneur.industry}'
        }
        
        applications.append(application)
    
    db_session.commit()
    
    program_data = {
        'config': program_config,
        'organization': organization,
        'mentors': mentors,
        'applications': applications,
        'current_batch': None,  # Se asigna cuando empieza el programa
        'statistics': {
            'total_applications': len(applications),
            'approved_applications': len([a for a in applications if a['status'] == 'approved']),
            'average_evaluation_score': sum(a['evaluation_score'] for a in applications) / len(applications),
            'industry_distribution': {},
            'geographic_distribution': {}
        }
    }
    
    logger.info(f"🚀 Programa acelerador creado: {program_config.name}")
    logger.info(f"📊 {len(applications)} aplicaciones, {len(mentors)} mentores")
    
    yield program_data


@pytest.fixture(scope='function')
def social_impact_incubator(db_session):
    """Incubadora de impacto social completa."""
    program_config = ProgramConfiguration(
        name="Incubadora Impacto Social",
        type=ProgramType.INCUBATOR,
        duration_weeks=24,
        investment_amount=25000,
        equity_percentage=5.0,
        batch_size=15,
        focus_industries=[IndustryVertical.EDTECH, IndustryVertical.CLEANTECH],
        application_deadline=datetime.utcnow() + timedelta(days=45),
        program_start_date=datetime.utcnow() + timedelta(days=75),
        requirements={
            'social_impact_focus': True,
            'sustainability_metrics': True,
            'community_validation': True,
            'impact_measurement_plan': True
        },
        benefits=[
            'Financiación no reembolsable $25,000 USD',
            'Mentoría en impacto social',
            'Acceso a fundaciones y donantes',
            'Certificación B-Corp',
            'Red de emprendimiento social'
        ],
        success_metrics={
            'target_beneficiaries': 10000,
            'sdg_alignment': True,
            'sustainability_certification': True,
            'social_roi': 300
        }
    )
    
    # Crear proyectos de impacto social
    social_projects = []
    impact_areas = [
        'educación_rural', 'acceso_agua_potable', 'energía_renovable',
        'agricultura_sostenible', 'salud_comunitaria', 'inclusión_digital'
    ]
    
    for i, area in enumerate(impact_areas):
        entrepreneur_user = UserFactory(
            email=f'social_entrepreneur_{i}@impact.org',
            role_type='entrepreneur'
        )
        
        entrepreneur = EntrepreneurFactory(
            user=entrepreneur_user,
            business_name=f'Impacto {area.replace("_", " ").title()}',
            stage='prototype',
            industry='social_impact'
        )
        
        project = ProjectFactory(
            entrepreneur=entrepreneur,
            name=f'Proyecto {area.replace("_", " ").title()}',
            description=f'Solución innovadora para {area.replace("_", " ")}',
            budget=random.randint(20000, 80000)
        )
        
        social_project = {
            'project': project,
            'impact_area': area,
            'target_beneficiaries': random.randint(1000, 50000),
            'sdg_goals': random.sample(['SDG3', 'SDG4', 'SDG6', 'SDG7', 'SDG8'], 2),
            'impact_metrics': {
                'lives_improved': random.randint(500, 25000),
                'co2_reduction_tons': random.randint(10, 1000),
                'jobs_created': random.randint(5, 50),
                'communities_served': random.randint(2, 20)
            },
            'sustainability_plan': f'Plan de sostenibilidad para {area}',
            'community_validation': True
        }
        
        social_projects.append(social_project)
    
    db_session.commit()
    
    yield {
        'config': program_config,
        'social_projects': social_projects,
        'impact_framework': {
            'measurement_methodology': 'Theory of Change + Impact Measurement',
            'reporting_frequency': 'quarterly',
            'evaluation_criteria': ['impact_potential', 'sustainability', 'scalability', 'innovation'],
            'certification_partners': ['B-Corp', 'Ashoka', 'Acumen Academy']
        }
    }


# ============================================================================
# FIXTURES DE SESIONES DE MENTORÍA
# ============================================================================

@pytest.fixture(scope='function')
def mentorship_complete_session(db_session):
    """Sesión completa de mentoría con todos los componentes."""
    # Crear emprendedor
    entrepreneur_user = UserFactory(
        email='entrepreneur@mentorship.test',
        role_type='entrepreneur'
    )
    entrepreneur = EntrepreneurFactory(
        user=entrepreneur_user,
        business_name='StartupTech Solutions',
        stage='mvp'
    )
    
    # Crear proyecto
    project = ProjectFactory(
        entrepreneur=entrepreneur,
        name='Plataforma AI para PyMEs',
        status='active',
        budget=100000
    )
    
    # Crear mentor
    mentor_user = UserFactory(
        email='mentor@techexpert.com',
        role_type='ally'
    )
    mentor = AllyFactory(
        user=mentor_user,
        expertise_areas=['technology', 'business_strategy'],
        experience_years=15,
        hourly_rate=200
    )
    
    # Crear sesión de mentoría
    session_data = {
        'id': 1,
        'entrepreneur': entrepreneur,
        'mentor': mentor,
        'project': project,
        'scheduled_at': datetime.utcnow() + timedelta(hours=2),
        'duration_minutes': 90,
        'session_type': 'strategic_review',
        'agenda': [
            'Revisión de modelo de negocio',
            'Estrategia de go-to-market',
            'Plan de fundraising',
            'Roadmap técnico Q2-Q3',
            'Próximos pasos y KPIs'
        ],
        'pre_session_materials': [
            {
                'type': 'pitch_deck',
                'url': 'https://storage.example.com/pitches/startuptech_v2.pdf',
                'title': 'Pitch Deck Actualizado'
            },
            {
                'type': 'financial_model',
                'url': 'https://storage.example.com/finance/financial_model.xlsx',
                'title': 'Modelo Financiero 3 años'
            },
            {
                'type': 'product_demo',
                'url': 'https://demo.startuptech.com',
                'title': 'Demo Interactivo MVP'
            }
        ],
        'session_objectives': [
            'Validar estrategia de monetización',
            'Definir métricas clave de producto',
            'Planificar ronda de inversión seed',
            'Identificar socios estratégicos potenciales'
        ],
        'mentor_preparation_notes': 'Revisar tendencias AI/ML en PyMEs y casos de éxito similares',
        'google_meet_link': 'https://meet.google.com/abc-defg-hij',
        'calendar_event_id': 'cal_event_12345',
        'status': 'scheduled',
        'session_cost': 300,  # 90 min * $200/hour
        'payment_status': 'pending'
    }
    
    # Crear registro de sesiones anteriores
    previous_sessions = []
    for i in range(3):
        prev_session = {
            'id': i + 10,
            'date': datetime.utcnow() - timedelta(days=(i + 1) * 14),
            'duration_minutes': 60,
            'session_type': ['technical_review', 'market_analysis', 'team_building'][i],
            'completed': True,
            'rating_entrepreneur': random.uniform(4.0, 5.0),
            'rating_mentor': random.uniform(4.2, 5.0),
            'key_outcomes': [
                'Redefinición de MVP features',
                'Validación de customer segments',
                'Plan de contratación CTO',
                'Estrategia de pricing'
            ][i:i+2],
            'action_items_completed': random.randint(3, 7),
            'follow_up_scheduled': True
        }
        previous_sessions.append(prev_session)
    
    # Crear métricas de progreso
    progress_metrics = {
        'total_sessions': len(previous_sessions),
        'average_session_rating': 4.6,
        'action_items_completion_rate': 0.85,
        'key_milestones_achieved': [
            'MVP lanzado exitosamente',
            'Primeros 100 usuarios registrados',
            'Validación product-market fit inicial',
            'Equipo técnico completado'
        ],
        'current_challenges': [
            'Escalamiento de infraestructura',
            'Optimización de customer acquisition cost',
            'Preparación para ronda de inversión'
        ],
        'recommended_next_steps': [
            'Implementar analytics avanzados',
            'Desarrollar partnerships estratégicos',
            'Preparar due diligence materials'
        ]
    }
    
    # Crear plan de seguimiento
    follow_up_plan = {
        'next_session_date': datetime.utcnow() + timedelta(days=14),
        'interim_checkins': [
            {
                'date': datetime.utcnow() + timedelta(days=7),
                'type': 'progress_update',
                'method': 'email'
            }
        ],
        'deliverables_due': [
            {
                'item': 'Métricas de usuario actualizadas',
                'due_date': datetime.utcnow() + timedelta(days=5),
                'responsible': 'entrepreneur'
            },
            {
                'item': 'Conexiones con inversionistas',
                'due_date': datetime.utcnow() + timedelta(days=10),
                'responsible': 'mentor'
            }
        ],
        'success_metrics': [
            'MAU growth > 20%',
            'CAC < $50',
            'NPS > 8.0',
            'Fundraising deck ready'
        ]
    }
    
    db_session.commit()
    
    complete_session = {
        'current_session': session_data,
        'previous_sessions': previous_sessions,
        'progress_metrics': progress_metrics,
        'follow_up_plan': follow_up_plan,
        'mentorship_program': {
            'total_duration_months': 6,
            'sessions_remaining': 8,
            'program_goals': [
                'Escalar producto a 1000+ usuarios',
                'Completar ronda seed $500K+',
                'Establecer product-market fit sólido',
                'Construir equipo de 10+ personas'
            ]
        }
    }
    
    logger.info(f"🎯 Sesión de mentoría completa creada")
    logger.info(f"📈 {len(previous_sessions)} sesiones anteriores, próxima: {session_data['scheduled_at']}")
    
    yield complete_session


@pytest.fixture(scope='function')
def group_mentorship_session(db_session):
    """Sesión de mentoría grupal con múltiples emprendedores."""
    # Crear mentor experto
    mentor_user = UserFactory(
        email='expert@groupmentor.com',
        role_type='ally'
    )
    mentor = AllyFactory(
        user=mentor_user,
        expertise_areas=['marketing', 'growth_hacking', 'fundraising'],
        experience_years=20,
        hourly_rate=300
    )
    
    # Crear múltiples emprendedores
    participants = []
    for i in range(5):
        entrepreneur_user = UserFactory(
            email=f'entrepreneur_{i}@group.test',
            role_type='entrepreneur'
        )
        entrepreneur = EntrepreneurFactory(
            user=entrepreneur_user,
            business_name=f'Startup Grupo {i}',
            stage=random.choice(['prototype', 'mvp', 'growth'])
        )
        
        project = ProjectFactory(
            entrepreneur=entrepreneur,
            name=f'Proyecto Colaborativo {i}',
            status='active'
        )
        
        participants.append({
            'entrepreneur': entrepreneur,
            'project': project,
            'current_challenge': random.choice([
                'customer_acquisition',
                'product_development',
                'team_building',
                'fundraising',
                'market_expansion'
            ]),
            'goals_for_session': [
                'Obtener feedback de otros emprendedores',
                'Aprender mejores prácticas',
                'Establecer colaboraciones',
                'Resolver challenge específico'
            ]
        })
    
    group_session = {
        'id': 100,
        'mentor': mentor,
        'participants': participants,
        'session_format': 'workshop_interactive',
        'scheduled_at': datetime.utcnow() + timedelta(days=1),
        'duration_minutes': 120,
        'max_participants': 6,
        'current_participants': len(participants),
        'topic': 'Growth Hacking para Startups Early-Stage',
        'agenda': [
            '🎯 Bienvenida y objetivos (10 min)',
            '🧠 Presentación: Framework de Growth (30 min)',
            '💡 Caso de estudio: Startup exitosa (20 min)',
            '🤝 Sesión colaborativa: Challenges individuales (40 min)',
            '📋 Plan de acción y compromisos (20 min)'
        ],
        'interactive_elements': [
            'Breakout rooms por industria',
            'Peer feedback sessions',
            'Collaborative problem solving',
            'Resource sharing',
            'Network building'
        ],
        'materials_provided': [
            'Growth Hacking Toolkit',
            'Customer Acquisition Templates',
            'Metrics Dashboard Template',
            'A/B Testing Framework',
            'Contact directory participantes'
        ],
        'follow_up_activities': [
            'Grupo WhatsApp para seguimiento',
            'Monthly peer check-ins',
            'Resource sharing channel',
            'Collaborative projects board'
        ],
        'cost_per_participant': 60,
        'total_session_revenue': len(participants) * 60
    }
    
    db_session.commit()
    
    yield group_session


# ============================================================================
# FIXTURES DE ANALYTICS Y MÉTRICAS
# ============================================================================

@pytest.fixture(scope='function')
def analytics_dashboard_data():
    """Datos completos para dashboard de analytics."""
    current_date = datetime.utcnow()
    
    # Métricas generales del ecosistema
    ecosystem_metrics = EcosystemMetrics(
        total_entrepreneurs=1250,
        active_projects=380,
        completed_mentorships=2150,
        total_funding_raised=Decimal('15500000.00'),
        average_project_valuation=Decimal('850000.00'),
        success_rate_percentage=68.5,
        geographic_distribution={
            'Bogotá': 420,
            'Medellín': 280,
            'Cali': 180,
            'Barranquilla': 120,
            'Bucaramanga': 95,
            'Otras': 155
        },
        industry_distribution={
            'fintech': 285,
            'healthtech': 220,
            'edtech': 195,
            'agtech': 145,
            'cleantech': 125,
            'retail': 110,
            'logistics': 95,
            'otros': 75
        },
        monthly_growth_rate=12.8,
        retention_rate=84.2
    )
    
    # Métricas de performance mensual
    monthly_metrics = []
    for i in range(12):
        month_date = current_date - timedelta(days=30 * i)
        metrics = {
            'month': month_date.strftime('%Y-%m'),
            'new_entrepreneurs': random.randint(80, 150),
            'new_projects': random.randint(25, 45),
            'completed_mentorships': random.randint(120, 200),
            'funding_events': random.randint(5, 15),
            'total_funding': random.randint(800000, 2500000),
            'graduation_rate': round(random.uniform(0.65, 0.85), 3),
            'nps_score': round(random.uniform(7.5, 9.2), 1),
            'active_mentors': random.randint(45, 65),
            'mentor_utilization': round(random.uniform(0.70, 0.90), 3),
            'revenue_generated': random.randint(15000, 35000)
        }
        monthly_metrics.append(metrics)
    
    # Métricas de programas
    program_metrics = [
        {
            'program_name': 'TechStart Accelerator',
            'current_batch': 3,
            'total_cohorts': 8,
            'total_graduates': 145,
            'success_rate': 0.72,
            'average_funding_raised': 450000,
            'jobs_created': 680,
            'companies_still_active': 104,
            'acquired_companies': 8,
            'unicorn_potential': 3,
            'next_demo_day': current_date + timedelta(days=45)
        },
        {
            'program_name': 'Incubadora Social',
            'current_batch': 2,
            'total_cohorts': 5,
            'total_graduates': 68,
            'success_rate': 0.78,
            'beneficiaries_impacted': 125000,
            'sdg_goals_addressed': 12,
            'sustainability_certified': 45,
            'social_roi_average': 380,
            'next_impact_showcase': current_date + timedelta(days=30)
        }
    ]
    
    # Métricas de mentorías
    mentorship_analytics = {
        'total_sessions_completed': 2150,
        'average_session_duration': 75,  # minutos
        'average_rating': 4.6,
        'mentor_retention_rate': 0.88,
        'entrepreneur_satisfaction': 0.92,
        'top_mentorship_topics': [
            ('business_strategy', 485),
            ('fundraising', 420),
            ('marketing', 385),
            ('product_development', 340),
            ('team_building', 295),
            ('legal_compliance', 225)
        ],
        'success_outcomes': {
            'funding_secured_post_mentorship': 0.34,
            'revenue_growth_average': 240,  # %
            'team_expansion_average': 3.2,  # nuevos miembros
            'product_launches': 0.67,
            'partnership_established': 0.28
        },
        'mentor_utilization_by_expertise': {
            'technology': 0.85,
            'business_strategy': 0.92,
            'marketing': 0.78,
            'finance': 0.88,
            'legal': 0.65,
            'operations': 0.72,
            'sales': 0.81,
            'hr': 0.58
        }
    }
    
    # Métricas de usuario y engagement
    user_engagement = {
        'daily_active_users': {
            'entrepreneurs': 145,
            'mentors': 38,
            'admin_staff': 12,
            'clients': 22
        },
        'weekly_active_users': {
            'entrepreneurs': 520,
            'mentors': 85,
            'admin_staff': 15,
            'clients': 45
        },
        'monthly_active_users': {
            'entrepreneurs': 1150,
            'mentors': 125,
            'admin_staff': 18,
            'clients': 78
        },
        'feature_usage': {
            'project_management': 0.85,
            'messaging_system': 0.92,
            'calendar_integration': 0.68,
            'document_sharing': 0.76,
            'video_calls': 0.84,
            'analytics_dashboard': 0.45,
            'mobile_app': 0.62
        },
        'user_journey_completion': {
            'onboarding_completion': 0.87,
            'profile_completion': 0.78,
            'first_project_creation': 0.65,
            'first_mentorship_booking': 0.52,
            'program_application': 0.34,
            'graduation_achievement': 0.28
        }
    }
    
    # Métricas financieras del ecosistema
    financial_metrics = {
        'total_ecosystem_revenue': Decimal('2850000.00'),
        'revenue_by_source': {
            'program_fees': Decimal('1650000.00'),
            'mentorship_commissions': Decimal('485000.00'),
            'corporate_partnerships': Decimal('380000.00'),
            'government_grants': Decimal('285000.00'),
            'event_sponsorships': Decimal('50000.00')
        },
        'cost_structure': {
            'staff_salaries': Decimal('1200000.00'),
            'technology_infrastructure': Decimal('180000.00'),
            'mentor_payments': Decimal('445000.00'),
            'program_operations': Decimal('220000.00'),
            'marketing_acquisition': Decimal('145000.00'),
            'office_facilities': Decimal('95000.00'),
            'legal_compliance': Decimal('45000.00')
        },
        'profitability': {
            'gross_margin': 0.72,
            'net_margin': 0.18,
            'cac_payback_months': 8.5,
            'ltv_cac_ratio': 4.2,
            'monthly_recurring_revenue': Decimal('185000.00'),
            'churn_rate': 0.045
        }
    }
    
    # Proyecciones y forecasting
    forecasting_data = {
        'next_quarter_projections': {
            'new_entrepreneurs': 420,
            'new_funding_events': 35,
            'projected_funding': Decimal('8500000.00'),
            'new_partnerships': 8,
            'program_launches': 2
        },
        'yearly_goals': {
            'total_entrepreneurs_target': 2000,
            'funding_raised_target': Decimal('25000000.00'),
            'job_creation_target': 1200,
            'international_expansion': ['México', 'Perú'],
            'new_programs_launch': 3
        },
        'trend_analysis': {
            'fastest_growing_industry': 'healthtech',
            'emerging_trends': ['AI/ML integration', 'Sustainability focus', 'Remote-first teams'],
            'market_opportunities': ['B2B SaaS', 'Climate tech', 'Digital health'],
            'risk_factors': ['Economic uncertainty', 'Competition increase', 'Talent shortage']
        }
    }
    
    dashboard_data = {
        'ecosystem_overview': ecosystem_metrics,
        'monthly_trends': monthly_metrics,
        'program_performance': program_metrics,
        'mentorship_analytics': mentorship_analytics,
        'user_engagement': user_engagement,
        'financial_health': financial_metrics,
        'forecasting': forecasting_data,
        'last_updated': current_date,
        'data_quality_score': 0.94,
        'real_time_alerts': [
            {
                'type': 'milestone_achieved',
                'message': 'Se alcanzaron 1,250 emprendedores registrados',
                'timestamp': current_date - timedelta(hours=2)
            },
            {
                'type': 'funding_event',
                'message': 'Startup XYZ cerró ronda seed de $800K',
                'timestamp': current_date - timedelta(hours=6)
            }
        ]
    }
    
    logger.info("📊 Dashboard completo de analytics generado")
    logger.info(f"📈 {ecosystem_metrics.total_entrepreneurs} emprendedores, ${ecosystem_metrics.total_funding_raised:,} en funding")
    
    yield dashboard_data


@pytest.fixture(scope='function')
def cohort_analysis_data():
    """Datos de análisis de cohortes para programas."""
    cohorts = []
    
    # Generar 8 cohortes históricas
    for cohort_num in range(1, 9):
        start_date = datetime.utcnow() - timedelta(days=365 + (cohort_num * 120))
        
        cohort = {
            'cohort_id': f'TECH_2023_C{cohort_num}',
            'program': 'TechStart Accelerator',
            'start_date': start_date,
            'end_date': start_date + timedelta(days=84),  # 12 semanas
            'initial_participants': random.randint(18, 22),
            'graduates': random.randint(15, 20),
            'graduation_rate': None,  # Se calcula después
            'demographics': {
                'average_age': random.randint(28, 35),
                'gender_distribution': {
                    'male': random.uniform(0.45, 0.65),
                    'female': random.uniform(0.30, 0.50),
                    'other': random.uniform(0.02, 0.08)
                },
                'education_level': {
                    'bachelor': random.uniform(0.35, 0.45),
                    'master': random.uniform(0.40, 0.55),
                    'phd': random.uniform(0.05, 0.15),
                    'other': random.uniform(0.02, 0.08)
                },
                'previous_experience': {
                    'first_time_founder': random.uniform(0.55, 0.75),
                    'repeat_founder': random.uniform(0.20, 0.35),
                    'corporate_background': random.uniform(0.60, 0.80)
                }
            },
            'outcomes_6_months': {
                'still_operating': random.randint(12, 18),
                'funding_raised': random.randint(8, 15),
                'total_funding_amount': random.randint(2500000, 8500000),
                'average_funding_per_company': None,  # Se calcula
                'jobs_created': random.randint(45, 120),
                'revenue_generating': random.randint(10, 16),
                'partnerships_established': random.randint(15, 35)
            },
            'outcomes_12_months': {
                'still_operating': random.randint(10, 16),
                'funding_raised': random.randint(10, 17),
                'total_funding_amount': random.randint(4500000, 15000000),
                'jobs_created': random.randint(80, 200),
                'revenue_generating': random.randint(12, 18),
                'series_a_ready': random.randint(3, 8),
                'acquired': random.randint(0, 2),
                'failed': random.randint(2, 6)
            },
            'success_metrics': {
                'product_market_fit_achieved': random.uniform(0.60, 0.85),
                'customer_validation_score': random.uniform(7.5, 9.2),
                'team_retention_rate': random.uniform(0.75, 0.92),
                'mentor_satisfaction': random.uniform(4.2, 4.8),
                'nps_score': random.uniform(7.8, 9.1)
            },
            'top_performing_startups': [
                {
                    'name': f'TopCo {cohort_num}.1',
                    'industry': random.choice(['fintech', 'healthtech', 'edtech']),
                    'funding_raised': random.randint(1000000, 5000000),
                    'employees': random.randint(15, 50),
                    'valuation': random.randint(8000000, 50000000)
                },
                {
                    'name': f'StarCorp {cohort_num}.2',
                    'industry': random.choice(['cleantech', 'logistics', 'retail']),
                    'funding_raised': random.randint(500000, 3000000),
                    'employees': random.randint(8, 30),
                    'valuation': random.randint(4000000, 25000000)
                }
            ]
        }
        
        # Calcular métricas derivadas
        cohort['graduation_rate'] = cohort['graduates'] / cohort['initial_participants']
        
        if cohort['outcomes_6_months']['funding_raised'] > 0:
            cohort['outcomes_6_months']['average_funding_per_company'] = (
                cohort['outcomes_6_months']['total_funding_amount'] / 
                cohort['outcomes_6_months']['funding_raised']
            )
        
        cohorts.append(cohort)
    
    # Análisis comparativo entre cohortes
    comparative_analysis = {
        'best_performing_cohort': max(cohorts, key=lambda x: x['graduation_rate'])['cohort_id'],
        'average_graduation_rate': sum(c['graduation_rate'] for c in cohorts) / len(cohorts),
        'total_funding_all_cohorts': sum(c['outcomes_12_months']['total_funding_amount'] for c in cohorts),
        'total_jobs_created': sum(c['outcomes_12_months']['jobs_created'] for c in cohorts),
        'total_companies_still_operating': sum(c['outcomes_12_months']['still_operating'] for c in cohorts),
        'improvement_trends': {
            'graduation_rate_trend': 'improving',  # Últimas 3 cohortes vs primeras 3
            'funding_success_trend': 'stable',
            'job_creation_trend': 'improving',
            'survival_rate_trend': 'improving'
        },
        'key_learnings': [
            'Cohortes con mayor diversidad de género tienen mejor performance',
            'Founders con experiencia corporativa tienden a crear más empleos',
            'Programas de 12 semanas muestran mejor ROI que 8 semanas',
            'Mentorías especializadas por industria incrementan éxito'
        ]
    }
    
    yield {
        'cohorts': cohorts,
        'comparative_analysis': comparative_analysis,
        'methodology': {
            'tracking_period': '12_months_post_graduation',
            'success_definition': 'Still operating + revenue generating',
            'data_sources': ['CRM', 'Financial reports', 'Surveys', 'Public records'],
            'update_frequency': 'quarterly',
            'quality_score': 0.91
        }
    }


# ============================================================================
# FIXTURES DE WORKFLOWS COMPLEJOS
# ============================================================================

@pytest.fixture(scope='function')
def investor_matching_scenario(db_session):
    """Scenario completo de matching entre startups e inversionistas."""
    
    # Crear inversionistas/clientes con diferentes perfiles
    investors = []
    investor_profiles = [
        {
            'name': 'Venture Capital Latam',
            'type': 'vc_fund',
            'investment_range': (500000, 5000000),
            'stage_focus': ['seed', 'series_a'],
            'industry_focus': ['fintech', 'healthtech'],
            'geographic_focus': ['colombia', 'mexico', 'chile'],
            'portfolio_size': 45,
            'successful_exits': 8,
            'investment_criteria': {
                'min_revenue': 50000,
                'min_team_size': 3,
                'market_size_min': 100000000,
                'scalability_required': True
            }
        },
        {
            'name': 'Angel Investor Network',
            'type': 'angel_group',
            'investment_range': (25000, 500000),
            'stage_focus': ['pre_seed', 'seed'],
            'industry_focus': ['edtech', 'cleantech', 'agtech'],
            'geographic_focus': ['colombia'],
            'portfolio_size': 120,
            'successful_exits': 25,
            'investment_criteria': {
                'social_impact_required': True,
                'founder_coachability': 'high',
                'prototype_required': True,
                'local_market_validation': True
            }
        },
        {
            'name': 'Corporate Ventures',
            'type': 'corporate_vc',
            'investment_range': (100000, 2000000),
            'stage_focus': ['seed', 'series_a'],
            'industry_focus': ['fintech', 'retail', 'logistics'],
            'geographic_focus': ['latam'],
            'portfolio_size': 28,
            'strategic_focus': 'innovation_partnerships',
            'investment_criteria': {
                'strategic_alignment': True,
                'technology_readiness': 'high',
                'partnership_potential': True,
                'enterprise_sales_ready': True
            }
        }
    ]
    
    for i, profile in enumerate(investor_profiles):
        investor_user = UserFactory(
            email=f'investor_{i}@{profile["name"].lower().replace(" ", "")}.com',
            role_type='client'
        )
        
        investor = ClientFactory(
            user=investor_user,
            organization=profile['name'],
            organization_type=profile['type'],
            investment_capacity=profile['investment_range'][1]
        )
        
        investor_data = {
            'profile': investor,
            'investment_profile': profile,
            'current_pipeline': [],
            'matching_score_threshold': 0.7,
            'last_investment_date': datetime.utcnow() - timedelta(days=random.randint(30, 180))
        }
        
        investors.append(investor_data)
    
    # Crear startups buscando inversión
    startups_seeking_funding = []
    for i in range(8):
        entrepreneur_user = UserFactory(
            email=f'founder_{i}@startup{i}.fund',
            role_type='entrepreneur'
        )
        
        entrepreneur = EntrepreneurFactory(
            user=entrepreneur_user,
            business_name=f'Startup Innovadora {i}',
            stage=random.choice(['prototype', 'mvp', 'growth']),
            industry=random.choice(['fintech', 'healthtech', 'edtech', 'cleantech'])
        )
        
        project = ProjectFactory(
            entrepreneur=entrepreneur,
            name=f'Proyecto Funding {i}',
            status='active',
            budget=random.randint(100000, 2000000)
        )
        
        # Perfil de funding
        funding_profile = {
            'seeking_amount': random.randint(250000, 3000000),
            'equity_offered': random.uniform(5.0, 25.0),
            'use_of_funds': {
                'product_development': random.uniform(0.25, 0.40),
                'marketing_sales': random.uniform(0.20, 0.35),
                'team_expansion': random.uniform(0.15, 0.30),
                'operations': random.uniform(0.10, 0.20),
                'working_capital': random.uniform(0.05, 0.15)
            },
            'current_metrics': {
                'monthly_revenue': random.randint(10000, 150000),
                'monthly_growth_rate': random.uniform(5.0, 25.0),
                'user_base': random.randint(1000, 50000),
                'team_size': random.randint(3, 15),
                'burn_rate': random.randint(15000, 80000),
                'runway_months': random.randint(6, 18)
            },
            'previous_funding': {
                'total_raised': random.randint(0, 500000),
                'investors': random.randint(0, 5),
                'last_round_date': datetime.utcnow() - timedelta(days=random.randint(180, 720)) if random.random() > 0.3 else None
            },
            'competitive_advantages': random.sample([
                'first_mover_advantage',
                'proprietary_technology',
                'strong_team',
                'proven_traction',
                'strategic_partnerships',
                'regulatory_moat',
                'network_effects',
                'data_advantage'
            ], 3),
            'target_market_size': random.randint(50000000, 1000000000),
            'go_to_market_strategy': random.choice([
                'direct_sales',
                'partner_channel',
                'digital_marketing',
                'enterprise_sales',
                'viral_growth'
            ])
        }
        
        startup_data = {
            'entrepreneur': entrepreneur,
            'project': project,
            'funding_profile': funding_profile,
            'pitch_materials': {
                'pitch_deck': f'https://storage.example.com/pitches/startup_{i}_deck.pdf',
                'financial_model': f'https://storage.example.com/models/startup_{i}_model.xlsx',
                'demo_video': f'https://storage.example.com/demos/startup_{i}_demo.mp4',
                'one_pager': f'https://storage.example.com/onepagers/startup_{i}.pdf'
            },
            'due_diligence_ready': random.choice([True, False]),
            'seeking_active': True,
            'last_pitch_date': datetime.utcnow() - timedelta(days=random.randint(7, 60))
        }
        
        startups_seeking_funding.append(startup_data)
    
    # Algoritmo de matching
    def calculate_matching_score(startup, investor):
        """Calcula score de matching entre startup e inversionista."""
        score = 0.0
        
        # Matching por industria (peso: 25%)
        if startup['entrepreneur'].industry in investor['investment_profile']['industry_focus']:
            score += 0.25
        
        # Matching por stage (peso: 20%)
        startup_stage = startup['entrepreneur'].stage
        if startup_stage in investor['investment_profile']['stage_focus']:
            score += 0.20
        
        # Matching por rango de inversión (peso: 20%)
        seeking_amount = startup['funding_profile']['seeking_amount']
        min_invest, max_invest = investor['investment_profile']['investment_range']
        if min_invest <= seeking_amount <= max_invest:
            score += 0.20
        elif seeking_amount < min_invest:
            score += 0.10  # Parcial si está cerca
        
        # Matching por métricas (peso: 15%)
        metrics = startup['funding_profile']['current_metrics']
        criteria = investor['investment_profile'].get('investment_criteria', {})
        
        if 'min_revenue' in criteria:
            if metrics['monthly_revenue'] >= criteria['min_revenue']:
                score += 0.05
        
        if 'min_team_size' in criteria:
            if metrics['team_size'] >= criteria['min_team_size']:
                score += 0.05
        
        if 'market_size_min' in criteria:
            if startup['funding_profile']['target_market_size'] >= criteria['market_size_min']:
                score += 0.05
        
        # Matching por criterios especiales (peso: 10%)
        if 'social_impact_required' in criteria:
            if startup['entrepreneur'].industry in ['edtech', 'cleantech', 'healthtech']:
                score += 0.05
        
        if 'strategic_alignment' in criteria:
            # Lógica específica para corporate VC
            if investor['investment_profile']['type'] == 'corporate_vc':
                score += 0.05
        
        # Factores adicionales (peso: 10%)
        if startup['due_diligence_ready']:
            score += 0.05
        
        if startup['funding_profile']['previous_funding']['total_raised'] > 0:
            score += 0.03  # Validación previa
        
        if metrics['monthly_growth_rate'] > 15:
            score += 0.02  # Alto crecimiento
        
        return min(score, 1.0)  # Cap at 1.0
    
    # Generar matches
    matches = []
    for startup in startups_seeking_funding:
        for investor in investors:
            score = calculate_matching_score(startup, investor)
            
            if score >= investor['matching_score_threshold']:
                match = {
                    'startup': startup,
                    'investor': investor,
                    'matching_score': round(score, 3),
                    'generated_at': datetime.utcnow(),
                    'status': 'pending_review',
                    'contact_initiated': False,
                    'next_steps': [
                        'Revisar pitch deck',
                        'Evaluar fit estratégico',
                        'Programar primera reunión',
                        'Solicitar due diligence materials'
                    ],
                    'estimated_timeline': '2-4 semanas',
                    'success_probability': score * 0.6  # Ajuste realista
                }
                matches.append(match)
    
    # Estadísticas del matching
    matching_stats = {
        'total_startups': len(startups_seeking_funding),
        'total_investors': len(investors),
        'total_matches_generated': len(matches),
        'average_matching_score': sum(m['matching_score'] for m in matches) / len(matches) if matches else 0,
        'matches_by_investor': {},
        'matches_by_industry': {},
        'high_quality_matches': len([m for m in matches if m['matching_score'] > 0.8]),
        'conversion_rate_estimate': 0.15  # 15% de matches resultan en inversión
    }
    
    # Agrupar estadísticas
    for match in matches:
        inv_name = match['investor']['investment_profile']['name']
        if inv_name not in matching_stats['matches_by_investor']:
            matching_stats['matches_by_investor'][inv_name] = 0
        matching_stats['matches_by_investor'][inv_name] += 1
        
        industry = match['startup']['entrepreneur'].industry
        if industry not in matching_stats['matches_by_industry']:
            matching_stats['matches_by_industry'][industry] = 0
        matching_stats['matches_by_industry'][industry] += 1
    
    db_session.commit()
    
    scenario_data = {
        'investors': investors,
        'startups_seeking_funding': startups_seeking_funding,
        'matches': matches,
        'matching_stats': matching_stats,
        'matching_algorithm': {
            'version': '2.1',
            'factors': [
                'industry_alignment',
                'stage_compatibility', 
                'investment_range_fit',
                'metrics_threshold',
                'strategic_criteria',
                'additional_factors'
            ],
            'weights': {
                'industry': 0.25,
                'stage': 0.20,
                'investment_range': 0.20,
                'metrics': 0.15,
                'special_criteria': 0.10,
                'additional': 0.10
            },
            'success_rate': 0.73,
            'last_updated': datetime.utcnow()
        }
    }
    
    logger.info(f"💰 Scenario de investor matching creado")
    logger.info(f"🎯 {len(matches)} matches generados entre {len(startups_seeking_funding)} startups y {len(investors)} investors")
    
    yield scenario_data


@pytest.fixture(scope='function')
def program_evaluation_workflow(db_session):
    """Workflow completo de evaluación y selección para programas."""
    
    # Crear programa con proceso de evaluación
    program_data = {
        'id': 1,
        'name': 'Accelerator Elite 2025',
        'type': 'accelerator',
        'application_deadline': datetime.utcnow() + timedelta(days=7),
        'program_start': datetime.utcnow() + timedelta(days=45),
        'available_spots': 15,
        'total_applications': 85,
        'evaluation_process': {
            'stages': [
                'application_review',
                'pitch_presentation', 
                'technical_evaluation',
                'final_interview',
                'committee_decision'
            ],
            'timeline_days': 21,
            'evaluators_per_stage': [2, 3, 2, 3, 5],
            'min_score_to_advance': [7.0, 7.5, 7.0, 8.0, 8.5]
        }
    }
    
    # Crear evaluadores
    evaluators = []
    evaluator_profiles = [
        ('senior_partner', 'María González', 15, ['business_strategy', 'fundraising']),
        ('investment_director', 'Carlos Rodríguez', 12, ['finance', 'venture_capital']),
        ('tech_lead', 'Ana Martínez', 8, ['technology', 'product_development']),
        ('marketing_expert', 'Luis Fernández', 10, ['marketing', 'growth']),
        ('industry_advisor', 'Sofia López', 20, ['industry_expertise', 'mentorship']),
        ('entrepreneur_in_residence', 'Diego Castro', 7, ['entrepreneurship', 'execution']),
        ('program_director', 'Carmen Ruiz', 6, ['program_management', 'education'])
    ]
    
    for role, name, experience, expertise in evaluator_profiles:
        evaluator_user = UserFactory(
            email=f'{name.lower().replace(" ", ".")}@accelerator.com',
            first_name=name.split()[0],
            last_name=name.split()[1],
            role_type='admin'
        )
        
        evaluator = {
            'user': evaluator_user,
            'role': role,
            'experience_years': experience,
            'expertise_areas': expertise,
            'evaluation_history': {
                'total_evaluations': random.randint(50, 200),
                'average_score_given': round(random.uniform(6.5, 8.5), 1),
                'accuracy_rate': round(random.uniform(0.75, 0.95), 2),
                'specialization_performance': random.uniform(0.80, 0.95)
            },
            'current_workload': random.randint(5, 15),
            'availability_hours_week': random.randint(8, 20)
        }
        
        evaluators.append(evaluator)
    
    # Crear aplicaciones en diferentes etapas
    applications = []
    
    for app_id in range(1, 86):  # 85 aplicaciones
        entrepreneur_user = UserFactory(
            email=f'applicant_{app_id}@startup{app_id}.com',
            role_type='entrepreneur'
        )
        
        entrepreneur = EntrepreneurFactory(
            user=entrepreneur_user,
            business_name=f'Innovative Startup {app_id}',
            stage=random.choice(['prototype', 'mvp', 'growth']),
            industry=random.choice(['fintech', 'healthtech', 'edtech', 'cleantech', 'agtech'])
        )
        
        project = ProjectFactory(
            entrepreneur=entrepreneur,
            name=f'Revolutionary Project {app_id}',
            status='active'
        )
        
        # Determinar etapa actual (distribución realista)
        stage_distribution = [0.25, 0.20, 0.20, 0.20, 0.15]  # % en cada etapa
        cumulative = 0
        random_val = random.random()
        current_stage_index = 0
        
        for i, prob in enumerate(stage_distribution):
            cumulative += prob
            if random_val <= cumulative:
                current_stage_index = i
                break
        
        current_stage = program_data['evaluation_process']['stages'][current_stage_index]
        
        # Generar evaluaciones para etapas completadas
        evaluations = []
        for stage_idx in range(current_stage_index):
            stage_name = program_data['evaluation_process']['stages'][stage_idx]
            num_evaluators = program_data['evaluation_process']['evaluators_per_stage'][stage_idx]
            
            stage_evaluations = []
            for eval_idx in range(num_evaluators):
                evaluator = random.choice(evaluators)
                
                # Score realista basado en etapa y calidad
                base_score = random.uniform(6.0, 9.5)
                if stage_idx > 0:  # Si avanzó, score más alto
                    base_score = max(base_score, 7.0 + stage_idx * 0.3)
                
                evaluation = {
                    'evaluator': evaluator,
                    'stage': stage_name,
                    'score': round(base_score, 1),
                    'completed_at': datetime.utcnow() - timedelta(days=random.randint(1, 14)),
                    'criteria_scores': {
                        'team_quality': round(random.uniform(6.0, 9.5), 1),
                        'market_opportunity': round(random.uniform(6.0, 9.5), 1),
                        'product_innovation': round(random.uniform(6.0, 9.5), 1),
                        'business_model': round(random.uniform(6.0, 9.5), 1),
                        'traction_growth': round(random.uniform(6.0, 9.5), 1),
                        'execution_capability': round(random.uniform(6.0, 9.5), 1)
                    },
                    'written_feedback': f'Evaluación {stage_name} para {entrepreneur.business_name}',
                    'recommendation': random.choice(['advance', 'advance_with_conditions', 'reject']) if base_score > 7.0 else 'reject'
                }
                
                stage_evaluations.append(evaluation)
            
            avg_stage_score = sum(e['score'] for e in stage_evaluations) / len(stage_evaluations)
            evaluations.append({
                'stage': stage_name,
                'evaluations': stage_evaluations,
                'average_score': round(avg_stage_score, 2),
                'stage_decision': 'advance' if avg_stage_score >= program_data['evaluation_process']['min_score_to_advance'][stage_idx] else 'reject',
                'completed_at': datetime.utcnow() - timedelta(days=random.randint(1, 10))
            })
        
        # Calcular score general
        overall_score = 0.0
        if evaluations:
            overall_score = sum(stage['average_score'] for stage in evaluations) / len(evaluations)
        
        application = {
            'id': app_id,
            'entrepreneur': entrepreneur,
            'project': project,
            'submitted_at': datetime.utcnow() - timedelta(days=random.randint(5, 25)),
            'current_stage': current_stage,
            'current_stage_index': current_stage_index,
            'overall_score': round(overall_score, 2),
            'evaluations_completed': evaluations,
            'status': 'in_progress' if current_stage_index < len(program_data['evaluation_process']['stages']) else 'completed',
            'application_materials': {
                'pitch_deck': f'https://storage.example.com/applications/app_{app_id}_deck.pdf',
                'business_plan': f'https://storage.example.com/applications/app_{app_id}_plan.pdf',
                'financial_projections': f'https://storage.example.com/applications/app_{app_id}_finance.xlsx',
                'demo_video': f'https://storage.example.com/applications/app_{app_id}_demo.mp4',
                'team_cvs': f'https://storage.example.com/applications/app_{app_id}_cvs.pdf'
            },
            'application_data': {
                'team_size': random.randint(2, 6),
                'funding_sought': random.randint(50000, 500000),
                'current_revenue': random.randint(0, 100000),
                'target_market_size': random.randint(10000000, 1000000000),
                'competitive_advantages': random.sample([
                    'first_mover', 'proprietary_tech', 'strong_team', 
                    'proven_traction', 'strategic_partnerships'
                ], 2)
            },
            'next_deadline': datetime.utcnow() + timedelta(days=random.randint(1, 7)) if current_stage_index < len(program_data['evaluation_process']['stages']) else None
        }
        
        applications.append(application)
    
    # Estadísticas del proceso
    process_stats = {
        'total_applications': len(applications),
        'applications_by_stage': {},
        'average_scores_by_stage': {},
        'completion_rate_by_stage': {},
        'evaluator_workload': {},
        'timeline_adherence': {
            'on_time_evaluations': 0.87,
            'average_delay_days': 1.3,
            'bottleneck_stages': ['technical_evaluation', 'final_interview']
        },
        'quality_metrics': {
            'inter_evaluator_agreement': 0.78,
            'score_distribution_healthy': True,
            'bias_indicators': {
                'gender_bias': 0.02,
                'industry_bias': 0.05,
                'experience_bias': 0.03
            }
        }
    }
    
    # Calcular estadísticas
    for app in applications:
        stage = app['current_stage']
        if stage not in process_stats['applications_by_stage']:
            process_stats['applications_by_stage'][stage] = 0
        process_stats['applications_by_stage'][stage] += 1
    
    # Predicciones finales
    predictions = {
        'estimated_final_cohort': [],
        'rejection_reasons_predicted': {
            'team_weakness': 0.25,
            'market_concerns': 0.20,
            'product_readiness': 0.18,
            'business_model': 0.15,
            'execution_risk': 0.12,
            'competition': 0.10
        },
        'success_probability_distribution': {
            'high_potential': len([a for a in applications if a['overall_score'] > 8.5]),
            'good_potential': len([a for a in applications if 7.5 <= a['overall_score'] <= 8.5]),
            'moderate_potential': len([a for a in applications if 6.5 <= a['overall_score'] < 7.5]),
            'low_potential': len([a for a in applications if a['overall_score'] < 6.5])
        }
    }
    
    # Seleccionar top candidates para cohort final
    top_applications = sorted(applications, key=lambda x: x['overall_score'], reverse=True)
    for app in top_applications[:program_data['available_spots']]:
        predictions['estimated_final_cohort'].append({
            'application_id': app['id'],
            'business_name': app['entrepreneur'].business_name,
            'overall_score': app['overall_score'],
            'industry': app['entrepreneur'].industry,
            'success_prediction': 'high' if app['overall_score'] > 8.0 else 'moderate'
        })
    
    db_session.commit()
    
    workflow_data = {
        'program': program_data,
        'evaluators': evaluators,
        'applications': applications,
        'process_statistics': process_stats,
        'predictions': predictions,
        'workflow_configuration': {
            'automated_screening': True,
            'blind_evaluation_enabled': True,
            'consensus_threshold': 0.8,
            'appeal_process_enabled': True,
            'feedback_provided_to_rejected': True
        }
    }
    
    logger.info(f"⚖️ Workflow de evaluación creado")
    logger.info(f"📝 {len(applications)} aplicaciones en {len(program_data['evaluation_process']['stages'])} etapas")
    logger.info(f"👨‍💼 {len(evaluators)} evaluadores asignados")
    
    yield workflow_data


# ============================================================================
# FIXTURES DE CONFIGURACIÓN DINÁMICA
# ============================================================================

@pytest.fixture(scope='function', params=['development', 'staging', 'production'])
def dynamic_environment_config(request):
    """Fixture parametrizada para diferentes entornos."""
    env = request.param
    
    configs = {
        'development': {
            'debug_mode': True,
            'logging_level': 'DEBUG',
            'cache_timeout': 60,
            'rate_limiting': False,
            'external_services_enabled': False,
            'mock_payments': True,
            'email_backend': 'console',
            'file_storage': 'local',
            'database_pool_size': 5,
            'async_task_eager': True,
            'security_headers': False,
            'cors_origins': ['*'],
            'session_timeout_minutes': 1440,  # 24 horas
            'max_file_size_mb': 10
        },
        'staging': {
            'debug_mode': False,
            'logging_level': 'INFO',
            'cache_timeout': 300,
            'rate_limiting': True,
            'external_services_enabled': True,
            'mock_payments': True,
            'email_backend': 'smtp',
            'file_storage': 'cloud',
            'database_pool_size': 10,
            'async_task_eager': False,
            'security_headers': True,
            'cors_origins': ['https://staging.ecosistema.com'],
            'session_timeout_minutes': 480,  # 8 horas
            'max_file_size_mb': 25
        },
        'production': {
            'debug_mode': False,
            'logging_level': 'WARNING',
            'cache_timeout': 3600,
            'rate_limiting': True,
            'external_services_enabled': True,
            'mock_payments': False,
            'email_backend': 'smtp',
            'file_storage': 'cloud',
            'database_pool_size': 20,
            'async_task_eager': False,
            'security_headers': True,
            'cors_origins': ['https://ecosistema.com'],
            'session_timeout_minutes': 240,  # 4 horas
            'max_file_size_mb': 50
        }
    }
    
    config = configs[env]
    config['environment'] = env
    
    logger.info(f"🔧 Configuración dinámica cargada para: {env}")
    
    yield config


@pytest.fixture(scope='function')
def feature_flags():
    """Fixture de feature flags para testing A/B."""
    flags = {
        'new_dashboard_ui': {
            'enabled': True,
            'rollout_percentage': 50,
            'target_roles': ['entrepreneur', 'ally'],
            'exclude_users': [],
            'start_date': datetime.utcnow() - timedelta(days=7),
            'end_date': datetime.utcnow() + timedelta(days=30)
        },
        'ai_mentor_matching': {
            'enabled': True,
            'rollout_percentage': 25,
            'target_roles': ['entrepreneur'],
            'exclude_users': [],
            'start_date': datetime.utcnow() - timedelta(days=3),
            'end_date': datetime.utcnow() + timedelta(days=60)
        },
        'advanced_analytics': {
            'enabled': True,
            'rollout_percentage': 100,
            'target_roles': ['admin', 'client'],
            'exclude_users': [],
            'start_date': datetime.utcnow() - timedelta(days=30),
            'end_date': None  # Permanent
        },
        'mobile_app_beta': {
            'enabled': False,
            'rollout_percentage': 0,
            'target_roles': [],
            'exclude_users': [],
            'start_date': None,
            'end_date': None
        },
        'blockchain_certificates': {
            'enabled': True,
            'rollout_percentage': 10,
            'target_roles': ['entrepreneur'],
            'exclude_users': [],
            'start_date': datetime.utcnow(),
            'end_date': datetime.utcnow() + timedelta(days=90)
        }
    }
    
    def is_enabled_for_user(flag_name, user_role, user_id=None):
        """Determina si un flag está habilitado para un usuario."""
        if flag_name not in flags:
            return False
        
        flag = flags[flag_name]
        
        if not flag['enabled']:
            return False
        
        if user_role not in flag['target_roles'] and flag['target_roles']:
            return False
        
        if user_id and user_id in flag['exclude_users']:
            return False
        
        # Check rollout percentage
        if user_id:
            # Deterministic based on user_id
            import hashlib
            hash_val = int(hashlib.md5(f"{flag_name}_{user_id}".encode()).hexdigest()[:8], 16)
            user_percentage = hash_val % 100
            return user_percentage < flag['rollout_percentage']
        
        return random.randint(1, 100) <= flag['rollout_percentage']
    
    yield {
        'flags': flags,
        'is_enabled_for_user': is_enabled_for_user,
        'total_flags': len(flags),
        'active_flags': len([f for f in flags.values() if f['enabled']])
    }


# ============================================================================
# EXPORTS Y CONFIGURACIÓN FINAL
# ============================================================================

logger.info("🧪 Fixtures especializadas del ecosistema cargadas")
logger.info("📊 Fixtures disponibles: programas, mentorías, analytics, workflows, configuraciones")
logger.info("✅ fixtures.py inicializado correctamente")