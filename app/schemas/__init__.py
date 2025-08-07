"""
Modern Pydantic schemas for API validation and serialization.
This module provides modern, type-safe schemas for the entrepreneurship ecosystem.
"""

from .auth import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    TokenRefreshRequest, TokenRefreshResponse, PasswordResetRequest,
    EmailVerificationRequest, TwoFactorRequest, TwoFactorResponse
)

from .user import (
    UserBase, UserCreate, UserUpdate, UserResponse, UserProfile,
    UserPreferences, UserActivity, UserSearch
)

from .entrepreneur import (
    EntrepreneurBase, EntrepreneurCreate, EntrepreneurUpdate, 
    EntrepreneurResponse, EntrepreneurProfile, EntrepreneurStats
)

from .ally import (
    AllyBase, AllyCreate, AllyUpdate, AllyResponse,
    AllyProfile, AllyCapabilities, AllyStats
)

from .client import (
    ClientBase, ClientCreate, ClientUpdate, ClientResponse,
    ClientProfile, ClientRequirements
)

from .project import (
    ProjectBase, ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectDetails, ProjectMetrics, ProjectMilestone
)

from .meeting import (
    MeetingBase, MeetingCreate, MeetingUpdate, MeetingResponse,
    MeetingSchedule, MeetingFeedback, MeetingStats
)

from .analytics import (
    AnalyticsRequest, AnalyticsResponse, MetricsData,
    PerformanceIndicator, DashboardData
)

from .common import (
    BaseResponse, ErrorResponse, PaginationMeta, 
    PaginatedResponse, SuccessResponse, ValidationError
)

__all__ = [
    # Auth schemas
    'LoginRequest', 'LoginResponse', 'RegisterRequest', 'RegisterResponse',
    'TokenRefreshRequest', 'TokenRefreshResponse', 'PasswordResetRequest',
    'EmailVerificationRequest', 'TwoFactorRequest', 'TwoFactorResponse',
    
    # User schemas
    'UserBase', 'UserCreate', 'UserUpdate', 'UserResponse', 'UserProfile',
    'UserPreferences', 'UserActivity', 'UserSearch',
    
    # Entrepreneur schemas
    'EntrepreneurBase', 'EntrepreneurCreate', 'EntrepreneurUpdate',
    'EntrepreneurResponse', 'EntrepreneurProfile', 'EntrepreneurStats',
    
    # Ally schemas
    'AllyBase', 'AllyCreate', 'AllyUpdate', 'AllyResponse',
    'AllyProfile', 'AllyCapabilities', 'AllyStats',
    
    # Client schemas
    'ClientBase', 'ClientCreate', 'ClientUpdate', 'ClientResponse',
    'ClientProfile', 'ClientRequirements',
    
    # Project schemas
    'ProjectBase', 'ProjectCreate', 'ProjectUpdate', 'ProjectResponse',
    'ProjectDetails', 'ProjectMetrics', 'ProjectMilestone',
    
    # Meeting schemas
    'MeetingBase', 'MeetingCreate', 'MeetingUpdate', 'MeetingResponse',
    'MeetingSchedule', 'MeetingFeedback', 'MeetingStats',
    
    # Analytics schemas
    'AnalyticsRequest', 'AnalyticsResponse', 'MetricsData',
    'PerformanceIndicator', 'DashboardData',
    
    # Common schemas
    'BaseResponse', 'ErrorResponse', 'PaginationMeta',
    'PaginatedResponse', 'SuccessResponse', 'ValidationError'
]