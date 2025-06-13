/**
 * ProgressBar Component
 * Componente de barra de progreso personalizable para el ecosistema de emprendimiento
 * Muestra el progreso de tareas, perfiles, proyectos, etc.
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoProgressBar {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.getElementById(element) : element;
        if (!this.element) {
            throw new Error('ProgressBar element not found');
        }

        this.config = {
            // Configuración básica
            value: options.value || 0, // Valor actual (0-100)
            max: options.max || 100,   // Valor máximo (usado si value no es porcentaje)
            type: options.type || 'default', // default, success, warning, danger, info
            label: options.label || null, // Texto a mostrar sobre la barra
            showPercentage: options.showPercentage !== false,
            striped: options.striped || false,
            animated: options.animated || false,
            height: options.height || '1rem', // Altura de la barra
            
            // Apariencia
            theme: options.theme || 'light', // light, dark
            borderRadius: options.borderRadius || '0.25rem',
            
            // Callbacks
            onChange: options.onChange || null, // Se llama cuando el valor cambia
            onComplete: options.onComplete || null, // Se llama cuando alcanza el 100%
            
            // Accesibilidad
            ariaLabel: options.ariaLabel || 'Barra de progreso',
            
            // Contexto del ecosistema
            context: options.context || 'general', // profile_completion, project_progress, task_status
            
            ...options
        };

        this.state = {
            currentValue: this.config.value,
            isComplete: false
        };

        this.init();
    }

    /**
     * Inicialización del componente
     */
    init() {
        try {
            this.render();
            this.update(); // Establecer valor inicial
            console.log('📊 EcoProgressBar initialized successfully for element:', this.element);
        } catch (error) {
            console.error('❌ Error initializing EcoProgressBar:', error);
            this.handleError(error);
        }
    }

    /**
     * Renderizar la estructura de la barra de progreso
     */
    render() {
        this.element.classList.add('eco-progress-bar-container', `theme-${this.config.theme}`);
        this.element.style.height = this.config.height;
        this.element.style.borderRadius = this.config.borderRadius;
        
        this.element.innerHTML = `
            <div class="eco-progress-bar progress-bar-${this.config.type}" 
                 role="progressbar" 
                 aria-valuenow="${this.getPercentage()}" 
                 aria-valuemin="0" 
                 aria-valuemax="100"
                 aria-label="${this.config.ariaLabel}"
                 style="width: ${this.getPercentage()}%; border-radius: ${this.config.borderRadius};">
                ${this.renderLabel()}
            </div>
        `;

        this.progressBarElement = this.element.querySelector('.eco-progress-bar');
        
        if (this.config.striped) {
            this.progressBarElement.classList.add('striped');
        }
        if (this.config.animated) {
            this.progressBarElement.classList.add('animated');
        }
    }

    /**
     * Renderizar la etiqueta de la barra
     */
    renderLabel() {
        if (this.config.label) {
            return `<span class="progress-label">${this.config.label}</span>`;
        }
        if (this.config.showPercentage) {
            return `<span class="progress-percentage">${this.getPercentage()}%</span>`;
        }
        return '';
    }

    /**
     * Obtener el valor porcentual
     */
    getPercentage() {
        const percentage = (this.state.currentValue / this.config.max) * 100;
        return Math.max(0, Math.min(100, Math.round(percentage))); // Asegurar entre 0 y 100
    }

    /**
     * Actualizar la barra de progreso
     * @param {number} newValue - Nuevo valor (opcional)
     */
    update(newValue = null) {
        if (newValue !== null) {
            this.state.currentValue = Number(newValue);
        }

        const percentage = this.getPercentage();
        
        if (this.progressBarElement) {
            this.progressBarElement.style.width = `${percentage}%`;
            this.progressBarElement.setAttribute('aria-valuenow', percentage);

            const labelElement = this.progressBarElement.querySelector('.progress-label');
            const percentageElement = this.progressBarElement.querySelector('.progress-percentage');

            if (labelElement && this.config.label) {
                labelElement.textContent = this.config.label;
            }
            if (percentageElement && this.config.showPercentage) {
                percentageElement.textContent = `${percentage}%`;
            }
        }

        // Verificar si se completó
        if (percentage >= 100 && !this.state.isComplete) {
            this.state.isComplete = true;
            if (this.config.onComplete) {
                this.config.onComplete(this);
            }
            this.element.classList.add('completed');
        } else if (percentage < 100 && this.state.isComplete) {
            this.state.isComplete = false;
            this.element.classList.remove('completed');
        }

        // Callback de cambio
        if (this.config.onChange && newValue !== null) {
            this.config.onChange(this.state.currentValue, percentage, this);
        }
    }

    /**
     * Establecer un nuevo valor
     * @param {number} value - Nuevo valor
     */
    setValue(value) {
        this.update(value);
    }

    /**
     * Obtener valor actual
     * @return {number} Valor actual
     */
    getValue() {
        return this.state.currentValue;
    }

    /**
     * Establecer tipo de barra (color)
     * @param {string} type - Nuevo tipo (default, success, etc.)
     */
    setType(type) {
        if (this.progressBarElement) {
            this.progressBarElement.className = `eco-progress-bar progress-bar-${type}`;
            if (this.config.striped) this.progressBarElement.classList.add('striped');
            if (this.config.animated) this.progressBarElement.classList.add('animated');
        }
        this.config.type = type;
    }

    /**
     * Establecer etiqueta
     * @param {string} label - Nueva etiqueta
     */
    setLabel(label) {
        this.config.label = label;
        this.config.showPercentage = !label; // Ocultar porcentaje si hay etiqueta
        this.update();
    }

    /**
     * Manejo de errores
     */
    handleError(error) {
        this.element.innerHTML = `<div class="eco-progress-bar-error">Error: ${error.message}</div>`;
    }

    /**
     * Limpieza
     */
    destroy() {
        this.element.innerHTML = '';
        this.element.classList.remove('eco-progress-bar-container', `theme-${this.config.theme}`);
        console.log('📊 EcoProgressBar destroyed for element:', this.element);
    }
}

// CSS básico para la barra de progreso (se puede mejorar y mover a un archivo .css)
const progressBarCSS = `
    .eco-progress-bar-container {
        background-color: #e9ecef;
        border-radius: 0.25rem;
        overflow: hidden;
        width: 100%;
    }
    .eco-progress-bar-container.theme-dark {
        background-color: #495057;
    }
    .eco-progress-bar {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 0.75rem;
        font-weight: 500;
        transition: width 0.6s ease;
        text-align: center;
        white-space: nowrap;
    }
    .eco-progress-bar.progress-bar-default { background-color: #007bff; }
    .eco-progress-bar.progress-bar-success { background-color: #28a745; }
    .eco-progress-bar.progress-bar-warning { background-color: #ffc107; color: #212529; }
    .eco-progress-bar.progress-bar-danger  { background-color: #dc3545; }
    .eco-progress-bar.progress-bar-info    { background-color: #17a2b8; }

    .eco-progress-bar.striped {
        background-image: linear-gradient(45deg, rgba(255,255,255,.15) 25%, transparent 25%, transparent 50%, rgba(255,255,255,.15) 50%, rgba(255,255,255,.15) 75%, transparent 75%, transparent);
        background-size: 1rem 1rem;
    }
    .eco-progress-bar.animated {
        animation: eco-progress-bar-stripes 1s linear infinite;
    }
    @keyframes eco-progress-bar-stripes {
        from { background-position: 1rem 0; }
        to { background-position: 0 0; }
    }
    .eco-progress-bar-error {
        color: red;
        padding: 10px;
        text-align: center;
    }
    .progress-label, .progress-percentage {
        padding: 0 5px;
    }
`;

// Inyectar CSS si no existe
if (!document.getElementById('eco-progress-bar-styles')) {
    const style = document.createElement('style');
    style.id = 'eco-progress-bar-styles';
    style.textContent = progressBarCSS;
    document.head.appendChild(style);
}

// Exportar para uso global si es necesario
window.EcoProgressBar = EcoProgressBar;
export default EcoProgressBar;