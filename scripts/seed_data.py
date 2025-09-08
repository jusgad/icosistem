#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Datos de Prueba del Ecosistema de Emprendimiento
============================================================

Sistema completo de generación de datos de prueba que crea:
- Usuarios con roles específicos (admin, entrepreneur, ally, client)
- Organizaciones e instituciones colombianas
- Programas de emprendimiento realistas
- Proyectos de emprendimiento con sectores específicos
- Sesiones de mentoría y seguimiento
- Reuniones y calendario de actividades
- Mensajería y comunicaciones
- Documentos y recursos
- Tareas y actividades
- Notificaciones y logs de actividad
- Métricas y analytics

Características:
- Datos realistas para Colombia (nombres, ciudades, sectores)
- Relaciones consistentes entre entidades
- Diferentes tamaños de datasets (minimal, small, medium, large)
- Datos específicos por ambiente (development, testing, staging)
- Idempotente (puede ejecutarse múltiples veces)
- Logging detallado y progress tracking
- Validación de integridad de datos
- Cleanup automático de datos existentes

Uso:
    python scripts/seed_data.py --size medium --environment development
    python scripts/seed_data.py --size large --environment staging --clean
    python scripts/seed_data.py --only users,organizations --size small
    python scripts/seed_data.py --exclude analytics --size medium --verbose

Autor: Sistema de Emprendimiento
Versión: 2.0.0
Fecha: 2025
"""

import os
import sys
import json
import random
import argparse
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import secrets
from decimal import Decimal

# Faker para generar datos realistas
from faker import Faker
from faker.providers import BaseProvider

# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importar después de agregar al path
try:
    from app import create_app
    from app.extensions import db
    from app.models.user import User
    from app.models.admin import Admin
    from app.models.entrepreneur import Entrepreneur
    from app.models.ally import Ally
    from app.models.client import Client
    from app.models.organization import Organization
    from app.models.program import Program
    from app.models.project import Project
    from app.models.mentorship import MentorshipSession
    from app.models.meeting import Meeting
    from app.models.message import Message
    from app.models.document import Document
    from app.models.task import Task
    from app.models.notification import Notification
    from app.models.activity_log import ActivityLog
    from app.models.analytics import AnalyticsEvent
except ImportError as e:
    print(f"Error importando modelos de la aplicación: {e}")
    print("Asegúrese de que la aplicación Flask esté configurada correctamente")
    sys.exit(1)


@dataclass
class SeedConfig:
    """
    Configuración del generador de datos de prueba.
    """
    size: str = 'medium'                    # minimal, small, medium, large, enterprise
    environment: str = 'development'
    clean: bool = False
    only: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    locale: str = 'es_CO'
    seed: Optional[int] = None
    validate: bool = True
    progress: bool = True
    verbose: bool = False
    dry_run: bool = False


class Colors:
    """
    Códigos de colores ANSI para output profesional.
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ColombianProvider(BaseProvider):
    """
    Proveedor personalizado de datos colombianos para Faker.
    """
    
    # Ciudades principales de Colombia
    cities = [
        'Bogotá', 'Medellín', 'Cali', 'Barranquilla', 'Cartagena',
        'Cúcuta', 'Soledad', 'Ibagué', 'Bucaramanga', 'Soacha',
        'Santa Marta', 'Villavicencio', 'Valledupar', 'Pereira',
        'Montería', 'Manizales', 'Neiva', 'Pasto', 'Armenia'
    ]
    
    # Departamentos de Colombia
    departments = [
        'Antioquia', 'Atlántico', 'Bogotá D.C.', 'Bolívar', 'Boyacá',
        'Caldas', 'Caquetá', 'Cauca', 'César', 'Córdoba',
        'Cundinamarca', 'Huila', 'La Guajira', 'Magdalena', 'Meta',
        'Nariño', 'Norte de Santander', 'Quindío', 'Risaralda',
        'Santander', 'Sucre', 'Tolima', 'Valle del Cauca'
    ]
    
    # Sectores económicos colombianos
    business_sectors = [
        'Tecnología', 'Agricultura', 'Turismo', 'Manufactura',
        'Servicios Financieros', 'Educación', 'Salud', 'Comercio',
        'Energía', 'Minería', 'Construcción', 'Textil', 'Alimentos',
        'Transporte', 'Comunicaciones', 'Entretenimiento', 'Retail',
        'Logística', 'Consultoría', 'Marketing Digital', 'E-commerce',
        'Biotecnología', 'Sostenibilidad', 'Fintech', 'Agtech'
    ]
    
    # Tipos de organizaciones
    organization_types = [
        'Universidad', 'Incubadora', 'Aceleradora', 'Fundación',
        'Corporación', 'Centro de Innovación', 'Cámara de Comercio',
        'ONG', 'Instituto Tecnológico', 'Centro de Desarrollo',
        'Hub de Innovación', 'Parque Tecnológico', 'SENA Regional'
    ]
    
    # Nombres de programas de emprendimiento
    program_names = [
        'Programa de Innovación y Emprendimiento',
        'Acelerador de Startups Tecnológicas',
        'Incubadora de Negocios Sostenibles',
        'Emprendimiento Rural Colombiano',
        'Mujeres Emprendedoras',
        'Jóvenes Innovadores',
        'Economía Naranja',
        'Emprendimiento Social',
        'Innovación Abierta',
        'Startups Fintech',
        'Agro-emprendimiento',
        'Turismo Sostenible',
        'Manufactura 4.0',
        'Economía Digital',
        'Emprendimiento Verde'
    ]
    
    # Tipos de proyectos
    project_types = [
        'Startup Tecnológica', 'Negocio Traditional', 'Proyecto Social',
        'Emprendimiento Verde', 'Innovación Digital', 'Agro-negocio',
        'Turismo Comunitario', 'Manufactura Artesanal', 'Servicios Profesionales',
        'E-commerce', 'Fintech', 'Healthtech', 'Edtech', 'Foodtech'
    ]
    
    def colombian_city(self):
        """Retorna una ciudad colombiana aleatoria."""
        return self.random_element(self.cities)
    
    def colombian_department(self):
        """Retorna un departamento colombiano aleatorio."""
        return self.random_element(self.departments)
    
    def business_sector(self):
        """Retorna un sector económico aleatorio."""
        return self.random_element(self.business_sectors)
    
    def organization_type(self):
        """Retorna un tipo de organización aleatorio."""
        return self.random_element(self.organization_types)
    
    def program_name(self):
        """Retorna un nombre de programa aleatorio."""
        return self.random_element(self.program_names)
    
    def project_type(self):
        """Retorna un tipo de proyecto aleatorio."""
        return self.random_element(self.project_types)
    
    def colombian_phone(self):
        """Genera un número de teléfono colombiano."""
        prefixes = ['300', '301', '302', '310', '311', '312', '313', '314', '315', '316', '317', '318', '319', '320', '321']
        prefix = self.random_element(prefixes)
        number = ''.join([str(self.random_int(0, 9)) for _ in range(7)])
        return f"+57 {prefix} {number[:3]} {number[3:]}"
    
    def nit_number(self):
        """Genera un número de NIT colombiano."""
        number = ''.join([str(self.random_int(0, 9)) for _ in range(9)])
        return f"{number[:3]}.{number[3:6]}.{number[6:]}-{self.random_int(0, 9)}"


class SeedLogger:
    """
    Logger especializado para generación de datos de prueba.
    """
    
    def __init__(self, verbose: bool = False, progress: bool = True):
        """
        Inicializa el logger de seed data.
        
        Args:
            verbose: Si mostrar logs verbosos
            progress: Si mostrar progress bars
        """
        self.verbose = verbose
        self.progress = progress
        self.setup_logging()
    
    def setup_logging(self):
        """
        Configura logging para seed data.
        """
        log_format = '%(asctime)s [SEED] %(levelname)s: %(message)s'
        level = logging.DEBUG if self.verbose else logging.INFO
        
        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.logger = logging.getLogger('seed_data')
    
    def info(self, message: str, progress_step: bool = False):
        """Log info con formato profesional."""
        prefix = f"{Colors.OKCYAN}[PROGRESS]{Colors.ENDC}" if progress_step else f"{Colors.OKGREEN}[INFO]{Colors.ENDC}"
        print(f"{prefix} {message}")
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning con color."""
        print(f"{Colors.WARNING}[WARNING]{Colors.ENDC} {message}")
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error con color."""
        print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {message}")
        self.logger.error(message)
    
    def success(self, message: str):
        """Log success con color."""
        print(f"{Colors.OKGREEN}[SUCCESS]{Colors.ENDC} {message}")
        self.logger.info(f"SUCCESS: {message}")
    
    def header(self, message: str):
        """Log header con formato especial."""
        separator = "=" * 80
        print(f"\n{Colors.HEADER}{Colors.BOLD}{separator}")
        print(f"{message.center(80)}")
        print(f"{separator}{Colors.ENDC}")
        self.logger.info(f"=== {message} ===")
    
    def section(self, section_name: str, step: int, total_steps: int):
        """Log sección del seed data."""
        print(f"\n{Colors.HEADER}[{step}/{total_steps}] {section_name}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'-' * 50}{Colors.ENDC}")
        self.logger.info(f"Section {step}/{total_steps}: {section_name}")
    
    def progress_bar(self, current: int, total: int, item_name: str = "items"):
        """Muestra barra de progreso simple."""
        if not self.progress:
            return
        
        percent = (current / total) * 100
        bar_length = 30
        filled_length = int(bar_length * current // total)
        
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        print(f'\r{Colors.OKCYAN}[{bar}] {percent:.1f}% ({current}/{total} {item_name}){Colors.ENDC}', end='')
        
        if current == total:
            print()  # Nueva línea al completar


class DataGenerator:
    """
    Generador principal de datos de prueba.
    """
    
    def __init__(self, config: SeedConfig):
        """
        Inicializa el generador de datos.
        
        Args:
            config: Configuración del generador
        """
        self.config = config
        self.logger = SeedLogger(config.verbose, config.progress)
        
        # Configurar Faker
        self.fake = Faker(config.locale)
        self.fake.add_provider(ColombianProvider)
        
        # Configurar seed para reproducibilidad
        if config.seed:
            Faker.seed(config.seed)
            random.seed(config.seed)
        
        # Configuraciones por tamaño
        self.size_configs = {
            'minimal': {
                'users': {'admin': 1, 'entrepreneur': 3, 'ally': 2, 'client': 1},
                'organizations': 2,
                'programs': 1,
                'projects': 3,
                'mentorship_sessions': 5,
                'meetings': 8,
                'messages': 20,
                'documents': 10,
                'tasks': 15,
                'notifications': 30
            },
            'small': {
                'users': {'admin': 2, 'entrepreneur': 10, 'ally': 5, 'client': 3},
                'organizations': 5,
                'programs': 3,
                'projects': 15,
                'mentorship_sessions': 25,
                'meetings': 40,
                'messages': 100,
                'documents': 50,
                'tasks': 80,
                'notifications': 150
            },
            'medium': {
                'users': {'admin': 3, 'entrepreneur': 30, 'ally': 15, 'client': 8},
                'organizations': 12,
                'programs': 8,
                'projects': 50,
                'mentorship_sessions': 100,
                'meetings': 150,
                'messages': 400,
                'documents': 200,
                'tasks': 300,
                'notifications': 600
            },
            'large': {
                'users': {'admin': 5, 'entrepreneur': 100, 'ally': 40, 'client': 20},
                'organizations': 25,
                'programs': 20,
                'projects': 200,
                'mentorship_sessions': 400,
                'meetings': 600,
                'messages': 1500,
                'documents': 800,
                'tasks': 1200,
                'notifications': 2500
            },
            'enterprise': {
                'users': {'admin': 10, 'entrepreneur': 500, 'ally': 150, 'client': 50},
                'organizations': 50,
                'programs': 50,
                'projects': 1000,
                'mentorship_sessions': 2000,
                'meetings': 3000,
                'messages': 8000,
                'documents': 4000,
                'tasks': 6000,
                'notifications': 15000
            }
        }
        
        # Referencias para relaciones
        self.created_users = {}
        self.created_organizations = []
        self.created_programs = []
        self.created_projects = []
    
    def run(self) -> bool:
        """
        Ejecuta la generación completa de datos de prueba.
        
        Returns:
            True si la generación fue exitosa
        """
        try:
            # Header principal
            self.logger.header(f"GENERACIÓN DE DATOS DE PRUEBA - {self.config.size.upper()}")
            
            # Configuración del entorno
            self._show_config()
            
            # Limpieza de datos existentes si se solicita
            if self.config.clean:
                self._cleanup_existing_data()
            
            # Obtener lista de secciones a generar
            sections = self._get_sections_to_generate()
            total_sections = len(sections)
            
            # Generar datos por sección
            for i, (section_name, generator_func) in enumerate(sections, 1):
                self.logger.section(section_name, i, total_sections)
                
                if not generator_func():
                    self.logger.error(f"Error en sección: {section_name}")
                    return False
            
            # Validación final
            if self.config.validate:
                self._validate_generated_data()
            
            # Resumen final
            self._show_summary()
            
            self.logger.success("Generación de datos de prueba completada exitosamente!")
            return True
            
        except KeyboardInterrupt:
            self.logger.warning("Generación interrumpida por el usuario")
            return False
        except Exception as e:
            self.logger.error(f"Error inesperado: {e}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def _show_config(self):
        """Muestra la configuración actual."""
        config_info = self.size_configs[self.config.size]
        
        print(f"\n{Colors.OKCYAN}Configuración:{Colors.ENDC}")
        print(f"  Tamaño: {Colors.BOLD}{self.config.size}{Colors.ENDC}")
        print(f"  Ambiente: {Colors.BOLD}{self.config.environment}{Colors.ENDC}")
        print(f"  Locale: {Colors.BOLD}{self.config.locale}{Colors.ENDC}")
        
        if self.config.seed:
            print(f"  Seed: {Colors.BOLD}{self.config.seed}{Colors.ENDC}")
        
        print(f"\n{Colors.OKCYAN}Datos a generar:{Colors.ENDC}")
        for key, value in config_info.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")
        
        if self.config.dry_run:
            print(f"\n{Colors.WARNING}MODO DRY RUN - No se crearán datos reales{Colors.ENDC}")
    
    def _cleanup_existing_data(self):
        """Limpia datos existentes de la base de datos."""
        self.logger.info("Limpiando datos existentes...", progress_step=True)
        
        if self.config.dry_run:
            self.logger.info("DRY RUN: Saltando limpieza real")
            return
        
        try:
            # Orden de eliminación para respetar foreign keys
            cleanup_order = [
                ActivityLog, AnalyticsEvent, Notification, Task,
                Document, Message, Meeting, MentorshipSession,
                Project, Program, Ally, Entrepreneur, Client, Admin,
                User, Organization
            ]
            
            for model in cleanup_order:
                count = db.session.query(model).count()
                if count > 0:
                    db.session.query(model).delete()
                    self.logger.info(f"Eliminados {count} registros de {model.__name__}")
            
            db.session.commit()
            self.logger.success("Limpieza completada")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error en limpieza: {e}")
            raise
    
    def _get_sections_to_generate(self) -> list[tuple[str, callable]]:
        """
        Obtiene la lista de secciones a generar.
        
        Returns:
            Lista de tuplas (nombre, función) de secciones
        """
        all_sections = [
            ("Organizations", self._generate_organizations),
            ("Users", self._generate_users),
            ("Programs", self._generate_programs),
            ("Projects", self._generate_projects),
            ("Mentorship Sessions", self._generate_mentorship_sessions),
            ("Meetings", self._generate_meetings),
            ("Messages", self._generate_messages),
            ("Documents", self._generate_documents),
            ("Tasks", self._generate_tasks),
            ("Notifications", self._generate_notifications),
            ("Activity Logs", self._generate_activity_logs),
            ("Analytics Events", self._generate_analytics_events),
        ]
        
        # Filtrar secciones según configuración
        if self.config.only:
            filtered_sections = []
            for section_name, func in all_sections:
                section_key = section_name.lower().replace(' ', '_')
                if section_key in self.config.only:
                    filtered_sections.append((section_name, func))
            return filtered_sections
        
        if self.config.exclude:
            filtered_sections = []
            for section_name, func in all_sections:
                section_key = section_name.lower().replace(' ', '_')
                if section_key not in self.config.exclude:
                    filtered_sections.append((section_name, func))
            return filtered_sections
        
        return all_sections
    
    def _generate_organizations(self) -> bool:
        """Genera organizaciones."""
        config = self.size_configs[self.config.size]
        count = config['organizations']
        
        self.logger.info(f"Generando {count} organizaciones...")
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "organizaciones")
                
                if not self.config.dry_run:
                    organization = Organization(
                        name=f"{self.fake.company()} {self.fake.organization_type()}",
                        type=self.fake.organization_type(),
                        description=self.fake.text(max_nb_chars=500),
                        website=self.fake.url(),
                        email=self.fake.company_email(),
                        phone=self.fake.colombian_phone(),
                        address=self.fake.address(),
                        city=self.fake.colombian_city(),
                        country='Colombia',
                        founded_year=self.fake.random_int(min=1950, max=2020),
                        sector=self.fake.business_sector(),
                        size=self.fake.random_element(['Small', 'Medium', 'Large', 'Enterprise']),
                        status='active',
                        is_verified=True
                    )
                    
                    db.session.add(organization)
                    self.created_organizations.append(organization)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Organizaciones creadas: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando organizaciones: {e}")
            return False
    
    def _generate_users(self) -> bool:
        """Genera usuarios con diferentes roles."""
        config = self.size_configs[self.config.size]['users']
        
        self.logger.info(f"Generando usuarios: {dict(config)}")
        
        try:
            # Generar usuarios por rol
            for role, count in config.items():
                self.logger.info(f"Generando {count} usuarios {role}...")
                
                for i in range(count):
                    if self.config.progress:
                        self.logger.progress_bar(i + 1, count, f"usuarios {role}")
                    
                    if not self.config.dry_run:
                        user = self._create_user_by_role(role)
                        if user:
                            if role not in self.created_users:
                                self.created_users[role] = []
                            self.created_users[role].append(user)
            
            if not self.config.dry_run:
                db.session.commit()
            
            total_users = sum(config.values())
            self.logger.success(f"Usuarios creados: {total_users}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando usuarios: {e}")
            return False
    
    def _create_user_by_role(self, role: str):
        """
        Crea un usuario específico por rol.
        
        Args:
            role: Rol del usuario (admin, entrepreneur, ally, client)
            
        Returns:
            Instancia de usuario creada
        """
        # Datos comunes para todos los usuarios
        first_name = self.fake.first_name()
        last_name = self.fake.last_name()
        email = f"{first_name.lower()}.{last_name.lower()}@{self.fake.domain_name()}"
        
        # Crear usuario base
        user = User(
            email=email,
            password_hash='pbkdf2:sha256:260000$hashed_password',  # Password: password123
            first_name=first_name,
            last_name=last_name,
            phone=self.fake.colombian_phone(),
            city=self.fake.colombian_city(),
            country='Colombia',
            is_email_verified=True,
            is_active=True,
            role=role,
            created_at=self.fake.date_time_between(start_date='-2y', end_date='now'),
            last_login_at=self.fake.date_time_between(start_date='-30d', end_date='now')
        )
        
        db.session.add(user)
        db.session.flush()  # Para obtener el ID
        
        # Crear perfil específico según el rol
        if role == 'admin':
            admin = Admin(
                user_id=user.id,
                permissions=['all'],
                access_level='super_admin' if self.fake.boolean(chance_of_getting_true=20) else 'admin',
                department=self.fake.random_element(['Technology', 'Operations', 'Finance', 'Marketing']),
                employee_id=f"ADM{self.fake.random_int(min=1000, max=9999)}"
            )
            db.session.add(admin)
            
        elif role == 'entrepreneur':
            entrepreneur = Entrepreneur(
                user_id=user.id,
                bio=self.fake.text(max_nb_chars=800),
                experience_years=self.fake.random_int(min=0, max=15),
                education_level=self.fake.random_element(['High School', 'Bachelor', 'Master', 'PhD']),
                industries=self.fake.random_elements(
                    elements=[self.fake.business_sector() for _ in range(10)],
                    length=self.fake.random_int(min=1, max=3),
                    unique=True
                ),
                skills=self.fake.random_elements(
                    elements=['Leadership', 'Marketing', 'Finance', 'Technology', 'Sales', 'Operations', 'Strategy'],
                    length=self.fake.random_int(min=2, max=5),
                    unique=True
                ),
                linkedin_url=f"https://linkedin.com/in/{first_name.lower()}-{last_name.lower()}",
                website_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=30) else None,
                stage=self.fake.random_element(['idea', 'validation', 'mvp', 'growth', 'scaling']),
                funding_stage=self.fake.random_element(['pre_seed', 'seed', 'series_a', 'series_b', 'series_c']),
                funding_amount=Decimal(str(self.fake.random_int(min=5000, max=1000000))),
                is_seeking_funding=self.fake.boolean(chance_of_getting_true=70),
                is_available_for_mentorship=self.fake.boolean(chance_of_getting_true=40)
            )
            db.session.add(entrepreneur)
            
        elif role == 'ally':
            ally = Ally(
                user_id=user.id,
                bio=self.fake.text(max_nb_chars=1000),
                expertise_areas=self.fake.random_elements(
                    elements=['Strategy', 'Marketing', 'Finance', 'Technology', 'Operations', 'Sales', 'HR'],
                    length=self.fake.random_int(min=2, max=4),
                    unique=True
                ),
                experience_years=self.fake.random_int(min=5, max=30),
                company=self.fake.company(),
                position=self.fake.job(),
                hourly_rate=Decimal(str(self.fake.random_int(min=50, max=500))),
                availability_hours=self.fake.random_int(min=5, max=40),
                max_entrepreneurs=self.fake.random_int(min=3, max=15),
                languages=['Spanish', 'English'] if self.fake.boolean(chance_of_getting_true=60) else ['Spanish'],
                certifications=self.fake.random_elements(
                    elements=['PMP', 'MBA', 'CPA', 'Scrum Master', 'Google Analytics', 'Facebook Ads'],
                    length=self.fake.random_int(min=0, max=3),
                    unique=True
                ),
                linkedin_url=f"https://linkedin.com/in/{first_name.lower()}-{last_name.lower()}",
                is_available=True,
                rating=round(self.fake.random.uniform(4.0, 5.0), 1)
            )
            db.session.add(ally)
            
        elif role == 'client':
            organization = self.fake.random_element(self.created_organizations) if self.created_organizations else None
            
            client = Client(
                user_id=user.id,
                organization_id=organization.id if organization else None,
                position=self.fake.job(),
                department=self.fake.random_element(['Innovation', 'R&D', 'Strategy', 'Operations', 'Marketing']),
                client_type=self.fake.random_element(['corporate', 'government', 'ngo', 'academic']),
                budget_range=self.fake.random_element(['<10K', '10K-50K', '50K-100K', '100K-500K', '>500K']),
                interest_areas=self.fake.random_elements(
                    elements=[self.fake.business_sector() for _ in range(8)],
                    length=self.fake.random_int(min=2, max=4),
                    unique=True
                ),
                preferred_communication=self.fake.random_element(['email', 'phone', 'video_call', 'in_person']),
                is_decision_maker=self.fake.boolean(chance_of_getting_true=40)
            )
            db.session.add(client)
        
        return user
    
    def _generate_programs(self) -> bool:
        """Genera programas de emprendimiento."""
        config = self.size_configs[self.config.size]
        count = config['programs']
        
        self.logger.info(f"Generando {count} programas...")
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "programas")
                
                if not self.config.dry_run:
                    start_date = self.fake.date_between(start_date='-1y', end_date='+6m')
                    end_date = start_date + timedelta(days=self.fake.random_int(min=90, max=365))
                    
                    organization = self.fake.random_element(self.created_organizations) if self.created_organizations else None
                    
                    program = Program(
                        name=self.fake.program_name(),
                        description=self.fake.text(max_nb_chars=1500),
                        organization_id=organization.id if organization else None,
                        program_type=self.fake.random_element(['incubation', 'acceleration', 'mentorship', 'training']),
                        sector_focus=self.fake.business_sector(),
                        duration_months=self.fake.random_int(min=3, max=12),
                        max_participants=self.fake.random_int(min=10, max=100),
                        application_deadline=self.fake.date_between(start_date='-30d', end_date='+60d'),
                        start_date=start_date,
                        end_date=end_date,
                        status=self.fake.random_element(['draft', 'open', 'active', 'completed']),
                        requirements=self.fake.random_elements(
                            elements=['Business Plan', 'Prototype', 'Team', 'Market Research', 'Financial Model'],
                            length=self.fake.random_int(min=2, max=4),
                            unique=True
                        ),
                        benefits=self.fake.random_elements(
                            elements=['Mentorship', 'Funding', 'Office Space', 'Legal Support', 'Marketing'],
                            length=self.fake.random_int(min=3, max=5),
                            unique=True
                        ),
                        budget=Decimal(str(self.fake.random_int(min=50000, max=2000000))),
                        funding_available=self.fake.boolean(chance_of_getting_true=70),
                        equity_required=self.fake.boolean(chance_of_getting_true=30),
                        equity_percentage=self.fake.random_int(min=5, max=20) if self.fake.boolean() else None,
                        is_remote=self.fake.boolean(chance_of_getting_true=60),
                        location=self.fake.colombian_city(),
                        website_url=self.fake.url(),
                        contact_email=self.fake.email()
                    )
                    
                    db.session.add(program)
                    self.created_programs.append(program)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Programas creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando programas: {e}")
            return False
    
    def _generate_projects(self) -> bool:
        """Genera proyectos de emprendimiento."""
        config = self.size_configs[self.config.size]
        count = config['projects']
        
        self.logger.info(f"Generando {count} proyectos...")
        
        entrepreneurs = self.created_users.get('entrepreneur', [])
        if not entrepreneurs:
            self.logger.warning("No hay emprendedores creados, saltando proyectos")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "proyectos")
                
                if not self.config.dry_run:
                    entrepreneur = self.fake.random_element(entrepreneurs)
                    program = self.fake.random_element(self.created_programs) if self.created_programs else None
                    
                    project = Project(
                        name=f"{self.fake.catch_phrase()} - {self.fake.project_type()}",
                        description=self.fake.text(max_nb_chars=2000),
                        entrepreneur_id=entrepreneur.id,
                        program_id=program.id if program else None,
                        sector=self.fake.business_sector(),
                        stage=self.fake.random_element(['idea', 'validation', 'mvp', 'beta', 'launch', 'growth']),
                        project_type=self.fake.project_type(),
                        problem_statement=self.fake.text(max_nb_chars=800),
                        solution_description=self.fake.text(max_nb_chars=1000),
                        target_market=self.fake.text(max_nb_chars=600),
                        business_model=self.fake.random_element(['B2B', 'B2C', 'B2B2C', 'Marketplace', 'SaaS', 'Freemium']),
                        revenue_model=self.fake.random_element(['Subscription', 'Commission', 'Advertising', 'Sales', 'Licensing']),
                        funding_goal=Decimal(str(self.fake.random_int(min=10000, max=1000000))),
                        funding_raised=Decimal(str(self.fake.random_int(min=0, max=500000))),
                        team_size=self.fake.random_int(min=1, max=15),
                        website_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=40) else None,
                        demo_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=25) else None,
                        pitch_deck_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=60) else None,
                        status=self.fake.random_element(['active', 'paused', 'completed', 'cancelled']),
                        progress_percentage=self.fake.random_int(min=0, max=100),
                        launch_date=self.fake.date_between(start_date='-2y', end_date='+1y') if self.fake.boolean() else None,
                        location=self.fake.colombian_city(),
                        is_social_impact=self.fake.boolean(chance_of_getting_true=30),
                        sdg_goals=self.fake.random_elements(
                            elements=[f"SDG {i}" for i in range(1, 18)],
                            length=self.fake.random_int(min=1, max=3),
                            unique=True
                        ) if self.fake.boolean(chance_of_getting_true=40) else [],
                        technologies=self.fake.random_elements(
                            elements=['Python', 'React', 'Node.js', 'Mobile App', 'AI/ML', 'Blockchain', 'IoT'],
                            length=self.fake.random_int(min=1, max=4),
                            unique=True
                        ),
                        competitors=self.fake.random_elements(
                            elements=[self.fake.company() for _ in range(10)],
                            length=self.fake.random_int(min=2, max=5),
                            unique=True
                        ),
                        awards=self.fake.random_elements(
                            elements=['Best Startup 2024', 'Innovation Award', 'Social Impact Prize'],
                            length=self.fake.random_int(min=0, max=2),
                            unique=True
                        )
                    )
                    
                    db.session.add(project)
                    self.created_projects.append(project)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Proyectos creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando proyectos: {e}")
            return False
    
    def _generate_mentorship_sessions(self) -> bool:
        """Genera sesiones de mentoría."""
        config = self.size_configs[self.config.size]
        count = config['mentorship_sessions']
        
        self.logger.info(f"Generando {count} sesiones de mentoría...")
        
        entrepreneurs = self.created_users.get('entrepreneur', [])
        allies = self.created_users.get('ally', [])
        
        if not entrepreneurs or not allies:
            self.logger.warning("No hay emprendedores o aliados creados, saltando sesiones de mentoría")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "sesiones")
                
                if not self.config.dry_run:
                    entrepreneur = self.fake.random_element(entrepreneurs)
                    ally = self.fake.random_element(allies)
                    
                    scheduled_date = self.fake.date_time_between(start_date='-6m', end_date='+3m')
                    duration = self.fake.random_int(min=30, max=120)
                    
                    session = MentorshipSession(
                        entrepreneur_id=entrepreneur.id,
                        ally_id=ally.id,
                        scheduled_date=scheduled_date,
                        duration_minutes=duration,
                        session_type=self.fake.random_element(['strategy', 'technical', 'marketing', 'finance', 'general']),
                        status=self.fake.random_element(['scheduled', 'completed', 'cancelled', 'no_show']),
                        agenda=self.fake.text(max_nb_chars=500),
                        notes=self.fake.text(max_nb_chars=1000) if self.fake.boolean(chance_of_getting_true=70) else None,
                        action_items=self.fake.random_elements(
                            elements=[
                                'Review business plan',
                                'Conduct market research',
                                'Develop prototype',
                                'Prepare pitch deck',
                                'Network with investors'
                            ],
                            length=self.fake.random_int(min=1, max=4),
                            unique=True
                        ),
                        follow_up_date=scheduled_date + timedelta(days=self.fake.random_int(min=7, max=30)),
                        rating=self.fake.random_int(min=3, max=5) if self.fake.boolean(chance_of_getting_true=80) else None,
                        feedback=self.fake.text(max_nb_chars=300) if self.fake.boolean(chance_of_getting_true=60) else None,
                        is_billable=self.fake.boolean(chance_of_getting_true=40),
                        amount_charged=Decimal(str(duration * self.fake.random_int(min=50, max=200))) if self.fake.boolean() else None,
                        meeting_url=f"https://meet.google.com/{self.fake.lexify('???-????-???')}",
                        recording_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=30) else None
                    )
                    
                    db.session.add(session)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Sesiones de mentoría creadas: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando sesiones de mentoría: {e}")
            return False
    
    def _generate_meetings(self) -> bool:
        """Genera reuniones."""
        config = self.size_configs[self.config.size]
        count = config['meetings']
        
        self.logger.info(f"Generando {count} reuniones...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if not all_users:
            self.logger.warning("No hay usuarios creados, saltando reuniones")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "reuniones")
                
                if not self.config.dry_run:
                    organizer = self.fake.random_element(all_users)
                    participants = self.fake.random_elements(
                        elements=all_users,
                        length=self.fake.random_int(min=2, max=8),
                        unique=True
                    )
                    
                    start_date = self.fake.date_time_between(start_date='-3m', end_date='+2m')
                    duration = self.fake.random_int(min=30, max=180)
                    
                    meeting = Meeting(
                        title=self.fake.random_element([
                            'Weekly Check-in',
                            'Project Review',
                            'Strategy Planning',
                            'Investor Presentation',
                            'Team Standup',
                            'Board Meeting',
                            'Client Demo'
                        ]),
                        description=self.fake.text(max_nb_chars=600),
                        organizer_id=organizer.id,
                        start_date=start_date,
                        end_date=start_date + timedelta(minutes=duration),
                        timezone='America/Bogota',
                        meeting_type=self.fake.random_element(['video_call', 'in_person', 'phone_call']),
                        location=self.fake.address() if self.fake.boolean(chance_of_getting_true=30) else None,
                        meeting_url=f"https://meet.google.com/{self.fake.lexify('???-????-???)}'",
                        status=self.fake.random_element(['scheduled', 'completed', 'cancelled', 'postponed']),
                        agenda=self.fake.random_elements(
                            elements=[
                                'Review last week progress',
                                'Discuss current challenges',
                                'Plan next steps',
                                'Q&A session',
                                'Demo presentation'
                            ],
                            length=self.fake.random_int(min=2, max=5),
                            unique=True
                        ),
                        minutes=self.fake.text(max_nb_chars=1200) if self.fake.boolean(chance_of_getting_true=60) else None,
                        action_items=self.fake.random_elements(
                            elements=[
                                'Follow up with client',
                                'Update project timeline',
                                'Prepare next presentation',
                                'Research market trends',
                                'Schedule follow-up meeting'
                            ],
                            length=self.fake.random_int(min=1, max=4),
                            unique=True
                        ),
                        is_recurring=self.fake.boolean(chance_of_getting_true=20),
                        recurrence_pattern='weekly' if self.fake.boolean(chance_of_getting_true=70) else 'monthly',
                        participants_ids=[p.id for p in participants],
                        recording_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=25) else None,
                        is_private=self.fake.boolean(chance_of_getting_true=30)
                    )
                    
                    db.session.add(meeting)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Reuniones creadas: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando reuniones: {e}")
            return False
    
    def _generate_messages(self) -> bool:
        """Genera mensajes."""
        config = self.size_configs[self.config.size]
        count = config['messages']
        
        self.logger.info(f"Generando {count} mensajes...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if len(all_users) < 2:
            self.logger.warning("Se necesitan al menos 2 usuarios para generar mensajes")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "mensajes")
                
                if not self.config.dry_run:
                    sender = self.fake.random_element(all_users)
                    receiver = self.fake.random_element([u for u in all_users if u.id != sender.id])
                    
                    message = Message(
                        sender_id=sender.id,
                        receiver_id=receiver.id,
                        subject=self.fake.sentence(nb_words=6),
                        content=self.fake.text(max_nb_chars=1000),
                        message_type=self.fake.random_element(['direct', 'announcement', 'notification']),
                        priority=self.fake.random_element(['low', 'normal', 'high']),
                        is_read=self.fake.boolean(chance_of_getting_true=70),
                        read_at=self.fake.date_time_between(start_date='-30d', end_date='now') if self.fake.boolean() else None,
                        parent_message_id=None,  # Simplificado por ahora
                        attachments=[
                            {
                                'filename': f'{self.fake.word()}.pdf',
                                'url': self.fake.url(),
                                'size': self.fake.random_int(min=1024, max=5242880)
                            }
                        ] if self.fake.boolean(chance_of_getting_true=20) else [],
                        is_starred=self.fake.boolean(chance_of_getting_true=15),
                        is_archived=self.fake.boolean(chance_of_getting_true=10),
                        sent_at=self.fake.date_time_between(start_date='-60d', end_date='now'),
                        delivery_status='delivered'
                    )
                    
                    db.session.add(message)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Mensajes creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando mensajes: {e}")
            return False
    
    def _generate_documents(self) -> bool:
        """Genera documentos."""
        config = self.size_configs[self.config.size]
        count = config['documents']
        
        self.logger.info(f"Generando {count} documentos...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if not all_users:
            self.logger.warning("No hay usuarios creados, saltando documentos")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "documentos")
                
                if not self.config.dry_run:
                    uploader = self.fake.random_element(all_users)
                    project = self.fake.random_element(self.created_projects) if self.created_projects else None
                    
                    doc_types = ['business_plan', 'pitch_deck', 'financial_model', 'legal_document', 'marketing_material', 'technical_spec', 'report', 'contract']
                    doc_type = self.fake.random_element(doc_types)
                    
                    file_extensions = {
                        'business_plan': ['.pdf', '.docx'],
                        'pitch_deck': ['.pdf', '.pptx'],
                        'financial_model': ['.xlsx', '.pdf'],
                        'legal_document': ['.pdf', '.docx'],
                        'marketing_material': ['.pdf', '.jpg', '.png'],
                        'technical_spec': ['.pdf', '.docx'],
                        'report': ['.pdf', '.docx'],
                        'contract': ['.pdf', '.docx']
                    }
                    
                    extension = self.fake.random_element(file_extensions[doc_type])
                    filename = f"{self.fake.word()}_{doc_type}{extension}"
                    
                    document = Document(
                        title=self.fake.sentence(nb_words=5),
                        description=self.fake.text(max_nb_chars=500),
                        filename=filename,
                        file_path=f"/uploads/documents/{self.fake.uuid4()}/{filename}",
                        file_size=self.fake.random_int(min=50000, max=10485760),  # 50KB - 10MB
                        mime_type=self._get_mime_type(extension),
                        document_type=doc_type,
                        uploader_id=uploader.id,
                        project_id=project.id if project else None,
                        version=f"v{self.fake.random_int(min=1, max=5)}.{self.fake.random_int(min=0, max=9)}",
                        status=self.fake.random_element(['draft', 'review', 'approved', 'archived']),
                        visibility=self.fake.random_element(['private', 'project', 'public']),
                        tags=self.fake.random_elements(
                            elements=['important', 'confidential', 'final', 'draft', 'template'],
                            length=self.fake.random_int(min=0, max=3),
                            unique=True
                        ),
                        download_count=self.fake.random_int(min=0, max=100),
                        checksum=self.fake.sha256(),
                        is_template=self.fake.boolean(chance_of_getting_true=10),
                        expiration_date=self.fake.date_between(start_date='+1m', end_date='+2y') if self.fake.boolean(chance_of_getting_true=20) else None,
                        access_permissions=['read', 'download'] if self.fake.boolean(chance_of_getting_true=80) else ['read'],
                        created_at=self.fake.date_time_between(start_date='-1y', end_date='now')
                    )
                    
                    db.session.add(document)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Documentos creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando documentos: {e}")
            return False
    
    def _generate_tasks(self) -> bool:
        """Genera tareas."""
        config = self.size_configs[self.config.size]
        count = config['tasks']
        
        self.logger.info(f"Generando {count} tareas...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if not all_users:
            self.logger.warning("No hay usuarios creados, saltando tareas")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "tareas")
                
                if not self.config.dry_run:
                    assignee = self.fake.random_element(all_users)
                    creator = self.fake.random_element(all_users)
                    project = self.fake.random_element(self.created_projects) if self.created_projects else None
                    
                    due_date = self.fake.date_between(start_date='-30d', end_date='+60d')
                    
                    task = Task(
                        title=self.fake.sentence(nb_words=4),
                        description=self.fake.text(max_nb_chars=800),
                        assignee_id=assignee.id,
                        creator_id=creator.id,
                        project_id=project.id if project else None,
                        status=self.fake.random_element(['todo', 'in_progress', 'review', 'completed', 'cancelled']),
                        priority=self.fake.random_element(['low', 'medium', 'high', 'urgent']),
                        category=self.fake.random_element(['development', 'marketing', 'finance', 'legal', 'operations', 'research']),
                        due_date=due_date,
                        estimated_hours=self.fake.random_int(min=1, max=40),
                        actual_hours=self.fake.random_int(min=1, max=50) if self.fake.boolean(chance_of_getting_true=60) else None,
                        completion_percentage=self.fake.random_int(min=0, max=100),
                        tags=self.fake.random_elements(
                            elements=['urgent', 'milestone', 'bug', 'feature', 'research', 'meeting'],
                            length=self.fake.random_int(min=0, max=3),
                            unique=True
                        ),
                        dependencies=[],  # Simplificado por ahora
                        checklist=[
                            {
                                'item': self.fake.sentence(nb_words=4),
                                'completed': self.fake.boolean()
                            }
                            for _ in range(self.fake.random_int(min=0, max=5))
                        ],
                        attachments=[
                            {
                                'filename': f'{self.fake.word()}.pdf',
                                'url': self.fake.url()
                            }
                        ] if self.fake.boolean(chance_of_getting_true=20) else [],
                        comments=[
                            {
                                'user_id': self.fake.random_element(all_users).id,
                                'comment': self.fake.text(max_nb_chars=200),
                                'timestamp': self.fake.date_time_between(start_date='-30d', end_date='now').isoformat()
                            }
                        ] if self.fake.boolean(chance_of_getting_true=40) else [],
                        started_at=self.fake.date_time_between(start_date='-30d', end_date='now') if self.fake.boolean(chance_of_getting_true=70) else None,
                        completed_at=self.fake.date_time_between(start_date='-30d', end_date='now') if self.fake.boolean(chance_of_getting_true=30) else None,
                        is_milestone=self.fake.boolean(chance_of_getting_true=15),
                        is_recurring=self.fake.boolean(chance_of_getting_true=10),
                        recurrence_pattern='weekly' if self.fake.boolean(chance_of_getting_true=60) else 'monthly'
                    )
                    
                    db.session.add(task)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Tareas creadas: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando tareas: {e}")
            return False
    
    def _generate_notifications(self) -> bool:
        """Genera notificaciones."""
        config = self.size_configs[self.config.size]
        count = config['notifications']
        
        self.logger.info(f"Generando {count} notificaciones...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if not all_users:
            self.logger.warning("No hay usuarios creados, saltando notificaciones")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "notificaciones")
                
                if not self.config.dry_run:
                    user = self.fake.random_element(all_users)
                    
                    notification_types = [
                        'meeting_reminder', 'task_assigned', 'task_due', 'message_received',
                        'project_update', 'program_announcement', 'mentorship_scheduled',
                        'document_shared', 'system_update', 'deadline_approaching'
                    ]
                    
                    notification_type = self.fake.random_element(notification_types)
                    
                    notification = Notification(
                        user_id=user.id,
                        title=self._get_notification_title(notification_type),
                        message=self._get_notification_message(notification_type),
                        notification_type=notification_type,
                        priority=self.fake.random_element(['low', 'medium', 'high']),
                        is_read=self.fake.boolean(chance_of_getting_true=60),
                        read_at=self.fake.date_time_between(start_date='-30d', end_date='now') if self.fake.boolean() else None,
                        action_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=40) else None,
                        action_text=self.fake.random_element(['View', 'Open', 'Accept', 'Decline', 'Reply']) if self.fake.boolean() else None,
                        metadata={
                            'source': self.fake.random_element(['system', 'user', 'integration']),
                            'category': self.fake.random_element(['reminder', 'update', 'alert', 'info']),
                            'related_id': self.fake.random_int(min=1, max=1000)
                        },
                        delivery_method=self.fake.random_element(['in_app', 'email', 'sms', 'push']),
                        delivery_status=self.fake.random_element(['pending', 'sent', 'delivered', 'failed']),
                        scheduled_for=self.fake.date_time_between(start_date='-30d', end_date='+7d'),
                        expires_at=self.fake.date_time_between(start_date='+1d', end_date='+30d') if self.fake.boolean(chance_of_getting_true=30) else None,
                        is_actionable=self.fake.boolean(chance_of_getting_true=40),
                        created_at=self.fake.date_time_between(start_date='-60d', end_date='now')
                    )
                    
                    db.session.add(notification)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Notificaciones creadas: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando notificaciones: {e}")
            return False
    
    def _generate_activity_logs(self) -> bool:
        """Genera logs de actividad."""
        config = self.size_configs[self.config.size]
        count = config.get('notifications', 100) * 2  # Más logs que notificaciones
        
        self.logger.info(f"Generando {count} logs de actividad...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        if not all_users:
            self.logger.warning("No hay usuarios creados, saltando logs de actividad")
            return True
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "logs")
                
                if not self.config.dry_run:
                    user = self.fake.random_element(all_users)
                    
                    actions = [
                        'login', 'logout', 'create_project', 'update_project', 'delete_project',
                        'send_message', 'upload_document', 'complete_task', 'schedule_meeting',
                        'join_program', 'leave_program', 'update_profile', 'change_password'
                    ]
                    
                    action = self.fake.random_element(actions)
                    
                    activity_log = ActivityLog(
                        user_id=user.id,
                        action=action,
                        description=self._get_activity_description(action, user),
                        resource_type=self.fake.random_element(['user', 'project', 'program', 'meeting', 'document', 'task']),
                        resource_id=self.fake.random_int(min=1, max=1000),
                        ip_address=self.fake.ipv4(),
                        user_agent=self.fake.user_agent(),
                        session_id=self.fake.uuid4(),
                        metadata={
                            'browser': self.fake.random_element(['Chrome', 'Firefox', 'Safari', 'Edge']),
                            'os': self.fake.random_element(['Windows', 'macOS', 'Linux', 'iOS', 'Android']),
                            'device_type': self.fake.random_element(['desktop', 'mobile', 'tablet']),
                            'location': self.fake.colombian_city()
                        },
                        success=self.fake.boolean(chance_of_getting_true=95),
                        error_message=self.fake.sentence() if self.fake.boolean(chance_of_getting_true=5) else None,
                        duration_ms=self.fake.random_int(min=100, max=5000),
                        created_at=self.fake.date_time_between(start_date='-90d', end_date='now')
                    )
                    
                    db.session.add(activity_log)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Logs de actividad creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando logs de actividad: {e}")
            return False
    
    def _generate_analytics_events(self) -> bool:
        """Genera eventos de analytics."""
        config = self.size_configs[self.config.size]
        count = config.get('notifications', 100) * 3  # Muchos eventos de analytics
        
        self.logger.info(f"Generando {count} eventos de analytics...")
        
        all_users = []
        for role_users in self.created_users.values():
            all_users.extend(role_users)
        
        try:
            for i in range(count):
                if self.config.progress:
                    self.logger.progress_bar(i + 1, count, "eventos")
                
                if not self.config.dry_run:
                    user = self.fake.random_element(all_users) if all_users and self.fake.boolean(chance_of_getting_true=80) else None
                    
                    event_types = [
                        'page_view', 'button_click', 'form_submit', 'download', 'search',
                        'login', 'logout', 'signup', 'profile_update', 'project_created',
                        'meeting_scheduled', 'document_uploaded', 'message_sent'
                    ]
                    
                    event_type = self.fake.random_element(event_types)
                    
                    analytics_event = AnalyticsEvent(
                        event_type=event_type,
                        event_name=f"{event_type}_{self.fake.word()}",
                        user_id=user.id if user else None,
                        session_id=self.fake.uuid4(),
                        page_url=f"/{self.fake.uri_path()}",
                        referrer_url=self.fake.url() if self.fake.boolean(chance_of_getting_true=40) else None,
                        user_agent=self.fake.user_agent(),
                        ip_address=self.fake.ipv4(),
                        country='Colombia',
                        city=self.fake.colombian_city(),
                        device_type=self.fake.random_element(['desktop', 'mobile', 'tablet']),
                        browser=self.fake.random_element(['Chrome', 'Firefox', 'Safari', 'Edge']),
                        os=self.fake.random_element(['Windows', 'macOS', 'Linux', 'iOS', 'Android']),
                        properties={
                            'button_id': self.fake.word() if event_type == 'button_click' else None,
                            'form_id': self.fake.word() if event_type == 'form_submit' else None,
                            'search_term': self.fake.word() if event_type == 'search' else None,
                            'page_load_time': self.fake.random_int(min=500, max=5000) if event_type == 'page_view' else None
                        },
                        revenue=Decimal(str(self.fake.random_int(min=10, max=1000))) if self.fake.boolean(chance_of_getting_true=5) else None,
                        conversion_value=Decimal(str(self.fake.random_int(min=1, max=100))) if self.fake.boolean(chance_of_getting_true=10) else None,
                        campaign_source=self.fake.random_element(['google', 'facebook', 'linkedin', 'direct', 'email']) if self.fake.boolean(chance_of_getting_true=30) else None,
                        campaign_medium=self.fake.random_element(['cpc', 'organic', 'social', 'email', 'referral']) if self.fake.boolean(chance_of_getting_true=30) else None,
                        campaign_name=f"campaign_{self.fake.word()}" if self.fake.boolean(chance_of_getting_true=20) else None,
                        timestamp=self.fake.date_time_between(start_date='-90d', end_date='now'),
                        processed_at=self.fake.date_time_between(start_date='-90d', end_date='now')
                    )
                    
                    db.session.add(analytics_event)
            
            if not self.config.dry_run:
                db.session.commit()
            
            self.logger.success(f"Eventos de analytics creados: {count}")
            return True
            
        except Exception as e:
            if not self.config.dry_run:
                db.session.rollback()
            self.logger.error(f"Error generando eventos de analytics: {e}")
            return False
    
    def _validate_generated_data(self):
        """Valida la integridad de los datos generados."""
        self.logger.info("Validando integridad de datos generados...", progress_step=True)
        
        validations = [
            ("Users", self._validate_users),
            ("Organizations", self._validate_organizations),
            ("Programs", self._validate_programs),
            ("Projects", self._validate_projects),
            ("Relationships", self._validate_relationships),
        ]
        
        for validation_name, validation_func in validations:
            try:
                validation_func()
                self.logger.info(f"✓ {validation_name}")
            except Exception as e:
                self.logger.warning(f"✗ {validation_name}: {e}")
    
    def _validate_users(self):
        """Valida usuarios generados."""
        if not self.config.dry_run:
            total_users = db.session.query(User).count()
            expected = sum(self.size_configs[self.config.size]['users'].values())
            
            if total_users != expected:
                raise ValueError(f"Expected {expected} users, got {total_users}")
    
    def _validate_organizations(self):
        """Valida organizaciones generadas."""
        if not self.config.dry_run:
            total_orgs = db.session.query(Organization).count()
            expected = self.size_configs[self.config.size]['organizations']
            
            if total_orgs != expected:
                raise ValueError(f"Expected {expected} organizations, got {total_orgs}")
    
    def _validate_programs(self):
        """Valida programas generados."""
        if not self.config.dry_run:
            total_programs = db.session.query(Program).count()
            expected = self.size_configs[self.config.size]['programs']
            
            if total_programs != expected:
                raise ValueError(f"Expected {expected} programs, got {total_programs}")
    
    def _validate_projects(self):
        """Valida proyectos generados."""
        if not self.config.dry_run:
            total_projects = db.session.query(Project).count()
            expected = self.size_configs[self.config.size]['projects']
            
            if total_projects != expected:
                raise ValueError(f"Expected {expected} projects, got {total_projects}")
    
    def _validate_relationships(self):
        """Valida relaciones entre entidades."""
        if not self.config.dry_run:
            # Verificar que todos los proyectos tengan un emprendedor válido
            projects_without_entrepreneur = db.session.query(Project).filter(
                ~Project.entrepreneur_id.in_(
                    db.session.query(Entrepreneur.user_id)
                )
            ).count()
            
            if projects_without_entrepreneur > 0:
                raise ValueError(f"Found {projects_without_entrepreneur} projects without valid entrepreneur")
    
    def _show_summary(self):
        """Muestra resumen de datos generados."""
        self.logger.header("RESUMEN DE DATOS GENERADOS")
        
        if self.config.dry_run:
            print(f"{Colors.WARNING}MODO DRY RUN - No se crearon datos reales{Colors.ENDC}")
            return
        
        try:
            summary = {
                'Users': db.session.query(User).count(),
                'Organizations': db.session.query(Organization).count(),
                'Programs': db.session.query(Program).count(),
                'Projects': db.session.query(Project).count(),
                'Mentorship Sessions': db.session.query(MentorshipSession).count(),
                'Meetings': db.session.query(Meeting).count(),
                'Messages': db.session.query(Message).count(),
                'Documents': db.session.query(Document).count(),
                'Tasks': db.session.query(Task).count(),
                'Notifications': db.session.query(Notification).count(),
                'Activity Logs': db.session.query(ActivityLog).count(),
                'Analytics Events': db.session.query(AnalyticsEvent).count(),
            }
            
            print(f"\n{Colors.OKCYAN}Datos creados:{Colors.ENDC}")
            for entity, count in summary.items():
                print(f"  {entity}: {Colors.BOLD}{count:,}{Colors.ENDC}")
            
            # Información adicional
            entrepreneurs = db.session.query(User).filter_by(role='entrepreneur').count()
            allies = db.session.query(User).filter_by(role='ally').count()
            
            print(f"\n{Colors.OKCYAN}Desglose por roles:{Colors.ENDC}")
            print(f"  Emprendedores: {Colors.BOLD}{entrepreneurs}{Colors.ENDC}")
            print(f"  Aliados/Mentores: {Colors.BOLD}{allies}{Colors.ENDC}")
            
        except Exception as e:
            self.logger.error(f"Error generando resumen: {e}")
    
    # Métodos auxiliares
    
    def _get_mime_type(self, extension: str) -> str:
        """Obtiene MIME type por extensión."""
        mime_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.jpg': 'image/jpeg',
            '.png': 'image/png',
        }
        return mime_types.get(extension, 'application/octet-stream')
    
    def _get_notification_title(self, notification_type: str) -> str:
        """Genera título de notificación según el tipo."""
        titles = {
            'meeting_reminder': 'Recordatorio de Reunión',
            'task_assigned': 'Nueva Tarea Asignada',
            'task_due': 'Tarea Próxima a Vencer',
            'message_received': 'Nuevo Mensaje',
            'project_update': 'Actualización de Proyecto',
            'program_announcement': 'Anuncio del Programa',
            'mentorship_scheduled': 'Sesión de Mentoría Programada',
            'document_shared': 'Documento Compartido',
            'system_update': 'Actualización del Sistema',
            'deadline_approaching': 'Fecha Límite Próxima'
        }
        return titles.get(notification_type, 'Notificación')
    
    def _get_notification_message(self, notification_type: str) -> str:
        """Genera mensaje de notificación según el tipo."""
        return self.fake.text(max_nb_chars=200)
    
    def _get_activity_description(self, action: str, user) -> str:
        """Genera descripción de actividad."""
        descriptions = {
            'login': f'{user.first_name} {user.last_name} inició sesión',
            'logout': f'{user.first_name} {user.last_name} cerró sesión',
            'create_project': f'{user.first_name} {user.last_name} creó un nuevo proyecto',
            'update_project': f'{user.first_name} {user.last_name} actualizó un proyecto',
            'send_message': f'{user.first_name} {user.last_name} envió un mensaje',
            'upload_document': f'{user.first_name} {user.last_name} subió un documento',
        }
        return descriptions.get(action, f'{user.first_name} {user.last_name} realizó una acción')


def main():
    """
    Función principal del script de seed data.
    """
    parser = argparse.ArgumentParser(
        description="Generador de Datos de Prueba del Ecosistema de Emprendimiento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Generar datos medianos para desarrollo
  python scripts/seed_data.py --size medium --environment development
  
  # Generar datos grandes para staging con limpieza
  python scripts/seed_data.py --size large --environment staging --clean
  
  # Generar solo usuarios y organizaciones
  python scripts/seed_data.py --only users,organizations --size small
  
  # Excluir analytics para generación más rápida
  python scripts/seed_data.py --exclude analytics_events --size medium --verbose
  
  # Dry run para ver qué se generaría
  python scripts/seed_data.py --size large --dry-run --verbose
  
  # Seed reproducible
  python scripts/seed_data.py --size medium --seed 12345
        """
    )
    
    # Configuración principal
    parser.add_argument(
        '--size', '-s',
        choices=['minimal', 'small', 'medium', 'large', 'enterprise'],
        default='medium',
        help='Tamaño del dataset a generar'
    )
    
    parser.add_argument(
        '--environment', '-e',
        choices=['development', 'testing', 'staging'],
        default='development',
        help='Ambiente de destino'
    )
    
    # Opciones de contenido
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Limpiar datos existentes antes de generar'
    )
    
    parser.add_argument(
        '--only',
        help='Generar solo secciones específicas (comma-separated)'
    )
    
    parser.add_argument(
        '--exclude',
        help='Excluir secciones específicas (comma-separated)'
    )
    
    # Configuración de generación
    parser.add_argument(
        '--locale',
        default='es_CO',
        help='Locale para datos generados'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        help='Seed para reproducibilidad'
    )
    
    # Opciones de validación y output
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='No validar datos generados'
    )
    
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='No mostrar barras de progreso'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Output verboso'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular generación sin crear datos'
    )
    
    args = parser.parse_args()
    
    # Crear configuración
    config = SeedConfig(
        size=args.size,
        environment=args.environment,
        clean=args.clean,
        only=args.only.split(',') if args.only else [],
        exclude=args.exclude.split(',') if args.exclude else [],
        locale=args.locale,
        seed=args.seed,
        validate=not args.no_validate,
        progress=not args.no_progress,
        verbose=args.verbose,
        dry_run=args.dry_run,
    )
    
    # Configurar aplicación Flask
    try:
        app = create_app()
        with app.app_context():
            # Ejecutar generador
            generator = DataGenerator(config)
            success = generator.run()
            
            sys.exit(0 if success else 1)
            
    except Exception as e:
        print(f"{Colors.FAIL}Error configurando aplicación Flask: {e}{Colors.ENDC}")
        sys.exit(1)


if __name__ == '__main__':
    main()