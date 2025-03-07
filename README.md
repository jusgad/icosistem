# Emprendimiento App

Plataforma web para la gestión de emprendedores, aliados y clientes en un ecosistema de emprendimiento. Esta aplicación facilita la conexión entre emprendedores y mentores (aliados), permitiendo el seguimiento de actividades, comunicación en tiempo real, y medición de impacto.

## Características Principales

- **Sistema multiusuario** con roles específicos:
  - Administradores: Gestión global de la plataforma
  - Emprendedores: Acceso a recursos y mentoría
  - Aliados: Acompañamiento a emprendedores
  - Clientes: Visualización de datos e impacto

- **Funcionalidades por rol**:
  - **Administrador**: Panel de control, gestión de usuarios, asignación de aliados, configuración global
  - **Emprendedor**: Perfil, mensajería, calendario, documentos, tareas, escritorio de trabajo
  - **Aliado**: Panel de acompañamiento, registro de horas, mensajería, calendario
  - **Cliente**: Dashboard de impacto, directorio de emprendimientos, reportes

- **Herramientas Integradas**:
  - Comunicación en tiempo real (Socket.IO)
  - Gestión de calendario y reuniones
  - Almacenamiento y gestión de documentos
  - Tablero de indicadores y estadísticas

## Tecnologías Utilizadas

- **Backend**: Flask (Python)
- **Base de Datos**: SQLAlchemy (ORM)
- **Frontend**: Bootstrap, jQuery, Chart.js
- **Comunicación en tiempo real**: Socket.IO
- **Integraciones**: Google Calendar, Google Meet, Email

## Requisitos

- Python 3.9+
- Base de datos compatible con SQLAlchemy (PostgreSQL, MySQL, SQLite)
- Node.js (opcional, para desarrollo frontend)

## Instalación

1. Clona el repositorio:
```bash
git clone https://github.com/tu-usuario/emprendimiento-app.git
cd emprendimiento-app
```

2. Crea y activa un entorno virtual:
```bash
python -m venv venv

# En Windows
venv\Scripts\activate

# En macOS/Linux
source venv/bin/activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt

# Para dependencias de desarrollo (opcional)
pip install -r requirements-dev.txt
```

4. Configura las variables de entorno:
```bash
cp .env.example .env
# Edita el archivo .env con tu configuración
```

5. Inicializa la base de datos:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. Ejecuta la aplicación:
```bash
python run.py
```

## Configuración

La aplicación utiliza variables de entorno para su configuración. Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```
# Configuración básica
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=tu_clave_secreta_aquí

# Base de datos
DATABASE_URL=postgresql://usuario:contraseña@localhost/nombre_db

# Email
MAIL_SERVER=smtp.ejemplo.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=tu_email@ejemplo.com
MAIL_PASSWORD=tu_contraseña

# Google OAuth (opcional)
GOOGLE_CLIENT_ID=tu_client_id
GOOGLE_CLIENT_SECRET=tu_client_secret
```

## Estructura del Proyecto

```
proyecto-postpenados/
├── app/                              # Código principal de la aplicación
│   ├── models/                       # Modelos de datos
│   ├── views/                        # Vistas/Controladores
│   ├── forms/                        # Formularios
│   ├── templates/                    # Plantillas HTML
│   ├── static/                       # Archivos estáticos (CSS, JS, imágenes)
│   ├── services/                     # Servicios externos (OAuth, Email, etc.)
│   ├── utils/                        # Utilidades
│   └── sockets/                      # Configuración de WebSockets
├── migrations/                       # Migraciones de base de datos
├── tests/                            # Pruebas
├── instance/                         # Configuración de instancia
├── requirements.txt                  # Dependencias de producción
├── requirements-dev.txt              # Dependencias de desarrollo
└── run.py                            # Script para ejecutar la aplicación
```

## Uso

### Administrador

1. Accede a `/admin/dashboard` para visualizar estadísticas generales
2. Gestiona usuarios en `/admin/users`
3. Asigna aliados a emprendedores en `/admin/assign_ally`

### Emprendedor

1. Completa tu perfil en `/entrepreneur/profile`
2. Revisa tu calendario en `/entrepreneur/calendar`
3. Comunícate con tu aliado en `/entrepreneur/messages`

### Aliado

1. Visualiza tus emprendedores asignados en `/ally/entrepreneurs`
2. Registra horas de mentoría en `/ally/hours`
3. Programa reuniones en `/ally/calendar`

### Cliente

1. Visualiza métricas de impacto en `/client/impact_dashboard`
2. Explora el directorio de emprendimientos en `/client/entrepreneurs`

## Desarrollo

Para contribuir al proyecto:

1. Crea un entorno de desarrollo:
```bash
pip install -r requirements-dev.txt
```

2. Ejecuta las pruebas:
```bash
pytest
```

3. Verifica el estilo de código:
```bash
flake8
black .
```

## Despliegue con Docker

1. Construye la imagen:
```bash
docker build -t proyecto-postpenados .
```

2. Ejecuta el contenedor:
```bash
docker run -p 5000:5000 proyecto-postpenados
```

O usa Docker Compose:
```bash
docker-compose up
```

## Licencia

[MIT](LICENSE)

## Contacto

Para preguntas o soporte, contacta a [jusga.adarve@gmail.com]
