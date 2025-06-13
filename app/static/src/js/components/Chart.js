/**
 * Chart Component
 * Sistema completo de gráficos para el ecosistema de emprendimiento
 * Soporta múltiples tipos, tiempo real, exportación y análisis avanzado
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class EcoChart {
    constructor(element, options = {}) {
        // Verificar dependencias
        if (typeof Chart === 'undefined') {
            throw new Error('Chart.js is required but not loaded');
        }

        this.element = typeof element === 'string' ? document.getElementById(element) : element;
        if (!this.element) {
            throw new Error('Chart element not found');
        }

        this.config = {
            // Configuración básica
            type: options.type || 'line',
            theme: options.theme || 'light',
            responsive: options.responsive !== false,
            maintainAspectRatio: options.maintainAspectRatio !== false,
            
            // Datos
            data: options.data || null,
            dataUrl: options.dataUrl || null,
            refreshInterval: options.refreshInterval || 0,
            
            // Animaciones
            animation: options.animation !== false,
            animationDuration: options.animationDuration || 750,
            animationEasing: options.animationEasing || 'easeOutQuart',
            
            // Interactividad
            interactive: options.interactive !== false,
            tooltip: options.tooltip !== false,
            legend: options.legend !== false,
            zoom: options.zoom || false,
            pan: options.pan || false,
            
            // Exportación
            exportable: options.exportable !== false,
            downloadFormats: options.downloadFormats || ['png', 'pdf', 'csv'],
            
            // Tiempo real
            realTime: options.realTime || false,
            webSocketUrl: options.webSocketUrl || null,
            
            // Personalización específica del ecosistema
            ecosystem: {
                showProgress: options.ecosystem?.showProgress || false,
                showTargets: options.ecosystem?.showTargets || false,
                showTrends: options.ecosystem?.showTrends || false,
                showComparisons: options.ecosystem?.showComparisons || false,
                userRole: options.ecosystem?.userRole || 'user',
                context: options.ecosystem?.context || 'general' // entrepreneur, mentor, admin, client
            },
            
            // Callbacks
            onDataUpdate: options.onDataUpdate || null,
            onPointClick: options.onPointClick || null,
            onExport: options.onExport || null,
            onError: options.onError || null,
            
            // Opciones específicas de Chart.js
            chartOptions: options.chartOptions || {},
            
            ...options
        };

        this.state = {
            chart: null,
            data: null,
            isLoading: false,
            lastUpdate: null,
            refreshTimer: null,
            socket: null,
            filters: {},
            zoom: { enabled: false, level: 1 },
            annotations: [],
            customMetrics: new Map()
        };

        this.templates = new Map();
        this.themes = new Map();
        this.eventListeners = [];
        this.plugins = [];

        this.init();
    }

    /**
     * Inicialización del componente
     */
    async init() {
        try {
            this.setupThemes();
            this.setupTemplates();
            this.setupPlugins();
            this.setupEventListeners();
            
            if (this.config.data) {
                await this.createChart(this.config.data);
            } else if (this.config.dataUrl) {
                await this.loadData();
            }
            
            if (this.config.realTime) {
                this.initializeRealTime();
            }
            
            if (this.config.refreshInterval > 0) {
                this.startAutoRefresh();
            }
            
            console.log('✅ EcoChart initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing EcoChart:', error);
            this.handleError(error);
        }
    }

    /**
     * Configurar temas
     */
    setupThemes() {
        // Tema claro
        this.themes.set('light', {
            backgroundColor: '#ffffff',
            textColor: '#333333',
            gridColor: '#e0e0e0',
            borderColor: '#cccccc',
            colors: [
                '#007bff', '#28a745', '#ffc107', '#dc3545', 
                '#6f42c1', '#fd7e14', '#20c997', '#6c757d'
            ],
            gradient: {
                primary: ['#007bff', '#0056b3'],
                success: ['#28a745', '#1e7e34'],
                warning: ['#ffc107', '#d39e00'],
                danger: ['#dc3545', '#bd2130']
            }
        });

        // Tema oscuro
        this.themes.set('dark', {
            backgroundColor: '#2c3e50',
            textColor: '#ecf0f1',
            gridColor: '#34495e',
            borderColor: '#7f8c8d',
            colors: [
                '#3498db', '#2ecc71', '#f1c40f', '#e74c3c',
                '#9b59b6', '#e67e22', '#1abc9c', '#95a5a6'
            ],
            gradient: {
                primary: ['#3498db', '#2980b9'],
                success: ['#2ecc71', '#27ae60'],
                warning: ['#f1c40f', '#d68910'],
                danger: ['#e74c3c', '#c0392b']
            }
        });

        // Tema ecosistema (colores corporativos)
        this.themes.set('ecosystem', {
            backgroundColor: '#f8f9fa',
            textColor: '#2c3e50',
            gridColor: '#dee2e6',
            borderColor: '#adb5bd',
            colors: [
                '#00d4aa', '#ff6b6b', '#4ecdc4', '#45b7d1',
                '#96ceb4', '#ffeaa7', '#dda0dd', '#98d8c8'
            ],
            gradient: {
                primary: ['#00d4aa', '#00a085'],
                success: ['#4ecdc4', '#45b7d1'],
                warning: ['#ffeaa7', '#fdcb6e'],
                danger: ['#ff6b6b', '#fd79a8']
            }
        });
    }

    /**
     * Configurar plantillas específicas del ecosistema
     */
    setupTemplates() {
        // Template para progreso de emprendedores
        this.templates.set('entrepreneur_progress', {
            type: 'radar',
            options: {
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 20,
                            callback: (value) => `${value}%`
                        }
                    }
                },
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${context.parsed.r}%`
                        }
                    }
                }
            }
        });

        // Template para métricas de mentoría
        this.templates.set('mentorship_metrics', {
            type: 'line',
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Horas de Mentoría' }
                    },
                    x: {
                        title: { display: true, text: 'Período' }
                    }
                },
                elements: {
                    line: { tension: 0.4 },
                    point: { radius: 6, hoverRadius: 8 }
                }
            }
        });

        // Template para distribución de sectores
        this.templates.set('sector_distribution', {
            type: 'doughnut',
            options: {
                cutout: '60%',
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });

        // Template para análisis de impacto
        this.templates.set('impact_analysis', {
            type: 'bar',
            options: {
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Puntuación de Impacto' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Template para comparativa de rendimiento
        this.templates.set('performance_comparison', {
            type: 'line',
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Rendimiento' }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: { position: 'top' }
                }
            }
        });

        // Template para dashboard ejecutivo
        this.templates.set('executive_dashboard', {
            type: 'line',
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.1)' }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                elements: {
                    line: { borderWidth: 3 },
                    point: { radius: 4 }
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { mode: 'index', intersect: false }
                }
            }
        });
    }

    /**
     * Configurar plugins personalizados
     */
    setupPlugins() {
        // Plugin para mostrar objetivos/metas
        this.plugins.push({
            id: 'targetLines',
            beforeDraw: (chart) => {
                if (!this.config.ecosystem.showTargets || !chart.options.targets) return;

                const ctx = chart.ctx;
                const chartArea = chart.chartArea;
                
                chart.options.targets.forEach(target => {
                    ctx.save();
                    ctx.strokeStyle = target.color || '#ff6b6b';
                    ctx.lineWidth = target.width || 2;
                    ctx.setLineDash(target.dash || [5, 5]);
                    
                    const yPixel = chart.scales.y.getPixelForValue(target.value);
                    
                    ctx.beginPath();
                    ctx.moveTo(chartArea.left, yPixel);
                    ctx.lineTo(chartArea.right, yPixel);
                    ctx.stroke();
                    
                    // Etiqueta del objetivo
                    if (target.label) {
                        ctx.fillStyle = target.color || '#ff6b6b';
                        ctx.font = '12px Arial';
                        ctx.fillText(target.label, chartArea.right - 60, yPixel - 5);
                    }
                    
                    ctx.restore();
                });
            }
        });

        // Plugin para mostrar tendencias
        this.plugins.push({
            id: 'trendLines',
            beforeDraw: (chart) => {
                if (!this.config.ecosystem.showTrends) return;

                // Calcular y dibujar líneas de tendencia
                chart.data.datasets.forEach((dataset, datasetIndex) => {
                    if (dataset.showTrend !== false && dataset.data.length > 1) {
                        const trend = this.calculateTrend(dataset.data);
                        this.drawTrendLine(chart, trend, datasetIndex);
                    }
                });
            }
        });

        // Plugin para anotaciones personalizadas
        this.plugins.push({
            id: 'customAnnotations',
            afterDatasetsDraw: (chart) => {
                this.state.annotations.forEach(annotation => {
                    this.drawAnnotation(chart, annotation);
                });
            }
        });

        // Plugin para métricas en tiempo real
        this.plugins.push({
            id: 'realTimeMetrics',
            afterUpdate: (chart) => {
                if (this.config.realTime) {
                    this.updateRealTimeIndicators(chart);
                }
            }
        });
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        // Resize observer para responsive
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                if (this.state.chart) {
                    this.state.chart.resize();
                }
            });
            this.resizeObserver.observe(this.element);
        }

        // Eventos de teclado para accesibilidad
        this.element.addEventListener('keydown', (e) => {
            this.handleKeyboardNavigation(e);
        });

        // Eventos de mouse para interactividad
        this.element.addEventListener('contextmenu', (e) => {
            if (this.config.exportable) {
                e.preventDefault();
                this.showContextMenu(e);
            }
        });
    }

    /**
     * Crear gráfico
     */
    async createChart(data) {
        try {
            this.state.isLoading = true;
            this.showLoading();

            // Procesar datos
            const processedData = await this.processData(data);
            
            // Obtener configuración del template si existe
            const template = this.templates.get(this.config.type);
            
            // Configurar opciones del gráfico
            const chartConfig = {
                type: template?.type || this.config.type,
                data: processedData,
                options: this.buildChartOptions(template?.options),
                plugins: this.plugins
            };

            // Crear el gráfico
            this.state.chart = new Chart(this.element, chartConfig);
            this.state.data = processedData;
            this.state.lastUpdate = new Date();

            // Configurar interactividad
            this.setupInteractivity();
            
            // Aplicar tema
            this.applyTheme(this.config.theme);

            this.hideLoading();
            this.state.isLoading = false;

        } catch (error) {
            this.state.isLoading = false;
            this.hideLoading();
            throw error;
        }
    }

    /**
     * Procesar datos según el contexto del ecosistema
     */
    async processData(rawData) {
        let processedData = { ...rawData };

        // Aplicar filtros si existen
        if (Object.keys(this.state.filters).length > 0) {
            processedData = this.applyFilters(processedData, this.state.filters);
        }

        // Agregar métricas personalizadas según el rol del usuario
        switch (this.config.ecosystem.userRole) {
            case 'entrepreneur':
                processedData = this.addEntrepreneurMetrics(processedData);
                break;
            case 'mentor':
                processedData = this.addMentorMetrics(processedData);
                break;
            case 'admin':
                processedData = this.addAdminMetrics(processedData);
                break;
            case 'client':
                processedData = this.addClientMetrics(processedData);
                break;
        }

        // Calcular tendencias si está habilitado
        if (this.config.ecosystem.showTrends) {
            processedData = this.addTrendData(processedData);
        }

        // Agregar datos de comparación si está habilitado
        if (this.config.ecosystem.showComparisons) {
            processedData = await this.addComparisonData(processedData);
        }

        return processedData;
    }

    /**
     * Construir opciones del gráfico
     */
    buildChartOptions(templateOptions = {}) {
        const theme = this.themes.get(this.config.theme);
        
        const baseOptions = {
            responsive: this.config.responsive,
            maintainAspectRatio: this.config.maintainAspectRatio,
            
            animation: this.config.animation ? {
                duration: this.config.animationDuration,
                easing: this.config.animationEasing,
                onComplete: () => {
                    if (this.config.onDataUpdate) {
                        this.config.onDataUpdate(this.state.chart);
                    }
                }
            } : false,

            plugins: {
                legend: {
                    display: this.config.legend,
                    position: 'top',
                    labels: {
                        color: theme.textColor,
                        usePointStyle: true,
                        padding: 20
                    }
                },
                
                tooltip: {
                    enabled: this.config.tooltip,
                    backgroundColor: theme.backgroundColor,
                    titleColor: theme.textColor,
                    bodyColor: theme.textColor,
                    borderColor: theme.borderColor,
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        title: (tooltipItems) => {
                            return this.formatTooltipTitle(tooltipItems);
                        },
                        label: (context) => {
                            return this.formatTooltipLabel(context);
                        },
                        afterBody: (tooltipItems) => {
                            return this.addTooltipInsights(tooltipItems);
                        }
                    }
                }
            },

            scales: this.buildScales(theme),
            
            interaction: {
                intersect: false,
                mode: 'index'
            },

            onClick: (event, elements) => {
                if (elements.length > 0 && this.config.onPointClick) {
                    const element = elements[0];
                    const dataPoint = this.getDataPoint(element);
                    this.config.onPointClick(dataPoint, event);
                }
            },

            onHover: (event, elements) => {
                this.element.style.cursor = elements.length > 0 ? 'pointer' : 'default';
            }
        };

        // Merge con opciones del template y configuración personalizada
        return this.deepMerge(baseOptions, templateOptions, this.config.chartOptions);
    }

    /**
     * Construir escalas según el tema
     */
    buildScales(theme) {
        const scales = {};

        // Escala Y
        scales.y = {
            beginAtZero: true,
            grid: {
                color: theme.gridColor,
                lineWidth: 1
            },
            ticks: {
                color: theme.textColor,
                callback: (value) => this.formatAxisValue(value, 'y')
            },
            title: {
                display: false,
                color: theme.textColor
            }
        };

        // Escala X
        scales.x = {
            grid: {
                color: theme.gridColor,
                lineWidth: 1
            },
            ticks: {
                color: theme.textColor,
                callback: (value, index) => this.formatAxisValue(value, 'x', index)
            },
            title: {
                display: false,
                color: theme.textColor
            }
        };

        return scales;
    }

    /**
     * Cargar datos desde URL
     */
    async loadData(url = null) {
        try {
            this.state.isLoading = true;
            this.showLoading();

            const dataUrl = url || this.config.dataUrl;
            const response = await fetch(dataUrl, {
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (this.state.chart) {
                await this.updateChart(data);
            } else {
                await this.createChart(data);
            }

        } catch (error) {
            console.error('Error loading chart data:', error);
            this.handleError(error);
        } finally {
            this.state.isLoading = false;
            this.hideLoading();
        }
    }

    /**
     * Actualizar gráfico con nuevos datos
     */
    async updateChart(newData) {
        if (!this.state.chart) return;

        const processedData = await this.processData(newData);
        
        // Actualizar datos
        this.state.chart.data = processedData;
        this.state.data = processedData;
        this.state.lastUpdate = new Date();
        
        // Animar la actualización
        this.state.chart.update('active');
        
        // Callback
        if (this.config.onDataUpdate) {
            this.config.onDataUpdate(this.state.chart);
        }
    }

    /**
     * Aplicar tema visual
     */
    applyTheme(themeName) {
        const theme = this.themes.get(themeName);
        if (!theme || !this.state.chart) return;

        // Actualizar colores de los datasets
        this.state.chart.data.datasets.forEach((dataset, index) => {
            if (!dataset.backgroundColor || dataset.backgroundColor === 'auto') {
                dataset.backgroundColor = this.createGradient(
                    theme.colors[index % theme.colors.length],
                    0.2
                );
            }
            
            if (!dataset.borderColor || dataset.borderColor === 'auto') {
                dataset.borderColor = theme.colors[index % theme.colors.length];
            }
        });

        // Actualizar opciones del gráfico
        const options = this.state.chart.options;
        
        if (options.plugins.legend) {
            options.plugins.legend.labels.color = theme.textColor;
        }
        
        if (options.scales) {
            Object.keys(options.scales).forEach(scaleKey => {
                const scale = options.scales[scaleKey];
                if (scale.grid) scale.grid.color = theme.gridColor;
                if (scale.ticks) scale.ticks.color = theme.textColor;
                if (scale.title) scale.title.color = theme.textColor;
            });
        }

        this.state.chart.update();
    }

    /**
     * Crear gradientes
     */
    createGradient(color, opacity = 0.2) {
        const canvas = this.element;
        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
        
        gradient.addColorStop(0, color + Math.floor(opacity * 255).toString(16).padStart(2, '0'));
        gradient.addColorStop(1, color + '00');
        
        return gradient;
    }

    /**
     * Configurar interactividad
     */
    setupInteractivity() {
        if (!this.config.interactive || !this.state.chart) return;

        // Zoom
        if (this.config.zoom) {
            this.enableZoom();
        }

        // Pan
        if (this.config.pan) {
            this.enablePan();
        }

        // Selección de datos
        this.enableDataSelection();
    }

    /**
     * Habilitar zoom
     */
    enableZoom() {
        this.element.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
                this.zoomChart(zoomFactor);
            }
        });
    }

    /**
     * Hacer zoom en el gráfico
     */
    zoomChart(factor) {
        this.state.zoom.level *= factor;
        this.state.zoom.level = Math.max(0.5, Math.min(5, this.state.zoom.level));
        
        // Aplicar zoom a las escalas
        const scales = this.state.chart.options.scales;
        Object.keys(scales).forEach(scaleKey => {
            const scale = scales[scaleKey];
            if (scale.min !== undefined && scale.max !== undefined) {
                const range = scale.max - scale.min;
                const center = (scale.max + scale.min) / 2;
                const newRange = range / this.state.zoom.level;
                
                scale.min = center - newRange / 2;
                scale.max = center + newRange / 2;
            }
        });
        
        this.state.chart.update();
    }

    /**
     * Inicializar tiempo real
     */
    initializeRealTime() {
        if (!this.config.webSocketUrl) return;

        try {
            if (typeof io !== 'undefined') {
                this.state.socket = io(this.config.webSocketUrl);
                
                this.state.socket.on('chartUpdate', (data) => {
                    this.handleRealTimeUpdate(data);
                });
                
                this.state.socket.on('connect', () => {
                    console.log('Chart WebSocket connected');
                });
                
            } else {
                console.warn('Socket.IO not available for real-time updates');
            }
        } catch (error) {
            console.error('Error initializing real-time updates:', error);
        }
    }

    /**
     * Manejar actualizaciones en tiempo real
     */
    handleRealTimeUpdate(data) {
        if (!this.state.chart) return;

        // Agregar nuevo punto de datos
        if (data.newPoint) {
            this.addDataPoint(data.newPoint);
        }
        
        // Actualizar punto existente
        if (data.updatePoint) {
            this.updateDataPoint(data.updatePoint);
        }
        
        // Reemplazar todos los datos
        if (data.replaceData) {
            this.updateChart(data.replaceData);
        }
        
        // Mantener solo los últimos N puntos para rendimiento
        this.limitDataPoints(100);
    }

    /**
     * Agregar punto de datos
     */
    addDataPoint(pointData) {
        const { datasetIndex = 0, label, value } = pointData;
        
        this.state.chart.data.labels.push(label);
        this.state.chart.data.datasets[datasetIndex].data.push(value);
        
        this.state.chart.update('none');
    }

    /**
     * Limitar puntos de datos para rendimiento
     */
    limitDataPoints(maxPoints) {
        const data = this.state.chart.data;
        
        if (data.labels.length > maxPoints) {
            data.labels.splice(0, data.labels.length - maxPoints);
            
            data.datasets.forEach(dataset => {
                dataset.data.splice(0, dataset.data.length - maxPoints);
            });
        }
    }

    /**
     * Métodos específicos del ecosistema
     */
    
    // Métricas para emprendedores
    addEntrepreneurMetrics(data) {
        // Agregar métricas de progreso, hitos, etc.
        if (this.config.ecosystem.showProgress) {
            data.progress = this.calculateProgress(data);
        }
        
        return data;
    }

    // Métricas para mentores
    addMentorMetrics(data) {
        // Agregar métricas de mentoría, emprendedores asignados, etc.
        if (this.state.customMetrics.has('mentorship_hours')) {
            data.mentorshipHours = this.state.customMetrics.get('mentorship_hours');
        }
        
        return data;
    }

    // Métricas para administradores
    addAdminMetrics(data) {
        // Agregar métricas administrativas, KPIs, etc.
        data.kpis = {
            totalUsers: data.totalUsers || 0,
            activeProjects: data.activeProjects || 0,
            completionRate: data.completionRate || 0
        };
        
        return data;
    }

    // Métricas para clientes
    addClientMetrics(data) {
        // Agregar métricas de impacto, ROI, etc.
        data.impact = {
            roi: data.roi || 0,
            socialImpact: data.socialImpact || 0,
            jobsCreated: data.jobsCreated || 0
        };
        
        return data;
    }

    /**
     * Exportación de gráficos
     */
    async exportChart(format = 'png', options = {}) {
        if (!this.state.chart) return null;

        try {
            let exportData;
            
            switch (format.toLowerCase()) {
                case 'png':
                case 'jpg':
                case 'jpeg':
                    exportData = this.exportAsImage(format, options);
                    break;
                case 'pdf':
                    exportData = await this.exportAsPDF(options);
                    break;
                case 'csv':
                    exportData = this.exportAsCSV(options);
                    break;
                case 'json':
                    exportData = this.exportAsJSON(options);
                    break;
                default:
                    throw new Error(`Unsupported export format: ${format}`);
            }
            
            // Callback de exportación
            if (this.config.onExport) {
                this.config.onExport(format, exportData);
            }
            
            return exportData;
            
        } catch (error) {
            console.error('Error exporting chart:', error);
            this.handleError(error);
            return null;
        }
    }

    /**
     * Exportar como imagen
     */
    exportAsImage(format, options = {}) {
        const canvas = this.state.chart.canvas;
        const filename = options.filename || `chart_${Date.now()}.${format}`;
        
        // Crear enlace de descarga
        const link = document.createElement('a');
        link.download = filename;
        link.href = canvas.toDataURL(`image/${format}`, options.quality || 0.9);
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        return link.href;
    }

    /**
     * Exportar como PDF
     */
    async exportAsPDF(options = {}) {
        // Requiere jsPDF
        if (typeof jsPDF === 'undefined') {
            throw new Error('jsPDF library is required for PDF export');
        }
        
        const canvas = this.state.chart.canvas;
        const imgData = canvas.toDataURL('image/png');
        
        const pdf = new jsPDF(options.orientation || 'landscape');
        const imgWidth = options.width || 280;
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        
        // Agregar título si se proporciona
        if (options.title) {
            pdf.setFontSize(16);
            pdf.text(options.title, 20, 20);
            pdf.addImage(imgData, 'PNG', 20, 30, imgWidth, imgHeight);
        } else {
            pdf.addImage(imgData, 'PNG', 20, 20, imgWidth, imgHeight);
        }
        
        // Agregar metadatos
        if (options.metadata) {
            let yPosition = options.title ? 30 + imgHeight + 20 : 20 + imgHeight + 20;
            
            pdf.setFontSize(10);
            Object.entries(options.metadata).forEach(([key, value]) => {
                pdf.text(`${key}: ${value}`, 20, yPosition);
                yPosition += 10;
            });
        }
        
        const filename = options.filename || `chart_${Date.now()}.pdf`;
        pdf.save(filename);
        
        return pdf.output('datauristring');
    }

    /**
     * Exportar como CSV
     */
    exportAsCSV(options = {}) {
        const data = this.state.chart.data;
        let csv = '';
        
        // Headers
        const headers = ['Label'];
        data.datasets.forEach(dataset => {
            headers.push(dataset.label || 'Dataset');
        });
        csv += headers.join(',') + '\n';
        
        // Data rows
        data.labels.forEach((label, index) => {
            const row = [label];
            data.datasets.forEach(dataset => {
                row.push(dataset.data[index] || '');
            });
            csv += row.join(',') + '\n';
        });
        
        // Crear y descargar archivo
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const filename = options.filename || `chart_data_${Date.now()}.csv`;
        
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        return csv;
    }

    /**
     * Exportar como JSON
     */
    exportAsJSON(options = {}) {
        const exportData = {
            type: this.config.type,
            data: this.state.chart.data,
            options: this.state.chart.options,
            timestamp: new Date().toISOString(),
            metadata: {
                userRole: this.config.ecosystem.userRole,
                context: this.config.ecosystem.context,
                theme: this.config.theme
            }
        };
        
        const jsonString = JSON.stringify(exportData, null, 2);
        
        // Crear y descargar archivo
        const blob = new Blob([jsonString], { type: 'application/json' });
        const link = document.createElement('a');
        const filename = options.filename || `chart_config_${Date.now()}.json`;
        
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        return exportData;
    }

    /**
     * Métodos de filtrado
     */
    addFilter(key, value) {
        this.state.filters[key] = value;
        if (this.state.data) {
            this.updateChart(this.state.data);
        }
    }

    removeFilter(key) {
        delete this.state.filters[key];
        if (this.state.data) {
            this.updateChart(this.state.data);
        }
    }

    clearFilters() {
        this.state.filters = {};
        if (this.state.data) {
            this.updateChart(this.state.data);
        }
    }

    /**
     * Utilidades
     */
    formatAxisValue(value, axis, index = null) {
        if (axis === 'y' && typeof value === 'number') {
            // Formatear números grandes
            if (value >= 1000000) {
                return (value / 1000000).toFixed(1) + 'M';
            } else if (value >= 1000) {
                return (value / 1000).toFixed(1) + 'K';
            }
            return value.toString();
        }
        
        return value;
    }

    formatTooltipLabel(context) {
        const dataset = context.dataset;
        const value = context.parsed.y || context.parsed;
        
        let label = dataset.label || '';
        if (label) label += ': ';
        
        // Formatear según el contexto
        if (this.config.ecosystem.context === 'financial') {
            label += '$' + this.formatCurrency(value);
        } else if (this.config.ecosystem.context === 'percentage') {
            label += value + '%';
        } else {
            label += this.formatNumber(value);
        }
        
        return label;
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('es-ES', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount);
    }

    formatNumber(num) {
        return new Intl.NumberFormat('es-ES').format(num);
    }

    calculateTrend(data) {
        if (data.length < 2) return null;
        
        const n = data.length;
        let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
        
        for (let i = 0; i < n; i++) {
            sumX += i;
            sumY += data[i];
            sumXY += i * data[i];
            sumXX += i * i;
        }
        
        const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;
        
        return { slope, intercept };
    }

    deepMerge(target, ...sources) {
        if (!sources.length) return target;
        const source = sources.shift();
        
        if (this.isObject(target) && this.isObject(source)) {
            for (const key in source) {
                if (this.isObject(source[key])) {
                    if (!target[key]) Object.assign(target, { [key]: {} });
                    this.deepMerge(target[key], source[key]);
                } else {
                    Object.assign(target, { [key]: source[key] });
                }
            }
        }
        
        return this.deepMerge(target, ...sources);
    }

    isObject(item) {
        return item && typeof item === 'object' && !Array.isArray(item);
    }

    showLoading() {
        const loader = document.createElement('div');
        loader.className = 'chart-loader';
        loader.innerHTML = `
            <div class="loader-spinner"></div>
            <div class="loader-text">Cargando gráfico...</div>
        `;
        
        this.element.appendChild(loader);
    }

    hideLoading() {
        const loader = this.element.querySelector('.chart-loader');
        if (loader) {
            loader.remove();
        }
    }

    handleError(error) {
        console.error('Chart error:', error);
        
        if (this.config.onError) {
            this.config.onError(error);
        }
        
        // Mostrar mensaje de error en el elemento
        this.element.innerHTML = `
            <div class="chart-error">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>Error al cargar el gráfico</h4>
                <p>${error.message}</p>
                <button onclick="this.parentElement.parentElement.ecoChart.retry()" class="btn btn-primary btn-sm">
                    Reintentar
                </button>
            </div>
        `;
    }

    retry() {
        this.element.innerHTML = '';
        this.init();
    }

    getCSRFToken() {
        return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }

    /**
     * Auto-refresh
     */
    startAutoRefresh() {
        if (this.state.refreshTimer) {
            clearInterval(this.state.refreshTimer);
        }
        
        this.state.refreshTimer = setInterval(() => {
            if (!this.state.isLoading) {
                this.loadData();
            }
        }, this.config.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.state.refreshTimer) {
            clearInterval(this.state.refreshTimer);
            this.state.refreshTimer = null;
        }
    }

    /**
     * API pública
     */
    refresh() {
        return this.loadData();
    }

    setTheme(themeName) {
        this.config.theme = themeName;
        this.applyTheme(themeName);
    }

    addAnnotation(annotation) {
        this.state.annotations.push(annotation);
        if (this.state.chart) {
            this.state.chart.update();
        }
    }

    setCustomMetric(key, value) {
        this.state.customMetrics.set(key, value);
    }

    getChart() {
        return this.state.chart;
    }

    getData() {
        return this.state.data;
    }

    /**
     * Cleanup
     */
    destroy() {
        // Detener auto-refresh
        this.stopAutoRefresh();
        
        // Cerrar WebSocket
        if (this.state.socket) {
            this.state.socket.disconnect();
        }
        
        // Destruir gráfico
        if (this.state.chart) {
            this.state.chart.destroy();
        }
        
        // Remover event listeners
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        
        // Desconectar resize observer
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        
        console.log('🧹 EcoChart destroyed');
    }
}

// CSS personalizado para los gráficos
const chartCSS = `
    .chart-loader {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        text-align: center;
        z-index: 1000;
    }
    
    .loader-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #007bff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 10px;
    }
    
    .loader-text {
        color: #666;
        font-size: 14px;
    }
    
    .chart-error {
        text-align: center;
        padding: 40px 20px;
        color: #666;
    }
    
    .chart-error i {
        font-size: 48px;
        color: #dc3545;
        margin-bottom: 15px;
    }
    
    .chart-error h4 {
        margin-bottom: 10px;
        color: #333;
    }
    
    .chart-error p {
        margin-bottom: 20px;
        font-size: 14px;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .chart-container {
        position: relative;
        height: 400px;
        width: 100%;
    }
    
    .chart-controls {
        margin-bottom: 15px;
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
    }
    
    .chart-export-btn {
        background: none;
        border: 1px solid #ddd;
        padding: 5px 10px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
    }
    
    .chart-export-btn:hover {
        background: #f8f9fa;
    }
    
    .chart-legend-custom {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        margin-top: 15px;
        justify-content: center;
    }
    
    .chart-legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 12px;
    }
    
    .chart-legend-color {
        width: 12px;
        height: 12px;
        border-radius: 2px;
    }
    
    @media (max-width: 768px) {
        .chart-controls {
            justify-content: center;
        }
        
        .chart-export-btn {
            font-size: 10px;
            padding: 4px 8px;
        }
    }
`;

// Inyectar CSS
if (!document.getElementById('eco-chart-styles')) {
    const style = document.createElement('style');
    style.id = 'eco-chart-styles';
    style.textContent = chartCSS;
    document.head.appendChild(style);
}

// Registrar en el elemento para acceso fácil
Object.defineProperty(EcoChart.prototype, 'register', {
    value: function() {
        this.element.ecoChart = this;
    }
});

// Auto-registro
const originalInit = EcoChart.prototype.init;
EcoChart.prototype.init = function() {
    const result = originalInit.call(this);
    this.register();
    return result;
};

// Factory methods para casos comunes
EcoChart.createEntrepreneurProgress = (element, data, options = {}) => {
    return new EcoChart(element, {
        type: 'entrepreneur_progress',
        data: data,
        ecosystem: { 
            userRole: 'entrepreneur',
            showProgress: true,
            showTargets: true
        },
        ...options
    });
};

EcoChart.createMentorshipMetrics = (element, data, options = {}) => {
    return new EcoChart(element, {
        type: 'mentorship_metrics',
        data: data,
        ecosystem: { 
            userRole: 'mentor',
            showTrends: true
        },
        realTime: true,
        ...options
    });
};

EcoChart.createSectorDistribution = (element, data, options = {}) => {
    return new EcoChart(element, {
        type: 'sector_distribution',
        data: data,
        ecosystem: { 
            context: 'admin',
            showComparisons: true
        },
        ...options
    });
};

EcoChart.createImpactAnalysis = (element, data, options = {}) => {
    return new EcoChart(element, {
        type: 'impact_analysis',
        data: data,
        ecosystem: { 
            userRole: 'client',
            context: 'impact'
        },
        ...options
    });
};

// Exportar
window.EcoChart = EcoChart;
export default EcoChart;