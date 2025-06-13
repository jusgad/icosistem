/**
 * Avatar Component para Ecosistema de Emprendimiento
 * Maneja avatares de usuarios con múltiples fuentes, estados y funcionalidades avanzadas
 * 
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

class AvatarComponent {
    constructor(element, options = {}) {
        this.element = element;
        this.options = {
            // Fuente de imagen
            src: options.src || element.getAttribute('data-src') || null,
            fallbackSrc: options.fallbackSrc || element.getAttribute('data-fallback') || null,
            
            // Información del usuario
            userId: options.userId || element.getAttribute('data-user-id') || null,
            userName: options.userName || element.getAttribute('data-user-name') || '',
            userEmail: options.userEmail || element.getAttribute('data-user-email') || '',
            userRole: options.userRole || element.getAttribute('data-user-role') || 'user',
            
            // Configuración visual
            size: options.size || element.getAttribute('data-size') || 'md',
            shape: options.shape || element.getAttribute('data-shape') || 'circle',
            showBadge: options.showBadge !== false && element.getAttribute('data-show-badge') !== 'false',
            showStatus: options.showStatus !== false && element.getAttribute('data-show-status') !== 'false',
            showTooltip: options.showTooltip !== false && element.getAttribute('data-show-tooltip') !== 'false',
            
            // Estados
            status: options.status || element.getAttribute('data-status') || 'offline',
            isOnline: options.isOnline || element.getAttribute('data-online') === 'true',
            lastSeen: options.lastSeen || element.getAttribute('data-last-seen') || null,
            
            // Configuración avanzada
            lazyLoad: options.lazyLoad !== false,
            useGravatar: options.useGravatar !== false,
            gravatarDefault: options.gravatarDefault || 'identicon',
            allowUpload: options.allowUpload || false,
            showInitials: options.showInitials !== false,
            backgroundColor: options.backgroundColor || null,
            
            // Callbacks
            onLoad: options.onLoad || null,
            onError: options.onError || null,
            onClick: options.onClick || null,
            onUpload: options.onUpload || null,
            
            // API endpoints
            uploadEndpoint: options.uploadEndpoint || '/api/v1/users/avatar',
            statusEndpoint: options.statusEndpoint || '/api/v1/users/status'
        };
        
        // Estados internos
        this.isLoaded = false;
        this.isError = false;
        this.currentSrc = null;
        this.observer = null;
        this.statusPoller = null;
        
        // Configuración de tamaños
        this.sizeConfig = {
            xs: { size: 24, fontSize: 10 },
            sm: { size: 32, fontSize: 12 },
            md: { size: 48, fontSize: 16 },
            lg: { size: 64, fontSize: 20 },
            xl: { size: 80, fontSize: 24 },
            '2xl': { size: 96, fontSize: 28 },
            '3xl': { size: 128, fontSize: 32 }
        };
        
        // Configuración de roles y badges
        this.roleConfig = {
            admin: {
                badge: 'fas fa-crown',
                color: '#ff6b35',
                label: 'Administrador'
            },
            entrepreneur: {
                badge: 'fas fa-lightbulb',
                color: '#4ecdc4',
                label: 'Emprendedor'
            },
            ally: {
                badge: 'fas fa-handshake',
                color: '#45b7d1',
                label: 'Aliado/Mentor'
            },
            client: {
                badge: 'fas fa-eye',
                color: '#96ceb4',
                label: 'Cliente'
            },
            organization: {
                badge: 'fas fa-building',
                color: '#feca57',
                label: 'Organización'
            }
        };
        
        // Estados de presencia
        this.statusConfig = {
            online: { color: '#10b981', label: 'En línea' },
            away: { color: '#f59e0b', label: 'Ausente' },
            busy: { color: '#ef4444', label: 'Ocupado' },
            offline: { color: '#6b7280', label: 'Desconectado' }
        };
        
        this.init();
    }
    
    /**
     * Inicializa el componente
     */
    init() {
        this.setupElement();
        this.generateAvatar();
        this.bindEvents();
        this.setupLazyLoading();
        this.setupStatusPolling();
        
        // Disparar evento de inicialización
        this.dispatchEvent('avatar:init');
    }
    
    /**
     * Configura el elemento base
     */
    setupElement() {
        this.element.classList.add('avatar-component');
        this.element.classList.add(`avatar-${this.options.size}`);
        this.element.classList.add(`avatar-${this.options.shape}`);
        this.element.classList.add(`avatar-role-${this.options.userRole}`);
        
        // Agregar atributos de accesibilidad
        this.element.setAttribute('role', 'img');
        this.element.setAttribute('tabindex', this.options.onClick ? '0' : '-1');
        
        // Configurar tooltip
        if (this.options.showTooltip) {
            this.setupTooltip();
        }
    }
    
    /**
     * Genera el contenido del avatar
     */
    generateAvatar() {
        const avatarHTML = `
            <div class="avatar-wrapper">
                ${this.generateImageContent()}
                ${this.options.showStatus ? this.generateStatusIndicator() : ''}
                ${this.options.showBadge ? this.generateRoleBadge() : ''}
                ${this.options.allowUpload ? this.generateUploadOverlay() : ''}
            </div>
            ${this.options.showTooltip ? this.generateTooltip() : ''}
        `;
        
        this.element.innerHTML = avatarHTML;
    }
    
    /**
     * Genera el contenido de la imagen
     */
    generateImageContent() {
        const sizeInfo = this.sizeConfig[this.options.size];
        
        return `
            <div class="avatar-image-container" style="width: ${sizeInfo.size}px; height: ${sizeInfo.size}px;">
                <div class="avatar-placeholder" style="font-size: ${sizeInfo.fontSize}px;">
                    ${this.generateInitials()}
                </div>
                <img class="avatar-image" 
                     style="display: none;"
                     alt="${this.getAltText()}"
                     onload="this.parentElement.parentElement.parentElement._avatarInstance.handleImageLoad()"
                     onerror="this.parentElement.parentElement.parentElement._avatarInstance.handleImageError()">
                <div class="avatar-loading" style="display: none;">
                    <i class="fas fa-spinner fa-spin"></i>
                </div>
            </div>
        `;
    }
    
    /**
     * Genera las iniciales del usuario
     */
    generateInitials() {
        if (!this.options.showInitials || !this.options.userName) {
            return '<i class="fas fa-user"></i>';
        }
        
        const names = this.options.userName.trim().split(' ');
        let initials = '';
        
        if (names.length >= 2) {
            initials = names[0].charAt(0) + names[names.length - 1].charAt(0);
        } else if (names.length === 1) {
            initials = names[0].charAt(0) + (names[0].charAt(1) || '');
        }
        
        return initials.toUpperCase() || '<i class="fas fa-user"></i>';
    }
    
    /**
     * Genera indicador de estado
     */
    generateStatusIndicator() {
        const statusInfo = this.statusConfig[this.options.status] || this.statusConfig.offline;
        
        return `
            <div class="avatar-status" 
                 style="background-color: ${statusInfo.color};"
                 title="${statusInfo.label}"
                 data-status="${this.options.status}">
            </div>
        `;
    }
    
    /**
     * Genera badge de rol
     */
    generateRoleBadge() {
        const roleInfo = this.roleConfig[this.options.userRole];
        
        if (!roleInfo) return '';
        
        return `
            <div class="avatar-badge" 
                 style="background-color: ${roleInfo.color};"
                 title="${roleInfo.label}"
                 data-role="${this.options.userRole}">
                <i class="${roleInfo.badge}"></i>
            </div>
        `;
    }
    
    /**
     * Genera overlay de upload
     */
    generateUploadOverlay() {
        return `
            <div class="avatar-upload-overlay">
                <div class="avatar-upload-content">
                    <i class="fas fa-camera"></i>
                    <span>Cambiar</span>
                </div>
                <input type="file" 
                       class="avatar-upload-input" 
                       accept="image/*" 
                       style="display: none;">
            </div>
        `;
    }
    
    /**
     * Genera tooltip
     */
    generateTooltip() {
        const lastSeenText = this.options.lastSeen ? 
            this.formatLastSeen(this.options.lastSeen) : '';
        
        return `
            <div class="avatar-tooltip" role="tooltip">
                <div class="avatar-tooltip-content">
                    <div class="tooltip-name">${this.options.userName}</div>
                    ${this.options.userEmail ? `<div class="tooltip-email">${this.options.userEmail}</div>` : ''}
                    <div class="tooltip-role">${this.roleConfig[this.options.userRole]?.label || 'Usuario'}</div>
                    <div class="tooltip-status">
                        <span class="status-indicator" style="background-color: ${this.statusConfig[this.options.status]?.color}"></span>
                        ${this.statusConfig[this.options.status]?.label}
                        ${lastSeenText ? `<span class="last-seen">${lastSeenText}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Configura tooltip
     */
    setupTooltip() {
        let tooltipTimeout;
        
        this.element.addEventListener('mouseenter', () => {
            clearTimeout(tooltipTimeout);
            tooltipTimeout = setTimeout(() => {
                this.showTooltip();
            }, 500);
        });
        
        this.element.addEventListener('mouseleave', () => {
            clearTimeout(tooltipTimeout);
            this.hideTooltip();
        });
    }
    
    /**
     * Muestra tooltip
     */
    showTooltip() {
        const tooltip = this.element.querySelector('.avatar-tooltip');
        if (tooltip) {
            tooltip.classList.add('show');
            this.positionTooltip(tooltip);
        }
    }
    
    /**
     * Oculta tooltip
     */
    hideTooltip() {
        const tooltip = this.element.querySelector('.avatar-tooltip');
        if (tooltip) {
            tooltip.classList.remove('show');
        }
    }
    
    /**
     * Posiciona tooltip
     */
    positionTooltip(tooltip) {
        const rect = this.element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        // Posición por defecto: arriba y centrado
        let top = rect.top - tooltipRect.height - 10;
        let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
        
        // Ajustar si se sale de la ventana
        if (top < 10) {
            top = rect.bottom + 10;
            tooltip.classList.add('tooltip-bottom');
        }
        
        if (left < 10) {
            left = 10;
        } else if (left + tooltipRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tooltipRect.width - 10;
        }
        
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }
    
    /**
     * Vincula eventos
     */
    bindEvents() {
        // Guardar referencia para acceso desde eventos HTML
        this.element._avatarInstance = this;
        
        // Click en avatar
        if (this.options.onClick) {
            this.element.addEventListener('click', (e) => {
                e.preventDefault();
                this.options.onClick(this.getUserData(), e);
            });
            
            // Navegación por teclado
            this.element.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.options.onClick(this.getUserData(), e);
                }
            });
        }
        
        // Upload de imagen
        if (this.options.allowUpload) {
            const uploadOverlay = this.element.querySelector('.avatar-upload-overlay');
            const uploadInput = this.element.querySelector('.avatar-upload-input');
            
            if (uploadOverlay && uploadInput) {
                uploadOverlay.addEventListener('click', () => {
                    uploadInput.click();
                });
                
                uploadInput.addEventListener('change', (e) => {
                    this.handleFileUpload(e.target.files[0]);
                });
            }
        }
        
        // Eventos de redimensionado para tooltip
        if (this.options.showTooltip) {
            window.addEventListener('resize', () => {
                this.hideTooltip();
            });
        }
    }
    
    /**
     * Configura lazy loading
     */
    setupLazyLoading() {
        if (!this.options.lazyLoad || !('IntersectionObserver' in window)) {
            this.loadImage();
            return;
        }
        
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadImage();
                    this.observer.unobserve(this.element);
                }
            });
        }, {
            rootMargin: '50px'
        });
        
        this.observer.observe(this.element);
    }
    
    /**
     * Carga la imagen
     */
    loadImage() {
        const img = this.element.querySelector('.avatar-image');
        const loading = this.element.querySelector('.avatar-loading');
        
        if (!img) return;
        
        // Mostrar loading
        if (loading) {
            loading.style.display = 'flex';
        }
        
        // Determinar fuente de imagen
        const imageSrc = this.determineImageSource();
        
        if (imageSrc) {
            this.currentSrc = imageSrc;
            img.src = imageSrc;
        } else {
            this.handleImageError();
        }
    }
    
    /**
     * Determina la fuente de imagen a usar
     */
    determineImageSource() {
        // 1. Imagen específica proporcionada
        if (this.options.src) {
            return this.options.src;
        }
        
        // 2. Gravatar si está habilitado y hay email
        if (this.options.useGravatar && this.options.userEmail) {
            return this.generateGravatarUrl();
        }
        
        // 3. Imagen de fallback
        if (this.options.fallbackSrc) {
            return this.options.fallbackSrc;
        }
        
        // 4. Avatar basado en iniciales/ID
        if (this.options.userId) {
            return this.generateIdenticon();
        }
        
        return null;
    }
    
    /**
     * Genera URL de Gravatar
     */
    generateGravatarUrl() {
        if (!this.options.userEmail) return null;
        
        const email = this.options.userEmail.toLowerCase().trim();
        const hash = this.md5(email);
        const size = this.sizeConfig[this.options.size].size * 2; // Retina
        
        return `https://www.gravatar.com/avatar/${hash}?s=${size}&d=${this.options.gravatarDefault}&r=pg`;
    }
    
    /**
     * Genera identicon
     */
    generateIdenticon() {
        // Usar servicio de identicon o generar localmente
        const seed = this.options.userId || this.options.userName || 'default';
        const size = this.sizeConfig[this.options.size].size;
        
        return `https://avatars.dicebear.com/api/identicon/${encodeURIComponent(seed)}.svg?size=${size}`;
    }
    
    /**
     * Maneja carga exitosa de imagen
     */
    handleImageLoad() {
        const img = this.element.querySelector('.avatar-image');
        const placeholder = this.element.querySelector('.avatar-placeholder');
        const loading = this.element.querySelector('.avatar-loading');
        
        if (img && placeholder) {
            img.style.display = 'block';
            placeholder.style.display = 'none';
            this.isLoaded = true;
            this.isError = false;
        }
        
        if (loading) {
            loading.style.display = 'none';
        }
        
        this.dispatchEvent('avatar:load', { src: this.currentSrc });
        
        if (this.options.onLoad) {
            this.options.onLoad(this.currentSrc);
        }
    }
    
    /**
     * Maneja error de carga de imagen
     */
    handleImageError() {
        const img = this.element.querySelector('.avatar-image');
        const placeholder = this.element.querySelector('.avatar-placeholder');
        const loading = this.element.querySelector('.avatar-loading');
        
        if (img && placeholder) {
            img.style.display = 'none';
            placeholder.style.display = 'flex';
            this.isError = true;
        }
        
        if (loading) {
            loading.style.display = 'none';
        }
        
        // Intentar con fallback si no se ha intentado
        if (this.currentSrc !== this.options.fallbackSrc && this.options.fallbackSrc) {
            this.currentSrc = this.options.fallbackSrc;
            img.src = this.options.fallbackSrc;
            return;
        }
        
        this.dispatchEvent('avatar:error', { src: this.currentSrc });
        
        if (this.options.onError) {
            this.options.onError(this.currentSrc);
        }
    }
    
    /**
     * Maneja upload de archivo
     */
    async handleFileUpload(file) {
        if (!file) return;
        
        // Validar archivo
        if (!file.type.startsWith('image/')) {
            this.showError('Por favor selecciona una imagen válida');
            return;
        }
        
        if (file.size > 5 * 1024 * 1024) { // 5MB
            this.showError('La imagen debe ser menor a 5MB');
            return;
        }
        
        try {
            this.showLoading();
            
            // Crear FormData
            const formData = new FormData();
            formData.append('avatar', file);
            formData.append('userId', this.options.userId);
            
            // Enviar archivo
            const response = await fetch(this.options.uploadEndpoint, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error('Error al subir la imagen');
            }
            
            const result = await response.json();
            
            // Actualizar imagen
            this.updateImage(result.avatarUrl);
            
            this.dispatchEvent('avatar:upload', { file, result });
            
            if (this.options.onUpload) {
                this.options.onUpload(file, result);
            }
            
        } catch (error) {
            console.error('Error uploading avatar:', error);
            this.showError('Error al subir la imagen');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Configura polling de estado
     */
    setupStatusPolling() {
        if (!this.options.showStatus || !this.options.userId) return;
        
        // Polling cada 30 segundos
        this.statusPoller = setInterval(() => {
            this.updateStatus();
        }, 30000);
        
        // Actualizar inmediatamente
        this.updateStatus();
    }
    
    /**
     * Actualiza estado del usuario
     */
    async updateStatus() {
        if (!this.options.statusEndpoint || !this.options.userId) return;
        
        try {
            const response = await fetch(`${this.options.statusEndpoint}/${this.options.userId}`);
            
            if (response.ok) {
                const data = await response.json();
                this.setStatus(data.status, data.lastSeen);
            }
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }
    
    /**
     * Establece estado del usuario
     */
    setStatus(status, lastSeen = null) {
        this.options.status = status;
        this.options.lastSeen = lastSeen;
        
        const statusElement = this.element.querySelector('.avatar-status');
        if (statusElement) {
            const statusInfo = this.statusConfig[status] || this.statusConfig.offline;
            statusElement.style.backgroundColor = statusInfo.color;
            statusElement.setAttribute('title', statusInfo.label);
            statusElement.setAttribute('data-status', status);
        }
        
        // Actualizar tooltip si existe
        if (this.options.showTooltip) {
            this.updateTooltip();
        }
        
        this.dispatchEvent('avatar:status-change', { status, lastSeen });
    }
    
    /**
     * Actualiza imagen
     */
    updateImage(src) {
        this.options.src = src;
        this.currentSrc = src;
        this.loadImage();
    }
    
    /**
     * Actualiza información del usuario
     */
    updateUser(userData) {
        Object.assign(this.options, userData);
        this.generateAvatar();
        this.setupTooltip();
    }
    
    /**
     * Actualiza tooltip
     */
    updateTooltip() {
        const tooltip = this.element.querySelector('.avatar-tooltip');
        if (tooltip) {
            const tooltipContent = this.generateTooltip();
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = tooltipContent;
            tooltip.replaceWith(tempDiv.firstElementChild);
        }
    }
    
    /**
     * Muestra loading
     */
    showLoading() {
        const loading = this.element.querySelector('.avatar-loading');
        if (loading) {
            loading.style.display = 'flex';
        }
    }
    
    /**
     * Oculta loading
     */
    hideLoading() {
        const loading = this.element.querySelector('.avatar-loading');
        if (loading) {
            loading.style.display = 'none';
        }
    }
    
    /**
     * Muestra error
     */
    showError(message) {
        // Implementar sistema de notificaciones
        console.error('Avatar Error:', message);
        
        // Trigger evento para sistema de notificaciones externo
        this.dispatchEvent('avatar:error-message', { message });
    }
    
    /**
     * Obtiene datos del usuario
     */
    getUserData() {
        return {
            userId: this.options.userId,
            userName: this.options.userName,
            userEmail: this.options.userEmail,
            userRole: this.options.userRole,
            status: this.options.status,
            lastSeen: this.options.lastSeen
        };
    }
    
    /**
     * Obtiene texto alternativo para la imagen
     */
    getAltText() {
        return `Avatar de ${this.options.userName || 'Usuario'}`;
    }
    
    /**
     * Formatea última conexión
     */
    formatLastSeen(lastSeen) {
        if (!lastSeen) return '';
        
        const date = new Date(lastSeen);
        const now = new Date();
        const diff = now - date;
        
        const minutes = Math.floor(diff / (1000 * 60));
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (minutes < 1) return 'Ahora';
        if (minutes < 60) return `Hace ${minutes}m`;
        if (hours < 24) return `Hace ${hours}h`;
        if (days < 7) return `Hace ${days}d`;
        
        return date.toLocaleDateString();
    }
    
    /**
     * Genera hash MD5 (implementación simple)
     */
    md5(string) {
        // Implementación básica de MD5 o usar librería externa
        // Para producción, usar crypto-js o similar
        function md5cycle(x, k) {
            var a = x[0], b = x[1], c = x[2], d = x[3];
            a = ff(a, b, c, d, k[0], 7, -680876936);
            d = ff(d, a, b, c, k[1], 12, -389564586);
            c = ff(c, d, a, b, k[2], 17, 606105819);
            b = ff(b, c, d, a, k[3], 22, -1044525330);
            // ... implementación completa del MD5
            return [a, b, c, d];
        }
        
        // Implementación simplificada para el ejemplo
        // En producción usar una librería como crypto-js
        let hash = 0;
        for (let i = 0; i < string.length; i++) {
            const char = string.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16);
    }
    
    /**
     * Despacha evento personalizado
     */
    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(eventName, {
            detail: { ...detail, instance: this },
            bubbles: true,
            cancelable: true
        });
        
        this.element.dispatchEvent(event);
        return event;
    }
    
    /**
     * Destruye el componente
     */
    destroy() {
        // Limpiar observers
        if (this.observer) {
            this.observer.disconnect();
        }
        
        // Limpiar polling
        if (this.statusPoller) {
            clearInterval(this.statusPoller);
        }
        
        // Limpiar referencias
        if (this.element._avatarInstance) {
            delete this.element._avatarInstance;
        }
        
        // Limpiar contenido
        this.element.innerHTML = '';
        
        this.dispatchEvent('avatar:destroy');
    }
}

// Inicialización automática
document.addEventListener('DOMContentLoaded', () => {
    // Buscar todos los elementos avatar
    const avatarElements = document.querySelectorAll('[data-avatar]');
    
    avatarElements.forEach(element => {
        // Obtener configuración desde atributos data
        const options = {
            src: element.getAttribute('data-src'),
            fallbackSrc: element.getAttribute('data-fallback'),
            userId: element.getAttribute('data-user-id'),
            userName: element.getAttribute('data-user-name'),
            userEmail: element.getAttribute('data-user-email'),
            userRole: element.getAttribute('data-user-role'),
            size: element.getAttribute('data-size'),
            shape: element.getAttribute('data-shape'),
            status: element.getAttribute('data-status'),
            showBadge: element.getAttribute('data-show-badge') !== 'false',
            showStatus: element.getAttribute('data-show-status') !== 'false',
            showTooltip: element.getAttribute('data-show-tooltip') !== 'false',
            allowUpload: element.getAttribute('data-allow-upload') === 'true',
            useGravatar: element.getAttribute('data-use-gravatar') !== 'false'
        };
        
        // Crear instancia
        const avatar = new AvatarComponent(element, options);
        
        // Guardar referencia
        element._avatarInstance = avatar;
    });
});

// Funciones de utilidad globales
window.AvatarUtils = {
    /**
     * Crea avatar programáticamente
     */
    create: (container, options) => {
        return new AvatarComponent(container, options);
    },
    
    /**
     * Actualiza múltiples avatares
     */
    updateMultiple: (selector, userData) => {
        document.querySelectorAll(selector).forEach(element => {
            if (element._avatarInstance) {
                element._avatarInstance.updateUser(userData);
            }
        });
    },
    
    /**
     * Actualiza estado en múltiples avatares
     */
    updateStatus: (userId, status, lastSeen) => {
        document.querySelectorAll(`[data-user-id="${userId}"]`).forEach(element => {
            if (element._avatarInstance) {
                element._avatarInstance.setStatus(status, lastSeen);
            }
        });
    }
};

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AvatarComponent;
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
    window.AvatarComponent = AvatarComponent;
}