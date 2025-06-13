/**
 * FileService.js - Servicio para la Gestión de Archivos
 * =====================================================
 *
 * Maneja la subida, descarga, eliminación y gestión de metadatos de archivos.
 * Se integra con el backend para el almacenamiento y la persistencia.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js (para App.http, App.notifications, etc.)
 */

'use strict';

// Verificar que main.js esté cargado
if (typeof window.EcosistemaApp === 'undefined') {
    throw new Error('main.js debe cargarse antes que FileService.js');
}

// Alias para facilitar acceso
const App = window.EcosistemaApp;

class FileService {
    constructor() {
        this.baseEndpoint = '/api/v1/files'; // Endpoint base para archivos
        this.uploadEndpoint = `${this.baseEndpoint}/upload`;
        this.chunkedUploadEndpoint = `${this.uploadEndpoint}/chunked`; // Coincide con FileUpload.js
        this.resumeUploadEndpoint = `${this.uploadEndpoint}/resume`;   // Coincide con FileUpload.js
    }

    /**
     * Sube un archivo al servidor (subida simple).
     * @param {File} file - El archivo a subir.
     * @param {Object} metadata - Metadatos adicionales (title, description, documentType, projectId, context, etc.).
     * @param {Function} [onProgress] - Callback para el progreso de la subida (progressEvent).
     * @return {Promise<Object>} - Promesa con la información del archivo subido desde el backend.
     */
    async uploadFile(file, metadata = {}, onProgress) {
        const formData = new FormData();
        formData.append('file', file, file.name); // Es buena práctica incluir el nombre original

        // Agregar metadatos al FormData
        // El backend debe estar preparado para recibir estos campos.
        for (const key in metadata) {
            if (metadata.hasOwnProperty(key)) {
                formData.append(key, metadata[key]);
            }
        }

        try {
            // El tercer argumento 'true' indica que el body es FormData
            // El cuarto argumento es el callback de progreso
            const response = await App.http.post(this.uploadEndpoint, formData, true, onProgress);
            App.notifications.success(`Archivo "${file.name}" subido exitosamente.`);
            return response;
        } catch (error) {
            console.error('FileService: Error al subir archivo:', error);
            App.notifications.error(error.message || `No se pudo subir el archivo "${file.name}".`);
            throw error; // Re-lanzar para que el llamador pueda manejarlo
        }
    }

    /**
     * Inicia una subida por chunks.
     * @param {File} file - El archivo a subir.
     * @param {Object} metadata - Metadatos del archivo (documentType, context, projectId, etc.).
     * @return {Promise<Object>} - Promesa con el ID de la subida y otra información del backend.
     */
    async initChunkedUpload(file, metadata = {}) {
        const payload = {
            fileName: file.name,
            fileSize: file.size,
            fileType: file.type,
            ...metadata // Incluir todos los metadatos adicionales
        };
        try {
            // El backend debería generar un uploadId único para esta sesión de subida
            return await App.http.post(`${this.chunkedUploadEndpoint}/init`, payload);
        } catch (error) {
            console.error('FileService: Error al iniciar subida por chunks:', error);
            App.notifications.error('No se pudo iniciar la subida fragmentada del archivo.');
            throw error;
        }
    }

    /**
     * Sube un chunk (fragmento) de un archivo.
     * @param {string} uploadId - ID de la subida (obtenido de initChunkedUpload).
     * @param {Blob} chunk - El chunk del archivo a subir.
     * @param {number} chunkIndex - Índice del chunk (base 0).
     * @param {number} totalChunks - Número total de chunks.
     * @param {string} originalFileName - Nombre original del archivo.
     * @param {Function} [onProgress] - Callback para el progreso de la subida del chunk.
     * @return {Promise<Object>} - Promesa con la respuesta del servidor para este chunk.
     */
    async uploadChunk(uploadId, chunk, chunkIndex, totalChunks, originalFileName, onProgress) {
        const formData = new FormData();
        formData.append('uploadId', uploadId);
        formData.append('chunk', chunk, `${originalFileName}.part${chunkIndex}`); // Nombre del chunk
        formData.append('chunkIndex', chunkIndex);
        formData.append('totalChunks', totalChunks);
        formData.append('originalFileName', originalFileName);


        try {
            return await App.http.post(`${this.chunkedUploadEndpoint}/upload`, formData, true, onProgress);
        } catch (error) {
            console.error(`FileService: Error al subir chunk ${chunkIndex}:`, error);
            App.notifications.error(`Error al subir parte ${chunkIndex + 1} del archivo.`);
            throw error;
        }
    }

    /**
     * Finaliza una subida por chunks, indicando al backend que ensamble los chunks.
     * @param {string} uploadId - ID de la subida.
     * @param {string} fileName - Nombre original del archivo.
     * @param {number} totalChunks - Número total de chunks.
     * @param {Object} metadata - Metadatos finales (title, description, documentType, etc.).
     * @return {Promise<Object>} - Promesa con la información del archivo finalizado desde el backend.
     */
    async finalizeChunkedUpload(uploadId, fileName, totalChunks, metadata = {}) {
        const payload = {
            uploadId,
            fileName,
            totalChunks,
            ...metadata // Incluir metadatos finales
        };
        try {
            const response = await App.http.post(`${this.chunkedUploadEndpoint}/finalize`, payload);
            App.notifications.success(`Archivo "${fileName}" procesado exitosamente.`);
            return response;
        } catch (error) {
            console.error('FileService: Error al finalizar subida por chunks:', error);
            App.notifications.error('Error al finalizar la subida fragmentada del archivo.');
            throw error;
        }
    }

    /**
     * Verifica el estado de una subida por chunks (para resumir subidas interrumpidas).
     * @param {string} uploadId - ID de la subida.
     * @return {Promise<Object>} - Promesa con la información del estado de la subida (e.g., nextChunk).
     */
    async checkResumeInfo(uploadId) {
        try {
            return await App.http.get(`${this.resumeUploadEndpoint}/${uploadId}`);
        } catch (error) {
            console.warn('FileService: Error al verificar estado de subida (resume):', error);
            // No notificar error al usuario, ya que esto puede ser una verificación de fondo.
            throw error;
        }
    }

    /**
     * Obtiene la información (metadatos) de un archivo específico.
     * @param {string} fileId - ID del archivo.
     * @return {Promise<Object>} - Promesa con los metadatos del archivo.
     */
    async getFileInfo(fileId) {
        try {
            return await App.http.get(`${this.baseEndpoint}/${fileId}`);
        } catch (error) {
            console.error(`FileService: Error al obtener información del archivo ${fileId}:`, error);
            App.notifications.error('No se pudo obtener la información del archivo.');
            throw error;
        }
    }

    /**
     * Construye la URL de descarga para un archivo.
     * El backend en esta URL se encargará de servir el archivo con los headers correctos.
     * @param {string} fileId - ID del archivo.
     * @param {string} [versionId] - ID de la versión específica (opcional).
     * @return {string} - URL de descarga.
     */
    getDownloadUrl(fileId, versionId) {
        let url = `${App.config.API_BASE_URL}${this.baseEndpoint}/${fileId}/download`;
        if (versionId) {
            url += `?version=${versionId}`;
        }
        // Para que la descarga funcione correctamente en el navegador,
        // esta URL debe ser accesible directamente y el backend debe
        // establecer el header 'Content-Disposition: attachment; filename="nombre_archivo.ext"'.
        return url;
    }

    /**
     * Elimina un archivo del servidor.
     * @param {string} fileId - ID del archivo a eliminar.
     * @return {Promise<void>}
     */
    async deleteFile(fileId) {
        try {
            await App.http.delete(`${this.baseEndpoint}/${fileId}`);
            App.notifications.success('Archivo eliminado exitosamente.');
        } catch (error) {
            console.error(`FileService: Error al eliminar archivo ${fileId}:`, error);
            App.notifications.error(error.message || 'No se pudo eliminar el archivo.');
            throw error;
        }
    }

    /**
     * Lista archivos según parámetros de filtrado y paginación.
     * @param {Object} params - Parámetros (e.g., { page: 1, per_page: 20, category: 'document', projectId: 'uuid' }).
     * @return {Promise<Object>} - Promesa con la lista de archivos y metadatos de paginación.
     */
    async listFiles(params = {}) {
        try {
            const queryString = new URLSearchParams(params).toString();
            return await App.http.get(`${this.baseEndpoint}?${queryString}`);
        } catch (error) {
            console.error('FileService: Error al listar archivos:', error);
            App.notifications.error('No se pudo cargar la lista de archivos.');
            throw error;
        }
    }

    /**
     * Actualiza los metadatos de un archivo.
     * @param {string} fileId - ID del archivo.
     * @param {Object} metadata - Nuevos metadatos (title, description, tags, is_public, etc.).
     * @return {Promise<Object>} - Promesa con la información del archivo actualizado.
     */
    async updateFileMetadata(fileId, metadata) {
        try {
            const response = await App.http.put(`${this.baseEndpoint}/${fileId}/metadata`, metadata);
            App.notifications.success('Metadatos del archivo actualizados.');
            return response;
        } catch (error) {
            console.error(`FileService: Error al actualizar metadatos del archivo ${fileId}:`, error);
            App.notifications.error(error.message || 'No se pudieron actualizar los metadatos.');
            throw error;
        }
    }

    /**
     * Obtiene las versiones de un archivo.
     * @param {string} fileId - ID del archivo.
     * @return {Promise<Array<Object>>} - Promesa con la lista de versiones.
     */
    async getFileVersions(fileId) {
        try {
            return await App.http.get(`${this.baseEndpoint}/${fileId}/versions`);
        } catch (error) {
            console.error(`FileService: Error al obtener versiones del archivo ${fileId}:`, error);
            App.notifications.error('No se pudieron cargar las versiones del archivo.');
            throw error;
        }
    }

    /**
     * Restaura una versión específica de un archivo, convirtiéndola en la versión actual.
     * @param {string} fileId - ID del archivo.
     * @param {string} versionId - ID de la versión a restaurar.
     * @return {Promise<Object>} - Promesa con la información del archivo restaurado (la nueva versión actual).
     */
    async restoreFileVersion(fileId, versionId) {
        try {
            const response = await App.http.post(`${this.baseEndpoint}/${fileId}/versions/${versionId}/restore`);
            App.notifications.success('Versión del archivo restaurada exitosamente.');
            return response;
        } catch (error) {
            console.error(`FileService: Error al restaurar versión ${versionId} del archivo ${fileId}:`, error);
            App.notifications.error('No se pudo restaurar la versión del archivo.');
            throw error;
        }
    }
}

// Registrar el servicio en la instancia global de la App
// Asumiendo que App.services es un objeto donde se registran los servicios.
if (App && App.services) {
    App.services.file = new FileService();
} else {
    console.warn('App.services no está definido. FileService no se pudo registrar globalmente.');
    // Podrías optar por exportar la clase o una instancia si no hay un objeto App global.
    // export default new FileService();
}
