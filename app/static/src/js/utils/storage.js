/**
 * Storage Utilities
 * Utilidades para manejar el almacenamiento del navegador (localStorage y sessionStorage)
 * de forma segura y con funcionalidades adicionales como expiración y manejo de JSON.
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

const StorageUtils = {
  // Tipos de almacenamiento
  LOCAL_STORAGE: 'localStorage',
  SESSION_STORAGE: 'sessionStorage',

  /**
     * Verifica si el tipo de almacenamiento especificado está disponible y es utilizable.
     * @param {string} type - Tipo de almacenamiento ('localStorage' o 'sessionStorage').
     * @returns {boolean} True si está disponible, false en caso contrario.
     */
  isStorageAvailable (type = this.LOCAL_STORAGE) {
    let storage
    try {
      storage = window[type]
      const x = '__storage_test__'
      storage.setItem(x, x)
      storage.removeItem(x)
      return true
    } catch (e) {
      console.warn(`StorageUtils: El almacenamiento tipo '${type}' no está disponible o está deshabilitado.`, e)
      return false
    }
  },

  /**
     * Guarda un valor en el almacenamiento.
     * @param {string} key - La clave bajo la cual guardar el valor.
     * @param {any} value - El valor a guardar (se convertirá a string).
     * @param {string} type - Tipo de almacenamiento ('localStorage' o 'sessionStorage'). Por defecto 'localStorage'.
     * @returns {boolean} True si se guardó correctamente, false en caso contrario.
     */
  set (key, value, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    try {
      window[type].setItem(key, String(value))
      return true
    } catch (e) {
      console.error(`StorageUtils: Error al guardar en '${type}' con clave '${key}'.`, e)
      return false
    }
  },

  /**
     * Obtiene un valor del almacenamiento.
     * @param {string} key - La clave del valor a obtener.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {string|null} El valor como string, o null si no se encuentra o hay error.
     */
  get (key, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return null
    }
    try {
      return window[type].getItem(key)
    } catch (e) {
      console.error(`StorageUtils: Error al obtener de '${type}' con clave '${key}'.`, e)
      return null
    }
  },

  /**
     * Guarda un objeto JSON en el almacenamiento.
     * @param {string} key - La clave.
     * @param {object} value - El objeto a guardar.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {boolean} True si se guardó correctamente.
     */
  setJSON (key, value, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    try {
      const jsonString = JSON.stringify(value)
      window[type].setItem(key, jsonString)
      return true
    } catch (e) {
      console.error(`StorageUtils: Error al guardar JSON en '${type}' con clave '${key}'.`, e)
      return false
    }
  },

  /**
     * Obtiene un objeto JSON del almacenamiento.
     * @param {string} key - La clave.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {object|null} El objeto parseado, o null si no se encuentra, hay error o no es JSON válido.
     */
  getJSON (key, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return null
    }
    try {
      const jsonString = window[type].getItem(key)
      if (jsonString === null) {
        return null
      }
      return JSON.parse(jsonString)
    } catch (e) {
      console.error(`StorageUtils: Error al obtener JSON de '${type}' con clave '${key}'.`, e)
      // Si falla el parseo, podría ser útil remover el item corrupto
      // this.remove(key, type);
      return null
    }
  },

  /**
     * Elimina un item del almacenamiento.
     * @param {string} key - La clave del item a eliminar.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {boolean} True si se eliminó correctamente o no existía, false en caso de error.
     */
  remove (key, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    try {
      window[type].removeItem(key)
      return true
    } catch (e) {
      console.error(`StorageUtils: Error al eliminar de '${type}' con clave '${key}'.`, e)
      return false
    }
  },

  /**
     * Limpia todo el almacenamiento del tipo especificado.
     * ¡Usar con precaución!
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {boolean} True si se limpió correctamente.
     */
  clear (type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    try {
      window[type].clear()
      return true
    } catch (e) {
      console.error(`StorageUtils: Error al limpiar '${type}'.`, e)
      return false
    }
  },

  /**
     * Verifica si una clave existe en el almacenamiento.
     * @param {string} key - La clave a verificar.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {boolean} True si la clave existe.
     */
  has (key, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    return window[type].getItem(key) !== null
  },

  /**
     * Guarda un item con tiempo de expiración (TTL - Time To Live).
     * @param {string} key - La clave.
     * @param {any} value - El valor a guardar.
     * @param {number} ttlInSeconds - Tiempo de vida en segundos.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {boolean} True si se guardó correctamente.
     */
  setWithExpiry (key, value, ttlInSeconds, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return false
    }
    const now = new Date()
    const item = {
      value,
      expiry: now.getTime() + (ttlInSeconds * 1000)
    }
    return this.setJSON(key, item, type)
  },

  /**
     * Obtiene un item guardado con `setWithExpiry`.
     * Si el item ha expirado, se elimina y retorna null.
     * @param {string} key - La clave.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {any|null} El valor si no ha expirado, o null.
     */
  getWithExpiry (key, type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return null
    }
    const item = this.getJSON(key, type)
    if (!item) {
      return null
    }
    const now = new Date()
    if (now.getTime() > item.expiry) {
      // Item expirado, eliminarlo
      this.remove(key, type)
      return null
    }
    return item.value
  },

  /**
     * Obtiene todas las claves del almacenamiento.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {string[]} Un array con todas las claves, o un array vacío si hay error.
     */
  getAllKeys (type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return []
    }
    try {
      const keys = []
      for (let i = 0; i < window[type].length; i++) {
        keys.push(window[type].key(i))
      }
      return keys
    } catch (e) {
      console.error(`StorageUtils: Error al obtener todas las claves de '${type}'.`, e)
      return []
    }
  },

  /**
     * Obtiene el uso actual del almacenamiento en KB.
     * Nota: Esto es una estimación y puede no ser preciso en todos los navegadores.
     * @param {string} type - Tipo de almacenamiento. Por defecto 'localStorage'.
     * @returns {number} Uso estimado en KB, o -1 si no se puede calcular.
     */
  getUsageKB (type = this.LOCAL_STORAGE) {
    if (!this.isStorageAvailable(type)) {
      return -1
    }
    try {
      let totalBytes = 0
      for (const key in window[type]) {
        if (window[type].hasOwnProperty(key)) {
          totalBytes += (window[type][key].length * 2) // Estimación: 2 bytes por caracter (UTF-16)
        }
      }
      return parseFloat((totalBytes / 1024).toFixed(2))
    } catch (e) {
      console.error(`StorageUtils: Error al calcular el uso de '${type}'.`, e)
      return -1
    }
  }
}

// Exportar para uso global o como módulo
if (typeof window !== 'undefined') {
  window.StorageUtils = StorageUtils
  // Si tienes un objeto App global, podrías adjuntarlo ahí:
  // window.App = window.App || {};
  // window.App.storage = StorageUtils;
}

// Para uso como módulo (si es necesario)
// export default StorageUtils;
