"""
Esquemas Pydantic modernos para operaciones de autenticación.
"""

from typing import Optional, Any
from datetime import datetime, timedelta
from pydantic import Field, EmailStr, validator
from enum import Enum

from .common import BaseSchema, StatusEnum
from .user import UserType, UserResponse


class TokenType(str, Enum):
    """Enumeración de tipos de token"""
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    TWO_FACTOR = "two_factor"


class AuthProvider(str, Enum):
    """Enumeración de proveedores de autenticación"""
    LOCAL = "local"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    GITHUB = "github"
    LINKEDIN = "linkedin"


class TwoFactorMethod(str, Enum):
    """Métodos de autenticación de dos factores"""
    SMS = "sms"
    EMAIL = "email"
    TOTP = "totp"  # Contraseña de un solo uso basada en tiempo (Google Authenticator, etc.)
    BACKUP_CODES = "backup_codes"


# ====================================
# ESQUEMAS DE INICIO/CIERRE DE SESIÓN
# ====================================

class LoginRequest(BaseSchema):
    """Esquema de solicitud de inicio de sesión"""
    
    email: EmailStr = Field(description="Dirección de email del usuario")
    password: str = Field(min_length=1, description="Contraseña del usuario")
    remember_me: bool = Field(default=False, description="Recordar sesión del usuario")
    device_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nombre del dispositivo para seguimiento"
    )
    two_factor_code: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=8,
        description="Two-factor authentication code"
    )


class LoginResponse(BaseSchema):
    """Login response schema"""
    
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    user: UserResponse = Field(description="Authenticated user information")
    permissions: list[str] = Field(description="User permissions")
    two_factor_required: bool = Field(
        default=False,
        description="Whether 2FA is required"
    )
    session_id: str = Field(description="Session identifier")


class LogoutRequest(BaseSchema):
    """Logout request schema"""
    
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token to invalidate"
    )
    logout_all_devices: bool = Field(
        default=False,
        description="Logout from all devices"
    )


# ====================================
# REGISTRATION SCHEMAS
# ====================================

class RegisterRequest(BaseSchema):
    """User registration request schema"""
    
    email: EmailStr = Field(description="User email address")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password"
    )
    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        description="Password confirmation"
    )
    first_name: str = Field(
        min_length=1,
        max_length=100,
        description="First name"
    )
    last_name: str = Field(
        min_length=1,
        max_length=100,
        description="Last name"
    )
    user_type: UserType = Field(description="Type of user account")
    phone: Optional[str] = Field(
        default=None,
        pattern=r'^\+?[1-9]\d{1,14}$',
        description="Phone number"
    )
    
    # Legal agreements
    terms_accepted: bool = Field(description="Terms and conditions acceptance")
    privacy_accepted: bool = Field(description="Privacy policy acceptance")
    marketing_consent: bool = Field(
        default=False,
        description="Marketing communications consent"
    )
    
    # Optional fields
    referral_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Referral code"
    )
    organization_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Organization name (for business accounts)"
    )
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        
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


class RegisterResponse(BaseSchema):
    """Registration response schema"""
    
    user: UserResponse = Field(description="Registered user information")
    access_token: Optional[str] = Field(
        default=None,
        description="JWT access token (if auto-login enabled)"
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="JWT refresh token (if auto-login enabled)"
    )
    email_verification_required: bool = Field(
        description="Whether email verification is required"
    )
    verification_email_sent: bool = Field(
        description="Whether verification email was sent"
    )
    message: str = Field(description="Registration success message")


# ====================================
# PASSWORD MANAGEMENT
# ====================================

class PasswordResetRequest(BaseSchema):
    """Password reset request schema"""
    
    email: EmailStr = Field(description="User email address")


class PasswordResetConfirm(BaseSchema):
    """Password reset confirmation schema"""
    
    token: str = Field(description="Password reset token")
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        description="Password confirmation"
    )
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordChangeRequest(BaseSchema):
    """Password change request (for authenticated users)"""
    
    current_password: str = Field(description="Current password")
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        description="Password confirmation"
    )
    logout_all_devices: bool = Field(
        default=True,
        description="Logout from all devices after password change"
    )
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


# ====================================
# EMAIL VERIFICATION
# ====================================

class EmailVerificationRequest(BaseSchema):
    """Email verification request schema"""
    
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email to verify (if not provided, uses current user email)"
    )


class EmailVerificationConfirm(BaseSchema):
    """Email verification confirmation schema"""
    
    token: str = Field(description="Email verification token")
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email being verified"
    )


# ====================================
# TWO-FACTOR AUTHENTICATION
# ====================================

class TwoFactorSetupRequest(BaseSchema):
    """Two-factor authentication setup request"""
    
    method: TwoFactorMethod = Field(description="2FA method to set up")
    phone_number: Optional[str] = Field(
        default=None,
        pattern=r'^\+?[1-9]\d{1,14}$',
        description="Phone number for SMS 2FA"
    )


class TwoFactorSetupResponse(BaseSchema):
    """Two-factor authentication setup response"""
    
    qr_code: Optional[str] = Field(
        default=None,
        description="Base64 encoded QR code for TOTP setup"
    )
    secret: Optional[str] = Field(
        default=None,
        description="Secret key for TOTP setup"
    )
    backup_codes: Optional[list[str]] = Field(
        default=None,
        description="Backup codes for recovery"
    )
    phone_verification_sent: bool = Field(
        default=False,
        description="Whether SMS verification was sent"
    )


class TwoFactorRequest(BaseSchema):
    """Two-factor authentication request"""
    
    code: str = Field(
        min_length=6,
        max_length=8,
        description="2FA verification code"
    )
    method: TwoFactorMethod = Field(description="2FA method used")
    remember_device: bool = Field(
        default=False,
        description="Remember this device for future logins"
    )


class TwoFactorResponse(BaseSchema):
    """Two-factor authentication response"""
    
    verified: bool = Field(description="Whether 2FA was successful")
    access_token: Optional[str] = Field(
        default=None,
        description="JWT access token (if verification successful)"
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description="JWT refresh token (if verification successful)"
    )
    device_trusted: bool = Field(
        default=False,
        description="Whether device was marked as trusted"
    )


class TwoFactorDisableRequest(BaseSchema):
    """Two-factor authentication disable request"""
    
    password: str = Field(description="Current password for verification")
    disable_all_methods: bool = Field(
        default=True,
        description="Disable all 2FA methods"
    )
    methods_to_disable: Optional[list[TwoFactorMethod]] = Field(
        default=None,
        description="Specific methods to disable"
    )


# ====================================
# TOKEN MANAGEMENT
# ====================================

class TokenRefreshRequest(BaseSchema):
    """Token refresh request schema"""
    
    refresh_token: str = Field(description="Refresh token")


class TokenRefreshResponse(BaseSchema):
    """Token refresh response schema"""
    
    access_token: str = Field(description="New JWT access token")
    refresh_token: str = Field(description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")


class TokenValidationRequest(BaseSchema):
    """Token validation request schema"""
    
    token: str = Field(description="Token to validate")
    token_type: TokenType = Field(description="Type of token")


class TokenValidationResponse(BaseSchema):
    """Token validation response schema"""
    
    valid: bool = Field(description="Whether token is valid")
    user_id: Optional[str] = Field(default=None, description="User ID if token is valid")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Token expiration timestamp"
    )
    permissions: Optional[list[str]] = Field(
        default=None,
        description="User permissions"
    )


# ====================================
# OAUTH AUTHENTICATION
# ====================================

class OAuthAuthorizationRequest(BaseSchema):
    """OAuth authorization request schema"""
    
    provider: AuthProvider = Field(description="OAuth provider")
    redirect_uri: str = Field(description="Redirect URI after authentication")
    state: Optional[str] = Field(
        default=None,
        description="State parameter for CSRF protection"
    )
    scopes: Optional[list[str]] = Field(
        default=None,
        description="Requested OAuth scopes"
    )


class OAuthCallbackRequest(BaseSchema):
    """OAuth callback request schema"""
    
    provider: AuthProvider = Field(description="OAuth provider")
    code: str = Field(description="Authorization code")
    state: Optional[str] = Field(default=None, description="State parameter")


class OAuthUserInfo(BaseSchema):
    """OAuth user information schema"""
    
    provider_id: str = Field(description="User ID from OAuth provider")
    email: EmailStr = Field(description="Email from OAuth provider")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    picture: Optional[str] = Field(default=None, description="Profile picture URL")
    provider_data: dict[str, Any] = Field(
        description="Additional data from OAuth provider"
    )


class OAuthLinkRequest(BaseSchema):
    """OAuth account linking request"""
    
    provider: AuthProvider = Field(description="OAuth provider to link")
    provider_user_id: str = Field(description="User ID from OAuth provider")
    access_token: str = Field(description="OAuth access token")


# ====================================
# SESSION MANAGEMENT
# ====================================

class SessionInfo(BaseSchema):
    """Session information schema"""
    
    session_id: str = Field(description="Session identifier")
    device_name: Optional[str] = Field(default=None, description="Device name")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    created_at: datetime = Field(description="Session creation time")
    last_activity: datetime = Field(description="Last activity time")
    is_current: bool = Field(description="Whether this is the current session")
    location: Optional[str] = Field(default=None, description="Approximate location")


class SessionListResponse(BaseSchema):
    """Active sessions list response"""
    
    sessions: list[SessionInfo] = Field(description="List of active sessions")
    total_sessions: int = Field(description="Total number of active sessions")


class SessionTerminateRequest(BaseSchema):
    """Session termination request"""
    
    session_id: Optional[str] = Field(
        default=None,
        description="Specific session to terminate (null for current)"
    )
    terminate_all: bool = Field(
        default=False,
        description="Terminate all sessions except current"
    )


# ====================================
# SECURITY EVENTS
# ====================================

class SecurityEventType(str, Enum):
    """Security event types"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    TWO_FACTOR_ENABLED = "two_factor_enabled"
    TWO_FACTOR_DISABLED = "two_factor_disabled"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ACCOUNT_LOCKED = "account_locked"
    OAUTH_LINKED = "oauth_linked"
    OAUTH_UNLINKED = "oauth_unlinked"


class SecurityEvent(BaseSchema):
    """Security event schema"""
    
    event_type: SecurityEventType = Field(description="Type of security event")
    timestamp: datetime = Field(description="Event timestamp")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    location: Optional[str] = Field(default=None, description="Approximate location")
    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional event details"
    )
    risk_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Risk score for the event"
    )


class SecurityEventListResponse(BaseSchema):
    """Security events list response"""
    
    events: list[SecurityEvent] = Field(description="List of security events")
    total_events: int = Field(description="Total number of events")
    high_risk_events: int = Field(description="Number of high-risk events")


# ====================================
# RATE LIMITING AND SECURITY
# ====================================

class LoginAttempt(BaseSchema):
    """Login attempt tracking schema"""
    
    email: EmailStr = Field(description="Email used in login attempt")
    success: bool = Field(description="Whether login was successful")
    timestamp: datetime = Field(description="Attempt timestamp")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")
    failure_reason: Optional[str] = Field(
        default=None,
        description="Reason for login failure"
    )


class AccountLockStatus(BaseSchema):
    """Account lock status schema"""
    
    is_locked: bool = Field(description="Whether account is locked")
    locked_until: Optional[datetime] = Field(
        default=None,
        description="Account locked until timestamp"
    )
    failed_attempts: int = Field(
        ge=0,
        description="Number of failed login attempts"
    )
    max_attempts: int = Field(
        ge=1,
        description="Maximum allowed attempts"
    )
    lockout_duration_minutes: int = Field(
        ge=1,
        description="Lockout duration in minutes"
    )


# ====================================
# API KEY MANAGEMENT
# ====================================

class ApiKeyCreateRequest(BaseSchema):
    """API key creation request"""
    
    name: str = Field(min_length=1, max_length=100, description="API key name")
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="API key description"
    )
    scopes: list[str] = Field(description="API key scopes/permissions")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="API key expiration date"
    )
    ip_whitelist: Optional[list[str]] = Field(
        default=None,
        description="IP addresses allowed to use this key"
    )


class ApiKeyResponse(BaseSchema):
    """API key response schema"""
    
    id: str = Field(description="API key ID")
    name: str = Field(description="API key name")
    description: Optional[str] = Field(default=None, description="API key description")
    key: Optional[str] = Field(
        default=None,
        description="API key value (only shown once during creation)"
    )
    scopes: list[str] = Field(description="API key scopes")
    created_at: datetime = Field(description="Creation timestamp")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Expiration timestamp"
    )
    last_used: Optional[datetime] = Field(
        default=None,
        description="Last usage timestamp"
    )
    is_active: bool = Field(description="Whether key is active")
    usage_count: int = Field(ge=0, description="Number of times key was used")