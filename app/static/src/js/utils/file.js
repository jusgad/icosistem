/**
 * File Utilities - Ecosistema de Emprendimiento
 * ============================================
 * 
 * Utilidades para manejo de archivos en el lado del cliente.
 * Incluye validación, formateo, lectura y manipulación de archivos.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

'use strict';

const FileUtils = {

    /**
     * Formatea el tamaño de un archivo a un formato legible.
     * @param {number} bytes - Tamaño del archivo en bytes.
     * @param {number} decimals - Número de decimales a mostrar (default: 2).
     * @return {string} Tamaño formateado (ej: "1.23 MB").
     */
    formatFileSize(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    /**
     * Obtiene la extensión de un archivo a partir de su nombre.
     * @param {string} filename - Nombre del archivo.
     * @return {string} Extensión del archivo en minúsculas, o string vacío.
     */
    getFileExtension(filename) {
        if (!filename || typeof filename !== 'string') return '';
        const lastDot = filename.lastIndexOf('.');
        if (lastDot === -1 || lastDot === 0 || lastDot === filename.length - 1) {
            return ''; // Sin extensión o archivo oculto
        }
        return filename.substring(lastDot + 1).toLowerCase();
    },

    /**
     * Obtiene el nombre del archivo sin la extensión.
     * @param {string} filename - Nombre del archivo.
     * @return {string} Nombre del archivo sin extensión.
     */
    getFileNameWithoutExtension(filename) {
        if (!filename || typeof filename !== 'string') return '';
        const lastDot = filename.lastIndexOf('.');
        if (lastDot === -1 || lastDot === 0) {
            return filename;
        }
        return filename.substring(0, lastDot);
    },

    /**
     * Valida si la extensión de un archivo está permitida.
     * @param {string} filename - Nombre del archivo.
     * @param {string[]|Set<string>} allowedExtensions - Array o Set de extensiones permitidas (sin punto, en minúsculas).
     * @return {boolean} True si la extensión es válida, false en caso contrario.
     */
    isValidExtension(filename, allowedExtensions) {
        const extension = this.getFileExtension(filename);
        if (!extension) return false;
        const extensionsSet = Array.isArray(allowedExtensions) ? new Set(allowedExtensions) : allowedExtensions;
        return extensionsSet.has(extension);
    },

    /**
     * Valida si el tamaño de un archivo está dentro del límite.
     * @param {File|number} fileOrSize - Objeto File o tamaño en bytes.
     * @param {number} maxSizeInBytes - Tamaño máximo permitido en bytes.
     * @return {boolean} True si el tamaño es válido.
     */
    isValidSize(fileOrSize, maxSizeInBytes) {
        const size = typeof fileOrSize === 'number' ? fileOrSize : fileOrSize.size;
        return size <= maxSizeInBytes;
    },

    /**
     * Lee el contenido de un archivo como texto.
     * @param {File} file - Objeto File.
     * @return {Promise<string>} Promesa que resuelve con el contenido del archivo como texto.
     */
    readFileAsText(file) {
        return new Promise((resolve, reject) => {
            if (!(file instanceof File)) {
                return reject(new TypeError('El argumento debe ser un objeto File.'));
            }
            const reader = new FileReader();
            reader.onload = (event) => resolve(event.target.result);
            reader.onerror = (error) => reject(error);
            reader.readAsText(file);
        });
    },

    /**
     * Lee el contenido de un archivo como Data URL (Base64).
     * @param {File} file - Objeto File.
     * @return {Promise<string>} Promesa que resuelve con el contenido del archivo como Data URL.
     */
    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            if (!(file instanceof File)) {
                return reject(new TypeError('El argumento debe ser un objeto File.'));
            }
            const reader = new FileReader();
            reader.onload = (event) => resolve(event.target.result);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(file);
        });
    },

    /**
     * Lee el contenido de un archivo como ArrayBuffer.
     * @param {File} file - Objeto File.
     * @return {Promise<ArrayBuffer>} Promesa que resuelve con el contenido del archivo como ArrayBuffer.
     */
    readFileAsArrayBuffer(file) {
        return new Promise((resolve, reject) => {
            if (!(file instanceof File)) {
                return reject(new TypeError('El argumento debe ser un objeto File.'));
            }
            const reader = new FileReader();
            reader.onload = (event) => resolve(event.target.result);
            reader.onerror = (error) => reject(error);
            reader.readAsArrayBuffer(file);
        });
    },

    /**
     * Crea una URL de objeto para un archivo o Blob.
     * Útil para previsualizaciones. Recuerda revocarla con `revokeObjectURL`.
     * @param {File|Blob} fileOrBlob - Objeto File o Blob.
     * @return {string|null} URL del objeto o null si falla.
     */
    createObjectURL(fileOrBlob) {
        if (!(fileOrBlob instanceof File) && !(fileOrBlob instanceof Blob)) {
            console.error('El argumento debe ser un objeto File o Blob.');
            return null;
        }
        try {
            return URL.createObjectURL(fileOrBlob);
        } catch (error) {
            console.error('Error creando Object URL:', error);
            return null;
        }
    },

    /**
     * Revoca una URL de objeto previamente creada.
     * @param {string} objectURL - URL del objeto a revocar.
     */
    revokeObjectURL(objectURL) {
        if (objectURL && typeof objectURL === 'string') {
            try {
                URL.revokeObjectURL(objectURL);
            } catch (error) {
                console.error('Error revocando Object URL:', error);
            }
        }
    },

    /**
     * Obtiene las dimensiones de una imagen.
     * @param {File|string} imageSource - Objeto File de la imagen o URL de la imagen.
     * @return {Promise<{width: number, height: number}>} Promesa que resuelve con las dimensiones.
     */
    getImageDimensions(imageSource) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                resolve({ width: img.naturalWidth, height: img.naturalHeight });
                if (typeof imageSource !== 'string') { // Si es File, revocar URL
                    this.revokeObjectURL(img.src);
                }
            };
            img.onerror = (error) => {
                reject(error);
                if (typeof imageSource !== 'string') {
                    this.revokeObjectURL(img.src);
                }
            };
            if (typeof imageSource === 'string') {
                img.src = imageSource;
            } else if (imageSource instanceof File) {
                img.src = this.createObjectURL(imageSource);
            } else {
                reject(new TypeError('La fuente debe ser un File o una URL.'));
            }
        });
    },

    /**
     * Genera un nombre de archivo único.
     * @param {string} originalFilename - Nombre original del archivo.
     * @return {string} Nombre de archivo único.
     */
    generateUniqueFilename(originalFilename) {
        const timestamp = Date.now();
        const randomSuffix = Math.random().toString(36).substring(2, 8);
        const extension = this.getFileExtension(originalFilename);
        const baseName = this.getFileNameWithoutExtension(originalFilename)
            .replace(/[^a-zA-Z0-9_.-]/g, '_') // Sanitizar nombre base
            .substring(0, 50); // Limitar longitud del nombre base

        return `${baseName}_${timestamp}_${randomSuffix}${extension ? '.' + extension : ''}`;
    },

    /**
     * Convierte un Data URL a un objeto File.
     * @param {string} dataUrl - El Data URL a convertir.
     * @param {string} filename - El nombre del archivo resultante.
     * @return {Promise<File>} Promesa que resuelve con el objeto File.
     */
    async dataURLtoFile(dataUrl, filename) {
        try {
            const res = await fetch(dataUrl);
            const blob = await res.blob();
            return new File([blob], filename, { type: blob.type });
        } catch (error) {
            console.error('Error convirtiendo Data URL a File:', error);
            throw error;
        }
    },

    /**
     * Obtiene el tipo MIME de un archivo basado en su extensión.
     * @param {string} filename - Nombre del archivo.
     * @return {string|null} Tipo MIME o null si no se puede determinar.
     */
    getMimeType(filename) {
        const extension = this.getFileExtension(filename);
        if (!extension) return null;

        // Mapeo común, se puede expandir
        const mimeTypes = {
            'txt': 'text/plain',
            'html': 'text/html',
            'css': 'text/css',
            'js': 'application/javascript',
            'json': 'application/json',
            'xml': 'application/xml',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'svg': 'image/svg+xml',
            'webp': 'image/webp',
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'zip': 'application/zip',
            'rar': 'application/x-rar-compressed',
            'tar': 'application/x-tar',
            'gz': 'application/gzip',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'mov': 'video/quicktime',
            'csv': 'text/csv'
        };
        return mimeTypes[extension] || null;
    },

    /**
     * Crea un archivo Blob a partir de un contenido y tipo.
     * @param {any} content - Contenido del archivo (string, ArrayBuffer, etc.).
     * @param {string} type - Tipo MIME del contenido.
     * @return {Blob}
     */
    createBlob(content, type) {
        return new Blob([content], { type });
    },

    /**
     * Inicia la descarga de un archivo en el navegador.
     * @param {string|Blob|File} source - URL del archivo, Blob o File.
     * @param {string} filename - Nombre con el que se descargará el archivo.
     */
    downloadFile(source, filename) {
        const link = document.createElement('a');
        if (typeof source === 'string') {
            link.href = source;
        } else if (source instanceof Blob || source instanceof File) {
            link.href = URL.createObjectURL(source);
        } else {
            console.error('Fuente inválida para descarga.');
            return;
        }
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        if (typeof source !== 'string') {
            URL.revokeObjectURL(link.href); // Limpiar URL de objeto
        }
    }
};

// Hacer disponible globalmente si es necesario
if (typeof window !== 'undefined') {
    window.FileUtils = FileUtils;
    
    // Integrar con EcosistemaApp si existe
    if (window.EcosistemaApp && window.EcosistemaApp.utils) {
        window.EcosistemaApp.utils.file = FileUtils;
    } else if (window.EcosistemaApp) {
        window.EcosistemaApp.utils = { file: FileUtils };
    }
}

// Para uso como módulo (si es necesario)
// export default FileUtils;
