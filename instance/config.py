# instance/config.py
# Este archivo contiene configuraciones sensibles y específicas de la instancia
# NO debe incluirse en el control de versiones (Git)

# Configuración de seguridad
SECRET_KEY = 'clave-secreta-muy-segura-generada-aleatoriamente'

# Configuración de base de datos
SQLALCHEMY_DATABASE_URI = 'postgresql://usuario:contraseña@localhost/emprendimiento_db'

# Configuración de correo electrónico
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'tu_correo@gmail.com'
MAIL_PASSWORD = 'tu_contraseña_o_token_de_app'
MAIL_DEFAULT_SENDER = 'tu_correo@gmail.com'

# Credenciales de Google (para Calendar, Meet, etc.)
GOOGLE_CLIENT_ID = 'tu-client-id.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = 'tu-client-secret'

# Configuración de almacenamiento (S3, Google Cloud Storage, etc.)
STORAGE_BUCKET = 'nombre-del-bucket'
STORAGE_ACCESS_KEY = 'clave-de-acceso'
STORAGE_SECRET_KEY = 'clave-secreta'

# Otras configuraciones específicas del entorno
DEBUG = False
TESTING = False