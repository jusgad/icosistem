# Import form classes from their respective modules
from .auth import (
    LoginForm,
    RegistrationForm,
    PasswordResetRequestForm,
    PasswordResetForm,
    ChangePasswordForm
)

from .admin import (
    UserCreateForm,
    UserEditForm,
    EntrepreneurApprovalForm,
    AllyAssignmentForm,
    GlobalSettingsForm
)

from .entrepreneur import (
    EntrepreneurProfileForm,
    CompanyInfoForm,
    DocumentUploadForm,
    TaskCreateForm,
    MeetingRequestForm
)

from .ally import (
    AllyProfileForm,
    HoursLogForm,
    EntrepreneurFeedbackForm,
    AvailabilityForm,
    MeetingScheduleForm
)

from .client import (
    ClientProfileForm,
    ImpactMetricsForm,
    ReportConfigForm
)

# Define __all__ to explicitly specify what gets imported with "from forms import *"
__all__ = [
    # Auth Forms
    'LoginForm',
    'RegistrationForm',
    'PasswordResetRequestForm',
    'PasswordResetForm',
    'ChangePasswordForm',
    
    # Admin Forms
    'UserCreateForm',
    'UserEditForm',
    'EntrepreneurApprovalForm',
    'AllyAssignmentForm',
    'GlobalSettingsForm',
    
    # Entrepreneur Forms
    'EntrepreneurProfileForm',
    'CompanyInfoForm',
    'DocumentUploadForm',
    'TaskCreateForm',
    'MeetingRequestForm',
    
    # Ally Forms
    'AllyProfileForm',
    'HoursLogForm',
    'EntrepreneurFeedbackForm',
    'AvailabilityForm',
    'MeetingScheduleForm',
    
    # Client Forms
    'ClientProfileForm',
    'ImpactMetricsForm',
    'ReportConfigForm'
]

# Version information
__version__ = '1.0.0'

# Module level doc-string
"""
Forms Package
============

This package contains all the forms used in the entrepreneurship platform.
Forms are organized by user type and functionality:

- auth: Authentication related forms
- admin: Administrative forms
- entrepreneur: Entrepreneur-specific forms
- ally: Ally-specific forms
- client: Client-specific forms

Usage:
------
    from app.forms import LoginForm, RegistrationForm
    
    # Create a login form instance
    form = LoginForm()
    
    # Validate form data
    if form.validate_on_submit():
        # Process form data
        pass
"""

# Optional: Add any package-level initialization code here
def init_forms(app):
    """
    Initialize forms package with the Flask application instance.
    This function can be used to set up any form-wide configurations.
    
    Args:
        app: Flask application instance
    """
    # Example: Set maximum upload size for file fields
    app.config.setdefault('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB max-limit
    
    # Example: Set default form configurations
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)  # 1 hour
    app.config.setdefault('WTF_CSRF_SSL_STRICT', True)

# Optional: Add any custom form validators that will be used across multiple forms
from wtforms.validators import ValidationError

def validate_phone_number(form, field):
    """
    Custom validator for phone number fields.
    Can be used in any form that requires phone number validation.
    
    Usage:
        phone = StringField('Phone', validators=[validate_phone_number])
    """
    if not field.data.replace('+', '').replace('-', '').replace(' ', '').isdigit():
        raise ValidationError('Invalid phone number format')

# Add commonly used form utilities
def flash_form_errors(form):
    """
    Utility function to flash all form errors.
    
    Args:
        form: The form instance containing errors
    """
    from flask import flash
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'error')