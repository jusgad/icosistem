/**
 * SyncService.js - Servicio de Sincronización de Datos
 * =====================================================
 *
 * Maneja la sincronización de datos entre el cliente y el servidor,
 * incluyendo la gestión de colas, conflictos y estado de sincronización.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.events, App.config, App.services.cache, App.services.auth)
 * @requires: NetworkService (opcional, para detectar estado de red)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que SyncService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class SyncService {
  constructor () {
    this.baseEndpoint = '/api/v1/sync' // Endpoint base para sincronización
    this.syncQueueKey = App.config.SYNC_QUEUE_KEY || 'syncQueue'
    this.lastSyncTimestampsKey = App.config.LAST_SYNC_TIMESTAMPS_KEY || 'lastSyncTimestamps'

    this.syncInterval = App.config.SYNC_INTERVAL || (5 * 60 * 1000) // 5 minutos por defecto
    this.maxRetries = App.config.SYNC_MAX_RETRIES || 3
    this.retryDelay = App.config.SYNC_RETRY_DELAY || 5000 // 5 segundos

    this.isSyncing = false
    this.syncTimer = null
    this.syncQueue = this._loadQueue() // Cola de operaciones pendientes
    this.registeredDataTypes = new Map() // Tipos de datos registrados para sincronizar

    this._initialize()
  }

  /**
     * Inicializa el servicio.
     * @private
     */
  _initialize () {
    // Registrar tipos de datos por defecto (ejemplos)
    this.registerDataType('projects', {
      endpoint: '/api/v1/projects',
      localCacheKey: 'projects_data',
      conflictResolver: this._defaultConflictResolver.bind(this)
    })
    this.registerDataType('tasks', {
      endpoint: '/api/v1/tasks',
      localCacheKey: 'tasks_data',
      conflictResolver: this._defaultConflictResolver.bind(this)
    })

    // Iniciar sincronización si el usuario está autenticado y hay conexión
    if (App.services.auth && App.services.auth.check() && navigator.onLine) {
      this.startPeriodicSync()
      this.processQueue() // Procesar cola pendiente al inicio
    }

    // Escuchar cambios de estado de autenticación y red
    App.events.addEventListener('auth:login', () => this.startPeriodicSync())
    App.events.addEventListener('auth:logout', () => this.stopPeriodicSync())

    if (App.services.network) {
      App.services.network.on('online', () => this.processQueue())
    } else {
      window.addEventListener('online', () => this.processQueue())
    }
  }

  /**
     * Registra un tipo de dato para ser sincronizado.
     * @param {string} name - Nombre del tipo de dato (e.g., 'projects').
     * @param {Object} config - Configuración para este tipo de dato.
     *   - endpoint: {string} Endpoint API para este dato.
     *   - localCacheKey: {string} Clave en CacheService para datos locales.
     *   - conflictResolver: {Function} Función para resolver conflictos.
     *   - preSyncHook: {Function} (Opcional) Hook antes de sincronizar.
     *   - postSyncHook: {Function} (Opcional) Hook después de sincronizar.
     */
  registerDataType (name, config) {
    if (!config.endpoint || !config.localCacheKey) {
      console.error(`SyncService: Configuración inválida para el tipo de dato '${name}'.`)
      return
    }
    this.registeredDataTypes.set(name, {
      name,
      lastSync: this._getLastSyncTimestamp(name),
      status: 'idle', // idle, syncing, error
      error: null,
      ...config
    })
    console.info(`SyncService: Tipo de dato '${name}' registrado para sincronización.`)
  }

  /**
     * Inicia la sincronización periódica.
     */
  startPeriodicSync () {
    this.stopPeriodicSync() // Asegurar que no haya timers duplicados
    if (App.config.ENABLE_PERIODIC_SYNC !== false) {
      this.syncTimer = setInterval(() => this.syncAllRegisteredTypes(), this.syncInterval)
      console.info('SyncService: Sincronización periódica iniciada.')
      this.syncAllRegisteredTypes() // Sincronizar inmediatamente al iniciar
    }
  }

  /**
     * Detiene la sincronización periódica.
     */
  stopPeriodicSync () {
    if (this.syncTimer) {
      clearInterval(this.syncTimer)
      this.syncTimer = null
      console.info('SyncService: Sincronización periódica detenida.')
    }
  }

  /**
     * Sincroniza todos los tipos de datos registrados.
     * @param {boolean} forceFullSync - Si se debe forzar una sincronización completa.
     */
  async syncAllRegisteredTypes (forceFullSync = false) {
    if (this.isSyncing) {
      console.warn('SyncService: Sincronización ya en progreso.')
      return
    }
    if (!navigator.onLine) {
      console.warn('SyncService: Sin conexión, sincronización pospuesta.')
      return
    }
    if (!App.services.auth || !App.services.auth.check()) {
      console.warn('SyncService: Usuario no autenticado, sincronización detenida.')
      this.stopPeriodicSync()
      return
    }

    this.isSyncing = true
    App.events.dispatchEvent('sync:global_started')
    console.info('SyncService: Iniciando sincronización global...')

    for (const dataType of this.registeredDataTypes.values()) {
      await this.syncDataType(dataType.name, forceFullSync)
    }

    this.isSyncing = false
    App.events.dispatchEvent('sync:global_completed')
    console.info('SyncService: Sincronización global completada.')
  }

  /**
     * Sincroniza un tipo de dato específico.
     * @param {string} typeName - Nombre del tipo de dato.
     * @param {boolean} forceFullSync - Si se debe forzar una sincronización completa.
     */
  async syncDataType (typeName, forceFullSync = false) {
    const dataType = this.registeredDataTypes.get(typeName)
    if (!dataType) {
      console.error(`SyncService: Tipo de dato '${typeName}' no registrado.`)
      return
    }

    if (dataType.status === 'syncing') {
      console.warn(`SyncService: Sincronización para '${typeName}' ya en progreso.`)
      return
    }

    this._updateDataTypeStatus(typeName, 'syncing')
    App.events.dispatchEvent(`sync:${typeName}_started`)
    console.info(`SyncService: Sincronizando '${typeName}'...`)

    try {
      // Ejecutar pre-sync hook si existe
      if (dataType.preSyncHook) await dataType.preSyncHook()

      // 1. Enviar cambios locales al servidor
      const pushSuccessful = await this._pushLocalChanges(dataType)
      if (!pushSuccessful) {
        // Si el push falla, podríamos decidir no continuar con el fetch
        // o manejarlo de forma diferente. Por ahora, continuamos.
        console.warn(`SyncService: Falló el envío de cambios locales para '${typeName}'.`)
      }

      // 2. Obtener cambios del servidor
      const serverChanges = await this._fetchServerChanges(dataType, forceFullSync)

      // 3. Aplicar cambios del servidor localmente
      if (serverChanges && serverChanges.length > 0) {
        await this._applyServerChanges(dataType, serverChanges)
      }

      // 4. Actualizar timestamp de última sincronización
      this._setLastSyncTimestamp(typeName, new Date().toISOString())
      this._updateDataTypeStatus(typeName, 'idle')
      App.events.dispatchEvent(`sync:${typeName}_completed`, { typeName, changes: serverChanges })
      console.info(`SyncService: Sincronización de '${typeName}' completada.`)

      // Ejecutar post-sync hook si existe
      if (dataType.postSyncHook) await dataType.postSyncHook(serverChanges)
    } catch (error) {
      console.error(`SyncService: Error sincronizando '${typeName}':`, error)
      this._updateDataTypeStatus(typeName, 'error', error.message)
      App.events.dispatchEvent(`sync:${typeName}_error`, { typeName, error: error.message })
    }
  }

  /**
     * Añade una operación a la cola de sincronización.
     * @param {Object} operation - La operación a encolar.
     *   - type: {string} Tipo de operación (create, update, delete).
     *   - dataType: {string} Nombre del tipo de dato.
     *   - data: {Object} Datos de la operación.
     *   - id: {string|number} (Opcional) ID del item.
     *   - timestamp: {string} ISO timestamp.
     *   - retries: {number} (Opcional) Número de reintentos.
     */
  queueOperation (operation) {
    if (!operation.type || !operation.dataType || !operation.data) {
      console.error('SyncService: Operación de sincronización inválida.', operation)
      return
    }
    operation.timestamp = new Date().toISOString()
    operation.id = operation.id || `op_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
    operation.retries = 0

    this.syncQueue.push(operation)
    this._saveQueue()
    App.events.dispatchEvent('sync:queued', operation)

    // Intentar procesar la cola inmediatamente si hay conexión
    if (navigator.onLine) {
      this.processQueue()
    }
  }

  /**
     * Procesa la cola de operaciones pendientes.
     */
  async processQueue () {
    if (this.isSyncing || !navigator.onLine || this.syncQueue.length === 0) {
      return
    }
    if (!App.services.auth || !App.services.auth.check()) return

    this.isSyncing = true // Bloquear para evitar procesamiento concurrente de la cola
    console.info(`SyncService: Procesando cola de ${this.syncQueue.length} operaciones.`)

    const operationsToRetry = []
    while (this.syncQueue.length > 0) {
      const operation = this.syncQueue.shift()
      try {
        const dataType = this.registeredDataTypes.get(operation.dataType)
        if (!dataType) {
          console.warn(`SyncService: Tipo de dato '${operation.dataType}' no registrado para operación encolada.`)
          operation.retries = (operation.retries || 0) + 1 // Contar como reintento
          if (operation.retries < this.maxRetries) operationsToRetry.push(operation)
          else console.error(`SyncService: Operación descartada para '${operation.dataType}' después de ${this.maxRetries} reintentos.`)
          continue
        }

        await this._executeOperation(operation, dataType)
        App.events.dispatchEvent('sync:operation_processed', operation)
      } catch (error) {
        console.error(`SyncService: Error procesando operación ${operation.id}:`, error)
        operation.retries = (operation.retries || 0) + 1
        if (operation.retries < this.maxRetries) {
          operationsToRetry.push(operation)
          await new Promise(resolve => setTimeout(resolve, this.retryDelay)) // Esperar antes de reintentar
        } else {
          console.error(`SyncService: Operación ${operation.id} descartada después de ${this.maxRetries} reintentos.`)
          App.events.dispatchEvent('sync:operation_failed', { operation, error: error.message })
        }
      }
    }

    // Re-encolar operaciones que fallaron y aún tienen reintentos
    if (operationsToRetry.length > 0) {
      this.syncQueue.unshift(...operationsToRetry)
    }

    this._saveQueue()
    this.isSyncing = false
    console.info('SyncService: Procesamiento de cola finalizado.')

    // Si la cola no está vacía, intentar de nuevo después de un delay
    if (this.syncQueue.length > 0) {
      setTimeout(() => this.processQueue(), this.retryDelay * 2)
    }
  }

  /**
     * Obtiene el estado de sincronización para un tipo de dato.
     * @param {string} typeName - Nombre del tipo de dato.
     * @return {Object|null} Estado o null si no está registrado.
     */
  getSyncStatus (typeName) {
    const dataType = this.registeredDataTypes.get(typeName)
    if (!dataType) return null
    return {
      name: dataType.name,
      status: dataType.status,
      lastSync: dataType.lastSync,
      error: dataType.error
    }
  }

  /**
     * Obtiene todos los estados de sincronización.
     * @return {Array<Object>}
     */
  getAllSyncStatuses () {
    return Array.from(this.registeredDataTypes.values()).map(dt => ({
      name: dt.name,
      status: dt.status,
      lastSync: dt.lastSync,
      error: dt.error
    }))
  }

  /**
     * Carga la cola de operaciones desde CacheService.
     * @private
     */
  _loadQueue () {
    return App.services.cache.get(this.syncQueueKey, 'localStorage') || []
  }

  /**
     * Guarda la cola de operaciones en CacheService.
     * @private
     */
  _saveQueue () {
    App.services.cache.set(this.syncQueueKey, this.syncQueue, Infinity, 'localStorage')
  }

  /**
     * Obtiene el timestamp de la última sincronización para un tipo de dato.
     * @param {string} typeName - Nombre del tipo de dato.
     * @return {string|null} ISO timestamp o null.
     * @private
     */
  _getLastSyncTimestamp (typeName) {
    const timestamps = App.services.cache.get(this.lastSyncTimestampsKey, 'localStorage') || {}
    return timestamps[typeName] || null
  }

  /**
     * Establece el timestamp de la última sincronización.
     * @param {string} typeName - Nombre del tipo de dato.
     * @param {string} timestamp - ISO timestamp.
     * @private
     */
  _setLastSyncTimestamp (typeName, timestamp) {
    const dataType = this.registeredDataTypes.get(typeName)
    if (dataType) dataType.lastSync = timestamp

    const timestamps = App.services.cache.get(this.lastSyncTimestampsKey, 'localStorage') || {}
    timestamps[typeName] = timestamp
    App.services.cache.set(this.lastSyncTimestampsKey, timestamps, Infinity, 'localStorage')
  }

  /**
     * Actualiza el estado de un tipo de dato.
     * @param {string} typeName - Nombre del tipo de dato.
     * @param {string} status - Nuevo estado.
     * @param {string|null} error - Mensaje de error (opcional).
     * @private
     */
  _updateDataTypeStatus (typeName, status, error = null) {
    const dataType = this.registeredDataTypes.get(typeName)
    if (dataType) {
      dataType.status = status
      dataType.error = error
      App.events.dispatchEvent('sync:status_changed', { typeName, status, error })
    }
  }

  /**
     * Envía cambios locales al servidor.
     * @param {Object} dataType - Configuración del tipo de dato.
     * @return {Promise<boolean>} True si fue exitoso.
     * @private
     */
  async _pushLocalChanges (dataType) {
    // Esta es una implementación simplificada.
    // En una app real, se necesitaría un sistema para rastrear cambios locales (dirty flags, change log).
    // Por ahora, asumimos que no hay cambios locales complejos que enviar o que se manejan por operación.
    console.info(`SyncService: Verificando cambios locales para '${dataType.name}' (implementación simplificada).`)
    // Aquí se procesaría la `this.syncQueue` para el `dataType` específico si las operaciones
    // no se procesan individualmente.
    return true
  }

  /**
     * Obtiene cambios del servidor.
     * @param {Object} dataType - Configuración del tipo de dato.
     * @param {boolean} forceFullSync - Si se debe forzar una sincronización completa.
     * @return {Promise<Array<Object>>} Array de cambios.
     * @private
     */
  async _fetchServerChanges (dataType, forceFullSync) {
    const params = {}
    if (!forceFullSync && dataType.lastSync) {
      params.since = dataType.lastSync
    }
    // Podría incluir otros parámetros como `limit`, `offset` para paginación de sync.

    try {
      const response = await App.http.get(`${dataType.endpoint}/changes`, params) // Asume un endpoint `/changes`
      // El formato de `response` dependerá de tu API. Podría ser:
      // { data: [...], deleted_ids: [...], new_sync_token: '...' }
      return response.data || response // Ajustar según la respuesta real de tu API
    } catch (error) {
      console.error(`SyncService: Error obteniendo cambios del servidor para '${dataType.name}':`, error)
      throw new Error(`No se pudieron obtener los cambios del servidor para ${dataType.name}.`)
    }
  }

  /**
     * Aplica cambios del servidor localmente.
     * @param {Object} dataType - Configuración del tipo de dato.
     * @param {Array<Object>} changes - Array de cambios del servidor.
     * @private
     */
  async _applyServerChanges (dataType, changes) {
    let localData = App.services.cache.get(dataType.localCacheKey, 'localStorage') || []
    if (!Array.isArray(localData)) localData = [] // Asegurar que sea un array

    // Asumimos que `changes` es un array de objetos y cada objeto tiene un `id`.
    // Y que `changes` puede contener items nuevos, actualizados o marcados para eliminación.
    changes.forEach(serverItem => {
      const localItemIndex = localData.findIndex(item => item.id === serverItem.id)

      if (serverItem._deleted) { // Asume una propiedad `_deleted` para marcar eliminaciones
        if (localItemIndex !== -1) {
          localData.splice(localItemIndex, 1)
        }
      } else if (localItemIndex !== -1) {
        // Item existe, aplicar resolución de conflictos y actualizar
        localData[localItemIndex] = dataType.conflictResolver(localData[localItemIndex], serverItem)
      } else {
        // Item nuevo, añadir
        localData.push(serverItem)
      }
    })

    App.services.cache.set(dataType.localCacheKey, localData, Infinity, 'localStorage')
    App.events.dispatchEvent(`data:${dataType.name}_updated`, { data: localData })
    console.info(`SyncService: Cambios del servidor aplicados localmente para '${dataType.name}'.`)
  }

  /**
     * Resuelve conflictos entre datos locales y del servidor.
     * Estrategia por defecto: "el servidor gana".
     * @param {Object} localItem - Item local.
     * @param {Object} serverItem - Item del servidor.
     * @return {Object} Item resuelto.
     * @private
     */
  _defaultConflictResolver (localItem, serverItem) {
    // Comparar timestamps si existen
    const localTimestamp = localItem.updated_at || localItem.timestamp
    const serverTimestamp = serverItem.updated_at || serverItem.timestamp

    if (localTimestamp && serverTimestamp) {
      // Si el servidor tiene una actualización más reciente, usarla.
      // Podrías implementar "last write wins" o una lógica más compleja.
      return new Date(serverTimestamp) > new Date(localTimestamp) ? serverItem : localItem
    }
    // Por defecto, el servidor gana si no hay timestamps o son iguales.
    return serverItem
  }

  /**
     * Ejecuta una operación de la cola.
     * @param {Object} operation - La operación a ejecutar.
     * @param {Object} dataType - Configuración del tipo de dato.
     * @private
     */
  async _executeOperation (operation, dataType) {
    let endpoint = dataType.endpoint
    let method

    switch (operation.type) {
      case 'create':
        method = 'post'
        break
      case 'update':
        method = 'put'
        endpoint = `${dataType.endpoint}/${operation.data.id || operation.id}` // Asume que el ID está en data o en la operación
        break
      case 'delete':
        method = 'delete'
        endpoint = `${dataType.endpoint}/${operation.id}` // Asume que el ID está en la operación
        break
      default:
        throw new Error(`SyncService: Tipo de operación desconocido '${operation.type}'.`)
    }

    try {
      const response = await App.httpmethod
      console.info(`SyncService: Operación ${operation.id} (${operation.type} ${operation.dataType}) ejecutada exitosamente.`)
      // Podrías querer actualizar el caché local con la respuesta del servidor aquí.
      // Por ejemplo, si el servidor devuelve el objeto creado/actualizado:
      // this._updateLocalCacheWithOperationResponse(dataType, response);
      return response
    } catch (error) {
      console.error(`SyncService: Error ejecutando operación ${operation.id}:`, error)
      // Si el error es un 409 (Conflicto), podría necesitar una lógica de resolución especial.
      if (error.status === 409) {
        // Intentar obtener la versión más reciente del servidor y resolver el conflicto.
        // Esto es complejo y depende de la aplicación.
        console.warn(`SyncService: Conflicto detectado para operación ${operation.id}. Se requiere resolución manual o estrategia automática.`)
      }
      throw error // Re-lanzar para que processQueue lo maneje (reintentos)
    }
  }
}

// Registrar el servicio en la instancia global de la App
App.services.sync = new SyncService()
