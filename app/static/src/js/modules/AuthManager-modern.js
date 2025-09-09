/**
 * Ecosistema Emprendimiento - Auth Manager Module (Modern)
 * ========================================================
 *
 * Módulo modernizado para gestionar la autenticación de usuarios,
 * incluyendo login, registro, logout, gestión de sesión
 * y recuperación de contraseña.
 *
 * @author Ecosistema Emprendimiento Team
 * @version 1.0.0
 * @updated 2025
 */

'use strict'

// Modern imports
import Swal from 'sweetalert2'

/**
 * AuthManager class - Modernized authentication management
 */
export default class AuthManager {
  constructor (app) {
    this.app = app || window.EcosistemaApp
    this.config = {
      endpoints: {
        login: '/auth/login',
        register: '/auth/register',
        logout: '/auth/logout',
        status: '/auth/status',
        forgotPassword: '/auth/forgot-password',
        resetPassword: '/auth/reset-password',
        refreshToken: '/auth/refresh'
      },
      storage: {
        tokenKey: 'authToken',
        userKey: 'currentUser',
        refreshTokenKey: 'refreshToken'
      },
      redirects: {
        loginSuccess: '/dashboard',
        logoutSuccess: '/login',
        registrationSuccess: '/login?registered=true'
      },
      session: {
        timeoutWarning: 5 * 60 * 1000, // 5 minutos antes de expirar
        autoRefresh: true,
        refreshThreshold: 10 * 60 * 1000 // 10 minutos antes de expirar
      }
    }

    // Estado interno usando Map para mejor performance
    this.state = new Map([
      ['isAuthenticated', false],
      ['currentUser', null],
      ['token', null],
      ['refreshToken', null],
      ['tokenExpiresAt', null],
      ['isCheckingStatus', false],
      ['sessionWarningTimer', null],
      ['refreshTimer', null]
    ])

    this.eventListeners = new Map()
    this.abortController = new AbortController()

    this.init()
  }

  /**
     * Inicializar módulo de forma asíncrona
     */
  async init () {
    // // console.log('🔒 Inicializando Auth Manager (Modern)')

    try {
      this.loadSession()
      await this.checkAuthStatus()
      this.setupEventListeners()
      this.setupInterceptors()

      // // console.log('✅ Auth Manager inicializado correctamente')
    } catch (error) {
      // // console.error('❌ Error inicializando Auth Manager:', error)
    }
  }

  /**
     * Cargar sesión desde localStorage
     */
  loadSession () {
    const token = this.app.storage.get(this.config.storage.tokenKey)
    const user = this.app.storage.get(this.config.storage.userKey)
    const refreshToken = this.app.storage.get(this.config.storage.refreshTokenKey)
    const expiresAt = this.app.storage.get(`${this.config.storage.tokenKey}_expires_at`)

    if (token && user) {
      this.state.set('token', token)
      this.state.set('refreshToken', refreshToken)
      this.state.set('currentUser', user)
      this.state.set('isAuthenticated', true)

      if (expiresAt) {
        this.state.set('tokenExpiresAt', new Date(expiresAt))
        this.setupSessionManagement()
      }

      this.updateGlobalState(user)
      this.emitAuthEvent('authenticated', { user, token })
    }
  }

  /**
     * Verificar estado de autenticación con el servidor
     */
  async checkAuthStatus () {
    if (this.state.get('isCheckingStatus')) return false

    this.state.set('isCheckingStatus', true)

    try {
      const token = this.state.get('token')
      if (!token) {
        this.updateAuthState(false, null)
        return false
      }

      // Verificar si el token expiró localmente
      const expiresAt = this.state.get('tokenExpiresAt')
      if (expiresAt && new Date() > expiresAt) {
        // // console.log('Token expirado localmente, intentando refresh...')
        return await this.refreshToken()
      }

      const response = await this.app.http.get(this.config.endpoints.status, {
        signal: this.abortController.signal
      })

      this.handleAuthResponse(response)
      return this.state.get('isAuthenticated')
    } catch (error) {
      if (error.name === 'AbortError') {
        // // console.log('Verificación de auth cancelada')
        return false
      }

      // console.warn('Error verificando estado de autenticación:', error.message)

      if (error.response?.status === 401) {
        await this.handleUnauthorized()
      }
      return false
    } finally {
      this.state.set('isCheckingStatus', false)
    }
  }

  /**
     * Iniciar sesión con validación mejorada
     */
  async login (credentials) {
    const { email, password, rememberMe = false } = credentials

    // Validar credenciales localmente
    if (!this.validateCredentials(email, password)) {
      throw new Error('Credenciales inválidas')
    }

    try {
      this.showLoading('Iniciando sesión...')

      const response = await this.app.http.post(this.config.endpoints.login, {
        email: email.toLowerCase().trim(),
        password,
        remember_me: rememberMe
      })

      this.handleAuthResponse(response, rememberMe)

      if (this.state.get('isAuthenticated')) {
        await this.onLoginSuccess(response)
      } else {
        throw new Error(response.message || 'Credenciales inválidas')
      }
    } catch (error) {
      await this.onLoginError(error)
      throw error
    } finally {
      this.hideLoading()
    }
  }

  /**
     * Registrar nuevo usuario con validación
     */
  async register (userData) {
    // Validar datos del usuario
    const validationErrors = this.validateRegistrationData(userData)
    if (validationErrors.length > 0) {
      throw new Error(validationErrors.join(', '))
    }

    try {
      this.showLoading('Registrando usuario...')

      const response = await this.app.http.post(this.config.endpoints.register, {
        ...userData,
        email: userData.email.toLowerCase().trim()
      })

      await this.onRegistrationSuccess(response)
    } catch (error) {
      await this.onRegistrationError(error)
      throw error
    } finally {
      this.hideLoading()
    }
  }

  /**
     * Cerrar sesión de forma segura
     */
  async logout (showNotification = true) {
    try {
      // Cancelar cualquier request pendiente
      this.abortController.abort()
      this.abortController = new AbortController()

      // Intentar notificar al servidor
      await this.app.http.post(this.config.endpoints.logout).catch(() => {
        // console.warn('Error notificando logout al servidor')
      })
    } finally {
      this.clearSessionData()
      this.updateAuthState(false, null)

      if (showNotification) {
        this.app.notifications.info('Sesión cerrada correctamente')
      }

      this.redirectToLogin()
    }
  }

  /**
     * Refresh token automático
     */
  async refreshToken () {
    const refreshToken = this.state.get('refreshToken')
    if (!refreshToken) {
      await this.logout(false)
      return false
    }

    try {
      const response = await this.app.http.post(this.config.endpoints.refreshToken, {
        refresh_token: refreshToken
      })

      this.handleAuthResponse(response, true)
      return this.state.get('isAuthenticated')
    } catch (error) {
      // // console.error('Error refreshing token:', error)
      await this.logout(false)
      return false
    }
  }

  /**
     * Manejar respuesta de autenticación
     */
  handleAuthResponse (response, rememberMe = false) {
    if (!response) return

    const { access_token, refresh_token, user, expires_in, expires_at } = response

    if (access_token && user) {
      let expiresAt = null

      if (expires_in) {
        expiresAt = new Date(Date.now() + expires_in * 1000)
      } else if (expires_at) {
        expiresAt = new Date(expires_at)
      }

      this.updateAuthState(true, user, access_token, refresh_token, expiresAt, rememberMe)
    } else if (response.is_authenticated === false) {
      this.updateAuthState(false, null)
    } else if (response.is_authenticated === true && response.user) {
      // Status check que devuelve usuario sin nuevo token
      this.updateAuthState(
        true,
        response.user,
        this.state.get('token'),
        this.state.get('refreshToken'),
        this.state.get('tokenExpiresAt'),
        rememberMe
      )
    }
  }

  /**
     * Actualizar estado de autenticación
     */
  updateAuthState (isAuthenticated, user, token = null, refreshToken = null, expiresAt = null, rememberMe = false) {
    this.state.set('isAuthenticated', isAuthenticated)
    this.state.set('currentUser', user)
    this.state.set('token', token)
    this.state.set('refreshToken', refreshToken)
    this.state.set('tokenExpiresAt', expiresAt)

    if (isAuthenticated && token && user) {
      this.storeSessionData(token, refreshToken, user, expiresAt)
      this.setupSessionManagement()
      this.updateGlobalState(user)
    } else {
      this.clearSessionData()
      this.clearSessionManagement()
      this.updateGlobalState(null)
    }

    this.updateUIState(isAuthenticated, user)
    this.emitAuthEvent(isAuthenticated ? 'authenticated' : 'unauthenticated', { user, token })
  }

  /**
     * Configurar gestión de sesión automatizada
     */
  setupSessionManagement () {
    this.clearSessionManagement()

    const expiresAt = this.state.get('tokenExpiresAt')
    if (!expiresAt) return

    const now = Date.now()
    const expiryTime = expiresAt.getTime()

    // Configurar warning de expiración
    const warningTime = expiryTime - now - this.config.session.timeoutWarning
    if (warningTime > 0) {
      const warningTimer = setTimeout(() => {
        this.showSessionWarning()
      }, warningTime)
      this.state.set('sessionWarningTimer', warningTimer)
    }

    // Configurar auto-refresh si está habilitado
    if (this.config.session.autoRefresh) {
      const refreshTime = expiryTime - now - this.config.session.refreshThreshold
      if (refreshTime > 0) {
        const refreshTimer = setTimeout(() => {
          this.refreshToken()
        }, refreshTime)
        this.state.set('refreshTimer', refreshTimer)
      }
    }
  }

  /**
     * Limpiar gestión de sesión
     */
  clearSessionManagement () {
    const warningTimer = this.state.get('sessionWarningTimer')
    const refreshTimer = this.state.get('refreshTimer')

    if (warningTimer) {
      clearTimeout(warningTimer)
      this.state.set('sessionWarningTimer', null)
    }

    if (refreshTimer) {
      clearTimeout(refreshTimer)
      this.state.set('refreshTimer', null)
    }
  }

  /**
     * Mostrar warning de sesión
     */
  async showSessionWarning () {
    const result = await Swal.fire({
      title: 'Sesión por expirar',
      text: 'Tu sesión está a punto de expirar. ¿Deseas extenderla?',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Sí, extender',
      cancelButtonText: 'No, cerrar sesión',
      timer: 30000,
      timerProgressBar: true
    })

    if (result.isConfirmed) {
      await this.refreshToken()
    } else {
      await this.logout()
    }
  }

  /**
     * Validar credenciales localmente
     */
  validateCredentials (email, password) {
    if (!email || !password) return false
    if (!this.app.utils.isValidEmail(email)) return false
    if (password.length < 6) return false
    return true
  }

  /**
     * Validar datos de registro
     */
  validateRegistrationData (userData) {
    const errors = []
    const { firstName, lastName, email, password, confirmPassword, termsAccepted } = userData

    if (!firstName?.trim()) errors.push('Nombre es requerido')
    if (!lastName?.trim()) errors.push('Apellido es requerido')
    if (!email || !this.app.utils.isValidEmail(email)) errors.push('Email inválido')
    if (!password || password.length < 8) errors.push('Contraseña debe tener al menos 8 caracteres')
    if (password !== confirmPassword) errors.push('Las contraseñas no coinciden')
    if (!termsAccepted) errors.push('Debe aceptar los términos y condiciones')

    return errors
  }

  /**
     * Almacenar datos de sesión
     */
  storeSessionData (token, refreshToken, user, expiresAt) {
    this.app.storage.set(this.config.storage.tokenKey, token)
    this.app.storage.set(this.config.storage.userKey, user)

    if (refreshToken) {
      this.app.storage.set(this.config.storage.refreshTokenKey, refreshToken)
    }

    if (expiresAt) {
      this.app.storage.set(`${this.config.storage.tokenKey}_expires_at`, expiresAt.toISOString())
    }
  }

  /**
     * Limpiar datos de sesión
     */
  clearSessionData () {
    this.app.storage.remove(this.config.storage.tokenKey)
    this.app.storage.remove(this.config.storage.userKey)
    this.app.storage.remove(this.config.storage.refreshTokenKey)
    this.app.storage.remove(`${this.config.storage.tokenKey}_expires_at`)
  }

  /**
     * Actualizar estado global
     */
  updateGlobalState (user) {
    this.app.currentUser = user
    if (this.app.state) {
      this.app.state.currentUser = user
    }
  }

  /**
     * Actualizar estado UI
     */
  updateUIState (isAuthenticated, user) {
    document.body.classList.toggle('authenticated', isAuthenticated)
    document.body.classList.toggle('unauthenticated', !isAuthenticated)

    if (user?.role) {
      document.body.setAttribute('data-user-role', user.role)
      document.body.setAttribute('data-user-type', user.type || 'user')
    } else {
      document.body.removeAttribute('data-user-role')
      document.body.removeAttribute('data-user-type')
    }
  }

  /**
     * Emitir eventos de autenticación
     */
  emitAuthEvent (eventType, data) {
    this.app.events.dispatchEvent(new CustomEvent(`auth:${eventType}`, {
      detail: data
    }))
  }

  /**
     * Configurar interceptors HTTP
     */
  setupInterceptors () {
    // Este método será llamado por el sistema HTTP para configurar interceptors
    if (this.app.http.addRequestInterceptor) {
      this.app.http.addRequestInterceptor((config) => {
        const token = this.state.get('token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      })
    }

    if (this.app.http.addResponseInterceptor) {
      this.app.http.addResponseInterceptor(
        (response) => response,
        async (error) => {
          if (error.response?.status === 401) {
            await this.handleUnauthorized()
          }
          return Promise.reject(error)
        }
      )
    }
  }

  /**
     * Manejar error 401 Unauthorized
     */
  async handleUnauthorized () {
    if (this.state.get('refreshToken')) {
      const refreshed = await this.refreshToken()
      if (refreshed) return
    }

    await this.logout(false)
    this.app.notifications.error('Tu sesión ha expirado. Por favor, inicia sesión nuevamente.')
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    // Event listeners para formularios de autenticación
    this.setupFormListeners()

    // Event listeners para eventos de la aplicación
    this.app.events.addEventListener('auth:requestLogout', () => this.logout())
    this.app.events.addEventListener('auth:requestRefresh', () => this.refreshToken())

    // Event listeners para visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.state.get('isAuthenticated')) {
        this.checkAuthStatus()
      }
    })
  }

  /**
     * Configurar listeners de formularios
     */
  setupFormListeners () {
    const loginForm = document.getElementById('login-form')
    if (loginForm) {
      loginForm.addEventListener('submit', async (e) => {
        e.preventDefault()

        const formData = new FormData(loginForm)
        const credentials = {
          email: formData.get('email'),
          password: formData.get('password'),
          rememberMe: formData.get('remember_me') === 'on'
        }

        try {
          await this.login(credentials)
        } catch (error) {
          // // console.error('Login error:', error)
        }
      })
    }

    const registerForm = document.getElementById('register-form')
    if (registerForm) {
      registerForm.addEventListener('submit', async (e) => {
        e.preventDefault()

        const formData = new FormData(registerForm)
        const userData = Object.fromEntries(formData.entries())

        try {
          await this.register(userData)
        } catch (error) {
          // // console.error('Registration error:', error)
        }
      })
    }
  }

  /**
     * Métodos de utilidad para eventos
     */
  async onLoginSuccess (response) {
    this.app.notifications.success('Inicio de sesión exitoso')

    // Redireccionar después de un breve delay para mostrar la notificación
    setTimeout(() => {
      window.location.href = this.config.redirects.loginSuccess
    }, 1000)
  }

  async onLoginError (error) {
    // // console.error('Error en login:', error)
    const message = error.response?.data?.message || error.message || 'Error al iniciar sesión'
    this.app.notifications.error(message)
  }

  async onRegistrationSuccess (response) {
    this.app.notifications.success(
      response.message || 'Registro exitoso. Por favor, verifica tu email.'
    )

    setTimeout(() => {
      window.location.href = this.config.redirects.registrationSuccess
    }, 1500)
  }

  async onRegistrationError (error) {
    // // console.error('Error en registro:', error)
    const message = error.response?.data?.message || error.message || 'Error al registrar la cuenta'
    this.app.notifications.error(message)
  }

  /**
     * Métodos de utilidad para UI
     */
  showLoading (message) {
    if (this.app.loading?.show) {
      this.app.loading.show(message)
    }
  }

  hideLoading () {
    if (this.app.loading?.hide) {
      this.app.loading.hide()
    }
  }

  redirectToLogin () {
    window.location.href = this.config.redirects.logoutSuccess
  }

  /**
     * API pública
     */
  getCurrentUser () {
    return this.state.get('currentUser')
  }

  getToken () {
    return this.state.get('token')
  }

  isAuthenticated () {
    return this.state.get('isAuthenticated')
  }

  hasRole (roles) {
    const user = this.state.get('currentUser')
    if (!this.isAuthenticated() || !user?.role) return false

    return Array.isArray(roles)
      ? roles.includes(user.role)
      : user.role === roles
  }

  hasPermission (permission) {
    const user = this.state.get('currentUser')
    if (!this.isAuthenticated() || !user?.permissions) return false

    return Array.isArray(user.permissions)
      ? user.permissions.includes(permission)
      : false
  }

  /**
     * Destruir módulo y limpiar recursos
     */
  destroy () {
    this.abortController.abort()
    this.clearSessionManagement()

    // Limpiar event listeners
    this.eventListeners.forEach((removeListener) => removeListener())
    this.eventListeners.clear()

    // // console.log('🧹 Auth Manager destruido')
  }
}
