/**
 * NotificationService.js - Servicio para la Gestión de Notificaciones
 * ===================================================================
 *
 * Maneja la creación, envío, seguimiento y gestión de notificaciones
 * a través de múltiples canales (in-app, email, push, SMS).
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.events, App.config, App.services.user)
 * @requires: WebSocketService (para notificaciones in-app en tiempo real)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que NotificationService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class NotificationService {
  constructor () {
    this.baseEndpoint = '/api/v1/notifications' // Endpoint para notificaciones
    this.preferencesEndpoint = '/api/v1/users/me/notification-preferences' // Endpoint para preferencias
    this.maxInAppNotifications = App.config.MAX_IN_APP_NOTIFICATIONS || 100
    this.inAppNotifications = [] // Almacén local para notificaciones in-app
    this.unreadCount = 0

    this._initialize()
  }

  /**
     * Inicializa el servicio, cargando notificaciones y preferencias.
     * @private
     */
  async _initialize () {
    if (App.services.auth && App.services.auth.check()) {
      await this.fetchUserPreferences()
      await this.fetchRecentNotifications()
    }

    // Escuchar eventos de WebSocket para notificaciones en tiempo real
    if (App.services.websocket) {
      App.services.websocket.on('new_notification', (notification) => {
        this.handleRealtimeNotification(notification)
      })
    }

    // Escuchar cambios de autenticación
    App.events.addEventListener('auth:login', () => this._onUserLogin())
    App.events.addEventListener('auth:logout', () => this._onUserLogout())
  }

  /**
     * Acciones a realizar cuando el usuario inicia sesión.
     * @private
     */
  async _onUserLogin () {
    await this.fetchUserPreferences()
    await this.fetchRecentNotifications()
  }

  /**
     * Acciones a realizar cuando el usuario cierra sesión.
     * @private
     */
  _onUserLogout () {
    this.inAppNotifications = []
    this.unreadCount = 0
    App.events.dispatchEvent('notifications:updated', {
      notifications: [],
      unreadCount: 0
    })
  }

  /**
     * Obtiene las preferencias de notificación del usuario.
     * @return {Promise<Object|null>}
     */
  async fetchUserPreferences () {
    if (!App.services.auth || !App.services.auth.check()) return null
    try {
      const preferences = await App.http.get(this.preferencesEndpoint)
      App.config.userNotificationPreferences = preferences // Guardar en config global
      return preferences
    } catch (error) {
      // console.warn('NotificationService: Error al obtener preferencias de notificación.', error)
      return null
    }
  }

  /**
     * Actualiza las preferencias de notificación del usuario.
     * @param {Object} preferences - Nuevas preferencias.
     * @return {Promise<Object|null>}
     */
  async updateUserPreferences (preferences) {
    if (!App.services.auth || !App.services.auth.check()) return null
    try {
      const updatedPreferences = await App.http.put(this.preferencesEndpoint, preferences)
      App.config.userNotificationPreferences = updatedPreferences
      App.notifications.success('Preferencias de notificación actualizadas.')
      return updatedPreferences
    } catch (error) {
      // // console.error('NotificationService: Error al actualizar preferencias.', error)
      App.notifications.error(error.message || 'No se pudieron actualizar las preferencias.')
      return null
    }
  }

  /**
     * Obtiene las notificaciones recientes del usuario.
     * @param {Object} params - Parámetros de paginación y filtrado.
     * @return {Promise<void>}
     */
  async fetchRecentNotifications (params = { limit: 50, unread: true }) {
    if (!App.services.auth || !App.services.auth.check()) return
    try {
      const queryString = new URLSearchParams(params).toString()
      const response = await App.http.get(`${this.baseEndpoint}?${queryString}`)

      this.inAppNotifications = response.notifications || []
      this.unreadCount = response.unread_count || 0

      App.events.dispatchEvent('notifications:loaded', {
        notifications: this.inAppNotifications,
        unreadCount: this.unreadCount
      })
    } catch (error) {
      // console.warn('NotificationService: Error al obtener notificaciones recientes.', error)
    }
  }

  /**
     * Maneja una notificación recibida en tiempo real.
     * @param {Object} notification - La notificación recibida.
     */
  handleRealtimeNotification (notification) {
    // Añadir al principio de la lista
    this.inAppNotifications.unshift(notification)

    // Mantener el límite de notificaciones in-app
    if (this.inAppNotifications.length > this.maxInAppNotifications) {
      this.inAppNotifications.pop()
    }

    if (!notification.read_at) {
      this.unreadCount++
    }

    App.events.dispatchEvent('notifications:new', notification)
    App.events.dispatchEvent('notifications:updated', {
      notifications: this.inAppNotifications,
      unreadCount: this.unreadCount
    })

    // Mostrar notificación visual si es relevante (ej. usando App.notifications.toast)
    if (App.notifications && App.notifications.toast) {
      App.notifications.toast(notification.title, notification.message, 'info', {
        onClick: () => {
          if (notification.action_url) window.location.href = notification.action_url
        }
      })
    }
  }

  /**
     * Marca una notificación como leída.
     * @param {string|number} notificationId - ID de la notificación.
     * @return {Promise<boolean>}
     */
  async markAsRead (notificationId) {
    try {
      await App.http.post(`${this.baseEndpoint}/${notificationId}/read`)

      const index = this.inAppNotifications.findIndex(n => n.id === notificationId)
      if (index !== -1 && !this.inAppNotifications[index].read_at) {
        this.inAppNotifications[index].read_at = new Date().toISOString()
        this.unreadCount = Math.max(0, this.unreadCount - 1)
      }

      App.events.dispatchEvent('notifications:updated', {
        notifications: this.inAppNotifications,
        unreadCount: this.unreadCount
      })
      App.events.dispatchEvent('notifications:read', { notificationId })
      return true
    } catch (error) {
      // // console.error(`NotificationService: Error al marcar notificación ${notificationId} como leída.`, error)
      return false
    }
  }

  /**
     * Marca todas las notificaciones como leídas.
     * @return {Promise<boolean>}
     */
  async markAllAsRead () {
    try {
      await App.http.post(`${this.baseEndpoint}/mark-all-read`)

      this.inAppNotifications.forEach(n => {
        if (!n.read_at) n.read_at = new Date().toISOString()
      })
      this.unreadCount = 0

      App.events.dispatchEvent('notifications:updated', {
        notifications: this.inAppNotifications,
        unreadCount: this.unreadCount
      })
      App.events.dispatchEvent('notifications:all_read')
      return true
    } catch (error) {
      // // console.error('NotificationService: Error al marcar todas las notificaciones como leídas.', error)
      return false
    }
  }

  /**
     * Elimina una notificación.
     * @param {string|number} notificationId - ID de la notificación.
     * @return {Promise<boolean>}
     */
  async deleteNotification (notificationId) {
    try {
      await App.http.delete(`${this.baseEndpoint}/${notificationId}`)

      const index = this.inAppNotifications.findIndex(n => n.id === notificationId)
      if (index !== -1) {
        const removedNotification = this.inAppNotifications.splice(index, 1)[0]
        if (!removedNotification.read_at) {
          this.unreadCount = Math.max(0, this.unreadCount - 1)
        }
      }

      App.events.dispatchEvent('notifications:updated', {
        notifications: this.inAppNotifications,
        unreadCount: this.unreadCount
      })
      App.events.dispatchEvent('notifications:deleted', { notificationId })
      return true
    } catch (error) {
      // // console.error(`NotificationService: Error al eliminar notificación ${notificationId}.`, error)
      return false
    }
  }

  /**
     * Obtiene las notificaciones in-app actuales.
     * @return {Array<Object>}
     */
  getInAppNotifications () {
    return this.inAppNotifications
  }

  /**
     * Obtiene el contador de notificaciones no leídas.
     * @return {number}
     */
  getUnreadCount () {
    return this.unreadCount
  }

  /**
     * Solicita permiso para notificaciones push del navegador.
     * @return {Promise<string>} - 'granted', 'denied', o 'default'.
     */
  async requestPushPermission () {
    if (!('Notification' in window)) {
      // console.warn('Este navegador no soporta notificaciones de escritorio.')
      return 'unsupported'
    }

    if (Notification.permission === 'granted') {
      return 'granted'
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission()
      if (permission === 'granted') {
        this._subscribeToPushService()
      }
      return permission
    }
    return 'denied'
  }

  /**
     * Suscribe el cliente al servicio de push notifications del backend.
     * @private
     */
  async _subscribeToPushService () {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      // console.warn('Push messaging no soportado.')
      return
    }

    try {
      const registration = await navigator.serviceWorker.ready
      let subscription = await registration.pushManager.getSubscription()

      if (subscription === null) {
        // Obtener VAPID public key del backend o config
        const vapidPublicKey = App.config.VAPID_PUBLIC_KEY
        if (!vapidPublicKey) {
          // // console.error('VAPID public key no configurada.')
          return
        }

        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: this._urlBase64ToUint8Array(vapidPublicKey)
        })
      }

      // Enviar suscripción al backend
      await App.http.post(`${this.baseEndpoint}/subscribe-push`, subscription.toJSON())
      // // console.log('Suscrito a notificaciones push.')
    } catch (error) {
      // // console.error('Error al suscribirse a notificaciones push:', error)
    }
  }

  /**
     * Helper para convertir VAPID key.
     * @private
     */
  _urlBase64ToUint8Array (base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4)
    const base64 = (base64String + padding)
      .replace(/\-/g, '+')
      .replace(/_/g, '/')

    const rawData = window.atob(base64)
    const outputArray = new Uint8Array(rawData.length)

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i)
    }
    return outputArray
  }
}

// Registrar el servicio en la instancia global de la App
App.services.notification = new NotificationService()
