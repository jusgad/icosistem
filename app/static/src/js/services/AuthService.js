/**
 * AuthService.js - Servicio de Autenticación y Gestión de Sesiones
 * =================================================================
 *
 * Maneja el login, logout, registro, verificación de tokens,
 * recuperación de contraseñas y el estado de la sesión del usuario.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.events, App.config, etc.)
 * @requires: UserService.js (para interactuar con datos de usuario)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que AuthService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class AuthService {
  constructor () {
    this.authEndpoint = '/api/v1/auth' // Endpoint base para autenticación
    this.tokenKey = App.config.TOKEN_STORAGE_KEY || 'authToken'
    this.userKey = App.config.USER_STORAGE_KEY || 'currentUser'
    this.isAuthenticated = false
    this.currentUser = null

    this._initialize()
  }

  /**
     * Inicializa el servicio, cargando el estado de autenticación.
     * @private
     */
  _initialize () {
    const token = this.getToken()
    if (token) {
      // Aquí podrías validar el token con el backend si es necesario
      // Por ahora, asumimos que si hay token, está autenticado.
      // En una app real, se haría una petición a /api/v1/auth/me
      const storedUser = localStorage.getItem(this.userKey)
      if (storedUser) {
        try {
          this.currentUser = JSON.parse(storedUser)
          this.isAuthenticated = true
          App.services.user.currentUser = this.currentUser // Sincronizar con UserService
          App.events.dispatchEvent('auth:login', this.currentUser)
        } catch (e) {
          console.error('AuthService: Error parsing stored user data.', e)
          this.logout() // Limpiar si los datos son corruptos
        }
      } else {
        // Si hay token pero no usuario, intentar obtenerlo
        this.fetchCurrentUser().catch(() => this.logout())
      }
    } else {
      this.isAuthenticated = false
      this.currentUser = null
      App.events.dispatchEvent('auth:logout')
    }
  }

  /**
     * Inicia sesión del usuario.
     * @param {string} email - Email del usuario.
     * @param {string} password - Contraseña del usuario.
     * @param {boolean} rememberMe - Si se debe recordar la sesión.
     * @return {Promise<Object>} Datos del usuario autenticado.
     */
  async login (email, password, rememberMe = false) {
    try {
      const response = await App.http.post(`${this.authEndpoint}/login`, {
        email,
        password,
        remember_me: rememberMe
      })

      if (response.access_token && response.user) {
        this.setToken(response.access_token, rememberMe)
        this.setCurrentUser(response.user)
        this.isAuthenticated = true
        App.services.user.currentUser = response.user // Sincronizar con UserService
        App.events.dispatchEvent('auth:login', response.user)
        return response.user
      } else {
        throw new Error(response.message || 'Respuesta de login inválida.')
      }
    } catch (error) {
      console.error('AuthService: Error en login:', error)
      App.events.dispatchEvent('auth:login_failed', error)
      throw error
    }
  }

  /**
     * Cierra la sesión del usuario.
     * @return {Promise<void>}
     */
  async logout () {
    try {
      // Opcional: notificar al backend sobre el logout
      await App.http.post(`${this.authEndpoint}/logout`)
    } catch (error) {
      // Ignorar errores de logout del backend, ya que el cliente debe cerrar sesión de todas formas
      console.warn('AuthService: Error notificando logout al backend:', error)
    } finally {
      this.clearToken()
      this.clearCurrentUser()
      this.isAuthenticated = false
      App.services.user.currentUser = null // Sincronizar con UserService
      App.events.dispatchEvent('auth:logout')
      // Redirigir a la página de login o inicio
      // window.location.href = App.config.LOGIN_URL || '/auth/login';
    }
  }

  /**
     * Registra un nuevo usuario.
     * @param {Object} userData - Datos del usuario (nombre, email, password, etc.).
     * @return {Promise<Object>} Datos del usuario registrado.
     */
  async register (userData) {
    try {
      const response = await App.http.post(`${this.authEndpoint}/register`, userData)
      // Podrías manejar el login automático después del registro o requerir verificación de email
      App.events.dispatchEvent('auth:register_success', response)
      return response
    } catch (error) {
      console.error('AuthService: Error en registro:', error)
      App.events.dispatchEvent('auth:register_failed', error)
      throw error
    }
  }

  /**
     * Obtiene los datos del usuario actualmente autenticado desde el backend.
     * @return {Promise<Object|null>}
     */
  async fetchCurrentUser () {
    if (!this.getToken()) {
      this.isAuthenticated = false
      this.currentUser = null
      return null
    }
    try {
      const userData = await App.http.get(`${this.authEndpoint}/me`)
      this.setCurrentUser(userData)
      this.isAuthenticated = true
      App.services.user.currentUser = userData // Sincronizar con UserService
      App.events.dispatchEvent('auth:user_refreshed', userData)
      return userData
    } catch (error) {
      console.warn('AuthService: Error obteniendo usuario actual, cerrando sesión.', error)
      // Si falla (ej. token expirado), cerrar sesión
      await this.logout()
      return null
    }
  }

  /**
     * Verifica si el usuario está autenticado.
     * @return {boolean}
     */
  check () {
    return this.isAuthenticated
  }

  /**
     * Obtiene el token de autenticación.
     * @return {string|null}
     */
  getToken () {
    return localStorage.getItem(this.tokenKey) || sessionStorage.getItem(this.tokenKey)
  }

  /**
     * Establece el token de autenticación.
     * @param {string} token - El token JWT.
     * @param {boolean} rememberMe - Si guardar en localStorage o sessionStorage.
     */
  setToken (token, rememberMe) {
    if (rememberMe) {
      localStorage.setItem(this.tokenKey, token)
      sessionStorage.removeItem(this.tokenKey)
    } else {
      sessionStorage.setItem(this.tokenKey, token)
      localStorage.removeItem(this.tokenKey)
    }
  }

  /**
     * Limpia el token de autenticación.
     */
  clearToken () {
    localStorage.removeItem(this.tokenKey)
    sessionStorage.removeItem(this.tokenKey)
  }

  /**
     * Establece los datos del usuario actual en localStorage.
     * @param {Object} user - Datos del usuario.
     */
  setCurrentUser (user) {
    this.currentUser = user
    localStorage.setItem(this.userKey, JSON.stringify(user))
  }

  /**
     * Limpia los datos del usuario actual de localStorage.
     */
  clearCurrentUser () {
    this.currentUser = null
    localStorage.removeItem(this.userKey)
  }

  /**
     * Solicita un reseteo de contraseña.
     * @param {string} email - Email del usuario.
     * @return {Promise<Object>}
     */
  async requestPasswordReset (email) {
    try {
      return await App.http.post(`${this.authEndpoint}/forgot-password`, { email })
    } catch (error) {
      console.error('AuthService: Error solicitando reseteo de contraseña:', error)
      throw error
    }
  }

  /**
     * Resetea la contraseña usando un token.
     * @param {string} token - Token de reseteo.
     * @param {string} newPassword - Nueva contraseña.
     * @param {string} confirmPassword - Confirmación de la nueva contraseña.
     * @return {Promise<Object>}
     */
  async resetPassword (token, newPassword, confirmPassword) {
    try {
      return await App.http.post(`${this.authEndpoint}/reset-password`, {
        token,
        new_password: newPassword,
        confirm_password: confirmPassword
      })
    } catch (error) {
      console.error('AuthService: Error reseteando contraseña:', error)
      throw error
    }
  }

  /**
     * Cambia la contraseña del usuario autenticado.
     * @param {string} currentPassword - Contraseña actual.
     * @param {string} newPassword - Nueva contraseña.
     * @param {string} confirmPassword - Confirmación de la nueva contraseña.
     * @return {Promise<Object>}
     */
  async changePassword (currentPassword, newPassword, confirmPassword) {
    try {
      return await App.http.post(`${this.authEndpoint}/change-password`, {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      })
    } catch (error) {
      console.error('AuthService: Error cambiando contraseña:', error)
      throw error
    }
  }

  /**
     * Verifica un token de email.
     * @param {string} token - El token de verificación.
     * @return {Promise<Object>}
     */
  async verifyEmailToken (token) {
    try {
      return await App.http.post(`${this.authEndpoint}/verify-email/${token}`)
    } catch (error) {
      console.error('AuthService: Error verificando token de email:', error)
      throw error
    }
  }

  /**
     * Reenvía el email de verificación.
     * @param {string} email - Email del usuario.
     * @return {Promise<Object>}
     */
  async resendVerificationEmail (email) {
    try {
      return await App.http.post(`${this.authEndpoint}/resend-verification`, { email })
    } catch (error) {
      console.error('AuthService: Error reenviando email de verificación:', error)
      throw error
    }
  }

  /**
     * Obtiene el usuario actual (sincrónico, desde el estado local).
     * Para obtener datos frescos del servidor, usar `fetchCurrentUser` o `UserService.getCurrentUser(true)`.
     * @return {Object|null}
     */
  getUser () {
    return this.currentUser
  }

  /**
     * Obtiene el ID del usuario actual.
     * @return {number|string|null}
     */
  getUserId () {
    return this.currentUser ? this.currentUser.id : null
  }

  /**
     * Verifica si el usuario actual tiene un rol específico.
     * @param {string} role - El rol a verificar.
     * @return {boolean}
     */
  hasRole (role) {
    return this.currentUser && this.currentUser.role === role
  }

  /**
     * Verifica si el usuario actual tiene un permiso específico.
     * (Asume que los permisos están en `currentUser.permissions`)
     * @param {string} permission - El permiso a verificar.
     * @return {boolean}
     */
  hasPermission (permission) {
    return this.currentUser && this.currentUser.permissions && this.currentUser.permissions.includes(permission)
  }
}

// Registrar el servicio en la instancia global de la App
App.services.auth = new AuthService()
