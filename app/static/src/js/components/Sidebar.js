/**
 * Sidebar Component
 * Sistema avanzado de navegación lateral para el ecosistema de emprendimiento
 * Soporta multi-nivel, roles, notificaciones, personalización y tiempo real
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class EcoSidebar {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.getElementById(container) : container;
        if (!this.container) {
            throw new Error('Sidebar container not found');
        }

        this.config = {
            // Configuración básica
            userRole: options.userRole || 'user',
            context: options.context || 'general',
            theme: options.theme || 'light',
            
            // Comportamiento
            collapsible: options.collapsible !== false,
            collapsed: options.collapsed || false,
            overlay: options.overlay !== false,
            backdrop: options.backdrop !== false,
            
            // Responsive
            responsive: options.responsive !== false,
            mobileBreakpoint: options.mobileBreakpoint || 768,
            tabletBreakpoint: options.tabletBreakpoint || 1024,
            
            // Funcionalidades
            enableSearch: options.enableSearch !== false,
            enableFavorites: options.enableFavorites !== false,
            enableNotifications: options.enableNotifications !== false,
            enableCustomization: options.enableCustomization !== false,
            enableRealTime: options.enableRealTime !== false,
            
            // Navegación
            multiLevel: options.multiLevel !== false,
            maxNestingLevel: options.maxNestingLevel || 3,
            autoExpand: options.autoExpand || false,
            rememberState: options.rememberState !== false,
            
            // Menú específico del ecosistema
            menuStructure: options.menuStructure || this.getDefaultMenuStructure(),
            
            // Personalización
            allowReorder: options.allowReorder || false,
            allowHideItems: options.allowHideItems || false,
            customSections: options.customSections || [],
            
            // Notificaciones
            notificationBadges: options.notificationBadges !== false,
            realTimeUpdates: options.realTimeUpdates !== false,
            
            // Integración
            webSocketUrl: options.webSocketUrl || '/ws/sidebar',
            apiBaseUrl: options.apiBaseUrl || '/api/v1',
            
            // UI/UX
            animations: options.animations !== false,
            animationDuration: options.animationDuration || 300,
            smoothScroll: options.smoothScroll !== false,
            
            // Accesibilidad
            enableKeyboardNav: options.enableKeyboardNav !== false,
            enableScreenReader: options.enableScreenReader !== false,
            
            // Analytics
            enableAnalytics: options.enableAnalytics !== false,
            trackNavigation: options.trackNavigation !== false,
            
            // Callbacks
            onToggle: options.onToggle || null,
            onNavigate: options.onNavigate || null,
            onNotification: options.onNotification || null,
            onCustomize: options.onCustomize || null,
            onError: options.onError || null,
            
            // Persistencia
            storageKey: options.storageKey || 'eco_sidebar_state',
            
            ...options
        };

        this.state = {
            // Estado de navegación
            collapsed: this.config.collapsed,
            activeItem: null,
            expandedItems: new Set(),
            hoveredItem: null,
            
            // Estado de datos
            menuItems: [],
            favoriteItems: new Set(),
            hiddenItems: new Set(),
            notifications: new Map(),
            
            // Estado de UI
            deviceType: 'desktop',
            searchQuery: '',
            searchResults: [],
            
            // Estado de personalización
            customOrder: [],
            userPreferences: {},
            
            // WebSocket y tiempo real
            socket: null,
            isConnected: false,
            
            // Métricas
            navigationStats: new Map(),
            lastActivity: Date.now()
        };

        this.elements = {};
        this.templates = new Map();
        this.eventListeners = [];
        this.searchTimeout = null;
        this.resizeObserver = null;
        this.touchStartX = 0;
        this.touchStartY = 0;

        this.init();
    }

    /**
     * Inicialización del componente
     */
    async init() {
        try {
            await this.detectDevice();
            await this.setupTemplates();
            await this.loadMenuStructure();
            await this.createInterface();
            await this.setupEventListeners();
            await this.restoreState();
            await this.loadNotifications();
            
            if (this.config.enableRealTime) {
                await this.initializeWebSocket();
            }
            
            console.log('✅ EcoSidebar initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing EcoSidebar:', error);
            this.handleError(error);
        }
    }

    /**
     * Detectar tipo de dispositivo
     */
    detectDevice() {
        const width = window.innerWidth;
        
        if (width < this.config.mobileBreakpoint) {
            this.state.deviceType = 'mobile';
            this.state.collapsed = true; // Siempre colapsado en móviles
        } else if (width < this.config.tabletBreakpoint) {
            this.state.deviceType = 'tablet';
        } else {
            this.state.deviceType = 'desktop';
        }
    }

    /**
     * Configurar templates
     */
    async setupTemplates() {
        // Template principal del sidebar
        this.templates.set('main', `
            <div class="eco-sidebar" 
                 data-theme="${this.config.theme}" 
                 data-role="${this.config.userRole}"
                 data-device="${this.state.deviceType}">
                
                <!-- Header del sidebar -->
                <div class="sidebar-header">
                    <div class="sidebar-brand">
                        <img src="{{brandLogo}}" alt="{{brandName}}" class="brand-logo">
                        <span class="brand-text">{{brandName}}</span>
                    </div>
                    <button type="button" class="sidebar-toggle" title="Contraer/Expandir">
                        <i class="fas fa-bars"></i>
                    </button>
                </div>
                
                <!-- Usuario info -->
                <div class="sidebar-user">
                    <div class="user-avatar">
                        <img src="{{userAvatar}}" alt="{{userName}}" class="avatar-img">
                        <div class="user-status {{userStatus}}"></div>
                    </div>
                    <div class="user-info">
                        <div class="user-name">{{userName}}</div>
                        <div class="user-role">{{userRoleText}}</div>
                    </div>
                    <div class="user-actions">
                        <button type="button" class="btn-user-menu" title="Menú de usuario">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Búsqueda de menú -->
                <div class="sidebar-search" style="display: none;">
                    <div class="search-input-wrapper">
                        <i class="fas fa-search search-icon"></i>
                        <input type="text" class="search-input" placeholder="Buscar en menú...">
                        <button type="button" class="search-clear" style="display: none;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="search-results" style="display: none;"></div>
                </div>
                
                <!-- Contenido principal del menú -->
                <div class="sidebar-content">
                    <!-- Favoritos -->
                    <div class="sidebar-section favorites-section" style="display: none;">
                        <div class="section-header">
                            <h6 class="section-title">
                                <i class="fas fa-star"></i>
                                <span>Favoritos</span>
                            </h6>
                        </div>
                        <ul class="sidebar-menu favorites-menu"></ul>
                    </div>
                    
                    <!-- Menú principal -->
                    <div class="sidebar-section main-section">
                        <ul class="sidebar-menu main-menu"></ul>
                    </div>
                    
                    <!-- Secciones personalizadas -->
                    <div class="custom-sections"></div>
                </div>
                
                <!-- Footer del sidebar -->
                <div class="sidebar-footer">
                    <div class="footer-stats">
                        <div class="stat-item">
                            <i class="fas fa-chart-line"></i>
                            <span class="stat-label">Progreso</span>
                            <span class="stat-value">{{progressPercent}}%</span>
                        </div>
                    </div>
                    
                    <div class="footer-actions">
                        {{#if enableCustomization}}
                        <button type="button" class="btn-customize" title="Personalizar menú">
                            <i class="fas fa-cog"></i>
                        </button>
                        {{/if}}
                        
                        <button type="button" class="btn-help" title="Ayuda">
                            <i class="fas fa-question-circle"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Overlay para móviles -->
                <div class="sidebar-overlay" style="display: none;"></div>
            </div>
        `);

        // Template para item de menú
        this.templates.set('menuItem', `
            <li class="menu-item {{#if hasChildren}}has-children{{/if}} {{#if isActive}}active{{/if}}" 
                data-id="{{id}}" 
                data-level="{{level}}">
                <a href="{{url}}" class="menu-link" {{#if isExternal}}target="_blank"{{/if}}>
                    <div class="menu-icon">
                        {{#if icon}}
                        <i class="{{icon}}"></i>
                        {{else}}
                        <span class="menu-dot"></span>
                        {{/if}}
                    </div>
                    <span class="menu-text">{{text}}</span>
                    {{#if badge}}
                    <span class="menu-badge {{badge.type}}">{{badge.value}}</span>
                    {{/if}}
                    {{#if hasChildren}}
                    <i class="menu-arrow fas fa-chevron-right"></i>
                    {{/if}}
                </a>
                {{#if hasChildren}}
                <ul class="submenu" style="display: none;">
                    {{#each children}}
                    {{> menuItem}}
                    {{/each}}
                </ul>
                {{/if}}
            </li>
        `);

        // Template para notificación
        this.templates.set('notification', `
            <div class="sidebar-notification {{type}}" data-id="{{id}}">
                <div class="notification-icon">
                    <i class="{{icon}}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-title">{{title}}</div>
                    <div class="notification-message">{{message}}</div>
                    <div class="notification-time">{{time}}</div>
                </div>
                <button type="button" class="notification-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `);
    }

    /**
     * Cargar estructura de menú según el rol
     */
    async loadMenuStructure() {
        if (this.config.menuStructure) {
            this.state.menuItems = this.config.menuStructure;
        } else {
            this.state.menuItems = await this.getMenuForRole(this.config.userRole);
        }

        // Filtrar elementos según permisos
        this.state.menuItems = this.filterMenuByPermissions(this.state.menuItems);
        
        // Cargar notificaciones para cada elemento
        await this.loadMenuNotifications();
    }

    /**
     * Obtener menú según el rol del usuario
     */
    getMenuForRole(role) {
        const menus = {
            entrepreneur: this.getEntrepreneurMenu(),
            mentor: this.getMentorMenu(),
            admin: this.getAdminMenu(),
            client: this.getClientMenu()
        };

        return menus[role] || this.getDefaultMenuStructure();
    }

    /**
     * Menú para emprendedores
     */
    getEntrepreneurMenu() {
        return [
            {
                id: 'dashboard',
                text: 'Dashboard',
                icon: 'fas fa-tachometer-alt',
                url: '/dashboard',
                badge: null
            },
            {
                id: 'mi-proyecto',
                text: 'Mi Proyecto',
                icon: 'fas fa-rocket',
                url: '/proyecto',
                children: [
                    {
                        id: 'resumen',
                        text: 'Resumen',
                        url: '/proyecto/resumen'
                    },
                    {
                        id: 'pitch-deck',
                        text: 'Pitch Deck',
                        url: '/proyecto/pitch-deck',
                        badge: { type: 'warning', value: '!' }
                    },
                    {
                        id: 'plan-negocio',
                        text: 'Plan de Negocio',
                        url: '/proyecto/plan-negocio'
                    },
                    {
                        id: 'financieros',
                        text: 'Documentos Financieros',
                        url: '/proyecto/financieros'
                    },
                    {
                        id: 'equipo',
                        text: 'Mi Equipo',
                        url: '/proyecto/equipo'
                    }
                ]
            },
            {
                id: 'mentoria',
                text: 'Mentoría',
                icon: 'fas fa-user-tie',
                url: '/mentoria',
                children: [
                    {
                        id: 'mi-mentor',
                        text: 'Mi Mentor',
                        url: '/mentoria/mentor'
                    },
                    {
                        id: 'sesiones',
                        text: 'Sesiones',
                        url: '/mentoria/sesiones',
                        badge: { type: 'primary', value: '2' }
                    },
                    {
                        id: 'calendario',
                        text: 'Calendario',
                        url: '/mentoria/calendario'
                    },
                    {
                        id: 'recursos',
                        text: 'Recursos',
                        url: '/mentoria/recursos'
                    }
                ]
            },
            {
                id: 'tareas',
                text: 'Tareas',
                icon: 'fas fa-tasks',
                url: '/tareas',
                badge: { type: 'danger', value: '5' }
            },
            {
                id: 'documentos',
                text: 'Documentos',
                icon: 'fas fa-folder',
                url: '/documentos'
            },
            {
                id: 'networking',
                text: 'Networking',
                icon: 'fas fa-users',
                url: '/networking',
                children: [
                    {
                        id: 'emprendedores',
                        text: 'Otros Emprendedores',
                        url: '/networking/emprendedores'
                    },
                    {
                        id: 'eventos',
                        text: 'Eventos',
                        url: '/networking/eventos',
                        badge: { type: 'success', value: '3' }
                    },
                    {
                        id: 'foros',
                        text: 'Foros',
                        url: '/networking/foros'
                    }
                ]
            },
            {
                id: 'financiamiento',
                text: 'Financiamiento',
                icon: 'fas fa-dollar-sign',
                url: '/financiamiento',
                children: [
                    {
                        id: 'oportunidades',
                        text: 'Oportunidades',
                        url: '/financiamiento/oportunidades'
                    },
                    {
                        id: 'mis-postulaciones',
                        text: 'Mis Postulaciones',
                        url: '/financiamiento/postulaciones'
                    },
                    {
                        id: 'tracker',
                        text: 'Funding Tracker',
                        url: '/financiamiento/tracker'
                    }
                ]
            },
            {
                id: 'progreso',
                text: 'Mi Progreso',
                icon: 'fas fa-chart-line',
                url: '/progreso'
            },
            {
                id: 'configuracion',
                text: 'Configuración',
                icon: 'fas fa-cog',
                url: '/configuracion'
            }
        ];
    }

    /**
     * Menú para mentores
     */
    getMentorMenu() {
        return [
            {
                id: 'dashboard',
                text: 'Dashboard',
                icon: 'fas fa-tachometer-alt',
                url: '/mentor/dashboard'
            },
            {
                id: 'mis-emprendedores',
                text: 'Mis Emprendedores',
                icon: 'fas fa-users',
                url: '/mentor/emprendedores',
                badge: { type: 'primary', value: '8' }
            },
            {
                id: 'sesiones',
                text: 'Sesiones de Mentoría',
                icon: 'fas fa-calendar-alt',
                url: '/mentor/sesiones',
                children: [
                    {
                        id: 'programadas',
                        text: 'Programadas',
                        url: '/mentor/sesiones/programadas',
                        badge: { type: 'warning', value: '3' }
                    },
                    {
                        id: 'completadas',
                        text: 'Completadas',
                        url: '/mentor/sesiones/completadas'
                    },
                    {
                        id: 'calendario',
                        text: 'Calendario',
                        url: '/mentor/sesiones/calendario'
                    }
                ]
            },
            {
                id: 'recursos',
                text: 'Recursos',
                icon: 'fas fa-book',
                url: '/mentor/recursos',
                children: [
                    {
                        id: 'mis-recursos',
                        text: 'Mis Recursos',
                        url: '/mentor/recursos/mis-recursos'
                    },
                    {
                        id: 'templates',
                        text: 'Templates',
                        url: '/mentor/recursos/templates'
                    },
                    {
                        id: 'biblioteca',
                        text: 'Biblioteca',
                        url: '/mentor/recursos/biblioteca'
                    }
                ]
            },
            {
                id: 'evaluaciones',
                text: 'Evaluaciones',
                icon: 'fas fa-clipboard-check',
                url: '/mentor/evaluaciones'
            },
            {
                id: 'reportes',
                text: 'Reportes',
                icon: 'fas fa-chart-bar',
                url: '/mentor/reportes'
            },
            {
                id: 'horas',
                text: 'Registro de Horas',
                icon: 'fas fa-clock',
                url: '/mentor/horas'
            },
            {
                id: 'perfil',
                text: 'Mi Perfil',
                icon: 'fas fa-user',
                url: '/mentor/perfil'
            }
        ];
    }

    /**
     * Menú para administradores
     */
    getAdminMenu() {
        return [
            {
                id: 'dashboard',
                text: 'Dashboard',
                icon: 'fas fa-tachometer-alt',
                url: '/admin/dashboard'
            },
            {
                id: 'usuarios',
                text: 'Gestión de Usuarios',
                icon: 'fas fa-users-cog',
                url: '/admin/usuarios',
                children: [
                    {
                        id: 'emprendedores',
                        text: 'Emprendedores',
                        url: '/admin/usuarios/emprendedores',
                        badge: { type: 'info', value: '145' }
                    },
                    {
                        id: 'mentores',
                        text: 'Mentores',
                        url: '/admin/usuarios/mentores',
                        badge: { type: 'info', value: '32' }
                    },
                    {
                        id: 'admins',
                        text: 'Administradores',
                        url: '/admin/usuarios/admins'
                    },
                    {
                        id: 'roles',
                        text: 'Roles y Permisos',
                        url: '/admin/usuarios/roles'
                    }
                ]
            },
            {
                id: 'programas',
                text: 'Programas',
                icon: 'fas fa-graduation-cap',
                url: '/admin/programas',
                children: [
                    {
                        id: 'activos',
                        text: 'Programas Activos',
                        url: '/admin/programas/activos'
                    },
                    {
                        id: 'cohortes',
                        text: 'Cohortes',
                        url: '/admin/programas/cohortes'
                    },
                    {
                        id: 'curriculums',
                        text: 'Curriculums',
                        url: '/admin/programas/curriculums'
                    }
                ]
            },
            {
                id: 'mentoria',
                text: 'Mentoría',
                icon: 'fas fa-handshake',
                url: '/admin/mentoria',
                children: [
                    {
                        id: 'asignaciones',
                        text: 'Asignaciones',
                        url: '/admin/mentoria/asignaciones',
                        badge: { type: 'warning', value: '12' }
                    },
                    {
                        id: 'sesiones',
                        text: 'Sesiones',
                        url: '/admin/mentoria/sesiones'
                    },
                    {
                        id: 'evaluaciones',
                        text: 'Evaluaciones',
                        url: '/admin/mentoria/evaluaciones'
                    }
                ]
            },
            {
                id: 'contenido',
                text: 'Gestión de Contenido',
                icon: 'fas fa-file-alt',
                url: '/admin/contenido',
                children: [
                    {
                        id: 'documentos',
                        text: 'Documentos',
                        url: '/admin/contenido/documentos'
                    },
                    {
                        id: 'recursos',
                        text: 'Recursos',
                        url: '/admin/contenido/recursos'
                    },
                    {
                        id: 'templates',
                        text: 'Templates',
                        url: '/admin/contenido/templates'
                    }
                ]
            },
            {
                id: 'analytics',
                text: 'Analytics',
                icon: 'fas fa-chart-line',
                url: '/admin/analytics',
                children: [
                    {
                        id: 'kpis',
                        text: 'KPIs',
                        url: '/admin/analytics/kpis'
                    },
                    {
                        id: 'reportes',
                        text: 'Reportes',
                        url: '/admin/analytics/reportes'
                    },
                    {
                        id: 'usuarios',
                        text: 'Actividad de Usuarios',
                        url: '/admin/analytics/usuarios'
                    }
                ]
            },
            {
                id: 'configuracion',
                text: 'Configuración',
                icon: 'fas fa-cogs',
                url: '/admin/configuracion',
                children: [
                    {
                        id: 'sistema',
                        text: 'Sistema',
                        url: '/admin/configuracion/sistema'
                    },
                    {
                        id: 'integraciones',
                        text: 'Integraciones',
                        url: '/admin/configuracion/integraciones'
                    },
                    {
                        id: 'notificaciones',
                        text: 'Notificaciones',
                        url: '/admin/configuracion/notificaciones'
                    }
                ]
            }
        ];
    }

    /**
     * Menú para clientes/stakeholders
     */
    getClientMenu() {
        return [
            {
                id: 'dashboard',
                text: 'Dashboard',
                icon: 'fas fa-tachometer-alt',
                url: '/client/dashboard'
            },
            {
                id: 'programas',
                text: 'Mis Programas',
                icon: 'fas fa-graduation-cap',
                url: '/client/programas'
            },
            {
                id: 'emprendedores',
                text: 'Directorio de Emprendedores',
                icon: 'fas fa-users',
                url: '/client/emprendedores'
            },
            {
                id: 'impacto',
                text: 'Medición de Impacto',
                icon: 'fas fa-chart-pie',
                url: '/client/impacto',
                children: [
                    {
                        id: 'metricas',
                        text: 'Métricas',
                        url: '/client/impacto/metricas'
                    },
                    {
                        id: 'reportes',
                        text: 'Reportes',
                        url: '/client/impacto/reportes'
                    },
                    {
                        id: 'roi',
                        text: 'ROI',
                        url: '/client/impacto/roi'
                    }
                ]
            },
            {
                id: 'documentos',
                text: 'Documentos',
                icon: 'fas fa-folder',
                url: '/client/documentos'
            },
            {
                id: 'eventos',
                text: 'Eventos',
                icon: 'fas fa-calendar',
                url: '/client/eventos'
            }
        ];
    }

    /**
     * Estructura de menú por defecto
     */
    getDefaultMenuStructure() {
        return [
            {
                id: 'dashboard',
                text: 'Dashboard',
                icon: 'fas fa-tachometer-alt',
                url: '/dashboard'
            },
            {
                id: 'perfil',
                text: 'Mi Perfil',
                icon: 'fas fa-user',
                url: '/perfil'
            },
            {
                id: 'configuracion',
                text: 'Configuración',
                icon: 'fas fa-cog',
                url: '/configuracion'
            }
        ];
    }

    /**
     * Crear interfaz de usuario
     */
    async createInterface() {
        // Datos para el template
        const templateData = {
            brandLogo: '/static/img/logo.png',
            brandName: 'Ecosistema',
            userAvatar: await this.getUserAvatar(),
            userName: await this.getUserName(),
            userRoleText: this.getRoleText(),
            userStatus: await this.getUserStatus(),
            progressPercent: await this.getProgressPercent(),
            enableCustomization: this.config.enableCustomization
        };

        // Renderizar template principal
        this.container.innerHTML = this.renderTemplate(this.templates.get('main'), templateData);

        // Obtener referencias a elementos
        this.elements = {
            sidebar: this.container.querySelector('.eco-sidebar'),
            header: this.container.querySelector('.sidebar-header'),
            toggle: this.container.querySelector('.sidebar-toggle'),
            user: this.container.querySelector('.sidebar-user'),
            search: this.container.querySelector('.sidebar-search'),
            searchInput: this.container.querySelector('.search-input'),
            searchClear: this.container.querySelector('.search-clear'),
            searchResults: this.container.querySelector('.search-results'),
            content: this.container.querySelector('.sidebar-content'),
            mainMenu: this.container.querySelector('.main-menu'),
            favoritesSection: this.container.querySelector('.favorites-section'),
            favoritesMenu: this.container.querySelector('.favorites-menu'),
            customSections: this.container.querySelector('.custom-sections'),
            footer: this.container.querySelector('.sidebar-footer'),
            overlay: this.container.querySelector('.sidebar-overlay')
        };

        // Aplicar estado inicial
        this.applyInitialState();

        // Renderizar menú
        this.renderMenu();

        // Mostrar búsqueda si está habilitada
        if (this.config.enableSearch) {
            this.elements.search.style.display = 'block';
        }

        // Renderizar favoritos si hay
        this.renderFavorites();

        // Renderizar secciones personalizadas
        this.renderCustomSections();
    }

    /**
     * Aplicar estado inicial
     */
    applyInitialState() {
        // Aplicar tema
        this.elements.sidebar.setAttribute('data-theme', this.config.theme);
        
        // Aplicar estado colapsado
        if (this.state.collapsed) {
            this.elements.sidebar.classList.add('collapsed');
        }

        // Aplicar tipo de dispositivo
        this.elements.sidebar.setAttribute('data-device', this.state.deviceType);
    }

    /**
     * Renderizar menú principal
     */
    renderMenu() {
        this.elements.mainMenu.innerHTML = '';
        
        this.state.menuItems.forEach(item => {
            const menuElement = this.createMenuElement(item, 0);
            this.elements.mainMenu.appendChild(menuElement);
        });
    }

    /**
     * Crear elemento de menú
     */
    createMenuElement(item, level) {
        const li = document.createElement('li');
        
        // Preparar datos del item
        const itemData = {
            ...item,
            level: level,
            hasChildren: item.children && item.children.length > 0,
            isActive: this.isActiveItem(item),
            badge: this.getItemBadge(item)
        };

        // Renderizar template
        li.innerHTML = this.renderTemplate(this.templates.get('menuItem'), itemData);
        
        const element = li.firstElementChild;
        
        // Configurar event listeners
        this.setupMenuItemListeners(element, item);
        
        return element;
    }

    /**
     * Configurar event listeners del menú
     */
    setupMenuItemListeners(element, item) {
        const link = element.querySelector('.menu-link');
        
        // Click en el link
        link.addEventListener('click', (e) => {
            this.handleMenuClick(e, item, element);
        });

        // Hover para mostrar tooltip en modo colapsado
        if (this.state.collapsed) {
            link.addEventListener('mouseenter', (e) => {
                this.showTooltip(e, item.text);
            });
            
            link.addEventListener('mouseleave', () => {
                this.hideTooltip();
            });
        }

        // Configurar submenús si existen
        if (item.children && item.children.length > 0) {
            this.setupSubmenuListeners(element, item);
        }
    }

    /**
     * Configurar listeners de submenús
     */
    setupSubmenuListeners(element, item) {
        const submenu = element.querySelector('.submenu');
        const arrow = element.querySelector('.menu-arrow');
        
        // Toggle submenu
        arrow.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggleSubmenu(element, item);
        });
    }

    /**
     * Manejar click en elemento de menú
     */
    async handleMenuClick(e, item, element) {
        // Si es un enlace externo, permitir navegación normal
        if (item.isExternal) {
            return;
        }

        // Si tiene submenús, toggle en lugar de navegar
        if (item.children && item.children.length > 0) {
            e.preventDefault();
            this.toggleSubmenu(element, item);
            return;
        }

        // Prevenir navegación para manejar routing personalizado
        if (this.config.onNavigate) {
            e.preventDefault();
            
            try {
                const result = await this.config.onNavigate(item, e);
                if (result !== false) {
                    this.setActiveItem(item.id);
                    this.trackNavigation(item);
                }
            } catch (error) {
                this.handleError(error);
            }
        } else {
            // Navegación normal
            this.setActiveItem(item.id);
            this.trackNavigation(item);
        }

        // Cerrar sidebar en móviles después de navegar
        if (this.state.deviceType === 'mobile') {
            this.collapse();
        }
    }

    /**
     * Toggle submenu
     */
    toggleSubmenu(element, item) {
        const submenu = element.querySelector('.submenu');
        const arrow = element.querySelector('.menu-arrow');
        const isExpanded = this.state.expandedItems.has(item.id);

        if (isExpanded) {
            // Colapsar
            submenu.style.display = 'none';
            arrow.classList.remove('expanded');
            this.state.expandedItems.delete(item.id);
        } else {
            // Expandir
            submenu.style.display = 'block';
            arrow.classList.add('expanded');
            this.state.expandedItems.add(item.id);
        }

        // Animar si está habilitado
        if (this.config.animations) {
            this.animateSubmenu(submenu, !isExpanded);
        }

        // Guardar estado
        this.saveState();
    }

    /**
     * Animar submenu
     */
    animateSubmenu(submenu, show) {
        if (show) {
            submenu.style.height = '0px';
            submenu.style.overflow = 'hidden';
            submenu.style.display = 'block';
            
            const height = submenu.scrollHeight;
            submenu.style.height = height + 'px';
            
            setTimeout(() => {
                submenu.style.height = 'auto';
                submenu.style.overflow = 'visible';
            }, this.config.animationDuration);
        } else {
            const height = submenu.scrollHeight;
            submenu.style.height = height + 'px';
            submenu.style.overflow = 'hidden';
            
            setTimeout(() => {
                submenu.style.height = '0px';
            }, 10);
            
            setTimeout(() => {
                submenu.style.display = 'none';
                submenu.style.overflow = 'visible';
            }, this.config.animationDuration);
        }
    }

    /**
     * Configurar event listeners principales
     */
    async setupEventListeners() {
        // Toggle sidebar
        this.elements.toggle.addEventListener('click', () => {
            this.toggle();
        });

        // Búsqueda
        this.setupSearchListeners();

        // Overlay para móviles
        this.elements.overlay.addEventListener('click', () => {
            this.collapse();
        });

        // Resize observer
        this.setupResizeObserver();

        // Navegación por teclado
        if (this.config.enableKeyboardNav) {
            this.setupKeyboardNavigation();
        }

        // Touch gestures
        this.setupTouchGestures();

        // Botones del footer
        this.setupFooterListeners();

        // Favoritos
        this.setupFavoritesListeners();
    }

    /**
     * Configurar listeners de búsqueda
     */
    setupSearchListeners() {
        if (!this.config.enableSearch) return;

        // Input de búsqueda
        this.elements.searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            this.state.searchQuery = query;

            // Mostrar/ocultar botón de limpiar
            this.elements.searchClear.style.display = query ? 'block' : 'none';

            // Debounce search
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                this.performSearch(query);
            }, 300);
        });

        // Limpiar búsqueda
        this.elements.searchClear.addEventListener('click', () => {
            this.clearSearch();
        });

        // Enter para buscar
        this.elements.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch(this.state.searchQuery);
            }
        });
    }

    /**
     * Configurar resize observer
     */
    setupResizeObserver() {
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                this.handleResize();
            });
            this.resizeObserver.observe(document.body);
        } else {
            // Fallback para navegadores sin ResizeObserver
            window.addEventListener('resize', this.debounce(() => {
                this.handleResize();
            }, 250));
        }
    }

    /**
     * Manejar cambio de tamaño
     */
    handleResize() {
        const previousDevice = this.state.deviceType;
        this.detectDevice();

        if (previousDevice !== this.state.deviceType) {
            this.handleDeviceChange(previousDevice, this.state.deviceType);
        }
    }

    /**
     * Manejar cambio de dispositivo
     */
    handleDeviceChange(from, to) {
        this.elements.sidebar.setAttribute('data-device', to);

        if (to === 'mobile') {
            // En móviles, siempre colapsado
            this.state.collapsed = true;
            this.elements.sidebar.classList.add('collapsed');
        } else if (from === 'mobile' && this.config.rememberState) {
            // Al salir de móvil, restaurar estado guardado
            this.restoreState();
        }
    }

    /**
     * Configurar navegación por teclado
     */
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Solo si el sidebar está enfocado
            if (!this.elements.sidebar.contains(document.activeElement)) return;

            switch (e.key) {
                case 'ArrowUp':
                    e.preventDefault();
                    this.navigateUp();
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    this.navigateDown();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    this.expandCurrentItem();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.collapseCurrentItem();
                    break;
                case 'Enter':
                    e.preventDefault();
                    this.activateCurrentItem();
                    break;
                case 'Escape':
                    e.preventDefault();
                    this.clearFocus();
                    break;
            }
        });
    }

    /**
     * Configurar gestos táctiles
     */
    setupTouchGestures() {
        // Swipe para abrir/cerrar en móviles
        this.elements.sidebar.addEventListener('touchstart', (e) => {
            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;
        });

        this.elements.sidebar.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            
            const deltaX = touchEndX - this.touchStartX;
            const deltaY = touchEndY - this.touchStartY;
            
            // Solo si el movimiento horizontal es mayor que el vertical
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                if (this.state.deviceType === 'mobile') {
                    if (deltaX < 0 && this.state.collapsed === false) {
                        this.collapse(); // Swipe left = close
                    } else if (deltaX > 0 && this.state.collapsed === true) {
                        this.expand(); // Swipe right = open
                    }
                }
            }
        });
    }

    /**
     * Configurar listeners del footer
     */
    setupFooterListeners() {
        // Botón de personalización
        const customizeBtn = this.elements.footer.querySelector('.btn-customize');
        if (customizeBtn) {
            customizeBtn.addEventListener('click', () => {
                this.showCustomizationModal();
            });
        }

        // Botón de ayuda
        const helpBtn = this.elements.footer.querySelector('.btn-help');
        if (helpBtn) {
            helpBtn.addEventListener('click', () => {
                this.showHelpModal();
            });
        }
    }

    /**
     * Configurar listeners de favoritos
     */
    setupFavoritesListeners() {
        if (!this.config.enableFavorites) return;

        // Context menu para agregar/quitar favoritos
        this.elements.mainMenu.addEventListener('contextmenu', (e) => {
            const menuItem = e.target.closest('.menu-item');
            if (menuItem) {
                e.preventDefault();
                this.showFavoriteContextMenu(e, menuItem);
            }
        });
    }

    /**
     * Toggle sidebar
     */
    toggle() {
        if (this.state.collapsed) {
            this.expand();
        } else {
            this.collapse();
        }
    }

    /**
     * Expandir sidebar
     */
    expand() {
        this.state.collapsed = false;
        this.elements.sidebar.classList.remove('collapsed');
        
        // Mostrar overlay en móviles
        if (this.state.deviceType === 'mobile') {
            this.elements.overlay.style.display = 'block';
        }

        // Callback
        if (this.config.onToggle) {
            this.config.onToggle(false);
        }

        // Guardar estado
        this.saveState();

        // Analytics
        this.trackEvent('sidebar_expand');
    }

    /**
     * Colapsar sidebar
     */
    collapse() {
        this.state.collapsed = true;
        this.elements.sidebar.classList.add('collapsed');
        
        // Ocultar overlay
        this.elements.overlay.style.display = 'none';

        // Callback
        if (this.config.onToggle) {
            this.config.onToggle(true);
        }

        // Guardar estado
        this.saveState();

        // Analytics
        this.trackEvent('sidebar_collapse');
    }

    /**
     * Realizar búsqueda en menú
     */
    performSearch(query) {
        if (!query) {
            this.clearSearchResults();
            return;
        }

        const results = this.searchMenuItems(query);
        this.showSearchResults(results);
    }

    /**
     * Buscar en elementos del menú
     */
    searchMenuItems(query) {
        const results = [];
        const searchTerm = query.toLowerCase();

        const searchInItems = (items, path = []) => {
            items.forEach(item => {
                const itemPath = [...path, item.text];
                
                // Buscar en texto del item
                if (item.text.toLowerCase().includes(searchTerm)) {
                    results.push({
                        ...item,
                        path: itemPath,
                        highlight: this.highlightText(item.text, query)
                    });
                }

                // Buscar en hijos
                if (item.children) {
                    searchInItems(item.children, itemPath);
                }
            });
        };

        searchInItems(this.state.menuItems);
        return results;
    }

    /**
     * Mostrar resultados de búsqueda
     */
    showSearchResults(results) {
        const resultsContainer = this.elements.searchResults;
        
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="no-results">No se encontraron resultados</div>';
        } else {
            const resultsHtml = results.map(result => `
                <div class="search-result" data-id="${result.id}">
                    <div class="result-icon">
                        ${result.icon ? `<i class="${result.icon}"></i>` : '<span class="menu-dot"></span>'}
                    </div>
                    <div class="result-content">
                        <div class="result-text">${result.highlight}</div>
                        <div class="result-path">${result.path.slice(0, -1).join(' > ')}</div>
                    </div>
                </div>
            `).join('');
            
            resultsContainer.innerHTML = resultsHtml;
            
            // Configurar clicks en resultados
            resultsContainer.querySelectorAll('.search-result').forEach(result => {
                result.addEventListener('click', () => {
                    const itemId = result.dataset.id;
                    this.navigateToItem(itemId);
                    this.clearSearch();
                });
            });
        }
        
        resultsContainer.style.display = 'block';
    }

    /**
     * Limpiar búsqueda
     */
    clearSearch() {
        this.elements.searchInput.value = '';
        this.elements.searchClear.style.display = 'none';
        this.state.searchQuery = '';
        this.clearSearchResults();
    }

    /**
     * Limpiar resultados de búsqueda
     */
    clearSearchResults() {
        this.elements.searchResults.style.display = 'none';
        this.elements.searchResults.innerHTML = '';
    }

    /**
     * Inicializar WebSocket
     */
    async initializeWebSocket() {
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not available for real-time updates');
            return;
        }

        try {
            this.state.socket = io(this.config.webSocketUrl);

            this.state.socket.on('connect', () => {
                this.state.isConnected = true;
                console.log('🔗 Sidebar WebSocket connected');
            });

            this.state.socket.on('disconnect', () => {
                this.state.isConnected = false;
                console.log('🔌 Sidebar WebSocket disconnected');
            });

            // Eventos específicos
            this.state.socket.on('notification_update', (data) => {
                this.handleNotificationUpdate(data);
            });

            this.state.socket.on('menu_update', (data) => {
                this.handleMenuUpdate(data);
            });

            this.state.socket.on('user_status_change', (data) => {
                this.handleUserStatusChange(data);
            });

        } catch (error) {
            console.error('Error initializing WebSocket:', error);
        }
    }

    /**
     * Cargar notificaciones
     */
    async loadNotifications() {
        if (!this.config.enableNotifications) return;

        try {
            const response = await fetch(`${this.config.apiBaseUrl}/notifications/sidebar`, {
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (response.ok) {
                const notifications = await response.json();
                this.updateNotifications(notifications);
            }
        } catch (error) {
            console.warn('Error loading notifications:', error);
        }
    }

    /**
     * Cargar notificaciones del menú
     */
    async loadMenuNotifications() {
        // Implementar lógica para cargar badges/contadores específicos de cada item
        // Por ejemplo, contar tareas pendientes, mensajes no leídos, etc.
    }

    /**
     * Actualizar notificaciones
     */
    updateNotifications(notifications) {
        // Actualizar badges en el menú
        notifications.forEach(notification => {
            this.updateMenuBadge(notification.menuId, notification.count, notification.type);
        });
    }

    /**
     * Actualizar badge de elemento del menú
     */
    updateMenuBadge(menuId, count, type = 'primary') {
        const menuItem = this.elements.mainMenu.querySelector(`[data-id="${menuId}"]`);
        if (!menuItem) return;

        let badge = menuItem.querySelector('.menu-badge');
        
        if (count > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = `menu-badge ${type}`;
                const link = menuItem.querySelector('.menu-link');
                link.appendChild(badge);
            }
            
            badge.textContent = count > 99 ? '99+' : count;
            badge.className = `menu-badge ${type}`;
        } else if (badge) {
            badge.remove();
        }
    }

    /**
     * Métodos de utilidad
     */
    
    async getUserAvatar() {
        // Implementar lógica para obtener avatar del usuario
        return '/static/img/default-avatar.png';
    }

    async getUserName() {
        // Implementar lógica para obtener nombre del usuario
        return 'Usuario';
    }

    getRoleText() {
        const roleTexts = {
            entrepreneur: 'Emprendedor',
            mentor: 'Mentor',
            admin: 'Administrador',
            client: 'Cliente'
        };
        return roleTexts[this.config.userRole] || 'Usuario';
    }

    async getUserStatus() {
        // Implementar lógica para obtener estado del usuario
        return 'online'; // online, offline, away, busy
    }

    async getProgressPercent() {
        // Implementar lógica para obtener progreso del usuario
        return 75;
    }

    isActiveItem(item) {
        // Implementar lógica para determinar si un item está activo
        return window.location.pathname === item.url;
    }

    getItemBadge(item) {
        // Implementar lógica para obtener badge de un item
        return item.badge || null;
    }

    setActiveItem(itemId) {
        // Remover active de todos los items
        this.elements.mainMenu.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });

        // Agregar active al item seleccionado
        const activeItem = this.elements.mainMenu.querySelector(`[data-id="${itemId}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
            this.state.activeItem = itemId;
        }
    }

    navigateToItem(itemId) {
        const item = this.findMenuItem(itemId);
        if (item) {
            if (this.config.onNavigate) {
                this.config.onNavigate(item);
            } else {
                window.location.href = item.url;
            }
            this.setActiveItem(itemId);
        }
    }

    findMenuItem(itemId) {
        const findInItems = (items) => {
            for (const item of items) {
                if (item.id === itemId) {
                    return item;
                }
                if (item.children) {
                    const found = findInItems(item.children);
                    if (found) return found;
                }
            }
            return null;
        };

        return findInItems(this.state.menuItems);
    }

    highlightText(text, query) {
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    filterMenuByPermissions(menuItems) {
        // Implementar lógica de filtrado por permisos
        return menuItems;
    }

    renderTemplate(template, data) {
        return template.replace(/\{\{(.*?)\}\}/g, (match, key) => {
            const keys = key.trim().split('.');
            let value = data;
            
            for (const k of keys) {
                value = value?.[k];
            }
            
            return value !== undefined ? value : '';
        }).replace(/\{\{#if (.*?)\}\}(.*?)\{\{\/if\}\}/gs, (match, condition, content) => {
            const value = data[condition.trim()];
            return value ? content : '';
        }).replace(/\{\{#each (.*?)\}\}(.*?)\{\{\/each\}\}/gs, (match, arrayName, itemTemplate) => {
            const array = data[arrayName.trim()] || [];
            return array.map(item => 
                itemTemplate.replace(/\{\{(.*?)\}\}/g, (match, key) => {
                    if (key.trim() === 'this') return item;
                    return item[key.trim()] || '';
                })
            ).join('');
        });
    }

    /**
     * Persistencia de estado
     */
    saveState() {
        if (!this.config.rememberState) return;

        const state = {
            collapsed: this.state.collapsed,
            expandedItems: Array.from(this.state.expandedItems),
            favoriteItems: Array.from(this.state.favoriteItems),
            hiddenItems: Array.from(this.state.hiddenItems),
            activeItem: this.state.activeItem
        };

        localStorage.setItem(this.config.storageKey, JSON.stringify(state));
    }

    async restoreState() {
        if (!this.config.rememberState) return;

        try {
            const saved = localStorage.getItem(this.config.storageKey);
            if (saved) {
                const state = JSON.parse(saved);
                
                // Solo restaurar si no es móvil
                if (this.state.deviceType !== 'mobile') {
                    this.state.collapsed = state.collapsed || false;
                }
                
                this.state.expandedItems = new Set(state.expandedItems || []);
                this.state.favoriteItems = new Set(state.favoriteItems || []);
                this.state.hiddenItems = new Set(state.hiddenItems || []);
                this.state.activeItem = state.activeItem;
            }
        } catch (error) {
            console.warn('Error restoring sidebar state:', error);
        }
    }

    /**
     * Favoritos
     */
    renderFavorites() {
        if (!this.config.enableFavorites || this.state.favoriteItems.size === 0) {
            this.elements.favoritesSection.style.display = 'none';
            return;
        }

        this.elements.favoritesSection.style.display = 'block';
        this.elements.favoritesMenu.innerHTML = '';

        this.state.favoriteItems.forEach(itemId => {
            const item = this.findMenuItem(itemId);
            if (item) {
                const favoriteElement = this.createMenuElement(item, 0);
                favoriteElement.classList.add('favorite-item');
                this.elements.favoritesMenu.appendChild(favoriteElement);
            }
        });
    }

    addToFavorites(itemId) {
        this.state.favoriteItems.add(itemId);
        this.renderFavorites();
        this.saveState();
    }

    removeFromFavorites(itemId) {
        this.state.favoriteItems.delete(itemId);
        this.renderFavorites();
        this.saveState();
    }

    /**
     * Secciones personalizadas
     */
    renderCustomSections() {
        if (this.config.customSections.length === 0) return;

        this.config.customSections.forEach(section => {
            const sectionElement = this.createCustomSection(section);
            this.elements.customSections.appendChild(sectionElement);
        });
    }

    createCustomSection(section) {
        const div = document.createElement('div');
        div.className = 'sidebar-section custom-section';
        div.innerHTML = `
            <div class="section-header">
                <h6 class="section-title">
                    ${section.icon ? `<i class="${section.icon}"></i>` : ''}
                    <span>${section.title}</span>
                </h6>
            </div>
            <div class="section-content">
                ${section.content || ''}
            </div>
        `;
        return div;
    }

    /**
     * Analytics y tracking
     */
    trackNavigation(item) {
        if (!this.config.trackNavigation) return;

        this.state.navigationStats.set(item.id, {
            count: (this.state.navigationStats.get(item.id)?.count || 0) + 1,
            lastAccess: Date.now()
        });

        // Enviar a analytics
        this.trackEvent('navigation', {
            item_id: item.id,
            item_text: item.text,
            item_url: item.url,
            user_role: this.config.userRole
        });
    }

    trackEvent(event, data = {}) {
        if (!this.config.enableAnalytics) return;

        if (typeof gtag !== 'undefined') {
            gtag('event', event, {
                event_category: 'sidebar',
                ...data
            });
        }
    }

    /**
     * Manejo de errores
     */
    handleError(error) {
        console.error('Sidebar error:', error);
        
        if (this.config.onError) {
            this.config.onError(error);
        }
    }

    getCSRFToken() {
        return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * API pública
     */
    
    // Control de estado
    isCollapsed() {
        return this.state.collapsed;
    }

    setTheme(theme) {
        this.config.theme = theme;
        this.elements.sidebar.setAttribute('data-theme', theme);
    }

    updateUserInfo(userInfo) {
        // Actualizar información del usuario
        const userNameElement = this.elements.user.querySelector('.user-name');
        const userRoleElement = this.elements.user.querySelector('.user-role');
        const userAvatarElement = this.elements.user.querySelector('.avatar-img');

        if (userInfo.name && userNameElement) {
            userNameElement.textContent = userInfo.name;
        }
        if (userInfo.role && userRoleElement) {
            userRoleElement.textContent = userInfo.role;
        }
        if (userInfo.avatar && userAvatarElement) {
            userAvatarElement.src = userInfo.avatar;
        }
    }

    updateProgress(percent) {
        const progressElement = this.elements.footer.querySelector('.stat-value');
        if (progressElement) {
            progressElement.textContent = `${percent}%`;
        }
    }

    // Gestión de menú
    addMenuItem(item, parentId = null) {
        if (parentId) {
            const parent = this.findMenuItem(parentId);
            if (parent) {
                if (!parent.children) parent.children = [];
                parent.children.push(item);
            }
        } else {
            this.state.menuItems.push(item);
        }
        this.renderMenu();
    }

    removeMenuItem(itemId) {
        const removeFromItems = (items) => {
            return items.filter(item => {
                if (item.id === itemId) {
                    return false;
                }
                if (item.children) {
                    item.children = removeFromItems(item.children);
                }
                return true;
            });
        };

        this.state.menuItems = removeFromItems(this.state.menuItems);
        this.renderMenu();
    }

    updateMenuItem(itemId, updates) {
        const item = this.findMenuItem(itemId);
        if (item) {
            Object.assign(item, updates);
            this.renderMenu();
        }
    }

    // Notificaciones
    updateBadge(itemId, count, type = 'primary') {
        this.updateMenuBadge(itemId, count, type);
    }

    clearBadge(itemId) {
        this.updateMenuBadge(itemId, 0);
    }

    /**
     * Cleanup
     */
    destroy() {
        // Desconectar WebSocket
        if (this.state.socket) {
            this.state.socket.disconnect();
        }

        // Desconectar ResizeObserver
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }

        // Remover event listeners
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });

        // Limpiar timers
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        console.log('🧹 EcoSidebar destroyed');
    }
}

// CSS personalizado para el sidebar
const sidebarCSS = `
    .eco-sidebar {
        position: fixed;
        top: 0;
        left: 0;
        height: 100vh;
        width: 280px;
        background: #fff;
        border-right: 1px solid #e9ecef;
        display: flex;
        flex-direction: column;
        transition: all 0.3s ease;
        z-index: 1000;
        overflow: hidden;
    }
    
    .eco-sidebar.collapsed {
        width: 70px;
    }
    
    .eco-sidebar[data-device="mobile"] {
        transform: translateX(-100%);
        box-shadow: 0 0 20px rgba(0,0,0,0.1);
    }
    
    .eco-sidebar[data-device="mobile"]:not(.collapsed) {
        transform: translateX(0);
    }
    
    /* Header */
    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem;
        border-bottom: 1px solid #e9ecef;
        min-height: 70px;
    }
    
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        overflow: hidden;
    }
    
    .brand-logo {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        flex-shrink: 0;
    }
    
    .brand-text {
        font-size: 1.25rem;
        font-weight: 700;
        color: #333;
        white-space: nowrap;
        transition: opacity 0.3s ease;
    }
    
    .eco-sidebar.collapsed .brand-text {
        opacity: 0;
        width: 0;
    }
    
    .sidebar-toggle {
        background: none;
        border: none;
        font-size: 1.2rem;
        color: #6c757d;
        cursor: pointer;
        padding: 0.5rem;
        border-radius: 4px;
        transition: all 0.2s ease;
    }
    
    .sidebar-toggle:hover {
        background: #f8f9fa;
        color: #495057;
    }
    
    /* Usuario */
    .sidebar-user {
        display: flex;
        align-items: center;
        padding: 1rem;
        border-bottom: 1px solid #f8f9fa;
        gap: 0.75rem;
        overflow: hidden;
    }
    
    .user-avatar {
        position: relative;
        flex-shrink: 0;
    }
    
    .avatar-img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
    }
    
    .user-status {
        position: absolute;
        bottom: 0;
        right: 0;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        border: 2px solid #fff;
    }
    
    .user-status.online { background: #28a745; }
    .user-status.away { background: #ffc107; }
    .user-status.busy { background: #dc3545; }
    .user-status.offline { background: #6c757d; }
    
    .user-info {
        flex: 1;
        min-width: 0;
        transition: opacity 0.3s ease;
    }
    
    .user-name {
        font-weight: 600;
        color: #333;
        font-size: 0.9rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .user-role {
        font-size: 0.8rem;
        color: #6c757d;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .eco-sidebar.collapsed .user-info {
        opacity: 0;
        width: 0;
    }
    
    .user-actions {
        flex-shrink: 0;
    }
    
    .btn-user-menu {
        background: none;
        border: none;
        color: #6c757d;
        padding: 0.25rem;
        border-radius: 4px;
        transition: all 0.2s ease;
    }
    
    .btn-user-menu:hover {
        background: #f8f9fa;
        color: #495057;
    }
    
    /* Búsqueda */
    .sidebar-search {
        padding: 1rem;
        border-bottom: 1px solid #f8f9fa;
    }
    
    .search-input-wrapper {
        position: relative;
        display: flex;
        align-items: center;
    }
    
    .search-icon {
        position: absolute;
        left: 0.75rem;
        color: #6c757d;
        font-size: 0.9rem;
        z-index: 1;
    }
    
    .search-input {
        width: 100%;
        padding: 0.5rem 0.75rem 0.5rem 2.25rem;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        font-size: 0.9rem;
        background: #f8f9fa;
        transition: all 0.2s ease;
    }
    
    .search-input:focus {
        outline: none;
        border-color: #007bff;
        background: #fff;
        box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
    }
    
    .search-clear {
        position: absolute;
        right: 0.5rem;
        background: none;
        border: none;
        color: #6c757d;
        padding: 0.25rem;
        cursor: pointer;
    }
    
    .search-results {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: #fff;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        z-index: 1000;
        max-height: 300px;
        overflow-y: auto;
        margin-top: 2px;
    }
    
    .search-result {
        display: flex;
        align-items: center;
        padding: 0.75rem;
        cursor: pointer;
        border-bottom: 1px solid #f8f9fa;
        gap: 0.75rem;
        transition: background 0.2s ease;
    }
    
    .search-result:hover {
        background: #f8f9fa;
    }
    
    .search-result:last-child {
        border-bottom: none;
    }
    
    .result-icon {
        flex-shrink: 0;
        width: 20px;
        text-align: center;
        color: #6c757d;
    }
    
    .result-content {
        flex: 1;
        min-width: 0;
    }
    
    .result-text {
        font-size: 0.9rem;
        color: #333;
        margin-bottom: 0.25rem;
    }
    
    .result-text mark {
        background: #fff3cd;
        padding: 0;
        font-weight: 600;
    }
    
    .result-path {
        font-size: 0.8rem;
        color: #6c757d;
    }
    
    .no-results {
        padding: 1rem;
        text-align: center;
        color: #6c757d;
        font-size: 0.9rem;
    }
    
    /* Contenido */
    .sidebar-content {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
    }
    
    .sidebar-section {
        border-bottom: 1px solid #f8f9fa;
    }
    
    .section-header {
        padding: 0.75rem 1rem 0.5rem;
    }
    
    .section-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-title i {
        font-size: 0.75rem;
    }
    
    /* Menú */
    .sidebar-menu {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .menu-item {
        position: relative;
    }
    
    .menu-link {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        color: #495057;
        text-decoration: none;
        transition: all 0.2s ease;
        gap: 0.75rem;
        position: relative;
    }
    
    .menu-link:hover {
        background: #f8f9fa;
        color: #007bff;
        text-decoration: none;
    }
    
    .menu-item.active > .menu-link {
        background: #e7f3ff;
        color: #007bff;
        border-right: 3px solid #007bff;
    }
    
    .menu-icon {
        flex-shrink: 0;
        width: 20px;
        text-align: center;
        font-size: 1rem;
    }
    
    .menu-dot {
        width: 6px;
        height: 6px;
        background: #6c757d;
        border-radius: 50%;
        display: inline-block;
    }
    
    .menu-text {
        flex: 1;
        font-size: 0.9rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        transition: opacity 0.3s ease;
    }
    
    .eco-sidebar.collapsed .menu-text {
        opacity: 0;
        width: 0;
    }
    
    .menu-badge {
        flex-shrink: 0;
        font-size: 0.7rem;
        padding: 0.2rem 0.4rem;
        border-radius: 10px;
        font-weight: 600;
        min-width: 18px;
        text-align: center;
        line-height: 1;
    }
    
    .menu-badge.primary {
        background: #007bff;
        color: #fff;
    }
    
    .menu-badge.success {
        background: #28a745;
        color: #fff;
    }
    
    .menu-badge.warning {
        background: #ffc107;
        color: #000;
    }
    
    .menu-badge.danger {
        background: #dc3545;
        color: #fff;
    }
    
    .menu-badge.info {
        background: #17a2b8;
        color: #fff;
    }
    
    .menu-arrow {
        flex-shrink: 0;
        transition: transform 0.2s ease;
        font-size: 0.8rem;
    }
    
    .menu-arrow.expanded {
        transform: rotate(90deg);
    }
    
    .eco-sidebar.collapsed .menu-badge,
    .eco-sidebar.collapsed .menu-arrow {
        opacity: 0;
        width: 0;
    }
    
    /* Submenús */
    .submenu {
        list-style: none;
        padding: 0;
        margin: 0;
        background: #f8f9fa;
        border-top: 1px solid #e9ecef;
    }
    
    .submenu .menu-link {
        padding-left: 3.5rem;
        font-size: 0.85rem;
    }
    
    .submenu .menu-icon {
        width: 16px;
        font-size: 0.8rem;
    }
    
    .submenu .submenu .menu-link {
        padding-left: 5rem;
    }
    
    /* Footer */
    .sidebar-footer {
        border-top: 1px solid #e9ecef;
        padding: 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
    }
    
    .footer-stats {
        flex: 1;
        min-width: 0;
    }
    
    .stat-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #6c757d;
    }
    
    .stat-item i {
        font-size: 0.9rem;
        color: #007bff;
    }
    
    .stat-value {
        font-weight: 600;
        color: #333;
    }
    
    .footer-actions {
        display: flex;
        gap: 0.25rem;
    }
    
    .footer-actions button {
        background: none;
        border: none;
        padding: 0.5rem;
        border-radius: 4px;
        color: #6c757d;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .footer-actions button:hover {
        background: #f8f9fa;
        color: #495057;
    }
    
    /* Overlay */
    .sidebar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0,0,0,0.5);
        z-index: 999;
        backdrop-filter: blur(2px);
    }
    
    /* Temas */
    .eco-sidebar[data-theme="dark"] {
        background: #2c3e50;
        border-color: #34495e;
        color: #ecf0f1;
    }
    
    .eco-sidebar[data-theme="dark"] .sidebar-header {
        border-color: #34495e;
    }
    
    .eco-sidebar[data-theme="dark"] .brand-text {
        color: #ecf0f1;
    }
    
    .eco-sidebar[data-theme="dark"] .menu-link {
        color: #bdc3c7;
    }
    
    .eco-sidebar[data-theme="dark"] .menu-link:hover {
        background: #34495e;
        color: #3498db;
    }
    
    .eco-sidebar[data-theme="dark"] .menu-item.active > .menu-link {
        background: #34495e;
        color: #3498db;
        border-color: #3498db;
    }
    
    .eco-sidebar[data-theme="dark"] .submenu {
        background: #34495e;
        border-color: #2c3e50;
    }
    
    .eco-sidebar[data-theme="dark"] .search-input {
        background: #34495e;
        border-color: #2c3e50;
        color: #ecf0f1;
    }
    
    .eco-sidebar[data-theme="dark"] .search-input:focus {
        border-color: #3498db;
        background: #2c3e50;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .eco-sidebar {
            width: 100%;
            max-width: 320px;
        }
        
        .eco-sidebar.collapsed {
            width: 100%;
            transform: translateX(-100%);
        }
    }
    
    /* Animaciones */
    @keyframes slideIn {
        from {
            transform: translateX(-100%);
        }
        to {
            transform: translateX(0);
        }
    }
    
    @keyframes fadeIn {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }
    
    .eco-sidebar[data-device="mobile"]:not(.collapsed) {
        animation: slideIn 0.3s ease;
    }
    
    .sidebar-overlay {
        animation: fadeIn 0.3s ease;
    }
    
    /* Tooltips para modo colapsado */
    .sidebar-tooltip {
        position: absolute;
        left: 80px;
        top: 50%;
        transform: translateY(-50%);
        background: #333;
        color: #fff;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8rem;
        white-space: nowrap;
        z-index: 1001;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s ease;
        pointer-events: none;
    }
    
    .sidebar-tooltip::before {
        content: '';
        position: absolute;
        left: -5px;
        top: 50%;
        transform: translateY(-50%);
        border: 5px solid transparent;
        border-right-color: #333;
    }
    
    .sidebar-tooltip.show {
        opacity: 1;
        visibility: visible;
    }
    
    /* Scrollbar personalizado */
    .sidebar-content::-webkit-scrollbar {
        width: 4px;
    }
    
    .sidebar-content::-webkit-scrollbar-track {
        background: transparent;
    }
    
    .sidebar-content::-webkit-scrollbar-thumb {
        background: #dee2e6;
        border-radius: 2px;
    }
    
    .sidebar-content::-webkit-scrollbar-thumb:hover {
        background: #adb5bd;
    }
    
    /* Estados de hover mejorados */
    .menu-item:hover .menu-icon {
        transform: scale(1.1);
        transition: transform 0.2s ease;
    }
    
    .menu-link:hover .menu-text {
        color: #007bff;
    }
    
    /* Indicador de carga */
    .sidebar-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    }
    
    .loading-spinner {
        width: 20px;
        height: 20px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;

// Inyectar CSS
if (!document.getElementById('eco-sidebar-styles')) {
    const style = document.createElement('style');
    style.id = 'eco-sidebar-styles';
    style.textContent = sidebarCSS;
    document.head.appendChild(style);
}

// Factory methods para roles específicos
EcoSidebar.createEntrepreneurSidebar = (container, options = {}) => {
    return new EcoSidebar(container, {
        userRole: 'entrepreneur',
        context: 'entrepreneur',
        ...options
    });
};

EcoSidebar.createMentorSidebar = (container, options = {}) => {
    return new EcoSidebar(container, {
        userRole: 'mentor',
        context: 'mentor',
        ...options
    });
};

EcoSidebar.createAdminSidebar = (container, options = {}) => {
    return new EcoSidebar(container, {
        userRole: 'admin',
        context: 'admin',
        enableCustomization: true,
        enableAnalytics: true,
        ...options
    });
};

EcoSidebar.createClientSidebar = (container, options = {}) => {
    return new EcoSidebar(container, {
        userRole: 'client',
        context: 'client',
        ...options
    });
};

// Auto-registro en elemento
Object.defineProperty(EcoSidebar.prototype, 'register', {
    value: function() {
        this.container.ecoSidebar = this;
    }
});

const originalInit = EcoSidebar.prototype.init;
EcoSidebar.prototype.init = function() {
    const result = originalInit.call(this);
    this.register();
    return result;
};

// Exportar
window.EcoSidebar = EcoSidebar;
export default EcoSidebar;