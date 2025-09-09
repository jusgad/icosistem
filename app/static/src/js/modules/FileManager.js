/**
 * File Manager Module
 * Sistema completo de gestión de archivos para el ecosistema de emprendimiento
 * Soporta upload, organización, compartir, versionado y colaboración
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class FileManager {
  constructor (options = {}) {
    this.config = {
      apiBaseUrl: '/api/v1/files',
      uploadUrl: '/api/v1/files/upload',
      maxFileSize: 100 * 1024 * 1024, // 100MB
      maxFiles: 10,
      chunkSize: 1024 * 1024, // 1MB chunks
      allowedTypes: [
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'rtf', 'csv', 'json', 'xml',
        'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp',
        'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm',
        'mp3', 'wav', 'ogg', 'flac',
        'zip', 'rar', '7z', 'tar', 'gz'
      ],
      thumbnailSize: { width: 150, height: 150 },
      previewSize: { width: 800, height: 600 },
      autoSave: true,
      enableVersioning: true,
      enableSharing: true,
      enableCollaboration: true,
      ...options
    }

    this.state = {
      currentPath: '/',
      selectedFiles: new Set(),
      currentView: 'grid', // grid, list, tree
      sortBy: 'name',
      sortOrder: 'asc',
      searchQuery: '',
      filters: {
        type: 'all',
        dateRange: 'all',
        owner: 'all',
        shared: 'all'
      },
      uploadQueue: [],
      isUploading: false,
      dragDropActive: false,
      clipboard: [],
      currentUser: null,
      permissions: {}
    }

    this.elements = {}
    this.dropZones = []
    this.eventListeners = []
    this.contextMenu = null
    this.previewModal = null
    this.shareModal = null
    this.socket = null

    this.init()
  }

  /**
     * Inicialización del FileManager
     */
  async init () {
    try {
      await this.setupDOM()
      await this.loadUserInfo()
      await this.setupEventListeners()
      await this.initializeWebSocket()
      await this.loadDirectory()
      await this.setupKeyboardShortcuts()
      await this.initializeContextMenu()

      // // console.log('✅ FileManager initialized successfully')
    } catch (error) {
      // // console.error('❌ Error initializing FileManager:', error)
      this.showError('Error al inicializar el gestor de archivos')
    }
  }

  /**
     * Configuración inicial del DOM
     */
  async setupDOM () {
    this.elements = {
      container: document.getElementById('file-manager'),
      toolbar: document.querySelector('.file-toolbar'),
      breadcrumbs: document.querySelector('.file-breadcrumbs'),
      searchInput: document.querySelector('.file-search'),
      viewToggle: document.querySelectorAll('.view-toggle'),
      sortSelect: document.querySelector('.sort-select'),
      filterPanel: document.querySelector('.filter-panel'),
      fileGrid: document.querySelector('.file-grid'),
      fileList: document.querySelector('.file-list'),
      fileTree: document.querySelector('.file-tree'),
      uploadArea: document.querySelector('.upload-area'),
      uploadInput: document.querySelector('#file-upload-input'),
      progressContainer: document.querySelector('.upload-progress'),
      statusBar: document.querySelector('.status-bar'),
      contextMenu: document.querySelector('.context-menu'),
      previewModal: document.querySelector('#preview-modal'),
      shareModal: document.querySelector('#share-modal'),
      propertiesModal: document.querySelector('#properties-modal')
    }

    // Crear elementos faltantes si no existen
    await this.createMissingElements()
  }

  /**
     * Crear elementos DOM faltantes
     */
  async createMissingElements () {
    if (!this.elements.container) {
      throw new Error('FileManager container not found')
    }

    // Crear estructura básica si no existe
    if (!this.elements.toolbar) {
      this.elements.container.innerHTML = this.getFileManagerHTML()
      await this.setupDOM() // Re-ejecutar para obtener nuevos elementos
    }
  }

  /**
     * HTML del FileManager
     */
  getFileManagerHTML () {
    return `
            <div class="file-manager-wrapper">
                <!-- Toolbar -->
                <div class="file-toolbar d-flex justify-content-between align-items-center p-3 border-bottom">
                    <div class="toolbar-left d-flex align-items-center">
                        <button class="btn btn-sm btn-primary me-2" id="upload-btn">
                            <i class="fas fa-upload"></i> Subir
                        </button>
                        <button class="btn btn-sm btn-outline-secondary me-2" id="new-folder-btn">
                            <i class="fas fa-folder-plus"></i> Nueva Carpeta
                        </button>
                        <div class="btn-group me-2">
                            <button class="btn btn-sm btn-outline-secondary" id="cut-btn" disabled>
                                <i class="fas fa-cut"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" id="copy-btn" disabled>
                                <i class="fas fa-copy"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" id="paste-btn" disabled>
                                <i class="fas fa-paste"></i>
                            </button>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" id="delete-btn" disabled>
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    
                    <div class="toolbar-center flex-grow-1 mx-3">
                        <div class="file-breadcrumbs d-flex align-items-center">
                            <span class="breadcrumb-item active">Inicio</span>
                        </div>
                    </div>
                    
                    <div class="toolbar-right d-flex align-items-center">
                        <input type="text" class="form-control form-control-sm file-search me-2" 
                               placeholder="Buscar archivos..." style="width: 200px;">
                        
                        <div class="btn-group me-2">
                            <button class="btn btn-sm btn-outline-secondary view-toggle active" data-view="grid">
                                <i class="fas fa-th"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary view-toggle" data-view="list">
                                <i class="fas fa-list"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary view-toggle" data-view="tree">
                                <i class="fas fa-sitemap"></i>
                            </button>
                        </div>
                        
                        <select class="form-select form-select-sm sort-select" style="width: auto;">
                            <option value="name-asc">Nombre A-Z</option>
                            <option value="name-desc">Nombre Z-A</option>
                            <option value="date-desc">Más reciente</option>
                            <option value="date-asc">Más antiguo</option>
                            <option value="size-desc">Tamaño mayor</option>
                            <option value="size-asc">Tamaño menor</option>
                            <option value="type-asc">Tipo</option>
                        </select>
                    </div>
                </div>

                <!-- Main Content -->
                <div class="file-manager-body d-flex" style="height: calc(100vh - 200px);">
                    <!-- Sidebar -->
                    <div class="file-sidebar border-end" style="width: 250px; min-width: 250px;">
                        <div class="filter-panel p-3">
                            <h6>Filtros</h6>
                            
                            <div class="mb-3">
                                <label class="form-label">Tipo</label>
                                <select class="form-select form-select-sm" id="type-filter">
                                    <option value="all">Todos</option>
                                    <option value="documents">Documentos</option>
                                    <option value="images">Imágenes</option>
                                    <option value="videos">Videos</option>
                                    <option value="audio">Audio</option>
                                    <option value="archives">Archivos</option>
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Fecha</label>
                                <select class="form-select form-select-sm" id="date-filter">
                                    <option value="all">Todas</option>
                                    <option value="today">Hoy</option>
                                    <option value="week">Esta semana</option>
                                    <option value="month">Este mes</option>
                                    <option value="year">Este año</option>
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Propietario</label>
                                <select class="form-select form-select-sm" id="owner-filter">
                                    <option value="all">Todos</option>
                                    <option value="me">Míos</option>
                                    <option value="shared">Compartidos</option>
                                </select>
                            </div>
                        </div>
                        
                        <!-- Quick Access -->
                        <div class="quick-access p-3 border-top">
                            <h6>Acceso Rápido</h6>
                            <ul class="list-unstyled">
                                <li><a href="#" class="quick-link" data-path="/recent"><i class="fas fa-clock"></i> Recientes</a></li>
                                <li><a href="#" class="quick-link" data-path="/shared"><i class="fas fa-users"></i> Compartidos</a></li>
                                <li><a href="#" class="quick-link" data-path="/favorites"><i class="fas fa-star"></i> Favoritos</a></li>
                                <li><a href="#" class="quick-link" data-path="/trash"><i class="fas fa-trash"></i> Papelera</a></li>
                            </ul>
                        </div>
                    </div>

                    <!-- Content Area -->
                    <div class="file-content flex-grow-1 position-relative">
                        <!-- Upload Drop Zone -->
                        <div class="upload-area position-absolute w-100 h-100 d-none" style="z-index: 1000;">
                            <div class="upload-overlay d-flex align-items-center justify-content-center h-100">
                                <div class="upload-message text-center">
                                    <i class="fas fa-cloud-upload-alt fa-4x text-primary mb-3"></i>
                                    <h4>Suelta los archivos aquí</h4>
                                    <p class="text-muted">O haz clic para seleccionar archivos</p>
                                </div>
                            </div>
                        </div>

                        <!-- File Views -->
                        <div class="file-views h-100">
                            <!-- Grid View -->
                            <div class="file-grid active p-3" style="overflow-y: auto; height: 100%;"></div>
                            
                            <!-- List View -->
                            <div class="file-list d-none p-3" style="overflow-y: auto; height: 100%;">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th width="30"><input type="checkbox" class="select-all"></th>
                                            <th>Nombre</th>
                                            <th>Tamaño</th>
                                            <th>Tipo</th>
                                            <th>Modificado</th>
                                            <th>Propietario</th>
                                            <th width="100">Acciones</th>
                                        </tr>
                                    </thead>
                                    <tbody></tbody>
                                </table>
                            </div>
                            
                            <!-- Tree View -->
                            <div class="file-tree d-none p-3" style="overflow-y: auto; height: 100%;"></div>
                        </div>

                        <!-- Upload Progress -->
                        <div class="upload-progress position-absolute bottom-0 end-0 m-3" style="width: 300px; z-index: 1001;"></div>
                    </div>
                </div>

                <!-- Status Bar -->
                <div class="status-bar d-flex justify-content-between align-items-center p-2 bg-light border-top">
                    <div class="status-left">
                        <span class="file-count">0 archivos</span>
                        <span class="selected-count ms-2"></span>
                    </div>
                    <div class="status-right">
                        <span class="storage-info">Almacenamiento usado: 0 GB</span>
                    </div>
                </div>

                <!-- Hidden File Input -->
                <input type="file" id="file-upload-input" multiple style="display: none;">
            </div>
        `
  }

  /**
     * Configuración de event listeners
     */
  async setupEventListeners () {
    // Upload button
    const uploadBtn = document.getElementById('upload-btn')
    if (uploadBtn) {
      uploadBtn.addEventListener('click', () => this.triggerFileSelection())
    }

    // File input
    if (this.elements.uploadInput) {
      this.elements.uploadInput.addEventListener('change', (e) => {
        this.handleFileSelection(e.target.files)
      })
    }

    // New folder button
    const newFolderBtn = document.getElementById('new-folder-btn')
    if (newFolderBtn) {
      newFolderBtn.addEventListener('click', () => this.createNewFolder())
    }

    // Toolbar buttons
    this.setupToolbarListeners()

    // View toggles
    document.querySelectorAll('.view-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const view = e.target.closest('button').dataset.view
        this.switchView(view)
      })
    })

    // Sort select
    const sortSelect = document.querySelector('.sort-select')
    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        const [sortBy, sortOrder] = e.target.value.split('-')
        this.updateSort(sortBy, sortOrder)
      })
    }

    // Search input
    const searchInput = document.querySelector('.file-search')
    if (searchInput) {
      let searchTimeout
      searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout)
        searchTimeout = setTimeout(() => {
          this.updateSearch(e.target.value)
        }, 300)
      })
    }

    // Filter selects
    this.setupFilterListeners()

    // Drag and drop
    this.setupDragAndDrop()

    // Quick access links
    document.querySelectorAll('.quick-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault()
        const path = e.target.closest('a').dataset.path
        this.navigateToPath(path)
      })
    })

    // Select all checkbox
    const selectAllCheckbox = document.querySelector('.select-all')
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener('change', (e) => {
        this.toggleSelectAll(e.target.checked)
      })
    }

    // Breadcrumb navigation
    this.setupBreadcrumbListeners()
  }

  /**
     * Configuración de toolbar listeners
     */
  setupToolbarListeners () {
    const toolbarButtons = {
      'cut-btn': () => this.cutSelectedFiles(),
      'copy-btn': () => this.copySelectedFiles(),
      'paste-btn': () => this.pasteFiles(),
      'delete-btn': () => this.deleteSelectedFiles()
    }

    Object.entries(toolbarButtons).forEach(([id, handler]) => {
      const btn = document.getElementById(id)
      if (btn) {
        btn.addEventListener('click', handler)
      }
    })
  }

  /**
     * Configuración de filtros
     */
  setupFilterListeners () {
    const filters = ['type-filter', 'date-filter', 'owner-filter']

    filters.forEach(filterId => {
      const filter = document.getElementById(filterId)
      if (filter) {
        filter.addEventListener('change', (e) => {
          const filterType = filterId.replace('-filter', '')
          this.updateFilter(filterType, e.target.value)
        })
      }
    })
  }

  /**
     * Configuración de drag and drop
     */
  setupDragAndDrop () {
    const dropZone = this.elements.container;

    // Eventos de drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, this.preventDefaults, false)
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => this.highlightDropZone(), false)
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, () => this.unhighlightDropZone(), false)
    })

    dropZone.addEventListener('drop', (e) => this.handleDrop(e), false)
  }

  /**
     * Configuración de atajos de teclado
     */
  async setupKeyboardShortcuts () {
    document.addEventListener('keydown', (e) => {
      // Ctrl/Cmd + A - Seleccionar todo
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault()
        this.selectAll()
      }

      // Ctrl/Cmd + C - Copiar
      if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        if (this.state.selectedFiles.size > 0) {
          e.preventDefault()
          this.copySelectedFiles()
        }
      }

      // Ctrl/Cmd + X - Cortar
      if ((e.ctrlKey || e.metaKey) && e.key === 'x') {
        if (this.state.selectedFiles.size > 0) {
          e.preventDefault()
          this.cutSelectedFiles()
        }
      }

      // Ctrl/Cmd + V - Pegar
      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        if (this.state.clipboard.length > 0) {
          e.preventDefault()
          this.pasteFiles()
        }
      }

      // Delete - Eliminar
      if (e.key === 'Delete') {
        if (this.state.selectedFiles.size > 0) {
          e.preventDefault()
          this.deleteSelectedFiles()
        }
      }

      // F2 - Renombrar
      if (e.key === 'F2') {
        if (this.state.selectedFiles.size === 1) {
          e.preventDefault()
          const fileId = Array.from(this.state.selectedFiles)[0]
          this.renameFile(fileId)
        }
      }

      // Escape - Deseleccionar
      if (e.key === 'Escape') {
        this.clearSelection()
        this.hideContextMenu()
      }
    })
  }

  /**
     * Inicialización del menú contextual
     */
  async initializeContextMenu () {
    // Crear menú contextual si no existe
    if (!this.elements.contextMenu) {
      this.contextMenu = this.createContextMenu()
      document.body.appendChild(this.contextMenu)
    }

    // Click derecho en archivos
    this.elements.container.addEventListener('contextmenu', (e) => {
      e.preventDefault()
      this.showContextMenu(e)
    })

    // Ocultar menú al hacer click fuera
    document.addEventListener('click', () => {
      this.hideContextMenu()
    })
  }

  /**
     * Crear menú contextual
     */
  createContextMenu () {
    const menu = document.createElement('div')
    menu.className = 'context-menu dropdown-menu position-absolute'
    menu.style.zIndex = '9999'
    menu.innerHTML = `
            <a class="dropdown-item" href="#" data-action="open"><i class="fas fa-folder-open me-2"></i>Abrir</a>
            <a class="dropdown-item" href="#" data-action="download"><i class="fas fa-download me-2"></i>Descargar</a>
            <div class="dropdown-divider"></div>
            <a class="dropdown-item" href="#" data-action="cut"><i class="fas fa-cut me-2"></i>Cortar</a>
            <a class="dropdown-item" href="#" data-action="copy"><i class="fas fa-copy me-2"></i>Copiar</a>
            <a class="dropdown-item" href="#" data-action="paste"><i class="fas fa-paste me-2"></i>Pegar</a>
            <div class="dropdown-divider"></div>
            <a class="dropdown-item" href="#" data-action="rename"><i class="fas fa-edit me-2"></i>Renombrar</a>
            <a class="dropdown-item" href="#" data-action="share"><i class="fas fa-share me-2"></i>Compartir</a>
            <a class="dropdown-item" href="#" data-action="properties"><i class="fas fa-info-circle me-2"></i>Propiedades</a>
            <div class="dropdown-divider"></div>
            <a class="dropdown-item text-danger" href="#" data-action="delete"><i class="fas fa-trash me-2"></i>Eliminar</a>
        `

    // Event listeners para el menú
    menu.addEventListener('click', (e) => {
      e.preventDefault()
      const action = e.target.closest('a')?.dataset.action
      if (action) {
        this.handleContextMenuAction(action)
        this.hideContextMenu()
      }
    })

    return menu
  }

  /**
     * Inicialización de WebSocket
     */
  initializeWebSocket () {
    if (typeof io !== 'undefined') {
      this.socket = io('/file-manager', {
        transports: ['websocket', 'polling']
      })

      this.socket.on('connect', () => {
        // // console.log('🔗 FileManager WebSocket connected')
      })

      this.socket.on('file_uploaded', (data) => {
        this.handleFileUploadedEvent(data)
      })

      this.socket.on('file_deleted', (data) => {
        this.handleFileDeletedEvent(data)
      })

      this.socket.on('file_shared', (data) => {
        this.handleFileSharedEvent(data)
      })

      this.socket.on('folder_created', (data) => {
        this.handleFolderCreatedEvent(data)
      })
    }
  }

  /**
     * Cargar información del usuario
     */
  async loadUserInfo () {
    try {
      const response = await this.fetchData('/auth/user-info')
      this.state.currentUser = response.user
      this.state.permissions = response.permissions
    } catch (error) {
      // // console.error('Error loading user info:', error)
    }
  }

  /**
     * Cargar directorio actual
     */
  async loadDirectory (path = null) {
    try {
      this.showLoader()

      const currentPath = path || this.state.currentPath
      const queryParams = new URLSearchParams({
        path: currentPath,
        sort: this.state.sortBy,
        order: this.state.sortOrder,
        search: this.state.searchQuery,
        ...this.state.filters
      })

      const data = await this.fetchData(`?${queryParams}`)

      this.state.currentPath = currentPath
      this.updateBreadcrumbs(currentPath)
      this.renderFiles(data.files)
      this.updateStatusBar(data)
    } catch (error) {
      // // console.error('Error loading directory:', error)
      this.showError('Error al cargar el directorio')
    } finally {
      this.hideLoader()
    }
  }

  /**
     * Renderizar archivos según la vista actual
     */
  renderFiles (files) {
    switch (this.state.currentView) {
      case 'grid':
        this.renderGridView(files)
        break
      case 'list':
        this.renderListView(files)
        break
      case 'tree':
        this.renderTreeView(files)
        break
    }
  }

  /**
     * Vista de cuadrícula
     */
  renderGridView (files) {
    const container = this.elements.fileGrid
    container.innerHTML = ''

    files.forEach(file => {
      const fileElement = this.createFileGridItem(file)
      container.appendChild(fileElement)
    })
  }

  /**
     * Crear item de cuadrícula
     */
  createFileGridItem (file) {
    const div = document.createElement('div')
    div.className = 'file-item col-md-2 col-sm-3 col-4 mb-3'
    div.dataset.fileId = file.id
    div.dataset.fileType = file.type

    const isSelected = this.state.selectedFiles.has(file.id)
    const selectedClass = isSelected ? 'selected' : ''

    div.innerHTML = `
            <div class="file-card card h-100 ${selectedClass}" style="cursor: pointer;">
                <div class="file-thumbnail d-flex align-items-center justify-content-center p-2" style="height: 120px;">
                    ${this.getFileThumbnail(file)}
                </div>
                <div class="card-body p-2">
                    <div class="file-name text-truncate" title="${file.name}">
                        <small>${file.name}</small>
                    </div>
                    <div class="file-meta">
                        <small class="text-muted">${this.formatFileSize(file.size)}</small>
                        ${file.isShared ? '<i class="fas fa-users text-info ms-1"></i>' : ''}
                        ${file.isFavorite ? '<i class="fas fa-star text-warning ms-1"></i>' : ''}
                    </div>
                </div>
                <div class="file-checkbox position-absolute top-0 start-0 m-1">
                    <input type="checkbox" class="form-check-input" ${isSelected ? 'checked' : ''}>
                </div>
            </div>
        `

    // Event listeners
    this.setupFileItemListeners(div, file)

    return div
  }

  /**
     * Vista de lista
     */
  renderListView (files) {
    const tbody = this.elements.fileList.querySelector('tbody')
    tbody.innerHTML = ''

    files.forEach(file => {
      const row = this.createFileListRow(file)
      tbody.appendChild(row)
    })
  }

  /**
     * Crear fila de lista
     */
  createFileListRow (file) {
    const tr = document.createElement('tr')
    tr.dataset.fileId = file.id
    tr.dataset.fileType = file.type

    const isSelected = this.state.selectedFiles.has(file.id)

    tr.innerHTML = `
            <td><input type="checkbox" class="form-check-input" ${isSelected ? 'checked' : ''}></td>
            <td>
                <div class="d-flex align-items-center">
                    ${this.getFileIcon(file)}
                    <span class="ms-2">${file.name}</span>
                    ${file.isShared ? '<i class="fas fa-users text-info ms-2"></i>' : ''}
                    ${file.isFavorite ? '<i class="fas fa-star text-warning ms-2"></i>' : ''}
                </div>
            </td>
            <td>${file.isFolder ? '-' : this.formatFileSize(file.size)}</td>
            <td>${this.getFileTypeDisplay(file)}</td>
            <td>${this.formatDate(file.modified)}</td>
            <td>${file.owner}</td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-sm" data-action="download" title="Descargar">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn btn-outline-info btn-sm" data-action="share" title="Compartir">
                        <i class="fas fa-share"></i>
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" data-action="more" title="Más opciones">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                </div>
            </td>
        `

    // Event listeners
    this.setupFileItemListeners(tr, file)

    return tr
  }

  /**
     * Configurar listeners de items de archivo
     */
  setupFileItemListeners (element, file) {
    // Click en el archivo
    element.addEventListener('click', (e) => {
      if (e.target.type === 'checkbox') {
        this.toggleFileSelection(file.id, e.target.checked)
      } else if (e.target.closest('[data-action]')) {
        const action = e.target.closest('[data-action]').dataset.action
        this.handleFileAction(action, file)
      } else {
        // Doble click para abrir
        if (e.detail === 2) {
          this.openFile(file)
        } else {
          // Single click para seleccionar
          if (!e.ctrlKey && !e.metaKey) {
            this.clearSelection()
          }
          this.toggleFileSelection(file.id, true)
        }
      }
    })

    // Checkbox change
    const checkbox = element.querySelector('input[type="checkbox"]')
    if (checkbox) {
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation()
        this.toggleFileSelection(file.id, e.target.checked)
      })
    }
  }

  /**
     * Obtener thumbnail del archivo
     */
  getFileThumbnail (file) {
    if (file.isFolder) {
      return '<i class="fas fa-folder fa-3x text-warning"></i>'
    }

    if (file.thumbnail) {
      return `<img src="${file.thumbnail}" alt="${file.name}" class="img-fluid" style="max-height: 100px;">`
    }

    return this.getFileIcon(file, 'fa-3x')
  }

  /**
     * Obtener icono del archivo
     */
  getFileIcon (file, size = '') {
    if (file.isFolder) {
      return `<i class="fas fa-folder ${size} text-warning"></i>`
    }

    const iconMap = {
      // Documentos
      pdf: 'fas fa-file-pdf text-danger',
      doc: 'fas fa-file-word text-primary',
      docx: 'fas fa-file-word text-primary',
      xls: 'fas fa-file-excel text-success',
      xlsx: 'fas fa-file-excel text-success',
      ppt: 'fas fa-file-powerpoint text-warning',
      pptx: 'fas fa-file-powerpoint text-warning',
      txt: 'fas fa-file-alt text-secondary',

      // Imágenes
      jpg: 'fas fa-file-image text-info',
      jpeg: 'fas fa-file-image text-info',
      png: 'fas fa-file-image text-info',
      gif: 'fas fa-file-image text-info',
      svg: 'fas fa-file-image text-info',

      // Videos
      mp4: 'fas fa-file-video text-danger',
      avi: 'fas fa-file-video text-danger',
      mov: 'fas fa-file-video text-danger',

      // Audio
      mp3: 'fas fa-file-audio text-success',
      wav: 'fas fa-file-audio text-success',

      // Archivos
      zip: 'fas fa-file-archive text-warning',
      rar: 'fas fa-file-archive text-warning',
      '7z': 'fas fa-file-archive text-warning'
    }

    const extension = file.name.split('.').pop().toLowerCase()
    const iconClass = iconMap[extension] || 'fas fa-file text-secondary'

    return `<i class="${iconClass} ${size}"></i>`
  }

  /**
     * Manejo de selección de archivos
     */
  triggerFileSelection () {
    this.elements.uploadInput.click()
  }

  /**
     * Manejo de archivos seleccionados
     */
  handleFileSelection (files) {
    if (files.length === 0) return

    // Validar archivos
    const validFiles = Array.from(files).filter(file => this.validateFile(file))

    if (validFiles.length > 0) {
      this.uploadFiles(validFiles)
    }
  }

  /**
     * Validar archivo
     */
  validateFile (file) {
    // Validar tamaño
    if (file.size > this.config.maxFileSize) {
      this.showError(`El archivo ${file.name} es muy grande. Tamaño máximo: ${this.formatFileSize(this.config.maxFileSize)}`)
      return false
    }

    // Validar tipo
    const extension = file.name.split('.').pop().toLowerCase()
    if (!this.config.allowedTypes.includes(extension)) {
      this.showError(`Tipo de archivo no permitido: ${extension}`)
      return false
    }

    return true
  }

  /**
     * Subir archivos
     */
  async uploadFiles (files) {
    this.state.isUploading = true
    this.updateToolbarState()

    for (const file of files) {
      try {
        await this.uploadFile(file)
      } catch (error) {
        // // console.error(`Error uploading ${file.name}:`, error)
        this.showError(`Error al subir ${file.name}: ${error.message}`)
      }
    }

    this.state.isUploading = false
    this.updateToolbarState()

    // Recargar directorio
    await this.loadDirectory()
  }

  /**
     * Subir archivo individual
     */
  async uploadFile (file) {
    const uploadId = this.generateId()
    const progressElement = this.createProgressElement(uploadId, file.name)

    try {
      // Si el archivo es grande, usar upload chunked
      if (file.size > this.config.chunkSize) {
        await this.uploadFileChunked(file, uploadId, progressElement)
      } else {
        await this.uploadFileSimple(file, uploadId, progressElement)
      }

      // Remover elemento de progreso después de 2 segundos
      setTimeout(() => {
        progressElement.remove()
      }, 2000)
    } catch (error) {
      progressElement.querySelector('.progress-bar').classList.add('bg-danger')
      progressElement.querySelector('.upload-status').textContent = 'Error'
      throw error
    }
  }

  /**
     * Upload simple de archivo
     */
  async uploadFileSimple (file, uploadId, progressElement) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('path', this.state.currentPath)
    formData.append('upload_id', uploadId)

    const xhr = new XMLHttpRequest()

    return new Promise((resolve, reject) => {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = (e.loaded / e.total) * 100
          this.updateProgress(progressElement, progress)
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
          const response = JSON.parse(xhr.responseText)
          this.updateProgress(progressElement, 100)
          resolve(response)
        } else {
          reject(new Error('Upload failed'))
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'))
      })

      xhr.open('POST', this.config.uploadUrl)
      xhr.setRequestHeader('X-CSRFToken', this.getCSRFToken())
      xhr.send(formData)
    })
  }

  /**
     * Upload chunked de archivo grande
     */
  async uploadFileChunked (file, uploadId, progressElement) {
    const chunks = Math.ceil(file.size / this.config.chunkSize)
    let uploadedBytes = 0

    for (let chunkIndex = 0; chunkIndex < chunks; chunkIndex++) {
      const start = chunkIndex * this.config.chunkSize
      const end = Math.min(start + this.config.chunkSize, file.size)
      const chunk = file.slice(start, end)

      const formData = new FormData()
      formData.append('file', chunk)
      formData.append('upload_id', uploadId)
      formData.append('chunk_index', chunkIndex)
      formData.append('total_chunks', chunks)
      formData.append('original_name', file.name)
      formData.append('path', this.state.currentPath)

      const response = await fetch(`${this.config.uploadUrl}/chunked`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': this.getCSRFToken()
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error('Chunk upload failed')
      }

      uploadedBytes += chunk.size
      const progress = (uploadedBytes / file.size) * 100
      this.updateProgress(progressElement, progress)
    }
  }

  /**
     * Crear elemento de progreso
     */
  createProgressElement (uploadId, fileName) {
    const container = this.elements.progressContainer
    const element = document.createElement('div')
    element.className = 'upload-item card mb-2'
    element.dataset.uploadId = uploadId

    element.innerHTML = `
            <div class="card-body p-2">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="upload-filename text-truncate">${fileName}</small>
                    <small class="upload-status">Subiendo...</small>
                </div>
                <div class="progress" style="height: 4px;">
                    <div class="progress-bar" style="width: 0%"></div>
                </div>
            </div>
        `

    container.appendChild(element)
    return element
  }

  /**
     * Actualizar progreso de upload
     */
  updateProgress (element, progress) {
    const progressBar = element.querySelector('.progress-bar')
    const status = element.querySelector('.upload-status')

    progressBar.style.width = `${progress}%`

    if (progress >= 100) {
      progressBar.classList.add('bg-success')
      status.textContent = 'Completado'
    } else {
      status.textContent = `${Math.round(progress)}%`
    }
  }

  /**
     * Manejo de drag and drop
     */
  preventDefaults (e) {
    e.preventDefault()
    e.stopPropagation()
  }

  highlightDropZone () {
    this.state.dragDropActive = true
    this.elements.uploadArea.classList.remove('d-none')
  }

  unhighlightDropZone () {
    this.state.dragDropActive = false
    this.elements.uploadArea.classList.add('d-none')
  }

  handleDrop (e) {
    const files = Array.from(e.dataTransfer.files)
    this.handleFileSelection(files)
  }

  /**
     * Operaciones de archivos
     */
  async openFile (file) {
    if (file.isFolder) {
      this.navigateToPath(file.path)
    } else {
      // Abrir preview o descargar
      if (this.isPreviewable(file)) {
        this.showPreview(file)
      } else {
        this.downloadFile(file)
      }
    }
  }

  async downloadFile (file) {
    try {
      const response = await fetch(`${this.config.apiBaseUrl}/${file.id}/download`, {
        headers: {
          'X-CSRFToken': this.getCSRFToken()
        }
      })

      if (!response.ok) throw new Error('Download failed')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      // // console.error('Error downloading file:', error)
      this.showError('Error al descargar el archivo')
    }
  }

  toggleFileSelection (fileId, selected) {
    if (selected) {
      this.state.selectedFiles.add(fileId)
    } else {
      this.state.selectedFiles.delete(fileId)
    }

    this.updateSelectionUI()
    this.updateToolbarState()
  }

  clearSelection () {
    this.state.selectedFiles.clear()
    this.updateSelectionUI()
    this.updateToolbarState()
  }

  selectAll () {
    const fileElements = document.querySelectorAll('[data-file-id]')
    fileElements.forEach(element => {
      const fileId = element.dataset.fileId
      this.state.selectedFiles.add(fileId)
    })

    this.updateSelectionUI()
    this.updateToolbarState()
  }

  /**
     * Operaciones de carpeta
     */
  async createNewFolder () {
    const name = prompt('Nombre de la nueva carpeta:')
    if (!name) return

    try {
      const response = await this.fetchData('/folders', {
        method: 'POST',
        body: JSON.stringify({
          name,
          path: this.state.currentPath
        })
      })

      this.showSuccess('Carpeta creada exitosamente')
      await this.loadDirectory()
    } catch (error) {
      // // console.error('Error creating folder:', error)
      this.showError('Error al crear la carpeta')
    }
  }

  /**
     * Navegación
     */
  navigateToPath (path) {
    this.state.currentPath = path
    this.loadDirectory(path)
  }

  updateBreadcrumbs (path) {
    const breadcrumbs = this.elements.breadcrumbs
    breadcrumbs.innerHTML = ''

    const parts = path.split('/').filter(part => part)
    let currentPath = ''

    // Home
    const homeItem = document.createElement('span')
    homeItem.className = 'breadcrumb-item'
    homeItem.innerHTML = '<a href="#" data-path="/">Inicio</a>'
    breadcrumbs.appendChild(homeItem)

    // Path parts
    parts.forEach((part, index) => {
      currentPath += `/${part}`
      const item = document.createElement('span')
      item.className = index === parts.length - 1 ? 'breadcrumb-item active' : 'breadcrumb-item'

      if (index === parts.length - 1) {
        item.textContent = part
      } else {
        item.innerHTML = `<a href="#" data-path="${currentPath}">${part}</a>`
      }

      breadcrumbs.appendChild(item)
    })
  }

  setupBreadcrumbListeners () {
    this.elements.breadcrumbs.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') {
        e.preventDefault()
        const path = e.target.dataset.path
        this.navigateToPath(path)
      }
    })
  }

  /**
     * Cambio de vista
     */
  switchView (view) {
    if (this.state.currentView === view) return

    // Ocultar vista actual
    document.querySelector(`.file-${this.state.currentView}`).classList.add('d-none')

    // Mostrar nueva vista
    document.querySelector(`.file-${view}`).classList.remove('d-none')

    // Actualizar botones
    document.querySelectorAll('.view-toggle').forEach(btn => {
      btn.classList.remove('active')
    })
    document.querySelector(`[data-view="${view}"]`).classList.add('active')

    this.state.currentView = view

    // Re-renderizar archivos en la nueva vista
    this.loadDirectory()
  }

  /**
     * Utilidades
     */
  async fetchData (endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${this.config.apiBaseUrl}${endpoint}`

    const defaultOptions = {
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
        'Content-Type': 'application/json'
      }
    }

    const response = await fetch(url, { ...defaultOptions, ...options })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return await response.json()
  }

  getCSRFToken () {
    return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
  }

  formatFileSize (bytes) {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  formatDate (dateString) {
    const date = new Date(dateString)
    return date.toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  generateId () {
    return Math.random().toString(36).substr(2, 9)
  }

  showLoader () {
    // Implementar loader
  }

  hideLoader () {
    // Implementar loader
  }

  showError (message) {
    // Implementar notificación de error
    // // console.error(message)
  }

  showSuccess (message) {
    // Implementar notificación de éxito
    // // console.log(message)
  }

  updateToolbarState () {
    const hasSelection = this.state.selectedFiles.size > 0
    const hasClipboard = this.state.clipboard.length > 0

    document.getElementById('cut-btn').disabled = !hasSelection
    document.getElementById('copy-btn').disabled = !hasSelection
    document.getElementById('paste-btn').disabled = !hasClipboard
    document.getElementById('delete-btn').disabled = !hasSelection
  }

  updateSelectionUI () {
    const count = this.state.selectedFiles.size
    const selectedCount = document.querySelector('.selected-count')

    if (selectedCount) {
      selectedCount.textContent = count > 0 ? `${count} seleccionados` : ''
    }

    // Actualizar checkboxes
    document.querySelectorAll('[data-file-id]').forEach(element => {
      const fileId = element.dataset.fileId
      const checkbox = element.querySelector('input[type="checkbox"]')
      const isSelected = this.state.selectedFiles.has(fileId)

      if (checkbox) {
        checkbox.checked = isSelected
      }

      if (this.state.currentView === 'grid') {
        element.querySelector('.file-card').classList.toggle('selected', isSelected)
      }
    })
  }

  updateStatusBar (data) {
    const fileCount = document.querySelector('.file-count')
    const storageInfo = document.querySelector('.storage-info')

    if (fileCount) {
      fileCount.textContent = `${data.totalFiles} archivos`
    }

    if (storageInfo) {
      storageInfo.textContent = `Almacenamiento usado: ${this.formatFileSize(data.usedStorage)}`
    }
  }

  /**
     * Cleanup
     */
  destroy () {
    if (this.socket) {
      this.socket.disconnect()
    }

    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    // // console.log('🧹 FileManager destroyed')
  }
}

// Inicialización automática
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('file-manager')) {
    window.fileManager = new FileManager()
  }
})

// Exportar para uso global
export default FileManager
