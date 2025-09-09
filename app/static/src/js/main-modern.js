/**
 * Main JavaScript for Ecosistema Emprendimiento
 * =============================================
 * 
 * Archivo principal de JavaScript que maneja la inicialización de la aplicación,
 * configuración de bibliotecas, eventos globales y funcionalidades comunes
 * 
 * @author Ecosistema Emprendimiento Team
 * @version 1.0.0
 * @updated 2025
 */

'use strict';

// Modern ES6+ imports
import axios from 'axios';
import { io } from 'socket.io-client';
import Swal from 'sweetalert2';
import Chart from 'chart.js/auto';
import moment from 'moment';
import _ from 'lodash';
import AOS from 'aos';
import { Swiper } from 'swiper';
import 'aos/dist/aos.css';
import 'swiper/css';

// ============================================================================
// CONFIGURACIÓN GLOBAL
// ============================================================================

// Configuración de la aplicación usando const para inmutabilidad
const EcosistemaApp = {
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
    modules: new Map(),
    
    // Event emitter para comunicación entre módulos
    events: new EventTarget(),
    
    // Cache para datos frecuentemente utilizados
    cache: new Map(),
    
    // Queue para acciones diferidas
    actionQueue: []
};

// Expose to window for backward compatibility
window.EcosistemaApp = EcosistemaApp;

// Alias para facilitar el acceso
const App = EcosistemaApp;

// ============================================================================
// UTILIDADES GLOBALES MODERNIZADAS
// ============================================================================

/**
 * Utilidades comunes de la aplicación
 */
App.utils = {
    /**
     * Debounce para optimizar eventos frecuentes
     */
    debounce: (func, wait = 300, immediate = false) => {
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
     */
    throttle: (func, limit = 100) => {
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
     */
    formatNumber: (num, locale = 'es-CO') => {
        if (typeof num !== 'number' || isNaN(num)) return '0';
        return new Intl.NumberFormat(locale).format(num);
    },

    /**
     * Formatear moneda
     */
    formatCurrency: (amount, currency = 'COP', locale = 'es-CO') => {
        if (typeof amount !== 'number' || isNaN(amount)) return '$0';
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },

    /**
     * Formatear fechas relativas usando moderna API
     */
    formatRelativeTime: (date, locale = 'es-CO') => {
        const now = new Date();
        const targetDate = new Date(date);
        const diffInSeconds = Math.floor((now - targetDate) / 1000);
        
        const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
        
        const intervals = [
            { seconds: 31536000, unit: 'year' },
            { seconds: 2592000, unit: 'month' },
            { seconds: 86400, unit: 'day' },
            { seconds: 3600, unit: 'hour' },
            { seconds: 60, unit: 'minute' },
            { seconds: 1, unit: 'second' }
        ];

        for (const interval of intervals) {
            const count = Math.floor(diffInSeconds / interval.seconds);
            if (count >= 1) {
                return rtf.format(-count, interval.unit);
            }
        }
        
        return rtf.format(-diffInSeconds, 'second');
    },

    /**
     * Truncar texto con elipsis
     */
    truncateText: (text, maxLength = 100) => {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    },

    /**
     * Generar UUID v4 usando crypto API moderna
     */
    generateUUID: () => {
        if (crypto?.randomUUID) {
            return crypto.randomUUID();
        }
        // Fallback para navegadores más antiguos
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Validar email
     */
    isValidEmail: (email) => {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },

    /**
     * Validar URL usando moderna API
     */
    isValidUrl: (url) => {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },

    /**
     * Obtener parámetros de la URL usando URLSearchParams
     */
    getUrlParams: () => {
        return Object.fromEntries(new URLSearchParams(window.location.search));
    },

    /**
     * Scroll suave a elemento usando moderna API
     */
    smoothScrollTo: (target, offset = 0) => {
        const element = typeof target === 'string' ? document.querySelector(target) : target;
        if (!element) return;
        
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
            inline: 'nearest'
        });
    },

    /**
     * Copiar al portapapeles usando moderna API
     */
    copyToClipboard: async (text) => {
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
     * Detectar dispositivo móvil usando moderna API
     */
    isMobile: () => {
        return navigator.userAgentData?.mobile || 
               /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    },

    /**
     * Detectar soporte de características
     */
    hasSupport: (feature) => {
        const features = {
            localStorage: typeof Storage !== 'undefined',
            sessionStorage: typeof Storage !== 'undefined',
            webSockets: typeof WebSocket !== 'undefined',
            serviceWorker: 'serviceWorker' in navigator,
            notifications: 'Notification' in window,
            geolocation: 'geolocation' in navigator,
            camera: navigator.mediaDevices?.getUserMedia !== undefined,
            touch: 'ontouchstart' in window,
            webGL: !!window.WebGLRenderingContext,
            webWorkers: typeof Worker !== 'undefined',
            intersectionObserver: 'IntersectionObserver' in window,
            resizeObserver: 'ResizeObserver' in window,
            webShare: navigator.share !== undefined
        };
        
        return features[feature] || false;
    }
};

// ============================================================================
// SISTEMA DE ALMACENAMIENTO MODERNIZADO
// ============================================================================

/**
 * Manejo de almacenamiento local con fallbacks y compresión
 */
App.storage = {
    /**
     * Obtener valor del almacenamiento
     */
    get: (key, defaultValue = null) => {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                return App.cache.get(key) || defaultValue;
            }
            
            const value = localStorage.getItem(`ecosistema_${key}`);
            if (!value) return defaultValue;
            
            try {
                return JSON.parse(value);
            } catch {
                return value; // Si no es JSON, devolver string
            }
        } catch (error) {
            // console.warn('Error getting from storage:', error);
            return defaultValue;
        }
    },

    /**
     * Guardar valor en almacenamiento
     */
    set: (key, value) => {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                App.cache.set(key, value);
                return true;
            }
            
            const serialized = typeof value === 'string' ? value : JSON.stringify(value);
            localStorage.setItem(`ecosistema_${key}`, serialized);
            return true;
        } catch (error) {
            // console.warn('Error setting to storage:', error);
            return false;
        }
    },

    /**
     * Eliminar valor del almacenamiento
     */
    remove: (key) => {
        try {
            if (!App.utils.hasSupport('localStorage')) {
                App.cache.delete(key);
                return true;
            }
            
            localStorage.removeItem(`ecosistema_${key}`);
            return true;
        } catch (error) {
            // console.warn('Error removing from storage:', error);
            return false;
        }
    },

    /**
     * Limpiar todo el almacenamiento de la app
     */
    clear: () => {
        try {
            if (App.utils.hasSupport('localStorage')) {
                Object.keys(localStorage)
                    .filter(key => key.startsWith('ecosistema_'))
                    .forEach(key => localStorage.removeItem(key));
            }
            App.cache.clear();
        } catch (error) {
            // console.warn('Error clearing storage:', error);
        }
    },

    /**
     * Obtener información del almacenamiento
     */
    getInfo: () => {
        if (!App.utils.hasSupport('localStorage')) return null;
        
        const used = new Blob(Object.values(localStorage)).size;
        const available = 5 * 1024 * 1024; // 5MB típico
        
        return {
            used,
            available,
            percentage: (used / available) * 100
        };
    }
};

// ============================================================================
// SISTEMA HTTP MODERNIZADO CON AXIOS
// ============================================================================

/**
 * Cliente HTTP modernizado usando axios
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
     * Configurar axios
     */
    setup: () => {
        // Crear instancia de axios
        const axiosInstance = axios.create({
            baseURL: App.apiUrl,
            timeout: App.http.defaults.timeout,
            headers: App.http.defaults.headers
        });

        // Interceptor de request
        axiosInstance.interceptors.request.use(
            (config) => {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
                if (csrfToken) {
                    config.headers['X-CSRF-Token'] = csrfToken;
                }
                
                const authToken = App.storage.get('authToken');
                if (authToken) {
                    config.headers.Authorization = `Bearer ${authToken}`;
                }
                
                return config;
            },
            (error) => Promise.reject(error)
        );

        // Interceptor de response
        axiosInstance.interceptors.response.use(
            (response) => response.data,
            (error) => {
                if (error.response?.status === 401) {
                    App.events.dispatchEvent(new CustomEvent('unauthorized'));
                }
                return Promise.reject(error);
            }
        );

        App.axios = axiosInstance;
    },

    /**
     * Métodos de conveniencia
     */
    get: (url, config = {}) => App.axios.get(url, config),
    post: (url, data, config = {}) => App.axios.post(url, data, config),
    put: (url, data, config = {}) => App.axios.put(url, data, config),
    patch: (url, data, config = {}) => App.axios.patch(url, data, config),
    delete: (url, config = {}) => App.axios.delete(url, config)
};

// ============================================================================
// SISTEMA DE NOTIFICACIONES MODERNIZADO
// ============================================================================

/**
 * Sistema de notificaciones modernizado con SweetAlert2
 */
App.notifications = {
    /**
     * Mostrar notificación toast
     */
    show: (message, type = 'info', options = {}) => {
        const config = {
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 5000,
            timerProgressBar: true,
            icon: type,
            title: message,
            showClass: {
                popup: 'animate__animated animate__fadeInDown'
            },
            hideClass: {
                popup: 'animate__animated animate__fadeOutUp'
            },
            ...options
        };

        return Swal.fire(config);
    },

    /**
     * Métodos de conveniencia
     */
    success: (message, options = {}) => App.notifications.show(message, 'success', options),
    error: (message, options = {}) => App.notifications.show(message, 'error', options),
    warning: (message, options = {}) => App.notifications.show(message, 'warning', options),
    info: (message, options = {}) => App.notifications.show(message, 'info', options),

    /**
     * Modal de confirmación
     */
    confirm: (title, text, confirmText = 'Sí', cancelText = 'No') => {
        return Swal.fire({
            title,
            text,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: confirmText,
            cancelButtonText: cancelText,
            reverseButtons: true
        });
    },

    /**
     * Notificación del navegador
     */
    browser: async (title, options = {}) => {
        if (!App.utils.hasSupport('notifications')) {
            return App.notifications.info(title);
        }

        if (Notification.permission === 'default') {
            await Notification.requestPermission();
        }

        if (Notification.permission === 'granted') {
            const config = {
                icon: '/static/img/logo-small.png',
                badge: '/static/img/badge.png',
                tag: 'ecosistema-notification',
                ...options
            };

            const notification = new Notification(title, config);
            
            setTimeout(() => {
                notification.close();
            }, 5000);

            return notification;
        }

        return App.notifications.info(title);
    }
};

// ============================================================================
// INICIALIZACIÓN MODERNIZADA
// ============================================================================

/**
 * Inicializar aplicación
 */
App.init = async function() {
    // // console.log(`🚀 Iniciando Ecosistema Emprendimiento v${this.version}`);

    try {
        // Configurar HTTP client
        this.http.setup();
        
        // Inicializar utilidades modernas
        this.initModernFeatures();
        
        // Cargar módulos dinámicamente
        await this.loadCoreModules();
        
        // Conectar WebSocket si está habilitado
        if (this.features.realTimeNotifications) {
            this.initWebSocket();
        }
        
        // Inicializar AOS (Animate on Scroll)
        AOS.init({
            duration: 1000,
            once: true
        });
        
        // Marcar como cargado
        document.body.classList.add('app-loaded');
        
        // Emitir evento de inicialización
        this.events.dispatchEvent(new CustomEvent('appInitialized'));
        
        // // console.log('✅ Aplicación inicializada correctamente');
    } catch (error) {
        // // console.error('❌ Error inicializando aplicación:', error);
        this.notifications.error('Error inicializando la aplicación');
    }
};

/**
 * Inicializar características modernas
 */
App.initModernFeatures = function() {
    // Service Worker
    if ('serviceWorker' in navigator && this.environment === 'production') {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => // // console.log('Service Worker registrado:', registration))
            .catch(error => // console.warn('Error registrando Service Worker:', error));
    }
    
    // Intersection Observer para lazy loading
    if ('IntersectionObserver' in window) {
        const lazyImages = document.querySelectorAll('img[data-src]');
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        lazyImages.forEach(img => imageObserver.observe(img));
    }
    
    // Performance observer
    if ('PerformanceObserver' in window) {
        const perfObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach(entry => {
                if (entry.entryType === 'largest-contentful-paint') {
                    // // console.log('LCP:', entry.startTime);
                }
            });
        });
        
        try {
            perfObserver.observe({ entryTypes: ['largest-contentful-paint'] });
        } catch (error) {
            // console.warn('Performance Observer not supported:', error);
        }
    }
};

/**
 * Cargar módulos core
 */
App.loadCoreModules = async function() {
    const coreModules = ['AuthManager', 'UserProfile', 'SettingsManager'];
    
    const loadPromises = coreModules.map(async (moduleName) => {
        try {
            const module = await import(`./modules/${moduleName}.js`);
            this.modules.set(moduleName, new module.default(this));
            // // console.log(`📦 Módulo ${moduleName} cargado`);
        } catch (error) {
            // console.warn(`⚠️ Error cargando módulo ${moduleName}:`, error);
        }
    });
    
    await Promise.allSettled(loadPromises);
};

/**
 * Inicializar WebSocket
 */
App.initWebSocket = function() {
    if (!App.utils.hasSupport('webSockets')) return;
    
    this.socket = io(this.wsUrl, {
        transports: ['websocket', 'polling']
    });
    
    this.socket.on('connect', () => {
        // // console.log('🔌 WebSocket conectado');
        this.events.dispatchEvent(new CustomEvent('websocketConnected'));
    });
    
    this.socket.on('disconnect', () => {
        // // console.log('🔌 WebSocket desconectado');
        this.events.dispatchEvent(new CustomEvent('websocketDisconnected'));
    });
    
    this.socket.on('notification', (data) => {
        this.notifications.show(data.message, data.type || 'info');
        this.notifications.browser(data.title || 'Nueva notificación', {
            body: data.message
        });
    });
};

// ============================================================================
// AUTO-INICIALIZACIÓN MODERNIZADA
// ============================================================================

// Inicializar cuando el DOM esté listo usando DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}

// Exportar para uso global y módulos
export default App;
window.App = App;