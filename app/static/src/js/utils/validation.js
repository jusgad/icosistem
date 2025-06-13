/**
 * Validation Utilities para Ecosistema de Emprendimiento
 * Sistema robusto de validación con reglas específicas del dominio y soporte multiidioma
 * 
 * @version 2.0.0
 * @author Sistema de Emprendimiento
 */

class ValidationEngine {
    constructor(options = {}) {
        this.options = {
            locale: options.locale || 'es',
            async: options.async !== false,
            stopOnFirstError: options.stopOnFirstError || false,
            sanitize: options.sanitize !== false,
            customMessages: options.customMessages || {},
            ...options
        };
        
        // Expresiones regulares comunes
        this.patterns = {
            email: /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/,
            phone: /^(\+?57|0057|57)?\s?[1-9]\d{9}$/, // Colombia format
            phoneInternational: /^\+?[1-9]\d{1,14}$/,
            url: /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$/,
            alphanumeric: /^[a-zA-Z0-9]+$/,
            alpha: /^[a-zA-Z]+$/,
            numeric: /^\d+$/,
            decimal: /^\d+(\.\d+)?$/,
            slug: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
            
            // Específicos del ecosistema
            nit: /^\d{8,10}-\d{1}$/, // NIT Colombia
            cedula: /^\d{6,10}$/, // Cédula Colombia
            rut: /^\d{8,15}$/, // RUT genérico
            iban: /^[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}$/,
            
            // Contraseñas
            password: {
                weak: /^.{6,}$/,
                medium: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
                strong: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/
            }
        };
        
        // Mensajes de error
        this.messages = {
            es: {
                required: 'Este campo es obligatorio',
                email: 'Debe ser un email válido',
                minLength: 'Debe tener al menos {min} caracteres',
                maxLength: 'No puede tener más de {max} caracteres',
                min: 'El valor mínimo es {min}',
                max: 'El valor máximo es {max}',
                pattern: 'El formato no es válido',
                url: 'Debe ser una URL válida',
                phone: 'Debe ser un número de teléfono válido',
                numeric: 'Solo se permiten números',
                alpha: 'Solo se permiten letras',
                alphanumeric: 'Solo se permiten letras y números',
                custom: 'El valor no es válido',
                
                // Específicos del ecosistema
                nit: 'Debe ser un NIT válido (formato: 12345678-9)',
                cedula: 'Debe ser un número de cédula válido',
                rut: 'Debe ser un RUT válido',
                businessName: 'Debe ser un nombre de empresa válido',
                projectName: 'Debe ser un nombre de proyecto válido',
                industry: 'Debe seleccionar una industria válida',
                stage: 'Debe seleccionar una etapa válida',
                funding: 'Debe ser un monto de financiación válido',
                
                // Contraseñas
                passwordWeak: 'La contraseña debe tener al menos 6 caracteres',
                passwordMedium: 'La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número',
                passwordStrong: 'La contraseña debe tener al menos 8 caracteres, mayúsculas, minúsculas, números y símbolos',
                passwordMatch: 'Las contraseñas no coinciden',
                
                // Archivos
                fileRequired: 'Debe seleccionar un archivo',
                fileSize: 'El archivo no puede superar {maxSize}MB',
                fileType: 'Tipo de archivo no permitido. Permitidos: {types}',
                fileCount: 'Puede subir máximo {max} archivos',
                
                // Fechas
                dateInvalid: 'Fecha no válida',
                dateMin: 'La fecha debe ser posterior a {min}',
                dateMax: 'La fecha debe ser anterior a {max}',
                dateRange: 'La fecha debe estar entre {min} y {max}',
                
                // Específicos de roles
                entrepreneurProfile: 'El perfil de emprendedor debe estar completo',
                allyProfile: 'El perfil de aliado debe estar completo',
                mentorExperience: 'Debe tener al menos 2 años de experiencia',
                organizationData: 'Los datos de la organización son inválidos'
            },
            
            en: {
                required: 'This field is required',
                email: 'Must be a valid email',
                minLength: 'Must be at least {min} characters',
                maxLength: 'Cannot exceed {max} characters',
                min: 'Minimum value is {min}',
                max: 'Maximum value is {max}',
                pattern: 'Invalid format',
                url: 'Must be a valid URL',
                phone: 'Must be a valid phone number',
                numeric: 'Only numbers allowed',
                alpha: 'Only letters allowed',
                alphanumeric: 'Only letters and numbers allowed',
                custom: 'Invalid value',
                
                // Ecosystem specific
                nit: 'Must be a valid NIT (format: 12345678-9)',
                cedula: 'Must be a valid ID number',
                rut: 'Must be a valid RUT',
                businessName: 'Must be a valid business name',
                projectName: 'Must be a valid project name',
                industry: 'Must select a valid industry',
                stage: 'Must select a valid stage',
                funding: 'Must be a valid funding amount',
                
                // Passwords
                passwordWeak: 'Password must be at least 6 characters',
                passwordMedium: 'Password must be at least 8 characters with uppercase, lowercase and number',
                passwordStrong: 'Password must be at least 8 characters with uppercase, lowercase, numbers and symbols',
                passwordMatch: 'Passwords do not match',
                
                // Files
                fileRequired: 'Must select a file',
                fileSize: 'File cannot exceed {maxSize}MB',
                fileType: 'File type not allowed. Allowed: {types}',
                fileCount: 'You can upload maximum {max} files',
                
                // Dates
                dateInvalid: 'Invalid date',
                dateMin: 'Date must be after {min}',
                dateMax: 'Date must be before {max}',
                dateRange: 'Date must be between {min} and {max}',
                
                // Role specific
                entrepreneurProfile: 'Entrepreneur profile must be complete',
                allyProfile: 'Ally profile must be complete',
                mentorExperience: 'Must have at least 2 years of experience',
                organizationData: 'Organization data is invalid'
            }
        };
        
        // Datos de referencia del ecosistema
        this.referenceData = {
            industries: [
                'technology', 'fintech', 'healthcare', 'education', 'retail',
                'manufacturing', 'agriculture', 'energy', 'transportation',
                'real-estate', 'tourism', 'media', 'consulting', 'other'
            ],
            
            projectStages: [
                'idea', 'validation', 'mvp', 'early-stage', 'growth',
                'scaling', 'expansion', 'mature'
            ],
            
            userRoles: [
                'entrepreneur', 'ally', 'mentor', 'client', 'admin', 'organization'
            ],
            
            countries: [
                'CO', 'MX', 'AR', 'PE', 'CL', 'VE', 'EC', 'BO', 'PY', 'UY',
                'BR', 'US', 'CA', 'ES', 'DE', 'FR', 'GB', 'IT', 'PT', 'NL'
            ],
            
            currencies: [
                'COP', 'USD', 'EUR', 'GBP', 'MXN', 'ARS', 'PEN', 'CLP',
                'VEF', 'BOB', 'PYG', 'UYU', 'BRL'
            ]
        };
        
        this.asyncValidators = new Map();
        this.customValidators = new Map();
    }
    
    /**
     * Valida un valor individual
     */
    async validateField(value, rules, context = {}) {
        const errors = [];
        
        // Normalizar reglas
        if (typeof rules === 'string') {
            rules = { [rules]: true };
        }
        
        // Sanitizar valor si está habilitado
        if (this.options.sanitize) {
            value = this.sanitizeValue(value, rules);
        }
        
        // Validar cada regla
        for (const [rule, ruleValue] of Object.entries(rules)) {
            try {
                const result = await this.validateRule(value, rule, ruleValue, context);
                if (result !== true) {
                    errors.push(result);
                    
                    if (this.options.stopOnFirstError) {
                        break;
                    }
                }
            } catch (error) {
                errors.push(this.getMessage('custom', { error: error.message }));
            }
        }
        
        return {
            valid: errors.length === 0,
            errors,
            value: value
        };
    }
    
    /**
     * Valida un formulario completo
     */
    async validateForm(data, schema, context = {}) {
        const results = {};
        const errors = {};
        let isValid = true;
        
        // Validar cada campo
        for (const [field, rules] of Object.entries(schema)) {
            const value = this.getNestedValue(data, field);
            const fieldResult = await this.validateField(value, rules, {
                ...context,
                field,
                data,
                allData: data
            });
            
            results[field] = fieldResult;
            
            if (!fieldResult.valid) {
                errors[field] = fieldResult.errors;
                isValid = false;
            }
        }
        
        // Validaciones cruzadas
        const crossValidationErrors = await this.validateCrossFields(data, schema, context);
        if (crossValidationErrors.length > 0) {
            errors._form = crossValidationErrors;
            isValid = false;
        }
        
        return {
            valid: isValid,
            errors,
            results,
            data: this.extractValidatedData(results)
        };
    }
    
    /**
     * Valida una regla específica
     */
    async validateRule(value, rule, ruleValue, context) {
        // Verificar si es un validador personalizado
        if (this.customValidators.has(rule)) {
            return await this.customValidators.get(rule)(value, ruleValue, context);
        }
        
        // Verificar si es un validador asíncrono
        if (this.asyncValidators.has(rule)) {
            return await this.asyncValidators.get(rule)(value, ruleValue, context);
        }
        
        // Validaciones síncronas
        switch (rule) {
            case 'required':
                return this.validateRequired(value, ruleValue);
                
            case 'email':
                return this.validateEmail(value, ruleValue);
                
            case 'minLength':
                return this.validateMinLength(value, ruleValue);
                
            case 'maxLength':
                return this.validateMaxLength(value, ruleValue);
                
            case 'min':
                return this.validateMin(value, ruleValue);
                
            case 'max':
                return this.validateMax(value, ruleValue);
                
            case 'pattern':
                return this.validatePattern(value, ruleValue);
                
            case 'url':
                return this.validateUrl(value, ruleValue);
                
            case 'phone':
                return this.validatePhone(value, ruleValue);
                
            case 'numeric':
                return this.validateNumeric(value, ruleValue);
                
            case 'alpha':
                return this.validateAlpha(value, ruleValue);
                
            case 'alphanumeric':
                return this.validateAlphanumeric(value, ruleValue);
                
            case 'file':
                return this.validateFile(value, ruleValue);
                
            case 'date':
                return this.validateDate(value, ruleValue);
                
            case 'password':
                return this.validatePassword(value, ruleValue);
                
            case 'passwordConfirm':
                return this.validatePasswordConfirm(value, ruleValue, context);
                
            // Validaciones específicas del ecosistema
            case 'nit':
                return this.validateNIT(value, ruleValue);
                
            case 'cedula':
                return this.validateCedula(value, ruleValue);
                
            case 'rut':
                return this.validateRUT(value, ruleValue);
                
            case 'industry':
                return this.validateIndustry(value, ruleValue);
                
            case 'projectStage':
                return this.validateProjectStage(value, ruleValue);
                
            case 'userRole':
                return this.validateUserRole(value, ruleValue);
                
            case 'country':
                return this.validateCountry(value, ruleValue);
                
            case 'currency':
                return this.validateCurrency(value, ruleValue);
                
            case 'businessName':
                return this.validateBusinessName(value, ruleValue);
                
            case 'projectName':
                return this.validateProjectName(value, ruleValue);
                
            case 'funding':
                return this.validateFunding(value, ruleValue);
                
            // Validaciones de perfil
            case 'entrepreneurProfile':
                return this.validateEntrepreneurProfile(value, ruleValue, context);
                
            case 'allyProfile':
                return this.validateAllyProfile(value, ruleValue, context);
                
            case 'mentorExperience':
                return this.validateMentorExperience(value, ruleValue);
                
            case 'organizationData':
                return this.validateOrganizationData(value, ruleValue);
                
            default:
                throw new Error(`Unknown validation rule: ${rule}`);
        }
    }
    
    /**
     * Validaciones básicas
     */
    validateRequired(value, required) {
        if (!required) return true;
        
        if (value === null || value === undefined) {
            return this.getMessage('required');
        }
        
        if (typeof value === 'string' && value.trim() === '') {
            return this.getMessage('required');
        }
        
        if (Array.isArray(value) && value.length === 0) {
            return this.getMessage('required');
        }
        
        return true;
    }
    
    validateEmail(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.email.test(value)) {
            return this.getMessage('email');
        }
        
        return true;
    }
    
    validateMinLength(value, minLength) {
        if (!value) return true;
        
        const length = typeof value === 'string' ? value.length : 0;
        if (length < minLength) {
            return this.getMessage('minLength', { min: minLength });
        }
        
        return true;
    }
    
    validateMaxLength(value, maxLength) {
        if (!value) return true;
        
        const length = typeof value === 'string' ? value.length : 0;
        if (length > maxLength) {
            return this.getMessage('maxLength', { max: maxLength });
        }
        
        return true;
    }
    
    validateMin(value, min) {
        if (!value) return true;
        
        const numValue = parseFloat(value);
        if (isNaN(numValue) || numValue < min) {
            return this.getMessage('min', { min });
        }
        
        return true;
    }
    
    validateMax(value, max) {
        if (!value) return true;
        
        const numValue = parseFloat(value);
        if (isNaN(numValue) || numValue > max) {
            return this.getMessage('max', { max });
        }
        
        return true;
    }
    
    validatePattern(value, pattern) {
        if (!value) return true;
        
        const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;
        if (!regex.test(value)) {
            return this.getMessage('pattern');
        }
        
        return true;
    }
    
    validateUrl(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.url.test(value)) {
            return this.getMessage('url');
        }
        
        return true;
    }
    
    validatePhone(value, options) {
        if (!value) return true;
        
        const config = typeof options === 'object' ? options : { international: false };
        const pattern = config.international ? 
            this.patterns.phoneInternational : this.patterns.phone;
        
        if (!pattern.test(value)) {
            return this.getMessage('phone');
        }
        
        return true;
    }
    
    validateNumeric(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.numeric.test(value)) {
            return this.getMessage('numeric');
        }
        
        return true;
    }
    
    validateAlpha(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.alpha.test(value)) {
            return this.getMessage('alpha');
        }
        
        return true;
    }
    
    validateAlphanumeric(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.alphanumeric.test(value)) {
            return this.getMessage('alphanumeric');
        }
        
        return true;
    }
    
    /**
     * Validación de archivos
     */
    validateFile(value, options) {
        if (!value) return true;
        
        const config = {
            maxSize: 10, // MB
            allowedTypes: [],
            maxCount: 1,
            ...options
        };
        
        const files = Array.isArray(value) ? value : [value];
        
        // Verificar cantidad
        if (files.length > config.maxCount) {
            return this.getMessage('fileCount', { max: config.maxCount });
        }
        
        for (const file of files) {
            // Verificar tamaño
            if (file.size > config.maxSize * 1024 * 1024) {
                return this.getMessage('fileSize', { maxSize: config.maxSize });
            }
            
            // Verificar tipo
            if (config.allowedTypes.length > 0) {
                const fileType = file.type || '';
                const fileName = file.name || '';
                const extension = fileName.split('.').pop()?.toLowerCase();
                
                const isAllowed = config.allowedTypes.some(type => {
                    if (type.includes('/')) {
                        return fileType === type;
                    } else {
                        return extension === type.toLowerCase();
                    }
                });
                
                if (!isAllowed) {
                    return this.getMessage('fileType', { 
                        types: config.allowedTypes.join(', ') 
                    });
                }
            }
        }
        
        return true;
    }
    
    /**
     * Validación de fechas
     */
    validateDate(value, options) {
        if (!value) return true;
        
        const date = new Date(value);
        if (isNaN(date.getTime())) {
            return this.getMessage('dateInvalid');
        }
        
        const config = typeof options === 'object' ? options : {};
        
        if (config.min) {
            const minDate = new Date(config.min);
            if (date < minDate) {
                return this.getMessage('dateMin', { min: this.formatDate(minDate) });
            }
        }
        
        if (config.max) {
            const maxDate = new Date(config.max);
            if (date > maxDate) {
                return this.getMessage('dateMax', { max: this.formatDate(maxDate) });
            }
        }
        
        return true;
    }
    
    /**
     * Validación de contraseñas
     */
    validatePassword(value, strength) {
        if (!value) return true;
        
        const level = strength || 'medium';
        const pattern = this.patterns.password[level];
        
        if (!pattern || !pattern.test(value)) {
            return this.getMessage(`password${level.charAt(0).toUpperCase() + level.slice(1)}`);
        }
        
        return true;
    }
    
    validatePasswordConfirm(value, confirmField, context) {
        if (!value) return true;
        
        const password = this.getNestedValue(context.data, confirmField);
        if (value !== password) {
            return this.getMessage('passwordMatch');
        }
        
        return true;
    }
    
    /**
     * Validaciones específicas del ecosistema
     */
    validateNIT(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.nit.test(value)) {
            return this.getMessage('nit');
        }
        
        // Validar dígito de verificación
        const [nit, dv] = value.split('-');
        const calculatedDV = this.calculateNITDigit(nit);
        
        if (parseInt(dv) !== calculatedDV) {
            return this.getMessage('nit');
        }
        
        return true;
    }
    
    validateCedula(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.cedula.test(value)) {
            return this.getMessage('cedula');
        }
        
        return true;
    }
    
    validateRUT(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.patterns.rut.test(value)) {
            return this.getMessage('rut');
        }
        
        return true;
    }
    
    validateIndustry(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.referenceData.industries.includes(value)) {
            return this.getMessage('industry');
        }
        
        return true;
    }
    
    validateProjectStage(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.referenceData.projectStages.includes(value)) {
            return this.getMessage('stage');
        }
        
        return true;
    }
    
    validateUserRole(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.referenceData.userRoles.includes(value)) {
            return this.getMessage('custom');
        }
        
        return true;
    }
    
    validateCountry(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.referenceData.countries.includes(value)) {
            return this.getMessage('custom');
        }
        
        return true;
    }
    
    validateCurrency(value, validate) {
        if (!validate || !value) return true;
        
        if (!this.referenceData.currencies.includes(value)) {
            return this.getMessage('custom');
        }
        
        return true;
    }
    
    validateBusinessName(value, validate) {
        if (!validate || !value) return true;
        
        // Validar longitud y caracteres
        if (value.length < 2 || value.length > 100) {
            return this.getMessage('businessName');
        }
        
        // Validar que no tenga solo espacios o caracteres especiales
        if (!/^[a-zA-ZÀ-ÿ0-9\s\-\.\&\,]+$/.test(value)) {
            return this.getMessage('businessName');
        }
        
        return true;
    }
    
    validateProjectName(value, validate) {
        if (!validate || !value) return true;
        
        if (value.length < 3 || value.length > 50) {
            return this.getMessage('projectName');
        }
        
        if (!/^[a-zA-ZÀ-ÿ0-9\s\-\.]+$/.test(value)) {
            return this.getMessage('projectName');
        }
        
        return true;
    }
    
    validateFunding(value, options) {
        if (!value) return true;
        
        const config = {
            min: 1000,
            max: 10000000,
            currency: 'COP',
            ...options
        };
        
        const amount = parseFloat(value);
        if (isNaN(amount) || amount < config.min || amount > config.max) {
            return this.getMessage('funding');
        }
        
        return true;
    }
    
    /**
     * Validaciones de perfil
     */
    validateEntrepreneurProfile(value, validate, context) {
        if (!validate || !value) return true;
        
        const required = ['name', 'email', 'industry', 'experience', 'projectStage'];
        for (const field of required) {
            if (!value[field]) {
                return this.getMessage('entrepreneurProfile');
            }
        }
        
        return true;
    }
    
    validateAllyProfile(value, validate, context) {
        if (!validate || !value) return true;
        
        const required = ['name', 'email', 'expertise', 'experience', 'availability'];
        for (const field of required) {
            if (!value[field]) {
                return this.getMessage('allyProfile');
            }
        }
        
        return true;
    }
    
    validateMentorExperience(value, minYears) {
        if (!value) return true;
        
        const years = parseInt(value);
        const min = minYears || 2;
        
        if (isNaN(years) || years < min) {
            return this.getMessage('mentorExperience');
        }
        
        return true;
    }
    
    validateOrganizationData(value, validate) {
        if (!validate || !value) return true;
        
        const required = ['name', 'nit', 'address', 'phone', 'email'];
        for (const field of required) {
            if (!value[field]) {
                return this.getMessage('organizationData');
            }
        }
        
        return true;
    }
    
    /**
     * Validaciones cruzadas
     */
    async validateCrossFields(data, schema, context) {
        const errors = [];
        
        // Validar fechas de rango
        if (data.startDate && data.endDate) {
            const start = new Date(data.startDate);
            const end = new Date(data.endDate);
            
            if (start >= end) {
                errors.push('La fecha de inicio debe ser anterior a la fecha de fin');
            }
        }
        
        // Validar coherencia de perfil
        if (data.role === 'entrepreneur' && data.companyStage === 'mature' && data.experience < 5) {
            errors.push('Un emprendedor con empresa madura debe tener más experiencia');
        }
        
        // Validar disponibilidad de mentor
        if (data.role === 'ally' && data.availability && data.availability.hoursPerWeek > 40) {
            errors.push('Las horas de mentoría no pueden exceder 40 por semana');
        }
        
        return errors;
    }
    
    /**
     * Validadores asíncronos
     */
    registerAsyncValidator(name, validator) {
        this.asyncValidators.set(name, validator);
    }
    
    /**
     * Validadores personalizados
     */
    registerCustomValidator(name, validator) {
        this.customValidators.set(name, validator);
    }
    
    /**
     * Utilidades
     */
    sanitizeValue(value, rules) {
        if (typeof value !== 'string') return value;
        
        let sanitized = value;
        
        // Sanitización básica
        if (rules.trim !== false) {
            sanitized = sanitized.trim();
        }
        
        if (rules.lowercase) {
            sanitized = sanitized.toLowerCase();
        }
        
        if (rules.uppercase) {
            sanitized = sanitized.toUpperCase();
        }
        
        if (rules.alphanumeric) {
            sanitized = sanitized.replace(/[^a-zA-Z0-9]/g, '');
        }
        
        if (rules.numeric) {
            sanitized = sanitized.replace(/[^0-9]/g, '');
        }
        
        return sanitized;
    }
    
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }
    
    extractValidatedData(results) {
        const data = {};
        
        for (const [field, result] of Object.entries(results)) {
            if (result.valid) {
                this.setNestedValue(data, field, result.value);
            }
        }
        
        return data;
    }
    
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        
        const target = keys.reduce((current, key) => {
            if (!current[key]) current[key] = {};
            return current[key];
        }, obj);
        
        target[lastKey] = value;
    }
    
    getMessage(key, params = {}) {
        const messages = this.messages[this.options.locale] || this.messages.es;
        let message = this.options.customMessages[key] || messages[key] || messages.custom;
        
        // Interpolación de parámetros
        for (const [param, value] of Object.entries(params)) {
            message = message.replace(new RegExp(`\\{${param}\\}`, 'g'), value);
        }
        
        return message;
    }
    
    formatDate(date) {
        return new Intl.DateTimeFormat(this.options.locale).format(date);
    }
    
    calculateNITDigit(nit) {
        const weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71];
        let sum = 0;
        
        for (let i = 0; i < nit.length; i++) {
            sum += parseInt(nit[i]) * weights[nit.length - 1 - i];
        }
        
        const remainder = sum % 11;
        return remainder < 2 ? remainder : 11 - remainder;
    }
}

/**
 * Validador de formularios en tiempo real
 */
class FormValidator {
    constructor(form, schema, options = {}) {
        this.form = form;
        this.schema = schema;
        this.validator = new ValidationEngine(options);
        this.errors = {};
        this.touched = new Set();
        this.isValidating = false;
        
        this.options = {
            validateOnBlur: options.validateOnBlur !== false,
            validateOnInput: options.validateOnInput !== false,
            showErrorsOnlyWhenTouched: options.showErrorsOnlyWhenTouched !== false,
            debounceMs: options.debounceMs || 300,
            ...options
        };
        
        this.bindEvents();
    }
    
    bindEvents() {
        this.form.addEventListener('blur', this.handleBlur.bind(this), true);
        this.form.addEventListener('input', this.debounce(this.handleInput.bind(this), this.options.debounceMs));
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
    }
    
    async handleBlur(event) {
        if (!this.options.validateOnBlur) return;
        
        const field = this.getFieldName(event.target);
        if (field && this.schema[field]) {
            this.touched.add(field);
            await this.validateField(field);
        }
    }
    
    async handleInput(event) {
        if (!this.options.validateOnInput) return;
        
        const field = this.getFieldName(event.target);
        if (field && this.schema[field] && this.touched.has(field)) {
            await this.validateField(field);
        }
    }
    
    async handleSubmit(event) {
        event.preventDefault();
        
        // Marcar todos los campos como tocados
        Object.keys(this.schema).forEach(field => this.touched.add(field));
        
        const isValid = await this.validateAll();
        
        if (isValid) {
            this.onSubmit && this.onSubmit(this.getFormData());
        } else {
            this.focusFirstError();
        }
    }
    
    async validateField(fieldName) {
        const value = this.getFieldValue(fieldName);
        const rules = this.schema[fieldName];
        
        const result = await this.validator.validateField(value, rules, {
            field: fieldName,
            data: this.getFormData()
        });
        
        if (result.valid) {
            delete this.errors[fieldName];
        } else {
            this.errors[fieldName] = result.errors;
        }
        
        this.updateFieldDisplay(fieldName);
        return result.valid;
    }
    
    async validateAll() {
        this.isValidating = true;
        const data = this.getFormData();
        
        const result = await this.validator.validateForm(data, this.schema);
        
        this.errors = result.errors;
        this.updateAllFieldsDisplay();
        
        this.isValidating = false;
        return result.valid;
    }
    
    getFieldName(element) {
        return element.name || element.getAttribute('data-field');
    }
    
    getFieldValue(fieldName) {
        const element = this.form.querySelector(`[name="${fieldName}"], [data-field="${fieldName}"]`);
        if (!element) return null;
        
        if (element.type === 'checkbox') {
            return element.checked;
        } else if (element.type === 'radio') {
            const checked = this.form.querySelector(`[name="${fieldName}"]:checked`);
            return checked ? checked.value : null;
        } else if (element.type === 'file') {
            return element.files.length > 0 ? element.files : null;
        } else {
            return element.value;
        }
    }
    
    getFormData() {
        const data = {};
        
        for (const fieldName of Object.keys(this.schema)) {
            data[fieldName] = this.getFieldValue(fieldName);
        }
        
        return data;
    }
    
    updateFieldDisplay(fieldName) {
        const element = this.form.querySelector(`[name="${fieldName}"], [data-field="${fieldName}"]`);
        if (!element) return;
        
        const errorContainer = this.findErrorContainer(element);
        const errors = this.errors[fieldName] || [];
        
        // Mostrar errores solo si el campo fue tocado
        const shouldShowErrors = !this.options.showErrorsOnlyWhenTouched || this.touched.has(fieldName);
        
        if (errors.length > 0 && shouldShowErrors) {
            element.classList.add('is-invalid');
            element.classList.remove('is-valid');
            
            if (errorContainer) {
                errorContainer.textContent = errors[0];
                errorContainer.style.display = 'block';
            }
        } else {
            element.classList.remove('is-invalid');
            if (this.touched.has(fieldName)) {
                element.classList.add('is-valid');
            }
            
            if (errorContainer) {
                errorContainer.style.display = 'none';
            }
        }
    }
    
    updateAllFieldsDisplay() {
        Object.keys(this.schema).forEach(fieldName => {
            this.updateFieldDisplay(fieldName);
        });
    }
    
    findErrorContainer(element) {
        // Buscar contenedor de error por varios métodos
        let errorContainer = element.parentNode.querySelector('.invalid-feedback');
        if (!errorContainer) {
            errorContainer = element.parentNode.querySelector('[data-error-for="' + element.name + '"]');
        }
        if (!errorContainer) {
            errorContainer = document.querySelector('#' + element.name + '-error');
        }
        
        return errorContainer;
    }
    
    focusFirstError() {
        const firstErrorField = Object.keys(this.errors)[0];
        if (firstErrorField) {
            const element = this.form.querySelector(`[name="${firstErrorField}"], [data-field="${firstErrorField}"]`);
            if (element) {
                element.focus();
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // API pública
    setErrors(errors) {
        this.errors = errors;
        this.updateAllFieldsDisplay();
    }
    
    clearErrors() {
        this.errors = {};
        this.updateAllFieldsDisplay();
    }
    
    getErrors() {
        return this.errors;
    }
    
    isValid() {
        return Object.keys(this.errors).length === 0;
    }
    
    destroy() {
        // Remover event listeners si es necesario
    }
}

/**
 * Esquemas de validación predefinidos para el ecosistema
 */
const ValidationSchemas = {
    // Registro de usuario
    userRegistration: {
        name: { required: true, minLength: 2, maxLength: 50 },
        email: { required: true, email: true },
        password: { required: true, password: 'medium' },
        passwordConfirm: { required: true, passwordConfirm: 'password' },
        role: { required: true, userRole: true },
        terms: { required: true }
    },
    
    // Perfil de emprendedor
    entrepreneurProfile: {
        name: { required: true, minLength: 2, maxLength: 50 },
        email: { required: true, email: true },
        phone: { phone: true },
        cedula: { cedula: true },
        company: { businessName: true },
        nit: { nit: true },
        industry: { required: true, industry: true },
        stage: { required: true, projectStage: true },
        experience: { required: true, min: 0, max: 50 },
        website: { url: true },
        bio: { maxLength: 500 }
    },
    
    // Proyecto
    project: {
        name: { required: true, projectName: true },
        description: { required: true, minLength: 50, maxLength: 2000 },
        industry: { required: true, industry: true },
        stage: { required: true, projectStage: true },
        fundingGoal: { funding: { min: 1000, max: 10000000 } },
        website: { url: true },
        pitch: { url: true }
    },
    
    // Aliado/Mentor
    allyProfile: {
        name: { required: true, minLength: 2, maxLength: 50 },
        email: { required: true, email: true },
        phone: { phone: true },
        expertise: { required: true, minLength: 10, maxLength: 500 },
        experience: { required: true, mentorExperience: 2 },
        availability: { required: true, min: 1, max: 40 },
        hourlyRate: { min: 0, max: 1000000 },
        bio: { maxLength: 1000 }
    },
    
    // Organización
    organization: {
        name: { required: true, businessName: true },
        nit: { required: true, nit: true },
        address: { required: true, minLength: 10, maxLength: 200 },
        phone: { required: true, phone: true },
        email: { required: true, email: true },
        website: { url: true },
        industry: { industry: true },
        description: { maxLength: 1000 }
    }
};

// Instancia global del validador
const validator = new ValidationEngine({
    locale: document.documentElement.lang || 'es'
});

// Registrar validadores asíncronos comunes
validator.registerAsyncValidator('emailAvailable', async (email) => {
    if (!email) return true;
    
    try {
        const response = await fetch('/api/v1/auth/check-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        return data.available ? true : 'Este email ya está registrado';
    } catch (error) {
        return true; // En caso de error, permitir continuar
    }
});

validator.registerAsyncValidator('nitAvailable', async (nit) => {
    if (!nit) return true;
    
    try {
        const response = await fetch('/api/v1/organizations/check-nit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nit })
        });
        
        const data = await response.json();
        return data.available ? true : 'Este NIT ya está registrado';
    } catch (error) {
        return true;
    }
});

// Inicialización automática de formularios
document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('[data-validate]');
    
    forms.forEach(form => {
        const schemaName = form.getAttribute('data-validate');
        const schema = ValidationSchemas[schemaName];
        
        if (schema) {
            const formValidator = new FormValidator(form, schema);
            form._validator = formValidator;
        }
    });
});

// Exportar para uso como módulo
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ValidationEngine,
        FormValidator,
        ValidationSchemas,
        validator
    };
}

// Hacer disponible globalmente
if (typeof window !== 'undefined') {
    window.ValidationEngine = ValidationEngine;
    window.FormValidator = FormValidator;
    window.ValidationSchemas = ValidationSchemas;
    window.validator = validator;
}