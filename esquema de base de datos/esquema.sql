-- Crear la base de datos
CREATE DATABASE proyecto_postpenados;

-- Conectar a la base de datos
\c proyecto_postpenados;

-- Crear extensión para UUID si es necesario
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Crear tablas

-- Tabla de usuarios
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    rol VARCHAR(50) NOT NULL CHECK (rol IN ('admin', 'coordinador', 'asistente', 'empresa')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_acceso TIMESTAMP,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de empresas colaboradoras
CREATE TABLE empresas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    nif VARCHAR(20) UNIQUE NOT NULL,
    direccion TEXT NOT NULL,
    codigo_postal VARCHAR(10) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    persona_contacto VARCHAR(200) NOT NULL,
    sector VARCHAR(100) NOT NULL,
    tamaño VARCHAR(50) CHECK (tamaño IN ('pequeña', 'mediana', 'grande')),
    descripcion TEXT,
    fecha_convenio DATE,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('activa', 'inactiva', 'en_proceso')),
    observaciones TEXT,
    user_id INTEGER REFERENCES users(id),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de postpenados
CREATE TABLE postpenados (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    dni VARCHAR(20) UNIQUE NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    genero VARCHAR(20) CHECK (genero IN ('masculino', 'femenino', 'otro')),
    nacionalidad VARCHAR(100) NOT NULL,
    direccion TEXT NOT NULL,
    codigo_postal VARCHAR(10) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    estado_civil VARCHAR(50),
    nivel_educativo VARCHAR(100) NOT NULL,
    experiencia_laboral TEXT,
    habilidades TEXT,
    intereses_profesionales TEXT,
    restricciones TEXT,
    fecha_liberacion DATE NOT NULL,
    centro_penitenciario VARCHAR(200),
    tipo_delito VARCHAR(200),
    duracion_condena VARCHAR(100),
    situacion_legal VARCHAR(200) NOT NULL,
    necesidades_especiales TEXT,
    asistente_id INTEGER REFERENCES users(id),
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('activo', 'inactivo', 'pendiente', 'completado')),
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de formaciones y capacitaciones
CREATE TABLE formaciones (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,
    tipo VARCHAR(100) NOT NULL,
    duracion INTEGER NOT NULL, -- en horas
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    lugar VARCHAR(255) NOT NULL,
    formador VARCHAR(255),
    capacidad INTEGER NOT NULL,
    requisitos TEXT,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('programada', 'en_curso', 'finalizada', 'cancelada')),
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de relación entre postpenados y formaciones (inscripciones)
CREATE TABLE postpenado_formacion (
    id SERIAL PRIMARY KEY,
    postpenado_id INTEGER NOT NULL REFERENCES postpenados(id) ON DELETE CASCADE,
    formacion_id INTEGER NOT NULL REFERENCES formaciones(id) ON DELETE CASCADE,
    fecha_inscripcion DATE NOT NULL DEFAULT CURRENT_DATE,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('inscrito', 'asistiendo', 'completado', 'abandono', 'no_asistio')),
    calificacion DECIMAL(5,2),
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (postpenado_id, formacion_id)
);

-- Tabla de ofertas laborales
CREATE TABLE ofertas_laborales (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
    descripcion TEXT NOT NULL,
    requisitos TEXT NOT NULL,
    funciones TEXT NOT NULL,
    tipo_contrato VARCHAR(100) NOT NULL,
    jornada VARCHAR(50) NOT NULL CHECK (jornada IN ('completa', 'parcial', 'por_horas', 'flexible')),
    salario DECIMAL(10,2),
    ubicacion VARCHAR(255) NOT NULL,
    fecha_publicacion DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_expiracion DATE NOT NULL,
    num_vacantes INTEGER NOT NULL DEFAULT 1,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('activa', 'cerrada', 'suspendida')),
    contacto VARCHAR(255),
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de procesos/solicitudes a ofertas
CREATE TABLE procesos (
    id SERIAL PRIMARY KEY,
    postpenado_id INTEGER NOT NULL REFERENCES postpenados(id) ON DELETE CASCADE,
    oferta_id INTEGER NOT NULL REFERENCES ofertas_laborales(id) ON DELETE CASCADE,
    fecha_solicitud DATE NOT NULL DEFAULT CURRENT_DATE,
    cv_enviado BOOLEAN NOT NULL DEFAULT FALSE,
    entrevista_fecha TIMESTAMP,
    resultado_entrevista TEXT,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('solicitado', 'preseleccionado', 'entrevista', 'contratado', 'rechazado')),
    fecha_contratacion DATE,
    tipo_contrato VARCHAR(100),
    duracion_contrato VARCHAR(100),
    seguimiento TEXT,
    evaluacion_empresa TEXT,
    motivo_rechazo TEXT,
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (postpenado_id, oferta_id)
);

-- Tabla de actividades y seguimiento
CREATE TABLE actividades (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(100) NOT NULL CHECK (tipo IN ('entrevista', 'seguimiento', 'orientacion', 'formacion', 'otro')),
    postpenado_id INTEGER REFERENCES postpenados(id) ON DELETE CASCADE,
    usuario_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT NOT NULL,
    fecha TIMESTAMP NOT NULL,
    duracion INTEGER, -- en minutos
    ubicacion VARCHAR(255),
    resultado TEXT,
    compromisos TEXT,
    proximos_pasos TEXT,
    estado VARCHAR(50) NOT NULL CHECK (estado IN ('programada', 'realizada', 'cancelada', 'pospuesta')),
    observaciones TEXT,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para archivos adjuntos
CREATE TABLE archivos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    tipo VARCHAR(100) NOT NULL,
    ruta VARCHAR(500) NOT NULL,
    tamaño INTEGER NOT NULL, -- en bytes
    entidad_tipo VARCHAR(50) NOT NULL CHECK (entidad_tipo IN ('postpenado', 'empresa', 'formacion', 'oferta', 'proceso', 'actividad')),
    entidad_id INTEGER NOT NULL,
    descripcion TEXT,
    usuario_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar el rendimiento
CREATE INDEX idx_postpenados_asistente ON postpenados (asistente_id);
CREATE INDEX idx_postpenados_estado ON postpenados (estado);
CREATE INDEX idx_empresas_estado ON empresas (estado);
CREATE INDEX idx_ofertas_empresa ON ofertas_laborales (empresa_id);
CREATE INDEX idx_ofertas_estado ON ofertas_laborales (estado);
CREATE INDEX idx_procesos_postpenado ON procesos (postpenado_id);
CREATE INDEX idx_procesos_oferta ON procesos (oferta_id);
CREATE INDEX idx_actividades_postpenado ON actividades (postpenado_id);
CREATE INDEX idx_formaciones_estado ON formaciones (estado);

-- Crear un usuario para la aplicación
CREATE USER app_postpenados WITH PASSWORD 'contraseña_segura';

-- Conceder privilegios al usuario
GRANT ALL PRIVILEGES ON DATABASE proyecto_postpenados TO app_postpenados;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_postpenados;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_postpenados;