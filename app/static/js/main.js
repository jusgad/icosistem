/**
 * main.js - Scripts principales para la plataforma de emprendimiento
 */

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Inicializar popovers de Bootstrap
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Toggle para el sidebar en dispositivos móviles
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            const mainContent = document.querySelector('.main-content');
            
            sidebar.classList.toggle('sidebar-collapsed');
            mainContent.classList.toggle('main-content-expanded');
        });
    }

    // Manejo de formularios con AJAX
    const ajaxForms = document.querySelectorAll('.ajax-form');
    ajaxForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...';
            
            const formData = new FormData(form);
            
            fetch(form.action, {
                method: form.method,
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
                
                if (data.success) {
                    showNotification('success', data.message || 'Operación completada con éxito');
                    
                    // Si hay redirección, navegar a la URL
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    }
                    
                    // Si hay que actualizar algún elemento
                    if (data.update_element && data.html) {
                        document.querySelector(data.update_element).innerHTML = data.html;
                    }
                    
                    // Si hay que resetear el formulario
                    if (data.reset_form) {
                        form.reset();
                    }
                } else {
                    showNotification('error', data.message || 'Ha ocurrido un error');
                    
                    // Mostrar errores de validación
                    if (data.errors) {
                        Object.keys(data.errors).forEach(field => {
                            const input = form.querySelector(`[name="${field}"]`);
                            if (input) {
                                input.classList.add('is-invalid');
                                
                                // Crear o actualizar mensaje de error
                                let feedbackDiv = input.nextElementSibling;
                                if (!feedbackDiv || !feedbackDiv.classList.contains('invalid-feedback')) {
                                    feedbackDiv = document.createElement('div');
                                    feedbackDiv.classList.add('invalid-feedback');
                                    input.parentNode.insertBefore(feedbackDiv, input.nextSibling);
                                }
                                feedbackDiv.textContent = data.errors[field];
                            }
                        });
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
                showNotification('error', 'Ha ocurrido un error en la comunicación con el servidor');
            });
        });
    });

    // Sistema de notificaciones
    window.showNotification = function(type, message, duration = 5000) {
        const notificationArea = document.getElementById('notification-area');
        if (!notificationArea) {
            // Crear área de notificaciones si no existe
            const newNotificationArea = document.createElement('div');
            newNotificationArea.id = 'notification-area';
            newNotificationArea.style.position = 'fixed';
            newNotificationArea.style.top = '20px';
            newNotificationArea.style.right = '20px';
            newNotificationArea.style.zIndex = '9999';
            document.body.appendChild(newNotificationArea);
        }
        
        const notification = document.createElement('div');
        notification.classList.add('toast', 'show');
        notification.role = 'alert';
        notification.ariaLive = 'assertive';
        notification.ariaAtomic = 'true';
        
        // Establecer color según el tipo
        let bgClass = 'bg-primary';
        if (type === 'success') bgClass = 'bg-success';
        if (type === 'error') bgClass = 'bg-danger';
        if (type === 'warning') bgClass = 'bg-warning';
        if (type === 'info') bgClass = 'bg-info';
        
        notification.innerHTML = `
            <div class="toast-header ${bgClass} text-white">
                <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        document.getElementById('notification-area').appendChild(notification);
        
        // Auto-cerrar después de la duración
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 500);
        }, duration);
        
        // Manejar el botón de cerrar
        const closeBtn = notification.querySelector('.btn-close');
        closeBtn.addEventListener('click', function() {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 500);
        });
    };

    // Inicializar dropdowns dinámicos
    const dynamicDropdowns = document.querySelectorAll('.dynamic-dropdown');
    dynamicDropdowns.forEach(dropdown => {
        const input = dropdown.querySelector('input[type="hidden"]');
        const searchInput = dropdown.querySelector('input[type="text"]');
        const dropdownMenu = dropdown.querySelector('.dropdown-menu');
        
        if (searchInput && dropdownMenu) {
            searchInput.addEventListener('focus', function() {
                dropdownMenu.classList.add('show');
            });
            
            searchInput.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const items = dropdownMenu.querySelectorAll('.dropdown-item');
                
                items.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    if (text.includes(searchTerm)) {
                        item.style.display = 'block';
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
            
            document.addEventListener('click', function(e) {
                if (!dropdown.contains(e.target)) {
                    dropdownMenu.classList.remove('show');
                }
            });
            
            dropdownMenu.addEventListener('click', function(e) {
                if (e.target.classList.contains('dropdown-item')) {
                    const value = e.target.dataset.value;
                    const text = e.target.textContent;
                    
                    input.value = value;
                    searchInput.value = text;
                    dropdownMenu.classList.remove('show');
                    
                    // Disparar evento de cambio
                    const event = new Event('change');
                    input.dispatchEvent(event);
                }
            });
        }
    });

    // Inicializar campos de fecha con flatpickr si está disponible
    if (typeof flatpickr !== 'undefined') {
        flatpickr('.datepicker', {
            dateFormat: 'Y-m-d',
            locale: 'es'
        });
        
        flatpickr('.datetimepicker', {
            enableTime: true,
            dateFormat: 'Y-m-d H:i',
            locale: 'es'
        });
    }
});