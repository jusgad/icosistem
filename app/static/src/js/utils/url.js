/**
 * URL Utilities para Ecosistema de Emprendimiento
 * Sistema completo de manejo de URLs, routing y navegación con funcionalidades avanzadas
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

/**
 * Clase principal para manipulación de URLs
 */
class URLHandler {
  constructor (baseURL = null) {
    this.baseURL = baseURL || window.location.origin
    this.cache = new Map()
    this.allowedDomains = [
      window.location.hostname,
      'localhost',
      '127.0.0.1'
    ]

    // Configuración específica del ecosistema
    this.routes = {
      // Rutas públicas
      home: '/',
      about: '/about',
      contact: '/contact',
      login: '/auth/login',
      register: '/auth/register',

      // Rutas de emprendedores
      entrepreneurs: '/entrepreneurs',
      entrepreneurProfile: '/entrepreneurs/:id',
      entrepreneurProjects: '/entrepreneurs/:id/projects',

      // Rutas de proyectos
      projects: '/projects',
      projectDetails: '/projects/:id',
      projectEdit: '/projects/:id/edit',
      projectDocuments: '/projects/:id/documents',

      // Rutas de aliados/mentores
      allies: '/allies',
      allyProfile: '/allies/:id',
      mentorship: '/mentorship',
      mentorshipSession: '/mentorship/sessions/:id',

      // Rutas de administración
      adminDashboard: '/admin',
      adminUsers: '/admin/users',
      adminProjects: '/admin/projects',
      adminAnalytics: '/admin/analytics',

      // Rutas de clientes
      clientDashboard: '/client',
      clientReports: '/client/reports',
      clientDirectory: '/client/directory'
    }

    // Patrones de URL específicos
    this.patterns = {
      slug: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      projectCode: /^PROJ-\d{4}-\d{3}$/,
      userHandle: /^@[a-zA-Z0-9_]{3,20}$/,
      meetingRoom: /^room-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/
    }
  }

  /**
     * Parsea una URL completa
     */
  parse (url) {
    try {
      const parsed = new URL(url, this.baseURL)

      return {
        href: parsed.href,
        origin: parsed.origin,
        protocol: parsed.protocol,
        hostname: parsed.hostname,
        port: parsed.port,
        pathname: parsed.pathname,
        search: parsed.search,
        hash: parsed.hash,
        searchParams: this.parseSearchParams(parsed.search),
        pathSegments: this.parsePathSegments(parsed.pathname),
        isExternal: parsed.origin !== window.location.origin,
        isSecure: parsed.protocol === 'https:',
        domain: parsed.hostname.replace(/^www\./, ''),
        subdomain: this.extractSubdomain(parsed.hostname),
        route: this.identifyRoute(parsed.pathname)
      }
    } catch (error) {
      // // console.error('Error parsing URL:', error)
      return null
    }
  }

  /**
     * Construye una URL con parámetros
     */
  build (path, params = {}, options = {}) {
    const config = {
      baseURL: options.baseURL || this.baseURL,
      absolute: options.absolute !== false,
      encode: options.encode !== false,
      fragment: options.fragment || null,
      ...options
    }

    try {
      // Resolver parámetros en el path (:id, :slug, etc.)
      const resolvedPath = this.resolvePath(path, params)

      // Crear URL base
      const url = config.absolute
        ? new URL(resolvedPath, config.baseURL)
        : new URL(resolvedPath, window.location.origin)

      // Agregar query parameters
      const queryParams = this.extractQueryParams(params)
      Object.entries(queryParams).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          if (Array.isArray(value)) {
            value.forEach(v => url.searchParams.append(key, v))
          } else {
            url.searchParams.set(key, value)
          }
        }
      })

      // Agregar fragment
      if (config.fragment) {
        url.hash = config.fragment.startsWith('#') ? config.fragment : `#${config.fragment}`
      }

      return config.absolute ? url.href : url.pathname + url.search + url.hash
    } catch (error) {
      // // console.error('Error building URL:', error)
      return path
    }
  }

  /**
     * Resuelve parámetros en el path
     */
  resolvePath (path, params) {
    let resolved = path

    // Reemplazar parámetros nombrados (:id, :slug, etc.)
    Object.entries(params).forEach(([key, value]) => {
      if (typeof value === 'string' || typeof value === 'number') {
        resolved = resolved.replace(`:${key}`, encodeURIComponent(value))
        resolved = resolved.replace(`{${key}}`, encodeURIComponent(value))
      }
    })

    return resolved
  }

  /**
     * Extrae query parameters excluyendo path parameters
     */
  extractQueryParams (params) {
    const query = {}

    Object.entries(params).forEach(([key, value]) => {
      // Excluir parámetros que se usan en el path
      if (!key.startsWith('_') && typeof value !== 'object' || Array.isArray(value)) {
        query[key] = value
      }
    })

    return query
  }

  /**
     * Parsea search parameters a objeto
     */
  parseSearchParams (search) {
    const params = {}
    const urlParams = new URLSearchParams(search)

    for (const [key, value] of urlParams) {
      if (params[key]) {
        // Manejar múltiples valores
        if (Array.isArray(params[key])) {
          params[key].push(value)
        } else {
          params[key] = [params[key], value]
        }
      } else {
        params[key] = value
      }
    }

    return params
  }

  /**
     * Parsea path en segmentos
     */
  parsePathSegments (pathname) {
    return pathname.split('/').filter(segment => segment !== '')
  }

  /**
     * Extrae subdominio
     */
  extractSubdomain (hostname) {
    const parts = hostname.split('.')
    return parts.length > 2 ? parts[0] : null
  }

  /**
     * Identifica ruta conocida
     */
  identifyRoute (pathname) {
    for (const [name, pattern] of Object.entries(this.routes)) {
      if (this.matchRoute(pathname, pattern)) {
        return name
      }
    }
    return 'unknown'
  }

  /**
     * Verifica si path coincide con patrón
     */
  matchRoute (path, pattern) {
    const pathSegments = this.parsePathSegments(path)
    const patternSegments = this.parsePathSegments(pattern)

    if (pathSegments.length !== patternSegments.length) {
      return false
    }

    return patternSegments.every((segment, index) => {
      return segment.startsWith(':') || segment === pathSegments[index]
    })
  }

  /**
     * Valida URL
     */
  validate (url, options = {}) {
    const config = {
      allowExternal: options.allowExternal || false,
      requireHTTPS: options.requireHTTPS || false,
      allowedDomains: options.allowedDomains || this.allowedDomains,
      ...options
    }

    try {
      const parsed = this.parse(url)
      if (!parsed) return { valid: false, error: 'Invalid URL format' }

      // Verificar protocolo
      if (config.requireHTTPS && parsed.protocol !== 'https:') {
        return { valid: false, error: 'HTTPS required' }
      }

      // Verificar dominio externo
      if (!config.allowExternal && parsed.isExternal) {
        return { valid: false, error: 'External URLs not allowed' }
      }

      // Verificar dominios permitidos
      if (parsed.isExternal && !config.allowedDomains.includes(parsed.domain)) {
        return { valid: false, error: 'Domain not allowed' }
      }

      return { valid: true, parsed }
    } catch (error) {
      return { valid: false, error: error.message }
    }
  }

  /**
     * Sanitiza URL para prevenir ataques
     */
  sanitize (url, options = {}) {
    const config = {
      removeFragment: options.removeFragment || false,
      allowedProtocols: options.allowedProtocols || ['http:', 'https:'],
      maxLength: options.maxLength || 2048,
      ...options
    }

    try {
      const sanitized = url.trim().substring(0, config.maxLength)

      const parsed = new URL(sanitized, this.baseURL)

      // Verificar protocolo
      if (!config.allowedProtocols.includes(parsed.protocol)) {
        parsed.protocol = 'https:'
      }

      // Remover fragment si se solicita
      if (config.removeFragment) {
        parsed.hash = ''
      }

      // Limpiar path de secuencias peligrosas
      parsed.pathname = parsed.pathname
        .replace(/\.{2,}/g, '') // Remover ../
        .replace(/[<>'"]/g, '') // Remover caracteres peligrosos

      return parsed.href
    } catch (error) {
      // // console.error('Error sanitizing URL:', error)
      return null
    }
  }

  /**
     * Compara dos URLs
     */
  compare (url1, url2, options = {}) {
    const config = {
      ignoreQuery: options.ignoreQuery || false,
      ignoreFragment: options.ignoreFragment || false,
      caseSensitive: options.caseSensitive || false,
      ...options
    }

    try {
      const parsed1 = this.parse(url1)
      const parsed2 = this.parse(url2)

      if (!parsed1 || !parsed2) return false

      let path1 = parsed1.pathname
      let path2 = parsed2.pathname

      if (!config.caseSensitive) {
        path1 = path1.toLowerCase()
        path2 = path2.toLowerCase()
      }

      if (parsed1.origin !== parsed2.origin || path1 !== path2) {
        return false
      }

      if (!config.ignoreQuery && parsed1.search !== parsed2.search) {
        return false
      }

      if (!config.ignoreFragment && parsed1.hash !== parsed2.hash) {
        return false
      }

      return true
    } catch (error) {
      // // console.error('Error comparing URLs:', error)
      return false
    }
  }
}

/**
 * Router simple para SPAs
 */
class SimpleRouter {
  constructor (options = {}) {
    this.routes = new Map()
    this.currentRoute = null
    this.basePath = options.basePath || ''
    this.mode = options.mode || 'history' // 'history' or 'hash'
    this.fallback = options.fallback || null
    this.middleware = []

    this.urlHandler = new URLHandler()

    // Configurar event listeners
    this.setupEventListeners()
  }

  /**
     * Registra una ruta
     */
  route (pattern, handler, options = {}) {
    const config = {
      name: options.name || null,
      middleware: options.middleware || [],
      meta: options.meta || {},
      ...options
    }

    this.routes.set(pattern, {
      pattern,
      handler,
      ...config
    })

    return this
  }

  /**
     * Registra middleware global
     */
  use (middleware) {
    this.middleware.push(middleware)
    return this
  }

  /**
     * Navega a una ruta
     */
  navigate (path, options = {}) {
    const config = {
      replace: options.replace || false,
      trigger: options.trigger !== false,
      ...options
    }

    try {
      const url = this.buildURL(path)

      if (this.mode === 'history') {
        if (config.replace) {
          history.replaceState(null, '', url)
        } else {
          history.pushState(null, '', url)
        }
      } else {
        window.location.hash = url
      }

      if (config.trigger) {
        this.handleRoute(path)
      }
    } catch (error) {
      // // console.error('Navigation error:', error)
    }

    return this
  }

  /**
     * Construye URL para modo actual
     */
  buildURL (path) {
    if (this.mode === 'hash') {
      return `#${this.basePath}${path}`
    } else {
      return `${this.basePath}${path}`
    }
  }

  /**
     * Obtiene path actual
     */
  getCurrentPath () {
    if (this.mode === 'hash') {
      return window.location.hash.slice(1).replace(this.basePath, '') || '/'
    } else {
      return window.location.pathname.replace(this.basePath, '') || '/'
    }
  }

  /**
     * Configura event listeners
     */
  setupEventListeners () {
    if (this.mode === 'history') {
      window.addEventListener('popstate', () => {
        this.handleRoute(this.getCurrentPath())
      })
    } else {
      window.addEventListener('hashchange', () => {
        this.handleRoute(this.getCurrentPath())
      })
    }
  }

  /**
     * Maneja routing
     */
  async handleRoute (path) {
    const route = this.matchRoute(path)

    if (!route) {
      if (this.fallback) {
        return this.handleRoute(this.fallback)
      } else {
        // console.warn('No route found for:', path)
        return
      }
    }

    try {
      // Ejecutar middleware global
      for (const middleware of this.middleware) {
        const result = await middleware(path, route)
        if (result === false) return // Bloquear navegación
      }

      // Ejecutar middleware específico de la ruta
      for (const middleware of route.middleware) {
        const result = await middleware(path, route)
        if (result === false) return
      }

      // Ejecutar handler de la ruta
      this.currentRoute = route
      await route.handler(route.params, route)
    } catch (error) {
      // // console.error('Route handler error:', error)
    }
  }

  /**
     * Encuentra ruta que coincida con path
     */
  matchRoute (path) {
    for (const [pattern, route] of this.routes) {
      const match = this.matchPattern(path, pattern)
      if (match) {
        return {
          ...route,
          params: match.params,
          query: this.urlHandler.parseSearchParams(window.location.search)
        }
      }
    }
    return null
  }

  /**
     * Verifica si path coincide con patrón
     */
  matchPattern (path, pattern) {
    const pathSegments = path.split('/').filter(s => s)
    const patternSegments = pattern.split('/').filter(s => s)

    if (pathSegments.length !== patternSegments.length) {
      return null
    }

    const params = {}

    for (let i = 0; i < patternSegments.length; i++) {
      const patternSegment = patternSegments[i]
      const pathSegment = pathSegments[i]

      if (patternSegment.startsWith(':')) {
        // Parámetro dinámico
        const paramName = patternSegment.slice(1)
        params[paramName] = decodeURIComponent(pathSegment)
      } else if (patternSegment !== pathSegment) {
        // Segmento no coincide
        return null
      }
    }

    return { params }
  }

  /**
     * Inicia el router
     */
  start () {
    this.handleRoute(this.getCurrentPath())
    return this
  }
}

/**
 * Generador de URLs específicas del ecosistema
 */
class EcosystemURLBuilder {
  constructor (urlHandler) {
    this.urlHandler = urlHandler
    this.baseRoutes = {
      // Perfiles
      entrepreneurProfile: '/entrepreneurs/{id}',
      allyProfile: '/allies/{id}',
      organizationProfile: '/organizations/{id}',

      // Proyectos
      projectDetails: '/projects/{id}',
      projectEdit: '/projects/{id}/edit',
      projectDocuments: '/projects/{id}/documents',
      projectTeam: '/projects/{id}/team',

      // Mentoría
      mentorshipSession: '/mentorship/sessions/{id}',
      mentorshipSchedule: '/mentorship/schedule',
      mentorshipFeedback: '/mentorship/sessions/{id}/feedback',

      // Reuniones
      meetingRoom: '/meetings/{id}/room',
      meetingRecording: '/meetings/{id}/recording',

      // Administración
      adminUserDetails: '/admin/users/{id}',
      adminProjectDetails: '/admin/projects/{id}',
      adminAnalytics: '/admin/analytics/{type}',

      // APIs
      apiProjects: '/api/v1/projects',
      apiEntrepreneurs: '/api/v1/entrepreneurs',
      apiMentorship: '/api/v1/mentorship'
    }
  }

  /**
     * Construye URL de perfil de emprendedor
     */
  entrepreneur (id, options = {}) {
    const params = { id, ...options }
    return this.urlHandler.build(this.baseRoutes.entrepreneurProfile, params, options)
  }

  /**
     * Construye URL de perfil de aliado
     */
  ally (id, options = {}) {
    const params = { id, ...options }
    return this.urlHandler.build(this.baseRoutes.allyProfile, params, options)
  }

  /**
     * Construye URL de proyecto
     */
  project (id, section = null, options = {}) {
    let route = this.baseRoutes.projectDetails

    switch (section) {
      case 'edit':
        route = this.baseRoutes.projectEdit
        break
      case 'documents':
        route = this.baseRoutes.projectDocuments
        break
      case 'team':
        route = this.baseRoutes.projectTeam
        break
    }

    const params = { id, ...options }
    return this.urlHandler.build(route, params, options)
  }

  /**
     * Construye URL de sesión de mentoría
     */
  mentorshipSession (id, action = null, options = {}) {
    let route = this.baseRoutes.mentorshipSession

    if (action === 'feedback') {
      route = this.baseRoutes.mentorshipFeedback
    }

    const params = { id, ...options }
    return this.urlHandler.build(route, params, options)
  }

  /**
     * Construye URL de sala de reunión
     */
  meetingRoom (meetingId, options = {}) {
    const params = { id: meetingId, ...options }
    return this.urlHandler.build(this.baseRoutes.meetingRoom, params, options)
  }

  /**
     * Construye URLs de API
     */
  api (endpoint, params = {}, options = {}) {
    const route = this.baseRoutes[`api${endpoint.charAt(0).toUpperCase() + endpoint.slice(1)}`]
    if (!route) {
      throw new Error(`Unknown API endpoint: ${endpoint}`)
    }

    return this.urlHandler.build(route, params, { absolute: true, ...options })
  }

  /**
     * Construye URL SEO-friendly
     */
  seoFriendly (type, data, options = {}) {
    const config = {
      includeId: options.includeId !== false,
      maxLength: options.maxLength || 60,
      ...options
    }

    let path = ''
    const slug = this.generateSlug(data.name || data.title, config.maxLength)

    switch (type) {
      case 'project':
        path = `/projects/${slug}`
        if (config.includeId) {
          path += `-${data.id}`
        }
        break

      case 'entrepreneur':
        path = `/entrepreneurs/${slug}`
        if (config.includeId) {
          path += `-${data.id}`
        }
        break

      case 'ally':
        path = `/allies/${slug}`
        if (config.includeId) {
          path += `-${data.id}`
        }
        break

      case 'blog':
        path = `/blog/${slug}`
        if (config.includeId) {
          path += `-${data.id}`
        }
        break

      default:
        throw new Error(`Unknown SEO type: ${type}`)
    }

    return this.urlHandler.build(path, {}, options)
  }

  /**
     * Genera slug SEO-friendly
     */
  generateSlug (text, maxLength = 60) {
    return text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // Remover acentos
      .replace(/[^\w\s-]/g, '') // Remover caracteres especiales
      .replace(/[\s_-]+/g, '-') // Reemplazar espacios por guiones
      .replace(/^-+|-+$/g, '') // Remover guiones al inicio/final
      .substring(0, maxLength)
      .replace(/-+$/, '') // Remover guión final si se cortó
  }

  /**
     * Extrae ID de URL SEO-friendly
     */
  extractIdFromSeoUrl (url) {
    const match = url.match(/-(\d+)$/)
    return match ? parseInt(match[1]) : null
  }
}

/**
 * Sistema de compartir en redes sociales
 */
class SocialSharing {
  constructor (urlHandler) {
    this.urlHandler = urlHandler
    this.platforms = {
      facebook: {
        url: 'https://www.facebook.com/sharer/sharer.php',
        params: ['u', 'quote']
      },
      twitter: {
        url: 'https://twitter.com/intent/tweet',
        params: ['url', 'text', 'hashtags', 'via']
      },
      linkedin: {
        url: 'https://www.linkedin.com/sharing/share-offsite/',
        params: ['url', 'title', 'summary']
      },
      whatsapp: {
        url: 'https://wa.me/',
        params: ['text']
      },
      telegram: {
        url: 'https://t.me/share/url',
        params: ['url', 'text']
      },
      email: {
        url: 'mailto:',
        params: ['subject', 'body']
      }
    }
  }

  /**
     * Genera URL para compartir
     */
  generateShareURL (platform, data) {
    const config = this.platforms[platform.toLowerCase()]
    if (!config) {
      throw new Error(`Unsupported platform: ${platform}`)
    }

    const params = new URLSearchParams()

    // Mapear datos a parámetros específicos de la plataforma
    switch (platform.toLowerCase()) {
      case 'facebook':
        if (data.url) params.set('u', data.url)
        if (data.quote) params.set('quote', data.quote)
        break

      case 'twitter':
        if (data.url) params.set('url', data.url)
        if (data.text) params.set('text', data.text)
        if (data.hashtags) params.set('hashtags', Array.isArray(data.hashtags) ? data.hashtags.join(',') : data.hashtags)
        if (data.via) params.set('via', data.via)
        break

      case 'linkedin':
        if (data.url) params.set('url', data.url)
        if (data.title) params.set('title', data.title)
        if (data.summary) params.set('summary', data.summary)
        break

      case 'whatsapp':
        const whatsappText = data.text + (data.url ? ` ${data.url}` : '')
        return `${config.url}?text=${encodeURIComponent(whatsappText)}`

      case 'telegram':
        if (data.url) params.set('url', data.url)
        if (data.text) params.set('text', data.text)
        break

      case 'email':
        const emailParams = new URLSearchParams()
        if (data.subject) emailParams.set('subject', data.subject)
        if (data.body) emailParams.set('body', data.body)
        return `${config.url}?${emailParams.toString()}`
    }

    return `${config.url}?${params.toString()}`
  }

  /**
     * Abre ventana de compartir
     */
  share (platform, data, options = {}) {
    const config = {
      popup: options.popup !== false,
      windowFeatures: options.windowFeatures || 'width=600,height=400,scrollbars=yes,resizable=yes',
      ...options
    }

    const shareURL = this.generateShareURL(platform, data)

    if (config.popup && platform.toLowerCase() !== 'email') {
      window.open(shareURL, 'share', config.windowFeatures)
    } else {
      window.location.href = shareURL
    }
  }

  /**
     * Genera datos para compartir proyecto
     */
  projectShareData (project, options = {}) {
    const projectURL = options.url || this.urlHandler.build(`/projects/${project.id}`)

    return {
      url: projectURL,
      title: project.name,
      text: `Conoce el proyecto ${project.name} en nuestro ecosistema de emprendimiento`,
      quote: project.description,
      hashtags: ['emprendimiento', project.industry, 'innovacion'],
      via: 'EcosistemaEmprendimiento',
      subject: `Te comparto el proyecto: ${project.name}`,
      body: `Hola! Te comparto este interesante proyecto de emprendimiento:\n\n${project.name}\n${project.description}\n\nVer más: ${projectURL}`
    }
  }

  /**
     * Genera datos para compartir perfil de emprendedor
     */
  entrepreneurShareData (entrepreneur, options = {}) {
    const profileURL = options.url || this.urlHandler.build(`/entrepreneurs/${entrepreneur.id}`)

    return {
      url: profileURL,
      title: `Perfil de ${entrepreneur.name}`,
      text: `Conoce a ${entrepreneur.name}, emprendedor en nuestro ecosistema`,
      quote: entrepreneur.bio,
      hashtags: ['emprendedor', entrepreneur.industry, 'networking'],
      via: 'EcosistemaEmprendimiento',
      subject: `Te presento a ${entrepreneur.name}`,
      body: `Te comparto el perfil de este emprendedor:\n\n${entrepreneur.name}\n${entrepreneur.bio}\n\nVer perfil: ${profileURL}`
    }
  }
}

/**
 * Sistema de tracking de URLs
 */
class URLTracker {
  constructor () {
    this.trackingData = new Map()
    this.sessionId = this.generateSessionId()
    this.startTime = Date.now()
  }

  /**
     * Rastrea visita a URL
     */
  track (url, data = {}) {
    const timestamp = Date.now()
    const trackingInfo = {
      url,
      timestamp,
      sessionId: this.sessionId,
      referrer: document.referrer,
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      timeOnPreviousPage: this.calculateTimeOnPage(),
      ...data
    }

    // Guardar en memoria
    this.trackingData.set(url, trackingInfo)

    // Enviar al servidor si está configurado
    this.sendTrackingData(trackingInfo)

    // Actualizar última URL
    this.lastURL = url
    this.lastTimestamp = timestamp
  }

  /**
     * Calcula tiempo en página anterior
     */
  calculateTimeOnPage () {
    if (this.lastTimestamp) {
      return Date.now() - this.lastTimestamp
    }
    return 0
  }

  /**
     * Envía datos de tracking al servidor
     */
  async sendTrackingData (data) {
    if (!window.TRACKING_ENDPOINT) return

    try {
      await fetch(window.TRACKING_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
    } catch (error) {
      // // console.error('Error sending tracking data:', error)
    }
  }

  /**
     * Obtiene datos de tracking
     */
  getTrackingData (url = null) {
    if (url) {
      return this.trackingData.get(url)
    }
    return Object.fromEntries(this.trackingData)
  }

  generateSessionId () {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

/**
 * Utilidades para breadcrumbs
 */
class BreadcrumbBuilder {
  constructor (urlHandler) {
    this.urlHandler = urlHandler
    this.labels = {
      // Rutas principales
      '/': 'Inicio',
      '/entrepreneurs': 'Emprendedores',
      '/projects': 'Proyectos',
      '/allies': 'Aliados',
      '/mentorship': 'Mentoría',
      '/admin': 'Administración',
      '/client': 'Cliente',

      // Secciones
      '/edit': 'Editar',
      '/documents': 'Documentos',
      '/team': 'Equipo',
      '/sessions': 'Sesiones',
      '/feedback': 'Retroalimentación',
      '/analytics': 'Analytics',
      '/reports': 'Reportes'
    }
  }

  /**
     * Genera breadcrumb desde URL actual
     */
  generate (customLabels = {}) {
    const path = window.location.pathname
    const segments = this.urlHandler.parsePathSegments(path)
    const breadcrumbs = []

    // Agregar inicio
    breadcrumbs.push({
      label: 'Inicio',
      url: '/',
      active: segments.length === 0
    })

    let currentPath = ''

    segments.forEach((segment, index) => {
      currentPath += `/${segment}`
      const isLast = index === segments.length - 1

      // Obtener label personalizado o por defecto
      const label = customLabels[currentPath] ||
                       this.labels[currentPath] ||
                       this.labels[`/${segment}`] ||
                       this.formatSegment(segment)

      breadcrumbs.push({
        label,
        url: currentPath,
        active: isLast,
        segment
      })
    })

    return breadcrumbs
  }

  /**
     * Formatea segmento para mostrar
     */
  formatSegment (segment) {
    // Si es un ID numérico, intentar obtener nombre del contexto
    if (/^\d+$/.test(segment)) {
      return this.getEntityName(segment) || `ID: ${segment}`
    }

    // Formatear slug
    return segment
      .replace(/-/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase())
  }

  /**
     * Obtiene nombre de entidad por ID (implementar según necesidad)
     */
  getEntityName (id) {
    // Esto debería implementarse para obtener nombres reales
    // desde caché, contexto o API
    return null
  }

  /**
     * Actualiza labels personalizados
     */
  updateLabels (newLabels) {
    Object.assign(this.labels, newLabels)
  }
}

/**
 * API principal del módulo URL
 */
const URLUtils = {
  // Instancias principales
  handler: new URLHandler(),
  router: null, // Se inicializa bajo demanda
  ecosystem: null, // Se inicializa con handler
  social: null, // Se inicializa con handler
  tracker: new URLTracker(),
  breadcrumb: null, // Se inicializa con handler

  /**
     * Inicializar componentes
     */
  init (options = {}) {
    this.ecosystem = new EcosystemURLBuilder(this.handler)
    this.social = new SocialSharing(this.handler)
    this.breadcrumb = new BreadcrumbBuilder(this.handler)

    // Configurar router si se solicita
    if (options.enableRouter) {
      this.router = new SimpleRouter(options.routerOptions)
    }

    // Configurar tracking automático si se solicita
    if (options.enableTracking) {
      this.setupAutoTracking()
    }

    // // console.log('🔗 URL utilities initialized')
  },

  /**
     * Configurar tracking automático
     */
  setupAutoTracking () {
    // Track página inicial
    this.tracker.track(window.location.href, { initial: true })

    // Track cambios de página (SPA)
    const originalPushState = history.pushState
    const originalReplaceState = history.replaceState

    history.pushState = function (...args) {
      originalPushState.apply(this, args)
      URLUtils.tracker.track(window.location.href, { type: 'pushState' })
    }

    history.replaceState = function (...args) {
      originalReplaceState.apply(this, args)
      URLUtils.tracker.track(window.location.href, { type: 'replaceState' })
    }

    // Track popstate
    window.addEventListener('popstate', () => {
      this.tracker.track(window.location.href, { type: 'popstate' })
    })
  },

  // Funciones de conveniencia
  parse: (url) => URLUtils.handler.parse(url),
  build: (path, params, options) => URLUtils.handler.build(path, params, options),
  validate: (url, options) => URLUtils.handler.validate(url, options),
  sanitize: (url, options) => URLUtils.handler.sanitize(url, options),
  compare: (url1, url2, options) => URLUtils.handler.compare(url1, url2, options),

  /**
     * Obtener parámetros de URL actual
     */
  getParams () {
    return this.handler.parseSearchParams(window.location.search)
  },

  /**
     * Actualizar parámetros de URL actual
     */
  updateParams (params, options = {}) {
    const config = {
      replace: options.replace || false,
      merge: options.merge !== false,
      ...options
    }

    const currentParams = config.merge ? this.getParams() : {}
    const newParams = { ...currentParams, ...params }

    // Remover parámetros null/undefined
    Object.keys(newParams).forEach(key => {
      if (newParams[key] === null || newParams[key] === undefined) {
        delete newParams[key]
      }
    })

    const newURL = this.build(window.location.pathname, newParams)

    if (config.replace) {
      history.replaceState(null, '', newURL)
    } else {
      history.pushState(null, '', newURL)
    }

    return newURL
  },

  /**
     * Navegar a URL
     */
  navigate (url, options = {}) {
    const config = {
      replace: options.replace || false,
      external: options.external || false,
      newTab: options.newTab || false,
      ...options
    }

    if (config.newTab) {
      window.open(url, '_blank')
      return
    }

    if (config.external || url.startsWith('http')) {
      window.location.href = url
      return
    }

    if (this.router) {
      this.router.navigate(url, { replace: config.replace })
    } else {
      if (config.replace) {
        history.replaceState(null, '', url)
      } else {
        history.pushState(null, '', url)
      }
    }
  },

  /**
     * Recargar página actual
     */
  reload (forceReload = false) {
    if (forceReload) {
      window.location.reload()
    } else {
      window.location.href = window.location.href
    }
  },

  /**
     * Ir atrás en historial
     */
  back () {
    history.back()
  },

  /**
     * Ir adelante en historial
     */
  forward () {
    history.forward()
  },

  /**
     * Verificar si es URL externa
     */
  isExternal (url) {
    try {
      const parsed = new URL(url, window.location.origin)
      return parsed.origin !== window.location.origin
    } catch {
      return false
    }
  },

  /**
     * Generar URL corta (mock - implementar servicio real)
     */
  async shorten (url, options = {}) {
    // Mock implementation - integrar con servicio real
    const shortId = Math.random().toString(36).substr(2, 8)
    const shortURL = `${window.location.origin}/s/${shortId}`

    // En implementación real, guardar en base de datos
    // // console.log(`Short URL generated: ${shortURL} -> ${url}`)

    return {
      shortURL,
      originalURL: url,
      id: shortId,
      expires: options.expires || null
    }
  }
}

// Auto-inicialización
document.addEventListener('DOMContentLoaded', () => {
  URLUtils.init({
    enableTracking: window.ENABLE_URL_TRACKING || false,
    enableRouter: window.ENABLE_SPA_ROUTER || false
  })
})

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = URLUtils
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.URLUtils = URLUtils
}
