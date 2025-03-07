"""
Servicio para manejar la autenticación OAuth con proveedores externos.
Este servicio facilita la autenticación con Google, Facebook, etc.
"""
from flask import current_app, url_for, redirect, session, request
import requests
from urllib.parse import urlencode
import json
import base64
import hmac
import hashlib
import time
from ..extensions import db
from ..models.user import User

class OAuth:
    """Clase para manejar autenticación OAuth con diferentes proveedores."""
    
    def __init__(self, app=None):
        """Inicializa el servicio OAuth."""
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Configura el servicio con la aplicación Flask."""
        self.app = app
        
        # Registrar las rutas de callback para los diferentes proveedores
        app.add_url_rule('/auth/google/callback', 
                         'google_oauth_callback', 
                         self.google_oauth_callback)
        app.add_url_rule('/auth/facebook/callback', 
                         'facebook_oauth_callback', 
                         self.facebook_oauth_callback)
    
    def get_google_auth_url(self, next_url=None):
        """
        Genera la URL para autenticación con Google.
        
        Args:
            next_url: URL a redireccionar después de la autenticación
            
        Returns:
            str: URL para iniciar flujo de autenticación de Google
        """
        if next_url:
            session['oauth_next_url'] = next_url
            
        params = {
            'client_id': current_app.config['GOOGLE_CLIENT_ID'],
            'redirect_uri': url_for('google_oauth_callback', _external=True),
            'scope': 'openid email profile',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    
    def google_oauth_callback(self):
        """
        Maneja el callback de Google OAuth.
        
        Returns:
            Response: Redirección a la URL adecuada tras autenticación
        """
        if 'error' in request.args:
            # Manejo de errores en la autenticación
            return redirect(url_for('auth.login', error="google_auth_failed"))
        
        if 'code' not in request.args:
            return redirect(url_for('auth.login'))
        
        # Intercambiar el código de autorización por tokens
        code = request.args.get('code')
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': current_app.config['GOOGLE_CLIENT_ID'],
            'client_secret': current_app.config['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': url_for('google_oauth_callback', _external=True),
            'grant_type': 'authorization_code'
        }
        
        token_response = requests.post(token_url, data=token_data)
        
        if token_response.status_code != 200:
            current_app.logger.error(f"Error al obtener token de Google: {token_response.text}")
            return redirect(url_for('auth.login', error="google_token_failed"))
        
        tokens = token_response.json()
        
        # Obtener información del usuario
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )
        
        if user_info_response.status_code != 200:
            current_app.logger.error(f"Error al obtener datos de usuario: {user_info_response.text}")
            return redirect(url_for('auth.login', error="google_userinfo_failed"))
        
        user_info = user_info_response.json()
        
        # Buscar o crear usuario
        user = User.query.filter_by(email=user_info['email']).first()
        
        if not user:
            # Crear nuevo usuario
            user = User(
                email=user_info['email'],
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                profile_picture=user_info.get('picture', ''),
                is_active=True,
                auth_provider='google',
                auth_provider_id=user_info['sub']
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Actualizar datos del usuario existente
            user.auth_provider = 'google'
            user.auth_provider_id = user_info['sub']
            user.profile_picture = user_info.get('picture', user.profile_picture)
            db.session.commit()
        
        # Iniciar sesión del usuario
        from flask_login import login_user
        login_user(user)
        
        # Redireccionar a la página adecuada
        next_url = session.pop('oauth_next_url', None)
        if next_url:
            return redirect(next_url)
        
        # Redireccionar según el rol del usuario
        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'entrepreneur':
            return redirect(url_for('entrepreneur.dashboard'))
        elif user.role == 'ally':
            return redirect(url_for('ally.dashboard'))
        elif user.role == 'client':
            return redirect(url_for('client.dashboard'))
        else:
            return redirect(url_for('main.index'))
    
    def get_facebook_auth_url(self, next_url=None):
        """
        Genera la URL para autenticación con Facebook.
        
        Args:
            next_url: URL a redireccionar después de la autenticación
            
        Returns:
            str: URL para iniciar flujo de autenticación de Facebook
        """
        if next_url:
            session['oauth_next_url'] = next_url
            
        params = {
            'client_id': current_app.config['FACEBOOK_APP_ID'],
            'redirect_uri': url_for('facebook_oauth_callback', _external=True),
            'scope': 'email,public_profile',
            'response_type': 'code',
        }
        
        return f"https://www.facebook.com/v14.0/dialog/oauth?{urlencode(params)}"
    
    def facebook_oauth_callback(self):
        """
        Maneja el callback de Facebook OAuth.
        
        Returns:
            Response: Redirección a la URL adecuada tras autenticación
        """
        if 'error' in request.args:
            return redirect(url_for('auth.login', error="facebook_auth_failed"))
        
        if 'code' not in request.args:
            return redirect(url_for('auth.login'))
        
        # Intercambiar el código por token de acceso
        code = request.args.get('code')
        token_url = 'https://graph.facebook.com/v14.0/oauth/access_token'
        token_params = {
            'client_id': current_app.config['FACEBOOK_APP_ID'],
            'redirect_uri': url_for('facebook_oauth_callback', _external=True),
            'client_secret': current_app.config['FACEBOOK_APP_SECRET'],
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params)
        
        if token_response.status_code != 200:
            current_app.logger.error(f"Error al obtener token de Facebook: {token_response.text}")
            return redirect(url_for('auth.login', error="facebook_token_failed"))
        
        access_token = token_response.json().get('access_token')
        
        # Obtener datos del usuario
        user_info_url = 'https://graph.facebook.com/me'
        user_info_params = {
            'fields': 'id,email,first_name,last_name,picture',
            'access_token': access_token
        }
        
        user_info_response = requests.get(user_info_url, params=user_info_params)
        
        if user_info_response.status_code != 200:
            current_app.logger.error(f"Error al obtener datos de usuario: {user_info_response.text}")
            return redirect(url_for('auth.login', error="facebook_userinfo_failed"))
        
        user_info = user_info_response.json()
        
        # Buscar o crear usuario
        user = User.query.filter_by(email=user_info.get('email')).first()
        
        if not user and 'email' in user_info:
            # Crear nuevo usuario
            user = User(
                email=user_info['email'],
                first_name=user_info.get('first_name', ''),
                last_name=user_info.get('last_name', ''),
                profile_picture=user_info.get('picture', {}).get('data', {}).get('url', ''),
                is_active=True,
                auth_provider='facebook',
                auth_provider_id=user_info['id']
            )
            db.session.add(user)
            db.session.commit()
        elif user:
            # Actualizar datos del usuario existente
            user.auth_provider = 'facebook'
            user.auth_provider_id = user_info['id']
            if 'picture' in user_info and 'data' in user_info['picture']:
                user.profile_picture = user_info['picture']['data'].get('url', user.profile_picture)
            db.session.commit()
        else:
            # No se pudo obtener correo del usuario
            return redirect(url_for('auth.login', error="facebook_email_required"))
        
        # Iniciar sesión del usuario
        from flask_login import login_user
        login_user(user)
        
        # Redireccionar a la página adecuada
        next_url = session.pop('oauth_next_url', None)
        if next_url:
            return redirect(next_url)
        
        # Redireccionar según el rol del usuario
        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'entrepreneur':
            return redirect(url_for('entrepreneur.dashboard'))
        elif user.role == 'ally':
            return redirect(url_for('ally.dashboard'))
        elif user.role == 'client':
            return redirect(url_for('client.dashboard'))
        else:
            return redirect(url_for('main.index'))
    
    def revoke_token(self, provider, token):
        """
        Revoca un token OAuth.
        
        Args:
            provider: Proveedor del token (google, facebook)
            token: Token a revocar
            
        Returns:
            bool: True si se revocó exitosamente, False en caso contrario
        """
        if provider == 'google':
            revoke_url = f'https://oauth2.googleapis.com/revoke?token={token}'
            response = requests.post(revoke_url)
            return response.status_code == 200
        elif provider == 'facebook':
            app_id = current_app.config['FACEBOOK_APP_ID']
            app_secret = current_app.config['FACEBOOK_APP_SECRET']
            revoke_url = f'https://graph.facebook.com/v14.0/me/permissions?access_token={token}'
            response = requests.delete(revoke_url)
            return response.status_code == 200
        
        return False

# Crear una instancia del servicio OAuth
oauth_service = OAuth()