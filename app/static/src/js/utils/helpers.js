/**
 * Helper Utilities para Ecosistema de Emprendimiento
 * Colección completa de funciones de utilidad para toda la aplicación
 * 
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

/**
 * FORMATEO DE FECHAS Y TIEMPO
 */
const DateHelpers = {
    /**
     * Formatea una fecha según el locale
     */
    formatDate(date, options = {}) {
        if (!date) return '';
        
        try {
            const dateObj = typeof date === 'string' ? new Date(date) : date;
            const defaultOptions = {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                ...options
            };
            
            return new Intl.DateTimeFormat('es-CO', defaultOptions).format(dateObj);
        } catch (error) {
            console.error('Error formatting date:', error);
            return '';
        }
    },
    
    /**
     * Formatea fecha y hora
     */
    formatDateTime(date, options = {}) {
        if (!date) return '';
        
        const defaultOptions = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            ...options
        };
        
        return this.formatDate(date, defaultOptions);
    },
    
    /**
     * Formatea fecha relativa (hace X tiempo)
     */
    formatRelativeTime(date) {
        if (!date) return '';
        
        try {
            const dateObj = typeof date === 'string' ? new Date(date) : date;
            const now = new Date();
            const diffInSeconds = Math.floor((now - dateObj) / 1000);
            
            if (diffInSeconds < 60) return 'hace unos segundos';
            if (diffInSeconds < 3600) return `hace ${Math.floor(diffInSeconds / 60)} minutos`;
            if (diffInSeconds < 86400) return `hace ${Math.floor(diffInSeconds / 3600)} horas`;
            if (diffInSeconds < 2592000) return `hace ${Math.floor(diffInSeconds / 86400)} días`;
            if (diffInSeconds < 31536000) return `hace ${Math.floor(diffInSeconds / 2592000)} meses`;
            
            return `hace ${Math.floor(diffInSeconds / 31536000)} años`;
        } catch (error) {
            console.error('Error formatting relative time:', error);
            return '';
        }
    },
    
    /**
     * Obtiene el rango de fechas para reportes
     */
    getDateRange(period) {
        const now = new Date();
        const ranges = {
            today: {
                start: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
                end: now
            },
            yesterday: {
                start: new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1),
                end: new Date(now.getFullYear(), now.getMonth(), now.getDate())
            },
            thisWeek: {
                start: new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay()),
                end: now
            },
            thisMonth: {
                start: new Date(now.getFullYear(), now.getMonth(), 1),
                end: now
            },
            thisQuarter: {
                start: new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1),
                end: now
            },
            thisYear: {
                start: new Date(now.getFullYear(), 0, 1),
                end: now
            }
        };
        
        return ranges[period] || ranges.thisMonth;
    },
    
    /**
     * Verifica si una fecha está en el rango
     */
    isDateInRange(date, startDate, endDate) {
        const checkDate = new Date(date);
        const start = new Date(startDate);
        const end = new Date(endDate);
        
        return checkDate >= start && checkDate <= end;
    },
    
    /**
     * Calcula la edad desde una fecha de nacimiento
     */
    calculateAge(birthDate) {
        const today = new Date();
        const birth = new Date(birthDate);
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }
};

/**
 * FORMATEO DE NÚMEROS Y MONEDAS
 */
const NumberHelpers = {
    /**
     * Formatea números como moneda
     */
    formatCurrency(amount, currency = 'COP', locale = 'es-CO') {
        if (amount === null || amount === undefined) return '';
        
        try {
            return new Intl.NumberFormat(locale, {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(amount);
        } catch (error) {
            console.error('Error formatting currency:', error);
            return amount.toString();
        }
    },
    
    /**
     * Formatea números grandes (K, M, B)
     */
    formatLargeNumber(num, decimals = 1) {
        if (num === null || num === undefined) return '';
        
        const absNum = Math.abs(num);
        const sign = num < 0 ? '-' : '';
        
        if (absNum >= 1e9) {
            return sign + (absNum / 1e9).toFixed(decimals) + 'B';
        } else if (absNum >= 1e6) {
            return sign + (absNum / 1e6).toFixed(decimals) + 'M';
        } else if (absNum >= 1e3) {
            return sign + (absNum / 1e3).toFixed(decimals) + 'K';
        }
        
        return num.toString();
    },
    
    /**
     * Formatea porcentajes
     */
    formatPercentage(value, decimals = 1) {
        if (value === null || value === undefined) return '';
        
        return `${(value * 100).toFixed(decimals)}%`;
    },
    
    /**
     * Formatea números con separadores de miles
     */
    formatNumber(num, decimals = 0) {
        if (num === null || num === undefined) return '';
        
        return new Intl.NumberFormat('es-CO', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(num);
    },
    
    /**
     * Convierte string a número limpio
     */
    parseNumber(str) {
        if (typeof str === 'number') return str;
        if (!str) return 0;
        
        // Remover caracteres no numéricos excepto punto y coma
        const cleanStr = str.toString().replace(/[^\d.,-]/g, '');
        
        // Convertir comas por puntos para decimales
        const normalizedStr = cleanStr.replace(',', '.');
        
        return parseFloat(normalizedStr) || 0;
    },
    
    /**
     * Genera número aleatorio en rango
     */
    randomInRange(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    },
    
    /**
     * Calcula crecimiento porcentual
     */
    calculateGrowth(current, previous) {
        if (!previous || previous === 0) return 0;
        return ((current - previous) / previous) * 100;
    }
};

/**
 * UTILIDADES DE STRINGS
 */
const StringHelpers = {
    /**
     * Capitaliza primera letra
     */
    capitalize(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    },
    
    /**
     * Convierte a Title Case
     */
    toTitleCase(str) {
        if (!str) return '';
        return str.replace(/\w\S*/g, this.capitalize);
    },
    
    /**
     * Genera slug desde string
     */
    slugify(str) {
        if (!str) return '';
        
        return str
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '') // Remover acentos
            .replace(/[^\w\s-]/g, '') // Remover caracteres especiales
            .replace(/[\s_-]+/g, '-') // Reemplazar espacios por guiones
            .replace(/^-+|-+$/g, ''); // Remover guiones al inicio/final
    },
    
    /**
     * Trunca texto con elipsis
     */
    truncate(str, length = 100, suffix = '...') {
        if (!str || str.length <= length) return str;
        return str.substring(0, length) + suffix;
    },
    
    /**
     * Extrae iniciales de un nombre
     */
    getInitials(name, maxInitials = 2) {
        if (!name) return '';
        
        const words = name.trim().split(' ');
        const initials = words
            .slice(0, maxInitials)
            .map(word => word.charAt(0).toUpperCase());
        
        return initials.join('');
    },
    
    /**
     * Máscara para teléfonos colombianos
     */
    formatPhoneNumber(phone) {
        if (!phone) return '';
        
        const digits = phone.replace(/\D/g, '');
        
        if (digits.length === 10) {
            return digits.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
        } else if (digits.length === 7) {
            return digits.replace(/(\d{3})(\d{4})/, '$1-$2');
        }
        
        return phone;
    },
    
    /**
     * Máscara para documentos
     */
    formatDocument(doc, type = 'cedula') {
        if (!doc) return '';
        
        const digits = doc.replace(/\D/g, '');
        
        switch (type) {
            case 'nit':
                if (digits.length >= 8) {
                    const nit = digits.slice(0, -1);
                    const dv = digits.slice(-1);
                    return `${nit}-${dv}`;
                }
                return digits;
                
            case 'cedula':
                return new Intl.NumberFormat('es-CO').format(parseInt(digits));
                
            default:
                return doc;
        }
    },
    
    /**
     * Genera password aleatorio
     */
    generatePassword(length = 12, includeSymbols = true) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        const symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?';
        const allChars = includeSymbols ? chars + symbols : chars;
        
        let password = '';
        for (let i = 0; i < length; i++) {
            password += allChars.charAt(Math.floor(Math.random() * allChars.length));
        }
        
        return password;
    },
    
    /**
     * Valida si es email válido
     */
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },
    
    /**
     * Resalta texto en búsquedas
     */
    highlightText(text, searchTerm) {
        if (!text || !searchTerm) return text;
        
        const regex = new RegExp(`(${searchTerm})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }
};

/**
 * UTILIDADES DE ARRAYS Y OBJETOS
 */
const CollectionHelpers = {
    /**
     * Agrupa array por propiedad
     */
    groupBy(array, key) {
        if (!Array.isArray(array)) return {};
        
        return array.reduce((groups, item) => {
            const group = typeof key === 'function' ? key(item) : item[key];
            groups[group] = groups[group] || [];
            groups[group].push(item);
            return groups;
        }, {});
    },
    
    /**
     * Ordena array por múltiples campos
     */
    sortBy(array, ...keys) {
        if (!Array.isArray(array)) return [];
        
        return array.sort((a, b) => {
            for (const key of keys) {
                let aVal, bVal, desc = false;
                
                if (typeof key === 'string') {
                    if (key.startsWith('-')) {
                        desc = true;
                        aVal = a[key.slice(1)];
                        bVal = b[key.slice(1)];
                    } else {
                        aVal = a[key];
                        bVal = b[key];
                    }
                } else if (typeof key === 'function') {
                    aVal = key(a);
                    bVal = key(b);
                }
                
                if (aVal < bVal) return desc ? 1 : -1;
                if (aVal > bVal) return desc ? -1 : 1;
            }
            return 0;
        });
    },
    
    /**
     * Filtra y busca en array
     */
    searchAndFilter(array, searchTerm, searchFields, filters = {}) {
        if (!Array.isArray(array)) return [];
        
        let result = array;
        
        // Aplicar filtros
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                result = result.filter(item => {
                    if (Array.isArray(value)) {
                        return value.includes(item[key]);
                    }
                    return item[key] === value;
                });
            }
        });
        
        // Aplicar búsqueda
        if (searchTerm && searchFields) {
            const term = searchTerm.toLowerCase();
            result = result.filter(item => {
                return searchFields.some(field => {
                    const value = this.getNestedValue(item, field);
                    return value && value.toString().toLowerCase().includes(term);
                });
            });
        }
        
        return result;
    },
    
    /**
     * Paginación de array
     */
    paginate(array, page = 1, perPage = 10) {
        if (!Array.isArray(array)) return { data: [], pagination: {} };
        
        const offset = (page - 1) * perPage;
        const data = array.slice(offset, offset + perPage);
        const total = array.length;
        const totalPages = Math.ceil(total / perPage);
        
        return {
            data,
            pagination: {
                page,
                perPage,
                total,
                totalPages,
                hasNext: page < totalPages,
                hasPrev: page > 1
            }
        };
    },
    
    /**
     * Obtiene valor anidado de objeto
     */
    getNestedValue(obj, path) {
        if (!obj || !path) return undefined;
        
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    },
    
    /**
     * Establece valor anidado en objeto
     */
    setNestedValue(obj, path, value) {
        if (!obj || !path) return obj;
        
        const keys = path.split('.');
        const lastKey = keys.pop();
        
        const target = keys.reduce((current, key) => {
            if (!current[key]) current[key] = {};
            return current[key];
        }, obj);
        
        target[lastKey] = value;
        return obj;
    },
    
    /**
     * Copia profunda de objeto
     */
    deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj);
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === 'object') {
            const cloned = {};
            Object.keys(obj).forEach(key => {
                cloned[key] = this.deepClone(obj[key]);
            });
            return cloned;
        }
        return obj;
    },
    
    /**
     * Combina objetos de forma profunda
     */
    deepMerge(target, ...sources) {
        if (!sources.length) return target;
        const source = sources.shift();
        
        if (this.isObject(target) && this.isObject(source)) {
            for (const key in source) {
                if (this.isObject(source[key])) {
                    if (!target[key]) Object.assign(target, { [key]: {} });
                    this.deepMerge(target[key], source[key]);
                } else {
                    Object.assign(target, { [key]: source[key] });
                }
            }
        }
        
        return this.deepMerge(target, ...sources);
    },
    
    /**
     * Verifica si es objeto
     */
    isObject(item) {
        return item && typeof item === 'object' && !Array.isArray(item);
    },
    
    /**
     * Obtiene diferencias entre objetos
     */
    diff(obj1, obj2) {
        const changes = {};
        
        Object.keys(obj2).forEach(key => {
            if (obj1[key] !== obj2[key]) {
                changes[key] = {
                    from: obj1[key],
                    to: obj2[key]
                };
            }
        });
        
        return changes;
    }
};

/**
 * UTILIDADES DEL DOM
 */
const DOMHelpers = {
    /**
     * Selecciona elemento con manejo de errores
     */
    $(selector, context = document) {
        try {
            return context.querySelector(selector);
        } catch (error) {
            console.error('Invalid selector:', selector);
            return null;
        }
    },
    
    /**
     * Selecciona múltiples elementos
     */
    $$(selector, context = document) {
        try {
            return Array.from(context.querySelectorAll(selector));
        } catch (error) {
            console.error('Invalid selector:', selector);
            return [];
        }
    },
    
    /**
     * Crea elemento con atributos
     */
    createElement(tag, attributes = {}, children = []) {
        const element = document.createElement(tag);
        
        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'className') {
                element.className = value;
            } else if (key === 'innerHTML') {
                element.innerHTML = value;
            } else if (key === 'textContent') {
                element.textContent = value;
            } else if (key.startsWith('data-')) {
                element.setAttribute(key, value);
            } else {
                element[key] = value;
            }
        });
        
        children.forEach(child => {
            if (typeof child === 'string') {
                element.appendChild(document.createTextNode(child));
            } else if (child instanceof Node) {
                element.appendChild(child);
            }
        });
        
        return element;
    },
    
    /**
     * Alterna clase en elemento
     */
    toggleClass(element, className, force) {
        if (!element) return;
        
        if (force !== undefined) {
            element.classList.toggle(className, force);
        } else {
            element.classList.toggle(className);
        }
    },
    
    /**
     * Verifica si elemento está visible en viewport
     */
    isInViewport(element, threshold = 0) {
        if (!element) return false;
        
        const rect = element.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        const windowWidth = window.innerWidth || document.documentElement.clientWidth;
        
        return (
            rect.top >= -threshold &&
            rect.left >= -threshold &&
            rect.bottom <= windowHeight + threshold &&
            rect.right <= windowWidth + threshold
        );
    },
    
    /**
     * Scroll suave a elemento
     */
    scrollToElement(element, options = {}) {
        if (!element) return;
        
        const defaultOptions = {
            behavior: 'smooth',
            block: 'start',
            inline: 'nearest',
            ...options
        };
        
        element.scrollIntoView(defaultOptions);
    },
    
    /**
     * Obtiene posición del elemento
     */
    getElementPosition(element) {
        if (!element) return { top: 0, left: 0 };
        
        const rect = element.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        
        return {
            top: rect.top + scrollTop,
            left: rect.left + scrollLeft,
            width: rect.width,
            height: rect.height
        };
    },
    
    /**
     * Copia texto al portapapeles
     */
    async copyToClipboard(text) {
        try {
            if (navigator.clipboard) {
                await navigator.clipboard.writeText(text);
                return true;
            } else {
                // Fallback para navegadores antiguos
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.opacity = '0';
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                return true;
            }
        } catch (error) {
            console.error('Error copying to clipboard:', error);
            return false;
        }
    },
    
    /**
     * Descarga archivo desde blob o URL
     */
    downloadFile(data, filename, mimeType = 'application/octet-stream') {
        const blob = data instanceof Blob ? data : new Blob([data], { type: mimeType });
        const url = window.URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        window.URL.revokeObjectURL(url);
    }
};

/**
 * UTILIDADES DE ALMACENAMIENTO
 */
const StorageHelpers = {
    /**
     * LocalStorage con manejo de errores y TTL
     */
    setLocal(key, value, ttl = null) {
        try {
            const item = {
                value,
                timestamp: Date.now(),
                ttl
            };
            localStorage.setItem(key, JSON.stringify(item));
            return true;
        } catch (error) {
            console.error('Error setting localStorage:', error);
            return false;
        }
    },
    
    getLocal(key) {
        try {
            const itemStr = localStorage.getItem(key);
            if (!itemStr) return null;
            
            const item = JSON.parse(itemStr);
            
            // Verificar TTL
            if (item.ttl && Date.now() - item.timestamp > item.ttl) {
                localStorage.removeItem(key);
                return null;
            }
            
            return item.value;
        } catch (error) {
            console.error('Error getting localStorage:', error);
            return null;
        }
    },
    
    removeLocal(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('Error removing localStorage:', error);
            return false;
        }
    },
    
    /**
     * SessionStorage con manejo de errores
     */
    setSession(key, value) {
        try {
            sessionStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('Error setting sessionStorage:', error);
            return false;
        }
    },
    
    getSession(key) {
        try {
            const item = sessionStorage.getItem(key);
            return item ? JSON.parse(item) : null;
        } catch (error) {
            console.error('Error getting sessionStorage:', error);
            return null;
        }
    },
    
    removeSession(key) {
        try {
            sessionStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('Error removing sessionStorage:', error);
            return false;
        }
    },
    
    /**
     * Limpia almacenamiento expirado
     */
    cleanExpiredStorage() {
        try {
            const keys = Object.keys(localStorage);
            keys.forEach(key => {
                this.getLocal(key); // Esto eliminará automáticamente los expirados
            });
        } catch (error) {
            console.error('Error cleaning expired storage:', error);
        }
    }
};

/**
 * UTILIDADES DE PERFORMANCE
 */
const PerformanceHelpers = {
    /**
     * Debounce function
     */
    debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    },
    
    /**
     * Throttle function
     */
    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    /**
     * Memoization
     */
    memoize(func, resolver) {
        const cache = new Map();
        
        return function memoized(...args) {
            const key = resolver ? resolver(...args) : JSON.stringify(args);
            
            if (cache.has(key)) {
                return cache.get(key);
            }
            
            const result = func.apply(this, args);
            cache.set(key, result);
            return result;
        };
    },
    
    /**
     * Lazy loading de imágenes
     */
    lazyLoadImages(selector = 'img[data-src]', options = {}) {
        const defaultOptions = {
            threshold: 0.1,
            rootMargin: '50px',
            ...options
        };
        
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            }, defaultOptions);
            
            document.querySelectorAll(selector).forEach(img => {
                observer.observe(img);
            });
        }
    },
    
    /**
     * Medición de performance
     */
    measure(name, fn) {
        return function measured(...args) {
            const start = performance.now();
            const result = fn.apply(this, args);
            const end = performance.now();
            
            console.log(`${name} took ${end - start} milliseconds`);
            return result;
        };
    }
};

/**
 * UTILIDADES ESPECÍFICAS DEL ECOSISTEMA
 */
const EcosystemHelpers = {
    /**
     * Formatea información de industria
     */
    formatIndustry(industry) {
        const industries = {
            technology: 'Tecnología',
            fintech: 'Fintech',
            healthcare: 'Salud',
            education: 'Educación',
            retail: 'Retail',
            manufacturing: 'Manufactura',
            agriculture: 'Agricultura',
            energy: 'Energía',
            transportation: 'Transporte',
            'real-estate': 'Inmobiliario',
            tourism: 'Turismo',
            media: 'Medios',
            consulting: 'Consultoría',
            other: 'Otro'
        };
        
        return industries[industry] || industry;
    },
    
    /**
     * Formatea etapa del proyecto
     */
    formatProjectStage(stage) {
        const stages = {
            idea: 'Idea',
            validation: 'Validación',
            mvp: 'MVP',
            'early-stage': 'Etapa Temprana',
            growth: 'Crecimiento',
            scaling: 'Escalamiento',
            expansion: 'Expansión',
            mature: 'Maduro'
        };
        
        return stages[stage] || stage;
    },
    
    /**
     * Obtiene color por etapa
     */
    getStageColor(stage) {
        const colors = {
            idea: '#f59e0b',
            validation: '#3b82f6',
            mvp: '#8b5cf6',
            'early-stage': '#10b981',
            growth: '#06b6d4',
            scaling: '#f97316',
            expansion: '#ef4444',
            mature: '#6b7280'
        };
        
        return colors[stage] || '#6b7280';
    },
    
    /**
     * Calcula score de completitud de perfil
     */
    calculateProfileCompleteness(profile, requiredFields) {
        if (!profile || !requiredFields) return 0;
        
        const completedFields = requiredFields.filter(field => {
            const value = CollectionHelpers.getNestedValue(profile, field);
            return value !== null && value !== undefined && value !== '';
        });
        
        return Math.round((completedFields.length / requiredFields.length) * 100);
    },
    
    /**
     * Genera métricas de proyecto
     */
    generateProjectMetrics(project) {
        if (!project) return {};
        
        const metrics = {
            completeness: this.calculateProfileCompleteness(project, [
                'name', 'description', 'industry', 'stage', 'team', 'business_model'
            ]),
            funding_progress: project.current_funding && project.funding_goal ? 
                (project.current_funding / project.funding_goal) * 100 : 0,
            team_size: project.team ? project.team.length : 0,
            days_since_creation: project.created_at ? 
                Math.floor((Date.now() - new Date(project.created_at)) / (1000 * 60 * 60 * 24)) : 0
        };
        
        return metrics;
    },
    
    /**
     * Formatea estado de usuario
     */
    formatUserStatus(status) {
        const statuses = {
            active: { label: 'Activo', color: '#10b981' },
            inactive: { label: 'Inactivo', color: '#6b7280' },
            pending: { label: 'Pendiente', color: '#f59e0b' },
            suspended: { label: 'Suspendido', color: '#ef4444' },
            verified: { label: 'Verificado', color: '#3b82f6' }
        };
        
        return statuses[status] || { label: status, color: '#6b7280' };
    },
    
    /**
     * Genera avatar por defecto con iniciales
     */
    generateDefaultAvatar(name, size = 48) {
        const initials = StringHelpers.getInitials(name);
        const colors = ['#f59e0b', '#3b82f6', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4'];
        const bgColor = colors[name.charCodeAt(0) % colors.length];
        
        const svg = `
            <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
                <rect width="${size}" height="${size}" fill="${bgColor}" rx="${size/8}"/>
                <text x="50%" y="50%" dy="0.35em" fill="white" font-family="Arial, sans-serif" 
                      font-size="${size/2.5}" font-weight="bold" text-anchor="middle">${initials}</text>
            </svg>
        `;
        
        return `data:image/svg+xml;base64,${btoa(svg)}`;
    },
    
    /**
     * Valida completitud de onboarding
     */
    validateOnboardingProgress(user, role) {
        const requirements = {
            entrepreneur: [
                'profile.name', 'profile.email', 'profile.phone',
                'company.name', 'company.industry', 'company.stage',
                'project.description', 'project.target_market'
            ],
            ally: [
                'profile.name', 'profile.email', 'profile.phone',
                'professional.expertise', 'professional.experience',
                'availability.hours_per_week', 'availability.schedule'
            ],
            organization: [
                'company.name', 'company.nit', 'company.address',
                'contact.email', 'contact.phone', 'programs.focus_areas'
            ]
        };
        
        const requiredFields = requirements[role] || [];
        return this.calculateProfileCompleteness(user, requiredFields);
    }
};

/**
 * UTILIDADES DE URL Y NAVEGACIÓN
 */
const URLHelpers = {
    /**
     * Obtiene parámetros de URL
     */
    getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};
        
        for (const [key, value] of params) {
            result[key] = value;
        }
        
        return result;
    },
    
    /**
     * Construye URL con parámetros
     */
    buildUrl(baseUrl, params = {}) {
        const url = new URL(baseUrl, window.location.origin);
        
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                url.searchParams.set(key, value);
            }
        });
        
        return url.toString();
    },
    
    /**
     * Actualiza URL sin recargar página
     */
    updateUrl(params = {}, replaceState = false) {
        const currentParams = this.getUrlParams();
        const newParams = { ...currentParams, ...params };
        
        // Remover parámetros null/undefined
        Object.keys(newParams).forEach(key => {
            if (newParams[key] === null || newParams[key] === undefined) {
                delete newParams[key];
            }
        });
        
        const newUrl = this.buildUrl(window.location.pathname, newParams);
        
        if (replaceState) {
            history.replaceState(null, '', newUrl);
        } else {
            history.pushState(null, '', newUrl);
        }
    },
    
    /**
     * Verifica si URL es válida
     */
    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }
};

/**
 * UTILIDADES DE ARCHIVOS
 */
const FileHelpers = {
    /**
     * Formatea tamaño de archivo
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    /**
     * Obtiene extensión de archivo
     */
    getFileExtension(filename) {
        return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
    },
    
    /**
     * Verifica tipo de archivo
     */
    getFileType(filename) {
        const extension = this.getFileExtension(filename).toLowerCase();
        
        const types = {
            // Imágenes
            jpg: 'image', jpeg: 'image', png: 'image', gif: 'image', svg: 'image', webp: 'image',
            // Documentos
            pdf: 'document', doc: 'document', docx: 'document', txt: 'document',
            // Hojas de cálculo
            xls: 'spreadsheet', xlsx: 'spreadsheet', csv: 'spreadsheet',
            // Presentaciones
            ppt: 'presentation', pptx: 'presentation',
            // Video
            mp4: 'video', avi: 'video', mov: 'video', wmv: 'video',
            // Audio
            mp3: 'audio', wav: 'audio', flac: 'audio'
        };
        
        return types[extension] || 'unknown';
    },
    
    /**
     * Lee archivo como texto
     */
    readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    },
    
    /**
     * Lee archivo como Data URL
     */
    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    },
    
    /**
     * Valida archivo
     */
    validateFile(file, options = {}) {
        const errors = [];
        
        // Validar tamaño
        if (options.maxSize && file.size > options.maxSize) {
            errors.push(`El archivo excede el tamaño máximo de ${this.formatFileSize(options.maxSize)}`);
        }
        
        // Validar tipo
        if (options.allowedTypes && options.allowedTypes.length > 0) {
            const fileType = this.getFileType(file.name);
            const extension = this.getFileExtension(file.name);
            
            const isAllowed = options.allowedTypes.some(type => 
                type === fileType || type === extension || file.type === type
            );
            
            if (!isAllowed) {
                errors.push(`Tipo de archivo no permitido. Permitidos: ${options.allowedTypes.join(', ')}`);
            }
        }
        
        return {
            valid: errors.length === 0,
            errors
        };
    }
};

/**
 * CONSOLIDACIÓN DE TODAS LAS UTILIDADES
 */
const Helpers = {
    // Namespaces organizados
    date: DateHelpers,
    number: NumberHelpers,
    string: StringHelpers,
    collection: CollectionHelpers,
    dom: DOMHelpers,
    storage: StorageHelpers,
    performance: PerformanceHelpers,
    ecosystem: EcosystemHelpers,
    url: URLHelpers,
    file: FileHelpers,
    
    /**
     * Inicialización de helpers
     */
    init() {
        // Limpiar storage expirado al cargar
        this.storage.cleanExpiredStorage();
        
        // Configurar lazy loading automático
        this.performance.lazyLoadImages();
        
        // Configurar eventos globales
        this.setupGlobalEvents();
        
        console.log('🚀 Helpers initialized successfully');
    },
    
    /**
     * Configurar eventos globales
     */
    setupGlobalEvents() {
        // Prevenir comportamiento por defecto en enlaces vacíos
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a[href="#"], a[href=""]');
            if (link) {
                e.preventDefault();
            }
        });
        
        // Manejo global de errores de imágenes
        document.addEventListener('error', (e) => {
            if (e.target.tagName === 'IMG') {
                e.target.src = '/static/images/placeholder.svg';
            }
        }, true);
    },
    
    /**
     * Utilidades rápidas (atajos)
     */
    // Formateo rápido
    fmt: {
        date: (date) => DateHelpers.formatDate(date),
        currency: (amount) => NumberHelpers.formatCurrency(amount),
        number: (num) => NumberHelpers.formatNumber(num),
        percent: (val) => NumberHelpers.formatPercentage(val),
        fileSize: (bytes) => FileHelpers.formatFileSize(bytes)
    },
    
    // Validaciones rápidas
    is: {
        email: (str) => StringHelpers.isValidEmail(str),
        url: (str) => URLHelpers.isValidUrl(str),
        empty: (val) => val === null || val === undefined || val === '',
        array: (val) => Array.isArray(val),
        object: (val) => CollectionHelpers.isObject(val)
    },
    
    // Utilidades comunes
    utils: {
        sleep: (ms) => new Promise(resolve => setTimeout(resolve, ms)),
        random: (min, max) => NumberHelpers.randomInRange(min, max),
        uuid: () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        }),
        noop: () => {},
        identity: (x) => x
    }
};

// Auto-inicialización cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => Helpers.init());
} else {
    Helpers.init();
}

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Helpers;
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
    window.Helpers = Helpers;
    
    // Atajos globales opcionales (descomenta si los necesitas)
    // window.fmt = Helpers.fmt;
    // window.is = Helpers.is;
    // window.utils = Helpers.utils;
}