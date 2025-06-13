/**
 * Ecosistema Emprendimiento - Client Reports Module
 * ================================================
 * 
 * Módulo para la generación y visualización de reportes
 * para clientes y stakeholders del ecosistema.
 * Permite analizar el rendimiento de inversiones, impacto, etc.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js, Chart.js
 */

'use strict';

class ClientReports {
    constructor(container, app) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        
        if (!this.container) {
            throw new Error('Container for ClientReports not found');
        }

        this.app = app || window.EcosistemaApp;
        this.main = this.app?.main || window.App;
        this.state = this.app?.state || window.EcosistemaStateManager;
        this.config = window.getConfig ? window.getConfig('modules.clientReports', {}) : {};

        // Configuración del módulo
        this.moduleConfig = {
            defaultReportType: 'portfolio_overview',
            enableExport: true,
            exportFormats: ['pdf', 'excel', 'csv'],
            enableScheduling: true,
            maxReportItems: 100,
            defaultDateRange: 90, // días
            chartOptions: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.label}: ${context.formattedValue}`
                        }
                    }
                }
            },
            ...this.config
        };

        // Estado interno del módulo
        this.moduleState = {
            isInitialized: false,
            isLoading: false,
            currentReportType: this.moduleConfig.defaultReportType,
            currentReportData: null,
            filters: {
                dateRange: {
                    start: new Date(Date.now() - (this.moduleConfig.defaultDateRange * 24 * 60 * 60 * 1000)),
                    end: new Date()
                },
                portfolioId: 'all',
                investmentStage: 'all',
                sector: 'all'
            },
            availableReports: [],
            scheduledReports: [],
            charts: {}
        };

        this.elements = {};
        this.eventListeners = new Map();

        this.init();
    }

    /**
     * Inicializar módulo
     */
    async init() {
        if (this.moduleState.isInitialized) return;

        try {
            console.log('📈 Inicializando Client Reports');
            this.showLoader(true, 'Cargando reportes...');

            this.createStructure();
            this.bindElements();
            this.setupEventListeners();
            
            await this.loadAvailableReports();
            await this.loadReport(this.moduleState.currentReportType);
            
            this.moduleState.isInitialized = true;
            console.log('✅ Client Reports inicializado');
        } catch (error) {
            console.error('❌ Error inicializando Client Reports:', error);
            this.showError('Error al inicializar el módulo de reportes', error.message);
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Crear estructura DOM del módulo
     */
    createStructure() {
        this.container.innerHTML = `
            <div class="client-reports" data-module="client-reports">
                <div class="reports-header">
                    <h3><i class="fas fa-file-invoice-dollar text-info me-2"></i>Reportes para Clientes</h3>
                    <div class="header-controls">
                        <select class="form-select form-select-sm me-2" data-control="report-type">
                            <!-- Opciones de reportes se cargarán aquí -->
                        </select>
                        <button class="btn btn-sm btn-outline-primary" data-action="refresh-report">
                            <i class="fas fa-sync-alt"></i> Actualizar
                        </button>
                        <button class="btn btn-sm btn-primary ms-2" data-action="export-report" 
                                ${this.moduleConfig.enableExport ? '' : 'disabled'}>
                            <i class="fas fa-download"></i> Exportar
                        </button>
                    </div>
                </div>

                <div class="reports-filters mt-3 mb-3 p-3 bg-light rounded">
                    <h5>Filtros</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <label for="reportDateRange" class="form-label form-label-sm">Rango de Fechas</label>
                            <input type="text" class="form-control form-control-sm" id="reportDateRange" data-filter="dateRange">
                        </div>
                        <div class="col-md-3">
                            <label for="reportPortfolio" class="form-label form-label-sm">Portfolio</label>
                            <select class="form-select form-select-sm" id="reportPortfolio" data-filter="portfolioId">
                                <option value="all" selected>Todos</option>
                                <!-- Opciones de portfolio -->
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="reportSector" class="form-label form-label-sm">Sector</label>
                            <select class="form-select form-select-sm" id="reportSector" data-filter="sector">
                                <option value="all" selected>Todos</option>
                                <!-- Opciones de sector -->
                            </select>
                        </div>
                        <div class="col-md-2 d-flex align-items-end">
                            <button class="btn btn-sm btn-primary w-100" data-action="apply-filters">Aplicar</button>
                        </div>
                    </div>
                </div>

                <div class="report-content-area card">
                    <div class="card-body">
                        <h4 class="report-title mb-3" data-content="report-title"></h4>
                        <div class="report-data" data-content="report-data">
                            <p class="text-muted">Seleccione un tipo de reporte para comenzar.</p>
                        </div>
                    </div>
                </div>
                
                <div class="reports-loader d-none">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Cargando datos del reporte...</p>
                </div>
            </div>
        `;
        // Inicializar DateRangePicker si está disponible
        if (typeof $ !== 'undefined' && $.fn.daterangepicker) {
            const dateRangeInput = this.container.querySelector('#reportDateRange');
            $(dateRangeInput).daterangepicker({
                startDate: this.moduleState.filters.dateRange.start,
                endDate: this.moduleState.filters.dateRange.end,
                locale: { format: 'DD/MM/YYYY', applyLabel: "Aplicar", cancelLabel: "Cancelar" },
                ranges: {
                   'Hoy': [moment(), moment()],
                   'Ayer': [moment().subtract(1, 'days'), moment().subtract(1, 'days')],
                   'Últimos 7 Días': [moment().subtract(6, 'days'), moment()],
                   'Últimos 30 Días': [moment().subtract(29, 'days'), moment()],
                   'Este Mes': [moment().startOf('month'), moment().endOf('month')],
                   'Mes Pasado': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
                }
            }, (start, end) => {
                this.moduleState.filters.dateRange = { start: start.toDate(), end: end.toDate() };
            });
        }
    }

    /**
     * Obtener referencias a elementos DOM
     */
    bindElements() {
        this.elements = {
            reportTypeSelect: this.container.querySelector('[data-control="report-type"]'),
            refreshButton: this.container.querySelector('[data-action="refresh-report"]'),
            exportButton: this.container.querySelector('[data-action="export-report"]'),
            applyFiltersButton: this.container.querySelector('[data-action="apply-filters"]'),
            reportTitle: this.container.querySelector('[data-content="report-title"]'),
            reportDataContainer: this.container.querySelector('[data-content="report-data"]'),
            loader: this.container.querySelector('.reports-loader'),
            dateRangeInput: this.container.querySelector('#reportDateRange'),
            portfolioFilter: this.container.querySelector('#reportPortfolio'),
            sectorFilter: this.container.querySelector('#reportSector')
        };
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        this.elements.reportTypeSelect?.addEventListener('change', (e) => {
            this.moduleState.currentReportType = e.target.value;
            this.loadReport(this.moduleState.currentReportType);
        });

        this.elements.refreshButton?.addEventListener('click', () => {
            this.loadReport(this.moduleState.currentReportType, true);
        });

        this.elements.exportButton?.addEventListener('click', () => {
            this.exportReport();
        });
        
        this.elements.applyFiltersButton?.addEventListener('click', () => {
            this.applyFiltersAndReload();
        });
    }

    /**
     * Cargar tipos de reportes disponibles
     */
    async loadAvailableReports() {
        try {
            const reports = await this.main.http.get(`${this.main.apiUrl}/client/reports/available`);
            this.moduleState.availableReports = reports;
            this.populateReportTypeSelect();
        } catch (error) {
            console.error('Error cargando reportes disponibles:', error);
            this.showError('No se pudieron cargar los tipos de reporte.');
        }
    }

    /**
     * Llenar select de tipos de reporte
     */
    populateReportTypeSelect() {
        if (!this.elements.reportTypeSelect) return;
        this.elements.reportTypeSelect.innerHTML = ''; // Limpiar opciones
        
        this.moduleState.availableReports.forEach(report => {
            const option = document.createElement('option');
            option.value = report.id;
            option.textContent = report.name;
            if (report.id === this.moduleState.currentReportType) {
                option.selected = true;
            }
            this.elements.reportTypeSelect.appendChild(option);
        });
    }
    
    /**
     * Aplicar filtros y recargar reporte
     */
    applyFiltersAndReload() {
        // Actualizar estado de filtros desde los inputs
        this.moduleState.filters.portfolioId = this.elements.portfolioFilter.value;
        this.moduleState.filters.sector = this.elements.sectorFilter.value;
        // El filtro de dateRange se actualiza con el callback del daterangepicker

        this.loadReport(this.moduleState.currentReportType, true); // Forzar refresh
    }

    /**
     * Cargar datos del reporte
     */
    async loadReport(reportType, forceRefresh = false) {
        if (!reportType) return;
        this.showLoader(true, `Cargando reporte: ${reportType}...`);
        
        try {
            const params = {
                ...this.moduleState.filters,
                startDate: this.moduleState.filters.dateRange.start.toISOString(),
                endDate: this.moduleState.filters.dateRange.end.toISOString(),
                forceRefresh: forceRefresh
            };
            delete params.dateRange; // API espera startDate y endDate

            const reportData = await this.main.http.get(`${this.main.apiUrl}/client/reports/${reportType}`, { params });
            this.moduleState.currentReportData = reportData;
            this.renderReportContent(reportData);
            this.elements.reportTitle.textContent = reportData.title || 'Reporte';
        } catch (error) {
            console.error(`Error cargando reporte ${reportType}:`, error);
            this.showError(`No se pudo cargar el reporte: ${reportType}`);
            this.elements.reportDataContainer.innerHTML = `<p class="text-danger">Error al cargar el reporte.</p>`;
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Renderizar contenido del reporte
     */
    renderReportContent(reportData) {
        if (!reportData || !reportData.sections) {
            this.elements.reportDataContainer.innerHTML = '<p class="text-muted">No hay datos para mostrar.</p>';
            return;
        }

        let html = '<div class="report-sections">';
        reportData.sections.forEach(section => {
            html += `<div class="report-section card mb-4">
                        <div class="card-header"><h5>${section.title}</h5></div>
                        <div class="card-body">`;
            
            switch(section.type) {
                case 'kpi_grid':
                    html += this.renderKpiGrid(section.data);
                    break;
                case 'table':
                    html += this.renderTable(section.data);
                    break;
                case 'chart':
                    // Placeholder para el canvas, el gráfico se renderizará después
                    const chartId = `chart-${section.id || Math.random().toString(36).substr(2, 9)}`;
                    html += `<canvas id="${chartId}" height="300"></canvas>`;
                    // Guardar info para renderizar después
                    if (!this.moduleState.charts[reportData.id]) this.moduleState.charts[reportData.id] = [];
                    this.moduleState.charts[reportData.id].push({ id: chartId, config: section.data });
                    break;
                case 'text_summary':
                    html += `<p>${section.data.text}</p>`;
                    break;
                default:
                    html += `<p class="text-muted">Tipo de sección no soportado: ${section.type}</p>`;
            }
            html += `   </div>
                     </div>`;
        });
        html += '</div>';
        this.elements.reportDataContainer.innerHTML = html;

        // Renderizar gráficos después de que el HTML esté en el DOM
        this.renderChartsForCurrentReport();
    }

    renderKpiGrid(kpiData) {
        let kpiHtml = '<div class="row">';
        kpiData.forEach(kpi => {
            kpiHtml += `
                <div class="col-md-3 mb-3">
                    <div class="kpi-card text-center p-3 border rounded">
                        <h2 class="kpi-value">${kpi.value}</h2>
                        <p class="kpi-label text-muted mb-0">${kpi.label}</p>
                        ${kpi.trend ? `<span class="kpi-trend ${kpi.trend >= 0 ? 'text-success' : 'text-danger'}">
                            <i class="fas fa-arrow-${kpi.trend >= 0 ? 'up' : 'down'}"></i> ${Math.abs(kpi.trend)}%
                        </span>` : ''}
                    </div>
                </div>`;
        });
        kpiHtml += '</div>';
        return kpiHtml;
    }

    renderTable(tableData) {
        if (!tableData.headers || !tableData.rows) return '<p class="text-muted">Datos de tabla incompletos.</p>';
        let tableHtml = '<div class="table-responsive"><table class="table table-striped table-hover">';
        // Headers
        tableHtml += '<thead><tr>';
        tableData.headers.forEach(header => tableHtml += `<th>${header}</th>`);
        tableHtml += '</tr></thead>';
        // Rows
        tableHtml += '<tbody>';
        tableData.rows.forEach(row => {
            tableHtml += '<tr>';
            row.forEach(cell => tableHtml += `<td>${cell}</td>`);
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table></div>';
        return tableHtml;
    }

    renderChartsForCurrentReport() {
        const reportId = this.moduleState.currentReportData?.id;
        if (!reportId || !this.moduleState.charts[reportId]) return;

        this.moduleState.charts[reportId].forEach(chartInfo => {
            const canvas = document.getElementById(chartInfo.id);
            if (canvas) {
                new Chart(canvas, {
                    type: chartInfo.config.chartType || 'bar',
                    data: chartInfo.config.data,
                    options: { ...this.moduleConfig.chartOptions, ...chartInfo.config.options }
                });
            }
        });
        // Limpiar para evitar re-renderizado
        this.moduleState.charts[reportId] = [];
    }

    /**
     * Exportar reporte actual
     */
    async exportReport() {
        if (!this.moduleConfig.enableExport || !this.moduleState.currentReportData) {
            this.showError('La exportación no está habilitada o no hay reporte cargado.');
            return;
        }
        // Lógica para mostrar modal de opciones de exportación y luego llamar a la API
        // Ejemplo:
        const format = prompt("Ingrese formato de exportación (pdf, excel, csv):", "pdf");
        if (!format || !this.moduleConfig.exportFormats.includes(format.toLowerCase())) {
            this.showError('Formato de exportación no válido.');
            return;
        }

        this.showLoader(true, `Exportando reporte como ${format.toUpperCase()}...`);
        try {
            const params = {
                ...this.moduleState.filters,
                startDate: this.moduleState.filters.dateRange.start.toISOString(),
                endDate: this.moduleState.filters.dateRange.end.toISOString(),
                format: format.toLowerCase()
            };
            delete params.dateRange;

            const response = await this.main.http.get(
                `${this.main.apiUrl}/client/reports/${this.moduleState.currentReportType}/export`, 
                { params, responseType: 'blob' } // Asumiendo que el backend devuelve un blob
            );
            
            // Lógica para descargar el archivo (similar a AllyReports)
            const blob = new Blob([response], { type: this.main.utils.getMimeType(format) });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${this.moduleState.currentReportType}_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            this.main.notifications.success('Reporte exportado exitosamente.');

        } catch (error) {
            console.error('Error exportando reporte:', error);
            this.showError('Error al exportar el reporte.');
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Mostrar/ocultar loader
     */
    showLoader(show, message = 'Cargando...') {
        if (this.elements.loader) {
            this.elements.loader.classList.toggle('d-none', !show);
            if (show) {
                const messageEl = this.elements.loader.querySelector('p');
                if (messageEl) messageEl.textContent = message;
            }
        }
        this.moduleState.isLoading = show;
    }

    /**
     * Mostrar mensaje de error
     */
    showError(title, message = '') {
        if (this.main.notifications) {
            this.main.notifications.error(message || title, { title: message ? title : 'Error' });
        } else {
            console.error(title, message);
        }
    }

    /**
     * Destruir módulo y limpiar recursos
     */
    destroy() {
        Object.values(this.moduleState.charts).forEach(chart => chart?.destroy());
        this.eventListeners.forEach((handler, element) => {
            element.removeEventListener(handler.event, handler.callback);
        });
        this.container.innerHTML = '';
        this.moduleState.isInitialized = false;
        console.log('🧹 Client Reports destruido');
    }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClientReports;
} else {
    window.ClientReports = ClientReports;
}

// Inicialización automática si el contenedor existe
document.addEventListener('DOMContentLoaded', () => {
    const clientReportsContainer = document.getElementById('client-reports-container');
    if (clientReportsContainer && window.EcosistemaApp) {
        window.EcosistemaApp.clientReports = new ClientReports(clientReportsContainer, window.EcosistemaApp);
    }
});
