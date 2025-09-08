"""
Ecosistema de Emprendimiento - Framework de Testing Unitario
===========================================================

Este módulo configura el framework especializado para testing unitario del ecosistema,
proporcionando herramientas, mocks y utilidades optimizadas para tests de componentes
individuales de la lógica de negocio.

Características especializadas:
- Mocks específicos para servicios del ecosistema
- Utilidades para testing de modelos de datos
- Helpers para testing de cálculos financieros
- Decorators para testing de validaciones de negocio
- Configuración de datos de prueba unitarios
- Testing de algoritmos de matching y scoring
- Utilities para testing de business rules
- Mocks para integraciones externas específicas
- Helpers para testing de métricas y analytics
- Configuración de performance testing unitario

Tipos de testing unitario soportados:
- Model Testing: Validación de modelos SQLAlchemy
- Service Testing: Lógica de servicios aislada
- Algorithm Testing: Algoritmos de negocio puros
- Validation Testing: Reglas de validación
- Calculation Testing: Cálculos financieros/métricas
- Utility Testing: Funciones auxiliares
- Business Rules Testing: Reglas de negocio complejas

Uso:
    from tests.unit import (
        UnitTestCase, ModelTestMixin, ServiceTestMixin,
        mock_external_api, calculate_funding_metrics,
        validate_business_model, create_minimal_user
    )
    
    class TestEntrepreneurModel(UnitTestCase, ModelTestMixin):
        def test_business_validation(self):
            entrepreneur = self.create_valid_entrepreneur()
            assert entrepreneur.is_eligible_for_funding()

Author: Sistema de Testing Empresarial
Created: 2025-06-13
Version: 2.1.0
"""

import os
import sys
import time
import uuid
import decimal
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from dataclasses import dataclass, field
from decimal import Decimal
import json
import logging

# Core testing imports
import pytest
import factory
from faker import Faker

# SQLAlchemy y database testing
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError, ValidationError

# Framework base imports
from tests import (
    logger, fake, TEST_CONFIG, 
    UserFactory, EntrepreneurFactory, AllyFactory, ClientFactory,
    ProjectFactory, MeetingFactory, MessageFactory,
    TestUtils, MockServices
)

# Project imports
try:
    from app.models.base import BaseModel
    from app.models.user import User
    from app.models.entrepreneur import Entrepreneur
    from app.models.ally import Ally  
    from app.models.client import Client
    from app.models.project import Project
    from app.models.meeting import Meeting
    from app.models.organization import Organization
    from app.models.program import Program
    from app.core.exceptions import ValidationError as AppValidationError
    from app.core.exceptions import BusinessRuleError, InsufficientDataError
    from app.services.analytics_service import AnalyticsService
    from app.services.mentorship_service import MentorshipService
    from app.services.project_service import ProjectService
    from app.utils.validators import validate_email, validate_business_model
    from app.utils.calculations import calculate_roi, calculate_valuation
except ImportError as e:
    logger.warning(f"Algunos imports opcionales no disponibles para testing unitario: {e}")


# ============================================================================
# CONFIGURACIÓN GLOBAL DE TESTING UNITARIO
# ============================================================================

# Configuración específica para tests unitarios
UNIT_TEST_CONFIG = {
    'isolated_database': True,
    'mock_external_services': True,
    'fast_execution_mode': True,
    'minimal_data_fixtures': True,
    'strict_assertions': True,
    'performance_monitoring': True,
    'memory_leak_detection': True,
    'deterministic_randomness': True,
    'comprehensive_coverage': True,
    'business_rules_validation': True,
}

# Constantes de testing de negocio
BUSINESS_CONSTANTS = {
    'min_team_size': 1,
    'max_team_size': 20,
    'min_funding_amount': 1000,
    'max_funding_amount': 10000000,
    'min_equity_percentage': 0.1,
    'max_equity_percentage': 100.0,
    'min_valuation': 10000,
    'max_valuation': 1000000000,
    'min_revenue': 0,
    'max_mentorship_hours': 40,
    'min_project_duration_days': 1,
    'max_project_duration_days': 1095,  # 3 años
    'valid_currencies': ['COP', 'USD', 'EUR', 'MXN'],
    'valid_countries': ['CO', 'MX', 'PE', 'CL', 'AR'],
    'valid_industries': [
        'fintech', 'healthtech', 'edtech', 'agtech', 'cleantech',
        'retail', 'logistics', 'entertainment', 'b2b_saas', 'consumer_apps'
    ],
    'valid_project_stages': [
        'idea', 'validation', 'prototype', 'mvp', 'growth', 'scale', 'mature'
    ],
    'valid_program_types': [
        'accelerator', 'incubator', 'bootcamp', 'competition', 'fellowship'
    ]
}

# Datos mínimos para testing rápido
MINIMAL_TEST_DATA = {
    'user': {
        'email': 'test@unit.test',
        'first_name': 'Test',
        'last_name': 'User',
        'password': 'TestPass123!',
        'role_type': 'entrepreneur'
    },
    'entrepreneur': {
        'business_name': 'Test Startup',
        'industry': 'fintech',
        'stage': 'mvp',
        'location': 'Bogotá'
    },
    'project': {
        'name': 'Test Project',
        'description': 'A test project for unit testing',
        'budget': 50000,
        'status': 'active'
    },
    'ally': {
        'expertise_areas': ['business_strategy'],
        'hourly_rate': 100,
        'availability_hours': 10
    },
    'meeting': {
        'title': 'Test Meeting',
        'duration_minutes': 60,
        'meeting_type': 'mentorship'
    }
}

# Configuración de performance para tests unitarios
PERFORMANCE_THRESHOLDS = {
    'max_execution_time_ms': 100,    # 100ms máximo por test unitario
    'max_database_queries': 5,        # Máximo 5 queries por test
    'max_memory_usage_mb': 10,        # 10MB máximo de memoria
    'max_external_calls': 0,          # No llamadas externas en unit tests
}


# ============================================================================
# CLASES BASE PARA TESTING UNITARIO
# ============================================================================

class UnitTestCase:
    """
    Clase base para todos los tests unitarios del ecosistema.
    Proporciona funcionalidades comunes y configuración estándar.
    """
    
    def setup_method(self, method):
        """Configuración ejecutada antes de cada test."""
        self.start_time = time.time()
        self.initial_memory = self._get_memory_usage()
        self.query_count = 0
        self.external_calls = 0
        
        logger.debug(f"🧪 Iniciando test unitario: {method.__name__}")
    
    def teardown_method(self, method):
        """Limpieza ejecutada después de cada test."""
        execution_time = (time.time() - self.start_time) * 1000  # ms
        memory_used = self._get_memory_usage() - self.initial_memory
        
        # Validar thresholds de performance
        if execution_time > PERFORMANCE_THRESHOLDS['max_execution_time_ms']:
            logger.warning(
                f"⚠️  Test lento: {method.__name__} tardó {execution_time:.2f}ms "
                f"(límite: {PERFORMANCE_THRESHOLDS['max_execution_time_ms']}ms)"
            )
        
        if memory_used > PERFORMANCE_THRESHOLDS['max_memory_usage_mb']:
            logger.warning(
                f"⚠️  Uso alto de memoria: {method.__name__} usó {memory_used:.2f}MB "
                f"(límite: {PERFORMANCE_THRESHOLDS['max_memory_usage_mb']}MB)"
            )
        
        if self.query_count > PERFORMANCE_THRESHOLDS['max_database_queries']:
            logger.warning(
                f"⚠️  Muchas queries: {method.__name__} ejecutó {self.query_count} queries "
                f"(límite: {PERFORMANCE_THRESHOLDS['max_database_queries']})"
            )
        
        logger.debug(f"✅ Test completado: {method.__name__} ({execution_time:.2f}ms)")
    
    def _get_memory_usage(self):
        """Obtiene uso actual de memoria."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return 0
    
    def assert_business_rule(self, condition, message="Business rule violation"):
        """Assertion específica para reglas de negocio."""
        if not condition:
            raise AssertionError(f"🚫 {message}")
    
    def assert_valid_currency(self, amount, currency='COP'):
        """Valida que un monto esté en formato de moneda válido."""
        assert isinstance(amount, (int, float, Decimal)), "Amount must be numeric"
        assert currency in BUSINESS_CONSTANTS['valid_currencies'], f"Invalid currency: {currency}"
        assert amount >= 0, "Amount must be non-negative"
    
    def assert_valid_percentage(self, percentage):
        """Valida que un porcentaje esté en rango válido."""
        assert isinstance(percentage, (int, float, Decimal)), "Percentage must be numeric"
        assert 0 <= percentage <= 100, f"Percentage must be between 0-100, got {percentage}"
    
    def assert_valid_email(self, email):
        """Valida formato de email."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        assert re.match(pattern, email), f"Invalid email format: {email}"


class ModelTestMixin:
    """
    Mixin para testing de modelos SQLAlchemy.
    Proporciona utilidades específicas para testing de modelos de datos.
    """
    
    def create_minimal_user(self, **overrides):
        """Crea usuario con datos mínimos para testing."""
        data = {**MINIMAL_TEST_DATA['user'], **overrides}
        return UserFactory(**data)
    
    def create_minimal_entrepreneur(self, user=None, **overrides):
        """Crea emprendedor con datos mínimos."""
        if user is None:
            user = self.create_minimal_user(role_type='entrepreneur')
        
        data = {**MINIMAL_TEST_DATA['entrepreneur'], **overrides}
        return EntrepreneurFactory(user=user, **data)
    
    def create_minimal_project(self, entrepreneur=None, **overrides):
        """Crea proyecto con datos mínimos."""
        if entrepreneur is None:
            entrepreneur = self.create_minimal_entrepreneur()
        
        data = {**MINIMAL_TEST_DATA['project'], **overrides}
        return ProjectFactory(entrepreneur=entrepreneur, **data)
    
    def assert_model_valid(self, model_instance):
        """Valida que un modelo sea válido según reglas de negocio."""
        assert model_instance is not None, "Model instance is None"
        assert hasattr(model_instance, 'id'), "Model must have ID field"
        
        # Validar timestamps si existen
        if hasattr(model_instance, 'created_at'):
            assert model_instance.created_at is not None, "created_at must be set"
            assert model_instance.created_at <= datetime.now(timezone.utc), "created_at cannot be in future"
        
        if hasattr(model_instance, 'updated_at'):
            assert model_instance.updated_at is not None, "updated_at must be set"
            assert model_instance.updated_at >= model_instance.created_at, "updated_at must be >= created_at"
    
    def assert_model_integrity(self, model_instance):
        """Valida integridad de modelo específica del dominio."""
        model_type = type(model_instance).__name__
        
        if model_type == 'User':
            self._assert_user_integrity(model_instance)
        elif model_type == 'Entrepreneur':
            self._assert_entrepreneur_integrity(model_instance)
        elif model_type == 'Project':
            self._assert_project_integrity(model_instance)
        elif model_type == 'Meeting':
            self._assert_meeting_integrity(model_instance)
    
    def _assert_user_integrity(self, user):
        """Validaciones específicas para modelo User."""
        assert user.email is not None, "User email is required"
        assert user.first_name is not None, "User first_name is required"
        assert user.role_type in ['admin', 'entrepreneur', 'ally', 'client'], f"Invalid role: {user.role_type}"
        self.assert_valid_email(user.email)
        
        if hasattr(user, 'is_active'):
            assert isinstance(user.is_active, bool), "is_active must be boolean"
    
    def _assert_entrepreneur_integrity(self, entrepreneur):
        """Validaciones específicas para modelo Entrepreneur."""
        assert entrepreneur.user is not None, "Entrepreneur must have user"
        assert entrepreneur.business_name is not None, "Business name is required"
        assert entrepreneur.industry in BUSINESS_CONSTANTS['valid_industries'], f"Invalid industry: {entrepreneur.industry}"
        assert entrepreneur.stage in BUSINESS_CONSTANTS['valid_project_stages'], f"Invalid stage: {entrepreneur.stage}"
        
        if hasattr(entrepreneur, 'founded_date') and entrepreneur.founded_date:
            assert entrepreneur.founded_date <= date.today(), "Founded date cannot be in future"
    
    def _assert_project_integrity(self, project):
        """Validaciones específicas para modelo Project."""
        assert project.entrepreneur is not None, "Project must have entrepreneur"
        assert project.name is not None, "Project name is required"
        assert project.budget >= BUSINESS_CONSTANTS['min_funding_amount'], f"Budget too low: {project.budget}"
        assert project.budget <= BUSINESS_CONSTANTS['max_funding_amount'], f"Budget too high: {project.budget}"
        
        if hasattr(project, 'start_date') and project.start_date:
            if hasattr(project, 'end_date') and project.end_date:
                assert project.end_date >= project.start_date, "End date must be >= start date"
    
    def _assert_meeting_integrity(self, meeting):
        """Validaciones específicas para modelo Meeting."""
        assert meeting.title is not None, "Meeting title is required"
        assert meeting.duration_minutes > 0, "Duration must be positive"
        assert meeting.duration_minutes <= BUSINESS_CONSTANTS['max_mentorship_hours'] * 60, "Duration too long"
        
        if hasattr(meeting, 'scheduled_at') and meeting.scheduled_at:
            assert meeting.scheduled_at >= datetime.now(timezone.utc) - timedelta(days=365), "Scheduled time too far in past"


class ServiceTestMixin:
    """
    Mixin para testing de servicios y lógica de negocio.
    Proporciona utilidades para testing aislado de servicios.
    """
    
    def mock_external_dependencies(self):
        """Configura mocks para todas las dependencias externas."""
        self.mocks = {}
        
        # Mock de servicios externos
        self.mocks['email_service'] = Mock()
        self.mocks['sms_service'] = Mock()
        self.mocks['google_calendar'] = Mock()
        self.mocks['google_meet'] = Mock()
        self.mocks['file_storage'] = Mock()
        self.mocks['analytics_service'] = Mock()
        
        # Configurar respuestas por defecto
        self.mocks['email_service'].send_email.return_value = True
        self.mocks['sms_service'].send_sms.return_value = True
        self.mocks['google_calendar'].create_event.return_value = {'id': 'test_event_123'}
        self.mocks['google_meet'].create_meeting.return_value = {'meet_link': 'https://meet.google.com/test'}
        self.mocks['file_storage'].upload_file.return_value = {'url': 'https://storage.test.com/file.pdf'}
        self.mocks['analytics_service'].track_event.return_value = True
        
        return self.mocks
    
    def assert_service_method_called(self, service_mock, method_name, *args, **kwargs):
        """Verifica que un método de servicio fue llamado con argumentos específicos."""
        method_mock = getattr(service_mock, method_name)
        if args and kwargs:
            method_mock.assert_called_with(*args, **kwargs)
        elif args:
            method_mock.assert_called_with(*args)
        elif kwargs:
            method_mock.assert_called_with(**kwargs)
        else:
            method_mock.assert_called()
    
    def assert_no_external_calls(self):
        """Verifica que no se hicieron llamadas externas durante el test."""
        assert self.external_calls == 0, f"Expected 0 external calls, got {self.external_calls}"
    
    def create_service_with_mocks(self, service_class, **mock_dependencies):
        """Crea instancia de servicio con dependencias mockeadas."""
        # Preparar mocks por defecto
        default_mocks = self.mock_external_dependencies()
        default_mocks.update(mock_dependencies)
        
        # Crear instancia del servicio inyectando mocks
        if hasattr(service_class, '__init__'):
            # Intentar inyectar mocks como argumentos del constructor
            import inspect
            sig = inspect.signature(service_class.__init__)
            init_kwargs = {}
            
            for param_name in sig.parameters:
                if param_name in default_mocks:
                    init_kwargs[param_name] = default_mocks[param_name]
            
            return service_class(**init_kwargs)
        else:
            return service_class()


class AlgorithmTestMixin:
    """
    Mixin para testing de algoritmos específicos del ecosistema.
    """
    
    def assert_algorithm_deterministic(self, algorithm_func, inputs, expected_output):
        """Verifica que un algoritmo sea determinístico."""
        for _ in range(5):  # Ejecutar 5 veces
            result = algorithm_func(*inputs)
            assert result == expected_output, f"Algorithm not deterministic: {result} != {expected_output}"
    
    def assert_algorithm_performance(self, algorithm_func, inputs, max_time_ms=50):
        """Verifica performance de algoritmo."""
        start_time = time.time()
        result = algorithm_func(*inputs)
        execution_time = (time.time() - start_time) * 1000
        
        assert execution_time <= max_time_ms, f"Algorithm too slow: {execution_time:.2f}ms > {max_time_ms}ms"
        return result
    
    def test_matching_algorithm(self, startups, investors, algorithm_func):
        """Test específico para algoritmos de matching."""
        matches = algorithm_func(startups, investors)
        
        # Verificar que retorna matches válidos
        assert isinstance(matches, list), "Matches should be a list"
        
        for match in matches:
            assert 'startup' in match, "Each match should have startup"
            assert 'investor' in match, "Each match should have investor"
            assert 'score' in match, "Each match should have score"
            assert 0 <= match['score'] <= 1, f"Score should be 0-1, got {match['score']}"
        
        # Verificar orden por score (descendente)
        scores = [match['score'] for match in matches]
        assert scores == sorted(scores, reverse=True), "Matches should be sorted by score (desc)"
        
        return matches
    
    def test_scoring_algorithm(self, entities, scoring_func, expected_range=(0, 100)):
        """Test específico para algoritmos de scoring."""
        min_score, max_score = expected_range
        
        for entity in entities:
            score = scoring_func(entity)
            assert isinstance(score, (int, float, Decimal)), f"Score should be numeric, got {type(score)}"
            assert min_score <= score <= max_score, f"Score {score} out of range {expected_range}"
        
        return [scoring_func(entity) for entity in entities]


# ============================================================================
# UTILIDADES ESPECÍFICAS DEL ECOSISTEMA
# ============================================================================

class BusinessCalculations:
    """
    Utilidades para testing de cálculos de negocio del ecosistema.
    """
    
    @staticmethod
    def calculate_valuation_metrics(project_data):
        """Calcula métricas de valuación para testing."""
        revenue = project_data.get('monthly_revenue', 0) * 12  # ARR
        growth_rate = project_data.get('growth_rate', 0)
        market_size = project_data.get('market_size', 1000000)
        team_score = project_data.get('team_score', 5)  # 1-10
        
        # Fórmula simplificada para testing
        base_multiple = 3 + (growth_rate / 100) * 2  # 3x-5x revenue
        team_multiplier = 0.8 + (team_score / 10) * 0.4  # 0.8x-1.2x
        market_multiplier = min(1.5, market_size / 10000000)  # Cap at 1.5x
        
        valuation = revenue * base_multiple * team_multiplier * market_multiplier
        
        return {
            'estimated_valuation': max(10000, int(valuation)),  # Mínimo 10K
            'revenue_multiple': base_multiple,
            'team_factor': team_multiplier,
            'market_factor': market_multiplier,
            'confidence_score': min(1.0, (team_score + growth_rate/10) / 15)
        }
    
    @staticmethod
    def calculate_funding_recommendation(entrepreneur_profile, project_data):
        """Calcula recomendación de funding para testing."""
        current_stage = entrepreneur_profile.get('stage', 'idea')
        burn_rate = project_data.get('burn_rate', 10000)
        runway_target_months = project_data.get('runway_target', 18)
        
        # Rangos típicos por stage
        stage_ranges = {
            'idea': (10000, 50000),
            'validation': (25000, 100000),
            'prototype': (50000, 250000),
            'mvp': (100000, 500000),
            'growth': (250000, 2000000),
            'scale': (500000, 10000000)
        }
        
        min_funding, max_funding = stage_ranges.get(current_stage, (10000, 50000))
        
        # Calcular funding basado en runway
        runway_funding = burn_rate * runway_target_months
        
        # Recomendar el mayor entre rango de stage y runway
        recommended_funding = max(min_funding, min(max_funding, runway_funding))
        
        return {
            'recommended_amount': recommended_funding,
            'min_viable_amount': min_funding,
            'max_realistic_amount': max_funding,
            'runway_months': runway_target_months,
            'stage_appropriate': min_funding <= recommended_funding <= max_funding
        }
    
    @staticmethod
    def calculate_mentor_match_score(entrepreneur, mentor):
        """Calcula score de matching mentor-emprendedor para testing."""
        score = 0.0
        
        # Matching por expertise (40% del score)
        entrepreneur_needs = entrepreneur.get('needs', [])
        mentor_expertise = mentor.get('expertise_areas', [])
        expertise_overlap = len(set(entrepreneur_needs) & set(mentor_expertise))
        expertise_score = min(1.0, expertise_overlap / max(1, len(entrepreneur_needs)))
        score += expertise_score * 0.4
        
        # Matching por industria (30% del score)
        if entrepreneur.get('industry') in mentor.get('industry_experience', []):
            score += 0.3
        
        # Matching por stage (20% del score)
        entrepreneur_stage = entrepreneur.get('stage', 'idea')
        mentor_stage_exp = mentor.get('stage_experience', [])
        if entrepreneur_stage in mentor_stage_exp:
            score += 0.2
        
        # Disponibilidad y costo (10% del score)
        mentor_rate = mentor.get('hourly_rate', 0)
        entrepreneur_budget = entrepreneur.get('mentorship_budget', 0)
        if mentor_rate <= entrepreneur_budget:
            score += 0.1
        
        return min(1.0, score)
    
    @staticmethod
    def calculate_program_eligibility(entrepreneur_profile, program_requirements):
        """Calcula elegibilidad para programa para testing."""
        eligibility = {
            'eligible': True,
            'score': 0.0,
            'missing_requirements': [],
            'recommendations': []
        }
        
        # Verificar requisitos obligatorios
        if 'min_team_size' in program_requirements:
            team_size = entrepreneur_profile.get('team_size', 1)
            if team_size < program_requirements['min_team_size']:
                eligibility['eligible'] = False
                eligibility['missing_requirements'].append(f'Team size too small: {team_size}')
        
        if 'required_stage' in program_requirements:
            current_stage = entrepreneur_profile.get('stage', 'idea')
            required_stages = program_requirements['required_stage']
            if current_stage not in required_stages:
                eligibility['eligible'] = False
                eligibility['missing_requirements'].append(f'Stage not suitable: {current_stage}')
        
        if 'min_revenue' in program_requirements:
            revenue = entrepreneur_profile.get('monthly_revenue', 0)
            if revenue < program_requirements['min_revenue']:
                eligibility['eligible'] = False
                eligibility['missing_requirements'].append(f'Revenue too low: {revenue}')
        
        # Calcular score si es elegible
        if eligibility['eligible']:
            # Score basado en fit con programa
            stage_fit = 0.3 if entrepreneur_profile.get('stage') in program_requirements.get('target_stages', []) else 0.1
            industry_fit = 0.2 if entrepreneur_profile.get('industry') in program_requirements.get('focus_industries', []) else 0.1
            traction_score = min(0.3, entrepreneur_profile.get('monthly_revenue', 0) / 10000 * 0.3)
            team_score = min(0.2, entrepreneur_profile.get('team_size', 1) / 5 * 0.2)
            
            eligibility['score'] = stage_fit + industry_fit + traction_score + team_score
        
        return eligibility


class EcosystemMetrics:
    """
    Utilidades para testing de métricas del ecosistema.
    """
    
    @staticmethod
    def calculate_ecosystem_health_score(metrics_data):
        """Calcula score de salud del ecosistema para testing."""
        # Métricas clave
        growth_rate = metrics_data.get('monthly_growth_rate', 0)
        retention_rate = metrics_data.get('retention_rate', 0)
        success_rate = metrics_data.get('success_rate', 0)
        funding_rate = metrics_data.get('funding_success_rate', 0)
        mentor_satisfaction = metrics_data.get('mentor_satisfaction', 0)
        
        # Pesos por importancia
        weights = {
            'growth': 0.25,
            'retention': 0.25,
            'success': 0.20,
            'funding': 0.15,
            'satisfaction': 0.15
        }
        
        # Normalizar métricas (0-1)
        normalized_growth = min(1.0, growth_rate / 20)  # 20% growth = 1.0
        normalized_retention = retention_rate / 100 if retention_rate <= 100 else 1.0
        normalized_success = success_rate / 100 if success_rate <= 100 else 1.0
        normalized_funding = funding_rate / 100 if funding_rate <= 100 else 1.0
        normalized_satisfaction = mentor_satisfaction / 10 if mentor_satisfaction <= 10 else mentor_satisfaction / 100
        
        # Calcular score ponderado
        health_score = (
            normalized_growth * weights['growth'] +
            normalized_retention * weights['retention'] +
            normalized_success * weights['success'] +
            normalized_funding * weights['funding'] +
            normalized_satisfaction * weights['satisfaction']
        )
        
        return {
            'overall_score': round(health_score * 100, 2),  # 0-100
            'grade': EcosystemMetrics._score_to_grade(health_score),
            'component_scores': {
                'growth': round(normalized_growth * 100, 1),
                'retention': round(normalized_retention * 100, 1),
                'success': round(normalized_success * 100, 1),
                'funding': round(normalized_funding * 100, 1),
                'satisfaction': round(normalized_satisfaction * 100, 1)
            },
            'recommendations': EcosystemMetrics._generate_recommendations(health_score, {
                'growth': normalized_growth,
                'retention': normalized_retention,
                'success': normalized_success,
                'funding': normalized_funding,
                'satisfaction': normalized_satisfaction
            })
        }
    
    @staticmethod
    def _score_to_grade(score):
        """Convierte score numérico a grade."""
        if score >= 0.9:
            return 'A+'
        elif score >= 0.8:
            return 'A'
        elif score >= 0.7:
            return 'B+'
        elif score >= 0.6:
            return 'B'
        elif score >= 0.5:
            return 'C+'
        elif score >= 0.4:
            return 'C'
        else:
            return 'D'
    
    @staticmethod
    def _generate_recommendations(overall_score, component_scores):
        """Genera recomendaciones basadas en scores."""
        recommendations = []
        
        if overall_score < 0.6:
            recommendations.append("El ecosistema necesita mejoras significativas")
        
        if component_scores['growth'] < 0.5:
            recommendations.append("Implementar estrategias de crecimiento y adquisición")
        
        if component_scores['retention'] < 0.7:
            recommendations.append("Mejorar experiencia de usuario y valor entregado")
        
        if component_scores['success'] < 0.6:
            recommendations.append("Fortalecer programas de mentoría y soporte")
        
        if component_scores['funding'] < 0.5:
            recommendations.append("Expandir red de inversionistas y mejorar preparación")
        
        if component_scores['satisfaction'] < 0.7:
            recommendations.append("Mejorar matching mentor-emprendedor y procesos")
        
        return recommendations


# ============================================================================
# DECORATORS PARA TESTING UNITARIO
# ============================================================================

def isolate_database(func):
    """Decorator que asegura aislamiento completo de base de datos."""
    def wrapper(*args, **kwargs):
        # Crear engine en memoria temporal
        engine = create_engine(
            'sqlite:///:memory:',
            poolclass=StaticPool,
            connect_args={'check_same_thread': False}
        )
        
        # Crear sesión aislada
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Crear esquema
            from app.extensions import db
            db.metadata.create_all(engine)
            
            # Ejecutar test con sesión aislada
            result = func(*args, session=session, **kwargs)
            
            return result
        finally:
            session.close()
            engine.dispose()
    
    return wrapper


def mock_external_services(services_to_mock=None):
    """Decorator que mockea servicios externos automáticamente."""
    if services_to_mock is None:
        services_to_mock = ['email', 'sms', 'google_calendar', 'file_storage']
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            patches = []
            
            for service in services_to_mock:
                if service == 'email':
                    patch_obj = patch('app.services.email.EmailService')
                elif service == 'sms':
                    patch_obj = patch('app.services.sms.SMSService')
                elif service == 'google_calendar':
                    patch_obj = patch('app.services.google_calendar.GoogleCalendarService')
                elif service == 'file_storage':
                    patch_obj = patch('app.services.file_storage.FileStorageService')
                else:
                    continue
                
                mock_service = patch_obj.start()
                patches.append(patch_obj)
                kwargs[f'mock_{service}'] = mock_service
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                for patch_obj in patches:
                    patch_obj.stop()
        
        return wrapper
    return decorator


def validate_business_rules(rules=None):
    """Decorator que valida reglas de negocio automáticamente."""
    if rules is None:
        rules = ['financial', 'temporal', 'logical']
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Ejecutar función
            result = func(*args, **kwargs)
            
            # Validar reglas de negocio en el resultado
            if isinstance(result, dict):
                for rule in rules:
                    if rule == 'financial':
                        _validate_financial_rules(result)
                    elif rule == 'temporal':
                        _validate_temporal_rules(result)
                    elif rule == 'logical':
                        _validate_logical_rules(result)
            
            return result
        
        return wrapper
    return decorator


def _validate_financial_rules(data):
    """Valida reglas financieras en los datos."""
    for key, value in data.items():
        if 'amount' in key.lower() or 'price' in key.lower() or 'cost' in key.lower():
            if isinstance(value, (int, float, Decimal)):
                assert value >= 0, f"Financial value {key} cannot be negative: {value}"
        
        if 'percentage' in key.lower() or 'rate' in key.lower():
            if isinstance(value, (int, float, Decimal)):
                assert 0 <= value <= 100, f"Percentage {key} must be 0-100: {value}"


def _validate_temporal_rules(data):
    """Valida reglas temporales en los datos."""
    for key, value in data.items():
        if 'date' in key.lower() and isinstance(value, (datetime, date)):
            if 'created' in key.lower():
                assert value <= datetime.now(), f"Created date {key} cannot be in future: {value}"
            elif 'start' in key.lower() and 'end' in key.lower().replace('start', ''):
                # Buscar fecha de fin correspondiente
                end_key = key.replace('start', 'end')
                if end_key in data:
                    end_date = data[end_key]
                    if isinstance(end_date, (datetime, date)):
                        assert end_date >= value, f"End date must be >= start date: {value} > {end_date}"


def _validate_logical_rules(data):
    """Valida reglas lógicas en los datos."""
    # Ejemplo: si hay funding_received, debe haber funding_amount
    if 'funding_received' in data and data['funding_received']:
        assert 'funding_amount' in data, "funding_amount required when funding_received is True"
        assert data['funding_amount'] > 0, "funding_amount must be positive when funding received"


# ============================================================================
# FIXTURES UNITARIAS ESPECIALIZADAS
# ============================================================================

@pytest.fixture(scope='function')
def unit_test_session():
    """Fixture de sesión de BD específica para tests unitarios."""
    engine = create_engine(
        'sqlite:///:memory:',
        poolclass=StaticPool,
        connect_args={'check_same_thread': False}
    )
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Crear esquema mínimo para testing
    from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime
    metadata = MetaData()
    
    # Tabla mínima para testing
    test_table = Table(
        'test_entities', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String(100)),
        Column('created_at', DateTime, default=datetime.utcnow)
    )
    
    metadata.create_all(engine)
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture(scope='function')
def business_calculator():
    """Fixture con calculadora de métricas de negocio."""
    return BusinessCalculations()


@pytest.fixture(scope='function')
def ecosystem_metrics_calculator():
    """Fixture con calculadora de métricas del ecosistema."""
    return EcosystemMetrics()


@pytest.fixture(scope='function')  
def mock_service_dependencies():
    """Fixture con mocks de dependencias de servicios."""
    mocks = {
        'email_service': Mock(),
        'sms_service': Mock(),
        'google_calendar': Mock(),
        'google_meet': Mock(),
        'file_storage': Mock(),
        'analytics_service': Mock(),
        'notification_service': Mock()
    }
    
    # Configurar comportamientos por defecto
    mocks['email_service'].send_email.return_value = True
    mocks['sms_service'].send_sms.return_value = True
    mocks['google_calendar'].create_event.return_value = {'id': 'cal_123'}
    mocks['google_meet'].create_meeting.return_value = {'meet_link': 'https://meet.google.com/test'}
    mocks['file_storage'].upload_file.return_value = {'url': 'https://storage.test.com/file'}
    mocks['analytics_service'].track_event.return_value = True
    mocks['notification_service'].send_notification.return_value = True
    
    yield mocks


# ============================================================================
# EXPORTS Y CONFIGURACIÓN FINAL
# ============================================================================

# Clases principales para import
__all__ = [
    # Clases base
    'UnitTestCase', 'ModelTestMixin', 'ServiceTestMixin', 'AlgorithmTestMixin',
    
    # Utilidades de cálculo
    'BusinessCalculations', 'EcosystemMetrics',
    
    # Decorators
    'isolate_database', 'mock_external_services', 'validate_business_rules',
    
    # Configuración
    'UNIT_TEST_CONFIG', 'BUSINESS_CONSTANTS', 'MINIMAL_TEST_DATA',
    'PERFORMANCE_THRESHOLDS',
    
    # Fixtures
    'unit_test_session', 'business_calculator', 'ecosystem_metrics_calculator',
    'mock_service_dependencies',
]

# Configuración de logging específica para unit tests
unit_logger = logging.getLogger('tests.unit')
unit_logger.setLevel(logging.DEBUG if os.getenv('DEBUG_UNIT_TESTS') else logging.INFO)

# Configurar Faker para tests unitarios determinísticos
fake.seed_instance(12345)  # Seed diferente para unit tests

logger.info("🧪 Framework de testing unitario inicializado")
logger.info(f"⚡ Performance thresholds: {PERFORMANCE_THRESHOLDS['max_execution_time_ms']}ms max")
logger.info(f"🔒 Aislamiento de BD: {UNIT_TEST_CONFIG['isolated_database']}")
logger.info(f"🎯 Reglas de negocio: {len(BUSINESS_CONSTANTS)} constantes configuradas")
logger.info("✅ tests/unit/__init__.py cargado correctamente")