/**
 * FileUpload Component
 * Sistema completo de subida de archivos para el ecosistema de emprendimiento
 * Soporta drag&drop, chunked uploads, validación avanzada y tiempo real
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class EcoFileUpload {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.getElementById(element) : element;
        if (!this.element) {
            throw new Error('FileUpload element not found');
        }

        this.config = {
            // URLs y endpoints
            uploadUrl: options.uploadUrl || '/api/v1/files/upload',
            chunkedUploadUrl: options.chunkedUploadUrl || '/api/v1/files/upload/chunked',
            resumeUploadUrl: options.resumeUploadUrl || '/api/v1/files/upload/resume',
            
            // Configuración de archivos
            maxFileSize: options.maxFileSize || 100 * 1024 * 1024, // 100MB
            maxFiles: options.maxFiles || 10,
            chunkSize: options.chunkSize || 1024 * 1024, // 1MB chunks
            
            // Tipos de archivo permitidos específicos del ecosistema
            allowedTypes: options.allowedTypes || {
                documents: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'],
                images: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'],
                videos: ['mp4', 'avi', 'mov', 'wmv', 'mkv', 'webm'],
                audio: ['mp3', 'wav', 'ogg', 'flac', 'm4a'],
                archives: ['zip', 'rar', '7z', 'tar', 'gz'],
                text: ['txt', 'rtf', 'csv', 'json', 'xml', 'md']
            },
            
            // Configuración específica del ecosistema
            documentTypes: options.documentTypes || {
                pitchDeck: {
                    name: 'Pitch Deck',
                    allowedFormats: ['pdf', 'ppt', 'pptx'],
                    maxSize: 50 * 1024 * 1024,
                    required: ['title', 'description']
                },
                businessPlan: {
                    name: 'Plan de Negocio',
                    allowedFormats: ['pdf', 'doc', 'docx'],
                    maxSize: 25 * 1024 * 1024,
                    required: ['title', 'version']
                },
                financials: {
                    name: 'Documentos Financieros',
                    allowedFormats: ['pdf', 'xls', 'xlsx'],
                    maxSize: 20 * 1024 * 1024,
                    required: ['period', 'type']
                },
                legal: {
                    name: 'Documentos Legales',
                    allowedFormats: ['pdf'],
                    maxSize: 15 * 1024 * 1024,
                    required: ['type', 'date']
                },
                media: {
                    name: 'Material Multimedia',
                    allowedFormats: ['jpg', 'jpeg', 'png', 'mp4', 'mov'],
                    maxSize: 100 * 1024 * 1024,
                    required: ['title']
                }
            },
            
            // Interfaz y UX
            dragAndDrop: options.dragAndDrop !== false,
            showPreview: options.showPreview !== false,
            autoUpload: options.autoUpload !== false,
            multiple: options.multiple !== false,
            
            // Compresión de imágenes
            imageCompression: options.imageCompression !== false,
            imageQuality: options.imageQuality || 0.8,
            maxImageWidth: options.maxImageWidth || 1920,
            maxImageHeight: options.maxImageHeight || 1080,
            
            // Validación avanzada
            enableMetadataExtraction: options.enableMetadataExtraction !== false,
            enableVirusScan: options.enableVirusScan || false,
            enableOCR: options.enableOCR || false,
            
            // Comportamiento
            resumable: options.resumable !== false,
            retryAttempts: options.retryAttempts || 3,
            retryDelay: options.retryDelay || 1000,
            
            // Tiempo real
            enableWebSocket: options.enableWebSocket !== false,
            webSocketUrl: options.webSocketUrl || '/ws/uploads',
            
            // Templates y temas
            theme: options.theme || 'default',
            customTemplate: options.customTemplate || null,
            
            // Callbacks
            onFileAdd: options.onFileAdd || null,
            onFileRemove: options.onFileRemove || null,
            onUploadStart: options.onUploadStart || null,
            onUploadProgress: options.onUploadProgress || null,
            onUploadComplete: options.onUploadComplete || null,
            onUploadError: options.onUploadError || null,
            onAllUploadsComplete: options.onAllUploadsComplete || null,
            onValidationError: options.onValidationError || null,
            
            // Contexto del ecosistema
            context: options.context || 'general', // entrepreneur, mentor, admin, client
            userRole: options.userRole || 'user',
            projectId: options.projectId || null,
            
            ...options
        };

        this.state = {
            files: new Map(),
            uploadQueue: [],
            isUploading: false,
            dragActive: false,
            totalFiles: 0,
            completedFiles: 0,
            failedFiles: 0,
            totalBytes: 0,
            uploadedBytes: 0,
            socket: null,
            resumeData: new Map(),
            retryCount: new Map()
        };

        this.templates = new Map();
        this.validators = new Map();
        this.processors = new Map();
        this.eventListeners = [];
        this.dropZone = null;
        this.fileInput = null;
        this.previewContainer = null;
        this.progressContainer = null;

        this.init();
    }

    /**
     * Inicialización del componente
     */
    async init() {
        try {
            await this.setupTemplates();
            await this.setupValidators();
            await this.setupProcessors();
            await this.createInterface();
            await this.setupEventListeners();
            await this.initializeWebSocket();
            
            console.log('✅ EcoFileUpload initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing EcoFileUpload:', error);
            this.handleError(error);
        }
    }

    /**
     * Configurar templates de interfaz
     */
    async setupTemplates() {
        // Template principal
        this.templates.set('main', `
            <div class="eco-file-upload" data-theme="${this.config.theme}">
                <div class="upload-header">
                    <h3 class="upload-title">{{title}}</h3>
                    <p class="upload-description">{{description}}</p>
                </div>
                
                <div class="upload-dropzone" tabindex="0" role="button" aria-label="Área de subida de archivos">
                    <div class="dropzone-content">
                        <div class="dropzone-icon">
                            <i class="fas fa-cloud-upload-alt"></i>
                        </div>
                        <div class="dropzone-text">
                            <h4>Arrastra archivos aquí o haz clic para seleccionar</h4>
                            <p class="dropzone-hint">{{hint}}</p>
                        </div>
                        <button type="button" class="btn btn-primary btn-select-files">
                            <i class="fas fa-folder-open"></i> Seleccionar Archivos
                        </button>
                    </div>
                    <input type="file" class="file-input" hidden {{multiple}} {{accept}}>
                </div>
                
                <div class="upload-constraints">
                    <div class="constraints-grid">
                        <div class="constraint-item">
                            <i class="fas fa-file"></i>
                            <span>Máximo {{maxFiles}} archivos</span>
                        </div>
                        <div class="constraint-item">
                            <i class="fas fa-weight-hanging"></i>
                            <span>{{maxSize}} por archivo</span>
                        </div>
                        <div class="constraint-item">
                            <i class="fas fa-check-circle"></i>
                            <span>{{allowedTypes}}</span>
                        </div>
                    </div>
                </div>
                
                <div class="upload-queue" style="display: none;">
                    <div class="queue-header">
                        <h4>Archivos seleccionados</h4>
                        <div class="queue-actions">
                            <button type="button" class="btn btn-sm btn-success btn-upload-all" disabled>
                                <i class="fas fa-upload"></i> Subir Todo
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary btn-clear-all">
                                <i class="fas fa-trash"></i> Limpiar
                            </button>
                        </div>
                    </div>
                    <div class="queue-files"></div>
                </div>
                
                <div class="upload-progress" style="display: none;">
                    <div class="progress-header">
                        <h4>Progreso general</h4>
                        <span class="progress-stats">0 / 0 archivos</span>
                    </div>
                    <div class="progress">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="progress-details">
                        <span class="progress-speed">0 KB/s</span>
                        <span class="progress-eta">--:--</span>
                    </div>
                </div>
                
                <div class="upload-completed" style="display: none;">
                    <div class="completed-files"></div>
                </div>
            </div>
        `);

        // Template para archivo individual
        this.templates.set('fileItem', `
            <div class="file-item" data-file-id="{{id}}">
                <div class="file-preview">
                    {{preview}}
                </div>
                <div class="file-info">
                    <div class="file-name" title="{{name}}">{{name}}</div>
                    <div class="file-meta">
                        <span class="file-size">{{size}}</span>
                        <span class="file-type">{{type}}</span>
                        {{#if documentType}}
                        <span class="file-document-type">{{documentType}}</span>
                        {{/if}}
                    </div>
                    {{#if requiresMetadata}}
                    <div class="file-metadata">
                        <input type="text" class="form-control form-control-sm" 
                               placeholder="Título" data-meta="title" required>
                        {{#if showDescription}}
                        <textarea class="form-control form-control-sm mt-1" 
                                  placeholder="Descripción" data-meta="description" rows="2"></textarea>
                        {{/if}}
                        {{#each customFields}}
                        <input type="{{type}}" class="form-control form-control-sm mt-1" 
                               placeholder="{{label}}" data-meta="{{name}}" {{#if required}}required{{/if}}>
                        {{/each}}
                    </div>
                    {{/if}}
                </div>
                <div class="file-progress">
                    <div class="progress" style="display: none;">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="progress-text">Pendiente</div>
                </div>
                <div class="file-actions">
                    <button type="button" class="btn btn-sm btn-outline-primary btn-upload" title="Subir">
                        <i class="fas fa-upload"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger btn-remove" title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="file-status">
                    <i class="fas fa-clock text-warning" title="Pendiente"></i>
                </div>
            </div>
        `);

        // Template para diferentes tipos de preview
        this.templates.set('imagePreview', `
            <img src="{{src}}" alt="{{name}}" class="preview-image">
        `);

        this.templates.set('videoPreview', `
            <video class="preview-video" preload="metadata">
                <source src="{{src}}" type="{{mimeType}}">
            </video>
            <div class="video-overlay">
                <i class="fas fa-play"></i>
            </div>
        `);

        this.templates.set('documentPreview', `
            <div class="document-preview">
                <i class="{{icon}} document-icon"></i>
                <span class="document-pages">{{pages}} páginas</span>
            </div>
        `);

        this.templates.set('defaultPreview', `
            <div class="default-preview">
                <i class="{{icon}}"></i>
            </div>
        `);
    }

    /**
     * Configurar validadores específicos del ecosistema
     */
    async setupValidators() {
        // Validador de tamaño de archivo
        this.validators.set('fileSize', (file, config) => {
            const maxSize = config.maxSize || this.config.maxFileSize;
            if (file.size > maxSize) {
                return `El archivo "${file.name}" excede el tamaño máximo de ${this.formatFileSize(maxSize)}`;
            }
            return null;
        });

        // Validador de tipo de archivo
        this.validators.set('fileType', (file, config) => {
            const extension = this.getFileExtension(file.name);
            const allowedTypes = config.allowedFormats || this.getAllowedExtensions();
            
            if (!allowedTypes.includes(extension)) {
                return `Tipo de archivo "${extension}" no permitido. Tipos válidos: ${allowedTypes.join(', ')}`;
            }
            return null;
        });

        // Validador específico para pitch decks
        this.validators.set('pitchDeck', (file, config) => {
            const extension = this.getFileExtension(file.name);
            const maxSlides = 20;
            
            if (!['pdf', 'ppt', 'pptx'].includes(extension)) {
                return 'Los pitch decks deben ser archivos PDF o PowerPoint';
            }
            
            // Validación adicional para PPT (requiere análisis del archivo)
            if (['ppt', 'pptx'].includes(extension)) {
                // Esta validación se haría en el servidor, aquí solo advertimos
                return null; // Se validará en el servidor
            }
            
            return null;
        });

        // Validador de documentos financieros
        this.validators.set('financials', (file, config) => {
            const extension = this.getFileExtension(file.name);
            const validFormats = ['pdf', 'xls', 'xlsx'];
            
            if (!validFormats.includes(extension)) {
                return 'Los documentos financieros deben ser PDF o Excel';
            }
            
            // Validar nombres comunes de archivos financieros
            const financialKeywords = ['balance', 'p&l', 'cash flow', 'projection', 'budget'];
            const fileName = file.name.toLowerCase();
            
            if (!financialKeywords.some(keyword => fileName.includes(keyword))) {
                // Solo advertencia, no error
                console.warn('Archivo financiero sin palabras clave reconocidas');
            }
            
            return null;
        });

        // Validador de imágenes para compresión
        this.validators.set('imageOptimization', (file, config) => {
            if (!file.type.startsWith('image/')) return null;
            
            const warnings = [];
            
            // Crear imagen temporal para obtener dimensiones
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = () => {
                    if (img.width > this.config.maxImageWidth || img.height > this.config.maxImageHeight) {
                        warnings.push(`Imagen grande (${img.width}x${img.height}), se comprimirá automáticamente`);
                    }
                    
                    if (file.size > 5 * 1024 * 1024) { // 5MB
                        warnings.push('Imagen grande, se comprimirá automáticamente');
                    }
                    
                    resolve(warnings.length > 0 ? warnings.join(', ') : null);
                };
                
                img.onerror = () => resolve('No se pudo verificar las dimensiones de la imagen');
                img.src = URL.createObjectURL(file);
            });
        });

        // Validador de virus (simulado - en producción sería del servidor)
        this.validators.set('virusScan', async (file, config) => {
            if (!this.config.enableVirusScan) return null;
            
            // Simulación de escaneo
            await this.delay(500);
            
            // En producción, esto sería una llamada al servidor
            const suspicious = ['malware', 'virus', 'trojan'].some(term => 
                file.name.toLowerCase().includes(term)
            );
            
            return suspicious ? 'Archivo sospechoso detectado' : null;
        });
    }

    /**
     * Configurar procesadores de archivos
     */
    async setupProcessors() {
        // Procesador de compresión de imágenes
        this.processors.set('imageCompression', async (file) => {
            if (!this.config.imageCompression || !file.type.startsWith('image/')) {
                return file;
            }

            try {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();

                return new Promise((resolve) => {
                    img.onload = () => {
                        // Calcular nuevas dimensiones
                        let { width, height } = img;
                        const maxWidth = this.config.maxImageWidth;
                        const maxHeight = this.config.maxImageHeight;

                        if (width > maxWidth) {
                            height = (height * maxWidth) / width;
                            width = maxWidth;
                        }

                        if (height > maxHeight) {
                            width = (width * maxHeight) / height;
                            height = maxHeight;
                        }

                        canvas.width = width;
                        canvas.height = height;

                        // Dibujar imagen redimensionada
                        ctx.drawImage(img, 0, 0, width, height);

                        // Convertir a blob
                        canvas.toBlob((blob) => {
                            // Crear nuevo archivo con el blob comprimido
                            const compressedFile = new File(
                                [blob],
                                file.name,
                                { type: file.type, lastModified: Date.now() }
                            );
                            
                            resolve(compressedFile);
                        }, file.type, this.config.imageQuality);
                    };

                    img.onerror = () => resolve(file);
                    img.src = URL.createObjectURL(file);
                });
            } catch (error) {
                console.warn('Error compressing image:', error);
                return file;
            }
        });

        // Procesador de extracción de metadatos
        this.processors.set('metadataExtraction', async (file) => {
            if (!this.config.enableMetadataExtraction) return { file };

            const metadata = {
                name: file.name,
                size: file.size,
                type: file.type,
                lastModified: new Date(file.lastModified),
                extension: this.getFileExtension(file.name)
            };

            // Metadatos específicos por tipo
            if (file.type.startsWith('image/')) {
                metadata.category = 'image';
                try {
                    const dimensions = await this.getImageDimensions(file);
                    metadata.width = dimensions.width;
                    metadata.height = dimensions.height;
                    metadata.aspectRatio = dimensions.width / dimensions.height;
                } catch (error) {
                    console.warn('Error getting image dimensions:', error);
                }
            } else if (file.type.startsWith('video/')) {
                metadata.category = 'video';
                try {
                    const videoInfo = await this.getVideoInfo(file);
                    metadata.duration = videoInfo.duration;
                    metadata.width = videoInfo.width;
                    metadata.height = videoInfo.height;
                } catch (error) {
                    console.warn('Error getting video info:', error);
                }
            } else if (file.type === 'application/pdf') {
                metadata.category = 'document';
                try {
                    // En producción, esto sería procesado en el servidor
                    metadata.pages = await this.getPDFPageCount(file);
                } catch (error) {
                    console.warn('Error getting PDF info:', error);
                }
            }

            return { file, metadata };
        });

        // Procesador de generación de thumbnails
        this.processors.set('thumbnailGeneration', async (fileData) => {
            const { file } = fileData;
            
            if (file.type.startsWith('image/')) {
                try {
                    const thumbnail = await this.generateImageThumbnail(file);
                    return { ...fileData, thumbnail };
                } catch (error) {
                    console.warn('Error generating image thumbnail:', error);
                }
            } else if (file.type.startsWith('video/')) {
                try {
                    const thumbnail = await this.generateVideoThumbnail(file);
                    return { ...fileData, thumbnail };
                } catch (error) {
                    console.warn('Error generating video thumbnail:', error);
                }
            }

            return fileData;
        });
    }

    /**
     * Crear interfaz de usuario
     */
    async createInterface() {
        const template = this.config.customTemplate || this.templates.get('main');
        
        // Datos para el template
        const templateData = {
            title: this.getContextTitle(),
            description: this.getContextDescription(),
            hint: this.getContextHint(),
            maxFiles: this.config.maxFiles,
            maxSize: this.formatFileSize(this.config.maxFileSize),
            allowedTypes: this.getAllowedTypesText(),
            multiple: this.config.multiple ? 'multiple' : '',
            accept: this.getAcceptAttribute()
        };

        // Renderizar template
        this.element.innerHTML = this.renderTemplate(template, templateData);

        // Obtener referencias a elementos
        this.dropZone = this.element.querySelector('.upload-dropzone');
        this.fileInput = this.element.querySelector('.file-input');
        this.queueContainer = this.element.querySelector('.upload-queue');
        this.queueFiles = this.element.querySelector('.queue-files');
        this.progressContainer = this.element.querySelector('.upload-progress');
        this.completedContainer = this.element.querySelector('.upload-completed');
        
        // Aplicar tema
        this.applyTheme();
    }

    /**
     * Configurar event listeners
     */
    async setupEventListeners() {
        // Drag and drop en dropzone
        if (this.config.dragAndDrop) {
            this.setupDragAndDrop();
        }

        // Click en dropzone para abrir selector
        this.dropZone.addEventListener('click', () => {
            this.fileInput.click();
        });

        // Tecla Enter/Espacio en dropzone (accesibilidad)
        this.dropZone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.fileInput.click();
            }
        });

        // Cambio en input de archivo
        this.fileInput.addEventListener('change', (e) => {
            this.handleFileSelection(Array.from(e.target.files));
        });

        // Botón seleccionar archivos
        const selectBtn = this.element.querySelector('.btn-select-files');
        selectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.fileInput.click();
        });

        // Botones de acción
        const uploadAllBtn = this.element.querySelector('.btn-upload-all');
        const clearAllBtn = this.element.querySelector('.btn-clear-all');

        uploadAllBtn.addEventListener('click', () => this.uploadAll());
        clearAllBtn.addEventListener('click', () => this.clearAll());

        // Event delegation para botones de archivo individual
        this.queueFiles.addEventListener('click', (e) => {
            const fileItem = e.target.closest('.file-item');
            if (!fileItem) return;

            const fileId = fileItem.dataset.fileId;
            
            if (e.target.closest('.btn-upload')) {
                this.uploadFile(fileId);
            } else if (e.target.closest('.btn-remove')) {
                this.removeFile(fileId);
            }
        });

        // Cambios en metadata
        this.queueFiles.addEventListener('input', (e) => {
            if (e.target.dataset.meta) {
                const fileItem = e.target.closest('.file-item');
                const fileId = fileItem.dataset.fileId;
                const metaKey = e.target.dataset.meta;
                const value = e.target.value;

                this.updateFileMetadata(fileId, metaKey, value);
            }
        });

        // Resize observer para responsive
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                this.handleResize();
            });
            this.resizeObserver.observe(this.element);
        }
    }

    /**
     * Configurar funcionalidad drag and drop
     */
    setupDragAndDrop() {
        // Prevenir comportamiento por defecto
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight en drag enter/over
        ['dragenter', 'dragover'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, () => this.highlight(), false);
        });

        // Unhighlight en drag leave/drop
        ['dragleave', 'drop'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, () => this.unhighlight(), false);
        });

        // Manejar drop
        this.dropZone.addEventListener('drop', (e) => this.handleDrop(e), false);
    }

    /**
     * Manejar selección de archivos
     */
    async handleFileSelection(files) {
        if (files.length === 0) return;

        // Verificar límite de archivos
        if (this.state.files.size + files.length > this.config.maxFiles) {
            this.showError(`Máximo ${this.config.maxFiles} archivos permitidos`);
            return;
        }

        // Procesar cada archivo
        for (const file of files) {
            try {
                await this.addFile(file);
            } catch (error) {
                console.error('Error adding file:', error);
                this.showError(`Error al agregar ${file.name}: ${error.message}`);
            }
        }

        this.updateInterface();
    }

    /**
     * Agregar archivo a la cola
     */
    async addFile(file) {
        const fileId = this.generateFileId();
        
        // Detectar tipo de documento específico del ecosistema
        const documentType = this.detectDocumentType(file);
        
        // Crear objeto de archivo
        const fileData = {
            id: fileId,
            file: file,
            name: file.name,
            size: file.size,
            type: file.type,
            extension: this.getFileExtension(file.name),
            documentType: documentType,
            status: 'pending',
            progress: 0,
            uploadedBytes: 0,
            chunkIndex: 0,
            metadata: {},
            thumbnail: null,
            preview: null,
            errors: [],
            warnings: []
        };

        // Validar archivo
        const validationResult = await this.validateFile(file, documentType);
        if (validationResult.errors.length > 0) {
            throw new Error(validationResult.errors[0]);
        }
        
        fileData.warnings = validationResult.warnings;

        // Procesar archivo (compresión, metadatos, etc.)
        const processedData = await this.processFile(fileData);
        
        // Actualizar archivo procesado
        Object.assign(fileData, processedData);

        // Agregar a la colección
        this.state.files.set(fileId, fileData);
        this.state.totalFiles++;
        this.state.totalBytes += fileData.file.size;

        // Callback
        if (this.config.onFileAdd) {
            this.config.onFileAdd(fileData);
        }

        return fileData;
    }

    /**
     * Validar archivo
     */
    async validateFile(file, documentType = null) {
        const errors = [];
        const warnings = [];

        // Obtener configuración del tipo de documento
        const docConfig = documentType ? this.config.documentTypes[documentType] : {};

        // Ejecutar validadores
        for (const [name, validator] of this.validators.entries()) {
            try {
                const result = await validator(file, docConfig);
                if (result) {
                    if (name === 'imageOptimization') {
                        warnings.push(result);
                    } else {
                        errors.push(result);
                    }
                }
            } catch (error) {
                console.warn(`Validator ${name} failed:`, error);
            }
        }

        // Callback de validación
        if (this.config.onValidationError && errors.length > 0) {
            this.config.onValidationError(file, errors);
        }

        return { errors, warnings };
    }

    /**
     * Procesar archivo
     */
    async processFile(fileData) {
        let processedData = { ...fileData };

        // Ejecutar procesadores en secuencia
        for (const [name, processor] of this.processors.entries()) {
            try {
                const result = await processor(processedData);
                if (result) {
                    processedData = { ...processedData, ...result };
                }
            } catch (error) {
                console.warn(`Processor ${name} failed:`, error);
            }
        }

        return processedData;
    }

    /**
     * Subir archivo individual
     */
    async uploadFile(fileId) {
        const fileData = this.state.files.get(fileId);
        if (!fileData || fileData.status === 'uploading' || fileData.status === 'completed') {
            return;
        }

        try {
            fileData.status = 'uploading';
            fileData.startTime = Date.now();
            this.updateFileUI(fileData);

            // Callback de inicio
            if (this.config.onUploadStart) {
                this.config.onUploadStart(fileData);
            }

            let result;
            
            // Decidir método de upload según el tamaño
            if (fileData.file.size > this.config.chunkSize) {
                result = await this.uploadFileChunked(fileData);
            } else {
                result = await this.uploadFileSimple(fileData);
            }

            // Marcar como completado
            fileData.status = 'completed';
            fileData.progress = 100;
            fileData.result = result;
            fileData.endTime = Date.now();

            this.state.completedFiles++;
            this.updateFileUI(fileData);
            this.updateGlobalProgress();

            // Callback de completado
            if (this.config.onUploadComplete) {
                this.config.onUploadComplete(fileData, result);
            }

        } catch (error) {
            fileData.status = 'error';
            fileData.error = error.message;
            this.state.failedFiles++;

            // Intentar reintento si está configurado
            const retryCount = this.state.retryCount.get(fileId) || 0;
            if (retryCount < this.config.retryAttempts) {
                this.state.retryCount.set(fileId, retryCount + 1);
                console.log(`Retrying upload for ${fileData.name} (attempt ${retryCount + 1})`);
                
                await this.delay(this.config.retryDelay);
                return this.uploadFile(fileId);
            }

            this.updateFileUI(fileData);

            // Callback de error
            if (this.config.onUploadError) {
                this.config.onUploadError(fileData, error);
            }

            throw error;
        }
    }

    /**
     * Upload simple para archivos pequeños
     */
    async uploadFileSimple(fileData) {
        const formData = new FormData();
        formData.append('file', fileData.file);
        formData.append('metadata', JSON.stringify(fileData.metadata));
        formData.append('documentType', fileData.documentType || '');
        formData.append('context', this.config.context);
        formData.append('projectId', this.config.projectId || '');

        const xhr = new XMLHttpRequest();

        return new Promise((resolve, reject) => {
            // Progress tracking
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const progress = (e.loaded / e.total) * 100;
                    this.updateFileProgress(fileData.id, progress, e.loaded);
                }
            });

            // Success
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (error) {
                        reject(new Error('Invalid response format'));
                    }
                } else {
                    reject(new Error(`Upload failed with status ${xhr.status}`));
                }
            });

            // Error
            xhr.addEventListener('error', () => {
                reject(new Error('Network error during upload'));
            });

            // Timeout
            xhr.addEventListener('timeout', () => {
                reject(new Error('Upload timeout'));
            });

            // Configurar y enviar
            xhr.open('POST', this.config.uploadUrl);
            xhr.setRequestHeader('X-CSRFToken', this.getCSRFToken());
            xhr.timeout = 300000; // 5 minutos
            xhr.send(formData);
        });
    }

    /**
     * Upload chunked para archivos grandes
     */
    async uploadFileChunked(fileData) {
        const file = fileData.file;
        const chunkSize = this.config.chunkSize;
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        let uploadId = fileData.uploadId || this.generateUploadId();
        fileData.uploadId = uploadId;

        // Verificar si hay chunks ya subidos (resume)
        if (this.config.resumable) {
            const resumeInfo = await this.checkResumeInfo(uploadId);
            if (resumeInfo) {
                fileData.chunkIndex = resumeInfo.nextChunk;
                fileData.uploadedBytes = resumeInfo.uploadedBytes;
            }
        }

        // Subir chunks
        for (let chunkIndex = fileData.chunkIndex; chunkIndex < totalChunks; chunkIndex++) {
            const start = chunkIndex * chunkSize;
            const end = Math.min(start + chunkSize, file.size);
            const chunk = file.slice(start, end);

            try {
                await this.uploadChunk(fileData, chunk, chunkIndex, totalChunks);
                fileData.chunkIndex = chunkIndex + 1;
                fileData.uploadedBytes = end;
                
                // Guardar progreso para resume
                if (this.config.resumable) {
                    this.saveResumeInfo(uploadId, {
                        nextChunk: chunkIndex + 1,
                        uploadedBytes: end,
                        totalBytes: file.size
                    });
                }
            } catch (error) {
                throw new Error(`Failed to upload chunk ${chunkIndex}: ${error.message}`);
            }
        }

        // Finalizar upload chunked
        return this.finalizeChunkedUpload(fileData, uploadId);
    }

    /**
     * Subir chunk individual
     */
    async uploadChunk(fileData, chunk, chunkIndex, totalChunks) {
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('uploadId', fileData.uploadId);
        formData.append('chunkIndex', chunkIndex);
        formData.append('totalChunks', totalChunks);
        formData.append('fileName', fileData.name);

        const response = await fetch(this.config.chunkedUploadUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            },
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Actualizar progreso
        const progress = ((chunkIndex + 1) / totalChunks) * 100;
        this.updateFileProgress(fileData.id, progress, fileData.uploadedBytes);

        return response.json();
    }

    /**
     * Finalizar upload chunked
     */
    async finalizeChunkedUpload(fileData, uploadId) {
        const response = await fetch(this.config.chunkedUploadUrl + '/finalize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                uploadId: uploadId,
                fileName: fileData.name,
                metadata: fileData.metadata,
                documentType: fileData.documentType,
                context: this.config.context,
                projectId: this.config.projectId
            })
        });

        if (!response.ok) {
            throw new Error(`Finalization failed: ${response.status}`);
        }

        // Limpiar información de resume
        if (this.config.resumable) {
            this.clearResumeInfo(uploadId);
        }

        return response.json();
    }

    /**
     * Subir todos los archivos
     */
    async uploadAll() {
        if (this.state.isUploading) return;

        this.state.isUploading = true;
        this.updateInterface();

        const pendingFiles = Array.from(this.state.files.values())
            .filter(file => file.status === 'pending');

        if (pendingFiles.length === 0) {
            this.state.isUploading = false;
            return;
        }

        try {
            // Subir archivos en paralelo (con límite)
            const concurrentUploads = 3;
            const chunks = this.chunkArray(pendingFiles, concurrentUploads);

            for (const chunk of chunks) {
                const promises = chunk.map(file => this.uploadFile(file.id));
                await Promise.allSettled(promises);
            }

            // Callback cuando todos terminan
            if (this.config.onAllUploadsComplete) {
                this.config.onAllUploadsComplete(Array.from(this.state.files.values()));
            }

        } finally {
            this.state.isUploading = false;
            this.updateInterface();
        }
    }

    /**
     * Actualizar progreso de archivo
     */
    updateFileProgress(fileId, progress, uploadedBytes) {
        const fileData = this.state.files.get(fileId);
        if (!fileData) return;

        fileData.progress = progress;
        fileData.uploadedBytes = uploadedBytes;

        // Calcular velocidad
        if (fileData.startTime) {
            const elapsed = Date.now() - fileData.startTime;
            fileData.speed = uploadedBytes / (elapsed / 1000); // bytes/second
        }

        this.updateFileUI(fileData);
        this.updateGlobalProgress();

        // Callback
        if (this.config.onUploadProgress) {
            this.config.onUploadProgress(fileData);
        }
    }

    /**
     * Actualizar progreso global
     */
    updateGlobalProgress() {
        const totalBytes = this.state.totalBytes;
        let uploadedBytes = 0;

        this.state.files.forEach(file => {
            if (file.status === 'completed') {
                uploadedBytes += file.file.size;
            } else if (file.status === 'uploading') {
                uploadedBytes += file.uploadedBytes || 0;
            }
        });

        const progress = totalBytes > 0 ? (uploadedBytes / totalBytes) * 100 : 0;
        this.state.uploadedBytes = uploadedBytes;

        // Actualizar UI de progreso global
        const progressBar = this.progressContainer.querySelector('.progress-bar');
        const progressStats = this.progressContainer.querySelector('.progress-stats');
        const progressSpeed = this.progressContainer.querySelector('.progress-speed');

        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }

        if (progressStats) {
            progressStats.textContent = `${this.state.completedFiles} / ${this.state.totalFiles} archivos`;
        }

        if (progressSpeed) {
            const avgSpeed = this.calculateAverageSpeed();
            progressSpeed.textContent = avgSpeed > 0 ? this.formatSpeed(avgSpeed) : '0 KB/s';
        }
    }

    /**
     * Actualizar UI de archivo individual
     */
    updateFileUI(fileData) {
        const fileElement = this.queueFiles.querySelector(`[data-file-id="${fileData.id}"]`);
        if (!fileElement) return;

        const progressBar = fileElement.querySelector('.progress-bar');
        const progressText = fileElement.querySelector('.progress-text');
        const statusIcon = fileElement.querySelector('.file-status i');
        const uploadBtn = fileElement.querySelector('.btn-upload');

        // Actualizar barra de progreso
        if (progressBar) {
            progressBar.style.width = `${fileData.progress}%`;
            fileElement.querySelector('.progress').style.display = 
                fileData.status === 'uploading' ? 'block' : 'none';
        }

        // Actualizar texto de progreso
        if (progressText) {
            switch (fileData.status) {
                case 'pending':
                    progressText.textContent = 'Pendiente';
                    break;
                case 'uploading':
                    const speed = fileData.speed ? this.formatSpeed(fileData.speed) : '';
                    progressText.textContent = `${Math.round(fileData.progress)}% ${speed}`;
                    break;
                case 'completed':
                    progressText.textContent = 'Completado';
                    break;
                case 'error':
                    progressText.textContent = `Error: ${fileData.error}`;
                    break;
            }
        }

        // Actualizar icono de estado
        if (statusIcon) {
            statusIcon.className = this.getStatusIcon(fileData.status);
        }

        // Actualizar botón de upload
        if (uploadBtn) {
            uploadBtn.disabled = fileData.status !== 'pending';
        }
    }

    /**
     * Actualizar interfaz general
     */
    updateInterface() {
        // Mostrar/ocultar secciones
        this.queueContainer.style.display = this.state.files.size > 0 ? 'block' : 'none';
        this.progressContainer.style.display = this.state.isUploading ? 'block' : 'none';

        // Actualizar botones
        const uploadAllBtn = this.element.querySelector('.btn-upload-all');
        const pendingFiles = Array.from(this.state.files.values())
            .filter(file => file.status === 'pending');

        uploadAllBtn.disabled = pendingFiles.length === 0 || this.state.isUploading;

        // Renderizar archivos
        this.renderFileQueue();
    }

    /**
     * Renderizar cola de archivos
     */
    renderFileQueue() {
        this.queueFiles.innerHTML = '';

        this.state.files.forEach(fileData => {
            const fileElement = this.createFileElement(fileData);
            this.queueFiles.appendChild(fileElement);
        });
    }

    /**
     * Crear elemento de archivo
     */
    createFileElement(fileData) {
        const template = this.templates.get('fileItem');
        const documentTypeConfig = this.config.documentTypes[fileData.documentType];
        
        const templateData = {
            id: fileData.id,
            name: fileData.name,
            size: this.formatFileSize(fileData.size),
            type: fileData.extension.toUpperCase(),
            documentType: documentTypeConfig?.name || '',
            preview: this.generatePreview(fileData),
            requiresMetadata: !!documentTypeConfig?.required?.length,
            showDescription: documentTypeConfig?.required?.includes('description'),
            customFields: this.getCustomFields(fileData.documentType)
        };

        const element = document.createElement('div');
        element.innerHTML = this.renderTemplate(template, templateData);
        
        return element.firstElementChild;
    }

    /**
     * Generar preview del archivo
     */
    generatePreview(fileData) {
        if (fileData.thumbnail) {
            if (fileData.file.type.startsWith('image/')) {
                return this.renderTemplate(this.templates.get('imagePreview'), {
                    src: fileData.thumbnail,
                    name: fileData.name
                });
            } else if (fileData.file.type.startsWith('video/')) {
                return this.renderTemplate(this.templates.get('videoPreview'), {
                    src: fileData.thumbnail,
                    mimeType: fileData.file.type
                });
            }
        }

        if (fileData.file.type === 'application/pdf') {
            return this.renderTemplate(this.templates.get('documentPreview'), {
                icon: 'fas fa-file-pdf text-danger',
                pages: fileData.metadata?.pages || '?'
            });
        }

        return this.renderTemplate(this.templates.get('defaultPreview'), {
            icon: this.getFileIcon(fileData.extension)
        });
    }

    /**
     * Inicializar WebSocket para actualizaciones en tiempo real
     */
    async initializeWebSocket() {
        if (!this.config.enableWebSocket || typeof io === 'undefined') {
            return;
        }

        try {
            this.state.socket = io(this.config.webSocketUrl);

            this.state.socket.on('connect', () => {
                console.log('🔗 FileUpload WebSocket connected');
            });

            this.state.socket.on('uploadProgress', (data) => {
                this.handleWebSocketProgress(data);
            });

            this.state.socket.on('uploadComplete', (data) => {
                this.handleWebSocketComplete(data);
            });

            this.state.socket.on('uploadError', (data) => {
                this.handleWebSocketError(data);
            });

        } catch (error) {
            console.warn('Error initializing WebSocket:', error);
        }
    }

    /**
     * Métodos de utilidad
     */
    
    // Detectar tipo de documento específico del ecosistema
    detectDocumentType(file) {
        const fileName = file.name.toLowerCase();
        const extension = this.getFileExtension(file.name);

        // Palabras clave para diferentes tipos
        const keywords = {
            pitchDeck: ['pitch', 'deck', 'presentacion', 'presentation'],
            businessPlan: ['business', 'plan', 'negocio', 'modelo'],
            financials: ['balance', 'p&l', 'cash', 'flow', 'budget', 'financiero'],
            legal: ['legal', 'contrato', 'contract', 'terminos', 'terms'],
            media: ['logo', 'video', 'promo', 'marketing']
        };

        for (const [type, words] of Object.entries(keywords)) {
            if (words.some(word => fileName.includes(word))) {
                const typeConfig = this.config.documentTypes[type];
                if (typeConfig && typeConfig.allowedFormats.includes(extension)) {
                    return type;
                }
            }
        }

        return null;
    }

    // Obtener título contextual
    getContextTitle() {
        const titles = {
            entrepreneur: 'Subir Documentos del Proyecto',
            mentor: 'Compartir Recursos',
            admin: 'Gestión de Archivos',
            client: 'Materiales del Programa'
        };
        return titles[this.config.context] || 'Subir Archivos';
    }

    // Obtener descripción contextual
    getContextDescription() {
        const descriptions = {
            entrepreneur: 'Sube tu pitch deck, plan de negocio y documentos relacionados',
            mentor: 'Comparte materiales y recursos con tus emprendedores',
            admin: 'Administra archivos del sistema y documentos oficiales',
            client: 'Accede a reportes y materiales del programa'
        };
        return descriptions[this.config.context] || 'Selecciona los archivos que deseas subir';
    }

    // Obtener hint contextual
    getContextHint() {
        const hints = {
            entrepreneur: 'Tip: Nombra tus archivos de forma descriptiva (ej: "PitchDeck_StartupXYZ_v2.pdf")',
            mentor: 'Tip: Organiza tus recursos por categorías para facilitar el acceso',
            admin: 'Tip: Revisa los permisos antes de subir documentos sensibles',
            client: 'Tip: Los documentos se organizarán automáticamente por fecha y tipo'
        };
        return hints[this.config.context] || 'Arrastra archivos aquí o haz clic para seleccionar';
    }

    // Generar thumbnail de imagen
    async generateImageThumbnail(file, size = 150) {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();

            img.onload = () => {
                const { width, height } = img;
                const aspectRatio = width / height;

                let newWidth, newHeight;
                if (aspectRatio > 1) {
                    newWidth = size;
                    newHeight = size / aspectRatio;
                } else {
                    newWidth = size * aspectRatio;
                    newHeight = size;
                }

                canvas.width = newWidth;
                canvas.height = newHeight;

                ctx.drawImage(img, 0, 0, newWidth, newHeight);
                resolve(canvas.toDataURL());
            };

            img.onerror = () => resolve(null);
            img.src = URL.createObjectURL(file);
        });
    }

    // Generar thumbnail de video
    async generateVideoThumbnail(file) {
        return new Promise((resolve) => {
            const video = document.createElement('video');
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');

            video.addEventListener('loadeddata', () => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                resolve(canvas.toDataURL());
            });

            video.addEventListener('error', () => resolve(null));
            video.src = URL.createObjectURL(file);
            video.currentTime = 1; // Obtener frame del segundo 1
        });
    }

    // Obtener información de video
    async getVideoInfo(file) {
        return new Promise((resolve) => {
            const video = document.createElement('video');
            
            video.addEventListener('loadedmetadata', () => {
                resolve({
                    duration: video.duration,
                    width: video.videoWidth,
                    height: video.videoHeight
                });
            });

            video.addEventListener('error', () => resolve({}));
            video.src = URL.createObjectURL(file);
        });
    }

    // Obtener dimensiones de imagen
    async getImageDimensions(file) {
        return new Promise((resolve) => {
            const img = new Image();
            
            img.onload = () => {
                resolve({
                    width: img.naturalWidth,
                    height: img.naturalHeight
                });
            };

            img.onerror = () => resolve({ width: 0, height: 0 });
            img.src = URL.createObjectURL(file);
        });
    }

    // Métodos de formato y utilidad
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatSpeed(bytesPerSecond) {
        return this.formatFileSize(bytesPerSecond) + '/s';
    }

    getFileExtension(fileName) {
        return fileName.split('.').pop().toLowerCase();
    }

    getFileIcon(extension) {
        const icons = {
            pdf: 'fas fa-file-pdf text-danger',
            doc: 'fas fa-file-word text-primary',
            docx: 'fas fa-file-word text-primary',
            xls: 'fas fa-file-excel text-success',
            xlsx: 'fas fa-file-excel text-success',
            ppt: 'fas fa-file-powerpoint text-warning',
            pptx: 'fas fa-file-powerpoint text-warning',
            jpg: 'fas fa-file-image text-info',
            jpeg: 'fas fa-file-image text-info',
            png: 'fas fa-file-image text-info',
            gif: 'fas fa-file-image text-info',
            mp4: 'fas fa-file-video text-danger',
            mov: 'fas fa-file-video text-danger',
            mp3: 'fas fa-file-audio text-success',
            zip: 'fas fa-file-archive text-warning',
            txt: 'fas fa-file-alt text-secondary'
        };
        return icons[extension] || 'fas fa-file text-secondary';
    }

    getStatusIcon(status) {
        const icons = {
            pending: 'fas fa-clock text-warning',
            uploading: 'fas fa-spinner fa-spin text-primary',
            completed: 'fas fa-check-circle text-success',
            error: 'fas fa-exclamation-circle text-danger'
        };
        return icons[status] || 'fas fa-question-circle text-secondary';
    }

    getAllowedExtensions() {
        const extensions = [];
        Object.values(this.config.allowedTypes).forEach(typeExtensions => {
            extensions.push(...typeExtensions);
        });
        return [...new Set(extensions)];
    }

    getAllowedTypesText() {
        const types = Object.keys(this.config.allowedTypes);
        return types.map(type => type.charAt(0).toUpperCase() + type.slice(1)).join(', ');
    }

    getAcceptAttribute() {
        const extensions = this.getAllowedExtensions();
        return extensions.map(ext => `.${ext}`).join(',');
    }

    renderTemplate(template, data) {
        return template.replace(/\{\{(.*?)\}\}/g, (match, key) => {
            const keys = key.trim().split('.');
            let value = data;
            
            for (const k of keys) {
                value = value?.[k];
            }
            
            return value || '';
        }).replace(/\{\{#if (.*?)\}\}(.*?)\{\{\/if\}\}/gs, (match, condition, content) => {
            const value = data[condition.trim()];
            return value ? content : '';
        }).replace(/\{\{#each (.*?)\}\}(.*?)\{\{\/each\}\}/gs, (match, arrayName, itemTemplate) => {
            const array = data[arrayName.trim()] || [];
            return array.map(item => 
                itemTemplate.replace(/\{\{(.*?)\}\}/g, (match, key) => item[key.trim()] || '')
            ).join('');
        });
    }

    generateFileId() {
        return 'file_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    generateUploadId() {
        return 'upload_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    getCSRFToken() {
        return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    chunkArray(array, size) {
        const chunks = [];
        for (let i = 0; i < array.length; i += size) {
            chunks.push(array.slice(i, i + size));
        }
        return chunks;
    }

    // Event handlers
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight() {
        this.dropZone.classList.add('drag-active');
        this.state.dragActive = true;
    }

    unhighlight() {
        this.dropZone.classList.remove('drag-active');
        this.state.dragActive = false;
    }

    handleDrop(e) {
        const files = Array.from(e.dataTransfer.files);
        this.handleFileSelection(files);
    }

    // API pública
    removeFile(fileId) {
        const fileData = this.state.files.get(fileId);
        if (!fileData) return;

        // No permitir eliminar archivos en proceso de subida
        if (fileData.status === 'uploading') {
            this.showError('No se puede eliminar un archivo que se está subiendo');
            return;
        }

        this.state.files.delete(fileId);
        this.state.totalFiles--;
        this.state.totalBytes -= fileData.file.size;

        // Callback
        if (this.config.onFileRemove) {
            this.config.onFileRemove(fileData);
        }

        this.updateInterface();
    }

    clearAll() {
        // Solo limpiar archivos que no estén subiendo
        const uploadingFiles = Array.from(this.state.files.values())
            .filter(file => file.status === 'uploading');

        if (uploadingFiles.length > 0) {
            if (!confirm('Hay archivos subiendo. ¿Estás seguro de que quieres cancelar?')) {
                return;
            }
        }

        this.state.files.clear();
        this.state.totalFiles = 0;
        this.state.completedFiles = 0;
        this.state.failedFiles = 0;
        this.state.totalBytes = 0;
        this.state.uploadedBytes = 0;

        this.updateInterface();
    }

    updateFileMetadata(fileId, key, value) {
        const fileData = this.state.files.get(fileId);
        if (fileData) {
            fileData.metadata[key] = value;
        }
    }

    getFiles() {
        return Array.from(this.state.files.values());
    }

    getCompletedFiles() {
        return Array.from(this.state.files.values())
            .filter(file => file.status === 'completed');
    }

    showError(message) {
        // Integrar con sistema de notificaciones
        if (window.notifications) {
            window.notifications.error('Error de Subida', message);
        } else {
            alert(message);
        }
    }

    showSuccess(message) {
        if (window.notifications) {
            window.notifications.success('Subida Exitosa', message);
        }
    }

    // Resume functionality
    saveResumeInfo(uploadId, info) {
        localStorage.setItem(`upload_resume_${uploadId}`, JSON.stringify(info));
    }

    async checkResumeInfo(uploadId) {
        const stored = localStorage.getItem(`upload_resume_${uploadId}`);
        if (!stored) return null;

        try {
            const info = JSON.parse(stored);
            
            // Verificar con el servidor si el upload parcial existe
            const response = await fetch(`${this.config.resumeUploadUrl}/${uploadId}`, {
                method: 'GET',
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });

            if (response.ok) {
                const serverInfo = await response.json();
                return serverInfo;
            }
        } catch (error) {
            console.warn('Error checking resume info:', error);
        }

        return null;
    }

    clearResumeInfo(uploadId) {
        localStorage.removeItem(`upload_resume_${uploadId}`);
    }

    calculateAverageSpeed() {
        let totalSpeed = 0;
        let activeUploads = 0;

        this.state.files.forEach(file => {
            if (file.status === 'uploading' && file.speed) {
                totalSpeed += file.speed;
                activeUploads++;
            }
        });

        return activeUploads > 0 ? totalSpeed / activeUploads : 0;
    }

    applyTheme() {
        this.element.dataset.theme = this.config.theme;
    }

    handleResize() {
        // Ajustar interfaz para diferentes tamaños de pantalla
        const isMobile = window.innerWidth < 768;
        this.element.classList.toggle('mobile-view', isMobile);
    }

    getCustomFields(documentType) {
        const docConfig = this.config.documentTypes[documentType];
        if (!docConfig || !docConfig.customFields) return [];
        
        return docConfig.customFields;
    }

    /**
     * Cleanup
     */
    destroy() {
        // Cancelar uploads activos
        this.state.files.forEach(file => {
            if (file.status === 'uploading') {
                // Cancelar XMLHttpRequest si existe
                if (file.xhr) {
                    file.xhr.abort();
                }
            }
        });

        // Desconectar WebSocket
        if (this.state.socket) {
            this.state.socket.disconnect();
        }

        // Remover event listeners
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });

        // Desconectar resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }

        console.log('🧹 EcoFileUpload destroyed');
    }
}

// CSS personalizado para el componente
const fileUploadCSS = `
    .eco-file-upload {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        max-width: 100%;
    }
    
    .upload-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .upload-title {
        margin-bottom: 0.5rem;
        color: #333;
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    .upload-description {
        color: #666;
        margin-bottom: 0;
    }
    
    .upload-dropzone {
        border: 2px dashed #ddd;
        border-radius: 12px;
        padding: 3rem 2rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        background: #fafafa;
        outline: none;
    }
    
    .upload-dropzone:hover,
    .upload-dropzone:focus {
        border-color: #007bff;
        background: #f0f8ff;
    }
    
    .upload-dropzone.drag-active {
        border-color: #28a745;
        background: #f0fff0;
        transform: scale(1.02);
    }
    
    .dropzone-content {
        pointer-events: none;
    }
    
    .dropzone-icon {
        font-size: 3rem;
        color: #007bff;
        margin-bottom: 1rem;
    }
    
    .dropzone-text h4 {
        margin-bottom: 0.5rem;
        color: #333;
        font-weight: 500;
    }
    
    .dropzone-hint {
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }
    
    .btn-select-files {
        pointer-events: all;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }
    
    .upload-constraints {
        margin-top: 1.5rem;
        padding: 1rem;
        background: #f8f9fa;
        border-radius: 8px;
    }
    
    .constraints-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
    }
    
    .constraint-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        color: #666;
    }
    
    .constraint-item i {
        color: #007bff;
        width: 16px;
    }
    
    .upload-queue {
        margin-top: 2rem;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        overflow: hidden;
    }
    
    .queue-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 1.5rem;
        background: #f8f9fa;
        border-bottom: 1px solid #e9ecef;
    }
    
    .queue-header h4 {
        margin: 0;
        font-size: 1.1rem;
    }
    
    .queue-actions {
        display: flex;
        gap: 0.5rem;
    }
    
    .queue-files {
        max-height: 400px;
        overflow-y: auto;
    }
    
    .file-item {
        display: grid;
        grid-template-columns: 80px 1fr auto auto auto;
        gap: 1rem;
        padding: 1rem 1.5rem;
        border-bottom: 1px solid #f0f0f0;
        align-items: center;
    }
    
    .file-item:last-child {
        border-bottom: none;
    }
    
    .file-preview {
        width: 64px;
        height: 64px;
        border-radius: 6px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
        border: 1px solid #e9ecef;
    }
    
    .preview-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .preview-video {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .video-overlay {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: white;
        font-size: 1.5rem;
    }
    
    .document-preview,
    .default-preview {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        font-size: 1.5rem;
    }
    
    .document-pages {
        font-size: 0.7rem;
        color: #666;
        margin-top: 0.25rem;
    }
    
    .file-info {
        min-width: 0;
    }
    
    .file-name {
        font-weight: 500;
        color: #333;
        margin-bottom: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .file-meta {
        display: flex;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #666;
        flex-wrap: wrap;
    }
    
    .file-document-type {
        background: #e7f3ff;
        color: #0066cc;
        padding: 0.125rem 0.375rem;
        border-radius: 3px;
        font-size: 0.7rem;
        font-weight: 500;
    }
    
    .file-metadata {
        margin-top: 0.5rem;
        display: grid;
        gap: 0.5rem;
    }
    
    .file-metadata input,
    .file-metadata textarea {
        font-size: 0.8rem;
    }
    
    .file-progress {
        min-width: 120px;
    }
    
    .file-progress .progress {
        height: 4px;
        margin-bottom: 0.25rem;
    }
    
    .progress-text {
        font-size: 0.8rem;
        color: #666;
        text-align: center;
    }
    
    .file-actions {
        display: flex;
        gap: 0.25rem;
    }
    
    .file-status {
        width: 24px;
        text-align: center;
    }
    
    .upload-progress {
        margin-top: 1.5rem;
        padding: 1.5rem;
        background: #f8f9fa;
        border-radius: 8px;
    }
    
    .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .progress-header h4 {
        margin: 0;
        font-size: 1.1rem;
    }
    
    .progress-stats {
        font-size: 0.9rem;
        color: #666;
    }
    
    .upload-progress .progress {
        height: 8px;
        margin-bottom: 0.5rem;
    }
    
    .progress-details {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #666;
    }
    
    /* Tema oscuro */
    .eco-file-upload[data-theme="dark"] {
        color: #e9ecef;
    }
    
    .eco-file-upload[data-theme="dark"] .upload-dropzone {
        background: #2c3e50;
        border-color: #495057;
        color: #e9ecef;
    }
    
    .eco-file-upload[data-theme="dark"] .upload-dropzone:hover {
        background: #34495e;
        border-color: #007bff;
    }
    
    .eco-file-upload[data-theme="dark"] .upload-constraints {
        background: #343a40;
    }
    
    .eco-file-upload[data-theme="dark"] .queue-header {
        background: #343a40;
        border-color: #495057;
    }
    
    .eco-file-upload[data-theme="dark"] .file-item {
        border-color: #495057;
    }
    
    .eco-file-upload[data-theme="dark"] .file-preview {
        background: #495057;
        border-color: #6c757d;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .eco-file-upload.mobile-view .file-item {
            grid-template-columns: 60px 1fr auto;
            gap: 0.75rem;
        }
        
        .eco-file-upload.mobile-view .file-progress,
        .eco-file-upload.mobile-view .file-status {
            display: none;
        }
        
        .eco-file-upload.mobile-view .file-actions {
            flex-direction: column;
            gap: 0.125rem;
        }
        
        .eco-file-upload.mobile-view .constraints-grid {
            grid-template-columns: 1fr;
        }
        
        .eco-file-upload.mobile-view .queue-header {
            flex-direction: column;
            gap: 0.75rem;
            align-items: stretch;
        }
        
        .eco-file-upload.mobile-view .progress-details {
            flex-direction: column;
            gap: 0.25rem;
        }
    }
    
    /* Animaciones */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .file-item {
        animation: fadeIn 0.3s ease;
    }
    
    .upload-progress {
        animation: fadeIn 0.3s ease;
    }
    
    /* Estados de error */
    .file-item.error {
        background: #fff5f5;
        border-left: 3px solid #dc3545;
    }
    
    .file-item.completed {
        background: #f0fff4;
        border-left: 3px solid #28a745;
    }
    
    .file-item.uploading {
        background: #f0f8ff;
        border-left: 3px solid #007bff;
    }
`;

// Inyectar CSS
if (!document.getElementById('eco-file-upload-styles')) {
    const style = document.createElement('style');
    style.id = 'eco-file-upload-styles';
    style.textContent = fileUploadCSS;
    document.head.appendChild(style);
}

// Registrar en elemento para fácil acceso
Object.defineProperty(EcoFileUpload.prototype, 'register', {
    value: function() {
        this.element.ecoFileUpload = this;
    }
});

// Auto-registro
const originalInit = EcoFileUpload.prototype.init;
EcoFileUpload.prototype.init = function() {
    const result = originalInit.call(this);
    this.register();
    return result;
};

// Factory methods
EcoFileUpload.createEntrepreneurUpload = (element, options = {}) => {
    return new EcoFileUpload(element, {
        context: 'entrepreneur',
        documentTypes: {
            pitchDeck: { name: 'Pitch Deck', allowedFormats: ['pdf', 'ppt', 'pptx'], required: ['title'] },
            businessPlan: { name: 'Plan de Negocio', allowedFormats: ['pdf', 'doc', 'docx'], required: ['title', 'version'] },
            financials: { name: 'Financieros', allowedFormats: ['pdf', 'xls', 'xlsx'], required: ['period'] }
        },
        maxFiles: 5,
        ...options
    });
};

EcoFileUpload.createMentorUpload = (element, options = {}) => {
    return new EcoFileUpload(element, {
        context: 'mentor',
        maxFiles: 10,
        allowedTypes: {
            documents: ['pdf', 'doc', 'docx', 'ppt', 'pptx'],
            media: ['jpg', 'jpeg', 'png', 'mp4', 'mov']
        },
        ...options
    });
};

EcoFileUpload.createAdminUpload = (element, options = {}) => {
    return new EcoFileUpload(element, {
        context: 'admin',
        maxFiles: 20,
        maxFileSize: 500 * 1024 * 1024, // 500MB
        enableVirusScan: true,
        ...options
    });
};

// Exportar
window.EcoFileUpload = EcoFileUpload;
export default EcoFileUpload;