/**
 * DOM Utilities para Ecosistema de Emprendimiento
 * Sistema completo de manipulación DOM con optimizaciones de performance y funcionalidades avanzadas
 *
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

/**
 * Clase principal para manipulación DOM
 */
class DOMElement {
  constructor (selector) {
    if (typeof selector === 'string') {
      this.elements = Array.from(document.querySelectorAll(selector))
    } else if (selector instanceof Element) {
      this.elements = [selector]
    } else if (selector instanceof NodeList || Array.isArray(selector)) {
      this.elements = Array.from(selector)
    } else {
      this.elements = []
    }

    this.length = this.elements.length
    return this
  }

  /**
     * Itera sobre los elementos
     */
  each (callback) {
    this.elements.forEach((element, index) => {
      callback.call(element, element, index)
    })
    return this
  }

  /**
     * Obtiene el primer elemento o el elemento en el índice especificado
     */
  get (index = 0) {
    return this.elements[index] || null
  }

  /**
     * Verifica si existe al menos un elemento
     */
  exists () {
    return this.length > 0
  }

  /**
     * Manipulación de clases
     */
  addClass (className) {
    return this.each(el => el.classList.add(className))
  }

  removeClass (className) {
    return this.each(el => el.classList.remove(className))
  }

  toggleClass (className, force) {
    return this.each(el => el.classList.toggle(className, force))
  }

  hasClass (className) {
    return this.elements.some(el => el.classList.contains(className))
  }

  /**
     * Manipulación de atributos
     */
  attr (name, value) {
    if (value === undefined) {
      return this.get()?.getAttribute(name)
    }
    return this.each(el => el.setAttribute(name, value))
  }

  removeAttr (name) {
    return this.each(el => el.removeAttribute(name))
  }

  data (key, value) {
    if (value === undefined) {
      return this.get()?.dataset[key]
    }
    return this.each(el => el.dataset[key] = value)
  }

  /**
     * Manipulación de contenido
     */
  html (content) {
    if (content === undefined) {
      return this.get()?.innerHTML
    }
    return this.each(el => el.innerHTML = content)
  }

  text (content) {
    if (content === undefined) {
      return this.get()?.textContent
    }
    return this.each(el => el.textContent = content)
  }

  value (val) {
    if (val === undefined) {
      return this.get()?.value
    }
    return this.each(el => el.value = val)
  }

  /**
     * Manipulación de estilos
     */
  css (property, value) {
    if (typeof property === 'object') {
      return this.each(el => {
        Object.assign(el.style, property)
      })
    }

    if (value === undefined) {
      return getComputedStyle(this.get())[property]
    }

    return this.each(el => el.style[property] = value)
  }

  show () {
    return this.css('display', 'block')
  }

  hide () {
    return this.css('display', 'none')
  }

  toggle (force) {
    return this.each(el => {
      const isHidden = getComputedStyle(el).display === 'none'
      const shouldShow = force !== undefined ? force : isHidden
      el.style.display = shouldShow ? 'block' : 'none'
    })
  }

  /**
     * Eventos
     */
  on (event, handler, options) {
    return this.each(el => el.addEventListener(event, handler, options))
  }

  off (event, handler, options) {
    return this.each(el => el.removeEventListener(event, handler, options))
  }

  trigger (event, detail) {
    const customEvent = new CustomEvent(event, { detail, bubbles: true })
    return this.each(el => el.dispatchEvent(customEvent))
  }

  /**
     * Manipulación del DOM
     */
  append (content) {
    return this.each(el => {
      if (typeof content === 'string') {
        el.insertAdjacentHTML('beforeend', content)
      } else {
        el.appendChild(content)
      }
    })
  }

  prepend (content) {
    return this.each(el => {
      if (typeof content === 'string') {
        el.insertAdjacentHTML('afterbegin', content)
      } else {
        el.insertBefore(content, el.firstChild)
      }
    })
  }

  before (content) {
    return this.each(el => {
      if (typeof content === 'string') {
        el.insertAdjacentHTML('beforebegin', content)
      } else {
        el.parentNode.insertBefore(content, el)
      }
    })
  }

  after (content) {
    return this.each(el => {
      if (typeof content === 'string') {
        el.insertAdjacentHTML('afterend', content)
      } else {
        el.parentNode.insertBefore(content, el.nextSibling)
      }
    })
  }

  remove () {
    return this.each(el => el.remove())
  }

  empty () {
    return this.each(el => el.innerHTML = '')
  }

  /**
     * Navegación DOM
     */
  parent (selector) {
    const parents = this.elements.map(el => el.parentElement).filter(Boolean)
    if (selector) {
      return new DOMElement(parents.filter(p => p.matches(selector)))
    }
    return new DOMElement(parents)
  }

  children (selector) {
    const children = this.elements.flatMap(el => Array.from(el.children))
    if (selector) {
      return new DOMElement(children.filter(c => c.matches(selector)))
    }
    return new DOMElement(children)
  }

  siblings (selector) {
    const siblings = this.elements.flatMap(el =>
      Array.from(el.parentElement.children).filter(sibling => sibling !== el)
    )
    if (selector) {
      return new DOMElement(siblings.filter(s => s.matches(selector)))
    }
    return new DOMElement(siblings)
  }

  find (selector) {
    const found = this.elements.flatMap(el => Array.from(el.querySelectorAll(selector)))
    return new DOMElement(found)
  }

  closest (selector) {
    const closest = this.elements.map(el => el.closest(selector)).filter(Boolean)
    return new DOMElement(closest)
  }

  /**
     * Posición y dimensiones
     */
  offset () {
    const el = this.get()
    if (!el) return { top: 0, left: 0 }

    const rect = el.getBoundingClientRect()
    return {
      top: rect.top + window.pageYOffset,
      left: rect.left + window.pageXOffset,
      width: rect.width,
      height: rect.height
    }
  }

  position () {
    const el = this.get()
    if (!el) return { top: 0, left: 0 }

    return {
      top: el.offsetTop,
      left: el.offsetLeft,
      width: el.offsetWidth,
      height: el.offsetHeight
    }
  }

  /**
     * Scroll
     */
  scrollTop (value) {
    if (value === undefined) {
      return this.get()?.scrollTop || 0
    }
    return this.each(el => el.scrollTop = value)
  }

  scrollLeft (value) {
    if (value === undefined) {
      return this.get()?.scrollLeft || 0
    }
    return this.each(el => el.scrollLeft = value)
  }

  scrollTo (options) {
    return this.each(el => {
      if (el.scrollTo) {
        el.scrollTo(options)
      }
    })
  }

  scrollIntoView (options = {}) {
    return this.each(el => {
      el.scrollIntoView({ behavior: 'smooth', ...options })
    })
  }
}

/**
 * Utilidades de selección DOM
 */
const Selectors = {
  /**
     * Función principal de selección (similar a jQuery)
     */
  $ (selector, context = document) {
    if (!selector) return new DOMElement([])

    if (typeof selector === 'function') {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', selector)
      } else {
        selector()
      }
      return
    }

    if (selector instanceof Element || selector instanceof NodeList || Array.isArray(selector)) {
      return new DOMElement(selector)
    }

    try {
      return new DOMElement(context.querySelectorAll(selector))
    } catch (error) {
      // // console.error('Invalid selector:', selector, error)
      return new DOMElement([])
    }
  },

  /**
     * Selección segura que no lanza errores
     */
  safe (selector, context = document) {
    try {
      const elements = context.querySelectorAll(selector)
      return Array.from(elements)
    } catch (error) {
      // console.warn('Invalid selector:', selector)
      return []
    }
  },

  /**
     * Buscar elementos por texto
     */
  byText (text, tag = '*', exact = false) {
    const elements = document.querySelectorAll(tag)
    return Array.from(elements).filter(el => {
      const content = el.textContent.trim()
      return exact ? content === text : content.includes(text)
    })
  },

  /**
     * Buscar elementos por data attribute
     */
  byData (attribute, value, context = document) {
    const selector = value !== undefined
      ? `[data-${attribute}="${value}"]`
      : `[data-${attribute}]`
    return Array.from(context.querySelectorAll(selector))
  },

  /**
     * Buscar elementos visibles
     */
  visible (selector, context = document) {
    const elements = context.querySelectorAll(selector)
    return Array.from(elements).filter(el => {
      const style = getComputedStyle(el)
      return style.display !== 'none' &&
                   style.visibility !== 'hidden' &&
                   style.opacity !== '0'
    })
  },

  /**
     * Buscar elementos en viewport
     */
  inViewport (selector, threshold = 0, context = document) {
    const elements = context.querySelectorAll(selector)
    return Array.from(elements).filter(el => this.isInViewport(el, threshold))
  },

  /**
     * Verificar si elemento está en viewport
     */
  isInViewport (element, threshold = 0) {
    const rect = element.getBoundingClientRect()
    const windowHeight = window.innerHeight || document.documentElement.clientHeight
    const windowWidth = window.innerWidth || document.documentElement.clientWidth

    return (
      rect.top >= -threshold &&
            rect.left >= -threshold &&
            rect.bottom <= windowHeight + threshold &&
            rect.right <= windowWidth + threshold
    )
  }
}

/**
 * Utilidades de creación de elementos
 */
const ElementCreator = {
  /**
     * Crear elemento con configuración completa
     */
  create (tag, config = {}) {
    const element = document.createElement(tag)

    // Atributos
    if (config.attributes) {
      Object.entries(config.attributes).forEach(([key, value]) => {
        element.setAttribute(key, value)
      })
    }

    // Propiedades
    if (config.properties) {
      Object.assign(element, config.properties)
    }

    // Clases
    if (config.className) {
      element.className = config.className
    }

    if (config.classes) {
      element.classList.add(...config.classes)
    }

    // Contenido
    if (config.textContent) {
      element.textContent = config.textContent
    }

    if (config.innerHTML) {
      element.innerHTML = config.innerHTML
    }

    // Estilos
    if (config.style) {
      Object.assign(element.style, config.style)
    }

    // Dataset
    if (config.dataset) {
      Object.assign(element.dataset, config.dataset)
    }

    // Eventos
    if (config.events) {
      Object.entries(config.events).forEach(([event, handler]) => {
        element.addEventListener(event, handler)
      })
    }

    // Hijos
    if (config.children) {
      config.children.forEach(child => {
        if (typeof child === 'string') {
          element.appendChild(document.createTextNode(child))
        } else {
          element.appendChild(child)
        }
      })
    }

    return element
  },

  /**
     * Crear desde template string
     */
  fromTemplate (template, data = {}) {
    // Simple template replacement
    let html = template
    Object.entries(data).forEach(([key, value]) => {
      const regex = new RegExp(`{{${key}}}`, 'g')
      html = html.replace(regex, value)
    })

    const div = document.createElement('div')
    div.innerHTML = html.trim()

    return div.children.length === 1 ? div.firstElementChild : Array.from(div.children)
  },

  /**
     * Crear elementos específicos del ecosistema
     */
  createCard (config) {
    return this.create('div', {
      className: 'card',
      children: [
        config.header
          ? this.create('div', {
            className: 'card-header',
            innerHTML: config.header
          })
          : null,
        this.create('div', {
          className: 'card-body',
          children: [
            config.title
              ? this.create('h5', {
                className: 'card-title',
                textContent: config.title
              })
              : null,
            config.content
              ? this.create('div', {
                className: 'card-content',
                innerHTML: config.content
              })
              : null,
            config.actions
              ? this.create('div', {
                className: 'card-actions',
                children: config.actions
              })
              : null
          ].filter(Boolean)
        }),
        config.footer
          ? this.create('div', {
            className: 'card-footer',
            innerHTML: config.footer
          })
          : null
      ].filter(Boolean),
      ...config
    })
  },

  /**
     * Crear modal
     */
  createModal (config) {
    const modal = this.create('div', {
      className: 'modal fade',
      attributes: {
        tabindex: '-1',
        role: 'dialog'
      },
      children: [
        this.create('div', {
          className: `modal-dialog ${config.size ? 'modal-' + config.size : ''}`,
          children: [
            this.create('div', {
              className: 'modal-content',
              children: [
                config.title
                  ? this.create('div', {
                    className: 'modal-header',
                    children: [
                      this.create('h5', {
                        className: 'modal-title',
                        textContent: config.title
                      }),
                      this.create('button', {
                        className: 'btn-close',
                        attributes: {
                          type: 'button',
                          'data-bs-dismiss': 'modal'
                        }
                      })
                    ]
                  })
                  : null,
                this.create('div', {
                  className: 'modal-body',
                  innerHTML: config.body
                }),
                config.footer
                  ? this.create('div', {
                    className: 'modal-footer',
                    innerHTML: config.footer
                  })
                  : null
              ].filter(Boolean)
            })
          ]
        })
      ]
    })

    document.body.appendChild(modal)
    return modal
  },

  /**
     * Crear loading spinner
     */
  createSpinner (config = {}) {
    return this.create('div', {
      className: `spinner-border ${config.size ? 'spinner-border-' + config.size : ''}`,
      attributes: {
        role: 'status'
      },
      children: [
        this.create('span', {
          className: 'sr-only',
          textContent: config.text || 'Cargando...'
        })
      ],
      ...config
    })
  },

  /**
     * Crear toast notification
     */
  createToast (config) {
    return this.create('div', {
      className: `toast ${config.type ? 'toast-' + config.type : ''}`,
      attributes: {
        role: 'alert'
      },
      children: [
        config.header
          ? this.create('div', {
            className: 'toast-header',
            innerHTML: config.header
          })
          : null,
        this.create('div', {
          className: 'toast-body',
          innerHTML: config.message
        })
      ].filter(Boolean)
    })
  }
}

/**
 * Utilidades de animación
 */
const Animations = {
  /**
     * Fade in/out
     */
  fadeIn (element, duration = 300) {
    return new Promise(resolve => {
      element.style.opacity = '0'
      element.style.display = 'block'

      const animation = element.animate([
        { opacity: 0 },
        { opacity: 1 }
      ], {
        duration,
        easing: 'ease-out'
      })

      animation.onfinish = () => {
        element.style.opacity = ''
        resolve()
      }
    })
  },

  fadeOut (element, duration = 300) {
    return new Promise(resolve => {
      const animation = element.animate([
        { opacity: 1 },
        { opacity: 0 }
      ], {
        duration,
        easing: 'ease-in'
      })

      animation.onfinish = () => {
        element.style.display = 'none'
        element.style.opacity = ''
        resolve()
      }
    })
  },

  /**
     * Slide animations
     */
  slideDown (element, duration = 300) {
    return new Promise(resolve => {
      const height = element.scrollHeight
      element.style.height = '0'
      element.style.overflow = 'hidden'
      element.style.display = 'block'

      const animation = element.animate([
        { height: '0px' },
        { height: `${height}px` }
      ], {
        duration,
        easing: 'ease-out'
      })

      animation.onfinish = () => {
        element.style.height = ''
        element.style.overflow = ''
        resolve()
      }
    })
  },

  slideUp (element, duration = 300) {
    return new Promise(resolve => {
      const height = element.scrollHeight
      element.style.height = `${height}px`
      element.style.overflow = 'hidden'

      const animation = element.animate([
        { height: `${height}px` },
        { height: '0px' }
      ], {
        duration,
        easing: 'ease-in'
      })

      animation.onfinish = () => {
        element.style.display = 'none'
        element.style.height = ''
        element.style.overflow = ''
        resolve()
      }
    })
  },

  /**
     * Animación de rebote
     */
  bounce (element, intensity = 10, duration = 600) {
    return new Promise(resolve => {
      const animation = element.animate([
        { transform: 'translateY(0)' },
        { transform: `translateY(-${intensity}px)` },
        { transform: 'translateY(0)' },
        { transform: `translateY(-${intensity / 2}px)` },
        { transform: 'translateY(0)' }
      ], {
        duration,
        easing: 'ease-out'
      })

      animation.onfinish = resolve
    })
  },

  /**
     * Shake animation
     */
  shake (element, intensity = 5, duration = 400) {
    return new Promise(resolve => {
      const animation = element.animate([
        { transform: 'translateX(0)' },
        { transform: `translateX(-${intensity}px)` },
        { transform: `translateX(${intensity}px)` },
        { transform: `translateX(-${intensity}px)` },
        { transform: `translateX(${intensity}px)` },
        { transform: 'translateX(0)' }
      ], {
        duration,
        easing: 'ease-out'
      })

      animation.onfinish = resolve
    })
  },

  /**
     * Highlight animation
     */
  highlight (element, color = '#ffeb3b', duration = 1000) {
    return new Promise(resolve => {
      const originalBackground = element.style.backgroundColor

      const animation = element.animate([
        { backgroundColor: color },
        { backgroundColor: originalBackground || 'transparent' }
      ], {
        duration,
        easing: 'ease-out'
      })

      animation.onfinish = resolve
    })
  },

  /**
     * Counter animation
     */
  animateCounter (element, from = 0, to, duration = 1000, formatter = null) {
    return new Promise(resolve => {
      const start = Date.now()
      const range = to - from

      const updateCounter = () => {
        const elapsed = Date.now() - start
        const progress = Math.min(elapsed / duration, 1)
        const easeOutQuart = 1 - Math.pow(1 - progress, 4)
        const current = from + (range * easeOutQuart)

        const value = Math.round(current)
        element.textContent = formatter ? formatter(value) : value

        if (progress < 1) {
          requestAnimationFrame(updateCounter)
        } else {
          resolve()
        }
      }

      requestAnimationFrame(updateCounter)
    })
  }
}

/**
 * Utilidades de formularios
 */
const Forms = {
  /**
     * Obtener datos del formulario
     */
  getData (form) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    const formData = new FormData(form)
    const data = {}

    for (const [key, value] of formData.entries()) {
      if (data[key]) {
        // Manejar múltiples valores (checkboxes, selects múltiples)
        if (Array.isArray(data[key])) {
          data[key].push(value)
        } else {
          data[key] = [data[key], value]
        }
      } else {
        data[key] = value
      }
    }

    return data
  },

  /**
     * Establecer datos del formulario
     */
  setData (form, data) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    Object.entries(data).forEach(([key, value]) => {
      const elements = form.querySelectorAll(`[name="${key}"]`)

      elements.forEach(element => {
        switch (element.type) {
          case 'checkbox':
          case 'radio':
            element.checked = Array.isArray(value)
              ? value.includes(element.value)
              : element.value === value
            break
          case 'select-multiple':
            Array.from(element.options).forEach(option => {
              option.selected = Array.isArray(value)
                ? value.includes(option.value)
                : option.value === value
            })
            break
          default:
            element.value = value
        }
      })
    })
  },

  /**
     * Validar formulario
     */
  validate (form, rules) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    const errors = {}
    const data = this.getData(form)

    Object.entries(rules).forEach(([field, fieldRules]) => {
      const value = data[field]
      const fieldErrors = []

      if (fieldRules.required && (!value || value.trim() === '')) {
        fieldErrors.push('Este campo es requerido')
      }

      if (value && fieldRules.minLength && value.length < fieldRules.minLength) {
        fieldErrors.push(`Mínimo ${fieldRules.minLength} caracteres`)
      }

      if (value && fieldRules.maxLength && value.length > fieldRules.maxLength) {
        fieldErrors.push(`Máximo ${fieldRules.maxLength} caracteres`)
      }

      if (value && fieldRules.email && !/\S+@\S+\.\S+/.test(value)) {
        fieldErrors.push('Email inválido')
      }

      if (value && fieldRules.pattern && !fieldRules.pattern.test(value)) {
        fieldErrors.push('Formato inválido')
      }

      if (fieldRules.custom && typeof fieldRules.custom === 'function') {
        const customError = fieldRules.custom(value, data)
        if (customError) {
          fieldErrors.push(customError)
        }
      }

      if (fieldErrors.length > 0) {
        errors[field] = fieldErrors
      }
    })

    return {
      isValid: Object.keys(errors).length === 0,
      errors,
      data
    }
  },

  /**
     * Mostrar errores de validación
     */
  showErrors (form, errors) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    // Limpiar errores previos
    this.clearErrors(form)

    Object.entries(errors).forEach(([field, fieldErrors]) => {
      const element = form.querySelector(`[name="${field}"]`)
      if (element) {
        element.classList.add('is-invalid')

        // Buscar o crear contenedor de error
        let errorContainer = element.parentElement.querySelector('.invalid-feedback')
        if (!errorContainer) {
          errorContainer = ElementCreator.create('div', {
            className: 'invalid-feedback'
          })
          element.parentElement.appendChild(errorContainer)
        }

        errorContainer.textContent = Array.isArray(fieldErrors)
          ? fieldErrors[0]
          : fieldErrors
      }
    })
  },

  /**
     * Limpiar errores
     */
  clearErrors (form) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    form.querySelectorAll('.is-invalid').forEach(el => {
      el.classList.remove('is-invalid')
    })

    form.querySelectorAll('.invalid-feedback').forEach(el => {
      el.remove()
    })
  },

  /**
     * Auto-save formulario
     */
  autoSave (form, key, delay = 2000) {
    if (typeof form === 'string') {
      form = document.querySelector(form)
    }

    let timeout

    const save = () => {
      const data = this.getData(form)
      localStorage.setItem(`autosave_${key}`, JSON.stringify({
        data,
        timestamp: Date.now()
      }))
    }

    const handleInput = () => {
      clearTimeout(timeout)
      timeout = setTimeout(save, delay)
    }

    form.addEventListener('input', handleInput)
    form.addEventListener('change', handleInput)

    // Restaurar datos guardados
    const saved = localStorage.getItem(`autosave_${key}`)
    if (saved) {
      try {
        const { data } = JSON.parse(saved)
        this.setData(form, data)
      } catch (error) {
        // // console.error('Error restoring autosaved data:', error)
      }
    }

    return {
      save,
      restore: () => {
        const saved = localStorage.getItem(`autosave_${key}`)
        if (saved) {
          const { data } = JSON.parse(saved)
          this.setData(form, data)
        }
      },
      clear: () => localStorage.removeItem(`autosave_${key}`)
    }
  }
}

/**
 * Utilidades de performance
 */
const Performance = {
  /**
     * Lazy loading de imágenes
     */
  lazyLoadImages (selector = 'img[data-src]', options = {}) {
    const defaultOptions = {
      threshold: 0.1,
      rootMargin: '50px',
      ...options
    }

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target

            // Crear nueva imagen para cargar
            const newImg = new Image()
            newImg.onload = () => {
              img.src = img.dataset.src
              img.classList.remove('lazy')
              img.classList.add('loaded')
            }
            newImg.onerror = () => {
              img.classList.add('error')
            }
            newImg.src = img.dataset.src

            observer.unobserve(img)
          }
        })
      }, defaultOptions)

      document.querySelectorAll(selector).forEach(img => {
        observer.observe(img)
      })

      return observer
    } else {
      // Fallback para navegadores sin soporte
      document.querySelectorAll(selector).forEach(img => {
        img.src = img.dataset.src
      })
    }
  },

  /**
     * Virtual scrolling
     */
  virtualScroll (container, items, renderItem, itemHeight = 50) {
    if (typeof container === 'string') {
      container = document.querySelector(container)
    }

    const viewport = ElementCreator.create('div', {
      style: {
        height: '100%',
        overflow: 'auto'
      }
    })

    const content = ElementCreator.create('div', {
      style: {
        height: `${items.length * itemHeight}px`,
        position: 'relative'
      }
    })

    viewport.appendChild(content)
    container.appendChild(viewport)

    let lastScrollTop = 0

    const render = () => {
      const scrollTop = viewport.scrollTop
      const viewportHeight = viewport.clientHeight

      const startIndex = Math.floor(scrollTop / itemHeight)
      const endIndex = Math.min(
        startIndex + Math.ceil(viewportHeight / itemHeight) + 1,
        items.length
      )

      // Limpiar contenido existente
      content.innerHTML = ''

      // Renderizar elementos visibles
      for (let i = startIndex; i < endIndex; i++) {
        const item = items[i]
        const element = renderItem(item, i)
        element.style.position = 'absolute'
        element.style.top = `${i * itemHeight}px`
        element.style.height = `${itemHeight}px`
        content.appendChild(element)
      }

      lastScrollTop = scrollTop
    }

    viewport.addEventListener('scroll', render)
    render() // Renderizado inicial

    return {
      refresh: render,
      updateItems: (newItems) => {
        items = newItems
        content.style.height = `${items.length * itemHeight}px`
        render()
      },
      destroy: () => {
        viewport.removeEventListener('scroll', render)
        container.removeChild(viewport)
      }
    }
  },

  /**
     * Debounce para eventos DOM
     */
  debounce (func, wait = 300) {
    let timeout
    return function executedFunction (...args) {
      const later = () => {
        clearTimeout(timeout)
        func(...args)
      }
      clearTimeout(timeout)
      timeout = setTimeout(later, wait)
    }
  },

  /**
     * Throttle para eventos DOM
     */
  throttle (func, limit = 100) {
    let inThrottle
    return function executedFunction (...args) {
      if (!inThrottle) {
        func.apply(this, args)
        inThrottle = true
        setTimeout(() => inThrottle = false, limit)
      }
    }
  }
}

/**
 * Utilidades específicas del ecosistema
 */
const EcosystemDOM = {
  /**
     * Crear card de proyecto
     */
  createProjectCard (project) {
    return ElementCreator.create('div', {
      className: 'project-card card',
      dataset: {
        projectId: project.id,
        stage: project.stage
      },
      children: [
        ElementCreator.create('div', {
          className: 'card-header d-flex justify-content-between align-items-center',
          children: [
            ElementCreator.create('h5', {
              className: 'card-title mb-0',
              textContent: project.name
            }),
            ElementCreator.create('span', {
              className: `badge badge-${this.getStageColor(project.stage)}`,
              textContent: this.formatStage(project.stage)
            })
          ]
        }),
        ElementCreator.create('div', {
          className: 'card-body',
          children: [
            ElementCreator.create('p', {
              className: 'card-text',
              textContent: project.description
            }),
            ElementCreator.create('div', {
              className: 'project-meta d-flex justify-content-between',
              children: [
                ElementCreator.create('small', {
                  className: 'text-muted',
                  textContent: `Industria: ${project.industry}`
                }),
                ElementCreator.create('small', {
                  className: 'text-muted',
                  textContent: `Creado: ${this.formatDate(project.created_at)}`
                })
              ]
            })
          ]
        }),
        ElementCreator.create('div', {
          className: 'card-footer',
          children: [
            ElementCreator.create('button', {
              className: 'btn btn-primary btn-sm',
              textContent: 'Ver Detalles',
              events: {
                click: () => this.viewProject(project.id)
              }
            }),
            ElementCreator.create('button', {
              className: 'btn btn-outline-secondary btn-sm ms-2',
              textContent: 'Editar',
              events: {
                click: () => this.editProject(project.id)
              }
            })
          ]
        })
      ]
    })
  },

  /**
     * Crear card de emprendedor
     */
  createEntrepreneurCard (entrepreneur) {
    return ElementCreator.create('div', {
      className: 'entrepreneur-card card',
      dataset: {
        entrepreneurId: entrepreneur.id
      },
      children: [
        ElementCreator.create('div', {
          className: 'card-body text-center',
          children: [
            ElementCreator.create('img', {
              className: 'rounded-circle mb-3',
              attributes: {
                src: entrepreneur.avatar || '/static/images/default-avatar.png',
                alt: entrepreneur.name,
                width: '80',
                height: '80'
              }
            }),
            ElementCreator.create('h5', {
              className: 'card-title',
              textContent: entrepreneur.name
            }),
            ElementCreator.create('p', {
              className: 'card-text text-muted',
              textContent: entrepreneur.company
            }),
            ElementCreator.create('p', {
              className: 'card-text',
              textContent: entrepreneur.bio
            }),
            ElementCreator.create('div', {
              className: 'tags mb-3',
              children: entrepreneur.skills?.map(skill =>
                ElementCreator.create('span', {
                  className: 'badge bg-secondary me-1',
                  textContent: skill
                })
              ) || []
            }),
            ElementCreator.create('button', {
              className: 'btn btn-primary',
              textContent: 'Ver Perfil',
              events: {
                click: () => this.viewEntrepreneur(entrepreneur.id)
              }
            })
          ]
        })
      ]
    })
  },

  /**
     * Crear formulario de contacto
     */
  createContactForm (config = {}) {
    return ElementCreator.create('form', {
      className: 'contact-form',
      children: [
        ElementCreator.create('div', {
          className: 'mb-3',
          children: [
            ElementCreator.create('label', {
              className: 'form-label',
              attributes: { for: 'contact-name' },
              textContent: 'Nombre completo'
            }),
            ElementCreator.create('input', {
              className: 'form-control',
              attributes: {
                type: 'text',
                id: 'contact-name',
                name: 'name',
                required: true
              }
            })
          ]
        }),
        ElementCreator.create('div', {
          className: 'mb-3',
          children: [
            ElementCreator.create('label', {
              className: 'form-label',
              attributes: { for: 'contact-email' },
              textContent: 'Email'
            }),
            ElementCreator.create('input', {
              className: 'form-control',
              attributes: {
                type: 'email',
                id: 'contact-email',
                name: 'email',
                required: true
              }
            })
          ]
        }),
        ElementCreator.create('div', {
          className: 'mb-3',
          children: [
            ElementCreator.create('label', {
              className: 'form-label',
              attributes: { for: 'contact-subject' },
              textContent: 'Asunto'
            }),
            ElementCreator.create('select', {
              className: 'form-select',
              attributes: {
                id: 'contact-subject',
                name: 'subject',
                required: true
              },
              children: [
                ElementCreator.create('option', {
                  attributes: { value: '' },
                  textContent: 'Seleccionar asunto...'
                }),
                ElementCreator.create('option', {
                  attributes: { value: 'mentorship' },
                  textContent: 'Solicitar mentoría'
                }),
                ElementCreator.create('option', {
                  attributes: { value: 'partnership' },
                  textContent: 'Propuesta de alianza'
                }),
                ElementCreator.create('option', {
                  attributes: { value: 'investment' },
                  textContent: 'Oportunidad de inversión'
                }),
                ElementCreator.create('option', {
                  attributes: { value: 'other' },
                  textContent: 'Otro'
                })
              ]
            })
          ]
        }),
        ElementCreator.create('div', {
          className: 'mb-3',
          children: [
            ElementCreator.create('label', {
              className: 'form-label',
              attributes: { for: 'contact-message' },
              textContent: 'Mensaje'
            }),
            ElementCreator.create('textarea', {
              className: 'form-control',
              attributes: {
                id: 'contact-message',
                name: 'message',
                rows: '4',
                required: true
              }
            })
          ]
        }),
        ElementCreator.create('button', {
          className: 'btn btn-primary',
          attributes: { type: 'submit' },
          textContent: 'Enviar mensaje'
        })
      ],
      events: {
        submit: (e) => {
          e.preventDefault()
          const formData = Forms.getData(e.target)
          config.onSubmit?.(formData)
        }
      }
    })
  },

  /**
     * Utilidades de formato
     */
  formatStage (stage) {
    const stages = {
      idea: 'Idea',
      validation: 'Validación',
      mvp: 'MVP',
      'early-stage': 'Etapa Temprana',
      growth: 'Crecimiento',
      scaling: 'Escalamiento'
    }
    return stages[stage] || stage
  },

  getStageColor (stage) {
    const colors = {
      idea: 'warning',
      validation: 'info',
      mvp: 'primary',
      'early-stage': 'success',
      growth: 'success',
      scaling: 'success'
    }
    return colors[stage] || 'secondary'
  },

  formatDate (dateString) {
    return new Date(dateString).toLocaleDateString('es-CO', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  },

  /**
     * Navegación
     */
  viewProject (projectId) {
    window.location.href = `/projects/${projectId}`
  },

  editProject (projectId) {
    window.location.href = `/projects/${projectId}/edit`
  },

  viewEntrepreneur (entrepreneurId) {
    window.location.href = `/entrepreneurs/${entrepreneurId}`
  }
}

/**
 * Utilidades de accesibilidad
 */
const Accessibility = {
  /**
     * Configurar atributos ARIA
     */
  setAria (element, attributes) {
    Object.entries(attributes).forEach(([key, value]) => {
      element.setAttribute(`aria-${key}`, value)
    })
  },

  /**
     * Anunciar a lectores de pantalla
     */
  announce (message, priority = 'polite') {
    const announcer = document.getElementById('aria-announcer') ||
            ElementCreator.create('div', {
              attributes: {
                id: 'aria-announcer',
                'aria-live': priority,
                'aria-atomic': 'true'
              },
              style: {
                position: 'absolute',
                left: '-10000px',
                width: '1px',
                height: '1px',
                overflow: 'hidden'
              }
            })

    if (!document.getElementById('aria-announcer')) {
      document.body.appendChild(announcer)
    }

    announcer.textContent = message
  },

  /**
     * Gestión de foco
     */
  trapFocus (container) {
    const focusableElements = container.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )

    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    const handleTabKey = (e) => {
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            lastElement.focus()
            e.preventDefault()
          }
        } else {
          if (document.activeElement === lastElement) {
            firstElement.focus()
            e.preventDefault()
          }
        }
      }
    }

    container.addEventListener('keydown', handleTabKey)

    return {
      activate: () => firstElement?.focus(),
      deactivate: () => container.removeEventListener('keydown', handleTabKey)
    }
  }
}

/**
 * API principal del módulo DOM
 */
const DOM = {
  // Funciones principales
  $: Selectors.$,
  select: Selectors.safe,
  create: ElementCreator.create,

  // Submódulos
  selectors: Selectors,
  elements: ElementCreator,
  animations: Animations,
  forms: Forms,
  performance: Performance,
  ecosystem: EcosystemDOM,
  accessibility: Accessibility,

  // Utilidades rápidas
  ready (callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback)
    } else {
      callback()
    }
  },

  loadScript (src, async = true) {
    return new Promise((resolve, reject) => {
      const script = ElementCreator.create('script', {
        attributes: { src, async },
        events: {
          load: resolve,
          error: reject
        }
      })
      document.head.appendChild(script)
    })
  },

  loadStyle (href) {
    return new Promise((resolve, reject) => {
      const link = ElementCreator.create('link', {
        attributes: {
          rel: 'stylesheet',
          href
        },
        events: {
          load: resolve,
          error: reject
        }
      })
      document.head.appendChild(link)
    })
  },

  /**
     * Inicializar sistema DOM
     */
  init () {
    // Configurar lazy loading automático
    this.performance.lazyLoadImages()

    // Configurar announcer para accesibilidad
    if (!document.getElementById('aria-announcer')) {
      const announcer = this.create('div', {
        attributes: {
          id: 'aria-announcer',
          'aria-live': 'polite',
          'aria-atomic': 'true'
        },
        style: {
          position: 'absolute',
          left: '-10000px',
          width: '1px',
          height: '1px',
          overflow: 'hidden'
        }
      })
      document.body.appendChild(announcer)
    }

    // // console.log('🎨 DOM utilities initialized')
  }
}

// Auto-inicialización
DOM.ready(() => DOM.init())

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DOM
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
  window.DOM = DOM
  window.$ = DOM.$ // Alias global opcional
}
