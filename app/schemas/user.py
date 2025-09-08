"""
Modern Pydantic schemas for user-related operations.
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import Field, EmailStr, validator
from enum import Enum

from .common import (
    BaseSchema, StatusEnum, ContactInfo, Address, AuditInfo, 
    NotificationPreferences, QueryRequest
)


class UserType(str, Enum):
    """User type enumeration"""
    ADMIN = "admin"
    ENTREPRENEUR = "entrepreneur"
    ALLY = "ally"
    CLIENT = "client"


class UserStatus(str, Enum):
    """User status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class LanguageCode(str, Enum):
    """Supported language codes"""
    ES = "es"  # Spanish
    EN = "en"  # English
    PT = "pt"  # Portuguese


class TimezoneEnum(str, Enum):
    """Common timezone options"""
    UTC = "UTC"
    AMERICA_BOGOTA = "America/Bogota"
    AMERICA_MEXICO_CITY = "America/Mexico_City"
    AMERICA_SAO_PAULO = "America/Sao_Paulo"
    AMERICA_NEW_YORK = "America/New_York"
    EUROPE_MADRID = "Europe/Madrid"


# ====================================
# BASE USER SCHEMAS
# ====================================

class UserBase(BaseSchema):
    """Base user schema with common fields"""
    
    email: EmailStr = Field(description="User email address")
    first_name: str = Field(min_length=1, max_length=100, description="First name")
    last_name: str = Field(min_length=1, max_length=100, description="Last name")
    user_type: UserType = Field(description="Type of user")
    phone: Optional[str] = Field(
        default=None,
        pattern=r'^\+?[1-9]\d{1,14}$',
        description="Phone number in E.164 format"
    )
    preferred_language: LanguageCode = Field(
        default=LanguageCode.ES, 
        description="Preferred language"
    )
    timezone: TimezoneEnum = Field(
        default=TimezoneEnum.AMERICA_BOGOTA, 
        description="User timezone"
    )


class UserCreate(UserBase):
    """Schema for creating a new user"""
    
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password (will be hashed)"
    )
    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        description="Password confirmation"
    )
    terms_accepted: bool = Field(
        default=False,
        description="Terms and conditions acceptance"
    )
    privacy_accepted: bool = Field(
        default=False,
        description="Privacy policy acceptance"
    )
    marketing_consent: bool = Field(
        default=False,
        description="Marketing communications consent"
    )
    referral_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Referral code"
    )
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('terms_accepted')
    def terms_must_be_accepted(cls, v):
        if not v:
            raise ValueError('Terms and conditions must be accepted')
        return v
    
    @validator('privacy_accepted')
    def privacy_must_be_accepted(cls, v):
        if not v:
            raise ValueError('Privacy policy must be accepted')
        return v


class UserUpdate(BaseSchema):
    """Schema for updating user information"""
    
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="First name"
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Last name"
    )
    phone: Optional[str] = Field(
        default=None,
        pattern=r'^\+?[1-9]\d{1,14}$',
        description="Phone number"
    )
    preferred_language: Optional[LanguageCode] = Field(
        default=None,
        description="Preferred language"
    )
    timezone: Optional[TimezoneEnum] = Field(
        default=None,
        description="User timezone"
    )
    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="User biography"
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="Avatar image URL"
    )
    
    # Contact information
    contact_info: Optional[ContactInfo] = Field(
        default=None,
        description="Contact information"
    )
    
    # Address
    address: Optional[Address] = Field(
        default=None,
        description="User address"
    )
    
    # Notification preferences
    notification_preferences: Optional[NotificationPreferences] = Field(
        default=None,
        description="Notification preferences"
    )


class UserResponse(UserBase):
    """Schema for user response data"""
    
    id: str = Field(description="User unique identifier")
    username: Optional[str] = Field(default=None, description="Username")
    status: UserStatus = Field(description="User status")
    email_verified: bool = Field(description="Email verification status")
    phone_verified: bool = Field(description="Phone verification status")
    two_factor_enabled: bool = Field(description="2FA status")
    last_login: Optional[datetime] = Field(default=None, description="Last login timestamp")
    profile_completion: int = Field(
        ge=0, le=100, 
        description="Profile completion percentage"
    )
    avatar_url: Optional[str] = Field(default=None, description="Avatar image URL")
    
    # Contact and address info
    contact_info: Optional[ContactInfo] = Field(default=None, description="Contact information")
    address: Optional[Address] = Field(default=None, description="User address")
    
    # Preferences
    notification_preferences: Optional[NotificationPreferences] = Field(
        default=None,
        description="Notification preferences"
    )
    
    # Audit info
    audit_info: AuditInfo = Field(description="Audit information")
    
    # Relationships count (optional, for performance)
    relationships_count: Optional[dict[str, int]] = Field(
        default=None,
        description="Count of related entities"
    )


# ====================================
# EXTENDED USER SCHEMAS
# ====================================

class UserProfile(UserResponse):
    """Extended user profile with additional details"""
    
    bio: Optional[str] = Field(default=None, description="User biography")
    skills: Optional[list[str]] = Field(default=None, description="User skills")
    interests: Optional[list[str]] = Field(default=None, description="User interests")
    certifications: Optional[list[str]] = Field(default=None, description="Professional certifications")
    education: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Educational background"
    )
    experience: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Professional experience"
    )
    achievements: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Achievements and awards"
    )
    
    # Social media links
    social_media: Optional[dict[str, str]] = Field(
        default=None,
        description="Social media profiles"
    )
    
    # Privacy settings
    privacy_settings: Optional[dict[str, Any]] = Field(
        default=None,
        description="Privacy settings"
    )


class UserPreferences(BaseSchema):
    """User preferences schema"""
    
    # Language and localization
    preferred_language: LanguageCode = Field(description="Preferred language")
    timezone: TimezoneEnum = Field(description="User timezone")
    date_format: Optional[str] = Field(default="YYYY-MM-DD", description="Date format preference")
    time_format: Optional[str] = Field(default="24h", description="Time format preference")
    
    # Dashboard preferences
    dashboard_layout: Optional[str] = Field(default="default", description="Dashboard layout")
    default_page: Optional[str] = Field(default="dashboard", description="Default landing page")
    
    # Theme preferences
    theme: Optional[str] = Field(default="light", description="UI theme preference")
    color_scheme: Optional[str] = Field(default="default", description="Color scheme")
    
    # Communication preferences
    notification_preferences: NotificationPreferences = Field(
        description="Notification preferences"
    )
    
    # Privacy preferences
    profile_visibility: Optional[str] = Field(
        default="public",
        description="Profile visibility setting"
    )
    show_email: bool = Field(default=False, description="Show email in profile")
    show_phone: bool = Field(default=False, description="Show phone in profile")
    allow_messaging: bool = Field(default=True, description="Allow direct messages")


class UserActivity(BaseSchema):
    """User activity schema"""
    
    activity_type: str = Field(description="Type of activity")
    description: str = Field(description="Activity description")
    timestamp: datetime = Field(description="Activity timestamp")
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional activity metadata"
    )
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")


class UserStats(BaseSchema):
    """User statistics schema"""
    
    total_projects: int = Field(ge=0, description="Total number of projects")
    active_projects: int = Field(ge=0, description="Number of active projects")
    completed_projects: int = Field(ge=0, description="Number of completed projects")
    total_meetings: int = Field(ge=0, description="Total number of meetings")
    total_messages: int = Field(ge=0, description="Total number of messages")
    profile_views: int = Field(ge=0, description="Profile view count")
    connections: int = Field(ge=0, description="Number of connections")
    
    # Time-based stats
    last_activity: Optional[datetime] = Field(default=None, description="Last activity timestamp")
    member_since: datetime = Field(description="Member since date")
    days_active: int = Field(ge=0, description="Number of active days")
    
    # Engagement metrics
    engagement_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="User engagement score"
    )
    response_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Message response rate"
    )


# ====================================
# SEARCH AND FILTERING
# ====================================

class UserSearchFilters(BaseSchema):
    """User search filters"""
    
    user_type: Optional[list[UserType]] = Field(default=None, description="User types to filter")
    status: Optional[list[UserStatus]] = Field(default=None, description="User statuses to filter")
    location: Optional[str] = Field(default=None, description="Location filter")
    skills: Optional[list[str]] = Field(default=None, description="Skills filter")
    interests: Optional[list[str]] = Field(default=None, description="Interests filter")
    verified_only: Optional[bool] = Field(default=None, description="Show only verified users")
    has_projects: Optional[bool] = Field(default=None, description="Has active projects")
    
    # Date filters
    created_after: Optional[datetime] = Field(default=None, description="Created after date")
    created_before: Optional[datetime] = Field(default=None, description="Created before date")
    last_active_after: Optional[datetime] = Field(default=None, description="Last active after")
    
    # Engagement filters
    min_profile_completion: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum profile completion percentage"
    )
    min_engagement_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum engagement score"
    )


class UserSearch(QueryRequest):
    """User search request with specific filters"""
    
    filters: Optional[UserSearchFilters] = Field(
        default=None,
        description="User-specific search filters"
    )


# ====================================
# BULK OPERATIONS
# ====================================

class BulkUserOperation(BaseSchema):
    """Bulk user operation schema"""
    
    operation: str = Field(description="Operation to perform (activate, deactivate, delete, etc.)")
    user_ids: list[str] = Field(min_length=1, description="List of user IDs")
    parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Operation parameters"
    )
    reason: Optional[str] = Field(default=None, description="Reason for bulk operation")


class UserImport(BaseSchema):
    """User import schema"""
    
    users: list[UserCreate] = Field(min_length=1, description="List of users to import")
    import_options: Optional[dict[str, Any]] = Field(
        default=None,
        description="Import options"
    )
    notify_users: bool = Field(default=True, description="Send welcome emails")
    auto_activate: bool = Field(default=False, description="Auto-activate imported users")


# ====================================
# ADMIN OPERATIONS
# ====================================

class UserStatusChange(BaseSchema):
    """User status change schema"""
    
    status: UserStatus = Field(description="New user status")
    reason: Optional[str] = Field(default=None, description="Reason for status change")
    notes: Optional[str] = Field(default=None, description="Administrative notes")
    notify_user: bool = Field(default=True, description="Notify user of status change")
    effective_date: Optional[datetime] = Field(
        default=None,
        description="Effective date of status change"
    )


class UserRoleAssignment(BaseSchema):
    """User role assignment schema"""
    
    user_type: UserType = Field(description="User type/role to assign")
    organization_id: Optional[str] = Field(
        default=None,
        description="Organization ID for role scope"
    )
    permissions: Optional[list[str]] = Field(
        default=None,
        description="Additional permissions"
    )
    expiry_date: Optional[datetime] = Field(
        default=None,
        description="Role expiry date"
    )
    notes: Optional[str] = Field(default=None, description="Role assignment notes")


class UserSuspension(BaseSchema):
    """User suspension schema"""
    
    reason: str = Field(description="Suspension reason")
    duration_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Suspension duration in days (null for indefinite)"
    )
    notes: Optional[str] = Field(default=None, description="Additional notes")
    notify_user: bool = Field(default=True, description="Notify user of suspension")
    restrict_login: bool = Field(default=True, description="Restrict login access")
    restrict_api: bool = Field(default=True, description="Restrict API access")


# ====================================
# VALIDATION HELPERS
# ====================================

def validate_user_type_transition(current_type: UserType, new_type: UserType) -> bool:
    """Validate if user type transition is allowed"""
    # Define allowed transitions
    allowed_transitions = {
        UserType.ENTREPRENEUR: [UserType.ALLY, UserType.CLIENT],
        UserType.ALLY: [UserType.ENTREPRENEUR, UserType.CLIENT],
        UserType.CLIENT: [UserType.ENTREPRENEUR, UserType.ALLY],
        UserType.ADMIN: [UserType.ENTREPRENEUR, UserType.ALLY, UserType.CLIENT]
    }
    
    return new_type in allowed_transitions.get(current_type, [])