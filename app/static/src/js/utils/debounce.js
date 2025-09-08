/**
 * Debounce Utilities para Ecosistema de Emprendimiento
 * Sistema completo de debounce/throttle con funcionalidades avanzadas para optimización de rendimiento
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

/**
 * Clase base para funciones debounced
 */
class DebouncedFunction {
  constructor (func, wait, options = {}) {
    this.func = func
    this.wait = wait
    this.options = {
      leading: options.leading || false,
      trailing: options.trailing !== false,
      maxWait: options.maxWait || null,
      context: options.context || null,
      ...options
    }

    this.timeoutId = null
    this.maxTimeoutId = null
    this.lastCallTime = 0
    this.lastInvokeTime = 0
    this.lastArgs = null
    this.lastThis = null
    this.result = undefined
    this.callCount = 0
    this.executeCount = 0
    this.isDebounced = true

    // Bind methods
    this.debounced = this.debounced.bind(this)
    this.cancel = this.cancel.bind(this)
    this.flush = this.flush.bind(this)
    this.pending = this.pending.bind(this)

    return this.debounced
  }

  /**
     * Función debounced principal
     */
  debounced (...args) {
    const time = Date.now()
    const isInvoking = this.shouldInvoke(time)

    this.lastArgs = args
    this.lastThis = this
    this.lastCallTime = time
    this.callCount++

    if (isInvoking) {
      if (this.timeoutId === null) {
        return this.leadingEdge(time)
      }
      if (this.options.maxWait) {
        // Handle invocations in a tight loop.
        this.timeoutId = setTimeout(this.timerExpired.bind(this), this.wait)
        this.maxTimeoutId = setTimeout(this.maxDelayExpired.bind(this), this.options.maxWait)
        return this.invokeFunc(time)
      }
    }

    if (this.timeoutId === null) {
      this.timeoutId = setTimeout(this.timerExpired.bind(this), this.wait)
    }

    return this.result
  }

  /**
     * Determina si se debe invocar la función
     */
  shouldInvoke (time) {
    const timeSinceLastCall = time - this.lastCallTime
    const timeSinceLastInvoke = time - this.lastInvokeTime

    return (
      this.lastCallTime === 0 ||
            timeSinceLastCall >= this.wait ||
            timeSinceLastCall < 0 ||
            (this.options.maxWait && timeSinceLastInvoke >= this.options.maxWait)
    )
  }

  /**
     * Maneja el leading edge
     */
  leadingEdge (time) {
    this.lastInvokeTime = time
    this.timeoutId = setTimeout(this.timerExpired.bind(this), this.wait)
    return this.options.leading ? this.invokeFunc(time) : this.result
  }

  /**
     * Maneja cuando expira el timer
     */
  timerExpired () {
    const time = Date.now()
    if (this.shouldInvoke(time)) {
      return this.trailingEdge(time)
    }
    this.timeoutId = setTimeout(this.timerExpired.bind(this), this.remainingWait(time))
  }

  /**
     * Maneja el trailing edge
     */
  trailingEdge (time) {
    this.timeoutId = null

    if (this.options.trailing && this.lastArgs) {
      return this.invokeFunc(time)
    }

    this.lastArgs = this.lastThis = null
    return this.result
  }

  /**
     * Maneja cuando expira el maxWait
     */
  maxDelayExpired () {
    const time = Date.now()
    if (this.shouldInvoke(time)) {
      return this.trailingEdge(time)
    }
  }

  /**
     * Calcula el tiempo restante de espera
     */
  remainingWait (time) {
    const timeSinceLastCall = time - this.lastCallTime
    const timeSinceLastInvoke = time - this.lastInvokeTime
    const timeWaiting = this.wait - timeSinceLastCall

    return this.options.maxWait
      ? Math.min(timeWaiting, this.options.maxWait - timeSinceLastInvoke)
      : timeWaiting
  }

  /**
     * Invoca la función
     */
  invokeFunc (time) {
    const args = this.lastArgs
    const thisArg = this.options.context || this.lastThis

    this.lastArgs = this.lastThis = null
    this.lastInvokeTime = time
    this.executeCount++

    try {
      this.result = this.func.apply(thisArg, args)
    } catch (error) {
      console.error('Error in debounced function:', error)
      throw error
    }

    return this.result
  }

  /**
     * Cancela la ejecución pendiente
     */
  cancel () {
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId)
      this.timeoutId = null
    }
    if (this.maxTimeoutId !== null) {
      clearTimeout(this.maxTimeoutId)
      this.maxTimeoutId = null
    }

    this.lastInvokeTime = 0
    this.lastArgs = this.lastThis = null

    return this
  }

  /**
     * Ejecuta inmediatamente si hay una ejecución pendiente
     */
  flush () {
    if (this.timeoutId === null) {
      return this.result
    }

    return this.trailingEdge(Date.now())
  }

  /**
     * Verifica si hay una ejecución pendiente
     */
  pending () {
    return this.timeoutId !== null
  }

  /**
     * Obtiene estadísticas de uso
     */
  getStats () {
    return {
      callCount: this.callCount,
      executeCount: this.executeCount,
      efficiency: this.callCount > 0 ? (this.executeCount / this.callCount) : 0,
      isPending: this.pending(),
      lastCallTime: this.lastCallTime,
      lastInvokeTime: this.lastInvokeTime
    }
  }
}

/**
 * Clase para funciones throttled
 */
class ThrottledFunction extends DebouncedFunction {
  constructor (func, wait, options = {}) {
    super(func, wait, {
      leading: true,
      trailing: true,
      ...options
    })

    this.isDebounced = false
    this.isThrottled = true
  }

  /**
     * Función throttled principal
     */
  debounced (...args) {
    const time = Date.now()
    const isInvoking = this.shouldInvoke(time)

    this.lastArgs = args
    this.lastThis = this
    this.lastCallTime = time
    this.callCount++

    if (isInvoking) {
      if (this.timeoutId === null) {
        return this.leadingEdge(time)
      }
      if (this.options.trailing && this.lastArgs) {
        return this.invokeFunc(time)
      }
    }

    if (this.timeoutId === null) {
      this.timeoutId = setTimeout(this.timerExpired.bind(this), this.wait)
    }

    return this.result
  }
}

/**
 * Gestor de múltiples funciones debounced
 */
class DebounceManager {
  constructor () {
    this.debouncedFunctions = new Map()
    this.defaultOptions = {
      wait: 300,
      leading: false,
      trailing: true
    }
  }

  /**
     * Crea o obtiene una función debounced
     */
  create (key, func, options = {}) {
    if (this.debouncedFunctions.has(key)) {
      return this.debouncedFunctions.get(key)
    }

    const config = { ...this.defaultOptions, ...options }
    const debouncedFunc = new DebouncedFunction(func, config.wait, config)

    this.debouncedFunctions.set(key, debouncedFunc)
    return debouncedFunc
  }

  /**
     * Crea o obtiene una función throttled
     */
  createThrottled (key, func, options = {}) {
    if (this.debouncedFunctions.has(key)) {
      return this.debouncedFunctions.get(key)
    }

    const config = { ...this.defaultOptions, wait: 100, ...options }
    const throttledFunc = new ThrottledFunction(func, config.wait, config)

    this.debouncedFunctions.set(key, throttledFunc)
    return throttledFunc
  }

  /**
     * Obtiene función por key
     */
  get (key) {
    return this.debouncedFunctions.get(key)
  }

  /**
     * Cancela función específica
     */
  cancel (key) {
    const func = this.debouncedFunctions.get(key)
    if (func) {
      func.cancel()
    }
    return this
  }

  /**
     * Cancela todas las funciones
     */
  cancelAll () {
    this.debouncedFunctions.forEach(func => func.cancel())
    return this
  }

  /**
     * Ejecuta función específica inmediatamente
     */
  flush (key) {
    const func = this.debouncedFunctions.get(key)
    if (func) {
      return func.flush()
    }
  }

  /**
     * Ejecuta todas las funciones inmediatamente
     */
  flushAll () {
    const results = {}
    this.debouncedFunctions.forEach((func, key) => {
      results[key] = func.flush()
    })
    return results
  }

  /**
     * Elimina función del manager
     */
  remove (key) {
    const func = this.debouncedFunctions.get(key)
    if (func) {
      func.cancel()
      this.debouncedFunctions.delete(key)
    }
    return this
  }

  /**
     * Limpia todas las funciones
     */
  clear () {
    this.cancelAll()
    this.debouncedFunctions.clear()
    return this
  }

  /**
     * Obtiene estadísticas de todas las funciones
     */
  getStats () {
    const stats = {}
    this.debouncedFunctions.forEach((func, key) => {
      stats[key] = func.getStats()
    })
    return stats
  }

  /**
     * Lista todas las funciones registradas
     */
  list () {
    return Array.from(this.debouncedFunctions.keys())
  }

  /**
     * Verifica si hay funciones pendientes
     */
  hasPending () {
    for (const func of this.debouncedFunctions.values()) {
      if (func.pending()) {
        return true
      }
    }
    return false
  }
}

/**
 * Debounce con soporte para Promises
 */
class AsyncDebouncedFunction {
  constructor (asyncFunc, wait, options = {}) {
    this.asyncFunc = asyncFunc
    this.wait = wait
    this.options = {
      leading: options.leading || false,
      trailing: options.trailing !== false,
      rejectOnCancel: options.rejectOnCancel || false,
      ...options
    }

    this.timeoutId = null
    this.pendingPromises = []
    this.lastArgs = null
    this.lastResult = null
    this.isExecuting = false

    this.debounced = this.debounced.bind(this)
    this.cancel = this.cancel.bind(this)
    this.flush = this.flush.bind(this)

    return this.debounced
  }

  /**
     * Función debounced que retorna Promise
     */
  debounced (...args) {
    return new Promise((resolve, reject) => {
      this.lastArgs = args

      // Agregar promise a la cola
      this.pendingPromises.push({ resolve, reject })

      // Cancelar timeout anterior
      if (this.timeoutId) {
        clearTimeout(this.timeoutId)
      }

      // Configurar nuevo timeout
      this.timeoutId = setTimeout(async () => {
        await this.executeFunction()
      }, this.wait)

      // Ejecutar inmediatamente si leading está habilitado
      if (this.options.leading && !this.isExecuting) {
        this.executeFunction()
      }
    })
  }

  /**
     * Ejecuta la función asíncrona
     */
  async executeFunction () {
    if (this.isExecuting) return

    this.isExecuting = true
    const promises = this.pendingPromises.splice(0)

    try {
      const result = await this.asyncFunc(...this.lastArgs)
      this.lastResult = result

      // Resolver todas las promises pendientes
      promises.forEach(({ resolve }) => resolve(result))
    } catch (error) {
      // Rechazar todas las promises pendientes
      promises.forEach(({ reject }) => reject(error))
    } finally {
      this.isExecuting = false
      this.timeoutId = null
    }
  }

  /**
     * Cancela la ejecución pendiente
     */
  cancel () {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId)
      this.timeoutId = null
    }

    // Manejar promises pendientes según configuración
    const promises = this.pendingPromises.splice(0)
    promises.forEach(({ resolve, reject }) => {
      if (this.options.rejectOnCancel) {
        reject(new Error('Debounced function cancelled'))
      } else {
        resolve(this.lastResult)
      }
    })

    return this
  }

  /**
     * Ejecuta inmediatamente
     */
  async flush () {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId)
      this.timeoutId = null
    }

    if (this.pendingPromises.length > 0) {
      await this.executeFunction()
    }

    return this.lastResult
  }

  /**
     * Verifica si hay ejecución pendiente
     */
  pending () {
    return this.timeoutId !== null || this.isExecuting
  }
}

/**
 * Funciones de utilidad principales
 */
const DebounceUtils = {
  /**
     * Debounce básico
     */
  debounce (func, wait = 300, options = {}) {
    return new DebouncedFunction(func, wait, options)
  },

  /**
     * Throttle básico
     */
  throttle (func, wait = 100, options = {}) {
    return new ThrottledFunction(func, wait, options)
  },

  /**
     * Debounce asíncrono
     */
  debounceAsync (asyncFunc, wait = 300, options = {}) {
    return new AsyncDebouncedFunction(asyncFunc, wait, options)
  },

  /**
     * Debounce con cancelación automática en cleanup
     */
  debounceWithCleanup (func, wait = 300, options = {}) {
    const debouncedFunc = new DebouncedFunction(func, wait, options)

    // Auto-cancelar en beforeunload
    const cleanup = () => debouncedFunc.cancel()
    window.addEventListener('beforeunload', cleanup)

    // Agregar método para remover listener
    debouncedFunc.removeCleanup = () => {
      window.removeEventListener('beforeunload', cleanup)
    }

    return debouncedFunc
  },

  /**
     * Debounce para elementos del DOM
     */
  debounceElement (element, event, handler, wait = 300, options = {}) {
    const debouncedHandler = this.debounce(handler, wait, options)

    element.addEventListener(event, debouncedHandler)

    return {
      debounced: debouncedHandler,
      remove: () => element.removeEventListener(event, debouncedHandler),
      cancel: () => debouncedHandler.cancel(),
      flush: () => debouncedHandler.flush()
    }
  },

  /**
     * Debounce reactivo para inputs
     */
  debounceInput (input, handler, wait = 300, options = {}) {
    const config = {
      leading: false,
      trailing: true,
      ...options
    }

    const debouncedHandler = this.debounce((event) => {
      handler(event.target.value, event)
    }, wait, config)

    input.addEventListener('input', debouncedHandler)

    // También manejar paste
    input.addEventListener('paste', (e) => {
      setTimeout(() => debouncedHandler(e), 0)
    })

    return {
      debounced: debouncedHandler,
      remove: () => {
        input.removeEventListener('input', debouncedHandler)
        input.removeEventListener('paste', debouncedHandler)
      },
      cancel: () => debouncedHandler.cancel(),
      flush: () => debouncedHandler.flush()
    }
  },

  /**
     * Debounce para múltiples eventos
     */
  debounceMultiEvent (element, events, handler, wait = 300, options = {}) {
    const debouncedHandler = this.debounce(handler, wait, options)
    const eventsList = Array.isArray(events) ? events : [events]

    eventsList.forEach(event => {
      element.addEventListener(event, debouncedHandler)
    })

    return {
      debounced: debouncedHandler,
      remove: () => {
        eventsList.forEach(event => {
          element.removeEventListener(event, debouncedHandler)
        })
      },
      cancel: () => debouncedHandler.cancel(),
      flush: () => debouncedHandler.flush()
    }
  },

  /**
     * Debounce con rate limiting
     */
  debounceWithRateLimit (func, wait = 300, options = {}) {
    const config = {
      maxCalls: 10,
      resetInterval: 60000, // 1 minuto
      ...options
    }

    let callCount = 0
    let resetTimer = null

    const resetCallCount = () => {
      callCount = 0
      resetTimer = null
    }

    const wrappedFunc = (...args) => {
      callCount++

      if (callCount === 1 && resetTimer === null) {
        resetTimer = setTimeout(resetCallCount, config.resetInterval)
      }

      if (callCount > config.maxCalls) {
        console.warn('Rate limit exceeded for debounced function')
        return
      }

      return func(...args)
    }

    return this.debounce(wrappedFunc, wait, options)
  }
}

/**
 * Utilidades específicas del ecosistema de emprendimiento
 */
const EcosystemDebounce = {
  /**
     * Debounce para búsqueda de proyectos
     */
  projectSearch (searchHandler, wait = 400) {
    return DebounceUtils.debounce((query) => {
      if (query.length < 2) return

      return searchHandler({
        query: query.trim(),
        filters: {
          status: 'active',
          verified: true
        },
        timestamp: Date.now()
      })
    }, wait, {
      leading: false,
      trailing: true
    })
  },

  /**
     * Debounce para búsqueda de emprendedores
     */
  entrepreneurSearch (searchHandler, wait = 400) {
    return DebounceUtils.debounce((query, filters = {}) => {
      if (query.length < 2) return

      return searchHandler({
        query: query.trim(),
        filters: {
          role: 'entrepreneur',
          status: 'active',
          ...filters
        },
        sortBy: 'relevance',
        limit: 20
      })
    }, wait)
  },

  /**
     * Debounce para validación de formularios
     */
  formValidation (validator, wait = 500) {
    return DebounceUtils.debounce((field, value, formData) => {
      return validator({
        field,
        value,
        formData,
        timestamp: Date.now()
      })
    }, wait, {
      leading: false,
      trailing: true
    })
  },

  /**
     * Debounce para auto-guardado
     */
  autoSave (saveHandler, wait = 2000) {
    return DebounceUtils.debounce((data, options = {}) => {
      const saveData = {
        ...data,
        lastModified: Date.now(),
        autoSaved: true,
        ...options
      }

      return saveHandler(saveData)
    }, wait, {
      leading: false,
      trailing: true,
      maxWait: 10000 // Forzar guardado máximo cada 10 segundos
    })
  },

  /**
     * Debounce para actualización de métricas
     */
  metricsUpdate (updateHandler, wait = 1000) {
    return DebounceUtils.throttle((metrics) => {
      return updateHandler({
        ...metrics,
        timestamp: Date.now(),
        source: 'realtime'
      })
    }, wait)
  },

  /**
     * Debounce para notificaciones
     */
  notificationBatch (notificationHandler, wait = 800) {
    const notifications = []

    return DebounceUtils.debounce(() => {
      if (notifications.length === 0) return

      const batch = notifications.splice(0)
      return notificationHandler({
        notifications: batch,
        count: batch.length,
        timestamp: Date.now()
      })
    }, wait)
  },

  /**
     * Debounce para actualización de estado en tiempo real
     */
  realtimeUpdate (updateHandler, wait = 300) {
    return DebounceUtils.throttle((updateData) => {
      return updateHandler({
        ...updateData,
        timestamp: Date.now(),
        type: 'realtime'
      })
    }, wait, {
      leading: true,
      trailing: true
    })
  },

  /**
     * Debounce para scroll infinito
     */
  infiniteScroll (loadHandler, wait = 200) {
    return DebounceUtils.throttle((scrollData) => {
      const { scrollTop, scrollHeight, clientHeight } = scrollData
      const threshold = 0.8 // Cargar cuando esté al 80%

      if (scrollTop + clientHeight >= scrollHeight * threshold) {
        return loadHandler({
          page: scrollData.page || 1,
          timestamp: Date.now()
        })
      }
    }, wait)
  },

  /**
     * Debounce para tracking de analytics
     */
  analyticsTrack (trackHandler, wait = 1000) {
    const events = []

    return DebounceUtils.debounce(() => {
      if (events.length === 0) return

      const batch = events.splice(0)
      return trackHandler({
        events: batch,
        batchSize: batch.length,
        timestamp: Date.now()
      })
    }, wait)
  }
}

/**
 * Manager global de debounce
 */
const globalDebounceManager = new DebounceManager()

/**
 * Configuración de debounce para elementos automáticamente
 */
const AutoDebounce = {
  /**
     * Configurar debounce automático para elementos con data attributes
     */
  setup () {
    // Inputs de búsqueda
    document.querySelectorAll('[data-debounce-search]').forEach(input => {
      const wait = parseInt(input.getAttribute('data-debounce-wait')) || 400
      const handler = window[input.getAttribute('data-debounce-handler')]

      if (handler) {
        DebounceUtils.debounceInput(input, handler, wait)
      }
    })

    // Formularios de auto-guardado
    document.querySelectorAll('[data-debounce-autosave]').forEach(form => {
      const wait = parseInt(form.getAttribute('data-debounce-wait')) || 2000
      const handler = window[form.getAttribute('data-debounce-handler')]

      if (handler) {
        const debouncedSave = DebounceUtils.debounce(handler, wait)

        form.addEventListener('input', () => {
          const formData = new FormData(form)
          debouncedSave(Object.fromEntries(formData))
        })
      }
    })

    // Validación de formularios
    document.querySelectorAll('[data-debounce-validate]').forEach(input => {
      const wait = parseInt(input.getAttribute('data-debounce-wait')) || 500
      const validator = window[input.getAttribute('data-debounce-validator')]

      if (validator) {
        DebounceUtils.debounceInput(input, (value) => {
          validator(input.name, value, new FormData(input.form))
        }, wait)
      }
    })
  },

  /**
     * Limpiar todos los debounces automáticos
     */
  cleanup () {
    globalDebounceManager.clear()
  }
}

/**
 * Utilidades para debugging y monitoreo
 */
const DebounceMonitor = {
  /**
     * Monitor de eficiencia de debounce
     */
  monitor (debouncedFunc, label = 'debounced') {
    const originalFunc = debouncedFunc.func
    const monitoringData = {
      label,
      calls: 0,
      executions: 0,
      avgWaitTime: 0,
      lastCallTime: 0,
      lastExecTime: 0
    }

    // Wrap la función original para monitoreo
    debouncedFunc.func = (...args) => {
      monitoringData.executions++
      monitoringData.lastExecTime = Date.now()

      if (monitoringData.calls > 0) {
        const waitTime = monitoringData.lastExecTime - monitoringData.lastCallTime
        monitoringData.avgWaitTime =
                    (monitoringData.avgWaitTime * (monitoringData.executions - 1) + waitTime) /
                    monitoringData.executions
      }

      console.log(`[Debounce Monitor] ${label}:`, {
        efficiency: `${((monitoringData.executions / monitoringData.calls) * 100).toFixed(1)}%`,
        savedCalls: monitoringData.calls - monitoringData.executions,
        avgWait: `${monitoringData.avgWaitTime.toFixed(0)}ms`
      })

      return originalFunc.apply(this, args)
    }

    // Wrap el debounced para contar llamadas
    const originalDebounced = debouncedFunc.debounced
    debouncedFunc.debounced = (...args) => {
      monitoringData.calls++
      monitoringData.lastCallTime = Date.now()
      return originalDebounced.apply(this, args)
    }

    return monitoringData
  },

  /**
     * Obtener estadísticas globales
     */
  getGlobalStats () {
    return globalDebounceManager.getStats()
  },

  /**
     * Verificar funciones pendientes
     */
  getPendingFunctions () {
    const stats = this.getGlobalStats()
    const pending = []

    Object.entries(stats).forEach(([key, stat]) => {
      if (stat.isPending) {
        pending.push({
          key,
          callCount: stat.callCount,
          executeCount: stat.executeCount,
          efficiency: stat.efficiency
        })
      }
    })

    return pending
  }
}

/**
 * API principal del módulo
 */
const Debounce = {
  // Funciones principales
  debounce: DebounceUtils.debounce,
  throttle: DebounceUtils.throttle,
  debounceAsync: DebounceUtils.debounceAsync,

  // Utilidades avanzadas
  utils: DebounceUtils,
  ecosystem: EcosystemDebounce,
  manager: globalDebounceManager,
  auto: AutoDebounce,
  monitor: DebounceMonitor,

  // Clases para uso avanzado
  DebouncedFunction,
  ThrottledFunction,
  AsyncDebouncedFunction,
  DebounceManager,

  /**
     * Configuración rápida para casos comunes
     */
  quick: {
    search: (handler) => EcosystemDebounce.projectSearch(handler),
    validate: (handler) => EcosystemDebounce.formValidation(handler),
    save: (handler) => EcosystemDebounce.autoSave(handler),
    scroll: (handler) => EcosystemDebounce.infiniteScroll(handler),
    track: (handler) => EcosystemDebounce.analyticsTrack(handler)
  },

  /**
     * Inicializar sistema de debounce
     */
  init () {
    AutoDebounce.setup()

    // Cleanup automático
    window.addEventListener('beforeunload', () => {
      globalDebounceManager.cancelAll()
    })

    console.log('🚀 Debounce system initialized')
  }
}

// Auto-inicialización
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Debounce.init())
} else {
  Debounce.init()
}

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Debounce
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.Debounce = Debounce
  window.debounce = Debounce.debounce
  window.throttle = Debounce.throttle
}
