/**
 * Performance Utilities - Ecosistema de Emprendimiento
 * ==================================================
 *
 * Utilidades para monitorear y medir el rendimiento del lado del cliente.
 * Incluye funciones para User Timing API, Web Vitals y otras métricas.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

'use strict'

const PerformanceUtils = {

  /**
     * Verifica si la API de Performance está disponible.
     * @return {boolean} True si está disponible.
     */
  isPerformanceAPISupported () {
    return !!(window.performance && window.performance.mark && window.performance.measure)
  },

  /**
     * Marca un punto en el tiempo usando User Timing API.
     * @param {string} markName - Nombre de la marca.
     */
  mark (markName) {
    if (this.isPerformanceAPISupported()) {
      try {
        window.performance.mark(markName)
      } catch (e) {
        console.warn(`PerformanceUtils: Error al crear la marca '${markName}'.`, e)
      }
    }
  },

  /**
     * Mide la duración entre dos marcas o desde el inicio de la navegación.
     * @param {string} measureName - Nombre de la medida.
     * @param {string} [startMarkName] - Nombre de la marca de inicio. Si es null, mide desde navigationStart.
     * @param {string} [endMarkName] - Nombre de la marca de fin. Si es null, mide hasta el momento actual.
     * @return {PerformanceMeasure|null} Objeto PerformanceMeasure o null si no se pudo medir.
     */
  measure (measureName, startMarkName, endMarkName) {
    if (this.isPerformanceAPISupported()) {
      try {
        window.performance.measure(measureName, startMarkName, endMarkName)
        const measures = window.performance.getEntriesByName(measureName, 'measure')
        return measures.length > 0 ? measures[measures.length - 1] : null
      } catch (e) {
        console.warn(`PerformanceUtils: Error al crear la medida '${measureName}'.`, e)
        return null
      }
    }
    return null
  },

  /**
     * Obtiene todas las entradas de performance por nombre y tipo.
     * @param {string} name - Nombre de la entrada.
     * @param {string} type - Tipo de entrada ('mark', 'measure', 'resource', etc.).
     * @return {PerformanceEntry[]} Array de entradas de performance.
     */
  getEntriesByName (name, type) {
    if (this.isPerformanceAPISupported()) {
      return window.performance.getEntriesByName(name, type)
    }
    return []
  },

  /**
     * Obtiene todas las entradas de performance por tipo.
     * @param {string} type - Tipo de entrada.
     * @return {PerformanceEntry[]} Array de entradas de performance.
     */
  getEntriesByType (type) {
    if (this.isPerformanceAPISupported()) {
      return window.performance.getEntriesByType(type)
    }
    return []
  },

  /**
     * Limpia marcas y medidas específicas.
     * @param {string[]} [markNames] - Nombres de marcas a limpiar.
     * @param {string[]} [measureNames] - Nombres de medidas a limpiar.
     */
  clearPerformanceEntries (markNames = [], measureNames = []) {
    if (this.isPerformanceAPISupported()) {
      markNames.forEach(name => window.performance.clearMarks(name))
      measureNames.forEach(name => window.performance.clearMeasures(name))
    }
  },

  /**
     * Obtiene métricas de Navigation Timing API.
     * @return {PerformanceNavigationTiming|null} Objeto con métricas de navegación.
     */
  getNavigationTiming () {
    if (window.performance && window.performance.timing) {
      return window.performance.timing
    }
    const navTiming = this.getEntriesByType('navigation')
    return navTiming.length > 0 ? navTiming[0] : null
  },

  /**
     * Obtiene métricas de Resource Timing API para un recurso específico o todos.
     * @param {string} [resourceUrl] - URL del recurso a buscar.
     * @return {PerformanceResourceTiming[]|PerformanceResourceTiming|null}
     */
  getResourceTiming (resourceUrl) {
    const resources = this.getEntriesByType('resource')
    if (resourceUrl) {
      return resources.find(r => r.name === resourceUrl) || null
    }
    return resources
  },

  /**
     * Observa el Largest Contentful Paint (LCP).
     * @param {function} callback - Función a llamar con la entrada LCP.
     */
  onLCP (callback) {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries()
        if (entries.length > 0) {
          const lcpEntry = entries[entries.length - 1] // El último es el LCP final
          callback(lcpEntry)
          observer.disconnect() // Desconectar después de obtener el LCP final
        }
      })
      observer.observe({ type: 'largest-contentful-paint', buffered: true })
    } else {
      console.warn('PerformanceObserver no soportado para LCP.')
    }
  },

  /**
     * Observa el First Input Delay (FID).
     * @param {function} callback - Función a llamar con la entrada FID.
     */
  onFID (callback) {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          callback(entry)
          observer.disconnect() // FID solo ocurre una vez
        }
      })
      observer.observe({ type: 'first-input', buffered: true })
    } else {
      console.warn('PerformanceObserver no soportado para FID.')
    }
  },

  /**
     * Observa el Cumulative Layout Shift (CLS).
     * @param {function} callback - Función a llamar con la entrada CLS.
     */
  onCLS (callback) {
    if ('PerformanceObserver' in window) {
      let clsValue = 0
      const observer = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          if (!entry.hadRecentInput) {
            clsValue += entry.value
            callback({ value: clsValue, entry })
          }
        }
      })
      observer.observe({ type: 'layout-shift', buffered: true })
      // También se puede reportar CLS al final de la sesión (visibilitychange, pagehide)
    } else {
      console.warn('PerformanceObserver no soportado para CLS.')
    }
  },

  /**
     * Registra métricas de Web Vitals.
     * @param {Object} [options] - Opciones para el registro.
     * @param {function} [options.lcpCallback]
     * @param {function} [options.fidCallback]
     * @param {function} [options.clsCallback]
     */
  observeWebVital (metricName, callback) {
    if ('PerformanceObserver' in window) {
      const entryTypeMap = {
        LCP: 'largest-contentful-paint',
        FID: 'first-input',
        CLS: 'layout-shift',
        INP: 'event' // Interaction to Next Paint
      }
      const type = entryTypeMap[metricName.toUpperCase()]
      if (!type) {
        console.warn(`Métrica Web Vital desconocida: ${metricName}`)
        return
      }

      const observer = new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries()
        if (entries.length > 0) {
          const lastEntry = entries[entries.length - 1]
          callback(lastEntry)
          // Para FID e INP (si se mide una sola vez), desconectar.
          // Para CLS, se acumula. Para LCP, el último es el final.
          if (type === 'first-input' || (type === 'event' && metricName.toUpperCase() === 'INP')) {
            // observer.disconnect(); // INP puede tener múltiples entradas, decidir estrategia
          }
        }
      })
      observer.observe({ type, buffered: true })
    } else {
      console.warn(`PerformanceObserver no soportado para ${metricName}.`)
    }
  },

  /**
     * Obtiene el uso de memoria (experimental, puede no estar disponible).
     * @return {object|null} Objeto con información de memoria.
     */
  getMemoryUsage () {
    if (window.performance && window.performance.memory) {
      return window.performance.memory
    }
    return null
  },

  /**
     * Envía datos de performance a un endpoint (simulado).
     * @param {string} metricName - Nombre de la métrica.
     * @param {number} value - Valor de la métrica.
     * @param {object} [dimensions] - Dimensiones adicionales.
     */
  sendMetricToServer (metricName, value, dimensions = {}) {
    const payload = {
      metric: metricName,
      value,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      dimensions
    }

    // En una aplicación real, se enviaría a un backend de analytics.
    console.log('Performance Metric to Server:', payload)

    // Ejemplo de envío con fetch:
    // fetch('/api/performance-metrics', {
    //     method: 'POST',
    //     headers: { 'Content-Type': 'application/json' },
    //     body: JSON.stringify(payload)
    // }).catch(error => console.error('Error sending performance metric:', error));
  },

  /**
     * Mide el tiempo de ejecución de una función.
     * @param {string} functionName - Nombre de la función para la métrica.
     * @param {function} func - La función a ejecutar y medir.
     * @return {any} El resultado de la función.
     */
  measureFunctionExecution (functionName, func) {
    const startMark = `start_${functionName}_${Date.now()}`
    const endMark = `end_${functionName}_${Date.now()}`

    this.mark(startMark)
    let result
    try {
      result = func()
    } finally {
      this.mark(endMark)
      const measure = this.measure(functionName, startMark, endMark)
      if (measure) {
        console.log(`Performance: ${functionName} tomó ${measure.duration.toFixed(2)}ms`)
        // Opcionalmente, enviar al servidor:
        // this.sendMetricToServer(functionName, measure.duration);
      }
      this.clearPerformanceEntries([startMark, endMark], [functionName])
    }
    return result
  },

  /**
     * Mide el tiempo de ejecución de una función asíncrona.
     * @param {string} functionName - Nombre de la función para la métrica.
     * @param {function} asyncFunc - La función asíncrona a ejecutar y medir.
     * @return {Promise<any>} El resultado de la función asíncrona.
     */
  async measureAsyncFunctionExecution (functionName, asyncFunc) {
    const startMark = `start_async_${functionName}_${Date.now()}`
    const endMark = `end_async_${functionName}_${Date.now()}`

    this.mark(startMark)
    let result
    try {
      result = await asyncFunc()
    } finally {
      this.mark(endMark)
      const measure = this.measure(`async_${functionName}`, startMark, endMark)
      if (measure) {
        console.log(`Performance: async ${functionName} tomó ${measure.duration.toFixed(2)}ms`)
        // this.sendMetricToServer(`async_${functionName}`, measure.duration);
      }
      this.clearPerformanceEntries([startMark, endMark], [`async_${functionName}`])
    }
    return result
  }
}

// Hacer disponible globalmente si es necesario
if (typeof window !== 'undefined') {
  window.PerformanceUtils = PerformanceUtils

  // Integrar con EcosistemaApp si existe
  if (window.EcosistemaApp && window.EcosistemaApp.utils) {
    window.EcosistemaApp.utils.performance = PerformanceUtils
  } else if (window.EcosistemaApp) {
    window.EcosistemaApp.utils = { performance: PerformanceUtils }
  }
}

// Para uso como módulo (si es necesario)
// export default PerformanceUtils;
