"""
Modern authentication endpoints using Flask-RESTX.
"""

from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt, decode_token
)
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, timezone
import pyotp
import qrcode
from io import BytesIO
import base64

# Create auth namespace
auth_ns = Namespace(
    'auth',
    description='Authentication and authorization endpoints',
    path='/auth'
)

# Authentication models
login_request_model = auth_ns.model('LoginRequest', {
    'email': fields.String(required=True, description='User email address', example='user@example.com'),
    'password': fields.String(required=True, description='User password'),
    'remember_me': fields.Boolean(default=False, description='Remember user session'),
    'device_name': fields.String(description='Device name for tracking'),
    'two_factor_code': fields.String(description='Two-factor authentication code')
})

login_response_model = auth_ns.model('LoginResponse', {
    'success': fields.Boolean(description='Login success status'),
    'access_token': fields.String(description='JWT access token'),
    'refresh_token': fields.String(description='JWT refresh token'),
    'token_type': fields.String(default='bearer', description='Token type'),
    'expires_in': fields.Integer(description='Token expiration time in seconds'),
    'user': fields.Raw(description='User information'),
    'permissions': fields.List(fields.String, description='User permissions'),
    'two_factor_required': fields.Boolean(default=False, description='Whether 2FA is required'),
    'session_id': fields.String(description='Session identifier')
})

register_request_model = auth_ns.model('RegisterRequest', {
    'email': fields.String(required=True, description='User email address'),
    'password': fields.String(required=True, description='User password (min 8 characters)'),
    'confirm_password': fields.String(required=True, description='Password confirmation'),
    'first_name': fields.String(required=True, description='First name'),
    'last_name': fields.String(required=True, description='Last name'),
    'user_type': fields.String(required=True, description='User type', 
                             enum=['entrepreneur', 'ally', 'client', 'admin']),
    'phone': fields.String(description='Phone number'),
    'terms_accepted': fields.Boolean(required=True, description='Terms and conditions acceptance'),
    'privacy_accepted': fields.Boolean(required=True, description='Privacy policy acceptance'),
    'marketing_consent': fields.Boolean(default=False, description='Marketing communications consent'),
    'organization_name': fields.String(description='Organization name (for business accounts)')
})

register_response_model = auth_ns.model('RegisterResponse', {
    'success': fields.Boolean(description='Registration success status'),
    'message': fields.String(description='Registration message'),
    'user': fields.Raw(description='Registered user information'),
    'email_verification_required': fields.Boolean(description='Whether email verification is required'),
    'verification_email_sent': fields.Boolean(description='Whether verification email was sent')
})

token_refresh_request_model = auth_ns.model('TokenRefreshRequest', {
    'refresh_token': fields.String(required=True, description='Refresh token')
})

token_refresh_response_model = auth_ns.model('TokenRefreshResponse', {
    'access_token': fields.String(description='New JWT access token'),
    'refresh_token': fields.String(description='New JWT refresh token'),
    'token_type': fields.String(default='bearer', description='Token type'),
    'expires_in': fields.Integer(description='Token expiration time in seconds')
})

password_reset_request_model = auth_ns.model('PasswordResetRequest', {
    'email': fields.String(required=True, description='User email address')
})

password_reset_confirm_model = auth_ns.model('PasswordResetConfirm', {
    'token': fields.String(required=True, description='Password reset token'),
    'new_password': fields.String(required=True, description='New password'),
    'confirm_password': fields.String(required=True, description='Password confirmation')
})

two_factor_setup_response_model = auth_ns.model('TwoFactorSetupResponse', {
    'qr_code': fields.String(description='Base64 encoded QR code for TOTP setup'),
    'secret': fields.String(description='Secret key for TOTP setup'),
    'backup_codes': fields.List(fields.String, description='Backup codes for recovery')
})

two_factor_verify_model = auth_ns.model('TwoFactorVerify', {
    'code': fields.String(required=True, description='2FA verification code')
})

error_response_model = auth_ns.model('ErrorResponse', {
    'success': fields.Boolean(default=False, description='Operation success status'),
    'error_type': fields.String(description='Error type'),
    'message': fields.String(description='Error message'),
    'timestamp': fields.DateTime(description='Error timestamp')
})


@auth_ns.route('/login')
class LoginResource(Resource):
    """User login endpoint."""
    
    @auth_ns.expect(login_request_model)
    @auth_ns.marshal_with(login_response_model, code=200)
    @auth_ns.marshal_with(error_response_model, code=401)
    @auth_ns.doc(
        'user_login',
        description='Authenticate user and return JWT tokens',
        responses={
            200: 'Login successful',
            400: 'Invalid request data',
            401: 'Authentication failed',
            423: 'Account locked due to too many failed attempts'
        }
    )
    def post(self):
        """
        Authenticate user and return access tokens.
        
        Supports:
        - Email/password authentication
        - Two-factor authentication
        - Account lockout protection
        - Device tracking
        - Remember me functionality
        """
        try:
            data = request.get_json()
            
            # Validate required fields
            if not data.get('email') or not data.get('password'):
                return {
                    'success': False,
                    'error_type': 'validation_error',
                    'message': 'Email and password are required',
                    'timestamp': datetime.now(timezone.utc)
                }, 400
            
            # Import here to avoid circular imports
            from app.models.user import User
            from app.services.auth_service import AuthService
            
            auth_service = AuthService()
            
            # Check for account lockout
            if auth_service.is_account_locked(data['email']):
                return {
                    'success': False,
                    'error_type': 'account_locked',
                    'message': 'Account temporarily locked due to failed login attempts',
                    'timestamp': datetime.now(timezone.utc)
                }, 423
            
            # Find user
            user = User.query.filter_by(email=data['email'].lower()).first()
            
            if not user or not check_password_hash(user.password_hash, data['password']):
                auth_service.record_failed_login(data['email'], request.remote_addr)
                return {
                    'success': False,
                    'error_type': 'authentication_error',
                    'message': 'Invalid email or password',
                    'timestamp': datetime.now(timezone.utc)
                }, 401
            
            # Check if account is active
            if not user.is_active:
                return {
                    'success': False,
                    'error_type': 'account_inactive',
                    'message': 'Account is inactive. Please contact support.',
                    'timestamp': datetime.now(timezone.utc)
                }, 401
            
            # Check if email is verified
            if not user.email_verified:
                return {
                    'success': False,
                    'error_type': 'email_not_verified',
                    'message': 'Please verify your email address before logging in',
                    'timestamp': datetime.now(timezone.utc)
                }, 401
            
            # Check for two-factor authentication
            if user.two_factor_enabled:
                if not data.get('two_factor_code'):
                    return {
                        'success': False,
                        'error_type': 'two_factor_required',
                        'message': 'Two-factor authentication code required',
                        'two_factor_required': True,
                        'timestamp': datetime.now(timezone.utc)
                    }, 200
                
                # Verify 2FA code
                if not auth_service.verify_two_factor_code(user, data['two_factor_code']):
                    return {
                        'success': False,
                        'error_type': 'invalid_two_factor',
                        'message': 'Invalid two-factor authentication code',
                        'timestamp': datetime.now(timezone.utc)
                    }, 401
            
            # Create tokens
            access_token = create_access_token(
                identity=user.id,
                expires_delta=timedelta(hours=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 1))
            )
            refresh_token = create_refresh_token(
                identity=user.id,
                expires_delta=timedelta(days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 30))
            )
            
            # Login user for Flask-Login
            login_user(user, remember=data.get('remember_me', False))
            
            # Record successful login
            auth_service.record_successful_login(
                user, 
                request.remote_addr, 
                request.user_agent.string,
                data.get('device_name')
            )
            
            # Get user permissions
            permissions = auth_service.get_user_permissions(user)
            
            return {
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'bearer',
                'expires_in': current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 3600),
                'user': auth_service.serialize_user(user),
                'permissions': permissions,
                'two_factor_required': False,
                'session_id': auth_service.create_session_id(user)
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during login',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/register')
class RegisterResource(Resource):
    """User registration endpoint."""
    
    @auth_ns.expect(register_request_model)
    @auth_ns.marshal_with(register_response_model, code=201)
    @auth_ns.marshal_with(error_response_model, code=400)
    @auth_ns.doc(
        'user_register',
        description='Register a new user account',
        responses={
            201: 'Registration successful',
            400: 'Invalid request data',
            409: 'User already exists'
        }
    )
    def post(self):
        """
        Register a new user account.
        
        Features:
        - Input validation
        - Password strength validation
        - Email uniqueness check
        - Terms acceptance verification
        - Email verification setup
        """
        try:
            data = request.get_json()
            
            # Import here to avoid circular imports
            from app.services.auth_service import AuthService
            from app.schemas.auth import RegisterRequest
            
            auth_service = AuthService()
            
            # Validate request data using Pydantic
            try:
                register_data = RegisterRequest(**data)
            except ValidationError as e:
                return {
                    'success': False,
                    'error_type': 'validation_error',
                    'message': 'Invalid registration data',
                    'details': e.errors(),
                    'timestamp': datetime.now(timezone.utc)
                }, 400
            
            # Check if user already exists
            from app.models.user import User
            existing_user = User.query.filter_by(email=register_data.email.lower()).first()
            if existing_user:
                return {
                    'success': False,
                    'error_type': 'user_exists',
                    'message': 'User with this email already exists',
                    'timestamp': datetime.now(timezone.utc)
                }, 409
            
            # Create new user
            result = auth_service.register_user(register_data)
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Registration successful. Please check your email for verification.',
                    'user': result['user'],
                    'email_verification_required': True,
                    'verification_email_sent': result.get('email_sent', False)
                }, 201
            else:
                return {
                    'success': False,
                    'error_type': 'registration_failed',
                    'message': result.get('message', 'Registration failed'),
                    'timestamp': datetime.now(timezone.utc)
                }, 400
                
        except Exception as e:
            current_app.logger.error(f"Registration error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during registration',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/logout')
class LogoutResource(Resource):
    """User logout endpoint."""
    
    @jwt_required()
    @auth_ns.doc(
        'user_logout',
        description='Logout user and invalidate tokens',
        security='Bearer Auth',
        responses={
            200: 'Logout successful',
            401: 'Authentication required'
        }
    )
    def post(self):
        """
        Logout user and invalidate access token.
        
        Features:
        - Token blacklisting
        - Session cleanup
        - Security event logging
        """
        try:
            # Get current JWT token
            jti = get_jwt()['jti']
            
            # Add token to blacklist
            from app.services.auth_service import AuthService
            auth_service = AuthService()
            auth_service.blacklist_token(jti)
            
            # Logout from Flask-Login
            logout_user()
            
            # Log security event
            user_id = get_jwt_identity()
            auth_service.log_security_event(
                user_id=user_id,
                event_type='logout',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            
            return {
                'success': True,
                'message': 'Logged out successfully',
                'timestamp': datetime.now(timezone.utc)
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Logout error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during logout',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/refresh')
class TokenRefreshResource(Resource):
    """Token refresh endpoint."""
    
    @jwt_required(refresh=True)
    @auth_ns.marshal_with(token_refresh_response_model, code=200)
    @auth_ns.marshal_with(error_response_model, code=401)
    @auth_ns.doc(
        'refresh_token',
        description='Refresh access token using refresh token',
        security='Bearer Auth',
        responses={
            200: 'Token refreshed successfully',
            401: 'Invalid or expired refresh token'
        }
    )
    def post(self):
        """
        Refresh access token using refresh token.
        
        Features:
        - Token rotation (optional)
        - User validation
        - Security checks
        """
        try:
            current_user_id = get_jwt_identity()
            
            # Verify user still exists and is active
            from app.models.user import User
            user = User.query.get(current_user_id)
            
            if not user or not user.is_active:
                return {
                    'success': False,
                    'error_type': 'invalid_user',
                    'message': 'User account is inactive or does not exist',
                    'timestamp': datetime.now(timezone.utc)
                }, 401
            
            # Create new access token
            new_access_token = create_access_token(
                identity=current_user_id,
                expires_delta=timedelta(hours=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 1))
            )
            
            # Optionally create new refresh token
            new_refresh_token = None
            if current_app.config.get('JWT_REFRESH_TOKEN_ROTATION', False):
                new_refresh_token = create_refresh_token(
                    identity=current_user_id,
                    expires_delta=timedelta(days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 30))
                )
                
                # Blacklist old refresh token
                old_jti = get_jwt()['jti']
                from app.services.auth_service import AuthService
                auth_service = AuthService()
                auth_service.blacklist_token(old_jti)
            
            response_data = {
                'access_token': new_access_token,
                'token_type': 'bearer',
                'expires_in': current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 3600)
            }
            
            if new_refresh_token:
                response_data['refresh_token'] = new_refresh_token
            
            return response_data, 200
            
        except Exception as e:
            current_app.logger.error(f"Token refresh error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during token refresh',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/password-reset')
class PasswordResetResource(Resource):
    """Password reset request endpoint."""
    
    @auth_ns.expect(password_reset_request_model)
    @auth_ns.doc(
        'password_reset_request',
        description='Request password reset email',
        responses={
            200: 'Password reset email sent',
            400: 'Invalid request data',
            404: 'User not found'
        }
    )
    def post(self):
        """
        Request password reset email.
        
        Features:
        - Rate limiting
        - Security logging
        - Email delivery
        """
        try:
            data = request.get_json()
            email = data.get('email')
            
            if not email:
                return {
                    'success': False,
                    'error_type': 'validation_error',
                    'message': 'Email address is required',
                    'timestamp': datetime.now(timezone.utc)
                }, 400
            
            from app.services.auth_service import AuthService
            auth_service = AuthService()
            
            # Send password reset email (always return success for security)
            result = auth_service.send_password_reset_email(email)
            
            return {
                'success': True,
                'message': 'If an account with that email exists, a password reset email has been sent',
                'timestamp': datetime.now(timezone.utc)
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Password reset request error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred processing the password reset request',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/two-factor/setup')
class TwoFactorSetupResource(Resource):
    """Two-factor authentication setup endpoint."""
    
    @jwt_required()
    @auth_ns.marshal_with(two_factor_setup_response_model, code=200)
    @auth_ns.doc(
        'setup_two_factor',
        description='Setup two-factor authentication',
        security='Bearer Auth',
        responses={
            200: '2FA setup successful',
            401: 'Authentication required'
        }
    )
    def post(self):
        """
        Setup two-factor authentication for the current user.
        
        Returns QR code and backup codes for TOTP setup.
        """
        try:
            current_user_id = get_jwt_identity()
            
            from app.models.user import User
            from app.services.auth_service import AuthService
            
            user = User.query.get(current_user_id)
            auth_service = AuthService()
            
            # Generate TOTP secret
            secret = pyotp.random_base32()
            
            # Generate QR code
            totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name="Ecosistema Emprendimiento"
            )
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(totp_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Generate backup codes
            backup_codes = auth_service.generate_backup_codes(user)
            
            # Save secret temporarily (will be confirmed when user verifies)
            auth_service.save_temp_two_factor_secret(user, secret)
            
            return {
                'qr_code': qr_code_base64,
                'secret': secret,
                'backup_codes': backup_codes
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"2FA setup error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during 2FA setup',
                'timestamp': datetime.now(timezone.utc)
            }, 500


@auth_ns.route('/two-factor/verify')
class TwoFactorVerifyResource(Resource):
    """Two-factor authentication verification endpoint."""
    
    @jwt_required()
    @auth_ns.expect(two_factor_verify_model)
    @auth_ns.doc(
        'verify_two_factor',
        description='Verify and enable two-factor authentication',
        security='Bearer Auth',
        responses={
            200: '2FA verification successful',
            400: 'Invalid verification code',
            401: 'Authentication required'
        }
    )
    def post(self):
        """
        Verify two-factor authentication code and enable 2FA.
        """
        try:
            current_user_id = get_jwt_identity()
            data = request.get_json()
            code = data.get('code')
            
            if not code:
                return {
                    'success': False,
                    'error_type': 'validation_error',
                    'message': 'Verification code is required',
                    'timestamp': datetime.now(timezone.utc)
                }, 400
            
            from app.models.user import User
            from app.services.auth_service import AuthService
            
            user = User.query.get(current_user_id)
            auth_service = AuthService()
            
            # Verify the code with temporary secret
            if auth_service.verify_temp_two_factor_code(user, code):
                # Enable 2FA for the user
                auth_service.enable_two_factor_auth(user)
                
                return {
                    'success': True,
                    'message': 'Two-factor authentication enabled successfully',
                    'timestamp': datetime.now(timezone.utc)
                }, 200
            else:
                return {
                    'success': False,
                    'error_type': 'invalid_code',
                    'message': 'Invalid verification code',
                    'timestamp': datetime.now(timezone.utc)
                }, 400
                
        except Exception as e:
            current_app.logger.error(f"2FA verification error: {str(e)}")
            return {
                'success': False,
                'error_type': 'internal_error',
                'message': 'An error occurred during 2FA verification',
                'timestamp': datetime.now(timezone.utc)
            }, 500