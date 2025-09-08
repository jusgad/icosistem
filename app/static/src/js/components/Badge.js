/**
 * Badge Component
 * Componente para mostrar badges/etiquetas personalizables en el ecosistema.
 * Soporta diferentes estilos, iconos y conteos.
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoBadge {
  constructor (element, options = {}) {
    this.element = typeof element === 'string' ? document.querySelector(element) : element
    if (!this.element) {
      throw new Error('Badge element not found')
    }

    this.config = {
      text: options.text || '',
      type: options.type || 'primary', // primary, secondary, success, danger, warning, info, light, dark
      pill: options.pill || false,
      icon: options.icon || null, // ej: 'fa-check-circle'
      count: options.count || null,
      tooltip: options.tooltip || null,
      closable: options.closable || false,
      onClick: options.onClick || null,
      onClose: options.onClose || null,
      ...options
    }

    this.state = {
      isVisible: true
    }

    this.eventListeners = []
    this.init()
  }

  /**
     * Inicialización del componente
     */
  init () {
    try {
      this.render()
      this.setupEventListeners()
      console.log('🏷️ EcoBadge initialized successfully for:', this.element)
    } catch (error) {
      console.error('❌ Error initializing EcoBadge:', error)
    }
  }

  /**
     * Renderizar el badge
     */
  render () {
    const typeClass = `badge-${this.config.type}`
    const pillClass = this.config.pill ? 'rounded-pill' : ''
    const iconHTML = this.config.icon ? `<i class="fa ${this.config.icon} me-1"></i>` : ''
    const countHTML = this.config.count !== null ? `<span class="badge-count ms-1">${this.config.count}</span>` : ''
    const closableClass = this.config.closable ? 'badge-closable' : ''
    const closeButtonHTML = this.config.closable
      ? '<button type="button" class="btn-close btn-close-sm ms-1" aria-label="Cerrar"></button>'
      : ''

    this.element.className = `badge eco-badge ${typeClass} ${pillClass} ${closableClass}`
    this.element.innerHTML = `${iconHTML}${this.config.text}${countHTML}${closeButtonHTML}`

    if (this.config.tooltip) {
      this.element.setAttribute('title', this.config.tooltip)
      this.element.setAttribute('data-bs-toggle', 'tooltip')
      // Inicializar tooltip si Bootstrap está disponible
      if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        new bootstrap.Tooltip(this.element)
      }
    }

    if (!this.state.isVisible) {
      this.element.style.display = 'none'
    }
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    if (this.config.onClick) {
      this.addEventListener(this.element, 'click', (e) => {
        if (e.target.classList.contains('btn-close')) return // No disparar onClick si se cierra
        this.config.onClick(this, e)
      })
    }

    if (this.config.closable) {
      const closeButton = this.element.querySelector('.btn-close')
      if (closeButton) {
        this.addEventListener(closeButton, 'click', (e) => {
          e.stopPropagation() // Evitar que se dispare el onClick del badge
          this.close()
        })
      }
    }
  }

  /**
     * API pública
     */
  setText (text) {
    this.config.text = text
    this.render()
  }

  setType (type) {
    this.config.type = type
    this.render()
  }

  setIcon (iconClass) {
    this.config.icon = iconClass
    this.render()
  }

  setCount (count) {
    this.config.count = count
    this.render()
  }

  setTooltip (tooltipText) {
    this.config.tooltip = tooltipText
    this.render() // Re-renderizar para actualizar atributos del tooltip
  }

  show () {
    this.state.isVisible = true
    this.element.style.display = '' // O el display original
    this.element.classList.remove('d-none')
  }

  hide () {
    this.state.isVisible = false
    this.element.style.display = 'none'
    this.element.classList.add('d-none')
  }

  toggle () {
    this.state.isVisible ? this.hide() : this.show()
  }

  close () {
    if (this.config.onClose) {
      const canClose = this.config.onClose(this)
      if (canClose === false) return // Permitir cancelar el cierre
    }
    this.hide()
    // Opcionalmente, se podría remover el elemento del DOM
    // this.destroy();
  }

  /**
     * Limpieza
     */
  destroy () {
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })
    this.eventListeners = []
    if (this.element.parentNode) {
      this.element.parentNode.removeChild(this.element)
    }
    console.log('🏷️ EcoBadge destroyed for:', this.element)
  }

  // Helper para añadir event listeners y guardarlos para limpieza
  addEventListener (element, event, handler) {
    element.addEventListener(event, handler)
    this.eventListeners.push({ element, event, handler })
  }
}

// CSS básico para el Badge (se puede mejorar y mover a un archivo .css)
const badgeCSS = `
    .eco-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.35em 0.65em;
        font-size: .85em;
        font-weight: 600;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: .375rem; /* Bootstrap 5 default */
    }
    .eco-badge.rounded-pill {
        border-radius: 50rem;
    }
    .eco-badge .badge-count {
        font-size: 0.8em;
        padding: 0.2em 0.4em;
        border-radius: 0.25rem;
        background-color: rgba(0,0,0,0.15);
    }
    .eco-badge.badge-closable {
        padding-right: 0.3em; /* Espacio para el botón de cerrar */
    }
    .eco-badge .btn-close {
        padding: 0.25em 0.25em;
        margin-left: 0.3em;
        filter: invert(1) grayscale(100%) brightness(200%); /* Para que se vea bien en badges oscuros */
    }
    .eco-badge.badge-light .btn-close,
    .eco-badge.badge-warning .btn-close,
    .eco-badge.badge-info .btn-close {
        filter: none; /* Sin filtro para badges claros */
    }
`

// Inyectar CSS si no existe
if (typeof document !== 'undefined' && !document.getElementById('eco-badge-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-badge-styles'
  style.textContent = badgeCSS
  document.head.appendChild(style)
}

// Registrar en el elemento para acceso fácil
Object.defineProperty(EcoBadge.prototype, 'register', {
  value: function () {
    this.element.ecoBadgeInstance = this
  }
})

// Auto-registro
const originalBadgeInit = EcoBadge.prototype.init
EcoBadge.prototype.init = function () {
  const result = originalBadgeInit.call(this)
  this.register()
  return result
}

// Exportar para uso global
if (typeof window !== 'undefined') {
  window.EcoBadge = EcoBadge
}

// Para uso como módulo (si es necesario)
// export default EcoBadge;
