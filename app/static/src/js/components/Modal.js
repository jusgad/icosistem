/**
 * Modal Component
 * Componente modal avanzado y reutilizable para el ecosistema de emprendimiento
 * Soporta múltiples tipos, animaciones, validación y accesibilidad completa
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class Modal {
  constructor (options = {}) {
    this.config = {
      // Configuración básica
      id: options.id || this.generateId(),
      title: options.title || '',
      content: options.content || '',
      type: options.type || 'default', // default, confirm, alert, form, custom
      size: options.size || 'md', // sm, md, lg, xl, fullscreen

      // Botones
      showClose: options.showClose !== false,
      showCancel: options.showCancel !== false,
      showConfirm: options.showConfirm !== false,

      // Textos de botones
      cancelText: options.cancelText || 'Cancelar',
      confirmText: options.confirmText || 'Confirmar',
      closeText: options.closeText || 'Cerrar',

      // Comportamiento
      backdrop: options.backdrop !== false, // true, false, 'static'
      keyboard: options.keyboard !== false,
      focus: options.focus !== false,
      closable: options.closable !== false,

      // Animaciones
      animation: options.animation !== false,
      animationDuration: options.animationDuration || 300,
      animationType: options.animationType || 'fade', // fade, slide, zoom, flip

      // Estilos
      headerClass: options.headerClass || '',
      bodyClass: options.bodyClass || '',
      footerClass: options.footerClass || '',
      modalClass: options.modalClass || '',

      // Callbacks
      onShow: options.onShow || null,
      onShown: options.onShown || null,
      onHide: options.onHide || null,
      onHidden: options.onHidden || null,
      onConfirm: options.onConfirm || null,
      onCancel: options.onCancel || null,

      // Formularios
      form: options.form || null,
      validation: options.validation || {},
      autoFocus: options.autoFocus || true,

      // Contenido dinámico
      url: options.url || null,
      ajaxOptions: options.ajaxOptions || {},

      // Accesibilidad
      ariaLabel: options.ariaLabel || '',
      ariaDescribedBy: options.ariaDescribedBy || '',

      // Responsive
      fullscreenBreakpoint: options.fullscreenBreakpoint || 'sm',

      // Stack management
      zIndexBase: options.zIndexBase || 1050,

      ...options
    }

    this.state = {
      isVisible: false,
      isAnimating: false,
      isLoading: false,
      formData: {},
      validationErrors: {},
      element: null,
      backdrop: null,
      previousActiveElement: null,
      stackIndex: 0
    }

    this.eventListeners = []
    this.validators = {}
    this.animations = {}

    this.init()
  }

  /**
     * Inicialización del modal
     */
  init () {
    this.setupAnimations()
    this.setupValidators()
    this.registerGlobalListeners()

    // Si hay contenido inicial, crear el modal
    if (this.config.content || this.config.url) {
      this.createElement()
    }
  }

  /**
     * Configurar animaciones personalizadas
     */
  setupAnimations () {
    this.animations = {
      fade: {
        show: {
          modal: [
            { opacity: '0', transform: 'scale(0.8)' },
            { opacity: '1', transform: 'scale(1)' }
          ],
          backdrop: [
            { opacity: '0' },
            { opacity: '0.5' }
          ]
        },
        hide: {
          modal: [
            { opacity: '1', transform: 'scale(1)' },
            { opacity: '0', transform: 'scale(0.8)' }
          ],
          backdrop: [
            { opacity: '0.5' },
            { opacity: '0' }
          ]
        }
      },
      slide: {
        show: {
          modal: [
            { transform: 'translateY(-100px)', opacity: '0' },
            { transform: 'translateY(0)', opacity: '1' }
          ],
          backdrop: [
            { opacity: '0' },
            { opacity: '0.5' }
          ]
        },
        hide: {
          modal: [
            { transform: 'translateY(0)', opacity: '1' },
            { transform: 'translateY(-100px)', opacity: '0' }
          ],
          backdrop: [
            { opacity: '0.5' },
            { opacity: '0' }
          ]
        }
      },
      zoom: {
        show: {
          modal: [
            { transform: 'scale(0.3)', opacity: '0' },
            { transform: 'scale(1)', opacity: '1' }
          ],
          backdrop: [
            { opacity: '0' },
            { opacity: '0.5' }
          ]
        },
        hide: {
          modal: [
            { transform: 'scale(1)', opacity: '1' },
            { transform: 'scale(0.3)', opacity: '0' }
          ],
          backdrop: [
            { opacity: '0.5' },
            { opacity: '0' }
          ]
        }
      },
      flip: {
        show: {
          modal: [
            { transform: 'rotateX(-90deg)', opacity: '0' },
            { transform: 'rotateX(0)', opacity: '1' }
          ],
          backdrop: [
            { opacity: '0' },
            { opacity: '0.5' }
          ]
        },
        hide: {
          modal: [
            { transform: 'rotateX(0)', opacity: '1' },
            { transform: 'rotateX(-90deg)', opacity: '0' }
          ],
          backdrop: [
            { opacity: '0.5' },
            { opacity: '0' }
          ]
        }
      }
    }
  }

  /**
     * Configurar validadores de formulario
     */
  setupValidators () {
    this.validators = {
      required: (value, field) => {
        const isEmpty = !value || (typeof value === 'string' && value.trim() === '')
        return isEmpty ? `${field.label || field.name} es requerido` : null
      },

      email: (value) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return value && !emailRegex.test(value) ? 'Email inválido' : null
      },

      minLength: (value, field) => {
        const min = field.minLength || 0
        return value && value.length < min ? `Mínimo ${min} caracteres` : null
      },

      maxLength: (value, field) => {
        const max = field.maxLength || Infinity
        return value && value.length > max ? `Máximo ${max} caracteres` : null
      },

      pattern: (value, field) => {
        const pattern = new RegExp(field.pattern)
        return value && !pattern.test(value) ? field.patternMessage || 'Formato inválido' : null
      },

      custom: (value, field) => {
        return field.validator ? field.validator(value, field) : null
      }
    }
  }

  /**
     * Registrar listeners globales
     */
  registerGlobalListeners () {
    // Escape key
    this.addGlobalListener(document, 'keydown', (e) => {
      if (e.key === 'Escape' && this.config.keyboard && this.state.isVisible) {
        this.hide()
      }
    })

    // Resize handler
    this.addGlobalListener(window, 'resize', this.debounce(() => {
      if (this.state.isVisible) {
        this.adjustPosition()
      }
    }, 150))
  }

  /**
     * Crear elemento del modal
     */
  createElement () {
    if (this.state.element) {
      this.state.element.remove()
    }

    this.state.element = document.createElement('div')
    this.state.element.className = this.getModalClasses()
    this.state.element.id = this.config.id
    this.state.element.setAttribute('tabindex', '-1')
    this.state.element.setAttribute('role', 'dialog')
    this.state.element.setAttribute('aria-modal', 'true')

    if (this.config.ariaLabel) {
      this.state.element.setAttribute('aria-label', this.config.ariaLabel)
    }

    if (this.config.ariaDescribedBy) {
      this.state.element.setAttribute('aria-describedby', this.config.ariaDescribedBy)
    }

    this.state.element.innerHTML = this.getModalHTML()

    // Añadir al DOM pero mantener oculto
    document.body.appendChild(this.state.element)

    // Setup event listeners
    this.setupModalListeners()

    // Cargar contenido si es necesario
    if (this.config.url) {
      this.loadContent()
    }

    return this.state.element
  }

  /**
     * Obtener clases CSS del modal
     */
  getModalClasses () {
    const classes = ['modal', 'ecosistema-modal']

    if (this.config.animation) {
      classes.push('modal-animated')
      classes.push(`modal-${this.config.animationType}`)
    }

    if (this.config.modalClass) {
      classes.push(this.config.modalClass)
    }

    return classes.join(' ')
  }

  /**
     * Generar HTML del modal
     */
  getModalHTML () {
    const sizeClass = this.getSizeClass()
    const headerContent = this.getHeaderContent()
    const bodyContent = this.getBodyContent()
    const footerContent = this.getFooterContent()

    return `
            <div class="modal-dialog ${sizeClass}" role="document">
                <div class="modal-content">
                    ${headerContent}
                    ${bodyContent}
                    ${footerContent}
                </div>
            </div>
        `
  }

  /**
     * Obtener clase de tamaño
     */
  getSizeClass () {
    const sizeMap = {
      sm: 'modal-sm',
      md: '',
      lg: 'modal-lg',
      xl: 'modal-xl',
      fullscreen: 'modal-fullscreen'
    }

    let sizeClass = sizeMap[this.config.size] || ''

    // Responsive fullscreen
    if (this.config.fullscreenBreakpoint && this.config.fullscreenBreakpoint !== 'never') {
      sizeClass += ` modal-fullscreen-${this.config.fullscreenBreakpoint}-down`
    }

    return sizeClass
  }

  /**
     * Generar contenido del header
     */
  getHeaderContent () {
    if (!this.config.title && !this.config.showClose) {
      return ''
    }

    const closeButton = this.config.showClose
      ? `
            <button type="button" class="btn-close modal-close" aria-label="${this.config.closeText}"></button>
        `
      : ''

    return `
            <div class="modal-header ${this.config.headerClass}">
                <h5 class="modal-title">${this.config.title}</h5>
                ${closeButton}
            </div>
        `
  }

  /**
     * Generar contenido del body
     */
  getBodyContent () {
    let content = this.config.content

    // Si hay un formulario, generar el HTML del formulario
    if (this.config.form) {
      content = this.generateFormHTML()
    }

    // Loading state
    const loadingHTML = `
            <div class="modal-loading text-center p-4" style="display: none;">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <div class="mt-2">Cargando...</div>
            </div>
        `

    return `
            <div class="modal-body ${this.config.bodyClass}">
                ${loadingHTML}
                <div class="modal-content-wrapper">
                    ${content}
                </div>
            </div>
        `
  }

  /**
     * Generar HTML del formulario
     */
  generateFormHTML () {
    if (!this.config.form || !this.config.form.fields) {
      return ''
    }

    let formHTML = '<form class="modal-form" novalidate>'

    this.config.form.fields.forEach(field => {
      formHTML += this.generateFieldHTML(field)
    })

    formHTML += '</form>'
    return formHTML
  }

  /**
     * Generar HTML de campo de formulario
     */
  generateFieldHTML (field) {
    const fieldId = `${this.config.id}_${field.name}`
    const required = field.required ? 'required' : ''
    const value = this.state.formData[field.name] || field.value || ''

    let fieldHTML = `
            <div class="mb-3 form-field" data-field="${field.name}">
                <label for="${fieldId}" class="form-label">
                    ${field.label}
                    ${field.required ? '<span class="text-danger">*</span>' : ''}
                </label>
        `

    switch (field.type) {
      case 'text':
      case 'email':
      case 'password':
      case 'number':
      case 'tel':
      case 'url':
        fieldHTML += `
                    <input type="${field.type}" 
                           class="form-control" 
                           id="${fieldId}" 
                           name="${field.name}"
                           value="${value}"
                           placeholder="${field.placeholder || ''}"
                           ${required}
                           ${field.readonly ? 'readonly' : ''}
                           ${field.disabled ? 'disabled' : ''}>
                `
        break

      case 'textarea':
        fieldHTML += `
                    <textarea class="form-control" 
                              id="${fieldId}" 
                              name="${field.name}"
                              rows="${field.rows || 3}"
                              placeholder="${field.placeholder || ''}"
                              ${required}
                              ${field.readonly ? 'readonly' : ''}
                              ${field.disabled ? 'disabled' : ''}>${value}</textarea>
                `
        break

      case 'select':
        fieldHTML += `<select class="form-select" id="${fieldId}" name="${field.name}" ${required}>`
        if (field.placeholder) {
          fieldHTML += `<option value="">${field.placeholder}</option>`
        }
        (field.options || []).forEach(option => {
          const selected = option.value === value ? 'selected' : ''
          fieldHTML += `<option value="${option.value}" ${selected}>${option.label}</option>`
        })
        fieldHTML += '</select>'
        break

      case 'checkbox':
        const checked = value ? 'checked' : ''
        fieldHTML += `
                    <div class="form-check">
                        <input class="form-check-input" 
                               type="checkbox" 
                               id="${fieldId}" 
                               name="${field.name}"
                               value="1"
                               ${checked}
                               ${field.disabled ? 'disabled' : ''}>
                        <label class="form-check-label" for="${fieldId}">
                            ${field.checkboxLabel || field.label}
                        </label>
                    </div>
                `
        break

      case 'radio':
        (field.options || []).forEach((option, index) => {
          const radioId = `${fieldId}_${index}`
          const checked = option.value === value ? 'checked' : ''
          fieldHTML += `
                        <div class="form-check">
                            <input class="form-check-input" 
                                   type="radio" 
                                   id="${radioId}" 
                                   name="${field.name}"
                                   value="${option.value}"
                                   ${checked}
                                   ${field.disabled ? 'disabled' : ''}>
                            <label class="form-check-label" for="${radioId}">
                                ${option.label}
                            </label>
                        </div>
                    `
        })
        break

      case 'file':
        fieldHTML += `
                    <input type="file" 
                           class="form-control" 
                           id="${fieldId}" 
                           name="${field.name}"
                           ${field.multiple ? 'multiple' : ''}
                           ${field.accept ? `accept="${field.accept}"` : ''}
                           ${required}
                           ${field.disabled ? 'disabled' : ''}>
                `
        break

      case 'hidden':
        fieldHTML += `
                    <input type="hidden" 
                           id="${fieldId}" 
                           name="${field.name}"
                           value="${value}">
                `
        break
    }

    // Help text
    if (field.help) {
      fieldHTML += `<div class="form-text">${field.help}</div>`
    }

    // Error container
    fieldHTML += '<div class="invalid-feedback"></div>'
    fieldHTML += '</div>'

    return fieldHTML
  }

  /**
     * Generar contenido del footer
     */
  getFooterContent () {
    if (this.config.type === 'alert' && !this.config.showCancel && !this.config.showConfirm) {
      return `
                <div class="modal-footer ${this.config.footerClass}">
                    <button type="button" class="btn btn-primary modal-close">${this.config.closeText}</button>
                </div>
            `
    }

    if (!this.config.showCancel && !this.config.showConfirm) {
      return ''
    }

    const cancelButton = this.config.showCancel
      ? `
            <button type="button" class="btn btn-secondary modal-cancel">${this.config.cancelText}</button>
        `
      : ''

    const confirmButton = this.config.showConfirm
      ? `
            <button type="button" class="btn btn-primary modal-confirm">${this.config.confirmText}</button>
        `
      : ''

    return `
            <div class="modal-footer ${this.config.footerClass}">
                ${cancelButton}
                ${confirmButton}
            </div>
        `
  }

  /**
     * Configurar event listeners del modal
     */
  setupModalListeners () {
    const modal = this.state.element

    // Botón cerrar
    modal.querySelectorAll('.modal-close').forEach(btn => {
      btn.addEventListener('click', () => this.hide())
    })

    // Botón cancelar
    modal.querySelectorAll('.modal-cancel').forEach(btn => {
      btn.addEventListener('click', () => this.cancel())
    })

    // Botón confirmar
    modal.querySelectorAll('.modal-confirm').forEach(btn => {
      btn.addEventListener('click', () => this.confirm())
    })

    // Click en backdrop
    if (this.config.backdrop !== 'static') {
      modal.addEventListener('click', (e) => {
        if (e.target === modal && this.config.backdrop) {
          this.hide()
        }
      })
    }

    // Formulario
    const form = modal.querySelector('.modal-form')
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault()
        this.confirm()
      })

      // Validación en tiempo real
      form.addEventListener('input', (e) => {
        this.validateField(e.target)
      })

      form.addEventListener('blur', (e) => {
        this.validateField(e.target)
      }, true)
    }

    // Navegación por teclado
    modal.addEventListener('keydown', (e) => {
      this.handleKeydown(e)
    })
  }

  /**
     * Mostrar modal
     */
  async show () {
    if (this.state.isVisible || this.state.isAnimating) {
      return this
    }

    // Crear elemento si no existe
    if (!this.state.element) {
      this.createElement()
    }

    // Callback antes de mostrar
    if (this.config.onShow) {
      const result = await this.config.onShow(this)
      if (result === false) return this
    }

    this.state.isAnimating = true
    this.state.stackIndex = Modal.getStackIndex()

    // Guardar elemento activo
    this.state.previousActiveElement = document.activeElement

    // Crear backdrop
    this.createBackdrop()

    // Añadir clase al body
    document.body.classList.add('modal-open')

    // Configurar z-index
    const zIndex = this.config.zIndexBase + (this.state.stackIndex * 10)
    this.state.element.style.zIndex = zIndex
    if (this.state.backdrop) {
      this.state.backdrop.style.zIndex = zIndex - 1
    }

    // Mostrar modal
    this.state.element.style.display = 'block'
    this.state.element.classList.add('show')

    // Aplicar animaciones
    if (this.config.animation) {
      await this.animateShow()
    }

    this.state.isVisible = true
    this.state.isAnimating = false

    // Focus management
    if (this.config.focus) {
      this.manageFocus()
    }

    // Ajustar posición
    this.adjustPosition()

    // Callback después de mostrar
    if (this.config.onShown) {
      await this.config.onShown(this)
    }

    return this
  }

  /**
     * Ocultar modal
     */
  async hide () {
    if (!this.state.isVisible || this.state.isAnimating) {
      return this
    }

    // Callback antes de ocultar
    if (this.config.onHide) {
      const result = await this.config.onHide(this)
      if (result === false) return this
    }

    this.state.isAnimating = true

    // Aplicar animaciones
    if (this.config.animation) {
      await this.animateHide()
    }

    // Ocultar elementos
    this.state.element.style.display = 'none'
    this.state.element.classList.remove('show')

    // Remover backdrop
    if (this.state.backdrop) {
      this.state.backdrop.remove()
      this.state.backdrop = null
    }

    // Remover clase del body si no hay más modales
    if (Modal.getActiveModals().length <= 1) {
      document.body.classList.remove('modal-open')
    }

    // Restaurar focus
    if (this.state.previousActiveElement) {
      this.state.previousActiveElement.focus()
    }

    this.state.isVisible = false
    this.state.isAnimating = false

    // Callback después de ocultar
    if (this.config.onHidden) {
      await this.config.onHidden(this)
    }

    return this
  }

  /**
     * Crear backdrop
     */
  createBackdrop () {
    if (!this.config.backdrop) return

    this.state.backdrop = document.createElement('div')
    this.state.backdrop.className = 'modal-backdrop fade'
    this.state.backdrop.style.zIndex = this.config.zIndexBase + (this.state.stackIndex * 10) - 1

    document.body.appendChild(this.state.backdrop)

    // Force reflow para activar transición
    this.state.backdrop.offsetHeight
    this.state.backdrop.classList.add('show')
  }

  /**
     * Animar mostrar
     */
  async animateShow () {
    const animations = this.animations[this.config.animationType]
    if (!animations) return

    const modalDialog = this.state.element.querySelector('.modal-dialog')

    const promises = []

    // Animar modal
    if (animations.show.modal) {
      promises.push(
        modalDialog.animate(animations.show.modal, {
          duration: this.config.animationDuration,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          fill: 'forwards'
        }).finished
      )
    }

    // Animar backdrop
    if (animations.show.backdrop && this.state.backdrop) {
      promises.push(
        this.state.backdrop.animate(animations.show.backdrop, {
          duration: this.config.animationDuration,
          easing: 'ease-out',
          fill: 'forwards'
        }).finished
      )
    }

    await Promise.all(promises)
  }

  /**
     * Animar ocultar
     */
  async animateHide () {
    const animations = this.animations[this.config.animationType]
    if (!animations) return

    const modalDialog = this.state.element.querySelector('.modal-dialog')

    const promises = []

    // Animar modal
    if (animations.hide.modal) {
      promises.push(
        modalDialog.animate(animations.hide.modal, {
          duration: this.config.animationDuration,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          fill: 'forwards'
        }).finished
      )
    }

    // Animar backdrop
    if (animations.hide.backdrop && this.state.backdrop) {
      promises.push(
        this.state.backdrop.animate(animations.hide.backdrop, {
          duration: this.config.animationDuration,
          easing: 'ease-in',
          fill: 'forwards'
        }).finished
      )
    }

    await Promise.all(promises)
  }

  /**
     * Confirmar modal
     */
  async confirm () {
    // Validar formulario si existe
    if (this.config.form && !this.validateForm()) {
      return false
    }

    // Obtener datos del formulario
    const formData = this.getFormData()

    // Callback de confirmación
    if (this.config.onConfirm) {
      const result = await this.config.onConfirm(formData, this)
      if (result === false) return false
    }

    await this.hide()
    return true
  }

  /**
     * Cancelar modal
     */
  async cancel () {
    // Callback de cancelación
    if (this.config.onCancel) {
      const result = await this.config.onCancel(this)
      if (result === false) return false
    }

    await this.hide()
    return true
  }

  /**
     * Validar formulario completo
     */
  validateForm () {
    if (!this.config.form) return true

    let isValid = true
    const form = this.state.element.querySelector('.modal-form')

    this.config.form.fields.forEach(field => {
      const fieldElement = form.querySelector(`[name="${field.name}"]`)
      if (fieldElement && !this.validateField(fieldElement)) {
        isValid = false
      }
    })

    return isValid
  }

  /**
     * Validar campo individual
     */
  validateField (fieldElement) {
    const fieldName = fieldElement.name
    const fieldConfig = this.config.form?.fields?.find(f => f.name === fieldName)

    if (!fieldConfig) return true

    const value = this.getFieldValue(fieldElement)
    const errors = []

    // Ejecutar validadores
    Object.keys(this.config.validation).forEach(validatorName => {
      if (fieldConfig[validatorName] !== undefined && this.validators[validatorName]) {
        const error = this.validators[validatorName](value, fieldConfig)
        if (error) errors.push(error)
      }
    })

    // Mostrar/ocultar errores
    const fieldContainer = fieldElement.closest('.form-field')
    const errorContainer = fieldContainer?.querySelector('.invalid-feedback')

    if (errors.length > 0) {
      fieldElement.classList.add('is-invalid')
      if (errorContainer) {
        errorContainer.textContent = errors[0]
      }
      this.state.validationErrors[fieldName] = errors
      return false
    } else {
      fieldElement.classList.remove('is-invalid')
      fieldElement.classList.add('is-valid')
      if (errorContainer) {
        errorContainer.textContent = ''
      }
      delete this.state.validationErrors[fieldName]
      return true
    }
  }

  /**
     * Obtener valor de campo
     */
  getFieldValue (fieldElement) {
    switch (fieldElement.type) {
      case 'checkbox':
        return fieldElement.checked
      case 'radio':
        const radioGroup = document.querySelectorAll(`[name="${fieldElement.name}"]`)
        const checkedRadio = Array.from(radioGroup).find(r => r.checked)
        return checkedRadio ? checkedRadio.value : ''
      case 'file':
        return fieldElement.files
      default:
        return fieldElement.value
    }
  }

  /**
     * Obtener datos del formulario
     */
  getFormData () {
    if (!this.config.form) return {}

    const form = this.state.element.querySelector('.modal-form')
    const formData = {}

    this.config.form.fields.forEach(field => {
      const fieldElement = form.querySelector(`[name="${field.name}"]`)
      if (fieldElement) {
        formData[field.name] = this.getFieldValue(fieldElement)
      }
    })

    return formData
  }

  /**
     * Cargar contenido desde URL
     */
  async loadContent () {
    if (!this.config.url) return

    this.showLoading()

    try {
      const response = await fetch(this.config.url, {
        ...this.config.ajaxOptions,
        headers: {
          'X-CSRFToken': this.getCSRFToken(),
          ...this.config.ajaxOptions.headers
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const content = await response.text()
      this.setContent(content)
    } catch (error) {
      console.error('Error loading modal content:', error)
      this.setContent('<div class="alert alert-danger">Error al cargar el contenido</div>')
    } finally {
      this.hideLoading()
    }
  }

  /**
     * Establecer contenido del modal
     */
  setContent (content) {
    const wrapper = this.state.element.querySelector('.modal-content-wrapper')
    if (wrapper) {
      wrapper.innerHTML = content

      // Re-setup listeners para nuevo contenido
      this.setupModalListeners()
    }
  }

  /**
     * Mostrar loading
     */
  showLoading () {
    this.state.isLoading = true
    const loading = this.state.element.querySelector('.modal-loading')
    const wrapper = this.state.element.querySelector('.modal-content-wrapper')

    if (loading) loading.style.display = 'block'
    if (wrapper) wrapper.style.display = 'none'
  }

  /**
     * Ocultar loading
     */
  hideLoading () {
    this.state.isLoading = false
    const loading = this.state.element.querySelector('.modal-loading')
    const wrapper = this.state.element.querySelector('.modal-content-wrapper')

    if (loading) loading.style.display = 'none'
    if (wrapper) wrapper.style.display = 'block'
  }

  /**
     * Gestión de focus y accesibilidad
     */
  manageFocus () {
    const focusableElements = this.state.element.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )

    if (focusableElements.length > 0) {
      // Auto-focus en el primer campo o botón
      if (this.config.autoFocus) {
        const firstInput = this.state.element.querySelector('input, select, textarea')
        const firstButton = this.state.element.querySelector('button:not(.btn-close)');
        (firstInput || firstButton || focusableElements[0]).focus()
      }

      // Trap focus dentro del modal
      this.trapFocus(focusableElements)
    }
  }

  /**
     * Trap focus dentro del modal
     */
  trapFocus (focusableElements) {
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    this.state.element.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          // Shift + Tab
          if (document.activeElement === firstElement) {
            e.preventDefault()
            lastElement.focus()
          }
        } else {
          // Tab
          if (document.activeElement === lastElement) {
            e.preventDefault()
            firstElement.focus()
          }
        }
      }
    })
  }

  /**
     * Manejar keydown events
     */
  handleKeydown (e) {
    // Enter en botones
    if (e.key === 'Enter' && e.target.classList.contains('modal-confirm')) {
      e.preventDefault()
      this.confirm()
    }

    // Escape
    if (e.key === 'Escape' && this.config.keyboard) {
      e.preventDefault()
      this.hide()
    }
  }

  /**
     * Ajustar posición del modal
     */
  adjustPosition () {
    const modalDialog = this.state.element.querySelector('.modal-dialog')
    if (!modalDialog) return

    // Reset styles
    modalDialog.style.marginTop = ''
    modalDialog.style.marginBottom = ''

    // Centrar verticalmente si es necesario
    const modalHeight = modalDialog.offsetHeight
    const windowHeight = window.innerHeight

    if (modalHeight < windowHeight) {
      const margin = Math.max(30, (windowHeight - modalHeight) / 2)
      modalDialog.style.marginTop = `${margin}px`
      modalDialog.style.marginBottom = `${margin}px`
    }
  }

  /**
     * Utilidades
     */
  generateId () {
    return 'modal_' + Math.random().toString(36).substr(2, 9)
  }

  getCSRFToken () {
    return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
  }

  addGlobalListener (element, event, handler) {
    element.addEventListener(event, handler)
    this.eventListeners.push({ element, event, handler })
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

  /**
     * Métodos estáticos para gestión global
     */
  static getStackIndex () {
    const modals = document.querySelectorAll('.modal.show')
    return modals.length
  }

  static getActiveModals () {
    return document.querySelectorAll('.modal.show')
  }

  static closeAll () {
    const modals = this.getActiveModals()
    modals.forEach(modal => {
      const modalInstance = modal.modalInstance
      if (modalInstance) {
        modalInstance.hide()
      }
    })
  }

  /**
     * Factory methods para tipos comunes de modal
     */
  static alert (options) {
    return new Modal({
      type: 'alert',
      showCancel: false,
      showConfirm: false,
      showClose: true,
      ...options
    }).show()
  }

  static confirm (options) {
    return new Modal({
      type: 'confirm',
      showCancel: true,
      showConfirm: true,
      ...options
    }).show()
  }

  static prompt (options) {
    const form = {
      fields: [{
        name: 'value',
        type: 'text',
        label: options.label || 'Valor',
        placeholder: options.placeholder || '',
        required: true,
        value: options.defaultValue || ''
      }]
    }

    return new Modal({
      type: 'form',
      form,
      validation: { required: true },
      showCancel: true,
      showConfirm: true,
      ...options
    }).show()
  }

  static form (options) {
    return new Modal({
      type: 'form',
      showCancel: true,
      showConfirm: true,
      ...options
    }).show()
  }

  /**
     * Cleanup
     */
  destroy () {
    if (this.state.isVisible) {
      this.hide()
    }

    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    if (this.state.element) {
      this.state.element.remove()
    }

    if (this.state.backdrop) {
      this.state.backdrop.remove()
    }
  }
}

// CSS personalizado para mejorar las animaciones
const modalCSS = `
    .ecosistema-modal .modal-dialog {
        transition: transform 0.3s ease-out;
    }
    
    .ecosistema-modal.modal-animated .modal-dialog {
        transform-origin: center center;
    }
    
    .ecosistema-modal .modal-content {
        border: none;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        border-radius: 8px;
    }
    
    .ecosistema-modal .modal-header {
        border-bottom: 1px solid #e9ecef;
        padding: 1.5rem;
    }
    
    .ecosistema-modal .modal-body {
        padding: 1.5rem;
    }
    
    .ecosistema-modal .modal-footer {
        border-top: 1px solid #e9ecef;
        padding: 1rem 1.5rem;
    }
    
    .ecosistema-modal .form-field {
        position: relative;
    }
    
    .ecosistema-modal .is-invalid {
        border-color: #dc3545;
    }
    
    .ecosistema-modal .is-valid {
        border-color: #28a745;
    }
    
    .ecosistema-modal .modal-loading {
        min-height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    @media (max-width: 576px) {
        .ecosistema-modal .modal-dialog {
            margin: 0.5rem;
        }
        
        .ecosistema-modal .modal-header,
        .ecosistema-modal .modal-body,
        .ecosistema-modal .modal-footer {
            padding: 1rem;
        }
    }
`

// Inyectar CSS si no existe
if (!document.getElementById('modal-custom-styles')) {
  const style = document.createElement('style')
  style.id = 'modal-custom-styles'
  style.textContent = modalCSS
  document.head.appendChild(style)
}

// Registro de instancia en elemento
Object.defineProperty(Modal.prototype, 'register', {
  value: function () {
    if (this.state.element) {
      this.state.element.modalInstance = this
    }
  }
})

// Auto-registro al crear elemento
const originalCreateElement = Modal.prototype.createElement
Modal.prototype.createElement = function () {
  const result = originalCreateElement.call(this)
  this.register()
  return result
}

// Exportar para uso global
window.Modal = Modal
export default Modal
