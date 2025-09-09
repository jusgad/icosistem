/**
 * Client-Side Router for Ecosistema Emprendimiento
 * ================================================
 * 
 * Router avanzado del lado cliente que maneja navegación SPA,
 * autenticación, autorización, lazy loading y estados de la aplicación
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js
 */

'use strict';

/**
 * Router principal del ecosistema
 */
class EcosistemaRouter {
    constructor(app) {
        this.app = app;
        this.main = app.main;
        
        // Configuración del router
        this.config = {
            baseUrl: window.location.origin,
            basePath: '',
            hashMode: false,
            history: true,
            scrollTop: true,
            preloadDelay: 100,
            transitionDuration: 300
        };
        
        // Estado del router
        this.state = {
            currentRoute: null,
            previousRoute: null,
            isNavigating: false,
            params: {},
            query: {},
            hash: '',
            title: '',
            breadcrumbs: []
        };
        
        // Almacenamiento de rutas
        this.routes = new Map();
        this.middleware = [];
        this.guards = new Map();
        this.layouts = new Map();
        this.components = new Map();
        
        // Cache para módulos cargados
        this.moduleCache = new Map();
        this.preloadedModules = new Set();
        
        // Event listeners
        this.listeners = new Map();
        
        // Inicializar automáticamente
        this.init();
    }

    /**
     * Inicializar router
     */
    init() {
        // // console.log('🧭 Inicializando Router del Ecosistema');
        
        // Configurar rutas del sistema
        this.setupRoutes();
        
        // Configurar middleware
        this.setupMiddleware();
        
        // Configurar guards
        this.setupGuards();
        
        // Configurar layouts
        this.setupLayouts();
        
        // Vincular eventos del navegador
        this.bindBrowserEvents();
        
        // Vincular eventos de la aplicación
        this.bindApplicationEvents();
        
        // Manejar ruta inicial
        this.handleInitialRoute();
        
        // // console.log('✅ Router inicializado correctamente');
    }

    /**
     * Configurar rutas del sistema
     */
    setupRoutes() {
        // Rutas públicas
        this.addRoute('/', {
            name: 'home',
            component: 'HomePage',
            layout: 'public',
            title: 'Inicio - Ecosistema Emprendimiento',
            meta: { requiresAuth: false }
        });

        this.addRoute('/login', {
            name: 'login',
            component: 'LoginPage',
            layout: 'auth',
            title: 'Iniciar Sesión',
            meta: { requiresAuth: false, redirectIfAuth: '/dashboard' }
        });

        this.addRoute('/register', {
            name: 'register',
            component: 'RegisterPage',
            layout: 'auth',
            title: 'Registrarse',
            meta: { requiresAuth: false, redirectIfAuth: '/dashboard' }
        });

        this.addRoute('/forgot-password', {
            name: 'forgot-password',
            component: 'ForgotPasswordPage',
            layout: 'auth',
            title: 'Recuperar Contraseña',
            meta: { requiresAuth: false }
        });

        // Rutas protegidas generales
        this.addRoute('/dashboard', {
            name: 'dashboard',
            component: 'DashboardPage',
            layout: 'app',
            title: 'Dashboard',
            meta: { requiresAuth: true },
            breadcrumbs: [{ name: 'Dashboard', path: '/dashboard' }]
        });

        this.addRoute('/profile', {
            name: 'profile',
            component: 'ProfilePage',
            layout: 'app',
            title: 'Mi Perfil',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Mi Perfil', path: '/profile' }
            ]
        });

        this.addRoute('/settings', {
            name: 'settings',
            component: 'SettingsPage',
            layout: 'app',
            title: 'Configuración',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Configuración', path: '/settings' }
            ]
        });

        this.addRoute('/notifications', {
            name: 'notifications',
            component: 'NotificationsPage',
            layout: 'app',
            title: 'Notificaciones',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Notificaciones', path: '/notifications' }
            ]
        });

        // Rutas de proyectos
        this.addRoute('/projects', {
            name: 'projects',
            component: 'ProjectsListPage',
            layout: 'app',
            title: 'Proyectos',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Proyectos', path: '/projects' }
            ]
        });

        this.addRoute('/projects/create', {
            name: 'projects.create',
            component: 'ProjectCreatePage',
            layout: 'app',
            title: 'Crear Proyecto',
            meta: { requiresAuth: true, roles: ['entrepreneur'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Proyectos', path: '/projects' },
                { name: 'Crear Proyecto', path: '/projects/create' }
            ]
        });

        this.addRoute('/projects/:id', {
            name: 'projects.show',
            component: 'ProjectDetailPage',
            layout: 'app',
            title: 'Detalle del Proyecto',
            meta: { requiresAuth: true },
            breadcrumbs: async (params) => [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Proyectos', path: '/projects' },
                { name: await this.getProjectName(params.id), path: `/projects/${params.id}` }
            ]
        });

        this.addRoute('/projects/:id/edit', {
            name: 'projects.edit',
            component: 'ProjectEditPage',
            layout: 'app',
            title: 'Editar Proyecto',
            meta: { requiresAuth: true, roles: ['entrepreneur'] },
            breadcrumbs: async (params) => [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Proyectos', path: '/projects' },
                { name: await this.getProjectName(params.id), path: `/projects/${params.id}` },
                { name: 'Editar', path: `/projects/${params.id}/edit` }
            ]
        });

        // Rutas de calendario y reuniones
        this.addRoute('/calendar', {
            name: 'calendar',
            component: 'CalendarPage',
            layout: 'app',
            title: 'Calendario',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Calendario', path: '/calendar' }
            ]
        });

        this.addRoute('/meetings', {
            name: 'meetings',
            component: 'MeetingsListPage',
            layout: 'app',
            title: 'Reuniones',
            meta: { requiresAuth: true },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Reuniones', path: '/meetings' }
            ]
        });

        this.addRoute('/meetings/:id', {
            name: 'meetings.show',
            component: 'MeetingDetailPage',
            layout: 'app',
            title: 'Detalle de Reunión',
            meta: { requiresAuth: true },
            breadcrumbs: async (params) => [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Reuniones', path: '/meetings' },
                { name: await this.getMeetingTitle(params.id), path: `/meetings/${params.id}` }
            ]
        });

        // Rutas específicas por tipo de usuario
        this.setupUserTypeRoutes();
        
        // Rutas de error
        this.addRoute('/404', {
            name: 'not-found',
            component: 'NotFoundPage',
            layout: 'error',
            title: 'Página no encontrada',
            meta: { requiresAuth: false }
        });

        this.addRoute('/403', {
            name: 'forbidden',
            component: 'ForbiddenPage',
            layout: 'error',
            title: 'Acceso denegado',
            meta: { requiresAuth: false }
        });

        this.addRoute('/500', {
            name: 'server-error',
            component: 'ServerErrorPage',
            layout: 'error',
            title: 'Error del servidor',
            meta: { requiresAuth: false }
        });
    }

    /**
     * Configurar rutas específicas por tipo de usuario
     */
    setupUserTypeRoutes() {
        // Rutas para emprendedores
        this.addRoute('/entrepreneur/mentorship', {
            name: 'entrepreneur.mentorship',
            component: 'EntrepreneurMentorshipPage',
            layout: 'app',
            title: 'Mi Mentoría',
            meta: { requiresAuth: true, roles: ['entrepreneur'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Mi Mentoría', path: '/entrepreneur/mentorship' }
            ]
        });

        this.addRoute('/entrepreneur/progress', {
            name: 'entrepreneur.progress',
            component: 'EntrepreneurProgressPage',
            layout: 'app',
            title: 'Mi Progreso',
            meta: { requiresAuth: true, roles: ['entrepreneur'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Mi Progreso', path: '/entrepreneur/progress' }
            ]
        });

        // Rutas para mentores
        this.addRoute('/mentor/mentees', {
            name: 'mentor.mentees',
            component: 'MentorMenteesPage',
            layout: 'app',
            title: 'Mis Emprendedores',
            meta: { requiresAuth: true, roles: ['mentor'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Mis Emprendedores', path: '/mentor/mentees' }
            ]
        });

        this.addRoute('/mentor/sessions', {
            name: 'mentor.sessions',
            component: 'MentorSessionsPage',
            layout: 'app',
            title: 'Sesiones de Mentoría',
            meta: { requiresAuth: true, roles: ['mentor'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Sesiones', path: '/mentor/sessions' }
            ]
        });

        this.addRoute('/mentor/availability', {
            name: 'mentor.availability',
            component: 'MentorAvailabilityPage',
            layout: 'app',
            title: 'Mi Disponibilidad',
            meta: { requiresAuth: true, roles: ['mentor'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Mi Disponibilidad', path: '/mentor/availability' }
            ]
        });

        // Rutas para administradores
        this.addRoute('/admin/users', {
            name: 'admin.users',
            component: 'AdminUsersPage',
            layout: 'app',
            title: 'Gestión de Usuarios',
            meta: { requiresAuth: true, roles: ['admin'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Usuarios', path: '/admin/users' }
            ]
        });

        this.addRoute('/admin/analytics', {
            name: 'admin.analytics',
            component: 'AdminAnalyticsPage',
            layout: 'app',
            title: 'Analytics',
            meta: { requiresAuth: true, roles: ['admin'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Analytics', path: '/admin/analytics' }
            ]
        });

        this.addRoute('/admin/system', {
            name: 'admin.system',
            component: 'AdminSystemPage',
            layout: 'app',
            title: 'Sistema',
            meta: { requiresAuth: true, roles: ['admin'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Sistema', path: '/admin/system' }
            ]
        });

        // Rutas para clientes
        this.addRoute('/client/portfolio', {
            name: 'client.portfolio',
            component: 'ClientPortfolioPage',
            layout: 'app',
            title: 'Portfolio',
            meta: { requiresAuth: true, roles: ['client'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Portfolio', path: '/client/portfolio' }
            ]
        });

        this.addRoute('/client/reports', {
            name: 'client.reports',
            component: 'ClientReportsPage',
            layout: 'app',
            title: 'Reportes',
            meta: { requiresAuth: true, roles: ['client'] },
            breadcrumbs: [
                { name: 'Dashboard', path: '/dashboard' },
                { name: 'Reportes', path: '/client/reports' }
            ]
        });
    }

    /**
     * Configurar middleware
     */
    setupMiddleware() {
        // Middleware de autenticación
        this.addMiddleware('auth', async (route, next) => {
            if (route.meta?.requiresAuth && !this.isAuthenticated()) {
                return this.navigate('/login', { replace: true });
            }
            next();
        });

        // Middleware de autorización por roles
        this.addMiddleware('roles', async (route, next) => {
            if (route.meta?.roles && !this.hasRequiredRole(route.meta.roles)) {
                return this.navigate('/403', { replace: true });
            }
            next();
        });

        // Middleware de redirección si ya está autenticado
        this.addMiddleware('guest', async (route, next) => {
            if (route.meta?.redirectIfAuth && this.isAuthenticated()) {
                return this.navigate(route.meta.redirectIfAuth, { replace: true });
            }
            next();
        });

        // Middleware de carga de datos
        this.addMiddleware('loadData', async (route, next) => {
            if (route.meta?.loadData) {
                try {
                    await this.loadRouteData(route);
                } catch (error) {
                    // // console.error('Error cargando datos de ruta:', error);
                    return this.navigate('/500', { replace: true });
                }
            }
            next();
        });

        // Middleware de analytics
        this.addMiddleware('analytics', async (route, next) => {
            if (this.app.features?.analytics) {
                this.app.analytics?.track('page_view', {
                    route: route.name,
                    path: route.path,
                    title: route.title
                });
            }
            next();
        });
    }

    /**
     * Configurar guards de navegación
     */
    setupGuards() {
        // Guard antes de navegar
        this.addGuard('beforeNavigate', async (to, from) => {
            // Prevenir navegación si hay cambios sin guardar
            if (this.hasUnsavedChanges()) {
                const confirmed = await this.confirmNavigation();
                if (!confirmed) return false;
            }
            return true;
        });

        // Guard después de navegar
        this.addGuard('afterNavigate', async (to, from) => {
            // Actualizar título de la página
            document.title = to.title || 'Ecosistema Emprendimiento';
            
            // Actualizar breadcrumbs
            await this.updateBreadcrumbs(to);
            
            // Scroll al top si está configurado
            if (this.config.scrollTop) {
                window.scrollTo(0, 0);
            }
            
            // Emit navigation event
            this.app.emit('routeChanged', { to, from });
        });

        // Guard de error
        this.addGuard('onError', async (error, route) => {
            // // console.error('Error en navegación:', error);
            
            if (error.status === 404) {
                return this.navigate('/404', { replace: true });
            } else if (error.status === 403) {
                return this.navigate('/403', { replace: true });
            } else {
                return this.navigate('/500', { replace: true });
            }
        });
    }

    /**
     * Configurar layouts
     */
    setupLayouts() {
        this.addLayout('public', {
            component: 'PublicLayout',
            template: '#public-layout-template'
        });

        this.addLayout('auth', {
            component: 'AuthLayout',
            template: '#auth-layout-template'
        });

        this.addLayout('app', {
            component: 'AppLayout',
            template: '#app-layout-template'
        });

        this.addLayout('error', {
            component: 'ErrorLayout',
            template: '#error-layout-template'
        });
    }

    /**
     * Agregar ruta
     */
    addRoute(path, config) {
        const routeConfig = {
            path,
            pattern: this.createPathPattern(path),
            ...config
        };
        
        this.routes.set(path, routeConfig);
    }

    /**
     * Agregar middleware
     */
    addMiddleware(name, handler) {
        this.middleware.push({ name, handler });
    }

    /**
     * Agregar guard
     */
    addGuard(type, handler) {
        if (!this.guards.has(type)) {
            this.guards.set(type, []);
        }
        this.guards.get(type).push(handler);
    }

    /**
     * Agregar layout
     */
    addLayout(name, config) {
        this.layouts.set(name, config);
    }

    /**
     * Crear patrón de ruta
     */
    createPathPattern(path) {
        const pattern = path
            .replace(/\/:([^/]+)/g, '/(?<$1>[^/]+)')
            .replace(/\*/g, '.*');
        
        return new RegExp(`^${pattern}$`);
    }

    /**
     * Vincular eventos del navegador
     */
    bindBrowserEvents() {
        // Navegación con History API
        window.addEventListener('popstate', (event) => {
            this.handleRoute(window.location.pathname, { 
                replace: true, 
                skipHistory: true 
            });
        });

        // Interceptar clics en enlaces
        document.addEventListener('click', (event) => {
            const link = event.target.closest('a[href]');
            if (link && this.shouldInterceptLink(link)) {
                event.preventDefault();
                this.navigate(link.getAttribute('href'));
            }
        });

        // Manejar envío de formularios
        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (form.dataset.navigate) {
                event.preventDefault();
                this.handleFormSubmit(form);
            }
        });
    }

    /**
     * Vincular eventos de la aplicación
     */
    bindApplicationEvents() {
        // Cambio de autenticación
        this.app.on('authChanged', (event) => {
            if (!event.detail.authenticated) {
                this.navigate('/login', { replace: true });
            }
        });

        // Cambio de rol
        this.app.on('roleChanged', (event) => {
            // Verificar si la ruta actual sigue siendo válida
            const currentRoute = this.getCurrentRoute();
            if (currentRoute && !this.hasRequiredRole(currentRoute.meta?.roles)) {
                this.navigate('/dashboard', { replace: true });
            }
        });

        // Error de red
        this.app.on('networkError', (event) => {
            if (event.detail.status >= 500) {
                this.navigate('/500', { replace: true });
            }
        });
    }

    /**
     * Manejar ruta inicial
     */
    handleInitialRoute() {
        const currentPath = window.location.pathname;
        this.handleRoute(currentPath, { replace: true, skipHistory: true });
    }

    /**
     * Navegar a una ruta
     */
    async navigate(path, options = {}) {
        const config = {
            replace: false,
            skipHistory: false,
            data: null,
            ...options
        };

        // Prevenir navegación múltiple simultánea
        if (this.state.isNavigating) {
            return false;
        }

        try {
            this.state.isNavigating = true;
            
            // Ejecutar guards antes de navegar
            const canNavigate = await this.executeGuards('beforeNavigate', path, this.state.currentRoute);
            if (!canNavigate) {
                return false;
            }

            // Manejar la ruta
            const result = await this.handleRoute(path, config);
            
            // Actualizar historial del navegador
            if (!config.skipHistory) {
                if (config.replace) {
                    window.history.replaceState(config.data, '', path);
                } else {
                    window.history.pushState(config.data, '', path);
                }
            }

            return result;

        } catch (error) {
            await this.executeGuards('onError', error, path);
            return false;
        } finally {
            this.state.isNavigating = false;
        }
    }

    /**
     * Manejar ruta
     */
    async handleRoute(path, options = {}) {
        const route = this.findRoute(path);
        
        if (!route) {
            return this.navigate('/404', { replace: true });
        }

        // Parsear parámetros
        const params = this.parseParams(path, route);
        const query = this.parseQuery();
        const hash = window.location.hash.substring(1);

        // Actualizar estado
        const previousRoute = this.state.currentRoute;
        this.state.previousRoute = previousRoute;
        this.state.currentRoute = route;
        this.state.params = params;
        this.state.query = query;
        this.state.hash = hash;

        // Ejecutar middleware
        await this.executeMiddleware(route);

        // Cargar layout si es necesario
        await this.loadLayout(route.layout);

        // Cargar componente
        await this.loadComponent(route.component, { params, query, hash });

        // Ejecutar guards después de navegar
        await this.executeGuards('afterNavigate', route, previousRoute);

        return true;
    }

    /**
     * Encontrar ruta que coincida con el path
     */
    findRoute(path) {
        for (const [routePath, route] of this.routes) {
            const match = path.match(route.pattern);
            if (match) {
                return { ...route, match };
            }
        }
        return null;
    }

    /**
     * Parsear parámetros de ruta
     */
    parseParams(path, route) {
        const params = {};
        const match = path.match(route.pattern);
        
        if (match && match.groups) {
            Object.assign(params, match.groups);
        }
        
        return params;
    }

    /**
     * Parsear query string
     */
    parseQuery() {
        const params = new URLSearchParams(window.location.search);
        const query = {};
        
        for (const [key, value] of params) {
            query[key] = value;
        }
        
        return query;
    }

    /**
     * Ejecutar middleware
     */
    async executeMiddleware(route) {
        for (const middleware of this.middleware) {
            await new Promise((resolve) => {
                middleware.handler(route, resolve);
            });
        }
    }

    /**
     * Ejecutar guards
     */
    async executeGuards(type, ...args) {
        const guards = this.guards.get(type) || [];
        
        for (const guard of guards) {
            const result = await guard(...args);
            if (result === false) {
                return false;
            }
        }
        
        return true;
    }

    /**
     * Cargar layout
     */
    async loadLayout(layoutName) {
        if (!layoutName) return;

        const layout = this.layouts.get(layoutName);
        if (!layout) {
            // console.warn(`Layout ${layoutName} no encontrado`);
            return;
        }

        // Cargar layout si no está cargado
        if (!this.components.has(layoutName)) {
            const LayoutComponent = await this.loadModule(`layouts/${layout.component}`);
            this.components.set(layoutName, LayoutComponent);
        }

        // Aplicar layout
        const LayoutComponent = this.components.get(layoutName);
        if (LayoutComponent && LayoutComponent.apply) {
            LayoutComponent.apply();
        }
    }

    /**
     * Cargar componente de página
     */
    async loadComponent(componentName, context = {}) {
        if (!componentName) return;

        try {
            // Mostrar loading
            this.showPageLoading();

            // Cargar componente si no está en cache
            if (!this.components.has(componentName)) {
                const PageComponent = await this.loadModule(`pages/${componentName}`);
                this.components.set(componentName, PageComponent);
            }

            // Obtener y renderizar componente
            const PageComponent = this.components.get(componentName);
            if (PageComponent) {
                await this.renderComponent(PageComponent, context);
            }

        } catch (error) {
            // // console.error(`Error cargando componente ${componentName}:`, error);
            throw error;
        } finally {
            this.hidePageLoading();
        }
    }

    /**
     * Cargar módulo dinámicamente
     */
    async loadModule(modulePath) {
        // Verificar cache
        if (this.moduleCache.has(modulePath)) {
            return this.moduleCache.get(modulePath);
        }

        try {
            const fullPath = `/static/dist/js/modules/${modulePath}.js`;
            const module = await import(fullPath);
            const ModuleClass = module.default || module;
            
            // Guardar en cache
            this.moduleCache.set(modulePath, ModuleClass);
            
            return ModuleClass;

        } catch (error) {
            // // console.error(`Error cargando módulo ${modulePath}:`, error);
            throw error;
        }
    }

    /**
     * Renderizar componente
     */
    async renderComponent(ComponentClass, context) {
        // Encontrar contenedor principal
        const container = document.querySelector('#app-content') || 
                         document.querySelector('main') || 
                         document.body;

        // Destruir componente anterior si existe
        if (this.currentComponent && this.currentComponent.destroy) {
            this.currentComponent.destroy();
        }

        // Crear e inicializar nuevo componente
        this.currentComponent = new ComponentClass(container, {
            router: this,
            app: this.app,
            ...context
        });

        if (this.currentComponent.init) {
            await this.currentComponent.init();
        }

        if (this.currentComponent.render) {
            await this.currentComponent.render();
        }
    }

    /**
     * Precargar módulos
     */
    async preloadModule(modulePath) {
        if (this.preloadedModules.has(modulePath)) return;

        try {
            setTimeout(async () => {
                await this.loadModule(modulePath);
                this.preloadedModules.add(modulePath);
            }, this.config.preloadDelay);
        } catch (error) {
            // console.warn(`Error precargando módulo ${modulePath}:`, error);
        }
    }

    /**
     * Actualizar breadcrumbs
     */
    async updateBreadcrumbs(route) {
        let breadcrumbs = [];

        if (route.breadcrumbs) {
            if (typeof route.breadcrumbs === 'function') {
                breadcrumbs = await route.breadcrumbs(this.state.params);
            } else {
                breadcrumbs = route.breadcrumbs;
            }
        }

        this.state.breadcrumbs = breadcrumbs;

        // Actualizar UI de breadcrumbs
        const breadcrumbContainer = document.querySelector('.breadcrumb-container');
        if (breadcrumbContainer) {
            this.renderBreadcrumbs(breadcrumbContainer, breadcrumbs);
        }
    }

    /**
     * Renderizar breadcrumbs
     */
    renderBreadcrumbs(container, breadcrumbs) {
        const breadcrumbHtml = breadcrumbs.map((item, index) => {
            const isLast = index === breadcrumbs.length - 1;
            const classes = `breadcrumb-item ${isLast ? 'active' : ''}`;
            
            if (isLast) {
                return `<li class="${classes}">${item.name}</li>`;
            } else {
                return `<li class="${classes}"><a href="${item.path}">${item.name}</a></li>`;
            }
        }).join('');

        container.innerHTML = `<ol class="breadcrumb">${breadcrumbHtml}</ol>`;
    }

    /**
     * Mostrar loading de página
     */
    showPageLoading() {
        const loadingElement = document.querySelector('.page-loading');
        if (loadingElement) {
            loadingElement.style.display = 'flex';
        } else {
            // Crear loading element si no existe
            const loading = document.createElement('div');
            loading.className = 'page-loading d-flex justify-content-center align-items-center position-fixed';
            loading.style.cssText = 'top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999; background: rgba(255,255,255,0.8);';
            loading.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
            `;
            document.body.appendChild(loading);
        }
    }

    /**
     * Ocultar loading de página
     */
    hidePageLoading() {
        const loadingElement = document.querySelector('.page-loading');
        if (loadingElement) {
            setTimeout(() => {
                loadingElement.style.display = 'none';
            }, this.config.transitionDuration);
        }
    }

    /**
     * Verificar si debe interceptar enlace
     */
    shouldInterceptLink(link) {
        const href = link.getAttribute('href');
        
        // No interceptar enlaces externos
        if (href.startsWith('http') || href.startsWith('//')) {
            return false;
        }
        
        // No interceptar enlaces con target="_blank"
        if (link.getAttribute('target') === '_blank') {
            return false;
        }
        
        // No interceptar enlaces con data-external
        if (link.hasAttribute('data-external')) {
            return false;
        }
        
        // No interceptar enlaces de descarga
        if (link.hasAttribute('download')) {
            return false;
        }
        
        return true;
    }

    /**
     * Manejar envío de formulario con navegación
     */
    async handleFormSubmit(form) {
        const action = form.action || form.dataset.navigate;
        const method = form.method || 'GET';
        
        if (method.toLowerCase() === 'get') {
            const formData = new FormData(form);
            const params = new URLSearchParams(formData);
            const url = `${action}?${params.toString()}`;
            this.navigate(url);
        } else {
            // Para POST, enviar datos y navegar según respuesta
            try {
                const formData = new FormData(form);
                const response = await this.app.main.http.post(action, formData);
                
                if (response.redirect) {
                    this.navigate(response.redirect);
                }
            } catch (error) {
                // // console.error('Error en envío de formulario:', error);
            }
        }
    }

    /**
     * Verificar si está autenticado
     */
    isAuthenticated() {
        return this.app.main.currentUser !== null;
    }

    /**
     * Verificar si tiene el rol requerido
     */
    hasRequiredRole(requiredRoles) {
        if (!requiredRoles || !Array.isArray(requiredRoles)) {
            return true;
        }
        
        const userRole = this.app.main.userRole;
        return requiredRoles.includes(userRole);
    }

    /**
     * Verificar si hay cambios sin guardar
     */
    hasUnsavedChanges() {
        const forms = document.querySelectorAll('form[data-dirty="true"]');
        return forms.length > 0;
    }

    /**
     * Confirmar navegación
     */
    async confirmNavigation() {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Cambios sin guardar</h5>
                        </div>
                        <div class="modal-body">
                            <p>Tienes cambios sin guardar. ¿Estás seguro de que quieres salir?</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-action="cancel">Cancelar</button>
                            <button type="button" class="btn btn-danger" data-action="confirm">Salir sin guardar</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            modal.addEventListener('click', (e) => {
                if (e.target.dataset.action === 'confirm') {
                    resolve(true);
                } else if (e.target.dataset.action === 'cancel') {
                    resolve(false);
                }
                
                document.body.removeChild(modal);
            });
            
            // Mostrar modal
            const modalInstance = new bootstrap.Modal(modal);
            modalInstance.show();
        });
    }

    /**
     * Cargar datos de ruta
     */
    async loadRouteData(route) {
        if (route.meta.loadData) {
            const dataLoaders = Array.isArray(route.meta.loadData) ? 
                route.meta.loadData : [route.meta.loadData];
            
            for (const loader of dataLoaders) {
                if (typeof loader === 'function') {
                    await loader(this.state.params, this.state.query);
                } else if (typeof loader === 'string') {
                    await this.app.main.http.get(loader);
                }
            }
        }
    }

    /**
     * Obtener nombre de proyecto para breadcrumbs
     */
    async getProjectName(projectId) {
        try {
            const project = await this.app.main.http.get(`/projects/${projectId}`);
            return project.name || `Proyecto #${projectId}`;
        } catch {
            return `Proyecto #${projectId}`;
        }
    }

    /**
     * Obtener título de reunión para breadcrumbs
     */
    async getMeetingTitle(meetingId) {
        try {
            const meeting = await this.app.main.http.get(`/meetings/${meetingId}`);
            return meeting.title || `Reunión #${meetingId}`;
        } catch {
            return `Reunión #${meetingId}`;
        }
    }

    /**
     * Obtener ruta actual
     */
    getCurrentRoute() {
        return this.state.currentRoute;
    }

    /**
     * Obtener parámetros actuales
     */
    getParams() {
        return { ...this.state.params };
    }

    /**
     * Obtener query actual
     */
    getQuery() {
        return { ...this.state.query };
    }

    /**
     * Ir hacia atrás
     */
    back() {
        window.history.back();
    }

    /**
     * Ir hacia adelante
     */
    forward() {
        window.history.forward();
    }

    /**
     * Generar URL
     */
    url(name, params = {}, query = {}) {
        const route = Array.from(this.routes.values()).find(r => r.name === name);
        if (!route) {
            throw new Error(`Ruta ${name} no encontrada`);
        }
        
        let path = route.path;
        
        // Reemplazar parámetros
        Object.entries(params).forEach(([key, value]) => {
            path = path.replace(`:${key}`, value);
        });
        
        // Agregar query string
        const queryString = new URLSearchParams(query).toString();
        if (queryString) {
            path += `?${queryString}`;
        }
        
        return path;
    }

    /**
     * Destruir router
     */
    destroy() {
        // Limpiar event listeners
        this.listeners.forEach((listener, element) => {
            element.removeEventListener(listener.event, listener.handler);
        });
        
        // Destruir componente actual
        if (this.currentComponent && this.currentComponent.destroy) {
            this.currentComponent.destroy();
        }
        
        // Limpiar cache
        this.moduleCache.clear();
        this.preloadedModules.clear();
        
        // // console.log('🧹 Router destruido');
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EcosistemaRouter;
} else {
    window.EcosistemaRouter = EcosistemaRouter;
}