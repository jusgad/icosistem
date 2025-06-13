/**
 * ReportService.js - Servicio para la Gestión de Reportes y Analíticas
 * ====================================================================
 *
 * Maneja la generación, obtención y visualización de reportes del sistema,
 * incluyendo métricas de emprendedores, proyectos, mentorías, etc.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.notifications, etc.)
 */

'use strict';

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
    throw new Error('main.js debe cargarse antes que ReportService.js');
}

// Alias para facilitar acceso
const App = window.EcosistemaApp;

class ReportService {
    constructor() {
        this.baseEndpoint = '/api/v1/reports'; // Endpoint base para reportes
        this.analyticsEndpoint = '/api/v1/analytics'; // Endpoint para datos de analíticas
        this.reportStatusCheckInterval = 5000; // Intervalo para verificar estado de reportes (5 segundos)
        this.activeReportChecks = new Map(); // Almacena IDs de intervalos para reportes en generación
    }

    /**
     * Obtiene la lista de tipos de reportes disponibles.
     * @return {Promise<Array<Object>>} - Promesa con la lista de tipos de reportes.
     */
    async getAvailableReportTypes() {
        try {
            return await App.http.get(`${this.baseEndpoint}/types`);
        } catch (error) {
            console.error('ReportService: Error al obtener tipos de reportes:', error);
            App.notifications.error('No se pudo cargar la lista de tipos de reportes.');
            return [];
        }
    }

    /**
     * Solicita la generación de un nuevo reporte.
     * @param {string} reportType - Tipo de reporte a generar (e.g., 'user_activity', 'project_summary').
     * @param {Object} parameters - Parámetros para la generación del reporte (filtros, rango de fechas, etc.).
     * @param {string} format - Formato deseado (e.g., 'pdf', 'csv', 'xlsx').
     * @return {Promise<Object>} - Promesa con la información del job de generación del reporte (e.g., reportId, status).
     */
    async generateReport(reportType, parameters = {}, format = 'pdf') {
        const payload = {
            report_type: reportType,
            parameters: parameters,
            format: format
        };
        try {
            const response = await App.http.post(`${this.baseEndpoint}/generate`, payload);
            App.notifications.info(`Solicitud de reporte "${reportType}" enviada. Te notificaremos cuando esté listo.`);
            return response; // Debería incluir un ID de reporte o job
        } catch (error) {
            console.error('ReportService: Error al solicitar generación de reporte:', error);
            App.notifications.error(error.message || 'No se pudo solicitar la generación del reporte.');
            throw error;
        }
    }

    /**
     * Verifica el estado de un reporte en generación.
     * @param {string} reportId - ID del reporte o job.
     * @return {Promise<Object>} - Promesa con el estado actual del reporte.
     */
    async getReportStatus(reportId) {
        try {
            return await App.http.get(`${this.baseEndpoint}/${reportId}/status`);
        } catch (error) {
            console.warn(`ReportService: Error al verificar estado del reporte ${reportId}:`, error);
            // No notificar al usuario por cada fallo de chequeo, podría ser un error temporal.
            throw error;
        }
    }

    /**
     * Inicia el polling para verificar el estado de un reporte hasta que esté completo o falle.
     * @param {string} reportId - ID del reporte.
     * @param {Function} onComplete - Callback cuando el reporte está listo (recibe la info del reporte).
     * @param {Function} [onError] - Callback si la generación del reporte falla (recibe el error).
     * @param {Function} [onProgress] - Callback para actualizaciones de progreso (recibe el estado).
     */
    pollReportStatus(reportId, onComplete, onError, onProgress) {
        if (this.activeReportChecks.has(reportId)) {
            console.warn(`ReportService: Ya se está verificando el reporte ${reportId}.`);
            return;
        }

        const checkStatus = async () => {
            try {
                const statusInfo = await this.getReportStatus(reportId);
                if (onProgress) onProgress(statusInfo);

                if (statusInfo.status === 'completed') {
                    this.stopPollingReportStatus(reportId);
                    App.notifications.success(`El reporte "${statusInfo.name || reportId}" está listo.`);
                    if (onComplete) onComplete(statusInfo);
                    App.events.dispatchEvent('report:completed', statusInfo);
                } else if (statusInfo.status === 'failed') {
                    this.stopPollingReportStatus(reportId);
                    App.notifications.error(`Falló la generación del reporte "${statusInfo.name || reportId}".`);
                    if (onError) onError(statusInfo.error || new Error('Generación de reporte fallida'));
                    App.events.dispatchEvent('report:failed', statusInfo);
                }
                // Si está 'pending' o 'processing', el intervalo continuará.
            } catch (error) {
                // Si el error es 404, el reporte podría no existir o el job terminó y fue limpiado.
                // O si es un error de red, etc.
                if (error.status === 404) {
                    this.stopPollingReportStatus(reportId);
                    App.notifications.warning(`No se pudo encontrar el reporte ${reportId}. Puede que haya sido eliminado.`);
                    if (onError) onError(error);
                    App.events.dispatchEvent('report:failed', { reportId, error });
                } else {
                    console.warn(`ReportService: Error en polling para reporte ${reportId}. Reintentando...`);
                }
            }
        };

        // Ejecutar inmediatamente y luego cada X segundos
        checkStatus();
        const intervalId = setInterval(checkStatus, this.reportStatusCheckInterval);
        this.activeReportChecks.set(reportId, intervalId);
    }

    /**
     * Detiene el polling para un reporte específico.
     * @param {string} reportId - ID del reporte.
     */
    stopPollingReportStatus(reportId) {
        if (this.activeReportChecks.has(reportId)) {
            clearInterval(this.activeReportChecks.get(reportId));
            this.activeReportChecks.delete(reportId);
        }
    }

    /**
     * Obtiene la URL de descarga para un reporte generado.
     * @param {string} reportId - ID del reporte.
     * @return {string} - URL de descarga.
     */
    getReportDownloadUrl(reportId) {
        // Asume que la URL base de la API está configurada en App.config.API_BASE_URL
        // o que el endpoint es relativo al dominio actual.
        return `${App.config.API_BASE_URL || ''}${this.baseEndpoint}/${reportId}/download`;
    }

    /**
     * Descarga un reporte directamente.
     * @param {string} reportId - ID del reporte.
     * @param {string} [filename] - Nombre de archivo sugerido para la descarga.
     */
    async downloadReport(reportId, filename) {
        const url = this.getReportDownloadUrl(reportId);
        try {
            // App.http.download debería manejar la descarga del archivo
            await App.http.download(url, filename || `reporte_${reportId}.pdf`);
        } catch (error) {
            console.error(`ReportService: Error al descargar reporte ${reportId}:`, error);
            App.notifications.error('No se pudo descargar el reporte.');
        }
    }

    /**
     * Lista los reportes generados por el usuario o a los que tiene acceso.
     * @param {Object} params - Parámetros de filtrado y paginación.
     * @return {Promise<Object>} - Promesa con la lista de reportes y metadatos de paginación.
     */
    async listReports(params = {}) {
        try {
            const queryString = new URLSearchParams(params).toString();
            return await App.http.get(`${this.baseEndpoint}?${queryString}`);
        } catch (error) {
            console.error('ReportService: Error al listar reportes:', error);
            App.notifications.error('No se pudo cargar la lista de reportes.');
            return { items: [], pagination: {} };
        }
    }

    /**
     * Obtiene los detalles de un reporte específico.
     * @param {string} reportId - ID del reporte.
     * @return {Promise<Object|null>} - Promesa con los detalles del reporte o null.
     */
    async getReportDetails(reportId) {
        try {
            return await App.http.get(`${this.baseEndpoint}/${reportId}`);
        } catch (error) {
            console.error(`ReportService: Error al obtener detalles del reporte ${reportId}:`, error);
            App.notifications.error('No se pudo cargar la información del reporte.');
            return null;
        }
    }

    /**
     * Elimina un reporte generado.
     * @param {string} reportId - ID del reporte a eliminar.
     * @return {Promise<boolean>} - True si fue exitoso.
     */
    async deleteReport(reportId) {
        try {
            await App.http.delete(`${this.baseEndpoint}/${reportId}`);
            App.notifications.success('Reporte eliminado exitosamente.');
            App.events.dispatchEvent('report:deleted', { reportId });
            return true;
        } catch (error) {
            console.error(`ReportService: Error al eliminar reporte ${reportId}:`, error);
            App.notifications.error(error.message || 'No se pudo eliminar el reporte.');
            return false;
        }
    }

    /**
     * Obtiene datos para un dashboard específico.
     * @param {string} dashboardId - ID o nombre del dashboard.
     * @param {Object} filters - Filtros a aplicar al dashboard.
     * @return {Promise<Object|null>} - Promesa con los datos del dashboard.
     */
    async getDashboardData(dashboardId, filters = {}) {
        try {
            const queryString = new URLSearchParams(filters).toString();
            return await App.http.get(`${this.analyticsEndpoint}/dashboard/${dashboardId}?${queryString}`);
        } catch (error) {
            console.error(`ReportService: Error al obtener datos del dashboard ${dashboardId}:`, error);
            App.notifications.error('No se pudieron cargar los datos del dashboard.');
            return null;
        }
    }

    /**
     * Obtiene una lista de dashboards disponibles para el usuario.
     * @return {Promise<Array<Object>>}
     */
    async getAvailableDashboards() {
        try {
            return await App.http.get(`${this.analyticsEndpoint}/dashboards`);
        } catch (error) {
            console.error('ReportService: Error al obtener lista de dashboards:', error);
            App.notifications.error('No se pudo cargar la lista de dashboards.');
            return [];
        }
    }
}

// Registrar el servicio en la instancia global de la App
App.services.report = new ReportService();
