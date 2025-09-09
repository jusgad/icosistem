/**
 * AnalyticsService.js - Servicio para el Seguimiento de Analíticas y Métricas
 * ==========================================================================
 *
 * Maneja el tracking de eventos, interacciones de usuario, métricas de rendimiento
 * y la integración con plataformas de analíticas (si aplica).
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.config, App.services.user, etc.)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que AnalyticsService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class AnalyticsService {
  constructor () {
    this.baseEndpoint = '/api/v1/analytics' // Endpoint para enviar datos de analíticas
    this.trackingEnabled = App.config.ANALYTICS_ENABLED !== false // Habilitado por defecto
    this.queue = [] // Cola para eventos si el envío falla o es en lote
    this.batchSize = App.config.ANALYTICS_BATCH_SIZE || 20
    this.batchInterval = App.config.ANALYTICS_BATCH_INTERVAL || 15000 // 15 segundos
    this.sessionId = this._generateSessionId()
    this.userId = null // Se establecerá al identificar al usuario
    this.userProperties = {} // Propiedades del usuario actual

    if (this.trackingEnabled) {
      this._initBatchProcessor()
      this._trackInitialPageView()
      this._setupPageLeaveTracking()
    }
  }

  /**
     * Genera un ID de sesión único.
     * @private
     */
  _generateSessionId () {
    return `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
  }

  /**
     * Inicializa el procesador de lotes para enviar eventos.
     * @private
     */
  _initBatchProcessor () {
    setInterval(() => {
      this.flushQueue()
    }, this.batchInterval)
  }

  /**
     * Rastrea la vista de página inicial.
     * @private
     */
  _trackInitialPageView () {
    this.trackPageView(window.location.pathname, document.title)
  }

  /**
     * Configura el rastreo de eventos al salir de la página.
     * @private
     */
  _setupPageLeaveTracking () {
    window.addEventListener('beforeunload', () => {
      if (this.queue.length > 0) {
        // Intentar enviar la cola de forma síncrona (puede no funcionar en todos los navegadores)
        this.flushQueue(true)
      }
    })
  }

  /**
     * Identifica al usuario actual para el seguimiento.
     * @param {string|number} userId - ID del usuario.
     * @param {Object} properties - Propiedades del usuario (e.g., rol, plan).
     */
  identifyUser (userId, properties = {}) {
    if (!this.trackingEnabled) return

    this.userId = userId
    this.userProperties = { ...this.userProperties, ...properties }

    this.trackEvent('user_identified', {
      userId: this.userId,
      ...this.userProperties
    })

    // Si hay un servicio de usuario, obtener más propiedades
    if (App.services.user && App.services.user.currentUser) {
      const user = App.services.user.currentUser
      this.setUserProperties({
        email: user.email,
        userType: user.user_type,
        organizationId: user.organization_id
      })
    }
  }

  /**
     * Establece propiedades del usuario para el seguimiento.
     * @param {Object} properties - Propiedades a establecer o actualizar.
     */
  setUserProperties (properties = {}) {
    if (!this.trackingEnabled) return
    this.userProperties = { ...this.userProperties, ...properties }
    // Podrías enviar un evento 'user_properties_updated' si tu backend lo soporta
  }

  /**
     * Rastrea un evento personalizado.
     * @param {string} eventName - Nombre del evento (e.g., 'project_created', 'mentor_assigned').
     * @param {Object} properties - Propiedades del evento.
     * @param {Function} [callback] - Callback opcional después de enviar.
     */
  async trackEvent (eventName, properties = {}, callback) {
    if (!this.trackingEnabled) {
      if (callback) callback(null, { status: 'tracking_disabled' })
      return
    }

    const eventData = {
      event: eventName,
      properties: {
        ...this._getDefaultProperties(),
        ...properties
      },
      timestamp: new Date().toISOString()
    }

    this.queue.push(eventData)

    if (this.queue.length >= this.batchSize) {
      await this.flushQueue()
    }

    if (callback) callback(null, { status: 'queued', event: eventData })
  }

  /**
     * Rastrea una vista de página.
     * @param {string} path - Ruta de la página (e.g., '/dashboard').
     * @param {string} title - Título de la página.
     */
  trackPageView (path, title) {
    if (!this.trackingEnabled) return

    this.trackEvent('page_viewed', {
      path,
      title,
      url: window.location.href,
      referrer: document.referrer
    })
  }

  /**
     * Rastrea una acción específica del usuario.
     * @param {string} actionName - Nombre de la acción (e.g., 'clicked_create_project_button').
     * @param {string} category - Categoría de la acción (e.g., 'projects', 'navigation').
     * @param {string} [label] - Etiqueta opcional para la acción.
     * @param {number} [value] - Valor numérico opcional asociado.
     */
  trackUserAction (actionName, category, label, value) {
    if (!this.trackingEnabled) return

    const properties = { category }
    if (label) properties.label = label
    if (value !== undefined) properties.value = value

    this.trackEvent(`user_action_${actionName}`, properties)
  }

  /**
     * Rastrea un error ocurrido en el frontend.
     * @param {Error} error - El objeto Error.
     * @param {Object} [extraInfo] - Información adicional sobre el error.
     */
  trackError (error, extraInfo = {}) {
    if (!this.trackingEnabled) return

    this.trackEvent('frontend_error', {
      errorMessage: error.message,
      errorStack: error.stack,
      component: extraInfo.component || 'unknown',
      ...extraInfo
    })
  }

  /**
     * Envía la cola de eventos al backend.
     * @param {boolean} synchronous - Si el envío debe ser síncrono (para beforeunload).
     */
  async flushQueue (synchronous = false) {
    if (!this.trackingEnabled || this.queue.length === 0) {
      return
    }

    const eventsToSend = [...this.queue]
    this.queue = []

    try {
      if (synchronous && navigator.sendBeacon) {
        // Usar sendBeacon para envíos síncronos fiables al salir de la página
        const data = new Blob([JSON.stringify({ events: eventsToSend })], { type: 'application/json' })
        navigator.sendBeacon(`${App.config.API_BASE_URL || ''}${this.baseEndpoint}/batch`, data)
      } else {
        // Envío asíncrono normal
        await App.http.post(`${this.baseEndpoint}/batch`, { events: eventsToSend })
      }
    } catch (error) {
      // console.warn('AnalyticsService: Error enviando eventos en lote. Re-encolando.', error)
      // Re-encolar eventos si falla el envío (con límite para evitar bucles infinitos)
      if (eventsToSend.length < this.batchSize * 5) { // Evitar re-encolar demasiado
        this.queue.unshift(...eventsToSend)
      }
    }
  }

  /**
     * Obtiene propiedades por defecto para cada evento.
     * @private
     */
  _getDefaultProperties () {
    const defaultProps = {
      sessionId: this.sessionId,
      timestamp_client: Date.now(),
      url: window.location.href,
      path: window.location.pathname,
      screenWidth: window.screen.width,
      screenHeight: window.screen.height,
      language: navigator.language,
      userAgent: navigator.userAgent,
      platform: App.platform || 'web' // Asume que App.platform está definido en main.js
    }

    if (this.userId) {
      defaultProps.userId = this.userId
    }
    if (Object.keys(this.userProperties).length > 0) {
      defaultProps.userProperties = this.userProperties
    }

    return defaultProps
  }

  /**
     * Obtiene datos de analíticas del backend.
     * @param {string} reportName - Nombre del reporte o tipo de datos.
     * @param {Object} params - Parámetros para la consulta (rango de fechas, filtros, etc.).
     * @return {Promise<Object|null>}
     */
  async getAnalyticsData (reportName, params = {}) {
    if (!this.trackingEnabled) { // O un flag diferente para solo lectura de analíticas
      // console.warn('AnalyticsService: El seguimiento está deshabilitado, no se pueden obtener datos.')
      return null
    }
    try {
      const queryString = new URLSearchParams(params).toString()
      return await App.http.get(`${this.baseEndpoint}/${reportName}?${queryString}`)
    } catch (error) {
      // // console.error(`AnalyticsService: Error obteniendo datos para ${reportName}:`, error)
      App.notifications.error('No se pudieron cargar los datos de analíticas.')
      return null
    }
  }

  /**
     * Obtiene un resumen del dashboard de analíticas.
     * @param {Object} filters - Filtros como rango de fechas.
     * @return {Promise<Object|null>}
     */
  async getDashboardSummary (filters = {}) {
    return this.getAnalyticsData('dashboard/summary', filters)
  }

  /**
     * Obtiene la actividad reciente de usuarios.
     * @param {Object} filters - Filtros como límite, tipo de usuario.
     * @return {Promise<Object|null>}
     */
  async getUserActivity (filters = {}) {
    return this.getAnalyticsData('activity/users', filters)
  }

  /**
     * Obtiene el uso de características (features).
     * @param {Object} filters - Filtros como nombre de feature, rango de fechas.
     * @return {Promise<Object|null>}
     */
  async getFeatureUsage (filters = {}) {
    return this.getAnalyticsData('usage/features', filters)
  }

  /**
     * Obtiene tasas de conversión para un embudo específico.
     * @param {string} funnelName - Nombre del embudo.
     * @param {Object} filters - Filtros.
     * @return {Promise<Object|null>}
     */
  async getConversionRates (funnelName, filters = {}) {
    return this.getAnalyticsData(`conversion/${funnelName}`, filters)
  }
}

// Registrar el servicio en la instancia global de la App
App.services.analytics = new AnalyticsService()
