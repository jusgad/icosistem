/**
 * Client Dashboard Module
 * Maneja todas las funcionalidades del dashboard del cliente/stakeholder
 * @author Ecosistema Emprendimiento
 * @version 2.0.0
 */

class ClientDashboard {
    constructor() {
        this.config = {
            apiBaseUrl: '/api/v1',
            refreshInterval: 30000, // 30 segundos
            chartsConfig: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        };

        this.state = {
            currentView: 'overview',
            filters: {
                dateRange: '3months',
                sector: 'all',
                stage: 'all',
                region: 'all'
            },
            selectedEntrepreneur: null,
            isLoading: false,
            lastUpdate: null
        };

        this.charts = {};
        this.socket = null;
        this.refreshTimer = null;
        this.notifications = [];

        this.init();
    }

    /**
     * Inicialización del módulo
     */
    async init() {
        try {
            this.showLoader();
            await this.setupEventListeners();
            await this.initializeWebSocket();
            await this.loadDashboardData();
            await this.initializeCharts();
            this.startAutoRefresh();
            this.hideLoader();
            
            console.log('✅ ClientDashboard initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing ClientDashboard:', error);
            this.showError('Error al inicializar el dashboard');
        }
    }

    /**
     * Configuración de event listeners
     */
    setupEventListeners() {
        // Navegación del dashboard
        document.querySelectorAll('[data-dashboard-nav]').forEach(nav => {
            nav.addEventListener('click', (e) => {
                e.preventDefault();
                const view = e.target.dataset.dashboardNav;
                this.switchView(view);
            });
        });

        // Filtros
        document.querySelectorAll('[data-filter]').forEach(filter => {
            filter.addEventListener('change', (e) => {
                const filterType = e.target.dataset.filter;
                const value = e.target.value;
                this.updateFilter(filterType, value);
            });
        });

        // Búsqueda de emprendedores
        const searchInput = document.getElementById('entrepreneur-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.searchEntrepreneurs(e.target.value);
                }, 300);
            });
        }

        // Exportación de reportes
        document.querySelectorAll('[data-export]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const format = e.target.dataset.export;
                this.exportReport(format);
            });
        });

        // Refresh manual
        const refreshBtn = document.getElementById('refresh-dashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshDashboard();
            });
        }

        // Modal handlers
        this.setupModalHandlers();

        // Responsive charts
        window.addEventListener('resize', this.debounce(() => {
            this.resizeCharts();
        }, 250));
    }

    /**
     * Inicialización de WebSocket para actualizaciones en tiempo real
     */
    initializeWebSocket() {
        if (typeof io !== 'undefined') {
            this.socket = io('/client-dashboard', {
                transports: ['websocket', 'polling']
            });

            this.socket.on('connect', () => {
                console.log('🔗 WebSocket connected');
                this.updateConnectionStatus(true);
            });

            this.socket.on('disconnect', () => {
                console.log('🔌 WebSocket disconnected');
                this.updateConnectionStatus(false);
            });

            this.socket.on('entrepreneur_update', (data) => {
                this.handleEntrepreneurUpdate(data);
            });

            this.socket.on('new_project', (data) => {
                this.handleNewProject(data);
            });

            this.socket.on('impact_update', (data) => {
                this.handleImpactUpdate(data);
            });

            this.socket.on('notification', (data) => {
                this.showNotification(data);
            });
        }
    }

    /**
     * Carga inicial de datos del dashboard
     */
    async loadDashboardData() {
        try {
            this.state.isLoading = true;
            
            const [
                overview,
                entrepreneurs,
                projects,
                impact,
                analytics
            ] = await Promise.all([
                this.fetchData('/clients/overview'),
                this.fetchData('/entrepreneurs/directory'),
                this.fetchData('/projects/summary'),
                this.fetchData('/analytics/impact'),
                this.fetchData('/analytics/dashboard')
            ]);

            this.updateOverviewCards(overview);
            this.updateEntrepreneursTable(entrepreneurs);
            this.updateProjectsSection(projects);
            this.updateImpactMetrics(impact);
            this.updateAnalytics(analytics);

            this.state.lastUpdate = new Date();
            this.updateLastRefreshTime();

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Error al cargar los datos del dashboard');
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Actualización de tarjetas de resumen
     */
    updateOverviewCards(data) {
        const cards = {
            'total-entrepreneurs': data.total_entrepreneurs,
            'active-projects': data.active_projects,
            'impact-score': data.impact_score,
            'monthly-growth': data.monthly_growth
        };

        Object.entries(cards).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                this.animateValue(element, parseInt(element.textContent) || 0, value, 1000);
            }
        });

        // Actualizar indicadores de tendencia
        this.updateTrendIndicators(data.trends);
    }

    /**
     * Actualización de tabla de emprendedores
     */
    updateEntrepreneursTable(data) {
        const tableBody = document.getElementById('entrepreneurs-table-body');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        data.entrepreneurs.forEach(entrepreneur => {
            const row = this.createEntrepreneurRow(entrepreneur);
            tableBody.appendChild(row);
        });

        // Actualizar paginación si existe
        this.updatePagination(data.pagination);
    }

    /**
     * Crear fila de emprendedor para la tabla
     */
    createEntrepreneurRow(entrepreneur) {
        const row = document.createElement('tr');
        row.className = 'entrepreneur-row';
        row.dataset.entrepreneurId = entrepreneur.id;

        const statusClass = this.getStatusClass(entrepreneur.status);
        const progressColor = this.getProgressColor(entrepreneur.progress);

        row.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <img src="${entrepreneur.avatar || '/static/img/default-avatar.png'}" 
                         alt="${entrepreneur.name}" class="avatar me-2">
                    <div>
                        <h6 class="mb-0">${entrepreneur.name}</h6>
                        <small class="text-muted">${entrepreneur.email}</small>
                    </div>
                </div>
            </td>
            <td>
                <span class="badge bg-${entrepreneur.sector_color}">${entrepreneur.sector}</span>
            </td>
            <td>
                <span class="status-badge status-${statusClass}">${entrepreneur.status}</span>
            </td>
            <td>
                <div class="progress" style="height: 6px;">
                    <div class="progress-bar bg-${progressColor}" 
                         style="width: ${entrepreneur.progress}%"></div>
                </div>
                <small class="text-muted">${entrepreneur.progress}%</small>
            </td>
            <td>
                <span class="text-muted">${this.formatDate(entrepreneur.last_activity)}</span>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary btn-sm" 
                            onclick="clientDashboard.viewEntrepreneurDetails(${entrepreneur.id})">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-outline-info btn-sm" 
                            onclick="clientDashboard.viewProjects(${entrepreneur.id})">
                        <i class="fas fa-folder"></i>
                    </button>
                    <button class="btn btn-outline-success btn-sm" 
                            onclick="clientDashboard.viewImpact(${entrepreneur.id})">
                        <i class="fas fa-chart-line"></i>
                    </button>
                </div>
            </td>
        `;

        return row;
    }

    /**
     * Inicialización de gráficos
     */
    async initializeCharts() {
        try {
            if (typeof Chart === 'undefined') {
                console.warn('Chart.js not loaded');
                return;
            }

            // Gráfico de impacto general
            await this.initImpactChart();
            
            // Gráfico de sectores
            await this.initSectorsChart();
            
            // Gráfico de crecimiento
            await this.initGrowthChart();
            
            // Gráfico de distribución geográfica
            await this.initGeographicChart();

        } catch (error) {
            console.error('Error initializing charts:', error);
        }
    }

    /**
     * Gráfico de impacto general
     */
    async initImpactChart() {
        const ctx = document.getElementById('impact-chart');
        if (!ctx) return;

        const data = await this.fetchData('/analytics/impact-over-time');

        this.charts.impact = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Puntuación de Impacto',
                    data: data.impact_scores,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }, {
                    label: 'Emprendedores Activos',
                    data: data.active_entrepreneurs,
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y1'
                }]
            },
            options: {
                ...this.config.chartsConfig,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Puntuación de Impacto'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Emprendedores'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            }
        });
    }

    /**
     * Gráfico de sectores
     */
    async initSectorsChart() {
        const ctx = document.getElementById('sectors-chart');
        if (!ctx) return;

        const data = await this.fetchData('/analytics/sectors-distribution');

        this.charts.sectors = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                ...this.config.chartsConfig,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const percentage = ((context.parsed / data.total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    /**
     * Gráfico de crecimiento
     */
    async initGrowthChart() {
        const ctx = document.getElementById('growth-chart');
        if (!ctx) return;

        const data = await this.fetchData('/analytics/growth-metrics');

        this.charts.growth = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Nuevos Emprendedores',
                    data: data.new_entrepreneurs,
                    backgroundColor: '#007bff',
                    borderRadius: 4
                }, {
                    label: 'Proyectos Completados',
                    data: data.completed_projects,
                    backgroundColor: '#28a745',
                    borderRadius: 4
                }]
            },
            options: {
                ...this.config.chartsConfig,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cantidad'
                        }
                    }
                }
            }
        });
    }

    /**
     * Gráfico de distribución geográfica
     */
    async initGeographicChart() {
        const ctx = document.getElementById('geographic-chart');
        if (!ctx) return;

        const data = await this.fetchData('/analytics/geographic-distribution');

        this.charts.geographic = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: data.regions,
                datasets: [{
                    label: 'Emprendedores por Región',
                    data: data.values,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.2)',
                    pointBackgroundColor: '#007bff',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                ...this.config.chartsConfig,
                scales: {
                    r: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cantidad de Emprendedores'
                        }
                    }
                }
            }
        });
    }

    /**
     * Cambio de vista del dashboard
     */
    switchView(view) {
        if (this.state.currentView === view) return;

        // Ocultar vista actual
        const currentView = document.querySelector(`[data-view="${this.state.currentView}"]`);
        if (currentView) {
            currentView.classList.add('d-none');
        }

        // Mostrar nueva vista
        const newView = document.querySelector(`[data-view="${view}"]`);
        if (newView) {
            newView.classList.remove('d-none');
        }

        // Actualizar navegación
        document.querySelectorAll('[data-dashboard-nav]').forEach(nav => {
            nav.classList.remove('active');
        });
        
        const activeNav = document.querySelector(`[data-dashboard-nav="${view}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
        }

        this.state.currentView = view;

        // Cargar datos específicos de la vista si es necesario
        this.loadViewData(view);
    }

    /**
     * Carga de datos específicos por vista
     */
    async loadViewData(view) {
        try {
            switch (view) {
                case 'directory':
                    await this.loadDirectoryData();
                    break;
                case 'impact':
                    await this.loadImpactData();
                    break;
                case 'reports':
                    await this.loadReportsData();
                    break;
                case 'analytics':
                    await this.loadAnalyticsData();
                    break;
                default:
                    break;
            }
        } catch (error) {
            console.error(`Error loading ${view} data:`, error);
            this.showError(`Error al cargar datos de ${view}`);
        }
    }

    /**
     * Actualización de filtros
     */
    async updateFilter(filterType, value) {
        this.state.filters[filterType] = value;
        
        // Aplicar filtros
        await this.applyFilters();
    }

    /**
     * Aplicación de filtros
     */
    async applyFilters() {
        try {
            this.showLoader();

            const queryParams = new URLSearchParams(this.state.filters);
            const data = await this.fetchData(`/clients/filtered-data?${queryParams}`);

            this.updateEntrepreneursTable(data.entrepreneurs);
            this.updateProjectsSection(data.projects);
            this.updateImpactMetrics(data.impact);

            // Actualizar gráficos con datos filtrados
            await this.updateChartsWithFilters(data.analytics);

        } catch (error) {
            console.error('Error applying filters:', error);
            this.showError('Error al aplicar filtros');
        } finally {
            this.hideLoader();
        }
    }

    /**
     * Búsqueda de emprendedores
     */
    async searchEntrepreneurs(query) {
        if (query.length < 2) {
            await this.loadDashboardData();
            return;
        }

        try {
            const data = await this.fetchData(`/entrepreneurs/search?q=${encodeURIComponent(query)}`);
            this.updateEntrepreneursTable({ entrepreneurs: data.results, pagination: data.pagination });
        } catch (error) {
            console.error('Error searching entrepreneurs:', error);
        }
    }

    /**
     * Ver detalles de emprendedor
     */
    async viewEntrepreneurDetails(entrepreneurId) {
        try {
            const data = await this.fetchData(`/entrepreneurs/${entrepreneurId}/details`);
            this.showEntrepreneurModal(data);
        } catch (error) {
            console.error('Error loading entrepreneur details:', error);
            this.showError('Error al cargar detalles del emprendedor');
        }
    }

    /**
     * Ver proyectos de emprendedor
     */
    async viewProjects(entrepreneurId) {
        try {
            const data = await this.fetchData(`/entrepreneurs/${entrepreneurId}/projects`);
            this.showProjectsModal(data);
        } catch (error) {
            console.error('Error loading projects:', error);
            this.showError('Error al cargar proyectos');
        }
    }

    /**
     * Ver impacto de emprendedor
     */
    async viewImpact(entrepreneurId) {
        try {
            const data = await this.fetchData(`/entrepreneurs/${entrepreneurId}/impact`);
            this.showImpactModal(data);
        } catch (error) {
            console.error('Error loading impact data:', error);
            this.showError('Error al cargar datos de impacto');
        }
    }

    /**
     * Exportación de reportes
     */
    async exportReport(format) {
        try {
            this.showLoader();

            const response = await fetch(`${this.config.apiBaseUrl}/reports/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    format: format,
                    filters: this.state.filters,
                    view: this.state.currentView
                })
            });

            if (!response.ok) throw new Error('Error en la exportación');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `reporte_${this.state.currentView}_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            this.showSuccess('Reporte exportado exitosamente');

        } catch (error) {
            console.error('Error exporting report:', error);
            this.showError('Error al exportar reporte');
        } finally {
            this.hideLoader();
        }
    }

    /**
     * Refresh del dashboard
     */
    async refreshDashboard() {
        await this.loadDashboardData();
        this.showSuccess('Dashboard actualizado');
    }

    /**
     * Configuración de modales
     */
    setupModalHandlers() {
        // Modal de detalles de emprendedor
        const entrepreneurModal = document.getElementById('entrepreneurModal');
        if (entrepreneurModal) {
            entrepreneurModal.addEventListener('hidden.bs.modal', () => {
                this.state.selectedEntrepreneur = null;
            });
        }
    }

    /**
     * Mostrar modal de emprendedor
     */
    showEntrepreneurModal(data) {
        const modal = document.getElementById('entrepreneurModal');
        if (!modal) return;

        // Actualizar contenido del modal
        const modalBody = modal.querySelector('.modal-body');
        modalBody.innerHTML = this.renderEntrepreneurDetails(data);

        // Mostrar modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        this.state.selectedEntrepreneur = data.id;
    }

    /**
     * Renderizar detalles de emprendedor
     */
    renderEntrepreneurDetails(data) {
        return `
            <div class="entrepreneur-details">
                <div class="row">
                    <div class="col-md-4 text-center">
                        <img src="${data.avatar || '/static/img/default-avatar.png'}" 
                             alt="${data.name}" class="img-fluid rounded-circle mb-3" style="max-width: 150px;">
                        <h5>${data.name}</h5>
                        <p class="text-muted">${data.title}</p>
                        <span class="badge bg-${data.sector_color}">${data.sector}</span>
                    </div>
                    <div class="col-md-8">
                        <h6>Información de Contacto</h6>
                        <ul class="list-unstyled">
                            <li><i class="fas fa-envelope me-2"></i> ${data.email}</li>
                            <li><i class="fas fa-phone me-2"></i> ${data.phone || 'No disponible'}</li>
                            <li><i class="fas fa-map-marker-alt me-2"></i> ${data.location}</li>
                        </ul>
                        
                        <h6 class="mt-4">Progreso Actual</h6>
                        <div class="progress mb-2">
                            <div class="progress-bar" style="width: ${data.progress}%"></div>
                        </div>
                        <small class="text-muted">${data.progress}% completado</small>
                        
                        <h6 class="mt-4">Métricas Clave</h6>
                        <div class="row">
                            <div class="col-6">
                                <div class="metric-card">
                                    <div class="metric-value">${data.metrics.projects_count}</div>
                                    <div class="metric-label">Proyectos</div>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="metric-card">
                                    <div class="metric-value">${data.metrics.impact_score}</div>
                                    <div class="metric-label">Puntuación Impacto</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Manejo de actualizaciones WebSocket
     */
    handleEntrepreneurUpdate(data) {
        // Actualizar fila de emprendedor en tiempo real
        const row = document.querySelector(`[data-entrepreneur-id="${data.entrepreneur_id}"]`);
        if (row) {
            this.updateEntrepreneurRow(row, data);
        }
        
        // Mostrar notificación
        this.showNotification({
            type: 'info',
            title: 'Actualización de Emprendedor',
            message: `${data.entrepreneur_name} ha actualizado su progreso`
        });
    }

    handleNewProject(data) {
        // Actualizar contadores
        this.incrementCounter('active-projects');
        
        // Mostrar notificación
        this.showNotification({
            type: 'success',
            title: 'Nuevo Proyecto',
            message: `${data.entrepreneur_name} ha creado un nuevo proyecto: ${data.project_name}`
        });
    }

    handleImpactUpdate(data) {
        // Actualizar métricas de impacto
        this.updateImpactMetrics(data);
        
        // Mostrar notificación
        this.showNotification({
            type: 'info',
            title: 'Actualización de Impacto',
            message: 'Las métricas de impacto han sido actualizadas'
        });
    }

    /**
     * Auto-refresh de datos
     */
    startAutoRefresh() {
        this.refreshTimer = setInterval(() => {
            if (!this.state.isLoading) {
                this.loadDashboardData();
            }
        }, this.config.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    /**
     * Utilidades
     */
    async fetchData(endpoint) {
        const response = await fetch(`${this.config.apiBaseUrl}${endpoint}`, {
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    getCSRFToken() {
        return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }

    showLoader() {
        const loader = document.getElementById('dashboard-loader');
        if (loader) loader.classList.remove('d-none');
    }

    hideLoader() {
        const loader = document.getElementById('dashboard-loader');
        if (loader) loader.classList.add('d-none');
    }

    showError(message) {
        this.showNotification({
            type: 'error',
            title: 'Error',
            message: message
        });
    }

    showSuccess(message) {
        this.showNotification({
            type: 'success',
            title: 'Éxito',
            message: message
        });
    }

    showNotification(notification) {
        // Implementar sistema de notificaciones
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${this.getToastClass(notification.type)} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${notification.title}</strong><br>
                    ${notification.message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        const container = document.getElementById('toast-container') || document.body;
        container.appendChild(toast);

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Remover toast después de que se oculte
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    getToastClass(type) {
        const classes = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info'
        };
        return classes[type] || 'info';
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-ES', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    getStatusClass(status) {
        const classes = {
            'active': 'success',
            'inactive': 'secondary',
            'pending': 'warning',
            'suspended': 'danger'
        };
        return classes[status] || 'secondary';
    }

    getProgressColor(progress) {
        if (progress >= 75) return 'success';
        if (progress >= 50) return 'info';
        if (progress >= 25) return 'warning';
        return 'danger';
    }

    animateValue(element, start, end, duration) {
        const range = end - start;
        const startTime = Date.now();

        const timer = setInterval(() => {
            const now = Date.now();
            const elapsed = now - startTime;
            
            if (elapsed >= duration) {
                element.textContent = end;
                clearInterval(timer);
            } else {
                const progress = elapsed / duration;
                const current = Math.round(start + (range * progress));
                element.textContent = current;
            }
        }, 16);
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.resize === 'function') {
                chart.resize();
            }
        });
    }

    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.className = connected ? 'text-success' : 'text-danger';
            indicator.title = connected ? 'Conectado' : 'Desconectado';
        }
    }

    updateLastRefreshTime() {
        const element = document.getElementById('last-refresh-time');
        if (element) {
            element.textContent = this.formatDate(this.state.lastUpdate);
        }
    }

    /**
     * Cleanup al destruir el módulo
     */
    destroy() {
        this.stopAutoRefresh();
        
        if (this.socket) {
            this.socket.disconnect();
        }

        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });

        console.log('🧹 ClientDashboard destroyed');
    }
}

// Inicialización automática cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.classList.contains('client-dashboard')) {
        window.clientDashboard = new ClientDashboard();
    }
});

// Exportar para uso global
export default ClientDashboard;