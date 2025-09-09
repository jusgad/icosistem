/**
 * Events Utilities para Ecosistema de Emprendimiento
 * Sistema completo de manejo de eventos con soporte para tiempo real, analytics y cross-tab
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

/**
 * EventEmitter personalizado con funcionalidades avanzadas
 */
class EventEmitter {
  constructor (options = {}) {
    this.events = new Map()
    this.onceEvents = new Map()
    this.maxListeners = options.maxListeners || 100
    this.enableLogging = options.enableLogging || false
    this.enableMetrics = options.enableMetrics || false
    this.metrics = new Map()
    this.middleware = []

    // Eventos del sistema
    this.systemEvents = {
      error: 'system:error',
      warning: 'system:warning',
      maxListeners: 'system:max-listeners'
    }
  }

  /**
     * Registra un listener para un evento
     */
  on (event, listener, options = {}) {
    if (typeof listener !== 'function') {
      throw new TypeError('Listener must be a function')
    }

    if (!this.events.has(event)) {
      this.events.set(event, [])
    }

    const listeners = this.events.get(event)

    // Verificar límite de listeners
    if (listeners.length >= this.maxListeners) {
      this.emit(this.systemEvents.maxListeners, { event, count: listeners.length })
      if (options.strict !== false) {
        throw new Error(`Too many listeners for event: ${event}`)
      }
    }

    const listenerObject = {
      fn: listener,
      context: options.context || null,
      priority: options.priority || 0,
      tags: options.tags || [],
      once: false,
      id: this.generateListenerId()
    }

    // Insertar por prioridad
    const insertIndex = listeners.findIndex(l => l.priority < listenerObject.priority)
    if (insertIndex >= 0) {
      listeners.splice(insertIndex, 0, listenerObject)
    } else {
      listeners.push(listenerObject)
    }

    this.log(`Registered listener for event: ${event}`)

    return listenerObject.id
  }

  /**
     * Registra un listener que se ejecuta solo una vez
     */
  once (event, listener, options = {}) {
    const listenerId = this.on(event, listener, options)

    if (!this.onceEvents.has(event)) {
      this.onceEvents.set(event, new Set())
    }

    this.onceEvents.get(event).add(listenerId)

    return listenerId
  }

  /**
     * Elimina listener(s) de un evento
     */
  off (event, listener) {
    if (!this.events.has(event)) return this

    const listeners = this.events.get(event)

    if (typeof listener === 'string') {
      // Remover por ID
      const index = listeners.findIndex(l => l.id === listener)
      if (index >= 0) {
        listeners.splice(index, 1)
        this.cleanupOnceEvent(event, listener)
      }
    } else if (typeof listener === 'function') {
      // Remover por función
      const index = listeners.findIndex(l => l.fn === listener)
      if (index >= 0) {
        const removedListener = listeners.splice(index, 1)[0]
        this.cleanupOnceEvent(event, removedListener.id)
      }
    } else {
      // Remover todos los listeners del evento
      listeners.length = 0
      this.onceEvents.delete(event)
    }

    // Limpiar evento si no hay listeners
    if (listeners.length === 0) {
      this.events.delete(event)
    }

    return this
  }

  /**
     * Emite un evento
     */
  emit (event, ...args) {
    this.updateMetrics(event)

    if (!this.events.has(event)) {
      this.log(`No listeners for event: ${event}`)
      return false
    }

    const listeners = this.events.get(event).slice() // Copia para evitar modificaciones durante iteración
    const eventData = {
      type: event,
      timestamp: Date.now(),
      args,
      defaultPrevented: false,
      stopPropagation: false
    }

    // Aplicar middleware
    for (const middleware of this.middleware) {
      try {
        const result = middleware(eventData)
        if (result === false) {
          this.log(`Event blocked by middleware: ${event}`)
          return false
        }
      } catch (error) {
        this.emit(this.systemEvents.error, { error, event, phase: 'middleware' })
      }
    }

    let hasListeners = false

    for (const listenerObj of listeners) {
      if (eventData.stopPropagation) break

      try {
        hasListeners = true

        // Ejecutar listener
        if (listenerObj.context) {
          listenerObj.fn.call(listenerObj.context, eventData, ...args)
        } else {
          listenerObj.fn(eventData, ...args)
        }

        // Remover si es 'once'
        if (this.onceEvents.has(event) && this.onceEvents.get(event).has(listenerObj.id)) {
          this.off(event, listenerObj.id)
        }
      } catch (error) {
        this.emit(this.systemEvents.error, { error, event, listener: listenerObj.id })
      }
    }

    this.log(`Emitted event: ${event} with ${listeners.length} listeners`)
    return hasListeners
  }

  /**
     * Registra middleware para procesamiento de eventos
     */
  use (middleware) {
    if (typeof middleware !== 'function') {
      throw new TypeError('Middleware must be a function')
    }

    this.middleware.push(middleware)
    return this
  }

  /**
     * Obtiene listeners de un evento
     */
  listeners (event) {
    if (!this.events.has(event)) return []
    return this.events.get(event).map(l => l.fn)
  }

  /**
     * Cuenta listeners de un evento
     */
  listenerCount (event) {
    if (!this.events.has(event)) return 0
    return this.events.get(event).length
  }

  /**
     * Lista todos los eventos registrados
     */
  eventNames () {
    return Array.from(this.events.keys())
  }

  /**
     * Limpia todos los eventos
     */
  removeAllListeners (event) {
    if (event) {
      this.events.delete(event)
      this.onceEvents.delete(event)
    } else {
      this.events.clear()
      this.onceEvents.clear()
    }

    return this
  }

  /**
     * Clona el EventEmitter
     */
  clone () {
    const cloned = new EventEmitter({
      maxListeners: this.maxListeners,
      enableLogging: this.enableLogging,
      enableMetrics: this.enableMetrics
    })

    // Copiar eventos
    for (const [event, listeners] of this.events) {
      cloned.events.set(event, listeners.slice())
    }

    return cloned
  }

  /**
     * Utilidades internas
     */
  generateListenerId () {
    return `listener_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  cleanupOnceEvent (event, listenerId) {
    if (this.onceEvents.has(event)) {
      this.onceEvents.get(event).delete(listenerId)
      if (this.onceEvents.get(event).size === 0) {
        this.onceEvents.delete(event)
      }
    }
  }

  updateMetrics (event) {
    if (!this.enableMetrics) return

    if (!this.metrics.has(event)) {
      this.metrics.set(event, { count: 0, lastEmitted: null })
    }

    const metric = this.metrics.get(event)
    metric.count++
    metric.lastEmitted = Date.now()
  }

  getMetrics (event) {
    if (event) {
      return this.metrics.get(event) || { count: 0, lastEmitted: null }
    }
    return Object.fromEntries(this.metrics)
  }

  log (message) {
    if (this.enableLogging) {
      // // console.log(`[EventEmitter] ${message}`)
    }
  }
}

/**
 * Event Bus Global para la aplicación
 */
class EventBus extends EventEmitter {
  constructor () {
    super({
      maxListeners: 500,
      enableLogging: true,
      enableMetrics: true
    })

    this.namespaces = new Map()
    this.eventHistory = []
    this.maxHistorySize = 1000

    // Configurar middleware por defecto
    this.setupDefaultMiddleware()
  }

  /**
     * Crea namespace para eventos
     */
  namespace (name) {
    if (!this.namespaces.has(name)) {
      const ns = new EventEmitter({
        maxListeners: 100,
        enableLogging: this.enableLogging
      })

      // Propagar eventos del namespace al bus principal
      ns.use((eventData) => {
        this.emit(`${name}:${eventData.type}`, ...eventData.args)
        return true
      })

      this.namespaces.set(name, ns)
    }

    return this.namespaces.get(name)
  }

  /**
     * Emite evento con historial
     */
  emit (event, ...args) {
    const result = super.emit(event, ...args)

    // Guardar en historial
    this.eventHistory.push({
      event,
      args,
      timestamp: Date.now(),
      listeners: this.listenerCount(event)
    })

    // Mantener tamaño del historial
    if (this.eventHistory.length > this.maxHistorySize) {
      this.eventHistory.shift()
    }

    return result
  }

  /**
     * Obtiene historial de eventos
     */
  getHistory (filter = {}) {
    let history = this.eventHistory

    if (filter.event) {
      history = history.filter(h => h.event.includes(filter.event))
    }

    if (filter.since) {
      history = history.filter(h => h.timestamp >= filter.since)
    }

    if (filter.limit) {
      history = history.slice(-filter.limit)
    }

    return history
  }

  /**
     * Configura middleware por defecto
     */
  setupDefaultMiddleware () {
    // Middleware de logging
    this.use((eventData) => {
      if (eventData.type.startsWith('system:')) {
        // console.warn(`[System Event] ${eventData.type}:`, eventData.args)
      }
      return true
    })

    // Middleware de rate limiting
    this.use((eventData) => {
      // Implementar rate limiting básico
      return true
    })
  }
}

/**
 * Gestor de eventos del DOM con delegation
 */
class DOMEventManager {
  constructor () {
    this.delegatedEvents = new Map()
    this.directEvents = new Map()
    this.eventBus = new EventBus()

    this.setupEventDelegation()
  }

  /**
     * Registra evento delegado
     */
  delegate (container, selector, event, handler, options = {}) {
    const containerElement = typeof container === 'string'
      ? document.querySelector(container)
      : container

    if (!containerElement) {
      throw new Error('Container not found')
    }

    const delegationKey = `${event}:${selector}`

    if (!this.delegatedEvents.has(containerElement)) {
      this.delegatedEvents.set(containerElement, new Map())
    }

    const containerEvents = this.delegatedEvents.get(containerElement)

    if (!containerEvents.has(delegationKey)) {
      const delegatedHandler = (e) => {
        const target = e.target.closest(selector)
        if (target && containerElement.contains(target)) {
          const eventObj = this.createEventObject(e, target)
          handler.call(target, eventObj)

          // Emitir evento en el bus
          this.eventBus.emit(`dom:${event}`, eventObj)
        }
      }

      containerElement.addEventListener(event, delegatedHandler, options)
      containerEvents.set(delegationKey, {
        handler: delegatedHandler,
        originalHandler: handler,
        options
      })
    }

    return delegationKey
  }

  /**
     * Registra evento directo
     */
  on (element, event, handler, options = {}) {
    const targetElement = typeof element === 'string'
      ? document.querySelector(element)
      : element

    if (!targetElement) {
      throw new Error('Element not found')
    }

    const eventKey = `${event}:${this.generateEventId()}`

    const wrappedHandler = (e) => {
      const eventObj = this.createEventObject(e, targetElement)
      handler.call(targetElement, eventObj)

      // Emitir evento en el bus
      this.eventBus.emit(`dom:${event}`, eventObj)
    }

    targetElement.addEventListener(event, wrappedHandler, options)

    if (!this.directEvents.has(targetElement)) {
      this.directEvents.set(targetElement, new Map())
    }

    this.directEvents.get(targetElement).set(eventKey, {
      handler: wrappedHandler,
      originalHandler: handler,
      options
    })

    return eventKey
  }

  /**
     * Elimina evento delegado
     */
  undelegate (container, delegationKey) {
    const containerElement = typeof container === 'string'
      ? document.querySelector(container)
      : container

    if (!containerElement || !this.delegatedEvents.has(containerElement)) {
      return false
    }

    const containerEvents = this.delegatedEvents.get(containerElement)
    const eventData = containerEvents.get(delegationKey)

    if (eventData) {
      const [event] = delegationKey.split(':')
      containerElement.removeEventListener(event, eventData.handler, eventData.options)
      containerEvents.delete(delegationKey)

      if (containerEvents.size === 0) {
        this.delegatedEvents.delete(containerElement)
      }

      return true
    }

    return false
  }

  /**
     * Elimina evento directo
     */
  off (element, eventKey) {
    const targetElement = typeof element === 'string'
      ? document.querySelector(element)
      : element

    if (!targetElement || !this.directEvents.has(targetElement)) {
      return false
    }

    const elementEvents = this.directEvents.get(targetElement)
    const eventData = elementEvents.get(eventKey)

    if (eventData) {
      const [event] = eventKey.split(':')
      targetElement.removeEventListener(event, eventData.handler, eventData.options)
      elementEvents.delete(eventKey)

      if (elementEvents.size === 0) {
        this.directEvents.delete(targetElement)
      }

      return true
    }

    return false
  }

  /**
     * Configura delegation automática para eventos comunes
     */
  setupEventDelegation () {
    // Clicks en elementos con data-action
    this.delegate(document.body, '[data-action]', 'click', (e) => {
      const action = e.target.getAttribute('data-action')
      this.eventBus.emit(`action:${action}`, {
        element: e.target,
        event: e.originalEvent
      })
    })

    // Envío de formularios
    this.delegate(document.body, 'form[data-form]', 'submit', (e) => {
      e.preventDefault()
      const formName = e.target.getAttribute('data-form')
      const formData = new FormData(e.target)

      this.eventBus.emit(`form:submit:${formName}`, {
        form: e.target,
        data: Object.fromEntries(formData),
        event: e.originalEvent
      })
    })

    // Cambios en inputs
    this.delegate(document.body, 'input[data-track], select[data-track], textarea[data-track]', 'change', (e) => {
      const trackName = e.target.getAttribute('data-track')

      this.eventBus.emit(`input:change:${trackName}`, {
        element: e.target,
        value: e.target.value,
        event: e.originalEvent
      })
    })
  }

  /**
     * Crea objeto de evento normalizado
     */
  createEventObject (originalEvent, target) {
    return {
      originalEvent,
      target,
      type: originalEvent.type,
      timestamp: Date.now(),
      preventDefault: () => originalEvent.preventDefault(),
      stopPropagation: () => originalEvent.stopPropagation(),
      data: this.extractEventData(target)
    }
  }

  /**
     * Extrae datos del elemento
     */
  extractEventData (element) {
    const data = {}

    // Data attributes
    for (const attr of element.attributes) {
      if (attr.name.startsWith('data-')) {
        const key = attr.name.slice(5).replace(/-([a-z])/g, (g) => g[1].toUpperCase())
        data[key] = attr.value
      }
    }

    return data
  }

  generateEventId () {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
     * Limpia todos los eventos
     */
  cleanup () {
    // Limpiar eventos delegados
    for (const [container, events] of this.delegatedEvents) {
      for (const [key, eventData] of events) {
        const [event] = key.split(':')
        container.removeEventListener(event, eventData.handler, eventData.options)
      }
    }

    // Limpiar eventos directos
    for (const [element, events] of this.directEvents) {
      for (const [key, eventData] of events) {
        const [event] = key.split(':')
        element.removeEventListener(event, eventData.handler, eventData.options)
      }
    }

    this.delegatedEvents.clear()
    this.directEvents.clear()
  }
}

/**
 * Gestor de WebSocket con reconexión automática
 */
class WebSocketManager extends EventEmitter {
  constructor (url, options = {}) {
    super({
      maxListeners: 200,
      enableLogging: true
    })

    this.url = url
    this.options = {
      autoReconnect: true,
      maxReconnectAttempts: 10,
      reconnectInterval: 5000,
      heartbeatInterval: 30000,
      ...options
    }

    this.ws = null
    this.isConnected = false
    this.reconnectAttempts = 0
    this.heartbeatTimer = null
    this.messageQueue = []

    this.connect()
  }

  /**
     * Establece conexión WebSocket
     */
  connect () {
    try {
      this.ws = new WebSocket(this.url)
      this.setupEventListeners()
    } catch (error) {
      this.emit('error', { error, phase: 'connection' })
    }
  }

  /**
     * Configura listeners del WebSocket
     */
  setupEventListeners () {
    this.ws.onopen = () => {
      this.isConnected = true
      this.reconnectAttempts = 0
      this.emit('connected')

      // Procesar cola de mensajes
      this.processMessageQueue()

      // Iniciar heartbeat
      this.startHeartbeat()

      this.log('WebSocket connected')
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.handleMessage(data)
      } catch (error) {
        this.emit('error', { error, phase: 'message-parsing', data: event.data })
      }
    }

    this.ws.onclose = (event) => {
      this.isConnected = false
      this.stopHeartbeat()

      this.emit('disconnected', { code: event.code, reason: event.reason })

      if (this.options.autoReconnect && this.reconnectAttempts < this.options.maxReconnectAttempts) {
        this.scheduleReconnect()
      }

      this.log(`WebSocket disconnected: ${event.code} - ${event.reason}`)
    }

    this.ws.onerror = (error) => {
      this.emit('error', { error, phase: 'websocket' })
    }
  }

  /**
     * Maneja mensajes recibidos
     */
  handleMessage (data) {
    const { type, payload, id } = data

    // Responder a heartbeat
    if (type === 'ping') {
      this.send({ type: 'pong', id })
      return
    }

    // Emitir evento específico del tipo de mensaje
    this.emit(`message:${type}`, payload, id)
    this.emit('message', data)

    this.log(`Received message: ${type}`)
  }

  /**
     * Envía mensaje
     */
  send (data) {
    const message = {
      ...data,
      timestamp: Date.now(),
      id: data.id || this.generateMessageId()
    }

    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
      this.emit('message:sent', message)
    } else {
      // Agregar a cola si no está conectado
      this.messageQueue.push(message)
      this.emit('message:queued', message)
    }

    return message.id
  }

  /**
     * Procesa cola de mensajes
     */
  processMessageQueue () {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()
      this.ws.send(JSON.stringify(message))
      this.emit('message:sent', message)
    }
  }

  /**
     * Programa reconexión
     */
  scheduleReconnect () {
    this.reconnectAttempts++
    const delay = this.options.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1)

    setTimeout(() => {
      this.log(`Attempting reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`)
      this.connect()
    }, delay)
  }

  /**
     * Inicia heartbeat
     */
  startHeartbeat () {
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.send({ type: 'ping' })
      }
    }, this.options.heartbeatInterval)
  }

  /**
     * Detiene heartbeat
     */
  stopHeartbeat () {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
     * Cierra conexión
     */
  close () {
    this.options.autoReconnect = false
    this.stopHeartbeat()

    if (this.ws) {
      this.ws.close()
    }
  }

  generateMessageId () {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Sistema de Analytics y Tracking de Eventos
 */
class EventAnalytics {
  constructor (options = {}) {
    this.options = {
      trackPageViews: true,
      trackClicks: true,
      trackFormSubmissions: true,
      trackCustomEvents: true,
      batchSize: 10,
      batchTimeout: 5000,
      endpoint: '/api/v1/analytics/events',
      ...options
    }

    this.eventQueue = []
    this.batchTimer = null
    this.sessionId = this.generateSessionId()
    this.userId = null

    this.setupTracking()
  }

  /**
     * Configura tracking automático
     */
  setupTracking () {
    if (this.options.trackPageViews) {
      this.trackPageView()

      // Track SPA route changes
      window.addEventListener('popstate', () => this.trackPageView())
    }

    if (this.options.trackClicks) {
      document.addEventListener('click', (e) => this.trackClick(e), true)
    }

    if (this.options.trackFormSubmissions) {
      document.addEventListener('submit', (e) => this.trackFormSubmission(e), true)
    }
  }

  /**
     * Rastrea vista de página
     */
  trackPageView () {
    this.track('page_view', {
      url: window.location.href,
      title: document.title,
      referrer: document.referrer,
      timestamp: Date.now()
    })
  }

  /**
     * Rastrea click
     */
  trackClick (event) {
    const element = event.target
    const data = {
      element_type: element.tagName.toLowerCase(),
      element_id: element.id,
      element_class: element.className,
      element_text: element.textContent?.substring(0, 100),
      page_url: window.location.href,
      timestamp: Date.now()
    }

    // Datos específicos según el tipo de elemento
    if (element.tagName === 'A') {
      data.link_url = element.href
      data.link_text = element.textContent
    } else if (element.tagName === 'BUTTON') {
      data.button_type = element.type
      data.button_text = element.textContent
    }

    // Tracking específico del ecosistema
    if (element.hasAttribute('data-track-action')) {
      data.custom_action = element.getAttribute('data-track-action')
    }

    this.track('click', data)
  }

  /**
     * Rastrea envío de formulario
     */
  trackFormSubmission (event) {
    const form = event.target
    const formData = new FormData(form)

    const data = {
      form_id: form.id,
      form_action: form.action,
      form_method: form.method,
      field_count: formData.keys().length,
      page_url: window.location.href,
      timestamp: Date.now()
    }

    // Agregar nombres de campos (sin valores por privacidad)
    data.field_names = Array.from(formData.keys())

    this.track('form_submission', data)
  }

  /**
     * Rastrea evento personalizado
     */
  track (event, properties = {}) {
    const eventData = {
      event,
      properties: {
        ...properties,
        session_id: this.sessionId,
        user_id: this.userId,
        user_agent: navigator.userAgent,
        screen_resolution: `${screen.width}x${screen.height}`,
        viewport_size: `${window.innerWidth}x${window.innerHeight}`,
        timestamp: Date.now()
      }
    }

    this.eventQueue.push(eventData)

    // Enviar batch si alcanza el tamaño límite
    if (this.eventQueue.length >= this.options.batchSize) {
      this.flush()
    } else {
      this.scheduleBatch()
    }
  }

  /**
     * Programa envío de batch
     */
  scheduleBatch () {
    if (this.batchTimer) return

    this.batchTimer = setTimeout(() => {
      this.flush()
    }, this.options.batchTimeout)
  }

  /**
     * Envía eventos al servidor
     */
  async flush () {
    if (this.eventQueue.length === 0) return

    const events = this.eventQueue.splice(0)

    if (this.batchTimer) {
      clearTimeout(this.batchTimer)
      this.batchTimer = null
    }

    try {
      await fetch(this.options.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ events })
      })
    } catch (error) {
      // // console.error('Failed to send analytics events:', error)
      // Reintroducir eventos en caso de error
      this.eventQueue.unshift(...events)
    }
  }

  /**
     * Establece ID de usuario
     */
  setUserId (userId) {
    this.userId = userId
  }

  /**
     * Rastrea evento específico del ecosistema
     */
  trackEcosystemEvent (action, category, data = {}) {
    const ecosystemData = {
      ecosystem_action: action,
      ecosystem_category: category,
      ...data
    }

    this.track('ecosystem_event', ecosystemData)
  }

  generateSessionId () {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Gestor de Cross-Tab Communication
 */
class CrossTabManager extends EventEmitter {
  constructor () {
    super()
    this.channel = new BroadcastChannel('entrepreneurship-ecosystem')
    this.tabId = this.generateTabId()
    this.activeTabs = new Set([this.tabId])

    this.setupChannelListeners()
    this.announcePresence()
  }

  /**
     * Configura listeners del canal
     */
  setupChannelListeners () {
    this.channel.onmessage = (event) => {
      const { type, data, fromTab } = event.data

      // Ignorar mensajes de la misma pestaña
      if (fromTab === this.tabId) return

      this.handleCrossTabMessage(type, data, fromTab)
    }

    // Limpiar al cerrar pestaña
    window.addEventListener('beforeunload', () => {
      this.broadcast('tab_closing', { tabId: this.tabId })
    })
  }

  /**
     * Maneja mensajes entre pestañas
     */
  handleCrossTabMessage (type, data, fromTab) {
    switch (type) {
      case 'tab_announcement':
        this.activeTabs.add(fromTab)
        this.emit('tab_connected', { tabId: fromTab })
        break

      case 'tab_closing':
        this.activeTabs.delete(data.tabId)
        this.emit('tab_disconnected', { tabId: data.tabId })
        break

      case 'user_login':
        this.emit('user_login_other_tab', data)
        // Recargar datos del usuario si es necesario
        window.location.reload()
        break

      case 'user_logout':
        this.emit('user_logout_other_tab', data)
        // Redirigir a login
        window.location.href = '/auth/login'
        break

      case 'notification':
        this.emit('notification_from_tab', data)
        break

      case 'data_update':
        this.emit('data_updated_other_tab', data)
        break

      default:
        this.emit(`cross_tab:${type}`, data, fromTab)
    }
  }

  /**
     * Transmite mensaje a otras pestañas
     */
  broadcast (type, data) {
    this.channel.postMessage({
      type,
      data,
      fromTab: this.tabId,
      timestamp: Date.now()
    })
  }

  /**
     * Anuncia presencia
     */
  announcePresence () {
    this.broadcast('tab_announcement', { tabId: this.tabId })
  }

  /**
     * Obtiene pestañas activas
     */
  getActiveTabs () {
    return Array.from(this.activeTabs)
  }

  generateTabId () {
    return `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
     * Cierra el canal
     */
  close () {
    this.broadcast('tab_closing', { tabId: this.tabId })
    this.channel.close()
  }
}

/**
 * Sistema de Events específicos del Ecosistema
 */
class EcosystemEvents extends EventBus {
  constructor () {
    super()
    this.setupEcosystemEvents()
  }

  /**
     * Configura eventos específicos del ecosistema
     */
  setupEcosystemEvents () {
    // Namespaces por módulo
    this.user = this.namespace('user')
    this.project = this.namespace('project')
    this.mentorship = this.namespace('mentorship')
    this.meeting = this.namespace('meeting')
    this.message = this.namespace('message')
    this.notification = this.namespace('notification')
    this.analytics = this.namespace('analytics')

    this.setupUserEvents()
    this.setupProjectEvents()
    this.setupMentorshipEvents()
    this.setupNotificationEvents()
  }

  /**
     * Eventos de usuario
     */
  setupUserEvents () {
    this.user.on('login', (eventData, userData) => {
      this.emit('ecosystem:user_login', userData)
      this.trackUserAction('login', userData)
    })

    this.user.on('logout', (eventData, userData) => {
      this.emit('ecosystem:user_logout', userData)
      this.trackUserAction('logout', userData)
    })

    this.user.on('profile_updated', (eventData, userData) => {
      this.emit('ecosystem:profile_updated', userData)
      this.trackUserAction('profile_update', userData)
    })

    this.user.on('status_changed', (eventData, statusData) => {
      this.emit('ecosystem:user_status_changed', statusData)
    })
  }

  /**
     * Eventos de proyecto
     */
  setupProjectEvents () {
    this.project.on('created', (eventData, projectData) => {
      this.emit('ecosystem:project_created', projectData)
      this.trackProjectAction('create', projectData)
    })

    this.project.on('updated', (eventData, projectData) => {
      this.emit('ecosystem:project_updated', projectData)
      this.trackProjectAction('update', projectData)
    })

    this.project.on('stage_changed', (eventData, stageData) => {
      this.emit('ecosystem:project_stage_changed', stageData)
      this.trackProjectAction('stage_change', stageData)
    })

    this.project.on('funding_received', (eventData, fundingData) => {
      this.emit('ecosystem:funding_received', fundingData)
      this.trackProjectAction('funding_received', fundingData)
    })
  }

  /**
     * Eventos de mentoría
     */
  setupMentorshipEvents () {
    this.mentorship.on('session_scheduled', (eventData, sessionData) => {
      this.emit('ecosystem:mentorship_scheduled', sessionData)
      this.trackMentorshipAction('schedule', sessionData)
    })

    this.mentorship.on('session_started', (eventData, sessionData) => {
      this.emit('ecosystem:mentorship_started', sessionData)
      this.trackMentorshipAction('start', sessionData)
    })

    this.mentorship.on('session_completed', (eventData, sessionData) => {
      this.emit('ecosystem:mentorship_completed', sessionData)
      this.trackMentorshipAction('complete', sessionData)
    })

    this.mentorship.on('feedback_submitted', (eventData, feedbackData) => {
      this.emit('ecosystem:mentorship_feedback', feedbackData)
      this.trackMentorshipAction('feedback', feedbackData)
    })
  }

  /**
     * Eventos de notificaciones
     */
  setupNotificationEvents () {
    this.notification.on('received', (eventData, notificationData) => {
      this.emit('ecosystem:notification_received', notificationData)
      this.showNotification(notificationData)
    })

    this.notification.on('read', (eventData, notificationData) => {
      this.emit('ecosystem:notification_read', notificationData)
    })
  }

  /**
     * Rastrea acciones de usuario
     */
  trackUserAction (action, data) {
    this.analytics.emit('user_action', {
      action,
      userId: data.id,
      userRole: data.role,
      timestamp: Date.now(),
      data
    })
  }

  /**
     * Rastrea acciones de proyecto
     */
  trackProjectAction (action, data) {
    this.analytics.emit('project_action', {
      action,
      projectId: data.id,
      projectStage: data.stage,
      industry: data.industry,
      timestamp: Date.now(),
      data
    })
  }

  /**
     * Rastrea acciones de mentoría
     */
  trackMentorshipAction (action, data) {
    this.analytics.emit('mentorship_action', {
      action,
      sessionId: data.id,
      mentorId: data.mentorId,
      entrepreneurId: data.entrepreneurId,
      timestamp: Date.now(),
      data
    })
  }

  /**
     * Muestra notificación
     */
  showNotification (data) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(data.title, {
        body: data.message,
        icon: data.icon || '/static/images/logo-small.png',
        badge: '/static/images/badge.png',
        tag: data.id,
        data
      })
    }
  }
}

/**
 * Performance Monitor para eventos
 */
class EventPerformanceMonitor {
  constructor (eventBus) {
    this.eventBus = eventBus
    this.metrics = new Map()
    this.slowEventThreshold = 100 // ms
    this.enableMonitoring = true

    this.setupMonitoring()
  }

  /**
     * Configura monitoreo de performance
     */
  setupMonitoring () {
    // Middleware para medir tiempo de ejecución
    this.eventBus.use((eventData) => {
      if (!this.enableMonitoring) return true

      const startTime = performance.now()

      // Usar setTimeout para medir después de la ejecución
      setTimeout(() => {
        const endTime = performance.now()
        const duration = endTime - startTime

        this.recordMetric(eventData.type, duration)

        if (duration > this.slowEventThreshold) {
          // console.warn(`Slow event detected: ${eventData.type} took ${duration.toFixed(2)}ms`)
        }
      }, 0)

      return true
    })
  }

  /**
     * Registra métrica
     */
  recordMetric (eventType, duration) {
    if (!this.metrics.has(eventType)) {
      this.metrics.set(eventType, {
        count: 0,
        totalTime: 0,
        avgTime: 0,
        maxTime: 0,
        minTime: Infinity
      })
    }

    const metric = this.metrics.get(eventType)
    metric.count++
    metric.totalTime += duration
    metric.avgTime = metric.totalTime / metric.count
    metric.maxTime = Math.max(metric.maxTime, duration)
    metric.minTime = Math.min(metric.minTime, duration)
  }

  /**
     * Obtiene métricas
     */
  getMetrics (eventType) {
    if (eventType) {
      return this.metrics.get(eventType)
    }
    return Object.fromEntries(this.metrics)
  }

  /**
     * Obtiene eventos lentos
     */
  getSlowEvents () {
    const slowEvents = []

    for (const [eventType, metric] of this.metrics) {
      if (metric.avgTime > this.slowEventThreshold) {
        slowEvents.push({
          eventType,
          avgTime: metric.avgTime,
          maxTime: metric.maxTime,
          count: metric.count
        })
      }
    }

    return slowEvents.sort((a, b) => b.avgTime - a.avgTime)
  }

  /**
     * Reinicia métricas
     */
  reset () {
    this.metrics.clear()
  }
}

/**
 * Instancias globales
 */
const eventBus = new EventBus()
const domManager = new DOMEventManager()
const analytics = new EventAnalytics()
const crossTab = new CrossTabManager()
const ecosystemEvents = new EcosystemEvents()
const performanceMonitor = new EventPerformanceMonitor(eventBus)

// Configurar WebSocket si está disponible
let wsManager = null
if (window.WS_URL) {
  wsManager = new WebSocketManager(window.WS_URL)

  // Conectar WebSocket con el bus de eventos
  wsManager.on('message:notification', (data) => {
    ecosystemEvents.notification.emit('received', data)
  })

  wsManager.on('message:user_update', (data) => {
    ecosystemEvents.user.emit('status_changed', data)
  })

  wsManager.on('message:project_update', (data) => {
    ecosystemEvents.project.emit('updated', data)
  })
}

/**
 * API pública de eventos
 */
const Events = {
  // Instancias principales
  bus: eventBus,
  dom: domManager,
  analytics,
  crossTab,
  ecosystem: ecosystemEvents,
  ws: wsManager,
  performance: performanceMonitor,

  // Atajos para uso común
  on: (event, listener, options) => eventBus.on(event, listener, options),
  once: (event, listener, options) => eventBus.once(event, listener, options),
  off: (event, listener) => eventBus.off(event, listener),
  emit: (event, ...args) => eventBus.emit(event, ...args),

  // Utilidades
  track: (event, data) => analytics.track(event, data),
  trackEcosystem: (action, category, data) => analytics.trackEcosystemEvent(action, category, data),

  // Configuración
  setUserId: (userId) => {
    analytics.setUserId(userId)
    ecosystemEvents.emit('user:id_set', { userId })
  },

  // Cleanup
  cleanup: () => {
    domManager.cleanup()
    crossTab.close()
    if (wsManager) wsManager.close()
    analytics.flush()
  },

  // Debug y métricas
  getMetrics: () => ({
    bus: eventBus.getMetrics(),
    performance: performanceMonitor.getMetrics(),
    analytics: analytics.eventQueue.length
  }),

  // Crear EventEmitter personalizado
  createEmitter: (options) => new EventEmitter(options)
}

// Auto-inicialización
document.addEventListener('DOMContentLoaded', () => {
  // // console.log('🎯 Events system initialized')

  // Configurar limpieza al cerrar
  window.addEventListener('beforeunload', () => {
    Events.cleanup()
  })
})

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    EventEmitter,
    EventBus,
    DOMEventManager,
    WebSocketManager,
    EventAnalytics,
    CrossTabManager,
    EcosystemEvents,
    EventPerformanceMonitor,
    Events
  }
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.Events = Events
  window.EventEmitter = EventEmitter
  window.eventBus = eventBus
}
