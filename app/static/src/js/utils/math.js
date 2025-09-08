/**
 * Math Utilities - Ecosistema de Emprendimiento
 * ============================================
 *
 * Utilidades matemáticas para cálculos comunes en el lado del cliente.
 * Incluye funciones para operaciones numéricas, estadísticas básicas,
 * geometría y otras manipulaciones matemáticas.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

'use strict'

const MathUtils = {

  /**
     * Restringe un número dentro de un rango (clamp).
     * @param {number} num - El número a restringir.
     * @param {number} min - El valor mínimo del rango.
     * @param {number} max - El valor máximo del rango.
     * @return {number} El número restringido.
     */
  clamp (num, min, max) {
    return Math.min(Math.max(num, min), max)
  },

  /**
     * Interpola linealmente entre dos valores.
     * @param {number} a - Valor inicial.
     * @param {number} b - Valor final.
     * @param {number} t - Factor de interpolación (0 a 1).
     * @return {number} El valor interpolado.
     */
  lerp (a, b, t) {
    return a + (b - a) * t
  },

  /**
     * Mapea un número de un rango a otro.
     * @param {number} num - El número a mapear.
     * @param {number} inMin - Mínimo del rango de entrada.
     * @param {number} inMax - Máximo del rango de entrada.
     * @param {number} outMin - Mínimo del rango de salida.
     * @param {number} outMax - Máximo del rango de salida.
     * @return {number} El número mapeado.
     */
  mapRange (num, inMin, inMax, outMin, outMax) {
    return ((num - inMin) * (outMax - outMin)) / (inMax - inMin) + outMin
  },

  /**
     * Genera un número entero aleatorio dentro de un rango (inclusivo).
     * @param {number} min - Valor mínimo.
     * @param {number} max - Valor máximo.
     * @return {number} Un entero aleatorio.
     */
  randomInt (min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min
  },

  /**
     * Genera un número flotante aleatorio dentro de un rango.
     * @param {number} min - Valor mínimo.
     * @param {number} max - Valor máximo.
     * @return {number} Un flotante aleatorio.
     */
  randomFloat (min, max) {
    return Math.random() * (max - min) + min
  },

  /**
     * Redondea un número a un número específico de decimales.
     * @param {number} num - El número a redondear.
     * @param {number} decimals - Número de decimales (default: 0).
     * @return {number} El número redondeado.
     */
  roundTo (num, decimals = 0) {
    const factor = Math.pow(10, decimals)
    return Math.round(num * factor) / factor
  },

  /**
     * Calcula el promedio de un array de números.
     * @param {number[]} numbers - Array de números.
     * @return {number} El promedio, o 0 si el array está vacío.
     */
  average (numbers) {
    if (!numbers || numbers.length === 0) return 0
    const sum = numbers.reduce((acc, val) => acc + val, 0)
    return sum / numbers.length
  },

  /**
     * Calcula la suma de un array de números.
     * @param {number[]} numbers - Array de números.
     * @return {number} La suma.
     */
  sum (numbers) {
    if (!numbers) return 0
    return numbers.reduce((acc, val) => acc + val, 0)
  },

  /**
     * Calcula la desviación estándar de un array de números.
     * @param {number[]} numbers - Array de números.
     * @return {number} La desviación estándar, o 0 si hay menos de 2 números.
     */
  standardDeviation (numbers) {
    if (!numbers || numbers.length < 2) return 0
    const avg = this.average(numbers)
    const squareDiffs = numbers.map(value => {
      const diff = value - avg
      return diff * diff
    })
    const avgSquareDiff = this.average(squareDiffs)
    return Math.sqrt(avgSquareDiff)
  },

  /**
     * Convierte grados a radianes.
     * @param {number} degrees - Ángulo en grados.
     * @return {number} Ángulo en radianes.
     */
  degreesToRadians (degrees) {
    return degrees * (Math.PI / 180)
  },

  /**
     * Convierte radianes a grados.
     * @param {number} radians - Ángulo en radianes.
     * @return {number} Ángulo en grados.
     */
  radiansToDegrees (radians) {
    return radians * (180 / Math.PI)
  },

  /**
     * Calcula la distancia entre dos puntos 2D.
     * @param {number} x1 - Coordenada X del primer punto.
     * @param {number} y1 - Coordenada Y del primer punto.
     * @param {number} x2 - Coordenada X del segundo punto.
     * @param {number} y2 - Coordenada Y del segundo punto.
     * @return {number} La distancia.
     */
  distance (x1, y1, x2, y2) {
    const dx = x2 - x1
    const dy = y2 - y1
    return Math.sqrt(dx * dx + dy * dy)
  },

  /**
     * Verifica si un número es par.
     * @param {number} num - El número a verificar.
     * @return {boolean} True si es par, false en caso contrario.
     */
  isEven (num) {
    return num % 2 === 0
  },

  /**
     * Verifica si un número es impar.
     * @param {number} num - El número a verificar.
     * @return {boolean} True si es impar, false en caso contrario.
     */
  isOdd (num) {
    return num % 2 !== 0
  },

  /**
     * Calcula el factorial de un número.
     * @param {number} num - Número entero no negativo.
     * @return {number} El factorial.
     */
  factorial (num) {
    if (num < 0) return -1 // O lanzar error
    if (num === 0) return 1
    let result = 1
    for (let i = 2; i <= num; i++) {
      result *= i
    }
    return result
  },

  /**
     * Calcula el máximo común divisor (MCD) de dos números.
     * @param {number} a - Primer número.
     * @param {number} b - Segundo número.
     * @return {number} El MCD.
     */
  gcd (a, b) {
    if (b === 0) {
      return a
    }
    return this.gcd(b, a % b)
  },

  /**
     * Calcula el mínimo común múltiplo (mcm) de dos números.
     * @param {number} a - Primer número.
     * @param {number} b - Segundo número.
     * @return {number} El mcm.
     */
  lcm (a, b) {
    return Math.abs(a * b) / this.gcd(a, b)
  },

  /**
     * Genera un UUID v4 simple.
     * No es criptográficamente seguro, usar para identificadores simples.
     * @return {string} Un UUID v4.
     */
  uuidv4 () {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = Math.random() * 16 | 0; const v = c === 'x' ? r : (r & 0x3 | 0x8)
      return v.toString(16)
    })
  },

  /**
     * Formatea un número como moneda.
     * @param {number} amount - El monto.
     * @param {string} currency - Código de moneda (ej: 'USD', 'COP'). Default: 'USD'.
     * @param {string} locale - Locale para formateo (ej: 'en-US', 'es-CO'). Default: 'es-CO'.
     * @return {string} El monto formateado como moneda.
     */
  formatCurrency (amount, currency = 'USD', locale = 'es-CO') {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        minimumFractionDigits: currency === 'COP' ? 0 : 2, // COP usualmente no usa decimales
        maximumFractionDigits: currency === 'COP' ? 0 : 2
      }).format(amount)
    } catch (error) {
      console.error('Error formateando moneda:', error)
      // Fallback simple
      return `${currency} ${amount.toFixed(2)}`
    }
  },

  /**
     * Calcula el porcentaje de un valor respecto a un total.
     * @param {number} part - La parte.
     * @param {number} total - El total.
     * @param {number} decimals - Número de decimales para el resultado (default: 2).
     * @return {number} El porcentaje (0-100).
     */
  calculatePercentage (part, total, decimals = 2) {
    if (total === 0) return 0
    const percentage = (part / total) * 100
    return this.roundTo(percentage, decimals)
  },

  /**
     * Obtiene el valor de un porcentaje de un total.
     * @param {number} percentage - El porcentaje (0-100).
     * @param {number} total - El total.
     * @return {number} El valor correspondiente al porcentaje.
     */
  getValueFromPercentage (percentage, total) {
    return (percentage / 100) * total
  }
}

// Hacer disponible globalmente si es necesario
if (typeof window !== 'undefined') {
  window.MathUtils = MathUtils

  // Integrar con EcosistemaApp si existe
  if (window.EcosistemaApp && window.EcosistemaApp.utils) {
    window.EcosistemaApp.utils.math = MathUtils
  } else if (window.EcosistemaApp) {
    window.EcosistemaApp.utils = { math: MathUtils }
  }
}

// Para uso como módulo (si es necesario)
// export default MathUtils;
