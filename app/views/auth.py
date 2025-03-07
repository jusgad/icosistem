from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    session,
    abort
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.urls import url_parse
from app.extensions import db
from app.models.user import User
from app.forms.auth import (
    LoginForm,
    RegistrationForm,
    PasswordResetRequestForm,
    PasswordResetForm,
    ChangePasswordForm,
    TwoFactorSetupForm,
    TwoFactorLoginForm
)
from app.utils.email import send_email
from app.utils.security import (
    generate_confirmation_token,
    confirm_token,
    get_reset_password_token,
    verify_reset_password_token,
    generate_2fa_secret,
    verify_2fa_code
)
from app.utils.decorators import anonymous_required
from app.utils.audit import log_auth_event
import pyqrcode
import logging
from datetime import datetime, timedelta

# Crear el blueprint para autenticación
auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@anonymous_required
def login():
    """Vista de inicio de sesión."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()
            
            if user is None or not user.check_password(form.password.data):
                flash('Email o contraseña incorrectos', 'error')
                log_auth_event('failed_login', email=form.email.data)
                return render_template('auth/login.html', form=form)

            if not user.is_active:
                flash('Tu cuenta está desactivada. Contacta al soporte.', 'error')
                log_auth_event('inactive_account_login_attempt', user=user)
                return render_template('auth/login.html', form=form)

            # Verificar si el usuario tiene 2FA activado
            if user.two_factor_enabled:
                session['two_factor_user_id'] = user.id
                return redirect(url_for('auth.two_factor_login'))

            # Login exitoso
            login_user(user, remember=form.remember_me.data)
            log_auth_event('successful_login', user=user)
            
            # Actualizar último login
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Redireccionar a la página solicitada o al dashboard
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = get_default_redirect(user)
                
            return redirect(next_page)

        except Exception as e:
            logger.error(f"Error en login: {str(e)}")
            flash('Error al procesar el inicio de sesión. Intenta de nuevo.', 'error')
            return render_template('auth/login.html', form=form)

    return render_template('auth/login.html', form=form)

@auth_bp.route('/two-factor', methods=['GET', 'POST'])
def two_factor_login():
    """Vista para verificación de dos factores."""
    if 'two_factor_user_id' not in session:
        return redirect(url_for('auth.login'))

    form = TwoFactorLoginForm()
    if form.validate_on_submit():
        user = User.query.get(session['two_factor_user_id'])
        if user and verify_2fa_code(user.two_factor_secret, form.verification_code.data):
            login_user(user)
            session.pop('two_factor_user_id', None)
            
            # Si el usuario eligió recordar el dispositivo
            if form.remember_device.data:
                token = user.generate_2fa_device_token()
                session['2fa_device_token'] = token
            
            log_auth_event('successful_2fa_login', user=user)
            return redirect(get_default_redirect(user))
        
        flash('Código de verificación inválido', 'error')
        log_auth_event('failed_2fa_attempt', user=user)

    return render_template('auth/two_factor_login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
@anonymous_required
def register():
    """Vista de registro de usuarios."""
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(
                email=form.email.data.lower(),
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role=form.role.data,
                phone=form.phone.data
            )
            user.set_password(form.password.data)
            
            # Generar token de confirmación
            token = generate_confirmation_token(user.email)
            user.confirmation_token = token
            
            db.session.add(user)
            db.session.commit()
            
            # Enviar email de confirmación
            send_confirmation_email(user)
            
            log_auth_event('user_registered', user=user)
            
            flash('Registro exitoso. Por favor revisa tu email para confirmar tu cuenta.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error en registro: {str(e)}")
            flash('Error al procesar el registro. Por favor intenta de nuevo.', 'error')

    return render_template('auth/register.html', form=form)

@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    """Confirmación de email."""
    try:
        email = confirm_token(token)
        if not email:
            flash('El enlace de confirmación es inválido o ha expirado.', 'error')
            return redirect(url_for('main.index'))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('main.index'))

        if user.confirmed:
            flash('Tu cuenta ya está confirmada.', 'info')
        else:
            user.confirmed = True
            user.confirmed_at = datetime.utcnow()
            db.session.commit()
            flash('¡Has confirmado tu cuenta! Ya puedes iniciar sesión.', 'success')
            log_auth_event('email_confirmed', user=user)

        return redirect(url_for('auth.login'))

    except Exception as e:
        logger.error(f"Error en confirmación de email: {str(e)}")
        flash('Error al confirmar el email.', 'error')
        return redirect(url_for('main.index'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    """Solicitud de restablecimiento de contraseña."""
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user:
                token = get_reset_password_token(user)
                send_password_reset_email(user, token)
                log_auth_event('password_reset_requested', user=user)
                
            flash('Se han enviado instrucciones a tu email para restablecer tu contraseña.', 'info')
            return redirect(url_for('auth.login'))

        except Exception as e:
            logger.error(f"Error en solicitud de reset: {str(e)}")
            flash('Error al procesar la solicitud. Intenta de nuevo.', 'error')

    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Restablecimiento de contraseña."""
    try:
        user_id = verify_reset_password_token(token)
        if not user_id:
            flash('El enlace de restablecimiento es inválido o ha expirado.', 'error')
            return redirect(url_for('main.index'))

        user = User.query.get(user_id)
        if not user:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('main.index'))

        form = PasswordResetForm()
        if form.validate_on_submit():
            user.set_password(form.password.data)
            db.session.commit()
            log_auth_event('password_reset_completed', user=user)
            flash('Tu contraseña ha sido actualizada.', 'success')
            return redirect(url_for('auth.login'))

        return render_template('auth/reset_password.html', form=form)

    except Exception as e:
        logger.error(f"Error en reset de contraseña: {str(e)}")
        flash('Error al restablecer la contraseña.', 'error')
        return redirect(url_for('main.index'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Cambio de contraseña para usuario autenticado."""
    form = ChangePasswordForm(current_user)
    if form.validate_on_submit():
        try:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            log_auth_event('password_changed', user=current_user)
            flash('Tu contraseña ha sido actualizada.', 'success')
            return redirect(url_for('main.index'))

        except Exception as e:
            logger.error(f"Error en cambio de contraseña: {str(e)}")
            flash('Error al cambiar la contraseña. Intenta de nuevo.', 'error')

    return render_template('auth/change_password.html', form=form)

@auth_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    """Configuración de autenticación de dos factores."""
    if current_user.two_factor_enabled:
        flash('La autenticación de dos factores ya está activada.', 'info')
        return redirect(url_for('main.index'))

    form = TwoFactorSetupForm()
    
    if request.method == 'GET':
        # Generar secreto 2FA
        secret = generate_2fa_secret()
        session['2fa_secret'] = secret
        
        # Generar QR code
        qr = pyqrcode.create(get_2fa_uri(current_user.email, secret))
        qr_base64 = qr.png_as_base64_str(scale=5)
        
        return render_template('auth/setup_2fa.html',
                             form=form,
                             qr_code=qr_base64,
                             secret=secret)

    if form.validate_on_submit():
        secret = session.pop('2fa_secret', None)
        if not secret:
            flash('Error en la configuración. Intenta de nuevo.', 'error')
            return redirect(url_for('auth.setup_2fa'))

        if verify_2fa_code(secret, form.verification_code.data):
            current_user.two_factor_secret = secret
            current_user.two_factor_enabled = True
            db.session.commit()
            log_auth_event('2fa_enabled', user=current_user)
            flash('Autenticación de dos factores activada exitosamente.', 'success')
            return redirect(url_for('main.index'))
        
        flash('Código de verificación inválido', 'error')
        return redirect(url_for('auth.setup_2fa'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Cierre de sesión."""
    log_auth_event('logout', user=current_user)
    logout_user()
    return redirect(url_for('main.index'))

# Funciones auxiliares

def get_default_redirect(user):
    """Determina la redirección por defecto según el rol del usuario."""
    role_redirects = {
        'admin': 'admin.dashboard',
        'entrepreneur': 'entrepreneur.dashboard',
        'ally': 'ally.dashboard',
        'client': 'client.dashboard'
    }
    return url_for(role_redirects.get(user.role, 'main.index'))

def send_confirmation_email(user):
    """Envía email de confirmación."""
    send_email(
        subject='Confirma tu cuenta',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/confirm_email.txt',
                                user=user, token=user.confirmation_token),
        html_body=render_template('email/confirm_email.html',
                                user=user, token=user.confirmation_token)
    )

def send_password_reset_email(user, token):
    """Envía email de restablecimiento de contraseña."""
    send_email(
        subject='Restablece tu contraseña',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/reset_password.txt',
                                user=user, token=token),
        html_body=render_template('email/reset_password.html',
                                user=user, token=token)
    )

def get_2fa_uri(email, secret):
    """Genera URI para código QR de 2FA."""
    return f'otpauth://totp/{current_app.config["APP_NAME"]}:{email}?secret={secret}&issuer={current_app.config["APP_NAME"]}'