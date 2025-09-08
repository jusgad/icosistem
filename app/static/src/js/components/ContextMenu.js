/**
 * ContextMenu Component
 * Sistema avanzado de menú contextual para el ecosistema de emprendimiento
 * Soporta anidación, iconos, acciones dinámicas y personalización completa
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoContextMenu {
  constructor (element, options = {}) {
    this.targetElement = typeof element === 'string' ? document.querySelector(element) : element
    if (!this.targetElement) {
      throw new Error('ContextMenu target element not found')
    }

    this.config = {
      // Configuración básica
      items: options.items || [], // [{ label: 'Opción', icon: 'fa-icon', action: () => {}, disabled: false, separator: false, submenu: [] }]
      trigger: options.trigger || 'contextmenu', // contextmenu, click, hover
      theme: options.theme || 'light', // light, dark

      // Comportamiento
      autoClose: options.autoClose !== false,
      closeOnClick: options.closeOnClick !== false, // Cerrar al hacer click en un item
      preventCloseOnClickInside: options.preventCloseOnClickInside || false,

      // Animaciones
      animation: options.animation !== false,
      animationDuration: options.animationDuration || 150,
      animationType: options.animationType || 'fade', // fade, slide-down

      // Posicionamiento
      positionOffset: options.positionOffset || { x: 5, y: 5 },

      // Callbacks
      onShow: options.onShow || null,
      onHide: options.onHide || null,
      onItemClick: options.onItemClick || null, // Callback global para click en item

      // Contexto del ecosistema
      ecosystemContext: options.ecosystemContext || 'general_context_menu',

      ...options
    }

    this.state = {
      isOpen: false,
      menuElement: null,
      currentPosition: { x: 0, y: 0 },
      activeSubmenu: null
    }

    this.eventListeners = []
    this.init()
  }

  /**
     * Inicialización del componente
     */
  init () {
    try {
      this.setupEventListeners()
      console.log('🖱️ EcoContextMenu initialized successfully for target:', this.targetElement)
    } catch (error) {
      console.error('❌ Error initializing EcoContextMenu:', error)
      this.handleError(error)
    }
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    // Listener para el trigger (contextmenu, click, etc.)
    this.addEventListener(this.targetElement, this.config.trigger, (e) => {
      e.preventDefault()
      e.stopPropagation()
      this.show(e)
    })

    // Cerrar al hacer click fuera
    this.addEventListener(document, 'click', (e) => {
      if (this.state.isOpen &&
                this.state.menuElement &&
                !this.state.menuElement.contains(e.target) &&
                !this.config.preventCloseOnClickInside) {
        this.hide()
      }
    })

    // Cerrar con tecla Escape
    this.addEventListener(document, 'keydown', (e) => {
      if (e.key === 'Escape' && this.state.isOpen) {
        this.hide()
      }
    })
  }

  /**
     * Crear elemento del menú
     */
  createMenuElement (items, isSubmenu = false) {
    const menu = document.createElement('ul')
    menu.className = `eco-context-menu theme-${this.config.theme} ${isSubmenu ? 'submenu' : ''}`
    menu.setAttribute('role', 'menu')

    items.forEach(item => {
      const li = document.createElement('li')
      li.className = 'menu-item'
      li.setAttribute('role', 'menuitem')

      if (item.separator) {
        li.className += ' separator'
        li.setAttribute('role', 'separator')
      } else {
        const button = document.createElement('button')
        button.type = 'button'
        button.className = 'menu-button'

        if (item.icon) {
          const iconEl = document.createElement('i')
          iconEl.className = `menu-icon fa ${item.icon}`
          button.appendChild(iconEl)
        }

        const labelEl = document.createElement('span')
        labelEl.className = 'menu-label'
        labelEl.textContent = item.label
        button.appendChild(labelEl)

        if (item.disabled) {
          button.disabled = true
          li.classList.add('disabled')
          li.setAttribute('aria-disabled', 'true')
        }

        if (item.submenu && item.submenu.length > 0) {
          li.classList.add('has-submenu')
          const arrowEl = document.createElement('i')
          arrowEl.className = 'menu-arrow fa fa-chevron-right'
          button.appendChild(arrowEl)

          // Crear submenu (recursivo)
          const submenuEl = this.createMenuElement(item.submenu, true)
          li.appendChild(submenuEl)

          this.addEventListener(li, 'mouseenter', () => this.showSubmenu(submenuEl, li))
          this.addEventListener(li, 'mouseleave', () => this.hideSubmenu(submenuEl))
        } else if (item.action) {
          this.addEventListener(button, 'click', (e) => {
            e.stopPropagation()
            this.handleItemClick(item, e)
          })
        }
        li.appendChild(button)
      }
      menu.appendChild(li)
    })
    return menu
  }

  /**
     * Mostrar menú
     */
  show (event) {
    // Ocultar cualquier menú existente
    this.hideAllContextMenus()

    this.state.menuElement = this.createMenuElement(this.config.items)
    document.body.appendChild(this.state.menuElement)

    this.positionMenu(event)

    this.state.isOpen = true
    this.state.menuElement.classList.add('open')

    // Aplicar animación
    if (this.config.animation) {
      this.animateMenu('show')
    }

    // Focus en el primer item
    const firstFocusable = this.state.menuElement.querySelector('button:not([disabled])')
    if (firstFocusable) {
      firstFocusable.focus()
    }

    if (this.config.onShow) {
      this.config.onShow(this, event)
    }
  }

  /**
     * Ocultar menú
     */
  hide () {
    if (!this.state.isOpen || !this.state.menuElement) return

    const doHide = () => {
      if (this.state.menuElement) {
        this.state.menuElement.remove()
        this.state.menuElement = null
      }
      this.state.isOpen = false
      this.state.activeSubmenu = null

      if (this.config.onHide) {
        this.config.onHide(this)
      }
    }

    if (this.config.animation) {
      this.animateMenu('hide').then(doHide)
    } else {
      doHide()
    }
  }

  /**
     * Ocultar todos los menús contextuales abiertos
     */
  hideAllContextMenus () {
    document.querySelectorAll('.eco-context-menu.open').forEach(menu => {
      // Si hay una instancia asociada, usar su método hide
      if (menu.ecoContextMenuInstance && menu.ecoContextMenuInstance.hide) {
        menu.ecoContextMenuInstance.hide()
      } else {
        menu.remove() // Fallback
      }
    })
  }

  /**
     * Posicionar menú
     */
  positionMenu (event) {
    const menu = this.state.menuElement
    if (!menu) return

    const clickX = event.clientX
    const clickY = event.clientY

    menu.style.left = `${clickX + this.config.positionOffset.x}px`
    menu.style.top = `${clickY + this.config.positionOffset.y}px`

    // Ajustar si se sale de la pantalla
    const menuRect = menu.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    if (menuRect.right > viewportWidth) {
      menu.style.left = `${viewportWidth - menuRect.width - this.config.positionOffset.x}px`
    }
    if (menuRect.bottom > viewportHeight) {
      menu.style.top = `${viewportHeight - menuRect.height - this.config.positionOffset.y}px`
    }
    if (menuRect.left < 0) {
      menu.style.left = `${this.config.positionOffset.x}px`
    }
    if (menuRect.top < 0) {
      menu.style.top = `${this.config.positionOffset.y}px`
    }

    this.state.currentPosition = { x: parseInt(menu.style.left), y: parseInt(menu.style.top) }
  }

  /**
     * Manejar click en item
     */
  handleItemClick (item, event) {
    if (item.disabled) return

    if (this.config.onItemClick) {
      this.config.onItemClick(item, event, this)
    }

    if (item.action) {
      item.action(event, this.targetElement, item)
    }

    if (this.config.closeOnClick) {
      this.hide()
    }
  }

  /**
     * Mostrar submenu
     */
  showSubmenu (submenuEl, parentLi) {
    if (this.state.activeSubmenu && this.state.activeSubmenu !== submenuEl) {
      this.state.activeSubmenu.classList.remove('open')
    }

    submenuEl.classList.add('open')
    this.state.activeSubmenu = submenuEl

    // Posicionar submenu
    const parentRect = parentLi.getBoundingClientRect()
    const menuRect = this.state.menuElement.getBoundingClientRect()

    submenuEl.style.top = `${parentLi.offsetTop}px`

    // Intentar a la derecha
    let leftPos = parentRect.width
    if (menuRect.left + parentRect.width + submenuEl.offsetWidth > window.innerWidth) {
      // Si no cabe a la derecha, intentar a la izquierda
      leftPos = -submenuEl.offsetWidth
    }
    submenuEl.style.left = `${leftPos}px`
  }

  /**
     * Ocultar submenu
     */
  hideSubmenu (submenuEl) {
    // Pequeño delay para permitir moverse al submenu
    setTimeout(() => {
      if (!submenuEl.matches(':hover') && !submenuEl.parentElement.matches(':hover')) {
        submenuEl.classList.remove('open')
        if (this.state.activeSubmenu === submenuEl) {
          this.state.activeSubmenu = null
        }
      }
    }, 100)
  }

  /**
     * Animar menú
     */
  animateMenu (direction = 'show') {
    return new Promise((resolve) => {
      const menu = this.state.menuElement
      if (!menu) {
        resolve()
        return
      }

      const animationType = this.config.animationType
      const duration = this.config.animationDuration
      let keyframes

      if (animationType === 'fade') {
        keyframes = direction === 'show'
          ? [{ opacity: 0, transform: 'scale(0.95)' }, { opacity: 1, transform: 'scale(1)' }]
          : [{ opacity: 1, transform: 'scale(1)' }, { opacity: 0, transform: 'scale(0.95)' }]
      } else if (animationType === 'slide-down') {
        keyframes = direction === 'show'
          ? [{ opacity: 0, transform: 'translateY(-10px)' }, { opacity: 1, transform: 'translateY(0)' }]
          : [{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(-10px)' }]
      } else {
        resolve() // Sin animación válida
        return
      }

      menu.animate(keyframes, { duration, easing: 'ease-out' }).onfinish = resolve
    })
  }

  /**
     * Manejo de errores
     */
  handleError (error) {
    // Podría mostrar un mensaje de error en la UI o usar un sistema de notificaciones
  }

  /**
     * API pública
     */
  updateItems (newItems) {
    this.config.items = newItems
    if (this.state.isOpen) {
      this.hide()
      // Podríamos re-mostrarlo, pero es mejor que el usuario lo haga
    }
  }

  setTheme (themeName) {
    this.config.theme = themeName
    if (this.state.menuElement) {
      this.state.menuElement.className = `eco-context-menu theme-${themeName} ${this.state.menuElement.classList.contains('submenu') ? 'submenu' : ''} open`
    }
  }

  /**
     * Limpieza
     */
  destroy () {
    this.hide()
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })
    this.eventListeners = []
    console.log('🖱️ EcoContextMenu destroyed for target:', this.targetElement)
  }

  // Helper para añadir event listeners y guardarlos para limpieza
  addEventListener (element, event, handler) {
    element.addEventListener(event, handler)
    this.eventListeners.push({ element, event, handler })
  }
}

// CSS básico para el ContextMenu (se puede mejorar y mover a un archivo .css)
const contextMenuCSS = `
    .eco-context-menu {
        position: fixed;
        z-index: 10000;
        background-color: #fff;
        border: 1px solid #ddd;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        padding: 6px 0;
        min-width: 180px;
        list-style: none;
        margin: 0;
        opacity: 0;
        transform: scale(0.95);
        display: none; /* Oculto por defecto */
    }
    .eco-context-menu.open {
        display: block; /* Mostrar cuando está abierto */
        opacity: 1;
        transform: scale(1);
    }
    .eco-context-menu.theme-dark {
        background-color: #333;
        border-color: #555;
        color: #fff;
    }
    .eco-context-menu .menu-item {
        position: relative;
    }
    .eco-context-menu .menu-button {
        display: flex;
        align-items: center;
        width: 100%;
        padding: 8px 15px;
        background: none;
        border: none;
        text-align: left;
        cursor: pointer;
        font-size: 14px;
        color: #333;
        white-space: nowrap;
    }
    .eco-context-menu.theme-dark .menu-button {
        color: #eee;
    }
    .eco-context-menu .menu-button:hover {
        background-color: #f0f0f0;
    }
    .eco-context-menu.theme-dark .menu-button:hover {
        background-color: #444;
    }
    .eco-context-menu .menu-item.disabled .menu-button {
        color: #aaa;
        cursor: not-allowed;
    }
    .eco-context-menu.theme-dark .menu-item.disabled .menu-button {
        color: #777;
    }
    .eco-context-menu .menu-icon {
        margin-right: 10px;
        width: 16px;
        text-align: center;
        color: #666;
    }
    .eco-context-menu.theme-dark .menu-icon {
        color: #ccc;
    }
    .eco-context-menu .menu-item.separator {
        height: 1px;
        background-color: #eee;
        margin: 6px 0;
        padding: 0;
    }
    .eco-context-menu.theme-dark .menu-item.separator {
        background-color: #555;
    }
    .eco-context-menu .menu-item.has-submenu .menu-arrow {
        margin-left: auto;
        font-size: 0.8em;
        color: #999;
    }
    .eco-context-menu .submenu {
        position: absolute;
        top: -7px; /* Ajustar para alinear con el item padre */
        left: 100%;
        display: none; /* Oculto por defecto */
        margin-left: 1px;
    }
    .eco-context-menu .menu-item:hover > .submenu.open,
    .eco-context-menu .submenu.open {
        display: block;
    }
`

// Inyectar CSS si no existe
if (!document.getElementById('eco-context-menu-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-context-menu-styles'
  style.textContent = contextMenuCSS
  document.head.appendChild(style)
}

// Registrar en el elemento para acceso fácil
Object.defineProperty(EcoContextMenu.prototype, 'register', {
  value: function () {
    this.targetElement.ecoContextMenuInstance = this
  }
})

// Auto-registro
const originalContextMenuInit = EcoContextMenu.prototype.init
EcoContextMenu.prototype.init = function () {
  const result = originalContextMenuInit.call(this)
  this.register()
  return result
}

// Exportar para uso global
window.EcoContextMenu = EcoContextMenu
export default EcoContextMenu
