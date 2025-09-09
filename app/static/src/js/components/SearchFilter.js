/* global gtag */
/**
 * SearchFilter Component
 * Sistema avanzado de búsqueda y filtrado para el ecosistema de emprendimiento
 * Soporta filtros complejos, autocompletar, guardado de filtros y tiempo real
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class EcoSearchFilter {
  constructor (container, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container
    if (!this.container) {
      throw new Error('SearchFilter container not found')
    }

    this.config = {
      // URLs y endpoints
      apiBaseUrl: options.apiBaseUrl || '/api/v1',
      searchEndpoint: options.searchEndpoint || '/search',
      suggestionsEndpoint: options.suggestionsEndpoint || '/suggestions',
      filtersEndpoint: options.filtersEndpoint || '/filters',

      // Configuración de búsqueda
      searchDelay: options.searchDelay || 300,
      minSearchLength: options.minSearchLength || 2,
      maxSuggestions: options.maxSuggestions || 10,
      maxRecentSearches: options.maxRecentSearches || 5,

      // Configuración específica del ecosistema
      context: options.context || 'general', // entrepreneurs, projects, mentors, documents, etc.
      userRole: options.userRole || 'user',

      // Esquema de filtros específico del ecosistema
      filterSchema: options.filterSchema || this.getDefaultFilterSchema(),

      // Funcionalidades
      enableAutoComplete: options.enableAutoComplete !== false,
      enableRecentSearches: options.enableRecentSearches !== false,
      enableSavedFilters: options.enableSavedFilters !== false,
      enableAdvancedMode: options.enableAdvancedMode !== false,
      enableExport: options.enableExport !== false,
      enableRealTime: options.enableRealTime !== false,
      enableGeolocation: options.enableGeolocation !== false,

      // UI y UX
      showResultsCount: options.showResultsCount !== false,
      showActiveFilters: options.showActiveFilters !== false,
      compactMode: options.compactMode || false,
      theme: options.theme || 'light',

      // Persistencia
      persistFilters: options.persistFilters !== false,
      storageKey: options.storageKey || 'eco_search_filters',

      // Callbacks
      onSearch: options.onSearch || null,
      onFilterChange: options.onFilterChange || null,
      onResultsUpdate: options.onResultsUpdate || null,
      onError: options.onError || null,

      // Integraciones
      enableAnalytics: options.enableAnalytics !== false,
      webSocketUrl: options.webSocketUrl || '/ws/search',

      ...options
    }

    this.state = {
      // Estado de búsqueda
      searchQuery: '',
      activeFilters: new Map(),
      appliedFilters: new Map(),
      isSearching: false,
      searchResults: [],
      resultsCount: 0,

      // Estado de UI
      isAdvancedMode: false,
      showSuggestions: false,
      suggestions: [],
      recentSearches: [],
      savedFilters: [],

      // Estado de datos
      filterOptions: new Map(),
      selectedSuggestion: -1,
      searchHistory: [],

      // WebSocket y tiempo real
      socket: null,
      realTimeUpdates: false,

      // Geolocalización
      userLocation: null,
      locationEnabled: false
    }

    this.elements = {}
    this.filterInstances = new Map()
    this.searchTimeout = null
    this.abortController = null
    this.eventListeners = []
    this.templates = new Map()

    this.init()
  }

  /**
     * Inicialización del componente
     */
  async init () {
    try {
      await this.setupTemplates()
      await this.setupFilterSchema()
      await this.createInterface()
      await this.setupEventListeners()
      await this.loadSavedFilters()
      await this.loadRecentSearches()
      await this.loadFilterOptions()

      if (this.config.enableRealTime) {
        await this.initializeWebSocket()
      }

      if (this.config.enableGeolocation) {
        await this.initializeGeolocation()
      }

      // Restaurar filtros persistidos
      if (this.config.persistFilters) {
        await this.restorePersistedFilters()
      }

      // // console.log('✅ EcoSearchFilter initialized successfully')
    } catch (error) {
      // // console.error('❌ Error initializing EcoSearchFilter:', error)
      this.handleError(error)
    }
  }

  /**
     * Configurar templates
     */
  async setupTemplates () {
    // Template principal
    this.templates.set('main', `
            <div class="eco-search-filter" data-theme="${this.config.theme}" data-context="${this.config.context}">
                <!-- Barra de búsqueda principal -->
                <div class="search-bar-container">
                    <div class="search-input-wrapper">
                        <div class="search-icon">
                            <i class="fas fa-search"></i>
                        </div>
                        <input type="text" 
                               class="search-input form-control" 
                               placeholder="{{searchPlaceholder}}"
                               autocomplete="off"
                               spellcheck="false">
                        <div class="search-actions">
                            <button type="button" class="btn-clear-search" title="Limpiar búsqueda" style="display: none;">
                                <i class="fas fa-times"></i>
                            </button>
                            <button type="button" class="btn-voice-search" title="Búsqueda por voz" style="display: none;">
                                <i class="fas fa-microphone"></i>
                            </button>
                            <button type="button" class="btn-advanced-toggle" title="Filtros avanzados">
                                <i class="fas fa-sliders-h"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Sugerencias de autocompletar -->
                    <div class="search-suggestions" style="display: none;">
                        <div class="suggestions-content">
                            <div class="suggestions-section recent-searches" style="display: none;">
                                <h6 class="suggestions-title">Búsquedas recientes</h6>
                                <ul class="suggestions-list recent-list"></ul>
                            </div>
                            <div class="suggestions-section auto-complete" style="display: none;">
                                <h6 class="suggestions-title">Sugerencias</h6>
                                <ul class="suggestions-list autocomplete-list"></ul>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Filtros rápidos -->
                <div class="quick-filters" style="display: none;">
                    <div class="quick-filters-content"></div>
                </div>
                
                <!-- Filtros activos -->
                <div class="active-filters" style="display: none;">
                    <div class="active-filters-content">
                        <span class="active-filters-label">Filtros activos:</span>
                        <div class="filter-tags"></div>
                        <button type="button" class="btn btn-sm btn-outline-secondary btn-clear-all">
                            Limpiar todo
                        </button>
                    </div>
                </div>
                
                <!-- Panel de filtros avanzados -->
                <div class="advanced-filters-panel" style="display: none;">
                    <div class="advanced-filters-header">
                        <h5>Filtros Avanzados</h5>
                        <div class="filter-actions">
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                                        type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-bookmark"></i> Filtros guardados
                                </button>
                                <ul class="dropdown-menu saved-filters-menu"></ul>
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary btn-save-filters">
                                <i class="fas fa-save"></i> Guardar
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-info btn-export-filters">
                                <i class="fas fa-download"></i> Exportar
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary btn-reset-filters">
                                <i class="fas fa-undo"></i> Resetear
                            </button>
                        </div>
                    </div>
                    <div class="advanced-filters-content"></div>
                </div>
                
                <!-- Resultados y estadísticas -->
                <div class="search-results-info" style="display: none;">
                    <div class="results-stats">
                        <span class="results-count">0 resultados</span>
                        <span class="search-time">en 0ms</span>
                    </div>
                    <div class="results-actions">
                        <div class="sort-options">
                            <select class="form-select form-select-sm sort-select">
                                <option value="relevance">Más relevante</option>
                                <option value="date_desc">Más reciente</option>
                                <option value="date_asc">Más antiguo</option>
                                <option value="name_asc">Nombre A-Z</option>
                                <option value="name_desc">Nombre Z-A</option>
                            </select>
                        </div>
                        <div class="view-options">
                            <button type="button" class="btn btn-sm btn-outline-secondary view-btn active" data-view="grid">
                                <i class="fas fa-th"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary view-btn" data-view="list">
                                <i class="fas fa-list"></i>
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Loading indicator -->
                <div class="search-loading" style="display: none;">
                    <div class="loading-spinner">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Buscando...</span>
                        </div>
                        <span class="loading-text">Buscando...</span>
                    </div>
                </div>
            </div>
        `)

    // Template para filtro individual
    this.templates.set('filterItem', `
            <div class="filter-item" data-filter-type="{{type}}" data-filter-key="{{key}}">
                <label class="filter-label">{{label}}</label>
                <div class="filter-input-container">
                    {{input}}
                </div>
                {{#if description}}
                <small class="filter-description text-muted">{{description}}</small>
                {{/if}}
            </div>
        `)

    // Template para tag de filtro activo
    this.templates.set('filterTag', `
            <span class="filter-tag" data-filter-key="{{key}}">
                <span class="tag-label">{{label}}: {{value}}</span>
                <button type="button" class="tag-remove" title="Eliminar filtro">
                    <i class="fas fa-times"></i>
                </button>
            </span>
        `)
  }

  /**
     * Configurar esquema de filtros específico del ecosistema
     */
  async setupFilterSchema () {
    if (this.config.filterSchema) {
      return // Ya está configurado
    }

    // Esquema por defecto según el contexto
    switch (this.config.context) {
      case 'entrepreneurs':
        this.config.filterSchema = this.getEntrepreneursFilterSchema()
        break
      case 'projects':
        this.config.filterSchema = this.getProjectsFilterSchema()
        break
      case 'mentors':
        this.config.filterSchema = this.getMentorsFilterSchema()
        break
      case 'documents':
        this.config.filterSchema = this.getDocumentsFilterSchema()
        break
      default:
        this.config.filterSchema = this.getDefaultFilterSchema()
    }
  }

  /**
     * Esquemas de filtros específicos del ecosistema
     */
  getEntrepreneursFilterSchema () {
    return [
      {
        key: 'sector',
        label: 'Sector',
        type: 'multiselect',
        options: [
          { value: 'tecnologia', label: 'Tecnología' },
          { value: 'salud', label: 'Salud y Bienestar' },
          { value: 'fintech', label: 'Fintech' },
          { value: 'ecommerce', label: 'E-commerce' },
          { value: 'educacion', label: 'Educación' },
          { value: 'sostenibilidad', label: 'Sostenibilidad' },
          { value: 'alimentacion', label: 'Alimentación' },
          { value: 'movilidad', label: 'Movilidad' }
        ],
        quickFilter: true
      },
      {
        key: 'stage',
        label: 'Etapa del Proyecto',
        type: 'select',
        options: [
          { value: 'idea', label: 'Idea' },
          { value: 'validacion', label: 'Validación' },
          { value: 'mvp', label: 'MVP' },
          { value: 'piloto', label: 'Piloto' },
          { value: 'escalamiento', label: 'Escalamiento' },
          { value: 'expansion', label: 'Expansión' }
        ],
        quickFilter: true
      },
      {
        key: 'location',
        label: 'Ubicación',
        type: 'location',
        enableNearby: true
      },
      {
        key: 'progress',
        label: 'Progreso',
        type: 'range',
        min: 0,
        max: 100,
        step: 5,
        suffix: '%'
      },
      {
        key: 'founding_date',
        label: 'Fecha de Fundación',
        type: 'daterange'
      },
      {
        key: 'team_size',
        label: 'Tamaño del Equipo',
        type: 'range',
        min: 1,
        max: 50,
        step: 1
      },
      {
        key: 'funding_status',
        label: 'Estado de Financiamiento',
        type: 'multiselect',
        options: [
          { value: 'bootstrapped', label: 'Autofinanciado' },
          { value: 'angel', label: 'Inversión Ángel' },
          { value: 'seed', label: 'Seed' },
          { value: 'series_a', label: 'Serie A' },
          { value: 'series_b', label: 'Serie B+' },
          { value: 'seeking', label: 'Buscando Inversión' }
        ]
      },
      {
        key: 'has_mentor',
        label: 'Con Mentor Asignado',
        type: 'boolean'
      },
      {
        key: 'is_active',
        label: 'Estado',
        type: 'select',
        options: [
          { value: 'active', label: 'Activo' },
          { value: 'inactive', label: 'Inactivo' },
          { value: 'paused', label: 'Pausado' },
          { value: 'graduated', label: 'Graduado' }
        ]
      }
    ]
  }

  getProjectsFilterSchema () {
    return [
      {
        key: 'status',
        label: 'Estado del Proyecto',
        type: 'multiselect',
        options: [
          { value: 'planning', label: 'Planificación' },
          { value: 'development', label: 'En Desarrollo' },
          { value: 'testing', label: 'Pruebas' },
          { value: 'launched', label: 'Lanzado' },
          { value: 'paused', label: 'Pausado' },
          { value: 'completed', label: 'Completado' }
        ],
        quickFilter: true
      },
      {
        key: 'priority',
        label: 'Prioridad',
        type: 'select',
        options: [
          { value: 'low', label: 'Baja' },
          { value: 'medium', label: 'Media' },
          { value: 'high', label: 'Alta' },
          { value: 'critical', label: 'Crítica' }
        ],
        quickFilter: true
      },
      {
        key: 'budget_range',
        label: 'Rango de Presupuesto',
        type: 'range',
        min: 0,
        max: 1000000,
        step: 10000,
        prefix: '$',
        formatter: 'currency'
      },
      {
        key: 'duration',
        label: 'Duración (meses)',
        type: 'range',
        min: 1,
        max: 36,
        step: 1
      },
      {
        key: 'tags',
        label: 'Etiquetas',
        type: 'tags',
        allowCustom: true
      },
      {
        key: 'mentor_assigned',
        label: 'Mentor Asignado',
        type: 'user_select',
        role: 'mentor'
      },
      {
        key: 'last_activity',
        label: 'Última Actividad',
        type: 'daterange'
      }
    ]
  }

  getMentorsFilterSchema () {
    return [
      {
        key: 'expertise',
        label: 'Área de Expertise',
        type: 'multiselect',
        options: [
          { value: 'business', label: 'Desarrollo de Negocio' },
          { value: 'technology', label: 'Tecnología' },
          { value: 'marketing', label: 'Marketing' },
          { value: 'finance', label: 'Finanzas' },
          { value: 'operations', label: 'Operaciones' },
          { value: 'legal', label: 'Legal' },
          { value: 'hr', label: 'Recursos Humanos' },
          { value: 'sales', label: 'Ventas' }
        ],
        quickFilter: true
      },
      {
        key: 'experience_years',
        label: 'Años de Experiencia',
        type: 'range',
        min: 1,
        max: 40,
        step: 1
      },
      {
        key: 'availability',
        label: 'Disponibilidad',
        type: 'select',
        options: [
          { value: 'available', label: 'Disponible' },
          { value: 'limited', label: 'Disponibilidad Limitada' },
          { value: 'full', label: 'Sin Disponibilidad' }
        ],
        quickFilter: true
      },
      {
        key: 'mentorship_style',
        label: 'Estilo de Mentoría',
        type: 'multiselect',
        options: [
          { value: 'hands_on', label: 'Hands-on' },
          { value: 'advisory', label: 'Consultivo' },
          { value: 'coaching', label: 'Coaching' },
          { value: 'networking', label: 'Networking' }
        ]
      },
      {
        key: 'current_mentees',
        label: 'Emprendedores Actuales',
        type: 'range',
        min: 0,
        max: 20,
        step: 1
      },
      {
        key: 'success_rate',
        label: 'Tasa de Éxito',
        type: 'range',
        min: 0,
        max: 100,
        step: 5,
        suffix: '%'
      }
    ]
  }

  getDocumentsFilterSchema () {
    return [
      {
        key: 'document_type',
        label: 'Tipo de Documento',
        type: 'multiselect',
        options: [
          { value: 'pitch_deck', label: 'Pitch Deck' },
          { value: 'business_plan', label: 'Plan de Negocio' },
          { value: 'financial', label: 'Documento Financiero' },
          { value: 'legal', label: 'Documento Legal' },
          { value: 'presentation', label: 'Presentación' },
          { value: 'report', label: 'Reporte' },
          { value: 'template', label: 'Template' }
        ],
        quickFilter: true
      },
      {
        key: 'file_format',
        label: 'Formato de Archivo',
        type: 'multiselect',
        options: [
          { value: 'pdf', label: 'PDF' },
          { value: 'docx', label: 'Word' },
          { value: 'xlsx', label: 'Excel' },
          { value: 'pptx', label: 'PowerPoint' },
          { value: 'image', label: 'Imagen' },
          { value: 'video', label: 'Video' }
        ]
      },
      {
        key: 'file_size',
        label: 'Tamaño de Archivo',
        type: 'range',
        min: 0,
        max: 100,
        step: 1,
        suffix: 'MB'
      },
      {
        key: 'upload_date',
        label: 'Fecha de Subida',
        type: 'daterange'
      },
      {
        key: 'shared_with_me',
        label: 'Compartido Conmigo',
        type: 'boolean'
      },
      {
        key: 'is_public',
        label: 'Público',
        type: 'boolean'
      }
    ]
  }

  getDefaultFilterSchema () {
    return [
      {
        key: 'created_date',
        label: 'Fecha de Creación',
        type: 'daterange'
      },
      {
        key: 'status',
        label: 'Estado',
        type: 'select',
        options: [
          { value: 'active', label: 'Activo' },
          { value: 'inactive', label: 'Inactivo' }
        ]
      }
    ]
  }

  /**
     * Crear interfaz de usuario
     */
  async createInterface () {
    // Renderizar template principal
    const templateData = {
      searchPlaceholder: this.getSearchPlaceholder()
    }

    this.container.innerHTML = this.renderTemplate(this.templates.get('main'), templateData)

    // Obtener referencias a elementos
    this.elements = {
      searchInput: this.container.querySelector('.search-input'),
      searchSuggestions: this.container.querySelector('.search-suggestions'),
      quickFilters: this.container.querySelector('.quick-filters'),
      activeFilters: this.container.querySelector('.active-filters'),
      advancedPanel: this.container.querySelector('.advanced-filters-panel'),
      advancedContent: this.container.querySelector('.advanced-filters-content'),
      resultsInfo: this.container.querySelector('.search-results-info'),
      resultsCount: this.container.querySelector('.results-count'),
      searchTime: this.container.querySelector('.search-time'),
      loading: this.container.querySelector('.search-loading'),
      filterTags: this.container.querySelector('.filter-tags'),
      sortSelect: this.container.querySelector('.sort-select'),

      // Botones
      btnClearSearch: this.container.querySelector('.btn-clear-search'),
      btnVoiceSearch: this.container.querySelector('.btn-voice-search'),
      btnAdvancedToggle: this.container.querySelector('.btn-advanced-toggle'),
      btnClearAll: this.container.querySelector('.btn-clear-all'),
      btnSaveFilters: this.container.querySelector('.btn-save-filters'),
      btnExportFilters: this.container.querySelector('.btn-export-filters'),
      btnResetFilters: this.container.querySelector('.btn-reset-filters')
    }

    // Crear filtros rápidos
    await this.createQuickFilters()

    // Crear filtros avanzados
    await this.createAdvancedFilters()

    // Aplicar tema
    this.applyTheme()
  }

  /**
     * Crear filtros rápidos
     */
  async createQuickFilters () {
    const quickFilters = this.config.filterSchema.filter(filter => filter.quickFilter)
    if (quickFilters.length === 0) return

    const quickFiltersHtml = quickFilters.map(filter => {
      return this.createFilterInput(filter, true)
    }).join('')

    this.elements.quickFilters.querySelector('.quick-filters-content').innerHTML = quickFiltersHtml
    this.elements.quickFilters.style.display = 'block'

    // Configurar event listeners para filtros rápidos
    this.setupQuickFiltersListeners()
  }

  /**
     * Crear filtros avanzados
     */
  async createAdvancedFilters () {
    const advancedFilters = this.config.filterSchema.filter(filter => !filter.quickFilter)

    const filtersHtml = advancedFilters.map(filter => {
      const input = this.createFilterInput(filter, false)
      return this.renderTemplate(this.templates.get('filterItem'), {
        type: filter.type,
        key: filter.key,
        label: filter.label,
        description: filter.description || '',
        input
      })
    }).join('')

    this.elements.advancedContent.innerHTML = filtersHtml

    // Configurar event listeners para filtros avanzados
    this.setupAdvancedFiltersListeners()
  }

  /**
     * Crear input de filtro según el tipo
     */
  createFilterInput (filter, isQuick = false) {
    const baseClass = isQuick ? 'form-control form-control-sm' : 'form-control'
    const id = `filter_${filter.key}${isQuick ? '_quick' : ''}`

    switch (filter.type) {
      case 'text':
        return `<input type="text" id="${id}" class="${baseClass}" placeholder="${filter.placeholder || ''}" data-filter-key="${filter.key}">`

      case 'select':
        const selectOptions = filter.options.map(option =>
                    `<option value="${option.value}">${option.label}</option>`
        ).join('')
        return `<select id="${id}" class="form-select ${isQuick ? 'form-select-sm' : ''}" data-filter-key="${filter.key}">
                    <option value="">Todos</option>
                    ${selectOptions}
                </select>`

      case 'multiselect':
        return this.createMultiSelectInput(filter, id, baseClass)

      case 'range':
        return this.createRangeInput(filter, id, baseClass)

      case 'daterange':
        return this.createDateRangeInput(filter, id, baseClass)

      case 'boolean':
        return `<div class="form-check">
                    <input class="form-check-input" type="checkbox" id="${id}" data-filter-key="${filter.key}">
                    <label class="form-check-label" for="${id}">Sí</label>
                </div>`

      case 'tags':
        return this.createTagsInput(filter, id, baseClass)

      case 'location':
        return this.createLocationInput(filter, id, baseClass)

      case 'user_select':
        return this.createUserSelectInput(filter, id, baseClass)

      default:
        return `<input type="text" id="${id}" class="${baseClass}" data-filter-key="${filter.key}">`
    }
  }

  /**
     * Crear input de multiselect
     */
  createMultiSelectInput (filter, id, baseClass) {
    const options = filter.options.map(option =>
            `<div class="form-check">
                <input class="form-check-input" type="checkbox" value="${option.value}" 
                       id="${id}_${option.value}" data-filter-key="${filter.key}">
                <label class="form-check-label" for="${id}_${option.value}">
                    ${option.label}
                </label>
            </div>`
    ).join('')

    return `<div class="multiselect-container" data-filter-key="${filter.key}">
            ${options}
        </div>`
  }

  /**
     * Crear input de rango
     */
  createRangeInput (filter, id, baseClass) {
    const prefix = filter.prefix || ''
    const suffix = filter.suffix || ''

    return `<div class="range-input-container" data-filter-key="${filter.key}">
            <div class="range-inputs">
                <div class="input-group input-group-sm">
                    ${prefix ? `<span class="input-group-text">${prefix}</span>` : ''}
                    <input type="number" class="form-control" placeholder="Min" 
                           id="${id}_min" min="${filter.min}" max="${filter.max}" step="${filter.step}">
                    ${suffix ? `<span class="input-group-text">${suffix}</span>` : ''}
                </div>
                <span class="range-separator">a</span>
                <div class="input-group input-group-sm">
                    ${prefix ? `<span class="input-group-text">${prefix}</span>` : ''}
                    <input type="number" class="form-control" placeholder="Max" 
                           id="${id}_max" min="${filter.min}" max="${filter.max}" step="${filter.step}">
                    ${suffix ? `<span class="input-group-text">${suffix}</span>` : ''}
                </div>
            </div>
            <div class="range-slider mt-2">
                <input type="range" class="form-range" id="${id}_slider" 
                       min="${filter.min}" max="${filter.max}" step="${filter.step}">
            </div>
        </div>`
  }

  /**
     * Crear input de rango de fechas
     */
  createDateRangeInput (filter, id, baseClass) {
    return `<div class="daterange-container" data-filter-key="${filter.key}">
            <div class="row g-2">
                <div class="col">
                    <input type="date" class="form-control form-control-sm" 
                           id="${id}_start" placeholder="Desde">
                </div>
                <div class="col">
                    <input type="date" class="form-control form-control-sm" 
                           id="${id}_end" placeholder="Hasta">
                </div>
            </div>
            <div class="date-presets mt-2">
                <button type="button" class="btn btn-sm btn-outline-secondary preset-btn" data-preset="last_week">
                    Última semana
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary preset-btn" data-preset="last_month">
                    Último mes
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary preset-btn" data-preset="last_quarter">
                    Último trimestre
                </button>
            </div>
        </div>`
  }

  /**
     * Crear input de tags
     */
  createTagsInput (filter, id, baseClass) {
    return `<div class="tags-input-container" data-filter-key="${filter.key}">
            <div class="tags-list"></div>
            <input type="text" class="form-control form-control-sm tags-input" 
                   id="${id}" placeholder="Escribir y presionar Enter...">
        </div>`
  }

  /**
     * Crear input de ubicación
     */
  createLocationInput (filter, id, baseClass) {
    const nearbyButton = filter.enableNearby
      ? `<button type="button" class="btn btn-sm btn-outline-primary btn-nearby" title="Cerca de mí">
                <i class="fas fa-location-arrow"></i>
            </button>`
      : ''

    return `<div class="location-input-container" data-filter-key="${filter.key}">
            <div class="input-group">
                <input type="text" class="form-control form-control-sm location-input" 
                       id="${id}" placeholder="Ciudad, región o país">
                ${nearbyButton}
            </div>
            <div class="location-suggestions" style="display: none;"></div>
        </div>`
  }

  /**
     * Crear input de selección de usuario
     */
  createUserSelectInput (filter, id, baseClass) {
    return `<div class="user-select-container" data-filter-key="${filter.key}">
            <input type="text" class="form-control form-control-sm user-search" 
                   id="${id}" placeholder="Buscar ${filter.role}..." data-role="${filter.role}">
            <div class="user-suggestions" style="display: none;"></div>
            <div class="selected-users"></div>
        </div>`
  }

  /**
     * Configurar event listeners
     */
  async setupEventListeners () {
    // Búsqueda principal
    this.setupSearchListeners()

    // Filtros
    this.setupFiltersListeners()

    // Botones de acción
    this.setupActionListeners()

    // Sugerencias y autocompletar
    this.setupSuggestionsListeners()

    // Ordenamiento y vista
    this.setupResultsListeners()

    // Teclado y accesibilidad
    this.setupKeyboardListeners()
  }

  /**
     * Configurar listeners de búsqueda
     */
  setupSearchListeners () {
    const searchInput = this.elements.searchInput

    // Input con debouncing
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.trim()
      this.state.searchQuery = query

      // Mostrar/ocultar botón de limpiar
      this.elements.btnClearSearch.style.display = query ? 'block' : 'none'

      // Debounce search
      clearTimeout(this.searchTimeout)
      this.searchTimeout = setTimeout(() => {
        this.performSearch(query)
      }, this.config.searchDelay)

      // Mostrar sugerencias si hay texto
      if (query.length >= this.config.minSearchLength) {
        this.showSuggestions(query)
      } else {
        this.hideSuggestions()
      }
    })

    // Focus y blur
    searchInput.addEventListener('focus', () => {
      if (this.state.searchQuery.length >= this.config.minSearchLength) {
        this.showSuggestions(this.state.searchQuery)
      } else if (this.state.recentSearches.length > 0) {
        this.showRecentSearches()
      }
    })

    searchInput.addEventListener('blur', (e) => {
      // Delay para permitir clicks en sugerencias
      setTimeout(() => {
        if (!this.container.contains(document.activeElement)) {
          this.hideSuggestions()
        }
      }, 150)
    })

    // Enter para buscar
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        this.performSearch(this.state.searchQuery)
        this.hideSuggestions()
      }
    })
  }

  /**
     * Configurar listeners de filtros
     */
  setupFiltersListeners () {
    // Event delegation para todos los filtros
    this.container.addEventListener('change', (e) => {
      const filterKey = e.target.dataset.filterKey
      if (filterKey) {
        this.handleFilterChange(filterKey, e.target)
      }
    })

    // Filtros específicos
    this.setupQuickFiltersListeners()
    this.setupAdvancedFiltersListeners()
  }

  /**
     * Configurar listeners de filtros rápidos
     */
  setupQuickFiltersListeners () {
    // Ya se manejan con event delegation
  }

  /**
     * Configurar listeners de filtros avanzados
     */
  setupAdvancedFiltersListeners () {
    // Presets de fecha
    this.container.addEventListener('click', (e) => {
      if (e.target.classList.contains('preset-btn')) {
        this.applyDatePreset(e.target.dataset.preset, e.target.closest('.daterange-container'))
      }
    })

    // Tags input
    this.container.addEventListener('keydown', (e) => {
      if (e.target.classList.contains('tags-input') && e.key === 'Enter') {
        e.preventDefault()
        this.addTag(e.target)
      }
    })

    // Ubicación
    this.container.addEventListener('click', (e) => {
      if (e.target.closest('.btn-nearby')) {
        this.useNearbyLocation(e.target.closest('.location-input-container'))
      }
    })
  }

  /**
     * Configurar listeners de acciones
     */
  setupActionListeners () {
    // Limpiar búsqueda
    this.elements.btnClearSearch.addEventListener('click', () => {
      this.clearSearch()
    })

    // Toggle filtros avanzados
    this.elements.btnAdvancedToggle.addEventListener('click', () => {
      this.toggleAdvancedFilters()
    })

    // Limpiar todos los filtros
    this.elements.btnClearAll.addEventListener('click', () => {
      this.clearAllFilters()
    })

    // Guardar filtros
    this.elements.btnSaveFilters.addEventListener('click', () => {
      this.saveCurrentFilters()
    })

    // Exportar filtros
    this.elements.btnExportFilters.addEventListener('click', () => {
      this.exportFilters()
    })

    // Resetear filtros
    this.elements.btnResetFilters.addEventListener('click', () => {
      this.resetFilters()
    })

    // Búsqueda por voz (si está habilitada)
    if (this.config.enableVoiceSearch && 'webkitSpeechRecognition' in window) {
      this.setupVoiceSearch()
    }
  }

  /**
     * Realizar búsqueda
     */
  async performSearch (query = '') {
    if (this.state.isSearching) {
      // Cancelar búsqueda anterior
      if (this.abortController) {
        this.abortController.abort()
      }
    }

    this.state.isSearching = true
    this.showLoading()

    // Crear nuevo AbortController
    this.abortController = new AbortController()

    try {
      const startTime = Date.now()

      // Preparar parámetros de búsqueda
      const searchParams = {
        query,
        filters: this.getActiveFiltersObject(),
        context: this.config.context,
        sort: this.elements.sortSelect.value || 'relevance',
        limit: 50
      }

      // Realizar búsqueda
      const response = await fetch(`${this.config.apiBaseUrl}${this.config.searchEndpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify(searchParams),
        signal: this.abortController.signal
      })

      if (!response.ok) {
        throw new Error(`Search failed: ${response.status}`)
      }

      const results = await response.json()
      const searchTime = Date.now() - startTime

      // Actualizar estado
      this.state.searchResults = results.data || []
      this.state.resultsCount = results.total || 0

      // Actualizar UI
      this.updateResultsInfo(this.state.resultsCount, searchTime)

      // Callback
      if (this.config.onResultsUpdate) {
        this.config.onResultsUpdate(this.state.searchResults, this.state.resultsCount)
      }

      // Guardar en historial si hay query
      if (query && query.length > 0) {
        this.addToSearchHistory(query)
      }

      // Analytics
      if (this.config.enableAnalytics) {
        this.trackSearch(query, this.state.resultsCount, searchTime)
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        // // console.error('Search error:', error)
        this.handleError(error)
      }
    } finally {
      this.state.isSearching = false
      this.hideLoading()
    }
  }

  /**
     * Manejar cambio de filtro
     */
  handleFilterChange (filterKey, element) {
    const filterConfig = this.config.filterSchema.find(f => f.key === filterKey)
    if (!filterConfig) return

    const value = this.extractFilterValue(element, filterConfig)

    if (value !== null && value !== '' && value !== undefined) {
      this.state.activeFilters.set(filterKey, {
        config: filterConfig,
        value,
        element
      })
    } else {
      this.state.activeFilters.delete(filterKey)
    }

    // Actualizar UI de filtros activos
    this.updateActiveFiltersUI()

    // Aplicar filtros
    this.applyFilters()

    // Callback
    if (this.config.onFilterChange) {
      this.config.onFilterChange(filterKey, value, this.getActiveFiltersObject())
    }
  }

  /**
     * Extraer valor del filtro según su tipo
     */
  extractFilterValue (element, filterConfig) {
    switch (filterConfig.type) {
      case 'text':
      case 'select':
        return element.value.trim()

      case 'multiselect':
        const container = element.closest('.multiselect-container')
        const checked = container.querySelectorAll('input[type="checkbox"]:checked')
        return Array.from(checked).map(cb => cb.value)

      case 'range':
        const rangeContainer = element.closest('.range-input-container')
        const minInput = rangeContainer.querySelector('[id$="_min"]')
        const maxInput = rangeContainer.querySelector('[id$="_max"]')
        return {
          min: minInput.value ? Number(minInput.value) : null,
          max: maxInput.value ? Number(maxInput.value) : null
        }

      case 'daterange':
        const dateContainer = element.closest('.daterange-container')
        const startInput = dateContainer.querySelector('[id$="_start"]')
        const endInput = dateContainer.querySelector('[id$="_end"]')
        return {
          start: startInput.value || null,
          end: endInput.value || null
        }

      case 'boolean':
        return element.checked

      case 'tags':
        const tagsContainer = element.closest('.tags-input-container')
        const tags = tagsContainer.querySelectorAll('.tag')
        return Array.from(tags).map(tag => tag.dataset.value)

      case 'location':
        return element.value.trim()

      case 'user_select':
        const userContainer = element.closest('.user-select-container')
        const selectedUsers = userContainer.querySelectorAll('.selected-user')
        return Array.from(selectedUsers).map(user => user.dataset.userId)

      default:
        return element.value
    }
  }

  /**
     * Aplicar filtros
     */
  async applyFilters () {
    // Clonar filtros activos a aplicados
    this.state.appliedFilters = new Map(this.state.activeFilters)

    // Persistir si está habilitado
    if (this.config.persistFilters) {
      this.persistFilters()
    }

    // Realizar nueva búsqueda con filtros
    await this.performSearch(this.state.searchQuery)
  }

  /**
     * Mostrar sugerencias
     */
  async showSuggestions (query) {
    if (!this.config.enableAutoComplete) return

    try {
      // Obtener sugerencias del servidor
      const response = await fetch(`${this.config.apiBaseUrl}${this.config.suggestionsEndpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify({
          query,
          context: this.config.context,
          limit: this.config.maxSuggestions
        })
      })

      if (response.ok) {
        const suggestions = await response.json()
        this.renderSuggestions(suggestions.data || [], query)
      }
    } catch (error) {
      // console.warn('Error fetching suggestions:', error)
    }
  }

  /**
     * Renderizar sugerencias
     */
  renderSuggestions (suggestions, query) {
    const suggestionsContainer = this.elements.searchSuggestions
    const autoCompleteSection = suggestionsContainer.querySelector('.auto-complete')
    const autoCompleteList = suggestionsContainer.querySelector('.autocomplete-list')

    if (suggestions.length === 0) {
      autoCompleteSection.style.display = 'none'
    } else {
      const suggestionsHtml = suggestions.map((suggestion, index) => {
        const highlightedText = this.highlightQuery(suggestion.text, query)
        return `<li class="suggestion-item" data-index="${index}" data-value="${suggestion.value}">
                    <div class="suggestion-content">
                        <div class="suggestion-text">${highlightedText}</div>
                        ${suggestion.description ? `<div class="suggestion-description">${suggestion.description}</div>` : ''}
                    </div>
                    <div class="suggestion-type">${suggestion.type || ''}</div>
                </li>`
      }).join('')

      autoCompleteList.innerHTML = suggestionsHtml
      autoCompleteSection.style.display = 'block'
    }

    // Mostrar búsquedas recientes si no hay query
    if (!query && this.state.recentSearches.length > 0) {
      this.showRecentSearches()
    }

    // Mostrar contenedor de sugerencias
    suggestionsContainer.style.display = 'block'
    this.state.showSuggestions = true
  }

  /**
     * Mostrar búsquedas recientes
     */
  showRecentSearches () {
    if (!this.config.enableRecentSearches || this.state.recentSearches.length === 0) return

    const suggestionsContainer = this.elements.searchSuggestions
    const recentSection = suggestionsContainer.querySelector('.recent-searches')
    const recentList = suggestionsContainer.querySelector('.recent-list')

    const recentHtml = this.state.recentSearches.map((search, index) => {
      return `<li class="suggestion-item recent-item" data-index="${index}" data-value="${search}">
                <div class="suggestion-content">
                    <div class="suggestion-text">${search}</div>
                </div>
                <div class="suggestion-actions">
                    <button type="button" class="btn-remove-recent" data-search="${search}" title="Eliminar">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </li>`
    }).join('')

    recentList.innerHTML = recentHtml
    recentSection.style.display = 'block'
    suggestionsContainer.style.display = 'block'
    this.state.showSuggestions = true
  }

  /**
     * Ocultar sugerencias
     */
  hideSuggestions () {
    this.elements.searchSuggestions.style.display = 'none'
    this.state.showSuggestions = false
    this.state.selectedSuggestion = -1
  }

  /**
     * Actualizar información de resultados
     */
  updateResultsInfo (count, searchTime) {
    this.elements.resultsCount.textContent = `${count.toLocaleString()} resultado${count !== 1 ? 's' : ''}`
    this.elements.searchTime.textContent = `en ${searchTime}ms`
    this.elements.resultsInfo.style.display = count > 0 ? 'flex' : 'none'
  }

  /**
     * Actualizar UI de filtros activos
     */
  updateActiveFiltersUI () {
    const filterTags = this.elements.filterTags
    filterTags.innerHTML = ''

    if (this.state.activeFilters.size === 0) {
      this.elements.activeFilters.style.display = 'none'
      return
    }

    this.state.activeFilters.forEach((filter, key) => {
      const tag = this.createFilterTag(key, filter)
      filterTags.appendChild(tag)
    })

    this.elements.activeFilters.style.display = 'block'
  }

  /**
     * Crear tag de filtro activo
     */
  createFilterTag (key, filter) {
    const value = this.formatFilterValue(filter.value, filter.config)
    const label = filter.config.label

    const tagElement = document.createElement('span')
    tagElement.innerHTML = this.renderTemplate(this.templates.get('filterTag'), {
      key,
      label,
      value
    })

    // Event listener para eliminar filtro
    tagElement.querySelector('.tag-remove').addEventListener('click', () => {
      this.removeFilter(key)
    })

    return tagElement.firstElementChild
  }

  /**
     * Formatear valor de filtro para mostrar
     */
  formatFilterValue (value, config) {
    switch (config.type) {
      case 'multiselect':
        if (Array.isArray(value)) {
          const labels = value.map(v => {
            const option = config.options.find(opt => opt.value === v)
            return option ? option.label : v
          })
          return labels.join(', ')
        }
        return value

      case 'range':
        if (value.min !== null && value.max !== null) {
          return `${value.min} - ${value.max}`
        } else if (value.min !== null) {
          return `≥ ${value.min}`
        } else if (value.max !== null) {
          return `≤ ${value.max}`
        }
        return ''

      case 'daterange':
        if (value.start && value.end) {
          return `${value.start} - ${value.end}`
        } else if (value.start) {
          return `Desde ${value.start}`
        } else if (value.end) {
          return `Hasta ${value.end}`
        }
        return ''

      case 'boolean':
        return value ? 'Sí' : 'No'

      case 'tags':
        return Array.isArray(value) ? value.join(', ') : value

      default:
        return value
    }
  }

  /**
     * Métodos de utilidad
     */

  getSearchPlaceholder () {
    const placeholders = {
      entrepreneurs: 'Buscar emprendedores por nombre, sector, ubicación...',
      projects: 'Buscar proyectos por nombre, descripción, etiquetas...',
      mentors: 'Buscar mentores por nombre, expertise, experiencia...',
      documents: 'Buscar documentos por nombre, tipo, contenido...'
    }
    return placeholders[this.config.context] || 'Buscar...'
  }

  getActiveFiltersObject () {
    const filters = {}
    this.state.appliedFilters.forEach((filter, key) => {
      filters[key] = filter.value
    })
    return filters
  }

  highlightQuery (text, query) {
    if (!query) return text
    const regex = new RegExp(`(${query})`, 'gi')
    return text.replace(regex, '<mark>$1</mark>')
  }

  renderTemplate (template, data) {
    return template.replace(/\{\{(.*?)\}\}/g, (match, key) => {
      const keys = key.trim().split('.')
      let value = data

      for (const k of keys) {
        value = value?.[k]
      }

      return value || ''
    }).replace(/\{\{#if (.*?)\}\}(.*?)\{\{\/if\}\}/gs, (match, condition, content) => {
      const value = data[condition.trim()]
      return value ? content : ''
    })
  }

  clearSearch () {
    this.elements.searchInput.value = ''
    this.state.searchQuery = ''
    this.elements.btnClearSearch.style.display = 'none'
    this.hideSuggestions()
    this.performSearch('')
  }

  clearAllFilters () {
    this.state.activeFilters.clear()
    this.state.appliedFilters.clear()

    // Limpiar inputs de filtros
    this.container.querySelectorAll('input, select').forEach(input => {
      if (input.type === 'checkbox') {
        input.checked = false
      } else {
        input.value = ''
      }
    })

    this.updateActiveFiltersUI()
    this.performSearch(this.state.searchQuery)
  }

  removeFilter (key) {
    this.state.activeFilters.delete(key)
    this.state.appliedFilters.delete(key)

    // Limpiar input correspondiente
    const inputs = this.container.querySelectorAll(`[data-filter-key="${key}"]`)
    inputs.forEach(input => {
      if (input.type === 'checkbox') {
        input.checked = false
      } else {
        input.value = ''
      }
    })

    this.updateActiveFiltersUI()
    this.performSearch(this.state.searchQuery)
  }

  toggleAdvancedFilters () {
    this.state.isAdvancedMode = !this.state.isAdvancedMode
    this.elements.advancedPanel.style.display = this.state.isAdvancedMode ? 'block' : 'none'

    const icon = this.elements.btnAdvancedToggle.querySelector('i')
    icon.className = this.state.isAdvancedMode ? 'fas fa-times' : 'fas fa-sliders-h'
  }

  showLoading () {
    this.elements.loading.style.display = 'block'
  }

  hideLoading () {
    this.elements.loading.style.display = 'none'
  }

  addToSearchHistory (query) {
    if (!this.state.recentSearches.includes(query)) {
      this.state.recentSearches.unshift(query)
      this.state.recentSearches = this.state.recentSearches.slice(0, this.config.maxRecentSearches)
      this.saveRecentSearches()
    }
  }

  saveRecentSearches () {
    localStorage.setItem(`${this.config.storageKey}_recent`, JSON.stringify(this.state.recentSearches))
  }

  async loadRecentSearches () {
    try {
      const saved = localStorage.getItem(`${this.config.storageKey}_recent`)
      if (saved) {
        this.state.recentSearches = JSON.parse(saved)
      }
    } catch (error) {
      // console.warn('Error loading recent searches:', error)
    }
  }

  trackSearch (query, resultsCount, searchTime) {
    if (typeof gtag !== 'undefined') {
      gtag('event', 'search', {
        search_term: query,
        search_results: resultsCount,
        search_time: searchTime,
        search_context: this.config.context
      })
    }
  }

  handleError (error) {
    if (this.config.onError) {
      this.config.onError(error)
    } else {
      // // console.error('SearchFilter error:', error)
    }
  }

  getCSRFToken () {
    return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
  }

  applyTheme () {
    this.container.dataset.theme = this.config.theme
  }

  /**
     * API pública
     */
  search (query) {
    this.elements.searchInput.value = query
    this.state.searchQuery = query
    return this.performSearch(query)
  }

  setFilter (key, value) {
    const filterConfig = this.config.filterSchema.find(f => f.key === key)
    if (filterConfig) {
      this.state.activeFilters.set(key, {
        config: filterConfig,
        value
      })
      this.updateActiveFiltersUI()
      this.applyFilters()
    }
  }

  getResults () {
    return this.state.searchResults
  }

  getFilters () {
    return this.getActiveFiltersObject()
  }

  reset () {
    this.clearSearch()
    this.clearAllFilters()
  }

  /**
     * Cleanup
     */
  destroy () {
    // Limpiar timers
    if (this.searchTimeout) {
      clearTimeout(this.searchTimeout)
    }

    // Cancelar requests pendientes
    if (this.abortController) {
      this.abortController.abort()
    }

    // Desconectar WebSocket
    if (this.state.socket) {
      this.state.socket.disconnect()
    }

    // Remover event listeners
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    // // console.log('🧹 EcoSearchFilter destroyed')
  }
}

// CSS personalizado para el componente
const searchFilterCSS = `
    .eco-search-filter {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        width: 100%;
    }
    
    .search-bar-container {
        position: relative;
        margin-bottom: 1rem;
    }
    
    .search-input-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        background: white;
        border: 2px solid #e0e6ed;
        border-radius: 12px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .search-input-wrapper:focus-within {
        border-color: #007bff;
        box-shadow: 0 4px 12px rgba(0,123,255,0.15);
    }
    
    .search-icon {
        padding: 12px 16px;
        color: #6c757d;
        font-size: 18px;
    }
    
    .search-input {
        flex: 1;
        border: none;
        background: transparent;
        padding: 12px 8px;
        font-size: 16px;
        outline: none;
    }
    
    .search-actions {
        display: flex;
        align-items: center;
        padding: 8px;
        gap: 4px;
    }
    
    .search-actions button {
        background: none;
        border: none;
        padding: 8px;
        border-radius: 6px;
        color: #6c757d;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .search-actions button:hover {
        background: #f8f9fa;
        color: #007bff;
    }
    
    .search-suggestions {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #e0e6ed;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        z-index: 1000;
        margin-top: 4px;
        overflow: hidden;
    }
    
    .suggestions-content {
        max-height: 300px;
        overflow-y: auto;
    }
    
    .suggestions-title {
        padding: 12px 16px 8px;
        margin: 0;
        font-size: 12px;
        font-weight: 600;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .suggestions-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .suggestion-item {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid #f8f9fa;
        cursor: pointer;
        transition: background 0.2s ease;
    }
    
    .suggestion-item:hover,
    .suggestion-item.selected {
        background: #f8f9fa;
    }
    
    .suggestion-content {
        flex: 1;
    }
    
    .suggestion-text {
        font-size: 14px;
        color: #333;
    }
    
    .suggestion-text mark {
        background: #fff3cd;
        padding: 1px 2px;
        border-radius: 2px;
    }
    
    .suggestion-description {
        font-size: 12px;
        color: #6c757d;
        margin-top: 2px;
    }
    
    .suggestion-type {
        font-size: 11px;
        color: #6c757d;
        background: #f8f9fa;
        padding: 2px 6px;
        border-radius: 4px;
    }
    
    .quick-filters {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 1rem;
    }
    
    .quick-filters-content {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
    }
    
    .active-filters {
        margin-bottom: 1rem;
    }
    
    .active-filters-content {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    
    .active-filters-label {
        font-size: 14px;
        font-weight: 500;
        color: #495057;
    }
    
    .filter-tags {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    
    .filter-tag {
        display: inline-flex;
        align-items: center;
        background: #e7f3ff;
        color: #0066cc;
        padding: 4px 8px;
        border-radius: 16px;
        font-size: 12px;
        gap: 4px;
    }
    
    .tag-remove {
        background: none;
        border: none;
        color: inherit;
        cursor: pointer;
        padding: 0;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.2s ease;
    }
    
    .tag-remove:hover {
        background: rgba(0,0,0,0.1);
    }
    
    .advanced-filters-panel {
        background: white;
        border: 1px solid #e0e6ed;
        border-radius: 12px;
        margin-bottom: 1rem;
        overflow: hidden;
    }
    
    .advanced-filters-header {
        background: #f8f9fa;
        padding: 16px 20px;
        border-bottom: 1px solid #e0e6ed;
        display: flex;
        justify-content: between;
        align-items: center;
    }
    
    .advanced-filters-header h5 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
    }
    
    .filter-actions {
        display: flex;
        gap: 8px;
    }
    
    .advanced-filters-content {
        padding: 20px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
    }
    
    .filter-item {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .filter-label {
        font-size: 14px;
        font-weight: 500;
        color: #333;
        margin: 0;
    }
    
    .filter-description {
        font-size: 12px;
        color: #6c757d;
        margin: 0;
    }
    
    .multiselect-container {
        max-height: 150px;
        overflow-y: auto;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 8px;
    }
    
    .range-input-container {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .range-inputs {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .range-separator {
        font-size: 12px;
        color: #6c757d;
    }
    
    .daterange-container .date-presets {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
    }
    
    .tags-input-container {
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 8px;
        min-height: 40px;
    }
    
    .tags-list {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
        margin-bottom: 8px;
    }
    
    .tag {
        background: #e7f3ff;
        color: #0066cc;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    
    .tag-remove-btn {
        background: none;
        border: none;
        color: inherit;
        cursor: pointer;
        padding: 0;
        width: 12px;
        height: 12px;
    }
    
    .location-input-container,
    .user-select-container {
        position: relative;
    }
    
    .location-suggestions,
    .user-suggestions {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        z-index: 100;
        margin-top: 2px;
    }
    
    .search-results-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #e0e6ed;
        margin-bottom: 1rem;
    }
    
    .results-stats {
        display: flex;
        gap: 8px;
        align-items: center;
        font-size: 14px;
        color: #6c757d;
    }
    
    .results-count {
        font-weight: 500;
        color: #333;
    }
    
    .results-actions {
        display: flex;
        gap: 12px;
        align-items: center;
    }
    
    .view-options {
        display: flex;
        gap: 2px;
    }
    
    .view-btn.active {
        background: #007bff;
        color: white;
    }
    
    .search-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        gap: 12px;
    }
    
    .loading-text {
        font-size: 14px;
        color: #6c757d;
    }
    
    /* Tema oscuro */
    .eco-search-filter[data-theme="dark"] {
        color: #e9ecef;
    }
    
    .eco-search-filter[data-theme="dark"] .search-input-wrapper {
        background: #343a40;
        border-color: #495057;
    }
    
    .eco-search-filter[data-theme="dark"] .search-input {
        color: #e9ecef;
    }
    
    .eco-search-filter[data-theme="dark"] .search-suggestions {
        background: #343a40;
        border-color: #495057;
    }
    
    .eco-search-filter[data-theme="dark"] .suggestion-item:hover {
        background: #495057;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .advanced-filters-content {
            grid-template-columns: 1fr;
            padding: 16px;
        }
        
        .search-results-info {
            flex-direction: column;
            gap: 12px;
            align-items: stretch;
        }
        
        .quick-filters-content {
            grid-template-columns: 1fr;
        }
        
        .filter-actions {
            flex-wrap: wrap;
        }
        
        .active-filters-content {
            flex-direction: column;
            align-items: stretch;
            gap: 12px;
        }
    }
    
    /* Animaciones */
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .search-suggestions {
        animation: slideDown 0.2s ease;
    }
    
    .advanced-filters-panel {
        animation: slideDown 0.3s ease;
    }
`

// Inyectar CSS
if (!document.getElementById('eco-search-filter-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-search-filter-styles'
  style.textContent = searchFilterCSS
  document.head.appendChild(style)
}

// Factory methods para contextos específicos
EcoSearchFilter.createEntrepreneursSearch = (container, options = {}) => {
  return new EcoSearchFilter(container, {
    context: 'entrepreneurs',
    ...options
  })
}

EcoSearchFilter.createProjectsSearch = (container, options = {}) => {
  return new EcoSearchFilter(container, {
    context: 'projects',
    ...options
  })
}

EcoSearchFilter.createMentorsSearch = (container, options = {}) => {
  return new EcoSearchFilter(container, {
    context: 'mentors',
    ...options
  })
}

EcoSearchFilter.createDocumentsSearch = (container, options = {}) => {
  return new EcoSearchFilter(container, {
    context: 'documents',
    ...options
  })
}

// Exportar
window.EcoSearchFilter = EcoSearchFilter
export default EcoSearchFilter
