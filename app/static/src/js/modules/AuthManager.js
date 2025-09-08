/**
 * Ecosistema Emprendimiento - Auth Manager Module
 * ==============================================
 *
 * Módulo para gestionar la autenticación de usuarios,
 * incluyendo login, registro, logout, gestión de sesión
 * y recuperación de contraseña.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js
 */

'use strict'

class AuthManager {
  constructor (app) {
    this.app = app || window.EcosistemaApp
    this.main = this.app?.main || window.App
    this.state = this.app?.state || window.EcosistemaStateManager
    this.config = window.getConfig ? window.getConfig('modules.authManager', {}) : {}

    // Configuración del módulo
    this.moduleConfig = {
      loginEndpoint: '/auth/login',
      registerEndpoint: '/auth/register',
      logoutEndpoint: '/auth/logout',
      checkStatusEndpoint: '/auth/status',
      forgotPasswordEndpoint: '/auth/forgot-password',
      resetPasswordEndpoint: '/auth/reset-password',
      tokenStorageKey: 'authToken',
      userStorageKey: 'currentUser',
      redirects: {
        loginSuccess: '/dashboard',
        logoutSuccess: '/login',
        registrationSuccess: '/login?registered=true'
      },
      sessionTimeoutWarning: 5 * 60 * 1000, // 5 minutos antes de expirar
      ...this.config
    }

    // Estado interno del módulo
    this.moduleState = {
      isAuthenticated: false,
      currentUser: null,
      token: null,
      tokenExpiresAt: null,
      isCheckingStatus: false,
      sessionWarningTimer: null
    }

    this.elements = {} // Para elementos UI si este módulo los maneja directamente
    this.eventListeners = new Map()

    this.init()
  }

  /**
     * Inicializar módulo
     */
  async init () {
    console.log('🔒 Inicializando Auth Manager')
    this.loadSession()
    await this.checkAuthStatus()
    this.setupEventListeners()
    console.log('✅ Auth Manager inicializado')
  }

  /**
     * Cargar sesión desde localStorage
     */
  loadSession () {
    const token = this.main.storage.get(this.moduleConfig.tokenStorageKey)
    const user = this.main.storage.get(this.moduleConfig.userStorageKey)
    const expiresAt = this.main.storage.get(`${this.moduleConfig.tokenStorageKey}_expires_at`)

    if (token && user) {
      this.moduleState.token = token
      this.moduleState.currentUser = user
      this.moduleState.isAuthenticated = true
      if (expiresAt) {
        this.moduleState.tokenExpiresAt = new Date(expiresAt)
        this.setupSessionWarning()
      }
      this.main.currentUser = user // Actualizar globalmente
      this.app.events.dispatchEvent(new CustomEvent('authStatusChanged', { detail: { isAuthenticated: true, user } }))
    }
  }

  /**
     * Verificar estado de autenticación con el servidor
     */
  async checkAuthStatus () {
    if (this.moduleState.isCheckingStatus) return
    this.moduleState.isCheckingStatus = true

    try {
      if (!this.moduleState.token) {
        this.updateAuthState(false, null)
        return false
      }
      // Si el token expiró localmente, no hacer la llamada
      if (this.moduleState.tokenExpiresAt && new Date() > this.moduleState.tokenExpiresAt) {
        console.log('Token expirado localmente, realizando logout.')
        this.logout() // Esto limpiará el estado
        return false
      }

      const response = await this.main.http.get(this.moduleConfig.checkStatusEndpoint)
      this.handleAuthResponse(response)
      return this.moduleState.isAuthenticated
    } catch (error) {
      console.warn('Error verificando estado de autenticación:', error.message)
      // Si hay un error (ej. token inválido en backend), desautenticar
      if (error.status === 401 || error.message.includes('401')) {
        this.updateAuthState(false, null)
      }
      return false
    } finally {
      this.moduleState.isCheckingStatus = false
    }
  }

  /**
     * Iniciar sesión
     * @param {string} email
     * @param {string} password
     * @param {boolean} rememberMe
     */
  async login (email, password, rememberMe = false) {
    try {
      this.main.loading.show('Iniciando sesión...')
      const response = await this.main.http.post(this.moduleConfig.loginEndpoint, { email, password, remember_me: rememberMe })
      this.handleAuthResponse(response, rememberMe)

      if (this.moduleState.isAuthenticated) {
        this.main.notifications.success('Inicio de sesión exitoso')
        window.location.href = this.moduleConfig.redirects.loginSuccess
      } else {
        throw new Error(response.message || 'Credenciales inválidas')
      }
    } catch (error) {
      console.error('Error en login:', error)
      this.main.notifications.error(error.message || 'Error al iniciar sesión')
      this.updateAuthState(false, null)
    } finally {
      this.main.loading.hide()
    }
  }

  /**
     * Registrar nuevo usuario
     * @param {Object} userData - Datos del usuario (firstName, lastName, email, password, etc.)
     */
  async register (userData) {
    try {
      this.main.loading.show('Registrando...')
      const response = await this.main.http.post(this.moduleConfig.registerEndpoint, userData)

      if (response.success || response.user) { // Ajustar según la respuesta de tu API
        this.main.notifications.success(response.message || 'Registro exitoso. Por favor, verifica tu email.')
        window.location.href = this.moduleConfig.redirects.registrationSuccess
      } else {
        throw new Error(response.message || 'Error en el registro')
      }
    } catch (error) {
      console.error('Error en registro:', error)
      this.main.notifications.error(error.message || 'Error al registrar la cuenta')
    } finally {
      this.main.loading.hide()
    }
  }

  /**
     * Cerrar sesión
     */
  async logout () {
    try {
      await this.main.http.post(this.moduleConfig.logoutEndpoint)
    } catch (error) {
      // Ignorar errores de logout en el backend, siempre limpiar localmente
      console.warn('Error en logout del servidor:', error.message)
    } finally {
      this.updateAuthState(false, null)
      this.main.notifications.info('Sesión cerrada')
      window.location.href = this.moduleConfig.redirects.logoutSuccess
    }
  }

  /**
     * Solicitar reseteo de contraseña
     * @param {string} email
     */
  async forgotPassword (email) {
    try {
      this.main.loading.show('Enviando instrucciones...')
      const response = await this.main.http.post(this.moduleConfig.forgotPasswordEndpoint, { email })
      this.main.notifications.success(response.message || 'Si el email existe, recibirás instrucciones para resetear tu contraseña.')
    } catch (error) {
      console.error('Error en forgotPassword:', error)
      this.main.notifications.error(error.message || 'Error al solicitar reseteo de contraseña.')
    } finally {
      this.main.loading.hide()
    }
  }

  /**
     * Resetear contraseña
     * @param {string} token
     * @param {string} newPassword
     */
  async resetPassword (token, newPassword) {
    try {
      this.main.loading.show('Reseteando contraseña...')
      const response = await this.main.http.post(this.moduleConfig.resetPasswordEndpoint, { token, new_password: newPassword })
      this.main.notifications.success(response.message || 'Contraseña reseteada exitosamente. Ya puedes iniciar sesión.')
      window.location.href = '/login' // O a donde corresponda
    } catch (error) {
      console.error('Error en resetPassword:', error)
      this.main.notifications.error(error.message || 'Error al resetear la contraseña.')
    } finally {
      this.main.loading.hide()
    }
  }

  /**
     * Manejar respuesta de autenticación
     * @param {Object} response - Respuesta del API
     * @param {boolean} rememberMe - Si se debe recordar la sesión
     */
  handleAuthResponse (response, rememberMe = false) {
    if (response && response.access_token && response.user) {
      const token = response.access_token
      const user = response.user
      const expiresIn = response.expires_in // en segundos
      let expiresAt = null
      if (expiresIn) {
        expiresAt = new Date(Date.now() + expiresIn * 1000)
      } else if (response.expires_at) { // Si la API devuelve una fecha de expiración
        expiresAt = new Date(response.expires_at)
      }

      this.updateAuthState(true, user, token, expiresAt, rememberMe)
    } else if (response && response.is_authenticated === false) {
      this.updateAuthState(false, null)
    } else if (response && response.is_authenticated === true && response.user) {
      // Caso donde el status check devuelve el usuario pero no un nuevo token
      this.updateAuthState(true, response.user, this.moduleState.token, this.moduleState.tokenExpiresAt, rememberMe)
    }
    // Si la respuesta no es clara o es un error, el estado no cambia aquí, se maneja en el catch del caller.
  }

  /**
     * Actualizar estado de autenticación
     * @param {boolean} isAuthenticated
     * @param {Object|null} user
     * @param {string|null} token
     * @param {Date|null} expiresAt
     * @param {boolean} rememberMe
     */
  updateAuthState (isAuthenticated, user, token = null, expiresAt = null, rememberMe = false) {
    this.moduleState.isAuthenticated = isAuthenticated
    this.moduleState.currentUser = user
    this.moduleState.token = token
    this.moduleState.tokenExpiresAt = expiresAt
    this.main.currentUser = user // Actualizar globalmente

    if (isAuthenticated && token && user) {
      this.main.storage.set(this.moduleConfig.tokenStorageKey, token)
      this.main.storage.set(this.moduleConfig.userStorageKey, user)
      if (expiresAt) {
        this.main.storage.set(`${this.moduleConfig.tokenStorageKey}_expires_at`, expiresAt.toISOString())
        this.setupSessionWarning()
      }
    } else {
      this.main.storage.remove(this.moduleConfig.tokenStorageKey)
      this.main.storage.remove(this.moduleConfig.userStorageKey)
      this.main.storage.remove(`${this.moduleConfig.tokenStorageKey}_expires_at`)
      this.clearSessionWarning()
    }

    // Actualizar UI y emitir evento
    document.body.classList.toggle('logged-in', isAuthenticated)
    document.body.classList.toggle('logged-out', !isAuthenticated)
    if (user && user.role) {
      document.body.setAttribute('data-user-role', user.role)
    } else {
      document.body.removeAttribute('data-user-role')
    }

    this.app.events.dispatchEvent(new CustomEvent('authStatusChanged', { detail: { isAuthenticated, user } }))
  }

  /**
     * Configurar advertencia de expiración de sesión
     */
  setupSessionWarning () {
    this.clearSessionWarning()
    if (this.moduleState.tokenExpiresAt && this.moduleConfig.sessionTimeoutWarning > 0) {
      const warningTime = this.moduleState.tokenExpiresAt.getTime() - Date.now() - this.moduleConfig.sessionTimeoutWarning
      if (warningTime > 0) {
        this.moduleState.sessionWarningTimer = setTimeout(() => {
          this.main.notifications.warning('Tu sesión está a punto de expirar.', { duration: 10000 })
          // Aquí se podría mostrar un modal para extender la sesión
        }, warningTime)
      }
    }
  }

  /**
     * Limpiar timer de advertencia de sesión
     */
  clearSessionWarning () {
    if (this.moduleState.sessionWarningTimer) {
      clearTimeout(this.moduleState.sessionWarningTimer)
      this.moduleState.sessionWarningTimer = null
    }
  }

  /**
     * Obtener usuario actual
     */
  getCurrentUser () {
    return this.moduleState.currentUser
  }

  /**
     * Obtener token de autenticación
     */
  getToken () {
    return this.moduleState.token
  }

  /**
     * Verificar si el usuario está autenticado
     */
  isAuthenticated () {
    return this.moduleState.isAuthenticated
  }

  /**
     * Verificar si el usuario tiene un rol específico
     * @param {string|Array<string>} roles
     */
  hasRole (roles) {
    if (!this.isAuthenticated() || !this.moduleState.currentUser?.role) {
      return false
    }
    const userRole = this.moduleState.currentUser.role
    if (Array.isArray(roles)) {
      return roles.includes(userRole)
    }
    return userRole === roles
  }

  /**
     * Verificar si el usuario tiene un permiso específico
     * @param {string} permission
     */
  hasPermission (permission) {
    if (!this.isAuthenticated() || !this.moduleState.currentUser?.permissions) {
      return false
    }
    // Asume que currentUser.permissions es un array de strings de permisos
    return this.moduleState.currentUser.permissions.includes(permission)
  }

  /**
     * Configurar event listeners (ej. para formularios de login/registro)
     */
  setupEventListeners () {
    // Ejemplo: si los formularios de login/registro están en la página
    const loginForm = document.getElementById('login-form')
    if (loginForm) {
      loginForm.addEventListener('submit', async (e) => {
        e.preventDefault()
        const email = loginForm.querySelector('input[name="email"]').value
        const password = loginForm.querySelector('input[name="password"]').value
        const rememberMe = loginForm.querySelector('input[name="remember_me"]')?.checked || false
        await this.login(email, password, rememberMe)
      })
    }

    const registerForm = document.getElementById('register-form')
    if (registerForm) {
      registerForm.addEventListener('submit', async (e) => {
        e.preventDefault()
        const formData = new FormData(registerForm)
        const userData = Object.fromEntries(formData.entries())
        await this.register(userData)
      })
    }

    // Escuchar evento de logout desde otras partes de la app
    this.app.events.addEventListener('requestLogout', () => this.logout())
  }

  /**
     * Destruir módulo y limpiar
     */
  destroy () {
    this.clearSessionWarning()
    // Limpiar otros listeners si es necesario
    console.log('🧹 Auth Manager destruido')
  }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AuthManager
} else {
  window.AuthManager = AuthManager
}

// Inicialización automática si EcosistemaApp está disponible
// Se asume que AuthManager se instancia desde app.js o main.js
