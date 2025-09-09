/**
 * UserService.js - Servicio para la Gestión de Usuarios
 * =====================================================
 *
 * Maneja todas las interacciones relacionadas con los datos de usuarios,
 * perfiles, autenticación (lado del cliente) y configuraciones.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.notifications, etc.)
 */

'use strict'

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
  throw new Error('main.js debe cargarse antes que UserService.js')
}

// Alias para facilitar acceso
const App = window.EcosistemaApp

class UserService {
  constructor () {
    this.baseEndpoint = '/api/v1/users' // Endpoint base para usuarios
    this.authEndpoint = '/api/v1/auth' // Endpoint para autenticación
    this.currentUser = null // Almacenar datos del usuario actual
    this.cache = new Map() // Cache simple para perfiles
    this.cacheTTL = 5 * 60 * 1000 // 5 minutos
  }

  /**
     * Obtener datos del usuario actual.
     * @param {boolean} forceRefresh - Forzar la recarga desde el servidor.
     * @return {Promise<Object|null>} Datos del usuario o null.
     */
  async getCurrentUser (forceRefresh = false) {
    if (this.currentUser && !forceRefresh) {
      return this.currentUser
    }
    try {
      const userData = await App.http.get(`${this.authEndpoint}/me`)
      this.currentUser = userData
      App.events.dispatchEvent('user:loaded', userData)
      return userData
    } catch (error) {
      // console.warn('UserService: No hay usuario autenticado o error al obtenerlo.', error)
      this.currentUser = null
      App.events.dispatchEvent('user:unauthenticated')
      return null
    }
  }

  /**
     * Obtener perfil de un usuario específico.
     * @param {string|number} userId - ID del usuario.
     * @param {boolean} forceRefresh - Forzar la recarga.
     * @return {Promise<Object|null>} Datos del perfil o null.
     */
  async getUserProfile (userId, forceRefresh = false) {
    const cacheKey = `user_profile_${userId}`
    if (!forceRefresh && this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey)
      if (Date.now() - cached.timestamp < this.cacheTTL) {
        return cached.data
      }
    }

    try {
      const profileData = await App.http.get(`${this.baseEndpoint}/${userId}`)
      this.cache.set(cacheKey, { data: profileData, timestamp: Date.now() })
      return profileData
    } catch (error) {
      // // console.error(`UserService: Error al obtener perfil para usuario ${userId}:`, error)
      App.notifications.error('No se pudo cargar el perfil del usuario.')
      return null
    }
  }

  /**
     * Actualizar perfil del usuario actual.
     * @param {Object} profileData - Datos del perfil a actualizar.
     * @return {Promise<Object|null>} Perfil actualizado o null.
     */
  async updateCurrentUserProfile (profileData) {
    if (!this.currentUser || !this.currentUser.id) {
      App.notifications.error('Debes iniciar sesión para actualizar tu perfil.')
      return null
    }
    try {
      const updatedProfile = await App.http.put(`${this.baseEndpoint}/${this.currentUser.id}`, profileData)
      this.currentUser = { ...this.currentUser, ...updatedProfile } // Actualizar localmente
      this.cache.delete(`user_profile_${this.currentUser.id}`) // Invalidar cache
      App.notifications.success('Perfil actualizado exitosamente.')
      App.events.dispatchEvent('user:profile_updated', this.currentUser)
      return updatedProfile
    } catch (error) {
      // // console.error('UserService: Error al actualizar perfil:', error)
      App.notifications.error(error.message || 'No se pudo actualizar el perfil.')
      return null
    }
  }

  /**
     * Subir foto de perfil.
     * @param {File} file - Archivo de imagen.
     * @return {Promise<Object|null>} Respuesta con la URL de la nueva foto o null.
     */
  async uploadProfilePhoto (file) {
    if (!this.currentUser || !this.currentUser.id) {
      App.notifications.error('Debes iniciar sesión para subir una foto.')
      return null
    }
    if (!file || !file.type.startsWith('image/')) {
      App.notifications.error('Por favor, selecciona un archivo de imagen válido.')
      return null
    }

    const formData = new FormData()
    formData.append('photo', file)

    try {
      const response = await App.http.post(`${this.baseEndpoint}/${this.currentUser.id}/photo`, formData, true) // true para indicar FormData
      if (this.currentUser && response.photo_url) {
        this.currentUser.avatar_url = response.photo_url // Asumiendo que el campo se llama avatar_url
        App.events.dispatchEvent('user:avatar_updated', { avatarUrl: response.photo_url })
      }
      App.notifications.success('Foto de perfil actualizada.')
      return response
    } catch (error) {
      // // console.error('UserService: Error al subir foto de perfil:', error)
      App.notifications.error(error.message || 'No se pudo subir la foto de perfil.')
      return null
    }
  }

  /**
     * Cambiar contraseña.
     * @param {string} currentPassword - Contraseña actual.
     * @param {string} newPassword - Nueva contraseña.
     * @return {Promise<boolean>} True si el cambio fue exitoso.
     */
  async changePassword (currentPassword, newPassword) {
    try {
      await App.http.post(`${this.authEndpoint}/change-password`, {
        current_password: currentPassword,
        new_password: newPassword
      })
      App.notifications.success('Contraseña cambiada exitosamente.')
      return true
    } catch (error) {
      // // console.error('UserService: Error al cambiar contraseña:', error)
      App.notifications.error(error.message || 'No se pudo cambiar la contraseña.')
      return false
    }
  }

  /**
     * Solicitar reseteo de contraseña.
     * @param {string} email - Email del usuario.
     * @return {Promise<boolean>} True si la solicitud fue exitosa.
     */
  async requestPasswordReset (email) {
    try {
      await App.http.post(`${this.authEndpoint}/forgot-password`, { email })
      App.notifications.info('Si el email está registrado, recibirás instrucciones para resetear tu contraseña.')
      return true
    } catch (error) {
      // // console.error('UserService: Error al solicitar reseteo de contraseña:', error)
      App.notifications.error(error.message || 'No se pudo procesar la solicitud.')
      return false
    }
  }

  /**
     * Resetear contraseña con token.
     * @param {string} token - Token de reseteo.
     * @param {string} newPassword - Nueva contraseña.
     * @return {Promise<boolean>} True si el reseteo fue exitoso.
     */
  async resetPassword (token, newPassword) {
    try {
      await App.http.post(`${this.authEndpoint}/reset-password`, {
        token,
        new_password: newPassword
      })
      App.notifications.success('Contraseña reseteada exitosamente. Ya puedes iniciar sesión.')
      return true
    } catch (error) {
      // // console.error('UserService: Error al resetear contraseña:', error)
      App.notifications.error(error.message || 'No se pudo resetear la contraseña. El token podría ser inválido o haber expirado.')
      return false
    }
  }

  /**
     * Listar usuarios (para administradores).
     * @param {Object} params - Parámetros de filtrado y paginación.
     * @return {Promise<Object|null>} Lista de usuarios y metadatos de paginación.
     */
  async listUsers (params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString()
      return await App.http.get(`${this.baseEndpoint}?${queryString}`)
    } catch (error) {
      // // console.error('UserService: Error al listar usuarios:', error)
      App.notifications.error('No se pudo cargar la lista de usuarios.')
      return null
    }
  }

  /**
     * Crear un nuevo usuario (para administradores).
     * @param {Object} userData - Datos del nuevo usuario.
     * @return {Promise<Object|null>} Usuario creado o null.
     */
  async createUser (userData) {
    try {
      const newUser = await App.http.post(this.baseEndpoint, userData)
      App.notifications.success(`Usuario ${newUser.email} creado exitosamente.`)
      return newUser
    } catch (error) {
      // // console.error('UserService: Error al crear usuario:', error)
      App.notifications.error(error.message || 'No se pudo crear el usuario.')
      return null
    }
  }

  /**
     * Actualizar un usuario específico (para administradores).
     * @param {string|number} userId - ID del usuario.
     * @param {Object} userData - Datos a actualizar.
     * @return {Promise<Object|null>} Usuario actualizado o null.
     */
  async updateUser (userId, userData) {
    try {
      const updatedUser = await App.http.put(`${this.baseEndpoint}/${userId}`, userData)
      App.notifications.success(`Usuario ${updatedUser.email} actualizado.`)
      this.cache.delete(`user_profile_${userId}`) // Invalidar cache
      return updatedUser
    } catch (error) {
      // // console.error(`UserService: Error al actualizar usuario ${userId}:`, error)
      App.notifications.error(error.message || 'No se pudo actualizar el usuario.')
      return null
    }
  }

  /**
     * Eliminar un usuario (para administradores).
     * @param {string|number} userId - ID del usuario.
     * @return {Promise<boolean>} True si fue exitoso.
     */
  async deleteUser (userId) {
    try {
      await App.http.delete(`${this.baseEndpoint}/${userId}`)
      App.notifications.success('Usuario eliminado exitosamente.')
      this.cache.delete(`user_profile_${userId}`) // Invalidar cache
      return true
    } catch (error) {
      // // console.error(`UserService: Error al eliminar usuario ${userId}:`, error)
      App.notifications.error(error.message || 'No se pudo eliminar el usuario.')
      return false
    }
  }

  /**
     * Verificar si el email está disponible.
     * @param {string} email - Email a verificar.
     * @param {string|number|null} excludeUserId - ID de usuario a excluir de la verificación (para edición).
     * @return {Promise<boolean>} True si el email está disponible.
     */
  async checkEmailAvailability (email, excludeUserId = null) {
    try {
      const payload = { email }
      if (excludeUserId) {
        payload.exclude_user_id = excludeUserId
      }
      const response = await App.http.post(`${this.baseEndpoint}/validate-email`, payload)
      return response.is_available
    } catch (error) {
      // // console.error('UserService: Error al verificar email:', error)
      // Asumir no disponible en caso de error para evitar duplicados
      return false
    }
  }

  /**
     * Obtener preferencias de notificación del usuario.
     * @return {Promise<Object|null>} Preferencias o null.
     */
  async getNotificationPreferences () {
    if (!this.currentUser || !this.currentUser.id) return null
    try {
      return await App.http.get(`${this.baseEndpoint}/${this.currentUser.id}/notification-preferences`)
    } catch (error) {
      // // console.error('UserService: Error al obtener preferencias de notificación:', error)
      return null
    }
  }

  /**
     * Actualizar preferencias de notificación del usuario.
     * @param {Object} preferences - Nuevas preferencias.
     * @return {Promise<Object|null>} Preferencias actualizadas o null.
     */
  async updateNotificationPreferences (preferences) {
    if (!this.currentUser || !this.currentUser.id) return null
    try {
      const updatedPrefs = await App.http.put(`${this.baseEndpoint}/${this.currentUser.id}/notification-preferences`, preferences)
      App.notifications.success('Preferencias de notificación actualizadas.')
      return updatedPrefs
    } catch (error) {
      // // console.error('UserService: Error al actualizar preferencias de notificación:', error)
      App.notifications.error('No se pudieron actualizar las preferencias.')
      return null
    }
  }
}

// Registrar el servicio en la instancia global de la App
App.services.user = new UserService()
