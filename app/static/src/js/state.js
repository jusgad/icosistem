/**
 * Ecosistema Emprendimiento - State Management System
 * ==================================================
 * 
 * Sistema completo de gestión de estado para el ecosistema de emprendimiento
 * Incluye estado reactivo, persistencia, sincronización y módulos específicos
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js
 */

'use strict';

/**
 * Gestor principal de estado del ecosistema
 */
class EcosistemaStateManager {
    constructor(app) {
        this.app = app;
        this.main = app?.main || window.App;
        
        // Configuración del state manager
        this.config = {
            enablePersistence: true,
            enableSync: true,
            enableTimeTravel: true,
            enableDevTools: false,
            persistenceKey: 'ecosistema_state',
            syncInterval: 30000, // 30 segundos
            maxHistoryEntries: 50,
            enableEncryption: false,
            enableCompression: true,
            autoHydrate: true
        };

        // Estado central
        this.state = {};
        
        // Módulos de estado
        this.modules = new Map();
        
        // Observadores reactivos
        this.observers = new Map();
        this.computedCache = new Map();
        
        // Middleware para interceptar mutations
        this.middlewares = [];
        
        // Historial para time travel debugging
        this.history = [];
        this.historyIndex = -1;
        
        // Subscripciones activas
        this.subscriptions = new Map();
        
        // Estado de sincronización
        this.syncState = {
            lastSync: null,
            syncInProgress: false,
            pendingUpdates: [],
            conflicts: []
        };
        
        // Estado de la aplicación
        this.appState = {
            isHydrated: false,
            isOnline: navigator.onLine,
            loadingStates: new Map(),
            errors: new Map(),
            notifications: []
        };

        // Inicializar
        this.init();
    }

    /**
     * Inicializar state manager
     */
    async init() {
        console.log('🗄️ Inicializando State Manager');
        
        try {
            // Registrar módulos de estado
            this.registerModules();
            
            // Configurar middleware por defecto
            this.setupDefaultMiddlewares();
            
            // Hidratar estado desde persistencia
            if (this.config.autoHydrate) {
                await this.hydrate();
            }
            
            // Configurar sincronización
            if (this.config.enableSync) {
                this.setupSync();
            }
            
            // Configurar eventos del navegador
            this.setupBrowserEvents();
            
            // Configurar WebSocket para tiempo real
            this.setupRealTimeSync();
            
            // Marcar como hidratado
            this.appState.isHydrated = true;
            this.emit('state:hydrated');
            
            console.log('✅ State Manager inicializado');
            
        } catch (error) {
            console.error('❌ Error inicializando State Manager:', error);
            this.handleError('INIT_ERROR', error);
        }
    }

    /**
     * Registrar módulos de estado específicos del dominio
     */
    registerModules() {
        // Módulo de usuario
        this.registerModule('user', new UserStateModule(this));
        
        // Módulo de proyectos
        this.registerModule('projects', new ProjectsStateModule(this));
        
        // Módulo de reuniones
        this.registerModule('meetings', new MeetingsStateModule(this));
        
        // Módulo de mentoría
        this.registerModule('mentorship', new MentorshipStateModule(this));
        
        // Módulo de documentos
        this.registerModule('documents', new DocumentsStateModule(this));
        
        // Módulo de notificaciones
        this.registerModule('notifications', new NotificationsStateModule(this));
        
        // Módulo de networking
        this.registerModule('network', new NetworkStateModule(this));
        
        // Módulo de chat
        this.registerModule('chat', new ChatStateModule(this));
        
        // Módulo de configuración
        this.registerModule('settings', new SettingsStateModule(this));
        
        // Módulo de analíticas
        this.registerModule('analytics', new AnalyticsStateModule(this));
        
        // Módulo de UI
        this.registerModule('ui', new UIStateModule(this));
        
        // Módulos específicos por tipo de usuario
        this.registerUserTypeModules();
    }

    /**
     * Registrar módulos específicos por tipo de usuario
     */
    registerUserTypeModules() {
        const userType = this.main?.userType;
        
        switch (userType) {
            case 'entrepreneur':
                this.registerModule('entrepreneurship', new EntrepreneurshipStateModule(this));
                break;
            case 'mentor':
                this.registerModule('mentoring', new MentoringStateModule(this));
                break;
            case 'admin':
                this.registerModule('administration', new AdministrationStateModule(this));
                break;
            case 'client':
                this.registerModule('clientPortal', new ClientPortalStateModule(this));
                break;
        }
    }

    /**
     * Registrar módulo de estado
     */
    registerModule(name, module) {
        if (this.modules.has(name)) {
            console.warn(`Módulo ${name} ya está registrado`);
            return;
        }

        // Inicializar estado del módulo
        this.state[name] = module.getInitialState();
        
        // Registrar módulo
        this.modules.set(name, module);
        
        // Inicializar módulo
        if (module.init) {
            module.init();
        }
        
        console.log(`📦 Módulo ${name} registrado`);
    }

    /**
     * Configurar middlewares por defecto
     */
    setupDefaultMiddlewares() {
        // Middleware de logging
        this.addMiddleware('logger', (mutation, state, prevState) => {
            if (this.main?.debug) {
                console.group(`🔄 Mutation: ${mutation.type}`);
                console.log('Payload:', mutation.payload);
                console.log('Estado anterior:', prevState);
                console.log('Estado nuevo:', state);
                console.groupEnd();
            }
        });

        // Middleware de validación
        this.addMiddleware('validator', (mutation, state, prevState) => {
            const module = this.modules.get(mutation.module);
            if (module && module.validateMutation) {
                const isValid = module.validateMutation(mutation, state, prevState);
                if (!isValid) {
                    throw new Error(`Mutation inválida: ${mutation.type}`);
                }
            }
        });

        // Middleware de persistencia
        this.addMiddleware('persistence', async (mutation, state, prevState) => {
            if (this.config.enablePersistence && mutation.persist !== false) {
                await this.persist();
            }
        });

        // Middleware de sincronización
        this.addMiddleware('sync', (mutation, state, prevState) => {
            if (this.config.enableSync && mutation.sync !== false) {
                this.queueSync(mutation);
            }
        });

        // Middleware de historial
        this.addMiddleware('history', (mutation, state, prevState) => {
            if (this.config.enableTimeTravel) {
                this.addToHistory(mutation, prevState, state);
            }
        });
    }

    /**
     * Agregar middleware
     */
    addMiddleware(name, handler) {
        this.middlewares.push({ name, handler });
    }

    /**
     * Ejecutar mutation con middlewares
     */
    async commit(mutationType, payload = {}, options = {}) {
        const [moduleName, actionName] = mutationType.split('/');
        const module = this.modules.get(moduleName);
        
        if (!module) {
            throw new Error(`Módulo ${moduleName} no encontrado`);
        }

        const mutation = {
            type: mutationType,
            module: moduleName,
            action: actionName,
            payload,
            timestamp: Date.now(),
            user: this.main?.currentUser?.id,
            ...options
        };

        const prevState = this.cloneState();

        try {
            // Ejecutar middleware pre-mutation
            for (const middleware of this.middlewares) {
                if (middleware.pre) {
                    await middleware.pre(mutation, this.state, prevState);
                }
            }

            // Ejecutar mutation
            module.mutate(actionName, this.state[moduleName], payload);

            // Ejecutar middleware post-mutation
            for (const middleware of this.middlewares) {
                if (middleware.handler) {
                    await middleware.handler(mutation, this.state, prevState);
                }
            }

            // Notificar observadores
            this.notifyObservers(mutationType, this.state[moduleName], prevState[moduleName]);

            // Invalidar cache computado
            this.invalidateComputedCache(moduleName);

            // Emitir evento
            this.emit('state:mutation', { mutation, state: this.state, prevState });

        } catch (error) {
            console.error('Error ejecutando mutation:', error);
            this.handleError('MUTATION_ERROR', error, mutation);
            
            // Revertir estado en caso de error
            this.state = prevState;
            throw error;
        }
    }

    /**
     * Ejecutar action asíncrona
     */
    async dispatch(actionType, payload = {}, options = {}) {
        const [moduleName, actionName] = actionType.split('/');
        const module = this.modules.get(moduleName);
        
        if (!module) {
            throw new Error(`Módulo ${moduleName} no encontrado`);
        }

        const action = {
            type: actionType,
            module: moduleName,
            action: actionName,
            payload,
            timestamp: Date.now(),
            user: this.main?.currentUser?.id,
            ...options
        };

        try {
            this.setLoading(actionType, true);
            
            // Ejecutar action
            const result = await module.action(actionName, {
                state: this.state,
                commit: this.commit.bind(this),
                dispatch: this.dispatch.bind(this),
                getters: this.getGetters(moduleName)
            }, payload);

            this.setLoading(actionType, false);
            
            // Emitir evento
            this.emit('state:action', { action, result, state: this.state });
            
            return result;

        } catch (error) {
            this.setLoading(actionType, false);
            this.handleError('ACTION_ERROR', error, action);
            throw error;
        }
    }

    /**
     * Obtener valor del estado
     */
    get(path) {
        return this.getNestedValue(this.state, path);
    }

    /**
     * Obtener getters computados de un módulo
     */
    getGetters(moduleName) {
        const module = this.modules.get(moduleName);
        if (!module || !module.getters) return {};

        const cacheKey = `getters_${moduleName}`;
        
        if (this.computedCache.has(cacheKey)) {
            return this.computedCache.get(cacheKey);
        }

        const getters = {};
        const moduleState = this.state[moduleName];

        Object.entries(module.getters).forEach(([key, getter]) => {
            Object.defineProperty(getters, key, {
                get: () => getter(moduleState, this.state, this.getGetters.bind(this))
            });
        });

        this.computedCache.set(cacheKey, getters);
        return getters;
    }

    /**
     * Subscribirse a cambios en el estado
     */
    subscribe(path, callback, options = {}) {
        const subscriptionId = this.generateId();
        const subscription = {
            id: subscriptionId,
            path,
            callback,
            immediate: options.immediate || false,
            deep: options.deep || false,
            once: options.once || false
        };

        if (!this.observers.has(path)) {
            this.observers.set(path, new Set());
        }

        this.observers.get(path).add(subscription);
        
        // Ejecutar inmediatamente si se especifica
        if (subscription.immediate) {
            callback(this.get(path), undefined);
        }

        // Retornar función para unsubscribe
        return () => {
            const pathObservers = this.observers.get(path);
            if (pathObservers) {
                pathObservers.delete(subscription);
                if (pathObservers.size === 0) {
                    this.observers.delete(path);
                }
            }
        };
    }

    /**
     * Notificar observadores de cambios
     */
    notifyObservers(mutationType, newValue, oldValue) {
        const [moduleName] = mutationType.split('/');
        
        // Notificar observadores específicos del módulo
        this.notifyPathObservers(moduleName, newValue, oldValue);
        
        // Notificar observadores profundos
        this.notifyDeepObservers(moduleName, newValue, oldValue);
    }

    /**
     * Notificar observadores de una ruta específica
     */
    notifyPathObservers(path, newValue, oldValue) {
        const pathObservers = this.observers.get(path);
        if (!pathObservers) return;

        const toRemove = [];

        pathObservers.forEach(subscription => {
            try {
                subscription.callback(newValue, oldValue);
                
                // Remover si es de una sola vez
                if (subscription.once) {
                    toRemove.push(subscription);
                }
            } catch (error) {
                console.error('Error en callback de observador:', error);
            }
        });

        // Remover subscripciones de una sola vez
        toRemove.forEach(subscription => {
            pathObservers.delete(subscription);
        });
    }

    /**
     * Notificar observadores profundos
     */
    notifyDeepObservers(basePath, newValue, oldValue) {
        this.observers.forEach((observers, path) => {
            if (path.startsWith(basePath) || basePath.startsWith(path)) {
                observers.forEach(subscription => {
                    if (subscription.deep) {
                        const currentValue = this.get(subscription.path);
                        subscription.callback(currentValue, oldValue);
                    }
                });
            }
        });
    }

    /**
     * Hidratar estado desde persistencia
     */
    async hydrate() {
        try {
            const persistedState = await this.loadPersistedState();
            
            if (persistedState) {
                // Merge con estado inicial
                this.state = this.mergeStates(this.state, persistedState);
                
                // Notificar módulos de hidratación
                this.modules.forEach((module, name) => {
                    if (module.onHydrate) {
                        module.onHydrate(this.state[name]);
                    }
                });
                
                console.log('💧 Estado hidratado desde persistencia');
            }
            
        } catch (error) {
            console.warn('⚠️ Error hidratando estado:', error);
        }
    }

    /**
     * Persistir estado
     */
    async persist() {
        if (!this.config.enablePersistence) return;

        try {
            const stateToSave = this.getStateToPersist();
            
            if (this.config.enableCompression) {
                // Comprimir estado antes de guardar
                const compressed = await this.compressState(stateToSave);
                await this.saveState(compressed);
            } else {
                await this.saveState(stateToSave);
            }
            
        } catch (error) {
            console.error('Error persistiendo estado:', error);
        }
    }

    /**
     * Obtener estado a persistir (filtrar datos sensibles)
     */
    getStateToPersist() {
        const stateToPersist = {};
        
        this.modules.forEach((module, name) => {
            if (module.shouldPersist && module.shouldPersist()) {
                const moduleState = this.state[name];
                
                if (module.getPersistedState) {
                    stateToPersist[name] = module.getPersistedState(moduleState);
                } else {
                    stateToPersist[name] = moduleState;
                }
            }
        });
        
        return stateToPersist;
    }

    /**
     * Cargar estado persistido
     */
    async loadPersistedState() {
        try {
            const stored = this.main.storage.get(this.config.persistenceKey);
            
            if (!stored) return null;
            
            if (this.config.enableCompression && stored.compressed) {
                return await this.decompressState(stored.data);
            }
            
            return stored;
            
        } catch (error) {
            console.error('Error cargando estado persistido:', error);
            return null;
        }
    }

    /**
     * Guardar estado
     */
    async saveState(state) {
        const stateData = {
            data: state,
            timestamp: Date.now(),
            version: this.app?.version || '1.0.0',
            compressed: this.config.enableCompression
        };
        
        this.main.storage.set(this.config.persistenceKey, stateData);
    }

    /**
     * Configurar sincronización con servidor
     */
    setupSync() {
        // Sincronización periódica
        setInterval(() => {
            if (!this.syncState.syncInProgress && this.appState.isOnline) {
                this.syncWithServer();
            }
        }, this.config.syncInterval);

        // Sincronización al recuperar conexión
        this.main.events.addEventListener('online', () => {
            this.appState.isOnline = true;
            this.syncWithServer();
        });

        this.main.events.addEventListener('offline', () => {
            this.appState.isOnline = false;
        });
    }

    /**
     * Sincronizar con servidor
     */
    async syncWithServer() {
        if (this.syncState.syncInProgress) return;

        try {
            this.syncState.syncInProgress = true;
            this.emit('state:syncStart');

            // Obtener actualizaciones del servidor
            const serverUpdates = await this.fetchServerUpdates();
            
            // Aplicar actualizaciones
            if (serverUpdates && serverUpdates.length > 0) {
                await this.applyServerUpdates(serverUpdates);
            }

            // Enviar actualizaciones pendientes
            if (this.syncState.pendingUpdates.length > 0) {
                await this.sendPendingUpdates();
            }

            this.syncState.lastSync = Date.now();
            this.emit('state:syncSuccess');

        } catch (error) {
            console.error('Error sincronizando con servidor:', error);
            this.emit('state:syncError', error);
        } finally {
            this.syncState.syncInProgress = false;
        }
    }

    /**
     * Configurar sincronización en tiempo real via WebSocket
     */
    setupRealTimeSync() {
        if (!this.main.websocket) return;

        // Escuchar actualizaciones en tiempo real
        this.main.events.addEventListener('websocket:state_update', (event) => {
            this.handleRealTimeUpdate(event.detail);
        });

        // Enviar actualizaciones en tiempo real
        this.subscribe('*', (newValue, oldValue, path) => {
            if (this.config.enableSync) {
                this.sendRealTimeUpdate(path, newValue, oldValue);
            }
        });
    }

    /**
     * Manejar actualización en tiempo real
     */
    async handleRealTimeUpdate(update) {
        try {
            const { type, module, payload, timestamp, user } = update;
            
            // Evitar loops de actualizaciones propias
            if (user === this.main.currentUser?.id) return;
            
            // Aplicar actualización sin sincronización
            await this.commit(`${module}/${type}`, payload, { 
                sync: false, 
                realTime: true 
            });
            
            this.emit('state:realTimeUpdate', update);
            
        } catch (error) {
            console.error('Error aplicando actualización en tiempo real:', error);
        }
    }

    /**
     * Configurar eventos del navegador
     */
    setupBrowserEvents() {
        // Sincronizar entre pestañas
        window.addEventListener('storage', (event) => {
            if (event.key === this.config.persistenceKey) {
                this.handleCrossTabSync(event);
            }
        });

        // Persistir antes de cerrar
        window.addEventListener('beforeunload', () => {
            this.persist();
        });

        // Detectar visibilidad de página
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                this.syncWithServer();
            }
        });
    }

    /**
     * Manejar sincronización entre pestañas
     */
    handleCrossTabSync(event) {
        try {
            const newState = JSON.parse(event.newValue);
            const oldState = JSON.parse(event.oldValue);
            
            if (newState && newState.timestamp > (oldState?.timestamp || 0)) {
                // Aplicar cambios de otra pestaña
                this.mergeExternalState(newState.data);
                this.emit('state:crossTabSync', { newState, oldState });
            }
            
        } catch (error) {
            console.error('Error en sincronización entre pestañas:', error);
        }
    }

    /**
     * Establecer estado de carga
     */
    setLoading(key, isLoading) {
        if (isLoading) {
            this.appState.loadingStates.set(key, Date.now());
        } else {
            this.appState.loadingStates.delete(key);
        }
        
        this.emit('state:loading', { key, isLoading });
    }

    /**
     * Verificar si algo está cargando
     */
    isLoading(key = null) {
        if (key) {
            return this.appState.loadingStates.has(key);
        }
        return this.appState.loadingStates.size > 0;
    }

    /**
     * Manejar errores
     */
    handleError(type, error, context = {}) {
        const errorData = {
            type,
            message: error.message,
            stack: error.stack,
            context,
            timestamp: Date.now(),
            user: this.main.currentUser?.id
        };

        this.appState.errors.set(type, errorData);
        this.emit('state:error', errorData);

        // Reportar error al servidor si es crítico
        if (['INIT_ERROR', 'SYNC_ERROR'].includes(type)) {
            this.reportError(errorData);
        }
    }

    /**
     * Reportar error al servidor
     */
    async reportError(errorData) {
        try {
            await this.main.http.post('/errors/report', errorData);
        } catch (error) {
            console.error('Error reportando error:', error);
        }
    }

    /**
     * Time travel - ir a un punto específico en el historial
     */
    timeTravel(index) {
        if (!this.config.enableTimeTravel) return false;
        
        if (index < 0 || index >= this.history.length) return false;
        
        const targetEntry = this.history[index];
        this.state = this.cloneState(targetEntry.state);
        this.historyIndex = index;
        
        this.emit('state:timeTravel', { index, state: this.state });
        return true;
    }

    /**
     * Agregar entrada al historial
     */
    addToHistory(mutation, prevState, newState) {
        const entry = {
            mutation,
            state: this.cloneState(newState),
            timestamp: Date.now()
        };

        // Remover entradas futuras si estamos en el medio del historial
        if (this.historyIndex < this.history.length - 1) {
            this.history = this.history.slice(0, this.historyIndex + 1);
        }

        this.history.push(entry);
        this.historyIndex = this.history.length - 1;

        // Mantener límite de entradas
        if (this.history.length > this.config.maxHistoryEntries) {
            this.history = this.history.slice(-this.config.maxHistoryEntries);
            this.historyIndex = this.history.length - 1;
        }
    }

    /**
     * Resetear estado a inicial
     */
    reset() {
        this.modules.forEach((module, name) => {
            this.state[name] = module.getInitialState();
        });
        
        this.clearCache();
        this.emit('state:reset');
    }

    /**
     * Limpiar cache
     */
    clearCache() {
        this.computedCache.clear();
        this.appState.errors.clear();
        this.appState.loadingStates.clear();
    }

    /**
     * Invalidar cache computado
     */
    invalidateComputedCache(moduleName = null) {
        if (moduleName) {
            this.computedCache.delete(`getters_${moduleName}`);
        } else {
            this.computedCache.clear();
        }
    }

    /**
     * Utilidades
     */
    cloneState(state = this.state) {
        return JSON.parse(JSON.stringify(state));
    }

    mergeStates(target, source) {
        const result = { ...target };
        
        Object.keys(source).forEach(key => {
            if (typeof source[key] === 'object' && source[key] !== null) {
                result[key] = { ...target[key], ...source[key] };
            } else {
                result[key] = source[key];
            }
        });
        
        return result;
    }

    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }

    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((current, key) => {
            if (!(key in current)) current[key] = {};
            return current[key];
        }, obj);
        
        target[lastKey] = value;
    }

    generateId() {
        return Math.random().toString(36).substr(2, 9);
    }

    emit(eventName, data) {
        this.main.events.dispatchEvent(new CustomEvent(eventName, {
            detail: data
        }));
    }

    /**
     * Comprimir estado
     */
    async compressState(state) {
        // Implementación simplificada de compresión
        const jsonString = JSON.stringify(state);
        return btoa(jsonString);
    }

    /**
     * Descomprimir estado
     */
    async decompressState(compressedData) {
        try {
            const jsonString = atob(compressedData);
            return JSON.parse(jsonString);
        } catch (error) {
            throw new Error('Error descomprimiendo estado');
        }
    }

    /**
     * Destruir state manager
     */
    destroy() {
        // Persistir estado final
        this.persist();
        
        // Limpiar observadores
        this.observers.clear();
        
        // Limpiar cache
        this.clearCache();
        
        // Limpiar módulos
        this.modules.forEach(module => {
            if (module.destroy) {
                module.destroy();
            }
        });
        
        console.log('🧹 State Manager destruido');
    }
}

// ============================================================================
// MÓDULO BASE PARA ESTADO
// ============================================================================

/**
 * Clase base para módulos de estado
 */
class BaseStateModule {
    constructor(stateManager) {
        this.state = stateManager;
        this.main = stateManager.main;
    }

    /**
     * Estado inicial del módulo (debe ser implementado)
     */
    getInitialState() {
        return {};
    }

    /**
     * Mutations del módulo (debe ser implementado)
     */
    mutate(action, state, payload) {
        // Implementar en módulos específicos
    }

    /**
     * Actions asíncronas del módulo
     */
    async action(actionName, context, payload) {
        // Implementar en módulos específicos
    }

    /**
     * Getters computados del módulo
     */
    get getters() {
        return {};
    }

    /**
     * Validar mutation
     */
    validateMutation(mutation, state, prevState) {
        return true;
    }

    /**
     * Debe persistir este módulo
     */
    shouldPersist() {
        return true;
    }

    /**
     * Obtener estado a persistir
     */
    getPersistedState(state) {
        return state;
    }

    /**
     * Callback al hidratar estado
     */
    onHydrate(state) {
        // Implementar si es necesario
    }

    /**
     * Inicializar módulo
     */
    init() {
        // Implementar si es necesario
    }

    /**
     * Destruir módulo
     */
    destroy() {
        // Implementar si es necesario
    }
}

// ============================================================================
// MÓDULOS ESPECÍFICOS DEL DOMINIO
// ============================================================================

/**
 * Módulo de estado del usuario
 */
class UserStateModule extends BaseStateModule {
    getInitialState() {
        return {
            currentUser: null,
            profile: {},
            preferences: {
                theme: 'light',
                language: 'es',
                notifications: true,
                autoSave: true
            },
            permissions: [],
            status: 'offline', // online, away, busy, offline
            lastActivity: null,
            loginHistory: [],
            sessions: []
        };
    }

    mutate(action, state, payload) {
        switch (action) {
            case 'SET_CURRENT_USER':
                state.currentUser = payload.user;
                state.profile = payload.user?.profile || {};
                state.permissions = payload.user?.permissions || [];
                state.lastActivity = Date.now();
                break;

            case 'UPDATE_PROFILE':
                state.profile = { ...state.profile, ...payload };
                break;

            case 'SET_PREFERENCES':
                state.preferences = { ...state.preferences, ...payload };
                break;

            case 'SET_STATUS':
                state.status = payload.status;
                state.lastActivity = Date.now();
                break;

            case 'ADD_LOGIN_HISTORY':
                state.loginHistory.unshift(payload);
                state.loginHistory = state.loginHistory.slice(0, 10); // Mantener solo 10
                break;

            case 'LOGOUT':
                state.currentUser = null;
                state.profile = {};
                state.permissions = [];
                state.status = 'offline';
                break;
        }
    }

    async action(actionName, { commit, dispatch }, payload) {
        switch (actionName) {
            case 'login':
                try {
                    const response = await this.main.http.post('/auth/login', payload);
                    commit('user/SET_CURRENT_USER', response);
                    commit('user/ADD_LOGIN_HISTORY', {
                        timestamp: Date.now(),
                        ip: payload.ip,
                        userAgent: navigator.userAgent
                    });
                    return response;
                } catch (error) {
                    throw error;
                }

            case 'updateProfile':
                try {
                    const response = await this.main.http.put('/user/profile', payload);
                    commit('user/UPDATE_PROFILE', response);
                    return response;
                } catch (error) {
                    throw error;
                }

            case 'updatePreferences':
                commit('user/SET_PREFERENCES', payload);
                // Persistir en servidor
                this.main.http.put('/user/preferences', payload).catch(console.error);
                break;

            case 'logout':
                await this.main.http.post('/auth/logout');
                commit('user/LOGOUT');
                break;
        }
    }

    get getters() {
        return {
            isAuthenticated: (state) => !!state.currentUser,
            userType: (state) => state.currentUser?.type || 'guest',
            userRole: (state) => state.currentUser?.role || 'user',
            fullName: (state) => state.profile?.fullName || state.currentUser?.email,
            avatar: (state) => state.profile?.avatar || '/static/img/default-avatar.png',
            hasPermission: (state) => (permission) => state.permissions.includes(permission),
            isOnline: (state) => state.status === 'online'
        };
    }
}

/**
 * Módulo de estado de proyectos
 */
class ProjectsStateModule extends BaseStateModule {
    getInitialState() {
        return {
            projects: [],
            currentProject: null,
            filters: {
                status: 'all',
                category: 'all',
                search: ''
            },
            view: 'grid', // grid, list, kanban
            pagination: {
                page: 1,
                limit: 20,
                total: 0
            },
            loading: false,
            lastUpdate: null
        };
    }

    mutate(action, state, payload) {
        switch (action) {
            case 'SET_PROJECTS':
                state.projects = payload.projects;
                state.pagination = { ...state.pagination, ...payload.pagination };
                state.lastUpdate = Date.now();
                break;

            case 'ADD_PROJECT':
                state.projects.unshift(payload);
                state.pagination.total += 1;
                break;

            case 'UPDATE_PROJECT':
                const index = state.projects.findIndex(p => p.id === payload.id);
                if (index !== -1) {
                    state.projects[index] = { ...state.projects[index], ...payload };
                }
                if (state.currentProject?.id === payload.id) {
                    state.currentProject = { ...state.currentProject, ...payload };
                }
                break;

            case 'DELETE_PROJECT':
                state.projects = state.projects.filter(p => p.id !== payload.id);
                state.pagination.total -= 1;
                if (state.currentProject?.id === payload.id) {
                    state.currentProject = null;
                }
                break;

            case 'SET_CURRENT_PROJECT':
                state.currentProject = payload;
                break;

            case 'SET_FILTERS':
                state.filters = { ...state.filters, ...payload };
                break;

            case 'SET_VIEW':
                state.view = payload;
                break;

            case 'SET_LOADING':
                state.loading = payload;
                break;
        }
    }

    async action(actionName, { commit, state }, payload) {
        switch (actionName) {
            case 'fetchProjects':
                try {
                    commit('projects/SET_LOADING', true);
                    const params = {
                        page: state.pagination.page,
                        limit: state.pagination.limit,
                        ...state.filters
                    };
                    const response = await this.main.http.get('/projects', { params });
                    commit('projects/SET_PROJECTS', response);
                    return response;
                } finally {
                    commit('projects/SET_LOADING', false);
                }

            case 'createProject':
                try {
                    const response = await this.main.http.post('/projects', payload);
                    commit('projects/ADD_PROJECT', response);
                    return response;
                } catch (error) {
                    throw error;
                }

            case 'updateProject':
                try {
                    const response = await this.main.http.put(`/projects/${payload.id}`, payload);
                    commit('projects/UPDATE_PROJECT', response);
                    return response;
                } catch (error) {
                    throw error;
                }

            case 'deleteProject':
                try {
                    await this.main.http.delete(`/projects/${payload.id}`);
                    commit('projects/DELETE_PROJECT', payload);
                } catch (error) {
                    throw error;
                }

            case 'loadProject':
                try {
                    const response = await this.main.http.get(`/projects/${payload.id}`);
                    commit('projects/SET_CURRENT_PROJECT', response);
                    return response;
                } catch (error) {
                    throw error;
                }
        }
    }

    get getters() {
        return {
            filteredProjects: (state) => {
                let projects = state.projects;
                
                if (state.filters.status !== 'all') {
                    projects = projects.filter(p => p.status === state.filters.status);
                }
                
                if (state.filters.category !== 'all') {
                    projects = projects.filter(p => p.category === state.filters.category);
                }
                
                if (state.filters.search) {
                    const search = state.filters.search.toLowerCase();
                    projects = projects.filter(p => 
                        p.name.toLowerCase().includes(search) ||
                        p.description.toLowerCase().includes(search)
                    );
                }
                
                return projects;
            },
            
            projectsByStatus: (state) => {
                const grouped = {};
                state.projects.forEach(project => {
                    if (!grouped[project.status]) {
                        grouped[project.status] = [];
                    }
                    grouped[project.status].push(project);
                });
                return grouped;
            },
            
            activeProjectsCount: (state) => {
                return state.projects.filter(p => p.status === 'active').length;
            },
            
            completedProjectsCount: (state) => {
                return state.projects.filter(p => p.status === 'completed').length;
            }
        };
    }
}

/**
 * Módulo de estado de reuniones
 */
class MeetingsStateModule extends BaseStateModule {
    getInitialState() {
        return {
            meetings: [],
            upcomingMeetings: [],
            currentMeeting: null,
            calendar: {
                view: 'month', // month, week, day
                date: new Date().toISOString(),
                events: []
            },
            loading: false,
            lastUpdate: null
        };
    }

    mutate(action, state, payload) {
        switch (action) {
            case 'SET_MEETINGS':
                state.meetings = payload;
                state.lastUpdate = Date.now();
                break;

            case 'SET_UPCOMING_MEETINGS':
                state.upcomingMeetings = payload;
                break;

            case 'ADD_MEETING':
                state.meetings.unshift(payload);
                // Agregar a próximas reuniones si es en el futuro
                if (new Date(payload.startTime) > new Date()) {
                    state.upcomingMeetings.push(payload);
                    state.upcomingMeetings.sort((a, b) => 
                        new Date(a.startTime) - new Date(b.startTime)
                    );
                }
                break;

            case 'UPDATE_MEETING':
                const index = state.meetings.findIndex(m => m.id === payload.id);
                if (index !== -1) {
                    state.meetings[index] = { ...state.meetings[index], ...payload };
                }
                break;

            case 'SET_CURRENT_MEETING':
                state.currentMeeting = payload;
                break;

            case 'SET_CALENDAR_VIEW':
                state.calendar.view = payload.view;
                state.calendar.date = payload.date || state.calendar.date;
                break;

            case 'SET_CALENDAR_EVENTS':
                state.calendar.events = payload;
                break;

            case 'SET_LOADING':
                state.loading = payload;
                break;
        }
    }

    async action(actionName, { commit, state }, payload) {
        switch (actionName) {
            case 'fetchMeetings':
                try {
                    commit('meetings/SET_LOADING', true);
                    const [meetings, upcoming] = await Promise.all([
                        this.main.http.get('/meetings'),
                        this.main.http.get('/meetings/upcoming')
                    ]);
                    commit('meetings/SET_MEETINGS', meetings);
                    commit('meetings/SET_UPCOMING_MEETINGS', upcoming);
                    return { meetings, upcoming };
                } finally {
                    commit('meetings/SET_LOADING', false);
                }

            case 'scheduleMeeting':
                try {
                    const response = await this.main.http.post('/meetings', payload);
                    commit('meetings/ADD_MEETING', response);
                    return response;
                } catch (error) {
                    throw error;
                }

            case 'loadCalendarEvents':
                try {
                    const { start, end } = payload;
                    const events = await this.main.http.get('/calendar/events', {
                        params: { start, end }
                    });
                    commit('meetings/SET_CALENDAR_EVENTS', events);
                    return events;
                } catch (error) {
                    throw error;
                }
        }
    }

    get getters() {
        return {
            todaysMeetings: (state) => {
                const today = new Date().toDateString();
                return state.meetings.filter(meeting => 
                    new Date(meeting.startTime).toDateString() === today
                );
            },
            
            nextMeeting: (state) => {
                return state.upcomingMeetings[0] || null;
            },
            
            meetingsByDate: (state) => {
                const grouped = {};
                state.meetings.forEach(meeting => {
                    const date = new Date(meeting.startTime).toDateString();
                    if (!grouped[date]) {
                        grouped[date] = [];
                    }
                    grouped[date].push(meeting);
                });
                return grouped;
            }
        };
    }
}

/**
 * Módulo de estado de notificaciones
 */
class NotificationsStateModule extends BaseStateModule {
    getInitialState() {
        return {
            notifications: [],
            unreadCount: 0,
            settings: {
                push: true,
                email: true,
                desktop: true,
                sound: true
            },
            loading: false
        };
    }

    mutate(action, state, payload) {
        switch (action) {
            case 'SET_NOTIFICATIONS':
                state.notifications = payload;
                state.unreadCount = payload.filter(n => !n.read).length;
                break;

            case 'ADD_NOTIFICATION':
                state.notifications.unshift(payload);
                if (!payload.read) {
                    state.unreadCount += 1;
                }
                break;

            case 'MARK_AS_READ':
                const notification = state.notifications.find(n => n.id === payload.id);
                if (notification && !notification.read) {
                    notification.read = true;
                    state.unreadCount -= 1;
                }
                break;

            case 'MARK_ALL_READ':
                state.notifications.forEach(n => n.read = true);
                state.unreadCount = 0;
                break;

            case 'REMOVE_NOTIFICATION':
                const index = state.notifications.findIndex(n => n.id === payload.id);
                if (index !== -1) {
                    const removed = state.notifications.splice(index, 1)[0];
                    if (!removed.read) {
                        state.unreadCount -= 1;
                    }
                }
                break;

            case 'SET_SETTINGS':
                state.settings = { ...state.settings, ...payload };
                break;
        }
    }

    get getters() {
        return {
            unreadNotifications: (state) => {
                return state.notifications.filter(n => !n.read);
            },
            
            notificationsByType: (state) => {
                const grouped = {};
                state.notifications.forEach(notification => {
                    if (!grouped[notification.type]) {
                        grouped[notification.type] = [];
                    }
                    grouped[notification.type].push(notification);
                });
                return grouped;
            },
            
            hasUnread: (state) => state.unreadCount > 0
        };
    }
}

/**
 * Módulo de estado de UI
 */
class UIStateModule extends BaseStateModule {
    getInitialState() {
        return {
            sidebar: {
                collapsed: false,
                mobile: false
            },
            modals: {},
            theme: 'light',
            viewport: 'desktop',
            loading: new Set(),
            errors: new Map(),
            breadcrumbs: []
        };
    }

    mutate(action, state, payload) {
        switch (action) {
            case 'TOGGLE_SIDEBAR':
                state.sidebar.collapsed = !state.sidebar.collapsed;
                break;

            case 'SET_SIDEBAR':
                state.sidebar = { ...state.sidebar, ...payload };
                break;

            case 'SHOW_MODAL':
                state.modals[payload.id] = {
                    ...payload,
                    visible: true,
                    timestamp: Date.now()
                };
                break;

            case 'HIDE_MODAL':
                if (state.modals[payload.id]) {
                    state.modals[payload.id].visible = false;
                }
                break;

            case 'SET_THEME':
                state.theme = payload;
                break;

            case 'SET_VIEWPORT':
                state.viewport = payload;
                break;

            case 'SET_BREADCRUMBS':
                state.breadcrumbs = payload;
                break;

            case 'ADD_LOADING':
                state.loading.add(payload);
                break;

            case 'REMOVE_LOADING':
                state.loading.delete(payload);
                break;

            case 'SET_ERROR':
                state.errors.set(payload.key, payload.error);
                break;

            case 'CLEAR_ERROR':
                state.errors.delete(payload.key);
                break;
        }
    }

    get getters() {
        return {
            isLoading: (state) => (key) => state.loading.has(key),
            hasAnyLoading: (state) => state.loading.size > 0,
            getError: (state) => (key) => state.errors.get(key),
            visibleModals: (state) => {
                return Object.values(state.modals).filter(modal => modal.visible);
            },
            isMobile: (state) => ['mobile', 'mobile-large'].includes(state.viewport)
        };
    }

    shouldPersist() {
        return true;
    }

    getPersistedState(state) {
        return {
            sidebar: state.sidebar,
            theme: state.theme
        };
    }
}

// Módulos específicos por tipo de usuario se definirían aquí...
// (EntrepreneurshipStateModule, MentoringStateModule, etc.)

// ============================================================================
// INICIALIZACIÓN Y EXPORTACIÓN
// ============================================================================

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { 
        EcosistemaStateManager, 
        BaseStateModule,
        UserStateModule,
        ProjectsStateModule,
        MeetingsStateModule,
        NotificationsStateModule,
        UIStateModule
    };
}

// Hacer disponible globalmente
window.EcosistemaStateManager = EcosistemaStateManager;
window.BaseStateModule = BaseStateModule;