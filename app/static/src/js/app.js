/**
 * App.js - Funcionalidades Específicas del Ecosistema de Emprendimiento
 * ====================================================================
 * 
 * Contiene toda la lógica de negocio específica del ecosistema,
 * componentes UI avanzados, workflows y funcionalidades especializadas
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js
 */

'use strict';

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
    throw new Error('main.js debe cargarse antes que app.js');
}

// Alias para facilitar acceso
const App = window.EcosistemaApp;

// ============================================================================
// CONFIGURACIÓN ESPECÍFICA DEL ECOSISTEMA
// ============================================================================

/**
 * Configuración específica del ecosistema de emprendimiento
 */
App.ecosystem = {
    // Tipos de usuarios del ecosistema
    userTypes: {
        ENTREPRENEUR: 'entrepreneur',
        MENTOR: 'mentor', 
        ADMIN: 'admin',
        CLIENT: 'client',
        GUEST: 'guest'
    },

    // Estados de proyectos
    projectStates: {
        IDEA: 'idea',
        VALIDATION: 'validation',
        DEVELOPMENT: 'development',
        LAUNCH: 'launch',
        GROWTH: 'growth',
        MATURE: 'mature',
        PIVOT: 'pivot',
        SUSPENDED: 'suspended'
    },

    // Tipos de reuniones
    meetingTypes: {
        MENTORSHIP: 'mentorship',
        WORKSHOP: 'workshop',
        NETWORKING: 'networking',
        DEMO_DAY: 'demo_day',
        EVALUATION: 'evaluation',
        FOLLOW_UP: 'follow_up'
    },

    // Categorías de emprendimiento
    categories: {
        TECH: 'technology',
        HEALTH: 'health',
        EDUCATION: 'education',
        FINTECH: 'fintech',
        ECOMMERCE: 'ecommerce',
        SUSTAINABILITY: 'sustainability',
        SOCIAL: 'social_impact',
        AGRICULTURE: 'agriculture',
        TOURISM: 'tourism',
        MANUFACTURING: 'manufacturing'
    },

    // Niveles de progreso
    progressLevels: {
        BEGINNER: 1,
        INTERMEDIATE: 2,
        ADVANCED: 3,
        EXPERT: 4
    },

    // Configuración de métricas
    metrics: {
        refreshInterval: 30000, // 30 segundos
        chartColors: [
            '#2563eb', '#10b981', '#f59e0b', '#dc2626', 
            '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16'
        ],
        animationDuration: 1000
    }
};

// ============================================================================
// GESTIÓN DE DATOS DEL ECOSISTEMA
// ============================================================================

/**
 * Manejador de datos específicos del ecosistema
 */
App.data = {
    // Cache de datos
    cache: {
        entrepreneurs: new Map(),
        mentors: new Map(),
        projects: new Map(),
        meetings: new Map(),
        metrics: new Map()
    },

    // Estado de sincronización
    lastSync: {
        entrepreneurs: null,
        mentors: null,
        projects: null,
        meetings: null,
        metrics: null
    },

    /**
     * Obtener datos con cache inteligente
     * @param {string} type - Tipo de datos
     * @param {Object} params - Parámetros de consulta
     * @param {boolean} forceRefresh - Forzar actualización
     * @return {Promise} Datos solicitados
     */
    async get(type, params = {}, forceRefresh = false) {
        const cacheKey = this.generateCacheKey(type, params);
        const cachedData = this.cache[type]?.get(cacheKey);
        const lastSync = this.lastSync[type];
        const cacheExpiry = 5 * 60 * 1000; // 5 minutos

        // Verificar si necesitamos actualizar
        const needsRefresh = forceRefresh || 
            !cachedData || 
            !lastSync || 
            (Date.now() - lastSync) > cacheExpiry;

        if (!needsRefresh) {
            return cachedData;
        }

        try {
            const data = await this.fetchData(type, params);
            
            // Actualizar cache
            if (!this.cache[type]) {
                this.cache[type] = new Map();
            }
            this.cache[type].set(cacheKey, data);
            this.lastSync[type] = Date.now();

            return data;
        } catch (error) {
            console.error(`Error fetching ${type}:`, error);
            
            // Devolver datos en cache si existen
            if (cachedData) {
                App.notifications.warning('Mostrando datos en cache. Conexión limitada.');
                return cachedData;
            }
            
            throw error;
        }
    },

    /**
     * Generar clave de cache
     * @param {string} type - Tipo de datos
     * @param {Object} params - Parámetros
     * @return {string} Clave de cache
     */
    generateCacheKey(type, params) {
        return `${type}_${JSON.stringify(params)}`;
    },

    /**
     * Obtener datos del servidor
     * @param {string} type - Tipo de datos
     * @param {Object} params - Parámetros
     * @return {Promise} Datos del servidor
     */
    async fetchData(type, params = {}) {
        const endpoints = {
            entrepreneurs: '/entrepreneurs',
            mentors: '/mentors',
            projects: '/projects',
            meetings: '/meetings',
            metrics: '/analytics/metrics'
        };

        const endpoint = endpoints[type];
        if (!endpoint) {
            throw new Error(`Endpoint no encontrado para tipo: ${type}`);
        }

        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;

        return await App.http.get(url);
    },

    /**
     * Invalidar cache específico
     * @param {string} type - Tipo de datos
     * @param {Object} params - Parámetros específicos
     */
    invalidateCache(type, params = null) {
        if (params) {
            const cacheKey = this.generateCacheKey(type, params);
            this.cache[type]?.delete(cacheKey);
        } else {
            this.cache[type]?.clear();
            this.lastSync[type] = null;
        }
    },

    /**
     * Limpiar todo el cache
     */
    clearCache() {
        Object.keys(this.cache).forEach(type => {
            this.cache[type].clear();
            this.lastSync[type] = null;
        });
    }
};

// ============================================================================
// DASHBOARD Y MÉTRICAS
// ============================================================================

/**
 * Sistema de dashboard con métricas en tiempo real
 */
App.dashboard = {
    charts: {},
    refreshInterval: null,
    isVisible: true,

    /**
     * Inicializar dashboard
     */
    async init() {
        if (!document.querySelector('.dashboard')) return;

        await this.loadMetrics();
        this.initCharts();
        this.bindEvents();
        this.startAutoRefresh();
        
        console.log('📊 Dashboard inicializado');
    },

    /**
     * Cargar métricas del dashboard
     */
    async loadMetrics() {
        try {
            App.loading.show('Cargando métricas...');
            
            const metrics = await App.data.get('metrics', {
                period: this.getSelectedPeriod(),
                user_type: App.userType
            });

            this.renderMetrics(metrics);
            
        } catch (error) {
            console.error('Error cargando métricas:', error);
            App.notifications.error('Error al cargar las métricas del dashboard');
        } finally {
            App.loading.hide();
        }
    },

    /**
     * Renderizar métricas
     * @param {Object} metrics - Datos de métricas
     */
    renderMetrics(metrics) {
        // Métricas principales
        this.renderKPIs(metrics.kpis || {});
        
        // Gráficos
        this.renderGrowthChart(metrics.growth || []);
        this.renderCategoriesChart(metrics.categories || []);
        this.renderActivityChart(metrics.activity || []);
        this.renderFunnelChart(metrics.funnel || []);
        
        // Tabla de actividad reciente
        this.renderRecentActivity(metrics.recent_activity || []);
        
        // Lista de próximas reuniones
        this.renderUpcomingMeetings(metrics.upcoming_meetings || []);
    },

    /**
     * Renderizar KPIs principales
     * @param {Object} kpis - Datos de KPIs
     */
    renderKPIs(kpis) {
        const kpiContainer = document.querySelector('.kpi-cards');
        if (!kpiContainer) return;

        const kpiConfigs = {
            total_entrepreneurs: {
                title: 'Emprendedores Activos',
                icon: 'fa-users',
                color: 'primary'
            },
            total_projects: {
                title: 'Proyectos en Desarrollo',
                icon: 'fa-rocket',
                color: 'success'
            },
            total_meetings: {
                title: 'Reuniones este Mes',
                icon: 'fa-calendar',
                color: 'info'
            },
            success_rate: {
                title: 'Tasa de Éxito',
                icon: 'fa-chart-line',
                color: 'warning',
                suffix: '%'
            }
        };

        let html = '';
        Object.entries(kpiConfigs).forEach(([key, config]) => {
            const value = kpis[key] || 0;
            const change = kpis[`${key}_change`] || 0;
            const changeClass = change >= 0 ? 'positive' : 'negative';
            const changeIcon = change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';

            html += `
                <div class="col-md-3">
                    <div class="card metric-card metric-${config.color} h-100">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="card-subtitle mb-2 text-muted">${config.title}</h6>
                                    <h2 class="card-title mb-0">
                                        ${App.utils.formatNumber(value)}${config.suffix || ''}
                                    </h2>
                                    <div class="metric-change ${changeClass} mt-2">
                                        <i class="fa ${changeIcon} me-1"></i>
                                        ${Math.abs(change)}% vs mes anterior
                                    </div>
                                </div>
                                <div class="metric-icon">
                                    <i class="fa ${config.icon}"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        kpiContainer.innerHTML = html;
        
        // Animar entrada de cards
        kpiContainer.querySelectorAll('.metric-card').forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.classList.add('animate__animated', 'animate__fadeInUp');
        });
    },

    /**
     * Renderizar gráfico de crecimiento
     * @param {Array} data - Datos de crecimiento
     */
    renderGrowthChart(data) {
        const canvas = document.getElementById('growthChart');
        if (!canvas) return;

        // Destruir gráfico existente
        if (this.charts.growth) {
            this.charts.growth.destroy();
        }

        const ctx = canvas.getContext('2d');
        this.charts.growth = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.date),
                datasets: [{
                    label: 'Emprendedores',
                    data: data.map(item => item.entrepreneurs),
                    borderColor: App.ecosystem.metrics.chartColors[0],
                    backgroundColor: App.ecosystem.metrics.chartColors[0] + '20',
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Proyectos',
                    data: data.map(item => item.projects),
                    borderColor: App.ecosystem.metrics.chartColors[1],
                    backgroundColor: App.ecosystem.metrics.chartColors[1] + '20',
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
                    },
                    title: {
                        display: true,
                        text: 'Crecimiento del Ecosistema'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return App.utils.formatNumber(value);
                            }
                        }
                    }
                },
                animation: {
                    duration: App.ecosystem.metrics.animationDuration
                }
            }
        });
    },

    /**
     * Renderizar gráfico de categorías
     * @param {Array} data - Datos por categorías
     */
    renderCategoriesChart(data) {
        const canvas = document.getElementById('categoriesChart');
        if (!canvas) return;

        if (this.charts.categories) {
            this.charts.categories.destroy();
        }

        const ctx = canvas.getContext('2d');
        this.charts.categories = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.name),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: App.ecosystem.metrics.chartColors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right'
                    },
                    title: {
                        display: true,
                        text: 'Proyectos por Categoría'
                    }
                },
                animation: {
                    duration: App.ecosystem.metrics.animationDuration
                }
            }
        });
    },

    /**
     * Renderizar gráfico de actividad
     * @param {Array} data - Datos de actividad
     */
    renderActivityChart(data) {
        const canvas = document.getElementById('activityChart');
        if (!canvas) return;

        if (this.charts.activity) {
            this.charts.activity.destroy();
        }

        const ctx = canvas.getContext('2d');
        this.charts.activity = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.day),
                datasets: [{
                    label: 'Reuniones',
                    data: data.map(item => item.meetings),
                    backgroundColor: App.ecosystem.metrics.chartColors[2] + '80',
                    borderColor: App.ecosystem.metrics.chartColors[2],
                    borderWidth: 1
                }, {
                    label: 'Mensajes',
                    data: data.map(item => item.messages),
                    backgroundColor: App.ecosystem.metrics.chartColors[3] + '80',
                    borderColor: App.ecosystem.metrics.chartColors[3],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: 'Actividad Semanal'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        stacked: false
                    }
                },
                animation: {
                    duration: App.ecosystem.metrics.animationDuration
                }
            }
        });
    },

    /**
     * Renderizar gráfico de embudo
     * @param {Array} data - Datos del embudo
     */
    renderFunnelChart(data) {
        const container = document.getElementById('funnelChart');
        if (!container) return;

        let html = '<div class="funnel-chart">';
        const total = data.length > 0 ? data[0].count : 1;

        data.forEach((stage, index) => {
            const percentage = (stage.count / total) * 100;
            const width = Math.max(percentage, 10); // Mínimo 10%

            html += `
                <div class="funnel-stage" style="width: ${width}%">
                    <div class="stage-content">
                        <span class="stage-name">${stage.name}</span>
                        <span class="stage-count">${App.utils.formatNumber(stage.count)}</span>
                        <span class="stage-percentage">${percentage.toFixed(1)}%</span>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Animar entrada
        container.querySelectorAll('.funnel-stage').forEach((stage, index) => {
            stage.style.animationDelay = `${index * 0.2}s`;
            stage.classList.add('animate__animated', 'animate__fadeInLeft');
        });
    },

    /**
     * Renderizar actividad reciente
     * @param {Array} activities - Actividades recientes
     */
    renderRecentActivity(activities) {
        const container = document.querySelector('.recent-activity-list');
        if (!container) return;

        if (!activities.length) {
            container.innerHTML = '<p class="text-muted">No hay actividad reciente</p>';
            return;
        }

        let html = '';
        activities.forEach(activity => {
            const iconMap = {
                project_created: 'fa-rocket text-success',
                meeting_scheduled: 'fa-calendar text-info',
                message_sent: 'fa-comment text-primary',
                user_registered: 'fa-user-plus text-warning'
            };

            const icon = iconMap[activity.type] || 'fa-circle text-muted';
            const timeAgo = App.utils.formatRelativeTime(activity.created_at);

            html += `
                <div class="activity-item d-flex align-items-center mb-3">
                    <div class="activity-icon me-3">
                        <i class="fa ${icon}"></i>
                    </div>
                    <div class="activity-content flex-grow-1">
                        <div class="activity-description">${activity.description}</div>
                        <small class="text-muted">${timeAgo}</small>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    /**
     * Renderizar próximas reuniones
     * @param {Array} meetings - Próximas reuniones
     */
    renderUpcomingMeetings(meetings) {
        const container = document.querySelector('.upcoming-meetings-list');
        if (!container) return;

        if (!meetings.length) {
            container.innerHTML = '<p class="text-muted">No hay reuniones programadas</p>';
            return;
        }

        let html = '';
        meetings.forEach(meeting => {
            const meetingDate = new Date(meeting.scheduled_at);
            const timeUntil = App.utils.formatRelativeTime(meeting.scheduled_at);

            html += `
                <div class="meeting-item card mb-2">
                    <div class="card-body p-3">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h6 class="mb-1">${meeting.title}</h6>
                                <p class="mb-1 text-muted">${meeting.description || 'Sin descripción'}</p>
                                <small class="text-info">
                                    <i class="fa fa-clock me-1"></i>
                                    ${timeUntil}
                                </small>
                            </div>
                            <div class="meeting-actions">
                                <button class="btn btn-sm btn-outline-primary" onclick="App.meetings.join('${meeting.id}')">
                                    <i class="fa fa-video me-1"></i>Unirse
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    /**
     * Inicializar gráficos
     */
    initCharts() {
        // Configuración global de Chart.js
        Chart.defaults.font.family = 'Inter, sans-serif';
        Chart.defaults.color = '#6b7280';
        Chart.defaults.borderColor = '#e5e7eb';
    },

    /**
     * Vincular eventos del dashboard
     */
    bindEvents() {
        // Selector de período
        const periodSelect = document.getElementById('dashboardPeriod');
        if (periodSelect) {
            periodSelect.addEventListener('change', () => {
                this.loadMetrics();
            });
        }

        // Botón de actualizar
        const refreshBtn = document.getElementById('refreshDashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                App.data.invalidateCache('metrics');
                this.loadMetrics();
            });
        }

        // Detectar visibilidad de la página
        document.addEventListener('visibilitychange', () => {
            this.isVisible = !document.hidden;
            if (this.isVisible) {
                this.loadMetrics();
            }
        });
    },

    /**
     * Obtener período seleccionado
     * @return {string} Período seleccionado
     */
    getSelectedPeriod() {
        const select = document.getElementById('dashboardPeriod');
        return select ? select.value : '30d';
    },

    /**
     * Iniciar actualización automática
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.isVisible) {
                this.loadMetrics();
            }
        }, App.ecosystem.metrics.refreshInterval);
    },

    /**
     * Detener actualización automática
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    },

    /**
     * Destruir dashboard
     */
    destroy() {
        this.stopAutoRefresh();
        
        // Destruir gráficos
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        
        this.charts = {};
    }
};

// ============================================================================
// GESTIÓN DE PROYECTOS
// ============================================================================

/**
 * Sistema de gestión de proyectos
 */
App.projects = {
    currentProject: null,
    kanbanBoard: null,

    /**
     * Inicializar sistema de proyectos
     */
    async init() {
        if (!document.querySelector('.projects-page')) return;

        await this.loadProjects();
        this.initKanban();
        this.bindEvents();
        
        console.log('🚀 Sistema de proyectos inicializado');
    },

    /**
     * Cargar proyectos
     */
    async loadProjects() {
        try {
            const projects = await App.data.get('projects', {
                user_id: App.currentUser?.id,
                include_team: true
            });

            this.renderProjectsList(projects);
            
        } catch (error) {
            console.error('Error cargando proyectos:', error);
            App.notifications.error('Error al cargar los proyectos');
        }
    },

    /**
     * Renderizar lista de proyectos
     * @param {Array} projects - Lista de proyectos
     */
    renderProjectsList(projects) {
        const container = document.querySelector('.projects-list');
        if (!container) return;

        if (!projects.length) {
            container.innerHTML = `
                <div class="empty-state text-center p-5">
                    <i class="fa fa-rocket fa-3x text-muted mb-3"></i>
                    <h4>No tienes proyectos aún</h4>
                    <p class="text-muted">Crea tu primer proyecto para comenzar tu emprendimiento</p>
                    <button class="btn btn-primary" onclick="App.projects.showCreateModal()">
                        <i class="fa fa-plus me-2"></i>Crear Proyecto
                    </button>
                </div>
            `;
            return;
        }

        let html = '';
        projects.forEach(project => {
            const progress = this.calculateProgress(project);
            const statusClass = this.getStatusClass(project.status);

            html += `
                <div class="col-lg-4 col-md-6 mb-4">
                    <div class="card project-card h-100" data-project-id="${project.id}">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <span class="badge bg-${statusClass}">${project.status}</span>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="dropdown">
                                    <i class="fa fa-ellipsis-v"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item" href="#" onclick="App.projects.edit('${project.id}')">Editar</a></li>
                                    <li><a class="dropdown-item" href="#" onclick="App.projects.duplicate('${project.id}')">Duplicar</a></li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li><a class="dropdown-item text-danger" href="#" onclick="App.projects.delete('${project.id}')">Eliminar</a></li>
                                </ul>
                            </div>
                        </div>
                        <div class="card-body">
                            <h5 class="card-title">${project.name}</h5>
                            <p class="card-text text-muted">${App.utils.truncateText(project.description, 80)}</p>
                            
                            <div class="project-meta mb-3">
                                <small class="text-muted">
                                    <i class="fa fa-tag me-1"></i>${project.category}
                                </small>
                                <small class="text-muted ms-3">
                                    <i class="fa fa-calendar me-1"></i>${App.utils.formatRelativeTime(project.created_at)}
                                </small>
                            </div>

                            <div class="progress mb-3" style="height: 6px;">
                                <div class="progress-bar bg-${statusClass}" style="width: ${progress}%"></div>
                            </div>

                            <div class="project-team d-flex align-items-center">
                                <div class="team-avatars me-2">
                                    ${this.renderTeamAvatars(project.team || [])}
                                </div>
                                <small class="text-muted">${project.team?.length || 0} miembros</small>
                            </div>
                        </div>
                        <div class="card-footer bg-transparent">
                            <div class="d-flex justify-content-between">
                                <button class="btn btn-outline-primary btn-sm" onclick="App.projects.view('${project.id}')">
                                    Ver Detalles
                                </button>
                                <button class="btn btn-primary btn-sm" onclick="App.projects.openKanban('${project.id}')">
                                    Abrir Tablero
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    /**
     * Calcular progreso del proyecto
     * @param {Object} project - Proyecto
     * @return {number} Porcentaje de progreso
     */
    calculateProgress(project) {
        if (!project.tasks) return 0;
        
        const total = project.tasks.length;
        const completed = project.tasks.filter(task => task.status === 'completed').length;
        
        return total > 0 ? Math.round((completed / total) * 100) : 0;
    },

    /**
     * Obtener clase de estado
     * @param {string} status - Estado del proyecto
     * @return {string} Clase CSS
     */
    getStatusClass(status) {
        const statusMap = {
            [App.ecosystem.projectStates.IDEA]: 'secondary',
            [App.ecosystem.projectStates.VALIDATION]: 'info',
            [App.ecosystem.projectStates.DEVELOPMENT]: 'warning',
            [App.ecosystem.projectStates.LAUNCH]: 'primary',
            [App.ecosystem.projectStates.GROWTH]: 'success',
            [App.ecosystem.projectStates.MATURE]: 'success',
            [App.ecosystem.projectStates.PIVOT]: 'warning',
            [App.ecosystem.projectStates.SUSPENDED]: 'danger'
        };

        return statusMap[status] || 'secondary';
    },

    /**
     * Renderizar avatares del equipo
     * @param {Array} team - Miembros del equipo
     * @return {string} HTML de avatares
     */
    renderTeamAvatars(team) {
        if (!team.length) return '<small class="text-muted">Sin equipo</small>';

        const maxShow = 3;
        let html = '';
        
        team.slice(0, maxShow).forEach(member => {
            html += `
                <img src="${member.avatar || '/static/img/default-avatar.png'}" 
                     alt="${member.name}" 
                     class="rounded-circle me-1" 
                     width="24" height="24" 
                     title="${member.name}">
            `;
        });

        if (team.length > maxShow) {
            html += `<span class="badge bg-secondary rounded-circle">+${team.length - maxShow}</span>`;
        }

        return html;
    },

    /**
     * Inicializar tablero Kanban
     */
    initKanban() {
        const kanbanContainer = document.getElementById('kanban-board');
        if (!kanbanContainer) return;

        // Implementar lógica de Kanban usando SortableJS o similar
        this.setupKanbanColumns();
        this.bindKanbanEvents();
    },

    /**
     * Configurar columnas del Kanban
     */
    setupKanbanColumns() {
        const columns = [
            { id: 'todo', title: 'Por Hacer', color: 'secondary' },
            { id: 'in_progress', title: 'En Progreso', color: 'warning' },
            { id: 'review', title: 'En Revisión', color: 'info' },
            { id: 'done', title: 'Completado', color: 'success' }
        ];

        const kanbanBoard = document.getElementById('kanban-board');
        if (!kanbanBoard) return;

        let html = '<div class="row">';
        columns.forEach(column => {
            html += `
                <div class="col-md-3">
                    <div class="kanban-column" data-column="${column.id}">
                        <div class="column-header bg-${column.color} text-white p-3 rounded-top">
                            <h6 class="mb-0">${column.title}</h6>
                            <small class="column-count">0 tareas</small>
                        </div>
                        <div class="column-body p-2 bg-light" style="min-height: 400px;">
                            <div class="tasks-list" data-status="${column.id}">
                                <!-- Las tareas se cargarán aquí -->
                            </div>
                            <button class="btn btn-outline-primary btn-sm w-100 mt-2" 
                                    onclick="App.projects.addTask('${column.id}')">
                                <i class="fa fa-plus me-1"></i>Agregar Tarea
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        kanbanBoard.innerHTML = html;
    },

    /**
     * Vincular eventos del Kanban
     */
    bindKanbanEvents() {
        // Implementar drag & drop entre columnas
        // Esto requeriría una librería como SortableJS
    },

    /**
     * Ver detalles del proyecto
     * @param {string} projectId - ID del proyecto
     */
    async view(projectId) {
        try {
            const project = await App.data.get('projects', { id: projectId });
            this.showProjectModal(project);
        } catch (error) {
            App.notifications.error('Error al cargar el proyecto');
        }
    },

    /**
     * Mostrar modal de proyecto
     * @param {Object} project - Datos del proyecto
     */
    showProjectModal(project) {
        const modal = new bootstrap.Modal(document.getElementById('projectModal'));
        
        // Llenar datos del modal
        document.getElementById('projectModalTitle').textContent = project.name;
        document.getElementById('projectModalDescription').textContent = project.description;
        
        modal.show();
    },

    /**
     * Mostrar modal de creación
     */
    showCreateModal() {
        const modal = new bootstrap.Modal(document.getElementById('createProjectModal'));
        modal.show();
    },

    /**
     * Crear nuevo proyecto
     * @param {Object} projectData - Datos del proyecto
     */
    async create(projectData) {
        try {
            App.loading.show('Creando proyecto...');
            
            const project = await App.http.post('/projects', projectData);
            
            App.notifications.success('Proyecto creado exitosamente');
            App.data.invalidateCache('projects');
            await this.loadProjects();
            
            return project;
        } catch (error) {
            App.notifications.error('Error al crear el proyecto');
            throw error;
        } finally {
            App.loading.hide();
        }
    },

    /**
     * Vincular eventos
     */
    bindEvents() {
        // Filtros de proyectos
        const statusFilter = document.getElementById('projectStatusFilter');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => {
                this.filterProjects();
            });
        }

        // Búsqueda de proyectos
        const searchInput = document.getElementById('projectSearch');
        if (searchInput) {
            searchInput.addEventListener('input', App.utils.debounce(() => {
                this.searchProjects(searchInput.value);
            }, 300));
        }
    }
};

// ============================================================================
// SISTEMA DE REUNIONES
// ============================================================================

/**
 * Sistema de gestión de reuniones
 */
App.meetings = {
    calendar: null,
    currentMeeting: null,

    /**
     * Inicializar sistema de reuniones
     */
    async init() {
        if (!document.querySelector('.meetings-page')) return;

        await this.loadMeetings();
        this.initCalendar();
        this.bindEvents();
        
        console.log('📅 Sistema de reuniones inicializado');
    },

    /**
     * Cargar reuniones
     */
    async loadMeetings() {
        try {
            const meetings = await App.data.get('meetings', {
                user_id: App.currentUser?.id,
                start_date: new Date().toISOString().split('T')[0],
                include_participants: true
            });

            this.renderMeetingsList(meetings);
            
        } catch (error) {
            console.error('Error cargando reuniones:', error);
            App.notifications.error('Error al cargar las reuniones');
        }
    },

    /**
     * Renderizar lista de reuniones
     * @param {Array} meetings - Lista de reuniones
     */
    renderMeetingsList(meetings) {
        const container = document.querySelector('.meetings-list');
        if (!container) return;

        const now = new Date();
        const upcoming = meetings.filter(m => new Date(m.scheduled_at) > now);
        const past = meetings.filter(m => new Date(m.scheduled_at) <= now);

        let html = '<div class="meetings-sections">';

        // Próximas reuniones
        html += '<div class="upcoming-meetings mb-4">';
        html += '<h5><i class="fa fa-clock me-2"></i>Próximas Reuniones</h5>';
        
        if (!upcoming.length) {
            html += '<p class="text-muted">No tienes reuniones programadas</p>';
        } else {
            upcoming.forEach(meeting => {
                html += this.renderMeetingCard(meeting, true);
            });
        }
        
        html += '</div>';

        // Reuniones pasadas
        html += '<div class="past-meetings">';
        html += '<h5><i class="fa fa-history me-2"></i>Reuniones Anteriores</h5>';
        
        if (!past.length) {
            html += '<p class="text-muted">No hay reuniones anteriores</p>';
        } else {
            past.slice(0, 5).forEach(meeting => {
                html += this.renderMeetingCard(meeting, false);
            });
        }
        
        html += '</div></div>';

        container.innerHTML = html;
    },

    /**
     * Renderizar tarjeta de reunión
     * @param {Object} meeting - Reunión
     * @param {boolean} isUpcoming - Es próxima reunión
     * @return {string} HTML de la tarjeta
     */
    renderMeetingCard(meeting, isUpcoming) {
        const meetingDate = new Date(meeting.scheduled_at);
        const typeClass = this.getMeetingTypeClass(meeting.type);
        const timeInfo = isUpcoming ? 
            App.utils.formatRelativeTime(meeting.scheduled_at) :
            meetingDate.toLocaleDateString('es-CO');

        return `
            <div class="card meeting-card mb-3" data-meeting-id="${meeting.id}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center mb-2">
                                <span class="badge bg-${typeClass} me-2">${meeting.type}</span>
                                <h6 class="mb-0">${meeting.title}</h6>
                            </div>
                            <p class="text-muted mb-2">${meeting.description || 'Sin descripción'}</p>
                            
                            <div class="meeting-meta">
                                <small class="text-info me-3">
                                    <i class="fa fa-clock me-1"></i>${timeInfo}
                                </small>
                                <small class="text-muted me-3">
                                    <i class="fa fa-stopwatch me-1"></i>${meeting.duration || 60} min
                                </small>
                                <small class="text-muted">
                                    <i class="fa fa-users me-1"></i>${meeting.participants?.length || 0} participantes
                                </small>
                            </div>
                        </div>
                        
                        <div class="meeting-actions">
                            ${isUpcoming ? this.renderUpcomingActions(meeting) : this.renderPastActions(meeting)}
                        </div>
                    </div>
                    
                    ${meeting.participants?.length ? this.renderParticipants(meeting.participants) : ''}
                </div>
            </div>
        `;
    },

    /**
     * Renderizar acciones para reuniones próximas
     * @param {Object} meeting - Reunión
     * @return {string} HTML de acciones
     */
    renderUpcomingActions(meeting) {
        const isStartingSoon = this.isStartingSoon(meeting.scheduled_at);
        
        return `
            <div class="btn-group-vertical btn-group-sm">
                ${meeting.meeting_url ? `
                    <button class="btn btn-primary ${isStartingSoon ? 'pulse' : ''}" 
                            onclick="App.meetings.join('${meeting.id}')">
                        <i class="fa fa-video me-1"></i>Unirse
                    </button>
                ` : ''}
                <button class="btn btn-outline-secondary" 
                        onclick="App.meetings.reschedule('${meeting.id}')">
                    <i class="fa fa-calendar me-1"></i>Reprogramar
                </button>
                <button class="btn btn-outline-danger" 
                        onclick="App.meetings.cancel('${meeting.id}')">
                    <i class="fa fa-times me-1"></i>Cancelar
                </button>
            </div>
        `;
    },

    /**
     * Renderizar acciones para reuniones pasadas
     * @param {Object} meeting - Reunión
     * @return {string} HTML de acciones
     */
    renderPastActions(meeting) {
        return `
            <div class="btn-group-vertical btn-group-sm">
                <button class="btn btn-outline-primary" 
                        onclick="App.meetings.viewNotes('${meeting.id}')">
                    <i class="fa fa-file-text me-1"></i>Ver Notas
                </button>
                <button class="btn btn-outline-secondary" 
                        onclick="App.meetings.reschedule('${meeting.id}')">
                    <i class="fa fa-copy me-1"></i>Duplicar
                </button>
            </div>
        `;
    },

    /**
     * Renderizar participantes
     * @param {Array} participants - Lista de participantes
     * @return {string} HTML de participantes
     */
    renderParticipants(participants) {
        if (!participants.length) return '';

        let html = '<div class="participants mt-3 pt-3 border-top">';
        html += '<small class="text-muted me-2">Participantes:</small>';
        
        participants.forEach(participant => {
            const statusClass = participant.status === 'confirmed' ? 'success' : 
                               participant.status === 'declined' ? 'danger' : 'warning';
            
            html += `
                <span class="badge bg-${statusClass} me-1" title="${participant.status}">
                    ${participant.name}
                </span>
            `;
        });
        
        html += '</div>';
        return html;
    },

    /**
     * Obtener clase de tipo de reunión
     * @param {string} type - Tipo de reunión
     * @return {string} Clase CSS
     */
    getMeetingTypeClass(type) {
        const typeMap = {
            [App.ecosystem.meetingTypes.MENTORSHIP]: 'primary',
            [App.ecosystem.meetingTypes.WORKSHOP]: 'info',
            [App.ecosystem.meetingTypes.NETWORKING]: 'success',
            [App.ecosystem.meetingTypes.DEMO_DAY]: 'warning',
            [App.ecosystem.meetingTypes.EVALUATION]: 'secondary',
            [App.ecosystem.meetingTypes.FOLLOW_UP]: 'dark'
        };

        return typeMap[type] || 'secondary';
    },

    /**
     * Verificar si la reunión está por comenzar
     * @param {string} scheduledAt - Fecha programada
     * @return {boolean} Está por comenzar
     */
    isStartingSoon(scheduledAt) {
        const meetingTime = new Date(scheduledAt);
        const now = new Date();
        const diffMinutes = (meetingTime - now) / (1000 * 60);
        
        return diffMinutes <= 15 && diffMinutes >= -5; // 15 min antes, 5 min después
    },

    /**
     * Unirse a reunión
     * @param {string} meetingId - ID de la reunión
     */
    async join(meetingId) {
        try {
            const meeting = await App.http.get(`/meetings/${meetingId}`);
            
            if (meeting.meeting_url) {
                window.open(meeting.meeting_url, '_blank');
                
                // Registrar asistencia
                await App.http.post(`/meetings/${meetingId}/attendance`, {
                    status: 'joined',
                    joined_at: new Date().toISOString()
                });
            } else {
                App.notifications.warning('La reunión aún no tiene enlace disponible');
            }
        } catch (error) {
            App.notifications.error('Error al unirse a la reunión');
        }
    },

    /**
     * Inicializar calendario
     */
    initCalendar() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) return;

        // Implementar calendario usando FullCalendar o similar
        // Por ahora, mostrar placeholder
        calendarEl.innerHTML = `
            <div class="calendar-placeholder text-center p-5">
                <i class="fa fa-calendar-alt fa-3x text-muted mb-3"></i>
                <h5>Calendario de Reuniones</h5>
                <p class="text-muted">El calendario se implementará con FullCalendar</p>
            </div>
        `;
    },

    /**
     * Vincular eventos
     */
    bindEvents() {
        // Filtros de reuniones
        const typeFilter = document.getElementById('meetingTypeFilter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                this.filterMeetings();
            });
        }

        // Programar nueva reunión
        const scheduleBtn = document.getElementById('scheduleMeeting');
        if (scheduleBtn) {
            scheduleBtn.addEventListener('click', () => {
                this.showScheduleModal();
            });
        }
    }
};

// ============================================================================
// CHAT Y MENSAJERÍA
// ============================================================================

/**
 * Sistema de chat y mensajería
 */
App.chat = {
    activeConversation: null,
    messageContainer: null,
    isTyping: false,

    /**
     * Inicializar sistema de chat
     */
    init() {
        if (!document.querySelector('.chat-container')) return;

        this.bindEvents();
        this.initEmojiPicker();
        this.loadConversations();
        
        console.log('💬 Sistema de chat inicializado');
    },

    /**
     * Cargar conversaciones
     */
    async loadConversations() {
        try {
            const conversations = await App.http.get('/conversations');
            this.renderConversationsList(conversations);
        } catch (error) {
            console.error('Error cargando conversaciones:', error);
        }
    },

    /**
     * Renderizar lista de conversaciones
     * @param {Array} conversations - Lista de conversaciones
     */
    renderConversationsList(conversations) {
        const container = document.querySelector('.conversations-list');
        if (!container) return;

        let html = '';
        conversations.forEach(conversation => {
            const lastMessage = conversation.last_message;
            const unreadCount = conversation.unread_count || 0;
            const timeAgo = lastMessage ? App.utils.formatRelativeTime(lastMessage.created_at) : '';

            html += `
                <div class="conversation-item ${conversation.id === this.activeConversation?.id ? 'active' : ''}" 
                     data-conversation-id="${conversation.id}"
                     onclick="App.chat.selectConversation('${conversation.id}')">
                    <div class="d-flex align-items-center">
                        <div class="avatar-container me-3">
                            <img src="${conversation.avatar || '/static/img/default-avatar.png'}" 
                                 alt="${conversation.name}" 
                                 class="rounded-circle" 
                                 width="40" height="40">
                            <span class="status-indicator ${conversation.is_online ? 'online' : 'offline'}"></span>
                        </div>
                        <div class="conversation-info flex-grow-1">
                            <div class="d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">${conversation.name}</h6>
                                <small class="text-muted">${timeAgo}</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <p class="mb-0 text-muted small">${App.utils.truncateText(lastMessage?.content || 'Sin mensajes', 30)}</p>
                                ${unreadCount > 0 ? `<span class="badge bg-primary rounded-pill">${unreadCount}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    },

    /**
     * Seleccionar conversación
     * @param {string} conversationId - ID de la conversación
     */
    async selectConversation(conversationId) {
        try {
            const conversation = await App.http.get(`/conversations/${conversationId}`);
            this.activeConversation = conversation;
            
            this.renderConversationHeader(conversation);
            await this.loadMessages(conversationId);
            this.markAsRead(conversationId);
            
        } catch (error) {
            App.notifications.error('Error al cargar la conversación');
        }
    },

    /**
     * Cargar mensajes de una conversación
     * @param {string} conversationId - ID de la conversación
     */
    async loadMessages(conversationId) {
        try {
            const messages = await App.http.get(`/conversations/${conversationId}/messages`);
            this.renderMessages(messages);
        } catch (error) {
            console.error('Error cargando mensajes:', error);
        }
    },

    /**
     * Renderizar mensajes
     * @param {Array} messages - Lista de mensajes
     */
    renderMessages(messages) {
        const container = document.querySelector('.messages-container');
        if (!container) return;

        this.messageContainer = container;
        let html = '';
        
        messages.forEach((message, index) => {
            const isOwn = message.sender_id === App.currentUser?.id;
            const showAvatar = !isOwn && (index === 0 || messages[index - 1].sender_id !== message.sender_id);
            const timeAgo = App.utils.formatRelativeTime(message.created_at);

            html += `
                <div class="message ${isOwn ? 'own' : 'other'} ${showAvatar ? 'show-avatar' : ''}">
                    ${showAvatar ? `
                        <img src="${message.sender_avatar || '/static/img/default-avatar.png'}" 
                             alt="${message.sender_name}" 
                             class="message-avatar rounded-circle" 
                             width="32" height="32">
                    ` : ''}
                    <div class="message-content">
                        <div class="message-bubble">
                            ${this.formatMessageContent(message.content)}
                        </div>
                        <small class="message-time text-muted">${timeAgo}</small>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
        this.scrollToBottom();
    },

    /**
     * Formatear contenido del mensaje
     * @param {string} content - Contenido del mensaje
     * @return {string} Contenido formateado
     */
    formatMessageContent(content) {
        // Escapar HTML
        content = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Convertir enlaces
        content = content.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
        
        // Convertir saltos de línea
        content = content.replace(/\n/g, '<br>');
        
        return content;
    },

    /**
     * Enviar mensaje
     * @param {string} content - Contenido del mensaje
     */
    async sendMessage(content) {
        if (!this.activeConversation || !content.trim()) return;

        try {
            const message = await App.http.post(`/conversations/${this.activeConversation.id}/messages`, {
                content: content.trim()
            });

            this.addMessageToUI(message);
            this.clearMessageInput();
            
        } catch (error) {
            App.notifications.error('Error al enviar el mensaje');
        }
    },

    /**
     * Agregar mensaje a la UI
     * @param {Object} message - Mensaje
     */
    addMessageToUI(message) {
        if (!this.messageContainer) return;

        const isOwn = message.sender_id === App.currentUser?.id;
        const timeAgo = App.utils.formatRelativeTime(message.created_at);

        const messageElement = document.createElement('div');
        messageElement.className = `message ${isOwn ? 'own' : 'other'} show-avatar`;
        messageElement.innerHTML = `
            <div class="message-content">
                <div class="message-bubble">
                    ${this.formatMessageContent(message.content)}
                </div>
                <small class="message-time text-muted">${timeAgo}</small>
            </div>
        `;

        this.messageContainer.appendChild(messageElement);
        this.scrollToBottom();
    },

    /**
     * Limpiar input de mensaje
     */
    clearMessageInput() {
        const input = document.querySelector('.message-input');
        if (input) {
            input.value = '';
            input.style.height = 'auto';
        }
    },

    /**
     * Scroll al final de los mensajes
     */
    scrollToBottom() {
        if (this.messageContainer) {
            this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
        }
    },

    /**
     * Marcar conversación como leída
     * @param {string} conversationId - ID de la conversación
     */
    async markAsRead(conversationId) {
        try {
            await App.http.post(`/conversations/${conversationId}/read`);
        } catch (error) {
            console.warn('Error marcando como leído:', error);
        }
    },

    /**
     * Inicializar selector de emojis
     */
    initEmojiPicker() {
        // Implementar selector de emojis
        // Por ahora, placeholder
        const emojiBtn = document.querySelector('.emoji-picker-btn');
        if (emojiBtn) {
            emojiBtn.addEventListener('click', () => {
                App.notifications.info('Selector de emojis próximamente');
            });
        }
    },

    /**
     * Vincular eventos del chat
     */
    bindEvents() {
        // Input de mensaje
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage(messageInput.value);
                }
            });

            messageInput.addEventListener('input', () => {
                this.adjustTextareaHeight(messageInput);
                this.handleTypingIndicator();
            });
        }

        // Botón de enviar
        const sendBtn = document.querySelector('.send-message-btn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                const input = document.querySelector('.message-input');
                if (input) {
                    this.sendMessage(input.value);
                }
            });
        }
    },

    /**
     * Ajustar altura del textarea
     * @param {Element} textarea - Elemento textarea
     */
    adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    },

    /**
     * Manejar indicador de escritura
     */
    handleTypingIndicator() {
        if (this.isTyping) return;
        
        this.isTyping = true;
        
        // Enviar indicador de escritura
        if (App.websocket.socket && this.activeConversation) {
            App.websocket.send('typing', {
                conversation_id: this.activeConversation.id
            });
        }
        
        // Resetear después de 2 segundos
        setTimeout(() => {
            this.isTyping = false;
        }, 2000);
    }
};

// ============================================================================
// INICIALIZACIÓN ESPECÍFICA DEL ECOSISTEMA
// ============================================================================

/**
 * Inicialización específica de funcionalidades del ecosistema
 */
App.initEcosystem = function() {
    // Determinar qué módulos inicializar según la página actual
    const pageType = document.body.dataset.page;
    
    switch (pageType) {
        case 'dashboard':
            App.dashboard.init();
            break;
        case 'projects':
            App.projects.init();
            break;
        case 'meetings':
            App.meetings.init();
            break;
        case 'chat':
            App.chat.init();
            break;
    }

    // Vincular eventos específicos del WebSocket para el ecosistema
    this.bindEcosystemWebSocketEvents();
    
    console.log('🌱 Funcionalidades del ecosistema inicializadas');
};

/**
 * Vincular eventos específicos del WebSocket
 */
App.bindEcosystemWebSocketEvents = function() {
    // Mensajes de chat en tiempo real
    this.events.addEventListener('chatMessage', (e) => {
        if (App.chat.activeConversation && 
            e.detail.conversation_id === App.chat.activeConversation.id) {
            App.chat.addMessageToUI(e.detail);
        }
    });

    // Actualizaciones de métricas en tiempo real
    this.events.addEventListener('websocket:metrics_update', (e) => {
        if (App.dashboard.isVisible) {
            App.dashboard.loadMetrics();
        }
    });

    // Notificaciones de nuevos proyectos
    this.events.addEventListener('websocket:project_created', (e) => {
        App.notifications.info(`Nuevo proyecto creado: ${e.detail.name}`);
        App.data.invalidateCache('projects');
    });

    // Recordatorios de reuniones
    this.events.addEventListener('websocket:meeting_reminder', (e) => {
        const meeting = e.detail;
        App.notifications.warning(
            `Reunión "${meeting.title}" en ${meeting.minutes} minutos`,
            { duration: 10000 }
        );
    });
};

// ============================================================================
// AUTO-INICIALIZACIÓN DEL ECOSISTEMA
// ============================================================================

// Esperar a que la aplicación principal esté inicializada
App.events.addEventListener('appInitialized', () => {
    App.initEcosystem();
});

// Si la aplicación ya está inicializada, ejecutar inmediatamente
if (document.body.classList.contains('app-loaded')) {
    App.initEcosystem();
}