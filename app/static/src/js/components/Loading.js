/**
 * Loading Component
 * Componente para mostrar indicadores de carga (spinners, barras de progreso)
 * personalizables en el ecosistema.
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoLoading {
  constructor (element, options = {}) {
    this.element = typeof element === 'string' ? document.querySelector(element) : element
    if (!this.element && !options.fullscreen) { // Permitir fullscreen sin elemento específico
      throw new Error('Loading target element not found and not fullscreen')
    }

    this.config = {
      type: options.type || 'spinner', // spinner, dots, bar
      size: options.size || 'md', // sm, md, lg
      message: options.message || 'Cargando...',
      showSpinner: options.showSpinner !== false,
      showText: options.showText !== false,
      overlay: options.overlay || false, // true para overlay sobre el elemento, 'fullscreen' para pantalla completa
      theme: options.theme || 'light', // light, dark
      customClass: options.customClass || '',
      delay: options.delay || 0, // Retraso en ms antes de mostrar
      minDuration: options.minDuration || 0, // Duración mínima en ms para evitar parpadeos
      ...options
    }

    this.state = {
      isVisible: false,
      startTime: null,
      delayTimeout: null,
      minDurationTimeout: null
    }

    this.loadingElement = null
    this.eventListeners = []
    this.init()
  }

  /**
     * Inicialización del componente
     */
  init () {
    try {
      if (this.config.overlay === 'fullscreen' && !this.element) {
        // Crear un elemento contenedor para el loader fullscreen si no se proporcionó uno
        this.element = document.createElement('div')
        this.element.id = `eco-loading-fullscreen-${Date.now()}`
        this.element.style.display = 'none' // Oculto hasta que se llame a show()
        document.body.appendChild(this.element)
      }
      // No renderizar inmediatamente, solo al llamar a show()
      // // // console.log('⏳ EcoLoading initialized for:', this.element || 'fullscreen')
    } catch (error) {
      // // // console.error('❌ Error initializing EcoLoading:', error)
    }
  }

  /**
     * Renderizar el indicador de carga
     */
  render () {
    if (!this.element && this.config.overlay !== 'fullscreen') return // No renderizar si no hay elemento y no es fullscreen

    const overlayClass = this.config.overlay ? (this.config.overlay === 'fullscreen' ? 'eco-loading-overlay-fullscreen' : 'eco-loading-overlay') : ''
    const themeClass = `eco-loading-theme-${this.config.theme}`
    const sizeClass = `eco-loading-size-${this.config.size}`

    let spinnerHTML = ''
    if (this.config.showSpinner) {
      switch (this.config.type) {
        case 'dots':
          spinnerHTML = `
                        <div class="eco-loading-spinner eco-loading-dots">
                            <div></div><div></div><div></div><div></div>
                        </div>`
          break
        case 'bar':
          spinnerHTML = `
                        <div class="eco-loading-spinner eco-loading-bar">
                            <div class="progress"><div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 100%"></div></div>
                        </div>`
          break
        case 'spinner':
        default:
          spinnerHTML = '<div class="eco-loading-spinner eco-loading-spinner-border"></div>'
          break
      }
    }

    const textHTML = this.config.showText && this.config.message ? `<div class="eco-loading-text">${this.config.message}</div>` : ''

    const loadingContentHTML = `
            <div class="eco-loading-content ${sizeClass}">
                ${spinnerHTML}
                ${textHTML}
            </div>
        `

    if (this.config.overlay) {
      this.loadingElement = document.createElement('div')
      this.loadingElement.className = `eco-loading ${overlayClass} ${themeClass} ${this.config.customClass}`
      this.loadingElement.innerHTML = loadingContentHTML

      if (this.config.overlay === 'fullscreen') {
        document.body.appendChild(this.loadingElement)
      } else if (this.element) {
        this.element.style.position = 'relative' // Necesario para el overlay
        this.element.appendChild(this.loadingElement)
      }
    } else if (this.element) {
      this.element.innerHTML = `<div class="eco-loading ${themeClass} ${this.config.customClass}">${loadingContentHTML}</div>`
      this.loadingElement = this.element.firstChild
    }
  }

  /**
     * Mostrar el indicador de carga
     */
  show () {
    if (this.state.isVisible) return

    this.state.startTime = Date.now()
    clearTimeout(this.state.delayTimeout)
    clearTimeout(this.state.minDurationTimeout)

    this.state.delayTimeout = setTimeout(() => {
      if (!this.loadingElement) {
        this.render()
      }
      if (this.loadingElement) {
        this.loadingElement.style.display = this.config.overlay === 'fullscreen' ? 'flex' : 'block' // O el display original
        this.loadingElement.classList.add('eco-loading-visible')
        if (this.config.overlay === 'fullscreen') {
          document.body.classList.add('eco-loading-body-lock')
        }
      }
      this.state.isVisible = true
    }, this.config.delay)
  }

  /**
     * Ocultar el indicador de carga
     */
  hide () {
    if (!this.state.isVisible && !this.state.delayTimeout) return // Si no está visible ni esperando delay

    clearTimeout(this.state.delayTimeout) // Cancelar si aún no se mostró por delay

    const elapsedTime = Date.now() - (this.state.startTime || Date.now())
    const remainingMinDuration = this.config.minDuration - elapsedTime

    if (remainingMinDuration > 0) {
      this.state.minDurationTimeout = setTimeout(() => this._performHide(), remainingMinDuration)
    } else {
      this._performHide()
    }
  }

  _performHide () {
    if (this.loadingElement) {
      this.loadingElement.style.display = 'none'
      this.loadingElement.classList.remove('eco-loading-visible')
      if (this.config.overlay === 'fullscreen') {
        document.body.classList.remove('eco-loading-body-lock')
        // Si el loader fullscreen fue creado dinámicamente, removerlo
        if (this.loadingElement.parentElement === document.body && this.element.id.startsWith('eco-loading-fullscreen-')) {
          this.loadingElement.remove()
          this.loadingElement = null
          this.element.remove() // Remover el div contenedor también
          this.element = null
        }
      } else if (this.config.overlay && this.element && this.loadingElement.parentElement === this.element) {
        // Si es un overlay sobre un elemento, remover el div del loader
        this.loadingElement.remove()
        this.loadingElement = null
      } else if (this.element && !this.config.overlay) {
        // Si no es overlay, limpiar el contenido del elemento
        this.element.innerHTML = ''
        this.loadingElement = null
      }
    }
    this.state.isVisible = false
    this.state.startTime = null
  }

  /**
     * Actualizar mensaje de carga
     * @param {string} message - Nuevo mensaje
     */
  setMessage (message) {
    this.config.message = message
    if (this.state.isVisible && this.loadingElement) {
      const textElement = this.loadingElement.querySelector('.eco-loading-text')
      if (textElement) {
        textElement.textContent = message
      } else if (this.config.showText) {
        // Si no existía y ahora se debe mostrar, re-renderizar una parte
        this.hide()
        this.show()
      }
    }
  }

  /**
     * Limpieza
     */
  destroy () {
    this.hide() // Asegurarse de que esté oculto y timers limpios
    if (this.loadingElement && this.loadingElement.parentElement) {
      this.loadingElement.remove()
    }
    if (this.element && this.element.ecoLoadingInstance) {
      delete this.element.ecoLoadingInstance
    }
    // // // console.log('⏳ EcoLoading destroyed for:', this.element || 'fullscreen')
  }
}

// CSS básico para el Loading (se puede mejorar y mover a un archivo .css)
const loadingCSS = `
    .eco-loading-overlay, .eco-loading-overlay-fullscreen {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    }
    .eco-loading-overlay {
        background-color: rgba(255, 255, 255, 0.7);
    }
    .eco-loading-overlay-fullscreen {
        position: fixed; /* Pantalla completa */
        background-color: rgba(0, 0, 0, 0.5);
    }
    .eco-loading-theme-dark .eco-loading-overlay {
        background-color: rgba(0, 0, 0, 0.7);
    }
    .eco-loading-theme-dark .eco-loading-overlay-fullscreen {
        background-color: rgba(50, 50, 50, 0.8);
    }
    .eco-loading-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 20px;
        border-radius: 8px;
    }
    .eco-loading-theme-light .eco-loading-content {
        background-color: #fff;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        color: #333;
    }
    .eco-loading-theme-dark .eco-loading-content {
        background-color: #424242;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        color: #f5f5f5;
    }
    .eco-loading-spinner-border {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #3498db;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: eco-loading-spin 1s linear infinite;
    }
    .eco-loading-theme-dark .eco-loading-spinner-border {
        border-color: #666;
        border-top-color: #3498db;
    }
    .eco-loading-size-sm .eco-loading-spinner-border { width: 20px; height: 20px; border-width: 2px; }
    .eco-loading-size-lg .eco-loading-spinner-border { width: 60px; height: 60px; border-width: 5px; }

    .eco-loading-dots div {
        display: inline-block;
        width: 10px;
        height: 10px;
        background-color: #3498db;
        border-radius: 50%;
        margin: 0 3px;
        animation: eco-loading-bounce 1.4s infinite ease-in-out both;
    }
    .eco-loading-theme-dark .eco-loading-dots div { background-color: #5dade2; }
    .eco-loading-size-sm .eco-loading-dots div { width: 6px; height: 6px; }
    .eco-loading-size-lg .eco-loading-dots div { width: 14px; height: 14px; }
    .eco-loading-dots div:nth-child(1) { animation-delay: -0.32s; }
    .eco-loading-dots div:nth-child(2) { animation-delay: -0.16s; }

    .eco-loading-bar .progress { width: 150px; height: 8px; background-color: #e9ecef; border-radius: 4px; }
    .eco-loading-bar .progress-bar { background-color: #3498db; }
    .eco-loading-size-sm .eco-loading-bar .progress { width: 100px; height: 5px; }
    .eco-loading-size-lg .eco-loading-bar .progress { width: 200px; height: 10px; }
    
    .eco-loading-text {
        margin-top: 10px;
        font-size: 1em;
    }
    .eco-loading-size-sm .eco-loading-text { font-size: 0.8em; margin-top: 5px; }
    .eco-loading-size-lg .eco-loading-text { font-size: 1.2em; margin-top: 15px; }

    .eco-loading-visible { opacity: 1; transition: opacity 0.3s ease-in-out; }
    .eco-loading-body-lock { overflow: hidden; }

    @keyframes eco-loading-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes eco-loading-bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1.0); }
    }
`

// Inyectar CSS si no existe
if (typeof document !== 'undefined' && !document.getElementById('eco-loading-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-loading-styles'
  style.textContent = loadingCSS
  document.head.appendChild(style)
}

// Registrar en el elemento para acceso fácil
Object.defineProperty(EcoLoading.prototype, 'register', {
  value: function () {
    if (this.element) { // Solo si el elemento existe (puede ser null para fullscreen creado dinámicamente)
      this.element.ecoLoadingInstance = this
    }
  }
})

// Auto-registro
const originalLoadingInit = EcoLoading.prototype.init
EcoLoading.prototype.init = function () {
  const result = originalLoadingInit.call(this)
  this.register()
  return result
}

// Exportar para uso global
if (typeof window !== 'undefined') {
  window.EcoLoading = EcoLoading
}

// Para uso como módulo (si es necesario)
// export default EcoLoading;
