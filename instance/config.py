"""
Configuración específica de la instancia.
Este archivo no debe incluirse en el control de versiones.
"""
import os

# Configuración de la base de datos PostgreSQL
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'postgresql://postpenados_user:secure_password@localhost:5432/postpenados_db'

# Asegúrate de que esta ruta exista y tenga permisos de escritura
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app/static/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configuración de correo electrónico (ejemplo)
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'tu_correo@gmail.com'
MAIL_PASSWORD = 'tu_contraseña_segura'
MAIL_DEFAULT_SENDER = 'no-reply@postpenados.org'

# Clave secreta para la aplicación
SECRET_KEY = 'clave_super_secreta_para_produccion'
SECURITY_PASSWORD_SALT = 'salt_seguro_para_produccion'

# Configuración de la sesión
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = True
SESSION_USE_SIGNER = True