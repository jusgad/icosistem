/**
 * Ecosistema Emprendimiento - Ally Messenger Module
 * =================================================
 *
 * Sistema completo de mensajería para aliados/mentores del ecosistema
 * Incluye chat en tiempo real, gestión de conversaciones, archivos y sesiones
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js
 */

'use strict'

/**
 * Módulo principal de mensajería para aliados
 */
class AllyMessenger {
  constructor (container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container

    if (!this.container) {
      throw new Error('Container for AllyMessenger not found')
    }

    // Referencias a sistemas principales
    this.app = window.EcosistemaApp
    this.main = window.App
    this.state = this.app?.state
    this.config = window.getConfig('modules.allyMessenger', {})

    // Configuración del módulo
    this.options = {
      enableRealTime: true,
      enableFileSharing: true,
      enableVideoCall: true,
      enableScreenShare: false,
      enableTypingIndicator: true,
      enableReadReceipts: true,
      enableMessageReactions: true,
      enableThreads: true,
      enableSearch: true,
      enableMentorshipTools: true,
      maxFileSize: 50 * 1024 * 1024, // 50MB
      allowedFileTypes: [
        'image/jpeg', 'image/png', 'image/gif',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain', 'application/zip'
      ],
      messagesPerPage: 50,
      autoScrollThreshold: 100,
      typingTimeout: 3000,
      theme: 'mentor', // mentor, entrepreneur, admin
      ...options
    }

    // Estado del módulo
    this.moduleState = {
      currentConversation: null,
      conversations: new Map(),
      messages: new Map(),
      typingUsers: new Set(),
      onlineUsers: new Set(),
      unreadCounts: new Map(),
      searchResults: [],
      isSearching: false,
      selectedMessages: new Set(),
      replyToMessage: null,
      editingMessage: null,
      uploadQueue: new Map(),
      mentorshipSession: null,
      callState: {
        active: false,
        type: null, // 'video', 'audio'
        participants: [],
        screenSharing: false
      }
    }

    // Event handlers
    this.handlers = new Map()

    // WebSocket connection
    this.socket = null

    // UI Elements
    this.elements = {}

    // Timers
    this.timers = {
      typing: null,
      autoSave: null,
      heartbeat: null
    }

    // Inicializar módulo
    this.init()
  }

  /**
     * Inicializar módulo
     */
  async init () {
    try {
      console.log('🤝 Inicializando AllyMessenger')

      // Verificar permisos
      if (!this.checkPermissions()) {
        throw new Error('Usuario sin permisos para usar AllyMessenger')
      }

      // Construir interfaz
      await this.buildInterface()

      // Configurar eventos
      this.setupEventHandlers()

      // Conectar WebSocket
      if (this.options.enableRealTime) {
        this.setupWebSocket()
      }

      // Cargar datos iniciales
      await this.loadInitialData()

      // Configurar funcionalidades específicas
      this.setupMentorshipFeatures()

      // Inicializar búsqueda
      if (this.options.enableSearch) {
        this.setupSearch()
      }

      // Configurar auto-guardado
      this.setupAutoSave()

      console.log('✅ AllyMessenger inicializado correctamente')
    } catch (error) {
      console.error('❌ Error inicializando AllyMessenger:', error)
      this.showError('Error inicializando sistema de mensajería')
    }
  }

  /**
     * Verificar permisos del usuario
     */
  checkPermissions () {
    const userType = this.main.userType
    const allowedTypes = ['mentor', 'admin', 'entrepreneur']
    return allowedTypes.includes(userType)
  }

  /**
     * Construir interfaz de usuario
     */
  async buildInterface () {
    this.container.innerHTML = this.getMainTemplate()

    // Cachear elementos principales
    this.elements = {
      sidebar: this.container.querySelector('.messenger-sidebar'),
      chatArea: this.container.querySelector('.messenger-chat'),
      header: this.container.querySelector('.chat-header'),
      messagesContainer: this.container.querySelector('.messages-container'),
      messagesList: this.container.querySelector('.messages-list'),
      inputArea: this.container.querySelector('.message-input-area'),
      messageInput: this.container.querySelector('.message-input'),
      sendButton: this.container.querySelector('.send-button'),
      fileInput: this.container.querySelector('.file-input'),
      searchInput: this.container.querySelector('.search-input'),
      conversationsList: this.container.querySelector('.conversations-list'),
      typingIndicator: this.container.querySelector('.typing-indicator'),
      callControls: this.container.querySelector('.call-controls'),
      mentorshipPanel: this.container.querySelector('.mentorship-panel')
    }

    // Aplicar tema
    this.applyTheme()

    // Configurar drag & drop para archivos
    this.setupFileDragDrop()
  }

  /**
     * Template principal de la interfaz
     */
  getMainTemplate () {
    return `
            <div class="ally-messenger ${this.options.theme}-theme">
                <!-- Sidebar con conversaciones -->
                <div class="messenger-sidebar">
                    <div class="sidebar-header">
                        <h3 class="sidebar-title">
                            <i class="fa fa-comments me-2"></i>
                            Mensajería Mentor
                        </h3>
                        <div class="sidebar-actions">
                            <button class="btn btn-sm btn-outline-primary" data-action="new-conversation">
                                <i class="fa fa-plus"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" data-action="toggle-search">
                                <i class="fa fa-search"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Búsqueda -->
                    <div class="search-container d-none">
                        <div class="search-input-wrapper">
                            <input type="text" class="form-control search-input" 
                                   placeholder="Buscar conversaciones o mensajes...">
                            <button class="btn btn-sm btn-outline-secondary search-clear">
                                <i class="fa fa-times"></i>
                            </button>
                        </div>
                        <div class="search-results"></div>
                    </div>

                    <!-- Lista de conversaciones -->
                    <div class="conversations-container">
                        <div class="conversations-list">
                            <!-- Las conversaciones se cargan dinámicamente -->
                        </div>
                    </div>

                    <!-- Panel de mentoría rápida -->
                    <div class="mentorship-quick-panel">
                        <h6>Herramientas de Mentoría</h6>
                        <div class="quick-actions">
                            <button class="btn btn-sm btn-success" data-action="schedule-session">
                                <i class="fa fa-calendar-plus"></i>
                                Programar Sesión
                            </button>
                            <button class="btn btn-sm btn-info" data-action="share-resource">
                                <i class="fa fa-share"></i>
                                Compartir Recurso
                            </button>
                            <button class="btn btn-sm btn-warning" data-action="create-assignment">
                                <i class="fa fa-tasks"></i>
                                Crear Tarea
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Área principal de chat -->
                <div class="messenger-chat">
                    <!-- Header del chat -->
                    <div class="chat-header">
                        <div class="chat-info">
                            <div class="chat-avatar">
                                <img src="/static/img/default-avatar.png" alt="Avatar" class="avatar-img">
                                <span class="status-indicator"></span>
                            </div>
                            <div class="chat-details">
                                <h5 class="chat-name">Selecciona una conversación</h5>
                                <span class="chat-status">Offline</span>
                            </div>
                        </div>
                        
                        <div class="chat-actions">
                            <!-- Llamada de video -->
                            <button class="btn btn-sm btn-outline-primary" data-action="video-call" 
                                    title="Videollamada">
                                <i class="fa fa-video"></i>
                            </button>
                            <!-- Llamada de audio -->
                            <button class="btn btn-sm btn-outline-success" data-action="audio-call"
                                    title="Llamada de audio">
                                <i class="fa fa-phone"></i>
                            </button>
                            <!-- Programar reunión -->
                            <button class="btn btn-sm btn-outline-info" data-action="schedule-meeting"
                                    title="Programar reunión">
                                <i class="fa fa-calendar"></i>
                            </button>
                            <!-- Info de la conversación -->
                            <button class="btn btn-sm btn-outline-secondary" data-action="conversation-info"
                                    title="Información">
                                <i class="fa fa-info-circle"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Controles de llamada activa -->
                    <div class="call-controls d-none">
                        <div class="call-info">
                            <span class="call-duration">00:00</span>
                            <span class="call-type">Videollamada</span>
                        </div>
                        <div class="call-actions">
                            <button class="btn btn-sm btn-secondary" data-action="mute-audio">
                                <i class="fa fa-microphone"></i>
                            </button>
                            <button class="btn btn-sm btn-secondary" data-action="mute-video">
                                <i class="fa fa-video"></i>
                            </button>
                            <button class="btn btn-sm btn-warning" data-action="share-screen">
                                <i class="fa fa-desktop"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" data-action="end-call">
                                <i class="fa fa-phone-slash"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Contenedor de mensajes -->
                    <div class="messages-container">
                        <div class="messages-list">
                            <!-- Placeholder cuando no hay conversación -->
                            <div class="no-conversation-placeholder">
                                <div class="placeholder-content">
                                    <i class="fa fa-comments fa-3x text-muted"></i>
                                    <h4>Bienvenido al sistema de mensajería</h4>
                                    <p class="text-muted">Selecciona una conversación para comenzar a chatear con tus mentees</p>
                                    <button class="btn btn-primary" data-action="new-conversation">
                                        <i class="fa fa-plus me-2"></i>
                                        Nueva Conversación
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Indicador de escritura -->
                        <div class="typing-indicator d-none">
                            <div class="typing-animation">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                            <span class="typing-text">escribiendo...</span>
                        </div>
                    </div>

                    <!-- Área de entrada de mensajes -->
                    <div class="message-input-area">
                        <!-- Responder a mensaje -->
                        <div class="reply-preview d-none">
                            <div class="reply-content">
                                <span class="reply-to">Respondiendo a:</span>
                                <div class="reply-message"></div>
                            </div>
                            <button class="btn btn-sm btn-outline-secondary reply-cancel">
                                <i class="fa fa-times"></i>
                            </button>
                        </div>

                        <!-- Barra de herramientas -->
                        <div class="input-toolbar">
                            <button class="btn btn-sm btn-outline-secondary" data-action="attach-file" 
                                    title="Adjuntar archivo">
                                <i class="fa fa-paperclip"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" data-action="insert-emoji"
                                    title="Emoji">
                                <i class="fa fa-smile"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-info" data-action="quick-template"
                                    title="Plantillas rápidas">
                                <i class="fa fa-magic"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-warning" data-action="mentorship-tool"
                                    title="Herramientas de mentoría">
                                <i class="fa fa-graduation-cap"></i>
                            </button>
                        </div>

                        <!-- Input principal -->
                        <div class="input-main">
                            <div class="input-wrapper">
                                <textarea class="form-control message-input" 
                                         placeholder="Escribe un mensaje..." 
                                         rows="1"></textarea>
                                <button class="btn btn-primary send-button" disabled>
                                    <i class="fa fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>

                        <!-- Input oculto para archivos -->
                        <input type="file" class="file-input d-none" multiple>

                        <!-- Progress bar para uploads -->
                        <div class="upload-progress d-none">
                            <div class="progress">
                                <div class="progress-bar" role="progressbar"></div>
                            </div>
                            <small class="upload-status">Subiendo archivo...</small>
                        </div>
                    </div>
                </div>

                <!-- Panel lateral de mentoría (colapsible) -->
                <div class="mentorship-panel d-none">
                    <div class="panel-header">
                        <h5>Herramientas de Mentoría</h5>
                        <button class="btn btn-sm btn-outline-secondary" data-action="close-panel">
                            <i class="fa fa-times"></i>
                        </button>
                    </div>
                    
                    <div class="panel-content">
                        <div class="mentorship-tabs">
                            <ul class="nav nav-tabs" role="tablist">
                                <li class="nav-item">
                                    <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#session-tab">
                                        Sesiones
                                    </button>
                                </li>
                                <li class="nav-item">
                                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#resources-tab">
                                        Recursos
                                    </button>
                                </li>
                                <li class="nav-item">
                                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#assignments-tab">
                                        Tareas
                                    </button>
                                </li>
                                <li class="nav-item">
                                    <button class="nav-link" data-bs-toggle="tab" data-bs-target="#progress-tab">
                                        Progreso
                                    </button>
                                </li>
                            </ul>
                        </div>

                        <div class="tab-content">
                            <div class="tab-pane fade show active" id="session-tab">
                                <div class="session-tools">
                                    <button class="btn btn-primary btn-sm w-100 mb-2" data-action="schedule-session">
                                        <i class="fa fa-calendar-plus me-2"></i>
                                        Programar Sesión
                                    </button>
                                    <div class="upcoming-sessions">
                                        <h6>Próximas Sesiones</h6>
                                        <div class="sessions-list">
                                            <!-- Se cargan dinámicamente -->
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="tab-pane fade" id="resources-tab">
                                <div class="resource-tools">
                                    <button class="btn btn-success btn-sm w-100 mb-2" data-action="share-document">
                                        <i class="fa fa-file-share me-2"></i>
                                        Compartir Documento
                                    </button>
                                    <button class="btn btn-info btn-sm w-100 mb-2" data-action="share-link">
                                        <i class="fa fa-link me-2"></i>
                                        Compartir Enlace
                                    </button>
                                    <div class="shared-resources">
                                        <h6>Recursos Compartidos</h6>
                                        <div class="resources-list">
                                            <!-- Se cargan dinámicamente -->
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="tab-pane fade" id="assignments-tab">
                                <div class="assignment-tools">
                                    <button class="btn btn-warning btn-sm w-100 mb-2" data-action="create-assignment">
                                        <i class="fa fa-tasks me-2"></i>
                                        Crear Tarea
                                    </button>
                                    <div class="assignments-list">
                                        <h6>Tareas Activas</h6>
                                        <!-- Se cargan dinámicamente -->
                                    </div>
                                </div>
                            </div>

                            <div class="tab-pane fade" id="progress-tab">
                                <div class="progress-tools">
                                    <div class="mentee-progress">
                                        <h6>Progreso del Mentee</h6>
                                        <div class="progress-metrics">
                                            <!-- Se cargan dinámicamente -->
                                        </div>
                                    </div>
                                    <button class="btn btn-primary btn-sm w-100 mt-2" data-action="generate-report">
                                        <i class="fa fa-chart-line me-2"></i>
                                        Generar Reporte
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
  }

  /**
     * Configurar manejadores de eventos
     */
  setupEventHandlers () {
    // Eventos de entrada de mensaje
    this.elements.messageInput.addEventListener('input', (e) => {
      this.handleInputChange(e)
    })

    this.elements.messageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        this.sendMessage()
      }
    })

    // Botón de envío
    this.elements.sendButton.addEventListener('click', () => {
      this.sendMessage()
    })

    // Adjuntar archivo
    this.container.addEventListener('click', (e) => {
      if (e.target.matches('[data-action="attach-file"]')) {
        this.elements.fileInput.click()
      }
    })

    this.elements.fileInput.addEventListener('change', (e) => {
      this.handleFileSelection(e)
    })

    // Búsqueda
    this.elements.searchInput?.addEventListener('input', this.debounce((e) => {
      this.performSearch(e.target.value)
    }, 300))

    // Eventos de conversación
    this.elements.conversationsList.addEventListener('click', (e) => {
      const conversationItem = e.target.closest('.conversation-item')
      if (conversationItem) {
        const conversationId = conversationItem.dataset.conversationId
        this.selectConversation(conversationId)
      }
    })

    // Eventos de mentoría
    this.container.addEventListener('click', (e) => {
      const action = e.target.closest('[data-action]')?.dataset.action
      if (action) {
        this.handleAction(action, e)
      }
    })

    // Scroll para cargar más mensajes
    this.elements.messagesContainer.addEventListener('scroll', (e) => {
      if (e.target.scrollTop === 0) {
        this.loadMoreMessages()
      }
    })

    // Eventos de estado de ventana
    window.addEventListener('focus', () => {
      this.markMessagesAsRead()
    })

    window.addEventListener('blur', () => {
      this.stopTypingIndicator()
    })
  }

  /**
     * Configurar WebSocket para tiempo real
     */
  setupWebSocket () {
    if (!this.main.websocket) {
      console.warn('WebSocket no disponible')
      return
    }

    // Escuchar eventos de mensajes
    this.main.events.addEventListener('websocket:message', (e) => {
      this.handleIncomingMessage(e.detail)
    })

    // Escuchar indicadores de escritura
    this.main.events.addEventListener('websocket:typing', (e) => {
      this.handleTypingIndicator(e.detail)
    })

    // Escuchar estado de usuarios
    this.main.events.addEventListener('websocket:user_status', (e) => {
      this.handleUserStatusChange(e.detail)
    })

    // Escuchar confirmaciones de lectura
    this.main.events.addEventListener('websocket:message_read', (e) => {
      this.handleMessageRead(e.detail)
    })
  }

  /**
     * Cargar datos iniciales
     */
  async loadInitialData () {
    try {
      // Cargar conversaciones
      await this.loadConversations()

      // Cargar usuarios online
      await this.loadOnlineUsers()

      // Si hay una conversación seleccionada, cargarla
      const lastConversationId = this.main.storage.get('lastConversationId')
      if (lastConversationId) {
        await this.selectConversation(lastConversationId)
      }
    } catch (error) {
      console.error('Error cargando datos iniciales:', error)
    }
  }

  /**
     * Cargar conversaciones
     */
  async loadConversations () {
    try {
      const conversations = await this.main.http.get('/messenger/conversations')

      this.moduleState.conversations.clear()
      conversations.forEach(conv => {
        this.moduleState.conversations.set(conv.id, conv)
      })

      this.renderConversations()
    } catch (error) {
      console.error('Error cargando conversaciones:', error)
    }
  }

  /**
     * Renderizar lista de conversaciones
     */
  renderConversations () {
    const conversations = Array.from(this.moduleState.conversations.values())

    const html = conversations.map(conv => this.getConversationItemTemplate(conv)).join('')

    this.elements.conversationsList.innerHTML = html || `
            <div class="no-conversations">
                <p class="text-muted">No hay conversaciones aún</p>
                <button class="btn btn-primary btn-sm" data-action="new-conversation">
                    <i class="fa fa-plus me-2"></i>
                    Nueva Conversación
                </button>
            </div>
        `
  }

  /**
     * Template para item de conversación
     */
  getConversationItemTemplate (conversation) {
    const unreadCount = this.moduleState.unreadCounts.get(conversation.id) || 0
    const isOnline = this.moduleState.onlineUsers.has(conversation.participants[0]?.id)
    const lastMessage = conversation.lastMessage

    return `
            <div class="conversation-item ${conversation.id === this.moduleState.currentConversation?.id ? 'active' : ''}"
                 data-conversation-id="${conversation.id}">
                <div class="conversation-avatar">
                    <img src="${conversation.participants[0]?.avatar || '/static/img/default-avatar.png'}" 
                         alt="${conversation.participants[0]?.name}" class="avatar-img">
                    <span class="status-indicator ${isOnline ? 'online' : 'offline'}"></span>
                </div>
                
                <div class="conversation-info">
                    <div class="conversation-header">
                        <h6 class="conversation-name">${conversation.participants[0]?.name || 'Usuario'}</h6>
                        <span class="conversation-time">${this.formatTime(lastMessage?.timestamp)}</span>
                    </div>
                    
                    <div class="conversation-preview">
                        <p class="last-message">
                            ${lastMessage?.type === 'file'
                                ? `<i class="fa fa-paperclip"></i> ${lastMessage.fileName}`
                                : this.truncateText(lastMessage?.content || 'Sin mensajes', 50)
                            }
                        </p>
                        ${unreadCount > 0 ? `<span class="unread-count">${unreadCount}</span>` : ''}
                    </div>
                </div>

                <div class="conversation-meta">
                    <div class="conversation-type">
                        <i class="fa fa-${conversation.type === 'mentorship' ? 'graduation-cap' : 'comment'}" 
                           title="${conversation.type === 'mentorship' ? 'Sesión de Mentoría' : 'Conversación'}"></i>
                    </div>
                </div>
            </div>
        `
  }

  /**
     * Seleccionar conversación
     */
  async selectConversation (conversationId) {
    try {
      const conversation = this.moduleState.conversations.get(conversationId)
      if (!conversation) {
        throw new Error('Conversación no encontrada')
      }

      this.moduleState.currentConversation = conversation

      // Guardar en storage
      this.main.storage.set('lastConversationId', conversationId)

      // Actualizar UI
      this.updateChatHeader(conversation)
      this.showNoConversationPlaceholder(false)

      // Cargar mensajes
      await this.loadMessages(conversationId)

      // Marcar como leído
      this.markMessagesAsRead()

      // Actualizar conversaciones activas
      this.renderConversations()

      // Cargar información de mentoría si aplica
      if (conversation.type === 'mentorship') {
        this.loadMentorshipData(conversationId)
      }
    } catch (error) {
      console.error('Error seleccionando conversación:', error)
      this.showError('Error al cargar la conversación')
    }
  }

  /**
     * Cargar mensajes de una conversación
     */
  async loadMessages (conversationId, page = 1) {
    try {
      const response = await this.main.http.get(`/messenger/conversations/${conversationId}/messages`, {
        params: { page, limit: this.options.messagesPerPage }
      })

      const messages = response.messages || []

      // Agregar mensajes al estado
      if (!this.moduleState.messages.has(conversationId)) {
        this.moduleState.messages.set(conversationId, [])
      }

      const existingMessages = this.moduleState.messages.get(conversationId)

      if (page === 1) {
        // Reemplazar mensajes existentes
        this.moduleState.messages.set(conversationId, messages)
      } else {
        // Agregar mensajes más antiguos al inicio
        existingMessages.unshift(...messages)
      }

      // Renderizar mensajes
      this.renderMessages()

      // Scroll automático si es página 1
      if (page === 1) {
        this.scrollToBottom()
      }

      return response
    } catch (error) {
      console.error('Error cargando mensajes:', error)
      throw error
    }
  }

  /**
     * Renderizar mensajes
     */
  renderMessages () {
    if (!this.moduleState.currentConversation) return

    const conversationId = this.moduleState.currentConversation.id
    const messages = this.moduleState.messages.get(conversationId) || []

    if (messages.length === 0) {
      this.elements.messagesList.innerHTML = `
                <div class="no-messages">
                    <div class="no-messages-content">
                        <i class="fa fa-comment-dots fa-2x text-muted"></i>
                        <p class="text-muted">No hay mensajes en esta conversación</p>
                        <small class="text-muted">Envía el primer mensaje para comenzar</small>
                    </div>
                </div>
            `
      return
    }

    const groupedMessages = this.groupMessagesByDate(messages)
    let html = ''

    for (const [date, dayMessages] of groupedMessages) {
      html += `<div class="date-separator">${this.formatDate(date)}</div>`

      for (let i = 0; i < dayMessages.length; i++) {
        const message = dayMessages[i]
        const prevMessage = dayMessages[i - 1]
        const nextMessage = dayMessages[i + 1]

        const isFirstInGroup = !prevMessage || prevMessage.senderId !== message.senderId ||
                    (new Date(message.timestamp) - new Date(prevMessage.timestamp)) > 300000 // 5 minutos

        const isLastInGroup = !nextMessage || nextMessage.senderId !== message.senderId ||
                    (new Date(nextMessage.timestamp) - new Date(message.timestamp)) > 300000

        html += this.getMessageTemplate(message, isFirstInGroup, isLastInGroup)
      }
    }

    this.elements.messagesList.innerHTML = html
  }

  /**
     * Template para mensaje
     */
  getMessageTemplate (message, isFirstInGroup, isLastInGroup) {
    const currentUserId = this.main.currentUser?.id
    const isOwn = message.senderId === currentUserId
    const sender = message.sender || { name: 'Usuario' }

    return `
            <div class="message-wrapper ${isOwn ? 'own' : 'other'}" data-message-id="${message.id}">
                ${!isOwn && isFirstInGroup
? `
                    <div class="message-sender">
                        <img src="${sender.avatar || '/static/img/default-avatar.png'}" 
                             alt="${sender.name}" class="sender-avatar">
                        <span class="sender-name">${sender.name}</span>
                    </div>
                `
: ''}
                
                <div class="message-content ${isFirstInGroup ? 'first-in-group' : ''} ${isLastInGroup ? 'last-in-group' : ''}">
                    ${message.replyTo ? this.getReplyTemplate(message.replyTo) : ''}
                    
                    <div class="message-body">
                        ${this.getMessageContentByType(message)}
                    </div>
                    
                    <div class="message-meta">
                        <span class="message-time">${this.formatTime(message.timestamp)}</span>
                        ${isOwn ? this.getMessageStatusIcon(message.status) : ''}
                        ${message.edited ? '<i class="fa fa-edit text-muted" title="Editado"></i>' : ''}
                    </div>
                    
                    ${this.options.enableMessageReactions ? this.getReactionsTemplate(message.reactions) : ''}
                </div>
                
                <div class="message-actions">
                    <button class="btn btn-sm btn-outline-secondary" data-action="reply" 
                            title="Responder">
                        <i class="fa fa-reply"></i>
                    </button>
                    ${isOwn
? `
                        <button class="btn btn-sm btn-outline-secondary" data-action="edit" 
                                title="Editar">
                            <i class="fa fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" data-action="delete" 
                                title="Eliminar">
                            <i class="fa fa-trash"></i>
                        </button>
                    `
: ''}
                    <button class="btn btn-sm btn-outline-secondary" data-action="react" 
                            title="Reaccionar">
                        <i class="fa fa-smile"></i>
                    </button>
                </div>
            </div>
        `
  }

  /**
     * Obtener contenido del mensaje según su tipo
     */
  getMessageContentByType (message) {
    switch (message.type) {
      case 'text':
        return `<p class="message-text">${this.formatMessageText(message.content)}</p>`

      case 'file':
        return this.getFileMessageTemplate(message)

      case 'meeting':
        return this.getMeetingMessageTemplate(message)

      case 'assignment':
        return this.getAssignmentMessageTemplate(message)

      case 'resource':
        return this.getResourceMessageTemplate(message)

      case 'system':
        return `<div class="system-message">${message.content}</div>`

      default:
        return `<p class="message-text">${message.content}</p>`
    }
  }

  /**
     * Template para mensaje de archivo
     */
  getFileMessageTemplate (message) {
    const file = message.file
    const isImage = file.type.startsWith('image/')

    return `
            <div class="file-message">
                ${isImage
? `
                    <div class="image-preview">
                        <img src="${file.url}" alt="${file.name}" class="message-image" 
                             onclick="this.classList.toggle('expanded')">
                    </div>
                `
: `
                    <div class="file-info">
                        <div class="file-icon">
                            <i class="fa fa-${this.getFileIcon(file.type)}"></i>
                        </div>
                        <div class="file-details">
                            <div class="file-name">${file.name}</div>
                            <div class="file-size">${this.formatFileSize(file.size)}</div>
                        </div>
                        <a href="${file.url}" download="${file.name}" 
                           class="btn btn-sm btn-outline-primary">
                            <i class="fa fa-download"></i>
                        </a>
                    </div>
                `}
                ${message.content ? `<p class="file-caption">${message.content}</p>` : ''}
            </div>
        `
  }

  /**
     * Template para mensaje de reunión
     */
  getMeetingMessageTemplate (message) {
    const meeting = message.meeting
    return `
            <div class="meeting-message">
                <div class="meeting-header">
                    <i class="fa fa-calendar-alt"></i>
                    <h6>Reunión Programada</h6>
                </div>
                <div class="meeting-details">
                    <div class="meeting-title">${meeting.title}</div>
                    <div class="meeting-time">
                        <i class="fa fa-clock"></i>
                        ${this.formatDateTime(meeting.startTime)}
                    </div>
                    <div class="meeting-duration">
                        <i class="fa fa-hourglass-half"></i>
                        ${meeting.duration} minutos
                    </div>
                </div>
                <div class="meeting-actions">
                    <a href="${meeting.joinUrl}" class="btn btn-sm btn-primary" target="_blank">
                        <i class="fa fa-video"></i> Unirse
                    </a>
                    <button class="btn btn-sm btn-outline-secondary" data-action="add-to-calendar">
                        <i class="fa fa-calendar-plus"></i> Agregar al calendario
                    </button>
                </div>
            </div>
        `
  }

  /**
     * Template para mensaje de tarea
     */
  getAssignmentMessageTemplate (message) {
    const assignment = message.assignment
    return `
            <div class="assignment-message">
                <div class="assignment-header">
                    <i class="fa fa-tasks"></i>
                    <h6>Nueva Tarea Asignada</h6>
                </div>
                <div class="assignment-details">
                    <div class="assignment-title">${assignment.title}</div>
                    <div class="assignment-description">${assignment.description}</div>
                    <div class="assignment-due">
                        <i class="fa fa-calendar"></i>
                        Fecha límite: ${this.formatDate(assignment.dueDate)}
                    </div>
                </div>
                <div class="assignment-actions">
                    <button class="btn btn-sm btn-success" data-action="view-assignment" 
                            data-assignment-id="${assignment.id}">
                        <i class="fa fa-eye"></i> Ver Detalles
                    </button>
                </div>
            </div>
        `
  }

  /**
     * Enviar mensaje
     */
  async sendMessage () {
    const content = this.elements.messageInput.value.trim()
    if (!content && this.moduleState.uploadQueue.size === 0) return

    if (!this.moduleState.currentConversation) {
      this.showError('Selecciona una conversación primero')
      return
    }

    try {
      const messageData = {
        conversationId: this.moduleState.currentConversation.id,
        content,
        type: 'text',
        replyTo: this.moduleState.replyToMessage?.id || null
      }

      // Si hay archivos en cola, enviarlos primero
      if (this.moduleState.uploadQueue.size > 0) {
        await this.processFileUploads()
      }

      // Crear mensaje temporal en UI
      const tempMessage = {
        id: 'temp_' + Date.now(),
        content,
        type: 'text',
        senderId: this.main.currentUser.id,
        sender: this.main.currentUser,
        timestamp: new Date().toISOString(),
        status: 'sending',
        replyTo: this.moduleState.replyToMessage
      }

      this.addMessageToUI(tempMessage)
      this.clearMessageInput()

      // Enviar mensaje al servidor
      const response = await this.main.http.post('/messenger/messages', messageData)

      // Actualizar mensaje en UI con respuesta del servidor
      this.updateMessageInUI(tempMessage.id, response)

      // Enviar por WebSocket para tiempo real
      if (this.options.enableRealTime) {
        this.main.websocket.send('message', response)
      }

      // Scroll automático
      this.scrollToBottom()
    } catch (error) {
      console.error('Error enviando mensaje:', error)
      this.showError('Error al enviar el mensaje')
    }
  }

  /**
     * Manejar mensaje entrante
     */
  handleIncomingMessage (messageData) {
    const { message, conversationId } = messageData

    // Agregar mensaje al estado
    if (!this.moduleState.messages.has(conversationId)) {
      this.moduleState.messages.set(conversationId, [])
    }

    this.moduleState.messages.get(conversationId).push(message)

    // Si es la conversación actual, actualizar UI
    if (this.moduleState.currentConversation?.id === conversationId) {
      this.addMessageToUI(message)
      this.scrollToBottom()

      // Marcar como leído si la ventana está enfocada
      if (document.hasFocus()) {
        this.markMessageAsRead(message.id)
      }
    } else {
      // Incrementar contador de no leídos
      const currentCount = this.moduleState.unreadCounts.get(conversationId) || 0
      this.moduleState.unreadCounts.set(conversationId, currentCount + 1)

      // Actualizar conversaciones
      this.renderConversations()

      // Mostrar notificación
      this.showMessageNotification(message)
    }

    // Actualizar última conversación
    this.updateLastMessage(conversationId, message)
  }

  /**
     * Configurar herramientas de mentoría
     */
  setupMentorshipFeatures () {
    // Solo disponible para mentores
    if (this.main.userType !== 'mentor') {
      this.container.querySelectorAll('.mentorship-panel, .mentorship-quick-panel')
        .forEach(el => el.style.display = 'none')
      return
    }

    // Configurar plantillas rápidas para mentores
    this.setupQuickTemplates()

    // Configurar herramientas de sesión
    this.setupSessionTools()
  }

  /**
     * Configurar plantillas rápidas
     */
  setupQuickTemplates () {
    this.templates = {
      greeting: '¡Hola! Espero que estés teniendo un buen día. ¿En qué puedo ayudarte hoy?',
      sessionReminder: 'Te recuerdo que tenemos una sesión programada para mañana a las {time}. ¿Te viene bien?',
      feedback: 'Me gustaría conocer tu opinión sobre la sesión de hoy. ¿Qué te pareció más útil?',
      resources: 'Te comparto algunos recursos que creo que te serán útiles para tu proyecto:',
      followup: '¿Cómo vas con las tareas que discutimos en nuestra última sesión?',
      encouragement: '¡Excelente progreso! Sigue así, estás en el camino correcto.'
    }
  }

  /**
     * Manejar acciones del módulo
     */
  async handleAction (action, event) {
    const element = event.target.closest('[data-action]')

    switch (action) {
      case 'new-conversation':
        await this.showNewConversationModal()
        break

      case 'schedule-session':
        await this.scheduleSession()
        break

      case 'share-resource':
        await this.shareResource()
        break

      case 'create-assignment':
        await this.createAssignment()
        break

      case 'video-call':
        await this.startVideoCall()
        break

      case 'audio-call':
        await this.startAudioCall()
        break

      case 'quick-template':
        this.showQuickTemplates()
        break

      case 'reply':
        this.setReplyToMessage(element)
        break

      case 'edit':
        this.editMessage(element)
        break

      case 'delete':
        await this.deleteMessage(element)
        break

      case 'react':
        this.showReactionPicker(element)
        break

      default:
        console.warn('Acción no reconocida:', action)
    }
  }

  /**
     * Programar sesión de mentoría
     */
  async scheduleSession () {
    if (!this.moduleState.currentConversation) {
      this.showError('Selecciona una conversación primero')
      return
    }

    try {
      // Mostrar modal de programación
      const modal = await this.showModal('schedule-session', {
        title: 'Programar Sesión de Mentoría',
        content: this.getScheduleSessionModalContent()
      })

      modal.addEventListener('submit', async (e) => {
        e.preventDefault()

        const formData = new FormData(e.target)
        const sessionData = {
          menteeId: this.moduleState.currentConversation.participants[0].id,
          title: formData.get('title'),
          description: formData.get('description'),
          startTime: formData.get('startTime'),
          duration: parseInt(formData.get('duration')),
          type: formData.get('type'),
          platform: formData.get('platform')
        }

        const session = await this.main.http.post('/mentorship/sessions', sessionData)

        // Enviar mensaje con la sesión programada
        await this.sendSessionMessage(session)

        this.hideModal()
        this.showSuccess('Sesión programada correctamente')
      })
    } catch (error) {
      console.error('Error programando sesión:', error)
      this.showError('Error al programar la sesión')
    }
  }

  /**
     * Configurar drag & drop para archivos
     */
  setupFileDragDrop () {
    const dropZone = this.elements.messagesContainer;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault()
        e.stopPropagation()
      })
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.add('drag-over')
      })
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => {
        dropZone.classList.remove('drag-over')
      })
    })

    dropZone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files
      this.handleFileSelection({ target: { files } })
    })
  }

  /**
     * Manejar selección de archivos
     */
  async handleFileSelection (event) {
    const files = Array.from(event.target.files)

    for (const file of files) {
      if (!this.validateFile(file)) continue

      try {
        await this.uploadFile(file)
      } catch (error) {
        console.error('Error subiendo archivo:', error)
        this.showError(`Error subiendo ${file.name}`)
      }
    }

    // Limpiar input
    event.target.value = ''
  }

  /**
     * Validar archivo
     */
  validateFile (file) {
    // Verificar tamaño
    if (file.size > this.options.maxFileSize) {
      this.showError(`El archivo ${file.name} es muy grande. Máximo ${this.formatFileSize(this.options.maxFileSize)}`)
      return false
    }

    // Verificar tipo
    if (!this.options.allowedFileTypes.includes(file.type)) {
      this.showError(`Tipo de archivo no permitido: ${file.type}`)
      return false
    }

    return true
  }

  /**
     * Subir archivo
     */
  async uploadFile (file) {
    const uploadId = this.generateId()

    // Agregar a cola de subida
    this.moduleState.uploadQueue.set(uploadId, {
      file,
      progress: 0,
      status: 'uploading'
    })

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('conversationId', this.moduleState.currentConversation.id)

      // Mostrar progreso
      this.showUploadProgress(uploadId, file.name)

      const response = await this.main.http.post('/messenger/files/upload', formData, {
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          this.updateUploadProgress(uploadId, progress)
        }
      })

      // Enviar mensaje con archivo
      await this.sendFileMessage(response)

      // Remover de cola
      this.moduleState.uploadQueue.delete(uploadId)
      this.hideUploadProgress()
    } catch (error) {
      this.moduleState.uploadQueue.delete(uploadId)
      this.hideUploadProgress()
      throw error
    }
  }

  /**
     * Aplicar tema visual
     */
  applyTheme () {
    const theme = this.options.theme
    const colors = {
      mentor: {
        primary: '#0d9488',
        secondary: '#14b8a6',
        accent: '#5eead4'
      },
      entrepreneur: {
        primary: '#8b5cf6',
        secondary: '#a78bfa',
        accent: '#c4b5fd'
      },
      admin: {
        primary: '#374151',
        secondary: '#4b5563',
        accent: '#6b7280'
      }
    }

    const themeColors = colors[theme] || colors.mentor

    this.container.style.setProperty('--primary-color', themeColors.primary)
    this.container.style.setProperty('--secondary-color', themeColors.secondary)
    this.container.style.setProperty('--accent-color', themeColors.accent)
  }

  /**
     * Utilidades
     */
  formatTime (timestamp) {
    return new Date(timestamp).toLocaleTimeString('es-CO', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  formatDate (date) {
    return new Date(date).toLocaleDateString('es-CO', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  formatFileSize (bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    if (bytes === 0) return '0 Bytes'
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  truncateText (text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
  }

  debounce (func, wait) {
    let timeout
    return function executedFunction (...args) {
      const later = () => {
        clearTimeout(timeout)
        func(...args)
      }
      clearTimeout(timeout)
      timeout = setTimeout(later, wait)
    }
  }

  generateId () {
    return Math.random().toString(36).substr(2, 9)
  }

  scrollToBottom () {
    this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight
  }

  showError (message) {
    this.main.notifications.error(message)
  }

  showSuccess (message) {
    this.main.notifications.success(message)
  }

  /**
     * Destruir módulo
     */
  destroy () {
    // Limpiar timers
    Object.values(this.timers).forEach(timer => {
      if (timer) clearTimeout(timer)
    })

    // Limpiar eventos
    this.handlers.forEach((handler, element) => {
      element.removeEventListener(handler.event, handler.callback)
    })

    // Limpiar estado
    this.moduleState.conversations.clear()
    this.moduleState.messages.clear()
    this.moduleState.uploadQueue.clear()

    console.log('🧹 AllyMessenger destruido')
  }
}

// Exportar módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AllyMessenger
}

// Hacer disponible globalmente
window.AllyMessenger = AllyMessenger
