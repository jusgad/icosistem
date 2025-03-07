/**
 * calendar.js - Scripts para la funcionalidad del calendario
 */

// Clase para manejar la funcionalidad del calendario
class CalendarManager {
    constructor(options = {}) {
        // Opciones por defecto
        this.options = Object.assign({
            calendarEl: '#calendar',
            modalEl: '#event-modal',
            formEl: '#event-form',
            deleteButtonEl: '#delete-event',
            currentUserId: null,
            currentUserRole: null,
            apiEndpoint: '/api/events',
            csrfToken: null
        }, options);
        
        // Referencias a elementos del DOM
        this.calendarEl = document.querySelector(this.options.calendarEl);
        this.modalEl = document.querySelector(this.options.modalEl);
        this.formEl = document.querySelector(this.options.formEl);
        this.deleteButtonEl = document.querySelector(this.options.deleteButtonEl);
        
        // Instancia de FullCalendar
        this.calendar = null;
        
        // Modal de Bootstrap
        this.modal = null;
        
        // Evento actual seleccionado
        this.currentEvent = null;
        
        // Inicializar
        this.init();
    }
    
    // Inicializar el calendario
    init() {
        // Verificar si los elementos necesarios existen
        if (!this.calendarEl) {
            console.warn('Elemento de calendario no encontrado en el DOM');
            return;
        }
        
        // Verificar si FullCalendar está disponible
        if (typeof FullCalendar === 'undefined') {
            console.warn('FullCalendar no está disponible. La funcionalidad de calendario no funcionará.');
            return;
        }
        
        // Inicializar modal de Bootstrap si existe
        if (this.modalEl && typeof bootstrap !== 'undefined') {
            this.modal = new bootstrap.Modal(this.modalEl);
        }
        
        // Inicializar calendario
        this.initCalendar();
        
        // Configurar eventos de la interfaz
        this.setupUIEvents();
    }
    
    // Inicializar calendario con FullCalendar
    initCalendar() {
        const self = this;
        
        this.calendar = new FullCalendar.Calendar(this.calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay,listMonth'
            },
            locale: 'es',
            buttonText: {
                today: 'Hoy',
                month: 'Mes',
                week: 'Semana',
                day: 'Día',
                list: 'Lista'
            },
            themeSystem: 'bootstrap5',
            events: this.options.apiEndpoint,
            editable: this.canEditEvents(),
            selectable: this.canCreateEvents(),
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                meridiem: false,
                hour12: false
            },
            eventClick: function(info) {
                self.handleEventClick(info);
            },
            select: function(info) {
                self.handleDateSelect(info);
            },
            eventDrop: function(info) {
                self.handleEventDrop(info);
            },
            eventResize: function(info) {
                self.handleEventResize(info);
            },
            loading: function(isLoading) {
                // Mostrar/ocultar indicador de carga
                const loadingIndicator = document.querySelector('#calendar-loading');
                if (loadingIndicator) {
                    loadingIndicator.style.display = isLoading ? 'block' : 'none';
                }
            }
        });
        
        this.calendar.render();
    }
    
    // Configurar eventos de la interfaz
    setupUIEvents() {
        // Manejar envío del formulario de evento
        if (this.formEl) {
            this.formEl.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleFormSubmit();
            });
        }
        
        // Manejar clic en botón de eliminar
        if (this.deleteButtonEl) {
            this.deleteButtonEl.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleDeleteEvent();
            });
        }
    }
    
    // Manejar clic en un evento
    handleEventClick(info) {
        // Guardar referencia al evento actual
        this.currentEvent = info.event;
        
        // Verificar si el usuario puede editar este evento
        const canEdit = this.canEditEvent(info.event);
        
        // Si hay un modal, mostrar detalles del evento
        if (this.modal && this.formEl) {
            // Llenar el formulario con los datos del evento
            const titleInput = this.formEl.querySelector('[name="title"]');
            const startInput = this.formEl.querySelector('[name="start"]');
            const endInput = this.formEl.querySelector('[name="end"]');
            const allDayInput = this.formEl.querySelector('[name="allDay"]');
            const descriptionInput = this.formEl.querySelector('[name="description"]');
            const colorInput = this.formEl.querySelector('[name="color"]');
            const eventIdInput = this.formEl.querySelector('[name="eventId"]');
            
            if (titleInput) titleInput.value = info.event.title;
            
            if (startInput) {
                const startDate = info.event.start;
                startInput.value = this.formatDateTimeForInput(startDate);
            }
            
            if (endInput) {
                const endDate = info.event.end || info.event.start;
                endInput.value = this.formatDateTimeForInput(endDate);
            }
            
            if (allDayInput) allDayInput.checked = info.event.allDay;
            
            if (descriptionInput) {
                const description = info.event.extendedProps.description || '';
                descriptionInput.value = description;
            }
            
            if (colorInput) {
                const color = info.event.backgroundColor || '#3498db';
                colorInput.value = color;
            }
            
            if (eventIdInput) eventIdInput.value = info.event.id || '';
            
            // Configurar formulario para edición o solo lectura
            this.formEl.querySelectorAll('input, textarea, select').forEach(el => {
                el.disabled = !canEdit;
            });
            
            // Mostrar/ocultar botones según permisos
            const submitButton = this.formEl.querySelector('[type="submit"]');
            if (submitButton) submitButton.style.display = canEdit ? 'block' : 'none';
            
            if (this.deleteButtonEl) {
                this.deleteButtonEl.style.display = canEdit ? 'block' : 'none';
            }
            
            // Cambiar título del modal
            const modalTitle = this.modalEl.querySelector('.modal-title');
            if (modalTitle) {
                modalTitle.textContent = canEdit ? 'Editar Evento' : 'Detalles del Evento';
            }
            
            // Mostrar modal
            this.modal.show();
        }
    }
    
    // Manejar selección de fecha
    handleDateSelect(info) {
        // Verificar si el usuario puede crear eventos
        if (!this.canCreateEvents()) return;
        
        // Limpiar evento actual
        this.currentEvent = null;
        
        // Si hay un modal, prepararlo para crear un nuevo evento
        if (this.modal && this.formEl) {
            // Resetear el formulario
            this.formEl.reset();
            
            // Llenar fechas seleccionadas
            const startInput = this.formEl.querySelector('[name="start"]');
            const endInput = this.formEl.querySelector('[name="end"]');
            const allDayInput = this.formEl.querySelector('[name="allDay"]');
            const eventIdInput = this.formEl.querySelector('[name="eventId"]');
            
            if (startInput) startInput.value = this.formatDateTimeForInput(info.start);
            if (endInput) endInput.value = this.formatDateTimeForInput(info.end);
            if (allDayInput) allDayInput.checked = info.allDay;
            if (eventIdInput) eventIdInput.value = '';
            
            // Habilitar todos los campos
            this.formEl.querySelectorAll('input, textarea, select').forEach(el => {
                el.disabled = false;
            });
            
            // Mostrar botón de guardar, ocultar botón de eliminar
            const submitButton = this.formEl.querySelector('[type="submit"]');
            if (submitButton) submitButton.style.display = 'block';
            
            if (this.deleteButtonEl) {
                this.deleteButtonEl.style.display = 'none';
            }
            
            // Cambiar título del modal
            const modalTitle = this.modalEl.querySelector('.modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Crear Nuevo Evento';
            }
            
            // Mostrar modal
            this.modal.show();
        }
        
        // Limpiar selección
        this.calendar.unselect();
    }
    
    // Manejar envío del formulario
    handleFormSubmit() {
        // Obtener datos del formulario
        const formData = new FormData(this.formEl);
        const eventData = {
            title: formData.get('title'),
            start: formData.get('start'),
            end: formData.get('end'),
            allDay: formData.get('allDay') === 'on',
            description: formData.get('description'),
            color: formData.get('color'),
            userId: this.options.currentUserId
        };
        
        // ID del evento (si existe)
        const eventId = formData.get('eventId');
        
        // URL y método para la petición
        const url = eventId ? 
            `${this.options.apiEndpoint}/${eventId}` : 
            this.options.apiEndpoint;
        
        const method = eventId ? 'PUT' : 'POST';
        
        // Enviar petición al servidor
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': this.options.csrfToken
            },
            body: JSON.stringify(eventData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al guardar el evento');
            }
            return response.json();
        })
        .then(data => {
            // Cerrar modal
            if (this.modal) {
                this.modal.hide();
            }
            
            // Actualizar calendario
            this.calendar.refetchEvents();
            
            // Mostrar notificación de éxito
            if (window.showNotification) {
                window.showNotification('success', eventId ? 'Evento actualizado correctamente' : 'Evento creado correctamente');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Mostrar notificación de error
            if (window.showNotification) {
                window.showNotification('error', 'Error al guardar el evento');
            }
        });
    }
    
    // Manejar eliminación de evento
    handleDeleteEvent() {
        if (!this.currentEvent || !this.currentEvent.id) return;
        
        // Confirmar eliminación
        if (!confirm('¿Estás seguro de que deseas eliminar este evento?')) return;
        
        // URL para la petición
        const url = `${this.options.apiEndpoint}/${this.currentEvent.id}`;
        
        // Enviar petición al servidor
        fetch(url, {
            method: 'DELETE',
            headers: {
                'X-CSRF-TOKEN': this.options.csrfToken
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al eliminar el evento');
            }
            return response.json();
        })
        .then(data => {
            // Cerrar modal
            if (this.modal) {
                this.modal.hide();
            }
            
            // Eliminar evento del calendario
            this.currentEvent.remove();
            
            // Mostrar notificación de éxito
            if (window.showNotification) {
                window.showNotification('success', 'Evento eliminado correctamente');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Mostrar notificación de error
            if (window.showNotification) {
                window.showNotification('error', 'Error al eliminar el evento');
            }
        });
    }
    
    // Manejar arrastre de evento
    handleEventDrop(info) {
        this.updateEventDates(info.event, info.oldEvent);
    }
    
    // Manejar redimensionamiento de evento
    handleEventResize(info) {
        this.updateEventDates(info.event, info.oldEvent);
    }
    
    // Actualizar fechas de un evento
    updateEventDates(event, oldEvent) {
        // Verificar si el usuario puede editar este evento
        if (!this.canEditEvent(event)) {
            // Revertir cambios
            event.setStart(oldEvent.start);
            event.setEnd(oldEvent.end);
            event.setAllDay(oldEvent.allDay);
            return;
        }
        
        // Datos del evento actualizado
        const eventData = {
            start: event.start.toISOString(),
            end: event.end ? event.end.toISOString() : null,
            allDay: event.allDay
        };

        // URL para la petición
        const url = `${this.options.apiEndpoint}/${event.id}`;
        
        // Enviar petición al servidor
        fetch(url, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': this.options.csrfToken
            },
            body: JSON.stringify(eventData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al actualizar el evento');
            }
            return response.json();
        })
        .then(data => {
            // Mostrar notificación de éxito
            if (window.showNotification) {
                window.showNotification('success', 'Evento actualizado correctamente');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            
            // Revertir cambios en el calendario
            event.setStart(oldEvent.start);
            event.setEnd(oldEvent.end);
            event.setAllDay(oldEvent.allDay);
            
            // Mostrar notificación de error
            if (window.showNotification) {
                window.showNotification('error', 'Error al actualizar el evento');
            }
        });
    }
    
    // Verificar si el usuario puede crear eventos
    canCreateEvents() {
        // Implementar lógica según el rol del usuario
        const role = this.options.currentUserRole;
        return role === 'admin' || role === 'entrepreneur' || role === 'ally';
    }
    
    // Verificar si el usuario puede editar eventos en general
    canEditEvents() {
        // Implementar lógica según el rol del usuario
        const role = this.options.currentUserRole;
        return role === 'admin' || role === 'entrepreneur' || role === 'ally';
    }
    
    // Verificar si el usuario puede editar un evento específico
    canEditEvent(event) {
        // Si es administrador, puede editar cualquier evento
        if (this.options.currentUserRole === 'admin') return true;
        
        // Si es el creador del evento, puede editarlo
        const creatorId = event.extendedProps.creatorId || event.extendedProps.userId;
        if (creatorId && creatorId.toString() === this.options.currentUserId.toString()) return true;
        
        // Si el evento está relacionado con una relación en la que participa
        const relationshipId = event.extendedProps.relationshipId;
        if (relationshipId && this.userBelongsToRelationship(relationshipId)) return true;
        
        return false;
    }
    
    // Verificar si el usuario pertenece a una relación
    userBelongsToRelationship(relationshipId) {
        // Esta información debería venir del backend
        // Por ahora, asumimos que el frontend tiene esta información
        const userRelationships = window.userRelationships || [];
        return userRelationships.includes(parseInt(relationshipId));
    }
    
    // Formatear fecha para input datetime-local
    formatDateTimeForInput(date) {
        if (!date) return '';
        
        const d = new Date(date);
        
        // Formatear como YYYY-MM-DDTHH:MM
        const year = d.getFullYear();
        const month = (d.getMonth() + 1).toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        const hours = d.getHours().toString().padStart(2, '0');
        const minutes = d.getMinutes().toString().padStart(2, '0');
        
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }
}

// Inicializar calendario cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Obtener datos del elemento calendar
    const calendarEl = document.querySelector('#calendar');
    if (!calendarEl) return;
    
    const currentUserId = calendarEl.dataset.userId;
    const currentUserRole = calendarEl.dataset.userRole;
    const apiEndpoint = calendarEl.dataset.apiEndpoint || '/api/events';
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Inicializar gestor de calendario
    window.calendarManager = new CalendarManager({
        calendarEl: '#calendar',
        modalEl: '#event-modal',
        formEl: '#event-form',
        deleteButtonEl: '#delete-event',
        currentUserId: currentUserId,
        currentUserRole: currentUserRole,
        apiEndpoint: apiEndpoint,
        csrfToken: csrfToken
    });
});