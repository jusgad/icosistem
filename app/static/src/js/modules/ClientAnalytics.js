/**
 * Ecosistema Emprendimiento - Client Analytics Module
 * ===================================================
 *
 * Módulo para que los clientes/stakeholders analicen el rendimiento
 * de sus inversiones, el impacto de los proyectos apoyados y
 * otras métricas relevantes del ecosistema.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js, Chart.js
 */

'use strict'

class ClientAnalytics {
  constructor (container, app) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container

    if (!this.container) {
      throw new Error('Container for ClientAnalytics not found')
    }

    this.app = app || window.EcosistemaApp
    this.main = this.app?.main || window.App
    this.state = this.app?.state || window.EcosistemaStateManager
    this.config = window.getConfig ? window.getConfig('modules.clientAnalytics', {}) : {}

    // Configuración del módulo
    this.moduleConfig = {
      defaultView: 'portfolio_performance',
      enableDataExport: true,
      exportFormats: ['csv', 'json', 'pdf'],
      chartOptions: {
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
      currentView: this.moduleConfig.defaultView,
      analyticsData: null,
      filters: {
        dateRange: 'last_year',
        investmentType: 'all',
        sector: 'all',
        projectStage: 'all'
      },
      charts: {}
    }

    this.elements = {}
    this.eventListeners = new Map()

    this.init()
  }

  /**
     * Inicializar módulo
     */
  async init () {
    if (this.moduleState.isInitialized) return

    try {
      // // console.log('🔍 Inicializando Client Analytics')
      this.showLoader(true, 'Cargando análisis...')

      this.createStructure()
      this.bindElements()
      this.setupEventListeners()

      await this.loadAnalyticsData()
      this.initializeCharts()

      this.moduleState.isInitialized = true
      // // console.log('✅ Client Analytics inicializado')
    } catch (error) {
      // // console.error('❌ Error inicializando Client Analytics:', error)
      this.showError('Error al inicializar el módulo de análisis', error.message)
    } finally {
      this.showLoader(false)
    }
  }

  /**
     * Crear estructura DOM del módulo
     */
  createStructure () {
    this.container.innerHTML = `
            <div class="client-analytics" data-module="client-analytics">
                <div class="analytics-header">
                    <h3><i class="fas fa-chart-line text-purple me-2"></i>Análisis para Clientes</h3>
                    <div class="header-controls">
                        <select class="form-select form-select-sm me-2" data-control="view-selector">
                            <option value="portfolio_performance" selected>Rendimiento del Portfolio</option>
                            <option value="impact_overview">Resumen de Impacto</option>
                            <option value="project_tracking">Seguimiento de Proyectos</option>
                        </select>
                        <button class="btn btn-sm btn-outline-primary" data-action="refresh-analytics">
                            <i class="fas fa-sync-alt"></i> Actualizar
                        </button>
                    </div>
                </div>

                <div class="analytics-filters mt-3 mb-3 p-3 bg-light rounded">
                    <h5>Filtros de Análisis</h5>
                    <div class="row">
                        <div class="col-md-3">
                            <label for="analyticsDateRange" class="form-label form-label-sm">Rango de Fechas</label>
                            <select class="form-select form-select-sm" id="analyticsDateRange" data-filter="dateRange">
                                <option value="last_month">Último Mes</option>
                                <option value="last_quarter">Último Trimestre</option>
                                <option value="last_year" selected>Último Año</option>
                                <option value="all_time">Todo el Tiempo</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="analyticsInvestmentType" class="form-label form-label-sm">Tipo de Inversión</label>
                            <select class="form-select form-select-sm" id="analyticsInvestmentType" data-filter="investmentType">
                                <option value="all" selected>Todos</option>
                                <option value="equity">Equity</option>
                                <option value="debt">Deuda</option>
                                <option value="grant">Subvención</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="analyticsSector" class="form-label form-label-sm">Sector</label>
                            <select class="form-select form-select-sm" id="analyticsSector" data-filter="sector">
                                <option value="all" selected>Todos</option>
                                <!-- Opciones de sector se cargarán aquí -->
                            </select>
                        </div>
                        <div class="col-md-3 d-flex align-items-end">
                            <button class="btn btn-sm btn-primary w-100" data-action="apply-filters">Aplicar Filtros</button>
                        </div>
                    </div>
                </div>

                <div class="analytics-content-area card mt-3">
                    <div class="card-body" data-content="analytics-view">
                        <!-- Contenido de la vista de análisis se cargará aquí -->
                        <p class="text-muted">Seleccione una vista y aplique filtros para ver el análisis.</p>
                    </div>
                </div>
                
                <div class="analytics-loader d-none">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos de análisis...</p>
                </div>
            </div>
        `
  }

  /**
     * Obtener referencias a elementos DOM
     */
  bindElements () {
    this.elements = {
      viewSelector: this.container.querySelector('[data-control="view-selector"]'),
      refreshButton: this.container.querySelector('[data-action="refresh-analytics"]'),
      applyFiltersButton: this.container.querySelector('[data-action="apply-filters"]'),
      analyticsViewContainer: this.container.querySelector('[data-content="analytics-view"]'),
      loader: this.container.querySelector('.analytics-loader'),
      dateRangeFilter: this.container.querySelector('#analyticsDateRange'),
      investmentTypeFilter: this.container.querySelector('#analyticsInvestmentType'),
      sectorFilter: this.container.querySelector('#analyticsSector')
      // ... más elementos según las vistas
    }
  }

  /**
     * Configurar event listeners
     */
  setupEventListeners () {
    this.elements.viewSelector?.addEventListener('change', (e) => {
      this.moduleState.currentView = e.target.value
      this.loadAnalyticsData()
    })

    this.elements.refreshButton?.addEventListener('click', () => {
      this.loadAnalyticsData(true) // Forzar refresh
    })

    this.elements.applyFiltersButton?.addEventListener('click', () => {
      this.applyFiltersAndReload()
    })
  }

  /**
     * Aplicar filtros y recargar datos
     */
  applyFiltersAndReload () {
    this.moduleState.filters.dateRange = this.elements.dateRangeFilter.value
    this.moduleState.filters.investmentType = this.elements.investmentTypeFilter.value
    this.moduleState.filters.sector = this.elements.sectorFilter.value
    // ... obtener más filtros

    this.loadAnalyticsData(true)
  }

  /**
     * Cargar datos de análisis
     */
  async loadAnalyticsData (forceRefresh = false) {
    this.showLoader(true, `Cargando vista: ${this.moduleState.currentView}...`)

    try {
      const params = {
        view: this.moduleState.currentView,
        ...this.moduleState.filters,
        forceRefresh
      }
      const data = await this.main.http.get(`${this.main.apiUrl}/client/analytics`, { params })
      this.moduleState.analyticsData = data
      this.renderCurrentView()
    } catch (error) {
      // // console.error(`Error cargando datos para ${this.moduleState.currentView}:`, error)
      this.showError('No se pudieron cargar los datos de análisis.')
      this.elements.analyticsViewContainer.innerHTML = '<p class="text-danger">Error al cargar la vista de análisis.</p>'
    } finally {
      this.showLoader(false)
    }
  }

  /**
     * Renderizar la vista actual
     */
  renderCurrentView () {
    if (!this.moduleState.analyticsData) return

    const view = this.moduleState.currentView
    const data = this.moduleState.analyticsData

    switch (view) {
      case 'portfolio_performance':
        this.renderPortfolioPerformance(data)
        break
      case 'impact_overview':
        this.renderImpactOverview(data)
        break
      case 'project_tracking':
        this.renderProjectTracking(data)
        break
      default:
        this.elements.analyticsViewContainer.innerHTML = `<p class="text-muted">Vista no implementada: ${view}</p>`
    }
    this.initializeChartsForView(view) // Renderizar gráficos específicos de la vista
  }

  /**
     * Renderizar vista de Rendimiento del Portfolio
     */
  renderPortfolioPerformance (data) {
    this.elements.analyticsViewContainer.innerHTML = `
            <h4>Rendimiento del Portfolio</h4>
            <div class="row mt-3">
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-success">${this.main.utils.formatCurrency(data.total_value, 'USD')}</h2>
                            <p class="text-muted mb-0">Valor Total del Portfolio</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">${data.roi.toFixed(2)}%</h2>
                            <p class="text-muted mb-0">ROI General</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-info">${data.active_investments}</h2>
                            <p class="text-muted mb-0">Inversiones Activas</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Evolución del Valor del Portfolio</h5>
                            <canvas id="portfolioValueChart" height="300"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Distribución por Sector</h5>
                            <canvas id="portfolioSectorChart" height="250"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Rendimiento por Inversión</h5>
                            <div data-content="investment-performance-table" class="table-responsive"></div>
                        </div>
                    </div>
                </div>
            </div>
        `
    // Lógica para renderizar tabla de rendimiento por inversión
    this.renderInvestmentPerformanceTable(data.investment_details)
  }

  renderInvestmentPerformanceTable (investments) {
    const container = this.container.querySelector('[data-content="investment-performance-table"]')
    if (!container || !investments || !investments.length) {
      container.innerHTML = '<p class="text-muted">No hay detalles de inversión para mostrar.</p>'
      return
    }

    let tableHtml = '<table class="table table-sm table-hover">'
    tableHtml += `
            <thead>
                <tr>
                    <th>Proyecto</th>
                    <th>Monto Invertido</th>
                    <th>Valor Actual</th>
                    <th>Ganancia/Pérdida</th>
                    <th>ROI</th>
                </tr>
            </thead>
            <tbody>
        `
    investments.forEach(inv => {
      const gainLoss = inv.current_value - inv.invested_amount
      const roi = (gainLoss / inv.invested_amount) * 100
      tableHtml += `
                <tr>
                    <td>${inv.project_name}</td>
                    <td>${this.main.utils.formatCurrency(inv.invested_amount, 'USD')}</td>
                    <td>${this.main.utils.formatCurrency(inv.current_value, 'USD')}</td>
                    <td class="${gainLoss >= 0 ? 'text-success' : 'text-danger'}">
                        ${this.main.utils.formatCurrency(gainLoss, 'USD')}
                    </td>
                    <td class="${roi >= 0 ? 'text-success' : 'text-danger'}">${roi.toFixed(2)}%</td>
                </tr>
            `
    })
    tableHtml += '</tbody></table>'
    container.innerHTML = tableHtml
  }

  /**
     * Renderizar vista de Resumen de Impacto
     */
  renderImpactOverview (data) {
    this.elements.analyticsViewContainer.innerHTML = `
            <h4>Resumen de Impacto</h4>
            <div class="row mt-3">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-success">${data.jobs_created}</h2>
                            <p class="text-muted mb-0">Empleos Creados</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-info">${data.communities_impacted}</h2>
                            <p class="text-muted mb-0">Comunidades Impactadas</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-warning">${data.sdg_alignment_score.toFixed(1)}/5</h2>
                            <p class="text-muted mb-0">Alineación ODS</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">${this.main.utils.formatCurrency(data.social_roi, 'USD')}</h2>
                            <p class="text-muted mb-0">SROI Estimado</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">Impacto por ODS</h5>
                            <canvas id="impactSDGChart" height="300"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        `
  }

  /**
     * Inicializar gráficos para la vista actual
     */
  initializeChartsForView (view) {
    const data = this.moduleState.analyticsData
    if (!data || typeof Chart === 'undefined') return

    // Destruir gráficos anteriores de esta vista
    Object.keys(this.moduleState.charts).forEach(chartId => {
      if (chartId.startsWith(view) && this.moduleState.charts[chartId]) {
        this.moduleState.charts[chartId].destroy()
        delete this.moduleState.charts[chartId]
      }
    })

    if (view === 'portfolio_performance') {
      const pvCtx = document.getElementById('portfolioValueChart')?.getContext('2d')
      if (pvCtx && data.portfolio_value_history) {
        this.moduleState.charts.portfolio_performance_value = new Chart(pvCtx, {
          type: 'line',
          data: {
            labels: data.portfolio_value_history.labels,
            datasets: [{
              label: 'Valor del Portfolio',
              data: data.portfolio_value_history.values,
              borderColor: this.main.utils.getColor('primary'),
              tension: 0.1
            }]
          },
          options: this.moduleConfig.chartOptions
        })
      }
      const psCtx = document.getElementById('portfolioSectorChart')?.getContext('2d')
      if (psCtx && data.portfolio_sector_distribution) {
        this.moduleState.charts.portfolio_performance_sector = new Chart(psCtx, {
          type: 'pie',
          data: {
            labels: data.portfolio_sector_distribution.labels,
            datasets: [{
              data: data.portfolio_sector_distribution.values,
              backgroundColor: this.main.utils.generateColorPalette(data.portfolio_sector_distribution.labels.length)
            }]
          },
          options: this.moduleConfig.chartOptions
        })
      }
    } else if (view === 'impact_overview') {
      const sdgCtx = document.getElementById('impactSDGChart')?.getContext('2d')
      if (sdgCtx && data.sdg_impact) {
        this.moduleState.charts.impact_overview_sdg = new Chart(sdgCtx, {
          type: 'radar',
          data: {
            labels: data.sdg_impact.labels, // Nombres de los ODS
            datasets: [{
              label: 'Impacto por ODS',
              data: data.sdg_impact.values,
              backgroundColor: 'rgba(0, 123, 255, 0.2)',
              borderColor: 'rgb(0, 123, 255)',
              pointBackgroundColor: 'rgb(0, 123, 255)'
            }]
          },
          options: { ...this.moduleConfig.chartOptions, scales: { r: { angleLines: { display: false }, suggestedMin: 0, suggestedMax: 100 } } }
        })
      }
    }
    // ... más gráficos para otras vistas
  }

  /**
     * Inicializar todos los gráficos (se llama una vez)
     */
  initializeCharts () {
    // Este método puede ser usado para configuraciones globales de Chart.js si es necesario
    // o para inicializar gráficos que no dependen de la vista actual.
    // La lógica principal de renderizado de gráficos ahora está en initializeChartsForView.
  }

  /**
     * Mostrar/ocultar loader
     */
  showLoader (show, message = 'Cargando...') {
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
      // // console.error(title, message)
    }
  }

  /**
     * Destruir módulo y limpiar recursos
     */
  destroy () {
    Object.values(this.moduleState.charts).forEach(chart => chart?.destroy())
    this.eventListeners.forEach((handler, element) => {
      element.removeEventListener(handler.event, handler.callback)
    })
    this.container.innerHTML = ''
    this.moduleState.isInitialized = false
    // // console.log('🧹 Client Analytics destruido')
  }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ClientAnalytics
} else {
  window.ClientAnalytics = ClientAnalytics
}

// Inicialización automática si el contenedor existe
document.addEventListener('DOMContentLoaded', () => {
  const clientAnalyticsContainer = document.getElementById('client-analytics-container')
  if (clientAnalyticsContainer && window.EcosistemaApp) {
    window.EcosistemaApp.clientAnalytics = new ClientAnalytics(clientAnalyticsContainer, window.EcosistemaApp)
  }
})
