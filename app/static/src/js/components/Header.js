/**
 * Header Component
 * Componente de cabecera principal para el ecosistema de emprendimiento
 * Maneja la navegación, perfil de usuario, notificaciones y búsqueda global
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoHeader {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        if (!this.element) {
            throw new Error('Header element not found');
        }

        this.config = {
            // Configuración básica
            appName: options.appName || 'Ecosistema App',
            logoUrl: options.logoUrl || '/static/img/logo.png',
            
            // Navegación
            navItems: options.navItems || [], // [{ label: 'Inicio', url: '/', icon: 'fa-home' }]
            showSearch: options.showSearch !== false,
            
            // Usuario
            showUserProfile: options.showUserProfile !== false,
            loginUrl: options.loginUrl || '/auth/login',
            logoutUrl: options.logoutUrl || '/auth/logout',
            profileUrl: options.profileUrl || '/profile',
            
            // Notificaciones
            showNotifications: options.showNotifications !== false,
            
            // Callbacks
            onSearch: options.onSearch || null,
            onNavClick: options.onNavClick || null,
            onLogout: options.onLogout || null,
            
            // Contexto del ecosistema
            user: options.user || null, // Objeto de usuario actual
            
            ...options
        };

        this.state = {
            isMobileMenuOpen: false,
            isProfileDropdownOpen: false,
            isNotificationsOpen: false,
            unreadNotifications: 0,
            searchTerm: ''
        };

        this.eventListeners = [];
        this.init();
    }

    /**
     * Inicialización del componente
     */
    init() {
        try {
            this.render();
            this.setupEventListeners();
            this.updateUserState();
            
            if (this.config.showNotifications) {
                this.initNotificationSystem();
            }
            
            console.log('🔝 EcoHeader initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing EcoHeader:', error);
        }
    }

    /**
     * Renderizar la cabecera
     */
    render() {
        const navHTML = this.renderNavigation();
        const userActionsHTML = this.renderUserActions();
        const searchHTML = this.config.showSearch ? this.renderSearch() : '';

        this.element.innerHTML = `
            <nav class="navbar navbar-expand-lg navbar-light bg-light fixed-top shadow-sm">
                <div class="container-fluid">
                    <a class="navbar-brand" href="/">
                        <img src="${this.config.logoUrl}" alt="${this.config.appName} Logo" height="30" class="d-inline-block align-top">
                        ${this.config.appName}
                    </a>
                    <button class="navbar-toggler" type="button" data-action="toggleMobileMenu" aria-label="Toggle navigation">
                        <span class="navbar-toggler-icon"></span>
                    </button>
                    <div class="collapse navbar-collapse" id="mainNavbar">
                        ${navHTML}
                        ${searchHTML}
                        ${userActionsHTML}
                    </div>
                </div>
            </nav>
        `;
        
        // Guardar referencias a elementos dinámicos
        this.mobileMenuToggler = this.element.querySelector('[data-action="toggleMobileMenu"]');
        this.navbarCollapse = this.element.querySelector('#mainNavbar');
    }

    /**
     * Renderizar elementos de navegación
     */
    renderNavigation() {
        if (!this.config.navItems.length) return '';

        let navLinksHTML = '';
        this.config.navItems.forEach(item => {
            navLinksHTML += `
                <li class="nav-item">
                    <a class="nav-link" href="${item.url}" data-nav-id="${item.id || item.label.toLowerCase()}">
                        ${item.icon ? `<i class="fa ${item.icon} me-1"></i>` : ''}
                        ${item.label}
                    </a>
                </li>
            `;
        });

        return `<ul class="navbar-nav me-auto mb-2 mb-lg-0">${navLinksHTML}</ul>`;
    }

    /**
     * Renderizar barra de búsqueda
     */
    renderSearch() {
        return `
            <form class="d-flex ms-lg-3" role="search" data-form="search">
                <input class="form-control form-control-sm me-2" type="search" placeholder="Buscar en el ecosistema..." aria-label="Buscar" name="q">
                <button class="btn btn-sm btn-outline-primary" type="submit">
                    <i class="fa fa-search"></i>
                </button>
            </form>
        `;
    }

    /**
     * Renderizar acciones de usuario (perfil, notificaciones, login/logout)
     */
    renderUserActions() {
        let actionsHTML = '<ul class="navbar-nav ms-auto mb-2 mb-lg-0 align-items-lg-center">';

        if (this.config.user && this.config.user.isAuthenticated) {
            // Usuario autenticado
            if (this.config.showNotifications) {
                actionsHTML += `
                    <li class="nav-item dropdown">
                        <a class="nav-link notification-bell" href="#" data-action="toggleNotifications" aria-label="Notificaciones">
                            <i class="fa fa-bell"></i>
                            <span class="badge rounded-pill bg-danger notification-count" style="display: none;">0</span>
                        </a>
                        <div class="dropdown-menu dropdown-menu-end notification-dropdown p-0">
                            <!-- Contenido de notificaciones se carga aquí -->
                        </div>
                    </li>
                `;
            }

            actionsHTML += `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle d-flex align-items-center" href="#" data-action="toggleProfileDropdown" aria-label="Perfil de usuario">
                        <img src="${this.config.user.avatarUrl || '/static/img/default-avatar.png'}" alt="Avatar" class="rounded-circle me-2" height="24" width="24">
                        ${this.config.user.displayName || 'Usuario'}
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item" href="${this.config.profileUrl}"><i class="fa fa-user me-2"></i>Mi Perfil</a></li>
                        <li><a class="dropdown-item" href="/settings"><i class="fa fa-cog me-2"></i>Configuración</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="#" data-action="logout"><i class="fa fa-sign-out-alt me-2"></i>Cerrar Sesión</a></li>
                    </ul>
                </li>
            `;
        } else {
            // Usuario no autenticado
            actionsHTML += `
                <li class="nav-item">
                    <a class="btn btn-outline-primary btn-sm me-2" href="${this.config.loginUrl}">Iniciar Sesión</a>
                </li>
                <li class="nav-item">
                    <a class="btn btn-primary btn-sm" href="/auth/register">Registrarse</a>
                </li>
            `;
        }

        actionsHTML += '</ul>';
        return actionsHTML;
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        // Toggle menú móvil
        if (this.mobileMenuToggler) {
            this.addEventListener(this.mobileMenuToggler, 'click', (e) => this.toggleMobileMenu(e));
        }

        // Clicks en acciones
        this.addEventListener(this.element, 'click', (e) => {
            const actionTarget = e.target.closest('[data-action]');
            if (actionTarget) {
                const action = actionTarget.dataset.action;
                this.handleAction(action, e);
            }
        });
        
        // Submit de búsqueda
        const searchForm = this.element.querySelector('[data-form="search"]');
        if (searchForm) {
            this.addEventListener(searchForm, 'submit', (e) => this.handleSearchSubmit(e));
        }
    }

    /**
     * Manejar acciones
     */
    handleAction(action, event) {
        switch (action) {
            case 'toggleMobileMenu':
                this.toggleMobileMenu();
                break;
            case 'toggleProfileDropdown':
                event.preventDefault();
                this.toggleProfileDropdown(event.currentTarget.parentNode);
                break;
            case 'toggleNotifications':
                event.preventDefault();
                this.toggleNotificationsDropdown(event.currentTarget.parentNode);
                break;
            case 'logout':
                event.preventDefault();
                this.logout();
                break;
        }
    }

    /**
     * Toggle menú móvil
     */
    toggleMobileMenu() {
        this.state.isMobileMenuOpen = !this.state.isMobileMenuOpen;
        this.navbarCollapse.classList.toggle('show', this.state.isMobileMenuOpen);
        this.mobileMenuToggler.setAttribute('aria-expanded', this.state.isMobileMenuOpen);
    }

    /**
     * Toggle dropdown de perfil
     */
    toggleProfileDropdown(dropdownElement) {
        this.state.isProfileDropdownOpen = !this.state.isProfileDropdownOpen;
        dropdownElement.classList.toggle('show', this.state.isProfileDropdownOpen);
        const menu = dropdownElement.querySelector('.dropdown-menu');
        if (menu) {
            menu.classList.toggle('show', this.state.isProfileDropdownOpen);
        }
        // Cerrar otros dropdowns
        if (this.state.isProfileDropdownOpen && this.state.isNotificationsOpen) {
            this.closeNotificationsDropdown();
        }
    }
    
    closeProfileDropdown() {
        const dropdownElement = this.element.querySelector('.nav-item.dropdown a[data-action="toggleProfileDropdown"]')?.parentNode;
        if (dropdownElement && this.state.isProfileDropdownOpen) {
            this.state.isProfileDropdownOpen = false;
            dropdownElement.classList.remove('show');
            const menu = dropdownElement.querySelector('.dropdown-menu');
            if (menu) menu.classList.remove('show');
        }
    }

    /**
     * Toggle dropdown de notificaciones
     */
    toggleNotificationsDropdown(dropdownElement) {
        this.state.isNotificationsOpen = !this.state.isNotificationsOpen;
        dropdownElement.classList.toggle('show', this.state.isNotificationsOpen);
        const menu = dropdownElement.querySelector('.dropdown-menu');
        if (menu) {
            menu.classList.toggle('show', this.state.isNotificationsOpen);
            if (this.state.isNotificationsOpen) {
                this.loadNotifications();
            }
        }
         // Cerrar otros dropdowns
        if (this.state.isNotificationsOpen && this.state.isProfileDropdownOpen) {
            this.closeProfileDropdown();
        }
    }

    closeNotificationsDropdown() {
        const dropdownElement = this.element.querySelector('.nav-item.dropdown a[data-action="toggleNotifications"]')?.parentNode;
        if (dropdownElement && this.state.isNotificationsOpen) {
            this.state.isNotificationsOpen = false;
            dropdownElement.classList.remove('show');
            const menu = dropdownElement.querySelector('.dropdown-menu');
            if (menu) menu.classList.remove('show');
        }
    }

    /**
     * Manejar submit de búsqueda
     */
    handleSearchSubmit(event) {
        event.preventDefault();
        const searchInput = event.target.querySelector('input[name="q"]');
        const term = searchInput.value.trim();

        if (this.config.onSearch) {
            this.config.onSearch(term);
        } else {
            // Comportamiento por defecto: redirigir a página de búsqueda
            if (term) {
                window.location.href = `/search?q=${encodeURIComponent(term)}`;
            }
        }
    }

    /**
     * Cerrar sesión
     */
    async logout() {
        try {
            // Idealmente, esto haría una petición POST al servidor para invalidar la sesión
            await fetch(this.config.logoutUrl, { method: 'POST', headers: {'X-CSRFToken': this.getCSRFToken()} });
            
            if (this.config.onLogout) {
                this.config.onLogout();
            } else {
                // Comportamiento por defecto: redirigir a la página de inicio
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Error al cerrar sesión:', error);
            // Mostrar error al usuario si es necesario
        }
    }

    /**
     * Actualizar estado del usuario (ej. después de login/logout)
     */
    updateUserState(userData = null) {
        this.config.user = userData || { isAuthenticated: false }; // Simulación
        // Re-renderizar solo las acciones de usuario para eficiencia
        const userActionsContainer = this.element.querySelector('#mainNavbar > ul.navbar-nav.ms-auto');
        if (userActionsContainer) {
            userActionsContainer.outerHTML = this.renderUserActions();
        }
        if (this.config.showNotifications) {
            this.updateNotificationCount();
        }
    }

    /**
     * Inicializar sistema de notificaciones
     */
    initNotificationSystem() {
        if (window.notifications) {
            // Escuchar eventos de notificaciones
            window.addEventListener('notification:new', (e) => this.handleNewNotification(e.detail));
            window.addEventListener('notification:read', (e) => this.handleNotificationRead(e.detail));
            window.addEventListener('notification:unread_count_update', (e) => this.updateNotificationCount(e.detail.count));
            
            // Obtener contador inicial
            this.updateNotificationCount(window.notifications.getUnreadCount());
        }
    }

    /**
     * Cargar notificaciones en el dropdown
     */
    async loadNotifications() {
        const dropdownMenu = this.element.querySelector('.notification-dropdown');
        if (!dropdownMenu) return;

        dropdownMenu.innerHTML = '<div class="p-3 text-center"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Cargando...</span></div></div>';

        try {
            // Simulación de carga de notificaciones
            // En una app real, esto vendría de window.notifications o una API
            const notifications = await this.fetchNotifications(); 
            
            if (notifications.length === 0) {
                dropdownMenu.innerHTML = '<div class="p-3 text-center text-muted">No hay notificaciones nuevas.</div>';
                return;
            }

            let notificationsHTML = '<ul class="list-unstyled mb-0">';
            notifications.slice(0, 5).forEach(notif => { // Mostrar máximo 5
                notificationsHTML += `
                    <li class="notification-item ${notif.isRead ? 'read' : ''}">
                        <a class="dropdown-item d-flex align-items-start py-2 px-3" href="${notif.link || '#'}">
                            <div class="flex-shrink-0 me-2">
                                <i class="fa ${this.getNotificationIcon(notif.type)} fa-fw"></i>
                            </div>
                            <div class="flex-grow-1">
                                <h6 class="mb-0 notification-title">${notif.title}</h6>
                                <p class="mb-0 notification-message small text-muted">${this.truncateText(notif.message, 50)}</p>
                                <small class="text-muted">${this.formatTimeAgo(notif.timestamp)}</small>
                            </div>
                        </a>
                    </li>
                `;
            });
            notificationsHTML += '</ul>';
            
            if (notifications.length > 0) {
                 notificationsHTML += `
                    <div class="dropdown-footer text-center py-2 border-top">
                        <a href="/notifications" class="small">Ver todas las notificaciones</a>
                    </div>
                `;
            }

            dropdownMenu.innerHTML = notificationsHTML;
        } catch (error) {
            console.error("Error cargando notificaciones:", error);
            dropdownMenu.innerHTML = '<div class="p-3 text-center text-danger">Error al cargar notificaciones.</div>';
        }
    }
    
    // Simulación de fetch de notificaciones
    async fetchNotifications() {
        return new Promise(resolve => {
            setTimeout(() => {
                resolve([
                    { id: '1', title: 'Nuevo Proyecto Creado', message: 'El proyecto "EcoHuerta Urbana" ha sido creado.', type: 'project', timestamp: new Date(Date.now() - 3600000), isRead: false, link: '/projects/1' },
                    { id: '2', title: 'Reunión Programada', message: 'Tienes una reunión de mentoría mañana a las 10 AM.', type: 'meeting', timestamp: new Date(Date.now() - 7200000), isRead: true, link: '/meetings/1' },
                    { id: '3', title: 'Mensaje Nuevo', message: 'Has recibido un nuevo mensaje de Ana Pérez.', type: 'message', timestamp: new Date(Date.now() - 10800000), isRead: false, link: '/chat/1' },
                ]);
            }, 500);
        });
    }

    getNotificationIcon(type) {
        const icons = {
            project: 'fa-rocket',
            meeting: 'fa-calendar-alt',
            message: 'fa-comment',
            system: 'fa-info-circle',
            default: 'fa-bell'
        };
        return icons[type] || icons.default;
    }

    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    formatTimeAgo(timestamp) {
        const now = new Date();
        const seconds = Math.round((now - new Date(timestamp)) / 1000);
        
        if (seconds < 60) return 'hace un momento';
        const minutes = Math.round(seconds / 60);
        if (minutes < 60) return `hace ${minutes} min`;
        const hours = Math.round(minutes / 60);
        if (hours < 24) return `hace ${hours} h`;
        const days = Math.round(hours / 24);
        return `hace ${days} día(s)`;
    }

    /**
     * Manejar nueva notificación (ej. de WebSocket)
     */
    handleNewNotification(notification) {
        this.updateNotificationCount(this.state.unreadNotifications + 1);
        // Si el dropdown está abierto, recargar
        if (this.state.isNotificationsOpen) {
            this.loadNotifications();
        }
    }

    /**
     * Manejar notificación leída
     */
    handleNotificationRead(notificationId) {
        this.updateNotificationCount(Math.max(0, this.state.unreadNotifications - 1));
         // Si el dropdown está abierto, recargar
        if (this.state.isNotificationsOpen) {
            this.loadNotifications();
        }
    }

    /**
     * Actualizar contador de notificaciones
     */
    updateNotificationCount(count = null) {
        if (count !== null) {
            this.state.unreadNotifications = count;
        }
        
        const countElement = this.element.querySelector('.notification-count');
        if (countElement) {
            countElement.textContent = this.state.unreadNotifications;
            countElement.style.display = this.state.unreadNotifications > 0 ? 'inline-block' : 'none';
        }
    }

    /**
     * Limpieza
     */
    destroy() {
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];
        this.element.innerHTML = ''; // Limpiar contenido
        console.log('🔝 EcoHeader destroyed');
    }
    
    // Helper para añadir event listeners y guardarlos para limpieza
    addEventListener(element, event, handler) {
        element.addEventListener(event, handler);
        this.eventListeners.push({ element, event, handler });
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    }
}

// Exportar para uso global si es necesario
window.EcoHeader = EcoHeader;

// Inicializar cabecera si existe el elemento
document.addEventListener('DOMContentLoaded', () => {
    const headerElement = document.querySelector('#appHeader'); // Asume que tu cabecera tiene id="appHeader"
    if (headerElement) {
        // Simular datos de usuario y navegación
        const currentUser = window.App?.currentUser || { isAuthenticated: false }; 
        const navItems = [
            { label: 'Dashboard', url: '/dashboard', icon: 'fa-tachometer-alt' },
            { label: 'Proyectos', url: '/projects', icon: 'fa-rocket' },
            { label: 'Mentorías', url: '/mentorships', icon: 'fa-users' },
            { label: 'Recursos', url: '/resources', icon: 'fa-book' }
        ];
        
        new EcoHeader(headerElement, {
            appName: 'Mi Ecosistema',
            user: currentUser,
            navItems: navItems
        });
    }
});

export default EcoHeader;
