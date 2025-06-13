/**
 * Ecosistema Emprendimiento - Settings Manager Module
 * ===================================================
 * 
 * Módulo para gestionar la configuración de la aplicación.
 * Permite a los usuarios personalizar su experiencia y a los
 * administradores modificar la configuración del sistema.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js
 */

'use strict';

class SettingsManager {
    constructor(container, app) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        
        if (!this.container) {
            throw new Error('Container for SettingsManager not found');
        }

        this.app = app || window.EcosistemaApp;
        this.main = this.app?.main || window.App;
        this.state = this.app?.state || window.EcosistemaStateManager;
        this.config = window.getConfig ? window.getConfig('modules.settingsManager', {}) : {};

        // Configuración del módulo
        this.moduleConfig = {
            enableUserProfileSettings: true,
            enableAppThemeSettings: true,
            enableNotificationSettings: true,
            enableDataPrivacySettings: true,
            userSettingsEndpoint: '/api/v1/users/settings',
            adminSettingsEndpoint: '/api/v1/admin/settings',
            availableLanguages: ['es', 'en'],
            defaultLanguage: 'es',
            themes: ['light', 'dark', 'system'],
            defaultTheme: 'light',
            ...this.config
        };

        // Estado interno del módulo
        this.moduleState = {
            isInitialized: false,
            isLoading: false,
            settings: {
                language: this.main.currentUser?.language || this.moduleConfig.defaultLanguage,
                theme: this.main.currentUser?.theme || this.moduleConfig.defaultTheme,
                notifications: {
                    email: true,
                    push: true,
                    sms: false
                },
                dataPrivacy: {
                    trackUsage: true,
                    shareData: false
                }
            }
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
            console.log('⚙️ Inicializando Settings Manager');
            this.showLoader(true, 'Cargando configuración...');

            this.createStructure();
            this.bindElements();
            this.setupEventListeners();

            await this.loadSettings();
            this.renderSettings();
            
            this.moduleState.isInitialized = true;
            console.log('✅ Settings Manager inicializado');
        } catch (error) {
            console.error('❌ Error inicializando Settings Manager:', error);
            this.showError('Error al inicializar la configuración', error.message);
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Crear estructura DOM del módulo
     */
    createStructure() {
        this.container.innerHTML = `
            <div class="settings-manager" data-module="settings-manager">
                <div class="settings-header">
                    <h3><i class="fas fa-cogs text-muted me-2"></i>Configuración</h3>
                </div>

                <div class="settings-content mt-3">
                    <!-- Configuración de perfil -->
                    ${this.moduleConfig.enableUserProfileSettings ? `
                        <div class="setting-section">
                            <h4>Perfil de Usuario</h4>
                            <div class="mb-3">
                                <label for="languageSelect" class="form-label">Idioma</label>
                                <select class="form-select form-select-sm" id="languageSelect" data-setting="language">
                                    ${this.moduleConfig.availableLanguages.map(lang => `
                                        <option value="${lang}">${lang}</option>
                                    `).join('')}
                                </select>
                            </div>
                        </div>
                    ` : ''}

                    <!-- Configuración de tema -->
                    ${this.moduleConfig.enableAppThemeSettings ? `
                        <div class="setting-section">
                            <h4>Tema de la Aplicación</h4>
                            <div class="mb-3">
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" id="themeSwitch" data-setting="theme">
                                    <label class="form-check-label" for="themeSwitch">Tema Oscuro</label>
                                </div>
                            </div>
                        </div>
                    ` : ''}

                    <!-- Configuración de notificaciones -->
                    ${this.moduleConfig.enableNotificationSettings ? `
                        <div class="setting-section">
                            <h4>Notificaciones</h4>
                            <div class="mb-2">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="emailNotifications" data-setting="emailNotifications">
                                    <label class="form-check-label" for="emailNotifications">Recibir notificaciones por email</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="pushNotifications" data-setting="pushNotifications">
                                    <label class="form-check-label" for="pushNotifications">Recibir notificaciones push</label>
                                </div>
                                 <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="smsNotifications" data-setting="smsNotifications">
                                    <label class="form-check-label" for="smsNotifications">Recibir notificaciones por SMS</label>
                                </div>
                            </div>
                        </div>
                    ` : ''}

                    <!-- Configuración de privacidad -->
                    ${this.moduleConfig.enableDataPrivacySettings ? `
                        <div class="setting-section">
                            <h4>Privacidad de Datos</h4>
                            <div class="mb-2">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="trackUsage" data-setting="trackUsage">
                                    <label class="form-check-label" for="trackUsage">Permitir seguimiento de uso</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="shareData" data-setting="shareData">
                                    <label class="form-check-label" for="shareData">Compartir datos anónimos con la comunidad</label>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                </div>

                <div class="settings-actions mt-3">
                    <button class="btn btn-primary" data-action="save-settings">
                        <i class="fas fa-save me-2"></i>Guardar
                    </button>
                </div>

                <div class="settings-loader d-none">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Guardando configuración...</p>
                </div>
            </div>
        `;
    }

    /**
     * Obtener referencias a elementos DOM
     */
    bindElements() {
        this.elements = {
            languageSelect: this.container.querySelector('#languageSelect'),
            themeSwitch: this.container.querySelector('#themeSwitch'),
            emailNotifications: this.container.querySelector('#emailNotifications'),
            pushNotifications: this.container.querySelector('#pushNotifications'),
            smsNotifications: this.container.querySelector('#smsNotifications'),
            trackUsage: this.container.querySelector('#trackUsage'),
            shareData: this.container.querySelector('#shareData'),
            saveButton: this.container.querySelector('[data-action="save-settings"]'),
            loader: this.container.querySelector('.settings-loader')
        };
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        this.elements.saveButton?.addEventListener('click', () => {
            this.saveSettings();
        });

        this.elements.languageSelect?.addEventListener('change', (e) => {
            this.moduleState.settings.language = e.target.value;
        });

        this.elements.themeSwitch?.addEventListener('change', (e) => {
            const theme = e.target.checked ? 'dark' : 'light';
            this.moduleState.settings.theme = theme;
        });

        this.elements.emailNotifications?.addEventListener('change', (e) => {
            this.moduleState.settings.notifications.email = e.target.checked;
        });

         this.elements.smsNotifications?.addEventListener('change', (e) => {
            this.moduleState.settings.notifications.sms = e.target.checked;
        });

        this.elements.pushNotifications?.addEventListener('change', (e) => {
            this.moduleState.settings.notifications.push = e.target.checked;
        });

        this.elements.trackUsage?.addEventListener('change', (e) => {
            this.moduleState.settings.dataPrivacy.trackUsage = e.target.checked;
        });

        this.elements.shareData?.addEventListener('change', (e) => {
            this.moduleState.settings.dataPrivacy.shareData = e.target.checked;
        });
    }

    /**
     * Cargar configuración del usuario
     */
    async loadSettings() {
        try {
            const settings = await this.main.http.get(this.moduleConfig.userSettingsEndpoint);
            this.moduleState.settings = { ...this.moduleState.settings, ...settings };
            this.renderSettings();
        } catch (error) {
            console.error('Error cargando configuración:', error);
            this.showError('No se pudo cargar la configuración.');
        }
    }

    /**
     * Renderizar configuración
     */
    renderSettings() {
        if (this.elements.languageSelect) {
            this.elements.languageSelect.value = this.moduleState.settings.language;
        }

        if (this.elements.themeSwitch) {
            this.elements.themeSwitch.checked = this.moduleState.settings.theme === 'dark';
            this.applyTheme();
        }

        if (this.elements.emailNotifications) {
            this.elements.emailNotifications.checked = this.moduleState.settings.notifications.email;
        }

         if (this.elements.smsNotifications) {
            this.elements.smsNotifications.checked = this.moduleState.settings.notifications.sms;
        }

        if (this.elements.pushNotifications) {
            this.elements.pushNotifications.checked = this.moduleState.settings.notifications.push;
        }

        if (this.elements.trackUsage) {
            this.elements.trackUsage.checked = this.moduleState.settings.dataPrivacy.trackUsage;
        }

        if (this.elements.shareData) {
            this.elements.shareData.checked = this.moduleState.settings.dataPrivacy.shareData;
        }
    }

    /**
     * Guardar configuración
     */
    async saveSettings() {
        this.showLoader(true);
        try {
            await this.main.http.post(this.moduleConfig.userSettingsEndpoint, this.moduleState.settings);
            this.main.notifications.success('Configuración guardada correctamente.');
            this.applyTheme();
        } catch (error) {
            console.error('Error guardando configuración:', error);
            this.showError('No se pudo guardar la configuración.');
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Aplicar tema visual
     */
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.moduleState.settings.theme);
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
        this.eventListeners.forEach((handler, element) => {
            element.removeEventListener(handler.event, handler.callback);
        });
        this.container.innerHTML = '';
        this.moduleState.isInitialized = false;
        console.log('🧹 Settings Manager destruido');
    }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SettingsManager;
} else {
    window.SettingsManager = SettingsManager;
}

// Inicialización automática si EcosistemaApp está disponible
document.addEventListener('DOMContentLoaded', () => {
    const settingsManagerContainer = document.getElementById('settings-manager-container');
    if (settingsManagerContainer && window.EcosistemaApp) {
        window.EcosistemaApp.settingsManager = new SettingsManager(settingsManagerContainer, window.EcosistemaApp);
    }
});
