/**
 * Ecosistema Emprendimiento - Configuration System
 * ===============================================
 * 
 * Sistema completo de configuración para el ecosistema de emprendimiento
 * Incluye configuraciones por ambiente, APIs, terceros y dominio específico
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

'use strict';

/**
 * Configurador principal del ecosistema
 */
class EcosistemaConfig {
    constructor() {
        // Detectar ambiente actual
        this.environment = this.detectEnvironment();
        
        // Configuraciones base
        this.baseConfig = this.getBaseConfig();
        
        // Configuraciones por ambiente
        this.envConfig = this.getEnvironmentConfig();
        
        // Configuraciones del dominio
        this.domainConfig = this.getDomainConfig();
        
        // Configuraciones de terceros
        this.thirdPartyConfig = this.getThirdPartyConfig();
        
        // Configuraciones de usuario
        this.userConfig = this.getUserConfig();
        
        // Configuraciones de UI/UX
        this.uiConfig = this.getUIConfig();
        
        // Configuraciones de seguridad
        this.securityConfig = this.getSecurityConfig();
        
        // Configuraciones de performance
        this.performanceConfig = this.getPerformanceConfig();
        
        // Merge todas las configuraciones
        this.config = this.mergeConfigurations();
        
        // Validar configuración
        this.validateConfig();
        
        // Exponer configuración globalmente
        this.exposeGlobalConfig();
    }

    /**
     * Detectar ambiente actual
     */
    detectEnvironment() {
        // Detectar por hostname
        const hostname = window.location.hostname;
        
        if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.includes('local')) {
            return 'development';
        }
        
        if (hostname.includes('staging') || hostname.includes('test') || hostname.includes('dev')) {
            return 'staging';
        }
        
        if (hostname.includes('demo') || hostname.includes('preview')) {
            return 'demo';
        }
        
        // Por defecto producción
        return 'production';
    }

    /**
     * Configuraciones base del sistema
     */
    getBaseConfig() {
        return {
            // Información de la aplicación
            app: {
                name: 'Ecosistema Emprendimiento',
                shortName: 'EcoEmprendimiento',
                version: '1.0.0',
                description: 'Plataforma integral para el ecosistema de emprendimiento',
                author: 'Ecosistema Emprendimiento Team',
                keywords: ['emprendimiento', 'startups', 'mentoría', 'innovación'],
                language: 'es',
                locale: 'es-CO',
                timezone: 'America/Bogota',
                currency: 'COP',
                country: 'CO'
            },

            // URLs base
            urls: {
                base: window.location.origin,
                api: '/api/v1',
                websocket: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`,
                cdn: '/static',
                uploads: '/static/uploads',
                avatars: '/static/uploads/avatars',
                documents: '/static/uploads/documents',
                assets: '/static/dist'
            },

            // Configuración de rutas
            routing: {
                mode: 'history',
                base: '/',
                scrollBehavior: 'smooth',
                caseSensitive: false,
                fallback: true,
                linkActiveClass: 'router-link-active',
                linkExactActiveClass: 'router-link-exact-active'
            },

            // Configuración de estado
            state: {
                enablePersistence: true,
                enableSync: true,
                enableTimeTravel: false, // Solo en development
                enableDevTools: false,   // Solo en development
                persistenceKey: 'ecosistema_state',
                syncInterval: 30000,
                maxHistoryEntries: 50,
                enableCompression: true,
                enableEncryption: false
            },

            // Configuración de cache
            cache: {
                enabled: true,
                prefix: 'ecosistema_',
                defaultTTL: 300000, // 5 minutos
                maxSize: 100, // MB
                storageQuota: 50 * 1024 * 1024, // 50MB
                enableServiceWorker: true,
                cacheStrategies: {
                    api: 'networkFirst',
                    assets: 'cacheFirst',
                    images: 'cacheFirst',
                    documents: 'networkFirst'
                }
            }
        };
    }

    /**
     * Configuraciones específicas por ambiente
     */
    getEnvironmentConfig() {
        const configs = {
            development: {
                debug: true,
                logging: {
                    level: 'debug',
                    console: true,
                    api: false,
                    performance: true,
                    websocket: true
                },
                api: {
                    timeout: 60000,
                    retries: 3,
                    baseURL: 'http://localhost:5000/api/v1',
                    enableMocks: false,
                    enableInterceptors: true
                },
                websocket: {
                    url: 'ws://localhost:5000/ws',
                    reconnectAttempts: 10,
                    reconnectDelay: 1000,
                    heartbeatInterval: 30000,
                    enableDebug: true
                },
                performance: {
                    enableMetrics: false,
                    enableProfiler: true,
                    enableBundleAnalyzer: false
                },
                security: {
                    enableCSP: false,
                    enableHTTPS: false,
                    enableHSTS: false,
                    cookieSecure: false,
                    enableXFrameOptions: false
                },
                state: {
                    enableTimeTravel: true,
                    enableDevTools: true
                },
                thirdParty: {
                    googleAnalytics: {
                        enabled: false,
                        trackingId: 'GA_MEASUREMENT_ID_DEV'
                    },
                    sentry: {
                        enabled: false,
                        dsn: 'SENTRY_DSN_DEV'
                    }
                }
            },

            staging: {
                debug: true,
                logging: {
                    level: 'warn',
                    console: true,
                    api: true,
                    performance: false,
                    websocket: false
                },
                api: {
                    timeout: 30000,
                    retries: 3,
                    baseURL: 'https://staging-api.ecosistema.com/api/v1',
                    enableMocks: false,
                    enableInterceptors: true
                },
                websocket: {
                    url: 'wss://staging-ws.ecosistema.com/ws',
                    reconnectAttempts: 5,
                    reconnectDelay: 2000,
                    heartbeatInterval: 30000,
                    enableDebug: false
                },
                performance: {
                    enableMetrics: true,
                    enableProfiler: false,
                    enableBundleAnalyzer: false
                },
                security: {
                    enableCSP: true,
                    enableHTTPS: true,
                    enableHSTS: false,
                    cookieSecure: true,
                    enableXFrameOptions: true
                },
                thirdParty: {
                    googleAnalytics: {
                        enabled: true,
                        trackingId: 'GA_MEASUREMENT_ID_STAGING'
                    },
                    sentry: {
                        enabled: true,
                        dsn: 'SENTRY_DSN_STAGING',
                        environment: 'staging'
                    }
                }
            },

            production: {
                debug: false,
                logging: {
                    level: 'error',
                    console: false,
                    api: true,
                    performance: false,
                    websocket: false
                },
                api: {
                    timeout: 30000,
                    retries: 3,
                    baseURL: 'https://api.ecosistema.com/api/v1',
                    enableMocks: false,
                    enableInterceptors: true
                },
                websocket: {
                    url: 'wss://ws.ecosistema.com/ws',
                    reconnectAttempts: 5,
                    reconnectDelay: 3000,
                    heartbeatInterval: 30000,
                    enableDebug: false
                },
                performance: {
                    enableMetrics: true,
                    enableProfiler: false,
                    enableBundleAnalyzer: false
                },
                security: {
                    enableCSP: true,
                    enableHTTPS: true,
                    enableHSTS: true,
                    cookieSecure: true,
                    enableXFrameOptions: true
                },
                thirdParty: {
                    googleAnalytics: {
                        enabled: true,
                        trackingId: 'GA_MEASUREMENT_ID_PROD'
                    },
                    sentry: {
                        enabled: true,
                        dsn: 'SENTRY_DSN_PROD',
                        environment: 'production'
                    }
                }
            }
        };

        return configs[this.environment] || configs.production;
    }

    /**
     * Configuraciones específicas del dominio de emprendimiento
     */
    getDomainConfig() {
        return {
            // Tipos de usuario del ecosistema
            userTypes: {
                entrepreneur: {
                    name: 'Emprendedor',
                    icon: 'fa-lightbulb',
                    color: '#8b5cf6',
                    permissions: [
                        'create_project',
                        'edit_own_project',
                        'request_mentorship',
                        'schedule_meetings',
                        'upload_documents',
                        'network_connect'
                    ],
                    features: [
                        'project_management',
                        'mentorship_requests',
                        'networking',
                        'document_management',
                        'progress_tracking',
                        'funding_tracker'
                    ],
                    defaultRoute: '/dashboard',
                    allowedRoutes: [
                        '/dashboard',
                        '/projects',
                        '/mentorship',
                        '/network',
                        '/documents',
                        '/calendar',
                        '/profile'
                    ]
                },
                mentor: {
                    name: 'Mentor',
                    icon: 'fa-user-tie',
                    color: '#0d9488',
                    permissions: [
                        'view_projects',
                        'provide_mentorship',
                        'schedule_sessions',
                        'create_reports',
                        'access_mentee_data'
                    ],
                    features: [
                        'mentee_management',
                        'session_scheduling',
                        'progress_monitoring',
                        'report_generation',
                        'expertise_sharing'
                    ],
                    defaultRoute: '/mentorship',
                    allowedRoutes: [
                        '/dashboard',
                        '/mentorship',
                        '/network',
                        '/calendar',
                        '/reports',
                        '/profile'
                    ]
                },
                admin: {
                    name: 'Administrador',
                    icon: 'fa-cog',
                    color: '#374151',
                    permissions: [
                        'manage_users',
                        'manage_projects',
                        'view_analytics',
                        'system_configuration',
                        'data_export',
                        'content_moderation'
                    ],
                    features: [
                        'user_management',
                        'project_oversight',
                        'system_analytics',
                        'content_management',
                        'system_configuration',
                        'reporting_suite'
                    ],
                    defaultRoute: '/admin',
                    allowedRoutes: [
                        '/admin',
                        '/dashboard',
                        '/analytics',
                        '/users',
                        '/projects',
                        '/reports'
                    ]
                },
                client: {
                    name: 'Cliente/Stakeholder',
                    icon: 'fa-briefcase',
                    color: '#ec4899',
                    permissions: [
                        'view_portfolio',
                        'access_reports',
                        'view_impact_metrics',
                        'export_data'
                    ],
                    features: [
                        'portfolio_view',
                        'impact_tracking',
                        'custom_reports',
                        'investment_overview'
                    ],
                    defaultRoute: '/portfolio',
                    allowedRoutes: [
                        '/portfolio',
                        '/reports',
                        '/impact',
                        '/analytics'
                    ]
                }
            },

            // Estados de proyectos
            projectStates: {
                idea: {
                    name: 'Idea',
                    color: '#6b7280',
                    icon: 'fa-lightbulb',
                    description: 'Proyecto en fase de ideación',
                    allowedTransitions: ['planning', 'cancelled']
                },
                planning: {
                    name: 'Planificación',
                    color: '#f59e0b',
                    icon: 'fa-clipboard-list',
                    description: 'Proyecto en planificación',
                    allowedTransitions: ['active', 'cancelled']
                },
                active: {
                    name: 'Activo',
                    color: '#0d6efd',
                    icon: 'fa-play-circle',
                    description: 'Proyecto en desarrollo activo',
                    allowedTransitions: ['review', 'paused', 'cancelled']
                },
                paused: {
                    name: 'Pausado',
                    color: '#fd7e14',
                    icon: 'fa-pause-circle',
                    description: 'Proyecto temporalmente pausado',
                    allowedTransitions: ['active', 'cancelled']
                },
                review: {
                    name: 'En Revisión',
                    color: '#6f42c1',
                    icon: 'fa-search',
                    description: 'Proyecto en proceso de revisión',
                    allowedTransitions: ['active', 'completed', 'cancelled']
                },
                completed: {
                    name: 'Completado',
                    color: '#198754',
                    icon: 'fa-check-circle',
                    description: 'Proyecto completado exitosamente',
                    allowedTransitions: ['archived']
                },
                cancelled: {
                    name: 'Cancelado',
                    color: '#dc3545',
                    icon: 'fa-times-circle',
                    description: 'Proyecto cancelado',
                    allowedTransitions: ['archived']
                },
                archived: {
                    name: 'Archivado',
                    color: '#868e96',
                    icon: 'fa-archive',
                    description: 'Proyecto archivado',
                    allowedTransitions: []
                }
            },

            // Categorías de proyectos
            projectCategories: {
                technology: {
                    name: 'Tecnología',
                    icon: 'fa-laptop-code',
                    color: '#0d6efd',
                    subcategories: ['software', 'hardware', 'ai_ml', 'blockchain', 'iot']
                },
                health: {
                    name: 'Salud',
                    icon: 'fa-heartbeat',
                    color: '#dc3545',
                    subcategories: ['medtech', 'biotech', 'telemedicine', 'wellness']
                },
                education: {
                    name: 'Educación',
                    icon: 'fa-graduation-cap',
                    color: '#198754',
                    subcategories: ['edtech', 'online_learning', 'skills_training']
                },
                finance: {
                    name: 'Finanzas',
                    icon: 'fa-coins',
                    color: '#f59e0b',
                    subcategories: ['fintech', 'payments', 'cryptocurrency', 'insurance']
                },
                sustainability: {
                    name: 'Sostenibilidad',
                    icon: 'fa-leaf',
                    color: '#20c997',
                    subcategories: ['cleantech', 'renewable_energy', 'circular_economy']
                },
                social: {
                    name: 'Impacto Social',
                    icon: 'fa-hands-helping',
                    color: '#6f42c1',
                    subcategories: ['social_enterprise', 'ngo', 'community_development']
                }
            },

            // Tipos de mentoría
            mentorshipTypes: {
                business: {
                    name: 'Desarrollo de Negocio',
                    icon: 'fa-chart-line',
                    color: '#0d6efd',
                    duration: 60, // minutos
                    description: 'Estrategia, modelo de negocio, mercado'
                },
                technical: {
                    name: 'Técnica',
                    icon: 'fa-code',
                    color: '#198754',
                    duration: 90,
                    description: 'Desarrollo técnico, arquitectura, tecnología'
                },
                marketing: {
                    name: 'Marketing',
                    icon: 'fa-bullhorn',
                    color: '#f59e0b',
                    duration: 60,
                    description: 'Estrategia de marketing, branding, comunicación'
                },
                financial: {
                    name: 'Financiera',
                    icon: 'fa-calculator',
                    color: '#dc3545',
                    duration: 75,
                    description: 'Finanzas, inversión, fundraising'
                },
                legal: {
                    name: 'Legal',
                    icon: 'fa-balance-scale',
                    color: '#6f42c1',
                    duration: 60,
                    description: 'Aspectos legales, propiedad intelectual'
                },
                personal: {
                    name: 'Desarrollo Personal',
                    icon: 'fa-user-plus',
                    color: '#20c997',
                    duration: 45,
                    description: 'Liderazgo, soft skills, networking'
                }
            },

            // Métricas del ecosistema
            metrics: {
                projects: {
                    total: { name: 'Total de Proyectos', icon: 'fa-project-diagram' },
                    active: { name: 'Proyectos Activos', icon: 'fa-play-circle' },
                    completed: { name: 'Proyectos Completados', icon: 'fa-check-circle' },
                    success_rate: { name: 'Tasa de Éxito', icon: 'fa-percentage' }
                },
                users: {
                    entrepreneurs: { name: 'Emprendedores', icon: 'fa-lightbulb' },
                    mentors: { name: 'Mentores', icon: 'fa-user-tie' },
                    active_users: { name: 'Usuarios Activos', icon: 'fa-users' },
                    engagement: { name: 'Nivel de Engagement', icon: 'fa-chart-line' }
                },
                mentorship: {
                    sessions: { name: 'Sesiones de Mentoría', icon: 'fa-handshake' },
                    hours: { name: 'Horas de Mentoría', icon: 'fa-clock' },
                    satisfaction: { name: 'Satisfacción', icon: 'fa-star' },
                    matches: { name: 'Matches Exitosos', icon: 'fa-heart' }
                },
                network: {
                    connections: { name: 'Conexiones Realizadas', icon: 'fa-network-wired' },
                    collaborations: { name: 'Colaboraciones', icon: 'fa-handshake' },
                    referrals: { name: 'Referencias', icon: 'fa-share-alt' }
                }
            },

            // Gamificación
            gamification: {
                enabled: true,
                points: {
                    project_created: 100,
                    project_completed: 500,
                    mentorship_session: 50,
                    document_uploaded: 25,
                    connection_made: 30,
                    profile_completed: 75,
                    first_meeting: 100,
                    milestone_reached: 200
                },
                levels: [
                    { name: 'Novato', min: 0, max: 499, icon: 'fa-seedling', color: '#6b7280' },
                    { name: 'Principiante', min: 500, max: 1499, icon: 'fa-leaf', color: '#10b981' },
                    { name: 'Emprendedor', min: 1500, max: 3999, icon: 'fa-rocket', color: '#3b82f6' },
                    { name: 'Innovador', min: 4000, max: 9999, icon: 'fa-lightbulb', color: '#f59e0b' },
                    { name: 'Visionario', min: 10000, max: 24999, icon: 'fa-eye', color: '#8b5cf6' },
                    { name: 'Líder', min: 25000, max: 49999, icon: 'fa-crown', color: '#ef4444' },
                    { name: 'Maestro', min: 50000, max: null, icon: 'fa-trophy', color: '#f97316' }
                ],
                badges: {
                    first_project: { name: 'Primer Proyecto', icon: 'fa-flag', description: 'Creó su primer proyecto' },
                    mentor_rookie: { name: 'Mentor Novato', icon: 'fa-graduation-cap', description: 'Primera sesión de mentoría' },
                    networker: { name: 'Networker', icon: 'fa-users', description: '10 conexiones realizadas' },
                    collaborator: { name: 'Colaborador', icon: 'fa-handshake', description: 'Participó en 5 colaboraciones' },
                    early_adopter: { name: 'Early Adopter', icon: 'fa-star', description: 'Usuario temprano de la plataforma' },
                    thought_leader: { name: 'Líder de Opinión', icon: 'fa-microphone', description: 'Compartió 20 insights' }
                }
            }
        };
    }

    /**
     * Configuraciones de terceros
     */
    getThirdPartyConfig() {
        return {
            // Google Services
            google: {
                clientId: 'GOOGLE_CLIENT_ID',
                apiKey: 'GOOGLE_API_KEY',
                scope: 'profile email',
                calendar: {
                    enabled: true,
                    apiKey: 'GOOGLE_CALENDAR_API_KEY',
                    clientId: 'GOOGLE_CALENDAR_CLIENT_ID',
                    scope: 'https://www.googleapis.com/auth/calendar'
                },
                meet: {
                    enabled: true,
                    autoCreateMeeting: true
                },
                drive: {
                    enabled: true,
                    apiKey: 'GOOGLE_DRIVE_API_KEY',
                    scope: 'https://www.googleapis.com/auth/drive.file'
                },
                maps: {
                    enabled: true,
                    apiKey: 'GOOGLE_MAPS_API_KEY',
                    libraries: ['places', 'geometry']
                }
            },

            // Microsoft Services
            microsoft: {
                clientId: 'MICROSOFT_CLIENT_ID',
                scope: 'user.read',
                teams: {
                    enabled: true,
                    autoCreateMeeting: false
                },
                outlook: {
                    enabled: true,
                    scope: 'https://graph.microsoft.com/calendars.readwrite'
                }
            },

            // Video Conference
            zoom: {
                enabled: true,
                apiKey: 'ZOOM_API_KEY',
                apiSecret: 'ZOOM_API_SECRET',
                webhook: '/webhooks/zoom',
                features: {
                    autoRecord: true,
                    waitingRoom: true,
                    muteOnEntry: true
                }
            },

            // Payment Processing
            stripe: {
                enabled: true,
                publishableKey: 'STRIPE_PUBLISHABLE_KEY',
                currency: 'COP',
                country: 'CO',
                features: {
                    subscriptions: true,
                    connect: true,
                    marketplace: true
                }
            },

            // Communication
            twilio: {
                enabled: true,
                accountSid: 'TWILIO_ACCOUNT_SID',
                features: {
                    sms: true,
                    whatsapp: true,
                    voice: false,
                    video: false
                }
            },

            // Email Service
            sendgrid: {
                enabled: true,
                apiKey: 'SENDGRID_API_KEY',
                fromEmail: 'noreply@ecosistema.com',
                fromName: 'Ecosistema Emprendimiento'
            },

            // Analytics
            googleAnalytics: {
                enabled: true,
                trackingId: 'GA_MEASUREMENT_ID',
                config: {
                    send_page_view: true,
                    anonymize_ip: true,
                    allow_google_signals: false
                }
            },

            // Error Tracking
            sentry: {
                enabled: true,
                dsn: 'SENTRY_DSN',
                environment: this.environment,
                config: {
                    beforeSend: true,
                    maxBreadcrumbs: 50,
                    attachStacktrace: true
                }
            },

            // File Storage
            cloudinary: {
                enabled: true,
                cloudName: 'CLOUDINARY_CLOUD_NAME',
                apiKey: 'CLOUDINARY_API_KEY',
                uploadPreset: 'ecosistema_uploads',
                folder: 'ecosistema'
            },

            // Social Login
            facebook: {
                enabled: true,
                appId: 'FACEBOOK_APP_ID',
                scope: 'email,public_profile'
            },

            linkedin: {
                enabled: true,
                clientId: 'LINKEDIN_CLIENT_ID',
                scope: 'r_liteprofile r_emailaddress'
            },

            // Push Notifications
            firebase: {
                enabled: true,
                config: {
                    apiKey: 'FIREBASE_API_KEY',
                    authDomain: 'ecosistema.firebaseapp.com',
                    projectId: 'ecosistema',
                    storageBucket: 'ecosistema.appspot.com',
                    messagingSenderId: 'FIREBASE_SENDER_ID',
                    appId: 'FIREBASE_APP_ID'
                },
                vapidKey: 'FIREBASE_VAPID_KEY'
            }
        };
    }

    /**
     * Configuraciones específicas por tipo de usuario
     */
    getUserConfig() {
        return {
            entrepreneur: {
                dashboard: {
                    defaultWidgets: [
                        'project_overview',
                        'upcoming_meetings',
                        'mentorship_progress',
                        'recent_documents',
                        'network_suggestions',
                        'funding_tracker'
                    ],
                    layout: 'grid',
                    refreshInterval: 300000 // 5 minutos
                },
                features: {
                    projectManagement: true,
                    mentorshipRequests: true,
                    documentSharing: true,
                    networkingTools: true,
                    progressTracking: true,
                    fundingTools: true,
                    analyticsBasic: true,
                    reportingBasic: true
                },
                limits: {
                    maxProjects: 10,
                    maxMentorshipSessions: 20,
                    maxDocumentSize: 50 * 1024 * 1024, // 50MB
                    maxConnections: 500
                }
            },

            mentor: {
                dashboard: {
                    defaultWidgets: [
                        'mentee_overview',
                        'upcoming_sessions',
                        'session_history',
                        'expertise_areas',
                        'availability_calendar',
                        'performance_metrics'
                    ],
                    layout: 'list',
                    refreshInterval: 180000 // 3 minutos
                },
                features: {
                    menteeManagement: true,
                    sessionScheduling: true,
                    progressMonitoring: true,
                    reportGeneration: true,
                    expertiseSharing: true,
                    availabilityManagement: true,
                    analyticsAdvanced: true,
                    bulkReporting: true
                },
                limits: {
                    maxMentees: 25,
                    maxSessionsPerWeek: 30,
                    maxReportSize: 100 * 1024 * 1024, // 100MB
                    maxExpertiseAreas: 10
                }
            },

            admin: {
                dashboard: {
                    defaultWidgets: [
                        'system_overview',
                        'user_metrics',
                        'project_metrics',
                        'platform_health',
                        'recent_activities',
                        'financial_overview',
                        'security_alerts'
                    ],
                    layout: 'dashboard',
                    refreshInterval: 60000 // 1 minuto
                },
                features: {
                    userManagement: true,
                    systemAnalytics: true,
                    contentModeration: true,
                    systemConfiguration: true,
                    dataExport: true,
                    securityMonitoring: true,
                    financialReporting: true,
                    systemMaintenance: true
                },
                limits: {
                    unlimited: true
                }
            },

            client: {
                dashboard: {
                    defaultWidgets: [
                        'portfolio_overview',
                        'impact_metrics',
                        'investment_performance',
                        'recent_reports',
                        'upcoming_milestones'
                    ],
                    layout: 'executive',
                    refreshInterval: 600000 // 10 minutos
                },
                features: {
                    portfolioView: true,
                    impactTracking: true,
                    customReporting: true,
                    investmentOverview: true,
                    executiveDashboard: true,
                    dataExport: true
                },
                limits: {
                    maxCustomReports: 50,
                    maxDataExports: 10,
                    reportRetention: 365 // días
                }
            }
        };
    }

    /**
     * Configuraciones de UI/UX
     */
    getUIConfig() {
        return {
            // Tema por defecto
            theme: {
                default: 'light',
                available: ['light', 'dark', 'auto'],
                persistence: true,
                systemPreference: true
            },

            // Configuraciones de responsive
            breakpoints: {
                xs: 0,
                sm: 576,
                md: 768,
                lg: 992,
                xl: 1200,
                xxl: 1400
            },

            // Configuraciones de navegación
            navigation: {
                sidebar: {
                    collapsible: true,
                    persistent: true,
                    autoCollapse: true,
                    mobileBreakpoint: 'lg'
                },
                breadcrumbs: {
                    enabled: true,
                    maxItems: 5,
                    showHome: true
                },
                pagination: {
                    defaultSize: 20,
                    maxSize: 100,
                    showSizeSelector: true,
                    showInfo: true
                }
            },

            // Configuraciones de modales
            modals: {
                backdrop: true,
                keyboard: true,
                focus: true,
                animation: true,
                size: 'md'
            },

            // Configuraciones de notificaciones
            notifications: {
                position: 'top-right',
                duration: 5000,
                maxVisible: 5,
                showProgress: true,
                pauseOnHover: true,
                closeOnClick: true,
                animation: 'slide'
            },

            // Configuraciones de formularios
            forms: {
                autoSave: {
                    enabled: true,
                    interval: 30000,
                    showIndicator: true
                },
                validation: {
                    realTime: true,
                    showErrors: 'onBlur',
                    highlightErrors: true
                },
                fileUpload: {
                    dragDrop: true,
                    preview: true,
                    progress: true,
                    multiSelect: true
                }
            },

            // Configuraciones de tablas
            tables: {
                responsive: true,
                pagination: true,
                sorting: true,
                filtering: true,
                export: true,
                selection: 'multiple',
                resizable: true
            },

            // Configuraciones de gráficos
            charts: {
                responsive: true,
                animation: true,
                tooltips: true,
                legends: true,
                downloadable: true,
                theme: 'auto'
            },

            // Configuraciones de editor
            editor: {
                toolbar: 'full',
                spellcheck: true,
                wordCount: true,
                autoSave: true,
                collaborative: true,
                imageUpload: true
            },

            // Configuraciones de calendario
            calendar: {
                defaultView: 'month',
                firstDay: 1, // Lunes
                timeFormat: '24h',
                weekNumbers: false,
                businessHours: {
                    start: '08:00',
                    end: '18:00',
                    days: [1, 2, 3, 4, 5] // Lunes a Viernes
                }
            },

            // Configuraciones de chat
            chat: {
                realTime: true,
                typing: true,
                readReceipts: true,
                fileSharing: true,
                emojis: true,
                mentions: true,
                threads: true
            },

            // Configuraciones de loading
            loading: {
                spinner: 'dots',
                overlay: true,
                text: true,
                progress: false,
                timeout: 30000
            }
        };
    }

    /**
     * Configuraciones de seguridad
     */
    getSecurityConfig() {
        return {
            // Autenticación
            auth: {
                sessionTimeout: 8 * 60 * 60 * 1000, // 8 horas
                refreshThreshold: 15 * 60 * 1000,    // 15 minutos
                maxLoginAttempts: 5,
                lockoutDuration: 15 * 60 * 1000,     // 15 minutos
                passwordRequirements: {
                    minLength: 8,
                    requireUppercase: true,
                    requireLowercase: true,
                    requireNumbers: true,
                    requireSpecialChars: true,
                    preventCommon: true
                },
                twoFactor: {
                    enabled: false,
                    methods: ['totp', 'sms', 'email'],
                    backup: true
                }
            },

            // CSRF Protection
            csrf: {
                enabled: true,
                cookieName: '_csrf_token',
                headerName: 'X-CSRF-Token',
                paramName: '_token'
            },

            // Content Security Policy
            csp: {
                enabled: this.environment === 'production',
                directives: {
                    'default-src': ["'self'"],
                    'script-src': ["'self'", "'unsafe-inline'", 'https://apis.google.com'],
                    'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
                    'img-src': ["'self'", 'data:', 'https:'],
                    'font-src': ["'self'", 'https://fonts.gstatic.com'],
                    'connect-src': ["'self'", 'https://api.ecosistema.com', 'wss://ws.ecosistema.com'],
                    'media-src': ["'self'"],
                    'object-src': ["'none'"],
                    'base-uri': ["'self'"],
                    'form-action': ["'self'"]
                }
            },

            // Rate Limiting
            rateLimit: {
                enabled: true,
                requests: 100,
                window: 15 * 60 * 1000, // 15 minutos
                skipSuccessfulRequests: false,
                skipFailedRequests: false
            },

            // Data Encryption
            encryption: {
                enabled: false, // Solo si es necesario
                algorithm: 'AES-256-GCM',
                keyRotation: 30 * 24 * 60 * 60 * 1000 // 30 días
            },

            // Privacy
            privacy: {
                cookieConsent: true,
                dataRetention: 365 * 24 * 60 * 60 * 1000, // 1 año
                rightToForget: true,
                dataPortability: true,
                auditLog: true
            }
        };
    }

    /**
     * Configuraciones de performance
     */
    getPerformanceConfig() {
        return {
            // Lazy Loading
            lazyLoading: {
                enabled: true,
                threshold: 0.1,
                rootMargin: '50px',
                images: true,
                components: true,
                routes: true
            },

            // Code Splitting
            codeSplitting: {
                enabled: true,
                strategy: 'route',
                chunks: 'async',
                maxSize: 250000 // 250KB
            },

            // Caching
            http: {
                timeout: 30000,
                retries: 3,
                retryDelay: 1000,
                cache: {
                    enabled: true,
                    ttl: 300000, // 5 minutos
                    maxSize: 50 * 1024 * 1024 // 50MB
                }
            },

            // Image Optimization
            images: {
                lazy: true,
                webp: true,
                responsive: true,
                placeholder: 'blur',
                quality: 80,
                formats: ['webp', 'jpg', 'png']
            },

            // Bundle Optimization
            bundle: {
                compression: true,
                minification: true,
                treeshaking: true,
                sourcemaps: this.environment === 'development'
            },

            // Service Worker
            serviceWorker: {
                enabled: this.environment === 'production',
                strategy: 'networkFirst',
                offline: true,
                precache: ['/', '/dashboard', '/projects']
            },

            // Monitoring
            monitoring: {
                enabled: true,
                metrics: {
                    vitals: true,
                    navigation: true,
                    resources: true,
                    errors: true
                },
                sampling: this.environment === 'production' ? 0.1 : 1.0
            }
        };
    }

    /**
     * Merge todas las configuraciones
     */
    mergeConfigurations() {
        return {
            ...this.baseConfig,
            ...this.envConfig,
            domain: this.domainConfig,
            thirdParty: this.thirdPartyConfig,
            userTypes: this.userConfig,
            ui: this.uiConfig,
            security: this.securityConfig,
            performance: this.performanceConfig,
            
            // Meta información
            meta: {
                environment: this.environment,
                buildTime: new Date().toISOString(),
                version: this.baseConfig.app.version,
                features: this.getEnabledFeatures()
            }
        };
    }

    /**
     * Obtener características habilitadas
     */
    getEnabledFeatures() {
        const features = [];
        
        if (this.config?.state?.enableTimeTravel) features.push('timeTravel');
        if (this.config?.thirdParty?.google?.enabled) features.push('googleIntegration');
        if (this.config?.domain?.gamification?.enabled) features.push('gamification');
        if (this.config?.performance?.serviceWorker?.enabled) features.push('offlineSupport');
        if (this.config?.security?.auth?.twoFactor?.enabled) features.push('twoFactorAuth');
        
        return features;
    }

    /**
     * Validar configuración
     */
    validateConfig() {
        const required = [
            'app.name',
            'app.version',
            'urls.base',
            'urls.api'
        ];

        const missing = required.filter(path => {
            return !this.getNestedValue(this.config, path);
        });

        if (missing.length > 0) {
            // // console.error('Configuraciones requeridas faltantes:', missing);
            throw new Error(`Configuraciones faltantes: ${missing.join(', ')}`);
        }

        // Validaciones específicas por ambiente
        if (this.environment === 'production') {
            this.validateProductionConfig();
        }
    }

    /**
     * Validar configuración de producción
     */
    validateProductionConfig() {
        const productionRequired = [
            'security.csrf.enabled',
            'security.csp.enabled',
            'performance.serviceWorker.enabled'
        ];

        const issues = [];

        productionRequired.forEach(path => {
            if (!this.getNestedValue(this.config, path)) {
                issues.push(`${path} debe estar habilitado en producción`);
            }
        });

        if (this.config.debug) {
            issues.push('Debug debe estar deshabilitado en producción');
        }

        if (issues.length > 0) {
            // // console.error('Problemas de configuración de producción:', issues);
        }
    }

    /**
     * Exponer configuración globalmente
     */
    exposeGlobalConfig() {
        // Exponer configuración completa
        window.EcosistemaConfig = this.config;
        
        // Exponer configuraciones específicas para facilidad de uso
        window.APP_CONFIG = this.config.app;
        window.API_CONFIG = this.config.api;
        window.UI_CONFIG = this.config.ui;
        
        // Función utilitaria para obtener configuración
        window.getConfig = (path, defaultValue = null) => {
            return this.getNestedValue(this.config, path) || defaultValue;
        };

        // Función para verificar si una característica está habilitada
        window.isFeatureEnabled = (feature) => {
            return this.config.meta.features.includes(feature);
        };

        // Función para obtener configuración por tipo de usuario
        window.getUserConfig = (userType = null) => {
            const type = userType || window.App?.userType || 'entrepreneur';
            return this.config.userTypes[type] || this.config.userTypes.entrepreneur;
        };
    }

    /**
     * Obtener valor anidado en objeto
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }

    /**
     * Obtener configuración por clave
     */
    get(path, defaultValue = null) {
        return this.getNestedValue(this.config, path) || defaultValue;
    }

    /**
     * Verificar si está en modo debug
     */
    isDebug() {
        return this.config.debug === true;
    }

    /**
     * Verificar si está en producción
     */
    isProduction() {
        return this.environment === 'production';
    }

    /**
     * Verificar si está en desarrollo
     */
    isDevelopment() {
        return this.environment === 'development';
    }

    /**
     * Obtener configuración para un servicio específico
     */
    getServiceConfig(serviceName) {
        const serviceConfigs = {
            api: {
                baseURL: this.config.api.baseURL,
                timeout: this.config.api.timeout,
                retries: this.config.api.retries
            },
            websocket: {
                url: this.config.websocket.url,
                reconnectAttempts: this.config.websocket.reconnectAttempts,
                heartbeatInterval: this.config.websocket.heartbeatInterval
            },
            cache: {
                enabled: this.config.cache.enabled,
                defaultTTL: this.config.cache.defaultTTL,
                maxSize: this.config.cache.maxSize
            }
        };

        return serviceConfigs[serviceName] || null;
    }
}

// ============================================================================
// INICIALIZACIÓN Y EXPORTACIÓN
// ============================================================================

// Crear instancia global de configuración
window.ConfigManager = new EcosistemaConfig();

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EcosistemaConfig;
}

// Hacer disponible globalmente
window.EcosistemaConfig = EcosistemaConfig;

// Log de inicialización
// // console.log(`⚙️ Configuración cargada para ambiente: ${window.ConfigManager.environment}`);
// // console.log(`🎯 Características habilitadas:`, window.ConfigManager.config.meta.features);