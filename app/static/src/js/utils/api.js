/**
 * API Utilities para Ecosistema de Emprendimiento
 * Cliente HTTP robusto con manejo avanzado de errores, caché, autenticación y offline support
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

class APIClient {
  constructor (config = {}) {
    this.config = {
      // Configuración base
      baseURL: config.baseURL || '/api/v1',
      timeout: config.timeout || 30000,
      retries: config.retries || 3,
      retryDelay: config.retryDelay || 1000,

      // Headers por defecto
      defaultHeaders: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...config.defaultHeaders
      },

      // Configuración de autenticación
      auth: {
        type: config.auth?.type || 'bearer', // bearer, basic, custom
        tokenKey: config.auth?.tokenKey || 'access_token',
        refreshTokenKey: config.auth?.refreshTokenKey || 'refresh_token',
        autoRefresh: config.auth?.autoRefresh !== false,
        ...config.auth
      },

      // Configuración de caché
      cache: {
        enabled: config.cache?.enabled !== false,
        ttl: config.cache?.ttl || 300000, // 5 minutos
        maxSize: config.cache?.maxSize || 100,
        storage: config.cache?.storage || 'memory', // memory, localStorage, sessionStorage
        ...config.cache
      },

      // Configuración offline
      offline: {
        enabled: config.offline?.enabled !== false,
        queueRequests: config.offline?.queueRequests !== false,
        maxQueueSize: config.offline?.maxQueueSize || 50,
        ...config.offline
      },

      // Rate limiting
      rateLimit: {
        enabled: config.rateLimit?.enabled || false,
        maxRequests: config.rateLimit?.maxRequests || 100,
        windowMs: config.rateLimit?.windowMs || 60000,
        ...config.rateLimit
      }
    }

    // Estados internos
    this.isOnline = navigator.onLine
    this.requestQueue = []
    this.activeRequests = new Map()
    this.rateLimitCounter = new Map()

    // Inicializar sistemas
    this.initializeCache()
    this.initializeInterceptors()
    this.initializeEventListeners()
    this.initializeWebSocket()

    // Endpoints específicos del ecosistema
    this.endpoints = {
      // Autenticación
      auth: {
        login: '/auth/login',
        logout: '/auth/logout',
        refresh: '/auth/refresh',
        register: '/auth/register',
        forgotPassword: '/auth/forgot-password',
        resetPassword: '/auth/reset-password',
        verifyEmail: '/auth/verify-email'
      },

      // Usuarios
      users: {
        profile: '/users/profile',
        update: '/users/profile',
        avatar: '/users/avatar',
        status: '/users/status',
        list: '/users',
        search: '/users/search'
      },

      // Emprendedores
      entrepreneurs: {
        list: '/entrepreneurs',
        create: '/entrepreneurs',
        profile: (id) => `/entrepreneurs/${id}`,
        projects: (id) => `/entrepreneurs/${id}/projects`,
        mentorship: (id) => `/entrepreneurs/${id}/mentorship`,
        progress: (id) => `/entrepreneurs/${id}/progress`
      },

      // Aliados/Mentores
      allies: {
        list: '/allies',
        profile: (id) => `/allies/${id}`,
        entrepreneurs: (id) => `/allies/${id}/entrepreneurs`,
        sessions: (id) => `/allies/${id}/sessions`,
        hours: (id) => `/allies/${id}/hours`,
        reports: (id) => `/allies/${id}/reports`
      },

      // Clientes/Stakeholders
      clients: {
        dashboard: '/clients/dashboard',
        directory: '/clients/directory',
        impact: '/clients/impact',
        reports: '/clients/reports',
        analytics: '/clients/analytics'
      },

      // Administración
      admin: {
        dashboard: '/admin/dashboard',
        users: '/admin/users',
        entrepreneurs: '/admin/entrepreneurs',
        allies: '/admin/allies',
        organizations: '/admin/organizations',
        programs: '/admin/programs',
        analytics: '/admin/analytics',
        settings: '/admin/settings'
      },

      // Proyectos
      projects: {
        list: '/projects',
        create: '/projects',
        details: (id) => `/projects/${id}`,
        update: (id) => `/projects/${id}`,
        delete: (id) => `/projects/${id}`,
        documents: (id) => `/projects/${id}/documents`,
        tasks: (id) => `/projects/${id}/tasks`
      },

      // Mentoría
      mentorship: {
        sessions: '/mentorship/sessions',
        schedule: '/mentorship/schedule',
        feedback: '/mentorship/feedback',
        resources: '/mentorship/resources'
      },

      // Reuniones
      meetings: {
        list: '/meetings',
        create: '/meetings',
        details: (id) => `/meetings/${id}`,
        join: (id) => `/meetings/${id}/join`,
        recording: (id) => `/meetings/${id}/recording`
      },

      // Mensajería
      messages: {
        conversations: '/messages/conversations',
        send: '/messages/send',
        thread: (id) => `/messages/conversations/${id}`,
        read: (id) => `/messages/${id}/read`
      },

      // Documentos
      documents: {
        list: '/documents',
        upload: '/documents/upload',
        download: (id) => `/documents/${id}/download`,
        share: (id) => `/documents/${id}/share`,
        versions: (id) => `/documents/${id}/versions`
      },

      // Analytics
      analytics: {
        overview: '/analytics/overview',
        users: '/analytics/users',
        projects: '/analytics/projects',
        engagement: '/analytics/engagement',
        export: '/analytics/export'
      },

      // Notificaciones
      notifications: {
        list: '/notifications',
        markRead: (id) => `/notifications/${id}/read`,
        markAllRead: '/notifications/read-all',
        settings: '/notifications/settings'
      },

      // Webhooks
      webhooks: {
        list: '/webhooks',
        create: '/webhooks',
        test: (id) => `/webhooks/${id}/test`,
        logs: (id) => `/webhooks/${id}/logs`
      }
    }
  }

  /**
     * Inicializa el sistema de caché
     */
  initializeCache () {
    this.cache = new Map()
    this.cacheTimestamps = new Map()

    // Limpiar caché periódicamente
    setInterval(() => {
      this.cleanExpiredCache()
    }, 60000) // Cada minuto
  }

  /**
     * Inicializa interceptors de request y response
     */
  initializeInterceptors () {
    this.requestInterceptors = []
    this.responseInterceptors = []
    this.errorInterceptors = []

    // Interceptor de autenticación por defecto
    this.addRequestInterceptor((config) => {
      const token = this.getAuthToken()
      if (token) {
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    // Interceptor de response por defecto
    this.addResponseInterceptor(
      (response) => response,
      (error) => this.handleResponseError(error)
    )
  }

  /**
     * Inicializa event listeners
     */
  initializeEventListeners () {
    // Detectar cambios de conectividad
    window.addEventListener('online', () => {
      this.isOnline = true
      this.processOfflineQueue()
      this.dispatchEvent('api:online')
    })

    window.addEventListener('offline', () => {
      this.isOnline = false
      this.dispatchEvent('api:offline')
    })

    // Limpiar antes de descargar la página
    window.addEventListener('beforeunload', () => {
      this.cleanup()
    })
  }

  /**
     * Inicializa WebSocket para notificaciones en tiempo real
     */
  initializeWebSocket () {
    if (typeof window.io !== 'undefined') {
      this.socket = window.io('/api-events', {
        autoConnect: false,
        transports: ['websocket', 'polling']
      })

      this.socket.on('connect', () => {
        // // console.log('API WebSocket connected')
        this.dispatchEvent('api:websocket:connected')
      })

      this.socket.on('disconnect', () => {
        // // console.log('API WebSocket disconnected')
        this.dispatchEvent('api:websocket:disconnected')
      })

      this.socket.on('api:invalidate-cache', (data) => {
        this.invalidateCache(data.pattern)
      })
    }
  }

  /**
     * Realiza petición HTTP
     */
  async request (config) {
    // Normalizar configuración
    config = this.normalizeConfig(config)

    // Aplicar interceptors de request
    for (const interceptor of this.requestInterceptors) {
      config = await interceptor(config)
    }

    // Verificar rate limiting
    if (this.config.rateLimit.enabled && !this.checkRateLimit(config)) {
      throw new APIError('Rate limit exceeded', 429)
    }

    // Verificar caché
    const cacheKey = this.generateCacheKey(config)
    if (config.method === 'GET' && this.config.cache.enabled) {
      const cachedResponse = this.getFromCache(cacheKey)
      if (cachedResponse) {
        return cachedResponse
      }
    }

    // Verificar conectividad
    if (!this.isOnline && this.config.offline.enabled) {
      return this.handleOfflineRequest(config)
    }

    // Realizar petición con reintentos
    return this.executeRequestWithRetry(config, cacheKey)
  }

  /**
     * Normaliza la configuración de la petición
     */
  normalizeConfig (config) {
    if (typeof config === 'string') {
      config = { url: config }
    }

    return {
      method: 'GET',
      timeout: this.config.timeout,
      ...config,
      url: this.resolveURL(config.url),
      headers: {
        ...this.config.defaultHeaders,
        ...config.headers
      }
    }
  }

  /**
     * Resuelve URL absoluta
     */
  resolveURL (url) {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url
    }

    return this.config.baseURL + (url.startsWith('/') ? url : '/' + url)
  }

  /**
     * Ejecuta petición con sistema de reintentos
     */
  async executeRequestWithRetry (config, cacheKey, attempt = 1) {
    const requestId = this.generateRequestId()

    try {
      // Registrar petición activa
      this.activeRequests.set(requestId, {
        config,
        startTime: Date.now(),
        attempt
      })

      // Realizar petición
      const response = await this.executeRequest(config)

      // Procesar response con interceptors
      const processedResponse = await this.processResponse(response)

      // Guardar en caché si es GET
      if (config.method === 'GET' && this.config.cache.enabled) {
        this.setCache(cacheKey, processedResponse)
      }

      // Limpiar petición activa
      this.activeRequests.delete(requestId)

      return processedResponse
    } catch (error) {
      // Limpiar petición activa
      this.activeRequests.delete(requestId)

      // Verificar si es reintentable
      if (this.shouldRetry(error, attempt)) {
        const delay = this.calculateRetryDelay(attempt)
        await this.sleep(delay)
        return this.executeRequestWithRetry(config, cacheKey, attempt + 1)
      }

      throw error
    }
  }

  /**
     * Ejecuta la petición HTTP real
     */
  async executeRequest (config) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), config.timeout)

    try {
      const fetchConfig = {
        method: config.method,
        headers: config.headers,
        signal: controller.signal,
        credentials: 'same-origin'
      }

      // Agregar body si no es GET/HEAD
      if (config.data && !['GET', 'HEAD'].includes(config.method)) {
        if (config.data instanceof FormData) {
          fetchConfig.body = config.data
          // Remover Content-Type para FormData (se establece automáticamente)
          delete fetchConfig.headers['Content-Type']
        } else if (typeof config.data === 'object') {
          fetchConfig.body = JSON.stringify(config.data)
        } else {
          fetchConfig.body = config.data
        }
      }

      const response = await fetch(config.url, fetchConfig)
      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new APIError(
                    `HTTP ${response.status}: ${response.statusText}`,
                    response.status,
                    response
        )
      }

      return response
    } catch (error) {
      clearTimeout(timeoutId)

      if (error.name === 'AbortError') {
        throw new APIError('Request timeout', 408)
      }

      throw error
    }
  }

  /**
     * Procesa la respuesta
     */
  async processResponse (response) {
    const contentType = response.headers.get('content-type') || ''
    let data

    // Parsear según content-type
    if (contentType.includes('application/json')) {
      data = await response.json()
    } else if (contentType.includes('text/')) {
      data = await response.text()
    } else if (contentType.includes('application/octet-stream') ||
                   contentType.includes('application/pdf')) {
      data = await response.blob()
    } else {
      data = await response.text()
    }

    const processedResponse = {
      data,
      status: response.status,
      statusText: response.statusText,
      headers: this.parseHeaders(response.headers),
      config: response.config,
      request: response
    }

    // Aplicar interceptors de response
    for (const interceptor of this.responseInterceptors) {
      if (interceptor.fulfilled) {
        processedResponse.data = await interceptor.fulfilled(processedResponse)
      }
    }

    return processedResponse
  }

  /**
     * Maneja errores de respuesta
     */
  async handleResponseError (error) {
    // Aplicar interceptors de error
    for (const interceptor of this.errorInterceptors) {
      error = await interceptor(error)
    }

    // Manejo específico de errores de autenticación
    if (error.status === 401 && this.config.auth.autoRefresh) {
      try {
        await this.refreshAuthToken()
        // Reintentar la petición original
        return this.request(error.config)
      } catch (refreshError) {
        this.dispatchEvent('api:auth:failed', { error: refreshError })
        throw refreshError
      }
    }

    // Log del error
    this.logError(error)

    throw error
  }

  /**
     * Métodos HTTP de conveniencia
     */
  async get (url, config = {}) {
    return this.request({ ...config, url, method: 'GET' })
  }

  async post (url, data, config = {}) {
    return this.request({ ...config, url, method: 'POST', data })
  }

  async put (url, data, config = {}) {
    return this.request({ ...config, url, method: 'PUT', data })
  }

  async patch (url, data, config = {}) {
    return this.request({ ...config, url, method: 'PATCH', data })
  }

  async delete (url, config = {}) {
    return this.request({ ...config, url, method: 'DELETE' })
  }

  /**
     * Upload de archivos
     */
  async upload (url, file, options = {}) {
    const formData = new FormData()

    if (file instanceof File || file instanceof Blob) {
      formData.append(options.fieldName || 'file', file)
    } else if (Array.isArray(file)) {
      file.forEach((f, index) => {
        formData.append(`${options.fieldName || 'file'}[${index}]`, f)
      })
    }

    // Agregar campos adicionales
    if (options.fields) {
      Object.entries(options.fields).forEach(([key, value]) => {
        formData.append(key, value)
      })
    }

    const config = {
      ...options,
      url,
      method: 'POST',
      data: formData,
      timeout: options.timeout || 300000, // 5 minutos para uploads
      onUploadProgress: options.onProgress
    }

    return this.request(config)
  }

  /**
     * Download de archivos
     */
  async download (url, filename, options = {}) {
    const response = await this.request({
      ...options,
      url,
      method: 'GET'
    })

    const blob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data])

    // Crear enlace de descarga
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)

    return response
  }

  /**
     * Peticiones en lote
     */
  async batch (requests) {
    const promises = requests.map(request =>
      this.request(request).catch(error => ({ error, request }))
    )

    const results = await Promise.all(promises)

    return {
      success: results.filter(r => !r.error),
      errors: results.filter(r => r.error),
      total: results.length
    }
  }

  /**
     * Petición con paginación automática
     */
  async paginate (url, options = {}) {
    const {
      pageParam = 'page',
      limitParam = 'limit',
      limit = 20,
      maxPages = 10,
      processor = null
    } = options

    const results = []
    let page = 1
    let hasMore = true

    while (hasMore && page <= maxPages) {
      const response = await this.get(url, {
        params: {
          [pageParam]: page,
          [limitParam]: limit,
          ...options.params
        }
      })

      const data = processor ? processor(response.data) : response.data
      results.push(...(Array.isArray(data) ? data : data.results || []))

      // Verificar si hay más páginas
      hasMore = data.hasMore ||
                     (data.results && data.results.length === limit) ||
                     (Array.isArray(data) && data.length === limit)

      page++
    }

    return results
  }

  /**
     * Gestión de autenticación
     */
  getAuthToken () {
    return localStorage.getItem(this.config.auth.tokenKey) ||
               sessionStorage.getItem(this.config.auth.tokenKey)
  }

  setAuthToken (token, remember = true) {
    const storage = remember ? localStorage : sessionStorage
    storage.setItem(this.config.auth.tokenKey, token)
    this.dispatchEvent('api:auth:token-set', { token })
  }

  removeAuthToken () {
    localStorage.removeItem(this.config.auth.tokenKey)
    sessionStorage.removeItem(this.config.auth.tokenKey)
    localStorage.removeItem(this.config.auth.refreshTokenKey)
    sessionStorage.removeItem(this.config.auth.refreshTokenKey)
    this.dispatchEvent('api:auth:token-removed')
  }

  async refreshAuthToken () {
    const refreshToken = localStorage.getItem(this.config.auth.refreshTokenKey) ||
                           sessionStorage.getItem(this.config.auth.refreshTokenKey)

    if (!refreshToken) {
      throw new APIError('No refresh token available', 401)
    }

    const response = await this.post(this.endpoints.auth.refresh, {
      refresh_token: refreshToken
    })

    this.setAuthToken(response.data.access_token)

    if (response.data.refresh_token) {
      const storage = localStorage.getItem(this.config.auth.refreshTokenKey)
        ? localStorage
        : sessionStorage
      storage.setItem(this.config.auth.refreshTokenKey, response.data.refresh_token)
    }

    return response.data
  }

  /**
     * Gestión de caché
     */
  generateCacheKey (config) {
    const key = `${config.method}:${config.url}`
    const params = config.params ? JSON.stringify(config.params) : ''
    return `${key}${params}`
  }

  getFromCache (key) {
    if (!this.cache.has(key)) return null

    const timestamp = this.cacheTimestamps.get(key)
    if (Date.now() - timestamp > this.config.cache.ttl) {
      this.cache.delete(key)
      this.cacheTimestamps.delete(key)
      return null
    }

    return this.cache.get(key)
  }

  setCache (key, data) {
    // Verificar límite de tamaño
    if (this.cache.size >= this.config.cache.maxSize) {
      const oldestKey = this.cache.keys().next().value
      this.cache.delete(oldestKey)
      this.cacheTimestamps.delete(oldestKey)
    }

    this.cache.set(key, data)
    this.cacheTimestamps.set(key, Date.now())
  }

  invalidateCache (pattern) {
    if (typeof pattern === 'string') {
      // Invalidar por patrón
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key)
          this.cacheTimestamps.delete(key)
        }
      }
    } else if (pattern instanceof RegExp) {
      // Invalidar por regex
      for (const key of this.cache.keys()) {
        if (pattern.test(key)) {
          this.cache.delete(key)
          this.cacheTimestamps.delete(key)
        }
      }
    }
  }

  clearCache () {
    this.cache.clear()
    this.cacheTimestamps.clear()
  }

  cleanExpiredCache () {
    const now = Date.now()
    for (const [key, timestamp] of this.cacheTimestamps) {
      if (now - timestamp > this.config.cache.ttl) {
        this.cache.delete(key)
        this.cacheTimestamps.delete(key)
      }
    }
  }

  /**
     * Manejo offline
     */
  handleOfflineRequest (config) {
    if (['GET'].includes(config.method)) {
      // Para GET, intentar caché
      const cacheKey = this.generateCacheKey(config)
      const cachedResponse = this.getFromCache(cacheKey)
      if (cachedResponse) {
        return Promise.resolve(cachedResponse)
      }
    }

    if (this.config.offline.queueRequests) {
      return this.queueOfflineRequest(config)
    }

    throw new APIError('Network unavailable', 0)
  }

  queueOfflineRequest (config) {
    return new Promise((resolve, reject) => {
      if (this.requestQueue.length >= this.config.offline.maxQueueSize) {
        reject(new APIError('Offline queue full', 507))
        return
      }

      this.requestQueue.push({
        config,
        resolve,
        reject,
        timestamp: Date.now()
      })
    })
  }

  async processOfflineQueue () {
    const queue = [...this.requestQueue]
    this.requestQueue = []

    for (const item of queue) {
      try {
        const response = await this.request(item.config)
        item.resolve(response)
      } catch (error) {
        item.reject(error)
      }
    }
  }

  /**
     * Rate limiting
     */
  checkRateLimit (config) {
    if (!this.config.rateLimit.enabled) return true

    const now = Date.now()
    const windowStart = now - this.config.rateLimit.windowMs
    const key = this.getRateLimitKey(config)

    // Limpiar registros antiguos
    const requests = this.rateLimitCounter.get(key) || []
    const validRequests = requests.filter(time => time > windowStart)

    if (validRequests.length >= this.config.rateLimit.maxRequests) {
      return false
    }

    validRequests.push(now)
    this.rateLimitCounter.set(key, validRequests)

    return true
  }

  getRateLimitKey (config) {
    // Agrupar por endpoint base
    const url = new URL(config.url, window.location.origin)
    return url.pathname.split('/').slice(0, 4).join('/')
  }

  /**
     * Sistema de reintentos
     */
  shouldRetry (error, attempt) {
    if (attempt >= this.config.retries) return false

    // Reintentar en errores de red o servidor
    if (error.status === 0 || error.status >= 500) return true

    // Reintentar en rate limiting
    if (error.status === 429) return true

    return false
  }

  calculateRetryDelay (attempt) {
    // Backoff exponencial con jitter
    const baseDelay = this.config.retryDelay
    const exponentialDelay = baseDelay * Math.pow(2, attempt - 1)
    const jitter = Math.random() * 1000

    return Math.min(exponentialDelay + jitter, 30000) // Max 30 segundos
  }

  /**
     * Interceptors
     */
  addRequestInterceptor (interceptor) {
    this.requestInterceptors.push(interceptor)
    return this.requestInterceptors.length - 1
  }

  addResponseInterceptor (onFulfilled, onRejected) {
    this.responseInterceptors.push({ fulfilled: onFulfilled, rejected: onRejected })
    return this.responseInterceptors.length - 1
  }

  addErrorInterceptor (interceptor) {
    this.errorInterceptors.push(interceptor)
    return this.errorInterceptors.length - 1
  }

  removeInterceptor (type, index) {
    const interceptors = this[`${type}Interceptors`]
    if (interceptors && interceptors[index]) {
      interceptors.splice(index, 1)
    }
  }

  /**
     * Utilidades
     */
  generateRequestId () {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  parseHeaders (headers) {
    const parsed = {}
    for (const [key, value] of headers.entries()) {
      parsed[key] = value
    }
    return parsed
  }

  sleep (ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  logError (error) {
    console.group('🚨 API Error')
    // // console.error('Message:', error.message)
    // // console.error('Status:', error.status)
    // // console.error('Config:', error.config)
    // // console.error('Stack:', error.stack)
    console.groupEnd()

    // Enviar a servicio de logging si está configurado
    this.dispatchEvent('api:error', { error })
  }

  dispatchEvent (type, detail = {}) {
    const event = new CustomEvent(type, {
      detail: { ...detail, api: this },
      bubbles: true
    })

    document.dispatchEvent(event)

    // También emitir via WebSocket si está conectado
    if (this.socket && this.socket.connected) {
      this.socket.emit('client-event', { type, detail })
    }
  }

  /**
     * Estadísticas y métricas
     */
  getStats () {
    return {
      activeRequests: this.activeRequests.size,
      cacheSize: this.cache.size,
      queueSize: this.requestQueue.length,
      isOnline: this.isOnline,
      rateLimitCounters: Object.fromEntries(this.rateLimitCounter)
    }
  }

  /**
     * Limpieza y destrucción
     */
  cleanup () {
    // Cancelar peticiones activas
    this.activeRequests.clear()

    // Limpiar timeouts
    clearInterval(this.cacheCleanupInterval)

    // Desconectar WebSocket
    if (this.socket) {
      this.socket.disconnect()
    }

    // Limpiar caché
    this.clearCache()
  }

  destroy () {
    this.cleanup()
    this.dispatchEvent('api:destroyed')
  }
}

/**
 * Clase de error personalizada para la API
 */
class APIError extends Error {
  constructor (message, status = 0, response = null) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.response = response
    this.timestamp = new Date().toISOString()
  }

  get isNetworkError () {
    return this.status === 0
  }

  get isServerError () {
    return this.status >= 500
  }

  get isClientError () {
    return this.status >= 400 && this.status < 500
  }

  get isAuthError () {
    return this.status === 401 || this.status === 403
  }
}

/**
 * Instancia global de la API
 */
const api = new APIClient({
  baseURL: window.APP_CONFIG?.API_BASE_URL || '/api/v1',
  auth: {
    autoRefresh: true,
    tokenKey: 'entrepreneurship_token',
    refreshTokenKey: 'entrepreneurship_refresh_token'
  },
  cache: {
    enabled: true,
    ttl: 300000 // 5 minutos
  },
  offline: {
    enabled: true,
    queueRequests: true
  }
})

/**
 * Servicios específicos del dominio
 */
const AuthService = {
  async login (credentials) {
    const response = await api.post(api.endpoints.auth.login, credentials)
    api.setAuthToken(response.data.access_token, credentials.remember)

    if (response.data.refresh_token) {
      const storage = credentials.remember ? localStorage : sessionStorage
      storage.setItem(api.config.auth.refreshTokenKey, response.data.refresh_token)
    }

    return response.data
  },

  async logout () {
    try {
      await api.post(api.endpoints.auth.logout)
    } finally {
      api.removeAuthToken()
      api.clearCache()
    }
  },

  async register (userData) {
    return api.post(api.endpoints.auth.register, userData)
  },

  async forgotPassword (email) {
    return api.post(api.endpoints.auth.forgotPassword, { email })
  },

  async resetPassword (token, password) {
    return api.post(api.endpoints.auth.resetPassword, { token, password })
  }
}

const UserService = {
  async getProfile () {
    return api.get(api.endpoints.users.profile)
  },

  async updateProfile (data) {
    return api.put(api.endpoints.users.profile, data)
  },

  async uploadAvatar (file) {
    return api.upload(api.endpoints.users.avatar, file)
  },

  async updateStatus (status) {
    return api.patch(api.endpoints.users.status, { status })
  },

  async searchUsers (query, filters = {}) {
    return api.get(api.endpoints.users.search, {
      params: { q: query, ...filters }
    })
  }
}

const ProjectService = {
  async getProjects (filters = {}) {
    return api.get(api.endpoints.projects.list, { params: filters })
  },

  async createProject (projectData) {
    return api.post(api.endpoints.projects.create, projectData)
  },

  async getProject (id) {
    return api.get(api.endpoints.projects.details(id))
  },

  async updateProject (id, data) {
    return api.put(api.endpoints.projects.update(id), data)
  },

  async deleteProject (id) {
    return api.delete(api.endpoints.projects.delete(id))
  },

  async getProjectDocuments (id) {
    return api.get(api.endpoints.projects.documents(id))
  }
}

const MessageService = {
  async getConversations () {
    return api.get(api.endpoints.messages.conversations)
  },

  async sendMessage (data) {
    return api.post(api.endpoints.messages.send, data)
  },

  async getThread (conversationId) {
    return api.get(api.endpoints.messages.thread(conversationId))
  },

  async markAsRead (messageId) {
    return api.patch(api.endpoints.messages.read(messageId))
  }
}

const NotificationService = {
  async getNotifications (params = {}) {
    return api.get(api.endpoints.notifications.list, { params })
  },

  async markAsRead (id) {
    return api.patch(api.endpoints.notifications.markRead(id))
  },

  async markAllAsRead () {
    return api.post(api.endpoints.notifications.markAllRead)
  },

  async updateSettings (settings) {
    return api.put(api.endpoints.notifications.settings, settings)
  }
}

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    APIClient,
    APIError,
    api,
    AuthService,
    UserService,
    ProjectService,
    MessageService,
    NotificationService
  }
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.APIClient = APIClient
  window.APIError = APIError
  window.api = api
  window.AuthService = AuthService
  window.UserService = UserService
  window.ProjectService = ProjectService
  window.MessageService = MessageService
  window.NotificationService = NotificationService
}
