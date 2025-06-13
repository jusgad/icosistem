/**
 * CacheService.js - Servicio Avanzado de Caching
 * =================================================
 *
 * Proporciona una interfaz unificada para el caching de datos
 * con soporte para múltiples backends (localStorage, sessionStorage, in-memory)
 * y gestión de TTL (Time-To-Live).
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.config)
 */

'use strict';

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
    throw new Error('main.js debe cargarse antes que CacheService.js');
}

// Alias para facilitar acceso
const App = window.EcosistemaApp;

class CacheService {
    constructor(defaultStore = 'memory') {
        this.stores = {
            memory: new Map(),
            localStorage: window.localStorage,
            sessionStorage: window.sessionStorage,
        };
        this.defaultStoreName = this._isStorageAvailable(defaultStore) ? defaultStore : 'memory';
        this.prefix = App.config.CACHE_PREFIX || 'ecosistema_cache_';
        this.defaultTTL = App.config.CACHE_DEFAULT_TTL || (60 * 60 * 1000); // 1 hora en milisegundos

        this._initialize();
    }

    /**
     * Inicializa el servicio, limpiando entradas expiradas.
     * @private
     */
    _initialize() {
        this.cleanupExpired();
        // Programar limpieza periódica (ej. cada hora)
        setInterval(() => this.cleanupExpired(), 60 * 60 * 1000);
        console.info(`CacheService inicializado con store por defecto: ${this.defaultStoreName}`);
    }

    /**
     * Verifica si un tipo de almacenamiento está disponible.
     * @param {string} storeName - Nombre del store ('localStorage', 'sessionStorage').
     * @return {boolean} - True si está disponible.
     * @private
     */
    _isStorageAvailable(storeName) {
        try {
            const storage = this.stores[storeName];
            if (!storage) return false;
            const testKey = '__storage_test__';
            storage.setItem(testKey, testKey);
            storage.removeItem(testKey);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Obtiene el store a utilizar.
     * @param {string|null} storeName - Nombre del store o null para usar el por defecto.
     * @return {Storage|Map} - El objeto de almacenamiento.
     * @private
     */
    _getStore(storeName = null) {
        const name = storeName || this.defaultStoreName;
        if (!this.stores[name] || (name !== 'memory' && !this._isStorageAvailable(name))) {
            console.warn(`CacheService: Store '${name}' no disponible, usando 'memory' como fallback.`);
            return this.stores.memory;
        }
        return this.stores[name];
    }

    /**
     * Construye la clave de caché con prefijo.
     * @param {string} key - Clave original.
     * @return {string} - Clave con prefijo.
     * @private
     */
    _buildKey(key) {
        return `${this.prefix}${key}`;
    }

    /**
     * Establece un valor en el caché.
     * @param {string} key - Clave.
     * @param {*} value - Valor a cachear.
     * @param {number} [ttl=this.defaultTTL] - Tiempo de vida en milisegundos.
     * @param {string} [storeName=this.defaultStoreName] - Store a utilizar.
     * @return {boolean} - True si se estableció correctamente.
     */
    set(key, value, ttl = this.defaultTTL, storeName = this.defaultStoreName) {
        const store = this._getStore(storeName);
        const cacheKey = this._buildKey(key);
        const expiresAt = Date.now() + ttl;

        const item = {
            value: value,
            expiresAt: expiresAt,
            createdAt: Date.now()
        };

        try {
            if (store === this.stores.memory) {
                store.set(cacheKey, item);
            } else {
                store.setItem(cacheKey, JSON.stringify(item));
            }
            return true;
        } catch (e) {
            console.error(`CacheService: Error al establecer '${key}' en '${storeName}':`, e);
            // Podría implementar una estrategia de limpieza si el storage está lleno (LRU)
            if (e.name === 'QuotaExceededError') {
                this.evictOldest(storeName, 1); // Intentar liberar espacio
                try { // Reintentar
                    if (store === this.stores.memory) store.set(cacheKey, item);
                    else store.setItem(cacheKey, JSON.stringify(item));
                    return true;
                } catch (e2) {
                    console.error(`CacheService: Reintento fallido para '${key}':`, e2);
                }
            }
            return false;
        }
    }

    /**
     * Obtiene un valor del caché.
     * @param {string} key - Clave.
     * @param {string} [storeName=this.defaultStoreName] - Store a utilizar.
     * @return {*|null} - Valor cacheado o null si no existe o expiró.
     */
    get(key, storeName = this.defaultStoreName) {
        const store = this._getStore(storeName);
        const cacheKey = this._buildKey(key);
        let item;

        try {
            if (store === this.stores.memory) {
                item = store.get(cacheKey);
            } else {
                const rawItem = store.getItem(cacheKey);
                if (rawItem) {
                    item = JSON.parse(rawItem);
                }
            }
        } catch (e) {
            console.error(`CacheService: Error al obtener '${key}' de '${storeName}':`, e);
            this.remove(key, storeName); // Remover item corrupto
            return null;
        }

        if (!item) {
            return null;
        }

        if (Date.now() > item.expiresAt) {
            this.remove(key, storeName); // Remover item expirado
            return null;
        }

        return item.value;
    }

    /**
     * Verifica si una clave existe en el caché y no ha expirado.
     * @param {string} key - Clave.
     * @param {string} [storeName=this.defaultStoreName] - Store a utilizar.
     * @return {boolean} - True si la clave existe y es válida.
     */
    has(key, storeName = this.defaultStoreName) {
        return this.get(key, storeName) !== null;
    }

    /**
     * Elimina un valor del caché.
     * @param {string} key - Clave.
     * @param {string} [storeName=this.defaultStoreName] - Store a utilizar.
     * @return {boolean} - True si se eliminó correctamente.
     */
    remove(key, storeName = this.defaultStoreName) {
        const store = this._getStore(storeName);
        const cacheKey = this._buildKey(key);
        try {
            if (store === this.stores.memory) {
                store.delete(cacheKey);
            } else {
                store.removeItem(cacheKey);
            }
            return true;
        } catch (e) {
            console.error(`CacheService: Error al eliminar '${key}' de '${storeName}':`, e);
            return false;
        }
    }

    /**
     * Limpia todas las entradas del caché (o de un store específico).
     * @param {string} [storeName=null] - Store a limpiar. Si es null, limpia todos los stores.
     */
    clear(storeName = null) {
        if (storeName) {
            const store = this._getStore(storeName);
            if (store === this.stores.memory) {
                store.clear();
            } else {
                // Limpiar solo las claves con nuestro prefijo para localStorage/sessionStorage
                for (let i = store.length - 1; i >= 0; i--) {
                    const key = store.key(i);
                    if (key && key.startsWith(this.prefix)) {
                        store.removeItem(key);
                    }
                }
            }
            console.info(`CacheService: Store '${storeName}' limpiado.`);
        } else {
            Object.keys(this.stores).forEach(name => this.clear(name));
            console.info(`CacheService: Todos los stores limpiados.`);
        }
    }

    /**
     * Limpia entradas expiradas de todos los stores.
     */
    cleanupExpired() {
        console.debug('CacheService: Ejecutando limpieza de expirados...');
        let cleanedCount = 0;
        Object.keys(this.stores).forEach(storeName => {
            const store = this._getStore(storeName);
            if (store === this.stores.memory) {
                for (const [key, item] of store.entries()) {
                    if (Date.now() > item.expiresAt) {
                        store.delete(key);
                        cleanedCount++;
                    }
                }
            } else {
                for (let i = store.length - 1; i >= 0; i--) {
                    const key = store.key(i);
                    if (key && key.startsWith(this.prefix)) {
                        try {
                            const rawItem = store.getItem(key);
                            if (rawItem) {
                                const item = JSON.parse(rawItem);
                                if (Date.now() > item.expiresAt) {
                                    store.removeItem(key);
                                    cleanedCount++;
                                }
                            }
                        } catch (e) {
                            // Item corrupto, eliminarlo
                            store.removeItem(key);
                            cleanedCount++;
                        }
                    }
                }
            }
        });
        if (cleanedCount > 0) {
            console.info(`CacheService: ${cleanedCount} items expirados eliminados.`);
        }
    }

    /**
     * Elimina los items más antiguos si se excede la cuota (estrategia LRU simple).
     * @param {string} storeName - Nombre del store.
     * @param {number} count - Número de items a eliminar.
     */
    evictOldest(storeName, count = 1) {
        const store = this._getStore(storeName);
        if (store === this.stores.memory) {
            // Para Map, el orden de inserción se mantiene, podemos eliminar los primeros.
            const keys = Array.from(store.keys());
            for (let i = 0; i < Math.min(count, keys.length); i++) {
                store.delete(keys[i]);
            }
        } else {
            // Para localStorage/sessionStorage, necesitamos 'createdAt' para LRU.
            let items = [];
            for (let i = 0; i < store.length; i++) {
                const key = store.key(i);
                if (key && key.startsWith(this.prefix)) {
                    try {
                        const rawItem = store.getItem(key);
                        if (rawItem) {
                            const item = JSON.parse(rawItem);
                            items.push({ key, createdAt: item.createdAt || 0 });
                        }
                    } catch (e) { /* ignorar corruptos */ }
                }
            }
            items.sort((a, b) => a.createdAt - b.createdAt); // Ordenar por más antiguo
            for (let i = 0; i < Math.min(count, items.length); i++) {
                store.removeItem(items[i].key);
            }
        }
        console.warn(`CacheService: Se eliminaron ${count} items antiguos de '${storeName}' para liberar espacio.`);
    }

    /**
     * Obtiene el tamaño actual del caché (aproximado para localStorage/sessionStorage).
     * @param {string} [storeName=this.defaultStoreName] - Store a consultar.
     * @return {number} - Número de items o tamaño en bytes.
     */
    getSize(storeName = this.defaultStoreName) {
        const store = this._getStore(storeName);
        if (store === this.stores.memory) {
            return store.size;
        } else {
            // Para localStorage/sessionStorage, esto es un conteo de items con nuestro prefijo.
            // El tamaño real en bytes es más complejo de obtener de forma precisa.
            let count = 0;
            for (let i = 0; i < store.length; i++) {
                if (store.key(i)?.startsWith(this.prefix)) {
                    count++;
                }
            }
            return count;
        }
    }

    /**
     * Obtiene o establece un valor. Si la clave no existe o ha expirado,
     * la función `valueFn` se ejecuta para obtener el nuevo valor,
     * que luego se cachea.
     * @param {string} key - Clave.
     * @param {Function} valueFn - Función que retorna una Promesa o el valor a cachear.
     * @param {number} [ttl=this.defaultTTL] - Tiempo de vida en milisegundos.
     * @param {string} [storeName=this.defaultStoreName] - Store a utilizar.
     * @return {Promise<*>} - El valor (cacheado o nuevo).
     */
    async remember(key, valueFn, ttl = this.defaultTTL, storeName = this.defaultStoreName) {
        const cachedValue = this.get(key, storeName);
        if (cachedValue !== null) {
            return cachedValue;
        }

        const newValue = await valueFn();
        if (newValue !== null && newValue !== undefined) { // No cachear null o undefined por defecto
            this.set(key, newValue, ttl, storeName);
        }
        return newValue;
    }
}

// Registrar el servicio en la instancia global de la App
App.services.cache = new CacheService(App.config.DEFAULT_CACHE_STORE || 'localStorage');
