/**
 * Ecosistema Emprendimiento - Ally Reports Module
 * ===============================================
 * 
 * Módulo especializado de reportes para aliados/mentores
 * Incluye generación de reportes, análisis de métricas,
 * visualizaciones avanzadas y exportación de datos
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js, Chart.js
 */

'use strict';

/**
 * Módulo principal de reportes para aliados
 */
class AllyReports {
    constructor(container, app) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        this.app = app;
        this.main = app?.main || window.App;
        this.state = app?.state || window.EcosistemaStateManager;
        this.config = window.getConfig('modules.allyReports', {});

        // Configuración del módulo
        this.moduleConfig = {
            enableRealTimeUpdates: true,
            enableAutoRefresh: true,
            autoRefreshInterval: 300000, // 5 minutos
            enableExportFormats: ['pdf', 'excel', 'csv', 'json'],
            enableCustomReports: true,
            enableScheduledReports: true,
            maxDataPoints: 1000,
            defaultDateRange: 30, // días
            enableComparativeAnalysis: true,
            enablePredictiveAnalytics: false,
            chartAnimations: true,
            enableDrillDown: true,
            cacheReports: true,
            cacheTimeout: 600000 // 10 minutos
        };

        // Estado interno del módulo
        this.moduleState = {
            isInitialized: false,
            currentReport: null,
            selectedDateRange: {
                start: new Date(Date.now() - (30 * 24 * 60 * 60 * 1000)),
                end: new Date()
            },
            filters: {
                emprendedores: [],
                categorias: [],
                estados: [],
                tiposSesion: []
            },
            reports: new Map(),
            charts: new Map(),
            dataCache: new Map(),
            exportQueue: [],
            isGenerating: false,
            lastRefresh: null,
            autoRefreshTimer: null,
            selectedMentees: new Set(),
            comparisonMode: false,
            drillDownStack: []
        };

        // Tipos de reportes disponibles
        this.reportTypes = {
            overview: {
                name: 'Resumen General',
                icon: 'fa-chart-pie',
                description: 'Vista general de métricas de mentoría',
                sections: ['metrics', 'sessions', 'progress', 'satisfaction'],
                refreshInterval: 300000
            },
            mentees: {
                name: 'Emprendedores',
                icon: 'fa-users',
                description: 'Análisis detallado de emprendedores',
                sections: ['list', 'progress', 'engagement', 'outcomes'],
                refreshInterval: 600000
            },
            sessions: {
                name: 'Sesiones de Mentoría',
                icon: 'fa-handshake',
                description: 'Análisis de sesiones y su efectividad',
                sections: ['frequency', 'duration', 'topics', 'feedback'],
                refreshInterval: 300000
            },
            impact: {
                name: 'Análisis de Impacto',
                icon: 'fa-chart-line',
                description: 'Medición del impacto de la mentoría',
                sections: ['roi', 'success_rate', 'improvements', 'testimonials'],
                refreshInterval: 900000
            },
            performance: {
                name: 'Rendimiento Personal',
                icon: 'fa-award',
                description: 'Métricas de rendimiento del mentor',
                sections: ['efficiency', 'ratings', 'growth', 'goals'],
                refreshInterval: 600000
            },
            financial: {
                name: 'Análisis Financiero',
                icon: 'fa-dollar-sign',
                description: 'Impacto financiero y ROI de mentoría',
                sections: ['revenue', 'costs', 'roi', 'projections'],
                refreshInterval: 1800000
            },
            custom: {
                name: 'Reportes Personalizados',
                icon: 'fa-cog',
                description: 'Reportes configurables por el usuario',
                sections: ['builder', 'templates', 'saved'],
                refreshInterval: null
            }
        };

        // Referencias DOM
        this.elements = {};

        // Event listeners
        this.eventListeners = new Map();

        // Instancias de gráficos
        this.chartInstances = new Map();

        // Templates de reportes
        this.reportTemplates = new Map();

        // Inicializar
        this.init();
    }

    /**
     * Inicializar módulo
     */
    async init() {
        if (this.moduleState.isInitialized) return;

        try {
            console.log('📊 Inicializando Ally Reports');

            // Verificar permisos
            if (!this.hasPermissions()) {
                throw new Error('Usuario no tiene permisos para reportes');
            }

            // Crear estructura DOM
            this.createStructure();

            // Obtener referencias DOM
            this.bindElements();

            // Configurar eventos
            this.bindEvents();

            // Cargar templates de reportes
            this.loadReportTemplates();

            // Cargar datos iniciales
            await this.loadInitialData();

            // Configurar auto-refresh
            this.setupAutoRefresh();

            // Configurar estado reactivo
            this.setupReactiveState();

            // Cargar reporte por defecto
            await this.loadDefaultReport();

            // Marcar como inicializado
            this.moduleState.isInitialized = true;

            console.log('✅ Ally Reports inicializado');

        } catch (error) {
            console.error('❌ Error inicializando Ally Reports:', error);
            this.showError('Error inicializando reportes', error.message);
        }
    }

    /**
     * Verificar permisos del usuario
     */
    hasPermissions() {
        const userType = this.main.userType;
        const allowedTypes = ['mentor', 'admin'];
        
        return allowedTypes.includes(userType) || 
               this.main.currentUser?.permissions?.includes('ally_reports');
    }

    /**
     * Crear estructura DOM del módulo
     */
    createStructure() {
        if (!this.container) {
            throw new Error('Contenedor no encontrado para Ally Reports');
        }

        this.container.innerHTML = `
            <div class="ally-reports" data-module="ally-reports">
                <!-- Header del módulo -->
                <div class="reports-header">
                    <div class="header-left">
                        <h3 class="reports-title">
                            <i class="fa fa-chart-bar text-primary me-2"></i>
                            Reportes de Mentoría
                        </h3>
                        <div class="last-update">
                            <small class="text-muted">
                                <i class="fa fa-clock me-1"></i>
                                <span class="update-time">Nunca actualizado</span>
                            </small>
                        </div>
                    </div>
                    <div class="header-right">
                        <div class="header-actions">
                            <div class="date-range-selector">
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text">
                                        <i class="fa fa-calendar"></i>
                                    </span>
                                    <input type="date" class="form-control" data-input="date-start">
                                    <span class="input-group-text">a</span>
                                    <input type="date" class="form-control" data-input="date-end">
                                    <button class="btn btn-outline-primary" data-action="apply-date-range">
                                        Aplicar
                                    </button>
                                </div>
                            </div>
                            <div class="btn-group" role="group">
                                <button class="btn btn-sm btn-outline-secondary" 
                                        data-action="refresh-data" 
                                        title="Actualizar datos">
                                    <i class="fa fa-sync-alt"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-secondary" 
                                        data-action="toggle-comparison" 
                                        title="Modo comparación">
                                    <i class="fa fa-balance-scale"></i>
                                </button>
                                <div class="dropdown">
                                    <button class="btn btn-sm btn-outline-primary dropdown-toggle" 
                                            data-bs-toggle="dropdown">
                                        <i class="fa fa-download me-1"></i>
                                        Exportar
                                    </button>
                                    <ul class="dropdown-menu dropdown-menu-end">
                                        <li><a class="dropdown-item" data-action="export" data-format="pdf">
                                            <i class="fa fa-file-pdf me-2 text-danger"></i>PDF
                                        </a></li>
                                        <li><a class="dropdown-item" data-action="export" data-format="excel">
                                            <i class="fa fa-file-excel me-2 text-success"></i>Excel
                                        </a></li>
                                        <li><a class="dropdown-item" data-action="export" data-format="csv">
                                            <i class="fa fa-file-csv me-2 text-info"></i>CSV
                                        </a></li>
                                        <li><hr class="dropdown-divider"></li>
                                        <li><a class="dropdown-item" data-action="schedule-report">
                                            <i class="fa fa-clock me-2"></i>Programar envío
                                        </a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Navegación de reportes -->
                <div class="reports-navigation">
                    <div class="nav nav-pills" role="tablist">
                        <button class="nav-link active" 
                                data-bs-toggle="pill" 
                                data-bs-target="#overview-tab" 
                                data-report-type="overview">
                            <i class="fa fa-chart-pie me-2"></i>
                            Resumen
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#mentees-tab" 
                                data-report-type="mentees">
                            <i class="fa fa-users me-2"></i>
                            Emprendedores
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#sessions-tab" 
                                data-report-type="sessions">
                            <i class="fa fa-handshake me-2"></i>
                            Sesiones
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#impact-tab" 
                                data-report-type="impact">
                            <i class="fa fa-chart-line me-2"></i>
                            Impacto
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#performance-tab" 
                                data-report-type="performance">
                            <i class="fa fa-award me-2"></i>
                            Rendimiento
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#financial-tab" 
                                data-report-type="financial">
                            <i class="fa fa-dollar-sign me-2"></i>
                            Financiero
                        </button>
                        <button class="nav-link" 
                                data-bs-toggle="pill" 
                                data-bs-target="#custom-tab" 
                                data-report-type="custom">
                            <i class="fa fa-cog me-2"></i>
                            Personalizado
                        </button>
                    </div>
                </div>

                <!-- Filtros avanzados -->
                <div class="reports-filters">
                    <div class="filters-container">
                        <div class="row g-3">
                            <div class="col-md-3">
                                <label class="form-label small">Emprendedores</label>
                                <select class="form-select form-select-sm" 
                                        multiple 
                                        data-filter="emprendedores">
                                    <option value="">Todos</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <label class="form-label small">Categorías</label>
                                <select class="form-select form-select-sm" 
                                        multiple 
                                        data-filter="categorias">
                                    <option value="">Todas</option>
                                    <option value="technology">Tecnología</option>
                                    <option value="health">Salud</option>
                                    <option value="education">Educación</option>
                                    <option value="finance">Finanzas</option>
                                    <option value="sustainability">Sostenibilidad</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <label class="form-label small">Estados</label>
                                <select class="form-select form-select-sm" 
                                        multiple 
                                        data-filter="estados">
                                    <option value="">Todos</option>
                                    <option value="active">Activo</option>
                                    <option value="paused">Pausado</option>
                                    <option value="completed">Completado</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label small">Tipos de Sesión</label>
                                <select class="form-select form-select-sm" 
                                        multiple 
                                        data-filter="tiposSesion">
                                    <option value="">Todos</option>
                                    <option value="business">Negocio</option>
                                    <option value="technical">Técnica</option>
                                    <option value="marketing">Marketing</option>
                                    <option value="financial">Financiera</option>
                                    <option value="personal">Personal</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <label class="form-label small">&nbsp;</label>
                                <div class="d-flex gap-2">
                                    <button class="btn btn-sm btn-primary" 
                                            data-action="apply-filters">
                                        <i class="fa fa-filter me-1"></i>
                                        Filtrar
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary" 
                                            data-action="clear-filters">
                                        <i class="fa fa-times"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Contenido de reportes -->
                <div class="reports-content">
                    <div class="tab-content">
                        <!-- Tab de Resumen -->
                        <div class="tab-pane fade show active" id="overview-tab">
                            <div class="overview-report">
                                <!-- KPIs principales -->
                                <div class="kpi-cards mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-3">
                                            <div class="kpi-card card">
                                                <div class="card-body">
                                                    <div class="kpi-icon">
                                                        <i class="fa fa-users text-primary"></i>
                                                    </div>
                                                    <div class="kpi-content">
                                                        <h3 class="kpi-value" data-kpi="total-mentees">0</h3>
                                                        <p class="kpi-label">Emprendedores Activos</p>
                                                        <span class="kpi-trend positive">
                                                            <i class="fa fa-arrow-up"></i> +5%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="kpi-card card">
                                                <div class="card-body">
                                                    <div class="kpi-icon">
                                                        <i class="fa fa-handshake text-success"></i>
                                                    </div>
                                                    <div class="kpi-content">
                                                        <h3 class="kpi-value" data-kpi="total-sessions">0</h3>
                                                        <p class="kpi-label">Sesiones Realizadas</p>
                                                        <span class="kpi-trend positive">
                                                            <i class="fa fa-arrow-up"></i> +12%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="kpi-card card">
                                                <div class="card-body">
                                                    <div class="kpi-icon">
                                                        <i class="fa fa-clock text-warning"></i>
                                                    </div>
                                                    <div class="kpi-content">
                                                        <h3 class="kpi-value" data-kpi="total-hours">0h</h3>
                                                        <p class="kpi-label">Horas de Mentoría</p>
                                                        <span class="kpi-trend positive">
                                                            <i class="fa fa-arrow-up"></i> +8%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="kpi-card card">
                                                <div class="card-body">
                                                    <div class="kpi-icon">
                                                        <i class="fa fa-star text-info"></i>
                                                    </div>
                                                    <div class="kpi-content">
                                                        <h3 class="kpi-value" data-kpi="avg-rating">0.0</h3>
                                                        <p class="kpi-label">Calificación Promedio</p>
                                                        <span class="kpi-trend positive">
                                                            <i class="fa fa-arrow-up"></i> +0.3
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Gráficos principales -->
                                <div class="main-charts">
                                    <div class="row g-4">
                                        <div class="col-md-8">
                                            <div class="card">
                                                <div class="card-header d-flex justify-content-between align-items-center">
                                                    <h5 class="card-title mb-0">Actividad de Mentoría</h5>
                                                    <div class="chart-controls">
                                                        <div class="btn-group btn-group-sm" role="group">
                                                            <input type="radio" class="btn-check" name="chartPeriod" id="period-week" value="week">
                                                            <label class="btn btn-outline-primary" for="period-week">Semana</label>
                                                            
                                                            <input type="radio" class="btn-check" name="chartPeriod" id="period-month" value="month" checked>
                                                            <label class="btn btn-outline-primary" for="period-month">Mes</label>
                                                            
                                                            <input type="radio" class="btn-check" name="chartPeriod" id="period-quarter" value="quarter">
                                                            <label class="btn btn-outline-primary" for="period-quarter">Trimestre</label>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="activityChart" height="300"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Distribución por Categoría</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="categoryChart" height="300"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Métricas adicionales -->
                                <div class="additional-metrics mt-4">
                                    <div class="row g-4">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Progreso de Emprendedores</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="progressChart" height="200"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Satisfacción y Feedback</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="satisfactionChart" height="200"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab de Emprendedores -->
                        <div class="tab-pane fade" id="mentees-tab">
                            <div class="mentees-report">
                                <div class="mentees-summary mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4">
                                            <div class="summary-card">
                                                <h4 data-summary="active-mentees">0</h4>
                                                <p>Emprendedores Activos</p>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="summary-card">
                                                <h4 data-summary="new-mentees">0</h4>
                                                <p>Nuevos este Mes</p>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="summary-card">
                                                <h4 data-summary="graduated-mentees">0</h4>
                                                <p>Graduados</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="mentees-table-container">
                                    <div class="card">
                                        <div class="card-header d-flex justify-content-between align-items-center">
                                            <h5 class="card-title mb-0">Lista de Emprendedores</h5>
                                            <div class="table-controls">
                                                <div class="input-group input-group-sm">
                                                    <span class="input-group-text">
                                                        <i class="fa fa-search"></i>
                                                    </span>
                                                    <input type="text" 
                                                           class="form-control" 
                                                           placeholder="Buscar emprendedor..." 
                                                           data-search="mentees">
                                                </div>
                                            </div>
                                        </div>
                                        <div class="card-body p-0">
                                            <div class="table-responsive">
                                                <table class="table table-hover mb-0" id="menteesTable">
                                                    <thead class="table-light">
                                                        <tr>
                                                            <th>Emprendedor</th>
                                                            <th>Proyecto</th>
                                                            <th>Categoría</th>
                                                            <th>Progreso</th>
                                                            <th>Última Sesión</th>
                                                            <th>Calificación</th>
                                                            <th>Estado</th>
                                                            <th>Acciones</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody data-content="mentees-list">
                                                        <!-- Se llena dinámicamente -->
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab de Sesiones -->
                        <div class="tab-pane fade" id="sessions-tab">
                            <div class="sessions-report">
                                <div class="sessions-analytics mb-4">
                                    <div class="row g-4">
                                        <div class="col-md-8">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Frecuencia de Sesiones</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="sessionsFrequencyChart" height="250"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Tipos de Sesión</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="sessionTypesChart" height="250"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="sessions-details">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title mb-0">Historial de Sesiones</h5>
                                        </div>
                                        <div class="card-body">
                                            <div class="table-responsive">
                                                <table class="table table-striped" id="sessionsTable">
                                                    <thead>
                                                        <tr>
                                                            <th>Fecha</th>
                                                            <th>Emprendedor</th>
                                                            <th>Tipo</th>
                                                            <th>Duración</th>
                                                            <th>Temas</th>
                                                            <th>Calificación</th>
                                                            <th>Notas</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody data-content="sessions-list">
                                                        <!-- Se llena dinámicamente -->
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab de Impacto -->
                        <div class="tab-pane fade" id="impact-tab">
                            <div class="impact-report">
                                <div class="impact-metrics mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">ROI de Mentoría</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="roiChart" height="200"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Tasa de Éxito</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="successRateChart" height="200"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="success-stories">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title mb-0">Casos de Éxito</h5>
                                        </div>
                                        <div class="card-body">
                                            <div class="success-stories-grid" data-content="success-stories">
                                                <!-- Se llena dinámicamente -->
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab de Rendimiento -->
                        <div class="tab-pane fade" id="performance-tab">
                            <div class="performance-report">
                                <div class="performance-dashboard">
                                    <div class="row g-4">
                                        <div class="col-md-12">
                                            <div class="card">
                                                <div class="card-header">
                                                    <h5 class="card-title mb-0">Dashboard de Rendimiento</h5>
                                                </div>
                                                <div class="card-body">
                                                    <canvas id="performanceChart" height="300"></canvas>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab Financiero -->
                        <div class="tab-pane fade" id="financial-tab">
                            <div class="financial-report">
                                <div class="financial-overview mb-4">
                                    <div class="row g-3">
                                        <div class="col-md-4">
                                            <div class="financial-card">
                                                <h4 data-financial="revenue">$0</h4>
                                                <p>Ingresos Generados</p>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="financial-card">
                                                <h4 data-financial="investment">$0</h4>
                                                <p>Inversión Atraída</p>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="financial-card">
                                                <h4 data-financial="roi">0%</h4>
                                                <p>ROI Promedio</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="financial-charts">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title mb-0">Análisis Financiero</h5>
                                        </div>
                                        <div class="card-body">
                                            <canvas id="financialChart" height="300"></canvas>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab Personalizado -->
                        <div class="tab-pane fade" id="custom-tab">
                            <div class="custom-reports">
                                <div class="report-builder">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title mb-0">Constructor de Reportes</h5>
                                        </div>
                                        <div class="card-body">
                                            <div class="builder-interface" data-content="report-builder">
                                                <!-- Interface del constructor -->
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modal de exportación -->
                <div class="modal fade" id="exportModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Exportar Reporte</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <form data-form="export-settings">
                                    <div class="mb-3">
                                        <label class="form-label">Formato de exportación</label>
                                        <select class="form-select" data-input="export-format">
                                            <option value="pdf">PDF</option>
                                            <option value="excel">Excel</option>
                                            <option value="csv">CSV</option>
                                            <option value="json">JSON</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Incluir</label>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" 
                                                   id="includeCharts" checked data-include="charts">
                                            <label class="form-check-label" for="includeCharts">
                                                Gráficos
                                            </label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" 
                                                   id="includeRawData" data-include="rawData">
                                            <label class="form-check-label" for="includeRawData">
                                                Datos en bruto
                                            </label>
                                        </div>
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" 
                                                   id="includeComments" data-include="comments">
                                            <label class="form-check-label" for="includeComments">
                                                Comentarios y notas
                                            </label>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Nombre del archivo</label>
                                        <input type="text" class="form-control" 
                                               data-input="filename" 
                                               placeholder="reporte_mentoria">
                                    </div>
                                </form>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                    Cancelar
                                </button>
                                <button type="button" class="btn btn-primary" data-action="confirm-export">
                                    <i class="fa fa-download me-2"></i>
                                    Exportar
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Loading overlay -->
                <div class="reports-loading d-none">
                    <div class="loading-content">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Generando reporte...</span>
                        </div>
                        <div class="mt-3">
                            <h5>Generando reporte...</h5>
                            <p class="text-muted">Por favor espera mientras procesamos los datos</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Agregar estilos CSS específicos
        this.injectStyles();
    }

    /**
     * Obtener referencias a elementos DOM
     */
    bindElements() {
        const reports = this.container.querySelector('.ally-reports');
        
        this.elements = {
            // Header
            updateTime: reports.querySelector('.update-time'),
            dateStart: reports.querySelector('[data-input="date-start"]'),
            dateEnd: reports.querySelector('[data-input="date-end"]'),
            
            // Navegación
            reportTabs: reports.querySelectorAll('[data-report-type]'),
            
            // Filtros
            filterEmprendedores: reports.querySelector('[data-filter="emprendedores"]'),
            filterCategorias: reports.querySelector('[data-filter="categorias"]'),
            filterEstados: reports.querySelector('[data-filter="estados"]'),
            filterTiposSesion: reports.querySelector('[data-filter="tiposSesion"]'),
            
            // KPIs
            kpiValues: reports.querySelectorAll('[data-kpi]'),
            
            // Contenedores de contenido
            menteesContent: reports.querySelector('[data-content="mentees-list"]'),
            sessionsContent: reports.querySelector('[data-content="sessions-list"]'),
            successStoriesContent: reports.querySelector('[data-content="success-stories"]'),
            
            // Modales
            exportModal: reports.querySelector('#exportModal'),
            
            // Loading
            loadingOverlay: reports.querySelector('.reports-loading')
        };
    }

    /**
     * Configurar eventos
     */
    bindEvents() {
        // Eventos de header
        this.addEventDelegate('click', '[data-action="refresh-data"]', this.refreshData.bind(this));
        this.addEventDelegate('click', '[data-action="apply-date-range"]', this.applyDateRange.bind(this));
        this.addEventDelegate('click', '[data-action="toggle-comparison"]', this.toggleComparison.bind(this));
        this.addEventDelegate('click', '[data-action="export"]', this.showExportModal.bind(this));
        this.addEventDelegate('click', '[data-action="schedule-report"]', this.showScheduleModal.bind(this));
        
        // Eventos de navegación
        this.addEventDelegate('click', '[data-report-type]', this.switchReport.bind(this));
        
        // Eventos de filtros
        this.addEventDelegate('click', '[data-action="apply-filters"]', this.applyFilters.bind(this));
        this.addEventDelegate('click', '[data-action="clear-filters"]', this.clearFilters.bind(this));
        this.addEventDelegate('change', '[data-filter]', this.handleFilterChange.bind(this));
        
        // Eventos de búsqueda
        this.addEventDelegate('input', '[data-search]', 
            this.main.utils.debounce(this.handleSearch.bind(this), 300));
        
        // Eventos de gráficos
        this.addEventDelegate('change', 'input[name="chartPeriod"]', this.handleChartPeriodChange.bind(this));
        
        // Eventos de tabla
        this.addEventDelegate('click', '.mentee-details', this.showMenteeDetails.bind(this));
        this.addEventDelegate('click', '.session-details', this.showSessionDetails.bind(this));
        
        // Eventos de exportación
        this.addEventDelegate('click', '[data-action="confirm-export"]', this.confirmExport.bind(this));
        
        // Eventos de comparación
        this.addEventDelegate('change', '.mentee-compare', this.handleMenteeCompare.bind(this));
    }

    /**
     * Agregar event listener con delegación
     */
    addEventDelegate(event, selector, handler) {
        const listener = (e) => {
            const target = e.target.closest(selector);
            if (target && this.container.contains(target)) {
                handler(e, target);
            }
        };
        
        this.container.addEventListener(event, listener);
        
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push({ selector, handler, listener });
    }

    /**
     * Cargar templates de reportes
     */
    loadReportTemplates() {
        // Templates predefinidos para diferentes tipos de reporte
        this.reportTemplates.set('overview', {
            sections: ['kpis', 'activity_chart', 'category_distribution', 'progress_summary'],
            charts: ['activity', 'category', 'progress', 'satisfaction'],
            refreshInterval: 300000
        });
        
        this.reportTemplates.set('mentees', {
            sections: ['summary', 'list', 'progress_details', 'engagement_metrics'],
            charts: ['mentee_progress', 'engagement_timeline'],
            refreshInterval: 600000
        });
        
        // Más templates...
    }

    /**
     * Cargar datos iniciales
     */
    async loadInitialData() {
        try {
            // Configurar fechas por defecto
            this.setDefaultDateRange();
            
            // Cargar opciones de filtros
            await this.loadFilterOptions();
            
            // Cargar datos básicos
            await this.loadBasicData();
            
        } catch (error) {
            console.error('Error cargando datos iniciales:', error);
            throw error;
        }
    }

    /**
     * Configurar fechas por defecto
     */
    setDefaultDateRange() {
        const end = new Date();
        const start = new Date(Date.now() - (this.moduleConfig.defaultDateRange * 24 * 60 * 60 * 1000));
        
        this.moduleState.selectedDateRange = { start, end };
        
        if (this.elements.dateStart) {
            this.elements.dateStart.value = start.toISOString().split('T')[0];
        }
        if (this.elements.dateEnd) {
            this.elements.dateEnd.value = end.toISOString().split('T')[0];
        }
    }

    /**
     * Cargar opciones de filtros
     */
    async loadFilterOptions() {
        try {
            const response = await this.main.http.get('/reports/filter-options');
            
            // Llenar select de emprendedores
            if (this.elements.filterEmprendedores && response.mentees) {
                this.elements.filterEmprendedores.innerHTML = 
                    '<option value="">Todos</option>' +
                    response.mentees.map(mentee => 
                        `<option value="${mentee.id}">${mentee.name}</option>`
                    ).join('');
            }
            
        } catch (error) {
            console.error('Error cargando opciones de filtros:', error);
        }
    }

    /**
     * Cargar datos básicos
     */
    async loadBasicData() {
        try {
            const params = this.buildApiParams();
            const response = await this.main.http.get('/reports/basic-data', { params });
            
            // Actualizar KPIs
            this.updateKPIs(response.kpis);
            
            // Guardar en cache
            this.moduleState.dataCache.set('basic-data', {
                data: response,
                timestamp: Date.now()
            });
            
        } catch (error) {
            console.error('Error cargando datos básicos:', error);
            throw error;
        }
    }

    /**
     * Cargar reporte por defecto
     */
    async loadDefaultReport() {
        await this.loadReport('overview');
    }

    /**
     * Cargar reporte específico
     */
    async loadReport(reportType) {
        if (this.moduleState.isGenerating) return;
        
        try {
            this.moduleState.isGenerating = true;
            this.showLoading(true);
            
            const params = this.buildApiParams();
            const response = await this.main.http.get(`/reports/${reportType}`, { params });
            
            // Guardar reporte
            this.moduleState.reports.set(reportType, response);
            this.moduleState.currentReport = reportType;
            
            // Renderizar contenido específico
            await this.renderReport(reportType, response);
            
            // Actualizar timestamp
            this.updateLastRefreshTime();
            
        } catch (error) {
            console.error(`Error cargando reporte ${reportType}:`, error);
            this.showError('Error cargando reporte', error.message);
        } finally {
            this.moduleState.isGenerating = false;
            this.showLoading(false);
        }
    }

    /**
     * Renderizar reporte
     */
    async renderReport(reportType, data) {
        switch (reportType) {
            case 'overview':
                await this.renderOverviewReport(data);
                break;
            case 'mentees':
                await this.renderMenteesReport(data);
                break;
            case 'sessions':
                await this.renderSessionsReport(data);
                break;
            case 'impact':
                await this.renderImpactReport(data);
                break;
            case 'performance':
                await this.renderPerformanceReport(data);
                break;
            case 'financial':
                await this.renderFinancialReport(data);
                break;
            default:
                console.warn(`Tipo de reporte no implementado: ${reportType}`);
        }
    }

    /**
     * Renderizar reporte de resumen
     */
    async renderOverviewReport(data) {
        // Actualizar KPIs
        this.updateKPIs(data.kpis);
        
        // Crear gráfico de actividad
        await this.createActivityChart(data.activity);
        
        // Crear gráfico de categorías
        await this.createCategoryChart(data.categories);
        
        // Crear gráfico de progreso
        await this.createProgressChart(data.progress);
        
        // Crear gráfico de satisfacción
        await this.createSatisfactionChart(data.satisfaction);
    }

    /**
     * Renderizar reporte de emprendedores
     */
    async renderMenteesReport(data) {
        // Actualizar resumen
        this.updateSummaryCards(data.summary);
        
        // Renderizar tabla de emprendedores
        this.renderMenteesTable(data.mentees);
    }

    /**
     * Renderizar tabla de emprendedores
     */
    renderMenteesTable(mentees) {
        const tbody = this.elements.menteesContent;
        if (!tbody) return;
        
        tbody.innerHTML = mentees.map(mentee => `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <img src="${mentee.avatar || '/static/img/default-avatar.png'}" 
                             alt="${mentee.name}" 
                             class="avatar-sm rounded-circle me-2">
                        <div>
                            <div class="fw-medium">${mentee.name}</div>
                            <small class="text-muted">${mentee.email}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="fw-medium">${mentee.project_name}</div>
                    <small class="text-muted">${mentee.project_description}</small>
                </td>
                <td>
                    <span class="badge bg-${this.getCategoryColor(mentee.category)}">
                        ${this.getCategoryLabel(mentee.category)}
                    </span>
                </td>
                <td>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar" role="progressbar" 
                             style="width: ${mentee.progress}%" 
                             aria-valuenow="${mentee.progress}" 
                             aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <small class="text-muted">${mentee.progress}%</small>
                </td>
                <td>
                    <div>${this.formatDate(mentee.last_session)}</div>
                    <small class="text-muted">${this.formatRelativeTime(mentee.last_session)}</small>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="me-2">${mentee.rating.toFixed(1)}</div>
                        <div class="rating-stars">
                            ${this.renderStars(mentee.rating)}
                        </div>
                    </div>
                </td>
                <td>
                    <span class="badge bg-${this.getStatusColor(mentee.status)}">
                        ${this.getStatusLabel(mentee.status)}
                    </span>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary mentee-details" 
                                data-mentee-id="${mentee.id}">
                            <i class="fa fa-eye"></i>
                        </button>
                        <button class="btn btn-outline-secondary" 
                                data-action="message-mentee" 
                                data-mentee-id="${mentee.id}">
                            <i class="fa fa-envelope"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    /**
     * Crear gráfico de actividad
     */
    async createActivityChart(data) {
        const ctx = document.getElementById('activityChart');
        if (!ctx) return;
        
        // Destruir gráfico anterior si existe
        if (this.chartInstances.has('activity')) {
            this.chartInstances.get('activity').destroy();
        }
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Sesiones',
                    data: data.sessions,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Horas',
                    data: data.hours,
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
        
        this.chartInstances.set('activity', chart);
    }

    /**
     * Crear gráfico de categorías
     */
    async createCategoryChart(data) {
        const ctx = document.getElementById('categoryChart');
        if (!ctx) return;
        
        if (this.chartInstances.has('category')) {
            this.chartInstances.get('category').destroy();
        }
        
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: [
                        '#007bff', '#28a745', '#ffc107', 
                        '#dc3545', '#6f42c1', '#20c997'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
        
        this.chartInstances.set('category', chart);
    }

    /**
     * Actualizar KPIs
     */
    updateKPIs(kpis) {
        this.elements.kpiValues.forEach(element => {
            const kpiName = element.dataset.kpi;
            if (kpis[kpiName] !== undefined) {
                element.textContent = this.formatKPIValue(kpiName, kpis[kpiName]);
            }
        });
    }

    /**
     * Formatear valor de KPI
     */
    formatKPIValue(kpiName, value) {
        switch (kpiName) {
            case 'total-hours':
                return `${value}h`;
            case 'avg-rating':
                return value.toFixed(1);
            default:
                return this.main.utils.formatNumber(value);
        }
    }

    /**
     * Cambiar reporte
     */
    async switchReport(event, element) {
        const reportType = element.dataset.reportType;
        
        // Actualizar navegación activa
        this.elements.reportTabs.forEach(tab => tab.classList.remove('active'));
        element.classList.add('active');
        
        // Cargar reporte
        await this.loadReport(reportType);
    }

    /**
     * Aplicar rango de fechas
     */
    async applyDateRange() {
        const startDate = new Date(this.elements.dateStart.value);
        const endDate = new Date(this.elements.dateEnd.value);
        
        if (startDate >= endDate) {
            this.showError('Error', 'La fecha de inicio debe ser anterior a la fecha de fin');
            return;
        }
        
        this.moduleState.selectedDateRange = {
            start: startDate,
            end: endDate
        };
        
        // Recargar reporte actual
        if (this.moduleState.currentReport) {
            await this.loadReport(this.moduleState.currentReport);
        }
    }

    /**
     * Aplicar filtros
     */
    async applyFilters() {
        // Recopilar filtros
        this.moduleState.filters = {
            emprendedores: Array.from(this.elements.filterEmprendedores.selectedOptions).map(o => o.value),
            categorias: Array.from(this.elements.filterCategorias.selectedOptions).map(o => o.value),
            estados: Array.from(this.elements.filterEstados.selectedOptions).map(o => o.value),
            tiposSesion: Array.from(this.elements.filterTiposSesion.selectedOptions).map(o => o.value)
        };
        
        // Recargar reporte actual
        if (this.moduleState.currentReport) {
            await this.loadReport(this.moduleState.currentReport);
        }
    }

    /**
     * Limpiar filtros
     */
    async clearFilters() {
        // Resetear filtros
        Object.keys(this.moduleState.filters).forEach(key => {
            this.moduleState.filters[key] = [];
        });
        
        // Limpiar selects
        document.querySelectorAll('[data-filter]').forEach(select => {
            select.selectedIndex = 0;
        });
        
        // Recargar reporte
        if (this.moduleState.currentReport) {
            await this.loadReport(this.moduleState.currentReport);
        }
    }

    /**
     * Refrescar datos
     */
    async refreshData() {
        // Limpiar cache
        this.moduleState.dataCache.clear();
        
        // Recargar reporte actual
        if (this.moduleState.currentReport) {
            await this.loadReport(this.moduleState.currentReport);
        }
    }

    /**
     * Mostrar modal de exportación
     */
    showExportModal(event, element) {
        const format = element.dataset.format;
        const modal = new bootstrap.Modal(this.elements.exportModal);
        
        // Pre-seleccionar formato si se especifica
        if (format) {
            this.elements.exportModal.querySelector('[data-input="export-format"]').value = format;
        }
        
        modal.show();
    }

    /**
     * Confirmar exportación
     */
    async confirmExport() {
        const modal = bootstrap.Modal.getInstance(this.elements.exportModal);
        const form = this.elements.exportModal.querySelector('form');
        const formData = new FormData(form);
        
        try {
            const exportData = {
                report_type: this.moduleState.currentReport,
                format: formData.get('export-format'),
                filename: formData.get('filename') || 'reporte_mentoria',
                date_range: this.moduleState.selectedDateRange,
                filters: this.moduleState.filters,
                include_charts: form.querySelector('[data-include="charts"]').checked,
                include_raw_data: form.querySelector('[data-include="rawData"]').checked,
                include_comments: form.querySelector('[data-include="comments"]').checked
            };
            
            const response = await this.main.http.post('/reports/export', exportData, {
                responseType: 'blob'
            });
            
            // Descargar archivo
            this.downloadFile(response, exportData.filename, exportData.format);
            
            modal.hide();
            
            this.main.notifications.success('Reporte exportado exitosamente');
            
        } catch (error) {
            console.error('Error exportando reporte:', error);
            this.showError('Error exportando reporte', error.message);
        }
    }

    /**
     * Descargar archivo
     */
    downloadFile(data, filename, format) {
        const blob = new Blob([data], { 
            type: this.getMimeType(format) 
        });
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    /**
     * Obtener MIME type por formato
     */
    getMimeType(format) {
        const mimeTypes = {
            pdf: 'application/pdf',
            excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            csv: 'text/csv',
            json: 'application/json'
        };
        
        return mimeTypes[format] || 'application/octet-stream';
    }

    /**
     * Construir parámetros para API
     */
    buildApiParams() {
        return {
            start_date: this.moduleState.selectedDateRange.start.toISOString(),
            end_date: this.moduleState.selectedDateRange.end.toISOString(),
            mentees: this.moduleState.filters.emprendedores.join(','),
            categories: this.moduleState.filters.categorias.join(','),
            states: this.moduleState.filters.estados.join(','),
            session_types: this.moduleState.filters.tiposSesion.join(',')
        };
    }

    /**
     * Configurar auto-refresh
     */
    setupAutoRefresh() {
        if (!this.moduleConfig.enableAutoRefresh) return;
        
        this.moduleState.autoRefreshTimer = setInterval(() => {
            if (this.moduleState.currentReport && !this.moduleState.isGenerating) {
                this.refreshData();
            }
        }, this.moduleConfig.autoRefreshInterval);
    }

    /**
     * Configurar estado reactivo
     */
    setupReactiveState() {
        // Escuchar cambios en datos de mentoría
        if (this.state) {
            this.state.subscribe('mentorship', () => {
                if (this.moduleConfig.enableRealTimeUpdates) {
                    this.refreshData();
                }
            });
        }
    }

    /**
     * Actualizar tiempo de última actualización
     */
    updateLastRefreshTime() {
        this.moduleState.lastRefresh = Date.now();
        
        if (this.elements.updateTime) {
            this.elements.updateTime.textContent = 
                `Actualizado ${this.main.utils.formatRelativeTime(this.moduleState.lastRefresh)}`;
        }
    }

    /**
     * Mostrar/ocultar loading
     */
    showLoading(show = true) {
        if (this.elements.loadingOverlay) {
            this.elements.loadingOverlay.classList.toggle('d-none', !show);
        }
    }

    /**
     * Inyectar estilos CSS específicos
     */
    injectStyles() {
        const styleId = 'ally-reports-styles';
        
        if (document.getElementById(styleId)) return;
        
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .ally-reports {
                height: 100%;
                display: flex;
                flex-direction: column;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            
            .reports-header {
                padding: 1.5rem;
                border-bottom: 1px solid #e9ecef;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .reports-navigation {
                padding: 1rem 1.5rem;
                border-bottom: 1px solid #e9ecef;
            }
            
            .reports-filters {
                padding: 1rem 1.5rem;
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
            }
            
            .reports-content {
                flex: 1;
                padding: 1.5rem;
                overflow-y: auto;
            }
            
            .kpi-card {
                border: none;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                border-radius: 8px;
            }
            
            .kpi-card .card-body {
                display: flex;
                align-items: center;
                padding: 1.5rem;
            }
            
            .kpi-icon {
                font-size: 2rem;
                margin-right: 1rem;
            }
            
            .kpi-value {
                font-size: 2rem;
                font-weight: 600;
                margin: 0;
                color: #2c3e50;
            }
            
            .kpi-label {
                margin: 0;
                color: #6c757d;
                font-size: 0.875rem;
            }
            
            .kpi-trend {
                font-size: 0.75rem;
                margin-top: 0.25rem;
            }
            
            .kpi-trend.positive {
                color: #28a745;
            }
            
            .kpi-trend.negative {
                color: #dc3545;
            }
            
            .avatar-sm {
                width: 32px;
                height: 32px;
                object-fit: cover;
            }
            
            .rating-stars {
                color: #ffc107;
            }
            
            .reports-loading {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.9);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
            }
            
            .loading-content {
                text-align: center;
            }
            
            @media (max-width: 768px) {
                .reports-header {
                    flex-direction: column;
                    gap: 1rem;
                    align-items: stretch;
                }
                
                .header-actions {
                    flex-direction: column;
                    gap: 0.5rem;
                }
                
                .date-range-selector .input-group {
                    flex-wrap: wrap;
                }
            }
        `;
        
        document.head.appendChild(style);
    }

    /**
     * Mostrar error
     */
    showError(title, message) {
        if (this.main.notifications) {
            this.main.notifications.error(`${title}: ${message}`);
        } else {
            console.error(`${title}:`, message);
        }
    }

    /**
     * Destruir módulo
     */
    destroy() {
        // Limpiar auto-refresh
        if (this.moduleState.autoRefreshTimer) {
            clearInterval(this.moduleState.autoRefreshTimer);
        }
        
        // Destruir gráficos
        this.chartInstances.forEach(chart => chart.destroy());
        
        // Limpiar event listeners
        this.eventListeners.forEach((listeners, event) => {
            listeners.forEach(({ listener }) => {
                this.container.removeEventListener(event, listener);
            });
        });
        
        // Limpiar cache
        this.moduleState.dataCache.clear();
        
        console.log('🧹 Ally Reports destruido');
    }

    // Métodos auxiliares adicionales...
    formatDate(date) {
        return new Date(date).toLocaleDateString('es-CO');
    }

    formatRelativeTime(date) {
        return this.main.utils.formatRelativeTime(date);
    }

    getCategoryColor(category) {
        const colors = {
            technology: 'primary',
            health: 'danger', 
            education: 'success',
            finance: 'warning',
            sustainability: 'info'
        };
        return colors[category] || 'secondary';
    }

    getCategoryLabel(category) {
        const labels = {
            technology: 'Tecnología',
            health: 'Salud',
            education: 'Educación', 
            finance: 'Finanzas',
            sustainability: 'Sostenibilidad'
        };
        return labels[category] || category;
    }

    getStatusColor(status) {
        const colors = {
            active: 'success',
            paused: 'warning',
            completed: 'info',
            cancelled: 'danger'
        };
        return colors[status] || 'secondary';
    }

    getStatusLabel(status) {
        const labels = {
            active: 'Activo',
            paused: 'Pausado',
            completed: 'Completado',
            cancelled: 'Cancelado'
        };
        return labels[status] || status;
    }

    renderStars(rating) {
        const stars = [];
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        
        for (let i = 0; i < fullStars; i++) {
            stars.push('<i class="fa fa-star"></i>');
        }
        
        if (hasHalfStar) {
            stars.push('<i class="fa fa-star-half-alt"></i>');
        }
        
        const emptyStars = 5 - Math.ceil(rating);
        for (let i = 0; i < emptyStars; i++) {
            stars.push('<i class="fa fa-star-o"></i>');
        }
        
        return stars.join('');
    }
}

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AllyReports;
}

// Hacer disponible globalmente
window.AllyReports = AllyReports;