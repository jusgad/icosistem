/**
 * Notification System
 * Sistema completo de notificaciones para el ecosistema de emprendimiento
 * Soporta toast, banner, push notifications y tiempo real
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class NotificationSystem {
  constructor (options = {}) {
    this.config = {
      // Configuración general
      apiBaseUrl: '/api/v1/notifications',
      enableWebSocket: true,
      enablePushNotifications: true,
      enableSounds: true,
      enableAnalytics: true,

      // Posición de las notificaciones
      position: options.position || 'top-right', // top-right, top-left, bottom-right, bottom-left, top-center, bottom-center

      // Configuración de toast
      defaultDuration: options.defaultDuration || 5000,
      maxVisible: options.maxVisible || 5,
      stackSpacing: options.stackSpacing || 10,

      // Animaciones
      animation: options.animation !== false,
      animationDuration: options.animationDuration || 300,
      animationType: options.animationType || 'slide', // slide, fade, bounce, flip

      // Auto-dismiss
      autoDismiss: options.autoDismiss !== false,
      pauseOnHover: options.pauseOnHover !== false,

      // Persistencia
      enablePersistence: options.enablePersistence !== false,
      storageKey: options.storageKey || 'ecosistema_notifications',
      maxStoredNotifications: options.maxStoredNotifications || 100,

      // Rate limiting
      enableRateLimit: options.enableRateLimit !== false,
      rateLimit: options.rateLimit || { max: 10, window: 60000 }, // 10 por minuto

      // Sonidos
      sounds: {
        success: options.sounds?.success || '/static/audio/success.mp3',
        error: options.sounds?.error || '/static/audio/error.mp3',
        warning: options.sounds?.warning || '/static/audio/warning.mp3',
        info: options.sounds?.info || '/static/audio/info.mp3',
        message: options.sounds?.message || '/static/audio/message.mp3'
      },

      // Templates personalizados
      templates: options.templates || {},

      // Callbacks globales
      onShow: options.onShow || null,
      onHide: options.onHide || null,
      onClick: options.onClick || null,
      onAction: options.onAction || null,

      ...options
    }

    this.state = {
      notifications: new Map(),
      queue: [],
      isInitialized: false,
      pushPermission: 'default',
      rateLimitCounts: new Map(),
      socket: null,
      soundsEnabled: true,
      doNotDisturbMode: false,
      unreadCount: 0,
      notificationGroups: new Map()
    }

    this.container = null
    this.templates = new Map()
    this.eventListeners = []
    this.audioContext = null
    this.sounds = new Map()

    this.init()
  }

  /**
     * Inicialización del sistema
     */
  async init () {
    try {
      await this.createContainer()
      await this.loadTemplates()
      await this.setupEventListeners()
      await this.initializeWebSocket()
      await this.initializePushNotifications()
      await this.loadPersistedNotifications()
      await this.initializeSounds()
      await this.setupServiceWorker()

      this.state.isInitialized = true
      this.processQueue()

      console.log('✅ NotificationSystem initialized successfully')
    } catch (error) {
      console.error('❌ Error initializing NotificationSystem:', error)
    }
  }

  /**
     * Crear contenedor de notificaciones
     */
  async createContainer () {
    // Remover contenedor existente si existe
    const existingContainer = document.getElementById('notification-container')
    if (existingContainer) {
      existingContainer.remove()
    }

    this.container = document.createElement('div')
    this.container.id = 'notification-container'
    this.container.className = `notification-container position-${this.config.position}`
    this.container.setAttribute('aria-live', 'polite')
    this.container.setAttribute('aria-label', 'Notificaciones')

    document.body.appendChild(this.container)
  }

  /**
     * Cargar templates de notificaciones
     */
  async loadTemplates () {
    // Template básico
    this.templates.set('default', {
      html: `
                <div class="notification-content">
                    <div class="notification-icon">{{icon}}</div>
                    <div class="notification-body">
                        <div class="notification-title">{{title}}</div>
                        <div class="notification-message">{{message}}</div>
                        {{#if timestamp}}
                        <div class="notification-timestamp">{{timestamp}}</div>
                        {{/if}}
                    </div>
                    <div class="notification-actions">
                        {{#each actions}}
                        <button class="btn btn-sm notification-action" data-action="{{action}}">{{label}}</button>
                        {{/each}}
                        <button class="btn-close notification-close" aria-label="Cerrar"></button>
                    </div>
                </div>
            `,
      styles: ['default']
    })

    // Template para mensajes del ecosistema
    this.templates.set('ecosystem', {
      html: `
                <div class="notification-content ecosystem-notification">
                    <div class="notification-avatar">
                        <img src="{{avatar}}" alt="{{sender}}" class="avatar-img">
                    </div>
                    <div class="notification-body">
                        <div class="notification-sender">{{sender}}</div>
                        <div class="notification-message">{{message}}</div>
                        <div class="notification-meta">
                            <span class="notification-role">{{senderRole}}</span>
                            <span class="notification-timestamp">{{timestamp}}</span>
                        </div>
                    </div>
                    <div class="notification-actions">
                        {{#each actions}}
                        <button class="btn btn-sm notification-action" data-action="{{action}}">{{label}}</button>
                        {{/each}}
                        <button class="btn-close notification-close" aria-label="Cerrar"></button>
                    </div>
                </div>
            `,
      styles: ['ecosystem']
    })

    // Template para progreso
    this.templates.set('progress', {
      html: `
                <div class="notification-content progress-notification">
                    <div class="notification-icon">{{icon}}</div>
                    <div class="notification-body">
                        <div class="notification-title">{{title}}</div>
                        <div class="notification-message">{{message}}</div>
                        <div class="progress notification-progress">
                            <div class="progress-bar" style="width: {{progress}}%"></div>
                        </div>
                        <div class="progress-text">{{progress}}% completado</div>
                    </div>
                    <div class="notification-actions">
                        <button class="btn-close notification-close" aria-label="Cerrar"></button>
                    </div>
                </div>
            `,
      styles: ['progress']
    })

    // Template para reuniones/eventos
    this.templates.set('meeting', {
      html: `
                <div class="notification-content meeting-notification">
                    <div class="notification-icon">
                        <i class="fas fa-calendar-alt"></i>
                    </div>
                    <div class="notification-body">
                        <div class="notification-title">{{title}}</div>
                        <div class="notification-message">{{message}}</div>
                        <div class="meeting-details">
                            <div class="meeting-time"><i class="fas fa-clock"></i> {{time}}</div>
                            <div class="meeting-participants"><i class="fas fa-users"></i> {{participants}}</div>
                        </div>
                    </div>
                    <div class="notification-actions">
                        <button class="btn btn-sm btn-success notification-action" data-action="join">Unirse</button>
                        <button class="btn btn-sm btn-outline-secondary notification-action" data-action="remind">Recordar</button>
                        <button class="btn-close notification-close" aria-label="Cerrar"></button>
                    </div>
                </div>
            `,
      styles: ['meeting']
    })

    // Cargar templates personalizados
    Object.entries(this.config.templates).forEach(([name, template]) => {
      this.templates.set(name, template)
    })
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    // Click en notificaciones
    this.container.addEventListener('click', (e) => {
      this.handleNotificationClick(e)
    })

    // Hover para pausar auto-dismiss
    if (this.config.pauseOnHover) {
      this.container.addEventListener('mouseenter', (e) => {
        if (e.target.closest('.notification')) {
          this.pauseNotification(e.target.closest('.notification'))
        }
      })

      this.container.addEventListener('mouseleave', (e) => {
        if (e.target.closest('.notification')) {
          this.resumeNotification(e.target.closest('.notification'))
        }
      })
    }

    // Visibilidad de la página
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.pauseAllNotifications()
      } else {
        this.resumeAllNotifications()
      }
    })

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Ctrl+Shift+N para mostrar todas las notificaciones
      if (e.ctrlKey && e.shiftKey && e.key === 'N') {
        e.preventDefault()
        this.showNotificationCenter()
      }

      // Escape para cerrar todas las notificaciones
      if (e.key === 'Escape' && e.ctrlKey) {
        this.clearAll()
      }
    })

    // Online/Offline events
    window.addEventListener('online', () => {
      this.show({
        type: 'success',
        title: 'Conectado',
        message: 'Conexión a internet restablecida',
        duration: 3000
      })
    })

    window.addEventListener('offline', () => {
      this.show({
        type: 'warning',
        title: 'Desconectado',
        message: 'Sin conexión a internet',
        persistent: true
      })
    })
  }

  /**
     * Inicializar WebSocket
     */
  async initializeWebSocket () {
    if (!this.config.enableWebSocket || typeof io === 'undefined') {
      return
    }

    try {
      this.state.socket = io('/notifications', {
        transports: ['websocket', 'polling']
      })

      this.state.socket.on('connect', () => {
        console.log('🔗 Notification WebSocket connected')
      })

      this.state.socket.on('disconnect', () => {
        console.log('🔌 Notification WebSocket disconnected')
      })

      // Eventos de notificaciones
      this.state.socket.on('notification', (data) => {
        this.handleWebSocketNotification(data)
      })

      this.state.socket.on('notification_read', (data) => {
        this.markAsRead(data.id)
      })

      this.state.socket.on('notification_deleted', (data) => {
        this.remove(data.id)
      })

      // Eventos específicos del ecosistema
      this.state.socket.on('new_message', (data) => {
        this.showMessage(data)
      })

      this.state.socket.on('meeting_reminder', (data) => {
        this.showMeetingReminder(data)
      })

      this.state.socket.on('project_update', (data) => {
        this.showProjectUpdate(data)
      })

      this.state.socket.on('mentorship_request', (data) => {
        this.showMentorshipRequest(data)
      })
    } catch (error) {
      console.error('Error initializing WebSocket:', error)
    }
  }

  /**
     * Inicializar Push Notifications
     */
  async initializePushNotifications () {
    if (!this.config.enablePushNotifications || !('Notification' in window)) {
      return
    }

    // Verificar permisos actuales
    this.state.pushPermission = Notification.permission

    // Si no se han pedido permisos, pedirlos
    if (this.state.pushPermission === 'default') {
      this.state.pushPermission = await Notification.requestPermission()
    }

    // Registrar service worker si es necesario
    if (this.state.pushPermission === 'granted' && 'serviceWorker' in navigator) {
      await this.registerServiceWorker()
    }
  }

  /**
     * Inicializar sonidos
     */
  async initializeSounds () {
    if (!this.config.enableSounds) {
      return
    }

    try {
      // Precargar sonidos
      for (const [type, url] of Object.entries(this.config.sounds)) {
        if (url) {
          const audio = new Audio(url)
          audio.preload = 'auto'
          this.sounds.set(type, audio)
        }
      }
    } catch (error) {
      console.warn('Error initializing sounds:', error)
    }
  }

  /**
     * Configurar Service Worker
     */
  async setupServiceWorker () {
    if (!('serviceWorker' in navigator)) {
      return
    }

    try {
      const registration = await navigator.serviceWorker.register('/static/js/sw-notifications.js')
      console.log('Service Worker registered:', registration)
    } catch (error) {
      console.warn('Service Worker registration failed:', error)
    }
  }

  /**
     * Mostrar notificación
     */
  show (options) {
    // Validar rate limiting
    if (!this.checkRateLimit(options.type || 'default')) {
      console.warn('Rate limit exceeded for notifications')
      return null
    }

    // Si no está inicializado, agregar a la cola
    if (!this.state.isInitialized) {
      this.state.queue.push(options)
      return null
    }

    // Crear notificación
    const notification = this.createNotification(options)

    // Añadir al DOM
    this.addToDOM(notification)

    // Configurar auto-dismiss
    if (options.duration !== false && this.config.autoDismiss) {
      this.setupAutoDismiss(notification)
    }

    // Reproducir sonido
    this.playSound(options.type || 'info')

    // Callback onShow
    if (this.config.onShow) {
      this.config.onShow(notification, options)
    }

    // Persistir si es necesario
    if (this.config.enablePersistence && !options.temporary) {
      this.persistNotification(notification)
    }

    // Analytics
    if (this.config.enableAnalytics) {
      this.trackNotification('show', notification)
    }

    return notification
  }

  /**
     * Crear notificación
     */
  createNotification (options) {
    const id = options.id || this.generateId()
    const type = options.type || 'info'
    const template = options.template || 'default'

    const notification = {
      id,
      type,
      template,
      title: options.title || '',
      message: options.message || '',
      duration: options.duration ?? this.config.defaultDuration,
      persistent: options.persistent || false,
      timestamp: new Date(),
      read: false,
      actions: options.actions || [],
      data: options.data || {},
      element: null,
      timer: null,
      paused: false,
      group: options.group || null,
      priority: options.priority || 'normal', // low, normal, high, urgent
      avatar: options.avatar || null,
      sender: options.sender || null,
      senderRole: options.senderRole || null,
      progress: options.progress || null,
      ...options
    }

    // Crear elemento DOM
    notification.element = this.createNotificationElement(notification)

    // Almacenar referencia
    this.state.notifications.set(id, notification)

    // Agrupar si es necesario
    if (notification.group) {
      this.addToGroup(notification)
    }

    return notification
  }

  /**
     * Crear elemento DOM de la notificación
     */
  createNotificationElement (notification) {
    const element = document.createElement('div')
    element.className = `notification notification-${notification.type} notification-${notification.priority}`
    element.id = `notification-${notification.id}`
    element.setAttribute('role', 'alert')
    element.setAttribute('aria-live', 'assertive')
    element.dataset.notificationId = notification.id

    // Aplicar template
    const template = this.templates.get(notification.template) || this.templates.get('default')
    element.innerHTML = this.renderTemplate(template.html, notification)

    // Aplicar estilos específicos del template
    if (template.styles) {
      template.styles.forEach(style => {
        element.classList.add(`notification-style-${style}`)
      })
    }

    return element
  }

  /**
     * Renderizar template
     */
  renderTemplate (template, data) {
    return template.replace(/\{\{(.*?)\}\}/g, (match, key) => {
      const keys = key.trim().split('.')
      let value = data

      for (const k of keys) {
        value = value?.[k]
      }

      if (key.includes('timestamp')) {
        return this.formatTimestamp(value)
      }

      if (key.includes('icon')) {
        return this.getIcon(data.type)
      }

      return value || ''
    }).replace(/\{\{#if (.*?)\}\}(.*?)\{\{\/if\}\}/g, (match, condition, content) => {
      const keys = condition.trim().split('.')
      let value = data

      for (const k of keys) {
        value = value?.[k]
      }

      return value ? content : ''
    }).replace(/\{\{#each (.*?)\}\}(.*?)\{\{\/each\}\}/g, (match, arrayName, itemTemplate) => {
      const array = data[arrayName.trim()] || []
      return array.map(item =>
        itemTemplate.replace(/\{\{(.*?)\}\}/g, (match, key) => item[key.trim()] || '')
      ).join('')
    })
  }

  /**
     * Añadir notificación al DOM
     */
  addToDOM (notification) {
    // Verificar límite de notificaciones visibles
    this.enforceVisibilityLimit()

    // Añadir al contenedor
    this.container.appendChild(notification.element)

    // Aplicar animación de entrada
    if (this.config.animation) {
      this.animateIn(notification.element)
    }

    // Actualizar contador de no leídas
    this.updateUnreadCount()
  }

  /**
     * Aplicar límite de notificaciones visibles
     */
  enforceVisibilityLimit () {
    const visibleNotifications = this.container.querySelectorAll('.notification')
    const excess = visibleNotifications.length - this.config.maxVisible + 1

    if (excess > 0) {
      // Remover las más antiguas
      for (let i = 0; i < excess; i++) {
        const oldest = visibleNotifications[i]
        const id = oldest.dataset.notificationId
        this.remove(id, false)
      }
    }
  }

  /**
     * Configurar auto-dismiss
     */
  setupAutoDismiss (notification) {
    if (notification.persistent || notification.duration === false) {
      return
    }

    const duration = notification.duration || this.config.defaultDuration

    notification.timer = setTimeout(() => {
      this.remove(notification.id)
    }, duration)
  }

  /**
     * Pausar notificación
     */
  pauseNotification (element) {
    const id = element.dataset.notificationId
    const notification = this.state.notifications.get(id)

    if (notification && notification.timer && !notification.paused) {
      clearTimeout(notification.timer)
      notification.paused = true
      element.classList.add('paused')
    }
  }

  /**
     * Reanudar notificación
     */
  resumeNotification (element) {
    const id = element.dataset.notificationId
    const notification = this.state.notifications.get(id)

    if (notification && notification.paused) {
      notification.paused = false
      element.classList.remove('paused')

      // Reiniciar timer si es necesario
      if (notification.duration && this.config.autoDismiss) {
        this.setupAutoDismiss(notification)
      }
    }
  }

  /**
     * Remover notificación
     */
  async remove (id, animate = true) {
    const notification = this.state.notifications.get(id)
    if (!notification) return

    // Limpiar timer
    if (notification.timer) {
      clearTimeout(notification.timer)
    }

    // Animar salida
    if (animate && this.config.animation) {
      await this.animateOut(notification.element)
    }

    // Remover del DOM
    if (notification.element && notification.element.parentNode) {
      notification.element.parentNode.removeChild(notification.element)
    }

    // Remover de memoria
    this.state.notifications.delete(id)

    // Remover de grupo si es necesario
    if (notification.group) {
      this.removeFromGroup(notification)
    }

    // Callback onHide
    if (this.config.onHide) {
      this.config.onHide(notification)
    }

    // Analytics
    if (this.config.enableAnalytics) {
      this.trackNotification('remove', notification)
    }

    // Actualizar contador
    this.updateUnreadCount()
  }

  /**
     * Manejar click en notificación
     */
  handleNotificationClick (e) {
    const notificationElement = e.target.closest('.notification')
    if (!notificationElement) return

    const id = notificationElement.dataset.notificationId
    const notification = this.state.notifications.get(id)
    if (!notification) return

    // Marcar como leída
    this.markAsRead(id)

    // Manejar botón cerrar
    if (e.target.closest('.notification-close')) {
      e.preventDefault()
      e.stopPropagation()
      this.remove(id)
      return
    }

    // Manejar acciones
    const actionButton = e.target.closest('.notification-action')
    if (actionButton) {
      e.preventDefault()
      e.stopPropagation()

      const action = actionButton.dataset.action
      this.handleAction(notification, action)
      return
    }

    // Click general en la notificación
    if (this.config.onClick) {
      this.config.onClick(notification, e)
    }

    // Remover al hacer click si no tiene acciones
    if (!notification.actions || notification.actions.length === 0) {
      this.remove(id)
    }
  }

  /**
     * Manejar acciones de notificación
     */
  async handleAction (notification, action) {
    const actionConfig = notification.actions?.find(a => a.action === action)
    if (!actionConfig) return

    // Callback global
    if (this.config.onAction) {
      const result = await this.config.onAction(notification, action, actionConfig)
      if (result === false) return
    }

    // Callback específico de la acción
    if (actionConfig.handler) {
      const result = await actionConfig.handler(notification, action)
      if (result === false) return
    }

    // Acciones predefinidas
    switch (action) {
      case 'dismiss':
        this.remove(notification.id)
        break

      case 'mark_read':
        this.markAsRead(notification.id)
        break

      case 'join':
        // Unirse a reunión
        window.open(notification.data.meetingUrl, '_blank')
        this.remove(notification.id)
        break

      case 'remind':
        // Recordar más tarde
        this.snooze(notification.id, 5 * 60 * 1000) // 5 minutos
        break

      case 'view':
        // Ver detalles
        if (notification.data.url) {
          window.location.href = notification.data.url
        }
        break
    }

    // Analytics
    if (this.config.enableAnalytics) {
      this.trackNotification('action', notification, { action })
    }
  }

  /**
     * Marcar como leída
     */
  markAsRead (id) {
    const notification = this.state.notifications.get(id)
    if (!notification || notification.read) return

    notification.read = true
    notification.element?.classList.add('read')

    // Actualizar en el servidor
    if (this.state.socket) {
      this.state.socket.emit('mark_read', { id })
    }

    this.updateUnreadCount()
  }

  /**
     * Posponer notificación
     */
  snooze (id, delay) {
    const notification = this.state.notifications.get(id)
    if (!notification) return

    // Remover temporalmente
    this.remove(id, false)

    // Reprogramar
    setTimeout(() => {
      this.show({
        ...notification,
        id: this.generateId() // Nuevo ID para evitar conflictos
      })
    }, delay)
  }

  /**
     * Animaciones
     */
  async animateIn (element) {
    const animations = this.getAnimations()
    const keyframes = animations[this.config.animationType]?.in || animations.slide.in

    return element.animate(keyframes, {
      duration: this.config.animationDuration,
      easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
      fill: 'forwards'
    }).finished
  }

  async animateOut (element) {
    const animations = this.getAnimations()
    const keyframes = animations[this.config.animationType]?.out || animations.slide.out

    return element.animate(keyframes, {
      duration: this.config.animationDuration,
      easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
      fill: 'forwards'
    }).finished
  }

  getAnimations () {
    return {
      slide: {
        in: [
          { transform: 'translateX(100%)', opacity: 0 },
          { transform: 'translateX(0)', opacity: 1 }
        ],
        out: [
          { transform: 'translateX(0)', opacity: 1 },
          { transform: 'translateX(100%)', opacity: 0 }
        ]
      },
      fade: {
        in: [
          { opacity: 0, transform: 'scale(0.8)' },
          { opacity: 1, transform: 'scale(1)' }
        ],
        out: [
          { opacity: 1, transform: 'scale(1)' },
          { opacity: 0, transform: 'scale(0.8)' }
        ]
      },
      bounce: {
        in: [
          { transform: 'translateY(-100px) scale(0.3)', opacity: 0 },
          { transform: 'translateY(0) scale(1)', opacity: 1 }
        ],
        out: [
          { transform: 'translateY(0) scale(1)', opacity: 1 },
          { transform: 'translateY(-100px) scale(0.3)', opacity: 0 }
        ]
      },
      flip: {
        in: [
          { transform: 'rotateY(-90deg)', opacity: 0 },
          { transform: 'rotateY(0)', opacity: 1 }
        ],
        out: [
          { transform: 'rotateY(0)', opacity: 1 },
          { transform: 'rotateY(-90deg)', opacity: 0 }
        ]
      }
    }
  }

  /**
     * Reproducir sonido
     */
  playSound (type) {
    if (!this.config.enableSounds || !this.state.soundsEnabled || this.state.doNotDisturbMode) {
      return
    }

    const audio = this.sounds.get(type)
    if (audio) {
      audio.currentTime = 0
      audio.play().catch(() => {
        // Ignorar errores de audio (autoplay policy)
      })
    }
  }

  /**
     * Métodos específicos del ecosistema
     */
  showMessage (data) {
    this.show({
      type: 'message',
      template: 'ecosystem',
      title: 'Nuevo Mensaje',
      message: data.message,
      sender: data.sender.name,
      senderRole: data.sender.role,
      avatar: data.sender.avatar,
      actions: [
        { action: 'view', label: 'Ver', handler: () => window.location.href = data.url },
        { action: 'dismiss', label: 'Cerrar' }
      ],
      data
    })
  }

  showMeetingReminder (data) {
    this.show({
      type: 'warning',
      template: 'meeting',
      title: 'Reunión Programada',
      message: `Reunión "${data.title}" en ${data.timeUntil}`,
      time: data.time,
      participants: data.participants,
      persistent: true,
      actions: [
        { action: 'join', label: 'Unirse' },
        { action: 'remind', label: 'Recordar' }
      ],
      data
    })
  }

  showProjectUpdate (data) {
    this.show({
      type: 'info',
      title: 'Actualización de Proyecto',
      message: `${data.project} - ${data.update}`,
      actions: [
        { action: 'view', label: 'Ver Proyecto' }
      ],
      data
    })
  }

  showMentorshipRequest (data) {
    this.show({
      type: 'info',
      template: 'ecosystem',
      title: 'Nueva Solicitud de Mentoría',
      message: `${data.entrepreneur} solicita mentoría en ${data.area}`,
      sender: data.entrepreneur,
      senderRole: 'Emprendedor',
      avatar: data.avatar,
      persistent: true,
      actions: [
        { action: 'accept', label: 'Aceptar', handler: () => this.acceptMentorship(data.id) },
        { action: 'view', label: 'Ver Perfil' },
        { action: 'dismiss', label: 'Declinar' }
      ],
      data
    })
  }

  showProgress (options) {
    return this.show({
      template: 'progress',
      type: 'info',
      persistent: true,
      ...options
    })
  }

  updateProgress (id, progress) {
    const notification = this.state.notifications.get(id)
    if (!notification) return

    notification.progress = progress

    const progressBar = notification.element.querySelector('.progress-bar')
    const progressText = notification.element.querySelector('.progress-text')

    if (progressBar) {
      progressBar.style.width = `${progress}%`
    }

    if (progressText) {
      progressText.textContent = `${progress}% completado`
    }

    // Auto-remover al completar
    if (progress >= 100) {
      setTimeout(() => {
        this.remove(id)
      }, 2000)
    }
  }

  /**
     * Push Notifications
     */
  async showPushNotification (options) {
    if (this.state.pushPermission !== 'granted') {
      return
    }

    const notification = new Notification(options.title, {
      body: options.message,
      icon: options.icon || '/static/img/notification-icon.png',
      badge: '/static/img/badge-icon.png',
      tag: options.id || this.generateId(),
      requireInteraction: options.requireInteraction || false,
      actions: options.actions || [],
      data: options.data || {}
    })

    notification.onclick = (e) => {
      e.preventDefault()
      window.focus()

      if (options.url) {
        window.location.href = options.url
      }

      notification.close()
    }

    return notification
  }

  /**
     * WebSocket handlers
     */
  handleWebSocketNotification (data) {
    // Mostrar notificación local
    this.show(data)

    // Mostrar push notification si la página no está visible
    if (document.hidden && this.state.pushPermission === 'granted') {
      this.showPushNotification(data)
    }
  }

  /**
     * Rate limiting
     */
  checkRateLimit (type) {
    if (!this.config.enableRateLimit) {
      return true
    }

    const now = Date.now()
    const windowStart = now - this.config.rateLimit.window

    // Limpiar contadores antiguos
    for (const [key, timestamps] of this.state.rateLimitCounts.entries()) {
      this.state.rateLimitCounts.set(key, timestamps.filter(t => t > windowStart))
    }

    // Verificar límite
    const counts = this.state.rateLimitCounts.get(type) || []
    if (counts.length >= this.config.rateLimit.max) {
      return false
    }

    // Agregar timestamp actual
    counts.push(now)
    this.state.rateLimitCounts.set(type, counts)

    return true
  }

  /**
     * Persistencia
     */
  persistNotification (notification) {
    try {
      const stored = JSON.parse(localStorage.getItem(this.config.storageKey) || '[]')

      stored.push({
        id: notification.id,
        type: notification.type,
        title: notification.title,
        message: notification.message,
        timestamp: notification.timestamp,
        read: notification.read,
        data: notification.data
      })

      // Mantener solo las últimas N notificaciones
      const trimmed = stored.slice(-this.config.maxStoredNotifications)

      localStorage.setItem(this.config.storageKey, JSON.stringify(trimmed))
    } catch (error) {
      console.warn('Error persisting notification:', error)
    }
  }

  async loadPersistedNotifications () {
    try {
      const stored = JSON.parse(localStorage.getItem(this.config.storageKey) || '[]')

      // Solo cargar las no leídas de las últimas 24 horas
      const yesterday = Date.now() - 24 * 60 * 60 * 1000

      const recent = stored.filter(n =>
        !n.read &&
                new Date(n.timestamp).getTime() > yesterday
      )

      // Mostrar las más recientes primero
      recent.reverse().forEach(notification => {
        this.show({
          ...notification,
          temporary: true // No persistir de nuevo
        })
      })
    } catch (error) {
      console.warn('Error loading persisted notifications:', error)
    }
  }

  /**
     * Agrupamiento
     */
  addToGroup (notification) {
    const groupId = notification.group

    if (!this.state.notificationGroups.has(groupId)) {
      this.state.notificationGroups.set(groupId, [])
    }

    this.state.notificationGroups.get(groupId).push(notification.id)

    // Si hay muchas notificaciones del mismo grupo, crear resumen
    const groupNotifications = this.state.notificationGroups.get(groupId)
    if (groupNotifications.length > 3) {
      this.createGroupSummary(groupId)
    }
  }

  createGroupSummary (groupId) {
    const groupNotifications = this.state.notificationGroups.get(groupId)

    // Remover notificaciones individuales del grupo
    groupNotifications.forEach(id => {
      this.remove(id, false)
    })

    // Crear resumen
    this.show({
      type: 'info',
      title: 'Múltiples Notificaciones',
      message: `Tienes ${groupNotifications.length} notificaciones de ${groupId}`,
      actions: [
        { action: 'view_all', label: 'Ver Todas' },
        { action: 'dismiss', label: 'Cerrar' }
      ],
      group: null // Evitar agrupamiento recursivo
    })

    // Limpiar grupo
    this.state.notificationGroups.delete(groupId)
  }

  /**
     * Métodos de utilidad
     */
  processQueue () {
    while (this.state.queue.length > 0) {
      const options = this.state.queue.shift()
      this.show(options)
    }
  }

  pauseAllNotifications () {
    this.state.notifications.forEach(notification => {
      if (notification.timer && !notification.paused) {
        clearTimeout(notification.timer)
        notification.paused = true
      }
    })
  }

  resumeAllNotifications () {
    this.state.notifications.forEach(notification => {
      if (notification.paused) {
        notification.paused = false
        if (notification.duration && this.config.autoDismiss) {
          this.setupAutoDismiss(notification)
        }
      }
    })
  }

  clearAll () {
    const notifications = Array.from(this.state.notifications.keys())
    notifications.forEach(id => this.remove(id))
  }

  clearRead () {
    const notifications = Array.from(this.state.notifications.values())
    notifications.filter(n => n.read).forEach(n => this.remove(n.id))
  }

  getUnreadCount () {
    return Array.from(this.state.notifications.values()).filter(n => !n.read).length
  }

  updateUnreadCount () {
    this.state.unreadCount = this.getUnreadCount()

    // Actualizar badge si existe
    const badge = document.querySelector('.notification-badge')
    if (badge) {
      badge.textContent = this.state.unreadCount
      badge.style.display = this.state.unreadCount > 0 ? 'block' : 'none'
    }

    // Actualizar título de la página
    if (this.state.unreadCount > 0) {
      document.title = `(${this.state.unreadCount}) ${document.title.replace(/^\(\d+\) /, '')}`
    } else {
      document.title = document.title.replace(/^\(\d+\) /, '')
    }
  }

  toggleSounds () {
    this.state.soundsEnabled = !this.state.soundsEnabled

    this.show({
      type: 'info',
      title: 'Sonidos',
      message: `Sonidos ${this.state.soundsEnabled ? 'activados' : 'desactivados'}`,
      duration: 2000
    })
  }

  toggleDoNotDisturb () {
    this.state.doNotDisturbMode = !this.state.doNotDisturbMode

    this.show({
      type: 'info',
      title: 'No Molestar',
      message: `Modo no molestar ${this.state.doNotDisturbMode ? 'activado' : 'desactivado'}`,
      duration: 2000
    })
  }

  formatTimestamp (timestamp) {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date

    if (diff < 60000) { // Menos de 1 minuto
      return 'Ahora'
    } else if (diff < 3600000) { // Menos de 1 hora
      return `${Math.floor(diff / 60000)}m`
    } else if (diff < 86400000) { // Menos de 1 día
      return `${Math.floor(diff / 3600000)}h`
    } else {
      return date.toLocaleDateString()
    }
  }

  getIcon (type) {
    const icons = {
      success: '<i class="fas fa-check-circle text-success"></i>',
      error: '<i class="fas fa-times-circle text-danger"></i>',
      warning: '<i class="fas fa-exclamation-triangle text-warning"></i>',
      info: '<i class="fas fa-info-circle text-info"></i>',
      message: '<i class="fas fa-comment text-primary"></i>'
    }

    return icons[type] || icons.info
  }

  generateId () {
    return 'notification_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now()
  }

  trackNotification (event, notification, data = {}) {
    if (!this.config.enableAnalytics) return

    // Implementar tracking según el sistema de analytics usado
    if (typeof gtag !== 'undefined') {
      gtag('event', 'notification_' + event, {
        notification_type: notification.type,
        notification_template: notification.template,
        ...data
      })
    }
  }

  /**
     * API pública simplificada
     */
  success (title, message, options = {}) {
    return this.show({ type: 'success', title, message, ...options })
  }

  error (title, message, options = {}) {
    return this.show({ type: 'error', title, message, persistent: true, ...options })
  }

  warning (title, message, options = {}) {
    return this.show({ type: 'warning', title, message, ...options })
  }

  info (title, message, options = {}) {
    return this.show({ type: 'info', title, message, ...options })
  }

  /**
     * Cleanup
     */
  destroy () {
    // Limpiar timers
    this.state.notifications.forEach(notification => {
      if (notification.timer) {
        clearTimeout(notification.timer)
      }
    })

    // Desconectar WebSocket
    if (this.state.socket) {
      this.state.socket.disconnect()
    }

    // Remover event listeners
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    // Remover contenedor
    if (this.container) {
      this.container.remove()
    }

    console.log('🧹 NotificationSystem destroyed')
  }
}

// CSS personalizado para las notificaciones
const notificationCSS = `
    .notification-container {
        position: fixed;
        z-index: 9999;
        pointer-events: none;
        max-width: 400px;
        width: 100%;
    }
    
    .notification-container.position-top-right {
        top: 20px;
        right: 20px;
    }
    
    .notification-container.position-top-left {
        top: 20px;
        left: 20px;
    }
    
    .notification-container.position-bottom-right {
        bottom: 20px;
        right: 20px;
    }
    
    .notification-container.position-bottom-left {
        bottom: 20px;
        left: 20px;
    }
    
    .notification-container.position-top-center {
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
    }
    
    .notification-container.position-bottom-center {
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
    }
    
    .notification {
        pointer-events: auto;
        margin-bottom: 10px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        border-left: 4px solid #007bff;
        overflow: hidden;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .notification:hover {
        transform: translateX(-5px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }
    
    .notification.paused {
        opacity: 0.8;
    }
    
    .notification.read {
        opacity: 0.7;
    }
    
    .notification-success {
        border-left-color: #28a745;
    }
    
    .notification-error {
        border-left-color: #dc3545;
    }
    
    .notification-warning {
        border-left-color: #ffc107;
    }
    
    .notification-info {
        border-left-color: #17a2b8;
    }
    
    .notification-priority-high {
        border-left-width: 6px;
        animation: pulse 2s infinite;
    }
    
    .notification-priority-urgent {
        border-left-width: 8px;
        animation: shake 0.5s infinite;
    }
    
    .notification-content {
        padding: 16px;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }
    
    .notification-icon {
        flex-shrink: 0;
        font-size: 20px;
    }
    
    .notification-avatar {
        flex-shrink: 0;
    }
    
    .notification-avatar .avatar-img {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
    }
    
    .notification-body {
        flex: 1;
        min-width: 0;
    }
    
    .notification-title {
        font-weight: 600;
        color: #333;
        margin-bottom: 4px;
        font-size: 14px;
    }
    
    .notification-message {
        color: #666;
        font-size: 13px;
        line-height: 1.4;
        margin-bottom: 8px;
    }
    
    .notification-timestamp {
        font-size: 11px;
        color: #999;
    }
    
    .notification-sender {
        font-weight: 600;
        color: #333;
        font-size: 13px;
        margin-bottom: 2px;
    }
    
    .notification-meta {
        display: flex;
        gap: 8px;
        align-items: center;
        font-size: 11px;
        color: #999;
        margin-top: 4px;
    }
    
    .notification-role {
        background: #f8f9fa;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10px;
    }
    
    .notification-actions {
        flex-shrink: 0;
        display: flex;
        gap: 4px;
        align-items: flex-start;
    }
    
    .notification-action {
        padding: 4px 8px;
        font-size: 12px;
        border-radius: 4px;
    }
    
    .notification-close {
        background: none;
        border: none;
        font-size: 18px;
        color: #999;
        cursor: pointer;
        padding: 0;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .notification-close:hover {
        color: #666;
    }
    
    .notification-progress {
        height: 4px;
        margin-top: 8px;
        background: #e9ecef;
        border-radius: 2px;
        overflow: hidden;
    }
    
    .notification-progress .progress-bar {
        height: 100%;
        background: #007bff;
        transition: width 0.3s ease;
    }
    
    .progress-text {
        font-size: 11px;
        color: #666;
        margin-top: 4px;
    }
    
    .meeting-details {
        margin-top: 8px;
        font-size: 12px;
        color: #666;
    }
    
    .meeting-details > div {
        margin-bottom: 4px;
    }
    
    .meeting-details i {
        width: 14px;
        color: #999;
        margin-right: 6px;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-2px); }
        75% { transform: translateX(2px); }
    }
    
    @media (max-width: 768px) {
        .notification-container {
            left: 10px !important;
            right: 10px !important;
            max-width: none;
            transform: none !important;
        }
        
        .notification-content {
            padding: 12px;
            gap: 8px;
        }
        
        .notification-actions {
            flex-direction: column;
            gap: 2px;
        }
        
        .notification-action {
            font-size: 11px;
            padding: 3px 6px;
        }
    }
`

// Inyectar CSS
if (!document.getElementById('notification-system-styles')) {
  const style = document.createElement('style')
  style.id = 'notification-system-styles'
  style.textContent = notificationCSS
  document.head.appendChild(style)
}

// Crear instancia global
window.NotificationSystem = NotificationSystem

// Inicialización automática
document.addEventListener('DOMContentLoaded', () => {
  window.notifications = new NotificationSystem({
    position: 'top-right',
    enableWebSocket: true,
    enablePushNotifications: true
  })
})

export default NotificationSystem
