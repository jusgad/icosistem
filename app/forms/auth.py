from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SelectField,
    SubmitField,
    EmailField
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    ValidationError,
    Regexp
)
from app.models.user import User
from app.utils.validators import password_strength

class LoginForm(FlaskForm):
    """Form for user login."""
    
    email = EmailField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required")
    ])
    
    remember_me = BooleanField('Remember Me')
    
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    """Form for user registration."""
    
    email = EmailField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters long"),
        password_strength()
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    
    first_name = StringField('First Name', validators=[
        DataRequired(message="First name is required"),
        Length(min=2, max=64, message="First name must be between 2 and 64 characters")
    ])
    
    last_name = StringField('Last Name', validators=[
        DataRequired(message="Last name is required"),
        Length(min=2, max=64, message="Last name must be between 2 and 64 characters")
    ])
    
    phone = StringField('Phone Number', validators=[
        DataRequired(message="Phone number is required"),
        Regexp(r'^\+?1?\d{9,15}$', message="Please enter a valid phone number")
    ])
    
    role = SelectField('Role', validators=[
        DataRequired(message="Please select a role")
    ], choices=[
        ('entrepreneur', 'Entrepreneur'),
        ('ally', 'Ally'),
        ('client', 'Client')
    ])
    
    terms_accepted = BooleanField('I accept the Terms and Conditions', validators=[
        DataRequired(message="You must accept the terms and conditions")
    ])
    
    submit = SubmitField('Register')
    
    def validate_email(self, field):
        """Validate that email is not already registered."""
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('This email address is already registered.')

class PasswordResetRequestForm(FlaskForm):
    """Form for requesting a password reset."""
    
    email = EmailField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address")
    ])
    
    submit = SubmitField('Request Password Reset')
    
    def validate_email(self, field):
        """Validate that email exists in the system."""
        user = User.query.filter_by(email=field.data.lower()).first()
        if not user:
            raise ValidationError('No account found with that email address.')

class PasswordResetForm(FlaskForm):
    """Form for resetting password with token."""
    
    password = PasswordField('New Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters long"),
        password_strength()
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password"),
        EqualTo('password', message="Passwords must match")
    ])
    
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    """Form for changing password while logged in."""
    
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message="Current password is required")
    ])
    
    new_password = PasswordField('New Password', validators=[
        DataRequired(message="New password is required"),
        Length(min=8, message="Password must be at least 8 characters long"),
        password_strength()
    ])
    
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message="Please confirm your new password"),
        EqualTo('new_password', message="Passwords must match")
    ])
    
    submit = SubmitField('Change Password')
    
    def __init__(self, user, *args, **kwargs):
        """Initialize form with user instance for password validation."""
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.user = user
    
    def validate_current_password(self, field):
        """Validate that current password is correct."""
        if not self.user.check_password(field.data):
            raise ValidationError('Current password is incorrect.')

class TwoFactorSetupForm(FlaskForm):
    """Form for setting up two-factor authentication."""
    
    verification_code = StringField('Verification Code', validators=[
        DataRequired(message="Verification code is required"),
        Length(min=6, max=6, message="Verification code must be 6 digits"),
        Regexp(r'^\d{6}$', message="Verification code must be 6 digits")
    ])
    
    submit = SubmitField('Verify')

class TwoFactorLoginForm(FlaskForm):
    """Form for two-factor authentication login step."""
    
    verification_code = StringField('Verification Code', validators=[
        DataRequired(message="Verification code is required"),
        Length(min=6, max=6, message="Verification code must be 6 digits"),
        Regexp(r'^\d{6}$', message="Verification code must be 6 digits")
    ])
    
    remember_device = BooleanField('Remember this device for 30 days')
    
    submit = SubmitField('Verify')