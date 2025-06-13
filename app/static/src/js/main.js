/**
 * Main JavaScript for Ecosistema Emprendimiento
 * =============================================
 * 
 * Archivo principal de JavaScript que maneja la inicialización de la aplicación,
 * configuración de bibliotecas, eventos globales y funcionalidades comunes
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

'use strict';

// ============================================================================
// CONFIGURACIÓN GLOBAL
// ============================================================================

// Configuración de la aplicación
window.EcosistemaApp = {
    // Información básica
    version: '1.0.0',
    environment: document.querySelector('meta[name="environment"]')?.content || 'production',
    debug: document.querySelector('meta[name="debug"]')?.content === 'true',
    
    // URLs y endpoints
    baseUrl: window.location.origin,
    apiUrl: document.querySelector('meta[name="api-url"]')?.content || '/api/v1',
    wsUrl: document.querySelector('meta[name="ws-url"]')?.content || 'ws://localhost:5000',
    
    // Configuración del usuario actual
    currentUser: null,
    userType: document.querySelector('meta[name="user-type"]')?.content || 'guest',
    userRole: document.querySelector('meta[name="user-role"]')?.content || 'user',
    
    // Configuración de funcionalidades
    features: {
        realTimeNotifications: true,
        analytics: true,
        darkMode: true,
        responsiveDesign: true,
        accessibility: true,
        offlineSupport: false
    },
    
    // Estado de la aplicación
    state: {
        isOnline: navigator.onLine,
        isLoading: false,
        theme: localStorage.getItem('theme') || 'light',
        language: document.documentElement.lang || 'es',
        viewport: 'desktop'
    },
    
    // Configuración de módulos
    modules: {},
    
    // Event emitter para comunicación entre módulos
    events: new EventTarget(),
    
    // Cache para datos frecuentemente utilizados
    cache: new Map(),
    
    // Queue para acciones diferidas
    actionQueue: []
};

// Alias para facilitar el acceso
const App = window.EcosistemaApp;

// ============================================================================
// UTILIDADES GLOBALES
// ============================================================================

/**
 * Utilidades comunes de la aplicación
 */
App.utils = {
    /**
     * Debounce para optimizar eventos frecuentes
     * @param {Function} func - Función a ejecutar
     * @param {number} wait - Tiempo de espera en ms
     * @param {boolean} immediate - Ejecutar inmediatamente
     * @return {Function} Función con debounce aplicado
     */
    debounce(func, wait = 300, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    },

    /**
     * Throttle para limitar ejecución de funciones
     * @param {Function} func - Función a ejecutar
     * @param {number} limit - Límite de tiempo en ms
     * @return {Function} Función con throttle aplicado
     */
    throttle(func, limit = 100) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Formatear números con separadores de miles
     * @param {number} num - Número a formatear
     * @param {string} locale - Configuración regional
     * @return {string} Número formateado
     */
    formatNumber(num, locale = 'es-CO') {
        if (typeof num !== 'number' || isNaN(num)) return '0';
        return new Intl.NumberFormat(locale).format(num);
    },

    /**
     * Formatear moneda
     * @param {number} amount - Cantidad a formatear
     * @param {string} currency - Código de moneda
     * @param {string} locale - Configuración regional
     * @return {string} Cantidad formateada como moneda
     */
    formatCurrency(amount, currency = 'COP', locale = 'es-CO') {
        if (typeof amount !== 'number' || isNaN(amount)) return '$0';
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },

    /**
     * Formatear fechas relativas
     * @param {Date|string} date - Fecha a formatear
     * @param {string} locale - Configuración regional
     * @return {string} Fecha formateada
     */
    formatRelativeTime(date, locale = 'es-CO') {
        const now = new Date();
        const targetDate = new Date(date);
        const diffInSeconds = Math.floor((now - targetDate) / 1000);
        
        const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
        
        if (diffInSeconds < 60) return rtf.format(-diffInSeconds, 'second');
        if (diffInSeconds < 3600) return rtf.format(-Math.floor(diffInSeconds / 60), 'minute');
        if (diffInSeconds < 86400) return rtf.format(-Math.floor(diffInSeconds / 3600), 'hour');
        if (diffInSeconds < 2592000) return rtf.format(-Math.floor(diffInSeconds / 86400), 'day');
        if (diffInSeconds < 31536000) return rtf.format(-Math.floor(diffInSeconds / 2592000), 'month');
        return rtf.format(-Math.floor(diffInSeconds / 31536000), 'year');
    },

    /**
     * Truncar texto con elipsis
     * @param {string} text - Texto a truncar
     * @param {number} maxLength - Longitud máxima
     * @return {string} Texto truncado
     */
    truncateText(text, maxLength = 100) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    },

    /**
     * Generar UUID v4
     * @return {string} UUID generado
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Validar email
     * @param {string} email - Email a validar
     * @return {boolean} Es válido
     */
    isValidEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },

    /**
     * Validar URL
     * @param {string} url - URL a validar
     * @return {boolean} Es válida
     */
    isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },

    /**
     * Obtener parámetros de la URL
     * @return {Object} Parámetros de la URL
     */
    getUrlParams() {
        return Object.fromEntries(new URLSearchParams(window.location.search));
    },

    /**
     * Scroll suave a elemento
     * @param {string|Element} target - Selector o elemento
     * @param {number} offset - Offset en pixels
     */
    smoothScrollTo(target, offset = 0) {
        const element = typeof target === 'string' ? document.querySelector(target) : target;
        if (!element) return;
        
        const targetPosition = element.offsetTop - offset;
        window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
        });
    },

    /**
     * Copiar al portapapeles
     * @param {string} text - Texto a copiar
     * @return {Promise<boolean>} Éxito de la operación
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch {
            // Fallback para navegadores más antiguos
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                document.execCommand('copy');
                return true;
            } catch {
                return false;
            } finally {
                document.body.removeChild(textArea);
            }
        }
    },

    /**
     * Detectar dispositivo móvil
     * @return {boolean} Es dispositivo móvil
     */
    isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    },

    /**
     * Detectar soporte de características
     * @param {string} feature - Característica a detectar
     * @return {boolean} Tiene soporte
     */
    hasSupport(feature) {
        const features = {
            localStorage: typeof Storage !== 'undefined',
            sessionStorage: typeof Storage !== 'undefined',
            webSockets: typeof WebSocket !== 'undefined',
            serviceWorker: 'serviceWorker' in navigator,
            notifications: 'Notification' in window,
            geolocation: 'geolocation' in navigator,
            camera: navigator.mediaDevices && navigator.mediaDevices.getUserMedia,
            touch: 'ontouchstart' in window,
            webGL: !!window.WebGLRenderingContext
        };
        
        return features[feature] || false;
    }
};

// ============================================================================
// SISTEMA DE ALMACENAMIENTO
// ============================================================================

/**
 * Manejo de almacenamiento local con fallbacks
 */
App.storage = {
    /**
     * Obtener valor del almacenamiento
     * @param {string} key - Clave
     * @param {any} defaultValue - Valor por defecto
     * @return {any} Valor almacenado
     */
    get(key, defaultValue = null) {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                return App.cache.get(key) || defaultValue;
            }
            
            const value = localStorage.getItem(`ecosistema_${key}`);
            return value ? JSON.parse(value) : defaultValue;
        } catch (error) {
            console.warn('Error getting from storage:', error);
            return defaultValue;
        }
    },

    /**
     * Guardar valor en almacenamiento
     * @param {string} key - Clave
     * @param {any} value - Valor a guardar
     * @return {boolean} Éxito de la operación
     */
    set(key, value) {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                App.cache.set(key, value);
                return true;
            }
            
            localStorage.setItem(`ecosistema_${key}`, JSON.stringify(value));
            return true;
        } catch (error) {
            console.warn('Error setting to storage:', error);
            return false;
        }
    },

    /**
     * Eliminar valor del almacenamiento
     * @param {string} key - Clave
     * @return {boolean} Éxito de la operación
     */
    remove(key) {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                App.cache.delete(key);
                return true;
            }
            
            localStorage.removeItem(`ecosistema_${key}`);
            return true;
        } catch (error) {
            console.warn('Error removing from storage:', error);
            return false;
        }
    },

    /**
     * Limpiar todo el almacenamiento de la app
     */
    clear() {
        try {
            if (App.utils.hasSupport('localStorage')) {
                Object.keys(localStorage)
                    .filter(key => key.startsWith('ecosistema_'))
                    .forEach(key => localStorage.removeItem(key));
            }
            App.cache.clear();
        } catch (error) {
            console.warn('Error clearing storage:', error);
        }
    }
};

// ============================================================================
// SISTEMA DE NOTIFICACIONES
// ============================================================================

/**
 * Sistema de notificaciones toast
 */
App.notifications = {
    container: null,
    
    /**
     * Inicializar sistema de notificaciones
     */
    init() {
        this.createContainer();
        this.requestPermission();
    },

    /**
     * Crear contenedor de notificaciones
     */
    createContainer() {
        if (this.container) return;
        
        this.container = document.createElement('div');
        this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
        this.container.style.zIndex = '9999';
        document.body.appendChild(this.container);
    },

    /**
     * Solicitar permisos para notificaciones del navegador
     */
    async requestPermission() {
        if (!App.utils.hasSupport('notifications')) return false;
        
        if (Notification.permission === 'default') {
            const permission = await Notification.requestPermission();
            return permission === 'granted';
        }
        
        return Notification.permission === 'granted';
    },

    /**
     * Mostrar notificación toast
     * @param {string} message - Mensaje
     * @param {string} type - Tipo (success, error, warning, info)
     * @param {Object} options - Opciones adicionales
     */
    show(message, type = 'info', options = {}) {
        const config = {
            duration: 5000,
            closable: true,
            autoHide: true,
            animate: true,
            icon: true,
            ...options
        };

        const toast = this.createToast(message, type, config);
        this.container.appendChild(toast);

        // Animación de entrada
        if (config.animate) {
            toast.classList.add('animate__animated', 'animate__slideInRight');
        }

        // Auto-hide
        if (config.autoHide) {
            setTimeout(() => {
                this.hide(toast, config.animate);
            }, config.duration);
        }

        return toast;
    },

    /**
     * Crear elemento toast
     * @param {string} message - Mensaje
     * @param {string} type - Tipo
     * @param {Object} config - Configuración
     * @return {Element} Elemento toast
     */
    createToast(message, type, config) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 mb-2`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const iconHtml = config.icon ? `<i class="fa ${icons[type]} me-2"></i>` : '';
        const closeButton = config.closable ? 
            '<button type="button" class="btn-close btn-close-white me-2" aria-label="Cerrar"></button>' : '';

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${iconHtml}${message}
                </div>
                ${closeButton}
            </div>
        `;

        // Event listener para cerrar
        if (config.closable) {
            const closeBtn = toast.querySelector('.btn-close');
            closeBtn.addEventListener('click', () => {
                this.hide(toast, config.animate);
            });
        }

        return toast;
    },

    /**
     * Ocultar notificación
     * @param {Element} toast - Elemento toast
     * @param {boolean} animate - Aplicar animación
     */
    hide(toast, animate = true) {
        if (!toast || !toast.parentNode) return;

        if (animate) {
            toast.classList.remove('animate__slideInRight');
            toast.classList.add('animate__slideOutRight');
            
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        } else {
            toast.parentNode.removeChild(toast);
        }
    },

    /**
     * Métodos de conveniencia
     */
    success(message, options = {}) {
        return this.show(message, 'success', options);
    },

    error(message, options = {}) {
        return this.show(message, 'danger', options);
    },

    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    },

    info(message, options = {}) {
        return this.show(message, 'info', options);
    },

    /**
     * Notificación del navegador
     * @param {string} title - Título
     * @param {Object} options - Opciones
     */
    browser(title, options = {}) {
        if (!App.utils.hasSupport('notifications') || Notification.permission !== 'granted') {
            return this.info(title);
        }

        const config = {
            icon: '/static/img/logo-small.png',
            badge: '/static/img/badge.png',
            tag: 'ecosistema-notification',
            renotify: false,
            ...options
        };

        const notification = new Notification(title, config);
        
        // Auto-close después de 5 segundos
        setTimeout(() => {
            notification.close();
        }, 5000);

        return notification;
    }
};

// ============================================================================
// SISTEMA DE CARGA Y LOADING
// ============================================================================

/**
 * Manejo de estados de carga
 */
App.loading = {
    /**
     * Mostrar loading global
     * @param {string} message - Mensaje de carga
     */
    show(message = 'Cargando...') {
        App.state.isLoading = true;
        
        let loader = document.getElementById('global-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'global-loader';
            loader.className = 'global-loader d-flex flex-column align-items-center justify-content-center';
            loader.innerHTML = `
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <div class="loading-message text-muted">${message}</div>
            `;
            document.body.appendChild(loader);
        } else {
            loader.querySelector('.loading-message').textContent = message;
            loader.style.display = 'flex';
        }
        
        document.body.classList.add('loading');
    },

    /**
     * Ocultar loading global
     */
    hide() {
        App.state.isLoading = false;
        
        const loader = document.getElementById('global-loader');
        if (loader) {
            loader.style.display = 'none';
        }
        
        document.body.classList.remove('loading');
    },

    /**
     * Loading para botones
     * @param {Element|string} button - Botón o selector
     * @param {boolean} loading - Estado de carga
     */
    button(button, loading = true) {
        const btn = typeof button === 'string' ? document.querySelector(button) : button;
        if (!btn) return;

        if (loading) {
            btn.disabled = true;
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Cargando...
            `;
        } else {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
            delete btn.dataset.originalText;
        }
    }
};

// ============================================================================
// SISTEMA HTTP/AJAX
// ============================================================================

/**
 * Cliente HTTP simplificado
 */
App.http = {
    /**
     * Configuración por defecto
     */
    defaults: {
        timeout: 30000,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    },

    /**
     * Realizar petición HTTP
     * @param {string} url - URL
     * @param {Object} options - Opciones
     * @return {Promise} Promesa de la respuesta
     */
    async request(url, options = {}) {
        const config = {
            method: 'GET',
            ...this.defaults,
            ...options,
            headers: {
                ...this.defaults.headers,
                ...options.headers
            }
        };

        // Agregar CSRF token si existe
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (csrfToken) {
            config.headers['X-CSRF-Token'] = csrfToken;
        }

        // Preparar body para JSON
        if (config.body && typeof config.body === 'object' && 
            config.headers['Content-Type'] === 'application/json') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);
            
            config.signal = controller.signal;
            
            const response = await fetch(url.startsWith('http') ? url : App.apiUrl + url, config);
            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            throw error;
        }
    },

    /**
     * Métodos de conveniencia
     */
    get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    },

    post(url, data, options = {}) {
        return this.request(url, { ...options, method: 'POST', body: data });
    },

    put(url, data, options = {}) {
        return this.request(url, { ...options, method: 'PUT', body: data });
    },

    patch(url, data, options = {}) {
        return this.request(url, { ...options, method: 'PATCH', body: data });
    },

    delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    }
};

// ============================================================================
// SISTEMA DE FORMULARIOS
// ============================================================================

/**
 * Manejo avanzado de formularios
 */
App.forms = {
    /**
     * Inicializar formularios en la página
     */
    init() {
        this.bindValidation();
        this.bindSubmission();
        this.bindFileUploads();
    },

    /**
     * Vincular validación en tiempo real
     */
    bindValidation() {
        document.querySelectorAll('form[data-validate="true"]').forEach(form => {
            form.querySelectorAll('input, textarea, select').forEach(field => {
                field.addEventListener('blur', () => this.validateField(field));
                field.addEventListener('input', App.utils.debounce(() => this.validateField(field), 500));
            });
        });
    },

    /**
     * Vincular envío de formularios
     */
    bindSubmission() {
        document.querySelectorAll('form[data-ajax="true"]').forEach(form => {
            form.addEventListener('submit', (e) => this.handleSubmit(e));
        });
    },

    /**
     * Vincular subida de archivos
     */
    bindFileUploads() {
        document.querySelectorAll('input[type="file"][data-upload="true"]').forEach(input => {
            input.addEventListener('change', (e) => this.handleFileUpload(e));
        });
    },

    /**
     * Validar campo individual
     * @param {Element} field - Campo a validar
     * @return {boolean} Es válido
     */
    validateField(field) {
        const value = field.value.trim();
        const type = field.type;
        const required = field.hasAttribute('required');
        const pattern = field.getAttribute('pattern');
        const minLength = field.getAttribute('minlength');
        const maxLength = field.getAttribute('maxlength');
        const min = field.getAttribute('min');
        const max = field.getAttribute('max');

        let isValid = true;
        let message = '';

        // Validar requerido
        if (required && !value) {
            isValid = false;
            message = 'Este campo es obligatorio';
        }

        // Validar email
        if (isValid && type === 'email' && value && !App.utils.isValidEmail(value)) {
            isValid = false;
            message = 'Ingrese un email válido';
        }

        // Validar URL
        if (isValid && type === 'url' && value && !App.utils.isValidUrl(value)) {
            isValid = false;
            message = 'Ingrese una URL válida';
        }

        // Validar longitud mínima
        if (isValid && minLength && value.length < parseInt(minLength)) {
            isValid = false;
            message = `Mínimo ${minLength} caracteres`;
        }

        // Validar longitud máxima
        if (isValid && maxLength && value.length > parseInt(maxLength)) {
            isValid = false;
            message = `Máximo ${maxLength} caracteres`;
        }

        // Validar números
        if (isValid && (type === 'number' || type === 'range')) {
            const numValue = parseFloat(value);
            if (value && isNaN(numValue)) {
                isValid = false;
                message = 'Ingrese un número válido';
            } else if (min && numValue < parseFloat(min)) {
                isValid = false;
                message = `El valor mínimo es ${min}`;
            } else if (max && numValue > parseFloat(max)) {
                isValid = false;
                message = `El valor máximo es ${max}`;
            }
        }

        // Validar patrón
        if (isValid && pattern && value && !new RegExp(pattern).test(value)) {
            isValid = false;
            message = field.getAttribute('data-pattern-message') || 'Formato no válido';
        }

        // Aplicar estilos de validación
        this.setFieldValidation(field, isValid, message);

        return isValid;
    },

    /**
     * Establecer estado de validación de campo
     * @param {Element} field - Campo
     * @param {boolean} isValid - Es válido
     * @param {string} message - Mensaje de error
     */
    setFieldValidation(field, isValid, message = '') {
        const formGroup = field.closest('.form-group') || field.closest('.mb-3');
        
        // Remover clases previas
        field.classList.remove('is-valid', 'is-invalid');
        
        if (formGroup) {
            formGroup.classList.remove('has-success', 'has-error');
            
            // Remover mensajes de error previos
            const prevError = formGroup.querySelector('.invalid-feedback');
            if (prevError) prevError.remove();
        }

        if (field.value.trim()) {
            if (isValid) {
                field.classList.add('is-valid');
                if (formGroup) formGroup.classList.add('has-success');
            } else {
                field.classList.add('is-invalid');
                if (formGroup) {
                    formGroup.classList.add('has-error');
                    
                    // Agregar mensaje de error
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    errorDiv.textContent = message;
                    field.insertAdjacentElement('afterend', errorDiv);
                }
            }
        }
    },

    /**
     * Manejar envío de formulario
     * @param {Event} e - Evento de envío
     */
    async handleSubmit(e) {
        e.preventDefault();
        
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        
        // Validar todo el formulario
        const isValid = this.validateForm(form);
        if (!isValid) return;

        // Mostrar loading en botón
        App.loading.button(submitBtn, true);

        try {
            const formData = new FormData(form);
            const url = form.action || window.location.pathname;
            const method = form.method || 'POST';

            // Convertir FormData a objeto si es JSON
            let data = formData;
            if (form.getAttribute('data-json') === 'true') {
                data = Object.fromEntries(formData.entries());
            }

            const response = await App.http.request(url, {
                method: method.toUpperCase(),
                body: data,
                headers: form.getAttribute('data-json') === 'true' ? 
                    { 'Content-Type': 'application/json' } : {}
            });

            // Manejar respuesta exitosa
            this.handleFormSuccess(form, response);

        } catch (error) {
            this.handleFormError(form, error);
        } finally {
            App.loading.button(submitBtn, false);
        }
    },

    /**
     * Validar formulario completo
     * @param {Element} form - Formulario
     * @return {boolean} Es válido
     */
    validateForm(form) {
        let isValid = true;
        
        form.querySelectorAll('input, textarea, select').forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });

        return isValid;
    },

    /**
     * Manejar éxito del formulario
     * @param {Element} form - Formulario
     * @param {Object} response - Respuesta del servidor
     */
    handleFormSuccess(form, response) {
        // Limpiar errores
        form.querySelectorAll('.is-invalid').forEach(field => {
            field.classList.remove('is-invalid');
        });
        form.querySelectorAll('.invalid-feedback').forEach(error => error.remove());

        // Mostrar mensaje de éxito
        App.notifications.success(response.message || 'Formulario enviado correctamente');

        // Redireccionar si se especifica
        if (response.redirect) {
            setTimeout(() => {
                window.location.href = response.redirect;
            }, 1500);
        }

        // Resetear formulario si se especifica
        if (form.getAttribute('data-reset') === 'true') {
            form.reset();
        }

        // Emitir evento personalizado
        App.events.dispatchEvent(new CustomEvent('formSuccess', {
            detail: { form, response }
        }));
    },

    /**
     * Manejar error del formulario
     * @param {Element} form - Formulario
     * @param {Error} error - Error
     */
    handleFormError(form, error) {
        let message = 'Error al enviar el formulario';
        
        // Intentar parsear errores del servidor
        try {
            const errorData = JSON.parse(error.message);
            if (errorData.errors) {
                // Errores de campos específicos
                Object.entries(errorData.errors).forEach(([field, fieldErrors]) => {
                    const input = form.querySelector(`[name="${field}"]`);
                    if (input) {
                        this.setFieldValidation(input, false, fieldErrors[0]);
                    }
                });
            }
            
            if (errorData.message) {
                message = errorData.message;
            }
        } catch {
            // Error genérico
        }

        App.notifications.error(message);

        // Emitir evento personalizado
        App.events.dispatchEvent(new CustomEvent('formError', {
            detail: { form, error }
        }));
    },

    /**
     * Manejar subida de archivos
     * @param {Event} e - Evento de cambio
     */
    async handleFileUpload(e) {
        const input = e.target;
        const files = input.files;
        
        if (!files.length) return;

        const maxSize = parseInt(input.getAttribute('data-max-size')) || 5 * 1024 * 1024; // 5MB por defecto
        const allowedTypes = input.getAttribute('data-allowed-types')?.split(',') || [];

        // Validar archivos
        for (const file of files) {
            if (file.size > maxSize) {
                App.notifications.error(`El archivo ${file.name} es muy grande. Máximo ${App.utils.formatNumber(maxSize / 1024 / 1024)}MB`);
                input.value = '';
                return;
            }

            if (allowedTypes.length && !allowedTypes.includes(file.type)) {
                App.notifications.error(`Tipo de archivo no permitido: ${file.type}`);
                input.value = '';
                return;
            }
        }

        // Mostrar preview si es imagen
        if (files[0].type.startsWith('image/')) {
            this.showImagePreview(input, files[0]);
        }

        // Upload automático si se especifica
        if (input.getAttribute('data-auto-upload') === 'true') {
            await this.uploadFile(input, files[0]);
        }
    },

    /**
     * Mostrar preview de imagen
     * @param {Element} input - Input file
     * @param {File} file - Archivo
     */
    showImagePreview(input, file) {
        const preview = input.nextElementSibling;
        if (!preview || !preview.classList.contains('image-preview')) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview" class="img-thumbnail" style="max-width: 200px;">`;
        };
        reader.readAsDataURL(file);
    },

    /**
     * Subir archivo
     * @param {Element} input - Input file
     * @param {File} file - Archivo
     * @return {Promise} Resultado de la subida
     */
    async uploadFile(input, file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('field', input.name);

        const uploadUrl = input.getAttribute('data-upload-url') || '/upload';

        try {
            const response = await App.http.post(uploadUrl, formData, {
                headers: {} // Dejar que el navegador establezca Content-Type
            });

            App.notifications.success('Archivo subido correctamente');
            
            // Emitir evento de subida exitosa
            App.events.dispatchEvent(new CustomEvent('fileUploaded', {
                detail: { input, file, response }
            }));

            return response;
        } catch (error) {
            App.notifications.error('Error al subir el archivo');
            throw error;
        }
    }
};

// ============================================================================
// SISTEMA DE WEBSOCKETS
// ============================================================================

/**
 * Cliente WebSocket para tiempo real
 */
App.websocket = {
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000,
    heartbeatInterval: null,

    /**
     * Conectar WebSocket
     */
    connect() {
        if (!App.utils.hasSupport('webSockets')) {
            console.warn('WebSocket no soportado');
            return;
        }

        try {
            this.socket = new WebSocket(App.wsUrl);
            this.bindEvents();
        } catch (error) {
            console.error('Error conectando WebSocket:', error);
        }
    },

    /**
     * Vincular eventos del WebSocket
     */
    bindEvents() {
        this.socket.onopen = () => {
            console.log('WebSocket conectado');
            this.reconnectAttempts = 0;
            this.startHeartbeat();
            
            // Autenticar conexión
            this.send('auth', {
                user_id: App.currentUser?.id,
                token: App.storage.get('auth_token')
            });
            
            App.events.dispatchEvent(new CustomEvent('websocketConnected'));
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.socket.onclose = () => {
            console.log('WebSocket desconectado');
            this.stopHeartbeat();
            this.reconnect();
            
            App.events.dispatchEvent(new CustomEvent('websocketDisconnected'));
        };

        this.socket.onerror = (error) => {
            console.error('Error en WebSocket:', error);
            App.events.dispatchEvent(new CustomEvent('websocketError', { detail: error }));
        };
    },

    /**
     * Manejar mensajes recibidos
     * @param {Object} data - Datos del mensaje
     */
    handleMessage(data) {
        const { type, payload } = data;

        switch (type) {
            case 'notification':
                this.handleNotification(payload);
                break;
            case 'user_status':
                this.handleUserStatus(payload);
                break;
            case 'message':
                this.handleChatMessage(payload);
                break;
            case 'meeting_reminder':
                this.handleMeetingReminder(payload);
                break;
            case 'system_update':
                this.handleSystemUpdate(payload);
                break;
            default:
                App.events.dispatchEvent(new CustomEvent(`websocket:${type}`, { detail: payload }));
        }
    },

    /**
     * Manejar notificación en tiempo real
     * @param {Object} notification - Notificación
     */
    handleNotification(notification) {
        App.notifications.show(notification.message, notification.type || 'info');
        
        // Notificación del navegador si la pestaña no está activa
        if (document.hidden) {
            App.notifications.browser(notification.title || 'Nueva notificación', {
                body: notification.message,
                data: notification
            });
        }

        // Actualizar contador de notificaciones
        this.updateNotificationCount();
    },

    /**
     * Manejar estado de usuario
     * @param {Object} status - Estado del usuario
     */
    handleUserStatus(status) {
        const userElements = document.querySelectorAll(`[data-user-id="${status.user_id}"]`);
        userElements.forEach(element => {
            element.classList.remove('status-online', 'status-away', 'status-busy', 'status-offline');
            element.classList.add(`status-${status.status}`);
        });
    },

    /**
     * Manejar mensaje de chat
     * @param {Object} message - Mensaje
     */
    handleChatMessage(message) {
        App.events.dispatchEvent(new CustomEvent('chatMessage', { detail: message }));
    },

    /**
     * Manejar recordatorio de reunión
     * @param {Object} reminder - Recordatorio
     */
    handleMeetingReminder(reminder) {
        App.notifications.warning(
            `Reunión "${reminder.title}" comenzará en ${reminder.minutes} minutos`,
            { duration: 10000 }
        );
    },

    /**
     * Manejar actualización del sistema
     * @param {Object} update - Actualización
     */
    handleSystemUpdate(update) {
        if (update.reload_required) {
            App.notifications.info(
                'Hay una actualización disponible. La página se recargará automáticamente.',
                { duration: 5000 }
            );
            
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        }
    },

    /**
     * Enviar mensaje por WebSocket
     * @param {string} type - Tipo de mensaje
     * @param {Object} payload - Datos
     */
    send(type, payload = {}) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, payload }));
        }
    },

    /**
     * Reconectar WebSocket
     */
    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Máximo número de intentos de reconexión alcanzado');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        setTimeout(() => {
            console.log(`Intentando reconectar WebSocket (intento ${this.reconnectAttempts})`);
            this.connect();
        }, delay);
    },

    /**
     * Iniciar heartbeat
     */
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this.send('ping');
        }, 30000);
    },

    /**
     * Detener heartbeat
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    },

    /**
     * Actualizar contador de notificaciones
     */
    updateNotificationCount() {
        // Implementar según el diseño específico
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            const currentCount = parseInt(badge.textContent) || 0;
            badge.textContent = currentCount + 1;
            badge.style.display = 'inline';
        }
    }
};

// ============================================================================
// SISTEMA DE TEMAS (DARK MODE)
// ============================================================================

/**
 * Manejo de temas claro/oscuro
 */
App.theme = {
    /**
     * Inicializar sistema de temas
     */
    init() {
        this.loadTheme();
        this.bindToggle();
        this.detectSystemTheme();
    },

    /**
     * Cargar tema guardado
     */
    loadTheme() {
        const savedTheme = App.storage.get('theme');
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        const theme = savedTheme || systemTheme;
        
        this.setTheme(theme);
    },

    /**
     * Establecer tema
     * @param {string} theme - Tema (light/dark)
     */
    setTheme(theme) {
        App.state.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        App.storage.set('theme', theme);
        
        // Actualizar toggles
        const toggles = document.querySelectorAll('[data-theme-toggle]');
        toggles.forEach(toggle => {
            toggle.checked = theme === 'dark';
        });

        // Emitir evento
        App.events.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    },

    /**
     * Alternar tema
     */
    toggle() {
        const newTheme = App.state.theme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },

    /**
     * Vincular controles de toggle
     */
    bindToggle() {
        document.querySelectorAll('[data-theme-toggle]').forEach(toggle => {
            toggle.addEventListener('change', () => {
                this.toggle();
            });
        });
    },

    /**
     * Detectar cambios en el tema del sistema
     */
    detectSystemTheme() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            if (!App.storage.get('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }
};

// ============================================================================
// DETECTOR DE VIEWPORT
// ============================================================================

/**
 * Detección y manejo de viewport responsivo
 */
App.viewport = {
    /**
     * Inicializar detector de viewport
     */
    init() {
        this.detect();
        this.bindResize();
    },

    /**
     * Detectar viewport actual
     */
    detect() {
        const width = window.innerWidth;
        let viewport = 'desktop';

        if (width < 576) {
            viewport = 'mobile';
        } else if (width < 768) {
            viewport = 'mobile-large';
        } else if (width < 992) {
            viewport = 'tablet';
        } else if (width < 1200) {
            viewport = 'desktop';
        } else {
            viewport = 'desktop-large';
        }

        if (App.state.viewport !== viewport) {
            const previous = App.state.viewport;
            App.state.viewport = viewport;
            
            document.body.className = document.body.className
                .replace(/viewport-\w+/g, '')
                .trim() + ` viewport-${viewport}`;

            App.events.dispatchEvent(new CustomEvent('viewportChanged', {
                detail: { viewport, previous, width }
            }));
        }
    },

    /**
     * Vincular evento de resize
     */
    bindResize() {
        window.addEventListener('resize', App.utils.throttle(() => {
            this.detect();
        }, 250));
    },

    /**
     * Verificar si es móvil
     * @return {boolean} Es móvil
     */
    isMobile() {
        return ['mobile', 'mobile-large'].includes(App.state.viewport);
    },

    /**
     * Verificar si es tablet
     * @return {boolean} Es tablet
     */
    isTablet() {
        return App.state.viewport === 'tablet';
    },

    /**
     * Verificar si es desktop
     * @return {boolean} Es desktop
     */
    isDesktop() {
        return ['desktop', 'desktop-large'].includes(App.state.viewport);
    }
};

// ============================================================================
// MANEJO DE ERRORES GLOBALES
// ============================================================================

/**
 * Sistema de manejo de errores
 */
App.errorHandler = {
    /**
     * Inicializar manejo de errores
     */
    init() {
        this.bindGlobalHandlers();
        this.setupUnhandledRejection();
    },

    /**
     * Vincular manejadores globales
     */
    bindGlobalHandlers() {
        window.addEventListener('error', (event) => {
            this.handleError({
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error
            });
        });

        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                message: 'Unhandled Promise Rejection',
                error: event.reason
            });
        });
    },

    /**
     * Configurar manejo de promesas rechazadas
     */
    setupUnhandledRejection() {
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            
            if (App.debug) {
                App.notifications.error('Error no controlado en la aplicación');
            }
        });
    },

    /**
     * Manejar error
     * @param {Object} errorInfo - Información del error
     */
    handleError(errorInfo) {
        console.error('Global error:', errorInfo);

        // En desarrollo, mostrar errores al usuario
        if (App.debug) {
            App.notifications.error(`Error: ${errorInfo.message}`);
        }

        // Reportar error al servidor (opcional)
        this.reportError(errorInfo);
    },

    /**
     * Reportar error al servidor
     * @param {Object} errorInfo - Información del error
     */
    async reportError(errorInfo) {
        try {
            await App.http.post('/error-report', {
                ...errorInfo,
                userAgent: navigator.userAgent,
                url: window.location.href,
                timestamp: new Date().toISOString(),
                userId: App.currentUser?.id
            });
        } catch {
            // Silenciar errores de reporte
        }
    }
};

// ============================================================================
// SISTEMA DE ANALÍTICAS
// ============================================================================

/**
 * Seguimiento de eventos y analíticas
 */
App.analytics = {
    /**
     * Inicializar analíticas
     */
    init() {
        if (!App.features.analytics) return;
        
        this.trackPageView();
        this.bindEvents();
    },

    /**
     * Rastrear vista de página
     */
    trackPageView() {
        this.track('page_view', {
            page: window.location.pathname,
            title: document.title,
            referrer: document.referrer
        });
    },

    /**
     * Vincular eventos automáticos
     */
    bindEvents() {
        // Rastrear clics en botones
        document.addEventListener('click', (e) => {
            const button = e.target.closest('button, a');
            if (button && button.dataset.track) {
                this.track('button_click', {
                    element: button.dataset.track,
                    text: button.textContent.trim(),
                    href: button.href
                });
            }
        });

        // Rastrear envío de formularios
        App.events.addEventListener('formSuccess', (e) => {
            this.track('form_submit', {
                form: e.detail.form.id || e.detail.form.name || 'unknown',
                action: e.detail.form.action
            });
        });
    },

    /**
     * Rastrear evento
     * @param {string} event - Nombre del evento
     * @param {Object} properties - Propiedades del evento
     */
    track(event, properties = {}) {
        const data = {
            event,
            properties: {
                ...properties,
                timestamp: new Date().toISOString(),
                user_type: App.userType,
                user_role: App.userRole,
                viewport: App.state.viewport,
                user_agent: navigator.userAgent
            }
        };

        // Enviar a servidor
        this.send(data);

        // Google Analytics (si está configurado)
        if (typeof gtag !== 'undefined') {
            gtag('event', event, properties);
        }
    },

    /**
     * Enviar datos al servidor
     * @param {Object} data - Datos a enviar
     */
    async send(data) {
        try {
            await App.http.post('/analytics', data);
        } catch (error) {
            console.warn('Error sending analytics:', error);
        }
    }
};

// ============================================================================
// INICIALIZACIÓN DE LA APLICACIÓN
// ============================================================================

/**
 * Inicializar aplicación
 */
App.init = function() {
    console.log(`🚀 Iniciando Ecosistema Emprendimiento v${this.version}`);

    // Verificar soporte básico
    if (!document.querySelector || !window.addEventListener) {
        console.error('Navegador no soportado');
        return;
    }

    // Inicializar módulos core
    this.viewport.init();
    this.theme.init();
    this.notifications.init();
    this.forms.init();
    this.errorHandler.init();
    this.analytics.init();

    // Conectar WebSocket si está habilitado
    if (this.features.realTimeNotifications) {
        this.websocket.connect();
    }

    // Cargar información del usuario actual
    this.loadCurrentUser();

    // Vincular eventos globales
    this.bindGlobalEvents();

    // Inicializar módulos específicos según la página
    this.initPageModules();

    // Marcar como cargado
    document.body.classList.add('app-loaded');
    
    // Emitir evento de inicialización
    this.events.dispatchEvent(new CustomEvent('appInitialized'));

    console.log('✅ Aplicación inicializada correctamente');
};

/**
 * Cargar información del usuario actual
 */
App.loadCurrentUser = async function() {
    try {
        const userElement = document.querySelector('meta[name="current-user"]');
        if (userElement) {
            this.currentUser = JSON.parse(userElement.content);
        } else {
            // Cargar desde API
            const user = await this.http.get('/auth/user');
            this.currentUser = user;
        }
    } catch (error) {
        console.warn('No se pudo cargar información del usuario:', error);
    }
};

/**
 * Vincular eventos globales
 */
App.bindGlobalEvents = function() {
    // Detectar estado online/offline
    window.addEventListener('online', () => {
        this.state.isOnline = true;
        this.notifications.success('Conexión restaurada');
    });

    window.addEventListener('offline', () => {
        this.state.isOnline = false;
        this.notifications.warning('Sin conexión a internet');
    });

    // Detectar visibilidad de la página
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            this.events.dispatchEvent(new CustomEvent('pageVisible'));
        } else {
            this.events.dispatchEvent(new CustomEvent('pageHidden'));
        }
    });

    // Vincular atajos de teclado
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K para búsqueda
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"], .search-input');
            if (searchInput) {
                searchInput.focus();
            }
        }

        // Escape para cerrar modales
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal.show');
            if (modal) {
                const closeBtn = modal.querySelector('.btn-close, [data-bs-dismiss="modal"]');
                if (closeBtn) closeBtn.click();
            }
        }
    });
};

/**
 * Inicializar módulos específicos de página
 */
App.initPageModules = function() {
    const pageType = document.body.dataset.page;
    const userType = this.userType;

    // Módulos por tipo de página
    const moduleMap = {
        'dashboard': ['dashboard', 'charts', 'realtime'],
        'profile': ['profile', 'fileUpload'],
        'chat': ['chat', 'emoji'],
        'calendar': ['calendar', 'scheduling'],
        'projects': ['projects', 'kanban'],
        'analytics': ['analytics', 'charts', 'exports'],
        'settings': ['settings', 'preferences']
    };

    // Módulos por tipo de usuario
    const userModuleMap = {
        'entrepreneur': ['entrepreneurTools', 'projectManagement'],
        'mentor': ['mentorTools', 'scheduling'],
        'admin': ['adminTools', 'userManagement', 'systemMonitoring'],
        'client': ['clientPortal', 'reporting']
    };

    // Cargar módulos específicos
    const pageMmodules = moduleMap[pageType] || [];
    const userModules = userModuleMap[userType] || [];
    const allModules = [...new Set([...pageMmodules, ...userModules])];

    allModules.forEach(moduleName => {
        this.loadModule(moduleName);
    });
};

/**
 * Cargar módulo dinámicamente
 * @param {string} moduleName - Nombre del módulo
 */
App.loadModule = async function(moduleName) {
    if (this.modules[moduleName]) return;

    try {
        // Importar módulo dinámicamente
        const module = await import(`/static/dist/js/modules/${moduleName}.js`);
        this.modules[moduleName] = module.default;
        
        // Inicializar módulo si tiene método init
        if (this.modules[moduleName].init) {
            this.modules[moduleName].init(this);
        }

        console.log(`📦 Módulo ${moduleName} cargado`);
    } catch (error) {
        console.warn(`⚠️ Error cargando módulo ${moduleName}:`, error);
    }
};

// ============================================================================
// AUTO-INICIALIZACIÓN
// ============================================================================

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}

// Exportar para uso global
window.App = App;