/**
 * Formatter Utilities
 * Utilidades para formatear datos como fechas, números, moneda, texto, etc.
 * de forma consistente en el ecosistema.
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

const FormatterUtils = {

    /**
     * Formatea una fecha.
     * @param {Date|string|number} dateInput - La fecha a formatear.
     * @param {string} format - El formato deseado (ej: 'DD/MM/YYYY', 'YYYY-MM-DD HH:mm').
     * @param {string} locale - El locale a usar (ej: 'es-CO', 'en-US'). Por defecto 'es-CO'.
     * @returns {string} La fecha formateada o string vacío si la entrada es inválida.
     */
    formatDate(dateInput, format = 'DD/MM/YYYY', locale = 'es-CO') {
        if (!dateInput) return '';
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return '';

        const options = {};
        let formattedDate = format;

        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const hours = date.getHours();
        const minutes = date.getMinutes();
        const seconds = date.getSeconds();

        const pad = (num) => String(num).padStart(2, '0');

        // Reemplazos básicos
        formattedDate = formattedDate.replace('YYYY', year);
        formattedDate = formattedDate.replace('YY', String(year).slice(-2));
        formattedDate = formattedDate.replace('MM', pad(month));
        formattedDate = formattedDate.replace('M', month);
        formattedDate = formattedDate.replace('DD', pad(day));
        formattedDate = formattedDate.replace('D', day);
        formattedDate = formattedDate.replace('HH', pad(hours));
        formattedDate = formattedDate.replace('H', hours);
        formattedDate = formattedDate.replace('hh', pad(hours % 12 || 12));
        formattedDate = formattedDate.replace('h', hours % 12 || 12);
        formattedDate = formattedDate.replace('mm', pad(minutes));
        formattedDate = formattedDate.replace('m', minutes);
        formattedDate = formattedDate.replace('ss', pad(seconds));
        formattedDate = formattedDate.replace('s', seconds);
        formattedDate = formattedDate.replace('A', hours >= 12 ? 'PM' : 'AM');
        formattedDate = formattedDate.replace('a', hours >= 12 ? 'pm' : 'am');

        // Para formatos más complejos, se podría usar Intl.DateTimeFormat
        // o una librería como date-fns o moment.js si ya está en el proyecto.
        // Este es un formateador simple.

        return formattedDate;
    },

    /**
     * Formatea una fecha y hora.
     * @param {Date|string|number} dateInput - La fecha y hora a formatear.
     * @param {string} locale - El locale. Por defecto 'es-CO'.
     * @returns {string} La fecha y hora formateada.
     */
    formatDateTime(dateInput, locale = 'es-CO') {
        if (!dateInput) return '';
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return '';
        try {
            return new Intl.DateTimeFormat(locale, {
                year: 'numeric', month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit', hour12: true
            }).format(date);
        } catch (e) {
            console.warn("FormatterUtils: Error formateando fecha y hora, usando fallback.", e);
            return this.formatDate(date, 'DD/MM/YYYY hh:mm a', locale);
        }
    },

    /**
     * Formatea una fecha como tiempo relativo (ej: "hace 5 minutos").
     * @param {Date|string|number} dateInput - La fecha a formatear.
     * @param {string} locale - El locale. Por defecto 'es-CO'.
     * @returns {string} El tiempo relativo.
     */
    formatRelativeTime(dateInput, locale = 'es-CO') {
        if (!dateInput) return '';
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return '';

        const now = new Date();
        const seconds = Math.round((now - date) / 1000);
        const minutes = Math.round(seconds / 60);
        const hours = Math.round(minutes / 60);
        const days = Math.round(hours / 24);
        const weeks = Math.round(days / 7);
        const months = Math.round(days / 30.44); // Promedio de días en un mes
        const years = Math.round(days / 365.25);

        try {
            const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });

            if (seconds < 45) return rtf.format(0, 'second');
            if (minutes < 45) return rtf.format(-minutes, 'minute');
            if (hours < 22) return rtf.format(-hours, 'hour');
            if (days < 26) return rtf.format(-days, 'day');
            if (days < 60) return rtf.format(-weeks, 'week'); // Intl no soporta 'week' directamente en todos los locales
            if (months < 11) return rtf.format(-months, 'month');
            return rtf.format(-years, 'year');
        } catch (e) {
            // Fallback si Intl.RelativeTimeFormat no está soportado o falla
            if (seconds < 60) return 'hace un momento';
            if (minutes < 60) return `hace ${minutes} min`;
            if (hours < 24) return `hace ${hours} h`;
            if (days < 7) return `hace ${days} día(s)`;
            if (weeks < 4) return `hace ${weeks} semana(s)`;
            if (months < 12) return `hace ${months} mes(es)`;
            return `hace ${years} año(s)`;
        }
    },

    /**
     * Formatea un número.
     * @param {number} numberInput - El número a formatear.
     * @param {string} locale - El locale. Por defecto 'es-CO'.
     * @param {object} options - Opciones de Intl.NumberFormat.
     * @returns {string} El número formateado.
     */
    formatNumber(numberInput, locale = 'es-CO', options = {}) {
        if (typeof numberInput !== 'number' || isNaN(numberInput)) return '';
        try {
            return new Intl.NumberFormat(locale, options).format(numberInput);
        } catch (e) {
            console.warn("FormatterUtils: Error formateando número, usando fallback.", e);
            return String(numberInput);
        }
    },

    /**
     * Formatea un número como porcentaje.
     * @param {number} numberInput - El número (ej: 0.25 para 25%).
     * @param {string} locale - El locale. Por defecto 'es-CO'.
     * @param {object} options - Opciones adicionales para Intl.NumberFormat.
     * @returns {string} El porcentaje formateado.
     */
    formatPercentage(numberInput, locale = 'es-CO', options = {}) {
        if (typeof numberInput !== 'number' || isNaN(numberInput)) return '';
        const defaultOptions = { style: 'percent', minimumFractionDigits: 0, maximumFractionDigits: 2, ...options };
        try {
            return new Intl.NumberFormat(locale, defaultOptions).format(numberInput);
        } catch (e) {
            console.warn("FormatterUtils: Error formateando porcentaje, usando fallback.", e);
            return `${(numberInput * 100).toFixed(defaultOptions.maximumFractionDigits)}%`;
        }
    },

    /**
     * Formatea un número como moneda.
     * @param {number} amount - El monto.
     * @param {string} currencyCode - El código de moneda (ej: 'COP', 'USD'). Por defecto 'COP'.
     * @param {string} locale - El locale. Por defecto 'es-CO'.
     * @param {object} options - Opciones adicionales para Intl.NumberFormat.
     * @returns {string} El monto formateado como moneda.
     */
    formatCurrency(amount, currencyCode = 'COP', locale = 'es-CO', options = {}) {
        if (typeof amount !== 'number' || isNaN(amount)) return '';
        const defaultOptions = { style: 'currency', currency: currencyCode, ...options };
        try {
            return new Intl.NumberFormat(locale, defaultOptions).format(amount);
        } catch (e) {
            console.warn("FormatterUtils: Error formateando moneda, usando fallback.", e);
            return `${currencyCode} ${amount.toFixed(2)}`;
        }
    },

    /**
     * Trunca un texto a una longitud máxima y añade puntos suspensivos.
     * @param {string} text - El texto a truncar.
     * @param {number} maxLength - La longitud máxima. Por defecto 100.
     * @param {string} ellipsis - Los puntos suspensivos. Por defecto '...'.
     * @returns {string} El texto truncado.
     */
    truncateText(text, maxLength = 100, ellipsis = '...') {
        if (typeof text !== 'string') return '';
        if (text.length <= maxLength) return text;
        return text.slice(0, maxLength - ellipsis.length) + ellipsis;
    },

    /**
     * Convierte la primera letra de un string a mayúscula.
     * @param {string} text - El texto.
     * @returns {string} El texto con la primera letra en mayúscula.
     */
    capitalizeFirstLetter(text) {
        if (typeof text !== 'string' || text.length === 0) return '';
        return text.charAt(0).toUpperCase() + text.slice(1);
    },

    /**
     * Convierte un string a formato slug (ej: "Hola Mundo" -> "hola-mundo").
     * @param {string} text - El texto a convertir.
     * @returns {string} El slug.
     */
    slugify(text) {
        if (typeof text !== 'string') return '';
        return text
            .toString()
            .normalize('NFKD') // Descompone caracteres acentuados
            .toLowerCase()
            .trim()
            .replace(/\s+/g, '-') // Reemplaza espacios con -
            .replace(/[^\w-]+/g, '') // Remueve caracteres no alfanuméricos (excepto -)
            .replace(/--+/g, '-'); // Reemplaza múltiples - con uno solo
    },

    /**
     * Formatea un tamaño de archivo en bytes a un formato legible (KB, MB, GB).
     * @param {number} bytes - El tamaño en bytes.
     * @param {number} decimals - Número de decimales. Por defecto 2.
     * @returns {string} El tamaño formateado.
     */
    formatFileSize(bytes, decimals = 2) {
        if (typeof bytes !== 'number' || isNaN(bytes) || bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    /**
     * Obtiene iniciales de un nombre.
     * @param {string} name - El nombre completo.
     * @param {number} count - Número de iniciales a obtener. Por defecto 2.
     * @returns {string} Las iniciales en mayúsculas.
     */
    getInitials(name, count = 2) {
        if (typeof name !== 'string' || !name.trim()) return '';
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) {
            return parts[0].substring(0, count).toUpperCase();
        }
        return parts.slice(0, count).map(part => part.charAt(0).toUpperCase()).join('');
    },

    /**
     * Formatea un número de teléfono a un formato estándar.
     * (Esta es una implementación simple, para producción usar librerías como libphonenumber-js)
     * @param {string} phoneNumber - El número de teléfono.
     * @param {string} countryCode - Código de país (ej: '+57' para Colombia).
     * @returns {string} El número formateado o el original si no se puede formatear.
     */
    formatPhoneNumber(phoneNumber, countryCode = '+57') {
        if (typeof phoneNumber !== 'string') return '';
        let cleaned = phoneNumber.replace(/\D/g, ''); // Remover no dígitos

        if (cleaned.startsWith(countryCode.replace('+', ''))) {
            cleaned = cleaned.substring(countryCode.length -1);
        } else if (cleaned.startsWith(countryCode.substring(1))) {
             cleaned = cleaned.substring(countryCode.length -1);
        }


        if (countryCode === '+57' && cleaned.length === 10) { // Colombia
            return `${countryCode} (${cleaned.substring(0, 3)}) ${cleaned.substring(3, 6)}-${cleaned.substring(6)}`;
        }
        // Añadir más lógicas para otros países o usar una librería
        return phoneNumber; // Devuelve original si no hay formato específico
    },

    /**
     * Escapa caracteres HTML para prevenir XSS.
     * @param {string} unsafeText - Texto potencialmente inseguro.
     * @returns {string} Texto seguro.
     */
    escapeHTML(unsafeText) {
        if (typeof unsafeText !== 'string') return '';
        return unsafeText
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
};

// Exportar para uso global o como módulo
if (typeof window !== 'undefined') {
    window.FormatterUtils = FormatterUtils;
    // Si tienes un objeto App global, podrías adjuntarlo ahí:
    // window.App = window.App || {};
    // window.App.format = FormatterUtils;
}

// Para uso como módulo (si es necesario)
// export default FormatterUtils;
