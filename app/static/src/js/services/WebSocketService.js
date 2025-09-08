/**
 * WebSocketService.js - Servicio para Comunicación en Tiempo Real
 * ===============================================================
 *
 * Maneja la conexión WebSocket, envío y recepción de mensajes,
 * y la gestión de eventos en tiempo real para la aplicación.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.config, App.events, App.services.auth)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que WebSocketService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class WebSocketService {
  constructor () {
    this.socket = null
    this.url = this._buildWebSocketUrl()
    this.isConnected = false
    this.eventListeners = new Map() // Almacena callbacks para eventos específicos
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = App.config.WS_MAX_RECONNECT_ATTEMPTS || 5
    this.reconnectInterval = App.config.WS_RECONNECT_INTERVAL || 5000 // 5 segundos
    this.pingInterval = App.config.WS_PING_INTERVAL || 30000 // 30 segundos
    this.pingTimeoutId = null // ID del intervalo de ping
    this.pongTimeoutId = null // ID del timeout para esperar pong
    this.pongWaitDuration = App.config.WS_PONG_WAIT_DURATION || 5000 // 5 segundos para esperar pong

    // Auto-conectar si el usuario está autenticado y el servicio está habilitado
    if (App.config.WEBSOCKET_ENABLED !== false) {
      if (App.services.auth && App.services.auth.check()) {
        this.connect()
      }

      // Escuchar eventos de autenticación para conectar/desconectar
      App.events.addEventListener('auth:login', () => this.connect())
      App.events.addEventListener('auth:logout', () => this.disconnect())
    } else {
      console.info('WebSocketService: El servicio WebSocket está deshabilitado en la configuración.')
    }
  }

  /**
     * Construye la URL del WebSocket.
     * @private
     */
  _buildWebSocketUrl () {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = App.config.WS_HOST || window.location.host
    const wsPath = App.config.WS_PATH || '/ws' // Asegúrate que este path exista en tu backend
    return `${wsProtocol}//${wsHost}${wsPath}`
  }

  /**
     * Establece la conexión WebSocket.
     */
  connect () {
    if (App.config.WEBSOCKET_ENABLED === false) {
      console.info('WebSocketService: Intento de conexión abortado, WebSocket deshabilitado.')
      return
    }

    if (this.isConnected || (this.socket && this.socket.readyState === WebSocket.CONNECTING)) {
      console.warn('WebSocketService: Ya conectado o intentando conectar.')
      return
    }

    // Verificar autenticación antes de conectar
    const token = App.services.auth ? App.services.auth.getToken() : null
    if (!token && App.config.WS_REQUIRE_AUTH !== false) {
      console.warn('WebSocketService: Autenticación requerida para WebSocket, pero no hay token.')
      // Podrías decidir no conectar o intentar una conexión anónima si tu backend lo soporta.
      return
    }

    // Añadir token a la URL si es necesario (o enviarlo después de conectar)
    // Es más seguro enviar el token en un mensaje después de la conexión si el protocolo lo permite.
    const urlWithParams = new URL(this.url)
    if (token && App.config.WS_SEND_TOKEN_IN_URL) {
      urlWithParams.searchParams.append('token', token)
    }
    // Podrías añadir otros parámetros como `client_version`, `user_id`, etc.
    // urlWithParams.searchParams.append('clientVersion', App.config.VERSION);

    console.log(`WebSocketService: Conectando a ${urlWithParams.toString()}...`)
    this.socket = new WebSocket(urlWithParams.toString())

    this.socket.onopen = (event) => this._handleOpen(event)
    this.socket.onmessage = (event) => this._handleMessage(event)
    this.socket.onerror = (event) => this._handleError(event)
    this.socket.onclose = (event) => this._handleClose(event)
  }

  /**
     * Cierra la conexión WebSocket.
     * @param {number} code - Código de cierre.
     * @param {string} reason - Razón del cierre.
     */
  disconnect (code = 1000, reason = 'Cierre manual por el cliente') {
    if (this.socket) {
      console.log(`WebSocketService: Desconectando con código ${code} y razón "${reason}"...`)
      this.socket.close(code, reason)
      this._clearTimers() // Limpiar timers de ping/pong
    }
    // El resto de la limpieza se maneja en _handleClose
  }

  /**
     * Maneja la apertura de la conexión.
     * @private
     */
  _handleOpen (event) {
    console.log('WebSocketService: Conexión establecida.')
    this.isConnected = true
    this.reconnectAttempts = 0 // Resetear intentos de reconexión
    App.events.dispatchEvent('websocket:connected', event)
    this._startPingPong()

    // Opcional: Enviar un mensaje de autenticación/handshake si no se envía el token en la URL
    // if (token && !App.config.WS_SEND_TOKEN_IN_URL) {
    //     this.send('authenticate', { token: token });
    // }
  }

  /**
     * Maneja los mensajes entrantes.
     * @private
     */
  _handleMessage (event) {
    try {
      const message = JSON.parse(event.data)
      // console.debug('WebSocketService: Mensaje recibido:', message);

      if (message.type === 'pong') {
        this._handlePong()
        return
      }

      // Despachar evento global de la aplicación
      // El nombre del evento podría venir en `message.event` o `message.type`
      const eventName = message.event || message.type || 'message'
      App.events.dispatchEvent(`websocket:${eventName}`, message.data || message)

      // Despachar a listeners específicos registrados
      if (this.eventListeners.has(eventName)) {
        this.eventListeners.get(eventName).forEach(callback => {
          try {
            callback(message.data || message)
          } catch (e) {
            console.error(`WebSocketService: Error en callback para evento '${eventName}':`, e)
          }
        })
      }
    } catch (error) {
      console.error('WebSocketService: Error procesando mensaje:', error, 'Data:', event.data)
    }
  }

  /**
     * Maneja los errores de WebSocket.
     * @private
     */
  _handleError (event) {
    console.error('WebSocketService: Error en WebSocket:', event)
    App.events.dispatchEvent('websocket:error', event)
    // El evento 'close' se disparará después, manejando la reconexión allí si es necesario.
  }

  /**
     * Maneja el cierre de la conexión.
     * @private
     */
  _handleClose (event) {
    console.log(`WebSocketService: Conexión cerrada. Código: ${event.code}, Razón: "${event.reason}", Limpio: ${event.wasClean}`)
    this.isConnected = false
    this.socket = null // Liberar la referencia al socket
    this._clearTimers()
    App.events.dispatchEvent('websocket:disconnected', event)

    // Intentar reconectar si no fue un cierre intencional (código 1000) o por logout
    // y si la reconexión está habilitada en la config.
    if (event.code !== 1000 && App.config.WS_AUTO_RECONNECT !== false) {
      this._reconnect()
    }
  }

  /**
     * Intenta reconectar al WebSocket con backoff exponencial.
     * @private
     */
  _reconnect () {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      // Backoff exponencial: 1*interval, 2*interval, 4*interval, ...
      const delay = Math.min(
        this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
        App.config.WS_MAX_RECONNECT_DELAY || 60000 // Max delay de 60s
      )
      console.log(`WebSocketService: Intento de reconexión ${this.reconnectAttempts}/${this.maxReconnectAttempts} en ${delay / 1000}s...`)
      setTimeout(() => {
        // Solo intentar reconectar si no estamos ya conectados o conectando
        if (!this.isConnected && (!this.socket || this.socket.readyState === WebSocket.CLOSED)) {
          this.connect()
        }
      }, delay)
    } else {
      console.error('WebSocketService: Máximo de intentos de reconexión alcanzado.')
      App.events.dispatchEvent('websocket:reconnect_failed')
    }
  }

  /**
     * Inicia el mecanismo de ping-pong para mantener viva la conexión.
     * @private
     */
  _startPingPong () {
    this._clearTimers() // Limpiar timers existentes

    this.pingTimeoutId = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        try {
          this.socket.send(JSON.stringify({ type: 'ping' }))
          // console.debug('WebSocketService: Ping enviado.');

          // Esperar pong
          this.pongTimeoutId = setTimeout(() => {
            console.warn('WebSocketService: No se recibió pong, la conexión podría estar muerta. Terminando...')
            this.socket.close(1001, 'Pong timeout') // 1001: Going Away (indica que el endpoint se va)
          }, this.pongWaitDuration)
        } catch (error) {
          console.error('WebSocketService: Error enviando ping:', error)
          // Si falla el envío del ping, la conexión probablemente esté mal, cerramos.
          this.socket.close(1001, 'Error enviando ping')
        }
      } else {
        // Si el socket ya no está abierto, detener el ping.
        this._clearTimers()
      }
    }, this.pingInterval)
  }

  /**
     * Maneja la recepción de un mensaje pong.
     * @private
     */
  _handlePong () {
    // console.debug('WebSocketService: Pong recibido.');
    if (this.pongTimeoutId) {
      clearTimeout(this.pongTimeoutId)
      this.pongTimeoutId = null
    }
  }

  /**
     * Limpia los timers de ping y pong.
     * @private
     */
  _clearTimers () {
    if (this.pingTimeoutId) {
      clearInterval(this.pingTimeoutId)
      this.pingTimeoutId = null
    }
    if (this.pongTimeoutId) {
      clearTimeout(this.pongTimeoutId)
      this.pongTimeoutId = null
    }
  }

  /**
     * Envía un mensaje al servidor WebSocket.
     * @param {string} event - Nombre del evento/tipo de mensaje.
     * @param {Object} data - Datos a enviar.
     * @return {boolean} - True si el mensaje fue enviado (o encolado), false si no.
     */
  send (event, data = {}) {
    if (!this.isConnected || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn('WebSocketService: No conectado. Mensaje no enviado:', { event, data })
      return false
    }
    try {
      const message = JSON.stringify({ event, data })
      this.socket.send(message)
      // console.debug('WebSocketService: Mensaje enviado:', { event, data });
      return true
    } catch (error) {
      console.error('WebSocketService: Error enviando mensaje:', error)
      return false
    }
  }

  /**
     * Registra un callback para un evento específico del servidor.
     * @param {string} eventName - Nombre del evento a escuchar.
     * @param {Function} callback - Función a ejecutar cuando el evento ocurra.
     */
  on (eventName, callback) {
    if (typeof callback !== 'function') {
      console.error('WebSocketService: El callback debe ser una función.')
      return
    }
    if (!this.eventListeners.has(eventName)) {
      this.eventListeners.set(eventName, [])
    }
    const listeners = this.eventListeners.get(eventName)
    if (!listeners.includes(callback)) {
      listeners.push(callback)
    }
  }

  /**
     * Elimina un callback para un evento específico.
     * @param {string} eventName - Nombre del evento.
     * @param {Function} callback - Función a eliminar. Si no se provee, elimina todos los listeners para ese evento.
     */
  off (eventName, callback) {
    if (!this.eventListeners.has(eventName)) {
      return
    }
    if (callback) {
      const listeners = this.eventListeners.get(eventName)
      const index = listeners.indexOf(callback)
      if (index > -1) {
        listeners.splice(index, 1)
      }
      if (listeners.length === 0) {
        this.eventListeners.delete(eventName)
      }
    } else {
      // Eliminar todos los listeners para este evento
      this.eventListeners.delete(eventName)
    }
  }

  /**
     * Verifica si el WebSocket está conectado y listo para enviar/recibir.
     * @return {boolean}
     */
  checkConnection () {
    return this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN
  }
}

// Registrar el servicio en la instancia global de la App
// Esto asume que App.services es un objeto donde se registran los servicios.
if (App && App.services) {
  App.services.websocket = new WebSocketService()
} else {
  console.warn('App.services no está definido. WebSocketService no se pudo registrar globalmente.')
  // Podrías optar por exportar la clase o una instancia si no hay un objeto App global.
  // export default new WebSocketService();
}
