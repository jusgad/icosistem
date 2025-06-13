/**
 * Tooltip Component para Ecosistema de Emprendimiento
 * Sistema avanzado de tooltips con posicionamiento inteligente, múltiples triggers y accesibilidad completa
 * 
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

class TooltipComponent {
    constructor(element, options = {}) {
        this.element = element;
        this.options = {
            // Contenido del tooltip
            content: options.content || element.getAttribute('data-tooltip') || element.getAttribute('title') || '',
            html: options.html || element.getAttribute('data-tooltip-html') === 'true',
            template: options.template || null,
            
            // Posicionamiento
            placement: options.placement || element.getAttribute('data-placement') || 'top',
            offset: options.offset || parseInt(element.getAttribute('data-offset')) || 10,
            boundary: options.boundary || 'viewport',
            flip: options.flip !== false && element.getAttribute('data-flip') !== 'false',
            fallbackPlacements: options.fallbackPlacements || ['top', 'right', 'bottom', 'left'],
            
            // Triggers
            trigger: options.trigger || element.getAttribute('data-trigger') || 'hover focus',
            delay: {
                show: options.delayShow || parseInt(element.getAttribute('data-delay-show')) || 100,
                hide: options.delayHide || parseInt(element.getAttribute('data-delay-hide')) || 100
            },
            
            // Comportamiento
            animation: options.animation !== false && element.getAttribute('data-animation') !== 'false',
            duration: options.duration || parseInt(element.getAttribute('data-duration')) || 200,
            interactive: options.interactive || element.getAttribute('data-interactive') === 'true',
            hideOnClick: options.hideOnClick !== false && element.getAttribute('data-hide-on-click') !== 'false',
            followCursor: options.followCursor || element.getAttribute('data-follow-cursor') === 'true',
            
            // Estilo y tema
            theme: options.theme || element.getAttribute('data-theme') || 'default',
            variant: options.variant || element.getAttribute('data-variant') || 'dark',
            size: options.size || element.getAttribute('data-size') || 'medium',
            maxWidth: options.maxWidth || element.getAttribute('data-max-width') || '320px',
            
            // Contenido dinámico
            ajax: options.ajax || null,
            onShow: options.onShow || null,
            onShown: options.onShown || null,
            onHide: options.onHide || null,
            onHidden: options.onHidden || null,
            
            // Configuraciones avanzadas
            zIndex: options.zIndex || 9999,
            appendTo: options.appendTo || document.body,
            allowHTML: options.allowHTML || false,
            sanitize: options.sanitize !== false,
            
            // Accesibilidad
            aria: options.aria !== false,
            role: options.role || 'tooltip'
        };
        
        // Estados internos
        this.isVisible = false;
        this.isAnimating = false;
        this.tooltipElement = null;
        this.arrowElement = null;
        this.timeouts = {};
        this.triggers = [];
        this.boundEvents = {};
        
        // Configuración de temas
        this.themes = {
            default: {
                backgroundColor: '#333',
                color: '#fff',
                borderRadius: '6px',
                fontSize: '14px'
            },
            light: {
                backgroundColor: '#fff',
                color: '#333',
                border: '1px solid #ddd',
                borderRadius: '6px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
            },
            success: {
                backgroundColor: '#10b981',
                color: '#fff',
                borderRadius: '6px'
            },
            warning: {
                backgroundColor: '#f59e0b',
                color: '#fff',
                borderRadius: '6px'
            },
            error: {
                backgroundColor: '#ef4444',
                color: '#fff',
                borderRadius: '6px'
            },
            info: {
                backgroundColor: '#3b82f6',
                color: '#fff',
                borderRadius: '6px'
            },
            // Temas específicos del ecosistema
            entrepreneur: {
                backgroundColor: '#4ecdc4',
                color: '#fff',
                borderRadius: '8px'
            },
            ally: {
                backgroundColor: '#45b7d1',
                color: '#fff',
                borderRadius: '8px'
            },
            admin: {
                backgroundColor: '#ff6b35',
                color: '#fff',
                borderRadius: '8px'
            },
            client: {
                backgroundColor: '#96ceb4',
                color: '#333',
                borderRadius: '8px'
            }
        };
        
        // Configuración de tamaños
        this.sizes = {
            small: {
                fontSize: '12px',
                padding: '4px 8px',
                maxWidth: '200px'
            },
            medium: {
                fontSize: '14px',
                padding: '8px 12px',
                maxWidth: '320px'
            },
            large: {
                fontSize: '16px',
                padding: '12px 16px',
                maxWidth: '400px'
            }
        };
        
        this.init();
    }
    
    /**
     * Inicializa el componente
     */
    init() {
        if (!this.options.content && !this.options.ajax && !this.options.template) {
            console.warn('Tooltip: No hay contenido para mostrar');
            return;
        }
        
        // Procesar triggers
        this.processTriggers();
        
        // Configurar eventos
        this.bindEvents();
        
        // Crear ID único si no existe
        if (!this.element.id) {
            this.element.id = `tooltip-trigger-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        
        // Configurar atributos de accesibilidad
        this.setupAccessibility();
        
        // Guardar referencia
        this.element._tooltipInstance = this;
        
        // Disparar evento de inicialización
        this.dispatchEvent('tooltip:init');
    }
    
    /**
     * Procesa los triggers configurados
     */
    processTriggers() {
        this.triggers = this.options.trigger.split(' ').filter(trigger => trigger);
        
        // Validar triggers
        const validTriggers = ['hover', 'focus', 'click', 'manual'];
        this.triggers = this.triggers.filter(trigger => validTriggers.includes(trigger));
        
        if (this.triggers.length === 0) {
            this.triggers = ['hover'];
        }
    }
    
    /**
     * Vincula eventos según los triggers configurados
     */
    bindEvents() {
        // Hover events
        if (this.triggers.includes('hover')) {
            this.boundEvents.mouseenter = () => this.show();
            this.boundEvents.mouseleave = () => this.hide();
            
            this.element.addEventListener('mouseenter', this.boundEvents.mouseenter);
            this.element.addEventListener('mouseleave', this.boundEvents.mouseleave);
            
            // Follow cursor si está habilitado
            if (this.options.followCursor) {
                this.boundEvents.mousemove = (e) => this.updateCursorPosition(e);
                this.element.addEventListener('mousemove', this.boundEvents.mousemove);
            }
        }
        
        // Focus events
        if (this.triggers.includes('focus')) {
            this.boundEvents.focusin = () => this.show();
            this.boundEvents.focusout = () => this.hide();
            
            this.element.addEventListener('focusin', this.boundEvents.focusin);
            this.element.addEventListener('focusout', this.boundEvents.focusout);
        }
        
        // Click events
        if (this.triggers.includes('click')) {
            this.boundEvents.click = (e) => {
                e.preventDefault();
                this.toggle();
            };
            
            this.element.addEventListener('click', this.boundEvents.click);
        }
        
        // Global events
        this.boundEvents.documentClick = (e) => {
            if (this.isVisible && this.options.hideOnClick && 
                !this.element.contains(e.target) && 
                (!this.tooltipElement || !this.tooltipElement.contains(e.target))) {
                this.hide();
            }
        };
        
        this.boundEvents.keydown = (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
                this.element.focus();
            }
        };
        
        this.boundEvents.resize = () => {
            if (this.isVisible) {
                this.updatePosition();
            }
        };
        
        this.boundEvents.scroll = () => {
            if (this.isVisible) {
                this.updatePosition();
            }
        };
        
        document.addEventListener('click', this.boundEvents.documentClick);
        document.addEventListener('keydown', this.boundEvents.keydown);
        window.addEventListener('resize', this.boundEvents.resize);
        window.addEventListener('scroll', this.boundEvents.scroll, true);
    }
    
    /**
     * Configura atributos de accesibilidad
     */
    setupAccessibility() {
        if (!this.options.aria) return;
        
        // Generar ID único para el tooltip
        this.tooltipId = `tooltip-${this.element.id}`;
        
        // Configurar ARIA attributes
        this.element.setAttribute('aria-describedby', this.tooltipId);
        
        // Si el elemento no es focusable y usa click trigger, hacerlo focusable
        if (this.triggers.includes('click') && !this.element.hasAttribute('tabindex')) {
            const focusableElements = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
            if (!focusableElements.includes(this.element.tagName)) {
                this.element.setAttribute('tabindex', '0');
            }
        }
    }
    
    /**
     * Crea el elemento tooltip
     */
    createTooltipElement() {
        if (this.tooltipElement) return;
        
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.className = this.getTooltipClasses();
        this.tooltipElement.id = this.tooltipId;
        this.tooltipElement.setAttribute('role', this.options.role);
        this.tooltipElement.style.cssText = this.getTooltipStyles();
        
        // Crear arrow
        this.arrowElement = document.createElement('div');
        this.arrowElement.className = 'tooltip-arrow';
        this.tooltipElement.appendChild(this.arrowElement);
        
        // Crear contenido
        this.contentElement = document.createElement('div');
        this.contentElement.className = 'tooltip-content';
        this.tooltipElement.appendChild(this.contentElement);
        
        // Agregar al DOM
        this.options.appendTo.appendChild(this.tooltipElement);
        
        // Configurar eventos del tooltip si es interactivo
        if (this.options.interactive) {
            this.setupInteractiveEvents();
        }
    }
    
    /**
     * Obtiene las clases CSS del tooltip
     */
    getTooltipClasses() {
        const classes = [
            'tooltip-component',
            `tooltip-${this.options.theme}`,
            `tooltip-${this.options.variant}`,
            `tooltip-${this.options.size}`,
            `tooltip-placement-${this.options.placement}`
        ];
        
        if (this.options.animation) {
            classes.push('tooltip-animated');
        }
        
        return classes.join(' ');
    }
    
    /**
     * Obtiene los estilos inline del tooltip
     */
    getTooltipStyles() {
        const theme = this.themes[this.options.theme] || this.themes.default;
        const size = this.sizes[this.options.size] || this.sizes.medium;
        
        const styles = {
            position: 'absolute',
            zIndex: this.options.zIndex,
            maxWidth: this.options.maxWidth || size.maxWidth,
            opacity: '0',
            visibility: 'hidden',
            pointerEvents: this.options.interactive ? 'auto' : 'none',
            transition: this.options.animation ? `opacity ${this.options.duration}ms ease, visibility ${this.options.duration}ms ease` : 'none',
            ...theme,
            ...size
        };
        
        return Object.entries(styles)
            .map(([key, value]) => `${this.camelToKebab(key)}: ${value}`)
            .join('; ');
    }
    
    /**
     * Configura eventos para tooltips interactivos
     */
    setupInteractiveEvents() {
        if (!this.tooltipElement) return;
        
        this.tooltipElement.addEventListener('mouseenter', () => {
            this.clearTimeout('hide');
        });
        
        this.tooltipElement.addEventListener('mouseleave', () => {
            if (this.triggers.includes('hover')) {
                this.hide();
            }
        });
    }
    
    /**
     * Muestra el tooltip
     */
    async show() {
        if (this.isVisible || this.isAnimating) return;
        
        // Disparar evento antes de mostrar
        const event = this.dispatchEvent('tooltip:show');
        if (event.defaultPrevented) return;
        
        // Callback onShow
        if (this.options.onShow) {
            const result = await this.options.onShow(this);
            if (result === false) return;
        }
        
        this.clearTimeout('hide');
        
        // Crear tooltip si no existe
        this.createTooltipElement();
        
        // Cargar contenido
        await this.loadContent();
        
        // Aplicar delay si está configurado
        if (this.options.delay.show > 0) {
            this.timeouts.show = setTimeout(() => {
                this.showTooltip();
            }, this.options.delay.show);
        } else {
            this.showTooltip();
        }
    }
    
    /**
     * Muestra el tooltip inmediatamente
     */
    showTooltip() {
        if (!this.tooltipElement) return;
        
        this.isAnimating = true;
        
        // Posicionar tooltip
        this.updatePosition();
        
        // Mostrar con animación
        this.tooltipElement.style.visibility = 'visible';
        this.tooltipElement.style.opacity = '1';
        
        this.isVisible = true;
        
        // Finalizar animación
        if (this.options.animation) {
            setTimeout(() => {
                this.isAnimating = false;
                this.dispatchEvent('tooltip:shown');
                
                if (this.options.onShown) {
                    this.options.onShown(this);
                }
            }, this.options.duration);
        } else {
            this.isAnimating = false;
            this.dispatchEvent('tooltip:shown');
            
            if (this.options.onShown) {
                this.options.onShown(this);
            }
        }
    }
    
    /**
     * Oculta el tooltip
     */
    hide() {
        if (!this.isVisible || this.isAnimating) return;
        
        // Disparar evento antes de ocultar
        const event = this.dispatchEvent('tooltip:hide');
        if (event.defaultPrevented) return;
        
        // Callback onHide
        if (this.options.onHide) {
            const result = this.options.onHide(this);
            if (result === false) return;
        }
        
        this.clearTimeout('show');
        
        // Aplicar delay si está configurado
        if (this.options.delay.hide > 0) {
            this.timeouts.hide = setTimeout(() => {
                this.hideTooltip();
            }, this.options.delay.hide);
        } else {
            this.hideTooltip();
        }
    }
    
    /**
     * Oculta el tooltip inmediatamente
     */
    hideTooltip() {
        if (!this.tooltipElement || !this.isVisible) return;
        
        this.isAnimating = true;
        
        // Ocultar con animación
        this.tooltipElement.style.opacity = '0';
        this.tooltipElement.style.visibility = 'hidden';
        
        this.isVisible = false;
        
        // Finalizar animación
        if (this.options.animation) {
            setTimeout(() => {
                this.isAnimating = false;
                this.dispatchEvent('tooltip:hidden');
                
                if (this.options.onHidden) {
                    this.options.onHidden(this);
                }
            }, this.options.duration);
        } else {
            this.isAnimating = false;
            this.dispatchEvent('tooltip:hidden');
            
            if (this.options.onHidden) {
                this.options.onHidden(this);
            }
        }
    }
    
    /**
     * Alterna la visibilidad del tooltip
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }
    
    /**
     * Carga el contenido del tooltip
     */
    async loadContent() {
        let content = '';
        
        // Contenido AJAX
        if (this.options.ajax) {
            try {
                content = await this.loadAjaxContent();
            } catch (error) {
                console.error('Error loading tooltip content:', error);
                content = 'Error al cargar el contenido';
            }
        }
        // Template personalizado
        else if (this.options.template) {
            content = this.renderTemplate();
        }
        // Contenido estático
        else {
            content = this.options.content;
        }
        
        // Sanitizar contenido si es necesario
        if (this.options.sanitize && this.options.html) {
            content = this.sanitizeContent(content);
        }
        
        // Establecer contenido
        if (this.options.html || this.options.allowHTML) {
            this.contentElement.innerHTML = content;
        } else {
            this.contentElement.textContent = content;
        }
    }
    
    /**
     * Carga contenido AJAX
     */
    async loadAjaxContent() {
        const response = await fetch(this.options.ajax.url, {
            method: this.options.ajax.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...this.options.ajax.headers
            },
            body: this.options.ajax.data ? JSON.stringify(this.options.ajax.data) : null
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        if (this.options.ajax.responseType === 'json') {
            const data = await response.json();
            return this.options.ajax.transform ? this.options.ajax.transform(data) : JSON.stringify(data);
        } else {
            return await response.text();
        }
    }
    
    /**
     * Renderiza template personalizado
     */
    renderTemplate() {
        if (typeof this.options.template === 'function') {
            return this.options.template(this.getTemplateData());
        } else if (typeof this.options.template === 'string') {
            return this.interpolateTemplate(this.options.template, this.getTemplateData());
        }
        
        return '';
    }
    
    /**
     * Obtiene datos para el template
     */
    getTemplateData() {
        return {
            element: this.element,
            content: this.options.content,
            userData: this.element.dataset,
            timestamp: new Date().toISOString()
        };
    }
    
    /**
     * Interpola template con datos
     */
    interpolateTemplate(template, data) {
        return template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
            return data[key] || match;
        });
    }
    
    /**
     * Sanitiza contenido HTML
     */
    sanitizeContent(content) {
        // Implementación básica de sanitización
        // En producción usar librería como DOMPurify
        const div = document.createElement('div');
        div.textContent = content;
        return div.innerHTML;
    }
    
    /**
     * Actualiza la posición del tooltip
     */
    updatePosition() {
        if (!this.tooltipElement || !this.isVisible) return;
        
        const placement = this.calculateOptimalPlacement();
        const position = this.calculatePosition(placement);
        
        // Aplicar posición
        this.tooltipElement.style.left = `${position.x}px`;
        this.tooltipElement.style.top = `${position.y}px`;
        
        // Actualizar clase de placement
        this.tooltipElement.className = this.tooltipElement.className
            .replace(/tooltip-placement-\w+/, `tooltip-placement-${placement}`);
        
        // Posicionar arrow
        this.updateArrowPosition(placement, position);
    }
    
    /**
     * Calcula el placement óptimo
     */
    calculateOptimalPlacement() {
        if (!this.options.flip) {
            return this.options.placement;
        }
        
        const elementRect = this.element.getBoundingClientRect();
        const tooltipRect = this.tooltipElement.getBoundingClientRect();
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        
        // Verificar si el placement preferido cabe
        const preferredFits = this.placementFits(this.options.placement, elementRect, tooltipRect, viewport);
        
        if (preferredFits) {
            return this.options.placement;
        }
        
        // Buscar placement alternativo
        for (const placement of this.options.fallbackPlacements) {
            if (this.placementFits(placement, elementRect, tooltipRect, viewport)) {
                return placement;
            }
        }
        
        // Si ninguno cabe, usar el preferido
        return this.options.placement;
    }
    
    /**
     * Verifica si un placement cabe en el viewport
     */
    placementFits(placement, elementRect, tooltipRect, viewport) {
        const position = this.calculatePosition(placement, elementRect, tooltipRect);
        
        return position.x >= 0 && 
               position.y >= 0 && 
               position.x + tooltipRect.width <= viewport.width && 
               position.y + tooltipRect.height <= viewport.height;
    }
    
    /**
     * Calcula la posición del tooltip
     */
    calculatePosition(placement, elementRect = null, tooltipRect = null) {
        elementRect = elementRect || this.element.getBoundingClientRect();
        tooltipRect = tooltipRect || this.tooltipElement.getBoundingClientRect();
        
        const offset = this.options.offset;
        let x, y;
        
        switch (placement) {
            case 'top':
                x = elementRect.left + (elementRect.width / 2) - (tooltipRect.width / 2);
                y = elementRect.top - tooltipRect.height - offset;
                break;
                
            case 'bottom':
                x = elementRect.left + (elementRect.width / 2) - (tooltipRect.width / 2);
                y = elementRect.bottom + offset;
                break;
                
            case 'left':
                x = elementRect.left - tooltipRect.width - offset;
                y = elementRect.top + (elementRect.height / 2) - (tooltipRect.height / 2);
                break;
                
            case 'right':
                x = elementRect.right + offset;
                y = elementRect.top + (elementRect.height / 2) - (tooltipRect.height / 2);
                break;
                
            default:
                x = elementRect.left;
                y = elementRect.top - tooltipRect.height - offset;
        }
        
        // Ajustar posición si está fuera del viewport
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        
        // Ajustar X
        if (x < 0) {
            x = 5;
        } else if (x + tooltipRect.width > viewport.width) {
            x = viewport.width - tooltipRect.width - 5;
        }
        
        // Ajustar Y
        if (y < 0) {
            y = 5;
        } else if (y + tooltipRect.height > viewport.height) {
            y = viewport.height - tooltipRect.height - 5;
        }
        
        return { x: x + window.scrollX, y: y + window.scrollY };
    }
    
    /**
     * Actualiza la posición del arrow
     */
    updateArrowPosition(placement, position) {
        if (!this.arrowElement) return;
        
        const elementRect = this.element.getBoundingClientRect();
        const arrowSize = 8; // Tamaño del arrow en px
        
        let arrowX, arrowY;
        
        switch (placement) {
            case 'top':
            case 'bottom':
                arrowX = (elementRect.left + elementRect.width / 2) - position.x;
                arrowX = Math.max(arrowSize, Math.min(arrowX, this.tooltipElement.offsetWidth - arrowSize));
                this.arrowElement.style.left = `${arrowX}px`;
                this.arrowElement.style.top = placement === 'top' ? '100%' : `-${arrowSize}px`;
                break;
                
            case 'left':
            case 'right':
                arrowY = (elementRect.top + elementRect.height / 2) - position.y;
                arrowY = Math.max(arrowSize, Math.min(arrowY, this.tooltipElement.offsetHeight - arrowSize));
                this.arrowElement.style.top = `${arrowY}px`;
                this.arrowElement.style.left = placement === 'left' ? '100%' : `-${arrowSize}px`;
                break;
        }
    }
    
    /**
     * Actualiza posición basada en cursor (para followCursor)
     */
    updateCursorPosition(event) {
        if (!this.options.followCursor || !this.isVisible) return;
        
        const offset = 15;
        this.tooltipElement.style.left = `${event.pageX + offset}px`;
        this.tooltipElement.style.top = `${event.pageY - this.tooltipElement.offsetHeight - offset}px`;
    }
    
    /**
     * Actualiza el contenido del tooltip
     */
    updateContent(content, html = false) {
        this.options.content = content;
        this.options.html = html;
        
        if (this.contentElement) {
            if (html || this.options.allowHTML) {
                this.contentElement.innerHTML = content;
            } else {
                this.contentElement.textContent = content;
            }
        }
        
        // Actualizar posición si está visible
        if (this.isVisible) {
            setTimeout(() => this.updatePosition(), 0);
        }
    }
    
    /**
     * Actualiza opciones del tooltip
     */
    updateOptions(newOptions) {
        Object.assign(this.options, newOptions);
        
        // Reconfigurar si es necesario
        if (newOptions.trigger) {
            this.unbindEvents();
            this.processTriggers();
            this.bindEvents();
        }
        
        if (this.tooltipElement) {
            this.tooltipElement.className = this.getTooltipClasses();
            this.tooltipElement.style.cssText = this.getTooltipStyles();
        }
    }
    
    /**
     * Habilita el tooltip
     */
    enable() {
        this.bindEvents();
    }
    
    /**
     * Deshabilita el tooltip
     */
    disable() {
        this.hide();
        this.unbindEvents();
    }
    
    /**
     * Desvincula eventos
     */
    unbindEvents() {
        Object.entries(this.boundEvents).forEach(([event, handler]) => {
            switch (event) {
                case 'mouseenter':
                case 'mouseleave':
                case 'mousemove':
                case 'focusin':
                case 'focusout':
                case 'click':
                    this.element.removeEventListener(event.replace('focusin', 'focus').replace('focusout', 'blur'), handler);
                    break;
                case 'documentClick':
                    document.removeEventListener('click', handler);
                    break;
                case 'keydown':
                    document.removeEventListener('keydown', handler);
                    break;
                case 'resize':
                    window.removeEventListener('resize', handler);
                    break;
                case 'scroll':
                    window.removeEventListener('scroll', handler, true);
                    break;
            }
        });
        
        this.boundEvents = {};
    }
    
    /**
     * Limpia timeout específico
     */
    clearTimeout(type) {
        if (this.timeouts[type]) {
            clearTimeout(this.timeouts[type]);
            delete this.timeouts[type];
        }
    }
    
    /**
     * Limpia todos los timeouts
     */
    clearAllTimeouts() {
        Object.values(this.timeouts).forEach(timeout => clearTimeout(timeout));
        this.timeouts = {};
    }
    
    /**
     * Convierte camelCase a kebab-case
     */
    camelToKebab(str) {
        return str.replace(/([a-z0-9]|(?=[A-Z]))([A-Z])/g, '$1-$2').toLowerCase();
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
        // Limpiar timeouts
        this.clearAllTimeouts();
        
        // Ocultar tooltip
        this.hide();
        
        // Desvincula eventos
        this.unbindEvents();
        
        // Remover tooltip del DOM
        if (this.tooltipElement && this.tooltipElement.parentNode) {
            this.tooltipElement.parentNode.removeChild(this.tooltipElement);
        }
        
        // Limpiar atributos de accesibilidad
        this.element.removeAttribute('aria-describedby');
        
        // Limpiar referencias
        if (this.element._tooltipInstance) {
            delete this.element._tooltipInstance;
        }
        
        this.dispatchEvent('tooltip:destroy');
    }
}

// Pool de instancias para optimización de memoria
class TooltipPool {
    constructor() {
        this.instances = new Map();
        this.recycledElements = [];
    }
    
    /**
     * Obtiene o crea instancia de tooltip
     */
    getInstance(element, options) {
        const key = this.generateKey(element);
        
        if (this.instances.has(key)) {
            const instance = this.instances.get(key);
            instance.updateOptions(options);
            return instance;
        }
        
        const instance = new TooltipComponent(element, options);
        this.instances.set(key, instance);
        return instance;
    }
    
    /**
     * Libera instancia
     */
    releaseInstance(element) {
        const key = this.generateKey(element);
        const instance = this.instances.get(key);
        
        if (instance) {
            instance.destroy();
            this.instances.delete(key);
        }
    }
    
    /**
     * Genera clave única para el elemento
     */
    generateKey(element) {
        if (!element._tooltipKey) {
            element._tooltipKey = `tooltip-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        return element._tooltipKey;
    }
    
    /**
     * Limpia todas las instancias
     */
    clear() {
        this.instances.forEach(instance => instance.destroy());
        this.instances.clear();
        this.recycledElements = [];
    }
}

// Instancia global del pool
const tooltipPool = new TooltipPool();

// Inicialización automática
document.addEventListener('DOMContentLoaded', () => {
    // Buscar todos los elementos con tooltip
    const tooltipElements = document.querySelectorAll('[data-tooltip], [title]');
    
    tooltipElements.forEach(element => {
        // Skip si ya tiene instancia
        if (element._tooltipInstance) return;
        
        // Obtener configuración desde atributos
        const options = {
            content: element.getAttribute('data-tooltip') || element.getAttribute('title'),
            placement: element.getAttribute('data-placement'),
            trigger: element.getAttribute('data-trigger'),
            theme: element.getAttribute('data-theme'),
            variant: element.getAttribute('data-variant'),
            size: element.getAttribute('data-size'),
            html: element.getAttribute('data-tooltip-html') === 'true',
            interactive: element.getAttribute('data-interactive') === 'true',
            followCursor: element.getAttribute('data-follow-cursor') === 'true',
            delayShow: parseInt(element.getAttribute('data-delay-show')) || undefined,
            delayHide: parseInt(element.getAttribute('data-delay-hide')) || undefined
        };
        
        // Limpiar title para evitar tooltip nativo
        if (element.hasAttribute('title')) {
            element.removeAttribute('title');
        }
        
        // Crear instancia usando el pool
        tooltipPool.getInstance(element, options);
    });
});

// API global de tooltips
window.Tooltip = {
    /**
     * Crea tooltip manualmente
     */
    create: (element, options = {}) => {
        return new TooltipComponent(element, options);
    },
    
    /**
     * Obtiene instancia existente
     */
    getInstance: (element) => {
        return element._tooltipInstance || null;
    },
    
    /**
     * Muestra tooltip específico
     */
    show: (selector) => {
        const elements = typeof selector === 'string' ? 
            document.querySelectorAll(selector) : [selector];
            
        elements.forEach(element => {
            const instance = element._tooltipInstance;
            if (instance) instance.show();
        });
    },
    
    /**
     * Oculta tooltip específico
     */
    hide: (selector) => {
        const elements = typeof selector === 'string' ? 
            document.querySelectorAll(selector) : [selector];
            
        elements.forEach(element => {
            const instance = element._tooltipInstance;
            if (instance) instance.hide();
        });
    },
    
    /**
     * Oculta todos los tooltips
     */
    hideAll: () => {
        tooltipPool.instances.forEach(instance => {
            if (instance.isVisible) instance.hide();
        });
    },
    
    /**
     * Actualiza contenido de tooltip
     */
    updateContent: (selector, content, html = false) => {
        const elements = typeof selector === 'string' ? 
            document.querySelectorAll(selector) : [selector];
            
        elements.forEach(element => {
            const instance = element._tooltipInstance;
            if (instance) instance.updateContent(content, html);
        });
    },
    
    /**
     * Destruye tooltip específico
     */
    destroy: (selector) => {
        const elements = typeof selector === 'string' ? 
            document.querySelectorAll(selector) : [selector];
            
        elements.forEach(element => {
            tooltipPool.releaseInstance(element);
        });
    },
    
    /**
     * Destruye todos los tooltips
     */
    destroyAll: () => {
        tooltipPool.clear();
    },
    
    // Pool de instancias
    pool: tooltipPool
};

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TooltipComponent, TooltipPool, Tooltip: window.Tooltip };
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
    window.TooltipComponent = TooltipComponent;
    window.TooltipPool = TooltipPool;
}