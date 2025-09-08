/**
 * Ecosistema Emprendimiento - Impact Dashboard Module
 * ==================================================
 *
 * Módulo para visualizar y analizar el impacto del ecosistema.
 * Incluye métricas de impacto social, económico, ambiental,
 * y seguimiento de Objetivos de Desarrollo Sostenible (ODS).
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js, Chart.js
 */

'use strict'

class ImpactDashboard {
  constructor (container, app) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container

    if (!this.container) {
      throw new Error('Container for ImpactDashboard not found')
    }

    this.app = app || window.EcosistemaApp
    this.main = this.app?.main || window.App
    this.state = this.app?.state || window.EcosistemaStateManager
    this.config = window.getConfig ? window.getConfig('modules.impactDashboard', {}) : {}

    // Configuración del módulo
    this.moduleConfig = {
      defaultDateRange: 365, // días
      refreshInterval: 600000, // 10 minutos
      enableRealTimeUpdates: false,
      maxDataPoints: 500,
      chartsConfig: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom'
          },
          tooltip: {
            callbacks: {
              label: (context) => `${context.label}: ${context.formattedValue}`
            }
          }
        }
      },
      ...this.config
    }

    // Estado interno del módulo
    this.moduleState = {
      isInitialized: false,
      isLoading: false,
      lastUpdate: null,
      filters: {
        dateRange: 'last_year',
        sector: 'all',
        region: 'all',
        odsGoal: 'all'
      },
      impactData: null
    }

    this.charts = {}
    this.eventListeners = new Map()

    this.init()
  }

  /**
     * Inicializar módulo
     */
  async init () {
    if (this.moduleState.isInitialized) return

    try {
      console.log('🌍 Inicializando Impact Dashboard')
      this.showLoader(true, 'Inicializando dashboard de impacto...')

      this.createStructure()
      this.bindElements()
      this.setupEventListeners()

      await this.loadDashboardData()
      this.initializeCharts()

      this.setupAutoRefresh()

      this.moduleState.isInitialized = true
      console.log('✅ Impact Dashboard inicializado')
    } catch (error) {
      console.error('❌ Error inicializando Impact Dashboard:', error)
      this.showError('Error al inicializar el dashboard de impacto', error.message)
    } finally {
      this.showLoader(false)
    }
  }

  /**
     * Crear estructura DOM del módulo
     */
  createStructure () {
    this.container.innerHTML = `
            <div class="impact-dashboard" data-module="impact-dashboard">
                <div class="dashboard-header">
                    <h3><i class="fas fa-globe-americas text-success me-2"></i>Dashboard de Impacto</h3>
                    <div class="header-controls">
                        <select class="form-select form-select-sm me-2" data-filter="dateRange">
                            <option value="last_month">Últimos 30 días</option>
                            <option value="last_quarter">Último Trimestre</option>
                            <option value="last_year" selected>Último Año</option>
                            <option value="all_time">Todo el Tiempo</option>
                        </select>
                        <button class="btn btn-sm btn-outline-primary" data-action="refresh-data">
                            <i class="fas fa-sync-alt"></i> Actualizar
                        </button>
                    </div>
                </div>

                <div class="dashboard-content mt-3">
                    <div class="row" id="impact-kpis">
                        <!-- KPIs se cargarán aquí -->
                    </div>
                    <div class="row mt-4">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Impacto por Sector</h5>
                                    <canvas id="impactBySectorChart"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Progreso ODS</h5>
                                    <canvas id="odsProgressChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="row mt-4">
                        <div class="col-12">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Impacto Geográfico</h5>
                                    <div id="impactMap" style="height: 400px;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="row mt-4">
                        <div class="col-12">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Historias de Impacto Destacadas</h5>
                                    <div id="impactStories">
                                        <!-- Historias se cargarán aquí -->
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="dashboard-loader d-none">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos de impacto...</p>
                </div>
            </div>
        `
  }

  /**
     * Obtener referencias a elementos DOM
     */
  bindElements () {
    this.elements = {
      kpiContainer: this.container.querySelector('#impact-kpis'),
      impactBySectorChartCtx: this.container.querySelector('#impactBySectorChart'),
      odsProgressChartCtx: this.container.querySelector('#odsProgressChart'),
      impactMapContainer: this.container.querySelector('#impactMap'),
      impactStoriesContainer: this.container.querySelector('#impactStories'),
      dateRangeFilter: this.container.querySelector('[data-filter="dateRange"]'),
      refreshButton: this.container.querySelector('[data-action="refresh-data"]'),
      loader: this.container.querySelector('.dashboard-loader')
    }
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    this.elements.dateRangeFilter?.addEventListener('change', (e) => {
      this.moduleState.filters.dateRange = e.target.value
      this.refreshDashboardData()
    })

    this.elements.refreshButton?.addEventListener('click', () => {
      this.refreshDashboardData()
    })
  }

  /**
     * Cargar datos del dashboard
     */
  async loadDashboardData () {
    this.showLoader(true)
    try {
      const params = { ...this.moduleState.filters }
      const data = await this.main.http.get(`${this.main.apiUrl}/analytics/impact-dashboard`, { params })
      this.moduleState.impactData = data
      this.renderDashboard()
      this.moduleState.lastUpdate = new Date()
      this.updateLastRefreshTime()
    } catch (error) {
      console.error('Error cargando datos de impacto:', error)
      this.showError('No se pudieron cargar los datos de impacto.')
    } finally {
      this.showLoader(false)
    }
  }

  /**
     * Renderizar el dashboard completo
     */
  renderDashboard () {
    if (!this.moduleState.impactData) return
    this.renderKPIs()
    this.renderImpactBySectorChart()
    this.renderOdsProgressChart()
    this.renderImpactMap()
    this.renderImpactStories()
  }

  /**
     * Renderizar KPIs de impacto
     */
  renderKPIs () {
    const kpis = this.moduleState.impactData?.kpis || []
    if (!this.elements.kpiContainer || !kpis.length) return

    this.elements.kpiContainer.innerHTML = kpis.map(kpi => `
            <div class="col-md-3 col-sm-6 mb-3">
                <div class="card kpi-card text-center">
                    <div class="card-body">
                        <h2 class="kpi-value">${kpi.value}</h2>
                        <p class="kpi-label text-muted">${kpi.label}</p>
                        ${kpi.trend
? `<span class="kpi-trend ${kpi.trend >= 0 ? 'text-success' : 'text-danger'}">
                            <i class="fas fa-arrow-${kpi.trend >= 0 ? 'up' : 'down'}"></i> ${Math.abs(kpi.trend)}%
                        </span>`
: ''}
                    </div>
                </div>
            </div>
        `).join('')
  }

  /**
     * Renderizar gráfico de impacto por sector
     */
  renderImpactBySectorChart () {
    const data = this.moduleState.impactData?.impactBySector
    if (!this.elements.impactBySectorChartCtx || !data) return

    if (this.charts.impactBySector) this.charts.impactBySector.destroy()

    this.charts.impactBySector = new Chart(this.elements.impactBySectorChartCtx, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [{
          label: 'Impacto por Sector',
          data: data.values,
          backgroundColor: this.main.utils.generateColorPalette(data.labels.length)
        }]
      },
      options: { ...this.moduleConfig.chartsConfig }
    })
  }

  /**
     * Renderizar gráfico de progreso ODS
     */
  renderOdsProgressChart () {
    const data = this.moduleState.impactData?.odsProgress
    if (!this.elements.odsProgressChartCtx || !data) return

    if (this.charts.odsProgress) this.charts.odsProgress.destroy()

    this.charts.odsProgress = new Chart(this.elements.odsProgressChartCtx, {
      type: 'radar',
      data: {
        labels: data.map(ods => `ODS ${ods.goal}: ${ods.name}`),
        datasets: [{
          label: 'Progreso ODS (%)',
          data: data.map(ods => ods.progress),
          backgroundColor: 'rgba(255, 99, 132, 0.2)',
          borderColor: 'rgb(255, 99, 132)',
          pointBackgroundColor: 'rgb(255, 99, 132)'
        }]
      },
      options: {
        ...this.moduleConfig.chartsConfig,
        scales: {
          r: {
            angleLines: { display: false },
            suggestedMin: 0,
            suggestedMax: 100
          }
        }
      }
    })
  }

  /**
     * Renderizar mapa de impacto geográfico
     */
  renderImpactMap () {
    const data = this.moduleState.impactData?.geographicImpact
    if (!this.elements.impactMapContainer || !data) return

    // Aquí se integraría una librería de mapas como Leaflet o Google Maps API
    this.elements.impactMapContainer.innerHTML = `
            <div class="text-center p-3">
                <i class="fas fa-map-marked-alt fa-3x text-muted"></i>
                <p class.text-muted mt-2>Visualización de mapa de impacto geográfico (requiere integración).</p>
                <p><strong>Regiones con mayor impacto:</strong> ${data.topRegions.join(', ')}</p>
            </div>
        `
  }

  /**
     * Renderizar historias de impacto
     */
  renderImpactStories () {
    const stories = this.moduleState.impactData?.impactStories
    if (!this.elements.impactStoriesContainer || !stories || !stories.length) {
      this.elements.impactStoriesContainer.innerHTML = '<p class="text-muted">No hay historias de impacto destacadas.</p>'
      return
    }

    this.elements.impactStoriesContainer.innerHTML = stories.map(story => `
            <div class="card mb-3 impact-story">
                <div class="row g-0">
                    <div class="col-md-4">
                        <img src="${story.imageUrl || '/static/img/placeholder-impact.jpg'}" class="img-fluid rounded-start" alt="${story.title}">
                    </div>
                    <div class="col-md-8">
                        <div class="card-body">
                            <h5 class="card-title">${story.title}</h5>
                            <p class="card-text">${this.main.utils.truncateText(story.summary, 150)}</p>
                            <p class="card-text">
                                <small class="text-muted">
                                    <i class="fas fa-user me-1"></i> ${story.entrepreneurName} | 
                                    <i class="fas fa-rocket ms-2 me-1"></i> ${story.projectName}
                                </small>
                            </p>
                            <a href="/impact/stories/${story.id}" class="btn btn-sm btn-outline-primary">Leer más</a>
                        </div>
                    </div>
                </div>
            </div>
        `).join('')
  }

  /**
     * Refrescar datos del dashboard
     */
  async refreshDashboardData () {
    await this.loadDashboardData()
    this.main.notifications.success('Dashboard de impacto actualizado.')
  }

  /**
     * Configurar auto-refresh
     */
  setupAutoRefresh () {
    if (this.moduleConfig.enableAutoRefresh && this.moduleConfig.refreshInterval > 0) {
      if (this.moduleState.autoRefreshTimer) clearInterval(this.moduleState.autoRefreshTimer)
      this.moduleState.autoRefreshTimer = setInterval(() => {
        if (document.visibilityState === 'visible') { // Solo refrescar si la pestaña está activa
          this.refreshDashboardData()
        }
      }, this.moduleConfig.refreshInterval)
    }
  }

  /**
     * Actualizar tiempo de última actualización
     */
  updateLastRefreshTime () {
    const timeEl = this.container.querySelector('.update-time')
    if (timeEl && this.moduleState.lastUpdate) {
      timeEl.textContent = `Actualizado ${this.main.utils.formatRelativeTime(this.moduleState.lastUpdate)}`
    }
  }

  /**
     * Mostrar/ocultar loader
     */
  showLoader (show, message = 'Cargando datos...') {
    if (this.elements.loader) {
      this.elements.loader.classList.toggle('d-none', !show)
      if (show) {
        const messageEl = this.elements.loader.querySelector('p')
        if (messageEl) messageEl.textContent = message
      }
    }
    this.moduleState.isLoading = show
  }

  /**
     * Mostrar mensaje de error
     */
  showError (title, message = '') {
    if (this.main.notifications) {
      this.main.notifications.error(message || title, { title: message ? title : 'Error' })
    } else {
      console.error(title, message)
    }
  }

  /**
     * Destruir módulo y limpiar recursos
     */
  destroy () {
    if (this.moduleState.autoRefreshTimer) {
      clearInterval(this.moduleState.autoRefreshTimer)
    }
    Object.values(this.charts).forEach(chart => chart?.destroy())
    this.eventListeners.forEach((handler, element) => {
      element.removeEventListener(handler.event, handler.callback)
    })
    this.container.innerHTML = ''
    this.moduleState.isInitialized = false
    console.log('🧹 Impact Dashboard destruido')
  }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ImpactDashboard
} else {
  window.ImpactDashboard = ImpactDashboard
}

// Inicialización automática si el contenedor existe
document.addEventListener('DOMContentLoaded', () => {
  const impactDashboardContainer = document.getElementById('impact-dashboard-container')
  if (impactDashboardContainer && window.EcosistemaApp) {
    window.EcosistemaApp.impactDashboard = new ImpactDashboard(impactDashboardContainer, window.EcosistemaApp)
  }
})
