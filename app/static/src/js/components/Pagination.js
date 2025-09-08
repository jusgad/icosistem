/**
 * Pagination Component
 * Sistema avanzado de paginación para el ecosistema de emprendimiento
 * Soporta múltiples estilos, infinite scroll, virtual scrolling y URL sync
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class EcoPagination {
  constructor (container, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container
    if (!this.container) {
      throw new Error('Pagination container not found')
    }

    this.config = {
      // Configuración básica
      currentPage: options.currentPage || 1,
      totalItems: options.totalItems || 0,
      itemsPerPage: options.itemsPerPage || 10,

      // Opciones de itemsPerPage
      itemsPerPageOptions: options.itemsPerPageOptions || [10, 25, 50, 100],
      showItemsPerPageSelector: options.showItemsPerPageSelector !== false,

      // Configuración de visualización
      maxVisiblePages: options.maxVisiblePages || 7,
      showFirstLast: options.showFirstLast !== false,
      showPrevNext: options.showPrevNext !== false,
      showPageNumbers: options.showPageNumbers !== false,
      showJumpTo: options.showJumpTo !== false,

      // Estilos de paginación
      style: options.style || 'classic', // classic, minimal, rounded, pills, compact
      size: options.size || 'md', // sm, md, lg
      alignment: options.alignment || 'center', // left, center, right

      // Funcionalidades avanzadas
      type: options.type || 'pagination', // pagination, infinite, loadmore, virtual
      enableUrlSync: options.enableUrlSync !== false,
      enableKeyboardNav: options.enableKeyboardNav !== false,
      enableTouchSwipe: options.enableTouchSwipe !== false,

      // Infinite scroll y load more
      loadMoreText: options.loadMoreText || 'Cargar más',
      loadingText: options.loadingText || 'Cargando...',
      noMoreText: options.noMoreText || 'No hay más elementos',

      // Virtual scrolling
      virtualItemHeight: options.virtualItemHeight || 60,
      virtualBufferSize: options.virtualBufferSize || 10,
      virtualEnableSmoothing: options.virtualEnableSmoothing !== false,

      // Contexto del ecosistema
      context: options.context || 'general', // entrepreneurs, projects, mentors, documents
      userRole: options.userRole || 'user',

      // Configuración de datos
      dataSource: options.dataSource || null, // function, URL, or array
      dataParams: options.dataParams || {},
      enablePrefetch: options.enablePrefetch !== false,
      cachePages: options.cachePages !== false,

      // Bulk operations
      enableBulkSelect: options.enableBulkSelect || false,
      bulkActions: options.bulkActions || [],

      // Export y download
      enableExport: options.enableExport || false,
      exportFormats: options.exportFormats || ['csv', 'xlsx', 'pdf'],

      // UI y UX
      showInfo: options.showInfo !== false,
      showTotal: options.showTotal !== false,
      showRange: options.showRange !== false,
      showProgressBar: options.showProgressBar || false,

      // Responsive
      responsiveBreakpoints: options.responsiveBreakpoints || {
        mobile: 576,
        tablet: 768,
        desktop: 992
      },

      // Animaciones
      enableAnimations: options.enableAnimations !== false,
      animationDuration: options.animationDuration || 300,

      // Persistencia
      persistState: options.persistState || false,
      storageKey: options.storageKey || 'eco_pagination_state',

      // Internacionalización
      language: options.language || 'es',
      translations: options.translations || this.getDefaultTranslations(),

      // Analytics
      enableAnalytics: options.enableAnalytics !== false,

      // Callbacks
      onPageChange: options.onPageChange || null,
      onItemsPerPageChange: options.onItemsPerPageChange || null,
      onDataLoad: options.onDataLoad || null,
      onBulkAction: options.onBulkAction || null,
      onError: options.onError || null,

      ...options
    }

    this.state = {
      // Estado de paginación
      currentPage: this.config.currentPage,
      totalItems: this.config.totalItems,
      itemsPerPage: this.config.itemsPerPage,
      totalPages: 0,

      // Estado de datos
      data: [],
      cache: new Map(),
      isLoading: false,
      hasMore: true,

      // Estado de selección
      selectedItems: new Set(),
      selectAll: false,

      // Estado de UI
      deviceType: 'desktop',
      visibleRange: { start: 0, end: 0 },

      // Virtual scrolling
      virtualScrollTop: 0,
      virtualOffset: 0,
      virtualViewportHeight: 0,

      // Infinite scroll
      infiniteData: [],
      infiniteLoading: false,

      // Estado de export
      isExporting: false,
      exportProgress: 0
    }

    this.elements = {}
    this.templates = new Map()
    this.eventListeners = []
    this.intersectionObserver = null
    this.prefetchQueue = []
    this.touchStartX = 0
    this.touchStartY = 0

    this.init()
  }

  /**
     * Inicialización del componente
     */
  async init () {
    try {
      await this.setupTemplates()
      await this.calculateTotalPages()
      await this.detectDeviceType()
      await this.createInterface()
      await this.setupEventListeners()
      await this.restoreState()
      await this.loadInitialData()

      if (this.config.enableUrlSync) {
        await this.syncWithUrl()
      }

      console.log('✅ EcoPagination initialized successfully')
    } catch (error) {
      console.error('❌ Error initializing EcoPagination:', error)
      this.handleError(error)
    }
  }

  /**
     * Configurar templates
     */
  async setupTemplates () {
    // Template principal
    this.templates.set('main', `
            <div class="eco-pagination" 
                 data-style="${this.config.style}" 
                 data-size="${this.config.size}" 
                 data-alignment="${this.config.alignment}"
                 data-context="${this.config.context}">
                
                <!-- Información superior -->
                <div class="pagination-header" style="display: none;">
                    <div class="pagination-info">
                        {{#if showTotal}}
                        <span class="total-items">{{totalItemsText}}</span>
                        {{/if}}
                        {{#if showRange}}
                        <span class="items-range">{{rangeText}}</span>
                        {{/if}}
                        {{#if showProgressBar}}
                        <div class="pagination-progress">
                            <div class="progress">
                                <div class="progress-bar" style="width: {{progressPercent}}%"></div>
                            </div>
                        </div>
                        {{/if}}
                    </div>
                    
                    <div class="pagination-controls">
                        {{#if showItemsPerPageSelector}}
                        <div class="items-per-page-selector">
                            <label for="items-per-page">{{itemsPerPageLabel}}:</label>
                            <select id="items-per-page" class="form-select form-select-sm">
                                {{#each itemsPerPageOptions}}
                                <option value="{{this}}" {{#if selected}}selected{{/if}}>{{this}}</option>
                                {{/each}}
                            </select>
                        </div>
                        {{/if}}
                        
                        {{#if enableBulkSelect}}
                        <div class="bulk-actions" style="display: none;">
                            <span class="selected-count">0 seleccionados</span>
                            <div class="bulk-actions-dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                                        type="button" data-bs-toggle="dropdown">
                                    Acciones
                                </button>
                                <ul class="dropdown-menu">
                                    {{#each bulkActions}}
                                    <li><a class="dropdown-item bulk-action" href="#" data-action="{{action}}">{{label}}</a></li>
                                    {{/each}}
                                </ul>
                            </div>
                        </div>
                        {{/if}}
                        
                        {{#if enableExport}}
                        <div class="export-controls">
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-info dropdown-toggle" 
                                        type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-download"></i> Exportar
                                </button>
                                <ul class="dropdown-menu">
                                    {{#each exportFormats}}
                                    <li><a class="dropdown-item export-action" href="#" data-format="{{this}}">
                                        {{this.toUpperCase()}}
                                    </a></li>
                                    {{/each}}
                                </ul>
                            </div>
                        </div>
                        {{/if}}
                    </div>
                </div>
                
                <!-- Contenedor principal de paginación -->
                <div class="pagination-container">
                    <!-- Paginación clásica -->
                    <div class="pagination-classic" style="display: none;">
                        <nav aria-label="Navegación de páginas">
                            <ul class="pagination pagination-{{size}} justify-content-{{alignment}}">
                                <!-- Se genera dinámicamente -->
                            </ul>
                        </nav>
                    </div>
                    
                    <!-- Load more button -->
                    <div class="pagination-loadmore" style="display: none;">
                        <div class="text-center">
                            <button type="button" class="btn btn-outline-primary btn-load-more">
                                <i class="fas fa-plus"></i> {{loadMoreText}}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Infinite scroll indicator -->
                    <div class="pagination-infinite" style="display: none;">
                        <div class="infinite-loading" style="display: none;">
                            <div class="text-center p-3">
                                <div class="spinner-border spinner-border-sm" role="status">
                                    <span class="visually-hidden">{{loadingText}}</span>
                                </div>
                                <div class="loading-text mt-2">{{loadingText}}</div>
                            </div>
                        </div>
                        <div class="infinite-end" style="display: none;">
                            <div class="text-center p-3 text-muted">
                                <i class="fas fa-check-circle"></i> {{noMoreText}}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Virtual scrolling container -->
                    <div class="pagination-virtual" style="display: none;">
                        <div class="virtual-scrollbar">
                            <div class="virtual-content"></div>
                        </div>
                        <div class="virtual-viewport">
                            <div class="virtual-items"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Jump to page -->
                <div class="pagination-jump" style="display: none;">
                    <div class="jump-to-page">
                        <label for="jump-page">Ir a la página:</label>
                        <div class="input-group input-group-sm">
                            <input type="number" id="jump-page" class="form-control" 
                                   min="1" max="{{totalPages}}" placeholder="Página">
                            <button type="button" class="btn btn-outline-secondary btn-jump">Ir</button>
                        </div>
                    </div>
                </div>
                
                <!-- Loading overlay -->
                <div class="pagination-loading" style="display: none;">
                    <div class="loading-overlay">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">{{loadingText}}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Export progress -->
                <div class="export-progress" style="display: none;">
                    <div class="progress">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             style="width: 0%"></div>
                    </div>
                    <div class="export-status">Preparando exportación...</div>
                </div>
            </div>
        `)

    // Template para botón de página
    this.templates.set('pageButton', `
            <li class="page-item {{#if disabled}}disabled{{/if}} {{#if active}}active{{/if}}">
                <a class="page-link" href="#" data-page="{{page}}" {{#if disabled}}tabindex="-1"{{/if}}>
                    {{#if isEllipsis}}
                        <span aria-hidden="true">&hellip;</span>
                    {{else}}
                        {{text}}
                    {{/if}}
                </a>
            </li>
        `)

    // Template para elemento virtual
    this.templates.set('virtualItem', `
            <div class="virtual-item" data-index="{{index}}" style="height: {{height}}px; top: {{top}}px;">
                {{content}}
            </div>
        `)
  }

  /**
     * Calcular total de páginas
     */
  calculateTotalPages () {
    this.state.totalPages = Math.ceil(this.state.totalItems / this.state.itemsPerPage)
    return this.state.totalPages
  }

  /**
     * Detectar tipo de dispositivo
     */
  detectDeviceType () {
    const width = window.innerWidth

    if (width < this.config.responsiveBreakpoints.mobile) {
      this.state.deviceType = 'mobile'
    } else if (width < this.config.responsiveBreakpoints.tablet) {
      this.state.deviceType = 'tablet'
    } else {
      this.state.deviceType = 'desktop'
    }
  }

  /**
     * Crear interfaz de usuario
     */
  async createInterface () {
    // Preparar datos para el template
    const templateData = {
      showTotal: this.config.showTotal,
      showRange: this.config.showRange,
      showProgressBar: this.config.showProgressBar,
      showItemsPerPageSelector: this.config.showItemsPerPageSelector,
      enableBulkSelect: this.config.enableBulkSelect,
      enableExport: this.config.enableExport,

      totalItemsText: this.getTotalItemsText(),
      rangeText: this.getRangeText(),
      progressPercent: this.getProgressPercent(),
      itemsPerPageLabel: this.translate('itemsPerPage'),
      loadMoreText: this.translate('loadMore'),
      loadingText: this.translate('loading'),
      noMoreText: this.translate('noMore'),

      itemsPerPageOptions: this.config.itemsPerPageOptions.map(option => ({
        value: option,
        selected: option === this.state.itemsPerPage
      })),

      bulkActions: this.config.bulkActions,
      exportFormats: this.config.exportFormats,

      size: this.config.size,
      alignment: this.config.alignment,
      totalPages: this.state.totalPages
    }

    // Renderizar template principal
    this.container.innerHTML = this.renderTemplate(this.templates.get('main'), templateData)

    // Obtener referencias a elementos
    this.elements = {
      header: this.container.querySelector('.pagination-header'),
      info: this.container.querySelector('.pagination-info'),
      controls: this.container.querySelector('.pagination-controls'),
      container: this.container.querySelector('.pagination-container'),
      classic: this.container.querySelector('.pagination-classic'),
      loadMore: this.container.querySelector('.pagination-loadmore'),
      infinite: this.container.querySelector('.pagination-infinite'),
      virtual: this.container.querySelector('.pagination-virtual'),
      jump: this.container.querySelector('.pagination-jump'),
      loading: this.container.querySelector('.pagination-loading'),
      exportProgress: this.container.querySelector('.export-progress'),

      // Controles específicos
      itemsPerPageSelect: this.container.querySelector('#items-per-page'),
      jumpInput: this.container.querySelector('#jump-page'),
      jumpButton: this.container.querySelector('.btn-jump'),
      loadMoreButton: this.container.querySelector('.btn-load-more'),

      // Elementos de paginación
      pagination: this.container.querySelector('.pagination'),

      // Bulk actions
      bulkActions: this.container.querySelector('.bulk-actions'),
      selectedCount: this.container.querySelector('.selected-count'),

      // Virtual scrolling
      virtualViewport: this.container.querySelector('.virtual-viewport'),
      virtualItems: this.container.querySelector('.virtual-items'),
      virtualScrollbar: this.container.querySelector('.virtual-scrollbar'),
      virtualContent: this.container.querySelector('.virtual-content')
    }

    // Mostrar header si hay contenido
    if (this.config.showInfo || this.config.showItemsPerPageSelector ||
            this.config.enableBulkSelect || this.config.enableExport) {
      this.elements.header.style.display = 'flex'
    }

    // Renderizar paginación según el tipo
    this.renderPagination()

    // Aplicar responsive design
    this.applyResponsiveLayout()
  }

  /**
     * Renderizar paginación según el tipo
     */
  renderPagination () {
    // Ocultar todos los tipos
    this.elements.classic.style.display = 'none'
    this.elements.loadMore.style.display = 'none'
    this.elements.infinite.style.display = 'none'
    this.elements.virtual.style.display = 'none'

    switch (this.config.type) {
      case 'pagination':
        this.renderClassicPagination()
        break
      case 'loadmore':
        this.renderLoadMorePagination()
        break
      case 'infinite':
        this.renderInfiniteScroll()
        break
      case 'virtual':
        this.renderVirtualScrolling()
        break
    }

    // Mostrar jump to page si está habilitado
    if (this.config.showJumpTo && this.config.type === 'pagination') {
      this.elements.jump.style.display = 'block'
    }
  }

  /**
     * Renderizar paginación clásica
     */
  renderClassicPagination () {
    if (this.state.totalPages <= 1) return

    this.elements.classic.style.display = 'block'
    const pagination = this.elements.pagination
    pagination.innerHTML = ''

    const pages = this.calculateVisiblePages()

    pages.forEach(page => {
      const pageElement = this.createPageElement(page)
      pagination.appendChild(pageElement)
    })
  }

  /**
     * Calcular páginas visibles
     */
  calculateVisiblePages () {
    const current = this.state.currentPage
    const total = this.state.totalPages
    const max = Math.min(this.config.maxVisiblePages, total)
    const pages = []

    // Botón "Primera página"
    if (this.config.showFirstLast && current > 1) {
      pages.push({
        page: 1,
        text: '«',
        type: 'first',
        disabled: false,
        active: false
      })
    }

    // Botón "Anterior"
    if (this.config.showPrevNext) {
      pages.push({
        page: current - 1,
        text: '‹',
        type: 'prev',
        disabled: current <= 1,
        active: false
      })
    }

    // Lógica para páginas numéricas
    let startPage, endPage

    if (total <= max) {
      // Mostrar todas las páginas
      startPage = 1
      endPage = total
    } else {
      // Calcular rango dinámico
      const halfMax = Math.floor(max / 2)

      if (current <= halfMax) {
        startPage = 1
        endPage = max
      } else if (current >= total - halfMax) {
        startPage = total - max + 1
        endPage = total
      } else {
        startPage = current - halfMax
        endPage = current + halfMax
      }
    }

    // Agregar ellipsis al inicio si es necesario
    if (startPage > 1) {
      if (startPage > 2) {
        pages.push({
          page: null,
          text: '...',
          type: 'ellipsis',
          disabled: true,
          active: false,
          isEllipsis: true
        })
      }
    }

    // Agregar páginas numéricas
    for (let i = startPage; i <= endPage; i++) {
      pages.push({
        page: i,
        text: i.toString(),
        type: 'page',
        disabled: false,
        active: i === current
      })
    }

    // Agregar ellipsis al final si es necesario
    if (endPage < total) {
      if (endPage < total - 1) {
        pages.push({
          page: null,
          text: '...',
          type: 'ellipsis',
          disabled: true,
          active: false,
          isEllipsis: true
        })
      }
    }

    // Botón "Siguiente"
    if (this.config.showPrevNext) {
      pages.push({
        page: current + 1,
        text: '›',
        type: 'next',
        disabled: current >= total,
        active: false
      })
    }

    // Botón "Última página"
    if (this.config.showFirstLast && current < total) {
      pages.push({
        page: total,
        text: '»',
        type: 'last',
        disabled: false,
        active: false
      })
    }

    return pages
  }

  /**
     * Crear elemento de página
     */
  createPageElement (pageData) {
    const li = document.createElement('li')
    li.innerHTML = this.renderTemplate(this.templates.get('pageButton'), pageData)

    const element = li.firstElementChild

    // Agregar event listener
    if (!pageData.disabled && !pageData.isEllipsis) {
      const link = element.querySelector('.page-link')
      link.addEventListener('click', (e) => {
        e.preventDefault()
        this.goToPage(pageData.page)
      })
    }

    return element
  }

  /**
     * Renderizar paginación Load More
     */
  renderLoadMorePagination () {
    this.elements.loadMore.style.display = 'block'

    const button = this.elements.loadMoreButton
    button.disabled = !this.state.hasMore || this.state.isLoading

    if (!this.state.hasMore) {
      button.innerHTML = `<i class="fas fa-check"></i> ${this.translate('noMore')}`
      button.classList.add('btn-success')
      button.classList.remove('btn-outline-primary')
    }
  }

  /**
     * Renderizar infinite scroll
     */
  renderInfiniteScroll () {
    this.elements.infinite.style.display = 'block'

    // Configurar intersection observer
    if (!this.intersectionObserver) {
      this.intersectionObserver = new IntersectionObserver(
        (entries) => this.handleInfiniteScroll(entries),
        { rootMargin: '100px' }
      )
    }

    // Observar el indicador de carga
    const loadingIndicator = this.elements.infinite.querySelector('.infinite-loading')
    this.intersectionObserver.observe(loadingIndicator)
  }

  /**
     * Renderizar virtual scrolling
     */
  renderVirtualScrolling () {
    this.elements.virtual.style.display = 'block'

    // Configurar virtual scrolling
    this.setupVirtualScrolling()
  }

  /**
     * Configurar event listeners
     */
  async setupEventListeners () {
    // Items per page selector
    if (this.elements.itemsPerPageSelect) {
      this.elements.itemsPerPageSelect.addEventListener('change', (e) => {
        this.changeItemsPerPage(parseInt(e.target.value))
      })
    }

    // Jump to page
    if (this.elements.jumpButton) {
      this.elements.jumpButton.addEventListener('click', () => {
        const page = parseInt(this.elements.jumpInput.value)
        if (page >= 1 && page <= this.state.totalPages) {
          this.goToPage(page)
        }
      })

      this.elements.jumpInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.elements.jumpButton.click()
        }
      })
    }

    // Load more button
    if (this.elements.loadMoreButton) {
      this.elements.loadMoreButton.addEventListener('click', () => {
        this.loadMore()
      })
    }

    // Bulk actions
    this.setupBulkActionListeners()

    // Export actions
    this.setupExportListeners()

    // Keyboard navigation
    if (this.config.enableKeyboardNav) {
      this.setupKeyboardNavigation()
    }

    // Touch swipe navigation
    if (this.config.enableTouchSwipe) {
      this.setupTouchNavigation()
    }

    // Window resize
    window.addEventListener('resize', this.debounce(() => {
      this.detectDeviceType()
      this.applyResponsiveLayout()
    }, 250))

    // URL changes (popstate)
    if (this.config.enableUrlSync) {
      window.addEventListener('popstate', () => {
        this.syncFromUrl()
      })
    }
  }

  /**
     * Configurar listeners de bulk actions
     */
  setupBulkActionListeners () {
    if (!this.config.enableBulkSelect) return

    // Bulk action buttons
    this.container.addEventListener('click', (e) => {
      if (e.target.classList.contains('bulk-action')) {
        e.preventDefault()
        const action = e.target.dataset.action
        this.executeBulkAction(action)
      }
    })
  }

  /**
     * Configurar listeners de export
     */
  setupExportListeners () {
    if (!this.config.enableExport) return

    this.container.addEventListener('click', (e) => {
      if (e.target.classList.contains('export-action')) {
        e.preventDefault()
        const format = e.target.dataset.format
        this.exportData(format)
      }
    })
  }

  /**
     * Configurar navegación por teclado
     */
  setupKeyboardNavigation () {
    document.addEventListener('keydown', (e) => {
      // Solo si el container está visible y enfocado
      if (!this.container.contains(document.activeElement)) return

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault()
          this.goToPrevious()
          break
        case 'ArrowRight':
          e.preventDefault()
          this.goToNext()
          break
        case 'Home':
          e.preventDefault()
          this.goToFirst()
          break
        case 'End':
          e.preventDefault()
          this.goToLast()
          break
      }
    })
  }

  /**
     * Configurar navegación táctil
     */
  setupTouchNavigation () {
    this.container.addEventListener('touchstart', (e) => {
      this.touchStartX = e.touches[0].clientX
      this.touchStartY = e.touches[0].clientY
    })

    this.container.addEventListener('touchend', (e) => {
      const touchEndX = e.changedTouches[0].clientX
      const touchEndY = e.changedTouches[0].clientY

      const deltaX = touchEndX - this.touchStartX
      const deltaY = touchEndY - this.touchStartY

      // Solo si el movimiento horizontal es mayor que el vertical
      if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
        if (deltaX > 0) {
          this.goToPrevious() // Swipe right = previous
        } else {
          this.goToNext() // Swipe left = next
        }
      }
    })
  }

  /**
     * Ir a página específica
     */
  async goToPage (page) {
    if (page < 1 || page > this.state.totalPages || page === this.state.currentPage) {
      return
    }

    const previousPage = this.state.currentPage
    this.state.currentPage = page

    try {
      // Mostrar loading
      this.showLoading()

      // Cargar datos
      await this.loadPageData(page)

      // Actualizar UI
      this.updateInterface()

      // Sincronizar con URL
      if (this.config.enableUrlSync) {
        this.updateUrl()
      }

      // Persistir estado
      if (this.config.persistState) {
        this.saveState()
      }

      // Callback
      if (this.config.onPageChange) {
        await this.config.onPageChange(page, previousPage, this.state.data)
      }

      // Analytics
      if (this.config.enableAnalytics) {
        this.trackPageChange(page, previousPage)
      }
    } catch (error) {
      // Revertir cambio en caso de error
      this.state.currentPage = previousPage
      this.handleError(error)
    } finally {
      this.hideLoading()
    }
  }

  /**
     * Cambiar items por página
     */
  async changeItemsPerPage (newItemsPerPage) {
    if (newItemsPerPage === this.state.itemsPerPage) return

    const oldItemsPerPage = this.state.itemsPerPage
    this.state.itemsPerPage = newItemsPerPage

    // Recalcular página actual para mantener la posición relativa
    const currentIndex = (this.state.currentPage - 1) * oldItemsPerPage
    this.state.currentPage = Math.floor(currentIndex / newItemsPerPage) + 1

    // Recalcular total de páginas
    this.calculateTotalPages()

    try {
      // Cargar datos con nuevo tamaño
      await this.loadPageData(this.state.currentPage)

      // Actualizar UI
      this.updateInterface()

      // Callback
      if (this.config.onItemsPerPageChange) {
        await this.config.onItemsPerPageChange(newItemsPerPage, oldItemsPerPage)
      }
    } catch (error) {
      // Revertir cambios
      this.state.itemsPerPage = oldItemsPerPage
      this.calculateTotalPages()
      this.handleError(error)
    }
  }

  /**
     * Cargar más elementos (Load More)
     */
  async loadMore () {
    if (this.state.isLoading || !this.state.hasMore) return

    try {
      this.state.isLoading = true
      this.elements.loadMoreButton.disabled = true
      this.elements.loadMoreButton.innerHTML = `
                <div class="spinner-border spinner-border-sm" role="status"></div>
                ${this.translate('loading')}
            `

      const nextPage = this.state.currentPage + 1
      const newData = await this.loadPageData(nextPage, false)

      // Agregar datos a los existentes
      this.state.data = [...this.state.data, ...newData]
      this.state.currentPage = nextPage

      // Verificar si hay más datos
      this.state.hasMore = nextPage < this.state.totalPages

      // Actualizar UI
      this.updateInterface()

      // Callback
      if (this.config.onDataLoad) {
        await this.config.onDataLoad(newData, 'loadmore')
      }
    } catch (error) {
      this.handleError(error)
    } finally {
      this.state.isLoading = false
      this.elements.loadMoreButton.disabled = false
      this.elements.loadMoreButton.innerHTML = `<i class="fas fa-plus"></i> ${this.translate('loadMore')}`
    }
  }

  /**
     * Manejar infinite scroll
     */
  async handleInfiniteScroll (entries) {
    const entry = entries[0]

    if (entry.isIntersecting && !this.state.infiniteLoading && this.state.hasMore) {
      await this.loadInfiniteData()
    }
  }

  /**
     * Cargar datos para infinite scroll
     */
  async loadInfiniteData () {
    if (this.state.infiniteLoading || !this.state.hasMore) return

    try {
      this.state.infiniteLoading = true
      this.showInfiniteLoading()

      const nextPage = Math.floor(this.state.infiniteData.length / this.state.itemsPerPage) + 1
      const newData = await this.loadPageData(nextPage, false)

      // Agregar datos al array infinito
      this.state.infiniteData = [...this.state.infiniteData, ...newData]

      // Verificar si hay más datos
      this.state.hasMore = this.state.infiniteData.length < this.state.totalItems

      // Actualizar UI
      if (!this.state.hasMore) {
        this.showInfiniteEnd()
      }

      // Callback
      if (this.config.onDataLoad) {
        await this.config.onDataLoad(newData, 'infinite')
      }
    } catch (error) {
      this.handleError(error)
    } finally {
      this.state.infiniteLoading = false
      this.hideInfiniteLoading()
    }
  }

  /**
     * Configurar virtual scrolling
     */
  setupVirtualScrolling () {
    const viewport = this.elements.virtualViewport
    const scrollbar = this.elements.virtualScrollbar

    // Calcular altura del viewport
    this.state.virtualViewportHeight = viewport.clientHeight

    // Configurar altura total del scrollbar
    const totalHeight = this.state.totalItems * this.config.virtualItemHeight
    this.elements.virtualContent.style.height = `${totalHeight}px`

    // Event listener para scroll
    viewport.addEventListener('scroll', () => {
      this.handleVirtualScroll()
    })

    // Render inicial
    this.renderVirtualItems()
  }

  /**
     * Manejar scroll virtual
     */
  handleVirtualScroll () {
    const scrollTop = this.elements.virtualViewport.scrollTop
    this.state.virtualScrollTop = scrollTop

    // Calcular items visibles
    const startIndex = Math.floor(scrollTop / this.config.virtualItemHeight)
    const endIndex = Math.min(
      startIndex + Math.ceil(this.state.virtualViewportHeight / this.config.virtualItemHeight) + this.config.virtualBufferSize,
      this.state.totalItems - 1
    )

    this.state.visibleRange = { start: startIndex, end: endIndex }

    // Re-render items visibles
    this.renderVirtualItems()
  }

  /**
     * Renderizar items virtuales
     */
  async renderVirtualItems () {
    const { start, end } = this.state.visibleRange
    const container = this.elements.virtualItems

    // Cargar datos si es necesario
    const pageStart = Math.floor(start / this.state.itemsPerPage) + 1
    const pageEnd = Math.floor(end / this.state.itemsPerPage) + 1

    for (let page = pageStart; page <= pageEnd; page++) {
      if (!this.state.cache.has(page)) {
        await this.loadPageData(page, true)
      }
    }

    // Limpiar container
    container.innerHTML = ''

    // Renderizar items visibles
    for (let i = start; i <= end; i++) {
      const item = await this.getVirtualItem(i)
      if (item) {
        const element = this.createVirtualElement(item, i)
        container.appendChild(element)
      }
    }
  }

  /**
     * Cargar datos de página
     */
  async loadPageData (page, cache = true) {
    // Verificar caché
    if (cache && this.state.cache.has(page)) {
      return this.state.cache.get(page)
    }

    let data = []

    if (typeof this.config.dataSource === 'function') {
      // Función personalizada
      data = await this.config.dataSource(page, this.state.itemsPerPage, this.config.dataParams)
    } else if (typeof this.config.dataSource === 'string') {
      // URL endpoint
      data = await this.loadFromUrl(page)
    } else if (Array.isArray(this.config.dataSource)) {
      // Array estático
      data = this.loadFromArray(page)
    }

    // Guardar en caché si está habilitado
    if (this.config.cachePages && cache) {
      this.state.cache.set(page, data)
    }

    // Actualizar estado
    if (!cache) {
      this.state.data = data
    }

    return data
  }

  /**
     * Cargar datos desde URL
     */
  async loadFromUrl (page) {
    const url = new URL(this.config.dataSource, window.location.origin)
    url.searchParams.set('page', page)
    url.searchParams.set('per_page', this.state.itemsPerPage)

    // Agregar parámetros adicionales
    Object.entries(this.config.dataParams).forEach(([key, value]) => {
      url.searchParams.set(key, value)
    })

    const response = await fetch(url, {
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
        Accept: 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const result = await response.json()

    // Actualizar totales si están incluidos
    if (result.total !== undefined) {
      this.state.totalItems = result.total
      this.calculateTotalPages()
    }

    return result.data || result.items || result
  }

  /**
     * Cargar datos desde array
     */
  loadFromArray (page) {
    const start = (page - 1) * this.state.itemsPerPage
    const end = start + this.state.itemsPerPage
    return this.config.dataSource.slice(start, end)
  }

  /**
     * Actualizar interfaz
     */
  updateInterface () {
    // Actualizar información
    this.updateInfo()

    // Renderizar paginación
    this.renderPagination()

    // Actualizar controles
    this.updateControls()

    // Actualizar jump input
    if (this.elements.jumpInput) {
      this.elements.jumpInput.max = this.state.totalPages
    }
  }

  /**
     * Actualizar información
     */
  updateInfo () {
    if (this.elements.info) {
      const totalText = this.getTotalItemsText()
      const rangeText = this.getRangeText()

      // Actualizar textos
      const totalElement = this.elements.info.querySelector('.total-items')
      const rangeElement = this.elements.info.querySelector('.items-range')

      if (totalElement) totalElement.textContent = totalText
      if (rangeElement) rangeElement.textContent = rangeText

      // Actualizar barra de progreso
      if (this.config.showProgressBar) {
        const progressBar = this.elements.info.querySelector('.progress-bar')
        if (progressBar) {
          progressBar.style.width = `${this.getProgressPercent()}%`
        }
      }
    }
  }

  /**
     * Actualizar controles
     */
  updateControls () {
    // Actualizar selector de items per page
    if (this.elements.itemsPerPageSelect) {
      this.elements.itemsPerPageSelect.value = this.state.itemsPerPage
    }

    // Actualizar bulk actions
    this.updateBulkActions()
  }

  /**
     * Aplicar layout responsive
     */
  applyResponsiveLayout () {
    const container = this.container

    // Remover clases anteriores
    container.classList.remove('mobile-layout', 'tablet-layout', 'desktop-layout')

    // Agregar clase según dispositivo
    container.classList.add(`${this.state.deviceType}-layout`)

    // Ajustar maxVisiblePages según dispositivo
    let maxVisible = this.config.maxVisiblePages

    if (this.state.deviceType === 'mobile') {
      maxVisible = Math.min(5, this.config.maxVisiblePages)
    } else if (this.state.deviceType === 'tablet') {
      maxVisible = Math.min(7, this.config.maxVisiblePages)
    }

    // Re-renderizar si cambió
    if (maxVisible !== this.config.maxVisiblePages) {
      const originalMax = this.config.maxVisiblePages
      this.config.maxVisiblePages = maxVisible
      this.renderPagination()
      this.config.maxVisiblePages = originalMax // Restaurar original
    }
  }

  /**
     * Métodos de navegación
     */
  goToNext () {
    if (this.state.currentPage < this.state.totalPages) {
      this.goToPage(this.state.currentPage + 1)
    }
  }

  goToPrevious () {
    if (this.state.currentPage > 1) {
      this.goToPage(this.state.currentPage - 1)
    }
  }

  goToFirst () {
    this.goToPage(1)
  }

  goToLast () {
    this.goToPage(this.state.totalPages)
  }

  /**
     * Métodos de bulk actions
     */
  updateBulkActions () {
    if (!this.config.enableBulkSelect) return

    const selectedCount = this.state.selectedItems.size
    const bulkActions = this.elements.bulkActions
    const countElement = this.elements.selectedCount

    if (selectedCount > 0) {
      bulkActions.style.display = 'flex'
      countElement.textContent = `${selectedCount} seleccionado${selectedCount !== 1 ? 's' : ''}`
    } else {
      bulkActions.style.display = 'none'
    }
  }

  selectItem (itemId) {
    this.state.selectedItems.add(itemId)
    this.updateBulkActions()
  }

  deselectItem (itemId) {
    this.state.selectedItems.delete(itemId)
    this.updateBulkActions()
  }

  selectAll () {
    // Agregar todos los items de la página actual
    this.state.data.forEach(item => {
      this.state.selectedItems.add(item.id)
    })
    this.state.selectAll = true
    this.updateBulkActions()
  }

  deselectAll () {
    this.state.selectedItems.clear()
    this.state.selectAll = false
    this.updateBulkActions()
  }

  async executeBulkAction (action) {
    if (this.state.selectedItems.size === 0) return

    try {
      if (this.config.onBulkAction) {
        await this.config.onBulkAction(action, Array.from(this.state.selectedItems))
      }

      // Limpiar selección después de la acción
      this.deselectAll()
    } catch (error) {
      this.handleError(error)
    }
  }

  /**
     * Métodos de export
     */
  async exportData (format) {
    if (this.state.isExporting) return

    try {
      this.state.isExporting = true
      this.showExportProgress()

      // Obtener todos los datos
      const allData = await this.getAllData()

      // Exportar según formato
      switch (format.toLowerCase()) {
        case 'csv':
          this.exportToCSV(allData)
          break
        case 'xlsx':
          this.exportToExcel(allData)
          break
        case 'pdf':
          this.exportToPDF(allData)
          break
        default:
          throw new Error(`Formato no soportado: ${format}`)
      }
    } catch (error) {
      this.handleError(error)
    } finally {
      this.state.isExporting = false
      this.hideExportProgress()
    }
  }

  async getAllData () {
    const allData = []

    for (let page = 1; page <= this.state.totalPages; page++) {
      this.updateExportProgress(((page - 1) / this.state.totalPages) * 100)
      const pageData = await this.loadPageData(page, false)
      allData.push(...pageData)
    }

    return allData
  }

  /**
     * Métodos de utilidad
     */
  getTotalItemsText () {
    const total = this.state.totalItems.toLocaleString()
    const context = this.getContextName()
    return `${total} ${context}`
  }

  getRangeText () {
    const start = ((this.state.currentPage - 1) * this.state.itemsPerPage) + 1
    const end = Math.min(this.state.currentPage * this.state.itemsPerPage, this.state.totalItems)
    return `${start}-${end}`
  }

  getProgressPercent () {
    return Math.round((this.state.currentPage / this.state.totalPages) * 100)
  }

  getContextName () {
    const names = {
      entrepreneurs: 'emprendedores',
      projects: 'proyectos',
      mentors: 'mentores',
      documents: 'documentos'
    }
    return names[this.config.context] || 'elementos'
  }

  getDefaultTranslations () {
    return {
      es: {
        itemsPerPage: 'Elementos por página',
        loadMore: 'Cargar más',
        loading: 'Cargando...',
        noMore: 'No hay más elementos',
        first: 'Primera',
        previous: 'Anterior',
        next: 'Siguiente',
        last: 'Última',
        jumpTo: 'Ir a la página',
        of: 'de',
        page: 'Página',
        selected: 'seleccionado',
        selectedPlural: 'seleccionados'
      }
    }
  }

  translate (key) {
    const lang = this.config.translations[this.config.language]
    return lang ? lang[key] || key : key
  }

  renderTemplate (template, data) {
    return template.replace(/\{\{(.*?)\}\}/g, (match, key) => {
      const keys = key.trim().split('.')
      let value = data

      for (const k of keys) {
        value = value?.[k]
      }

      return value !== undefined ? value : ''
    }).replace(/\{\{#if (.*?)\}\}(.*?)\{\{\/if\}\}/gs, (match, condition, content) => {
      const value = data[condition.trim()]
      return value ? content : ''
    }).replace(/\{\{#each (.*?)\}\}(.*?)\{\{\/each\}\}/gs, (match, arrayName, itemTemplate) => {
      const array = data[arrayName.trim()] || []
      return array.map(item =>
        itemTemplate.replace(/\{\{(.*?)\}\}/g, (match, key) => {
          if (key.trim() === 'this') return item
          return item[key.trim()] || ''
        })
      ).join('')
    })
  }

  debounce (func, wait) {
    let timeout
    return function executedFunction (...args) {
      const later = () => {
        clearTimeout(timeout)
        func(...args)
      }
      clearTimeout(timeout)
      timeout = setTimeout(later, wait)
    }
  }

  showLoading () {
    if (this.elements.loading) {
      this.elements.loading.style.display = 'block'
    }
  }

  hideLoading () {
    if (this.elements.loading) {
      this.elements.loading.style.display = 'none'
    }
  }

  showInfiniteLoading () {
    const loading = this.elements.infinite.querySelector('.infinite-loading')
    if (loading) loading.style.display = 'block'
  }

  hideInfiniteLoading () {
    const loading = this.elements.infinite.querySelector('.infinite-loading')
    if (loading) loading.style.display = 'none'
  }

  showInfiniteEnd () {
    const end = this.elements.infinite.querySelector('.infinite-end')
    if (end) end.style.display = 'block'
  }

  showExportProgress () {
    if (this.elements.exportProgress) {
      this.elements.exportProgress.style.display = 'block'
    }
  }

  hideExportProgress () {
    if (this.elements.exportProgress) {
      this.elements.exportProgress.style.display = 'none'
    }
  }

  updateExportProgress (percent) {
    const progressBar = this.elements.exportProgress?.querySelector('.progress-bar')
    if (progressBar) {
      progressBar.style.width = `${percent}%`
    }
  }

  /**
     * Sincronización con URL
     */
  updateUrl () {
    const url = new URL(window.location)
    url.searchParams.set('page', this.state.currentPage)
    url.searchParams.set('per_page', this.state.itemsPerPage)

    window.history.pushState({}, '', url)
  }

  syncFromUrl () {
    const url = new URL(window.location)
    const page = parseInt(url.searchParams.get('page')) || 1
    const perPage = parseInt(url.searchParams.get('per_page')) || this.state.itemsPerPage

    if (perPage !== this.state.itemsPerPage) {
      this.changeItemsPerPage(perPage)
    } else if (page !== this.state.currentPage) {
      this.goToPage(page)
    }
  }

  async syncWithUrl () {
    this.syncFromUrl()
  }

  /**
     * Persistencia de estado
     */
  saveState () {
    const state = {
      currentPage: this.state.currentPage,
      itemsPerPage: this.state.itemsPerPage,
      selectedItems: Array.from(this.state.selectedItems)
    }

    localStorage.setItem(this.config.storageKey, JSON.stringify(state))
  }

  async restoreState () {
    if (!this.config.persistState) return

    try {
      const saved = localStorage.getItem(this.config.storageKey)
      if (saved) {
        const state = JSON.parse(saved)

        this.state.currentPage = state.currentPage || 1
        this.state.itemsPerPage = state.itemsPerPage || this.config.itemsPerPage
        this.state.selectedItems = new Set(state.selectedItems || [])

        this.calculateTotalPages()
      }
    } catch (error) {
      console.warn('Error restoring pagination state:', error)
    }
  }

  /**
     * Analytics
     */
  trackPageChange (newPage, oldPage) {
    if (typeof gtag !== 'undefined') {
      gtag('event', 'pagination_page_change', {
        old_page: oldPage,
        new_page: newPage,
        context: this.config.context,
        pagination_type: this.config.type
      })
    }
  }

  /**
     * Manejo de errores
     */
  handleError (error) {
    console.error('Pagination error:', error)

    if (this.config.onError) {
      this.config.onError(error)
    }
  }

  getCSRFToken () {
    return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
  }

  /**
     * API pública
     */

  // Métodos de control
  setTotalItems (total) {
    this.state.totalItems = total
    this.calculateTotalPages()
    this.updateInterface()
  }

  refresh () {
    this.state.cache.clear()
    return this.goToPage(this.state.currentPage)
  }

  reset () {
    this.state.currentPage = 1
    this.state.selectedItems.clear()
    this.state.cache.clear()
    this.updateInterface()
  }

  // Getters
  getCurrentPage () {
    return this.state.currentPage
  }

  getTotalPages () {
    return this.state.totalPages
  }

  getSelectedItems () {
    return Array.from(this.state.selectedItems)
  }

  getData () {
    return this.state.data
  }

  getState () {
    return { ...this.state }
  }

  /**
     * Cleanup
     */
  destroy () {
    // Limpiar intersection observer
    if (this.intersectionObserver) {
      this.intersectionObserver.disconnect()
    }

    // Remover event listeners
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    // Limpiar caché
    this.state.cache.clear()

    console.log('🧹 EcoPagination destroyed')
  }
}

// CSS personalizado para el componente
const paginationCSS = `
    .eco-pagination {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        width: 100%;
    }
    
    .pagination-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding: 0.75rem 0;
        border-bottom: 1px solid #e9ecef;
        flex-wrap: wrap;
        gap: 1rem;
    }
    
    .pagination-info {
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    .total-items {
        font-weight: 500;
        color: #495057;
    }
    
    .pagination-progress {
        min-width: 150px;
    }
    
    .pagination-progress .progress {
        height: 4px;
    }
    
    .pagination-controls {
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
    }
    
    .items-per-page-selector {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
    }
    
    .items-per-page-selector select {
        width: auto;
        min-width: 70px;
    }
    
    .bulk-actions {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        background: #e7f3ff;
        border-radius: 6px;
        border: 1px solid #b3d9ff;
    }
    
    .selected-count {
        font-size: 0.85rem;
        font-weight: 500;
        color: #0066cc;
    }
    
    .pagination-container {
        position: relative;
    }
    
    /* Estilos específicos por tipo */
    .eco-pagination[data-style="minimal"] .pagination .page-link {
        border: none;
        color: #6c757d;
        padding: 0.5rem 0.75rem;
    }
    
    .eco-pagination[data-style="minimal"] .pagination .page-item.active .page-link {
        background: #007bff;
        color: white;
        border-radius: 6px;
    }
    
    .eco-pagination[data-style="rounded"] .pagination .page-link {
        border-radius: 50%;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 2px;
    }
    
    .eco-pagination[data-style="pills"] .pagination .page-link {
        border-radius: 20px;
        margin: 0 2px;
    }
    
    .eco-pagination[data-style="compact"] .pagination-header {
        margin-bottom: 0.5rem;
    }
    
    .eco-pagination[data-style="compact"] .pagination .page-link {
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
    }
    
    /* Load more button */
    .btn-load-more {
        min-width: 120px;
        position: relative;
    }
    
    .btn-load-more:disabled {
        opacity: 0.6;
    }
    
    /* Infinite scroll */
    .infinite-loading,
    .infinite-end {
        padding: 1rem 0;
    }
    
    .loading-text {
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    /* Virtual scrolling */
    .pagination-virtual {
        position: relative;
        height: 400px;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        overflow: hidden;
    }
    
    .virtual-viewport {
        height: 100%;
        overflow-y: auto;
        position: relative;
    }
    
    .virtual-items {
        position: relative;
    }
    
    .virtual-item {
        position: absolute;
        left: 0;
        right: 0;
        border-bottom: 1px solid #f8f9fa;
        display: flex;
        align-items: center;
        padding: 0 1rem;
    }
    
    /* Jump to page */
    .pagination-jump {
        margin-top: 1rem;
        text-align: center;
    }
    
    .jump-to-page {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
    }
    
    .jump-to-page input {
        width: 80px;
        text-align: center;
    }
    
    /* Loading overlay */
    .pagination-loading {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10;
    }
    
    .loading-overlay {
        text-align: center;
    }
    
    /* Export progress */
    .export-progress {
        margin-top: 1rem;
        padding: 1rem;
        background: #f8f9fa;
        border-radius: 6px;
    }
    
    .export-status {
        text-align: center;
        font-size: 0.9rem;
        color: #6c757d;
        margin-top: 0.5rem;
    }
    
    /* Responsive design */
    .eco-pagination.mobile-layout .pagination-header {
        flex-direction: column;
        align-items: stretch;
        gap: 0.75rem;
    }
    
    .eco-pagination.mobile-layout .pagination-info {
        justify-content: center;
        order: 2;
    }
    
    .eco-pagination.mobile-layout .pagination-controls {
        justify-content: center;
        order: 1;
    }
    
    .eco-pagination.mobile-layout .pagination .page-item {
        display: none;
    }
    
    .eco-pagination.mobile-layout .pagination .page-item.active,
    .eco-pagination.mobile-layout .pagination .page-item:first-child,
    .eco-pagination.mobile-layout .pagination .page-item:last-child,
    .eco-pagination.mobile-layout .pagination .page-item:nth-child(2),
    .eco-pagination.mobile-layout .pagination .page-item:nth-last-child(2) {
        display: block;
    }
    
    .eco-pagination.tablet-layout .pagination .page-link {
        padding: 0.375rem 0.75rem;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .eco-pagination[data-enable-animations="true"] .pagination-container {
        animation: fadeIn 0.3s ease;
    }
    
    .eco-pagination[data-enable-animations="true"] .bulk-actions {
        animation: fadeIn 0.3s ease;
    }
    
    /* Hover effects */
    .pagination .page-link:hover {
        background-color: #e9ecef;
        border-color: #dee2e6;
        color: #0056b3;
        transform: translateY(-1px);
        transition: all 0.2s ease;
    }
    
    .pagination .page-item.active .page-link:hover {
        background-color: #0056b3;
        border-color: #004085;
        transform: none;
    }
    
    /* Focus styles for accessibility */
    .pagination .page-link:focus {
        outline: 2px solid #007bff;
        outline-offset: 2px;
    }
    
    .btn-load-more:focus {
        outline: 2px solid #007bff;
        outline-offset: 2px;
    }
    
    /* Dark theme support */
    .eco-pagination[data-theme="dark"] {
        color: #e9ecef;
    }
    
    .eco-pagination[data-theme="dark"] .pagination-header {
        border-color: #495057;
    }
    
    .eco-pagination[data-theme="dark"] .pagination .page-link {
        background-color: #343a40;
        border-color: #495057;
        color: #e9ecef;
    }
    
    .eco-pagination[data-theme="dark"] .pagination .page-link:hover {
        background-color: #495057;
        border-color: #6c757d;
        color: #fff;
    }
    
    .eco-pagination[data-theme="dark"] .pagination .page-item.active .page-link {
        background-color: #007bff;
        border-color: #007bff;
    }
    
    /* Print styles */
    @media print {
        .eco-pagination {
            display: none;
        }
    }
    
    /* High contrast mode */
    @media (prefers-contrast: high) {
        .pagination .page-link {
            border-width: 2px;
        }
        
        .pagination .page-item.active .page-link {
            background-color: #000;
            border-color: #000;
            color: #fff;
        }
    }
    
    /* Reduced motion */
    @media (prefers-reduced-motion: reduce) {
        .eco-pagination * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }
`

// Inyectar CSS
if (!document.getElementById('eco-pagination-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-pagination-styles'
  style.textContent = paginationCSS
  document.head.appendChild(style)
}

// Factory methods para casos comunes
EcoPagination.createClassicPagination = (container, options = {}) => {
  return new EcoPagination(container, {
    type: 'pagination',
    style: 'classic',
    ...options
  })
}

EcoPagination.createInfiniteScroll = (container, options = {}) => {
  return new EcoPagination(container, {
    type: 'infinite',
    showInfo: true,
    showItemsPerPageSelector: false,
    ...options
  })
}

EcoPagination.createLoadMore = (container, options = {}) => {
  return new EcoPagination(container, {
    type: 'loadmore',
    showInfo: true,
    ...options
  })
}

EcoPagination.createVirtualScrolling = (container, options = {}) => {
  return new EcoPagination(container, {
    type: 'virtual',
    showInfo: false,
    showItemsPerPageSelector: false,
    ...options
  })
}

// Auto-registro en elemento
Object.defineProperty(EcoPagination.prototype, 'register', {
  value: function () {
    this.container.ecoPagination = this
  }
})

const originalInit = EcoPagination.prototype.init
EcoPagination.prototype.init = function () {
  const result = originalInit.call(this)
  this.register()
  return result
}

// Exportar
window.EcoPagination = EcoPagination
export default EcoPagination
