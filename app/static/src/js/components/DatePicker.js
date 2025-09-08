/**
 * DatePicker Component
 * Componente avanzado de selección de fecha y hora para el ecosistema de emprendimiento
 * Soporta rangos, internacionalización, temas y validación
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoDatePicker {
  constructor (element, options = {}) {
    this.element = typeof element === 'string' ? document.getElementById(element) : element
    if (!this.element) {
      throw new Error('DatePicker element not found')
    }

    this.config = {
      // Configuración básica
      type: options.type || 'date', // date, datetime, time, range
      format: options.format || (options.type === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DD HH:mm'),
      initialDate: options.initialDate || null,
      minDate: options.minDate || null,
      maxDate: options.maxDate || null,

      // Internacionalización
      locale: options.locale || 'es',
      firstDayOfWeek: options.firstDayOfWeek || 1, // 0 = Domingo, 1 = Lunes

      // Comportamiento
      autoClose: options.autoClose !== false,
      clearButton: options.clearButton !== false,
      todayButton: options.todayButton !== false,
      showWeekNumbers: options.showWeekNumbers || false,

      // Apariencia
      theme: options.theme || 'light', // light, dark
      inline: options.inline || false,
      showTimePicker: options.type === 'datetime' || options.type === 'time',
      timePicker24Hour: options.timePicker24Hour !== false,
      timePickerIncrement: options.timePickerIncrement || 5, // minutos

      // Rango de fechas
      enableRange: options.type === 'range',
      rangeSeparator: options.rangeSeparator || ' - ',

      // Callbacks
      onSelect: options.onSelect || null,
      onOpen: options.onOpen || null,
      onClose: options.onClose || null,
      onClear: options.onClear || null,
      onChangeMonth: options.onChangeMonth || null,
      onChangeYear: options.onChangeYear || null,

      // Contexto del ecosistema
      ecosystemContext: options.ecosystemContext || 'general', // project_timeline, meeting_schedule

      ...options
    }

    this.state = {
      selectedDate: null,
      selectedEndDate: null, // Para rangos
      currentMonth: null,
      currentYear: null,
      isOpen: false,
      pickerElement: null,
      inputElement: this.element.tagName === 'INPUT' ? this.element : null
    }

    this.eventListeners = []
    this.dayNames = []
    this.monthNames = []

    this.init()
  }

  /**
     * Inicialización del componente
     */
  init () {
    try {
      this.setupLocaleData()

      if (this.config.initialDate) {
        this.setDate(this.config.initialDate)
      } else {
        const today = new Date()
        this.state.currentMonth = today.getMonth()
        this.state.currentYear = today.getFullYear()
      }

      if (!this.config.inline) {
        this.createInputElement()
      } else {
        this.createPickerElement()
        this.render()
        this.show()
      }

      this.setupEventListeners()

      console.log('📅 EcoDatePicker initialized successfully')
    } catch (error) {
      console.error('❌ Error initializing EcoDatePicker:', error)
      this.handleError(error)
    }
  }

  /**
     * Configurar datos de localización (nombres de días y meses)
     */
  setupLocaleData () {
    const locale = this.config.locale
    this.dayNames = []
    for (let i = 0; i < 7; i++) {
      this.dayNames.push(new Date(2023, 0, i + this.config.firstDayOfWeek).toLocaleDateString(locale, { weekday: 'short' }))
    }
    this.monthNames = []
    for (let i = 0; i < 12; i++) {
      this.monthNames.push(new Date(2023, i, 1).toLocaleDateString(locale, { month: 'long' }))
    }
  }

  /**
     * Crear input si el elemento no es un input
     */
  createInputElement () {
    if (this.state.inputElement) return

    this.state.inputElement = document.createElement('input')
    this.state.inputElement.type = 'text'
    this.state.inputElement.className = 'form-control eco-datepicker-input'
    this.state.inputElement.placeholder = this.config.format.toLowerCase()
    this.state.inputElement.readOnly = true // Para forzar el uso del picker

    this.element.appendChild(this.state.inputElement)
    this.updateInputValue()
  }

  /**
     * Crear elemento del picker
     */
  createPickerElement () {
    if (this.state.pickerElement) return

    this.state.pickerElement = document.createElement('div')
    this.state.pickerElement.className = `eco-datepicker-picker theme-${this.config.theme} ${this.config.inline ? 'inline' : 'dropdown'}`
    this.state.pickerElement.setAttribute('tabindex', '-1')

    if (this.config.inline) {
      this.element.appendChild(this.state.pickerElement)
    } else {
      document.body.appendChild(this.state.pickerElement)
    }
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    if (this.state.inputElement && !this.config.inline) {
      this.addEventListener(this.state.inputElement, 'click', () => this.toggle())
      this.addEventListener(this.state.inputElement, 'focus', () => this.show())
    }

    if (this.state.pickerElement) {
      this.addEventListener(this.state.pickerElement, 'click', (e) => this.handlePickerClick(e))
    }

    // Cerrar al hacer click fuera (si no es inline)
    if (!this.config.inline) {
      this.addEventListener(document, 'click', (e) => {
        if (this.state.isOpen &&
                    !this.state.pickerElement.contains(e.target) &&
                    e.target !== this.state.inputElement) {
          this.hide()
        }
      })
    }

    // Teclado
    this.addEventListener(this.config.inline ? this.state.pickerElement : (this.state.inputElement || document), 'keydown', (e) => this.handleKeyDown(e))
  }

  /**
     * Renderizar el picker
     */
  render () {
    if (!this.state.pickerElement) this.createPickerElement()

    const month = this.state.currentMonth
    const year = this.state.currentYear

    let html = '<div class="datepicker-container">'
    html += this.renderHeader(month, year)
    html += this.renderDaysOfWeek()
    html += this.renderCalendar(month, year)
    if (this.config.showTimePicker) {
      html += this.renderTimePicker()
    }
    html += this.renderFooter()
    html += '</div>'

    this.state.pickerElement.innerHTML = html
    this.updateActiveDate()
  }

  renderHeader (month, year) {
    return `
            <div class="datepicker-header">
                <button type="button" class="btn-nav prev-month" aria-label="Mes anterior">&lt;</button>
                <div class="current-month-year">
                    <select class="month-select" aria-label="Seleccionar mes">
                        ${this.monthNames.map((m, i) => `<option value="${i}" ${i === month ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                    <input type="number" class="year-input" value="${year}" min="1900" max="2100" aria-label="Seleccionar año">
                </div>
                <button type="button" class="btn-nav next-month" aria-label="Mes siguiente">&gt;</button>
            </div>
        `
  }

  renderDaysOfWeek () {
    let html = '<div class="datepicker-days-of-week">'
    this.dayNames.forEach(day => {
      html += `<div class="day-name">${day}</div>`
    })
    html += '</div>'
    return html
  }

  renderCalendar (month, year) {
    let html = '<div class="datepicker-calendar">'
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()

    let startingDay = firstDay.getDay() - this.config.firstDayOfWeek
    if (startingDay < 0) startingDay += 7

    // Días del mes anterior
    for (let i = 0; i < startingDay; i++) {
      html += '<div class="day other-month"></div>'
    }

    // Días del mes actual
    for (let day = 1; day <= daysInMonth; day++) {
      const currentDate = new Date(year, month, day)
      let classes = 'day'
      let isDisabled = false

      if (this.isSameDate(currentDate, this.state.selectedDate)) classes += ' selected'
      if (this.config.enableRange && this.state.selectedEndDate && this.isSameDate(currentDate, this.state.selectedEndDate)) classes += ' selected-end'
      if (this.config.enableRange && this.isInRange(currentDate)) classes += ' in-range'
      if (this.isSameDate(currentDate, new Date())) classes += ' today'

      if ((this.config.minDate && currentDate < this.parseDate(this.config.minDate)) ||
                (this.config.maxDate && currentDate > this.parseDate(this.config.maxDate))) {
        classes += ' disabled'
        isDisabled = true
      }

      html += `<button type="button" class="${classes}" data-date="${this.formatDate(currentDate, 'YYYY-MM-DD')}" ${isDisabled ? 'disabled' : ''}>${day}</button>`
    }

    // Días del mes siguiente (para completar la cuadrícula)
    const totalCells = startingDay + daysInMonth
    const remainingCells = (7 - (totalCells % 7)) % 7
    for (let i = 0; i < remainingCells; i++) {
      html += '<div class="day other-month"></div>'
    }

    html += '</div>'
    return html
  }

  renderTimePicker () {
    if (!this.config.showTimePicker) return ''

    const selected = this.state.selectedDate || new Date()
    let hours = selected.getHours()
    const minutes = selected.getMinutes()
    let ampm = 'AM'

    if (!this.config.timePicker24Hour) {
      ampm = hours >= 12 ? 'PM' : 'AM'
      hours = hours % 12 || 12
    }

    return `
            <div class="datepicker-timepicker">
                <input type="number" class="time-input hour" value="${String(hours).padStart(2, '0')}" min="0" max="${this.config.timePicker24Hour ? 23 : 12}" aria-label="Hora">
                <span>:</span>
                <input type="number" class="time-input minute" value="${String(minutes).padStart(2, '0')}" min="0" max="59" step="${this.config.timePickerIncrement}" aria-label="Minutos">
                ${!this.config.timePicker24Hour
? `
                    <select class="time-ampm" aria-label="AM/PM">
                        <option value="AM" ${ampm === 'AM' ? 'selected' : ''}>AM</option>
                        <option value="PM" ${ampm === 'PM' ? 'selected' : ''}>PM</option>
                    </select>
                `
: ''}
            </div>
        `
  }

  renderFooter () {
    let html = '<div class="datepicker-footer">'
    if (this.config.todayButton) {
      html += '<button type="button" class="btn-today">Hoy</button>'
    }
    if (this.config.clearButton) {
      html += '<button type="button" class="btn-clear">Limpiar</button>'
    }
    html += '</div>'
    return html
  }

  /**
     * Manejar clicks en el picker
     */
  handlePickerClick (e) {
    const target = e.target

    if (target.classList.contains('prev-month')) {
      this.prevMonth()
    } else if (target.classList.contains('next-month')) {
      this.nextMonth()
    } else if (target.classList.contains('day') && !target.classList.contains('other-month') && !target.classList.contains('disabled')) {
      this.selectDate(this.parseDate(target.dataset.date))
    } else if (target.classList.contains('btn-today')) {
      this.selectDate(new Date())
      this.state.currentMonth = new Date().getMonth()
      this.state.currentYear = new Date().getFullYear()
      this.render()
    } else if (target.classList.contains('btn-clear')) {
      this.clear()
    }
  }

  /**
     * Manejar cambios en los inputs de navegación (mes, año, hora, minuto)
     */
  handleInputChange (e) {
    const target = e.target
    if (target.classList.contains('month-select')) {
      this.state.currentMonth = parseInt(target.value)
      this.render()
    } else if (target.classList.contains('year-input')) {
      this.state.currentYear = parseInt(target.value)
      this.render()
    } else if (target.classList.contains('time-input')) {
      this.updateTimeFromInputs()
    } else if (target.classList.contains('time-ampm')) {
      this.updateTimeFromInputs()
    }
  }

  /**
     * Actualizar la hora basada en los inputs del timepicker
     */
  updateTimeFromInputs () {
    if (!this.state.selectedDate) return

    const hourInput = this.state.pickerElement.querySelector('.time-input.hour')
    const minuteInput = this.state.pickerElement.querySelector('.time-input.minute')
    const ampmSelect = this.state.pickerElement.querySelector('.time-ampm')

    let hours = parseInt(hourInput.value)
    const minutes = parseInt(minuteInput.value)

    if (!this.config.timePicker24Hour && ampmSelect) {
      if (ampmSelect.value === 'PM' && hours < 12) hours += 12
      if (ampmSelect.value === 'AM' && hours === 12) hours = 0 // Medianoche
    }

    const newDate = new Date(this.state.selectedDate)
    newDate.setHours(hours, minutes)

    this.state.selectedDate = newDate
    this.updateInputValue()

    if (this.config.onSelect) {
      this.config.onSelect(this.getSelectedDate(), this)
    }
  }

  /**
     * Seleccionar fecha
     */
  selectDate (date) {
    if (this.config.enableRange) {
      if (!this.state.selectedDate || this.state.selectedEndDate) {
        this.state.selectedDate = date
        this.state.selectedEndDate = null
      } else if (date < this.state.selectedDate) {
        this.state.selectedEndDate = this.state.selectedDate
        this.state.selectedDate = date
      } else {
        this.state.selectedEndDate = date
      }
    } else {
      this.state.selectedDate = date
    }

    // Si hay timepicker, mantener la hora actual o poner mediodía
    if (this.config.showTimePicker) {
      const currentHours = this.state.selectedDate ? this.state.selectedDate.getHours() : 12
      const currentMinutes = this.state.selectedDate ? this.state.selectedDate.getMinutes() : 0
      this.state.selectedDate.setHours(currentHours, currentMinutes, 0, 0)
    }

    this.updateInputValue()
    this.updateActiveDate()

    if (this.config.onSelect) {
      this.config.onSelect(this.getSelectedDate(), this)
    }

    if (this.config.autoClose && !this.config.enableRange && !this.config.showTimePicker) {
      this.hide()
    } else if (this.config.autoClose && this.config.enableRange && this.state.selectedEndDate) {
      this.hide()
    }

    // Si es inline, re-renderizar para reflejar selección
    if (this.config.inline) {
      this.render()
    }
  }

  /**
     * Actualizar valor del input
     */
  updateInputValue () {
    if (!this.state.inputElement || this.config.inline) return

    if (this.config.enableRange) {
      if (this.state.selectedDate && this.state.selectedEndDate) {
        this.state.inputElement.value =
                    this.formatDate(this.state.selectedDate) +
                    this.config.rangeSeparator +
                    this.formatDate(this.state.selectedEndDate)
      } else if (this.state.selectedDate) {
        this.state.inputElement.value = this.formatDate(this.state.selectedDate)
      } else {
        this.state.inputElement.value = ''
      }
    } else {
      this.state.inputElement.value = this.state.selectedDate ? this.formatDate(this.state.selectedDate) : ''
    }
  }

  /**
     * Actualizar la fecha activa en el calendario (resaltado)
     */
  updateActiveDate () {
    if (!this.state.pickerElement) return

    this.state.pickerElement.querySelectorAll('.day.selected, .day.selected-end, .day.in-range').forEach(el => {
      el.classList.remove('selected', 'selected-end', 'in-range')
    })

    if (this.state.selectedDate) {
      const dateStr = this.formatDate(this.state.selectedDate, 'YYYY-MM-DD')
      const dayEl = this.state.pickerElement.querySelector(`.day[data-date="${dateStr}"]`)
      if (dayEl) dayEl.classList.add('selected')
    }

    if (this.config.enableRange && this.state.selectedEndDate) {
      const endDateStr = this.formatDate(this.state.selectedEndDate, 'YYYY-MM-DD')
      const endDayEl = this.state.pickerElement.querySelector(`.day[data-date="${endDateStr}"]`)
      if (endDayEl) endDayEl.classList.add('selected-end')

      // Marcar rango
      this.state.pickerElement.querySelectorAll('.day').forEach(el => {
        const dayDate = this.parseDate(el.dataset.date)
        if (this.isInRange(dayDate)) {
          el.classList.add('in-range')
        }
      })
    }
  }

  /**
     * Mostrar/ocultar picker
     */
  toggle () {
    this.state.isOpen ? this.hide() : this.show()
  }

  show () {
    if (this.config.inline || this.state.isOpen) return

    this.state.isOpen = true
    if (!this.state.pickerElement) this.createPickerElement()

    this.render()
    this.positionPicker()
    this.state.pickerElement.style.display = 'block'
    this.state.pickerElement.classList.add('open')
    this.state.pickerElement.focus() // Para accesibilidad y eventos de teclado

    if (this.config.onOpen) this.config.onOpen(this)
  }

  hide () {
    if (this.config.inline || !this.state.isOpen) return

    this.state.isOpen = false
    this.state.pickerElement.classList.remove('open')
    this.state.pickerElement.style.display = 'none'

    if (this.config.onClose) this.config.onClose(this)
  }

  /**
     * Posicionar el picker (para modo dropdown)
     */
  positionPicker () {
    if (this.config.inline || !this.state.inputElement || !this.state.pickerElement) return

    const inputRect = this.state.inputElement.getBoundingClientRect()
    const pickerHeight = this.state.pickerElement.offsetHeight
    const spaceBelow = window.innerHeight - inputRect.bottom
    const spaceAbove = inputRect.top

    let top; let left = inputRect.left + window.scrollX

    if (spaceBelow >= pickerHeight || spaceBelow >= spaceAbove) {
      top = inputRect.bottom + window.scrollY + 5 // 5px de espacio
    } else {
      top = inputRect.top + window.scrollY - pickerHeight - 5
    }

    // Ajustar si se sale de la pantalla horizontalmente
    const pickerWidth = this.state.pickerElement.offsetWidth
    if (left + pickerWidth > window.innerWidth) {
      left = window.innerWidth - pickerWidth - 10 // 10px de margen
    }
    if (left < 10) left = 10

    this.state.pickerElement.style.top = `${top}px`
    this.state.pickerElement.style.left = `${left}px`
  }

  /**
     * Navegación de meses/años
     */
  prevMonth () {
    this.state.currentMonth--
    if (this.state.currentMonth < 0) {
      this.state.currentMonth = 11
      this.state.currentYear--
    }
    this.render()
    if (this.config.onChangeMonth) this.config.onChangeMonth(this.state.currentMonth, this.state.currentYear, this)
  }

  nextMonth () {
    this.state.currentMonth++
    if (this.state.currentMonth > 11) {
      this.state.currentMonth = 0
      this.state.currentYear++
    }
    this.render()
    if (this.config.onChangeMonth) this.config.onChangeMonth(this.state.currentMonth, this.state.currentYear, this)
  }

  /**
     * Limpiar selección
     */
  clear () {
    this.state.selectedDate = null
    this.state.selectedEndDate = null
    this.updateInputValue()
    this.updateActiveDate()
    if (this.config.onClear) this.config.onClear(this)
    if (this.config.inline) this.render()
  }

  /**
     * Formatear fecha
     */
  formatDate (date, format = null) {
    if (!date) return ''
    format = format || this.config.format

    // Simple YYYY-MM-DD HH:mm formatter (para evitar dependencias pesadas)
    const pad = (n) => n < 10 ? '0' + n : n
    const year = date.getFullYear()
    const month = pad(date.getMonth() + 1)
    const day = pad(date.getDate())
    const hours = pad(date.getHours())
    const minutes = pad(date.getMinutes())

    let formatted = format
    formatted = formatted.replace('YYYY', year)
    formatted = formatted.replace('MM', month)
    formatted = formatted.replace('DD', day)

    if (this.config.showTimePicker) {
      formatted = formatted.replace('HH', hours)
      formatted = formatted.replace('mm', minutes)
    }

    return formatted.trim()
  }

  /**
     * Parsear fecha desde string
     */
  parseDate (dateString) {
    if (!dateString) return null
    if (dateString instanceof Date) return dateString

    // Intentar parsear con el formato especificado
    // Esto es simplificado. Una librería como date-fns o moment.js sería más robusta.
    try {
      const parts = dateString.split(/[-/ :]/)
      const formatParts = this.config.format.split(/[-/ :]/)

      let year; let month; let day; let hours = 0; let minutes = 0

      formatParts.forEach((part, index) => {
        const value = parseInt(parts[index])
        if (part.includes('YYYY')) year = value
        else if (part.includes('MM')) month = value - 1 // Meses son 0-indexados
        else if (part.includes('DD')) day = value
        else if (part.includes('HH')) hours = value
        else if (part.includes('mm')) minutes = value
      })

      if (year && month !== undefined && day) {
        return new Date(year, month, day, hours, minutes)
      }
    } catch (e) {
      // Fallback a new Date() si el formato es complejo
    }

    const parsed = new Date(dateString)
    return isNaN(parsed.getTime()) ? null : parsed
  }

  /**
     * Utilidades de fecha
     */
  isSameDate (date1, date2) {
    if (!date1 || !date2) return false
    return date1.getFullYear() === date2.getFullYear() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getDate() === date2.getDate()
  }

  isInRange (date) {
    if (!this.config.enableRange || !this.state.selectedDate || !this.state.selectedEndDate) {
      return false
    }
    return date > this.state.selectedDate && date < this.state.selectedEndDate
  }

  /**
     * API pública
     */
  getDate () {
    return this.state.selectedDate
  }

  getFormattedDate (format = null) {
    return this.formatDate(this.state.selectedDate, format)
  }

  getRange () {
    if (this.config.enableRange) {
      return { start: this.state.selectedDate, end: this.state.selectedEndDate }
    }
    return null
  }

  setDate (date, triggerSelect = false) {
    const newDate = this.parseDate(date)
    if (newDate) {
      this.state.selectedDate = newDate
      this.state.currentMonth = newDate.getMonth()
      this.state.currentYear = newDate.getFullYear()
      this.updateInputValue()
      if (this.state.isOpen || this.config.inline) this.render()

      if (triggerSelect && this.config.onSelect) {
        this.config.onSelect(this.getSelectedDate(), this)
      }
    }
  }

  getSelectedDate () {
    if (this.config.enableRange) {
      return this.getRange()
    }
    return this.getDate()
  }

  /**
     * Manejo de errores
     */
  handleError (error) {
    console.error('EcoDatePicker Error:', error)
    if (this.config.onError) {
      this.config.onError(error, this)
    }
    // Podría mostrar un mensaje de error en la UI
  }

  /**
     * Manejo de teclado para accesibilidad
     */
  handleKeyDown (e) {
    if (!this.state.isOpen && !this.config.inline) return

    let newDate
    const currentDate = this.state.selectedDate || new Date(this.state.currentYear, this.state.currentMonth, 1)

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault()
        newDate = new Date(currentDate)
        newDate.setDate(currentDate.getDate() - 1)
        this.navigateToDate(newDate)
        break
      case 'ArrowRight':
        e.preventDefault()
        newDate = new Date(currentDate)
        newDate.setDate(currentDate.getDate() + 1)
        this.navigateToDate(newDate)
        break
      case 'ArrowUp':
        e.preventDefault()
        newDate = new Date(currentDate)
        newDate.setDate(currentDate.getDate() - 7)
        this.navigateToDate(newDate)
        break
      case 'ArrowDown':
        e.preventDefault()
        newDate = new Date(currentDate)
        newDate.setDate(currentDate.getDate() + 7)
        this.navigateToDate(newDate)
        break
      case 'PageUp':
        e.preventDefault()
        this.prevMonth()
        this.focusFirstDayOfMonth()
        break
      case 'PageDown':
        e.preventDefault()
        this.nextMonth()
        this.focusFirstDayOfMonth()
        break
      case 'Home':
        e.preventDefault()
        newDate = new Date(this.state.currentYear, this.state.currentMonth, 1)
        this.navigateToDate(newDate)
        break
      case 'End':
        e.preventDefault()
        newDate = new Date(this.state.currentYear, this.state.currentMonth + 1, 0)
        this.navigateToDate(newDate)
        break
      case 'Enter':
      case ' ': // Space
        e.preventDefault()
        if (document.activeElement && document.activeElement.classList.contains('day')) {
          this.selectDate(this.parseDate(document.activeElement.dataset.date))
        } else if (this.state.selectedDate) {
          this.hide() // Confirm selection
        }
        break
      case 'Escape':
        e.preventDefault()
        this.hide()
        break
    }
  }

  navigateToDate (date) {
    this.state.currentMonth = date.getMonth()
    this.state.currentYear = date.getFullYear()
    this.render()

    // Enfocar la nueva fecha
    const dateStr = this.formatDate(date, 'YYYY-MM-DD')
    const dayEl = this.state.pickerElement.querySelector(`.day[data-date="${dateStr}"]`)
    if (dayEl && !dayEl.disabled) {
      dayEl.focus()
    }
  }

  focusFirstDayOfMonth () {
    const firstDayEl = this.state.pickerElement.querySelector('.day:not(.other-month):not(.disabled)')
    if (firstDayEl) {
      firstDayEl.focus()
    }
  }

  /**
     * Limpieza
     */
  destroy () {
    this.eventListeners.forEach(({ element, event, handler }) => {
      element.removeEventListener(event, handler)
    })

    if (this.state.pickerElement) {
      this.state.pickerElement.remove()
    }

    // Si el input fue creado por el componente, removerlo
    if (this.state.inputElement && this.element !== this.state.inputElement) {
      this.state.inputElement.remove()
    }

    console.log('📅 EcoDatePicker destroyed')
  }

  // Helper para añadir event listeners y guardarlos para limpieza
  addEventListener (element, event, handler) {
    element.addEventListener(event, handler)
    this.eventListeners.push({ element, event, handler })
  }
}

// CSS básico para el DatePicker (se puede mejorar y mover a un archivo .css)
const datePickerCSS = `
    .eco-datepicker-picker {
        background-color: #fff;
        border: 1px solid #ccc;
        border-radius: 4px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        padding: 10px;
        width: 300px;
        z-index: 1000;
    }
    .eco-datepicker-picker.inline {
        position: relative;
        box-shadow: none;
        border: none;
    }
    .eco-datepicker-picker.dropdown {
        position: absolute;
    }
    .datepicker-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .datepicker-header .btn-nav { background: none; border: none; cursor: pointer; font-size: 1.2em; }
    .current-month-year { display: flex; gap: 5px; }
    .current-month-year select, .current-month-year input { font-size: 0.9em; padding: 2px 5px; border: 1px solid #ddd; border-radius: 3px; }
    .datepicker-days-of-week, .datepicker-calendar { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; }
    .datepicker-days-of-week .day-name { font-weight: bold; font-size: 0.8em; padding: 5px 0; color: #555; }
    .datepicker-calendar .day { border: none; background: none; cursor: pointer; padding: 8px 0; border-radius: 3px; font-size: 0.9em; }
    .datepicker-calendar .day:hover:not(.disabled) { background-color: #f0f0f0; }
    .datepicker-calendar .day.other-month { color: #ccc; cursor: default; }
    .datepicker-calendar .day.disabled { color: #aaa; cursor: not-allowed; text-decoration: line-through; }
    .datepicker-calendar .day.today { font-weight: bold; border: 1px solid #007bff; }
    .datepicker-calendar .day.selected { background-color: #007bff; color: white; }
    .datepicker-calendar .day.selected-end { background-color: #0056b3; color: white; }
    .datepicker-calendar .day.in-range { background-color: #cfe2ff; color: #004085; }
    .datepicker-timepicker { display: flex; justify-content: center; align-items: center; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }
    .datepicker-timepicker .time-input { width: 50px; text-align: center; margin: 0 5px; }
    .datepicker-timepicker .time-ampm { margin-left: 5px; }
    .datepicker-footer { display: flex; justify-content: space-between; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }
    .datepicker-footer button { background: none; border: 1px solid #ccc; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
    .datepicker-footer button:hover { background-color: #f0f0f0; }
    .eco-datepicker-picker.theme-dark { background-color: #333; color: #fff; border-color: #555; }
    .eco-datepicker-picker.theme-dark .btn-nav, .eco-datepicker-picker.theme-dark .day-name { color: #bbb; }
    .eco-datepicker-picker.theme-dark select, .eco-datepicker-picker.theme-dark input { background-color: #444; color: #fff; border-color: #666; }
    .eco-datepicker-picker.theme-dark .day:hover:not(.disabled) { background-color: #555; }
    .eco-datepicker-picker.theme-dark .day.other-month { color: #777; }
    .eco-datepicker-picker.theme-dark .day.disabled { color: #666; }
    .eco-datepicker-picker.theme-dark .day.today { border-color: #00aaff; }
    .eco-datepicker-picker.theme-dark .day.selected { background-color: #00aaff; }
    .eco-datepicker-picker.theme-dark .day.selected-end { background-color: #0077cc; }
    .eco-datepicker-picker.theme-dark .day.in-range { background-color: #005599; color: #fff; }
    .eco-datepicker-picker.theme-dark .datepicker-footer button { border-color: #555; color: #fff; }
    .eco-datepicker-picker.theme-dark .datepicker-footer button:hover { background-color: #444; }
`

// Inyectar CSS si no existe
if (!document.getElementById('eco-datepicker-styles')) {
  const style = document.createElement('style')
  style.id = 'eco-datepicker-styles'
  style.textContent = datePickerCSS
  document.head.appendChild(style)
}

// Exportar para uso global
window.EcoDatePicker = EcoDatePicker
export default EcoDatePicker
