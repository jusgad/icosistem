/**
 * Utilidades para manejo de fechas
 * Sistema de Ecosistema de Emprendimiento
 * 
 * Proporciona funciones para formatear, validar, calcular y manipular fechas
 * con soporte para múltiples formatos, zonas horarias y localización en español
 */

// Configuración de localización
const LOCALE_ES = 'es-CO'; // Colombia
const TIMEZONE_BOGOTA = 'America/Bogota';

// Constantes de tiempo
const TIME_CONSTANTS = {
    SECOND: 1000,
    MINUTE: 60 * 1000,
    HOUR: 60 * 60 * 1000,
    DAY: 24 * 60 * 60 * 1000,
    WEEK: 7 * 24 * 60 * 60 * 1000,
    MONTH: 30 * 24 * 60 * 60 * 1000,
    YEAR: 365 * 24 * 60 * 60 * 1000
};

// Configuración de formatos comunes
const DATE_FORMATS = {
    SHORT: 'dd/MM/yyyy',
    MEDIUM: 'dd MMM yyyy',
    LONG: 'dd MMMM yyyy',
    FULL: 'EEEE, dd MMMM yyyy',
    ISO: 'yyyy-MM-dd',
    DATETIME: 'dd/MM/yyyy HH:mm',
    DATETIME_LONG: 'dd MMMM yyyy HH:mm',
    TIME: 'HH:mm',
    TIME_SECONDS: 'HH:mm:ss'
};

// Nombres de meses y días en español
const MONTHS_ES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
];

const MONTHS_SHORT_ES = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic'
];

const DAYS_ES = [
    'domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'
];

const DAYS_SHORT_ES = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

/**
 * Clase principal para utilidades de fecha
 */
class DateUtils {
    
    /**
     * Obtiene la fecha actual en zona horaria de Bogotá
     * @returns {Date} Fecha actual
     */
    static now() {
        return new Date();
    }

    /**
     * Obtiene la fecha actual como string ISO
     * @returns {string} Fecha en formato ISO
     */
    static nowISO() {
        return new Date().toISOString();
    }

    /**
     * Obtiene solo la fecha (sin hora) actual
     * @returns {Date} Fecha actual sin hora
     */
    static today() {
        const now = new Date();
        return new Date(now.getFullYear(), now.getMonth(), now.getDate());
    }

    /**
     * Obtiene la fecha de ayer
     * @returns {Date} Fecha de ayer
     */
    static yesterday() {
        const date = this.today();
        date.setDate(date.getDate() - 1);
        return date;
    }

    /**
     * Obtiene la fecha de mañana
     * @returns {Date} Fecha de mañana
     */
    static tomorrow() {
        const date = this.today();
        date.setDate(date.getDate() + 1);
        return date;
    }

    /**
     * Valida si una fecha es válida
     * @param {*} date - Fecha a validar
     * @returns {boolean} True si es válida
     */
    static isValid(date) {
        if (!date) return false;
        if (date instanceof Date) {
            return !isNaN(date.getTime());
        }
        const parsed = new Date(date);
        return !isNaN(parsed.getTime());
    }

    /**
     * Convierte string o timestamp a objeto Date
     * @param {string|number|Date} input - Entrada a convertir
     * @returns {Date|null} Objeto Date o null si es inválido
     */
    static parse(input) {
        if (!input) return null;
        
        if (input instanceof Date) {
            return this.isValid(input) ? input : null;
        }

        // Si es timestamp
        if (typeof input === 'number') {
            const date = new Date(input);
            return this.isValid(date) ? date : null;
        }

        // Si es string
        if (typeof input === 'string') {
            // Formato dd/MM/yyyy
            const ddmmyyyy = input.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
            if (ddmmyyyy) {
                const [, day, month, year] = ddmmyyyy;
                const date = new Date(year, month - 1, day);
                return this.isValid(date) ? date : null;
            }

            // Formato yyyy-MM-dd
            const yyyymmdd = input.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
            if (yyyymmdd) {
                const [, year, month, day] = yyyymmdd;
                const date = new Date(year, month - 1, day);
                return this.isValid(date) ? date : null;
            }

            // Intenta parsing estándar
            const date = new Date(input);
            return this.isValid(date) ? date : null;
        }

        return null;
    }

    /**
     * Formatea una fecha según el formato especificado
     * @param {Date|string|number} date - Fecha a formatear
     * @param {string} format - Formato de salida
     * @returns {string} Fecha formateada
     */
    static format(date, format = DATE_FORMATS.SHORT) {
        const d = this.parse(date);
        if (!d) return '';

        try {
            // Usar Intl.DateTimeFormat para formatos estándar
            const options = this._getIntlOptions(format);
            if (options) {
                return new Intl.DateTimeFormat(LOCALE_ES, options).format(d);
            }

            // Formateo manual para formatos personalizados
            return this._manualFormat(d, format);
        } catch (error) {
            console.warn('Error formateando fecha:', error);
            return d.toLocaleDateString(LOCALE_ES);
        }
    }

    /**
     * Convierte formato a opciones de Intl.DateTimeFormat
     * @private
     */
    static _getIntlOptions(format) {
        const options = {};
        
        switch (format) {
            case DATE_FORMATS.SHORT:
                return { day: '2-digit', month: '2-digit', year: 'numeric' };
            case DATE_FORMATS.MEDIUM:
                return { day: '2-digit', month: 'short', year: 'numeric' };
            case DATE_FORMATS.LONG:
                return { day: '2-digit', month: 'long', year: 'numeric' };
            case DATE_FORMATS.FULL:
                return { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' };
            case DATE_FORMATS.DATETIME:
                return { 
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit', hour12: false
                };
            case DATE_FORMATS.DATETIME_LONG:
                return { 
                    day: '2-digit', month: 'long', year: 'numeric',
                    hour: '2-digit', minute: '2-digit', hour12: false
                };
            case DATE_FORMATS.TIME:
                return { hour: '2-digit', minute: '2-digit', hour12: false };
            case DATE_FORMATS.TIME_SECONDS:
                return { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
            default:
                return null;
        }
    }

    /**
     * Formateo manual para casos especiales
     * @private
     */
    static _manualFormat(date, format) {
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');

        return format
            .replace('dd', day)
            .replace('MM', month)
            .replace('yyyy', year)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds);
    }

    /**
     * Obtiene fecha en formato ISO (yyyy-MM-dd)
     * @param {Date|string|number} date - Fecha
     * @returns {string} Fecha en formato ISO
     */
    static toISO(date) {
        const d = this.parse(date);
        if (!d) return '';
        
        const year = d.getFullYear();
        const month = (d.getMonth() + 1).toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    }

    /**
     * Obtiene fecha y hora en formato ISO completo
     * @param {Date|string|number} date - Fecha
     * @returns {string} Fecha y hora en formato ISO
     */
    static toISOString(date) {
        const d = this.parse(date);
        return d ? d.toISOString() : '';
    }

    /**
     * Calcula la diferencia entre dos fechas
     * @param {Date|string|number} date1 - Primera fecha
     * @param {Date|string|number} date2 - Segunda fecha
     * @param {string} unit - Unidad de diferencia (days, hours, minutes, etc.)
     * @returns {number} Diferencia en la unidad especificada
     */
    static diff(date1, date2, unit = 'days') {
        const d1 = this.parse(date1);
        const d2 = this.parse(date2);
        
        if (!d1 || !d2) return 0;
        
        const diffMs = Math.abs(d1.getTime() - d2.getTime());
        
        switch (unit) {
            case 'years':
                return Math.floor(diffMs / TIME_CONSTANTS.YEAR);
            case 'months':
                return Math.floor(diffMs / TIME_CONSTANTS.MONTH);
            case 'weeks':
                return Math.floor(diffMs / TIME_CONSTANTS.WEEK);
            case 'days':
                return Math.floor(diffMs / TIME_CONSTANTS.DAY);
            case 'hours':
                return Math.floor(diffMs / TIME_CONSTANTS.HOUR);
            case 'minutes':
                return Math.floor(diffMs / TIME_CONSTANTS.MINUTE);
            case 'seconds':
                return Math.floor(diffMs / TIME_CONSTANTS.SECOND);
            default:
                return Math.floor(diffMs / TIME_CONSTANTS.DAY);
        }
    }

    /**
     * Añade tiempo a una fecha
     * @param {Date|string|number} date - Fecha base
     * @param {number} amount - Cantidad a añadir
     * @param {string} unit - Unidad de tiempo
     * @returns {Date|null} Nueva fecha
     */
    static add(date, amount, unit = 'days') {
        const d = this.parse(date);
        if (!d) return null;
        
        const result = new Date(d);
        
        switch (unit) {
            case 'years':
                result.setFullYear(result.getFullYear() + amount);
                break;
            case 'months':
                result.setMonth(result.getMonth() + amount);
                break;
            case 'weeks':
                result.setDate(result.getDate() + (amount * 7));
                break;
            case 'days':
                result.setDate(result.getDate() + amount);
                break;
            case 'hours':
                result.setHours(result.getHours() + amount);
                break;
            case 'minutes':
                result.setMinutes(result.getMinutes() + amount);
                break;
            case 'seconds':
                result.setSeconds(result.getSeconds() + amount);
                break;
            default:
                result.setDate(result.getDate() + amount);
        }
        
        return result;
    }

    /**
     * Resta tiempo a una fecha
     * @param {Date|string|number} date - Fecha base
     * @param {number} amount - Cantidad a restar
     * @param {string} unit - Unidad de tiempo
     * @returns {Date|null} Nueva fecha
     */
    static subtract(date, amount, unit = 'days') {
        return this.add(date, -amount, unit);
    }

    /**
     * Obtiene el inicio del día para una fecha
     * @param {Date|string|number} date - Fecha
     * @returns {Date|null} Inicio del día
     */
    static startOfDay(date) {
        const d = this.parse(date);
        if (!d) return null;
        
        return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    }

    /**
     * Obtiene el final del día para una fecha
     * @param {Date|string|number} date - Fecha
     * @returns {Date|null} Final del día
     */
    static endOfDay(date) {
        const d = this.parse(date);
        if (!d) return null;
        
        return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
    }

    /**
     * Obtiene el inicio de la semana (lunes)
     * @param {Date|string|number} date - Fecha
     * @returns {Date|null} Inicio de semana
     */
    static startOfWeek(date) {
        const d = this.parse(date);
        if (!d) return null;
        
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Lunes como inicio
        return new Date(d.setDate(diff));
    }

    /**
     * Obtiene el inicio del mes
     * @param {Date|string|number} date - Fecha
     * @returns {Date|null} Inicio del mes
     */
    static startOfMonth(date) {
        const d = this.parse(date);
        if (!d) return null;
        
        return new Date(d.getFullYear(), d.getMonth(), 1);
    }

    /**
     * Obtiene el final del mes
     * @param {Date|string|number} date - Fecha
     * @returns {Date|null} Final del mes
     */
    static endOfMonth(date) {
        const d = this.parse(date);
        if (!d) return null;
        
        return new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);
    }

    /**
     * Verifica si una fecha es hoy
     * @param {Date|string|number} date - Fecha a verificar
     * @returns {boolean} True si es hoy
     */
    static isToday(date) {
        const d = this.parse(date);
        if (!d) return false;
        
        const today = this.today();
        return d.toDateString() === today.toDateString();
    }

    /**
     * Verifica si una fecha es ayer
     * @param {Date|string|number} date - Fecha a verificar
     * @returns {boolean} True si es ayer
     */
    static isYesterday(date) {
        const d = this.parse(date);
        if (!d) return false;
        
        const yesterday = this.yesterday();
        return d.toDateString() === yesterday.toDateString();
    }

    /**
     * Verifica si una fecha es mañana
     * @param {Date|string|number} date - Fecha a verificar
     * @returns {boolean} True si es mañana
     */
    static isTomorrow(date) {
        const d = this.parse(date);
        if (!d) return false;
        
        const tomorrow = this.tomorrow();
        return d.toDateString() === tomorrow.toDateString();
    }

    /**
     * Verifica si una fecha está en el pasado
     * @param {Date|string|number} date - Fecha a verificar
     * @returns {boolean} True si está en el pasado
     */
    static isPast(date) {
        const d = this.parse(date);
        if (!d) return false;
        
        return d.getTime() < Date.now();
    }

    /**
     * Verifica si una fecha está en el futuro
     * @param {Date|string|number} date - Fecha a verificar
     * @returns {boolean} True si está en el futuro
     */
    static isFuture(date) {
        const d = this.parse(date);
        if (!d) return false;
        
        return d.getTime() > Date.now();
    }

    /**
     * Verifica si una fecha está entre dos fechas
     * @param {Date|string|number} date - Fecha a verificar
     * @param {Date|string|number} start - Fecha inicio
     * @param {Date|string|number} end - Fecha fin
     * @returns {boolean} True si está entre las fechas
     */
    static isBetween(date, start, end) {
        const d = this.parse(date);
        const s = this.parse(start);
        const e = this.parse(end);
        
        if (!d || !s || !e) return false;
        
        return d.getTime() >= s.getTime() && d.getTime() <= e.getTime();
    }

    /**
     * Obtiene fecha relativa en texto (hace 2 días, en 3 horas, etc.)
     * @param {Date|string|number} date - Fecha
     * @returns {string} Texto relativo
     */
    static relative(date) {
        const d = this.parse(date);
        if (!d) return '';
        
        const now = new Date();
        const diffMs = d.getTime() - now.getTime();
        const isPast = diffMs < 0;
        const absDiffMs = Math.abs(diffMs);
        
        if (absDiffMs < TIME_CONSTANTS.MINUTE) {
            return 'ahora mismo';
        }
        
        if (absDiffMs < TIME_CONSTANTS.HOUR) {
            const minutes = Math.floor(absDiffMs / TIME_CONSTANTS.MINUTE);
            return isPast 
                ? `hace ${minutes} minuto${minutes !== 1 ? 's' : ''}`
                : `en ${minutes} minuto${minutes !== 1 ? 's' : ''}`;
        }
        
        if (absDiffMs < TIME_CONSTANTS.DAY) {
            const hours = Math.floor(absDiffMs / TIME_CONSTANTS.HOUR);
            return isPast 
                ? `hace ${hours} hora${hours !== 1 ? 's' : ''}`
                : `en ${hours} hora${hours !== 1 ? 's' : ''}`;
        }
        
        if (absDiffMs < TIME_CONSTANTS.WEEK) {
            const days = Math.floor(absDiffMs / TIME_CONSTANTS.DAY);
            if (days === 1) {
                return isPast ? 'ayer' : 'mañana';
            }
            return isPast 
                ? `hace ${days} días`
                : `en ${days} días`;
        }
        
        if (absDiffMs < TIME_CONSTANTS.MONTH) {
            const weeks = Math.floor(absDiffMs / TIME_CONSTANTS.WEEK);
            return isPast 
                ? `hace ${weeks} semana${weeks !== 1 ? 's' : ''}`
                : `en ${weeks} semana${weeks !== 1 ? 's' : ''}`;
        }
        
        if (absDiffMs < TIME_CONSTANTS.YEAR) {
            const months = Math.floor(absDiffMs / TIME_CONSTANTS.MONTH);
            return isPast 
                ? `hace ${months} mes${months !== 1 ? 'es' : ''}`
                : `en ${months} mes${months !== 1 ? 'es' : ''}`;
        }
        
        const years = Math.floor(absDiffMs / TIME_CONSTANTS.YEAR);
        return isPast 
            ? `hace ${years} año${years !== 1 ? 's' : ''}`
            : `en ${years} año${years !== 1 ? 's' : ''}`;
    }

    /**
     * Obtiene el nombre del mes en español
     * @param {Date|string|number} date - Fecha
     * @param {boolean} short - Si usar versión corta
     * @returns {string} Nombre del mes
     */
    static getMonthName(date, short = false) {
        const d = this.parse(date);
        if (!d) return '';
        
        const monthIndex = d.getMonth();
        return short ? MONTHS_SHORT_ES[monthIndex] : MONTHS_ES[monthIndex];
    }

    /**
     * Obtiene el nombre del día en español
     * @param {Date|string|number} date - Fecha
     * @param {boolean} short - Si usar versión corta
     * @returns {string} Nombre del día
     */
    static getDayName(date, short = false) {
        const d = this.parse(date);
        if (!d) return '';
        
        const dayIndex = d.getDay();
        return short ? DAYS_SHORT_ES[dayIndex] : DAYS_ES[dayIndex];
    }

    /**
     * Obtiene el número de días en un mes
     * @param {number} year - Año
     * @param {number} month - Mes (1-12)
     * @returns {number} Número de días
     */
    static getDaysInMonth(year, month) {
        return new Date(year, month, 0).getDate();
    }

    /**
     * Verifica si un año es bisiesto
     * @param {number} year - Año
     * @returns {boolean} True si es bisiesto
     */
    static isLeapYear(year) {
        return (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
    }

    /**
     * Genera un rango de fechas
     * @param {Date|string|number} start - Fecha inicio
     * @param {Date|string|number} end - Fecha fin
     * @param {string} unit - Unidad de incremento
     * @returns {Date[]} Array de fechas
     */
    static range(start, end, unit = 'days') {
        const startDate = this.parse(start);
        const endDate = this.parse(end);
        
        if (!startDate || !endDate) return [];
        
        const dates = [];
        let current = new Date(startDate);
        
        while (current <= endDate) {
            dates.push(new Date(current));
            current = this.add(current, 1, unit);
        }
        
        return dates;
    }

    /**
     * Valida si una fecha está en formato válido
     * @param {string} dateString - String de fecha
     * @param {string} format - Formato esperado
     * @returns {boolean} True si es válido
     */
    static isValidFormat(dateString, format = DATE_FORMATS.SHORT) {
        if (!dateString || typeof dateString !== 'string') return false;
        
        const parsed = this.parse(dateString);
        if (!parsed) return false;
        
        // Verificar que el formato de vuelta coincida
        const formatted = this.format(parsed, format);
        return formatted === dateString;
    }

    /**
     * Convierte fecha a timestamp
     * @param {Date|string|number} date - Fecha
     * @returns {number} Timestamp
     */
    static toTimestamp(date) {
        const d = this.parse(date);
        return d ? d.getTime() : 0;
    }

    /**
     * Convierte timestamp a fecha
     * @param {number} timestamp - Timestamp
     * @returns {Date|null} Fecha
     */
    static fromTimestamp(timestamp) {
        if (typeof timestamp !== 'number') return null;
        return new Date(timestamp);
    }

    /**
     * Obtiene la edad a partir de fecha de nacimiento
     * @param {Date|string|number} birthDate - Fecha de nacimiento
     * @returns {number} Edad en años
     */
    static getAge(birthDate) {
        const birth = this.parse(birthDate);
        if (!birth) return 0;
        
        const today = new Date();
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }

    /**
     * Formatea duración en texto legible
     * @param {number} milliseconds - Duración en milisegundos
     * @returns {string} Duración formateada
     */
    static formatDuration(milliseconds) {
        if (typeof milliseconds !== 'number' || milliseconds < 0) return '0 segundos';
        
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) {
            return `${days} día${days !== 1 ? 's' : ''}`;
        }
        if (hours > 0) {
            return `${hours} hora${hours !== 1 ? 's' : ''}`;
        }
        if (minutes > 0) {
            return `${minutes} minuto${minutes !== 1 ? 's' : ''}`;
        }
        return `${seconds} segundo${seconds !== 1 ? 's' : ''}`;
    }
}

// Funciones de conveniencia exportadas
export const {
    now,
    nowISO,
    today,
    yesterday,
    tomorrow,
    isValid,
    parse,
    format,
    toISO,
    toISOString,
    diff,
    add,
    subtract,
    startOfDay,
    endOfDay,
    startOfWeek,
    startOfMonth,
    endOfMonth,
    isToday,
    isYesterday,
    isTomorrow,
    isPast,
    isFuture,
    isBetween,
    relative,
    getMonthName,
    getDayName,
    getDaysInMonth,
    isLeapYear,
    range,
    isValidFormat,
    toTimestamp,
    fromTimestamp,
    getAge,
    formatDuration
} = DateUtils;

// Exportar clase principal y constantes
export { DateUtils as default, DATE_FORMATS, TIME_CONSTANTS, MONTHS_ES, DAYS_ES };

// Para uso directo en HTML sin módulos
if (typeof window !== 'undefined') {
    window.DateUtils = DateUtils;
    window.DATE_FORMATS = DATE_FORMATS;
}