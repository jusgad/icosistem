/**
 * Breadcrumb Component para Ecosistema de Emprendimiento
 * Maneja la navegación contextual para diferentes tipos de usuarios y secciones
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

class BreadcrumbComponent {
  constructor (options = {}) {
    this.container = options.container || document.querySelector('[data-breadcrumb]')
    this.separator = options.separator || '>'
    this.maxItems = options.maxItems || 5
    this.showHome = options.showHome !== false
    this.showIcons = options.showIcons !== false
    this.userRole = options.userRole || this.getCurrentUserRole()
    this.currentPath = window.location.pathname

    // Configuración de rutas y labels personalizados
    this.routeConfig = {
      // Rutas de administrador
      admin: {
        '/admin': { label: 'Panel Admin', icon: 'fas fa-tachometer-alt', home: true },
        '/admin/dashboard': { label: 'Dashboard', icon: 'fas fa-chart-line' },
        '/admin/users': { label: 'Usuarios', icon: 'fas fa-users' },
        '/admin/entrepreneurs': { label: 'Emprendedores', icon: 'fas fa-lightbulb' },
        '/admin/allies': { label: 'Aliados', icon: 'fas fa-handshake' },
        '/admin/organizations': { label: 'Organizaciones', icon: 'fas fa-building' },
        '/admin/programs': { label: 'Programas', icon: 'fas fa-graduation-cap' },
        '/admin/analytics': { label: 'Analytics', icon: 'fas fa-chart-bar' },
        '/admin/settings': { label: 'Configuración', icon: 'fas fa-cog' }
      },

      // Rutas de emprendedor
      entrepreneur: {
        '/entrepreneur': { label: 'Mi Panel', icon: 'fas fa-rocket', home: true },
        '/entrepreneur/dashboard': { label: 'Dashboard', icon: 'fas fa-chart-line' },
        '/entrepreneur/profile': { label: 'Mi Perfil', icon: 'fas fa-user' },
        '/entrepreneur/projects': { label: 'Mis Proyectos', icon: 'fas fa-project-diagram' },
        '/entrepreneur/mentorship': { label: 'Mentoría', icon: 'fas fa-chalkboard-teacher' },
        '/entrepreneur/calendar': { label: 'Calendario', icon: 'fas fa-calendar' },
        '/entrepreneur/documents': { label: 'Documentos', icon: 'fas fa-folder' },
        '/entrepreneur/tasks': { label: 'Tareas', icon: 'fas fa-tasks' },
        '/entrepreneur/messages': { label: 'Mensajes', icon: 'fas fa-envelope' },
        '/entrepreneur/progress': { label: 'Mi Progreso', icon: 'fas fa-chart-line' }
      },

      // Rutas de aliado/mentor
      ally: {
        '/ally': { label: 'Panel Mentor', icon: 'fas fa-chalkboard-teacher', home: true },
        '/ally/dashboard': { label: 'Dashboard', icon: 'fas fa-chart-line' },
        '/ally/profile': { label: 'Mi Perfil', icon: 'fas fa-user' },
        '/ally/entrepreneurs': { label: 'Mis Emprendedores', icon: 'fas fa-users' },
        '/ally/mentorship': { label: 'Sesiones', icon: 'fas fa-video' },
        '/ally/calendar': { label: 'Calendario', icon: 'fas fa-calendar' },
        '/ally/hours': { label: 'Registro Horas', icon: 'fas fa-clock' },
        '/ally/messages': { label: 'Mensajes', icon: 'fas fa-envelope' },
        '/ally/reports': { label: 'Reportes', icon: 'fas fa-file-alt' }
      },

      // Rutas de cliente/stakeholder
      client: {
        '/client': { label: 'Portal Cliente', icon: 'fas fa-eye', home: true },
        '/client/dashboard': { label: 'Dashboard', icon: 'fas fa-chart-line' },
        '/client/directory': { label: 'Directorio', icon: 'fas fa-list' },
        '/client/impact': { label: 'Impacto', icon: 'fas fa-chart-pie' },
        '/client/reports': { label: 'Reportes', icon: 'fas fa-file-alt' },
        '/client/analytics': { label: 'Analytics', icon: 'fas fa-analytics' }
      },

      // Rutas públicas
      public: {
        '/': { label: 'Inicio', icon: 'fas fa-home', home: true },
        '/about': { label: 'Acerca de', icon: 'fas fa-info-circle' },
        '/programs': { label: 'Programas', icon: 'fas fa-graduation-cap' },
        '/entrepreneurs': { label: 'Emprendedores', icon: 'fas fa-lightbulb' },
        '/contact': { label: 'Contacto', icon: 'fas fa-envelope' }
      }
    }

    // Configuraciones especiales para diferentes contextos
    this.specialRoutes = {
      // Rutas que requieren parámetros dinámicos
      dynamics: [
        {
          pattern: /^\/admin\/users\/(\d+)$/,
          generate: (matches) => [
            { path: '/admin', label: 'Panel Admin', icon: 'fas fa-tachometer-alt' },
            { path: '/admin/users', label: 'Usuarios', icon: 'fas fa-users' },
            { path: `/admin/users/${matches[1]}`, label: 'Detalle Usuario', icon: 'fas fa-user' }
          ]
        },
        {
          pattern: /^\/entrepreneur\/projects\/(\d+)$/,
          generate: (matches) => [
            { path: '/entrepreneur', label: 'Mi Panel', icon: 'fas fa-rocket' },
            { path: '/entrepreneur/projects', label: 'Mis Proyectos', icon: 'fas fa-project-diagram' },
            { path: `/entrepreneur/projects/${matches[1]}`, label: 'Detalle Proyecto', icon: 'fas fa-eye' }
          ]
        },
        {
          pattern: /^\/ally\/entrepreneurs\/(\d+)$/,
          generate: (matches) => [
            { path: '/ally', label: 'Panel Mentor', icon: 'fas fa-chalkboard-teacher' },
            { path: '/ally/entrepreneurs', label: 'Mis Emprendedores', icon: 'fas fa-users' },
            { path: `/ally/entrepreneurs/${matches[1]}`, label: 'Perfil Emprendedor', icon: 'fas fa-user' }
          ]
        }
      ]
    }

    this.init()
  }

  /**
     * Inicializa el componente
     */
  init () {
    if (!this.container) {
      // // console.warn('Breadcrumb: Container no encontrado')
      return
    }

    this.render()
    this.bindEvents()

    // Escuchar cambios de ruta para SPAs
    window.addEventListener('popstate', () => {
      this.currentPath = window.location.pathname
      this.render()
    })

    // Evento personalizado para actualizar breadcrumbs
    document.addEventListener('breadcrumb:update', (e) => {
      if (e.detail) {
        this.updateBreadcrumb(e.detail)
      } else {
        this.render()
      }
    })
  }

  /**
     * Obtiene el rol actual del usuario
     */
  getCurrentUserRole () {
    // Intentar obtener del atributo data del body
    const role = document.body.getAttribute('data-user-role')
    if (role) return role

    // Obtener del path URL
    const path = window.location.pathname
    if (path.startsWith('/admin')) return 'admin'
    if (path.startsWith('/entrepreneur')) return 'entrepreneur'
    if (path.startsWith('/ally')) return 'ally'
    if (path.startsWith('/client')) return 'client'

    return 'public'
  }

  /**
     * Genera los elementos del breadcrumb
     */
  generateBreadcrumbItems () {
    // Verificar rutas especiales dinámicas primero
    for (const route of this.specialRoutes.dynamics) {
      const matches = this.currentPath.match(route.pattern)
      if (matches) {
        return route.generate(matches)
      }
    }

    // Generar breadcrumb estándar
    const pathSegments = this.currentPath.split('/').filter(segment => segment)
    const items = []

    // Agregar home si está habilitado
    if (this.showHome) {
      const homeConfig = this.getRouteConfig('/') ||
                              this.getRouteConfig(`/${this.userRole}`) ||
                              { label: 'Inicio', icon: 'fas fa-home' }

      items.push({
        path: this.userRole === 'public' ? '/' : `/${this.userRole}`,
        label: homeConfig.label,
        icon: homeConfig.icon,
        isHome: true
      })
    }

    // Construir ruta progresivamente
    let currentPath = ''
    for (let i = 0; i < pathSegments.length; i++) {
      currentPath += '/' + pathSegments[i]

      // Evitar duplicar home
      if (this.showHome && (currentPath === '/' || currentPath === `/${this.userRole}`)) {
        continue
      }

      const config = this.getRouteConfig(currentPath)
      items.push({
        path: currentPath,
        label: config ? config.label : this.formatSegment(pathSegments[i]),
        icon: config ? config.icon : this.getDefaultIcon(pathSegments[i]),
        isCurrent: i === pathSegments.length - 1
      })
    }

    return this.limitItems(items)
  }

  /**
     * Obtiene la configuración de una ruta
     */
  getRouteConfig (path) {
    const roleConfig = this.routeConfig[this.userRole]
    if (roleConfig && roleConfig[path]) {
      return roleConfig[path]
    }

    // Buscar en configuración pública como fallback
    if (this.routeConfig.public && this.routeConfig.public[path]) {
      return this.routeConfig.public[path]
    }

    return null
  }

  /**
     * Formatea un segmento de URL para mostrar
     */
  formatSegment (segment) {
    return segment
      .replace(/-/g, ' ')
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  /**
     * Obtiene un icono por defecto basado en el segmento
     */
  getDefaultIcon (segment) {
    const iconMap = {
      dashboard: 'fas fa-chart-line',
      profile: 'fas fa-user',
      settings: 'fas fa-cog',
      users: 'fas fa-users',
      projects: 'fas fa-project-diagram',
      tasks: 'fas fa-tasks',
      calendar: 'fas fa-calendar',
      messages: 'fas fa-envelope',
      documents: 'fas fa-folder',
      reports: 'fas fa-file-alt',
      analytics: 'fas fa-chart-bar'
    }

    return iconMap[segment] || 'fas fa-folder'
  }

  /**
     * Limita el número de elementos mostrados
     */
  limitItems (items) {
    if (items.length <= this.maxItems) {
      return items
    }

    // Mantener siempre el primero (home) y último (actual)
    const result = [items[0]]

    // Agregar separador si hay elementos omitidos
    result.push({
      label: '...',
      isEllipsis: true,
      icon: 'fas fa-ellipsis-h'
    })

    // Agregar los últimos elementos
    const remainingSlots = this.maxItems - 2 // -2 por home y actual
    const startIndex = Math.max(1, items.length - remainingSlots)

    for (let i = startIndex; i < items.length; i++) {
      result.push(items[i])
    }

    return result
  }

  /**
     * Renderiza el breadcrumb
     */
  render () {
    const items = this.generateBreadcrumbItems()

    if (items.length === 0) {
      this.container.style.display = 'none'
      return
    }

    this.container.style.display = ''

    const breadcrumbHTML = `
            <nav aria-label="Breadcrumb" class="breadcrumb-nav">
                <ol class="breadcrumb-list" role="list">
                    ${items.map((item, index) => this.renderItem(item, index, items.length)).join('')}
                </ol>
            </nav>
        `

    this.container.innerHTML = breadcrumbHTML

    // Disparar evento de renderizado
    this.dispatchEvent('breadcrumb:rendered', { items })
  }

  /**
     * Renderiza un elemento individual
     */
  renderItem (item, index, total) {
    const isLast = index === total - 1
    const isEllipsis = item.isEllipsis

    if (isEllipsis) {
      return `
                <li class="breadcrumb-item breadcrumb-ellipsis" role="listitem">
                    <span class="breadcrumb-ellipsis-content">
                        ${this.showIcons ? `<i class="${item.icon}" aria-hidden="true"></i>` : ''}
                        <span class="breadcrumb-text">${item.label}</span>
                    </span>
                </li>
            `
    }

    const itemClass = `breadcrumb-item ${item.isHome ? 'breadcrumb-home' : ''} ${item.isCurrent ? 'breadcrumb-current' : ''}`
    const ariaAttributes = item.isCurrent ? 'aria-current="page"' : ''

    const content = `
            ${this.showIcons ? `<i class="${item.icon}" aria-hidden="true"></i>` : ''}
            <span class="breadcrumb-text">${item.label}</span>
        `

    if (isLast || !item.path) {
      return `
                <li class="${itemClass}" role="listitem" ${ariaAttributes}>
                    <span class="breadcrumb-current-content">
                        ${content}
                    </span>
                </li>
            `
    } else {
      return `
                <li class="${itemClass}" role="listitem">
                    <a href="${item.path}" class="breadcrumb-link" data-path="${item.path}">
                        ${content}
                    </a>
                    <span class="breadcrumb-separator" aria-hidden="true">${this.separator}</span>
                </li>
            `
    }
  }

  /**
     * Vincula eventos
     */
  bindEvents () {
    // Manejar clics en los enlaces
    this.container.addEventListener('click', (e) => {
      const link = e.target.closest('.breadcrumb-link')
      if (link) {
        e.preventDefault()
        const path = link.getAttribute('data-path')
        this.navigateTo(path)
      }
    })

    // Navegación por teclado
    this.container.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const link = e.target.closest('.breadcrumb-link')
        if (link) {
          e.preventDefault()
          const path = link.getAttribute('data-path')
          this.navigateTo(path)
        }
      }
    })
  }

  /**
     * Navega a una ruta
     */
  navigateTo (path) {
    // Disparar evento antes de navegar
    const event = this.dispatchEvent('breadcrumb:navigate', {
      path,
      currentPath: this.currentPath
    })

    if (event.defaultPrevented) {
      return
    }

    // Usar History API para SPAs o navegación tradicional
    if (window.history && window.history.pushState) {
      window.history.pushState(null, '', path)
      this.currentPath = path
      this.render()

      // Disparar evento popstate manualmente para SPAs
      window.dispatchEvent(new PopStateEvent('popstate'))
    } else {
      window.location.href = path
    }
  }

  /**
     * Actualiza el breadcrumb manualmente
     */
  updateBreadcrumb (config) {
    if (config.path) {
      this.currentPath = config.path
    }

    if (config.customItems) {
      this.customItems = config.customItems
    }

    if (config.userRole) {
      this.userRole = config.userRole
    }

    this.render()
  }

  /**
     * Agrega configuración de ruta personalizada
     */
  addRouteConfig (role, routes) {
    if (!this.routeConfig[role]) {
      this.routeConfig[role] = {}
    }

    Object.assign(this.routeConfig[role], routes)
  }

  /**
     * Agrega ruta dinámica especial
     */
  addDynamicRoute (pattern, generator) {
    this.specialRoutes.dynamics.push({
      pattern,
      generate: generator
    })
  }

  /**
     * Despacha evento personalizado
     */
  dispatchEvent (eventName, detail) {
    const event = new CustomEvent(eventName, {
      detail,
      bubbles: true,
      cancelable: true
    })

    this.container.dispatchEvent(event)
    return event
  }

  /**
     * Destruye el componente
     */
  destroy () {
    if (this.container) {
      this.container.innerHTML = ''
    }

    // Remover event listeners si es necesario
    // (Los event listeners se limpian automáticamente al limpiar innerHTML)
  }
}

// Inicialización automática
document.addEventListener('DOMContentLoaded', () => {
  // Buscar todos los contenedores de breadcrumb
  const breadcrumbContainers = document.querySelectorAll('[data-breadcrumb]')

  breadcrumbContainers.forEach(container => {
    // Obtener configuración desde atributos data
    const options = {
      container,
      separator: container.getAttribute('data-separator') || '>',
      maxItems: parseInt(container.getAttribute('data-max-items')) || 5,
      showHome: container.getAttribute('data-show-home') !== 'false',
      showIcons: container.getAttribute('data-show-icons') !== 'false',
      userRole: container.getAttribute('data-user-role')
    }

    // Crear instancia
    const breadcrumb = new BreadcrumbComponent(options)

    // Guardar referencia en el elemento
    container._breadcrumbInstance = breadcrumb
  })
})

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = BreadcrumbComponent
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.BreadcrumbComponent = BreadcrumbComponent
}
