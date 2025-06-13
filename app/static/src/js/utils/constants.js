/**
 * constants.js - Constantes Globales para el Frontend del Ecosistema
 * ==================================================================
 * 
 * Centraliza todas las constantes utilizadas en la aplicación frontend,
 * incluyendo roles, estados, tipos, endpoints de API y configuraciones UI.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

const AppConstants = {

    // === ROLES DEL SISTEMA ===
    USER_ROLES: {
        ADMIN: 'admin',
        ENTREPRENEUR: 'entrepreneur',
        ALLY: 'ally', // o MENTOR
        CLIENT: 'client',
        GUEST: 'guest'
    },

    // === ESTADOS DE PROYECTOS ===
    PROJECT_STATUS: {
        IDEA: 'idea',
        VALIDATION: 'validation',
        DEVELOPMENT: 'development',
        LAUNCH: 'launch',
        GROWTH: 'growth',
        SCALE: 'scale',
        EXIT: 'exit',
        PAUSED: 'paused',
        CANCELLED: 'cancelled'
    },
    
    ACTIVE_PROJECT_STATUSES: [
        'idea', 'validation', 'development', 'launch', 'growth', 'scale'
    ],

    // === TIPOS DE REUNIONES ===
    MEETING_TYPES: {
        MENTORSHIP: 'mentorship',
        REVIEW: 'review',
        PLANNING: 'planning',
        PITCH: 'pitch',
        FOLLOW_UP: 'follow_up',
        WORKSHOP: 'workshop',
        NETWORKING: 'networking'
    },

    // === TIPOS DE NOTIFICACIONES (ejemplos) ===
    NOTIFICATION_TYPES: {
        SYSTEM: 'system',
        TASK_REMINDER: 'task_reminder',
        MEETING_INVITED: 'meeting_invited',
        PROJECT_UPDATE: 'project_update',
        MESSAGE_RECEIVED: 'message_received'
    },

    // === ENDPOINTS DE API (base) ===
    API_ENDPOINTS: {
        BASE_URL: '/api/v1',
        AUTH: '/api/v1/auth',
        USERS: '/api/v1/users',
        PROJECTS: '/api/v1/projects',
        MEETINGS: '/api/v1/meetings',
        DOCUMENTS: '/api/v1/documents',
        MESSAGES: '/api/v1/messages',
        NOTIFICATIONS: '/api/v1/notifications',
        ANALYTICS: '/api/v1/analytics',
        // ... más endpoints según tu API
    },

    // === CONFIGURACIÓN UI ===
    UI_SETTINGS: {
        DEFAULT_PAGE_SIZE: 20,
        MAX_PAGE_SIZE: 100,
        ANIMATION_DURATION: 300, // ms
        DEBOUNCE_DELAY: 250, // ms
        TOOLTIP_DELAY: 500, // ms
        DATE_FORMAT: 'DD/MM/YYYY',
        DATETIME_FORMAT: 'DD/MM/YYYY HH:mm',
        CURRENCY_SYMBOL: '$', // Podría ser dinámico según locale
        DEFAULT_LOCALE: 'es-CO'
    },

    // === EVENTOS PERSONALIZADOS ===
    CUSTOM_EVENTS: {
        USER_LOGGED_IN: 'ecosistema:userLoggedIn',
        USER_LOGGED_OUT: 'ecosistema:userLoggedOut',
        PROFILE_UPDATED: 'ecosistema:profileUpdated',
        PROJECT_CREATED: 'ecosistema:projectCreated',
        PROJECT_UPDATED: 'ecosistema:projectUpdated',
        NOTIFICATION_RECEIVED: 'ecosistema:notificationReceived',
        MODAL_OPENED: 'ecosistema:modalOpened',
        MODAL_CLOSED: 'ecosistema:modalClosed'
    },

    // === CACHE KEYS (para localStorage/sessionStorage) ===
    CACHE_KEYS: {
        USER_PREFERENCES: 'ecosistema_user_prefs',
        AUTH_TOKEN: 'ecosistema_auth_token',
        LAST_VISITED_ROUTE: 'ecosistema_last_route',
        DASHBOARD_LAYOUT: 'ecosistema_dashboard_layout'
    },

    // === LÍMITES Y RESTRICCIONES ===
    LIMITS: {
        MAX_FILE_UPLOAD_SIZE_MB: 10, // MB
        MAX_PROJECT_TITLE_LENGTH: 100,
        MAX_DESCRIPTION_LENGTH: 2000,
        MIN_PASSWORD_LENGTH: 8
    },

    // === COLORES DEL ECOSISTEMA (para gráficos, UI, etc.) ===
    ECOSYSTEM_COLORS: {
        PRIMARY: '#007bff',    // Azul principal
        SECONDARY: '#6c757d',  // Gris secundario
        SUCCESS: '#28a745',   // Verde éxito
        DANGER: '#dc3545',    // Rojo peligro
        WARNING: '#ffc107',   // Amarillo advertencia
        INFO: '#17a2b8',      // Azul info
        LIGHT: '#f8f9fa',     // Gris claro
        DARK: '#343a40',      // Negro/gris oscuro
        ENTREPRENEUR: '#ff6b6b', // Color para emprendedores
        ALLY: '#4ecdc4',      // Color para aliados
        CLIENT: '#45b7d1'     // Color para clientes
    },

    // === ESTADOS DE CARGA ===
    LOADING_STATUS: {
        IDLE: 'idle',
        LOADING: 'loading',
        SUCCESS: 'success',
        ERROR: 'error'
    },

    // === TIPOS DE DOCUMENTOS (ejemplos) ===
    DOCUMENT_TYPES: {
        PITCH_DECK: 'pitch_deck',
        BUSINESS_PLAN: 'business_plan',
        FINANCIALS: 'financial_model',
        LEGAL: 'legal_document',
        REPORT: 'report'
    },

    // === MÓDULOS DE LA APLICACIÓN (para routing o lógica condicional) ===
    APP_MODULES: {
        DASHBOARD: 'dashboard',
        PROFILE: 'profile',
        PROJECTS: 'projects',
        MENTORSHIP: 'mentorship',
        MEETINGS: 'meetings',
        DOCUMENTS: 'documents',
        MESSAGES: 'messages',
        ANALYTICS: 'analytics',
        SETTINGS: 'settings',
        ADMIN: 'admin'
    },

    // === VALORES POR DEFECTO ===
    DEFAULTS: {
        AVATAR_URL: '/static/img/default-avatar.png',
        PROJECT_LOGO_URL: '/static/img/default-project-logo.png',
        ITEMS_PER_PAGE: 10,
        REQUEST_TIMEOUT: 15000 // 15 segundos
    },

    // === EXPRESIONES REGULARES COMUNES ===
    REGEX: {
        EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
        PHONE_CO: /^(?:\+57|0057)?[ -]*(?:(3[0-2]\d)[ -]*(\d{3})[ -]*(\d{4})|([1-8])\d{6})$/, // Teléfono Colombia
        STRONG_PASSWORD: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,
        URL: /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/
    }
};

// Exportar como módulo si se usa un sistema de módulos (ej. ES6, CommonJS)
// Si no, estará disponible globalmente como AppConstants.

// Para ES6 modules:
// export default AppConstants;

// Para CommonJS (Node.js):
// module.exports = AppConstants;

// Para disponibilidad global en el navegador (si no se usan módulos):
if (typeof window !== 'undefined') {
    window.AppConstants = AppConstants;
}
